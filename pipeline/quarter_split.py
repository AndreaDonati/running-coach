#!/usr/bin/env python3
"""Raggruppa i riassunti per attivita' in file trimestrali.

Legge `athletes/<person>/training_data/activities/*.md`, li raggruppa per
trimestre solare (YYYY_Qn) e scrive in `athletes/<person>/training_data/`:

  - `<YYYY>_Q<n>_activities.md`  una riga per attivita', ordinate
  - `summary.md`                 volumi e tendenze aggregate
  - `manifest.md`                indice: quali file leggere e in che ordine

Legge solo i `.md`. Il JSON con la timeseries prodotto dal converter non serve
a questo passo (vedi `batch_convert.py`).

Esempi:
    python pipeline/quarter_split.py --person andrea --dry-run
    python pipeline/quarter_split.py --person andrea
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402


# I riassunti prodotti dal converter sono liste puntate:
#     - **Distance:** 6.12 km
# I pattern originali ancoravano a `^\*\*Distance:` e quindi non agganciavano
# mai niente: distanza, calorie e durata risultavano None per OGNI attivita' e
# summary.md riportava 0.0 km e 0.0 ore su centinaia di sedute. Le date si
# salvavano solo grazie al fallback ISO_SEARCH_RE. Il prefisso "- " e' ora
# opzionale, e i nomi dei campi coprono entrambe le diciture usate dal converter.
_FIELD = r"^(?:[-*]\s*)?\*\*{}:?\*\*:?\s*"

DATE_RE = re.compile(_FIELD.format(r"Date") + r"(.+)$", re.IGNORECASE | re.MULTILINE)
DIST_RE = re.compile(_FIELD.format(r"(?:Total distance|Distance)") + r"([0-9,.]+)\s*km",
                     re.IGNORECASE | re.MULTILINE)
CAL_RE = re.compile(_FIELD.format(r"Calories") + r"([0-9,]+)", re.IGNORECASE | re.MULTILINE)
MOVING_RE = re.compile(_FIELD.format(r"Moving time") + r"([0-9:]+)", re.IGNORECASE | re.MULTILINE)
ELAPSED_RE = re.compile(_FIELD.format(r"Elapsed time") + r"([0-9:]+)", re.IGNORECASE | re.MULTILINE)
ASCENT_RE = re.compile(_FIELD.format(r"Total ascent") + r"([0-9,.]+)\s*m",
                       re.IGNORECASE | re.MULTILINE)
TYPE_RE = re.compile(_FIELD.format(r"Type") + r"(.+)$", re.IGNORECASE | re.MULTILINE)
ISO_SEARCH_RE = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}")


def parse_iso_or_epoch(s: str) -> Optional[datetime]:
    s = s.strip()
    # Try ISO
    try:
        return datetime.fromisoformat(s)
    except Exception:
        pass

    # Try a few common formats
    fmts = ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue

    # Try numeric epoch (seconds / milliseconds)
    if s.isdigit():
        try:
            v = int(s)
            if v > 1_000_000_000_000:  # epoch in ms
                return datetime.fromtimestamp(v / 1000)
            return datetime.fromtimestamp(v)
        except Exception:
            return None

    return None


def parse_duration_to_seconds(s: str) -> Optional[int]:
    s = s.strip()
    parts = s.split(":")
    try:
        if len(parts) == 3:
            h, m, sec = map(int, parts)
            return h * 3600 + m * 60 + sec
        if len(parts) == 2:
            a, b = map(int, parts)
            if a < 60:
                return a * 60 + b
            return a * 3600 + b * 60
        if len(parts) == 1:
            return int(parts[0])
    except Exception:
        return None
    return None


def _repo_relative(path: Path) -> str:
    """Percorso relativo alla root del repo, cosi' il manifest resta valido
    anche su un'altra macchina."""
    try:
        return str(path.resolve().relative_to(paths.REPO_ROOT))
    except ValueError:
        return str(path)


def quarter_of(dt: datetime) -> str:
    q = (dt.month - 1) // 3 + 1
    return f"{dt.year}_Q{q}"


def human_seconds(sec: Optional[int]) -> str:
    if sec is None:
        return ""
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


