#!/usr/bin/env python3
"""Porta i dati di un atleta dallo stato "ho corso" a "il coach lo sa".

    Garmin  --download--> raw/activities/*.fit
            --convert---> training_data/activities/*.md
            --split-----> <YYYY>_Q<n>_activities.md, manifest, summary, weekly

I comandi cURL per il download si esportano dal browser con la sessione
Garmin aperta (vedi `pipeline/curl.txt.example`); `--curl-from-clipboard` li
prende dagli appunti e aggiorna `curl_<atleta>.txt` da solo — uno per atleta,
perche' i cookie appartengono a un account. L'ordine non conta: lo
script riconosce dall'URL quale e' l'elenco e quale il download.

Esempi:
    # dopo aver copiato i due cURL dal browser
    python pipeline/run_pipeline.py andrea --curl-from-clipboard

    # cookie ancora validi
    python pipeline/run_pipeline.py andrea --download

    # i .fit sono gia' sul disco
    python pipeline/run_pipeline.py andrea

    # ricostruisce tutti i riassunti da zero
    python pipeline/run_pipeline.py andrea --recreate

Uscita: 0 fatto, 1 errore, 2 nessuna attivita' nuova da scaricare,
4 nessun .fit da convertire, 5 alcune attivita' non convertite.
"""
from __future__ import annotations

import argparse
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

PIPELINE = Path(__file__).resolve().parent

LIST_URL = "activitylist-service"
DOWNLOAD_URL = "download-service"


