"""Registry de templates aprovados — implementa allowlist da constituição P3."""

from types import ModuleType
from typing import Any

from app.es.templates import (
    distribuicao_carater_hospitalar,
    distribuicao_risco,
    distribuicao_status,
    fila_snapshot,
    free_text_search,
    top_cids,
    top_cids_hospitalar,
    top_cids_marcacao,
    top_procedimentos,
    top_unidades_executantes,
    top_unidades_solicitantes,
)

_TEMPLATES: dict[str, ModuleType] = {
    top_cids.NAME: top_cids,
    top_cids_marcacao.NAME: top_cids_marcacao,
    top_cids_hospitalar.NAME: top_cids_hospitalar,
    top_unidades_solicitantes.NAME: top_unidades_solicitantes,
    top_unidades_executantes.NAME: top_unidades_executantes,
    top_procedimentos.NAME: top_procedimentos,
    distribuicao_risco.NAME: distribuicao_risco,
    distribuicao_status.NAME: distribuicao_status,
    distribuicao_carater_hospitalar.NAME: distribuicao_carater_hospitalar,
    fila_snapshot.NAME: fila_snapshot,
    free_text_search.NAME: free_text_search,
}


def get(name: str) -> ModuleType:
    if name not in _TEMPLATES:
        raise KeyError(
            f"Template '{name}' não está na allowlist. "
            f"Disponíveis: {sorted(_TEMPLATES)}"
        )
    return _TEMPLATES[name]


def tool_schemas() -> list[dict[str, Any]]:
    return [t.tool_schema() for t in _TEMPLATES.values()]


def names() -> list[str]:
    return list(_TEMPLATES.keys())
