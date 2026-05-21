"""Testes do anonymizer (constituicao P2)."""

from app.anonymize.fields import ALWAYS_MASKED_PII, POC_VISIBLE_PII
from app.anonymize.redactor import scrub


def test_always_masked_pii_disjoint_from_poc_visible():
    """Conjuntos devem ser disjuntos — campo nao pode estar nas duas listas."""
    overlap = ALWAYS_MASKED_PII & POC_VISIBLE_PII
    assert overlap == frozenset(), f"campos em ambas listas: {overlap}"


def test_scrub_drops_always_masked_in_producao(doc_com_pii):
    """Em modo producao, ALWAYS_MASKED some."""
    out = scrub(doc_com_pii, mode="producao", pii_exposure=False)
    for field in ALWAYS_MASKED_PII:
        assert field not in out, f"campo {field} deveria ter sido removido"


def test_scrub_drops_poc_visible_in_producao(doc_com_pii):
    """Em producao, POC_VISIBLE tambem some (estado default da P2)."""
    out = scrub(doc_com_pii, mode="producao", pii_exposure=False)
    for field in POC_VISIBLE_PII:
        assert field not in out


def test_scrub_keeps_poc_visible_when_poc_and_pii_exposure(doc_com_pii):
    """POC + pii_exposure=True: POC_VISIBLE passa."""
    out = scrub(doc_com_pii, mode="poc", pii_exposure=True)
    for field in POC_VISIBLE_PII:
        assert field in out, f"campo POC_VISIBLE {field} deveria ter passado em POC com pii_exposure"


def test_scrub_drops_always_masked_even_in_poc_with_pii_exposure(doc_com_pii):
    """ALWAYS_MASKED nunca passa — nem em POC com pii_exposure."""
    out = scrub(doc_com_pii, mode="poc", pii_exposure=True)
    for field in ALWAYS_MASKED_PII:
        assert field not in out, f"campo ALWAYS_MASKED {field} vazou em POC+pii_exposure"


def test_scrub_keeps_non_pii_fields(doc_com_pii):
    """Campos nao-PII (codigo, unidade publica) sempre passam."""
    for mode_setup in [("producao", False), ("poc", False), ("poc", True)]:
        mode, pii = mode_setup
        out = scrub(doc_com_pii, mode=mode, pii_exposure=pii)
        assert out["codigo_cid_solicitado"] == "I10"
        assert out["codigo_unidade_solicitante"] == "0011355"
        assert out["nome_unidade_solicitante"] == "UBS 3"
        assert out["data_solicitacao"] == "2026-05-20T00:00:00Z"


def test_scrub_recursive_through_lists():
    payload = {
        "hits": [
            {"cns_usuario": "123", "codigo_cid_solicitado": "I10"},
            {"cns_usuario": "456", "codigo_cid_solicitado": "C50"},
        ]
    }
    out = scrub(payload, mode="producao", pii_exposure=False)
    for hit in out["hits"]:
        assert "cns_usuario" not in hit
        assert "codigo_cid_solicitado" in hit


def test_scrub_handles_none_and_primitives():
    """scrub deve passar primitivos e None sem alterar."""
    assert scrub(None) is None
    assert scrub(42) == 42
    assert scrub("string") == "string"
    assert scrub(True) is True


def test_scrub_idempotent():
    """Scrub duas vezes deve dar mesmo resultado que uma vez."""
    payload = {"cns_usuario": "123", "codigo_cid_solicitado": "I10"}
    once = scrub(payload, mode="producao")
    twice = scrub(once, mode="producao")
    assert once == twice
