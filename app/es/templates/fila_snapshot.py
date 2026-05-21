"""Template — Snapshot atual da fila ambulatorial.

Sem range temporal — retrata o estado AGORA. Conta solicitacoes pendentes em
solicitacao-ambulatorial por status (pendente regulador, pendente fila, reenviada).
"""

from typing import Any

from pydantic import BaseModel, Field

from app.config import DF_INDEX_SUFFIX
from app.es.templates._helpers import STATUS_PENDENTES, df_filter

NAME = "fila_snapshot"
DESCRIPTION = (
    "Snapshot ATUAL da fila ambulatorial DF — quem esta pendente AGORA, sem filtro temporal. "
    "Conta por status_solicitacao restrito a pendentes (PENDENTE/REGULADOR, FILA DE ESPERA, REENVIADA). "
    "Use para: 'como esta a fila hoje', 'quantas solicitacoes pendentes existem agora', 'estado atual da fila'."
)


class Params(BaseModel):
    # Sem range. Sem janela. So um filtro de status.
    incluir_distribuicao_por_risco: bool = Field(
        True,
        description="Se true, agrega tambem por classificacao_risco dentro do snapshot.",
    )


def index(params: Params) -> str:
    return f"solicitacao-ambulatorial-{DF_INDEX_SUFFIX}"


def render(params: Params) -> dict[str, Any]:
    aggs: dict[str, Any] = {
        "por_status": {
            "terms": {"field": "status_solicitacao.keyword", "size": 10},
        }
    }
    if params.incluir_distribuicao_por_risco:
        aggs["por_risco"] = {
            "terms": {"field": "codigo_classificacao_risco", "size": 10}
        }
    return {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "must": [
                    df_filter(),
                    {"terms": {"status_solicitacao.keyword": STATUS_PENDENTES}},
                ]
            }
        },
        "aggs": aggs,
    }


def consolidate(es_response: dict[str, Any], params: Params) -> dict[str, Any]:
    from app.es.templates._helpers import RISCO_DESCRICAO

    total = es_response.get("hits", {}).get("total", {}).get("value", 0)
    took_ms = es_response.get("took", 0)
    aggregations = es_response.get("aggregations", {})

    por_status = [
        {
            "status_solicitacao": b["key"],
            "count": b["doc_count"],
            "pct": round(100 * b["doc_count"] / total, 2) if total else None,
        }
        for b in aggregations.get("por_status", {}).get("buckets", [])
    ]
    out: dict[str, Any] = {
        "total_pendentes_agora": total,
        "por_status": por_status,
        "performance": {"took_ms": took_ms},
    }
    if "por_risco" in aggregations:
        out["por_risco"] = [
            {
                "codigo_classificacao_risco": str(b["key"]),
                "descricao": RISCO_DESCRICAO.get(str(b["key"]), f"Codigo {b['key']}"),
                "count": b["doc_count"],
                "pct": round(100 * b["doc_count"] / total, 2) if total else None,
            }
            for b in aggregations["por_risco"]["buckets"]
        ]
    return out


def tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": NAME,
            "description": DESCRIPTION,
            "parameters": Params.model_json_schema(),
        },
    }
