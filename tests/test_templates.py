"""Testes de render e consolidate dos templates — determinismo e shape."""

import pytest

from app.config import DF_INDEX_SUFFIX
from app.es import registry


# --- top_cids ---


def test_top_cids_render_deterministic():
    """Mesmos params devem produzir mesmo body."""
    t = registry.get("top_cids")
    params = t.Params(janela_dias=30, top_n=10)
    body1 = t.render(params)
    body2 = t.render(params)
    assert body1 == body2


def test_top_cids_render_includes_df_filter():
    t = registry.get("top_cids")
    params = t.Params(janela_dias=30, top_n=10)
    body = t.render(params)
    must = body["query"]["bool"]["must"]
    assert any("codigo_uf_regulador" in step.get("term", {}) for step in must)


def test_top_cids_render_uses_codigo_cid_no_keyword():
    """Ambulatorial: codigo_* eh keyword direto (sem .keyword)."""
    t = registry.get("top_cids")
    params = t.Params(janela_dias=10, top_n=5)
    body = t.render(params)
    field = body["aggs"]["top_cids"]["terms"]["field"]
    assert field == "codigo_cid_solicitado", f"esperado sem .keyword, recebido {field}"


def test_top_cids_index_is_solicitacao_ambulatorial_df():
    t = registry.get("top_cids")
    params = t.Params(janela_dias=10)
    assert t.index(params) == f"solicitacao-ambulatorial-{DF_INDEX_SUFFIX}"


def test_top_cids_consolidate_shape(es_response_top_cids):
    t = registry.get("top_cids")
    params = t.Params(janela_dias=30, top_n=10)
    out = t.consolidate(es_response_top_cids, params)
    assert "linhas" in out
    assert "totais" in out
    assert "performance" in out
    assert out["totais"]["documentos_no_universo_filtrado"] == 64528
    assert len(out["linhas"]) == 2
    assert out["linhas"][0]["cid"] == "I10"
    assert out["linhas"][0]["descricao"] == "HIPERTENSAO ESSENCIAL"


def test_top_cids_validates_top_n_max_50():
    t = registry.get("top_cids")
    with pytest.raises(Exception):
        t.Params(janela_dias=10, top_n=100)


def test_top_cids_validates_janela_dias_max_365():
    t = registry.get("top_cids")
    with pytest.raises(Exception):
        t.Params(janela_dias=400, top_n=10)


# --- top_cids_marcacao ---


def test_top_cids_marcacao_atendidos_uses_data_confirmacao():
    t = registry.get("top_cids_marcacao")
    params = t.Params(tipo="atendidos", janela_dias=30, top_n=10)
    body = t.render(params)
    must = body["query"]["bool"]["must"]
    has_data_confirmacao = any("data_confirmacao" in step.get("range", {}) for step in must)
    assert has_data_confirmacao, "atendidos deve filtrar por data_confirmacao"


def test_top_cids_marcacao_cancelados_inclui_status_cancelado():
    t = registry.get("top_cids_marcacao")
    params = t.Params(tipo="cancelados", janela_dias=30, top_n=10)
    body = t.render(params)
    must = body["query"]["bool"]["must"]
    status_filters = [step for step in must if "terms" in step and "status_solicitacao.keyword" in step["terms"]]
    assert status_filters, "cancelados deve ter filter de status"
    values = status_filters[0]["terms"]["status_solicitacao.keyword"]
    assert any("CANCELADA" in v or "CANCELADO" in v or "NEGADA" in v for v in values)


def test_top_cids_marcacao_todos_sem_filtro_status():
    t = registry.get("top_cids_marcacao")
    params = t.Params(tipo="todos", janela_dias=30, top_n=10)
    body = t.render(params)
    must = body["query"]["bool"]["must"]
    has_status_filter = any("terms" in step and "status_solicitacao.keyword" in step.get("terms", {}) for step in must)
    assert not has_status_filter, "tipo=todos nao deve incluir filtro de status"


# --- top_cids_hospitalar ---


def test_top_cids_hospitalar_uses_keyword_subfield():
    """Hospitalar-v3: codigo_cid eh text+keyword."""
    t = registry.get("top_cids_hospitalar")
    params = t.Params(janela_dias=30, top_n=10)
    body = t.render(params)
    field = body["aggs"]["top_cids"]["terms"]["field"]
    assert field == "codigo_cid.keyword"


