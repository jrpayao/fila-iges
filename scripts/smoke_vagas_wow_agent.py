"""Smoke do Pacote Wow via agente (LLM) — roteamento + narrativa."""

from __future__ import annotations

from app.vagas.orchestrator import ask

PERGUNTAS = [
    "Me da um panorama executivo da rede de vagas.",
    "Onde eu ataco o bloqueio de vagas primeiro?",
    "Quanto da oferta ativa abre porta para paciente novo?",
    "Quais procedimentos dependem de pouquissimos hospitais?",
    "Quantas vagas disponiveis ha neste mes?",
]

for q in PERGUNTAS:
    print("\n" + "=" * 78)
    print("Q:", q)
    r = ask(q)
    if r.error:
        print("  ERROR:", r.error); continue
    if r.refusal_reason:
        print("  RECUSA:", r.refusal_reason); continue
    if r.clarifications:
        print("  CLARIF:", [(c.field, c.raw) for c in r.clarifications]); continue
    prims = [s.primitive for s in r.plan.steps]
    print(f"  primitivas={prims} metric={r.envelope.metric} shape={r.envelope.shape.value}")
    print("  NARRATIVA:")
    for ln in (r.narrativa or "").splitlines():
        print("   ", ln)
print("\nOK")
