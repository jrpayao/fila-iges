"""PII Scanner mecanico — defesa adicional pos-narrator.

Roda regex sobre o texto final pra detectar vazamentos obvios que o anonymize.scrub()
nao pegou (porque anonymize trabalha em dict; o LLM pode escrever PII no texto livre).

Padroes detectados:
- CPF formatado (000.000.000-00) e nao-formatado (11 digitos consecutivos)
- CNS (15 digitos)
- CEP formatado (00000-000) e nao-formatado (8 digitos isolados)
- Telefones (61) 9XXXX-XXXX

Nao detecta nomes proprios — isso fica para o PII Auditor LLM (P2 defense in depth).
"""

import re
from typing import Any

PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "cpf_formatted": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    "cpf_digits_only": re.compile(r"(?<!\d)\d{11}(?!\d)"),
    "cns": re.compile(r"(?<!\d)\d{15}(?!\d)"),
    "cep_formatted": re.compile(r"\b\d{5}-\d{3}\b"),
    "cep_digits_only": re.compile(r"(?<!\d)\d{8}(?!\d)"),
    "telefone_br": re.compile(r"\(\d{2}\)\s?9?\d{4}-?\d{4}"),
}


def scan(text: str) -> dict[str, list[str]]:
    """Retorna {pattern_name: [matches]} dos padroes detectados (mascarando os matches)."""
    if not text:
        return {}
    findings: dict[str, list[str]] = {}
    for name, pattern in PII_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            findings[name] = [_mask(m) for m in matches]
    return findings


def _mask(value: str) -> str:
    """Mascara o match no log de audit — substitui digitos do meio por X."""
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def has_findings(text: str) -> bool:
    """Helper rapido — true se algum padrao bateu."""
    if not text:
        return False
    return any(p.search(text) for p in PII_PATTERNS.values())
