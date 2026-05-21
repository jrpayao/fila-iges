"""Helpers compartilhados entre templates."""

from typing import Any

from app.config import settings

# Vocabulario de status_solicitacao (literal, com barras e espacos)
STATUS_ATENDIDOS = ["AGENDAMENTO / CONFIRMADO / EXECUTANTE"]
STATUS_AGENDADOS = [
    "SOLICITAÇÃO / AGENDADA / FILA DE ESPERA",
    "SOLICITAÇÃO / AGENDADA / SOLICITANTE",
    "SOLICITAÇÃO / AUTORIZADA / REGULADOR",
    "SOLICITAÇÃO / AGENDADA / COORDENADOR",
    "AGENDAMENTO / PENDENTE CONFIRMAÇÃO / EXECUTANTE",
]
STATUS_CANCELADOS = [
    "SOLICITAÇÃO / CANCELADA / SOLICITANTE",
    "SOLICITAÇÃO / CANCELADA / REGULADOR",
    "SOLICITAÇÃO / CANCELADA / COORDENADOR",
    "AGENDAMENTO / CANCELADO / REGULADOR",
    "AGENDAMENTO / CANCELADO / SOLICITANTE",
    "AGENDAMENTO / CANCELADO / COORDENADOR",
    "SOLICITAÇÃO / NEGADA / REGULADOR",
    "SOLICITAÇÃO / DEVOLVIDA / REGULADOR",
]
STATUS_PENDENTES = [
    "SOLICITAÇÃO / PENDENTE / REGULADOR",
    "SOLICITAÇÃO / PENDENTE / FILA DE ESPERA",
    "SOLICITAÇÃO / REENVIADA / REGULADOR",
]
STATUS_FALTA = ["AGENDAMENTO / FALTA / EXECUTANTE"]

# Mapa risco -> descricao humana (PDF §5)
RISCO_DESCRICAO = {
    "1": "Prioridade 0 — Emergência",
    "2": "Prioridade 1 — Urgência",
    "3": "Prioridade 2 — Não urgente",
    "4": "Prioridade 3 — Eletivo",
}


def df_filter() -> dict[str, Any]:
    """Filtro defensivo de UF DF para familia ambulatorial (codigo_uf_regulador e keyword direto)."""
    return {"term": {"codigo_uf_regulador": settings.sisreg_uf_code_ibge}}


def df_filter_hospitalar() -> dict[str, Any]:
    """Filtro de UF DF para familia hospitalar-v3 (codigo_uf_regulador e text+keyword)."""
    return {"term": {"codigo_uf_regulador.keyword": settings.sisreg_uf_code_ibge}}


def shard_size_for(top_n: int) -> int:
    return max(200, top_n * 20)


def consolidate_terms_buckets(
    es_response: dict[str, Any],
    agg_name: str,
    *,
    descricao_field: str | None = None,
    key_label: str = "valor",
    extra_top_hit_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Consolida agg terms com top_hits aninhado para enriquecimento."""
    total = es_response.get("hits", {}).get("total", {}).get("value", 0)
    took_ms = es_response.get("took", 0)
    agg = es_response.get("aggregations", {}).get(agg_name, {})
    buckets = agg.get("buckets", [])
    sum_other = agg.get("sum_other_doc_count", 0)
    error_upper = agg.get("doc_count_error_upper_bound", 0)

    linhas = []
    for b in buckets:
        linha: dict[str, Any] = {
            key_label: b["key"],
            "count": b["doc_count"],
            "pct": round(100 * b["doc_count"] / total, 2) if total else None,
        }
        descricao_hits = b.get("enriquecimento", {}).get("hits", {}).get("hits", [])
        if descricao_hits and descricao_field:
            source = descricao_hits[0].get("_source", {})
            linha["descricao"] = source.get(descricao_field, "").strip() if isinstance(source.get(descricao_field), str) else source.get(descricao_field)
            if extra_top_hit_fields:
                for field in extra_top_hit_fields:
                    linha[field] = source.get(field)
        linhas.append(linha)

    return {
        "linhas": linhas,
        "totais": {
            "documentos_no_universo_filtrado": total,
            "documentos_fora_do_top": sum_other,
            "erro_maximo_contagem": error_upper,
        },
        "performance": {"took_ms": took_ms},
    }
