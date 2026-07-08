"""Smoke das mudancas A+B antes de rodar a bateria completa.

5 perguntas:
- 1 timeseries
- 1 lead_time (era stats -> agora deve ser lead_time)
- 1 hospitalar (era refused -> agora on-topic)
- 1 compare HRT (agora deve usar CNES validado, doc_count > 0)
- 1 diagnostic (composition=diagnostic novo)
"""
from __future__ import annotations
import time
import httpx

API = "http://127.0.0.1:8000/chat"

PROBES = [
    {"id": "smoke1_ts", "q": "Serie diaria de solicitacoes nos ultimos 14 dias"},
    {"id": "smoke2_leadtime", "q": "Qual o tempo medio de regulacao nos ultimos 30 dias?"},
    {"id": "smoke3_hospitalar", "q": "Top 10 CIDs em internacoes hospitalares no ultimo mes"},
    {"id": "smoke4_compare_hrt", "q": "Compare o HRT com a media de unidades em volume de fila"},
    {"id": "smoke5_diagnostic", "q": "Como diminuir a fila eletiva?"},
]

with httpx.Client(timeout=180.0) as client:
    for p in PROBES:
        t0 = time.time()
        try:
            r = client.post(API, json={"pergunta": p["q"]})
            ms = int((time.time() - t0) * 1000)
            data = r.json()
            prov = data.get("proveniencia") or {}
            plan = prov.get("plan") or {}
            dados = data.get("dados") or {}
            narr = (data.get("narrativa") or "").replace("\n", " ")
            print(f"\n=== {p['id']} ({ms}ms HTTP {r.status_code}) ===")
            print(f"Q: {p['q']}")
            print(f"  composition: {plan.get('composition')}")
            print(f"  steps: {len(plan.get('steps') or [])} -> {[s.get('primitive') for s in (plan.get('steps') or [])]}")
            print(f"  shape: {prov.get('shape') or dados.get('shape')}")
            print(f"  metric: {prov.get('metric') or plan.get('metric')}")
            print(f"  metric_kind: {prov.get('metric_kind')}")
            print(f"  source_index: {prov.get('source_index')}")
            print(f"  total_documents: {prov.get('total_documents')}")
            print(f"  method_note: {prov.get('method_note')}")
            print(f"  refusal: {prov.get('refusal_reason')}")
            print(f"  narrativa[0:240]: {narr[:240]}")
        except Exception as e:
            print(f"\n=== {p['id']} FAILED: {type(e).__name__}: {e} ===")
