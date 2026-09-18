#!/usr/bin/env python3
"""Su quali numeri poggiano le zone di un atleta, e quanto sono solidi.

Le zone in `profile_stats.ZONE` sono percentuali: diventano battiti solo
applicandole a una FC massima, che oggi sta nel profilo scritta a mano. Questo
script ricava dai `.fit` gli ancoraggi che si possono misurare — FC massima
osservata, FC a riposo, frequenza alla soglia — e stampa le tre scale di zone
che ne derivano, una accanto all'altra.

Serve quando le zone del piano e quelle dell'orologio non coincidono, che e' la
regola: quasi sempre non e' la FC massima a essere diversa, e' il metodo. Se
l'elenco scaricato da Garmin contiene i minuti per zona, lo script ricostruisce
per inversione anche i confini che l'orologio sta usando davvero.

Non scrive niente e non tocca il profilo. Ogni numero e' stampato con la seduta
da cui viene, perche' la domanda che conta — quello sforzo era massimale? — la
puo' risolvere solo chi c'era.

    pipeline/.venv/bin/python pipeline/hr_estimate.py andrea
    pipeline/.venv/bin/python pipeline/hr_estimate.py andrea --giorni 180
    pipeline/.venv/bin/python pipeline/hr_estimate.py andrea --tutto --json

Codici di uscita: `0` fatto, `1` errore, `4` nessun dato cardiaco utilizzabile.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import activity_metrics as am  # noqa: E402
import paths  # noqa: E402
import profile_stats as ps  # noqa: E402
import quarter_split as qs  # noqa: E402

# Tipi di attivita' su cui ha senso stimare la soglia di corsa. La FC massima
# si prende invece da tutto: un picco in bici e' comunque un picco.
TIPI_CORSA = {"running", "trail_running", "treadmill_running", "track_running"}

# Finestra predefinita. Un anno prende dentro la stagione scorsa, che di solito
# contiene la gara da cui esce il picco vero; oltre, si stanno confrontando
# atleti diversi.
GIORNI_DEFAULT = 365

# Rapporto plausibile fra frequenza alla soglia e FC massima. Fuori da questo
# intervallo non e' che sia impossibile: e' che quasi sempre uno dei due numeri
# viene da uno sforzo che non era quello che si crede.
RAPPORTO_SOGLIA_ATTESO = (0.83, 0.93)

# Versione dei calcoli messi in cache. Va alzata quando cambia una funzione in
# `activity_metrics`: senza, una correzione al calcolo resta invisibile sulle
# attivita' gia' lette, che e' il modo piu' silenzioso di tenersi un bug.
VERSIONE_CACHE = 1


# --- lettura e cache --------------------------------------------------------

def _cache_path(person: str) -> Path:
    return paths.LOGS_DIR / f"hr_cache_{person}.json"


def _carica_cache(person: str) -> dict:
    p = _cache_path(person)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}   # una cache illeggibile si rifa', non e' un errore


def _salva_cache(person: str, cache: dict) -> None:
    paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(person).write_text(json.dumps(cache))


def _misura_fit(percorso: Path) -> dict:
    """Tutto cio' che serve da un `.fit`, in una passata sola.

    Aprire un `.fit` costa circa un secondo: su un archivio di trecento
    attivita' e' la differenza fra uno strumento che si usa e uno che no. Da
    qui esce un dizionario piccolo, che finisce in cache.
    """
    from fitparse import FitFile

    from fit_reader import extract_hr_settings, extract_summary, extract_timeseries

    fit = FitFile(str(percorso))
    ts = extract_timeseries(fit)
    hr = [r["heart_rate"] for r in ts if r.get("heart_rate")]
    if not hr:
        return {"fc": False}

    sommario = extract_summary(fit)
    out = {
        "fc": True,
        "tipo": sommario.get("activity_type"),
        "fcmax": max(hr),
        "fcmax_pulita": am.fcmax_pulita(ts),
        "sostenute": {str(k): v for k, v in am.massimi_sostenuti(ts).items()},
        "istogramma": {str(k): v for k, v in am.istogramma_hr(ts).items()},
    }
    out.update(extract_hr_settings(fit))
    return out


def misura(person: str, da: datetime | None, verbose: bool = True) -> list[dict]:
    """Una riga per attivita' con FC, nella finestra richiesta.

    Le date vengono dai riassunti in `training_data/`, non dai `.fit`: sono
    gia' li' e leggerle costa un millesimo. Il `.fit` si apre solo per le
    attivita' che rientrano nella finestra e non sono gia' in cache.
    """
    riassunti = paths.activity_summaries(person)
    grezzi = paths.raw_activities(person)
    if not riassunti.is_dir():
        raise SystemExit(
            f"Nessun dato convertito per '{person}'.\n"
            f"Lancia prima: pipeline/.venv/bin/python pipeline/run_pipeline.py {person}"
        )
    paths.require_fitparse()

    da_fare = []
    for f in sorted(riassunti.glob("*.md")):
        a = qs.read_activity_file(f)
        if not a or (da and a["date"] < da):
            continue
        fit = grezzi / (f.stem + ".fit")
        if fit.exists():
            da_fare.append((a, fit))
    if not da_fare:
        return []

    cache = _carica_cache(person)
    out, nuovi = [], 0
    for i, (a, fit) in enumerate(da_fare, 1):
        st = fit.stat()
        chiave = f"v{VERSIONE_CACHE}:{fit.name}:{st.st_size}:{int(st.st_mtime)}"
        if chiave not in cache:
            if verbose and nuovi == 0:
                print(f"Lettura dei .fit ({len(da_fare)} attività; la prima volta "
                      f"è lenta, poi resta in cache)...", file=sys.stderr)
            cache[chiave] = _misura_fit(fit)
            nuovi += 1
            if verbose and nuovi % 25 == 0:
                print(f"  {i}/{len(da_fare)}", file=sys.stderr)
        m = dict(cache[chiave])
        if not m.get("fc"):
            continue
        m["data"] = a["date"]
        m["nome"] = a["filename"]
        m["km"] = a["distance_km"]
        m["dplus"] = a["ascent_m"]
        m["tipo"] = m.get("tipo") or a.get("activity_type")
        out.append(m)

    if nuovi:
        _salva_cache(person, cache)
    return out


# --- stima ------------------------------------------------------------------

def _picco(misure: list[dict], chiave: str, sottochiave=None):
    """Attivita' col valore piu' alto, e il valore. `(None, None)` se non c'e'."""
    def val(m):
        v = m.get(chiave)
        if sottochiave is not None:
            v = (v or {}).get(sottochiave)
        return v

    cand = [(val(m), m) for m in misure if val(m) is not None]
    if not cand:
        return None, None
    v, m = max(cand, key=lambda x: x[0])
    return v, m


def stima(misure: list[dict], fc_max_profilo: int | None) -> dict:
    """Gli ancoraggi, ciascuno con la seduta da cui viene."""
    corsa = [m for m in misure if (m.get("tipo") or "") in TIPI_CORSA]

    fcmax, a_fcmax = _picco(misure, "fcmax")
    pulita, a_pulita = _picco(misure, "fcmax_pulita")

    sostenute = {}
    for w in am.FINESTRE_SOSTENUTE_S:
        v, a = _picco(corsa, "sostenute", str(w))
        sostenute[w] = {"bpm": v, "attivita": a}

    # Convenzione: la frequenza alla soglia e' la media piu' alta tenuta per
    # trenta minuti. E' la stima da campo piu' diffusa e la piu' robusta fra
    # quelle possibili con questi dati — la variante "ultimi venti minuti di un
    # test da trenta" richiede un test fatto apposta, che in archivio non c'e'.
    soglia = sostenute[1800]["bpm"]

    riposo = sorted(m["resting_hr"] for m in misure if m.get("resting_hr"))

    return {
        "attivita": len(misure),
        "attivita_corsa": len(corsa),
        "da": min(m["data"] for m in misure) if misure else None,
        "a": max(m["data"] for m in misure) if misure else None,
        "fcmax": {"bpm": fcmax, "attivita": a_fcmax},
        "fcmax_pulita": {"bpm": pulita, "attivita": a_pulita},
        "fcmax_profilo": fc_max_profilo,
        "fcmax_dispositivo": sorted({m["fcmax_dispositivo"] for m in misure
                                     if m.get("fcmax_dispositivo")}),
        "soglia_dispositivo": sorted({m["soglia_dispositivo"] for m in misure
                                      if m.get("soglia_dispositivo")}),
        "sostenute": sostenute,
        "soglia": round(soglia) if soglia else None,
        "riposo": {
            "mediana": riposo[len(riposo) // 2] if riposo else None,
            "min": riposo[0] if riposo else None,
            "max": riposo[-1] if riposo else None,
            "n": len(riposo),
        },
    }


def confini_garmin(person: str, misure: list[dict]) -> dict | None:
    """I confini di zona che Garmin sta usando, ricavati per inversione.

    Garmin pubblica in `raw/garmin_list/activities.json` i secondi passati in
    ciascuna delle cinque zone, ma non i battiti che le separano. I battiti si
    ricavano: il confine basso della Z5 e' il bpm sopra il quale si e' passato
    esattamente il tempo che Garmin attribuisce alla Z5, e cosi' a scendere
    sommando le zone dall'alto.

    Su una singola attivita' la risposta e' rumorosa — se in Z4 ci sono stati
    dieci secondi, il confine e' indeterminato — quindi si tengono solo le
    attivita' in cui la zona ha tempo a sufficienza e l'inversione torna entro
    il 3%, e di tutte le risposte si prende la moda.

    Restituisce anche le date in cui i confini sono cambiati: se l'atleta (o
    l'auto-rilevamento della FC massima) ha spostato le impostazioni, meta' del
    disaccordo con l'orologio si spiega li'.
    """
    elenco = paths.athlete_dir(person) / "raw" / "garmin_list" / "activities.json"
    if not elenco.exists():
        return None
    try:
        attivita = json.loads(elenco.read_text())
    except Exception:
        return None

    per_id = {str(a.get("activityId")): a for a in attivita}
    stime = {n: [] for n in ("Z1", "Z2", "Z3", "Z4", "Z5")}
    coperte = 0
    for m in misure:
        aid = m["nome"].replace("activity_", "").replace(".md", "")
        a = per_id.get(aid)
        if not a:
            continue
        z = [a.get(f"hrTimeInZone_{i}") or 0.0 for i in range(1, 6)]
        if sum(z) < 600:
            continue
        coperte += 1
        istogramma = {int(k): v for k, v in m["istogramma"].items()}
        totale = sum(istogramma.values())
        # Confine basso di ogni zona: il tempo sopra e' la somma delle zone da
        # quella in su. La Z1 inclusa: sotto il suo confine Garmin non conta
        # niente, ed e' il motivo per cui le sue percentuali non si sommano
        # come le nostre.
        cumulato = 0.0
        for i, nome in ((4, "Z5"), (3, "Z4"), (2, "Z3"), (1, "Z2"), (0, "Z1")):
            cumulato += z[i]
            if cumulato < 90 or cumulato > totale - 90:
                continue
            r = am.confine_da_tempo_sopra(istogramma, cumulato)
            if r and r[1] / cumulato < 0.03:
                stime[nome].append((m["data"], r[0]))

    ultima = max((a.get("startTimeLocal") or "" for a in attivita), default="")[:10]
    if not any(stime.values()):
        # L'elenco c'e' ma non copre la finestra: succede spesso, perche' il
        # download dei `.fit` e quello dell'elenco sono due richieste diverse e
        # l'elenco invecchia prima. Meglio dirlo che sparire.
        return {"attivita_confrontate": coperte, "zone": {}, "cambi": [],
                "dal": None, "ultima_nell_elenco": ultima}

    # Cambi di impostazione: la moda della Z4 su blocchi di dieci attivita'.
    # Un salto in quella serie e' qualcuno — o l'auto-rilevamento della FC
    # massima — che ha spostato le zone.
    cambi = []
    serie = sorted(stime["Z4"] or stime["Z3"])
    prec = None
    for i in range(0, len(serie), 10):
        blocco = serie[i:i + 10]
        if len(blocco) < 5:
            continue
        moda = Counter(v for _, v in blocco).most_common(1)[0][0]
        if prec is not None and abs(moda - prec) < 5:
            continue
        # Data del cambio: la prima attivita' del blocco che ha gia' il valore
        # nuovo, non l'inizio del blocco. Resta approssimata per eccesso.
        dal = next((d for d, v in blocco if abs(v - moda) <= 2), blocco[0][0])
        cambi.append({"dal": dal, "bpm": moda})
        prec = moda

    # I confini da riportare sono quelli **attuali**: mescolare i periodi
    # darebbe una Z5 vecchia sotto una Z4 nuova, cioe' zone che si scavalcano.
    inizio = cambi[-1]["dal"] if cambi else None
    out = {"attivita_confrontate": coperte, "zone": {},
           "cambi": [{"dal": c["dal"].date().isoformat(), "bpm": c["bpm"]}
                     for c in cambi],
           "dal": inizio.date().isoformat() if inizio else None,
           "ultima_nell_elenco": ultima}
    for nome, vals in stime.items():
        attuali = [v for d, v in vals if inizio is None or d >= inizio]
        if not attuali:
            continue
        moda, n = Counter(attuali).most_common(1)[0]
        out["zone"][nome] = {"bpm": moda, "accordo": f"{n}/{len(attuali)}"}
    return out


def riconosci_metodo(g: dict, fc_max: int | None, riposo: int | None,
                     soglia: int | None) -> str | None:
    """Con quale delle tre convenzioni sono stati tracciati quei confini.

    Si prova ognuna con gli ancoraggi noti e si tiene quella che sbaglia meno.
    Sopra i 4 bpm di scarto medio non si dichiara niente: vorrebbe dire che le
    zone sono state messe a mano, ed e' un'informazione anche quella.
    """
    osservati = {n: v["bpm"] for n, v in g.get("zone", {}).items()}
    if len(osservati) < 3:
        return None

    candidate = []
    if fc_max:
        candidate.append((f"% FC massima ({fc_max})", ps.scala_fcmax(fc_max)))
        if riposo:
            candidate.append((f"% riserva cardiaca (Karvonen, {fc_max}/{riposo})",
                              ps.scala_riserva(fc_max, riposo)))
    if soglia:
        candidate.append((f"% FC alla soglia ({soglia})", ps.scala_soglia(soglia)))

    migliore, scarto_migliore = None, None
    for etichetta, scala in candidate:
        atteso = {nome: lo for nome, lo, _, _ in scala}
        # La Z1 esclusa: la nostra parte da zero per costruzione, quella di
        # Garmin da un confine vero, e il confronto non direbbe niente.
        comuni = [n for n in osservati if n in atteso and n != "Z1"]
        if not comuni:
            continue
        scarto = sum(abs(osservati[n] - atteso[n]) for n in comuni) / len(comuni)
        if scarto_migliore is None or scarto < scarto_migliore:
            migliore, scarto_migliore = etichetta, scarto
    if migliore and scarto_migliore <= 4:
        return f"{migliore} — scarto medio {scarto_migliore:.1f} bpm"
    return None


# --- stampa -----------------------------------------------------------------

ZONE_NOMI = ("Z1", "Z2", "Z3", "Z4", "Z5")


def _riga_attivita(a: dict | None) -> str:
    if not a:
        return ""
    pezzi = [a["data"].date().isoformat(), (a.get("tipo") or "").replace("_", " ")]
    if a.get("km"):
        pezzi.append(f"{a['km']:.1f} km")
    if a.get("dplus"):
        pezzi.append(f"{a['dplus']:.0f} D+")
    return "  ".join(p for p in pezzi if p)


def _intestazione_zone() -> str:
    return "  " + " " * 14 + "".join(f"{n:>13}" for n in ZONE_NOMI)


def render(d: dict, g: dict | None) -> str:
    L = [f"Ancoraggi cardiaci — {d['attivita']} attività con FC "
         f"({d['attivita_corsa']} di corsa) "
         f"dal {d['da'].date()} al {d['a'].date()}", ""]

    # Riferimento per le zone: la FC massima dichiarata vince su quella
    # osservata, che e' solo il picco dei mesi guardati.
    fc = d["fcmax_profilo"] or d["fcmax"]["bpm"]
    rientro = " " * 38

    L.append("FC MASSIMA")
    if d["fcmax"]["bpm"]:
        L.append(f"  osservata                {d['fcmax']['bpm']:>3} bpm   "
                 f"{_riga_attivita(d['fcmax']['attivita'])}")
    if d["fcmax_pulita"]["bpm"]:
        scarto = (d["fcmax"]["bpm"] or 0) - d["fcmax_pulita"]["bpm"]
        nota = "il picco grezzo regge" if scarto <= 5 else \
               "il picco grezzo può essere cadenza invece che battito"
        L.append(f"  senza cadence lock       {d['fcmax_pulita']['bpm']:>3} bpm   "
                 f"{_riga_attivita(d['fcmax_pulita']['attivita'])}")
        L.append(f"{rientro}30 s con i passi ≥{am.CADENZA_GAP_MIN} bpm sotto il "
                 f"battito: −{scarto} bpm, {nota}")
    if d["fcmax_profilo"]:
        L.append(f"  dichiarata nel profilo   {d['fcmax_profilo']:>3} bpm")
    if d["fcmax_dispositivo"]:
        v = "/".join(str(x) for x in d["fcmax_dispositivo"])
        L.append(f"  usata dall'orologio      {v:>3} bpm")
        if len(d["fcmax_dispositivo"]) > 1:
            L.append(f"{rientro}⚠️  è cambiata {len(d['fcmax_dispositivo'])} volte "
                     f"nella finestra: l'orologio la auto-rileva,")
            L.append(f"{rientro}    e con lei sposta le proprie zone senza che "
                     f"nessuno tocchi niente")

    L += ["", "FC A RIPOSO  (dal profilo utente che l'orologio scrive nei .fit)"]
    r = d["riposo"]
    if r["mediana"]:
        L.append(f"  mediana {r['mediana']} bpm   intervallo {r['min']}-{r['max']} "
                 f"su {r['n']} attività")
    else:
        L.append("  non registrata: senza, la scala per riserva cardiaca non "
                 "si traccia")

    L += ["", "SFORZI SOSTENUTI  (media più alta su una finestra, solo corsa)"]
    for w in am.FINESTRE_SOSTENUTE_S:
        s = d["sostenute"][w]
        if s["bpm"]:
            L.append(f"  {w // 60:>2} min   {s['bpm']:>5} bpm   "
                     f"{_riga_attivita(s['attivita'])}")

    L += ["", "SOGLIA STIMATA"]
    if d["soglia"]:
        a = d["sostenute"][1800]["attivita"]
        L.append(f"  {d['soglia']} bpm — media migliore su 30 minuti, "
                 f"{_riga_attivita(a)}")
        if fc:
            rap = d["soglia"] / fc
            L.append(f"  {100 * rap:.0f}% della FC massima di riferimento ({fc})")
            if not RAPPORTO_SOGLIA_ATTESO[0] <= rap <= RAPPORTO_SOGLIA_ATTESO[1]:
                L.append("  ⚠️  fuori dall'intervallo tipico (83-93%): uno dei due "
                         "numeri non viene dallo sforzo che sembra")
        giorni = (datetime.now() - a["data"]).days if a else None
        if giorni and giorni > 120:
            L.append(f"  ⚠️  quello sforzo è di {giorni} giorni fa: la stima "
                     f"descrive la forma di allora")
        L += ["  ⚠️  è la miglior mezz'ora presente in archivio, non un test: vale",
              "      come stima solo se quella seduta era davvero al massimo. Un",
              "      test da 30 minuti in piano, tutto quello che si ha, la chiude."]
    else:
        L.append("  non stimabile: in archivio non ci sono 30 minuti continui "
                 "di corsa")
    if d["soglia_dispositivo"]:
        L.append(f"  soglia rilevata dall'orologio: "
                 f"{'/'.join(str(x) for x in d['soglia_dispositivo'])} bpm")

    L += ["", f"LE TRE SCALE A CONFRONTO  (FC massima {fc})", "", _intestazione_zone()]
    scale = [("% FC massima", ps.scala_fcmax(fc))]
    if r["mediana"]:
        scale.append(("% riserva", ps.scala_riserva(fc, r["mediana"])))
    if d["soglia"]:
        scale.append(("% soglia", ps.scala_soglia(d["soglia"])))
    for etichetta, scala in scale:
        celle = [f"{lo}-{hi}" if hi else f"{lo}+" for _, lo, hi, _ in scala]
        L.append(f"  {etichetta:<14}" + "".join(f"{c:>13}" for c in celle))
    L += ["",
          "  La prima è quella del repository (profile_stats.ZONE), ed è quella con",
          "  cui sono calcolate le distribuzioni in weekly.md. Le altre due sono le",
          "  convenzioni alternative: stesso atleta, stessi dati, confini diversi."]

    if g and not g["zone"]:
        L += ["", "COSA USA GARMIN",
              "  Non ricostruibile su questa finestra: l'elenco in "
              "raw/garmin_list/activities.json",
              f"  arriva al {g['ultima_nell_elenco'] or '?'}. Rilancia con --tutto, "
              f"oppure riscarica",
              "  l'elenco (run_pipeline.py --download) per confrontare le zone recenti."]
    elif g:
        periodo = f", in vigore dal {g['dal']}" if g.get("dal") else ""
        L += ["", f"COSA USA GARMIN  (da {g['attivita_confrontate']} attività "
                  f"con i minuti per zona{periodo})", "", _intestazione_zone()]
        celle = [(f"{g['zone'][n]['bpm']}+" if n in g["zone"] else "?")
                 for n in ZONE_NOMI]
        L.append("  confine basso " + "".join(f"{c:>13}" for c in celle))
        metodo = riconosci_metodo(g, fc, r["mediana"], d["soglia"])
        L += ["", f"  Metodo riconosciuto: {metodo}"] if metodo else \
             ["", "  Nessuna delle tre convenzioni riproduce questi confini: "
                  "probabile che siano stati messi a mano."]
        if len(g["cambi"]) > 1:
            L += ["", "  I confini sono cambiati nel tempo:"]
            for c in g["cambi"]:
                L.append(f"    dal {c['dal']}   Z4 da {c['bpm']} bpm")
            L.append("    (le distribuzioni per zona di Garmin non sono "
                     "confrontabili fra periodi diversi)")

    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("person")
    ap.add_argument("--giorni", type=int, default=GIORNI_DEFAULT,
                    help=f"finestra da analizzare (predefinita: {GIORNI_DEFAULT})")
    ap.add_argument("--tutto", action="store_true",
                    help="tutto l'archivio, invece della finestra")
    ap.add_argument("--no-garmin", action="store_true",
                    help="salta il confronto con le zone dell'orologio")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    da = None if args.tutto else datetime.now() - timedelta(days=args.giorni)
    misure = misura(args.person, da, verbose=not args.json)
    if not misure:
        print(f"Nessuna attività con frequenza cardiaca per '{args.person}' "
              f"nella finestra richiesta.", file=sys.stderr)
        raise SystemExit(4)

    d = stima(misure, ps.leggi_fc_massima(args.person))
    g = None if args.no_garmin else confini_garmin(args.person, misure)

    if args.json:
        def pulisci(o):
            # L'istogramma e' un dettaglio interno da migliaia di voci: serve
            # all'inversione dei confini, non a chi legge l'uscita.
            if isinstance(o, dict):
                return {k: pulisci(v) for k, v in o.items() if k != "istogramma"}
            if isinstance(o, list):
                return [pulisci(v) for v in o]
            if isinstance(o, datetime):
                return o.isoformat()
            return o
        print(json.dumps(pulisci({"stima": d, "garmin": g}), indent=2,
                         ensure_ascii=False, default=str))
    else:
        print(render(d, g))


if __name__ == "__main__":
    main()
