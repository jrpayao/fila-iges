"""Router Agent — primeira porta do pipeline.

Classifica pergunta em data_query / meta / out_of_scope antes de gastar tokens
nos agentes pesados (planner, validator, narrator).

Modelo: gpt-4o-mini (rapido e barato — decisao simples).
"""

from enum import Enum

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.llm.prompts import ROUTER_SYSTEM, ROUTER_VERSION
from app.llm.telemetry import capture_cache_telemetry


class Intent(str, Enum):
    DATA_QUERY = "data_query"
    META = "meta"
    OUT_OF_SCOPE = "out_of_scope"


class RouterResult(BaseModel):
    intent: Intent = Field(..., description="Categoria da pergunta")
    needs_pii: bool = Field(
        default=False,
        description="True se a pergunta requer dados individuais identificaveis",
    )
    reasoning: str = Field(..., description="Justificativa curta da classificacao")


def classify(pergunta: str) -> RouterResult:
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.beta.chat.completions.parse(
        model=settings.openai_router_model,
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM},
            {"role": "user", "content": pergunta},
        ],
        response_format=RouterResult,
        temperature=0.0,
    )
    capture_cache_telemetry(response, "router")
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("Router nao retornou RouterResult parseavel.")
    return parsed


def version() -> str:
    return ROUTER_VERSION
