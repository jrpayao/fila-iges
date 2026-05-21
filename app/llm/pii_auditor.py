"""PII Auditor Agent — 6o agente do pipeline.

Revisa a narrativa final ANTES de ser entregue ao usuario, em busca de vazamentos
de PII que o anonymize mecanico + o critic nao pegaram.

Roda APENAS quando:
- app_mode = "poc" (em prod, anonymize ja garantiu zero PII pra LLM)
- pii_exposure = False (usuario nao consentiu PII explicitamente)

E uma "linha de defesa final" — se detectar leak, engine retorna mensagem generica
em vez da narrativa.

Modelo: gpt-4o-mini (revisao textual focada e barata).
"""

import json
from enum import Enum
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.llm.prompts import PII_AUDITOR_SYSTEM, PII_AUDITOR_VERSION
from app.llm.telemetry import capture_cache_telemetry


class PIIDecision(str, Enum):
    CLEAN = "clean"
    LEAK_DETECTED = "leak_detected"


class PIIAuditResult(BaseModel):
    decision: PIIDecision = Field(..., description="clean ou leak_detected")
    leaks: list[str] = Field(
        default_factory=list,
        description="Lista dos itens suspeitos encontrados (sem reproduzir o PII em si).",
    )
    reasoning: str = Field(..., description="Justificativa curta da decisao.")


def audit(narrativa: str, proveniencia: dict[str, Any]) -> PIIAuditResult:
    payload = {
        "narrativa_a_revisar": narrativa,
        "proveniencia_da_query": proveniencia,
        "lembrete": (
            "Voce esta verificando se a narrativa contem PII de paciente individual. "
            "Considere PII: CPF, nome de paciente individual, endereco completo, CNS, "
            "telefone, data de nascimento. Nome de unidade publica (UBS, hospital) NAO eh PII."
        ),
    }
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.beta.chat.completions.parse(
        model=settings.openai_critic_model,
        messages=[
            {"role": "system", "content": PII_AUDITOR_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ],
        response_format=PIIAuditResult,
        temperature=0.0,
    )
    capture_cache_telemetry(response, "pii_auditor")
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("PII Auditor nao retornou PIIAuditResult parseavel.")
    return parsed


def version() -> str:
    return PII_AUDITOR_VERSION
