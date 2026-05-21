#!/usr/bin/env bash
set -euo pipefail
cd /mnt/d/ZELLO/IGES/fila-eletiva
source .venv/bin/activate
python - <<'PY'
from app.config import settings
from app.es.client import SisregESClient
import json

body = json.loads(open("scripts/queries/debug_nested.json").read())
with SisregESClient() as es:
    r = es.search(f"solicitacao-ambulatorial-{__import__('app').config.DF_INDEX_SUFFIX}", body)
print(json.dumps(r.get("aggregations", {}), indent=2, ensure_ascii=False)[:3000])
PY
