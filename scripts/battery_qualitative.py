"""Avaliacao qualitativa: re-hit API para amostra representativa, mostra resposta
completa e dimensoes de qualidade (P2/P3, utilidade gestor, coerencia plan-narrativa)."""

import json
import textwrap
from pathlib import Path
from typing import Any

import httpx

API = "http://127.0.0.1:8000/chat"

# Amostra: 1 por categoria + 2 falhas relevantes
SAMPLE_IDS = {
    1: "A_scalar_snapshot — pendentes agora",
    12: "B_scalar_flow — atendimentos 30d",
    21: "C_breakdown_cid — top 10 CIDs",
    33: "D_breakdown_unidade — top 5 solicitantes",
    44: "E_breakdown_outras — distribuicao status",
    56: "F_timeseries — evolucao diaria",
    66: "G_comparison — HRT vs outras",
    74: "H_distribution — tempo medio regulacao",
    84: "I_ratio — taxa de falta",
    93: "J_projection — previsao catarata HRT",
    98: "K_edge — como diminuir a fila (P11 corrigido)",
    99: "K_edge — cardapio (off-topic)",
    # falhas que vale revisar
    76: "H_distribution — FALHA (planner usou stats em vez de lead_time)",
    25: "C_breakdown_cid — FALHA (planner recusou hospitalar)",
}

PERGUNTAS = {
    1: "Quantos pacientes estao na fila ambulatorial agora?",
    12: "Quantos atendimentos foram realizados em 30 dias?",
    21: "Top 10 CIDs solicitados nos ultimos 30 dias",
    33: "Top 5 unidades solicitantes nos ultimos 30 dias",
    44: "Distribuicao por status na fila ambulatorial agora",
    56: "Evolucao diaria das solicitacoes nos ultimos 14 dias",
    66: "Compare o volume de solicitacoes do HRT com outras unidades em 30 dias",
    74: "Tempo medio de regulacao dos agendamentos nos ultimos 30 dias",
    84: "Taxa de falta nos agendamentos em 30 dias",
    93: "Previsao de atendimento para catarata senil (H25) no HRT",
    98: "Como diminuir a fila eletiva?",
    99: "Qual o cardapio do restaurante?",
    76: "Qual a mediana do tempo de marcacao em 60 dias?",
    25: "Top 10 CIDs em internacoes hospitalares",
}


def hit(pergunta: str) -> dict[str, Any] | None:
    try:
        r = httpx.post(API, json={"pergunta": pergunta}, timeout=120)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"_error": str(exc)}


def show(qid: int, label: str, pergunta: str, resp: dict | None) -> None:
    print("=" * 88)
    print(f"#{qid:3d}  {label}")
    print(f"     Q: {pergunta}")
    print("=" * 88)
    if resp is None:
        print("  [SEM RESPOSTA]")
        return
    if "_error" in resp:
        print(f"  [ERRO]: {resp['_error']}")
        return

    prov = resp.get("proveniencia") or {}
    plan = prov.get("plan") or {}
    dados = resp.get("dados") or {}
    narrativa = resp.get("narrativa") or ""
    chart = resp.get("chart")

    # PLAN
    print("\n>> PLAN")
    if plan:
        print(f"   in_scope: {plan.get('is_in_scope')}")
        if plan.get("refusal_reason"):
            print(f"   refusal_reason: {plan['refusal_reason']}")
        print(f"   rationale:    {plan.get('rationale')}")
        print(f"   metric:       {plan.get('metric')}")
        print(f"   composition:  {plan.get('composition')}")
        for s in plan.get("steps", []):
            filters = {k: v for k, v in (s.get("filters") or {}).items() if v is not None}
            print(f"   step '{s.get('label')}':")
            print(f"      primitive={s.get('primitive')} metric={s.get('metric_name')}")
            print(f"      family={s.get('source_family')} window_days={s.get('window_days')}")
            if s.get("dimension"):
                print(f"      dimension={s['dimension']}  top_n={s.get('top_n')}")
            if s.get("date_field"):
                print(f"      date_field={s['date_field']}")
            if s.get("start_date_field") and s.get("end_date_field"):
                print(f"      lead_time: {s['start_date_field']} -> {s['end_date_field']}")
            if filters:
                print(f"      filters: {filters}")
    else:
        print("   (sem plan)")

    # ENVELOPE/DADOS
    print("\n>> ENVELOPE")
    if dados:
        print(f"   shape: {dados.get('shape')}  units: {dados.get('units')}")
        print(f"   total_documents: {dados.get('total_documents')}")
        if dados.get("doc_count_error"):
            print(f"   doc_count_error: {dados['doc_count_error']}")
        if dados.get("method_note"):
            print(f"   method_note: {dados['method_note']}")
        data = dados.get("data") or []
        print(f"   data (top 3):")
        for d in data[:3]:
            s = json.dumps(d, ensure_ascii=False, default=str)
            if len(s) > 180:
                s = s[:180] + "..."
            print(f"     {s}")
    elif prov.get("clarifications"):
        print(f"   CLARIFICATION: {len(prov['clarifications'])} pendencias")
        for c in prov["clarifications"][:3]:
            print(f"     - {c.get('field')}={c.get('raw')!r} ({c.get('reason')})")
            for sug in (c.get("suggestions") or [])[:3]:
                print(f"         {sug}")
    elif prov.get("refusal_reason"):
        print(f"   REFUSED: {prov['refusal_reason']}")

    # CHART
    print(f"\n>> CHART: {'presente' if chart else 'ausente (scalar/refusal/clarification)'}")

    # NARRATIVA
    print("\n>> NARRATIVA")
    print(textwrap.indent(narrativa.strip(), "     "))


for qid, label in SAMPLE_IDS.items():
    pergunta = PERGUNTAS[qid]
    resp = hit(pergunta)
    show(qid, label, pergunta, resp)
    print()
