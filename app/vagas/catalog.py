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
    "especialidade": "especialidade",
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
    # --- derivadas do Pacote Wow (so com os campos existentes) ---
    "indice_porta_entrada": MetricDef(
        name="indice_porta_entrada",
        description="% das vagas ativas que sao de 1a vez (acesso de paciente novo) = ativ_1 / vagas_ativas",
        default_unit="%",
        default_shape=Shape.SCALAR,
        kind=MetricKind.DERIVED,
        depends_on=("vagas_ativas",),
        method_note="indice_porta_entrada = ativ_1 / vagas_ativas * 100. Baixo = rede fechada a paciente novo.",
    ),
    "taxa_reserva": MetricDef(
        name="taxa_reserva",
        description="% das vagas ativas em 'reserva' (nao circulam pela regulacao aberta) = ativ_reserva / vagas_ativas",
        default_unit="%",
        default_shape=Shape.SCALAR,
        kind=MetricKind.DERIVED,
        depends_on=("vagas_ativas",),
        method_note="taxa_reserva = ativ_reserva / vagas_ativas * 100.",
    ),
    "cobertura_rede": MetricDef(
        name="cobertura_rede",
        description="Numero de hospitais que ofertam cada procedimento (resiliencia da rede)",
        default_unit="hospitais",
        default_shape=Shape.BREAKDOWN,
        method_note="Contagem de hospitais distintos com vagas_disponiveis > 0 por procedimento.",
    ),
    "vagas_perdidas_ytd": MetricDef(
        name="vagas_perdidas_ytd",
        description="Soma de vagas bloqueadas de janeiro ate a competencia (custo acumulado do bloqueio no ano)",
        default_unit="vagas-mes",
        default_shape=Shape.SCALAR,
        kind=MetricKind.DERIVED,
        method_note="Soma de vagas_bloqueadas de jan/AAAA ate a competencia informada.",
    ),
    "oportunidade_desbloqueio": MetricDef(
        name="oportunidade_desbloqueio",
        description="Pares hospital x procedimento com mais vagas bloqueadas — onde desbloquear rende mais",
        default_unit="vagas",
        default_shape=Shape.BREAKDOWN,
        method_note="Top-N pares (hospital, procedimento) por vagas_bloqueadas, com meses de persistencia.",
    ),
    # --- 2a onda ---
    "simular_desbloqueio": MetricDef(
        name="simular_desbloqueio",
        description="What-if: quantas vagas seriam liberadas ao reduzir a taxa de bloqueio a uma meta",
        default_unit="vagas",
        default_shape=Shape.SCALAR,
        kind=MetricKind.DERIVED,
        method_note="freed = bloqueadas - meta% * capacidade. Estimativa de gestao da oferta.",
    ),
    "anomalias": MetricDef(
        name="anomalias",
        description="Maiores quedas de oferta (e procedimentos/hospitais que zeraram) vs o mes anterior",
        default_unit="vagas perdidas",
        default_shape=Shape.BREAKDOWN,
        method_note="Ranking das maiores quedas de vagas_disponiveis por dimensao vs competencia anterior.",
    ),
    "raio_x_unidade": MetricDef(
        name="raio_x_unidade",
        description="Ficha de uma unidade: oferta, bloqueio (vs rede), porta de entrada, volatilidade, top procedimentos",
        default_unit="vagas",
        default_shape=Shape.BREAKDOWN,
        method_note="Diagnostico de um hospital com contexto de rede (medianas) e volatilidade.",
    ),
    # --- 3a onda ---
    "concentracao": MetricDef(
        name="concentracao",
        description="Indice HHI de concentracao da oferta (dependencia de poucos executantes)",
        default_unit="HHI",
        default_shape=Shape.BREAKDOWN,
        kind=MetricKind.DERIVED,
        method_note="HHI = soma dos quadrados das participacoes dos hospitais. >0,25 = concentrado.",
    ),
    "projecao_oferta": MetricDef(
        name="projecao_oferta",
        description="Projecao transparente da oferta para a proxima competencia (estimativa, nao previsao)",
        default_unit="vagas",
        default_shape=Shape.SCALAR,
        kind=MetricKind.DERIVED,
        method_note="Ultimo valor + tendencia media dos ultimos 3 meses. Rotulada como estimativa (P3).",
    ),
    "comparar_hospitais": MetricDef(
        name="comparar_hospitais",
        description="Head-to-head de dois hospitais (vagas, bloqueio, porta de entrada)",
        default_unit="vagas",
        default_shape=Shape.BREAKDOWN,
        method_note="Compara hospital_a vs hospital_b nas metricas-chave da competencia.",
    ),
    "plano_acao": MetricDef(
        name="plano_acao",
        description="Plano de acao priorizado: desbloqueio + monofornecedores + anomalias",
        default_unit="vagas",
        default_shape=Shape.BREAKDOWN,
        method_note="Sintese prescritiva de gestao da oferta a partir de 3 diagnosticos.",
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
