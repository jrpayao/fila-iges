#!/usr/bin/env bash
# Deploy do fila-eletiva-api ao CapRover via tarball (--tarFile).
# Tarball evita o prompt interativo de "voce nao esta em git root".
set -euo pipefail

cd "$(dirname "$0")/.."

CAPROVER_URL="${CAPROVER_URL:-https://captain.payao.tech}"
APP_NAME="${API_APP_NAME:-fila-eletiva-api}"

echo "[1/3] preparando tarball..."
TMP_DIR=$(mktemp -d -t fila-api-XXXXXX)
TMP_TAR="${TMP_DIR}.tar.gz"

cleanup() {
    rm -rf "${TMP_DIR}" "${TMP_TAR}"
}
trap cleanup EXIT

# captain-definition.api.json vira o captain-definition canonico
cp captain-definition.api.json "${TMP_DIR}/captain-definition"
cp Dockerfile.api "${TMP_DIR}/"
cp requirements.txt "${TMP_DIR}/"
cp -r app "${TMP_DIR}/app"

# Limpa caches Python que poderiam ter vazado
find "${TMP_DIR}" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "${TMP_DIR}" -name '*.pyc' -delete 2>/dev/null || true

tar -C "${TMP_DIR}" -czf "${TMP_TAR}" .
TAR_SIZE=$(du -h "${TMP_TAR}" | cut -f1)
echo "  tarball: ${TMP_TAR} (${TAR_SIZE})"

echo "[2/3] caprover deploy ${APP_NAME} em ${CAPROVER_URL}..."
caprover deploy \
    --caproverUrl "$CAPROVER_URL" \
    --appName "$APP_NAME" \
    --tarFile "$TMP_TAR"

echo "[3/3] OK — ${APP_NAME} deployed"
echo "Verificar logs: dashboard ${CAPROVER_URL} > Apps > ${APP_NAME} > App Logs"
