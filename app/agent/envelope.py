"""Envelope tipado — Princípio P4 da constituição v2.

Fonte única de número para prosa, gráfico e export. Nenhum desses 3 artefatos
recalcula a partir de dados crus; todos consomem o Envelope.

Spec: §8 (Contrato de Saída — o Envelope).
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class Shape(str, Enum):
    """Forma do dado dentro do envelope. Define como o gráfico/export renderiza."""

    SCALAR = "scalar"          # 1 número (ex.: estoque atual = 395.555)
    TIMESERIES = "timeseries"  # série temporal (date_histogram)
    BREAKDOWN = "breakdown"    # buckets por dimensão (top-N CIDs, por unidade)
    COMPARISON = "comparison"  # entidade em destaque vs benchmark
    DISTRIBUTION = "distribution"  # estatísticas (mediana/p90/min/max)


class Unit(str, Enum):
    """Unidade do valor numérico."""

    DOCUMENTOS = "documentos"
    PERCENT = "%"
    DIAS = "dias"
    HORAS = "horas"


class MetricKind(str, Enum):
    """Estoque vs fluxo (Princípio P5 — nunca somar)."""

    SNAPSHOT = "snapshot"  # fila viva no momento (sem range temporal)
    FLOW = "flow"          # eventos num período (entrada, atendimento, falta)
    DERIVED = "derived"    # taxa, lead_time etc — calculado a partir de outros


class Window(BaseModel):
    """Janela temporal aplicada ao Envelope."""

    gte: date | None = Field(None, description="Data inicial. None = snapshot.")
    lte: date | None = Field(None, description="Data final. None = aberta.")
    label: str = Field(..., description="Rotulo legivel: 'ultimos 30 dias', 'snapshot', 'maio/2026'.")


class Envelope(BaseModel):
    """Resultado tipado de uma execucao do agente. Princípio P4.

    Toda saida do orquestrador respeita este contrato. Prosa, grafico e export
    leem este Envelope - nunca recalculam.
    """

    shape: Shape = Field(..., description="Forma do dado em `data`.")
    metric: str = Field(..., description="Nome da metrica do catalogo (P9).")
    metric_kind: MetricKind = Field(..., description="snapshot | flow | derived (P5).")
    dimension: str | None = Field(None, description="Dimensao do breakdown (cid, unidade, etc). null em scalar.")
    filters: dict[str, Any] = Field(default_factory=dict, description="Filtros aplicados na query.")
    window: Window = Field(..., description="Janela temporal.")
    data: list[dict[str, Any]] = Field(default_factory=list, description="Pontos de dado. Schema varia por `shape`.")
    units: Unit | str = Field(..., description="Unidade do valor.")
    method_note: str | None = Field(
        None,
        description=(
            "Anotacao do metodo (P3). OBRIGATORIA para metric_kind=derived "
            "envolvendo projecao (ex.: previsao_atendimento)."
        ),
    )
    source_index: str = Field(..., description="Indice ES de origem. Pode ser 'multi' se cross-index reconciliado.")
    doc_count_error: int = Field(0, ge=0, description="doc_count_error_upper_bound do terms agg.")
    total_documents: int | None = Field(None, ge=0, description="Total de docs no universo filtrado.")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    poc: bool = Field(True, description="Banner POC. False quando em modo producao.")
    request_id: str | None = Field(None, description="Correlacao com audit log.")
    sub_envelopes: Optional[list[dict[str, Any]]] = Field(
        None,
        description=(
            "Composition=diagnostic: lista de sub-envelopes (cada um eh um dict de model_dump). "
            "Synthesizer le essa lista pra construir prosa prescritiva."
        ),
    )

    @model_validator(mode="after")
    def _projection_requires_method_note(self) -> "Envelope":
        """Princípio P3: projecao exige method_note explicita."""
        if self.metric == "previsao_atendimento" and not self.method_note:
            raise ValueError(
                "Envelope com metric='previsao_atendimento' exige method_note explicita (Principio P3)."
            )
        return self

    @model_validator(mode="after")
    def _scalar_has_one_datapoint(self) -> "Envelope":
        if self.shape == Shape.SCALAR and len(self.data) != 1:
            raise ValueError(f"Envelope shape=scalar deve ter exatamente 1 datapoint, recebido {len(self.data)}.")
        return self

    # ----- Construtores de conveniencia -----

    @classmethod
    def scalar(
        cls,
        *,
        metric: str,
        metric_kind: MetricKind,
        value: float,
        units: Unit | str,
        source_index: str,
        window: Window,
        filters: dict[str, Any] | None = None,
        method_note: str | None = None,
        total_documents: int | None = None,
        request_id: str | None = None,
    ) -> "Envelope":
        return cls(
            shape=Shape.SCALAR,
            metric=metric,
            metric_kind=metric_kind,
            data=[{"value": value}],
            units=units,
            source_index=source_index,
            window=window,
            filters=filters or {},
            method_note=method_note,
            total_documents=total_documents,
            request_id=request_id,
        )

    @classmethod
    def breakdown(
        cls,
        *,
        metric: str,
        metric_kind: MetricKind,
        dimension: str,
        buckets: list[dict[str, Any]],
        units: Unit | str,
        source_index: str,
        window: Window,
        filters: dict[str, Any] | None = None,
        method_note: str | None = None,
        doc_count_error: int = 0,
        total_documents: int | None = None,
        request_id: str | None = None,
    ) -> "Envelope":
        return cls(
            shape=Shape.BREAKDOWN,
            metric=metric,
            metric_kind=metric_kind,
            dimension=dimension,
            data=buckets,
            units=units,
            source_index=source_index,
            window=window,
            filters=filters or {},
            method_note=method_note,
            doc_count_error=doc_count_error,
            total_documents=total_documents,
            request_id=request_id,
        )

    @classmethod
    def timeseries(
        cls,
        *,
        metric: str,
        metric_kind: MetricKind,
        points: list[dict[str, Any]],
        units: Unit | str,
        source_index: str,
        window: Window,
        filters: dict[str, Any] | None = None,
        method_note: str | None = None,
        total_documents: int | None = None,
        request_id: str | None = None,
    ) -> "Envelope":
        return cls(
            shape=Shape.TIMESERIES,
            metric=metric,
            metric_kind=metric_kind,
            data=points,
            units=units,
            source_index=source_index,
            window=window,
            filters=filters or {},
            method_note=method_note,
            total_documents=total_documents,
            request_id=request_id,
        )

    @classmethod
    def distribution(
        cls,
        *,
        metric: str,
        metric_kind: MetricKind,
        stats: dict[str, float],
        units: Unit | str,
        source_index: str,
        window: Window,
        filters: dict[str, Any] | None = None,
        method_note: str | None = None,
        total_documents: int | None = None,
        request_id: str | None = None,
    ) -> "Envelope":
        """Distribuicao tipica: stats = {min, max, avg, p50, p90, p99}."""
        return cls(
            shape=Shape.DISTRIBUTION,
            metric=metric,
            metric_kind=metric_kind,
            data=[stats],
            units=units,
            source_index=source_index,
            window=window,
            filters=filters or {},
            method_note=method_note,
            total_documents=total_documents,
            request_id=request_id,
        )

    @classmethod
    def comparison(
        cls,
        *,
        metric: str,
        metric_kind: MetricKind,
        dimension: str,
        focus: dict[str, Any],
        benchmark: list[dict[str, Any]],
        units: Unit | str,
        source_index: str,
        window: Window,
        filters: dict[str, Any] | None = None,
        method_note: str | None = None,
        total_documents: int | None = None,
        request_id: str | None = None,
    ) -> "Envelope":
        """Comparison: focus = entidade destaque, benchmark = pontos de referencia."""
        return cls(
            shape=Shape.COMPARISON,
            metric=metric,
            metric_kind=metric_kind,
            dimension=dimension,
            data=[{"focus": focus, "benchmark": benchmark}],
            units=units,
            source_index=source_index,
            window=window,
            filters=filters or {},
            method_note=method_note,
            total_documents=total_documents,
            request_id=request_id,
        )
