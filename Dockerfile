# ofertas-vagas — imagem unica (API FastAPI + UI Streamlit no mesmo container).
# Build context: raiz do projeto. CapRover espera a porta 80 (Streamlit publico).
# A API roda interna em 127.0.0.1:8000; a UI a consome via API_BASE_URL.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# Deps (camada cacheada — muda raro)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codigo
COPY app /app/app
COPY ui /app/ui
COPY .streamlit /app/.streamlit
COPY start.sh /app/start.sh

# Usuario nao-root + diretorios persistentes (cache de vagas + logs diarios)
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data /app/logs \
    && chmod +x /app/start.sh \
    && chown -R appuser:appuser /app
USER appuser

# Config runtime (sobrescreva os segredos no painel do CapRover)
ENV API_BASE_URL=http://localhost:8000 \
    VAGAS_CACHE_PATH=/app/data/vagas_cache.sqlite \
    QUERY_LOG_DIR=/app/logs \
    AUDIT_JSONL_PATH=/app/logs/audit.jsonl \
    APP_MODE=poc

# Streamlit publico na 8501 (nao-root nao pode bind < 1024). CapRover: Container HTTP Port = 8501.
EXPOSE 8501

# Saude = Streamlit no ar (a API interna e checada pela propria UI ao consultar)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://127.0.0.1:8501/_stcore/health', timeout=3).raise_for_status()" || exit 1

CMD ["/app/start.sh"]
