"""Engine — orquestra o pipeline multi-agente.

Fluxo:
  [Router] -> [Planner <-> Validator] (retry max 2) -> safety -> ES -> anonymize
           -> [Narrator <-> Critic] (retry max 2) -> resposta

Cada etapa registra evento em audit.jsonl.
"""

from datetime import date
from typing import Any

from pydantic import ValidationError

from app import audit
from app.anonymize import scanner
from app.anonymize.redactor import scrub
from app.config import settings
from app.es import registry, safety
from app.es.client import SisregESClient
from app.es.templates import free_text_search
from app.llm import critic, narrator, pii_auditor, planner, router, validator
from app.llm.router import Intent


class EngineError(RuntimeError):
    pass


META_RESPONSE = (
    "Sou o assistente do fila-eletiva (IGES-DF/ZELLO). Respondo perguntas sobre a fila "
    "de regulacao do SISREG-DF (ambulatorial e hospitalar) — coisas como: top CIDs em "
    "uma janela, distribuicao por status, agendamentos confirmados, cancelamentos por "
    "unidade. Faca a pergunta em portugues, com periodo se relevante (ex.: 'ultimos 30 "
    "dias')."
)

OUT_OF_SCOPE_RESPONSE = (
    "Sua pergunta nao parece relacionada a fila de regulacao do SISREG-DF. Posso te "
    "ajudar com: top CIDs em uma janela, distribuicao de status, agendamentos, "
    "cancelamentos, top unidades solicitantes. Reformule por favor."
)


def _plan_with_retry(pergunta: str, request_id: str) -> dict[str, Any]:
    """Roda planner+validator em loop ate approve ou max_attempts."""
    feedback: str | None = None
    last_validation = None
    for attempt in range(1, settings.max_planner_attempts + 1):
        plan_result = planner.plan(pergunta, feedback=feedback)
        audit.event(
            "planner.completed",
            request_id=request_id,
            attempt=attempt,
            template=plan_result.template_name,
            params=plan_result.params,
            planner_version=planner.version(),
            had_feedback=feedback is not None,
        )
        if not plan_result.matched:
            return {
                "status": "no_template_match",
                "rationale": plan_result.rationale,
                "attempt": attempt,
            }

        template = registry.get(plan_result.template_name)
        try:
            params = template.Params(**plan_result.params)
            body = template.render(params)
            indice = template.index(params)
        except (ValidationError, ValueError) as exc:
            audit.event(
                "planner.params_invalid",
                request_id=request_id,
                attempt=attempt,
                template=plan_result.template_name,
                error=str(exc),
            )
            feedback = (
                f"Os parametros que voce passou para o template '{plan_result.template_name}' "
                f"foram rejeitados pela validacao: {exc}. "
                "Reanalise se este e mesmo o template certo — talvez precise usar "
                "free_text_search em vez deste."
            )
            continue
        audit.event(
            "es.query.rendered",
            request_id=request_id,
            attempt=attempt,
            template=plan_result.template_name,
            indice=indice,
            body=body,
        )

        validation = validator.validate(
            pergunta=pergunta,
            template_name=plan_result.template_name,
            params=params.model_dump(),
            indice_resolvido=indice,
            body=body,
        )
        revised_dsl = validation.revised_dsl()
        audit.event(
            "validator.completed",
            request_id=request_id,
            attempt=attempt,
            decision=validation.decision.value,
            reasoning=validation.reasoning,
            concerns=validation.concerns,
            revised=revised_dsl is not None,
            validator_version=validator.version(),
        )
        last_validation = validation

        if validation.decision.value == "approve":
            return {
                "status": "approved",
                "template": template,
                "template_name": plan_result.template_name,
                "params": params,
                "body": body,
                "indice": indice,
                "validation": validation,
                "attempt": attempt,
            }

        if validation.decision.value == "revise":
            if plan_result.template_name != free_text_search.NAME:
                # Templates especializados nao aceitam revisao automatica
                return {
                    "status": "rejected_no_revise",
                    "validation": validation,
                    "attempt": attempt,
                }
            if not revised_dsl:
                return {
                    "status": "revise_without_dsl",
                    "validation": validation,
                    "attempt": attempt,
                }
            safety.validate(revised_dsl)
            return {
                "status": "approved",
                "template": template,
                "template_name": plan_result.template_name,
                "params": params,
                "body": revised_dsl,
                "indice": indice,
                "validation": validation,
                "attempt": attempt,
            }

        # decision == reject -> proxima iteracao com feedback
        feedback = validation.reasoning

    # Esgotou attempts
    return {
        "status": "rejected_max_attempts",
        "validation": last_validation,
        "attempt": settings.max_planner_attempts,
    }


