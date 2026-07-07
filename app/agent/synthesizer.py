"""Synthesizer v2 — Envelope -> prosa em portugues.

Substituto do narrator v1. Le SOMENTE o Envelope (P4 — fonte unica de numero).
"""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.agent.envelope import Envelope
from app.agent.prompts import SYNTHESIZER_SYSTEM, SYNTHESIZER_VERSION
from app.config import settings
from app.llm.telemetry import capture_cache_telemetry


def synthesize(
    pergunta: str,
    envelope: Envelope,
    *,
    request_id: str | None = None,
) -> str:
    """Envelope -> prosa em portugues. Cita janela/total/metodo (P2)."""
    user_payload: dict[str, Any] = {
        "pergunta": pergunta,
        "envelope": envelope.model_dump(mode="json"),
    }
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_narrator_model,
        messages=[
            {"role": "system", "content": SYNTHESIZER_SYSTEM},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, default=str)},
        ],
        temperature=0.2,
    )
    capture_cache_telemetry(response, "synthesizer_v2", request_id=request_id)
    return response.choices[0].message.content or ""


def version() -> str:
    return SYNTHESIZER_VERSION
