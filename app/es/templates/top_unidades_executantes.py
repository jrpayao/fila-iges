"""Template — Top N unidades executantes (CNES) em marcacao ou hospitalar.

Util para "quais unidades mais atendem", "hospitais com mais internacoes", etc.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import DF_INDEX_SUFFIX
from app.es.templates._helpers import (
    STATUS_ATENDIDOS,
    consolidate_terms_buckets,
    df_filter,
    df_filter_hospitalar,
    shard_size_for,
)

NAME = "top_unidades_executantes"
DESCRIPTION = (
    "Top N unidades executantes (CNES) em marcacao-ambulatorial ou solicitacao-hospitalar. "
    "Use para: 'quais unidades mais atendem', 'hospitais com mais internacoes', "
    "'ranking de prestadores'. Em marcacao, default filtra por status CONFIRMADO (atendimentos efetivos)."
)


class Params(BaseModel):
    indice: Literal["marcacao-ambulatorial", "solicitacao-hospitalar"] = Field(...)
    apenas_confirmados: bool = Field(
        True,
        description="So em marcacao-ambulatorial: filtra status=CONFIRMADO. Em hospitalar e ignorado.",
    )
    janela_dias: int = Field(..., ge=1, le=365)
    top_n: int = Field(10, ge=1, le=50)


def index(params: Params) -> str:
    return f"{params.indice}-{DF_INDEX_SUFFIX}"


def render(params: Params) -> dict[str, Any]:
    if params.indice == "marcacao-ambulatorial":
        must: list[dict[str, Any]] = [
            df_filter(),
            {"range": {"data_confirmacao": {"gte": f"now-{params.janela_dias}d/d", "lte": "now/d"}}},
        ]
        if params.apenas_confirmados:
            must.append({"terms": {"status_solicitacao.keyword": STATUS_ATENDIDOS}})
        campo_unidade = "codigo_unidade_executante"
        campo_nome = "nome_unidade_executante.keyword"
    else:  # solicitacao-hospitalar
        must = [
            df_filter_hospitalar(),
            {"range": {"data_internacao": {"gte": f"now-{params.janela_dias}d/d", "lte": "now/d"}}},
        ]
        campo_unidade = "codigo_unidade_executante.keyword"
        campo_nome = "nome_unidade_executante.keyword"

    return {
        "size": 0,
        "track_total_hits": True,
        "query": {"bool": {"must": must}},
        "aggs": {
            "top_unidades": {
                "terms": {
                    "field": campo_unidade,
                    "size": params.top_n,
                    "shard_size": shard_size_for(params.top_n),
                    "order": {"_count": "desc"},
                },
                "aggs": {
                    "enriquecimento": {
                        "top_hits": {
                            "size": 1,
                            "_source": [campo_nome.replace(".keyword", "")],
                        }
                    }
                },
            }
        },
    }


def consolidate(es_response: dict[str, Any], params: Params) -> dict[str, Any]:
    return consolidate_terms_buckets(
        es_response,
        "top_unidades",
        descricao_field="nome_unidade_executante",
        key_label="codigo_unidade",
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
