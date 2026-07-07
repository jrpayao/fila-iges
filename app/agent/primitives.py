"""Primitivas Analiticas — Spec §5 (P9 — vocabulario fechado).

6 primitivas. Cada uma:
  - Recebe filtros canonicos (resolvidos), janela e parametros especificos.
  - Constroi DSL ES via app.agent.filters.
  - Executa via SisregESClient (read-only, P1).
  - Retorna Envelope tipado (P4).

`request_id` propagado para correlacao em audit.jsonl (P15).
"""

from __future__ import annotations

from typing import Any, Optional

from app import audit
from app.agent.envelope import Envelope, MetricKind, Shape, Unit, Window
from app.agent.filters import (
    build_query_body,
    dimension_to_es,
    family_of,
    index_alias_for_family,
)
from app.es.client import SisregESClient


def _execute(
    index: str,
    body: dict[str, Any],
    *,
    primitive: str,
    request_id: Optional[str],
    client: Optional[SisregESClient] = None,
) -> dict[str, Any]:
    """Executa body no ES. Aceita client injetado pra testes."""
    audit.event(
        "primitive.executing",
        primitive=primitive,
        index=index,
        request_id=request_id or "",
        body=body,
    )
    if client is not None:
        response = client.search(index, body)
    else:
        with SisregESClient() as es:
            response = es.search(index, body)
    audit.event(
        "primitive.executed",
        primitive=primitive,
        index=index,
        request_id=request_id or "",
        took_ms=response.get("took"),
        total=response.get("hits", {}).get("total"),
    )
    return response


# ============ count ============


def count(
    *,
    index: str,
    filters: dict[str, Any],
    window: Window,
    metric_name: str,
    metric_kind: MetricKind,
    date_field: Optional[str] = None,
    units: str = Unit.DOCUMENTOS.value,
    request_id: Optional[str] = None,
    client: Optional[SisregESClient] = None,
) -> Envelope:
    """Conta documentos. Envelope[scalar]."""
    body = build_query_body(filters=filters, window=window, index=index, date_field=date_field, size=0)
    response = _execute(index, body, primitive="count", request_id=request_id, client=client)
    total = response.get("hits", {}).get("total", {}).get("value", 0)
    return Envelope.scalar(
        metric=metric_name,
        metric_kind=metric_kind,
        value=total,
        units=units,
        source_index=index,
        window=window,
        filters=filters,
        total_documents=total,
        request_id=request_id,
    )


# ============ breakdown ============


def breakdown(
    *,
    index: str,
    dimension: str,
    filters: dict[str, Any],
    window: Window,
    metric_name: str,
    metric_kind: MetricKind,
    date_field: Optional[str] = None,
    top_n: int = 10,
    units: str = Unit.DOCUMENTOS.value,
    request_id: Optional[str] = None,
    client: Optional[SisregESClient] = None,
) -> Envelope:
    """Breakdown por dimensao via terms agg. Envelope[breakdown]."""
    field, desc_field = dimension_to_es(dimension, index)
    body = build_query_body(filters=filters, window=window, index=index, date_field=date_field, size=0)
    body["aggs"] = {
        "buckets": {
            "terms": {
                "field": field,
                "size": top_n,
                "shard_size": max(200, top_n * 20),
                "order": {"_count": "desc"},
            }
        }
    }
    if desc_field:
        body["aggs"]["buckets"]["aggs"] = {
            "desc": {"top_hits": {"size": 1, "_source": [desc_field]}}
        }
    response = _execute(index, body, primitive="breakdown", request_id=request_id, client=client)
    total = response.get("hits", {}).get("total", {}).get("value", 0)
    raw = response.get("aggregations", {}).get("buckets", {})
    error = raw.get("doc_count_error_upper_bound", 0)
    items: list[dict[str, Any]] = []
    for b in raw.get("buckets", []):
        item: dict[str, Any] = {"key": b["key"], "value": b["doc_count"], "count": b["doc_count"]}
        if desc_field:
            hits = b.get("desc", {}).get("hits", {}).get("hits", [])
            if hits:
                src = hits[0].get("_source", {})
                desc_value = src.get(desc_field, "")
                if isinstance(desc_value, str):
                    item["descricao"] = desc_value.strip()
        items.append(item)
    return Envelope.breakdown(
        metric=metric_name,
        metric_kind=metric_kind,
        dimension=dimension,
        buckets=items,
        units=units,
        source_index=index,
        window=window,
        filters=filters,
        doc_count_error=error,
        total_documents=total,
        request_id=request_id,
    )


