"""FastAPI wrapper sobre engine.ask.

Endpoints:
- POST /chat          -> {pergunta, [pii_exposure, justificativa]} -> resultado completo
- GET  /health        -> sanidade (config + ES alcancavel + OpenAI alcancavel)
- GET  /audit         -> tail do audit.jsonl (debug)
- GET  /              -> info do servico
"""

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from app import __version__, audit, query_log
from app.config import settings
from app.engine import EngineError, ask
from app.vagas.orchestrator import get_df

# --- Basic Auth opcional (env-gated, util pra deploy publico) ---
_AUTH_ENABLED = os.environ.get("API_AUTH_ENABLED", "false").lower() == "true"
_AUTH_USER = os.environ.get("API_AUTH_USER", "")
_AUTH_PASS = os.environ.get("API_AUTH_PASS", "")
_basic_security = HTTPBasic(auto_error=False)


def require_auth(credentials: HTTPBasicCredentials | None = Depends(_basic_security)) -> None:
    """Dependencia FastAPI — se API_AUTH_ENABLED=true, exige Basic Auth."""
    if not _AUTH_ENABLED:
        return
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais ausentes",
            headers={"WWW-Authenticate": "Basic"},
        )
    user_ok = secrets.compare_digest(credentials.username, _AUTH_USER)
    pass_ok = secrets.compare_digest(credentials.password, _AUTH_PASS)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais invalidas",
            headers={"WWW-Authenticate": "Basic"},
        )

app = FastAPI(
    title="fila-eletiva",
    version=__version__,
    description="Chat sobre fila SISREG-DF (IGES/ZELLO) com pipeline multi-agente.",
)

# CORS para UI local (Streamlit em :8501)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class HistoryTurn(BaseModel):
    pergunta: str = ""
    metric: str | None = None
    filters: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    pergunta: str = Field(..., min_length=1, max_length=500)
    history: list[HistoryTurn] = Field(default_factory=list, description="Turnos anteriores (memoria de conversa)")
    pii_exposure: bool = Field(default=False)
    justificativa: str = Field(default="")


class ChatResponse(BaseModel):
    narrativa: str
    dados: Any | None
    proveniencia: dict[str, Any]
    chart: dict[str, Any] | None = None
    sugestoes: list[dict[str, Any]] = []


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "fila-eletiva",
        "version": __version__,
        "app_mode": settings.app_mode,
        "poc_expires_at": str(settings.poc_expires_at),
        "endpoints": ["GET /", "GET /health", "POST /chat", "GET /audit", "GET /insights"],
    }


@app.get("/insights", dependencies=[Depends(require_auth)])
def insights(days: int = 7) -> dict[str, Any]:
    """Agrega o log diario de perguntas: temas mais pedidos, lacunas, volume."""
    return query_log.summarize(days=days)


@app.get("/health")
def health() -> dict[str, Any]:
    checks: dict[str, Any] = {
        "config_loaded": True,
        "fonte_reachable": False,
        "openai_reachable": False,
        "app_mode": settings.app_mode,
        "poc_expires_at": str(settings.poc_expires_at),
    }
    # Fonte de vagas: cache carregado (com competencias)
    try:
        df = get_df()
        checks["fonte_reachable"] = not df.empty
        checks["competencias_em_cache"] = int(df["competencia"].nunique()) if not df.empty else 0
        checks["registros_em_cache"] = int(len(df))
    except Exception as exc:
        checks["fonte_error"] = str(exc)
    # OpenAI check
    try:
        with httpx.Client(timeout=3) as c:
            r = c.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            )
            checks["openai_reachable"] = r.status_code == 200
            if r.status_code != 200:
                checks["openai_status"] = r.status_code
    except Exception as exc:
        checks["openai_error"] = str(exc)

    ok = checks["config_loaded"] and checks["fonte_reachable"] and checks["openai_reachable"]
    return {"ok": ok, **checks}


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_auth)])
def chat(req: ChatRequest) -> ChatResponse:
    try:
        result = ask(
            req.pergunta,
            history=[h.model_dump() for h in req.history],
            pii_exposure=req.pii_exposure,
            justificativa=req.justificativa,
        )
    except EngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        audit.event("api.chat.error", error=str(exc), error_type=type(exc).__name__)
        raise HTTPException(status_code=500, detail=f"Erro interno: {exc}")
    return ChatResponse(**result)


@app.get("/audit", dependencies=[Depends(require_auth)])
def audit_tail(limit: int = 50) -> dict[str, Any]:
    path = Path(settings.audit_jsonl_path)
    if not path.exists():
        return {"events": [], "total_read": 0}
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    tail = lines[-limit:]
    events = []
    for line in tail:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return {
        "events": events,
        "total_read": len(events),
        "file": str(path.resolve()),
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
