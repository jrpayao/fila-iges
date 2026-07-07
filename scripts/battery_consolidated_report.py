"""Relatorio consolidado das duas baterias (tecnica 100q + gestao 25q).

Lê:
  scripts/battery_results.json (bateria 1 - 100 perguntas)
  scripts/battery_gestao_results.json (bateria 2 - gestao)
  scripts/battery_results_pre_AB_fixes.json (baseline anterior, se existir)

Imprime:
  - Tabela comparativa pre vs pos fixes A+B (por categoria)
  - Resumo bateria gestao
  - Lista de falhas remanescentes com proximos passos sugeridos
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
P_PRE = HERE / "battery_results_pre_AB_fixes.json"
P_POS = HERE / "battery_results.json"
P_GEST = HERE / "battery_gestao_results.json"


def load(p: Path) -> list[dict]:
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def cat_stats(items: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = defaultdict(lambda: {"pass": 0, "fail": 0, "total": 0, "elapsed": 0.0})
    for r in items:
        c = r.get("cat", "?")
        out[c]["total"] += 1
        out[c]["pass" if r.get("pass") else "fail"] += 1
        out[c]["elapsed"] += r.get("elapsed_s", 0)
    return out


def banner(s: str) -> None:
    print("\n" + "=" * 78)
    print(s)
    print("=" * 78)


def main() -> int:
    pre = load(P_PRE)
    pos = load(P_POS)
    gest = load(P_GEST)

    banner("BATERIA 1 — PRE vs POS fixes A+B (100 perguntas)")
    if not pre:
        print("Sem baseline 'pre_AB_fixes' encontrado — pulando comparativo.")
    else:
        pre_cat = cat_stats(pre)
        pos_cat = cat_stats(pos)
        cats = sorted(set(pre_cat) | set(pos_cat))
        print(f"\n{'Categoria':28s} {'PRE pass':>9} {'POS pass':>9} {'Delta':>6}")
        print("-" * 60)
        sum_pre = sum_pos = sum_tot = 0
        for c in cats:
            pp = pre_cat.get(c, {}).get("pass", 0)
            pt = pre_cat.get(c, {}).get("total", 0)
            xp = pos_cat.get(c, {}).get("pass", 0)
            xt = pos_cat.get(c, {}).get("total", 0)
            tot = max(pt, xt)
            delta = xp - pp
            arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
            print(f"{c:28s} {pp:>3}/{pt:<3}   {xp:>3}/{xt:<3}   {arrow} {delta:+d}")
            sum_pre += pp
            sum_pos += xp
            sum_tot += tot
        print("-" * 60)
        print(f"{'TOTAL':28s} {sum_pre:>3}/{sum_tot:<3}   {sum_pos:>3}/{sum_tot:<3}   Δ {sum_pos-sum_pre:+d}")
        if sum_tot:
            print(f"\nTaxa PRE: {sum_pre/sum_tot*100:.1f}%   Taxa POS: {sum_pos/sum_tot*100:.1f}%")

    banner("BATERIA 1 — POS A+B: composition usage")
    by_comp: dict[str, int] = defaultdict(int)
    for r in pos:
        c = r.get("composition") or "(none/refusal/error)"
        by_comp[c] += 1
    for c, n in sorted(by_comp.items()):
        print(f"  {c:14s}: {n}")

    banner(f"BATERIA 2 — GESTAO ({len(gest)} perguntas)")
    if not gest:
        print("(bateria gestao ainda nao rodada)")
    else:
        cat = cat_stats(gest)
        print(f"\n{'Categoria':22s} {'PASS':>6} {'FAIL':>6} {'TOT':>6}  {'Avg s':>7}")
        print("-" * 56)
        gp = gt = 0
        for c in sorted(cat):
            s = cat[c]
            avg = s["elapsed"] / s["total"] if s["total"] else 0
            print(f"{c:22s} {s['pass']:>6} {s['fail']:>6} {s['total']:>6}  {avg:>6.1f}s")
            gp += s["pass"]
            gt += s["total"]
        print("-" * 56)
        print(f"{'TOTAL':22s} {gp:>6} {gt-gp:>6} {gt:>6}")
        print(f"\nGestao taxa: {gp/max(gt,1)*100:.1f}%")
        diag = sum(1 for r in gest if r.get("composition") == "diagnostic")
        print(f"Composition=diagnostic em gestao: {diag}/{gt}")

    banner("FALHAS REMANESCENTES — bateria tecnica")
    fails = [r for r in pos if not r.get("pass")]
    if not fails:
        print("Nenhuma falha. 100/100 ✓")
    else:
        for r in fails:
            cs = r.get("checks") or {}
            failed_checks = [k for k, v in cs.items() if not v]
            print(f"  #{r['id']:3d} [{r['cat']}] {r.get('status'):20s} {r['q'][:60]}")
            if failed_checks:
                print(f"        checks_fail: {failed_checks}")
            if r.get("shape"):
                print(f"        got shape={r['shape']} metric={r.get('metric')} comp={r.get('composition')}")

    banner("FALHAS REMANESCENTES — bateria gestao")
    fails_g = [r for r in gest if not r.get("pass")]
    if not fails_g:
        print("Nenhuma falha.")
    else:
        for r in fails_g:
            print(f"  #{r['id']:3d} [{r['cat']}] {r.get('status'):20s} {r['q'][:60]}")
            if r.get("composition"):
                print(f"        composition={r['composition']} steps={r.get('steps_count')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
