#!/usr/bin/env bash
# Deploy do fila-eletiva-ui ao CapRover via tarball (--tarFile).
set -euo pipefail

cd "$(dirname "$0")/.."

CAPROVER_URL="${CAPROVER_URL:-https://captain.payao.tech}"
APP_NAME="${UI_APP_NAME:-fila-eletiva-ui}"

echo "[1/3] preparando tarball..."
TMP_DIR=$(mktemp -d -t fila-ui-XXXXXX)
TMP_TAR="${TMP_DIR}.tar.gz"

cleanup() {
    rm -rf "${TMP_DIR}" "${TMP_TAR}"
}
trap cleanup EXIT

cp captain-definition.ui.json "${TMP_DIR}/captain-definition"
cp Dockerfile.ui "${TMP_DIR}/"
cp requirements.txt "${TMP_DIR}/"
cp -r ui "${TMP_DIR}/ui"
cp -r .streamlit "${TMP_DIR}/.streamlit"

# Limpa caches Python
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
