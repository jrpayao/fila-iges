"""Catalogo semantico do motor de vagas (P9 — vocabulario fechado).

Reancorado no schema da API de vagas (Emenda constitucional v3.0). Tudo `snapshot`
(a fonte e capacidade num instante por competencia). Nao executa nada — descreve.

- MEASURES: nome -> como calcular a medida (Series por linha, somavel).
- DIMENSIONS: nome -> coluna de group-by no DataFrame.
- METRICS: metadados (descricao/unidade/forma) para o planejador (Fase 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from app.agent.envelope import MetricKind, Shape

# ===== Medidas — Series por linha (somavel apos filtro/groupby) =====

MEASURES: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
    "vagas_disponiveis": lambda df: df["vagas_disponiveis"].fillna(0),
    "vagas_ativas": lambda df: (
        df["ativ_1"].fillna(0) + df["ativ_retorno"].fillna(0) + df["ativ_reserva"].fillna(0)
    ),
    "vagas_bloqueadas": lambda df: (
        df["bloq_1"].fillna(0) + df["bloq_retorno"].fillna(0) + df["bloq_reserva"].fillna(0)
    ),
}

# Componentes do mix por tipo de vaga (1a vez / retorno / reserva).
MIX_COMPONENTS: dict[str, dict[str, str]] = {
    "ativas": {"primeira_vez": "ativ_1", "retorno": "ativ_retorno", "reserva": "ativ_reserva"},
    "bloqueadas": {"primeira_vez": "bloq_1", "retorno": "bloq_retorno", "reserva": "bloq_reserva"},
}

# ===== Dimensoes — coluna de group-by =====

DIMENSIONS: dict[str, str] = {
    "procedimento": "procedimento",
    "hospital": "hospital",
    "competencia": "competencia",
}

# ===== Metadados de metrica (para o planejador) =====


@dataclass(frozen=True)
class MetricDef:
    name: str
    description: str
    default_unit: str
    default_shape: Shape
    kind: MetricKind = MetricKind.SNAPSHOT
    measure: str | None = None  # chave em MEASURES (None para derivadas/especiais)
    depends_on: tuple[str, ...] = ()
    method_note: str | None = None


CATALOG: dict[str, MetricDef] = {
    "vagas_disponiveis": MetricDef(
        name="vagas_disponiveis",
        description="Total de vagas SISREG disponiveis (oferta) na competencia",
        default_unit="vagas",
        default_shape=Shape.SCALAR,
        measure="vagas_disponiveis",
    ),
    "vagas_ativas": MetricDef(
        name="vagas_ativas",
        description="Vagas ativas (1a vez + retorno + reserva) — capacidade utilizavel",
        default_unit="vagas",
        default_shape=Shape.SCALAR,
        measure="vagas_ativas",
    ),
    "vagas_bloqueadas": MetricDef(
        name="vagas_bloqueadas",
        description="Vagas bloqueadas (1a vez + retorno + reserva) — capacidade travada",
        default_unit="vagas",
        default_shape=Shape.SCALAR,
        measure="vagas_bloqueadas",
    ),
    "taxa_bloqueio": MetricDef(
        name="taxa_bloqueio",
        description="Percentual da capacidade que esta bloqueada = bloqueadas / (ativas + bloqueadas)",
        default_unit="%",
        default_shape=Shape.SCALAR,
        kind=MetricKind.DERIVED,
        depends_on=("vagas_bloqueadas", "vagas_ativas"),
        method_note="taxa_bloqueio = vagas_bloqueadas / (vagas_ativas + vagas_bloqueadas) * 100.",
    ),
    "mix_tipo_vaga": MetricDef(
        name="mix_tipo_vaga",
        description="Distribuicao das vagas ativas por tipo (1a vez / retorno / reserva)",
        default_unit="vagas",
        default_shape=Shape.BREAKDOWN,
        measure="vagas_ativas",
    ),
}

# Nomes exportados para validacao do planejador (P9).
METRIC_NAMES: frozenset[str] = frozenset(CATALOG)
DIMENSION_NAMES: frozenset[str] = frozenset(DIMENSIONS)
MEASURE_NAMES: frozenset[str] = frozenset(MEASURES)


def measure_series(df: pd.DataFrame, metric_or_measure: str) -> pd.Series:
    """Series da medida por linha. Aceita nome de metrica (via CATALOG) ou de medida."""
    key = metric_or_measure
    if key in CATALOG and CATALOG[key].measure:
        key = CATALOG[key].measure  # type: ignore[assignment]
    if key not in MEASURES:
        raise KeyError(f"Medida '{metric_or_measure}' nao existe (P9). Medidas: {sorted(MEASURES)}")
    return MEASURES[key](df)


def get(name: str) -> MetricDef:
    if name not in CATALOG:
        raise KeyError(f"Metrica '{name}' fora do catalogo (P9). Disponiveis: {sorted(CATALOG)}")
    return CATALOG[name]
