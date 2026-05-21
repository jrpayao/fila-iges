"""Template T-AGG-CID — Top N CIDs solicitados em janela temporal.

Cenário-âncora US-01 da spec. Família ambulatorial (codigo_* keyword direto).
"""

from typing import Any

from pydantic import BaseModel, Field

from app.config import DF_INDEX_SUFFIX, settings

NAME = "top_cids"
DESCRIPTION = (
    "Retorna os top N CIDs **SOLICITADOS** (novos pedidos) na fila ambulatorial DF "
    "em uma janela temporal. ESCOPO ESTRITO: solicitacao-ambulatorial + data_solicitacao "
    "OU data_atualizacao. "
    "NAO USE para 'atendidos', 'agendados', 'confirmados', 'cancelados' — esses casos "
    "exigem marcacao-ambulatorial com status especifico e devem ir para free_text_search. "
    "Use quando a pergunta for: 'top CIDs solicitados', 'principais CIDs novos', "
    "'doencas mais pedidas', 'principais CIDs na fila ambulatorial'."
)


class Params(BaseModel):
    janela_dias: int = Field(
        ...,
        ge=1,
        le=365,
        description="Tamanho da janela em dias contados a partir de hoje (ex.: 10, 30, 90).",
    )
    top_n: int = Field(
        10,
        ge=1,
        le=50,
        description="Quantos CIDs do topo retornar. Default 10.",
    )
    base_temporal: str = Field(
        "data_solicitacao",
        description=(
            "Campo de data para o filtro range. "
            "'data_solicitacao' = quando o pedido foi feito (pode ser antigo na fila eletiva). "
            "'data_atualizacao' = quando o doc se mexeu por último (movimentação recente)."
        ),
        pattern="^(data_solicitacao|data_atualizacao)$",
    )


def index(params: "Params") -> str:
    return f"solicitacao-ambulatorial-{DF_INDEX_SUFFIX}"


def render(params: Params) -> dict[str, Any]:
    shard_size = max(200, params.top_n * 20)
    return {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "must": [
                    {"term": {"codigo_uf_regulador": settings.sisreg_uf_code_ibge}},
                    {
                        "range": {
                            params.base_temporal: {
                                "gte": f"now-{params.janela_dias}d/d",
                                "lte": "now/d",
                            }
                        }
                    },
                ]
            }
        },
        "aggs": {
            "top_cids": {
                "terms": {
                    "field": "codigo_cid_solicitado",
                    "size": params.top_n,
                    "shard_size": shard_size,
                    "order": {"_count": "desc"},
                },
                "aggs": {
                    "descricao": {
                        "top_hits": {
                            "size": 1,
                            "_source": ["descricao_cid_solicitado"],
                        }
                    }
                },
            }
        },
    }


def consolidate(es_response: dict[str, Any], params: Params) -> dict[str, Any]:
    """Reduz a resposta ES bruta a uma forma tabular pronta para narrador + UI."""
    total = es_response.get("hits", {}).get("total", {}).get("value", 0)
    took_ms = es_response.get("took", 0)
    buckets = es_response.get("aggregations", {}).get("top_cids", {}).get("buckets", [])
    sum_other = es_response.get("aggregations", {}).get("top_cids", {}).get("sum_other_doc_count", 0)
    error_upper = es_response.get("aggregations", {}).get("top_cids", {}).get("doc_count_error_upper_bound", 0)

    linhas = []
    for b in buckets:
        cid = b["key"]
        count = b["doc_count"]
        descricao_hits = b.get("descricao", {}).get("hits", {}).get("hits", [])
        descricao = ""
        if descricao_hits:
            descricao = descricao_hits[0].get("_source", {}).get("descricao_cid_solicitado", "").strip()
        pct = round(100 * count / total, 2) if total else None
        linhas.append({"cid": cid, "descricao": descricao, "count": count, "pct": pct})

    return {
        "linhas": linhas,
        "totais": {
            "documentos_no_universo_filtrado": total,
            "documentos_fora_do_top": sum_other,
            "erro_maximo_contagem": error_upper,
        },
        "performance": {"took_ms": took_ms},
    }


def tool_schema() -> dict[str, Any]:
    """Schema OpenAI function-calling para este template."""
    return {
        "type": "function",
        "function": {
            "name": NAME,
            "description": DESCRIPTION,
            "parameters": Params.model_json_schema(),
        },
    }
