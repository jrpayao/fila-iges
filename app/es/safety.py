"""Safety guard para DSL gerado pelo LLM (constituicao P3 POC override / T-FREE).

Allowlist negativa: tudo permitido exceto:
- Chaves perigosas (script, runtime_mappings, etc.)
- PII (ALWAYS_MASKED_PII) como alvo de filtro
- size > 50
"""

from typing import Any

from app.anonymize.fields import ALWAYS_MASKED_PII

FORBIDDEN_KEYS: frozenset[str] = frozenset({
    "script",
    "script_score",
    "scripted_metric",
    "function_score",
    "runtime_mappings",
    "search_template",
    "_runtime_mappings",
})

FILTER_KEYS: frozenset[str] = frozenset({
    "term",
    "terms",
    "match",
    "match_phrase",
    "match_phrase_prefix",
    "multi_match",
    "prefix",
    "wildcard",
    "regexp",
    "fuzzy",
})


class UnsafeDSLError(ValueError):
    """Raised quando o DSL viola a allowlist negativa."""


def validate(dsl: dict[str, Any], *, max_hit_size: int = 50) -> None:
    if not isinstance(dsl, dict):
        raise UnsafeDSLError(
            f"DSL raiz deve ser dict, recebido {type(dsl).__name__}"
        )
    size = dsl.get("size", 10)
    if not isinstance(size, int) or size < 0 or size > max_hit_size:
        raise UnsafeDSLError(
            f"size={size!r} fora do range permitido [0, {max_hit_size}]"
        )
    _walk(dsl, path="$")


def _walk(node: Any, path: str) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FORBIDDEN_KEYS:
                raise UnsafeDSLError(f"chave proibida '{key}' em {path}")
            if key in FILTER_KEYS:
                _check_filter_target(value, path=f"{path}.{key}")
            _walk(value, path=f"{path}.{key}")
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _walk(item, path=f"{path}[{i}]")


def _check_filter_target(node: Any, path: str) -> None:
    if not isinstance(node, dict):
        return
    for field_name in node.keys():
        base = field_name.split(".")[0]
        if base in ALWAYS_MASKED_PII:
            raise UnsafeDSLError(
                f"PII '{field_name}' nao pode ser alvo de filtro (P2) em {path}"
            )
