"""Bateria 2 - Perguntas de gestao de saude publica.

Foco em decisoes que um coordenador da CGRA, diretor IGES, ou Secretario de Saude
faria. Diferente da bateria 1 (cobertura tecnica do catalogo), aqui mede a
capacidade do agente de responder perguntas de gestao DE VERDADE — incluindo
muitas que naturalmente disparam composition=diagnostic.

Salva em scripts/battery_gestao_results.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

import httpx

API = "http://127.0.0.1:8000/chat"
TIMEOUT = 240  # diagnostic pode demorar mais (N steps)
RESULTS_PATH = Path(__file__).parent / "battery_gestao_results.json"


QUESTIONS: list[dict[str, Any]] = [
    # ===== Diagnostico operacional (8) =====
    {"id": 1, "cat": "DIAG_operacional",
     "q": "Como diminuir a fila eletiva ambulatorial?", "expect": "on_topic_diagnostic"},
    {"id": 2, "cat": "DIAG_operacional",
     "q": "Onde esta o maior gargalo na regulacao hoje?", "expect": "on_topic_diagnostic"},
    {"id": 3, "cat": "DIAG_operacional",
     "q": "Por que tantos pacientes faltam as consultas marcadas?", "expect": "on_topic_diagnostic"},
    {"id": 4, "cat": "DIAG_operacional",
     "q": "Quais unidades estao mais sobrecarregadas em demanda eletiva?", "expect": "on_topic"},
    {"id": 5, "cat": "DIAG_operacional",
     "q": "Quais especialidades concentram mais espera na fila?", "expect": "on_topic"},
    {"id": 6, "cat": "DIAG_operacional",
     "q": "Como melhorar a taxa de comparecimento aos agendamentos?", "expect": "on_topic_diagnostic"},
    {"id": 7, "cat": "DIAG_operacional",
     "q": "Onde concentrar esforco operacional para reduzir tempo de espera?", "expect": "on_topic_diagnostic"},
    {"id": 8, "cat": "DIAG_operacional",
     "q": "Qual o impacto do aviso ao paciente na taxa de comparecimento?", "expect": "on_topic"},

    # ===== Capacidade vs demanda (5) =====
    {"id": 9, "cat": "CAPACIDADE",
     "q": "A entrada de solicitacoes esta acima da nossa capacidade de atendimento?", "expect": "on_topic"},
    {"id": 10, "cat": "CAPACIDADE",
     "q": "Em quanto tempo zeraremos a fila atual se mantivermos a vazao?", "expect": "on_topic"},
    {"id": 11, "cat": "CAPACIDADE",
     "q": "A vazao mensal de atendimentos esta crescendo, estabilizada ou caindo?", "expect": "on_topic"},
    {"id": 12, "cat": "CAPACIDADE",
     "q": "Quantos atendimentos por dia precisariamos para nao acumular fila?", "expect": "on_topic"},
    {"id": 13, "cat": "CAPACIDADE",
     "q": "Qual a previsao de espera para casos eletivos (P3) hoje?", "expect": "on_topic"},

    # ===== Prioridade clinica (4) =====
    {"id": 14, "cat": "PRIORIDADE",
     "q": "Os casos urgentes (P1) estao sendo priorizados em relacao aos eletivos (P3)?", "expect": "on_topic"},
    {"id": 15, "cat": "PRIORIDADE",
     "q": "Quantas emergencias (P0) estao aguardando na fila agora?", "expect": "on_topic"},
    {"id": 16, "cat": "PRIORIDADE",
     "q": "O tempo medio de regulacao para urgencias (P1) e adequado?", "expect": "on_topic"},
    {"id": 17, "cat": "PRIORIDADE",
     "q": "Distribuicao da fila por prioridade de risco", "expect": "on_topic"},

    # ===== Equidade territorial (3) =====
    {"id": 18, "cat": "EQUIDADE",
     "q": "Quais municipios concentram mais pacientes na fila de espera?", "expect": "on_topic"},
    {"id": 19, "cat": "EQUIDADE",
     "q": "Algum bairro ou regiao tem volume desproporcional de fila?", "expect": "on_topic"},
    {"id": 20, "cat": "EQUIDADE",
     "q": "Como esta distribuida a fila ambulatorial entre as regionais de saude?", "expect": "on_topic"},

    # ===== Risco clinico / impacto (3) =====
    {"id": 21, "cat": "RISCO_CLINICO",
     "q": "Quais CIDs oncologicos (C00-C97) estao mais represados na fila?", "expect": "on_topic"},
    {"id": 22, "cat": "RISCO_CLINICO",
     "q": "Quantos pacientes com hipertensao essencial (I10) estao aguardando atendimento?", "expect": "on_topic"},
    {"id": 23, "cat": "RISCO_CLINICO",
     "q": "Qual o tempo medio de espera para neoplasias malignas?", "expect": "on_topic"},

    # ===== Off-topic / boundary (2) =====
    {"id": 24, "cat": "OFF_TOPIC",
     "q": "Qual o melhor remedio para hipertensao em paciente diabetico?", "expect": "refusal"},
    {"id": 25, "cat": "OFF_TOPIC",
     "q": "Quem e o secretario de saude do DF atualmente?", "expect": "refusal"},
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

    out: dict = {
        "id": case["id"],
        "cat": case["cat"],
        "q": case["q"],
        "elapsed_s": round(elapsed, 1),
        "narrativa_preview": narrativa.replace("\n", " ")[:200],
        "narrativa_full": narrativa,  # gestao quer ler resposta inteira
    }

    expect = case["expect"]

    if expect == "refusal":
        out["status"] = "refusal" if "refusal_reason" in prov else "UNEXPECTED_RESPONSE"
        out["pass"] = out["status"] == "refusal"
        return out

    # on_topic_diagnostic: deve ter composition=diagnostic OU pelo menos resposta substantiva
    if expect == "on_topic_diagnostic":
        if prov.get("refusal_reason"):
            out["status"] = "WRONG_REFUSAL"
            out["pass"] = False
            return out
        comp = plan.get("composition")
        out["composition"] = comp
        out["steps_count"] = len(plan.get("steps") or [])
        out["has_sub_envelopes"] = bool(dados.get("sub_envelopes") or prov.get("method_note", "").startswith("Diagnostico"))
        out["total"] = prov.get("total_documents")
        # Aceita: diagnostic com >=2 steps, OU resposta substantiva (>= 300 chars)
        if comp == "diagnostic" and out["steps_count"] >= 2:
            out["status"] = "diagnostic_ok"
            out["pass"] = True
        elif len(narrativa) > 300 and plan.get("steps"):
            out["status"] = "fallback_responded"
            out["pass"] = True  # nao virou diagnostic, mas respondeu substantivamente
        else:
            out["status"] = "INSUFFICIENT_ANSWER"
            out["pass"] = False
        return out

    # on_topic generico
    if prov.get("refusal_reason"):
        out["status"] = "WRONG_REFUSAL"
        out["pass"] = False
        return out
    if "clarifications" in prov:
        out["status"] = "CLARIFICATION_UNEXPECTED"
        out["pass"] = False
        return out
    out["shape"] = prov.get("shape")
    out["metric"] = prov.get("metric")
    out["composition"] = plan.get("composition")
    out["steps_count"] = len(plan.get("steps") or [])
    out["total"] = prov.get("total_documents")
    out["status"] = "responded" if narrativa and plan else "WEAK_RESPONSE"
    out["pass"] = bool(narrativa and plan)
    return out


def main() -> int:
    print(f"Bateria GESTAO ({len(QUESTIONS)} perguntas) via {API}")
    print(f"Resultados em: {RESULTS_PATH}\n")

    done: dict[int, dict] = {}
    if RESULTS_PATH.exists():
        try:
            for r in json.loads(RESULTS_PATH.read_text(encoding="utf-8")):
                done[r["id"]] = r
            print(f"Resume: {len(done)} ja processados\n")
        except Exception:
            pass

    results: list[dict] = list(done.values())

    for case in QUESTIONS:
        if case["id"] in done:
            continue
        q = case["q"]
        print(f"[{case['id']:3d}/{len(QUESTIONS)}] {case['cat']:20s} {q[:60]}", end="", flush=True)
        resp, elapsed, err = hit(q)
        if err or resp is None:
            res = {"id": case["id"], "cat": case["cat"], "q": q,
                   "elapsed_s": round(elapsed, 1), "status": "error",
                   "error": err, "pass": False}
        else:
            res = evaluate(case, resp, elapsed)
        results.append(res)
        RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        mark = "OK" if res.get("pass") else f"FAIL ({res.get('status')})"
        print(f"  [{elapsed:5.1f}s] {mark}")

    # Summary
    print("\n" + "=" * 78)
    print("RESUMO GESTAO")
    print("=" * 78)
    by_cat: dict[str, dict] = {}
    for r in results:
        cat = r["cat"]
        by_cat.setdefault(cat, {"pass": 0, "fail": 0, "total": 0, "avg_s": 0.0})
        by_cat[cat]["total"] += 1
        by_cat[cat]["pass" if r.get("pass") else "fail"] += 1
        by_cat[cat]["avg_s"] += r.get("elapsed_s", 0)

    total_pass = sum(1 for r in results if r.get("pass"))
    total_elapsed = sum(r.get("elapsed_s", 0) for r in results)
    print(f"\n{'Categoria':22s} {'PASS':>6} {'FAIL':>6} {'TOT':>6}  {'Avg s':>7}")
    print("-" * 56)
    for cat in sorted(by_cat):
        s = by_cat[cat]
        avg = s["avg_s"] / s["total"] if s["total"] else 0
        print(f"{cat:22s} {s['pass']:>6} {s['fail']:>6} {s['total']:>6}  {avg:>6.1f}s")
    print("-" * 56)
    print(f"{'TOTAL':22s} {total_pass:>6} {len(results)-total_pass:>6} {len(results):>6}")
    print(f"Tempo total: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
    print(f"Taxa de sucesso: {total_pass/max(len(results),1)*100:.1f}%")

    # Quantas viraram diagnostic
    diag = sum(1 for r in results if r.get("composition") == "diagnostic")
    print(f"Composition=diagnostic: {diag}/{len(results)} perguntas")

    fails = [r for r in results if not r.get("pass")]
    if fails:
        print(f"\nFalhas ({len(fails)}):")
        for r in fails:
            print(f"  #{r['id']} [{r['cat']}] status={r.get('status')}: {r['q'][:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
