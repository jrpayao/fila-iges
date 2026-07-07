"""Sanity-check rapido das mudancas em prompts.py."""
from app.agent import prompts

print("PLANNER_VERSION:", prompts.PLANNER_VERSION)
print("SYNTHESIZER_VERSION:", prompts.SYNTHESIZER_VERSION)

planner = prompts.planner_system()
synth = prompts.SYNTHESIZER_SYSTEM

print(f"planner_system len: {len(planner)}")
print(f"SYNTHESIZER_SYSTEM len: {len(synth)}")

checks = [
    ("diagnostic", planner, "diagnostic"),
    ("lead_time rule", planner, "NUNCA use primitive"),
    ("hospitalar scope", planner, "solicitacao-hospitalar"),
    ("tempo_regulacao example", planner, "tempo medio de regulacao"),
    ("diminuir fila example", planner, "Como diminuir a fila"),
    ("gargalo example", planner, "gargalo da regulacao"),
    ("falta example", planner, "tanta gente falta"),
    ("synth diagnostic mode", synth, "Modo DIAGNOSTICO"),
    ("synth sub_envelopes", synth, "sub_envelopes"),
]
for name, body, needle in checks:
    ok = needle in body
    print(f"  [{'OK' if ok else 'MISS'}] {name}: '{needle}'")
