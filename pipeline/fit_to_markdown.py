#!/usr/bin/env python3
"""Converte un file .fit Garmin nel riassunto Markdown che il coach legge.

Il prodotto e' il **Markdown**: un paio di chili di testo con metadati, split al
chilometro e lap registrati. Il JSON con la timeseries completa (~1.2 MB) si
ottiene solo chiedendolo con `--json`, e serve a guardare dentro a una singola
attivita' quando un numero non torna.

    python pipeline/fit_to_markdown.py attivita.fit riassunto.md
    python pipeline/fit_to_markdown.py attivita.fit riassunto.md --json dump.json

Questo file e' l'orchestratore: legge (`fit_reader`), calcola
(`activity_metrics`), scrive (`activity_markdown`).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import mean

from fitparse import FitFile

sys.path.insert(0, str(Path(__file__).resolve().parent))

from activity_markdown import write_markdown  # noqa: E402
from activity_metrics import (  # noqa: E402
    compute_ascent_from_altitude,
    compute_decoupling,
    compute_grade_adjusted_pace,
    compute_hr_bands,
    compute_splits,
    scale_splits,
    segmenti_corretti,
)
from fit_reader import (  # noqa: E402
    extract_laps,
    extract_summary,
    extract_timeseries,
    prepare_input_path,
    safe_val,
)


def convert(in_path, md_path, json_path=None, prefer_fit=False,
            ascent_method='auto'):
    fit = FitFile(in_path)
    summary = extract_summary(fit)




    timeseries_raw = extract_timeseries(fit)
    timeseries_out = []
    for r in timeseries_raw:
        out_r = {k: v for k, v in r.items() if k != "ts"}
        timeseries_out.append(out_r)

    # derive elapsed and moving times from timeseries to avoid incorrect FIT summary values
    if timeseries_raw:
        first_ts = timeseries_raw[0].get('ts')
        last_ts = timeseries_raw[-1].get('ts')
        try:
            elapsed_s = (last_ts - first_ts).total_seconds() if first_ts and last_ts else None
        except Exception:
            elapsed_s = None
        # moving time: sum intervals where distance increases (treat small noise as movement threshold)
        moving_s = 0.0
        prev = timeseries_raw[0]
        for cur in timeseries_raw[1:]:
            try:
                dt = (cur.get('ts') - prev.get('ts')).total_seconds()
            except Exception:
                dt = 0
            dist_prev = prev.get('distance_m') or 0.0
            dist_cur = cur.get('distance_m') or 0.0
            if dist_cur - dist_prev > 0.5:
                moving_s += dt
            prev = cur
        # prefer timeseries-derived elapsed/moving times (more reliable)
        if elapsed_s is not None:
            summary['elapsed_time_s'] = elapsed_s
        if moving_s is not None:
            # always prefer timeseries-derived moving time (overrides null FIT field)
            summary['moving_time_s'] = round(moving_s, 1) if moving_s > 0 else summary.get('moving_time_s')
        # ensure duration_s exists (use moving time if available)
        if summary.get('duration_s') is None and summary.get('moving_time_s') is not None:
            summary['duration_s'] = summary.get('moving_time_s')

    # compute overall stats from timeseries_raw
    hr_vals_all = [r["heart_rate"] for r in timeseries_raw if r.get("heart_rate") is not None]
    cad_vals_all = [r["cadence"] for r in timeseries_raw if r.get("cadence") is not None]
    if hr_vals_all:
        summary["avg_hr"] = mean(hr_vals_all)
        summary["max_hr"] = max(hr_vals_all)
        summary["min_hr"] = min(hr_vals_all)
    else:
        summary["avg_hr"] = summary.get("avg_hr")
        summary["max_hr"] = summary.get("max_hr")
        summary["min_hr"] = summary.get("min_hr")
    if cad_vals_all:
        summary["avg_cadence"] = mean(cad_vals_all)
        summary["max_cadence"] = max(cad_vals_all)
    else:
        summary["avg_cadence"] = summary.get("avg_cadence")
        summary["max_cadence"] = summary.get("max_cadence")

    # Il dislivello buono e' quello che l'orologio scrive nel file: lo
    # calcola con il proprio barometro. Il ricalcolo dai campioni di quota
    # serve solo quando il file non lo dichiara, e su questo archivio se ne
    # discosta di circa il 7% mediano.
    stima = compute_ascent_from_altitude(timeseries_raw)
    summary['ascent_recomputed_m'] = stima[0]
    summary['descent_recomputed_m'] = stima[1]

    fit_asc = summary.get('fit_total_ascent_m')
    usa_dispositivo = fit_asc is not None and ascent_method in ('auto', 'fit')
    if prefer_fit and fit_asc is not None:
        usa_dispositivo = True
    if ascent_method == 'recomputed':
        usa_dispositivo = False

    if usa_dispositivo:
        summary['total_ascent_m'] = float(fit_asc)
        fit_desc = summary.get('fit_total_descent_m')
        summary['total_descent_m'] = float(fit_desc) if fit_desc is not None else None
        chosen = 'device'
    else:
        summary['total_ascent_m'], summary['total_descent_m'] = stima
        chosen = 'recomputed'
        if ascent_method == 'fit':
            # richiesto esplicitamente il dato del dispositivo, ma non c'e'
            chosen = 'recomputed'

    summary['total_ascent_m_source'] = chosen

    bande = compute_hr_bands(timeseries_raw)
    if bande:
        summary['hr_bands_s'] = bande

    # I segmenti corretti per la pendenza servono sia al passo equivalente
    # sia al decoupling: si calcolano una volta sola.
    segmenti = segmenti_corretti(timeseries_raw)
    gap = compute_grade_adjusted_pace(segmenti)
    if gap:
        summary['grade_adjusted_pace_s_km'] = gap

    dec = compute_decoupling(
        segmenti,
        sub_sport=summary.get('sub_sport'),
        ascent_m=summary.get('total_ascent_m'),
        distance_m=summary.get('distance_m'),
    )
    if dec is not None:
        summary['decoupling_pct'] = dec

    splits_km = compute_splits(timeseries_raw, 1000)

    # scale per-split elevation gains/losses to match chosen total when appropriate
    try:
        total_ascent = float(summary.get('total_ascent_m') or 0.0)
    except Exception:
        total_ascent = 0.0
    try:
        total_descent = float(summary.get('total_descent_m') or 0.0)
    except Exception:
        total_descent = 0.0

    sum_split_ascent = sum([(s.get('elevation_gain_m') or 0.0) for s in splits_km])
    sum_split_descent = sum([(s.get('elevation_loss_m') or 0.0) for s in splits_km])


    # apply scaling for ascent and descent
    _fa = scale_splits(splits_km, total_ascent, sum_split_ascent, 'elevation_gain_m')
    _fd = scale_splits(splits_km, total_descent, sum_split_descent, 'elevation_loss_m')
    laps = extract_laps(fit)

    # Il Markdown e' il prodotto: se fallisce, fallisce la conversione.
    # Prima stava in un `try/except: pass`, e un errore qui usciva dallo
    # script come successo lasciando a chi chiamava il compito di
    # accorgersi del file mancante.
    write_markdown(md_path, summary, splits_km, laps)

    if json_path:
        out = {"file": in_path, "summary": summary,
               "timeseries": timeseries_out, "splits_km": splits_km,
               "laps": laps}
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    return

def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("infile", help="File .fit da convertire")
    p.add_argument("outfile", help="Riassunto Markdown da scrivere")
    p.add_argument("--json", dest="json_path",
                   help="Scrive anche il JSON con la timeseries completa (~1.2 MB)")
    p.add_argument("--prefer-fit-totals", action="store_true",
                   help="Usa il dislivello dichiarato dal FIT anche quando ascent-method direbbe altro")
    p.add_argument("--ascent-method", choices=("auto", "fit", "recomputed"),
                   default="auto",
                   help="auto: il valore del dispositivo se c'e', altrimenti il "
                        "ricalcolo dai campioni di quota")
    args = p.parse_args()

    prepared_path, cleanup = prepare_input_path(args.infile)
    try:
        convert(prepared_path, args.outfile, json_path=args.json_path,
                prefer_fit=args.prefer_fit_totals, ascent_method=args.ascent_method)
    finally:
        if cleanup and prepared_path and os.path.exists(prepared_path):
            try:
                os.remove(prepared_path)
            except OSError:
                pass


if __name__ == "__main__":
    main()
