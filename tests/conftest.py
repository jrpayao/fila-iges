"""Fixtures e configuracao pytest. Isola testes de qualquer chamada real a ES/OpenAI."""

import os

import pytest

# Defaults seguros para testes — evita Settings exigir .env real
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-pytest")
os.environ.setdefault("SISREG_USER", "test-user")
os.environ.setdefault("SISREG_PASS", "test-pass")


@pytest.fixture
def es_response_top_cids():
    """Resposta ES tipica de top_cids — pra teste de consolidate."""
    return {
        "took": 1234,
        "hits": {
            "total": {"value": 64528, "relation": "eq"},
            "hits": [],
        },
        "aggregations": {
            "top_cids": {
                "doc_count_error_upper_bound": 5,
                "sum_other_doc_count": 50000,
                "buckets": [
                    {
                        "key": "I10",
                        "doc_count": 1808,
                        "descricao": {
                            "hits": {
                                "hits": [
                                    {"_source": {"descricao_cid_solicitado": "HIPERTENSAO ESSENCIAL"}}
                                ]
                            }
                        },
                    },
                    {
                        "key": "C50",
                        "doc_count": 1841,
                        "enriquecimento": {
                            "hits": {
                                "hits": [
                                    {"_source": {"descricao_cid_solicitado": "NEOPLASIA MALIGNA DA MAMA"}}
                                ]
                            }
                        },
                    },
                ],
            }
        },
    }


@pytest.fixture
def es_response_fila_snapshot():
    return {
        "took": 800,
        "hits": {"total": {"value": 395555, "relation": "eq"}, "hits": []},
        "aggregations": {
            "por_status": {
                "buckets": [
                    {"key": "SOLICITAÇÃO / PENDENTE / REGULADOR", "doc_count": 389788},
                    {"key": "SOLICITAÇÃO / REENVIADA / REGULADOR", "doc_count": 5634},
                ]
            },
            "por_risco": {
                "buckets": [
                    {"key": "2", "doc_count": 254816},
                    {"key": "3", "doc_count": 75801},
                ]
            },
        },
    }


@pytest.fixture
def doc_com_pii():
    """Doc de exemplo com varios campos PII pra testar redactor."""
    return {
        "no_usuario": "MARIA DA SILVA",
        "cns_usuario": "700123456789012",
        "cpf_usuario": "12345678901",
        "no_mae_usuario": "JOSEFA DA SILVA",
        "telefone": "(61)99999-9999",
        "dt_nascimento_usuario": "1980-05-20",
        "sexo_usuario": "FEMININO",
        "endereco_paciente_residencia": "RUA TESTE",
        "bairro_paciente_residencia": "ASA SUL",
        "cep_paciente_residencia": "70000000",
        "numero_paciente_residencia": "123",
        "complemento_paciente_residencia": "APTO 1",
        "tipo_logradouro_paciente_residencia": "RUA",
        "nome_medico_solicitante": "DR FULANO",
        "numero_crm": "12345",
        "codigo_cid_solicitado": "I10",
        "codigo_unidade_solicitante": "0011355",
        "nome_unidade_solicitante": "UBS 3",  # nao e PII (entidade publica)
        "data_solicitacao": "2026-05-20T00:00:00Z",
    }
