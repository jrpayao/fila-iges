"""Testes do safety guard DSL (constituicao P3 — free_text_search)."""

import pytest

from app.es.safety import UnsafeDSLError, validate


def test_simple_query_passes():
    dsl = {
        "size": 10,
        "query": {"term": {"codigo_uf_regulador": "53"}},
    }
    validate(dsl)  # nao deve levantar


def test_aggs_query_passes():
    dsl = {
        "size": 0,
        "query": {"bool": {"must": [{"term": {"codigo_uf_regulador": "53"}}]}},
        "aggs": {
            "top_cids": {
                "terms": {"field": "codigo_cid_solicitado", "size": 10}
            }
        },
    }
    validate(dsl)


def test_size_too_big_blocked():
    dsl = {"size": 100, "query": {}}
    with pytest.raises(UnsafeDSLError, match="size"):
        validate(dsl)


def test_size_negative_blocked():
    dsl = {"size": -1, "query": {}}
    with pytest.raises(UnsafeDSLError, match="size"):
        validate(dsl)


def test_script_blocked():
    dsl = {
        "size": 0,
        "query": {"script": {"source": "doc['x'].value > 0"}},
    }
    with pytest.raises(UnsafeDSLError, match="chave proibida 'script'"):
        validate(dsl)


def test_script_score_blocked():
    dsl = {
        "size": 0,
        "query": {"function_score": {"script_score": {"source": "..."}}},
    }
    with pytest.raises(UnsafeDSLError):
        validate(dsl)


def test_runtime_mappings_blocked():
    dsl = {
        "size": 0,
        "runtime_mappings": {"computed_field": {"type": "keyword"}},
        "query": {"match_all": {}},
    }
    with pytest.raises(UnsafeDSLError, match="chave proibida 'runtime_mappings'"):
        validate(dsl)


def test_cpf_in_term_filter_blocked():
    """ALWAYS_MASKED_PII nao pode ser alvo de filtro (P2)."""
    dsl = {
        "size": 1,
        "query": {"term": {"cpf_usuario": "12345678901"}},
    }
    with pytest.raises(UnsafeDSLError, match="cpf_usuario"):
        validate(dsl)


def test_cpf_keyword_subfield_also_blocked():
    """Subfield .keyword tambem e bloqueado."""
    dsl = {
        "size": 1,
        "query": {"term": {"cpf_usuario.keyword": "12345678901"}},
    }
    with pytest.raises(UnsafeDSLError, match="cpf_usuario"):
        validate(dsl)


def test_endereco_in_match_blocked():
    dsl = {
        "size": 1,
        "query": {"match": {"endereco_paciente_residencia": "RUA"}},
    }
    with pytest.raises(UnsafeDSLError):
        validate(dsl)


def test_deeply_nested_script_blocked():
    """Walk recursivo deve pegar script em bool.must.[].function_score.script."""
    dsl = {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"codigo_uf_regulador": "53"}},
                    {"function_score": {"script_score": {"source": "..."}}},
                ]
            }
        },
    }
    with pytest.raises(UnsafeDSLError):
        validate(dsl)


def test_dsl_root_must_be_dict():
    with pytest.raises(UnsafeDSLError):
        validate(["not", "a", "dict"])  # type: ignore[arg-type]


def test_aggs_with_terms_on_non_pii_field_passes():
    dsl = {
        "size": 0,
        "query": {"match_all": {}},
        "aggs": {
            "por_status": {
                "terms": {"field": "status_solicitacao.keyword", "size": 20}
            }
        },
    }
    validate(dsl)
