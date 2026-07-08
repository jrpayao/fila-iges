"""Smoke do Pacote Wow (sem LLM) — novas primitivas + delta."""

from __future__ import annotations

from app.vagas import primitives as P
from app.vagas.store import VagasStore


def main() -> int:
    df = VagasStore().load_df()
    if df.empty:
        print("cache vazio"); return 1

    print("== A: delta automatico ==")
    e = P.total(df, metric="vagas_disponiveis")
    print("  total:", e.data[0])

    print("\n== C: metricas derivadas ==")
    for fn, name in [(P.indice_porta_entrada, "porta_entrada"), (P.taxa_reserva, "taxa_reserva")]:
        e = fn(df)
        print(f"  {name}: value={e.data[0]['value']}% delta={e.data[0].get('delta_pct')} note={e.method_note[:60]}")
    e = P.vagas_perdidas_ytd(df)
    print(f"  perdidas_ytd: {e.data[0]['value']} ({e.window.label})")

    print("\n== B: oportunidade de desbloqueio (top 5) ==")
    e = P.oportunidade_desbloqueio(df, top_n=5)
    for b in e.data:
        print(f"    {b['value']:>5} bloq | persist={b['persistencia_meses']}m | {b['key']}")

    print("\n== D: monofornecedores (<=2 hospitais) ==")
    e = P.cobertura_rede(df, max_hospitais=2, top_n=8)
    for b in e.data:
        print(f"    {b['value']} hosp | {b['key'][:60]}")
    print(f"  (metric={e.metric}, total procedimentos frageis listados={len(e.data)})")

    print("\n== E: panorama (briefing) ==")
    e = P.panorama(df)
    print(f"  primary shape={e.shape.value} sub_envelopes={len(e.sub_envelopes)}")
    for s in e.sub_envelopes:
        print(f"    - {s['metric']:24s} shape={s['shape']} val0={s['data'][0].get('value') if s['data'] else '?'}")

    print("\nOK — Pacote Wow (primitivas) funcionando.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
