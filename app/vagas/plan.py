"""Plan tipado do motor de vagas — saida do planejador LLM (structured outputs).

Compativel com OpenAI `parse(response_format=VagasPlan)` (strict): todo campo e
required ou Optional[X]=None; extra proibido. Valores de filtro sao BRUTOS —
o orquestrador resolve via app.vagas.resolver antes de executar (P10).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class VagasFilterSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    procedimento: Optional[str] = Field(None, description="Codigo SIGTAP ou nome do procedimento (ex: 'ressonancia', '3104000')")
    hospital: Optional[str] = Field(None, description="CNES ou nome/alias do hospital (ex: 'HUB', 'universitario')")
    competencia: Optional[str] = Field(
        None,
        description="Competencia: 'MM/AAAA', 'julho 2026', '202607' ou 'atual'. None = mais recente.",
    )


class VagasStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., description="Identificador unico no plano (ex: 'total_proc', 'serie').")
    primitive: Literal[
        "total", "taxa_bloqueio", "breakdown", "mix_tipo_vaga", "timeseries", "compare",
        # Pacote Wow (estrategicas):
        "indice_porta_entrada", "taxa_reserva", "vagas_perdidas_ytd",
        "cobertura_rede", "monofornecedores", "oportunidade_desbloqueio", "panorama",
        # 2a onda:
        "simular_desbloqueio", "anomalias", "raio_x_unidade",
        # 3a onda:
        "concentracao", "projecao", "comparar_hospitais", "plano_acao",
    ]
    metric: Literal["vagas_disponiveis", "vagas_ativas", "vagas_bloqueadas"] = Field(
        "vagas_disponiveis",
        description="Medida a agregar. Ignorada por taxa_bloqueio. Em mix_tipo_vaga, use vagas_ativas.",
    )
    dimension: Optional[Literal["procedimento", "especialidade", "hospital", "competencia"]] = Field(
        None, description="Dimensao do breakdown/compare. 'especialidade' agrupa procedimentos (imagem, cardio, oftalmo...)."
    )
    focus_value: Optional[str] = Field(None, description="compare: entidade em destaque (nome de hospital/procedimento).")
    hospital_b: Optional[str] = Field(None, description="comparar_hospitais: o segundo hospital (o primeiro vai em filters.hospital).")
    top_n: int = Field(10, ge=1, le=50)
    mix_base: Optional[Literal["ativas", "bloqueadas"]] = Field(
        None, description="mix_tipo_vaga: sobre vagas ativas ou bloqueadas (default ativas)."
    )
    target_pct: Optional[float] = Field(
        None, description="simular_desbloqueio: meta de taxa de bloqueio em % (ex: 15). Default 15."
    )
    filters: VagasFilterSpec = Field(default_factory=VagasFilterSpec)


class VagasPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_in_scope: bool = Field(
        ...,
        description=(
            "True se a pergunta e sobre VAGAS/capacidade SISREG do IGES (procedimentos, hospitais, "
            "oferta, bloqueio, tendencia). False so para o que nao tem relacao (clima, cardapio, "
            "conduta clinica individual)."
        ),
    )
    refusal_reason: Optional[str] = Field(None, description="Se fora de escopo, motivo curto.")
    demanda_caveat: bool = Field(
        False,
        description=(
            "True se a pergunta pede FILA/ESPERA/DEMANDA (tempo de espera, tamanho de fila, faltas). "
            "A fonte so cobre OFERTA — responda a capacidade e sinalize a limitacao."
        ),
    )
    rationale: Optional[str] = Field(None, description="1 frase justificando o plano.")
    metric: Optional[str] = Field(None, description="Metrica principal (rotulo canonico).")
    composition: Literal["none", "diagnostic"] = Field(
        "none",
        description="'none' = 1 step. 'diagnostic' = varios steps citados juntos na prosa (ex: 'como esta a oferta de X').",
    )
    steps: list[VagasStep] = Field(default_factory=list)