def _narrate_with_retry(
    pergunta: str,
    dados: dict[str, Any],
    proveniencia: dict[str, Any],
    pii_exposure: bool,
    request_id: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Roda narrator+critic em loop ate approve ou max_attempts.

    Retorna (narrativa_final, lista_de_critiques_em_ordem).
    """
    issues_feedback: list[str] | None = None
    critiques: list[dict[str, Any]] = []
    narrativa = ""
    for attempt in range(1, settings.max_narrator_attempts + 1):
        narrativa = narrator.narrate(
            pergunta,
            dados,
            proveniencia,
            pii_exposure=pii_exposure,
            feedback_issues=issues_feedback,
        )
        audit.event(
            "narrator.completed",
            request_id=request_id,
            attempt=attempt,
            narrator_version=narrator.version(),
            had_feedback=issues_feedback is not None,
        )
        critique = critic.review(pergunta, narrativa, proveniencia)
        audit.event(
            "critic.completed",
            request_id=request_id,
            attempt=attempt,
            decision=critique.decision.value,
            issues=critique.issues,
            reasoning=critique.reasoning,
            critic_version=critic.version(),
        )
        critiques.append(
            {
                "attempt": attempt,
                "decision": critique.decision.value,
                "issues": critique.issues,
                "reasoning": critique.reasoning,
            }
        )
        if critique.decision.value == "approve":
            break
        issues_feedback = critique.issues
    return narrativa, critiques


def ask(pergunta: str, *, pii_exposure: bool = False, justificativa: str = "") -> dict[str, Any]:
    """Loop completo multi-agente: NL -> ... -> resposta narrada e revisada."""
    request_id = audit.event("request.received", pergunta=pergunta, pii_exposure=pii_exposure)

    # PII override (constituicao P2 POC)
    if pii_exposure:
        if settings.app_mode != "poc":
            raise EngineError("pii_exposure=True so e permitido em app_mode='poc'.")
        if date.today() > settings.poc_expires_at:
            raise EngineError(
                f"Modo POC expirou em {settings.poc_expires_at}. "
                "Migre para producao (ver constituicao P2/P8)."
            )
        if not justificativa or len(justificativa.strip()) < 20:
            raise EngineError("pii_exposure=True exige justificativa textual com >=20 chars.")

    # ===== AGENT 1: ROUTER =====
    routing = router.classify(pergunta)
    audit.event(
        "router.completed",
        request_id=request_id,
        intent=routing.intent.value,
        needs_pii=routing.needs_pii,
        reasoning=routing.reasoning,
        router_version=router.version(),
    )

    if routing.intent == Intent.META:
        audit.event("request.completed", request_id=request_id, short_circuit="meta")
        return {
            "narrativa": META_RESPONSE,
            "dados": None,
            "proveniencia": {"request_id": request_id, "intent": "meta"},
        }
    if routing.intent == Intent.OUT_OF_SCOPE:
        audit.event("request.completed", request_id=request_id, short_circuit="out_of_scope")
        return {
            "narrativa": OUT_OF_SCOPE_RESPONSE,
            "dados": None,
            "proveniencia": {"request_id": request_id, "intent": "out_of_scope"},
        }

    if routing.needs_pii and not pii_exposure:
        audit.event("request.completed", request_id=request_id, short_circuit="needs_pii_no_consent")
        return {
            "narrativa": (
                "Sua pergunta parece exigir dados individuais identificaveis. "
                "Para esse caminho, o operador precisa rodar com pii_exposure=True "
                "e justificativa textual (ver constituicao P2 — POC override)."
            ),
            "dados": None,
            "proveniencia": {
                "request_id": request_id,
                "intent": "data_query",
                "needs_pii": True,
                "block_reason": "pii_not_consented",
            },
        }

    # ===== AGENTS 2+3: PLANNER + VALIDATOR (com retry) =====
    plan_outcome = _plan_with_retry(pergunta, request_id)

    if plan_outcome["status"] == "no_template_match":
        audit.event("request.completed", request_id=request_id, short_circuit="no_template")
        return {
            "narrativa": (
                f"Nao consigo responder isso ainda. Detalhe do planner: {plan_outcome['rationale']}"
            ),
            "dados": None,
            "proveniencia": {"request_id": request_id, "template_matched": False},
        }
    if plan_outcome["status"] != "approved":
        validation = plan_outcome.get("validation")
        reasoning = validation.reasoning if validation else "sem motivo registrado"
        audit.event(
            "request.completed",
            request_id=request_id,
            short_circuit=plan_outcome["status"],
        )
        return {
            "narrativa": (
                f"O validador rejeitou a query apos {plan_outcome['attempt']} tentativa(s).\n\n"
                f"Motivo final: {reasoning}\n\n"
                "Sugestao: reformule a pergunta com mais especificidade."
            ),
            "dados": None,
            "proveniencia": {
                "request_id": request_id,
                "validacao_final": {
                    "decision": validation.decision.value if validation else "unknown",
                    "reasoning": reasoning,
                    "concerns": validation.concerns if validation else [],
                    "attempts": plan_outcome["attempt"],
                },
            },
        }

    template = plan_outcome["template"]
    params = plan_outcome["params"]
    body = plan_outcome["body"]
    indice = plan_outcome["indice"]
    validation = plan_outcome["validation"]

    # ===== MECÂNICO: ES execute + anonymize =====
    with SisregESClient() as es:
        es_response = es.search(indice, body)
    audit.event(
        "es.query.executed",
        request_id=request_id,
        took_ms=es_response.get("took"),
        total=es_response.get("hits", {}).get("total"),
    )

    consolidated = template.consolidate(es_response, params)
    consolidated_clean = scrub(consolidated, mode=settings.app_mode, pii_exposure=pii_exposure)

    # ===== Proveniência =====
    proveniencia: dict[str, Any] = {
        "request_id": request_id,
        "intent": routing.intent.value,
        "template": plan_outcome["template_name"],
        "indice": indice,
        "params": params.model_dump(),
        "modo": settings.app_mode,
        "modo_expira_em": str(settings.poc_expires_at) if settings.app_mode == "poc" else None,
        "router_version": router.version(),
        "planner_version": planner.version(),
        "validator_version": validator.version(),
        "narrator_version": narrator.version(),
        "critic_version": critic.version(),
        "pii_exposure": pii_exposure,
        "planner_attempts": plan_outcome["attempt"],
        "validacao": {
            "decision": validation.decision.value,
            "reasoning": validation.reasoning,
            "concerns": validation.concerns,
        },
    }

    # ===== AGENTS 4+5: NARRATOR + CRITIC (com retry) =====
    narrativa, critiques = _narrate_with_retry(
        pergunta=pergunta,
        dados=consolidated_clean,
        proveniencia=proveniencia,
        pii_exposure=pii_exposure,
        request_id=request_id,
    )
    proveniencia["critic_attempts"] = len(critiques)
    proveniencia["critiques"] = critiques
    proveniencia["pii_auditor_version"] = pii_auditor.version()

    # ===== CAMADA EXTRA: PII Scanner mecanico + PII Auditor LLM =====
    pii_scan = scanner.scan(narrativa)
    audit.event(
        "pii.scanner.completed",
        request_id=request_id,
        findings=pii_scan,
        any_match=bool(pii_scan),
    )
    proveniencia["pii_scanner"] = {"findings": pii_scan, "any_match": bool(pii_scan)}

    # Auditor LLM so roda quando expectativa e "sem PII" — defesa em profundidade.
    if settings.app_mode == "poc" and not pii_exposure:
        pii_audit = pii_auditor.audit(narrativa, proveniencia)
        audit.event(
            "pii.auditor.completed",
            request_id=request_id,
            decision=pii_audit.decision.value,
            leaks=pii_audit.leaks,
            reasoning=pii_audit.reasoning,
        )
        proveniencia["pii_auditor"] = {
            "decision": pii_audit.decision.value,
            "leaks": pii_audit.leaks,
            "reasoning": pii_audit.reasoning,
        }
        if pii_audit.decision.value == "leak_detected":
            audit.event(
                "request.blocked_pii_leak",
                request_id=request_id,
                leaks=pii_audit.leaks,
            )
            return {
                "narrativa": (
                    "Resposta bloqueada pela auditoria final de PII. "
                    "Detalhes em audit (request_id no campo proveniencia)."
                ),
                "dados": None,
                "proveniencia": proveniencia,
            }

    audit.event("request.completed", request_id=request_id)
    return {
        "narrativa": narrativa,
        "dados": consolidated_clean,
        "proveniencia": proveniencia,
    }
