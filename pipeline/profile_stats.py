#!/usr/bin/env python3
"""Fotografia di un atleta ricavata dai suoi dati.

Serve all'onboarding (`coach/workflows/onboard.md`): riempie da solo i campi del
profilo che si possono calcolare, invece di chiederli a una persona che li
stimerebbe a occhio. Volume settimanale, sedute a settimana, ripartizione per
sport e terreno, corsa piu' lunga, dislivello, disponibilita' di potenza e
decoupling.

Legge i riassunti gia' convertiti in `training_data/activities/`, non i `.fit`:
sono due ordini di grandezza piu' veloci e contengono tutto il necessario.

    pipeline/.venv/bin/python pipeline/profile_stats.py andrea
    pipeline/.venv/bin/python pipeline/profile_stats.py andrea --json
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import quarter_split as qs  # noqa: E402

HR_RE = re.compile(r"^(?:[-*]\s*)?\*\*Avg HR:?\*\*:?\s*([0-9.]+)", re.I | re.M)
CAD_RE = re.compile(r"^(?:[-*]\s*)?\*\*Avg cadence:?\*\*:?\s*([0-9.]+)", re.I | re.M)
TERRAIN_RE = re.compile(r"^(?:[-*]\s*)?\*\*Terrain:?\*\*:?\s*(\w+)", re.I | re.M)
POWER_RE = re.compile(r"^(?:[-*]\s*)?\*\*Avg power:?\*\*:?\s*([0-9.]+)", re.I | re.M)
BANDE_RE = re.compile(r"^(?:[-*]\s*)?\*\*Tempo per banda FC[^:]*:?\*\*:?\s*(.+)$", re.I | re.M)
DECOUP_RE = re.compile(r"^(?:[-*]\s*)?\*\*Decoupling[^:]*:?\*\*:?\s*([+-]?[0-9.]+)", re.I | re.M)


# Zone di frequenza cardiaca come percentuale della FC massima. E' una
# convenzione fra le tante: scritta qui perche' sia una scelta esplicita e
# modificabile, non un numero sepolto nel codice.
ZONE = [
    ("Z1", 0.00, 0.72, "recupero"),
    ("Z2", 0.72, 0.82, "fondo aerobico"),
    ("Z3", 0.82, 0.87, "medio"),
    ("Z4", 0.87, 0.92, "soglia"),
    ("Z5", 0.92, 9.99, "VO2max"),
]

# Le altre due convenzioni con cui si tracciano le stesse cinque zone. Cambia
# l'ancora: la riserva cardiaca (FC massima meno FC a riposo) invece della sola
# FC massima, o la frequenza alla soglia anaerobica.
#
# Non sono equivalenti e non e' un dettaglio: sullo stesso atleta il confine
# fra fondo e medio puo' spostarsi di dieci battiti a seconda di quale si usa.
# Stanno qui tutte e tre perche' l'orologio ne usa una e il piano un'altra, e
# il confronto e' l'unico modo di accorgersi che si sta parlando di due cose
# diverse chiamandole "Z2". Le confronta `hr_estimate.py`.

# Frazioni di riserva cardiaca, convenzione Karvonen (e predefinita Garmin).
ZONE_RISERVA = [
    ("Z1", 0.50, 0.60, "recupero"),
    ("Z2", 0.60, 0.70, "fondo aerobico"),
    ("Z3", 0.70, 0.80, "medio"),
    ("Z4", 0.80, 0.90, "soglia"),
    ("Z5", 0.90, 9.99, "VO2max"),
]

# Frazioni della FC alla soglia, convenzione Friel per la corsa, accorpata a
# cinque zone: le sue Z5a/Z5b/Z5c diventano una sola Z5.
ZONE_SOGLIA = [
    ("Z1", 0.00, 0.81, "recupero"),
    ("Z2", 0.81, 0.90, "fondo aerobico"),
    ("Z3", 0.90, 0.94, "medio"),
    ("Z4", 0.94, 1.00, "soglia"),
    ("Z5", 1.00, 9.99, "VO2max"),
]


def _in_bpm(zone: list, ampiezza: float, base: float = 0.0) -> list:
    """Da frazioni a battiti. `None` come estremo alto significa 'senza tetto'."""
    return [(nome, round(base + lo * ampiezza),
             None if hi > 9 else round(base + hi * ampiezza), desc)
            for nome, lo, hi, desc in zone]


def scala_fcmax(fc_max: int) -> list:
    """Zone in bpm come percentuale della FC massima. E' quella che usa il repo."""
    return _in_bpm(ZONE, fc_max)


