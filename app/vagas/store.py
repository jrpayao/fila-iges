"""Cache local das competencias de vagas + carga em DataFrame.

O dado e minusculo (~850 regs/mes) — cabe inteiro em memoria. Cacheamos por
competencia num SQLite para nao rebater a API a cada pergunta e para ter um
historico estavel (a API pode reextrair). A carga tipa os campos numericos
(a API entrega tudo como string) e deriva colunas uteis.

Fluxo tipico:
    store = VagasStore()
    store.sync_range((1, 2025), (7, 2026))   # baixa o que faltar
    df = store.load_df()                       # DataFrame tipado
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd

_RE_CONSULTA = re.compile(r"\s*CONSULTA\s+EM\s+(.+?)(?:\s*-\s|\s*\(|$)", re.I)
_RE_GRUPO = re.compile(r"\s*GRUPO\s*-\s*(?:\d+\.)?\s*(.+?)\s*\(", re.I)


def _especialidade(nome) -> str:
    """Extrai especialidade/grupo do nome do procedimento (dimensao agregadora)."""
    if not isinstance(nome, str) or not nome.strip():
        return "OUTROS"
    m = _RE_CONSULTA.match(nome)
    if m:
        return m.group(1).strip().upper()
    m = _RE_GRUPO.match(nome)
    if m:
        return m.group(1).strip().upper()
    s = re.sub(r"\(.*?\)|\[.*?\]", "", nome).strip()
    return (s[:40].strip() or "OUTROS").upper()

from app import audit
from app.config import settings
from app.vagas.client import (
    RECORD_FIELDS,
    NoDataForCompetencia,
    VagasSisregClient,
)

# Colunas numericas inteiras (a API devolve como string).
_INT_COLS = (
    "vagas_disponiveis",
    "bloq_1",
    "bloq_retorno",
    "bloq_reserva",
    "ativ_1",
    "ativ_retorno",
    "ativ_reserva",
    "mes_comp",
    "ano_comp",
)
_TABLE = "vagas"
_COLS = sorted(RECORD_FIELDS)


class VagasStore:
    def __init__(self, cache_path: str | None = None) -> None:
        self._path = Path(cache_path or settings.vagas_cache_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ----- schema -----

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def _init_schema(self) -> None:
        cols_ddl = ", ".join(f'"{c}" TEXT' for c in _COLS)
        with self._connect() as con:
            con.execute(
                f'CREATE TABLE IF NOT EXISTS {_TABLE} ('
                f"{cols_ddl}, "
                '"_ingested_at" TEXT'
                ")"
            )
            con.execute(
                f'CREATE INDEX IF NOT EXISTS ix_comp ON {_TABLE} ("ano_comp", "mes_comp")'
            )

    # ----- sync -----

    def cached_competencias(self) -> set[tuple[int, int]]:
        """Conjunto de (mes, ano) ja presentes no cache."""
        with self._connect() as con:
            rows = con.execute(
                f'SELECT DISTINCT "mes_comp", "ano_comp" FROM {_TABLE}'
            ).fetchall()
        out: set[tuple[int, int]] = set()
        for m, a in rows:
            try:
                out.add((int(m), int(a)))
            except (TypeError, ValueError):
                continue
        return out

    def sync_competencia(
        self,
        mes: int,
        ano: int,
        *,
        client: VagasSisregClient | None = None,
        force: bool = False,
    ) -> int:
        """Garante a competencia no cache. Retorna nº de registros gravados.

        Idempotente: se ja existe e nao `force`, nao rebate a API (retorna o
        count cacheado). Substitui a competencia inteira ao (re)baixar.
        """
        if not force and (mes, ano) in self.cached_competencias():
            return self._count_competencia(mes, ano)

        owns = client is None
        client = client or VagasSisregClient()
        try:
            records = client.fetch_competencia(mes, ano)
        finally:
            if owns:
                client.close()

        self._replace_competencia(mes, ano, records)
        audit.event("vagas.competencia.synced", mes=mes, ano=ano, n=len(records))
        return len(records)

    def sync_range(
        self,
        start: tuple[int, int],
        end: tuple[int, int] | None = None,
        *,
        force: bool = False,
    ) -> dict[str, int]:
        """Sincroniza de `start`=(mes,ano) ate `end` (default: mes corrente).

        Competencias sem dado (HTML de erro) sao puladas silenciosamente.
        Retorna resumo {"synced": n_comp, "records": total, "skipped": n_vazias}.
        """
        end = end or (date.today().month, date.today().year)
        synced = records = skipped = 0
        with VagasSisregClient() as client:
            for mes, ano in _iter_competencias(start, end):
                try:
                    n = self.sync_competencia(mes, ano, client=client, force=force)
                    synced += 1
                    records += n
                except NoDataForCompetencia:
                    skipped += 1
        return {"synced": synced, "records": records, "skipped": skipped}

    # ----- carga -----

    def load_df(
        self,
        *,
        competencias: Iterable[tuple[int, int]] | None = None,
    ) -> pd.DataFrame:
        """Carrega o cache num DataFrame tipado. Filtra por competencias se dado."""
        with self._connect() as con:
            df = pd.read_sql_query(f"SELECT * FROM {_TABLE}", con)

        if df.empty:
            return df

        for col in _INT_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        if "data_extracao" in df.columns:
            df["data_extracao"] = pd.to_datetime(df["data_extracao"], errors="coerce", utc=True)

        # Coluna derivada de competencia (AAAAMM) para ordenacao/serie temporal.
        df["competencia"] = df["ano_comp"] * 100 + df["mes_comp"]

        # Coluna derivada de especialidade/grupo, extraida do nome do procedimento.
        if "procedimento" in df.columns:
            df["especialidade"] = df["procedimento"].map(_especialidade)

        if competencias is not None:
            wanted = {a * 100 + m for m, a in competencias}
            df = df[df["competencia"].isin(wanted)]

        return df.reset_index(drop=True)

    # ----- internos -----

    def _replace_competencia(self, mes: int, ano: int, records: list[dict]) -> None:
        now = _utcnow_iso()
        with self._connect() as con:
            con.execute(
                f'DELETE FROM {_TABLE} WHERE "mes_comp"=? AND "ano_comp"=?',
                (str(mes), str(ano)),
            )
            if records:
                placeholders = ", ".join("?" for _ in _COLS) + ", ?"
                rows = [
                    tuple(str(r.get(c, "")) for c in _COLS) + (now,)
                    for r in records
                ]
                con.executemany(
                    f'INSERT INTO {_TABLE} ({", ".join(chr(34)+c+chr(34) for c in _COLS)}, "_ingested_at") '
                    f"VALUES ({placeholders})",
                    rows,
                )

    def _count_competencia(self, mes: int, ano: int) -> int:
        with self._connect() as con:
            (n,) = con.execute(
                f'SELECT COUNT(*) FROM {_TABLE} WHERE "mes_comp"=? AND "ano_comp"=?',
                (str(mes), str(ano)),
            ).fetchone()
        return int(n)


# ----- helpers -----


def _iter_competencias(
    start: tuple[int, int], end: tuple[int, int]
) -> Iterable[tuple[int, int]]:
    """Itera (mes, ano) inclusivo de start ate end."""
    smes, sano = start
    emes, eano = end
    cur = sano * 12 + (smes - 1)
    last = eano * 12 + (emes - 1)
    while cur <= last:
        yield (cur % 12) + 1, cur // 12
        cur += 1


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
