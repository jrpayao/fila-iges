"""Orquestrador do motor de vagas.

Pipeline: pergunta -> Planner -> VagasPlan -> resolver filtros -> primitivas
         -> compose -> Envelope -> Synthesizer -> resposta.

Reusa Envelope (P4), ClarificationRequest (P10) e audit (P15) do motor v2.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from app import audit
from app.agent.envelope import Envelope, Shape
from app.agent.plan import ClarificationRequest
from app.agent.resolver import AmbiguityError, UnresolvedError
from app.vagas import planner as _planner
from app.vagas import primitives as P
from app.vagas import resolver as R
from app.vagas import synthesizer as _synth
from app.vagas.plan import VagasPlan, VagasStep
from app.vagas.store import VagasStore

# ----- DataFrame em memoria (carrega uma vez, recarrega sob demanda) -----
_DF: pd.DataFrame | None = None


def get_df(*, force_reload: bool = False) -> pd.DataFrame:
    global _DF
    if _DF is None or force_reload:
        _DF = VagasStore().load_df()
    return _DF


@dataclass
class VagasResponse:
    request_id: str
    pergunta: str
    envelope: Optional[Envelope] = None
    narrativa: Optional[str] = None
    plan: Optional[VagasPlan] = None
    clarifications: list[ClarificationRequest] = field(default_factory=list)
    refusal_reason: Optional[str] = None
    error: Optional[str] = None


# ===== Resolucao de filtros de um step =====


def _resolve_step(step: VagasStep, df: pd.DataFrame):
    """Retorna (filters_dict, competencia, clarifications)."""
    filters: dict[str, Any] = {}
    clarifs: list[ClarificationRequest] = []
    spec = step.filters

    if spec.procedimento:
        try:
            filters["procedimento"] = R.resolve_procedimento(spec.procedimento, df).valor
        except AmbiguityError as exc:
            clarifs.append(ClarificationRequest(field="procedimento", raw=spec.procedimento, reason="ambiguous", suggestions=exc.candidates[:6]))
        except UnresolvedError as exc:
            clarifs.append(ClarificationRequest(field="procedimento", raw=spec.procedimento, reason="unresolved", suggestions=exc.suggestions[:6]))

    if spec.hospital:
        try:
            filters["hospital"] = R.resolve_hospital(spec.hospital, df).nome
        except AmbiguityError as exc:
            clarifs.append(ClarificationRequest(field="hospital", raw=spec.hospital, reason="ambiguous", suggestions=exc.candidates[:6]))
        except UnresolvedError as exc:
            clarifs.append(ClarificationRequest(field="hospital", raw=spec.hospital, reason="unresolved", suggestions=exc.suggestions[:6]))

    competencia = None
    if spec.competencia:
        try:
            competencia = R.resolve_competencia(spec.competencia, df)
        except UnresolvedError as exc:
            clarifs.append(ClarificationRequest(field="competencia", raw=spec.competencia, reason="unresolved", suggestions=exc.suggestions[:6]))

    return filters, competencia, clarifs


def _execute_step(step: VagasStep, df: pd.DataFrame, *, request_id: str) -> tuple[Optional[Envelope], list[ClarificationRequest]]:
    filters, competencia, clarifs = _resolve_step(step, df)
    if clarifs:
        return None, clarifs

    prim = step.primitive
    if prim == "total":
        env = P.total(df, metric=step.metric, filters=filters, competencia=competencia, request_id=request_id)
    elif prim == "taxa_bloqueio":
        env = P.taxa_bloqueio(df, filters=filters, competencia=competencia, request_id=request_id)
    elif prim == "breakdown":
        if not step.dimension:
            raise ValueError(f"step '{step.label}': breakdown exige dimension")
        env = P.breakdown(df, metric=step.metric, dimension=step.dimension, filters=filters, competencia=competencia, top_n=step.top_n, request_id=request_id)
    elif prim == "mix_tipo_vaga":
        env = P.mix_tipo_vaga(df, base=step.mix_base or "ativas", filters=filters, competencia=competencia, request_id=request_id)
    elif prim == "timeseries":
        env = P.timeseries(df, metric=step.metric, filters=filters, request_id=request_id)
    elif prim == "compare":
        if not step.dimension or not step.focus_value:
            raise ValueError(f"step '{step.label}': compare exige dimension + focus_value")
        focus = _resolve_focus(step.dimension, step.focus_value, df)
        env = P.compare(df, metric=step.metric, dimension=step.dimension, focus_value=focus, filters=filters, competencia=competencia, top_n=step.top_n, request_id=request_id)
    else:
        raise ValueError(f"primitiva desconhecida: {prim}")
    return env, []


def _resolve_focus(dimension: str, raw: str, df: pd.DataFrame) -> str:
    """Traduz focus_value textual para o valor canonico da dimensao."""
    try:
        if dimension == "hospital":
            return R.resolve_hospital(raw, df).nome
        if dimension == "procedimento":
            return R.resolve_procedimento(raw, df).valor
    except (AmbiguityError, UnresolvedError):
        pass
    return raw


# ===== Composicao =====


def _compose(plan: VagasPlan, envelopes: dict[str, Envelope]) -> Envelope:
    if len(envelopes) == 1:
        return next(iter(envelopes.values()))
    # diagnostic: empacota sub_envelopes, escolhe um primary visual
    sub = [e.model_dump(mode="json") for e in envelopes.values()]
    primary = None
    for e in envelopes.values():
        if e.shape in (Shape.BREAKDOWN, Shape.TIMESERIES, Shape.COMPARISON):
            primary = e
            break
    primary = primary or next(iter(envelopes.values()))
    return primary.model_copy(update={
        "metric": plan.metric or primary.metric,
        "sub_envelopes": sub,
        "method_note": f"Diagnostico com {len(sub)} steps; veja sub_envelopes.",
    })


# ===== API principal =====


def ask(pergunta: str, *, request_id: str | None = None) -> VagasResponse:
    rid = request_id or str(uuid.uuid4())
    resp = VagasResponse(request_id=rid, pergunta=pergunta)
    audit.event("vagas.request.received", request_id=rid, pergunta=pergunta)

    df = get_df()
    if df.empty:
        resp.error = "Cache de vagas vazio — rode o sync (scripts/smoke_vagas.py)."
        return resp

    # 1) Planner
    try:
        plan_obj = _planner.plan(pergunta, request_id=rid)
    except Exception as exc:
        audit.event("vagas.planner.failed", request_id=rid, error=str(exc))
        resp.error = f"Planner falhou: {exc}"
        return resp
    resp.plan = plan_obj
    audit.event("vagas.plan.generated", request_id=rid, is_in_scope=plan_obj.is_in_scope,
                metric=plan_obj.metric, composition=plan_obj.composition, n_steps=len(plan_obj.steps))

    if not plan_obj.is_in_scope:
        resp.refusal_reason = plan_obj.refusal_reason or "Pergunta fora de escopo (nao e sobre vagas SISREG)."
        return resp
    if not plan_obj.steps:
        resp.error = "Plan sem steps."
        return resp

    # 2) Executar steps
    envelopes: dict[str, Envelope] = {}
    all_clarifs: list[ClarificationRequest] = []
    for step in plan_obj.steps:
        try:
            env, clarifs = _execute_step(step, df, request_id=rid)
        except Exception as exc:
            audit.event("vagas.step.failed", request_id=rid, step=step.label, error=str(exc))
            resp.error = f"Falha no step '{step.label}': {exc}"
            return resp
        if clarifs:
            all_clarifs.extend(clarifs)
            continue
        envelopes[step.label] = env
        audit.event("vagas.step.executed", request_id=rid, step=step.label, metric=env.metric, shape=env.shape.value)

    if all_clarifs:
        seen: set[tuple[str, str]] = set()
        uniq: list[ClarificationRequest] = []
        for c in all_clarifs:
            if (c.field, c.raw) not in seen:
                uniq.append(c)
                seen.add((c.field, c.raw))
        resp.clarifications = uniq
        return resp

    # 3) Compor
    try:
        final_env = _compose(plan_obj, envelopes)
    except Exception as exc:
        resp.error = f"Composicao falhou: {exc}"
        return resp
    resp.envelope = final_env

    # 4) Sintetizar
    try:
        resp.narrativa = _synth.synthesize(pergunta, final_env, demanda_caveat=plan_obj.demanda_caveat, request_id=rid)
    except Exception as exc:
        audit.event("vagas.synth.failed", request_id=rid, error=str(exc))
        resp.narrativa = f"(sem prosa — erro no sintetizador) Dados: {final_env.data}"
        resp.error = f"Sintetizador falhou: {exc}"
        return resp

    audit.event("vagas.request.completed", request_id=rid)
    return resp
