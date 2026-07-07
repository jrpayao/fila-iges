"""Orquestrador v2 — Spec §2 (arquitetura).

Pipeline:
  pergunta -> Planner -> Plan -> resolver filtros -> executar primitivas
           -> compor (none|ratio|projection) -> Envelope -> Synthesizer -> resposta

Cada transicao audita em audit.jsonl (P15). Falha em qualquer ponto retorna
AgentResponse com `error` preenchido (nunca quebra silenciosamente).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

from app import audit
from app.agent import metrics, primitives, resolver, synthesizer
from app.agent.envelope import Envelope, MetricKind, Unit, Window
from app.agent.filters import index_alias_for_family
from app.agent.plan import ClarificationRequest, FilterSpec, Plan, PlanStep
from app.agent.planner import plan as run_planner
from app.agent.resolver import (
    STATUS_GROUPS,
    AmbiguityError,
    UnresolvedError,
)


# ===== Resposta do orquestrador =====


@dataclass
class AgentResponse:
    request_id: str
    pergunta: str
    envelope: Optional[Envelope] = None
    narrativa: Optional[str] = None
    plan: Optional[Plan] = None
    clarifications: list[ClarificationRequest] = field(default_factory=list)
    refusal_reason: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "pergunta": self.pergunta,
            "envelope": self.envelope.model_dump(mode="json") if self.envelope else None,
            "narrativa": self.narrativa,
            "plan": self.plan.model_dump(mode="json") if self.plan else None,
            "clarifications": [c.model_dump() for c in self.clarifications],
            "refusal_reason": self.refusal_reason,
            "error": self.error,
        }


# ===== Resolucao de filtros =====


def _resolve_filter_spec(
    spec: FilterSpec,
) -> tuple[dict[str, Any], list[ClarificationRequest]]:
    """Converte FilterSpec (valores brutos) em dict canonico (valores resolvidos).

    Retorna (filtros_resolvidos, lista_de_clarifications).
    """
    out: dict[str, Any] = {}
    clarif: list[ClarificationRequest] = []

    if spec.cid:
        try:
            r = resolver.resolve_cid(spec.cid)
            out["cid"] = r.codigo
        except AmbiguityError as exc:
            clarif.append(
                ClarificationRequest(field="cid", raw=spec.cid, reason="ambiguous", suggestions=exc.candidates[:6])
            )
        except UnresolvedError as exc:
            clarif.append(
                ClarificationRequest(field="cid", raw=spec.cid, reason="unresolved", suggestions=exc.suggestions[:6])
            )

    if spec.prioridade:
        try:
            r = resolver.resolve_prioridade(spec.prioridade)
            out["prioridade"] = r.codigo
        except UnresolvedError as exc:
            clarif.append(
                ClarificationRequest(
                    field="prioridade", raw=spec.prioridade, reason="unresolved", suggestions=exc.suggestions[:6]
                )
            )

    if spec.unidade_solicitante:
        try:
            r = resolver.resolve_unidade(spec.unidade_solicitante)
            out["unidade_solicitante"] = r.cnes or r.nome_oficial
        except AmbiguityError as exc:
            clarif.append(
                ClarificationRequest(
                    field="unidade_solicitante", raw=spec.unidade_solicitante, reason="ambiguous",
                    suggestions=exc.candidates[:6],
                )
            )
        except UnresolvedError as exc:
            clarif.append(
                ClarificationRequest(
                    field="unidade_solicitante", raw=spec.unidade_solicitante, reason="unresolved",
                    suggestions=exc.suggestions[:6],
                )
            )

    if spec.unidade_executante:
        try:
            r = resolver.resolve_unidade(spec.unidade_executante)
            out["unidade_executante"] = r.cnes or r.nome_oficial
        except AmbiguityError as exc:
            clarif.append(
                ClarificationRequest(
                    field="unidade_executante", raw=spec.unidade_executante, reason="ambiguous",
                    suggestions=exc.candidates[:6],
                )
            )
        except UnresolvedError as exc:
            clarif.append(
                ClarificationRequest(
                    field="unidade_executante", raw=spec.unidade_executante, reason="unresolved",
                    suggestions=exc.suggestions[:6],
                )
            )

    if spec.status_grupo:
        # Pode ser lista de grupos ('fila') OU literais ('SOLICITAÇÃO / PENDENTE / ...').
        expanded: list[str] = []
        for item in spec.status_grupo:
            if item in STATUS_GROUPS:
                expanded.extend(STATUS_GROUPS[item])
            else:
                # assume literal
                expanded.append(item)
        # dedup preservando ordem
        seen: set[str] = set()
        unique: list[str] = []
        for s in expanded:
            if s not in seen:
                unique.append(s)
                seen.add(s)
        out["status_grupo"] = unique

    if spec.tipo_regulacao:
        out["tipo_regulacao"] = spec.tipo_regulacao.upper()
    if spec.tipo_vaga:
        out["tipo_vaga"] = str(spec.tipo_vaga)
    if spec.grupo_procedimento:
        out["grupo_procedimento"] = spec.grupo_procedimento
    if spec.municipio:
        out["municipio"] = spec.municipio
    if spec.bairro:
        out["bairro"] = spec.bairro

    return out, clarif


# ===== Window helpers =====


def _window_from_step(step: PlanStep) -> Window:
    if step.window_days is None:
        return Window(gte=None, lte=None, label="snapshot (agora)")
    today = date.today()
    gte = today - timedelta(days=step.window_days)
    label = f"ultimos {step.window_days} dias" if step.window_days != 1 else "hoje"
    return Window(gte=gte, lte=today, label=label)


# ===== Execucao de um step =====


def _execute_step(
    step: PlanStep,
    *,
    request_id: str,
) -> tuple[Envelope, list[ClarificationRequest]]:
    """Resolve filtros, executa a primitiva, devolve Envelope + clarifications."""
    resolved_filters, clarifs = _resolve_filter_spec(step.filters)
    if clarifs:
        return None, clarifs  # type: ignore[return-value]

    index = index_alias_for_family(step.source_family)
    window = _window_from_step(step)
    kind = MetricKind(step.metric_kind)
    units = _units_for_step(step)

    if step.primitive == "count":
        env = primitives.count(
            index=index, filters=resolved_filters, window=window,
            metric_name=step.metric_name, metric_kind=kind, date_field=step.date_field,
            units=units, request_id=request_id,
        )
    elif step.primitive == "breakdown":
        if not step.dimension:
            raise ValueError(f"Step '{step.label}' primitive=breakdown exige `dimension`")
        env = primitives.breakdown(
            index=index, dimension=step.dimension, filters=resolved_filters, window=window,
            metric_name=step.metric_name, metric_kind=kind, date_field=step.date_field,
            top_n=step.top_n, units=units, request_id=request_id,
        )
    elif step.primitive == "timeseries":
        if not step.date_field or not step.interval:
            raise ValueError(f"Step '{step.label}' primitive=timeseries exige date_field+interval")
        env = primitives.timeseries(
            index=index, date_field=step.date_field, interval=step.interval,
            filters=resolved_filters, window=window, metric_name=step.metric_name,
            metric_kind=kind, units=units, request_id=request_id,
        )
    elif step.primitive == "stats":
        if not step.field:
            raise ValueError(f"Step '{step.label}' primitive=stats exige `field`")
        env = primitives.stats(
            index=index, field=step.field, filters=resolved_filters, window=window,
            metric_name=step.metric_name, metric_kind=kind, date_field=step.date_field,
            units=units, request_id=request_id,
        )
    elif step.primitive == "lead_time":
        if not step.start_date_field or not step.end_date_field:
            raise ValueError(f"Step '{step.label}' primitive=lead_time exige start_date_field+end_date_field")
        env = primitives.lead_time(
            index=index, start_date_field=step.start_date_field, end_date_field=step.end_date_field,
            filters=resolved_filters, window=window, metric_name=step.metric_name,
            metric_kind=kind, request_id=request_id,
        )
    elif step.primitive == "compare":
        if not step.dimension:
            raise ValueError(f"Step '{step.label}' primitive=compare exige dimension")
        # Resolve focus_value: traduz apelido textual -> valor indexado no ES.
        # Para dimensoes binarias conhecidas, se focus_value faltar default ao caso positivo.
        fv = _normalize_focus_value(step.dimension, step.focus_value)
        if fv is None:
            raise ValueError(
                f"Step '{step.label}' primitive=compare exige focus_value para dimension='{step.dimension}'"
            )
        if step.dimension in ("unidade_solicitante", "unidade_executante"):
            try:
                u = resolver.resolve_unidade(fv)
                if u.cnes:
                    fv = u.cnes
            except (AmbiguityError, UnresolvedError):
                pass  # mantem raw — se houver match exato vira
        elif step.dimension == "cid":
            try:
                c = resolver.resolve_cid(fv)
                fv = c.codigo
            except (AmbiguityError, UnresolvedError):
                pass
        env = primitives.compare(
            index=index, dimension=step.dimension, focus_value=fv,
            filters=resolved_filters, window=window, metric_name=step.metric_name,
            metric_kind=kind, date_field=step.date_field, top_n=step.top_n,
            units=units, request_id=request_id,
        )
    else:
        raise ValueError(f"Primitive desconhecida: {step.primitive}")

    return env, []


def _units_for_step(step: PlanStep) -> str:
    """Inferir units da metrica do catalogo, default documentos."""
    if step.metric_name in metrics.CATALOG:
        return metrics.CATALOG[step.metric_name].default_unit
    return Unit.DOCUMENTOS.value


# Dimensoes binarias e o valor que representa o "caso positivo" (focus default).
_BINARY_DIMENSION_DEFAULTS: dict[str, str] = {
    "paciente_avisado": "1",   # 1 = avisado (caso positivo)
    "tipo_vaga": "1",          # 1 = primeira vez (caso comum)
    "tipo_regulacao": "R",     # R = regulado (vs F = fila)
}

# Aliases textuais -> valor indexado por dimensao binaria.
_BINARY_DIMENSION_ALIASES: dict[str, dict[str, str]] = {
    "paciente_avisado": {
        "sim": "1", "avisado": "1", "avisados": "1", "comunicado": "1",
        "true": "1", "1": "1", "y": "1", "yes": "1",
        "nao": "0", "não": "0", "nao avisado": "0", "não avisado": "0",
        "false": "0", "0": "0", "n": "0", "no": "0",
    },
    "tipo_vaga": {
        "primeira vez": "1", "primeira": "1", "1ª vez": "1", "1": "1",
        "retorno": "2", "2": "2",
    },
    "tipo_regulacao": {
        "regulado": "R", "regulada": "R", "r": "R",
        "fila": "F", "fila de espera": "F", "f": "F",
    },
}


def _normalize_focus_value(dimension: str, raw: Optional[str]) -> Optional[str]:
    """Traduz focus_value textual para o valor indexado no ES.

    Para dimensoes binarias (paciente_avisado, tipo_vaga, tipo_regulacao):
    - Se raw vazio, defaulta ao caso positivo conhecido.
    - Se raw textual ('Sim'/'avisado'/'primeira vez'), mapeia via alias table.
    - Se nao reconhecido, retorna raw como veio (compare pode ainda achar bucket).

    Para outras dimensoes, retorna raw inalterado.
    """
    if dimension in _BINARY_DIMENSION_DEFAULTS and not raw:
        return _BINARY_DIMENSION_DEFAULTS[dimension]
    if raw is None:
        return None
    if dimension in _BINARY_DIMENSION_ALIASES:
        key = raw.strip().lower()
        return _BINARY_DIMENSION_ALIASES[dimension].get(key, raw)
    return raw


# ===== Composicao =====


def _compose(plan: Plan, envelopes: dict[str, Envelope], request_id: str) -> Envelope:
    """Combina envelopes conforme composition. Retorna Envelope final."""
    if plan.composition == "none":
        if len(envelopes) != 1:
            raise ValueError(f"composition=none exige 1 step, recebi {len(envelopes)}")
        env = next(iter(envelopes.values()))
        # opcional: substituir metric pelo metric do plan (alias canonico)
        if plan.metric and plan.metric != env.metric:
            return env.model_copy(update={"metric": plan.metric})
        return env

    if plan.composition == "ratio":
        if not (plan.ratio_numerator_label and plan.ratio_denominator_label):
            raise ValueError("composition=ratio exige labels num/den")
        num_env = envelopes[plan.ratio_numerator_label]
        den_env = envelopes[plan.ratio_denominator_label]
        num_val = float(num_env.data[0]["value"])
        den_val = float(den_env.data[0]["value"])
        ratio_pct = (num_val / den_val * 100) if den_val else 0.0
        return Envelope.scalar(
            metric=plan.metric or "ratio",
            metric_kind=MetricKind.DERIVED,
            value=round(ratio_pct, 2),
            units=Unit.PERCENT.value,
            source_index=num_env.source_index,
            window=num_env.window,
            filters=num_env.filters,
            method_note=(
                f"{plan.metric} = {plan.ratio_numerator_label} ({int(num_val)}) / "
                f"{plan.ratio_denominator_label} ({int(den_val)}) * 100. "
                f"{metrics.CATALOG[plan.metric].method_note if plan.metric in metrics.CATALOG else ''}"
            ).strip(),
            total_documents=int(den_val),
            request_id=request_id,
        )

    if plan.composition == "diagnostic":
        if len(envelopes) < 2:
            raise ValueError(f"composition=diagnostic exige >=2 steps, recebi {len(envelopes)}")
        # Empacota TODOS os envelopes como sub_envelopes
        sub_envs = [e.model_dump(mode="json") for e in envelopes.values()]
        # Escolhe o "primary" pra renderizar como envelope principal:
        # 1a opcao: primeiro breakdown (mais visual no chart)
        # 2a opcao: primeiro comparison/distribution
        # fallback: primeiro envelope
        primary = None
        from app.agent.envelope import Shape as _S
        for e in envelopes.values():
            if e.shape == _S.BREAKDOWN:
                primary = e
                break
        if primary is None:
            for e in envelopes.values():
                if e.shape in (_S.COMPARISON, _S.DISTRIBUTION, _S.TIMESERIES):
                    primary = e
                    break
        if primary is None:
            primary = next(iter(envelopes.values()))
        return primary.model_copy(
            update={
                "metric": plan.metric or primary.metric,
                "sub_envelopes": sub_envs,
                "method_note": (
                    f"Diagnostico composto de {len(sub_envs)} steps. "
                    f"Veja sub_envelopes para todos os valores citados na prosa."
                ),
            }
        )

    if plan.composition == "projection":
        if not (plan.projection_stock_label and plan.projection_flow_label):
            raise ValueError("composition=projection exige labels stock+flow")
        stock_env = envelopes[plan.projection_stock_label]
        flow_env = envelopes[plan.projection_flow_label]
        stock_val = float(stock_env.data[0]["value"])
        flow_val = float(flow_env.data[0]["value"])
        days = plan.projection_days or 30
        rate = flow_val / days if days else 0.0
        if rate <= 0:
            estimate = -1.0  # sentinel: indeterminado
            note = (
                f"Vazao media diaria = 0 em {days} dias (atendimentos={int(flow_val)}, "
                f"estoque={int(stock_val)}). Nao da pra projetar — sem vazao recente, "
                "fila e indeterminada."
            )
        else:
            estimate = round(stock_val / rate, 1)
            note = (
                f"Estimativa = estoque({int(stock_val)}) / "
                f"(vazao({int(flow_val)}) / {days} dias) = {estimate} dias. "
                "Mantido o ritmo atual e sem repriorizacao. Estimativa, nao previsao estatistica."
            )
        return Envelope.scalar(
            metric="previsao_atendimento",
            metric_kind=MetricKind.DERIVED,
            value=estimate,
            units=Unit.DIAS.value,
            source_index="multi",
            window=stock_env.window,
            filters=stock_env.filters,
            method_note=note,
            total_documents=int(stock_val),
            request_id=request_id,
        )

    raise ValueError(f"Composition desconhecida: {plan.composition}")


# ===== API principal =====


def ask(pergunta: str, *, request_id: str | None = None) -> AgentResponse:
    """Pipeline completo. Retorna AgentResponse com envelope+narrativa ou clarification/error."""
    rid = request_id or str(uuid.uuid4())
    resp = AgentResponse(request_id=rid, pergunta=pergunta)
    audit.event("agent.request.received", request_id=rid, pergunta=pergunta)

    # 1) Planner
    try:
        plan_obj = run_planner(pergunta, request_id=rid)
    except Exception as exc:
        audit.event("agent.planner.failed", request_id=rid, error=str(exc))
        resp.error = f"Planner falhou: {exc}"
        return resp
    resp.plan = plan_obj
    audit.event(
        "agent.plan.generated",
        request_id=rid,
        is_in_scope=plan_obj.is_in_scope,
        metric=plan_obj.metric,
        composition=plan_obj.composition,
        n_steps=len(plan_obj.steps),
    )

    if not plan_obj.is_in_scope:
        resp.refusal_reason = plan_obj.refusal_reason or "Pergunta fora de escopo."
        audit.event("agent.request.refused", request_id=rid, reason=resp.refusal_reason)
        return resp

    if not plan_obj.steps:
        resp.error = "Plan vazio (sem steps)."
        return resp

    # 2) Executar steps com resolucao de filtros
    envelopes: dict[str, Envelope] = {}
    all_clarifs: list[ClarificationRequest] = []
    for step in plan_obj.steps:
        try:
            env, clarifs = _execute_step(step, request_id=rid)
        except Exception as exc:
            audit.event("agent.step.failed", request_id=rid, step=step.label, error=str(exc))
            resp.error = f"Falha no step '{step.label}': {exc}"
            return resp
        if clarifs:
            all_clarifs.extend(clarifs)
            continue
        envelopes[step.label] = env
        audit.event(
            "agent.step.executed",
            request_id=rid,
            step=step.label,
            metric=env.metric,
            shape=env.shape.value,
            total=env.total_documents,
        )

    if all_clarifs:
        # dedup por (field, raw)
        seen: set[tuple[str, str]] = set()
        unique: list[ClarificationRequest] = []
        for c in all_clarifs:
            key = (c.field, c.raw)
            if key not in seen:
                unique.append(c)
                seen.add(key)
        resp.clarifications = unique
        audit.event("agent.clarification.needed", request_id=rid, count=len(unique))
        return resp

    # 3) Compor
    try:
        final_env = _compose(plan_obj, envelopes, rid)
    except Exception as exc:
        audit.event("agent.compose.failed", request_id=rid, error=str(exc))
        resp.error = f"Composicao falhou: {exc}"
        return resp
    resp.envelope = final_env
    audit.event(
        "agent.envelope.assembled",
        request_id=rid,
        metric=final_env.metric,
        shape=final_env.shape.value,
        units=final_env.units,
    )

    # 4) Sintetizar prosa
    try:
        resp.narrativa = synthesizer.synthesize(pergunta, final_env, request_id=rid)
    except Exception as exc:
        audit.event("agent.synthesizer.failed", request_id=rid, error=str(exc))
        resp.error = f"Sintetizador falhou: {exc}"
        resp.narrativa = f"(sem prosa — erro no sintetizador) Resultado bruto: {final_env.data}"
        return resp
    audit.event("agent.request.completed", request_id=rid)
    return resp
