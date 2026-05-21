"""Template T-FREE — DSL livre validado por safety guard.

POC ONLY (constituicao P3 override). Expira em settings.poc_expires_at.

O LLM gera o body DSL diretamente, usando os mappings injetados no system prompt.
Antes de executar, app.es.safety.validate() faz allowlist negativa.
"""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.config import DF_INDEX_SUFFIX, settings
from app.es import safety

NAME = "free_text_search"
DESCRIPTION = (
    "Use quando a pergunta nao se encaixa em um template especializado. "
    "Voce escreve o body DSL Elasticsearch diretamente, baseado nos mappings dos "
    "indices fornecidos no system prompt. Restricoes: size <= 50 em hits; sem "
    "script/runtime_mappings/scripted_metric; sem PII (cpf_*, endereco_*, etc.) "
    "como alvo de filtro; somente os 3 indices DF."
)


class Params(BaseModel):
    indice: Literal[
        "solicitacao-ambulatorial",
        "marcacao-ambulatorial",
        "solicitacao-hospitalar",
    ] = Field(..., description="Familia do indice (sem sufixo DF — o engine adiciona).")
    dsl: dict[str, Any] = Field(..., description="Body completo da query Elasticsearch.")
    justificativa: str = Field(
        ...,
        min_length=20,
        description=(
            "Justificativa do operador (texto curto, >=20 chars) explicando "
            "por que esta pergunta exige DSL custom em vez de template fixo."
        ),
    )

    @model_validator(mode="after")
    def _safety_checks(self) -> "Params":
        if settings.app_mode != "poc":
            raise ValueError(
                "free_text_search disponivel apenas em app_mode='poc'."
            )
        if date.today() > settings.poc_expires_at:
            raise ValueError(
                f"Modo POC expirou em {settings.poc_expires_at}. "
                "free_text_search nao disponivel."
            )
        safety.validate(self.dsl)
        return self


def index(params: Params) -> str:
    return f"{params.indice}-{DF_INDEX_SUFFIX}"


def render(params: Params) -> dict[str, Any]:
    """Pass-through — DSL ja foi validado em Params.__init__."""
    return params.dsl


def consolidate(es_response: dict[str, Any], params: Params) -> dict[str, Any]:
    """Consolidacao generica: hits + aggregations."""
    hits_obj = es_response.get("hits", {})
    return {
        "took_ms": es_response.get("took"),
        "total": hits_obj.get("total"),
        "hits": [h.get("_source", {}) for h in hits_obj.get("hits", [])],
        "aggregations": es_response.get("aggregations"),
    }


def tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": NAME,
            "description": DESCRIPTION,
            "parameters": Params.model_json_schema(),
        },
    }
