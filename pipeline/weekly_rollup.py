#!/usr/bin/env python3
"""Genera `training_data/weekly.md`: una riga per settimana, dai dati reali.

Il problema: `plans/weeks/` cresce di un file a settimana e nessuno li riassume.
Per farsi il quadro dell'ultimo trimestre il coach doveva aprirne dodici, circa
87 KB di prosa, per estrarne dodici numeri.

Qui i numeri arrivano dalle **attivita' convertite**, non dai file settimana:
niente da parsare, niente che vada fuori sincrono se il coach cambia il modo di
scrivere un piano. E' il carico che l'atleta ha davvero sostenuto, mentre i file
settimana restano la fonte del *perche'*.

    pipeline/.venv/bin/python pipeline/weekly_rollup.py andrea

Lanciato da `run_pipeline.py` a ogni sincronizzazione, insieme allo split per
trimestre.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import profile_stats  # noqa: E402

# Quante settimane tenere nel file. Un anno abbondante: oltre, il dettaglio
# settimanale non serve piu' a nessuna decisione e i file trimestrali coprono
# gia' lo storico.
SETTIMANE_MAX = 60


def lunedi(d: datetime) -> date:
    g = d.date()
    return g - timedelta(days=g.weekday())


def corsa(a: dict) -> bool:
    return (a.get("activity_type") or "").startswith("running")


def raggruppa(attivita: list[dict]) -> dict[date, dict]:
    settimane: dict[date, dict] = defaultdict(
        lambda: {"km": 0.0, "sec": 0, "dplus": 0.0, "n": 0, "n_corsa": 0,
                 "km_corsa": 0.0, "hr": [], "lunga_km": 0.0, "tipi": defaultdict(int),
                 "terreni": defaultdict(int), "bande": defaultdict(int)})
    for a in attivita:
        s = settimane[lunedi(a["date"])]
        s["km"] += a.get("distance_km") or 0.0
        s["sec"] += a.get("duration_s") or 0
        s["dplus"] += a.get("ascent_m") or 0.0
        s["n"] += 1
        s["tipi"][a.get("activity_type") or "?"] += 1
        if a.get("terrain"):
            s["terreni"][a["terrain"]] += 1
        if a.get("avg_hr"):
            s["hr"].append(a["avg_hr"])
        for banda, secondi in (a.get("hr_bands") or {}).items():
            s["bande"][banda] += secondi
        if corsa(a):
            s["n_corsa"] += 1
            s["km_corsa"] += a.get("distance_km") or 0.0
            s["lunga_km"] = max(s["lunga_km"], a.get("distance_km") or 0.0)
    return settimane


def freccia(valore: float, precedente: float | None) -> str:
    """Direzione rispetto alla settimana prima, con una soglia morta al 5%.

    Senza soglia ogni oscillazione naturale diventerebbe una tendenza, e una
    colonna che segnala sempre qualcosa non segnala niente.
    """
    if precedente is None or precedente <= 0:
        return " "
    delta = (valore - precedente) / precedente
    if delta > 0.05:
        return "↑"
    if delta < -0.05:
        return "↓"
    return "="


def render(person: str, attivita: list[dict], fc_max: int | None = None,
           fc_polso_ok: bool | None = None) -> str:
    settimane = raggruppa(attivita)
    chiavi = sorted(settimane)[-SETTIMANE_MAX:]

    righe = [
        f"# Riepilogo settimanale — {person}",
        "",
        f"*Generato: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        "Una riga per settimana, ricavata dalle attività convertite: è il carico",
        "**effettivamente sostenuto**. Il piano previsto e il perché delle scelte",
        "stanno nei file in `plans/weeks/`, uno per settimana.",
        "",
        "Le frecce confrontano con la settimana precedente, con una soglia del 5%.",
        "",
        "| Settimana | Sedute | Corse | km | km corsa | Tempo | D+ | Lunga | FC media |",
        "|-----------|-------:|------:|---:|---------:|------:|---:|------:|---------:|",
    ]

    prec = None
    for k in chiavi:
        s = settimane[k]
        km = s["km"]
        hr = f"{statistics.mean(s['hr']):.0f}" if s["hr"] else "—"
        righe.append(
            f"| {k.isoformat()} | {s['n']} | {s['n_corsa']} | "
            f"{km:.1f}{freccia(km, prec)} | {s['km_corsa']:.1f} | "
            f"{s['sec'] / 3600:.1f}h | {s['dplus']:.0f} m | "
            f"{s['lunga_km']:.1f} | {hr} |"
        )
        prec = km

    # --- blocchi di 4 settimane: e' la scala su cui si legge il carico -------
    righe += ["", "## Blocchi di 4 settimane", "",
              "| Periodo | Sedute | km | km/sett | D+ | Tempo |",
              "|---------|-------:|---:|--------:|---:|------:|"]
    for i in range(len(chiavi) - 1, -1, -4):
        blocco = chiavi[max(0, i - 3): i + 1]
        if len(blocco) < 2:
            continue
        agg = [settimane[b] for b in blocco]
        km = sum(a["km"] for a in agg)
        righe.append(
            f"| {blocco[0].isoformat()} → {blocco[-1].isoformat()} | "
            f"{sum(a['n'] for a in agg)} | {km:.0f} | {km / len(blocco):.1f} | "
            f"{sum(a['dplus'] for a in agg):.0f} m | "
            f"{sum(a['sec'] for a in agg) / 3600:.1f}h |"
        )

    # --- distribuzione di intensita' -----------------------------------------
    # E' cio' su cui si giudica se una settimana e' polarizzata o tutta in mezzo:
    # "FC media 146" non lo dice, la ripartizione per zona si'.
    if fc_max:
        righe += ["", f"## Distribuzione per zona (FC massima {fc_max} bpm)", ""]
        if fc_polso_ok is False:
            righe += [
                "> ⚠️ Il profilo dichiara la **FC da polso inaffidabile** su questo",
                "> atleta (cadence lock). Sotto sforzo il sensore legge i passi invece",
                "> del battito, quindi questa ripartizione **sovrastima l'intensità**:",
                "> tempo attribuito a Z3-Z5 che in realtà era più basso. Utile come",
                "> tendenza fra settimane, non come misura. Una fascia toracica la",
                "> renderebbe attendibile.",
                "",
            ]
        elif fc_polso_ok is None:
            righe += [
                "> ⚠️ Non è stato verificato se la FC da polso di questo atleta sia",
                "> attendibile. Se il sensore soffre di *cadence lock*, questa",
                "> ripartizione sovrastima l'intensità. Il test richiede mezzo minuto",
                "> di corsa: `coach/workflows/onboard.md`.",
                "",
            ]
        righe += ["Percentuale del tempo con frequenza cardiaca registrata.", "",
                  "| Settimana | Z1 | Z2 | Z3 | Z4 | Z5 | Tempo in zona |",
                  "|-----------|---:|---:|---:|---:|---:|--------------:|"]
        for k in chiavi[-12:]:
            zone = profile_stats.bande_in_zone(settimane[k]["bande"], fc_max)
            tot = sum(zone.values())
            if tot < 600:
                continue
            celle = " | ".join(f"{100 * zone[z] / tot:.0f}%" for z, _, _, _ in profile_stats.ZONE)
            righe.append(f"| {k.isoformat()} | {celle} | {tot / 3600:.1f}h |")
    elif any(a.get("hr_bands") for a in attivita):
        righe += ["", "## Distribuzione per zona", "",
                  "Non calcolabile: manca la **FC massima** nel profilo dell'atleta.",
                  "I dati grezzi ci sono (il tempo per banda di 10 bpm e' in ogni",
                  "riassunto di attivita'), serve solo il riferimento su cui mapparli.",
                  "Aggiungi al profilo una riga `- **FC massima**: <bpm>`."]

    # --- settimane vuote: un buco nel carico e' un'informazione -------------
    if chiavi:
        mancanti = []
        cur = chiavi[0]
        while cur <= chiavi[-1]:
            if cur not in settimane:
                mancanti.append(cur)
            cur += timedelta(days=7)
        if mancanti:
            righe += ["", "## Settimane senza attività", "",
                      "Uno stop, una vacanza, o un import incompleto: vale la pena",
                      "sapere quale prima di leggere una tendenza.", ""]
            righe += [f"- {m.isoformat()}" for m in mancanti[-12:]]
            if len(mancanti) > 12:
                righe.append(f"- ... e altre {len(mancanti) - 12} più vecchie")

    return "\n".join(righe) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("person")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fc-max", type=int,
                    help="FC massima da usare per le zone, invece di quella nel profilo")
    args = ap.parse_args()

    person = args.person.strip().lower()
    paths.athlete_dir(person)
    attivita = profile_stats.load(person)
    if not attivita:
        print(f"Nessuna attività per {person}: niente da riepilogare.")
        return 0

    fc_max = args.fc_max or profile_stats.leggi_fc_massima(person)
    testo = render(person, attivita, fc_max,
                   profile_stats.fc_polso_attendibile(person))
    out = paths.training_data(person) / "weekly.md"
    if args.dry_run:
        print(testo)
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(testo)
    n = testo.count("\n| 20")
    print(f"✓ {out.relative_to(paths.REPO_ROOT)} — {n} righe settimanali")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
