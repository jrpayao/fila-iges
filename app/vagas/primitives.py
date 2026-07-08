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


def _prev_comp(df: pd.DataFrame, comp: ResolvedCompetencia) -> Optional[ResolvedCompetencia]:
    """Competencia imediatamente anterior a `comp` presente no dado."""
    keys = sorted({int(k) for k in df["competencia"].dropna().unique() if int(k) < comp.key})
    if not keys:
        return None
    k = keys[-1]
    return ResolvedCompetencia(mes=k % 100, ano=k // 100)


def _delta_fields(base_all: pd.DataFrame, value_fn, prev: Optional[ResolvedCompetencia], value: float) -> dict[str, Any]:
    """Compara `value` (comp atual) com a mesma medida na competencia anterior."""
    if prev is None:
        return {}
    prev_df = base_all[base_all["competencia"] == prev.key]
    if prev_df.empty:
        return {}
    pv = value_fn(prev_df)
    out: dict[str, Any] = {"prev_value": pv, "prev_competencia": prev.label, "delta_abs": round(value - pv, 2)}
    if pv:
        out["delta_pct"] = round((value - pv) / pv * 100, 1)
    return out


def _fmt_valor(value: float, units: str) -> str:
    """Rotulo pt-BR inequivoco do numero (evita 0,58% ser narrado como 58%)."""
    if units == "%":
        return f"{value:.2f}".replace(".", ",") + "%"
    return f"{int(round(value)):,}".replace(",", ".") + (f" {units}" if units and units != "vagas" else "")


def _scalar_env(*, metric, kind, value, units, window, filters_meta, method_note=None,
                total_documents=None, request_id=None, extra=None) -> Envelope:
    data: dict[str, Any] = {"value": value, "value_label": _fmt_valor(value, str(units))}
    if extra:
        data.update(extra)
    return Envelope(
        shape=Shape.SCALAR, metric=metric, metric_kind=kind, data=[data], units=units,
        source_index=SOURCE, window=window, filters=filters_meta, method_note=method_note,
        total_documents=total_documents, request_id=request_id,
    )


# ===== Primitivas =====


def total(
    df: pd.DataFrame,
    *,
    metric: str,
    filters: dict[str, Any] | None = None,
    competencia: Optional[ResolvedCompetencia] = None,
    request_id: str | None = None,
) -> Envelope:
    """Soma escalar de uma medida na competencia, com delta vs competencia anterior (A)."""
    filters = filters or {}
    base = _apply_filters(df, filters)
    fdf, comp = _select_competencia(base, competencia)

    def vfn(d: pd.DataFrame) -> int:
        return int(catalog.measure_series(d, metric).sum())

    value = vfn(fdf)
    extra = _delta_fields(base, vfn, _prev_comp(df, comp), value)
    mdef = catalog.get(metric) if metric in catalog.CATALOG else None
    return _scalar_env(
        metric=metric, kind=MetricKind.SNAPSHOT, value=value,
        units=mdef.default_unit if mdef else "vagas",
        window=_window(comp), filters_meta=_filters_meta(filters, comp),
        total_documents=int(len(fdf)), request_id=request_id, extra=extra,
    )


def taxa_bloqueio(
    df: pd.DataFrame,
    *,
    filters: dict[str, Any] | None = None,
    competencia: Optional[ResolvedCompetencia] = None,
    request_id: str | None = None,
) -> Envelope:
    """Percentual da capacidade que esta bloqueada (derivada), com delta (A)."""
    filters = filters or {}
    base = _apply_filters(df, filters)
    fdf, comp = _select_competencia(base, competencia)

    def vfn(d: pd.DataFrame) -> float:
        a = int(catalog.measure_series(d, "vagas_ativas").sum())
        b = int(catalog.measure_series(d, "vagas_bloqueadas").sum())
        return round(b / (a + b) * 100, 2) if (a + b) else 0.0

    ativ = int(catalog.measure_series(fdf, "vagas_ativas").sum())
    bloq = int(catalog.measure_series(fdf, "vagas_bloqueadas").sum())
    pct = vfn(fdf)
    extra = _delta_fields(base, vfn, _prev_comp(df, comp), pct)
    return _scalar_env(
        metric="taxa_bloqueio", kind=MetricKind.DERIVED, value=pct, units="%",
        window=_window(comp), filters_meta=_filters_meta(filters, comp),
        method_note=f"taxa_bloqueio = bloqueadas({bloq}) / (ativas({ativ}) + bloqueadas({bloq})) * 100.",
        total_documents=ativ + bloq, request_id=request_id, extra=extra,
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


# ===== Pacote Wow — metricas derivadas e capacidades estrategicas =====


def indice_porta_entrada(df, *, filters=None, competencia=None, request_id=None) -> Envelope:
    """C — % das vagas ativas que sao de 1a vez (acesso de paciente novo)."""
    filters = filters or {}
    base = _apply_filters(df, filters)
    fdf, comp = _select_competencia(base, competencia)

    def vfn(d: pd.DataFrame) -> float:
        a = int(catalog.measure_series(d, "vagas_ativas").sum())
        p = int(d["ativ_1"].fillna(0).sum())
        return round(p / a * 100, 2) if a else 0.0

    val = vfn(fdf)
    p = int(fdf["ativ_1"].fillna(0).sum())
    a = int(catalog.measure_series(fdf, "vagas_ativas").sum())
    extra = _delta_fields(base, vfn, _prev_comp(df, comp), val)
    return _scalar_env(
        metric="indice_porta_entrada", kind=MetricKind.DERIVED, value=val, units="%",
        window=_window(comp), filters_meta=_filters_meta(filters, comp),
        method_note=f"indice_porta_entrada = ativ_1({p}) / vagas_ativas({a}) * 100.",
        total_documents=a, request_id=request_id, extra=extra,
    )


def taxa_reserva(df, *, filters=None, competencia=None, request_id=None) -> Envelope:
    """C — % das vagas ativas em 'reserva' (nao circulam pela regulacao aberta)."""
    filters = filters or {}
    base = _apply_filters(df, filters)
    fdf, comp = _select_competencia(base, competencia)

    def vfn(d: pd.DataFrame) -> float:
        a = int(catalog.measure_series(d, "vagas_ativas").sum())
        r = int(d["ativ_reserva"].fillna(0).sum())
        return round(r / a * 100, 2) if a else 0.0

    val = vfn(fdf)
    r = int(fdf["ativ_reserva"].fillna(0).sum())
    a = int(catalog.measure_series(fdf, "vagas_ativas").sum())
    extra = _delta_fields(base, vfn, _prev_comp(df, comp), val)
    return _scalar_env(
        metric="taxa_reserva", kind=MetricKind.DERIVED, value=val, units="%",
        window=_window(comp), filters_meta=_filters_meta(filters, comp),
        method_note=f"taxa_reserva = ativ_reserva({r}) / vagas_ativas({a}) * 100.",
        total_documents=a, request_id=request_id, extra=extra,
    )


def vagas_perdidas_ytd(df, *, filters=None, competencia=None, request_id=None) -> Envelope:
    """C — soma de vagas bloqueadas de jan ate a competencia (custo acumulado)."""
    filters = filters or {}
    base = _apply_filters(df, filters)
    _, comp = _select_competencia(base, competencia)
    ini = comp.ano * 100 + 1
    janela = base[(base["competencia"] >= ini) & (base["competencia"] <= comp.key)]
    val = int(catalog.measure_series(janela, "vagas_bloqueadas").sum())
    win = Window(gte=None, lte=None, label=f"jan..{comp.label} (acumulado no ano)")
    meta = {k: v for k, v in filters.items() if v}
    meta["competencia_ate"] = comp.label
    return _scalar_env(
        metric="vagas_perdidas_ytd", kind=MetricKind.DERIVED, value=val, units="vagas-mes",
        window=win, filters_meta=meta,
        method_note=f"Soma de vagas_bloqueadas de {comp.ano}-01 ate {comp.label}.",
        total_documents=val, request_id=request_id,
    )


def cobertura_rede(df, *, filters=None, competencia=None, top_n=15, max_hospitais=None, request_id=None) -> Envelope:
    """D/C — nº de hospitais que ofertam cada procedimento (ordem crescente = mais fragil)."""
    filters = filters or {}
    base = _apply_filters(df, filters)
    fdf, comp = _select_competencia(base, competencia)
    disp = fdf[fdf["vagas_disponiveis"].fillna(0) > 0]
    cov = disp.groupby("procedimento")["hospital_cnes"].nunique().sort_values()
    if max_hospitais is not None:
        cov = cov[cov <= max_hospitais]
    buckets = [{"key": str(k), "value": int(v)} for k, v in cov.head(top_n).items()]
    metric = "monofornecedores" if max_hospitais is not None else "cobertura_rede"
    return Envelope.breakdown(
        metric=metric, metric_kind=MetricKind.SNAPSHOT, dimension="procedimento",
        buckets=buckets, units="hospitais", source_index=SOURCE, window=_window(comp),
        filters=_filters_meta(filters, comp), total_documents=int(cov.shape[0]), request_id=request_id,
    )


def _persistencia_bloqueio(base: pd.DataFrame, hosp: str, proc: str, comp: ResolvedCompetencia) -> int:
    """Meses consecutivos (ate comp) com bloqueio > 0 para o par hospital x procedimento."""
    sub = base[(base["hospital"] == hosp) & (base["procedimento"] == proc)]
    if sub.empty:
        return 0
    by = sub.groupby("competencia").apply(
        lambda d: int(catalog.measure_series(d, "vagas_bloqueadas").sum()), include_groups=False
    )
    n = 0
    k = comp.key
    while int(by.get(k, 0) or 0) > 0:
        n += 1
        m, a = k % 100, k // 100
        k = (a - 1) * 100 + 12 if m == 1 else a * 100 + (m - 1)
    return n


def oportunidade_desbloqueio(df, *, filters=None, competencia=None, top_n=10, request_id=None) -> Envelope:
    """B — pares hospital x procedimento com mais vagas bloqueadas + persistencia."""
    filters = filters or {}
    base = _apply_filters(df, filters)
    fdf, comp = _select_competencia(base, competencia)
    work = fdf.copy()
    work["_b"] = catalog.measure_series(work, "vagas_bloqueadas")
    g = work.groupby(["hospital", "procedimento"])["_b"].sum().sort_values(ascending=False)
    g = g[g > 0].head(top_n)
    buckets = []
    for (hosp, proc), b in g.items():
        buckets.append({
            "key": f"{hosp} · {str(proc)[:40]}",
            "value": int(b),
            "hospital": hosp,
            "procedimento": proc,
            "persistencia_meses": _persistencia_bloqueio(base, hosp, proc, comp),
        })
    return Envelope.breakdown(
        metric="oportunidade_desbloqueio", metric_kind=MetricKind.SNAPSHOT,
        dimension="hospital_procedimento", buckets=buckets, units="vagas", source_index=SOURCE,
        window=_window(comp), filters=_filters_meta(filters, comp),
        total_documents=int(work["_b"].sum()), request_id=request_id,
    )


def panorama(df, *, filters=None, competencia=None, request_id=None) -> Envelope:
    """E — briefing executivo: oferta, bloqueio, porta de entrada, concentracao, oportunidades."""
    filters = filters or {}
    base = _apply_filters(df, filters)
    _, comp = _select_competencia(base, competencia)
    subs = [
        total(df, metric="vagas_disponiveis", filters=filters, competencia=comp, request_id=request_id),
        taxa_bloqueio(df, filters=filters, competencia=comp, request_id=request_id),
        indice_porta_entrada(df, filters=filters, competencia=comp, request_id=request_id),
        breakdown(df, metric="vagas_disponiveis", dimension="hospital", filters=filters, competencia=comp, top_n=3, request_id=request_id),
        oportunidade_desbloqueio(df, filters=filters, competencia=comp, top_n=5, request_id=request_id),
    ]
    primary = subs[3]  # concentracao por hospital (visual no chart)
    return primary.model_copy(update={
        "metric": "panorama",
        "sub_envelopes": [e.model_dump(mode="json") for e in subs],
        "method_note": (
            f"Panorama executivo da competencia {comp.label}: oferta total, taxa de bloqueio, "
            "indice de porta de entrada, concentracao (top-3 hospitais) e oportunidades de desbloqueio."
        ),
    })
