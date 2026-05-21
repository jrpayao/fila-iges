"""Testes do registry — allowlist de templates (P3)."""

import pytest

from app.es import registry


def test_registry_has_expected_templates():
    """Registry deve ter os 11 templates esperados."""
    expected = {
        "top_cids",
        "top_cids_marcacao",
        "top_cids_hospitalar",
        "top_unidades_solicitantes",
        "top_unidades_executantes",
        "top_procedimentos",
        "distribuicao_risco",
        "distribuicao_status",
        "distribuicao_carater_hospitalar",
        "fila_snapshot",
        "free_text_search",
    }
    actual = set(registry.names())
    assert actual == expected, f"diff: missing={expected-actual}, extra={actual-expected}"


def test_registry_get_known_template_works():
    template = registry.get("top_cids")
    assert template.NAME == "top_cids"
    assert callable(template.render)
    assert callable(template.consolidate)
    assert callable(template.index)
    assert callable(template.tool_schema)


def test_registry_get_unknown_raises_keyerror():
    with pytest.raises(KeyError, match="allowlist"):
        registry.get("template_que_nao_existe")


def test_registry_tool_schemas_returns_valid_openai_format():
    schemas = registry.tool_schemas()
    assert len(schemas) == 11
    for schema in schemas:
        assert schema["type"] == "function"
        assert "function" in schema
        fn = schema["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        # JSON Schema must have type=object
        assert fn["parameters"].get("type") == "object"


def test_all_templates_have_consistent_interface():
    """Todo template deve expor: NAME, DESCRIPTION, Params, index, render, consolidate, tool_schema."""
    for name in registry.names():
        template = registry.get(name)
        assert hasattr(template, "NAME"), f"{name} sem NAME"
        assert hasattr(template, "DESCRIPTION"), f"{name} sem DESCRIPTION"
        assert hasattr(template, "Params"), f"{name} sem Params"
        assert hasattr(template, "index"), f"{name} sem index()"
        assert hasattr(template, "render"), f"{name} sem render()"
        assert hasattr(template, "consolidate"), f"{name} sem consolidate()"
        assert hasattr(template, "tool_schema"), f"{name} sem tool_schema()"
        assert template.NAME == name, f"NAME mismatch em {name}"
