"""Smoke de integracao Fase 5 — engine.ask -> dict {narrativa, dados, proveniencia, chart}."""

from __future__ import annotations

from app.engine import ask

for q in [
    "Quais procedimentos tem mais vagas disponiveis neste mes?",   # breakdown -> chart bar
    "Como evoluiu a oferta de ressonancia magnetica?",             # timeseries -> chart line
    "Quantas vagas disponiveis ha em julho de 2026?",              # scalar -> chart None
]:
    print("\n" + "=" * 70)
    print("Q:", q)
    r = ask(q)
    prov = r.get("proveniencia", {})
    dados = r.get("dados") or {}
    chart = r.get("chart")
    print(f"  engine_version={prov.get('engine_version')} metric={prov.get('metric')} shape={prov.get('shape')}")
    print(f"  dados.shape={dados.get('shape')} chart={'sim (' + chart['data'][0]['type'] + ')' if chart else 'None (scalar)'}")
    print(f"  narrativa[:120]: {(r.get('narrativa') or '')[:120]}")
print("\nOK — engine.ask -> dict + chart funcionando (Fase 5).")