# ============ timeseries ============


def timeseries(
    *,
    index: str,
    date_field: str,
    interval: str,  # 'day' | 'week' | 'month'
    filters: dict[str, Any],
    window: Window,
    metric_name: str,
    metric_kind: MetricKind,
    units: str = Unit.DOCUMENTOS.value,
    request_id: Optional[str] = None,
    client: Optional[SisregESClient] = None,
) -> Envelope:
    """Serie temporal via date_histogram. Envelope[timeseries]."""
    body = build_query_body(filters=filters, window=window, index=index, date_field=date_field, size=0)
    bounds: dict[str, str] = {}
    if window.gte:
        bounds["min"] = window.gte.isoformat()
    if window.lte:
        bounds["max"] = window.lte.isoformat()
    body["aggs"] = {
        "series": {
            "date_histogram": {
                "field": date_field,
                "calendar_interval": interval,
                "min_doc_count": 0,
                **({"extended_bounds": bounds} if bounds else {}),
            }
        }
    }
    response = _execute(index, body, primitive="timeseries", request_id=request_id, client=client)
    total = response.get("hits", {}).get("total", {}).get("value", 0)
    buckets = response.get("aggregations", {}).get("series", {}).get("buckets", [])
    points = [{"timestamp": b.get("key_as_string"), "value": b["doc_count"]} for b in buckets]
    return Envelope.timeseries(
        metric=metric_name,
        metric_kind=metric_kind,
        points=points,
        units=units,
        source_index=index,
        window=window,
        filters=filters,
        total_documents=total,
        request_id=request_id,
    )


# ============ stats ============


def stats(
    *,
    index: str,
    field: str,
    filters: dict[str, Any],
    window: Window,
    metric_name: str,
    metric_kind: MetricKind,
    date_field: Optional[str] = None,
    units: str = Unit.DOCUMENTOS.value,
    percentiles: tuple[int, ...] = (50, 90, 99),
    request_id: Optional[str] = None,
    client: Optional[SisregESClient] = None,
) -> Envelope:
    """Stats agregadas (min/max/avg/percentiles) sobre `field`. Envelope[distribution]."""
    body = build_query_body(filters=filters, window=window, index=index, date_field=date_field, size=0)
    body["aggs"] = {
        "stats": {"stats": {"field": field}},
        "percentiles": {"percentiles": {"field": field, "percents": list(percentiles)}},
    }
    response = _execute(index, body, primitive="stats", request_id=request_id, client=client)
    total = response.get("hits", {}).get("total", {}).get("value", 0)
    s = response.get("aggregations", {}).get("stats", {})
    p = response.get("aggregations", {}).get("percentiles", {}).get("values", {})
    stats_dict: dict[str, Any] = {
        "count": s.get("count", 0),
        "min": s.get("min"),
        "max": s.get("max"),
        "avg": s.get("avg"),
    }
    for pct in percentiles:
        stats_dict[f"p{pct}"] = p.get(f"{float(pct)}")
    return Envelope.distribution(
        metric=metric_name,
        metric_kind=metric_kind,
        stats=stats_dict,
        units=units,
        source_index=index,
        window=window,
        filters=filters,
        total_documents=total,
        request_id=request_id,
    )


# ============ lead_time ============


