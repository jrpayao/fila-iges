"""Sugestoes de acompanhamento — os proximos passos clicaveis apos uma resposta.

Ex.: apos "Quantas vagas no HUB?" -> "Evolucao mes a mes", "Quanto esta bloqueado",
"Mix por tipo de vaga", "Comparar com outros hospitais".

Deterministico (sem LLM): deriva do que acabou de ser respondido (metric + filtros +
shape). Cada sugestao tem `label` (chip curto) e `question` (a pergunta completa, com
escopo explicito, para nao depender de estado externo).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.vagas.orchestrator import VagasResponse

_MAX = 4


def _short_proc(proc: str) -> str:
    """'GRUPO - 7.RESSONANCIA MAGNETICA (3104000) [FISICO]' -> 'ressonancia magnetica'."""
    s = re.sub(r"\[[^\]]*\]", "", proc)          # tira [FISICO]
    s = re.sub(r"\([^)]*\)", "", s)               # tira (codigo)
    s = re.sub(r"^\s*GRUPO\s*-\s*", "", s, flags=re.I)
    s = re.sub(r"^\s*\d+\.\s*", "", s)            # tira '7.'
    return s.strip().lower() or proc


def _escopo(hosp: str | None, proc_short: str | None) -> str:
    if hosp and proc_short:
        return f"de {proc_short} no {hosp}"
    if hosp:
        return f"no {hosp}"
    if proc_short:
        return f"de {proc_short}"
    return ""


def _rules(resp: "VagasResponse") -> list[dict]:
    """Fallback deterministico: ate 4 sugestoes contextuais (sem LLM)."""
    env = resp.envelope
    if env is None:
        return []
    f = env.filters or {}
    hosp = f.get("hospital")
    proc = f.get("procedimento")
    proc_short = _short_proc(proc) if proc else None
    metric = env.metric
    shape = env.shape.value
    esc = _escopo(hosp, proc_short)
    esc_sp = f" {esc}" if esc else ""

    cands: list[tuple[str, str]] = []

    # Temporal (sempre util quando nao for ja uma serie)
    if shape != "timeseries":
        cands.append(("📈 Evolução mês a mês", f"Mostre a evolução da oferta{esc_sp} ao longo dos meses."))

    # Bloqueio
    if metric != "taxa_bloqueio":
        cands.append(("🔒 Quanto está bloqueado", f"Qual a taxa de bloqueio das vagas{esc_sp}?"))

    # Mix por tipo de vaga
    if metric != "mix_tipo_vaga":
        cands.append(("🧩 Mix por tipo de vaga", f"Qual a distribuição por tipo de vaga (1ª vez, retorno, reserva){esc_sp}?"))

    # Especificas de hospital
    if hosp and shape == "scalar":
        cands.append(("🏥 Procedimentos nesse hospital", f"Quais procedimentos o {hosp} mais oferta?"))
        cands.append(("⚖️ Comparar com outros hospitais", f"Como o {hosp} se compara aos outros hospitais em vagas?"))

    # Especificas de procedimento (sem hospital)
    if proc_short and not hosp:
        cands.append(("🏥 Quais hospitais ofertam", f"Quais hospitais ofertam {proc_short}?"))

    # Panorama (fecho estrategico)
    if metric != "panorama":
        cands.append(("🗺️ Panorama da rede", "Me dá um panorama executivo da rede de vagas."))

    # dedupe por pergunta, cap
    seen: set[str] = set()
    out: list[dict] = []
    for label, q in cands:
        if q in seen:
            continue
        seen.add(q)
        out.append({"label": label, "question": q})
        if len(out) >= _MAX:
            break
    return out


# ===== Geracao por LLM (com fallback para as regras) =====


class _Suggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(..., description="Chip curto e amigavel, com 1 emoji no inicio (<= ~28 chars).")
    question: str = Field(..., description="Pergunta completa e autossuficiente em pt-BR, no escopo de vagas.")


class _SuggestionList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sugestoes: list[_Suggestion]


_SUGGEST_SYSTEM = """\
Voce propoe de 3 a 4 PERGUNTAS DE ACOMPANHAMENTO para um chat sobre a OFERTA DE VAGAS
SISREG (capacidade) da rede IGES-DF. O objetivo e guiar o gestor ao proximo passo natural.

