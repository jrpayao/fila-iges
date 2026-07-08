"""Smoke da memoria de conversa — perguntas de acompanhamento resolvem por contexto."""

from __future__ import annotations

from app.vagas.orchestrator import ask, history_entry

CONVERSA = [
    "Quantas vagas de ressonancia magnetica ha neste mes?",
    "e no HUB?",
    "e em junho?",
    "e a taxa de bloqueio?",
]

history: list[dict] = []
for q in CONVERSA:
    print("\n" + "=" * 78)
    print("Usuario:", q)
    r = ask(q, history=history)
    if r.error:
        print("  ERROR:", r.error); continue
    if r.clarifications:
        print("  CLARIF:", [(c.field, c.raw) for c in r.clarifications])
    prims = [s.primitive for s in r.plan.steps] if r.plan else []
    print(f"  primitivas={prims}")
    if r.envelope:
        print(f"  metric={r.envelope.metric} filtros_resolvidos={r.envelope.filters}")
    print("  Resposta:", (r.narrativa or "").replace("\n", " ")[:180])
    history.append(history_entry(r))

print("\nOK — memoria de conversa: verifique se HUB/junho/bloqueio foram herdados do contexto.")
