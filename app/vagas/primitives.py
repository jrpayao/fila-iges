"""Primitivas do motor de vagas — agregam sobre o DataFrame e devolvem Envelope (P4).

Substituem as primitivas ES. Semantica: tudo `snapshot` por competencia. Todo
numero nasce de uma agregacao pandas rastreavel (P1); o Envelope e a fonte unica (P4).
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from app.agent.envelope import Envelope, MetricKind, Shape, Window
from app.vagas import catalog
from app.vagas.resolver import ResolvedCompetencia, latest_competencia

SOURCE = "iges:dados_vagas_sisreg"


# ===== Preparo comum =====


def _apply_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    """Filtra por valores canonicos (procedimento/hospital). Competencia e a parte."""
    out = df
    if filters.get("procedimento"):
        out = out[out["procedimento"] == filters["procedimento"]]
    if filters.get("hospital"):
        out = out[out["hospital"] == filters["hospital"]]
    return out


def _select_competencia(
    df: pd.DataFrame, competencia: Optional[ResolvedCompetencia]
) -> tuple[pd.DataFrame, ResolvedCompetencia]:
    comp = competencia or latest_competencia(df)
    return df[df["competencia"] == comp.key], comp


def _window(comp: ResolvedCompetencia) -> Window:
    return Window(gte=None, lte=None, label=f"competencia {comp.label}")


def _filters_meta(filters: dict[str, Any], comp: ResolvedCompetencia) -> dict[str, Any]:
    meta = {k: v for k, v in filters.items() if v}
    meta["competencia"] = comp.label
    return meta


# ===== Primitivas =====


def total(
    df: pd.DataFrame,
    *,
    metric: str,
    filters: dict[str, Any] | None = None,
    competencia: Optional[ResolvedCompetencia] = None,
    request_id: str | None = None,
) -> Envelope:
    """Soma escalar de uma medida na competencia."""
    filters = filters or {}
    fdf = _apply_filters(df, filters)
    fdf, comp = _select_competencia(fdf, competencia)
    value = int(catalog.measure_series(fdf, metric).sum())
    mdef = catalog.get(metric) if metric in catalog.CATALOG else None
    return Envelope.scalar(
        metric=metric,
        metric_kind=MetricKind.SNAPSHOT,
        value=value,
        units=mdef.default_unit if mdef else "vagas",
        source_index=SOURCE,
        window=_window(comp),
        filters=_filters_meta(filters, comp),
        total_documents=int(len(fdf)),
        request_id=request_id,
    )


def taxa_bloqueio(
    df: pd.DataFrame,
    *,
    filters: dict[str, Any] | None = None,
    competencia: Optional[ResolvedCompetencia] = None,
    request_id: str | None = None,
) -> Envelope:
    """Percentual da capacidade que esta bloqueada (derivada)."""
    filters = filters or {}
    fdf = _apply_filters(df, filters)
    fdf, comp = _select_competencia(fdf, competencia)
    ativ = int(catalog.measure_series(fdf, "vagas_ativas").sum())
    bloq = int(catalog.measure_series(fdf, "vagas_bloqueadas").sum())
    denom = ativ + bloq
    pct = round(bloq / denom * 100, 2) if denom else 0.0
    return Envelope.scalar(
        metric="taxa_bloqueio",
        metric_kind=MetricKind.DERIVED,
        value=pct,
        units="%",
        source_index=SOURCE,
        window=_window(comp),
        filters=_filters_meta(filters, comp),
        method_note=(
            f"taxa_bloqueio = bloqueadas({bloq}) / (ativas({ativ}) + bloqueadas({bloq})) * 100."
        ),
        total_documents=denom,
        request_id=request_id,
    )


def breakdown(
    df: pd.DataFrame,
    *,
    metric: str,
    dimension: str,
    filters: dict[str, Any] | None = None,
    competencia: Optional[ResolvedCompetencia] = None,
    top_n: int = 10,
    request_id: str | None = None,
) -> Envelope:
    """Top-N por dimensao (procedimento/hospital), somando a medida."""
    if dimension not in catalog.DIMENSIONS:
        raise ValueError(f"Dimensao '{dimension}' fora do catalogo (P9): {sorted(catalog.DIMENSIONS)}")
    filters = filters or {}
    fdf = _apply_filters(df, filters)
    fdf, comp = _select_competencia(fdf, competencia)
    col = catalog.DIMENSIONS[dimension]

    work = fdf.copy()
    work["_m"] = catalog.measure_series(work, metric)
    grouped = work.groupby(col)["_m"].sum().sort_values(ascending=False)
    buckets = [{"key": str(k), "value": int(v)} for k, v in grouped.head(top_n).items()]
    mdef = catalog.get(metric) if metric in catalog.CATALOG else None
    return Envelope.breakdown(
        metric=metric,
        metric_kind=MetricKind.SNAPSHOT,
        dimension=dimension,
        buckets=buckets,
        units=mdef.default_unit if mdef else "vagas",
        source_index=SOURCE,
        window=_window(comp),
        filters=_filters_meta(filters, comp),
        total_documents=int(grouped.shape[0]),
        request_id=request_id,
    )


def mix_tipo_vaga(
    df: pd.DataFrame,
    *,
    base: str = "ativas",
    filters: dict[str, Any] | None = None,
    competencia: Optional[ResolvedCompetencia] = None,
    request_id: str | None = None,
) -> Envelope:
    """Distribuicao por tipo de vaga (1a vez / retorno / reserva)."""
    comps = catalog.MIX_COMPONENTS.get(base)
    if comps is None:
        raise ValueError(f"base='{base}' invalida; use 'ativas' ou 'bloqueadas'.")
    filters = filters or {}
    fdf = _apply_filters(df, filters)
    fdf, comp = _select_competencia(fdf, competencia)
    buckets = [
        {"key": tipo, "value": int(fdf[col].fillna(0).sum())}
        for tipo, col in comps.items()
    ]
    buckets.sort(key=lambda b: b["value"], reverse=True)
    return Envelope.breakdown(
        metric="mix_tipo_vaga",
        metric_kind=MetricKind.SNAPSHOT,
        dimension="tipo_vaga",
        buckets=buckets,
        units="vagas",
        source_index=SOURCE,
        window=_window(comp),
        filters={**_filters_meta(filters, comp), "base": base},
        total_documents=sum(b["value"] for b in buckets),
        request_id=request_id,
    )


def timeseries(
    df: pd.DataFrame,
    *,
    metric: str,
    filters: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> Envelope:
    """Serie temporal da medida por competencia (todas as competencias do cache)."""
    filters = filters or {}
    fdf = _apply_filters(df, filters)
    work = fdf.copy()
    work["_m"] = catalog.measure_series(work, metric)
    serie = work.groupby("competencia")["_m"].sum().sort_index()
    points = [
        {"key": f"{int(k) % 100:02d}/{int(k) // 100}", "competencia": int(k), "value": int(v)}
        for k, v in serie.items()
    ]
    mdef = catalog.get(metric) if metric in catalog.CATALOG else None
    comps = [ResolvedCompetencia(mes=int(k) % 100, ano=int(k) // 100) for k in serie.index]
    label = (
        f"competencias {comps[0].label}..{comps[-1].label}" if comps else "sem competencias"
    )
    return Envelope.timeseries(
        metric=metric,
        metric_kind=MetricKind.SNAPSHOT,
        points=points,
        units=mdef.default_unit if mdef else "vagas",
        source_index=SOURCE,
        window=Window(gte=None, lte=None, label=label),
        filters={k: v for k, v in filters.items() if v},
        total_documents=len(points),
        request_id=request_id,
    )


def compare(
    df: pd.DataFrame,
    *,
    metric: str,
    dimension: str,
    focus_value: str,
    filters: dict[str, Any] | None = None,
    competencia: Optional[ResolvedCompetencia] = None,
    top_n: int = 5,
    request_id: str | None = None,
) -> Envelope:
    """Entidade em destaque vs benchmark (top-N da dimensao) na competencia."""
    if dimension not in catalog.DIMENSIONS:
        raise ValueError(f"Dimensao '{dimension}' fora do catalogo (P9): {sorted(catalog.DIMENSIONS)}")
    filters = filters or {}
    fdf = _apply_filters(df, filters)
    fdf, comp = _select_competencia(fdf, competencia)
    col = catalog.DIMENSIONS[dimension]
    work = fdf.copy()
    work["_m"] = catalog.measure_series(work, metric)
    grouped = work.groupby(col)["_m"].sum().sort_values(ascending=False)

    focus_val = int(grouped.get(focus_value, 0))
    benchmark = [
        {"key": str(k), "value": int(v)}
        for k, v in grouped.head(top_n).items()
        if str(k) != str(focus_value)
    ]
    mdef = catalog.get(metric) if metric in catalog.CATALOG else None
    return Envelope.comparison(
        metric=metric,
        metric_kind=MetricKind.SNAPSHOT,
        dimension=dimension,
        focus={"key": str(focus_value), "value": focus_val},
        benchmark=benchmark,
        units=mdef.default_unit if mdef else "vagas",
        source_index=SOURCE,
        window=_window(comp),
        filters=_filters_meta(filters, comp),
        total_documents=int(grouped.sum()),
        request_id=request_id,
    )
