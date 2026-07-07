"""Planner v2 — pergunta NL -> Plan tipado via OpenAI structured outputs.

Compativel com a saida do client.beta.chat.completions.parse(response_format=Plan).
Validacao adicional eh feita pelo orquestrador (entidades, catalogo, P9).
"""

from __future__ import annotations

from openai import OpenAI

from app.agent.plan import Plan
from app.agent.prompts import PLANNER_VERSION, planner_system
from app.config import settings
from app.llm.telemetry import capture_cache_telemetry


def plan(pergunta: str, *, feedback: str | None = None, request_id: str | None = None) -> Plan:
    """Pergunta livre -> Plan estruturado. Levanta excecao se LLM falha o parse."""
    client = OpenAI(api_key=settings.openai_api_key)
    system = planner_system()
    user_content = pergunta
    if feedback:
        user_content = (
            f"{pergunta}\n\n"
            f"[REVISAO] Tentativa anterior tinha problema: {feedback}\n"
            "Reemita o plano corrigindo o problema, mantendo o resto."
        )
    response = client.beta.chat.completions.parse(
        model=settings.openai_planner_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        response_format=Plan,
        temperature=0.0,
    )
    capture_cache_telemetry(response, "planner_v2", request_id=request_id)
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("Planner v2 nao retornou Plan parseavel.")
    return parsed


def version() -> str:
    return PLANNER_VERSION
