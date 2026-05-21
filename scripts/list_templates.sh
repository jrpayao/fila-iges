#!/usr/bin/env bash
set -euo pipefail
cd /mnt/d/ZELLO/IGES/fila-eletiva
source .venv/bin/activate
python - <<'PY'
from app.es import registry
print(f"templates registrados: {len(registry.names())}")
for n in registry.names():
    print(f"  - {n}")
PY
