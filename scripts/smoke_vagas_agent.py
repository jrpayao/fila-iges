"""Smoke da Fase 3 — pipeline completo NL -> Plan -> Envelope -> prosa (OpenAI real)."""

from __future__ import annotations

from app.vagas.orchestrator import ask

PERGUNTAS = [
    "Quais procedimentos tem mais vagas disponiveis em julho de 2026?",
    "Quanto da capacidade esta bloqueada no Hospital Universitario de Brasilia?",
    "Como evoluiu a oferta de ressonancia magnetica ao longo dos meses?",
    "Qual o tempo de espera para consulta de nefrologia?",   # demanda -> caveat
    "Qual a previsao do tempo para amanha em Brasilia?",       # off-topic -> recusa
]


def main() -> int:
    for q in PERGUNTAS:
        print("\n" + "=" * 80)
        print("Q:", q)
        r = ask(q)
        if r.error:
            print("  ERROR:", r.error); continue
        if r.refusal_reason:
            print("  [RECUSA]", r.refusal_reason); continue
        if r.clarifications:
            print("  [CLARIFICACAO]", [(c.field, c.raw) for c in r.clarifications]); continue
        plan = r.plan
        print(f"  plan: composition={plan.composition} demanda_caveat={plan.demanda_caveat} "
              f"steps={[s.primitive for s in plan.steps]}")
        if r.envelope:
            print(f"  envelope: metric={r.envelope.metric} shape={r.envelope.shape.value} "
                  f"window={r.envelope.window.label}")
        print("  NARRATIVA:")
        for line in (r.narrativa or "").splitlines():
            print("   ", line)
    print("\nOK — Fase 3 (agente completo) executou.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
