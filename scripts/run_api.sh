#!/usr/bin/env bash
# Roda a FastAPI em http://localhost:8000
# Use: wsl -- bash /mnt/d/.../scripts/run_api.sh
set -euo pipefail
cd /mnt/d/ZELLO/IGES/fila-eletiva
source .venv/bin/activate
exec uvicorn app.api:app --host 0.0.0.0 --port 8000 --log-level info
