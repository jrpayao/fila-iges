"""Mostra status atual da bateria."""

import json
from collections import Counter
from pathlib import Path

p = Path(__file__).parent / "battery_results.json"
if not p.exists():
    print("Sem arquivo de resultados ainda.")
    raise SystemExit(0)

results = json.loads(p.read_text(encoding="utf-8"))
print(f"Processadas: {len(results)} / 100")

passed = sum(1 for r in results if r.get("pass"))
failed = len(results) - passed
print(f"  PASS: {passed}")
print(f"  FAIL: {failed}")

# breakdown por status
by_status = Counter(r.get("status", "?") for r in results)
print(f"\nPor status:")
for st, n in by_status.most_common():
    print(f"  {st:20s}  {n}")

# tempo medio
elapsed = [r.get("elapsed_s", 0) for r in results if r.get("elapsed_s")]
if elapsed:
    total = sum(elapsed)
    avg = total / len(elapsed)
    print(f"\nTempo: total {total:.0f}s ({total/60:.1f} min), media {avg:.1f}s/pergunta")

# ultimas 5
print(f"\nUltimas processadas:")
for r in results[-5:]:
    ok = "OK" if r.get("pass") else "FAIL"
    print(f"  #{r['id']:3d} [{r['cat']:24s}] {ok:5s} {r['elapsed_s']:5.1f}s  {r['q'][:50]}")
