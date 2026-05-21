#!/usr/bin/env bash
set -euo pipefail
curl -s -m 10 'http://127.0.0.1:8000/audit?limit=12' | python3 <<'PY'
import json, sys
d = json.load(sys.stdin)
print(f"total eventos lidos: {d['total_read']}")
print(f"arquivo: {d['file']}")
print()
for e in d["events"]:
    rid = (e.get("request_id") or "")[:8]
    ev = e.get("event", "?")
    extras = []
    if "decision" in e: extras.append(f"decision={e['decision']}")
    if "intent" in e: extras.append(f"intent={e['intent']}")
    if "took_ms" in e: extras.append(f"took={e['took_ms']}ms")
    if "template" in e: extras.append(f"template={e['template']}")
    suffix = " | " + " ".join(extras) if extras else ""
    print(f"  {ev:32s} | rid={rid}...{suffix}")
PY
