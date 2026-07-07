"""Converte filtros canonicos (cid, prioridade, unidade, status_grupo, etc.) em
clausulas Elasticsearch must, respeitando convencoes de mapping por familia (P9 + P14).

A regra `.keyword` muda por familia:
- ambulatorial: codigo_* sao keyword direto; status_solicitacao eh text+keyword (precisa .keyword).
- hospitalar-v3: tudo texto eh text+keyword (use .keyword em term/terms/sort/agg).

CID field tambem muda por indice:
- solicitacao-ambulatorial: codigo_cid_solicitado
- marcacao-ambulatorial: codigo_cid_agendado (default; aceita _solicitado tambem)
- solicitacao-hospitalar: codigo_cid.keyword
"""

from __future__ import annotations

from typing import Any

from app.agent.envelope import Window
from app.config import DF_INDEX_SUFFIX, settings


def family_of(index: str) -> str:
    """'ambulatorial' | 'hospitalar' a partir do nome do indice."""
    if "hospitalar" in index:
        return "hospitalar"
    return "ambulatorial"


def df_filter_clause(index: str) -> dict[str, Any]:
    """Filtro defensivo de UF (P14). Difere por familia."""
    if family_of(index) == "hospitalar":
        return {"term": {"codigo_uf_regulador.keyword": settings.sisreg_uf_code_ibge}}
    return {"term": {"codigo_uf_regulador": settings.sisreg_uf_code_ibge}}


def cid_field_for(index: str) -> str:
    """Campo de CID a usar conforme indice."""
    if family_of(index) == "hospitalar":
        return "codigo_cid.keyword"
    if "marcacao" in index:
        return "codigo_cid_agendado"
    return "codigo_cid_solicitado"


def build_must(filters: dict[str, Any], index: str) -> list[dict[str, Any]]:
    """Converte filtros canonicos -> lista de clausulas `must` no bool query.

    `filters` aceita chaves:
      - cid: str (codigo X00/X000)
      - prioridade: str ("1"-"4")
      - unidade_solicitante: str (CNES)
      - unidade_executante: str (CNES)
      - status_grupo: list[str] (literais de status_solicitacao)
      - tipo_regulacao: "R" | "F"
      - tipo_vaga: "1" | "2"
      - grupo_procedimento: str
      - municipio: str
      - bairro: str
    Filtros omissos sao ignorados.
    """
    family = family_of(index)
    must: list[dict[str, Any]] = [df_filter_clause(index)]

    if cid := filters.get("cid"):
        must.append({"term": {cid_field_for(index): cid}})

    if pri := filters.get("prioridade"):
        # codigo_classificacao_risco: keyword direto em ambulatorial, long em hospitalar
        if family == "hospitalar":
            must.append({"term": {"codigo_classificacao_risco": int(pri)}})
        else:
            must.append({"term": {"codigo_classificacao_risco": str(pri)}})

    if uni := filters.get("unidade_solicitante"):
        field = "codigo_unidade_solicitante.keyword" if family == "hospitalar" else "codigo_unidade_solicitante"
        must.append({"term": {field: uni}})

    if uni := filters.get("unidade_executante"):
        field = "codigo_unidade_executante.keyword" if family == "hospitalar" else "codigo_unidade_executante"
        must.append({"term": {field: uni}})

    if status_grupo := filters.get("status_grupo"):
        # status_solicitacao em ambulatorial: text+keyword (use .keyword)
        # em hospitalar o campo se chama `status`, mesmo padrao
        field = "status.keyword" if family == "hospitalar" else "status_solicitacao.keyword"
        must.append({"terms": {field: status_grupo}})

    if treg := filters.get("tipo_regulacao"):
        field = "codigo_tipo_regulacao.keyword" if family == "hospitalar" else "codigo_tipo_regulacao"
        must.append({"term": {field: treg}})

    if tvaga := filters.get("tipo_vaga"):
        field = "codigo_tipo_vaga_solicitada.keyword" if family == "hospitalar" else "codigo_tipo_vaga_solicitada"
        must.append({"term": {field: str(tvaga)}})

    if grupo := filters.get("grupo_procedimento"):
        field = "codigo_grupo_procedimento.keyword" if family == "hospitalar" else "codigo_grupo_procedimento"
        must.append({"term": {field: grupo}})

    if mun := filters.get("municipio"):
        must.append({"term": {"municipio_paciente_residencia.keyword": mun}})

    if bairro := filters.get("bairro"):
        must.append({"term": {"bairro_paciente_residencia.keyword": bairro}})

    return must


