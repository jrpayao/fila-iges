"""Analise completa dos resultados da bateria de 100 perguntas."""

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

p = Path(__file__).parent / "battery_results.json"
results = json.loads(p.read_text(encoding="utf-8"))

print("=" * 80)
print(f"ANALISE BATERIA — {len(results)} perguntas")
print("=" * 80)

passed = [r for r in results if r.get("pass")]
failed = [r for r in results if not r.get("pass")]

print(f"\n--> PASS: {len(passed)} ({len(passed)/len(results)*100:.1f}%)")
print(f"--> FAIL: {len(failed)} ({len(failed)/len(results)*100:.1f}%)")

# ===== 1. POR CATEGORIA =====
print("\n" + "=" * 80)
print("1. PASS RATE POR CATEGORIA")
print("=" * 80)
by_cat: dict[str, dict] = defaultdict(lambda: {"pass": 0, "fail": 0, "elapsed": []})
for r in results:
    cat = r["cat"]
    by_cat[cat]["pass" if r.get("pass") else "fail"] += 1
    if r.get("elapsed_s"):
        by_cat[cat]["elapsed"].append(r["elapsed_s"])

print(f"\n{'Categoria':30s}  {'PASS':>4}  {'FAIL':>4}  {'TOT':>4}  {'%':>5}  {'Media':>6}  {'p90':>6}")
print("-" * 80)
for cat in sorted(by_cat):
    s = by_cat[cat]
    tot = s["pass"] + s["fail"]
    pct = s["pass"] / tot * 100 if tot else 0
    avg = statistics.mean(s["elapsed"]) if s["elapsed"] else 0
    p90 = sorted(s["elapsed"])[int(len(s["elapsed"]) * 0.9)] if len(s["elapsed"]) >= 2 else avg
    print(f"{cat:30s}  {s['pass']:>4}  {s['fail']:>4}  {tot:>4}  {pct:>4.0f}%  {avg:>5.1f}s  {p90:>5.1f}s")

# ===== 2. ANALISE DAS FALHAS TECNICAS (errors) =====
print("\n" + "=" * 80)
print("2. ERRORS TECNICOS")
print("=" * 80)
errors = [r for r in failed if r.get("status") == "error"]
print(f"\nTotal errors: {len(errors)}")
error_types: Counter = Counter()
for r in errors:
    err = r.get("error", "?")
    # extract error class
    if "HTTPStatusError" in err or "HTTP " in err:
        error_types["HTTP status"] += 1
    elif "ReadTimeout" in err or "timeout" in err.lower():
        error_types["timeout"] += 1
    elif "Connect" in err:
        error_types["connection"] += 1
    else:
        error_types[err[:60]] += 1

for et, n in error_types.most_common():
    print(f"  {n:3d}x  {et}")

if errors:
    print(f"\nDetalhe dos errors:")
    for r in errors:
        err_preview = (r.get("error") or "")[:120]
        print(f"  #{r['id']:3d} [{r['cat']}] ({r.get('elapsed_s')}s)")
        print(f"        Q: {r['q']}")
        print(f"        Err: {err_preview}")

# ===== 3. FALHAS DE VALIDACAO =====
print("\n" + "=" * 80)
print("3. FALHAS DE VALIDACAO (planner/synthesizer errou)")
print("=" * 80)
val_fails = [r for r in failed if r.get("status") not in ("error",)]
print(f"\nTotal: {len(val_fails)}")

# Categoriza por tipo
fail_reasons: Counter = Counter()
for r in val_fails:
    status = r.get("status", "?")
    if status == "fail":
        # Detalhe via checks
        for k, v in (r.get("checks") or {}).items():
            if not v:
                fail_reasons[f"check:{k}"] += 1
    else:
        fail_reasons[status] += 1

for reason, n in fail_reasons.most_common():
    print(f"  {n:3d}x  {reason}")

print(f"\nDetalhe:")
for r in val_fails:
    print(f"  #{r['id']:3d} [{r['cat']}] status={r.get('status')} ({r.get('elapsed_s')}s)")
    print(f"        Q: {r['q']}")
    if r.get("checks"):
        failed_checks = [k for k, v in r["checks"].items() if not v]
        print(f"        Falhou em: {failed_checks}")
    print(f"        shape={r.get('shape')} metric={r.get('metric')} composition={r.get('composition')}")
    preview = (r.get("narrativa_preview") or "")[:100]
    print(f"        Preview: {preview}")

# ===== 4. LATENCIA POR SHAPE =====
print("\n" + "=" * 80)
print("4. LATENCIA POR SHAPE")
print("=" * 80)
by_shape: dict[str, list[float]] = defaultdict(list)
for r in passed:
    shape = r.get("shape")
    if shape and r.get("elapsed_s"):
        by_shape[shape].append(r["elapsed_s"])

print(f"\n{'Shape':20s}  {'N':>4}  {'min':>6}  {'mediana':>8}  {'avg':>6}  {'p90':>6}  {'max':>6}")
print("-" * 65)
for shape in sorted(by_shape):
    vals = sorted(by_shape[shape])
    n = len(vals)
    mn = vals[0]
    md = statistics.median(vals)
    avg = statistics.mean(vals)
    p90 = vals[int(n * 0.9)] if n >= 2 else avg
    mx = vals[-1]
    print(f"{shape:20s}  {n:>4}  {mn:>5.1f}s  {md:>7.1f}s  {avg:>5.1f}s  {p90:>5.1f}s  {mx:>5.1f}s")

# ===== 5. SUMARIO FINAL =====
print("\n" + "=" * 80)
print("5. METRICAS GERAIS")
print("=" * 80)
all_elapsed = [r["elapsed_s"] for r in results if r.get("elapsed_s")]
total_s = sum(all_elapsed)
print(f"  Tempo total: {total_s:.0f}s ({total_s/60:.1f} min)")
print(f"  Media: {statistics.mean(all_elapsed):.1f}s")
print(f"  Mediana: {statistics.median(all_elapsed):.1f}s")
print(f"  Min/Max: {min(all_elapsed):.1f}s / {max(all_elapsed):.1f}s")
print(f"  Errors: {len(errors)} ({len(errors)/len(results)*100:.1f}%)")
print(f"  Validation fails: {len(val_fails)} ({len(val_fails)/len(results)*100:.1f}%)")
print(f"  Pass rate: {len(passed)/len(results)*100:.1f}%")