# Comandi che leggono gli appunti, per sistema operativo. Il primo che esiste
# vince. Senza questa tabella, `--curl-from-clipboard` funzionava solo su macOS
# e altrove falliva con "No such file or directory: 'pbpaste'".
CLIPBOARD_CMDS = {
    "darwin": [["pbpaste"]],
    "linux": [["wl-paste"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b"]],
    "win32": [["powershell", "-NoProfile", "-Command", "Get-Clipboard"]],
}


def read_clipboard() -> str:
    """Contenuto degli appunti, su macOS, Linux (Wayland o X11) e Windows."""
    import shutil as _shutil

    for cmd in CLIPBOARD_CMDS.get(sys.platform, []):
        if _shutil.which(cmd[0]) is None:
            continue
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            continue
        if res.stdout.strip():
            return res.stdout

    suggerimento = {
        "linux": "Installa wl-clipboard (Wayland) o xclip (X11), oppure",
        "win32": "Se PowerShell non e' raggiungibile,",
    }.get(sys.platform, "In alternativa,")
    raise SystemExit(
        f"Non riesco a leggere gli appunti su questo sistema ({sys.platform}).\n"
        f"{suggerimento} salva i due comandi cURL in un file e usa:\n"
        f"  pipeline/run_pipeline.py <atleta> --curl-file <percorso>"
    )


def split_curls(text: str) -> tuple[str, str]:
    """Estrae i due comandi cURL e li restituisce come (lista, download).

    Tollera: ordine invertito, righe vuote in mezzo, testo estraneo prima o dopo.
    """
    blocks = [b.strip() for b in re.split(r"\n(?=curl\s)", text) if b.strip().startswith("curl")]
    if len(blocks) < 2:
        raise SystemExit(
            f"Trovati {len(blocks)} comandi cURL, ne servono 2.\n"
            f"Servono la richiesta di ELENCO ({LIST_URL}) e quella di\n"
            f"DOWNLOAD ({DOWNLOAD_URL}). Vedi pipeline/curl.txt.example."
        )

    listing = next((b for b in blocks if LIST_URL in b), None)
    download = next((b for b in blocks if DOWNLOAD_URL in b), None)
    if listing is None or download is None:
        found = ", ".join(
            "elenco" if LIST_URL in b else "download" if DOWNLOAD_URL in b else "?"
            for b in blocks
        )
        raise SystemExit(
            f"Non riconosco i due comandi: trovati [{found}].\n"
            f"Serve una richiesta a {LIST_URL} e una a {DOWNLOAD_URL}."
        )
    return listing, download


def write_curl_file(person: str, listing: str, download: str) -> None:
    """Scrive i cookie nel file di questo atleta, non in uno condiviso.

    Se si stava ancora usando il vecchio `curl.txt` condiviso, da qui in avanti
    si scrive su `curl_<atleta>.txt`: i cookie sono di un account, e un file
    solo per due atleti significa che ogni sync cancella la sessione dell'altro.
    """
    f = PIPELINE / f"curl_{person.strip().lower()}.txt"
    f.write_text(f"{listing}\n\n{download}\n")
    f.chmod(0o600)
    print(f"✓ Aggiornato {f.relative_to(paths.REPO_ROOT)}")


def check_curl_freshness(person: str) -> None:
    """Avviso se i cookie sono vecchi: quelli di Garmin scadono in poche ore."""
    f = paths.curl_file(person)
    if not f.exists():
        raise SystemExit(
            f"{f.relative_to(paths.REPO_ROOT)} non esiste.\n"
            f"Esporta i due comandi cURL con la sessione Garmin di '{person}' "
            f"aperta e rilancia con --curl-from-clipboard "
            f"(vedi pipeline/curl.txt.example)."
        )
    import time

    age_h = (time.time() - f.stat().st_mtime) / 3600
    if age_h > 6:
        print(f"⚠️  {f.name} ha {age_h:.0f} ore: i cookie sono probabilmente scaduti.")
        print("   Se il download fallisce, riesportali e rilancia con --curl-from-clipboard.")




def run_cmd(cmd: list[str], dry_run: bool = False) -> int:
    """Esegue un passo e restituisce il suo codice di uscita.

    Non solleva: un singolo .fit corrotto faceva morire l'intera esecuzione con
    un traceback, buttando via anche la conversione dei file sani. I passi
    decidono da soli se un errore e' fatale.
    """
    logging.info("Eseguo: %s", " ".join(cmd))
    if dry_run:
        return 0
    return subprocess.run(cmd, cwd=str(paths.REPO_ROOT)).returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("person", help="Nome cartella atleta (es. andrea, giorgia)")
    fonte = parser.add_mutually_exclusive_group()
    fonte.add_argument("--curl-from-clipboard", action="store_true",
                       help="Prende i due comandi cURL dagli appunti, aggiorna "
                            "curl_<atleta>.txt e scarica")
    fonte.add_argument("--curl-file",
                       help="Come sopra, leggendo i due cURL da un file")
    parser.add_argument("--download", action="store_true",
                        help="Scarica da Garmin i .fit non ancora presenti, "
                             "riusando i cookie gia' salvati per l'atleta")
    parser.add_argument("--recreate", action="store_true",
                        help="Cancella i riassunti gia' convertiti e li rigenera tutti")
    parser.add_argument("--workers", type=int, default=4,
                        help="Conversioni in parallelo (default: 4)")
    parser.add_argument("--ascent-method", choices=("auto", "fit", "recomputed"), default="auto",
                        help="Provenienza del dislivello: auto usa il valore del "
                             "dispositivo quando c'e', altrimenti lo ricalcola")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Salta le attivita' gia' convertite")
    parser.add_argument("--json-dir",
                        help="Conserva anche il dump JSON della timeseries in questa "
                             "cartella; serve solo per diagnostica")
    parser.add_argument("--dry-run", action="store_true",
                        help="Stampa i comandi senza eseguirli")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )

    person = args.person.strip().lower()
    paths.athlete_dir(person)  # esce con un messaggio utile se non esiste

    sorgente = paths.raw_activities(person)
    if not args.dry_run:
        paths.require_fitparse()

    da_appunti = args.curl_from_clipboard or bool(args.curl_file)
    if da_appunti:
        testo = (read_clipboard() if args.curl_from_clipboard
                 else Path(args.curl_file).read_text())
        write_curl_file(person, *split_curls(testo))

    scarica = args.download or da_appunti
    if scarica:
        check_curl_freshness(person)
        prima = len(list(sorgente.glob("*.fit")))
        if run_cmd([sys.executable, str(PIPELINE / "download_garmin.py"), person],
                   dry_run=args.dry_run) != 0:
            logging.error("Download fallito. Se la sessione Garmin e' scaduta, "
                          "riesporta i comandi cURL e rilancia con --curl-from-clipboard.")
            return 1
        nuove = len(list(sorgente.glob("*.fit"))) - prima
        logging.info("%d attivita' nuove", nuove)
        if nuove == 0 and not args.recreate and args.skip_existing:
            logging.info("Niente da convertire.")
            return 2

    # Un atleta appena creato ha la cartella .fit vuota: senza questo
    # controllo arrivava in fondo stampando "Pipeline completata" e uscendo
    # con 0, e chi la lancia la prima volta crede che abbia funzionato.
    if not args.dry_run and not list(sorgente.glob("*.fit")):
        logging.error("Nessun file .fit in %s", sorgente)
        logging.error("Copia li' le attivita' scaricate da Garmin, oppure scarica con:")
        logging.error("  pipeline/.venv/bin/python pipeline/run_pipeline.py %s "
                      "--curl-from-clipboard", person)
        return 4

    # --recreate cancella i riassunti .md in training_data/activities/.
    # Nota: prima della riorganizzazione questo flag puntava a
    # <person>/data/training_data/activities mentre la conversione scriveva in
    # <person>/training_data/activities: cancellava una cartella morta e
    # --recreate non ricreava niente.
    summaries = paths.activity_summaries(person)
    if args.recreate and summaries.exists():
        if args.dry_run:
            logging.info("(dry-run) rimuoverei %s", summaries)
        else:
            logging.info("Cancello i riassunti esistenti in %s", summaries)
            shutil.rmtree(summaries)
            summaries.mkdir(parents=True, exist_ok=True)

    convert_cmd = [
        sys.executable, str(PIPELINE / "batch_convert.py"),
        "--person", person,
        "--workers", str(args.workers),
        "--ascent-method", args.ascent_method,
    ]
    if args.skip_existing:
        convert_cmd.append("--skip-existing")
    if args.json_dir:
        convert_cmd.extend(["--json-dir", args.json_dir])
    if args.dry_run:
        convert_cmd.append("--dry-run")
    # Una conversione parzialmente fallita non e' fatale: i file sani sono
    # stati scritti e il controllo di allineamento in coda dira' quanti mancano.
    conversione_ok = run_cmd(convert_cmd, dry_run=args.dry_run) == 0
    if not conversione_ok:
        logging.warning("Alcune attivita' non sono state convertite: si prosegue "
                        "con quelle riuscite.")

    split_cmd = [sys.executable, str(PIPELINE / "quarter_split.py"), "--person", person]
    if args.dry_run:
        split_cmd.append("--dry-run")
    if run_cmd(split_cmd, dry_run=args.dry_run) != 0:
        logging.error("Raggruppamento per trimestre fallito.")
        return 1

    rollup_cmd = [sys.executable, str(PIPELINE / "weekly_rollup.py"), person]
    if args.dry_run:
        rollup_cmd.append("--dry-run")
    if run_cmd(rollup_cmd, dry_run=args.dry_run) != 0:
        logging.error("Riepilogo settimanale fallito.")
        return 1

    # Controllo di allineamento: un download interrotto a meta', o un .fit
    # corrotto, lascerebbe meno riassunti che file grezzi senza che niente lo
    # segnali. Il coach leggerebbe uno storico incompleto credendolo completo.
    fit = {f.stem for f in paths.raw_activities(person).glob("*.fit")}
    md = {f.stem for f in paths.activity_summaries(person).glob("*.md")}
    mancanti, orfani = fit - md, md - fit
    if mancanti or orfani:
        if mancanti:
            logging.warning("%d attivita' non convertite: %s%s", len(mancanti),
                            ", ".join(sorted(mancanti)[:5]),
                            " ..." if len(mancanti) > 5 else "")
            logging.warning("Vedi %s", paths.LOGS_DIR / f"{person}-convert.log")
        if orfani:
            logging.warning("%d riassunti senza il .fit corrispondente: %s%s",
                            len(orfani), ", ".join(sorted(orfani)[:5]),
                            " ..." if len(orfani) > 5 else "")
    else:
        logging.info("%d attivita', .fit e riassunti allineati", len(fit))

    logging.info("Pipeline completata per %s", person)
    logging.info("Output in %s", paths.training_data(person))
    return 5 if mancanti else 0


if __name__ == "__main__":
    raise SystemExit(main())