def scala_riserva(fc_max: int, fc_riposo: int) -> list:
    """Zone in bpm come percentuale della riserva cardiaca (Karvonen)."""
    return _in_bpm(ZONE_RISERVA, fc_max - fc_riposo, fc_riposo)


def scala_soglia(lthr: int) -> list:
    """Zone in bpm come percentuale della FC alla soglia."""
    return _in_bpm(ZONE_SOGLIA, lthr)

FC_MAX_RE = re.compile(
    r"^(?:[-*]\s*)?\*\*(?:FC massima|FCmax|Max HR|Frequenza cardiaca massima)\*\*:?\s*"
    r"([0-9]{2,3})\b", re.I | re.M)


FC_POLSO_RE = re.compile(
    r"^(?:[-*]\s*)?\*\*FC da polso attendibile\*\*:?\s*(si|sì|no|n\.d\.)", re.I | re.M)


def fc_polso_attendibile(person: str) -> bool | None:
    """Se la FC da polso di questo atleta e' utilizzabile.

    Serve alle zone: su un sensore affetto da *cadence lock* la frequenza e'
    gonfiata sotto sforzo, quindi la distribuzione per zona sovrastima
    l'intensita'. Il dato resta utile come tendenza, ma va letto sapendolo —
    e chi lo legge e' un modello, che non lo sa se non glielo si dice.
    """
    percorso = paths.profile(person)
    if not percorso.exists():
        return None
    m = FC_POLSO_RE.search(percorso.read_text())
    if not m:
        return None
    risposta = m.group(1).lower()
    if risposta in ("si", "sì"):
        return True
    if risposta == "no":
        return False
    return None   # "n.d.": non e' stato verificato, che non e' come dire "no"


def leggi_fc_massima(person: str) -> int | None:
    """FC massima dichiarata nel profilo, se c'e' e se e' un numero sensato.

    Senza, le zone non si calcolano: e' un dato che l'atleta deve fornire, non
    qualcosa da stimare con 220 meno l'eta' — quella formula sbaglia di 10-12
    battiti su un individuo, abbastanza da spostare una seduta di una zona
    intera.
    """
    percorso = paths.profile(person)
    if not percorso.exists():
        return None
    m = FC_MAX_RE.search(percorso.read_text())
    if not m:
        return None
    v = int(m.group(1))
    return v if 120 <= v <= 230 else None


def bande_in_zone(bande: dict, fc_max: int) -> dict:
    """Ripartisce i secondi delle bande FC nelle zone, in proporzione.

    Una banda da 10 bpm puo' cadere a cavallo di due zone: il tempo si divide
    sulla parte di banda che ricade in ciascuna, invece di assegnarlo tutto a
    quella del bordo inferiore.
    """
    fuori = {nome: 0.0 for nome, _, _, _ in ZONE}
    for etichetta, secondi in (bande or {}).items():
        if not secondi:
            continue
        if etichetta.endswith("+"):
            basso, alto = int(etichetta[:-1]), 230
        else:
            basso, alto = (int(x) for x in etichetta.split("-"))
        larghezza = alto - basso
        for nome, lo, hi, _ in ZONE:
            zl, zh = lo * fc_max, hi * fc_max
            sovrapposizione = max(0.0, min(alto, zh) - max(basso, zl))
            if sovrapposizione > 0:
                fuori[nome] += secondi * sovrapposizione / larghezza
    return {k: round(v) for k, v in fuori.items()}


def _parse_bande(riga: str) -> dict:
    """Riconverte in secondi la riga delle bande FC del riassunto."""
    out = {}
    for pezzo in riga.split("·"):
        pezzo = pezzo.strip()
        m = re.match(r"([0-9]+(?:-[0-9]+|\+))\s+([0-9]+):([0-9]{2})$", pezzo)
        if m:
            out[m.group(1)] = int(m.group(2)) * 60 + int(m.group(3))
    return out


def load(person: str) -> list[dict]:
    d = paths.activity_summaries(person)
    if not d.is_dir():
        raise SystemExit(
            f"Nessun dato convertito per '{person}'.\n"
            f"Lancia prima: pipeline/.venv/bin/python pipeline/run_pipeline.py {person}"
        )
    out = []
    for f in sorted(d.glob("*.md")):
        a = qs.read_activity_file(f)
        if not a:
            continue
        text = a["content"]
        for key, pat, cast in (("avg_hr", HR_RE, float), ("avg_cadence", CAD_RE, float),
                               ("avg_power", POWER_RE, float), ("decoupling", DECOUP_RE, float)):
            m = pat.search(text)
            a[key] = cast(m.group(1)) if m else None
        m = TERRAIN_RE.search(text)
        a["terrain"] = m.group(1).lower() if m else None
        m = BANDE_RE.search(text)
        a["hr_bands"] = _parse_bande(m.group(1)) if m else None
        out.append(a)
    return out


