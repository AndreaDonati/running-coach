#!/usr/bin/env bash
set -euo pipefail
# Crea o aggiorna il venv in `pipeline/.venv` e installa `requirements.txt`.
# Da lanciare dalla root del repo: ./pipeline/setup_venv.sh

PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PIPELINE_DIR/.venv"
PYTHON=${PYTHON:-python3}

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python non trovato ('$PYTHON')." >&2
  echo "Installa Python 3.9 o superiore, oppure indica quale usare:" >&2
  echo "  PYTHON=/percorso/di/python3 ./pipeline/setup_venv.sh" >&2
  exit 1
fi

# Minimo verificato: 3.9. La pipeline e i test girano su 3.9.6 e su 3.14.
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "Serve Python 3.9 o superiore, trovato $("$PYTHON" -V 2>&1)." >&2
  echo "Indica un interprete piu' recente con:" >&2
  echo "  PYTHON=/percorso/di/python3.12 ./pipeline/setup_venv.sh" >&2
  exit 1
fi

echo "Using Python: ${PYTHON} ($("$PYTHON" -V 2>&1))"
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment at $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
else
  echo "Virtual environment exists at $VENV_DIR"
fi

echo "Upgrading pip and core build tools"
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel

REQ_FILE="$PIPELINE_DIR/requirements.txt"
if [ -f "$REQ_FILE" ]; then
  echo "Installing from $REQ_FILE"
  "$VENV_DIR/bin/pip" install -r "$REQ_FILE"
else
  echo "No requirements.txt found at $REQ_FILE — skipping install"
fi

echo
echo "Fatto. Per usare la pipeline, la via piu' sicura e' l'interprete esplicito:"
echo "  $VENV_DIR/bin/python pipeline/run_pipeline.py <atleta>"
echo
echo "In alternativa attiva il venv:"
echo "  source $VENV_DIR/bin/activate"
