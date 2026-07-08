"""Skill `chart` — Envelope.shape -> figura Plotly (deterministico, sem LLM).

Spec §8.1 mapa shape -> visual:
  scalar       -> None (UI renderiza st.metric)
  timeseries   -> linha
  breakdown    -> barra horizontal (tabela se cardinalidade > limite)
  comparison   -> barra com entidade em destaque
  distribution -> barra com stats (min/p50/avg/p90/max)

Retorna dict (Plotly figure serializada). UI faz st.plotly_chart(dict).
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

from app.agent.envelope import Envelope, Shape

# Paleta IGES (mesma da UI)
COLOR_PRIMARY = "#1A6FA8"
COLOR_ACCENT = "#37B8C5"
COLOR_FOCUS = "#E8851E"
COLOR_GREEN = "#9DCC23"
COLOR_NEUTRAL = "#94A3B8"

_LAYOUT_BASE = dict(
    paper_bgcolor="white",
    plot_bgcolor="#F8FAFC",
    font=dict(family="Helvetica, Arial, sans-serif", size=12, color="#1A1F2E"),
    margin=dict(l=20, r=20, t=50, b=40),
)


def to_plotly_dict(envelope: Envelope) -> dict[str, Any] | None:
    """Roteador deterministico. None para scalar (UI usa metric card)."""
    shape = envelope.shape
    if shape == Shape.SCALAR:
        return None
    if shape == Shape.BREAKDOWN:
        return _breakdown_bar(envelope)
    if shape == Shape.TIMESERIES:
        return _timeseries_line(envelope)
    if shape == Shape.COMPARISON:
        return _comparison_bar(envelope)
    if shape == Shape.DISTRIBUTION:
        return _distribution_bar(envelope)
    return None


def _breakdown_bar(env: Envelope) -> dict[str, Any]:
    labels: list[str] = []
    values: list[float] = []
    hovers: list[str] = []
    for item in env.data:
        key = str(item.get("key", ""))
        desc = item.get("descricao")
        if isinstance(desc, str) and desc:
            label = f"{key} · {desc[:60]}"
        else:
            label = key
        labels.append(label)
        v = item.get("value", item.get("count", 0)) or 0
        values.append(float(v))
        pct = item.get("pct")
        hover = f"{key}<br><b>{int(v):,}</b> {env.units}".replace(",", ".")
        if pct is not None:
            hover += f" ({pct}%)"
        if isinstance(desc, str) and desc:
            hover += f"<br><i>{desc}</i>"
        hovers.append(hover)

    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color=COLOR_PRIMARY),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hovers,
        )
    )
    title = f"{env.metric} por {env.dimension}" if env.dimension else env.metric
    fig.update_layout(
        title=title,
        xaxis_title=str(env.units),
        yaxis=dict(autorange="reversed"),
        height=max(280, len(labels) * 32 + 80),
        **_LAYOUT_BASE,
    )
    return fig.to_dict()


def _timeseries_line(env: Envelope) -> dict[str, Any]:
    # Fonte legada usa 'timestamp' (data); motor de vagas usa 'key' (competencia MM/AAAA).
    x = [p.get("timestamp") or p.get("key") for p in env.data]
    y = [float(p.get("value", 0) or 0) for p in env.data]
    is_date = bool(env.data) and env.data[0].get("timestamp") is not None
    hover = (
        "%{x|%d/%m/%Y}<br><b>%{y:,.0f}</b> " + str(env.units) + "<extra></extra>"
        if is_date
        else "%{x}<br><b>%{y:,.0f}</b> " + str(env.units) + "<extra></extra>"
    )
    fig = go.Figure(
        go.Scatter(
            x=x,
            y=y,
            mode="lines+markers",
            line=dict(color=COLOR_PRIMARY, width=2.5),
            marker=dict(size=6, color=COLOR_PRIMARY),
            fill="tozeroy",
            fillcolor="rgba(26,111,168,0.08)",
            hovertemplate=hover,
        )
    )
    fig.update_layout(
        title=f"{env.metric} ao longo do tempo",
        xaxis_title="competência" if not is_date else "data",
        yaxis_title=str(env.units),
        height=340,
        **_LAYOUT_BASE,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E5E7EB")
    return fig.to_dict()


def _comparison_bar(env: Envelope) -> dict[str, Any]:
    item = env.data[0] if env.data else {}
    focus = item.get("focus", {}) or {}
    benchmark = item.get("benchmark", []) or []

    all_items = [focus] + list(benchmark)
    labels = [str(it.get("key", "?")) for it in all_items]
    values = [float(it.get("value", it.get("count", 0)) or 0) for it in all_items]
    colors = [COLOR_FOCUS] + [COLOR_PRIMARY] * len(benchmark)

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            hovertemplate="%{x}<br><b>%{y:,.0f}</b> " + str(env.units) + "<extra></extra>",
        )
    )
    focus_label = focus.get("key", "?")
    fig.update_layout(
        title=f"{env.metric} — destaque: {focus_label}",
        yaxis_title=str(env.units),
        height=340,
        **_LAYOUT_BASE,
    )
    fig.update_yaxes(gridcolor="#E5E7EB")
    return fig.to_dict()


def _distribution_bar(env: Envelope) -> dict[str, Any]:
    stats = env.data[0] if env.data else {}
    order = ("min", "p50", "avg", "p90", "p99", "max")
    labels_pretty = {
        "min": "mínimo",
        "p50": "mediana (p50)",
        "avg": "média",
        "p90": "p90",
        "p99": "p99",
        "max": "máximo",
    }
    labels: list[str] = []
    values: list[float] = []
    for k in order:
        v = stats.get(k)
        if v is None:
            continue
        labels.append(labels_pretty[k])
        values.append(float(v))

    colors = []
    for lbl in labels:
        if "mediana" in lbl or "média" in lbl:
            colors.append(COLOR_PRIMARY)
        elif "p90" in lbl or "p99" in lbl:
            colors.append(COLOR_FOCUS)
        else:
            colors.append(COLOR_NEUTRAL)

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{v:.1f}" for v in values],
            textposition="outside",
            hovertemplate="%{x}: <b>%{y:.2f}</b> " + str(env.units) + "<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{env.metric} — distribuição",
        yaxis_title=str(env.units),
        height=340,
        **_LAYOUT_BASE,
    )
    fig.update_yaxes(gridcolor="#E5E7EB")
    return fig.to_dict()
