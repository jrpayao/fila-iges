#!/usr/bin/env bash
# Build local das duas imagens para sanidade dos Dockerfiles.
set -euo pipefail
cd /mnt/d/ZELLO/IGES/fila-eletiva

echo "=== Build da imagem API ==="
docker build -f Dockerfile.api -t fila-eletiva-api:local .
echo

echo "=== Build da imagem UI ==="
docker build -f Dockerfile.ui -t fila-eletiva-ui:local .
echo

echo "=== Tamanhos das imagens ==="
docker images --filter "reference=fila-eletiva-*:local" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
