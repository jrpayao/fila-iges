"""Template — Distribuicao URGENTE x ELETIVA em solicitacao-hospitalar.

Campo `carater` (text+keyword na familia hospitalar-v3).
"""

from typing import Any

from pydantic import BaseModel, Field

from app.config import DF_INDEX_SUFFIX
from app.es.templates._helpers import df_filter_hospitalar

NAME = "distribuicao_carater_hospitalar"
DESCRIPTION = (
    "Distribuicao URGENTE/ELETIVA das solicitacoes hospitalares em uma janela. "
    "Use para: 'quantas internacoes urgentes', 'urgencia vs eletiva no mes', "
    "'composicao por carater hospitalar'."
)


class Params(BaseModel):
    janela_dias: int = Field(30, ge=1, le=365)


def index(params: Params) -> str:
    return f"solicitacao-hospitalar-{DF_INDEX_SUFFIX}"


def render(params: Params) -> dict[str, Any]:
    return {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "must": [
                    df_filter_hospitalar(),
                    {"range": {"data_solicitacao": {"gte": f"now-{params.janela_dias}d/d", "lte": "now/d"}}},
                ]
            }
        },
        "aggs": {
            "por_carater": {
                "terms": {"field": "carater.keyword", "size": 5}
            }
        },
    }


def consolidate(es_response: dict[str, Any], params: Params) -> dict[str, Any]:
    total = es_response.get("hits", {}).get("total", {}).get("value", 0)
    took_ms = es_response.get("took", 0)
    buckets = es_response.get("aggregations", {}).get("por_carater", {}).get("buckets", [])
    linhas = [
        {
            "carater": b["key"],
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
