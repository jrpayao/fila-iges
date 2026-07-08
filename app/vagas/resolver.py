"""Resolucao de entidades do motor de vagas — data-driven (contra o DataFrame).

Diferente da fonte legada (dicionarios externos de CID/unidade), aqui os valores
canonicos VIVEM no proprio dado: os nomes de procedimento e hospital vem da API.
Entao resolvemos texto livre contra os valores distintos do DataFrame.

Levanta AmbiguityError / UnresolvedError (P10) — reaproveitadas do resolver v2.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pandas as pd

from app.agent.resolver import AmbiguityError, UnresolvedError  # reuso das excecoes P10

_TOKEN = re.compile(r"[a-z0-9]+")
_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}


def _norm(s: str) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    nfkd = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(_norm(text)) if len(t) >= 3]


# ===== Competencia =====


@dataclass(frozen=True)
class ResolvedCompetencia:
    mes: int
    ano: int

    @property
    def key(self) -> int:
        return self.ano * 100 + self.mes

    @property
    def label(self) -> str:
        return f"{self.mes:02d}/{self.ano}"


def available_competencias(df: pd.DataFrame) -> list[ResolvedCompetencia]:
    keys = sorted({int(k) for k in df["competencia"].dropna().unique()})
    return [ResolvedCompetencia(mes=k % 100, ano=k // 100) for k in keys]


def latest_competencia(df: pd.DataFrame) -> ResolvedCompetencia:
    comps = available_competencias(df)
    if not comps:
        raise UnresolvedError("competencia", "", suggestions=["Cache vazio — rode o sync."])
    return comps[-1]


def resolve_competencia(raw: str | None, df: pd.DataFrame) -> ResolvedCompetencia:
    """Texto -> ResolvedCompetencia. Default (raw vazio / 'atual') = mais recente."""
    avail = {c.key: c for c in available_competencias(df)}
    if not raw or _norm(raw) in {"atual", "atualmente", "agora", "mais recente", "ultima", "ultimo mes", "corrente"}:
        return latest_competencia(df)

    n = _norm(raw)
    mes = ano = None

    m = re.search(r"\b(\d{4})[-/](\d{1,2})\b", n)          # 2026-07 / 2026/7
    if m:
        ano, mes = int(m.group(1)), int(m.group(2))
    if mes is None:
        m = re.search(r"\b(\d{1,2})[-/](\d{4})\b", n)      # 07/2026
        if m:
            mes, ano = int(m.group(1)), int(m.group(2))
    if mes is None:
        m = re.search(r"\b(\d{6})\b", n)                   # 202607
        if m:
            ano, mes = int(m.group(1)[:4]), int(m.group(1)[4:])
    if mes is None:                                         # "julho de 2026"
        for nome, num in _MESES.items():
            if nome in n:
                mes = num
                break
        ma = re.search(r"\b(20\d{2})\b", n)
        if ma:
            ano = int(ma.group(1))
        if mes is not None and ano is None:
            ano = latest_competencia(df).ano  # assume ano corrente disponivel

    if mes is None or ano is None:
        raise UnresolvedError(
            "competencia", raw,
            suggestions=[f"{c.mes:02d}/{c.ano}" for c in list(avail.values())[-6:]],
        )
    key = ano * 100 + mes
    if key not in avail:
        raise UnresolvedError(
            "competencia", raw,
            suggestions=[f"Sem dados para {mes:02d}/{ano}."]
            + [f"{c.mes:02d}/{c.ano}" for c in list(avail.values())[-6:]],
        )
    return avail[key]


# ===== Procedimento =====

_CODE_RE = re.compile(r"\b(\d{7,10})\b")


@dataclass(frozen=True)
class ResolvedProcedimento:
    valor: str  # nome canonico exato como aparece no dado


def resolve_procedimento(raw: str, df: pd.DataFrame) -> ResolvedProcedimento:
    """Codigo SIGTAP OU nome livre -> nome canonico do procedimento."""
    universe = df["procedimento"].dropna().unique().tolist()

    # 1) Codigo SIGTAP (bate no cod_procedimento OU no codigo dentro do nome)
    m = _CODE_RE.search(raw)
    if m:
        code = m.group(1)
        hit = df[df["cod_procedimento"].astype(str) == code]["procedimento"].unique().tolist()
        if len(hit) == 1:
            return ResolvedProcedimento(hit[0])
        if len(hit) > 1:
            raise AmbiguityError("procedimento", raw, hit[:8])

    # 2) Nome livre: todos os tokens presentes na descricao
    toks = _tokens(raw)
    if not toks:
        raise UnresolvedError("procedimento", raw, suggestions=universe[:5])
    matches = [p for p in universe if all(t in _norm(p) for t in toks)]
    if len(matches) == 1:
        return ResolvedProcedimento(matches[0])
    if len(matches) > 1:
        # desempate: match exato do nome normalizado
        exact = [p for p in matches if _norm(p) == _norm(raw)]
        if len(exact) == 1:
            return ResolvedProcedimento(exact[0])
        raise AmbiguityError("procedimento", raw, matches[:8])
    raise UnresolvedError("procedimento", raw, suggestions=universe[:5])


# ===== Hospital =====


@dataclass(frozen=True)
class ResolvedHospital:
    nome: str
    cnes: str | None = None


# Siglas informais dos hospitais publicos do IGES presentes no dado de vagas.
# alias normalizado -> CNES (a resolucao confere se o CNES existe no DataFrame).
HOSPITAL_ALIASES: dict[str, str] = {
    "hub": "0010510", "universitario": "0010510",
    "hbdf": "0010456", "hb": "0010456", "base": "0010456", "hospital de base": "0010456",
    "hmib": "0010537", "materno infantil": "0010537", "materno": "0010537",
    "hcb": "6876617", "hospital da crianca": "6876617", "crianca": "6876617",
    "hab": "2649527", "hospital de apoio": "2649527", "apoio": "2649527",
    "ictdf": "3276678", "instituto de cardiologia": "3276678", "cardiologia": "3276678",
    "crdf": "3044432", "complexo regulador": "3044432", "regulador": "3044432",
}


def resolve_hospital(raw: str, df: pd.DataFrame) -> ResolvedHospital:
    """CNES OU nome/sigla/alias livre -> hospital canonico."""
    pairs = df[["hospital_cnes", "hospital"]].drop_duplicates()

    stripped = raw.strip()
    by_cnes = pairs[pairs["hospital_cnes"].astype(str) == stripped]
    if len(by_cnes) >= 1:
        row = by_cnes.iloc[0]
        return ResolvedHospital(nome=row["hospital"], cnes=str(row["hospital_cnes"]))

    n = _norm(raw)

    # Sigla/alias conhecido -> CNES (se presente no dado)
    if n in HOSPITAL_ALIASES:
        cnes = HOSPITAL_ALIASES[n]
        hit = pairs[pairs["hospital_cnes"].astype(str) == cnes]
        if len(hit) >= 1:
            row = hit.iloc[0]
            return ResolvedHospital(nome=row["hospital"], cnes=str(row["hospital_cnes"]))
    names = pairs["hospital"].dropna().unique().tolist()
    subs = [h for h in names if n and n in _norm(h)]
    if len(subs) == 1:
        cnes = pairs[pairs["hospital"] == subs[0]]["hospital_cnes"].iloc[0]
        return ResolvedHospital(nome=subs[0], cnes=str(cnes))
    if len(subs) > 1:
        raise AmbiguityError("hospital", raw, subs[:8])

    # tokens (ex.: "universitario brasilia")
    toks = _tokens(raw)
    if toks:
        tok_matches = [h for h in names if all(t in _norm(h) for t in toks)]
        if len(tok_matches) == 1:
            cnes = pairs[pairs["hospital"] == tok_matches[0]]["hospital_cnes"].iloc[0]
            return ResolvedHospital(nome=tok_matches[0], cnes=str(cnes))
        if len(tok_matches) > 1:
            raise AmbiguityError("hospital", raw, tok_matches[:8])

    raise UnresolvedError("hospital", raw, suggestions=names[:5])
