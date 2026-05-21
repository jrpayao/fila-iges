"""Validator Agent — revisa a query produzida pelo Planner antes da execucao no ES.

Segunda linha de defesa apos o safety guard mecanico (app/es/safety.py).
Pega erros SEMANTICOS que regex-style validation nao pega:
- Indice errado para o tipo de pergunta (ex.: 'atendimento' indo em solicitacao)
- Campo de data errado (ex.: data_solicitacao quando pediu 'atendidos')
- .keyword aplicado errado por familia (ambulatorial vs hospitalar)
- Campos nested filtrados sem nested query
- shard_size ausente em terms agg

Decisoes: approve | revise | reject.
"""

import json
from enum import Enum
from typing import Any, Optional

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.es import mappings
from app.llm.prompts import VALIDATOR_VERSION, validator_system
from app.llm.telemetry import capture_cache_telemetry


class Decision(str, Enum):
    APPROVE = "approve"
    REVISE = "revise"
    REJECT = "reject"


class ValidationResult(BaseModel):
    decision: Decision = Field(
        ..., description="approve | revise | reject"
    )
    reasoning: str = Field(
        ..., description="Explicacao curta. Se reject, deve ser acionavel pro usuario."
    )
    concerns: list[str] = Field(
        default_factory=list,
        description="Lista de problemas categorizados (ex.: 'mapping', 'safety', 'semantico').",
    )
    revised_dsl_json: Optional[str] = Field(
        default=None,
        description=(
            "DSL corrigido como STRING JSON (sera parseado na nossa ponta). "
            "Obrigatorio quando decision=revise E template=free_text_search. "
            "Ex.: '{\"size\": 0, \"query\": ..., \"aggs\": ...}'."
        ),
    )

    def revised_dsl(self) -> Optional[dict[str, Any]]:
        """Parseia revised_dsl_json em dict ou retorna None."""
        if not self.revised_dsl_json:
            return None
        return json.loads(self.revised_dsl_json)


def _build_user_payload(
    pergunta: str,
    template_name: str,
    params: dict[str, Any],
    indice_resolvido: str,
    body: dict[str, Any],
) -> str:
    payload = {
        "pergunta_original": pergunta,
        "template_escolhido": template_name,
        "params": params,
        "indice_resolvido": indice_resolvido,
        "body_dsl_final": body,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def validate(
    pergunta: str,
    template_name: str,
    params: dict[str, Any],
    indice_resolvido: str,
    body: dict[str, Any],
) -> ValidationResult:
    """Roda o validator agent. Retorna ValidationResult ou levanta excecao."""
    client = OpenAI(api_key=settings.openai_api_key)
    system = validator_system(mappings.format_for_prompt())
    user_payload = _build_user_payload(pergunta, template_name, params, indice_resolvido, body)

    response = client.beta.chat.completions.parse(
        model=settings.openai_validator_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_payload},
        ],
        response_format=ValidationResult,
        temperature=0.0,
    )
    capture_cache_telemetry(response, "validator")
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("Validator nao retornou ValidationResult parseavel.")
    return parsed


def version() -> str:
    return VALIDATOR_VERSION
