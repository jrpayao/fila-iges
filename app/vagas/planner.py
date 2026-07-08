"""Planner do motor de vagas — pergunta NL -> VagasPlan via OpenAI structured outputs."""

from __future__ import annotations

from openai import OpenAI

from app.config import settings
from app.vagas.plan import VagasPlan
from app.vagas.prompts import PLANNER_VERSION, planner_system


def plan(pergunta: str, *, request_id: str | None = None) -> VagasPlan:
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.beta.chat.completions.parse(
        model=settings.openai_planner_model,
        messages=[
            {"role": "system", "content": planner_system()},
            {"role": "user", "content": pergunta},
        ],
        response_format=VagasPlan,
        temperature=0.0,
    )
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("Planner de vagas nao retornou VagasPlan parseavel.")
    return parsed


def version() -> str:
    return PLANNER_VERSION
