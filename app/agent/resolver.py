"""Resolucao de Entidades — Spec §3.

Mapeia texto livre do usuario para chaves canonicas dos indices SISREG.
Lanca AmbiguityError ou UnresolvedError quando precisa de clarificacao (P10).

NAO faz match contra o ES diretamente — usa dicionarios locais. CID livre
('diabetes') exige tabela de referencia CID-10 (TODO em fase posterior).
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

_CID10_JSON_PATH = Path(__file__).parent / "data" / "cid10.json"
_UNIDADES_JSON_PATH = Path(__file__).parent / "data" / "unidades.json"
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


# ===== Excecoes de resolucao (P10 — disparam clarificacao na UI) =====


class ResolutionError(Exception):
    """Base — algum termo nao se resolveu."""


class UnresolvedError(ResolutionError):
    """Termo nao bateu com nada no dicionario. Sugerir alternativas se possivel."""

    def __init__(self, kind: str, raw: str, suggestions: list[str] | None = None) -> None:
        self.kind = kind
        self.raw = raw
        self.suggestions = suggestions or []
        super().__init__(f"{kind}: '{raw}' nao resolveu. Sugestoes: {suggestions}")


class AmbiguityError(ResolutionError):
    """Multiplos candidatos validos — clarificacao obrigatoria."""

    def __init__(self, kind: str, raw: str, candidates: list[str]) -> None:
        self.kind = kind
        self.raw = raw
        self.candidates = candidates
        super().__init__(f"{kind}: '{raw}' ambiguo entre {candidates}.")


# ===== Vocabulario fechado =====


# ---- 3.2 Prioridade ----
_PRIORIDADE_MAP: dict[str, str] = {
    # variantes para codigo_classificacao_risco
    "emergencia": "1",
    "emergência": "1",
    "p0": "1",
    "prioridade 0": "1",
    "urgencia": "2",
    "urgência": "2",
    "p1": "2",
    "prioridade 1": "2",
    "nao urgente": "3",
    "não urgente": "3",
    "p2": "3",
    "prioridade 2": "3",
    "eletivo": "4",
    "eletiva": "4",
    "p3": "4",
    "prioridade 3": "4",
}

PRIORIDADE_DESCRICAO: dict[str, str] = {
    "1": "Prioridade 0 — Emergência",
    "2": "Prioridade 1 — Urgência",
    "3": "Prioridade 2 — Não urgente",
    "4": "Prioridade 3 — Eletivo",
}


# ---- 3.4 Grupos de status (ambulatorial) ----
STATUS_GROUPS: dict[str, list[str]] = {
    "fila": [
        "SOLICITAÇÃO / PENDENTE / FILA DE ESPERA",
        "SOLICITAÇÃO / PENDENTE / REGULADOR",
        "SOLICITAÇÃO / REENVIADA / REGULADOR",
    ],
    "pendente": [
        "SOLICITAÇÃO / PENDENTE / FILA DE ESPERA",
        "SOLICITAÇÃO / PENDENTE / REGULADOR",
        "SOLICITAÇÃO / REENVIADA / REGULADOR",
    ],
    "agendado": [
        "SOLICITAÇÃO / AGENDADA / SOLICITANTE",
        "SOLICITAÇÃO / AGENDADA / COORDENADOR",
        "SOLICITAÇÃO / AGENDADA / FILA DE ESPERA",
        "SOLICITAÇÃO / AUTORIZADA / REGULADOR",
        "AGENDAMENTO / PENDENTE CONFIRMAÇÃO / EXECUTANTE",
    ],
    "atendido": ["AGENDAMENTO / CONFIRMADO / EXECUTANTE"],
    "confirmado": ["AGENDAMENTO / CONFIRMADO / EXECUTANTE"],
    "falta": ["AGENDAMENTO / FALTA / EXECUTANTE"],
    "cancelado": [
        "SOLICITAÇÃO / CANCELADA / SOLICITANTE",
        "SOLICITAÇÃO / CANCELADA / REGULADOR",
        "SOLICITAÇÃO / CANCELADA / COORDENADOR",
        "AGENDAMENTO / CANCELADO / REGULADOR",
        "AGENDAMENTO / CANCELADO / SOLICITANTE",
        "AGENDAMENTO / CANCELADO / COORDENADOR",
        "SOLICITAÇÃO / NEGADA / REGULADOR",
        "SOLICITAÇÃO / DEVOLVIDA / REGULADOR",
    ],
    "negado": ["SOLICITAÇÃO / NEGADA / REGULADOR"],
    "devolvido": ["SOLICITAÇÃO / DEVOLVIDA / REGULADOR"],
}


# ---- 3.1 Unidades — catalogo oficial CGRA/SES-DF (data/unidades.json) ----
@dataclass(frozen=True)
class UnidadeRef:
    nome_oficial: str
    cnes: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)


# Aliases adicionais por CNES (alem da sigla oficial do JSON).
# Usuarios usam variantes informais — mapeie aqui sem mexer no JSON.
_ALIASES_EXTRA: dict[str, tuple[str, ...]] = {
    "0010456": ("HB", "Base", "Hospital de Base"),
    "0010499": ("Taguatinga", "Hospital Regional de Taguatinga"),
    "0010510": ("Universitario",),
    "0010464": ("Asa Norte", "Hospital Regional da Asa Norte"),
    "0010480": ("Ceilandia", "Hospital Regional de Ceilandia"),
    "0010472": ("Gama", "Hospital Regional do Gama"),
    "2814897": ("HRGU", "HR Guara", "Hospital Regional do Guara"),
    "0010529": ("Planaltina", "Hospital Regional de Planaltina"),
    "0010502": ("Sobradinho", "Hospital Regional de Sobradinho"),
    "0010545": ("Brazlandia", "Hospital Regional de Brazlandia"),
    "2672197": ("Samambaia", "Hospital Regional de Samambaia"),
    "5717515": ("Santa Maria", "Hospital Regional de Santa Maria"),
    "2645157": ("Paranoa", "Hospital Regional do Paranoa"),
    "0010537": ("Materno Infantil", "Hospital Materno Infantil"),
    "6876617": ("Hospital da Crianca", "HCB"),
}


@lru_cache(maxsize=1)
def _unidades_data() -> list[UnidadeRef]:
    """Carrega 300+ unidades canonicas do CGRA/SES-DF a partir do JSON oficial."""
    if not _UNIDADES_JSON_PATH.exists():
        return []
    raw = json.loads(_UNIDADES_JSON_PATH.read_text(encoding="utf-8"))
    out: list[UnidadeRef] = []
    for entry in raw:
        codigo = entry.get("codigo")
        nome = entry.get("nome") or ""
        sigla = entry.get("sigla") or ""
        aliases: list[str] = []
        if sigla:
            aliases.append(sigla)
        if codigo and codigo in _ALIASES_EXTRA:
            aliases.extend(_ALIASES_EXTRA[codigo])
        out.append(UnidadeRef(nome_oficial=nome, cnes=codigo, aliases=tuple(aliases)))
    return out


@lru_cache(maxsize=1)
def _unidades_by_alias() -> dict[str, list[UnidadeRef]]:
    """Indice O(1): alias normalizado -> lista de UnidadeRef (>1 = ambiguo).

    Dedup por CNES: a mesma unidade nao aparece duas vezes mesmo se tiver
    multiplos aliases que normalizam para a mesma key.
    """
    idx: dict[str, list[UnidadeRef]] = {}
    seen: dict[str, set[str | None]] = {}
    for u in _unidades_data():
        for alias in u.aliases:
            key = _norm(alias)
            if not key:
                continue
            seen_for_key = seen.setdefault(key, set())
            if u.cnes in seen_for_key:
                continue
            seen_for_key.add(u.cnes)
            idx.setdefault(key, []).append(u)
    return idx


@lru_cache(maxsize=1)
def _unidades_by_cnes() -> dict[str, UnidadeRef]:
    """Indice O(1): cnes string -> UnidadeRef."""
    return {u.cnes: u for u in _unidades_data() if u.cnes}


# Compat: codigo legacy que pode ser referenciado em outro lugar (lista crua).
# Vazia na pratica — UNIDADES_DF agora vem do JSON via _unidades_data().
def _all_unidades() -> list[UnidadeRef]:
    return _unidades_data()


# ===== Resultados =====


@dataclass(frozen=True)
class ResolvedUnit:
    nome_oficial: str
    cnes: str | None
    matched_via: str  # "alias" | "fuzzy:<token>"


@dataclass(frozen=True)
class ResolvedPriority:
    codigo: str
    descricao: str


@dataclass(frozen=True)
class ResolvedStatusGroup:
    grupo: str
    valores: list[str]


@dataclass(frozen=True)
class ResolvedCID:
    codigo: str
    descricao: str | None = None


# ===== Helpers internos =====


def _norm(s: str) -> str:
    """Normaliza para comparacao: lower + sem acento + sem espaco extra."""
    if not s:
        return ""
    s = s.strip().lower()
    nfkd = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _tokens(text: str) -> list[str]:
    """Tokens normalizados (ascii) com tamanho >= 3."""
    norm = _norm(text)
    return [t for t in _TOKEN_PATTERN.findall(norm) if len(t) >= 3]


_CID_PATTERN = re.compile(r"^[A-Z]\d{2,3}$", re.IGNORECASE)


# ===== CID-10 BR (DATASUS) — carregado de app/agent/data/cid10.json =====


@lru_cache(maxsize=1)
def _cid10_data() -> dict[str, str]:
    """Catalogo CID-10 completo: {codigo: descricao}.

    Inclui 3-char (CAT) e 4-char (SUBCAT). 14k+ entradas. ~50ms de load.
    """
    if not _CID10_JSON_PATH.exists():
        return {}
    return json.loads(_CID10_JSON_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _cid10_search_index() -> dict[str, list[str]]:
    """Indice invertido: token normalizado -> lista de codigos cuja descricao contem o token.

    Construido uma unica vez no primeiro uso.
    """
    index: dict[str, list[str]] = {}
    for code, desc in _cid10_data().items():
        for token in _tokens(desc):
            index.setdefault(token, []).append(code)
    return index


# ===== API publica =====


def resolve_prioridade(raw: str) -> ResolvedPriority:
    """Texto livre -> ResolvedPriority. Levanta UnresolvedError."""
    key = _norm(raw)
    codigo = _PRIORIDADE_MAP.get(key)
    if not codigo:
        # tentar so o token principal
        token = key.split()[0] if key else ""
        codigo = _PRIORIDADE_MAP.get(token)
    if not codigo:
        raise UnresolvedError(
            "prioridade",
            raw,
            suggestions=["emergência (P0)", "urgência (P1)", "não urgente (P2)", "eletivo (P3)"],
        )
    return ResolvedPriority(codigo=codigo, descricao=PRIORIDADE_DESCRICAO[codigo])


def resolve_status_grupo(raw: str) -> ResolvedStatusGroup:
    """Texto livre -> ResolvedStatusGroup."""
    key = _norm(raw)
    valores = STATUS_GROUPS.get(key)
    if not valores:
        raise UnresolvedError(
            "status_grupo",
            raw,
            suggestions=sorted(STATUS_GROUPS.keys()),
        )
    return ResolvedStatusGroup(grupo=key, valores=valores)


def resolve_unidade(raw: str) -> ResolvedUnit:
    """Texto livre -> ResolvedUnit. CNES direto > alias O(1) > fuzzy substring no nome."""
    if not raw or not raw.strip():
        raise UnresolvedError("unidade", raw)

    # 1. CNES direto (string numerica que existe no catalogo)
    stripped = raw.strip()
    by_cnes = _unidades_by_cnes()
    if stripped in by_cnes:
        u = by_cnes[stripped]
        return ResolvedUnit(nome_oficial=u.nome_oficial, cnes=u.cnes, matched_via="cnes")

    norm = _norm(raw)

    # 2. Alias exato (sigla oficial OU alias extra) via indice O(1)
    by_alias = _unidades_by_alias()
    hits = by_alias.get(norm) or []
    if len(hits) == 1:
        u = hits[0]
        return ResolvedUnit(nome_oficial=u.nome_oficial, cnes=u.cnes, matched_via="alias")
    if len(hits) > 1:
        # Mesma sigla em multiplas unidades (ex: AIO Matriz/Filial) -> P10
        raise AmbiguityError(
            "unidade",
            raw,
            [f"{u.nome_oficial} (CNES {u.cnes})" for u in hits],
        )

    # 3. Fuzzy: substring no nome oficial normalizado
    fuzzy: list[UnidadeRef] = []
    for u in _unidades_data():
        if norm and norm in _norm(u.nome_oficial):
            fuzzy.append(u)
    if len(fuzzy) == 1:
        u = fuzzy[0]
        return ResolvedUnit(nome_oficial=u.nome_oficial, cnes=u.cnes, matched_via=f"fuzzy:{norm}")
    if len(fuzzy) > 1:
        # Limite de 8 sugestoes pra nao explodir UI
        candidates = [f"{u.nome_oficial} (CNES {u.cnes})" for u in fuzzy[:8]]
        raise AmbiguityError("unidade", raw, candidates)

    # 4. Nada bateu — sugere primeiros 5 hospitais conhecidos
    universe = _unidades_data()
    raise UnresolvedError(
        "unidade", raw, suggestions=[u.nome_oficial for u in universe[:5]]
    )


def search_cid(query: str, *, limit: int = 10) -> list[ResolvedCID]:
    """Busca CIDs por codigo OU nome. Lista (vazia se nada bate).

    - Codigo direto (ex. 'I10', 'M54.5') -> 1 resultado se existir.
    - Nome livre (ex. 'diabetes') -> N resultados ranqueados.
    - Multipalavras (ex. 'cancer mama') -> codigos cuja descricao contem TODOS os tokens.

    Util pra UI (chips de clarificacao P10) e pra `resolve_cid` decidir entre 1, 0 ou N.
    """
    if not query or not query.strip():
        return []
    cid10 = _cid10_data()
    if not cid10:
        return []

    cleaned = query.strip().upper().replace(".", "").replace("-", "")
    if _CID_PATTERN.match(cleaned):
        desc = cid10.get(cleaned)
        if desc:
            return [ResolvedCID(codigo=cleaned, descricao=desc)]
        return []

    tokens = _tokens(query)
    if not tokens:
        return []
    index = _cid10_search_index()
    sets = [set(index.get(t, [])) for t in tokens]
    if not sets or not sets[0]:
        return []
    common = sets[0]
    for s in sets[1:]:
        common &= s
    if not common:
        return []
    ordered = sorted(common)[:limit]
    return [ResolvedCID(codigo=c, descricao=cid10[c]) for c in ordered]


def resolve_cid(raw: str) -> ResolvedCID:
    """Texto -> ResolvedCID. Aceita codigo CID-10 BR OU nome em portugues.

    - Codigo bem-formado existente -> retorna direto com descricao.
    - Codigo bem-formado mas inexistente -> UnresolvedError.
    - Nome com 1 match -> ResolvedCID.
    - Nome com 2+ matches -> AmbiguityError (gatilho de P10, clarificacao).
    - Nenhum match -> UnresolvedError.
    """
    if not raw or not raw.strip():
        raise UnresolvedError("cid", raw)

    cid10 = _cid10_data()
    cleaned = raw.strip().upper().replace(".", "").replace("-", "")
    if _CID_PATTERN.match(cleaned):
        desc = cid10.get(cleaned)
        if desc:
            return ResolvedCID(codigo=cleaned, descricao=desc)
        raise UnresolvedError(
            "cid",
            raw,
            suggestions=[
                f"Codigo {cleaned} nao existe no CID-10 BR (DATASUS).",
                "Verifique a grafia ou pesquise pelo nome da doenca.",
            ],
        )

    candidates = search_cid(raw, limit=10)
    if not candidates:
        raise UnresolvedError(
            "cid",
            raw,
            suggestions=[
                "Nenhum CID encontrado.",
                "Use codigo CID-10 ('I10') ou termos do CID em portugues "
                "('hipertensao essencial', 'diabetes', 'catarata').",
            ],
        )
    if len(candidates) == 1:
        return candidates[0]

    # Heuristica de desempate: se ha exatamente UMA categoria 3-char cuja
    # descricao contem TODOS os tokens da query, prefere essa categoria.
    # Resolve casos como "hipertensao essencial" -> I10 (e nao O100 que so
    # menciona "essencial" no contexto de gravidez).
    # Conservador: nao auto-resolve "diabetes" (que tem E10..E14 todas categorias).
    categorias = [c for c in candidates if len(c.codigo) == 3]
    if len(categorias) == 1:
        cat = categorias[0]
        query_tokens = set(_tokens(raw))
        desc_tokens = set(_tokens(cat.descricao or ""))
        if query_tokens and query_tokens.issubset(desc_tokens):
            return cat

    raise AmbiguityError(
        "cid",
        raw,
        [f"{c.codigo}: {c.descricao}" for c in candidates],
    )


# ===== Resolucao de filtros completos (multipla) =====


@dataclass
class ResolvedFilters:
    """Conjunto de filtros ja resolvidos para a query ES.

    None em qualquer campo = filtro nao aplicado.
    """

    cid: str | None = None
    prioridade: str | None = None
    unidade_solicitante: str | None = None
    unidade_executante: str | None = None
    status_grupo: list[str] | None = None
    tipo_regulacao: str | None = None  # 'R' ou 'F'
    tipo_vaga: str | None = None       # '1' ou '2'
    grupo_procedimento: str | None = None
    municipio: str | None = None
    bairro: str | None = None
    _meta: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Versao serializavel — somente campos preenchidos."""
        out: dict[str, object] = {}
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            if v is not None:
                out[k] = v
        return out
