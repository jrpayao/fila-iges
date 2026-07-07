"""Bateria de testes via API. Roda 13 perguntas, valida resposta."""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Optional

import httpx

API = "http://127.0.0.1:8000/chat"
TIMEOUT = 180

QUESTIONS: list[dict[str, Any]] = [
    # SCALAR
    {"id": 1, "shape_expected": "scalar", "metric_expected": "estoque_fila",
     "q": "Quantas solicitacoes estao pendentes na fila ambulatorial agora?"},
    {"id": 2, "shape_expected": "scalar", "metric_expected": "entrada_solicitacoes",
     "q": "Quantas solicitacoes novas chegaram nos ultimos 30 dias?"},
    # BREAKDOWN
    {"id": 3, "shape_expected": "breakdown", "metric_expected": "entrada_solicitacoes",
     "q": "Top 10 CIDs solicitados nos ultimos 30 dias"},
    {"id": 4, "shape_expected": "breakdown",
     "q": "Quais as 5 unidades que mais solicitam atendimento nos ultimos 60 dias?"},
    {"id": 5, "shape_expected": "breakdown",
     "q": "Como esta a distribuicao por prioridade na fila atual?"},
    # TIMESERIES
    {"id": 6, "shape_expected": "timeseries",
     "q": "Mostre a evolucao diaria das solicitacoes nas ultimas 2 semanas"},
    # COMPARISON
    {"id": 7, "shape_expected": "comparison",
     "q": "Compare o volume de solicitacoes do HRT com outras unidades nos ultimos 30 dias"},
    # DISTRIBUTION
    {"id": 8, "shape_expected": "distribution",
     "q": "Qual o tempo medio de regulacao dos agendamentos nos ultimos 30 dias?"},
    # DERIVED — ratio
    {"id": 9, "shape_expected": "scalar", "metric_expected": "taxa_falta",
     "composition_expected": "ratio",
     "q": "Qual a taxa de falta nos agendamentos nos ultimos 30 dias?"},
    # DERIVED — projection
    {"id": 10, "shape_expected": "scalar", "metric_expected": "previsao_atendimento",
     "composition_expected": "projection",
     "q": "Qual a estimativa de atendimento para hipertensao essencial no HBDF?"},
    # CLARIFICATION
    {"id": 11, "expect": "clarification",
     "q": "Top CIDs de catarata no ultimo mes"},
    # ON-TOPIC (P11 corrigido)
    {"id": 12, "expect": "on_topic",
     "q": "Como diminuir a fila eletiva?"},
    # OFF-TOPIC
    {"id": 13, "expect": "refusal",
     "q": "Qual o cardapio do restaurante?"},
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


def check(case: dict[str, Any], resp: dict[str, Any]) -> dict[str, Any]:
    prov = resp.get("proveniencia") or {}
    plan = prov.get("plan") or {}
    dados = resp.get("dados") or {}
    narrativa = resp.get("narrativa") or ""
    chart = resp.get("chart")

    expect = case.get("expect")
    results: dict[str, Any] = {}

    if expect == "refusal":
        results["refusal_emitted"] = "refusal_reason" in prov
        results["no_envelope"] = resp.get("dados") is None
        return results

    if expect == "clarification":
        results["clarification_emitted"] = "clarifications" in prov and bool(prov.get("clarifications"))
        results["no_envelope"] = resp.get("dados") is None
        return results

    # Casos normais (data_query)
    results["plan_present"] = bool(plan)
    results["plan_in_scope"] = plan.get("is_in_scope", False)

    shape = prov.get("shape") or dados.get("shape")
    metric = prov.get("metric") or plan.get("metric")
    composition = plan.get("composition")
    method_note = prov.get("method_note")
    metric_kind = prov.get("metric_kind")

    if "shape_expected" in case:
        results["shape_match"] = shape == case["shape_expected"]
        results["shape_actual"] = shape
    if "metric_expected" in case:
        results["metric_match"] = metric == case["metric_expected"]
        results["metric_actual"] = metric
    if "composition_expected" in case:
        results["composition_match"] = composition == case["composition_expected"]
        results["composition_actual"] = composition

    # P2: narrativa cita contexto temporal + total + indice?
    win = prov.get("window") or {}
    win_label = (win.get("label") or "").lower()
    win_gte = (win.get("gte") or "")
    win_lte = (win.get("lte") or "")
    src = prov.get("source_index", "")
    total = prov.get("total_documents")
    narr = narrativa.lower()
    # P2 — janela: aceita label literal OR data ISO OR palavras temporais
    cites_window = (
        (win_label and win_label in narr)
        or (win_gte and win_gte in narrativa)
        or (win_lte and win_lte in narrativa)
        or any(w in narr for w in ("snapshot", "atual", "agora", "ultimos", "últimos",
                                    "abril", "maio", "marco", "março", "janeiro",
                                    "fevereiro", "junho", "dia", "mes", "mês"))
    )
    cites_index = bool(src and (src in narrativa or src.split("-")[0] in narrativa))
    total_str_norm = narrativa.replace(".", "").replace(",", "")
    cites_total = total is not None and (
        str(total) in total_str_norm or f"{total:,}".replace(",", ".") in narrativa
    )
    results["P2_cites_window"] = bool(cites_window)
    results["P2_cites_index_or_metric"] = bool(cites_index or (metric and metric in narrativa))
    results["P2_cites_total"] = bool(cites_total)

    # P3: derived com projection exige method_note
    if metric_kind == "derived" and composition in {"ratio", "projection"}:
        results["P3_method_note"] = bool(method_note)
        if metric == "previsao_atendimento":
            results["P3_says_estimativa"] = "estimativa" in (method_note or "").lower() or "estimativa" in narrativa.lower()

    # Chart presence rule:
    # scalar -> chart None (UI usa metric card)
    # outros -> chart deve ser dict com 'data' field do Plotly
    if shape == "scalar":
        results["chart_correctly_absent"] = chart is None
    else:
        results["chart_present"] = isinstance(chart, dict) and "data" in chart

    return results


def fmt_check(results: dict[str, Any]) -> str:
    lines = []
    for k, v in results.items():
        if isinstance(v, bool):
            mark = "PASS" if v else "FAIL"
            lines.append(f"     [{mark}] {k}")
        else:
            lines.append(f"     [info] {k} = {v}")
    return "\n".join(lines)


def main() -> int:
    print(f"Bateria de {len(QUESTIONS)} perguntas via {API}\n")
    summary = {"pass": 0, "fail": 0, "error": 0}
    for case in QUESTIONS:
        q = case["q"]
        print(f"=" * 78)
        print(f"#{case['id']:2d}  {q}")
        resp, elapsed, err = hit(q)
        if err:
            print(f"     ERRO ({elapsed:.1f}s): {err}")
            summary["error"] += 1
            continue
        if resp is None:
            print(f"     ERRO ({elapsed:.1f}s): resposta vazia")
            summary["error"] += 1
            continue
        results = check(case, resp)
        narrativa_preview = (resp.get("narrativa") or "").split("\n")[0][:120]
        print(f"     [{elapsed:5.1f}s] narrativa: {narrativa_preview}")
        print(fmt_check(results))

        # Conta pass/fail dos checks booleanos
        bools = [v for v in results.values() if isinstance(v, bool)]
        all_pass = all(bools)
        if all_pass:
            summary["pass"] += 1
        else:
            summary["fail"] += 1
        print()

    print("=" * 78)
    print(f"RESUMO: {summary['pass']} passaram, {summary['fail']} falharam, {summary['error']} erros")
    return 0 if summary["fail"] == 0 and summary["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
