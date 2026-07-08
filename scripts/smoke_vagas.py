"""Smoke da Fase 1 — fonte v3 (API de vagas SISREG/IGES).

Prova ponta-a-ponta: client -> store (cache SQLite) -> DataFrame tipado -> agregacoes.
Baixa de jan/2025 ate a competencia corrente (pula meses sem dado).

Rodar da raiz do projeto (le .env):
    $py scripts/smoke_vagas.py
"""

from __future__ import annotations

import sys
from datetime import date

from app.vagas.store import VagasStore


def main() -> int:
    store = VagasStore()

    start = (1, 2025)
    end = (date.today().month, date.today().year)
    print(f"Sincronizando competencias {start[0]:02d}/{start[1]} -> {end[0]:02d}/{end[1]} ...")
    summary = store.sync_range(start, end)
    print(f"  -> synced={summary['synced']} competencias | "
          f"records={summary['records']} | vazias(puladas)={summary['skipped']}")

    df = store.load_df()
    if df.empty:
        print("!! DataFrame vazio — nada baixado."); return 1

    print(f"\nDataFrame: {len(df)} linhas x {df.shape[1]} colunas")
    comps = sorted(df["competencia"].unique())
    print(f"competencias no cache: {len(comps)} -> {comps[0]} .. {comps[-1]}")
    print(f"hospitais distintos: {df['hospital_cnes'].nunique()} | "
          f"procedimentos distintos: {df['cod_procedimento'].nunique()}")
    print(f"extracao min/max: {df['data_extracao'].min()} .. {df['data_extracao'].max()}")

    # Agregacao 1: capacidade da competencia mais recente
    ult = df[df["competencia"] == comps[-1]]
    print(f"\n[competencia {comps[-1]}] soma vagas_disponiveis = {int(ult['vagas_disponiveis'].sum())}")
    print("top 5 procedimentos por vagas:")
    top = (ult.groupby("procedimento")["vagas_disponiveis"].sum()
              .sort_values(ascending=False).head(5))
    for nome, v in top.items():
        print(f"  {int(v):>6}  {nome[:60]}")

    # Agregacao 2: bloqueadas vs ativas (prova as colunas bloq_/ativ_)
    bloq = int(ult[["bloq_1", "bloq_retorno", "bloq_reserva"]].sum().sum())
    ativ = int(ult[["ativ_1", "ativ_retorno", "ativ_reserva"]].sum().sum())
    print(f"\n[competencia {comps[-1]}] vagas ativas={ativ} | bloqueadas={bloq}")

    # Agregacao 3: serie temporal da oferta total por competencia
    print("\nserie temporal (soma vagas por competencia):")
    serie = df.groupby("competencia")["vagas_disponiveis"].sum().sort_index()
    for comp, v in serie.items():
        print(f"  {comp}: {int(v)}")

    print("\nOK — pipeline client->store->DataFrame->agregacao funcionando.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
