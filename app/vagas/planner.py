"""Planner do motor de vagas — pergunta NL -> VagasPlan via OpenAI structured outputs.

Suporta memoria de conversa: recebe o historico dos turnos anteriores (compacto) e o
injeta como mensagens, para resolver referencias ("e no HUB?", "e em junho?").
"""

from __future__ import annotations

import json

from openai import OpenAI

from app.config import settings
from app.vagas.plan import VagasPlan
from app.vagas.prompts import PLANNER_VERSION, planner_system

_MAX_TURNS = 4  # janela de contexto (turnos anteriores considerados)


def _hist_summary(entry: dict) -> str:
    """Resumo compacto do que foi resolvido num turno (vira a fala do assistente)."""
    return json.dumps(
        {"resolvido": {"metric": entry.get("metric"), "filtros": entry.get("filters") or {}}},
        ensure_ascii=False,
    )


def plan(pergunta: str, *, history: list[dict] | None = None, request_id: str | None = None) -> VagasPlan:
    client = OpenAI(api_key=settings.openai_api_key)
    messages: list[dict] = [{"role": "system", "content": planner_system()}]
    for h in (history or [])[-_MAX_TURNS:]:
        if h.get("pergunta"):
            messages.append({"role": "user", "content": h["pergunta"]})
            messages.append({"role": "assistant", "content": _hist_summary(h)})
    messages.append({"role": "user", "content": pergunta})

    response = client.beta.chat.completions.parse(
        model=settings.openai_planner_model,
        messages=messages,
        response_format=VagasPlan,
        temperature=0.0,
    )
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("Planner de vagas nao retornou VagasPlan parseavel.")
    return parsed


def version() -> str:
    return PLANNER_VERSION
