"""Bateria expandida — 100 perguntas cobrindo as 5 shapes, 17 metricas, 3 composicoes,
multiplas dimensoes, filtros, janelas, e cenarios constitutionais (P10, P11, off-topic).

Save incremental em scripts/battery_results.json — permite resume e analise pos-hoc.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

import httpx

API = "http://127.0.0.1:8000/chat"
TIMEOUT = 180
RESULTS_PATH = Path(__file__).parent / "battery_results.json"


# 100 perguntas categorizadas
QUESTIONS: list[dict[str, Any]] = [
    # A) Scalar — Estoque/snapshot (10)
    {"id": 1, "cat": "A_scalar_snapshot", "q": "Quantos pacientes estao na fila ambulatorial agora?", "expect_shape": "scalar", "expect_metric": "estoque_fila"},
    {"id": 2, "cat": "A_scalar_snapshot", "q": "Quantas solicitacoes pendentes existem hoje?", "expect_shape": "scalar"},
    {"id": 3, "cat": "A_scalar_snapshot", "q": "Qual o tamanho atual da fila eletiva ambulatorial?", "expect_shape": "scalar"},
    {"id": 4, "cat": "A_scalar_snapshot", "q": "Quantos casos urgentes (P1) estao na fila atualmente?", "expect_shape": "scalar"},
    {"id": 5, "cat": "A_scalar_snapshot", "q": "Quantas emergencias (P0) estao pendentes na fila?", "expect_shape": "scalar"},
    {"id": 6, "cat": "A_scalar_snapshot", "q": "Quantos casos eletivos (P3) aguardam atendimento?", "expect_shape": "scalar"},
    {"id": 7, "cat": "A_scalar_snapshot", "q": "Quantas solicitacoes o HBDF tem pendentes?", "expect_shape": "scalar"},
    {"id": 8, "cat": "A_scalar_snapshot", "q": "Quantos casos de hipertensao essencial (I10) estao na fila?", "expect_shape": "scalar"},
    {"id": 9, "cat": "A_scalar_snapshot", "q": "Volume da fila no HRT agora", "expect_shape": "scalar"},
    {"id": 10, "cat": "A_scalar_snapshot", "q": "Quantas solicitacoes nao urgentes (P2) existem agora?", "expect_shape": "scalar"},

    # B) Scalar — Flow em janela (10)
    {"id": 11, "cat": "B_scalar_flow", "q": "Quantas solicitacoes chegaram nos ultimos 7 dias?", "expect_shape": "scalar"},
    {"id": 12, "cat": "B_scalar_flow", "q": "Quantos atendimentos foram realizados em 30 dias?", "expect_shape": "scalar"},
    {"id": 13, "cat": "B_scalar_flow", "q": "Quantas faltas tivemos no ultimo mes?", "expect_shape": "scalar"},
    {"id": 14, "cat": "B_scalar_flow", "q": "Quantos cancelamentos nos ultimos 60 dias?", "expect_shape": "scalar"},
    {"id": 15, "cat": "B_scalar_flow", "q": "Quantos agendamentos foram feitos em 14 dias?", "expect_shape": "scalar"},
    {"id": 16, "cat": "B_scalar_flow", "q": "Total de solicitacoes em 90 dias", "expect_shape": "scalar"},
    {"id": 17, "cat": "B_scalar_flow", "q": "Volume de atendimentos confirmados em 30 dias", "expect_shape": "scalar"},
    {"id": 18, "cat": "B_scalar_flow", "q": "Quantas marcacoes foram feitas no ultimo trimestre (90 dias)?", "expect_shape": "scalar"},
    {"id": 19, "cat": "B_scalar_flow", "q": "Solicitacoes recebidas nos ultimos 45 dias", "expect_shape": "scalar"},
    {"id": 20, "cat": "B_scalar_flow", "q": "Quantos atendimentos o HBDF executou em 30 dias?", "expect_shape": "scalar"},

    # C) Breakdown — Top CIDs (12)
    {"id": 21, "cat": "C_breakdown_cid", "q": "Top 10 CIDs solicitados nos ultimos 30 dias", "expect_shape": "breakdown"},
    {"id": 22, "cat": "C_breakdown_cid", "q": "Quais os 5 CIDs mais agendados em 60 dias?", "expect_shape": "breakdown"},
    {"id": 23, "cat": "C_breakdown_cid", "q": "Top 15 CIDs com mais cancelamentos no ultimo mes", "expect_shape": "breakdown"},
    {"id": 24, "cat": "C_breakdown_cid", "q": "Principais CIDs atendidos em 30 dias", "expect_shape": "breakdown"},
    {"id": 25, "cat": "C_breakdown_cid", "q": "Top 10 CIDs em internacoes hospitalares", "expect_shape": "breakdown"},
    {"id": 26, "cat": "C_breakdown_cid", "q": "Quais doencas geram mais entrada na fila em 30 dias?", "expect_shape": "breakdown"},
    {"id": 27, "cat": "C_breakdown_cid", "q": "CIDs com mais faltas nos ultimos 30 dias", "expect_shape": "breakdown"},
    {"id": 28, "cat": "C_breakdown_cid", "q": "Top 20 CIDs solicitados nos ultimos 90 dias", "expect_shape": "breakdown"},
    {"id": 29, "cat": "C_breakdown_cid", "q": "CIDs mais frequentes em cancelamento ambulatorial", "expect_shape": "breakdown"},
    {"id": 30, "cat": "C_breakdown_cid", "q": "Quais os principais CIDs de oftalmologia solicitados?", "expect_shape": "breakdown"},
    {"id": 31, "cat": "C_breakdown_cid", "q": "Top 8 CIDs agendados no ultimo mes", "expect_shape": "breakdown"},
    {"id": 32, "cat": "C_breakdown_cid", "q": "Top 10 CIDs solicitados de janeiro a marco", "expect_shape": "breakdown"},

    # D) Breakdown — Top unidades (10)
    {"id": 33, "cat": "D_breakdown_unidade", "q": "Top 5 unidades solicitantes nos ultimos 30 dias", "expect_shape": "breakdown"},
    {"id": 34, "cat": "D_breakdown_unidade", "q": "Quais hospitais mais solicitam atendimento em 60 dias?", "expect_shape": "breakdown"},
    {"id": 35, "cat": "D_breakdown_unidade", "q": "Top 10 unidades com mais cancelamentos no mes", "expect_shape": "breakdown"},
    {"id": 36, "cat": "D_breakdown_unidade", "q": "Unidades que mais executam atendimentos em 30 dias", "expect_shape": "breakdown"},
    {"id": 37, "cat": "D_breakdown_unidade", "q": "Top 5 unidades com mais entrada de solicitacoes", "expect_shape": "breakdown"},
    {"id": 38, "cat": "D_breakdown_unidade", "q": "Quais 7 hospitais executam mais atendimentos em 60 dias?", "expect_shape": "breakdown"},
    {"id": 39, "cat": "D_breakdown_unidade", "q": "Unidades solicitantes em casos de emergencia (P0)", "expect_shape": "breakdown"},
    {"id": 40, "cat": "D_breakdown_unidade", "q": "Quais unidades mais pedem consultas em 30 dias?", "expect_shape": "breakdown"},
    {"id": 41, "cat": "D_breakdown_unidade", "q": "Top 5 hospitais por volume de faltas", "expect_shape": "breakdown"},
    {"id": 42, "cat": "D_breakdown_unidade", "q": "Top 10 unidades solicitantes em casos urgentes", "expect_shape": "breakdown"},

    # E) Breakdown — outras dimensoes (13)
    {"id": 43, "cat": "E_breakdown_outras", "q": "Distribuicao por prioridade na fila atual", "expect_shape": "breakdown"},
    {"id": 44, "cat": "E_breakdown_outras", "q": "Distribuicao por status na fila ambulatorial agora", "expect_shape": "breakdown"},
    {"id": 45, "cat": "E_breakdown_outras", "q": "Distribuicao por tipo de vaga (primeira vez vs retorno)", "expect_shape": "breakdown"},
    {"id": 46, "cat": "E_breakdown_outras", "q": "Carater hospitalar: urgente vs eletiva nos ultimos 30 dias", "expect_shape": "breakdown"},
    {"id": 47, "cat": "E_breakdown_outras", "q": "Como esta dividida a fila por urgencia hoje?", "expect_shape": "breakdown"},
    {"id": 48, "cat": "E_breakdown_outras", "q": "Top municipios com mais solicitacoes em 30 dias", "expect_shape": "breakdown"},
    {"id": 49, "cat": "E_breakdown_outras", "q": "Distribuicao por tipo de regulacao (R vs F) na fila", "expect_shape": "breakdown"},
    {"id": 50, "cat": "E_breakdown_outras", "q": "Quem mais cancela: paciente ou sistema? (perfil_cancelamento)", "expect_shape": "breakdown"},
    {"id": 51, "cat": "E_breakdown_outras", "q": "Distribuicao de agendamentos por status nos ultimos 30 dias", "expect_shape": "breakdown"},
    {"id": 52, "cat": "E_breakdown_outras", "q": "Quais prioridades concentram os atendimentos confirmados?", "expect_shape": "breakdown"},
    {"id": 53, "cat": "E_breakdown_outras", "q": "Tipo de vaga dos agendamentos em 30 dias", "expect_shape": "breakdown"},
    {"id": 54, "cat": "E_breakdown_outras", "q": "Quem cancelou mais nos ultimos 60 dias por perfil?", "expect_shape": "breakdown"},
    {"id": 55, "cat": "E_breakdown_outras", "q": "Top 8 grupos de procedimento mais solicitados", "expect_shape": "breakdown"},

    # F) Timeseries (10)
    {"id": 56, "cat": "F_timeseries", "q": "Evolucao diaria das solicitacoes nos ultimos 14 dias", "expect_shape": "timeseries"},
    {"id": 57, "cat": "F_timeseries", "q": "Tendencia semanal dos atendimentos nos ultimos 90 dias", "expect_shape": "timeseries"},
    {"id": 58, "cat": "F_timeseries", "q": "Faltas dia a dia em 30 dias", "expect_shape": "timeseries"},
    {"id": 59, "cat": "F_timeseries", "q": "Cancelamentos diarios nas ultimas 2 semanas", "expect_shape": "timeseries"},
    {"id": 60, "cat": "F_timeseries", "q": "Inflow diario da fila em 30 dias", "expect_shape": "timeseries"},
    {"id": 61, "cat": "F_timeseries", "q": "Atendimentos semanais nos ultimos 60 dias", "expect_shape": "timeseries"},
    {"id": 62, "cat": "F_timeseries", "q": "Curva de agendamentos diaria em 30 dias", "expect_shape": "timeseries"},
    {"id": 63, "cat": "F_timeseries", "q": "Tendencia mensal de entradas nos ultimos 90 dias", "expect_shape": "timeseries"},
    {"id": 64, "cat": "F_timeseries", "q": "Evolucao das faltas semanais em 60 dias", "expect_shape": "timeseries"},
    {"id": 65, "cat": "F_timeseries", "q": "Volume diario de solicitacoes em maio", "expect_shape": "timeseries"},

    # G) Comparison (8)
    {"id": 66, "cat": "G_comparison", "q": "Compare o volume de solicitacoes do HRT com outras unidades em 30 dias", "expect_shape": "comparison"},
    {"id": 67, "cat": "G_comparison", "q": "HBDF vs outras unidades em volume de atendimentos em 60 dias", "expect_shape": "comparison"},
    {"id": 68, "cat": "G_comparison", "q": "HUB comparado com outras unidades em cancelamentos", "expect_shape": "comparison"},
    {"id": 69, "cat": "G_comparison", "q": "Como o HRT se compara com outros hospitais em faltas?", "expect_shape": "comparison"},
    {"id": 70, "cat": "G_comparison", "q": "Compare a unidade HRAN com as outras em solicitacoes", "expect_shape": "comparison"},
    {"id": 71, "cat": "G_comparison", "q": "Volume do HMIB vs outras unidades em 30 dias", "expect_shape": "comparison"},
    {"id": 72, "cat": "G_comparison", "q": "HRGu vs outras unidades em entradas em 60 dias", "expect_shape": "comparison"},
    {"id": 73, "cat": "G_comparison", "q": "Compare a producao do HRC com outros hospitais", "expect_shape": "comparison"},

    # H) Distribution — lead_time / stats (10)
    {"id": 74, "cat": "H_distribution", "q": "Tempo medio de regulacao dos agendamentos nos ultimos 30 dias", "expect_shape": "distribution"},
    {"id": 75, "cat": "H_distribution", "q": "Distribuicao do tempo total de espera (solicitacao ate atendimento)", "expect_shape": "distribution"},
    {"id": 76, "cat": "H_distribution", "q": "Qual a mediana do tempo de marcacao em 60 dias?", "expect_shape": "distribution"},
    {"id": 77, "cat": "H_distribution", "q": "Tempo de execucao dos atendimentos nos ultimos 60 dias", "expect_shape": "distribution"},
    {"id": 78, "cat": "H_distribution", "q": "Distribuicao de tempo solicitacao-aprovacao no mes", "expect_shape": "distribution"},
    {"id": 79, "cat": "H_distribution", "q": "Mediana do tempo da fila ate confirmacao em 90 dias", "expect_shape": "distribution"},
    {"id": 80, "cat": "H_distribution", "q": "P90 do tempo de regulacao nos ultimos 60 dias", "expect_shape": "distribution"},
    {"id": 81, "cat": "H_distribution", "q": "Tempo medio de regulacao para o HRT no ultimo mes", "expect_shape": "distribution"},
    {"id": 82, "cat": "H_distribution", "q": "Quanto demora em media do agendamento ao atendimento?", "expect_shape": "distribution"},
    {"id": 83, "cat": "H_distribution", "q": "Distribuicao do tempo total de espera ambulatorial", "expect_shape": "distribution"},

    # I) Derived — ratio (9)
    {"id": 84, "cat": "I_ratio", "q": "Taxa de falta nos agendamentos em 30 dias", "expect_shape": "scalar", "expect_metric": "taxa_falta", "expect_composition": "ratio"},
    {"id": 85, "cat": "I_ratio", "q": "Taxa de conversao em atendimento nos ultimos 60 dias", "expect_shape": "scalar", "expect_metric": "taxa_conversao", "expect_composition": "ratio"},
    {"id": 86, "cat": "I_ratio", "q": "Taxa de cancelamento dos ultimos 30 dias", "expect_shape": "scalar", "expect_metric": "taxa_cancelamento", "expect_composition": "ratio"},
    {"id": 87, "cat": "I_ratio", "q": "Taxa de falta do HRT no ultimo mes", "expect_shape": "scalar", "expect_metric": "taxa_falta"},
    {"id": 88, "cat": "I_ratio", "q": "Taxa de conversao do HBDF em 30 dias", "expect_shape": "scalar", "expect_metric": "taxa_conversao"},
    {"id": 89, "cat": "I_ratio", "q": "Qual a taxa de cancelamento de primeira vez vs retorno?", "expect_shape": "scalar"},
    {"id": 90, "cat": "I_ratio", "q": "Taxa de falta para hipertensao essencial (I10)", "expect_shape": "scalar"},
    {"id": 91, "cat": "I_ratio", "q": "Compare taxa de falta de pacientes avisados vs nao avisados", "expect_metric": "efeito_aviso"},
    {"id": 92, "cat": "I_ratio", "q": "Taxa de conversao em emergencias (P0) nos ultimos 30 dias", "expect_shape": "scalar"},

    # J) Derived — projection (5)
    {"id": 93, "cat": "J_projection", "q": "Previsao de atendimento para catarata senil (H25) no HRT", "expect_metric": "previsao_atendimento", "expect_composition": "projection"},
    {"id": 94, "cat": "J_projection", "q": "Estimativa de espera para hipertensao essencial (I10) globalmente", "expect_metric": "previsao_atendimento", "expect_composition": "projection"},
    {"id": 95, "cat": "J_projection", "q": "Qual a previsao para neoplasia maligna mama (C50) no HBDF?", "expect_metric": "previsao_atendimento", "expect_composition": "projection"},
    {"id": 96, "cat": "J_projection", "q": "Estimativa de atendimento para casos eletivos (P3) na fila", "expect_composition": "projection"},
    {"id": 97, "cat": "J_projection", "q": "Previsao de espera para emergencias (P0) hoje", "expect_composition": "projection"},

    # K) Edge cases (3)
    {"id": 98, "cat": "K_edge", "q": "Como diminuir a fila eletiva?", "expect": "on_topic"},
    {"id": 99, "cat": "K_edge", "q": "Qual o cardapio do restaurante?", "expect": "refusal"},
    {"id": 100, "cat": "K_edge", "q": "Qual a melhor conduta clinica para hipertensao?", "expect": "refusal"},
]


def hit(q: str) -> tuple[Optional[dict], float, Optional[str]]:
    t0 = time.time()
    try:
        r = httpx.post(API, json={"pergunta": q}, timeout=TIMEOUT)
        elapsed = time.time() - t0
        if r.status_code != 200:
            return None, elapsed, f"HTTP {r.status_code}: {r.text[:200]}"
        return r.json(), elapsed, None
    except Exception as exc:
        return None, time.time() - t0, str(exc)


def evaluate(case: dict, resp: dict, elapsed: float) -> dict:
    prov = resp.get("proveniencia") or {}
    plan = prov.get("plan") or {}
    dados = resp.get("dados") or {}
    narrativa = resp.get("narrativa") or ""
    chart = resp.get("chart")

    out: dict = {
        "id": case["id"],
        "cat": case["cat"],
        "q": case["q"],
        "elapsed_s": round(elapsed, 1),
        "narrativa_preview": narrativa.replace("\n", " ")[:140],
    }

    expect = case.get("expect")
    if expect == "refusal":
        out["status"] = "refusal" if "refusal_reason" in prov else "UNEXPECTED_RESPONSE"
        out["pass"] = out["status"] == "refusal"
        return out
    if expect == "on_topic":
        if prov.get("refusal_reason"):
            out["status"] = "WRONG_REFUSAL"
            out["pass"] = False
        elif "clarifications" in prov:
            out["status"] = "CLARIFICATION"
            out["pass"] = False
        else:
            out["status"] = "responded"
            out["pass"] = bool(narrativa) and bool(plan)
        return out

    # data_query normal
    if "clarifications" in prov:
        out["status"] = "clarification"
        out["pass"] = case.get("expect") == "clarification"
        return out
    if "refusal_reason" in prov:
        out["status"] = "REFUSED"
        out["pass"] = False
        return out

    shape = prov.get("shape") or dados.get("shape")
    metric = prov.get("metric") or plan.get("metric")
    composition = plan.get("composition")

    out["shape"] = shape
    out["metric"] = metric
    out["composition"] = composition
    out["total"] = prov.get("total_documents")

    checks: dict[str, bool] = {}
    if "expect_shape" in case:
        checks["shape_ok"] = shape == case["expect_shape"]
    if "expect_metric" in case:
        checks["metric_ok"] = metric == case["expect_metric"]
    if "expect_composition" in case:
        checks["composition_ok"] = composition == case["expect_composition"]

    # P2: cita janela (lenient)
    win = prov.get("window") or {}
    win_label = (win.get("label") or "").lower()
    narr = narrativa.lower()
    temporal_words = ("snapshot", "atual", "agora", "ultimos", "últimos", "ultimas", "últimas",
                      "abril", "maio", "marco", "março", "janeiro", "fevereiro", "junho",
                      "dia", "mes", "mês", "periodo", "período")
    checks["P2_window"] = bool(win_label and win_label in narr) or any(w in narr for w in temporal_words)
    # P2: cita total
    total = prov.get("total_documents")
    if total is not None:
        narr_norm = narrativa.replace(".", "").replace(",", "")
        checks["P2_total"] = str(total) in narr_norm or f"{total:,}".replace(",", ".") in narrativa
    # Chart presence rule
    if shape == "scalar":
        checks["chart"] = chart is None
    elif shape in ("breakdown", "timeseries", "comparison", "distribution"):
        checks["chart"] = isinstance(chart, dict) and "data" in chart

    out["checks"] = checks
    out["pass"] = all(checks.values())
    out["status"] = "ok" if out["pass"] else "fail"
    return out


def main() -> int:
    print(f"Bateria 100 perguntas via {API}")
    print(f"Resultados em: {RESULTS_PATH}\n")

    # Carrega resultados existentes pra resume
    done: dict[int, dict] = {}
    if RESULTS_PATH.exists():
        try:
            for r in json.loads(RESULTS_PATH.read_text(encoding="utf-8")):
                done[r["id"]] = r
            print(f"Resume: {len(done)} ja processados")
        except Exception:
            pass

    results: list[dict] = list(done.values())

    for case in QUESTIONS:
        if case["id"] in done:
            continue
        q = case["q"]
        print(f"[{case['id']:3d}/{len(QUESTIONS)}] {case['cat']:24s} {q[:60]}", end="", flush=True)
        resp, elapsed, err = hit(q)
        if err or resp is None:
            res = {"id": case["id"], "cat": case["cat"], "q": q,
                   "elapsed_s": round(elapsed, 1), "status": "error",
                   "error": err, "pass": False}
        else:
            res = evaluate(case, resp, elapsed)
        results.append(res)
        # Save incrementally
        RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        mark = "OK" if res.get("pass") else f"FAIL ({res.get('status')})"
        print(f"  [{elapsed:5.1f}s] {mark}")

    # Summary
    print("\n" + "=" * 78)
    print("RESUMO")
    print("=" * 78)
    by_cat: dict[str, dict] = {}
    for r in results:
        cat = r["cat"]
        by_cat.setdefault(cat, {"pass": 0, "fail": 0, "total": 0, "avg_s": 0.0})
        by_cat[cat]["total"] += 1
        if r.get("pass"):
            by_cat[cat]["pass"] += 1
        else:
            by_cat[cat]["fail"] += 1
        by_cat[cat]["avg_s"] += r.get("elapsed_s", 0)

    total_pass = sum(1 for r in results if r.get("pass"))
    total_fail = len(results) - total_pass
    total_elapsed = sum(r.get("elapsed_s", 0) for r in results)
    print(f"\n{'Categoria':30s} {'PASS':>6} {'FAIL':>6} {'TOT':>6}  {'Avg s':>7}")
    print("-" * 60)
    for cat in sorted(by_cat):
        stats = by_cat[cat]
        avg = stats["avg_s"] / stats["total"] if stats["total"] else 0
        print(f"{cat:30s} {stats['pass']:>6} {stats['fail']:>6} {stats['total']:>6}  {avg:>6.1f}s")
    print("-" * 60)
    print(f"{'TOTAL':30s} {total_pass:>6} {total_fail:>6} {len(results):>6}  {total_elapsed/max(len(results),1):>6.1f}s")
    print(f"\nTempo total: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
    print(f"Taxa de sucesso: {total_pass/len(results)*100:.1f}%")

    # Lista falhas
    fails = [r for r in results if not r.get("pass")]
    if fails:
        print(f"\nFalhas detalhadas ({len(fails)}):")
        for r in fails:
            print(f"  #{r['id']:3d} [{r['cat']}] status={r.get('status')}")
            print(f"        Q: {r['q']}")
            if "checks" in r:
                failed_checks = [k for k, v in r["checks"].items() if not v]
                print(f"        Falhou em: {failed_checks}")
                if "shape" in r and r.get("shape"):
                    print(f"        shape={r['shape']} metric={r.get('metric')} composition={r.get('composition')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
