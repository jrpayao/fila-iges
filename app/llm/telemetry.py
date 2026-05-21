"""Telemetria compartilhada dos agentes LLM (cached_tokens, usage)."""

from typing import Any

from app import audit


def capture_cache_telemetry(response: Any, agent: str, *, request_id: str | None = None) -> None:
    """Loga cached_tokens do OpenAI prompt cache.

    OpenAI cacheia automaticamente prompts >1024 tokens. Em chamadas subsequentes
    com o mesmo system prompt, cached_tokens > 0 indica hit. Custo do cached eh 50%
    do normal e latencia bem menor.
    """
    try:
        usage = response.usage
        cached = 0
        if hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details:
            cached = getattr(usage.prompt_tokens_details, "cached_tokens", 0) or 0
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        audit.event(
            "llm.openai.usage",
            request_id=request_id or "",
            agent=agent,
            prompt_tokens=prompt_tokens,
            cached_tokens=cached,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            cache_hit_pct=round(100 * cached / max(prompt_tokens, 1), 1),
        )
    except Exception:
        # Telemetria nunca quebra o fluxo
        pass
