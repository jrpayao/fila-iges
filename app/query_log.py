"""Log diario de perguntas + agregacao de insights ("o que o pessoal pergunta").

- `append(record)` grava uma linha JSON no arquivo do dia: logs/perguntas-AAAA-MM-DD.jsonl.
- `summarize(days)` le os arquivos recentes e devolve um resumo agregado.

Sem PII: aqui vive a pergunta do gestor + metadados de execucao, nunca dado de paciente.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import settings

_PREFIX = "perguntas-"


def _dir() -> Path:
    d = Path(getattr(settings, "query_log_dir", "./logs"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _day_file(ts: datetime) -> Path:
    return _dir() / f"{_PREFIX}{ts.strftime('%Y-%m-%d')}.jsonl"


def append(record: dict[str, Any]) -> None:
    """Grava um turno no log do dia (append). Nunca levanta pra nao quebrar a resposta."""
    try:
        ts = datetime.now(timezone.utc)
        record = {"ts": ts.isoformat(), **record}
        with _day_file(ts).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


# ===== Leitura / agregacao =====


def iter_records(days: int = 7) -> list[dict[str, Any]]:
    """Registros dos ultimos `days` dias (por data do arquivo)."""
    out: list[dict[str, Any]] = []
    today = datetime.now(timezone.utc).date()
    for i in range(days):
        d = today - timedelta(days=i)
        f = _dir() / f"{_PREFIX}{d.strftime('%Y-%m-%d')}.jsonl"
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def summarize(days: int = 7, *, top: int = 8) -> dict[str, Any]:
    """Resumo de insights sobre as perguntas dos ultimos `days` dias."""
    recs = iter_records(days)
    n = len(recs)
    por_dia: Counter = Counter()
    status: Counter = Counter()
    metric: Counter = Counter()
    primitiva: Counter = Counter()
    procedimento: Counter = Counter()
    hospital: Counter = Counter()
    clarif_field: Counter = Counter()
    demanda = 0

    for r in recs:
        por_dia[(r.get("ts") or "")[:10]] += 1
        status[r.get("status") or "?"] += 1
        if r.get("metric"):
            metric[r["metric"]] += 1
        for p in r.get("primitivas") or []:
            primitiva[p] += 1
        filt = r.get("filters") or {}
        if filt.get("procedimento"):
            procedimento[filt["procedimento"]] += 1
        if filt.get("hospital"):
            hospital[filt["hospital"]] += 1
        for cf in r.get("clarifications") or []:
            clarif_field[cf] += 1
        if r.get("demanda_caveat"):
            demanda += 1

    def pct(k: str) -> float:
        return round(status.get(k, 0) / n * 100, 1) if n else 0.0

    return {
        "janela_dias": days,
        "total_perguntas": n,
        "por_dia": dict(sorted(por_dia.items())),
        "por_status": dict(status),
        "taxa_recusa_pct": pct("refusal"),
        "taxa_clarificacao_pct": pct("clarification"),
        "taxa_erro_pct": pct("error"),
        "top_metricas": metric.most_common(top),
        "top_primitivas": primitiva.most_common(top),
        "top_procedimentos": procedimento.most_common(top),
        "top_hospitais": hospital.most_common(top),
        # LACUNAS — o que os usuarios querem e nao entregamos plenamente:
        "lacunas": {
            "perguntas_de_demanda_fila": demanda,  # querem tempo de espera / tamanho de fila
            "campos_nao_resolvidos": clarif_field.most_common(top),  # onde o resolver falhou
            "recusas": status.get("refusal", 0),
        },
        "perguntas_recentes": [
            {"ts": r.get("ts"), "pergunta": r.get("pergunta"), "status": r.get("status")}
            for r in recs[-15:]
        ],
    }
