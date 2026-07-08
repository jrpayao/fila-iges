"""Export do Envelope para CSV com carimbo de proveniencia (P8).

Todo arquivo carrega cabecalho: fonte, competencia/janela, filtros, metrica,
method_note e gerado_em. Le SOMENTE o Envelope (P4).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any


def _rows_for(shape: str, data: list[dict], units: str) -> tuple[list[str], list[list]]:
    """Cabecalho + linhas tabulares conforme o shape do envelope."""
    if shape == "scalar":
        d = data[0] if data else {}
        header = ["metrica_valor", "unidade"]
        rows = [[d.get("value_label", d.get("value")), units]]
        if d.get("delta_pct") is not None:
            header += ["vs_anterior_%", "competencia_anterior"]
            rows[0] += [d.get("delta_pct"), d.get("prev_competencia")]
        return header, rows
    if shape == "timeseries":
        return ["competencia", "valor"], [[p.get("key"), p.get("value")] for p in data]
    if shape == "comparison":
        item = data[0] if data else {}
        rows = [["(destaque) " + str(item.get("focus", {}).get("key", "")), item.get("focus", {}).get("value")]]
        rows += [[b.get("key"), b.get("value")] for b in item.get("benchmark", [])]
        return ["item", units], rows
    # breakdown (default)
    extra_keys: list[str] = []
    for b in data:
        for k in b:
            if k not in ("key", "value") and k not in extra_keys:
                extra_keys.append(k)
    header = ["item", units] + extra_keys
    rows = [[b.get("key"), b.get("value")] + [b.get(k) for k in extra_keys] for b in data]
    return header, rows


def envelope_to_csv(envelope: dict[str, Any] | Any) -> str:
    """Envelope (dict de model_dump OU objeto) -> CSV string (pt-BR, `;`, com BOM)."""
    env = envelope if isinstance(envelope, dict) else envelope.model_dump(mode="json")
    buf = io.StringIO()
    buf.write("﻿")  # BOM p/ Excel abrir acentos certo
    w = csv.writer(buf, delimiter=";", lineterminator="\n")

    win = env.get("window") or {}
    w.writerow(["# PROVENIENCIA"])
    w.writerow(["# fonte", env.get("source_index")])
    w.writerow(["# metrica", env.get("metric")])
    w.writerow(["# janela", win.get("label")])
    w.writerow(["# filtros", "; ".join(f"{k}={v}" for k, v in (env.get("filters") or {}).items())])
    if env.get("method_note"):
        w.writerow(["# metodo", env["method_note"]])
    w.writerow(["# gerado_em", datetime.now(timezone.utc).isoformat()])
    w.writerow([])

    subs = env.get("sub_envelopes")
    if subs:
        for s in subs:
            w.writerow([f"== {s.get('metric')} ({s.get('shape')}) =="])
            header, rows = _rows_for(s.get("shape"), s.get("data") or [], str(s.get("units")))
            w.writerow(header)
            w.writerows(rows)
            w.writerow([])
    else:
        header, rows = _rows_for(env.get("shape"), env.get("data") or [], str(env.get("units")))
        w.writerow(header)
        w.writerows(rows)

    return buf.getvalue()
