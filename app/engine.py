"""Engine — adapter fino sobre app.agent.orchestrator (v2).

Mantem a interface `ask(pergunta) -> dict{narrativa, dados, proveniencia}` esperada
por app/api.py e ui/streamlit_app.py. A logica real vive em app/agent/.

Backward compat:
- `pii_exposure` e `justificativa` aceitos mas IGNORADOS — na v2 a constituicao P6 e
  absoluta, agregacao sempre. Mantemos os params no kwargs apenas pra nao quebrar
  chamadores.
- Erros do orquestrador viram `EngineError`.
- Clarification e refusal sao serializados em `narrativa` (texto) enquanto a UI nao
  tiver suporte a chips (Fase 4). proveniencia carrega plan/envelope completos.
"""

from __future__ import annotations

from typing import Any

from app.agent.envelope import Envelope
from app.agent.orchestrator import AgentResponse
from app.agent.orchestrator import ask as _agent_ask
from app.agent.plan import ClarificationRequest
from app.agent.skills.chart import to_plotly_dict


class EngineError(RuntimeError):
    """Erro do pipeline. Mantida pra compat com api.py."""


def ask(
    pergunta: str,
    *,
    pii_exposure: bool = False,  # noqa: ARG001 — backward compat, ignorado na v2
    justificativa: str = "",  # noqa: ARG001 — backward compat, ignorado na v2
) -> dict[str, Any]:
    """Pergunta livre -> resposta no shape esperado pela UI v1."""
    resp = _agent_ask(pergunta)

    if resp.error:
        raise EngineError(resp.error)

    proveniencia = _build_proveniencia(resp)

    if resp.refusal_reason:
        return {
            "narrativa": resp.refusal_reason,
            "dados": None,
            "proveniencia": proveniencia,
            "chart": None,
        }

    if resp.clarifications:
        return {
            "narrativa": _format_clarifications(resp.clarifications),
            "dados": None,
            "proveniencia": proveniencia,
            "chart": None,
        }

    chart = None
    if resp.envelope is not None:
        try:
            chart = to_plotly_dict(resp.envelope)
        except Exception:
            chart = None  # falha de chart nunca quebra a resposta

    return {
        "narrativa": resp.narrativa or "(sem narrativa)",
        "dados": _envelope_to_dados(resp.envelope) if resp.envelope else None,
        "proveniencia": proveniencia,
        "chart": chart,
    }


# ===== helpers =====


def _build_proveniencia(resp: AgentResponse) -> dict[str, Any]:
    prov: dict[str, Any] = {
        "request_id": resp.request_id,
        "pergunta": resp.pergunta,
        "engine_version": "v2-agent",
    }
    if resp.plan is not None:
        prov["plan"] = resp.plan.model_dump(mode="json", exclude_none=True)
    if resp.envelope is not None:
        env = resp.envelope
        prov.update(
            {
                "metric": env.metric,
                "shape": env.shape.value,
                "metric_kind": env.metric_kind.value,
                "source_index": env.source_index,
                "window": env.window.model_dump(mode="json"),
                "units": env.units,
                "total_documents": env.total_documents,
                "doc_count_error": env.doc_count_error,
                "filters": env.filters,
            }
        )
        if env.method_note:
            prov["method_note"] = env.method_note
    if resp.clarifications:
        prov["clarifications"] = [c.model_dump() for c in resp.clarifications]
    if resp.refusal_reason:
        prov["refusal_reason"] = resp.refusal_reason
    return prov


def _envelope_to_dados(envelope: Envelope) -> dict[str, Any]:
    """Achata Envelope.data + metadados num formato amigavel pro painel debug da UI."""
    return {
        "shape": envelope.shape.value,
        "units": envelope.units,
        "data": envelope.data,
        "total_documents": envelope.total_documents,
        "doc_count_error": envelope.doc_count_error,
        "method_note": envelope.method_note,
    }


def _format_clarifications(clarifications: list[ClarificationRequest]) -> str:
    """Serializa clarifications como markdown temporario (Fase 4 troca por chips)."""
    lines = ["**Preciso de mais detalhes para responder:**", ""]
    for c in clarifications:
        verb = "Termo ambíguo" if c.reason == "ambiguous" else "Não consegui resolver"
        lines.append(f"- {verb}: `{c.field}` = _\"{c.raw}\"_")
        if c.suggestions:
            lines.append("  Sugestões:")
            for s in c.suggestions[:5]:
                lines.append(f"    - {s}")
        lines.append("")
    lines.append("Reformule a pergunta indicando uma das opções acima.")
    return "\n".join(lines)
