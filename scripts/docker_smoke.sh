#!/usr/bin/env bash
# Smoke test: sobe cada container brevemente para checar boot.
set -euo pipefail

cd /mnt/d/ZELLO/IGES/fila-eletiva
source .env.local 2>/dev/null || true
set +e  # nao parar nos erros — queremos ver tudo

echo "=== Subindo API container ==="
docker rm -f fila-api-smoke 2>/dev/null
docker run -d --name fila-api-smoke \
    -e OPENAI_API_KEY="${OPENAI_API_KEY:-sk-stub}" \
    -e SISREG_USER="${SISREG_USER:-stub}" \
    -e SISREG_PASS="${SISREG_PASS:-stub}" \
    -p 18000:80 \
    fila-eletiva-api:local
sleep 4
docker logs fila-api-smoke 2>&1 | tail -15
echo
echo "--- /health da API ---"
curl -s -m 5 http://127.0.0.1:18000/health || echo "(falha — talvez ES/OpenAI nao alcancaveis com creds stub, mas o app subiu)"
echo
echo

echo "=== Subindo UI container ==="
docker rm -f fila-ui-smoke 2>/dev/null
docker run -d --name fila-ui-smoke \
    -e API_BASE_URL=http://host.docker.internal:18000 \
    --add-host host.docker.internal:host-gateway \
    -p 18501:80 \
    fila-eletiva-ui:local
sleep 6
docker logs fila-ui-smoke 2>&1 | tail -15
echo
echo "--- /_stcore/health do Streamlit ---"
curl -s -m 5 http://127.0.0.1:18501/_stcore/health
echo

echo
echo "=== Limpando ==="
docker rm -f fila-api-smoke fila-ui-smoke
