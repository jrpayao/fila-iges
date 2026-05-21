"""Template — Top N procedimentos solicitados (nested em solicitacao-ambulatorial).

procedimentos e um array nested com codigo_interno, codigo_sigtap, descricao_sigtap,
descricao_interna. Exige nested query + nested agg.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.config import DF_INDEX_SUFFIX
from app.es.templates._helpers import df_filter, shard_size_for

NAME = "top_procedimentos"
DESCRIPTION = (
    "Top N procedimentos solicitados em solicitacao-ambulatorial. Usa nested agg sobre "
    "procedimentos.codigo_sigtap. Use para 'top procedimentos', 'principais exames pedidos', "
    "'procedimentos mais solicitados em X dias'."
)


class Params(BaseModel):
    janela_dias: int = Field(..., ge=1, le=365)
    top_n: int = Field(10, ge=1, le=50)


def index(params: Params) -> str:
    return f"solicitacao-ambulatorial-{DF_INDEX_SUFFIX}"


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
            "procedimentos_nested": {
                "nested": {"path": "procedimentos"},
                "aggs": {
                    "top_sigtap": {
                        "terms": {
                            "field": "procedimentos.codigo_sigtap",
                            "size": params.top_n,
                            "shard_size": shard_size_for(params.top_n),
                            "order": {"_count": "desc"},
                        },
                        "aggs": {
                            "enriquecimento": {
                                "top_hits": {
                                    "size": 1,
                                    "_source": True,
                                }
                            }
                        },
                    }
                },
            }
        },
    }


def consolidate(es_response: dict[str, Any], params: Params) -> dict[str, Any]:
    total = es_response.get("hits", {}).get("total", {}).get("value", 0)
    took_ms = es_response.get("took", 0)
    nested_agg = es_response.get("aggregations", {}).get("procedimentos_nested", {})
    nested_total = nested_agg.get("doc_count", 0)
    buckets = nested_agg.get("top_sigtap", {}).get("buckets", [])
    sum_other = nested_agg.get("top_sigtap", {}).get("sum_other_doc_count", 0)
    error_upper = nested_agg.get("top_sigtap", {}).get("doc_count_error_upper_bound", 0)
    linhas = []
    for b in buckets:
        descricao_hits = b.get("enriquecimento", {}).get("hits", {}).get("hits", [])
        descricao_sigtap = ""
        descricao_interna = ""
        codigo_interno = ""
        if descricao_hits:
            # Em nested context, _source ja vem como o objeto nested direto.
            source = descricao_hits[0].get("_source", {}) or {}
            descricao_sigtap = (source.get("descricao_sigtap") or "").strip()
            descricao_interna = (source.get("descricao_interna") or "").strip()
            codigo_interno = source.get("codigo_interno") or ""
        linhas.append(
            {
                "codigo_sigtap": b["key"],
                "codigo_interno": codigo_interno,
                "descricao_sigtap": descricao_sigtap,
                "descricao_interna": descricao_interna,
                "count": b["doc_count"],
                "pct": round(100 * b["doc_count"] / nested_total, 2) if nested_total else None,
            }
        )
    return {
        "linhas": linhas,
        "totais": {
            "documentos_no_universo_filtrado": total,
            "procedimentos_total_aninhado": nested_total,
            "documentos_fora_do_top": sum_other,
            "erro_maximo_contagem": error_upper,
        },
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
