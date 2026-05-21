"""Template — Distribuicao por status_solicitacao em uma janela.

Aplica em solicitacao-ambulatorial ou marcacao-ambulatorial.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import DF_INDEX_SUFFIX
from app.es.templates._helpers import df_filter

NAME = "distribuicao_status"
DESCRIPTION = (
    "Distribuicao por status_solicitacao em uma janela temporal. Use para: "
    "'qual a distribuicao por status', 'composicao dos status na fila', "
    "'quantos estao pendentes vs agendados'. Default 30 dias."
)


class Params(BaseModel):
    indice: Literal["solicitacao-ambulatorial", "marcacao-ambulatorial"] = Field(...)
    janela_dias: int = Field(30, ge=1, le=365)
    base_temporal: Literal["data_solicitacao", "data_atualizacao"] = Field("data_atualizacao")
    top_n: int = Field(20, ge=1, le=30)


def index(params: Params) -> str:
    return f"{params.indice}-{DF_INDEX_SUFFIX}"


def render(params: Params) -> dict[str, Any]:
    return {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "must": [
                    df_filter(),
                    {"range": {params.base_temporal: {"gte": f"now-{params.janela_dias}d/d", "lte": "now/d"}}},
                ]
            }
        },
        "aggs": {
            "por_status": {
                "terms": {
                    "field": "status_solicitacao.keyword",
                    "size": params.top_n,
                    "order": {"_count": "desc"},
                }
            }
        },
    }


def consolidate(es_response: dict[str, Any], params: Params) -> dict[str, Any]:
    total = es_response.get("hits", {}).get("total", {}).get("value", 0)
    took_ms = es_response.get("took", 0)
    buckets = es_response.get("aggregations", {}).get("por_status", {}).get("buckets", [])
    linhas = [
        {
            "status_solicitacao": b["key"],
            "count": b["doc_count"],
            "pct": round(100 * b["doc_count"] / total, 2) if total else None,
        }
        for b in buckets
    ]
    return {
        "linhas": linhas,
        "totais": {"documentos_no_universo_filtrado": total},
        "performance": {"took_ms": took_ms},
    }


def tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": NAME,
            "description": DESCRIPTION,
            "parameters": Params.model_json_schema(),
        },
    }
