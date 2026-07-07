"""Quick dump das falhas atuais."""
import json
from pathlib import Path

r = json.loads((Path(__file__).parent / "battery_results.json").read_text(encoding="utf-8"))
fails = [x for x in r if not x.get("pass")]
print(f"FAILS atuais: {len(fails)}")
for x in fails:
    print(f"  #{x['id']:3d} [{x['cat']}] {x.get('status'):14s}: {x['q'][:55]}")
    cs = x.get("checks") or {}
    bad = [k for k, v in cs.items() if not v]
    if bad:
        print(f"        checks_fail={bad}")
    if x.get("shape"):
        print(f"        got shape={x['shape']} metric={x.get('metric')} comp={x.get('composition')} total={x.get('total')}")