def window(acts: list[dict], days: int, now: datetime) -> list[dict]:
    return [a for a in acts if a["date"] >= now - timedelta(days=days)]


def volume(acts: list[dict], days: int, now: datetime) -> dict:
    w = window(acts, days, now)
    weeks = days / 7
    return {
        "attivita": len(w),
        "km_settimana": round(sum(a["distance_km"] or 0 for a in w) / weeks, 1),
        "ore_settimana": round(sum(a["duration_s"] or 0 for a in w) / 3600 / weeks, 1),
        "dplus_settimana": round(sum(a["ascent_m"] or 0 for a in w) / weeks),
        "sedute_settimana": round(len(w) / weeks, 1),
    }


# --- Perche' qui NON c'e' un controllo sul cardio da polso ------------------
#
# Il *cadence lock* (il sensore ottico che legge i passi invece del battito) e'
# la cosa piu' utile che si vorrebbe dedurre dai dati: se la FC e' falsa, ogni
# prescrizione che ci si basa sopra e' falsa. Il tentativo c'e' stato: confronto
# fra passi al minuto e FC media, sul quartile di corse a FC piu' bassa (il
# miglior sostituto di "corsa facile" senza conoscere la FC massima).
#
# Non funziona. Su questo archivio, l'atleta con cadence lock **confermato a
# mano** esce con scarti larghi quanto quelli dell'atleta con sensore buono
# (+52 bpm sulle facili contro +46). Il motivo e' che le sedute in cui il
# problema si manifesta — veloci, all'aperto — sono poche e si perdono nella
# mediana, mentre a intensita' alta FC e cadenza convergono anche con un
# sensore perfetto.
#
# Un indicatore che sbaglia l'unico caso di cui conosciamo la risposta e'
# peggio di nessun indicatore: verrebbe letto come una misura. La risposta si
# ottiene in trenta secondi correndo (test in `coach/workflows/onboard.md`) e
# l'onboarding la chiede li'.
#
# Se un giorno ci fossero piu' atleti con esito noto, il punto da cui ripartire
# e' filtrare sulle sedute veloci all'aperto invece che sulla mediana.


def build(person: str) -> dict:
    acts = load(person)
    if not acts:
        raise SystemExit(
            f"Nessuna attivita' leggibile per '{person}'.\n"
            f"La cartella {paths.activity_summaries(person)} e' vuota o i file non\n"
            f"sono nel formato atteso. Genera i dati con:\n"
            f"  pipeline/.venv/bin/python pipeline/run_pipeline.py {person}"
        )
    # Le finestre sono ancorate all'ULTIMA attivita', non a oggi: su un archivio
    # importato a meta' o su chi si e' fermato, ancorarle a oggi darebbe zeri
    # ovunque e nasconderebbe il problema invece di mostrarlo. Lo scarto da oggi
    # e' riportato a parte proprio perche' e' un'informazione, non un dettaglio.
    now = max(a["date"] for a in acts)
    giorni_fa = (datetime.now() - now).days

    tipi = Counter(a.get("activity_type") or "sconosciuto" for a in acts)
    terreni = Counter(a["terrain"] for a in acts if a.get("terrain"))

    corse = [a for a in acts if (a.get("activity_type") or "").startswith("running")]
    lunga = max(corse, key=lambda a: a["distance_km"] or 0, default=None)
    dplus = max(acts, key=lambda a: a["ascent_m"] or 0, default=None)

    per_anno = defaultdict(lambda: {"n": 0, "km": 0.0})
    for a in acts:
        y = per_anno[a["date"].year]
        y["n"] += 1
        y["km"] += a["distance_km"] or 0

    dec = [a["decoupling"] for a in acts if a.get("decoupling") is not None]
    pot = [a["avg_power"] for a in acts if a.get("avg_power") is not None]

    return {
        "atleta": person,
        "attivita_totali": len(acts),
        "periodo": {
            "da": min(a["date"] for a in acts).date().isoformat(),
            "a": now.date().isoformat(),
            "ultima_attivita_giorni_fa": giorni_fa,
        },
        "volume": {
            "ultime_4_settimane": volume(acts, 28, now),
            "ultime_12_settimane": volume(acts, 84, now),
            "ultime_52_settimane": volume(acts, 365, now),
        },
        "per_anno": {k: {"attivita": v["n"], "km": round(v["km"])}
                     for k, v in sorted(per_anno.items())},
        "tipi_attivita": dict(tipi.most_common()),
        "terreni": dict(terreni.most_common()),
        "corsa_piu_lunga": {
            "km": round(lunga["distance_km"], 1),
            "data": lunga["date"].date().isoformat(),
        } if lunga and lunga["distance_km"] else None,
        "uscita_con_piu_dislivello": {
            "dplus_m": round(dplus["ascent_m"]),
            "km": round(dplus["distance_km"] or 0, 1),
            "data": dplus["date"].date().isoformat(),
        } if dplus and dplus["ascent_m"] else None,
        "potenza_di_corsa": {
            "disponibile_su": f"{len(pot)}/{len(acts)} attivita'",
            "media_W": round(statistics.mean(pot)) if pot else None,
        },
        "decoupling": {
            "calcolabile_su": f"{len(dec)}/{len(acts)} attivita'",
            "mediano_pct": round(statistics.median(dec), 1) if dec else None,
        },
        "dati_assenti": [
            "HRV, sonno, stress: health_status.md non e' prodotto dalla pipeline",
            "FC massima e a riposo: vanno chieste all'atleta, servono per le zone",
            "Attendibilita' del cardio da polso: non deducibile dai dati, "
            "si verifica correndo (coach/workflows/onboard.md)",
        ],
    }


