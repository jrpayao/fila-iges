#!/usr/bin/env bash
# Roda a UI Streamlit em http://localhost:8501
# Pressupoe API rodando em :8000.
# Use: wsl -- bash /mnt/d/.../scripts/run_ui.sh
set -euo pipefail
cd /mnt/d/ZELLO/IGES/fila-eletiva
source .venv/bin/activate
exec streamlit run ui/streamlit_app.py --server.port 8501 --server.headless true
