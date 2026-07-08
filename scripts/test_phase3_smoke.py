"""Smoke test Fase 3 — orquestrador v2 end-to-end com 4 perguntas representativas.

Cobre os 4 cenarios do Exemplo §9 da spec:
  A) descritivo simples ("Top 10 CIDs solicitados nos ultimos 30 dias")
  B) projecao ("previsao de atendimento de catarata no HRT")
  C) diagnostico via ratio ("taxa de falta do HRT")
  D) off-topic ("qual o cardapio do restaurante?")
"""

import json
import textwrap

from app.agent.orchestrator import ask


def show(label: str, pergunta: str) -> None:
    print(f"\n{'=' * 78}")
    print(f"=== {label}")
    print(f"=== Pergunta: {pergunta}")
    print(f"{'=' * 78}")
    resp = ask(pergunta)

    if resp.error:
        print(f"ERRO: {resp.error}")
        return
    if resp.refusal_reason:
        print(f"OFF-TOPIC: {resp.refusal_reason}")
        return
    if resp.clarifications:
        print(f"CLARIFICATION NEEDED ({len(resp.clarifications)}):")
        for c in resp.clarifications:
            print(f"  - {c.field}={c.raw!r} ({c.reason})")
            for s in c.suggestions[:3]:
                print(f"      {s}")
        return

    plan = resp.plan
    env = resp.envelope
    print(f"\nPLAN (rationale: {plan.rationale}):")
    print(f"  metric={plan.metric}  composition={plan.composition}  steps={len(plan.steps)}")
    for s in plan.steps:
        print(f"  - {s.label}: {s.primitive}({s.metric_name}) "
              f"family={s.source_family} window={s.window_days}d "
              f"dim={s.dimension or '-'} top_n={s.top_n} "
              f"filters={s.filters.model_dump(exclude_none=True)}")

    print(f"\nENVELOPE:")
    print(f"  metric={env.metric}  shape={env.shape.value}  kind={env.metric_kind.value}")
    print(f"  source={env.source_index}  window={env.window.label}  units={env.units}")
    print(f"  total={env.total_documents}")
    if env.method_note:
        print(f"  method_note: {env.method_note}")
    print(f"  data (top 3):")
    for d in env.data[:3]:
        s = json.dumps(d, ensure_ascii=False, default=str)
        if len(s) > 200:
            s = s[:200] + "..."
        print(f"    {s}")

    print(f"\nNARRATIVA:")
    print(textwrap.indent(resp.narrativa or "(vazio)", "  "))


# Cenarios
show("A. Descritivo (entrada por CID)",
     "Top 10 CIDs solicitados nos ultimos 30 dias")

show("C. Diagnostico via ratio (taxa_falta)",
     "Qual a taxa de falta nos agendamentos nos ultimos 30 dias?")

show("B. Projecao (previsao_atendimento)",
     "Qual a previsao de atendimento para catarata nos proximos meses?")

show("D. Off-topic (router redefinido P11)",
     "Qual o cardapio do restaurante?")
