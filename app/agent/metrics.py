"""Catalogo Semantico — Spec §4. 17 metricas tipadas (P9 — vocabulario fechado).

Cada MetricDef declara: o que e, em qual indice nasce, com qual campo de data filtra,
qual a unidade, qual a forma esperada do envelope, se eh snapshot/flow/derived, e
- quando derivada - quais outras metricas compoe.

Esse catalogo eh consultado pelo planejador (Fase 3) e pelas primitivas (este arquivo nao
executa nada; so descreve).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.agent.envelope import MetricKind, Shape, Unit


@dataclass(frozen=True)
class MetricDef:
    """Definicao tipada de uma metrica do catalogo."""

    name: str
    description: str
    kind: MetricKind  # snapshot | flow | derived (Principio P5)
    source_index_family: str  # 'solicitacao-ambulatorial' | 'marcacao-ambulatorial' | 'solicitacao-hospitalar' | 'multi'
    default_unit: str
    default_shape: Shape
    date_field: Optional[str] = None
    status_group: Optional[str] = None
    method_note: Optional[str] = None
    depends_on: tuple[str, ...] = ()
    notes: str = ""

    @property
    def is_snapshot(self) -> bool:
        return self.kind == MetricKind.SNAPSHOT


# ===== Catalogo das 17 metricas =====


CATALOG: dict[str, MetricDef] = {
    "estoque_fila": MetricDef(
        name="estoque_fila",
        description="Fila viva no momento — quantos pacientes estao pendentes na regulacao agora",
        kind=MetricKind.SNAPSHOT,
        source_index_family="solicitacao-ambulatorial",
        default_unit=Unit.DOCUMENTOS.value,
        default_shape=Shape.SCALAR,
        status_group="fila",
        notes="Snapshot — sem janela temporal. Nunca somar com metricas de fluxo (P5).",
    ),
    "entrada_solicitacoes": MetricDef(
        name="entrada_solicitacoes",
        description="Novas solicitacoes recebidas no periodo (inflow da fila)",
        kind=MetricKind.FLOW,
        source_index_family="solicitacao-ambulatorial",
        default_unit=Unit.DOCUMENTOS.value,
        default_shape=Shape.SCALAR,
        date_field="data_solicitacao",
    ),
    "agendamentos": MetricDef(
        name="agendamentos",
        description="Marcacoes realizadas no periodo",
        kind=MetricKind.FLOW,
        source_index_family="marcacao-ambulatorial",
        default_unit=Unit.DOCUMENTOS.value,
        default_shape=Shape.SCALAR,
        date_field="data_marcacao",
    ),
    "atendimentos": MetricDef(
        name="atendimentos",
        description="Agendamentos confirmados pelo executante (vazao real)",
        kind=MetricKind.FLOW,
        source_index_family="marcacao-ambulatorial",
        default_unit=Unit.DOCUMENTOS.value,
        default_shape=Shape.SCALAR,
        date_field="data_confirmacao",
        status_group="atendido",
    ),
    "faltas": MetricDef(
        name="faltas",
        description="Agendamentos com falta registrada (no-show)",
        kind=MetricKind.FLOW,
        source_index_family="marcacao-ambulatorial",
        default_unit=Unit.DOCUMENTOS.value,
        default_shape=Shape.SCALAR,
        date_field="data_marcacao",
        status_group="falta",
        notes="Filtrado por status_group=falta. Alternativa: st_falta_registrada=1.",
    ),
    "cancelamentos": MetricDef(
        name="cancelamentos",
        description="Cancelados, negados ou devolvidos no periodo",
        kind=MetricKind.FLOW,
        source_index_family="marcacao-ambulatorial",
        default_unit=Unit.DOCUMENTOS.value,
        default_shape=Shape.SCALAR,
        date_field="data_cancelamento",
        status_group="cancelado",
    ),
    "taxa_falta": MetricDef(
        name="taxa_falta",
        description="Percentual de faltas sobre o total de agendamentos no periodo",
        kind=MetricKind.DERIVED,
        source_index_family="marcacao-ambulatorial",
        default_unit=Unit.PERCENT.value,
        default_shape=Shape.SCALAR,
        date_field="data_marcacao",
        depends_on=("faltas", "agendamentos"),
        method_note="taxa_falta = faltas / agendamentos no periodo informado.",
    ),
    "taxa_conversao": MetricDef(
        name="taxa_conversao",
        description="Percentual de agendamentos que viraram atendimento confirmado",
        kind=MetricKind.DERIVED,
        source_index_family="marcacao-ambulatorial",
        default_unit=Unit.PERCENT.value,
        default_shape=Shape.SCALAR,
        date_field="data_marcacao",
        depends_on=("atendimentos", "agendamentos"),
        method_note="taxa_conversao = atendimentos / agendamentos no periodo informado.",
    ),
    "taxa_cancelamento": MetricDef(
        name="taxa_cancelamento",
        description="Percentual de agendamentos cancelados/negados/devolvidos",
        kind=MetricKind.DERIVED,
        source_index_family="marcacao-ambulatorial",
        default_unit=Unit.PERCENT.value,
        default_shape=Shape.SCALAR,
        date_field="data_marcacao",
        depends_on=("cancelamentos", "agendamentos"),
        method_note="taxa_cancelamento = cancelamentos / agendamentos no periodo informado.",
    ),
    "tempo_espera_total": MetricDef(
        name="tempo_espera_total",
        description="Lead time ponta-a-ponta: solicitacao -> confirmacao",
        kind=MetricKind.DERIVED,
        source_index_family="marcacao-ambulatorial",
        default_unit=Unit.DIAS.value,
        default_shape=Shape.DISTRIBUTION,
        date_field="data_confirmacao",
        notes="Reportar como mediana e p90. Usa primitiva lead_time.",
    ),
    "tempo_regulacao": MetricDef(
        name="tempo_regulacao",
        description="Tempo entre a solicitacao e a aprovacao pela regulacao",
        kind=MetricKind.DERIVED,
        source_index_family="marcacao-ambulatorial",
        default_unit=Unit.DIAS.value,
        default_shape=Shape.DISTRIBUTION,
        date_field="data_aprovacao",
        notes="Segmento da cadeia de espera (solicitacao -> aprovacao).",
    ),
    "tempo_marcacao": MetricDef(
        name="tempo_marcacao",
        description="Tempo entre aprovacao e marcacao efetiva",
        kind=MetricKind.DERIVED,
        source_index_family="marcacao-ambulatorial",
        default_unit=Unit.DIAS.value,
        default_shape=Shape.DISTRIBUTION,
        date_field="data_marcacao",
        notes="Segmento da cadeia (aprovacao -> marcacao).",
    ),
    "tempo_execucao": MetricDef(
        name="tempo_execucao",
        description="Tempo entre marcacao e atendimento confirmado",
        kind=MetricKind.DERIVED,
        source_index_family="marcacao-ambulatorial",
        default_unit=Unit.DIAS.value,
        default_shape=Shape.DISTRIBUTION,
        date_field="data_confirmacao",
        notes="Segmento final (marcacao -> confirmacao).",
    ),
    "efeito_aviso": MetricDef(
        name="efeito_aviso",
        description="Taxa de falta segmentada por st_paciente_avisado (alavanca de confirmacao ativa)",
        kind=MetricKind.DERIVED,
        source_index_family="marcacao-ambulatorial",
        default_unit=Unit.PERCENT.value,
        default_shape=Shape.COMPARISON,
        date_field="data_marcacao",
        depends_on=("faltas", "agendamentos"),
        method_note="taxa_falta segmentada por st_paciente_avisado in {0, 1}.",
        notes="Prova alavanca: confirmacao ativa reduz no-show. Ancora com numero, nao palpite.",
    ),
    "previsao_atendimento": MetricDef(
        name="previsao_atendimento",
        description="Estimativa de espera = estoque_fila / vazao_media_diaria",
        kind=MetricKind.DERIVED,
        source_index_family="multi",
        default_unit=Unit.DIAS.value,
        default_shape=Shape.SCALAR,
        depends_on=("estoque_fila", "atendimentos"),
        method_note=(
            "Projecao por vazao: estoque_fila atual / (atendimentos / dias_janela). "
            "Mantido o ritmo atual e sem repriorizacao. Estimativa, nao previsao estatistica."
        ),
        notes="Principio P3: rotular como estimativa, method_note obrigatoria.",
    ),
    "mix_tipo_vaga": MetricDef(
        name="mix_tipo_vaga",
        description="Distribuicao por tipo de vaga (1=primeira vez, 2=retorno)",
        kind=MetricKind.SNAPSHOT,
        source_index_family="solicitacao-ambulatorial",
        default_unit=Unit.DOCUMENTOS.value,
        default_shape=Shape.BREAKDOWN,
        notes="Retorno tende a entupir a fila. Pode ser aplicado tambem em marcacao.",
    ),
    "cancel_por_perfil": MetricDef(
        name="cancel_por_perfil",
        description="Breakdown de cancelamentos por nome_perfil_cancelamento (paciente vs sistema)",
        kind=MetricKind.FLOW,
        source_index_family="marcacao-ambulatorial",
        default_unit=Unit.DOCUMENTOS.value,
        default_shape=Shape.BREAKDOWN,
        date_field="data_cancelamento",
        status_group="cancelado",
        notes="Cancelado pelo paciente vs pelo sistema → alavancas diferentes.",
    ),
}


# ===== API =====


def get(name: str) -> MetricDef:
    if name not in CATALOG:
        raise KeyError(f"Metrica '{name}' nao esta no catalogo (P9). Disponiveis: {sorted(CATALOG)}")
    return CATALOG[name]


def names() -> list[str]:
    return sorted(CATALOG.keys())


def by_kind(kind: MetricKind) -> list[MetricDef]:
    return [m for m in CATALOG.values() if m.kind == kind]


def by_family(family: str) -> list[MetricDef]:
    return [m for m in CATALOG.values() if m.source_index_family == family or m.source_index_family == "multi"]
