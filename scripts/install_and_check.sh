#!/usr/bin/env bash
set -euo pipefail
cd /mnt/d/ZELLO/IGES/fila-eletiva
source .venv/bin/activate
echo "[1/3] instalando deps (incluindo fastapi/uvicorn/streamlit)..."
python -m pip install -q -r requirements.txt
echo "[2/3] verificando imports da api..."
python -c "from app.api import app; print('  api OK')"
echo "[3/3] verificando streamlit..."
python -c "import streamlit; print('  streamlit OK, versao', streamlit.__version__)"
echo "===INSTALL_DONE==="