O que o chat SABE responder (so isso):
- oferta/total de vagas; vagas ativas; vagas bloqueadas; taxa de bloqueio.
- mix por tipo de vaga (1a vez / retorno / reserva).
- evolucao mensal (serie temporal); ranking por procedimento ou por hospital.
- comparacao entre hospitais; procedimentos com poucos ofertantes (monofornecedores).
- oportunidade de desbloqueio (onde ha mais vagas travadas); panorama executivo da rede.

REGRAS:
- NUNCA proponha tempo de espera, tamanho de fila, demanda, faltas ou conduta clinica — a fonte NAO tem.
- Cada sugestao: um `label` curto com 1 emoji + uma `question` completa e autossuficiente em pt-BR.
- Mantenha o ESCOPO do que foi perguntado (hospital / procedimento / competencia) quando fizer sentido.
- NAO repita o que a resposta ja mostrou; proponha aprofundar, cruzar dimensao, ou comparar no tempo.
- Perguntas curtas, acionaveis e realmente respondiveis pelo chat.

SEJA ESPECIFICO (isto e o mais importante — evita sugestoes genericas e repetitivas):
- Use NOMES e NUMEROS que aparecem na resposta. Se ha `principais_itens`, sugira mergulhar
  num deles pelo nome (ex.: "Ver o DIAGNOSTICO CLINICA DE IMAGENS em detalhe").
- Se a narrativa cita uma variacao (ex.: caiu 36%), proponha investigar a causa
  ("Qual hospital puxou a queda de 36%?").
- VARIE os angulos entre as respostas — nao devolva sempre as mesmas 4 sugestoes.
- No maximo 1 sugestao generica (tipo panorama); as outras devem ser ancoradas no conteudo.
"""


def _llm(resp: "VagasResponse") -> list[dict]:
    """Gera sugestoes com o LLM (narrator). Retorna [] em qualquer falha (cai no fallback)."""
    env = resp.envelope
    if env is None:
        return []
    import json

    from openai import OpenAI

    from app.config import settings

    # Entidades concretas da resposta -> ajudam o LLM a sugerir mergulhos especificos.
    itens: list = []
    data = env.data or []
    if env.shape.value == "breakdown":
        itens = [b.get("key") for b in data[:5] if b.get("key")]
    elif env.shape.value == "comparison" and data:
        foc = data[0].get("focus", {}) or {}
        itens = [foc.get("key")] + [b.get("key") for b in (data[0].get("benchmark") or [])[:3]]
        itens = [x for x in itens if x]

    payload = {
        "pergunta": resp.pergunta,
        "metric": env.metric,
        "shape": env.shape.value,
        "filtros": env.filters,
        "principais_itens": itens,
        "narrativa": (resp.narrativa or "")[:600],
    }
    client = OpenAI(api_key=settings.openai_api_key)
    r = client.beta.chat.completions.parse(
        model=settings.openai_narrator_model,
        messages=[
            {"role": "system", "content": _SUGGEST_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ],
        response_format=_SuggestionList,
        temperature=0.8,
    )
    parsed = r.choices[0].message.parsed
    if not parsed or not parsed.sugestoes:
        return []
    seen: set[str] = set()
    out: list[dict] = []
    for s in parsed.sugestoes:
        q = (s.question or "").strip()
        lbl = (s.label or "").strip()
        if not q or q in seen:
            continue
        seen.add(q)
        out.append({"label": lbl or q[:28], "question": q})
        if len(out) >= _MAX:
            break
    return out


def build(resp: "VagasResponse") -> list[dict]:
    """Sugestoes de acompanhamento: LLM primeiro, regras deterministicas como fallback."""
    if resp.envelope is None:
        return []
    try:
        via_llm = _llm(resp)
        if via_llm:
            return via_llm
    except Exception:
        pass  # LLM indisponivel/erro -> fallback silencioso
    return _rules(resp)
