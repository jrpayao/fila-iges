"""Synthesizer do motor de vagas — Envelope -> prosa (le SOMENTE o Envelope, P4)."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.agent.envelope import Envelope
from app.config import settings
from app.vagas.prompts import SYNTHESIZER_SYSTEM, SYNTHESIZER_VERSION


def synthesize(
    pergunta: str,
    envelope: Envelope,
    *,
    demanda_caveat: bool = False,
    request_id: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "pergunta": pergunta,
        "envelope": envelope.model_dump(mode="json"),
        "aviso_demanda": (
            "A pergunta toca demanda/fila/espera, mas a fonte so cobre OFERTA de vagas. "
            "Responda a capacidade e sinalize essa limitacao."
            if demanda_caveat else None
        ),
    }
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_narrator_model,
        messages=[
            {"role": "system", "content": SYNTHESIZER_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""


def version() -> str:
    return SYNTHESIZER_VERSION
