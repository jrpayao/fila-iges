"""Template — Top N CIDs em marcacao-ambulatorial, parametrizavel por tipo.

Tipos:
- atendidos: status CONFIRMADO + data_confirmacao
- agendados: status AGENDADA/AUTORIZADA + data_aprovacao
- cancelados: status CANCELADA/NEGADA/DEVOLVIDA + data_solicitacao
- todos: sem filtro de status + data_solicitacao
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import DF_INDEX_SUFFIX
from app.es.templates._helpers import (
    STATUS_AGENDADOS,
    STATUS_ATENDIDOS,
    STATUS_CANCELADOS,
    consolidate_terms_buckets,
    df_filter,
    shard_size_for,
)

NAME = "top_cids_marcacao"
DESCRIPTION = (
    "Top N CIDs no indice marcacao-ambulatorial. Parametrizavel por tipo: "
    "'atendidos' (CONFIRMADO+data_confirmacao), 'agendados' (AGENDADA/AUTORIZADA+data_aprovacao), "
    "'cancelados' (CANCELADA/NEGADA/DEVOLVIDA+data_solicitacao), 'todos'. "
    "Use para: 'top CIDs atendidos no ultimo mes', 'CIDs mais cancelados', 'CIDs mais agendados em 60 dias'."
)


class Params(BaseModel):
    tipo: Literal["atendidos", "agendados", "cancelados", "todos"] = Field(
        ..., description="atendidos | agendados | cancelados | todos"
    )
    janela_dias: int = Field(..., ge=1, le=365)
    top_n: int = Field(10, ge=1, le=50)
    qual_cid: Literal["solicitado", "agendado"] = Field(
        "agendado",
        description="codigo_cid_solicitado ou codigo_cid_agendado. Default 'agendado' faz sentido pra atendidos/agendados.",
    )


def index(params: Params) -> str:
    return f"marcacao-ambulatorial-{DF_INDEX_SUFFIX}"


def _params_for_tipo(tipo: str) -> tuple[list[str] | None, str]:
    """Returns (status_values, campo_data)."""
    if tipo == "atendidos":
        return STATUS_ATENDIDOS, "data_confirmacao"
    if tipo == "agendados":
        return STATUS_AGENDADOS, "data_aprovacao"
    if tipo == "cancelados":
        return STATUS_CANCELADOS, "data_solicitacao"
    return None, "data_solicitacao"


def render(params: Params) -> dict[str, Any]:
    status_values, campo_data = _params_for_tipo(params.tipo)
    campo_cid = f"codigo_cid_{params.qual_cid}"
    campo_desc = f"descricao_cid_{params.qual_cid}"
    must: list[dict[str, Any]] = [
        df_filter(),
        {"range": {campo_data: {"gte": f"now-{params.janela_dias}d/d", "lte": "now/d"}}},
    ]
    if status_values:
        must.append({"terms": {"status_solicitacao.keyword": status_values}})
    return {
        "size": 0,
        "track_total_hits": True,
        "query": {"bool": {"must": must}},
        "aggs": {
            "top_cids": {
                "terms": {
                    "field": campo_cid,
                    "size": params.top_n,
                    "shard_size": shard_size_for(params.top_n),
                    "order": {"_count": "desc"},
                },
                "aggs": {
                    "enriquecimento": {
                        "top_hits": {
                            "size": 1,
                            "_source": [campo_desc],
                        }
                    }
                },
            }
        },
    }


def consolidate(es_response: dict[str, Any], params: Params) -> dict[str, Any]:
    campo_desc = f"descricao_cid_{params.qual_cid}"
    return consolidate_terms_buckets(
        es_response,
        "top_cids",
        descricao_field=campo_desc,
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
