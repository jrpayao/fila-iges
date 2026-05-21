#!/usr/bin/env bash
set -euo pipefail
cd /mnt/d/ZELLO/IGES/fila-eletiva
python3 - <<'PY'
import json
from pathlib import Path

events = []
for line in Path("audit.jsonl").read_text(encoding="utf-8").strip().splitlines():
    try:
        events.append(json.loads(line))
    except json.JSONDecodeError:
        pass

usage_events = [e for e in events if e.get("event") == "llm.openai.usage"]
recent_usage = usage_events[-12:]

print(f"=== Ultimos {len(recent_usage)} eventos llm.openai.usage ===")
print(f"{'agent':<14} | {'prompt':>7} | {'cached':>7} | {'pct':>5} | {'completion':>10}")
print("-" * 64)
for e in recent_usage:
    agent = e.get("agent", "?")
    p = e.get("prompt_tokens", 0)
    c = e.get("cached_tokens", 0)
    pct = e.get("cache_hit_pct", 0)
    comp = e.get("completion_tokens", 0)
    print(f"{agent:<14} | {p:>7} | {c:>7} | {pct:>4}% | {comp:>10}")
PY
