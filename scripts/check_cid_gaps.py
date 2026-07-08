"""Inspecao da base CID-10 atual: lista U-codes presentes e codigos-alvo de COVID."""

import json
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "agent" / "data" / "cid10.json"
data = json.loads(p.read_text(encoding="utf-8"))

print(f"Total de codigos na base: {len(data)}\n")

print("=== Codigos U-* atuais (capitulo XXII) ===")
u_codes = sorted([(k, v) for k, v in data.items() if k.startswith("U")])
for k, v in u_codes:
    print(f"  {k:6} {v}")

print("\n=== Codigos COVID/Zika esperados (verificar gap) ===")
expected = [
    "U07", "U071", "U072",
    "U08", "U089",
    "U09", "U099",
    "U10", "U109",
    "U11", "U119",
    "U12", "U129",
    "A925",  # Zika
]
for code in expected:
    status = "PRESENTE" if code in data else "FALTA"
    print(f"  {code:6} {status}: {data.get(code, '')}")
