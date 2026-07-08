"""Smoke da Fase 2 — primitivas de vagas sobre o DataFrame -> Envelope."""

from __future__ import annotations

from app.vagas import primitives as P
from app.vagas import resolver as R
from app.vagas.store import VagasStore


def show(env, titulo):
    print(f"\n### {titulo}")
    print(f"  metric={env.metric} shape={env.shape.value} units={env.units} kind={env.metric_kind.value}")
    print(f"  window={env.window.label} filters={env.filters}")
    d = env.data
    if env.shape.value == "scalar":
        print(f"  value={d[0]['value']}")
    elif env.shape.value in ("breakdown",):
        for b in d[:6]:
            print(f"    {b['value']:>7}  {b['key'][:58]}")
    elif env.shape.value == "timeseries":
        print("    " + " ".join(f"{p['key']}={p['value']}" for p in d[:6]) + " ...")
    elif env.shape.value == "comparison":
        print(f"  focus={d[0]['focus']}  benchmark[0..2]={d[0]['benchmark'][:2]}")


def main() -> int:
    df = VagasStore().load_df()
    if df.empty:
        print("cache vazio — rode scripts/smoke_vagas.py antes."); return 1

    comp = R.latest_competencia(df)
    print(f"competencia mais recente: {comp.label} | linhas={len(df)}")

    show(P.total(df, metric="vagas_disponiveis"), "total vagas_disponiveis (comp atual)")
    show(P.total(df, metric="vagas_ativas"), "total vagas_ativas")
    show(P.total(df, metric="vagas_bloqueadas"), "total vagas_bloqueadas")
    show(P.taxa_bloqueio(df), "taxa_bloqueio")
    show(P.breakdown(df, metric="vagas_disponiveis", dimension="procedimento", top_n=5),
         "top 5 procedimentos por vagas")
    show(P.breakdown(df, metric="vagas_disponiveis", dimension="hospital", top_n=5),
         "top 5 hospitais por vagas")
    show(P.mix_tipo_vaga(df, base="ativas"), "mix tipo de vaga (ativas)")
    show(P.timeseries(df, metric="vagas_disponiveis"), "serie temporal vagas")

    # resolver + filtro
    proc = R.resolve_procedimento("ressonancia magnetica", df)
    print(f"\nresolver procedimento 'ressonancia magnetica' -> {proc.valor[:50]}")
    show(P.timeseries(df, metric="vagas_disponiveis", filters={"procedimento": proc.valor}),
         "serie temporal — ressonancia")

    hosp = R.resolve_hospital("universitario", df)
    print(f"\nresolver hospital 'universitario' -> {hosp.nome} (CNES {hosp.cnes})")
    show(P.taxa_bloqueio(df, filters={"hospital": hosp.nome}), "taxa_bloqueio no HUB")

    show(P.compare(df, metric="vagas_disponiveis", dimension="hospital", focus_value=hosp.nome, top_n=5),
         "compare HUB vs benchmark hospitais")

    print("\nOK — Fase 2 (catalogo + resolver + primitivas -> Envelope) funcionando.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
