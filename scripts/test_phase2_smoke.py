"""Smoke test Fase 2 — primitivas reais contra o ES SISREG-DF.

Roda metricas representativas e mostra o Envelope resultante. Sem LLM nesta fase —
chamamos as primitivas diretamente pelo nome.
"""

import json
from datetime import date, timedelta

from app.agent import metrics, primitives
from app.agent.envelope import MetricKind, Window
from app.agent.filters import index_alias_for_family


def show(envelope, label):
    print(f"\n=== {label} ===")
    print(f"  metric:        {envelope.metric}  ({envelope.metric_kind.value})")
    print(f"  shape:         {envelope.shape.value}")
    print(f"  source_index:  {envelope.source_index}")
    print(f"  window:        {envelope.window.label}")
    print(f"  units:         {envelope.units}")
    print(f"  total_docs:    {envelope.total_documents}")
    if envelope.method_note:
        print(f"  method_note:   {envelope.method_note}")
    print(f"  data (top 5):")
    for d in envelope.data[:5]:
        # mascara chaves longas
        truncated = {k: (v[:80] + "...") if isinstance(v, str) and len(v) > 80 else v for k, v in d.items()}
        print(f"    {truncated}")


# Janela default: ultimos 30 dias
today = date.today()
window_30d = Window(gte=today - timedelta(days=30), lte=today, label="ultimos 30 dias")
window_snapshot = Window(gte=None, lte=None, label="snapshot (agora)")

idx_solicitacao = index_alias_for_family("solicitacao-ambulatorial")
idx_marcacao = index_alias_for_family("marcacao-ambulatorial")

# 1) estoque_fila (snapshot, count, sem range)
md = metrics.get("estoque_fila")
env = primitives.count(
    index=idx_solicitacao,
    filters={"status_grupo": ["SOLICITAÇÃO / PENDENTE / FILA DE ESPERA",
                              "SOLICITAÇÃO / PENDENTE / REGULADOR",
                              "SOLICITAÇÃO / REENVIADA / REGULADOR"]},
    window=window_snapshot,
    metric_name=md.name,
    metric_kind=md.kind,
    date_field=None,
)
show(env, "estoque_fila (snapshot)")

# 2) entrada_solicitacoes (flow, count, com range em data_solicitacao)
md = metrics.get("entrada_solicitacoes")
env = primitives.count(
    index=idx_solicitacao,
    filters={},
    window=window_30d,
    metric_name=md.name,
    metric_kind=md.kind,
    date_field=md.date_field,
)
show(env, "entrada_solicitacoes (ultimos 30d)")

# 3) breakdown por CID em solicitacao-ambulatorial
md = metrics.get("entrada_solicitacoes")  # base do count, dimensionado por cid
env = primitives.breakdown(
    index=idx_solicitacao,
    dimension="cid",
    filters={},
    window=window_30d,
    metric_name="top_cids_solicitados",
    metric_kind=MetricKind.FLOW,
    date_field="data_solicitacao",
    top_n=5,
)
show(env, "breakdown CID em solicitacao (top 5, ultimos 30d)")

# 4) breakdown por unidade_solicitante (top 5 com mais inflow)
env = primitives.breakdown(
    index=idx_solicitacao,
    dimension="unidade_solicitante",
    filters={},
    window=window_30d,
    metric_name="top_unidades_solicitantes",
    metric_kind=MetricKind.FLOW,
    date_field="data_solicitacao",
    top_n=5,
)
show(env, "breakdown unidade_solicitante (top 5)")

# 5) timeseries diaria de inflow nos ultimos 14 dias
window_14d = Window(gte=today - timedelta(days=14), lte=today, label="ultimos 14 dias")
env = primitives.timeseries(
    index=idx_solicitacao,
    date_field="data_solicitacao",
    interval="day",
    filters={},
    window=window_14d,
    metric_name="inflow_diario",
    metric_kind=MetricKind.FLOW,
)
show(env, "timeseries inflow diario (14d)")

# 6) lead_time tempo_regulacao em marcacao-ambulatorial (data_solicitacao -> data_aprovacao)
try:
    md = metrics.get("tempo_regulacao")
    env = primitives.lead_time(
        index=idx_marcacao,
        start_date_field="data_solicitacao",
        end_date_field="data_aprovacao",
        filters={},
        window=window_30d,
        metric_name=md.name,
        percentiles=(50, 90),
    )
    show(env, "tempo_regulacao (lead_time)")
except Exception as exc:
    print(f"\n=== tempo_regulacao FALHOU ===")
    print(f"  ERRO: {type(exc).__name__}: {str(exc)[:200]}")
    print("  Causa provavel: cluster ES com Painless desabilitado.")

print("\nOK")
