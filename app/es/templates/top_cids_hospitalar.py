"""Template — Top N CIDs em solicitacao-hospitalar (familia hospitalar-v3).

Atencao: na familia hospitalar-v3, codigo_cid e text+keyword (precisa .keyword).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import DF_INDEX_SUFFIX
from app.es.templates._helpers import (
    consolidate_terms_buckets,
    df_filter_hospitalar,
    shard_size_for,
)

NAME = "top_cids_hospitalar"
DESCRIPTION = (
    "Top N CIDs em solicitacao-hospitalar (internacoes). Use para 'top CIDs hospitalares', "
    "'principais doencas que levaram a internacao em X dias', 'top CIDs de internacao'. "
    "Filtra por janela em data_solicitacao OU data_internacao."
)


class Params(BaseModel):
    janela_dias: int = Field(..., ge=1, le=365)
    top_n: int = Field(10, ge=1, le=50)
    base_temporal: Literal["data_solicitacao", "data_internacao", "data_atualizacao"] = Field(
        "data_solicitacao",
        description="Campo de data para o range filter.",
    )


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
                    {"range": {params.base_temporal: {"gte": f"now-{params.janela_dias}d/d", "lte": "now/d"}}},
                ]
            }
        },
        "aggs": {
            "top_cids": {
                "terms": {
                    "field": "codigo_cid.keyword",
                    "size": params.top_n,
                    "shard_size": shard_size_for(params.top_n),
                    "order": {"_count": "desc"},
                },
                "aggs": {
                    "enriquecimento": {
                        "top_hits": {
                            "size": 1,
                            "_source": ["descricao_cid"],
                        }
                    }
                },
            }
        },
    }


def consolidate(es_response: dict[str, Any], params: Params) -> dict[str, Any]:
    return consolidate_terms_buckets(
        es_response,
        "top_cids",
        descricao_field="descricao_cid",
        key_label="cid",
    )


def tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": NAME,
            "description": DESCRIPTION,
            "parameters": Params.model_json_schema(),
        },
    }
