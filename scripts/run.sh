#!/usr/bin/env bash
# Wrapper para rodar o motor com a pergunta como argumento.
# Uso: wsl -- bash /mnt/d/.../scripts/run.sh "sua pergunta"
set -euo pipefail
cd /mnt/d/ZELLO/IGES/fila-eletiva
source .venv/bin/activate
python -m app "$@"
