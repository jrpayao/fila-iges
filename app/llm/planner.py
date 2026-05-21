"""Planner Agent — pergunta NL -> tool_call (template + params/DSL).

Suporta retry-com-feedback: na segunda tentativa, recebe o motivo do validator
embutido na mensagem do usuario.
"""

import json
from typing import Any

from openai import OpenAI

from app.config import settings
from app.es import mappings, registry
from app.llm.prompts import PLANNER_VERSION, planner_system
from app.llm.telemetry import capture_cache_telemetry


class PlannerResult:
    def __init__(self, template_name: str | None, params: dict[str, Any], rationale: str) -> None:
        self.template_name = template_name
        self.params = params
        self.rationale = rationale

    @property
    def matched(self) -> bool:
        return self.template_name is not None


def plan(pergunta: str, *, feedback: str | None = None) -> PlannerResult:
    client = OpenAI(api_key=settings.openai_api_key)
    system = planner_system(mappings.format_for_prompt())
    user_content = pergunta
    if feedback:
        user_content = (
            f"{pergunta}\n\n"
            f"[REVISAO] Sua tentativa anterior foi rejeitada pelo validator.\n"
            f"Motivo: {feedback}\n\n"
            "Gere uma nova query corrigindo APENAS o problema apontado."
        )
    response = client.chat.completions.create(
        model=settings.openai_planner_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        tools=registry.tool_schemas(),
        tool_choice="auto",
        temperature=0.0,
    )
    capture_cache_telemetry(response, "planner")
    message = response.choices[0].message
    if not message.tool_calls:
        return PlannerResult(
            template_name=None,
            params={},
            rationale=message.content or "Sem tool call e sem mensagem.",
        )
    call = message.tool_calls[0]
    try:
        args = json.loads(call.function.arguments)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Planner retornou JSON invalido em arguments: {exc}") from exc
    return PlannerResult(
        template_name=call.function.name,
        params=args,
        rationale=message.content or "",
    )


def version() -> str:
    return PLANNER_VERSION
