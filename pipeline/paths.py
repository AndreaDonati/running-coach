"""Risoluzione dei percorsi del repository.

Unico posto in cui e' scritto dove stanno le cose. Prima ogni script aveva la
sua copia della convenzione (`<person>/data/activities`, `<person>/training_data`,
...) e due di quelle copie erano fuori sincrono fra loro, cosa che rendeva
`run_pipeline.py --recreate` un no-op silenzioso.

I percorsi sono derivati da `__file__`, non dalla directory corrente: gli script
si possono lanciare da qualunque punto del filesystem.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = REPO_ROOT / "pipeline"
ATHLETES_DIR = REPO_ROOT / "athletes"
LOGS_DIR = PIPELINE_DIR / "logs"

# Cartella modello: si copia per aggiungere un atleta, non e' un atleta.
TEMPLATE_NAME = "_template"


def known_athletes() -> list[str]:
    """Nomi degli atleti presenti, in ordine alfabetico."""
    if not ATHLETES_DIR.is_dir():
        return []
    return sorted(
        d.name
        for d in ATHLETES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith((".", "_"))
    )


def athlete_dir(person: str) -> Path:
    """Cartella di un atleta, verificata.

    Solleva `SystemExit` con un messaggio utile invece di restituire un percorso
    inesistente che poi fallisce dieci righe piu' avanti in modo oscuro.
    """
    name = person.strip().lower()
    if name == TEMPLATE_NAME:
        raise SystemExit(
            f"'{TEMPLATE_NAME}' e' la cartella modello, non un atleta. "
            f"Copiala con: cp -R athletes/{TEMPLATE_NAME} athletes/<nome>"
        )
    path = ATHLETES_DIR / name
    if not path.is_dir():
        available = ", ".join(known_athletes()) or "nessuno"
        raise SystemExit(
            f"Atleta '{person}' non trovato in {ATHLETES_DIR}.\n"
            f"Disponibili: {available}\n"
            f"Per aggiungerlo: cp -R athletes/{TEMPLATE_NAME} athletes/{name}"
        )
    return path


def raw_activities(person: str) -> Path:
    """`.fit` scaricati da Garmin. Input della conversione."""
    return athlete_dir(person) / "raw" / "activities"


def training_data(person: str) -> Path:
    """Output della pipeline: file trimestrali, manifest, summary."""
    return athlete_dir(person) / "training_data"


def activity_summaries(person: str) -> Path:
    """Un `.md` per attivita'. E' cio' che il coach legge davvero."""
    return training_data(person) / "activities"


def plans_dir(person: str) -> Path:
    return athlete_dir(person) / "plans"


def weeks_dir(person: str) -> Path:
    return plans_dir(person) / "weeks"


def profile(person: str) -> Path:
    return athlete_dir(person) / "profile.md"


def require_fitparse() -> None:
    """Preflight: fallisce subito e con una spiegazione se manca `fitparse`.

    La conversione lancia i sottoprocessi con `sys.executable`. Lanciata con un
    Python di sistema senza dipendenze produceva 'Converted: 0, Errors: N' e un
    `ModuleNotFoundError` sepolto nello stderr di ogni sottoprocesso. Meglio
    accorgersene prima di processare 600 file.
    """
    try:
        import fitparse  # noqa: F401
    except ImportError:
        import sys

        raise SystemExit(
            f"'fitparse' non e' installato nel Python in uso ({sys.executable}).\n"
            f"Usa l'interprete del venv della pipeline:\n"
            f"  {PIPELINE_DIR / '.venv' / 'bin' / 'python'} <script> ...\n"
            f"Se il venv non esiste ancora: ./pipeline/setup_venv.sh"
        )