def read_activity_file(path: Path, verbose: bool = False) -> Optional[Dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        if verbose:
            print(f"⚠ Could not read {path}")
        return None

    # Extract metadata
    date_m = DATE_RE.search(text)
    dist_m = DIST_RE.search(text)
    cal_m = CAL_RE.search(text)
    moving_m = MOVING_RE.search(text)
    elapsed_m = ELAPSED_RE.search(text)
    ascent_m = ASCENT_RE.search(text)
    type_m = TYPE_RE.search(text)

    date = None
    if date_m:
        date = parse_iso_or_epoch(date_m.group(1))
    else:
        iso = ISO_SEARCH_RE.search(text)
        if iso:
            date = parse_iso_or_epoch(iso.group(0))

    distance = None
    if dist_m:
        try:
            distance = float(dist_m.group(1).replace(',', ''))
        except Exception:
            distance = None

    calories = None
    if cal_m:
        try:
            calories = int(cal_m.group(1).replace(',', ''))
        except Exception:
            calories = None

    # Il tempo di riferimento e' quello in movimento: e' il tempo di allenamento.
    # L'elapsed include le soste e gonfia i totali.
    moving_seconds = parse_duration_to_seconds(moving_m.group(1)) if moving_m else None
    elapsed_seconds = parse_duration_to_seconds(elapsed_m.group(1)) if elapsed_m else None
    duration_seconds = moving_seconds if moving_seconds is not None else elapsed_seconds

    ascent_m_val = None
    if ascent_m:
        try:
            ascent_m_val = float(ascent_m.group(1).replace(',', ''))
        except ValueError:
            ascent_m_val = None

    if not date:
        if verbose:
            print(f"⚠ Skipping {path.name}: date not found or unparseable")
        return None

    return {
        "filename": path.name,
        "path": str(path),
        "date": date,
        "distance_km": distance,
        "duration_s": duration_seconds,
        "elapsed_s": elapsed_seconds,
        "ascent_m": ascent_m_val,
        "activity_type": type_m.group(1).strip() if type_m else None,
        "calories": calories,
        "content": text,
    }


def write_quarter_file(outfile: Path, quarter: str, activities: List[Dict]):
    md = [f"# {quarter} Activities", "", f"- **Total Activities**: {len(activities)}", ""]

    md.append("## Activities")
    md.append("")
    for a in activities:
        date_str = a["date"].isoformat()
        dist = f"{a['distance_km']:.2f} km" if a["distance_km"] is not None else ""
        dur = human_seconds(a.get("duration_s"))
        cal = str(a.get("calories")) if a.get("calories") is not None else ""
        md.append(f"### {a['filename']}")
        md.append("")
        md.append(f"- **Date**: {date_str}")
        if a.get("activity_type"):
            md.append(f"- **Type**: {a['activity_type']}")
        if dist:
            md.append(f"- **Distance**: {dist}")
        if dur:
            md.append(f"- **Moving time**: {dur}")
        if a.get("ascent_m") is not None:
            md.append(f"- **Ascent**: {a['ascent_m']:.0f} m")
        if cal:
            md.append(f"- **Calories**: {cal}")
        md.append("")
        md.append(a["content"].rstrip())
        md.append("")

    outfile.write_text("\n".join(md))


def generate_summary(output_dir: Path, activities: List[Dict]):
    total_distance = sum(a.get("distance_km") or 0.0 for a in activities)
    total_duration_s = sum(a.get("duration_s") or 0 for a in activities)
    total_cal = sum(a.get("calories") or 0 for a in activities)
    total_ascent = sum(a.get("ascent_m") or 0.0 for a in activities)
    # Reso esplicito invece che silenziosamente sommato come zero: se il parsing
    # fallisce di nuovo, il totale sbagliato si vede subito.
    missing_dist = sum(1 for a in activities if a.get("distance_km") is None)

    md: List[str] = []
    md.append("# Training Summary")
    md.append("")
    md.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    md.append("")
    md.append("## Training Volume")
    md.append("")
    md.append(f"- **Total Time** (moving): {total_duration_s/3600:.1f} hours")
    md.append(f"- **Total Distance**: {total_distance:.1f} km")
    md.append(f"- **Total Ascent**: {total_ascent:.0f} m")
    md.append(f"- **Total Calories**: {total_cal:.0f} kcal")
    md.append(f"- **Number of Sessions**: {len(activities)}")
    if missing_dist:
        md.append(f"- **Sessions without distance**: {missing_dist} "
                  f"(not counted in the totals above)")
    md.append("")

    # Recent form: last 7 days
    md.append("## Recent Form")
    md.append("")
    try:
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        recent = [a for a in activities if a["date"] >= week_ago]
        recent_time = sum(a.get("duration_s") or 0 for a in recent)
        recent_dist = sum(a.get("distance_km") or 0.0 for a in recent)
        md.append(f"- **Last 7 days sessions**: {len(recent)}")
        md.append(f"- **Last 7 days distance**: {recent_dist:.1f} km")
        md.append(f"- **Last 7 days time**: {recent_time/3600:.2f} hours")
    except Exception:
        pass

    md.append("")
    # Recovery status placeholder
    md.append("## Recovery Status")
    md.append("")
    if output_dir.joinpath("health_status.md").exists():
        md.append("- **HRV / sonno / stress**: vedi `health_status.md`")
    else:
        md.append("- **HRV / sonno / stress**: non disponibili. La pipeline non")
        md.append("  produce `health_status.md`: governare le")
        md.append("  sedute a passo e RPE, e dichiararlo.")
    md.append("")
    md.append("## Context for AI Analysis")
    md.append("")
    md.append("Use this summary alongside quarterly activity files to:")
    md.append("- Identify patterns and trends over time")
    md.append("- Detect recovery windows from HRV and sleep data")
    md.append("- Suggest progressive training loads")
    md.append("- Recommend appropriate rest and recovery")
    md.append("")

    output_dir.joinpath("summary.md").write_text("\n".join(md))


def generate_manifest(output_dir: Path, quarterly: Dict[str, List[Dict]]):
    """Scrive manifest.md: l'indice che l'agente legge per orientarsi.

    Descrive solo file che esistono davvero. La versione precedente annunciava
    `full_historic_activities.md` (che questo script non produce apposta) e
    `health_status.md` (che nessuno script produce), e li citava in tutte e
    quattro le ricette di lettura: il coach partiva cercando due file assenti.
    Costruiva inoltre due manifest, scrivendo il primo e sovrascrivendolo subito
    col secondo.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_acts = sum(len(v) for v in quarterly.values())
    quarters = sorted(quarterly.keys())
    latest = quarters[-1] if quarters else None

    has_health = output_dir.joinpath("health_status.md").exists()

    md = [
        "# Training Data Manifest",
        "",
        f"*Generato: {now}*",
        "",
        "Indice dei dati di allenamento disponibili per questo atleta.",
        "Tutti i file sono generati da `pipeline/`: non modificarli a mano.",
        "",
        "## File per trimestre",
        "",
        "Una riga per attivita', con distanza, tempo, FC e dislivello.",
        "",
        "| Trimestre | File | Attività | Periodo |",
        "|-----------|------|----------|---------|",
    ]

    min_date = max_date = None
    for q in quarters:
        acts = quarterly[q]
        start_d = min(a["date"] for a in acts).date()
        end_d = max(a["date"] for a in acts).date()
        md.append(f"| {q} | `{q}_activities.md` | {len(acts)} | {start_d} → {end_d} |")
        min_date = start_d if min_date is None or start_d < min_date else min_date
        max_date = end_d if max_date is None or end_d > max_date else max_date

    md += [
        "",
        "## Altri file",
        "",
        "**`summary.md`** — volume totale, ripartizione per tipo di attività,",
        "andamento settimanale.",
        "",
        "**`weekly.md`** — una riga per settimana: sedute, km, tempo, dislivello,",
        "corsa più lunga, FC media, distribuzione per zona (se il profilo dichiara",
        "la FC massima), più i blocchi di 4 settimane. È il file da",
        "leggere per il quadro di un trimestre, al posto dei file settimana.",
        "",
        "**`activities/activity_<id>.md`** — la singola seduta: split al km, lap",
        f"registrati, FC. {total_acts} file.",
        "",
    ]

    if has_health:
        md += [
            "**`health_status.md`** — HRV, sonno, stress, composizione corporea.",
            "",
        ]
    else:
        md += [
            "**`health_status.md`** — non presente. HRV, sonno e stress non sono",
            "prodotti dalla pipeline: il coach lavora senza e",
            "deve dichiararlo, non assumerli.",
            "",
        ]

    health_suffix = " + `health_status.md`" if has_health else ""
    md += [
        "## Cosa leggere, a seconda della domanda",
        "",
        "| Domanda | File |",
        "|---------|------|",
        f"| Forma attuale, pianificazione immediata | `{latest}_activities.md`{health_suffix} |"
        if latest else "| Forma attuale | `summary.md` |",
        f"| Carico delle ultime settimane | `weekly.md` |",
        f"| Tendenza di lungo periodo | `summary.md` + `weekly.md`{health_suffix} |",
        "| Confronto fra due periodi | due file trimestrali consecutivi |",
        "| Dettaglio di una singola seduta | `activities/activity_<id>.md` |",
        "",
        "## Statistiche",
        "",
        f"- **Attività totali**: {total_acts}",
        f"- **Trimestri**: {len(quarterly)}",
    ]
    if min_date and max_date:
        md.append(f"- **Periodo coperto**: {min_date} → {max_date}")
    md += [
        f"- **Ultimo aggiornamento**: {now}",
        "",
        f"Percorso: `{_repo_relative(output_dir)}/`",
        "",
    ]

    output_dir.joinpath("manifest.md").write_text("\n".join(md))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--person", required=True)
    p.add_argument("--input-dir", help="Cartella dei .md di attivita' (sovrascrive --person)")
    p.add_argument("--output-dir", help="Cartella training_data di destinazione (sovrascrive --person)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backup", action="store_true", help="Backup full_historic_activities.md before deleting")
    p.add_argument("--delete-full", action="store_true", help="Delete full_historic_activities.md after split")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    person = args.person.strip().lower()
    # Prima: Path.cwd() / person, quindi lo script funzionava solo se lanciato
    # dalla root del repo. Ora i percorsi sono derivati da paths.py.
    input_dir = Path(args.input_dir) if args.input_dir else paths.activity_summaries(person)
    output_dir = Path(args.output_dir) if args.output_dir else paths.training_data(person)

    if args.verbose:
        print(f"Input dir: {input_dir}")
        print(f"Output dir: {output_dir}")

    if not input_dir.exists():
        print(f"✗ Input directory does not exist: {input_dir}")
        return

    md_files = sorted([p for p in input_dir.glob("*.md")])
    activities = []
    for md in md_files:
        a = read_activity_file(md, verbose=args.verbose)
        if a:
            activities.append(a)

    if not activities:
        print("⚠ No parsable activity files found.")
        return

    activities.sort(key=lambda x: x["date"], reverse=True)

    quarterly: Dict[str, List[Dict]] = {}
    for a in activities:
        q = quarter_of(a["date"])
        quarterly.setdefault(q, []).append(a)

    if args.dry_run:
        print("Dry run: would write the following quarter files:")
        for q, acts in sorted(quarterly.items()):
            print(f" - {q}_activities.md: {len(acts)} activities")
        print(f"Would update summary.md and manifest.md in {output_dir}")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        for q, acts in sorted(quarterly.items()):
            outpath = output_dir / f"{q}_activities.md"
            write_quarter_file(outpath, q, acts)
            if args.verbose:
                print(f"✓ Wrote {outpath}")

        generate_summary(output_dir, activities)
        generate_manifest(output_dir, quarterly)

        full = output_dir / "full_historic_activities.md"
        if args.delete_full and full.exists():
            if args.backup:
                stamp = datetime.now().strftime("%Y%m%d%H%M%S")
                bak = output_dir / f"full_historic_activities.{stamp}.bak.md"
                full.replace(bak)
                print(f"✓ Backed up full_historic_activities.md → {bak}")
            else:
                full.unlink()
                print("✓ Deleted full_historic_activities.md")

        print("✓ Split complete. summary.md and manifest.md updated.")


if __name__ == "__main__":
    main()