def lead_time(
    *,
    index: str,
    start_date_field: str,
    end_date_field: str,
    filters: dict[str, Any],
    window: Window,
    metric_name: str,
    metric_kind: MetricKind = MetricKind.DERIVED,
    percentiles: tuple[int, ...] = (50, 90),
    request_id: Optional[str] = None,
    client: Optional[SisregESClient] = None,
) -> Envelope:
    """Lead time entre dois campos de data, em dias. Usa runtime field Painless.

    Window aplicada sobre `end_date_field` (eventos com final dentro do periodo).
    Envelope[distribution] com mediana, p90 (e o que mais pedir) + avg.

    Limitacao: requer Painless scripting habilitado no cluster ES. Se desabilitado,
    o ES retorna 400 e a primitiva propaga o erro — fallback client-side fica pra
    iteracao futura.
    """
    body = build_query_body(filters=filters, window=window, index=index, date_field=end_date_field, size=0)
    body["runtime_mappings"] = {
        "lead_time_days": {
            "type": "long",
            "script": {
                "source": (
                    "if (doc[params.start].size() == 0 || doc[params.end].size() == 0) return; "
                    "long s = doc[params.start].value.toInstant().toEpochMilli(); "
                    "long e = doc[params.end].value.toInstant().toEpochMilli(); "
                    "if (e < s) return; "
                    "emit((e - s) / 86400000L);"
                ),
                "params": {"start": start_date_field, "end": end_date_field},
            },
        }
    }
    body["aggs"] = {
        "stats": {"stats": {"field": "lead_time_days"}},
        "percentiles": {"percentiles": {"field": "lead_time_days", "percents": list(percentiles)}},
    }
    response = _execute(index, body, primitive="lead_time", request_id=request_id, client=client)
    total = response.get("hits", {}).get("total", {}).get("value", 0)
    s = response.get("aggregations", {}).get("stats", {})
    p = response.get("aggregations", {}).get("percentiles", {}).get("values", {})
    stats_dict: dict[str, Any] = {
        "count": s.get("count", 0),
        "min": s.get("min"),
        "max": s.get("max"),
        "avg": s.get("avg"),
    }
    for pct in percentiles:
        stats_dict[f"p{pct}"] = p.get(f"{float(pct)}")
    return Envelope.distribution(
        metric=metric_name,
        metric_kind=metric_kind,
        stats=stats_dict,
        units=Unit.DIAS.value,
        source_index=index,
        window=window,
        filters=filters,
        total_documents=total,
        method_note=f"lead_time em dias = {end_date_field} - {start_date_field} (so eventos com end na janela).",
        request_id=request_id,
    )


# ============ compare ============


def compare(
    *,
    index: str,
    dimension: str,
    focus_value: str,
    filters: dict[str, Any],
    window: Window,
    metric_name: str,
    metric_kind: MetricKind,
    date_field: Optional[str] = None,
    top_n: int = 10,
    units: str = Unit.DOCUMENTOS.value,
    request_id: Optional[str] = None,
    client: Optional[SisregESClient] = None,
) -> Envelope:
    """Compara `focus_value` vs benchmark (top N). Envelope[comparison].

    Executa breakdown internamente, depois separa o bucket do focus do resto.
    """
    bd = breakdown(
        index=index,
        dimension=dimension,
        filters=filters,
        window=window,
        metric_name=metric_name,
        metric_kind=metric_kind,
        date_field=date_field,
        top_n=top_n,
        units=units,
        request_id=request_id,
        client=client,
    )
    buckets = bd.data
    focus_item = next((b for b in buckets if str(b.get("key")) == str(focus_value)), None)
    benchmark = [b for b in buckets if str(b.get("key")) != str(focus_value)]
    if focus_item is None:
        focus_item = {"key": focus_value, "value": 0, "count": 0, "not_in_top": True}
    return Envelope.comparison(
        metric=metric_name,
        metric_kind=metric_kind,
        dimension=dimension,
        focus=focus_item,
        benchmark=benchmark,
        units=units,
        source_index=index,
        window=window,
        filters=filters,
        total_documents=bd.total_documents,
        request_id=request_id,
    )


# ============ Re-export pra orquestrador ============

__all__ = [
    "count",
    "breakdown",
    "timeseries",
    "stats",
    "lead_time",
    "compare",
    "index_alias_for_family",
]
