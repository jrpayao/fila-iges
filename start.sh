#!/bin/sh
# ofertas-vagas — sobe a API (interna, 8000) e a UI (publica, 80) no mesmo container.
set -e

# API FastAPI interna — so localhost, consumida pela UI.
uvicorn app.api:app \
    --host 127.0.0.1 --port 8000 \
    --log-level info --proxy-headers --forwarded-allow-ips='*' &

# UI Streamlit publica na 8501 (processo em primeiro plano = PID 1 do container).
# CapRover: configure "Container HTTP Port = 8501".
exec streamlit run ui/streamlit_app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false