def build_range(date_field: str, window: Window) -> dict[str, Any] | None:
    """Constroi clausula range a partir de Window. Retorna None se janela vazia."""
    rng: dict[str, str] = {}
    if window.gte:
        rng["gte"] = window.gte.isoformat()
    if window.lte:
        rng["lte"] = window.lte.isoformat()
    if not rng:
        return None
    return {"range": {date_field: rng}}


def build_query_body(
    *,
    filters: dict[str, Any],
    window: Window,
    index: str,
    date_field: str | None,
    size: int = 0,
    track_total_hits: bool = True,
) -> dict[str, Any]:
    """Compoe body base com bool/must + opcional range. Cada primitiva adiciona aggs."""
    must = build_must(filters, index)
    if date_field:
        range_clause = build_range(date_field, window)
        if range_clause:
            must.append(range_clause)
    body: dict[str, Any] = {
        "size": size,
        "query": {"bool": {"must": must}},
    }
    if track_total_hits:
        body["track_total_hits"] = True
    return body


# ===== Dimensoes -> campos ES (P9 vocabulario fechado) =====


def dimension_to_es(dimension: str, index: str) -> tuple[str, str | None]:
    """Mapeia uma dimensao canonica para (campo_terms, campo_descricao_top_hits).

    Retorna (None, None) para dimensao nao suportada.
    """
    family = family_of(index)

    mapping_ambulatorial: dict[str, tuple[str, str | None]] = {
        "cid": (cid_field_for(index), _cid_descricao_field(index)),
        "prioridade": ("codigo_classificacao_risco", None),
        "unidade_solicitante": ("codigo_unidade_solicitante", "nome_unidade_solicitante"),
        "unidade_executante": ("codigo_unidade_executante", "nome_unidade_executante"),
        "status": ("status_solicitacao.keyword", None),
        "tipo_regulacao": ("codigo_tipo_regulacao", None),
        "tipo_vaga": ("codigo_tipo_vaga_solicitada", None),
        "grupo_procedimento": ("codigo_grupo_procedimento", "nome_grupo_procedimento"),
        "municipio": ("municipio_paciente_residencia.keyword", None),
        "bairro": ("bairro_paciente_residencia.keyword", None),
        "perfil_cancelamento": ("nome_perfil_cancelamento.keyword", None),
        "paciente_avisado": ("st_paciente_avisado", None),
    }

    mapping_hospitalar: dict[str, tuple[str, str | None]] = {
        "cid": ("codigo_cid.keyword", "descricao_cid"),
        "prioridade": ("codigo_classificacao_risco", None),
        "unidade_solicitante": ("codigo_unidade_solicitante.keyword", "nome_unidade_solicitante"),
        "unidade_executante": ("codigo_unidade_executante.keyword", "nome_unidade_executante"),
        "status": ("status.keyword", None),
        "carater": ("carater.keyword", None),
        "tipo_regulacao": ("codigo_tipo_regulacao.keyword", None),
        "municipio": ("municipio_paciente_residencia.keyword", None),
    }

    table = mapping_hospitalar if family == "hospitalar" else mapping_ambulatorial
    if dimension in table:
        return table[dimension]
    raise ValueError(f"Dimensao '{dimension}' nao suportada em familia '{family}' (P9).")


def _cid_descricao_field(index: str) -> str:
    if "marcacao" in index:
        return "descricao_cid_agendado"
    return "descricao_cid_solicitado"


# ===== Helper para resolver alias completo a partir da familia =====


def index_alias_for_family(family: str) -> str:
    """Familia -> alias ES com sufixo DF."""
    return f"{family}-{DF_INDEX_SUFFIX}"
