"""Carrega e cacheia mappings dos 3 indices DF para uso no prompt do planner/validator.

Cache por processo (lru_cache). Reset = reiniciar processo.
"""

from functools import lru_cache
from typing import Any

from app.config import DF_INDEX_SUFFIX
from app.es.client import SisregESClient

ALIAS_FAMILIES = [
    "solicitacao-ambulatorial",
    "marcacao-ambulatorial",
    "solicitacao-hospitalar",
]


def alias_for(family: str) -> str:
    return f"{family}-{DF_INDEX_SUFFIX}"


@lru_cache(maxsize=1)
def get_all() -> dict[str, dict[str, Any]]:
    """Returns {alias: {physical_index, properties, dynamic_templates}}."""
    result: dict[str, dict[str, Any]] = {}
    with SisregESClient() as es:
        for family in ALIAS_FAMILIES:
            alias = alias_for(family)
            raw = es.get_mapping(alias)
            physical, body = next(iter(raw.items()))
            mappings = body.get("mappings", {})
            result[alias] = {
                "physical_index": physical,
                "properties": mappings.get("properties", {}),
                "dynamic_templates": mappings.get("dynamic_templates", []),
            }
    return result


def _summarize_field(name: str, info: dict[str, Any]) -> str:
    typ = info.get("type", "?")
    if typ == "nested":
        subprops = info.get("properties", {})
        sub = ", ".join(
            f"{k}({v.get('type','?')})" for k, v in sorted(subprops.items())
        )
        return f"  - {name}: nested[{sub}]"
    extras: list[str] = []
    if "keyword" in info.get("fields", {}):
        extras.append("+.keyword")
    if info.get("analyzer"):
        extras.append(f"analyzer={info['analyzer']}")
    extra_str = (" " + " ".join(extras)) if extras else ""
    return f"  - {name}: {typ}{extra_str}"


def format_for_prompt() -> str:
    """Resumo textual compacto pra colar no system prompt do planner/validator."""
    out: list[str] = []
    for alias, m in get_all().items():
        out.append(f"### Indice: {alias}  (fisico: {m['physical_index']})")
        if m["dynamic_templates"]:
            out.append("dynamic_templates:")
            for dt in m["dynamic_templates"]:
                for _, rule in dt.items():
                    match = rule.get("match", "?")
                    typ = rule.get("mapping", {}).get("type", "?")
                    out.append(f"  - campos {match} -> {typ}")
        out.append("properties:")
        for field in sorted(m["properties"].keys()):
            out.append(_summarize_field(field, m["properties"][field]))
        out.append("")
    return "\n".join(out)
