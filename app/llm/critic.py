"""Critic Agent — revisa a narrativa do Narrator antes de devolver ao usuario.

Segunda linha de defesa para P2 (PII na resposta final) e garante P5 (citacao).
Se rejeitar, narrator re-tenta com o feedback.

Modelo: gpt-4o-mini (revisao textual e barata).
"""

import json
from enum import Enum
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.llm.prompts import CRITIC_SYSTEM, CRITIC_VERSION
from app.llm.telemetry import capture_cache_telemetry


class CriticDecision(str, Enum):
    APPROVE = "approve"
    REVISE = "revise"


class CriticResult(BaseModel):
    decision: CriticDecision = Field(..., description="approve | revise")
    reasoning: str = Field(..., description="Explicacao curta")
    issues: list[str] = Field(
        default_factory=list,
        description="Itens que falharam (ex.: 'P5: nao citou janela temporal')",
    )


def review(
    pergunta: str,
    narrativa: str,
    proveniencia: dict[str, Any],
) -> CriticResult:
    payload = {
        "pergunta_original": pergunta,
        "narrativa_produzida": narrativa,
        "proveniencia_da_query": proveniencia,
    }
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.beta.chat.completions.parse(
        model=settings.openai_critic_model,
        messages=[
            {"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ],
        response_format=CriticResult,
        temperature=0.0,
    )
    capture_cache_telemetry(response, "critic")
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("Critic nao retornou CriticResult parseavel.")
    return parsed


def version() -> str:
    return CRITIC_VERSION
