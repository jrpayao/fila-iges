"""Bateria de regressao do motor de vagas (Fase 4).

Roda perguntas de capacidade pelo pipeline completo (orchestrator.ask) e checa
shape/primitiva/escopo/caveat. Imprime pass rate por categoria e dump JSON.

    $py scripts/battery_vagas.py
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from app.vagas.orchestrator import ask

# expect: scope(in|off), shape, primitive, caveat(bool)
CASES = [
    # A — total de uma medida
    ("A_total", "Quantas vagas de ressonancia magnetica ha na competencia atual?", {"scope": "in", "shape": "scalar", "primitive": "total"}),
    ("A_total", "Qual o total de vagas disponiveis em julho de 2026?", {"scope": "in", "shape": "scalar", "primitive": "total"}),
    ("A_total", "Quantas vagas ativas existem no Hospital Universitario de Brasilia?", {"scope": "in", "shape": "scalar", "primitive": "total"}),
    # B — breakdown
    ("B_breakdown", "Quais procedimentos tem mais vagas disponiveis?", {"scope": "in", "shape": "breakdown", "primitive": "breakdown"}),
    ("B_breakdown", "Quais hospitais oferecem mais vagas em julho de 2026?", {"scope": "in", "shape": "breakdown", "primitive": "breakdown"}),
    ("B_breakdown", "Ranking de hospitais por vagas de ressonancia magnetica.", {"scope": "in", "shape": "breakdown", "primitive": "breakdown"}),
    # C — bloqueio
    ("C_bloqueio", "Quanto da capacidade esta bloqueada neste mes?", {"scope": "in", "shape": "scalar", "primitive": "taxa_bloqueio"}),
    ("C_bloqueio", "Qual a taxa de bloqueio de vagas no HUB?", {"scope": "in", "shape": "scalar", "primitive": "taxa_bloqueio"}),
    ("C_bloqueio", "Quantas vagas estao bloqueadas em julho de 2026?", {"scope": "in", "shape": "scalar", "primitive": "total"}),
    # D — timeseries
    ("D_timeseries", "Como evoluiu a oferta de ressonancia magnetica ao longo dos meses?", {"scope": "in", "shape": "timeseries", "primitive": "timeseries"}),
    ("D_timeseries", "Mostre a tendencia de vagas de ecocardiografia.", {"scope": "in", "shape": "timeseries", "primitive": "timeseries"}),
    ("D_timeseries", "A oferta total de vagas cresceu ou caiu no ultimo ano?", {"scope": "in", "shape": "timeseries", "primitive": "timeseries"}),
    # E — mix
    ("E_mix", "Qual a distribuicao das vagas por tipo (primeira vez, retorno, reserva)?", {"scope": "in", "shape": "breakdown", "primitive": "mix_tipo_vaga"}),
    ("E_mix", "Do total de vagas ativas, quanto e de retorno?", {"scope": "in", "shape": "breakdown", "primitive": "mix_tipo_vaga"}),
    # F — compare
    ("F_compare", "Como o HUB se compara aos outros hospitais em vagas disponiveis?", {"scope": "in", "shape": "comparison", "primitive": "compare"}),
    ("F_compare", "Compare o Hospital de Base com os demais em oferta de vagas.", {"scope": "in", "shape": "comparison", "primitive": "compare"}),
    # G — demanda (caveat de oferta)
    ("G_demanda", "Qual o tempo de espera para ressonancia magnetica?", {"scope": "in", "caveat": True}),
    ("G_demanda", "Quantas pessoas estao na fila de ecocardiografia?", {"scope": "in", "caveat": True}),
    # H — off-topic
    ("H_offtopic", "Qual a previsao do tempo amanha em Brasilia?", {"scope": "off"}),
    ("H_offtopic", "Qual o melhor tratamento para hipertensao?", {"scope": "off"}),
    # I — Pacote Wow (estrategicas)
    ("I_wow", "Me da um panorama executivo da rede de vagas.", {"scope": "in", "shape": "breakdown", "primitive": "panorama"}),
    ("I_wow", "Onde eu ataco o bloqueio de vagas primeiro?", {"scope": "in", "shape": "breakdown", "primitive": "oportunidade_desbloqueio"}),
    ("I_wow", "Quanto da oferta ativa abre porta para paciente novo?", {"scope": "in", "shape": "scalar", "primitive": "indice_porta_entrada"}),
    ("I_wow", "Qual a taxa de reserva das vagas neste mes?", {"scope": "in", "shape": "scalar", "primitive": "taxa_reserva"}),
    ("I_wow", "Quais procedimentos dependem de pouquissimos hospitais?", {"scope": "in", "shape": "breakdown", "primitive": "monofornecedores"}),
    ("I_wow", "Quantas vagas a rede ja perdeu por bloqueio acumulado no ano?", {"scope": "in", "shape": "scalar", "primitive": "vagas_perdidas_ytd"}),
]


def check(r, exp: dict) -> tuple[bool, dict, str]:
    checks: dict[str, bool] = {}
    status = "ok"
    if exp["scope"] == "off":
        checks["refused"] = bool(r.refusal_reason)
        status = "refusal" if r.refusal_reason else "should_refuse"
        return all(checks.values()), checks, status

    # in-scope
    checks["not_refused"] = not r.refusal_reason
    if r.error:
        return False, {"error": False}, "error"
    if r.clarifications:
        # clarificacao nao e falha "dura", mas nao cumpre o expect -> marca
        return False, {"no_clarification": False}, "clarification"
    checks["has_narrative"] = bool(r.narrativa)
    plan = r.plan
    prims = [s.primitive for s in plan.steps] if plan else []
    if "primitive" in exp:
        checks["primitive_ok"] = exp["primitive"] in prims
    if "shape" in exp and r.envelope:
        checks["shape_ok"] = r.envelope.shape.value == exp["shape"]
    if "caveat" in exp and plan:
        checks["caveat_ok"] = plan.demanda_caveat == exp["caveat"]
    return all(checks.values()), checks, status


def main() -> int:
    results = []
    for i, (cat, q, exp) in enumerate(CASES, 1):
        t0 = time.time()
        try:
            r = ask(q)
            ok, checks, status = check(r, exp)
            rec = {
                "id": i, "cat": cat, "q": q, "pass": ok, "status": status,
                "checks": checks,
                "shape": r.envelope.shape.value if r.envelope else None,
                "primitives": [s.primitive for s in r.plan.steps] if r.plan else [],
                "caveat": r.plan.demanda_caveat if r.plan else None,
                "clarifications": [(c.field, c.raw) for c in r.clarifications],
                "refusal": r.refusal_reason,
                "error": r.error,
                "elapsed_s": round(time.time() - t0, 1),
            }
        except Exception as e:
            rec = {"id": i, "cat": cat, "q": q, "pass": False, "status": "exception", "error": str(e)[:200]}
        results.append(rec)
        mark = "PASS" if rec.get("pass") else "FAIL"
        print(f"#{i:2d} [{cat:12s}] {mark} ({rec.get('elapsed_s','?')}s) {q[:55]}")
        if not rec.get("pass"):
            print(f"      status={rec.get('status')} checks={rec.get('checks')} "
                  f"shape={rec.get('shape')} prims={rec.get('primitives')} clar={rec.get('clarifications')}")

    Path(__file__).with_name("battery_vagas_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    by_cat = defaultdict(lambda: [0, 0])
    for r in results:
        by_cat[r["cat"]][0 if r.get("pass") else 1] += 1
    print("\n" + "=" * 60)
    print(f"{'Categoria':16s} {'PASS':>5} {'FAIL':>5} {'%':>5}")
    tot_p = tot = 0
    for cat in sorted(by_cat):
        p, f = by_cat[cat]
        tot_p += p; tot += p + f
        print(f"{cat:16s} {p:>5} {f:>5} {p/(p+f)*100:>4.0f}%")
    print("-" * 60)
    print(f"{'TOTAL':16s} {tot_p:>5} {tot-tot_p:>5} {tot_p/tot*100:>4.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
