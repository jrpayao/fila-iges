"""Smoke focado nos 3 fixes do round 2: CNES catalogo, focus boolean, compare vs diagnostic."""
from __future__ import annotations
import time
import httpx

API = "http://127.0.0.1:8000/chat"

PROBES = [
    # 1. Compare HMIB (novo CNES no catalogo): antes virava breakdown com diagnostic, agora deve ser comparison.
    {"id": "compare_hmib", "q": "Compare o volume de solicitacoes do HMIB com outras unidades em 30 dias",
     "expect_shape": "comparison", "expect_metric_in": ("entrada_solicitacoes", "solicitacoes")},
    # 2. Compare HRC (novo CNES): mesmo.
    {"id": "compare_hrc", "q": "Compare a producao do HRC com outros hospitais em atendimentos",
     "expect_shape": "comparison"},
    # 3. Compare HRT em faltas: ja existia CNES, mas o planner pode virar diagnostic. Agora deve ser comparison.
    {"id": "compare_hrt_faltas", "q": "Como o HRT se compara com outros hospitais em faltas?",
     "expect_shape": "comparison"},
    # 4. Compare paciente_avisado: antes erro 'compare exige focus_value', agora deve funcionar.
    {"id": "compare_avisado", "q": "Compare a taxa de falta de pacientes avisados vs nao avisados",
     "expect_shape_in": ("comparison", "breakdown")},
    # 5. Diagnostic continua funcionando.
    {"id": "diagnostic_fila", "q": "Como diminuir a fila eletiva?",
     "expect_composition": "diagnostic"},
]

with httpx.Client(timeout=240.0) as client:
    ok = 0
    fail = 0
    for p in PROBES:
        t0 = time.time()
        try:
            r = client.post(API, json={"pergunta": p["q"]})
            ms = int((time.time() - t0) * 1000)
            data = r.json()
            prov = data.get("proveniencia") or {}
            plan = prov.get("plan") or {}
            narr = (data.get("narrativa") or "").replace("\n", " ")
            shape = prov.get("shape")
            metric = prov.get("metric")
            comp = plan.get("composition")
            total = prov.get("total_documents")
            print(f"\n=== {p['id']} ({ms}ms HTTP {r.status_code}) ===")
            print(f"  Q: {p['q']}")
            print(f"  shape={shape} metric={metric} composition={comp} total={total}")
            print(f"  steps: {[(s.get('primitive'), s.get('dimension'), s.get('focus_value')) for s in (plan.get('steps') or [])]}")
            print(f"  narrativa[:200]: {narr[:200]}")
            # Verifica expectativas
            checks: list[str] = []
            if "expect_shape" in p:
                checks.append(f"shape {'OK' if shape == p['expect_shape'] else f'FAIL got={shape} want={p[chr(34)+chr(101)+chr(120)+chr(112)+chr(101)+chr(99)+chr(116)+chr(95)+chr(115)+chr(104)+chr(97)+chr(112)+chr(101)+chr(34)]}'}")
            if "expect_shape_in" in p:
                checks.append(f"shape {'OK' if shape in p['expect_shape_in'] else 'FAIL'}")
            if "expect_composition" in p:
                checks.append(f"composition {'OK' if comp == p['expect_composition'] else 'FAIL'}")
            if "expect_metric_in" in p and metric:
                checks.append(f"metric {'OK' if any(m in metric for m in p['expect_metric_in']) else 'FAIL'}")
            all_ok = all("OK" in c for c in checks)
            print(f"  CHECKS: {checks}  ->  {'PASS' if all_ok else 'FAIL'}")
            if all_ok:
                ok += 1
            else:
                fail += 1
        except Exception as e:
            print(f"\n=== {p['id']} EXCEPTION: {type(e).__name__}: {e} ===")
            fail += 1

    print(f"\n\n{ok}/{len(PROBES)} smokes OK")
