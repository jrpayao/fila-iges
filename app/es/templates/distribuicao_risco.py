"""Template — Distribuicao por classificacao de risco em uma janela.

Aplica em solicitacao-ambulatorial ou marcacao-ambulatorial.
Mapeia codigo_classificacao_risco em descricao humana (Prioridade 0/1/2/3).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import DF_INDEX_SUFFIX
from app.es.templates._helpers import RISCO_DESCRICAO, df_filter

NAME = "distribuicao_risco"
DESCRIPTION = (
    "Distribuicao por classificacao de risco (Prioridade 0-3) em uma janela temporal. "
    "Use para: 'qual a distribuicao por risco', 'quanto eh urgente vs eletivo', "
    "'composicao de prioridades na fila'."
)


class Params(BaseModel):
    indice: Literal["solicitacao-ambulatorial", "marcacao-ambulatorial"] = Field(...)
    janela_dias: int = Field(30, ge=1, le=365)


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
                    {"range": {"data_solicitacao": {"gte": f"now-{params.janela_dias}d/d", "lte": "now/d"}}},
                ]
            }
        },
        "aggs": {
            "por_risco": {
                "terms": {"field": "codigo_classificacao_risco", "size": 10}
            }
        },
    }


def consolidate(es_response: dict[str, Any], params: Params) -> dict[str, Any]:
    total = es_response.get("hits", {}).get("total", {}).get("value", 0)
    took_ms = es_response.get("took", 0)
    buckets = es_response.get("aggregations", {}).get("por_risco", {}).get("buckets", [])
    linhas = []
    for b in buckets:
        codigo = str(b["key"])
        descricao = RISCO_DESCRICAO.get(codigo, f"Codigo {codigo} (nao mapeado)")
        linhas.append(
            {
                "codigo_classificacao_risco": codigo,
                "descricao": descricao,
                "count": b["doc_count"],
                "pct": round(100 * b["doc_count"] / total, 2) if total else None,
            }
        )
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
