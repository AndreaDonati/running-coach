#!/usr/bin/env python3
"""Converte in parallelo tutti i .fit di un atleta nei riassunti Markdown.

Legge `athletes/<person>/raw/activities/*.fit` e scrive
`athletes/<person>/training_data/activities/activity_<id>.md`, mantenendo il
nome base del file di origine.

Il lavoro vero lo fa `fit_to_markdown.py`, lanciato un processo per file.
Con `--json-dir` si tiene anche il dump JSON della timeseries (~1.2 MB per
attivita'), che serve solo per diagnostica.

Esempi:
    python pipeline/batch_convert.py --person andrea --dry-run --limit 5
    python pipeline/batch_convert.py --person andrea --skip-existing --workers 4
"""
from __future__ import annotations

import argparse
import concurrent.futures
import logging
import subprocess
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

CONVERTER = Path(__file__).resolve().parent / "fit_to_markdown.py"

# Sotto questa soglia il file non puo' contenere un header FIT valido: e' un
# download troncato o una pagina di errore salvata con estensione .fit.
MIN_FIT_BYTES = 12


def find_fit_files(src: Path) -> List[Path]:
    if not src.exists():
        return []
    return sorted(p for p in src.iterdir() if p.is_file() and p.suffix.lower() == ".fit")


def run_converter(in_path: Path, out_md: Path, python: str, prefer_fit: bool,
                  ascent_method: str, out_json: Path | None) -> subprocess.CompletedProcess:
    cmd = [python, str(CONVERTER), str(in_path), str(out_md)]
    if out_json:
        cmd.extend(["--json", str(out_json)])
    if prefer_fit:
        cmd.append("--prefer-fit-totals")
    if ascent_method:
        cmd.extend(["--ascent-method", ascent_method])
    return subprocess.run(cmd, capture_output=True, text=True)


def process_one(in_path: Path, dst_dir: Path, json_dir: Path | None, skip_existing: bool,
                dry_run: bool, python: str, prefer_fit: bool,
                ascent_method: str) -> tuple:
    out_md = dst_dir / f"{in_path.stem}.md"

    if skip_existing and out_md.exists():
        return (in_path, "skipped", "esiste gia'")
    if dry_run:
        return (in_path, "dry-run", str(out_md))

    try:
        if in_path.stat().st_size < MIN_FIT_BYTES:
            return (in_path, "error",
                    f"file troppo piccolo ({in_path.stat().st_size} byte)")
    except OSError as e:
        return (in_path, "error", f"stat fallita: {e}")

    # Il converter scrive direttamente a destinazione. Prima passava da una
    # cartella temporanea perche' il Markdown nasceva accanto al JSON, e ogni
    # attivita' costava 1.2 MB scritti e subito cancellati.
    out_json = json_dir / f"{in_path.stem}.json" if json_dir else None
    try:
        res = run_converter(in_path, out_md, python, prefer_fit, ascent_method, out_json)
    except Exception as e:  # noqa: BLE001 - vogliamo il nome del file nel report
        return (in_path, "error", f"eccezione: {e}")

    if res.returncode != 0:
        return (in_path, "error", res.stderr.strip() or res.stdout.strip())
    if not out_md.exists():
        return (in_path, "error", "nessun .md prodotto")
    return (in_path, "ok", str(out_md))


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--person", required=True, help="Nome cartella atleta (es. andrea)")
    p.add_argument("--src-dir", help="Sorgente .fit (default: athletes/<person>/raw/activities)")
    p.add_argument("--dst-dir", help="Destinazione .md (default: athletes/<person>/training_data/activities)")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--prefer-fit", action="store_true",
                   help="Usa il dislivello totale dichiarato dal FIT quando c'e'")
    p.add_argument("--ascent-method", choices=("auto", "fit", "recomputed"), default="auto",
                   help="auto: il valore del dispositivo se c'e', altrimenti il ricalcolo")
    p.add_argument("--json-dir",
                   help="Scrive anche il dump JSON della timeseries in questa "
                        "cartella (~1.2 MB per attivita'). Solo per diagnostica")
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=0, help="Processa solo N file (0 = tutti)")
    p.add_argument("--python", default=sys.executable,
                   help="Interprete con cui lanciare il converter")
    args = p.parse_args(argv)

    person = args.person.strip().lower()
    src = Path(args.src_dir) if args.src_dir else paths.raw_activities(person)
    dst = Path(args.dst_dir) if args.dst_dir else paths.activity_summaries(person)
    dst.mkdir(parents=True, exist_ok=True)
    paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("batch-convert")
    fh = logging.FileHandler(paths.LOGS_DIR / f"{person}-convert.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)

    fits = find_fit_files(src)
    if args.limit > 0:
        fits = fits[: args.limit]
    if not fits:
        print(f"Nessun .fit trovato in {src}")
        return 0

    json_dir = Path(args.json_dir) if args.json_dir else None
    if json_dir:
        json_dir.mkdir(parents=True, exist_ok=True)

    def work(f: Path) -> tuple:
        return process_one(f, dst, json_dir, args.skip_existing, args.dry_run,
                           args.python, args.prefer_fit, args.ascent_method)

    if args.workers > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
            results = [fut.result() for fut in
                       concurrent.futures.as_completed([ex.submit(work, f) for f in fits])]
    else:
        results = [work(f) for f in fits]

    ok = skipped = 0
    errors: list[tuple[Path, str]] = []
    for fit_path, status, msg in results:
        if status == "ok":
            ok += 1
            logger.info("OK %s -> %s", fit_path, msg)
        elif status == "skipped":
            skipped += 1
            logger.info("SKIP %s (%s)", fit_path, msg)
        elif status == "dry-run":
            print(f"DRYRUN {fit_path} -> {msg}")
        else:
            errors.append((fit_path, msg))
            logger.error("ERR %s: %s", fit_path, msg)
            print(f"ERR {fit_path}: {msg}")

    print(f"Convertite: {ok}, saltate: {skipped}, errori: {len(errors)}")
    if errors:
        print(f"Alcuni file sono falliti. Log: {paths.LOGS_DIR / f'{person}-convert.log'}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