def render(d: dict) -> str:
    L = [f"Fotografia di {d['atleta']} — {d['attivita_totali']} attività "
         f"dal {d['periodo']['da']} al {d['periodo']['a']}", ""]

    g = d["periodo"]["ultima_attivita_giorni_fa"]
    if g > 10:
        L += [f"  ⚠️  L'ultima attività risale a {g} giorni fa. Le finestre qui sotto",
              "     sono ancorate a quella data, non a oggi. Se hai corso da allora,",
              "     l'import è incompleto: rilancia la sincronizzazione.", ""]

    L.append(f"VOLUME  (finestre che finiscono il {d['periodo']['a']})")
    for etichetta, chiave in (("ultime 4 settimane", "ultime_4_settimane"),
                              ("ultime 12 settimane", "ultime_12_settimane"),
                              ("ultimo anno", "ultime_52_settimane")):
        v = d["volume"][chiave]
        L.append(f"  {etichetta:20} {v['km_settimana']:6.1f} km/sett   "
                 f"{v['ore_settimana']:4.1f} h/sett   {v['dplus_settimana']:5} m D+/sett   "
                 f"{v['sedute_settimana']:4.1f} sedute/sett")

    L += ["", "PER ANNO"]
    for anno, v in d["per_anno"].items():
        L.append(f"  {anno}   {v['attivita']:4} attività   {v['km']:6} km")

    L += ["", "COSA FA"]
    tot = d["attivita_totali"]
    for k, v in list(d["tipi_attivita"].items())[:6]:
        L.append(f"  {k:26} {v:4}  ({100*v//tot}%)")
    if d["terreni"]:
        L.append("  terreni: " + ", ".join(f"{k} {v}" for k, v in d["terreni"].items()))

    L += ["", "ESTREMI"]
    if d["corsa_piu_lunga"]:
        L.append(f"  corsa più lunga        {d['corsa_piu_lunga']['km']} km "
                 f"({d['corsa_piu_lunga']['data']})")
    if d["uscita_con_piu_dislivello"]:
        u = d["uscita_con_piu_dislivello"]
        L.append(f"  più dislivello         {u['dplus_m']} m su {u['km']} km ({u['data']})")

    p, dc = d["potenza_di_corsa"], d["decoupling"]
    L += ["", "METRICHE AVANZATE"]
    L.append(f"  potenza di corsa       {p['disponibile_su']}"
             + (f", media {p['media_W']} W" if p["media_W"] else ""))
    L.append(f"  decoupling             {dc['calcolabile_su']}"
             + (f", mediano {dc['mediano_pct']:+}%" if dc["mediano_pct"] is not None else ""))

    L += ["", "NON DISPONIBILE"]
    L += [f"  - {x}" for x in d["dati_assenti"]]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("person")
    ap.add_argument("--json", action="store_true", help="Output JSON invece che testo")
    args = ap.parse_args()

    person = args.person.strip().lower()
    paths.athlete_dir(person)
    d = build(person)
    print(json.dumps(d, indent=2, ensure_ascii=False) if args.json else render(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
