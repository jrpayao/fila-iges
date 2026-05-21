"""Narrator Agent — dados consolidados -> resposta em portugues claro.

Suporta retry-com-feedback: na segunda tentativa, recebe os issues do critic
embutidos no payload de input.
"""

import json
from typing import Any

from openai import OpenAI

from app.config import settings
from app.llm.prompts import NARRATOR_SYSTEM, NARRATOR_VERSION
from app.llm.telemetry import capture_cache_telemetry


def narrate(
    pergunta: str,
    dados_consolidados: dict[str, Any],
    proveniencia: dict[str, Any],
    *,
    pii_exposure: bool = False,
    feedback_issues: list[str] | None = None,
) -> str:
    user_payload: dict[str, Any] = {
        "pergunta": pergunta,
        "dados": dados_consolidados,
        "proveniencia": proveniencia,
        "pii_exposure": pii_exposure,
    }
    if feedback_issues:
        user_payload["revisao_anterior"] = {
            "issues_do_critic": feedback_issues,
            "instrucao": (
                "Sua narrativa anterior foi rejeitada pelo critic. Corrija APENAS "
                "os itens listados acima e mantenha o resto."
            ),
        }
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_narrator_model,
        messages=[
            {"role": "system", "content": NARRATOR_SYSTEM},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, default=str)},
        ],
        temperature=0.2,
    )
    capture_cache_telemetry(response, "narrator")
    return response.choices[0].message.content or ""


def version() -> str:
    return NARRATOR_VERSION
