"""Template — Top N unidades solicitantes (CNES) em um indice ambulatorial.

Aplica em: solicitacao-ambulatorial ou marcacao-ambulatorial.
Util para "quais unidades pedem mais X" ou "ranking de unidades por volume".
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import DF_INDEX_SUFFIX
from app.es.templates._helpers import (
    STATUS_CANCELADOS,
    consolidate_terms_buckets,
    df_filter,
    shard_size_for,
)

NAME = "top_unidades_solicitantes"
DESCRIPTION = (
    "Top N unidades solicitantes (CNES) em ambulatorial, por contagem de pedidos. "
    "Use para: 'quais unidades mais pedem consultas', 'ranking de unidades solicitantes', "
    "'unidades com mais cancelamentos'. Pode filtrar por tipo (todos | cancelados)."
)


class Params(BaseModel):
    indice: Literal["solicitacao-ambulatorial", "marcacao-ambulatorial"] = Field(
        ...,
        description="solicitacao-ambulatorial pra fila atual; marcacao-ambulatorial pra historico.",
    )
    tipo: Literal["todos", "cancelados"] = Field("todos")
    janela_dias: int = Field(..., ge=1, le=365)
    top_n: int = Field(10, ge=1, le=50)


def index(params: Params) -> str:
    return f"{params.indice}-{DF_INDEX_SUFFIX}"


def render(params: Params) -> dict[str, Any]:
    must: list[dict[str, Any]] = [
        df_filter(),
        {"range": {"data_solicitacao": {"gte": f"now-{params.janela_dias}d/d", "lte": "now/d"}}},
    ]
    if params.tipo == "cancelados" and params.indice == "marcacao-ambulatorial":
        must.append({"terms": {"status_solicitacao.keyword": STATUS_CANCELADOS}})
    return {
        "size": 0,
        "track_total_hits": True,
        "query": {"bool": {"must": must}},
        "aggs": {
            "top_unidades": {
                "terms": {
                    "field": "codigo_unidade_solicitante",
                    "size": params.top_n,
                    "shard_size": shard_size_for(params.top_n),
                    "order": {"_count": "desc"},
                },
                "aggs": {
                    "enriquecimento": {
                        "top_hits": {
                            "size": 1,
                            "_source": ["nome_unidade_solicitante"],
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
        descricao_field="nome_unidade_solicitante",
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