def test_top_cids_hospitalar_uf_filter_keyword():
    t = registry.get("top_cids_hospitalar")
    params = t.Params(janela_dias=30, top_n=10)
    body = t.render(params)
    must = body["query"]["bool"]["must"]
    assert any("codigo_uf_regulador.keyword" in step.get("term", {}) for step in must)


# --- top_procedimentos ---


def test_top_procedimentos_uses_nested_agg():
    t = registry.get("top_procedimentos")
    params = t.Params(janela_dias=30, top_n=5)
    body = t.render(params)
    assert "procedimentos_nested" in body["aggs"]
    assert body["aggs"]["procedimentos_nested"]["nested"]["path"] == "procedimentos"


# --- distribuicao_risco ---


def test_distribuicao_risco_uses_codigo_classificacao_risco():
    t = registry.get("distribuicao_risco")
    params = t.Params(indice="solicitacao-ambulatorial", janela_dias=30)
    body = t.render(params)
    field = body["aggs"]["por_risco"]["terms"]["field"]
    assert field == "codigo_classificacao_risco"


# --- distribuicao_status ---


def test_distribuicao_status_uses_keyword():
    t = registry.get("distribuicao_status")
    params = t.Params(indice="solicitacao-ambulatorial", janela_dias=30)
    body = t.render(params)
    field = body["aggs"]["por_status"]["terms"]["field"]
    assert field == "status_solicitacao.keyword"


# --- fila_snapshot ---


def test_fila_snapshot_no_temporal_range():
    """Snapshot eh sem range temporal."""
    t = registry.get("fila_snapshot")
    params = t.Params()
    body = t.render(params)
    must = body["query"]["bool"]["must"]
    has_range = any("range" in step for step in must)
    assert not has_range, "fila_snapshot nao deve ter range"


def test_fila_snapshot_filters_pendentes():
    t = registry.get("fila_snapshot")
    params = t.Params()
    body = t.render(params)
    must = body["query"]["bool"]["must"]
    status_filter = next(s for s in must if "terms" in s and "status_solicitacao.keyword" in s["terms"])
    statuses = status_filter["terms"]["status_solicitacao.keyword"]
    assert any("PENDENTE" in s or "REENVIADA" in s for s in statuses)


# --- distribuicao_carater_hospitalar ---


def test_distribuicao_carater_hospitalar_uses_keyword():
    """Hospitalar: carater eh text+keyword."""
    t = registry.get("distribuicao_carater_hospitalar")
    params = t.Params(janela_dias=30)
    body = t.render(params)
    field = body["aggs"]["por_carater"]["terms"]["field"]
    assert field == "carater.keyword"


# --- free_text_search ---


def test_free_text_search_validates_dsl():
    """DSL livre deve passar pelo safety guard via model_validator."""
    from app.es.safety import UnsafeDSLError

    t = registry.get("free_text_search")
    # DSL com script — deve falhar no model_validator
    with pytest.raises((UnsafeDSLError, ValueError)):
        t.Params(
            indice="solicitacao-ambulatorial",
            dsl={"query": {"script": {"source": "..."}}, "size": 1},
            justificativa="testando bloqueio de script com pelo menos 20 caracteres",
        )


def test_free_text_search_aceita_dsl_segura():
    t = registry.get("free_text_search")
    params = t.Params(
        indice="solicitacao-ambulatorial",
        dsl={
            "size": 0,
            "query": {"term": {"codigo_uf_regulador": "53"}},
            "aggs": {"x": {"terms": {"field": "codigo_cid_solicitado", "size": 5}}},
        },
        justificativa="agregacao custom nao coberta por template especializado",
    )
    assert params.indice == "solicitacao-ambulatorial"


def test_free_text_search_rejects_justificativa_curta():
    t = registry.get("free_text_search")
    with pytest.raises(Exception):
        t.Params(
            indice="solicitacao-ambulatorial",
            dsl={"size": 0, "query": {"match_all": {}}},
            justificativa="curta",  # < 20 chars
        )
