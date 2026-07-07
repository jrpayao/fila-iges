"""Plan + PlanStep — saida tipada do Planejador v2.

Esquema compativel com OpenAI structured outputs (strict mode): todos os campos
sao required ou explicitamente Optional[X] = None; nenhum dict[str, str] arbitrario.

Spec: §5 (primitivas) + §8 (envelope) + §7 (clarificacao P10).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ===== Filtros canonicos (vocabulario fechado P9) =====


class FilterSpec(BaseModel):
    """Filtros que o planejador pode emitir. Valores SAO BRUTOS do usuario.

    O orquestrador resolve cada valor via app.agent.resolver antes de executar
    a primitiva. Ambiguidade/unresolved -> ClarificationNeeded (P10).
    """

    model_config = ConfigDict(extra="forbid")

    cid: Optional[str] = Field(None, description="CID-10 (codigo X00/X000 OU nome em portugues)")
    prioridade: Optional[str] = Field(
        None, description="Prioridade do CID: P0/P1/P2/P3 ou 'emergencia'/'urgencia'/'nao urgente'/'eletivo'"
    )
    unidade_solicitante: Optional[str] = Field(None, description="Texto/alias da unidade que pede (ex: 'HRT', 'HBDF')")
    unidade_executante: Optional[str] = Field(None, description="Texto/alias da unidade que executa")
    status_grupo: Optional[list[str]] = Field(
        None,
        description=(
            "Lista de status_solicitacao literais OU nome de grupo "
            "(fila/agendado/atendido/falta/cancelado/pendente). Orquestrador expande grupo->lista."
        ),
    )
    tipo_regulacao: Optional[str] = Field(None, description="'R' (regulado) ou 'F' (fila de espera)")
    tipo_vaga: Optional[str] = Field(None, description="'1' (primeira vez) ou '2' (retorno)")
    grupo_procedimento: Optional[str] = Field(None, description="Codigo do grupo de procedimento (ex: '0301000000')")
    municipio: Optional[str] = Field(None, description="Municipio do paciente")
    bairro: Optional[str] = Field(None, description="Bairro do paciente")


# ===== PlanStep — invocacao de uma primitiva =====


class PlanStep(BaseModel):
    """Uma invocacao de primitiva dentro de um Plan."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., description="Identificador unico no plano (ex: 'fila_atual', 'vazao_30d')")
    primitive: Literal["count", "breakdown", "timeseries", "stats", "lead_time", "compare"]
    metric_name: str = Field(..., description="Nome da metrica do catalogo OU label de etapa intermediaria")
    metric_kind: Literal["snapshot", "flow", "derived"]
    source_family: Literal[
        "solicitacao-ambulatorial",
        "marcacao-ambulatorial",
        "solicitacao-hospitalar",
    ]
    filters: FilterSpec = Field(default_factory=FilterSpec, description="Filtros aplicados (valores brutos)")
    window_days: Optional[int] = Field(
        None, description="Janela em dias retroativos. None = snapshot (sem range)."
    )
    date_field: Optional[str] = Field(
        None,
        description=(
            "Campo de data para o range. Obrigatorio se window_days != None. Ex: data_solicitacao, "
            "data_aprovacao, data_marcacao, data_confirmacao, data_cancelamento, data_atualizacao."
        ),
    )

    # breakdown / compare
    dimension: Optional[str] = Field(
        None,
        description=(
            "Dimensao do breakdown/compare. Valores validos (familia ambulatorial): "
            "cid, prioridade, unidade_solicitante, unidade_executante, status, tipo_regulacao, "
            "tipo_vaga, grupo_procedimento, municipio, bairro, perfil_cancelamento, paciente_avisado."
        ),
    )
    top_n: int = Field(10, ge=1, le=50)
    focus_value: Optional[str] = Field(None, description="Para compare: valor da dimensao em destaque")

    # timeseries
    interval: Optional[Literal["day", "week", "month"]] = None

    # stats
    field: Optional[str] = Field(None, description="Campo numerico para stats (ex: codigo_classificacao_risco)")

    # lead_time
    start_date_field: Optional[str] = None
    end_date_field: Optional[str] = None


# ===== Plan — saida do Planejador LLM =====


class Plan(BaseModel):
    """Plano completo: pode ser refusal (off-topic), pedido de clarificacao, ou steps a executar.

    O orquestrador decide o que fazer baseado nos campos preenchidos.
    """

    model_config = ConfigDict(extra="forbid")

    is_in_scope: bool = Field(
        ...,
        description=(
            "True se a pergunta e sobre a fila de regulacao SISREG-DF (P11 — analise sobre fila NAO eh off-topic). "
            "False so para perguntas claramente fora (cardapio, clima, conduta clinica individual)."
        ),
    )
    refusal_reason: Optional[str] = Field(
        None,
        description="Se is_in_scope=false, motivo curto da recusa.",
    )

    rationale: Optional[str] = Field(
        None, description="Justificativa curta (1 frase) das escolhas do plano."
    )
    metric: Optional[str] = Field(None, description="Metrica principal do catalogo que a pergunta pede.")

    composition: Literal["none", "ratio", "projection", "diagnostic"] = Field(
        "none",
        description=(
            "Como combinar os steps:\n"
            "- 'none': EXATAMENTE 1 step, resultado direto\n"
            "- 'ratio': EXATAMENTE 2 steps scalar. Resultado = num.value / den.value * 100 -> percentual. "
            "Preencha ratio_numerator_label e ratio_denominator_label.\n"
            "- 'projection': EXATAMENTE 2 steps scalar (estoque + vazao). Resultado em dias. "
            "Preencha projection_stock_label, projection_flow_label, projection_days.\n"
            "- 'diagnostic': N steps (>=2). Synthesizer cita TODOS no relatorio prescritivo. "
            "Use para perguntas tipo 'como melhorar X', 'onde esta o gargalo', 'por que Y'."
        ),
    )
    ratio_numerator_label: Optional[str] = None
    ratio_denominator_label: Optional[str] = None
    projection_stock_label: Optional[str] = None
    projection_flow_label: Optional[str] = None
    projection_days: Optional[int] = Field(
        None, description="Janela usada para computar vazao na projecao (default 30)."
    )

    steps: list[PlanStep] = Field(default_factory=list, description="Lista de invocacoes de primitivas.")


# ===== Resposta do agente =====


class ClarificationRequest(BaseModel):
    """Quando entidade nao resolve / e ambigua. Disparador da UI de chips (P10)."""

    model_config = ConfigDict(extra="forbid")

    field: str  # 'cid', 'unidade_solicitante', etc.
    raw: str  # texto original do usuario
    reason: Literal["unresolved", "ambiguous"]
    suggestions: list[str] = Field(default_factory=list)
