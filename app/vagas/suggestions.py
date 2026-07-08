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


def build(resp: "VagasResponse") -> list[dict]:
    """Ate 4 sugestoes contextuais. Vazio se nao houve resposta com dado."""
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
