"""Converte CID-10-CATEGORIAS.CSV e CID-10-SUBCATEGORIAS.CSV (DATASUS, latin-1)
em um JSON unico UTF-8 plano: {codigo: descricao}.

Inclui CATEGORIAS (3 chars, ex. I10), SUBCATEGORIAS (4 chars, ex. I101) e
augmentations pos-2007 de docs/reference/cid10_augmentations.json (COVID, Zika, etc.).

Uso:
    rm -rf docs/reference/cid10_tmp && unzip -q docs/reference/CID10CSV.zip -d docs/reference/cid10_tmp
    python scripts/build_cid10_json.py
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "reference" / "cid10_tmp"
AUG = ROOT / "docs" / "reference" / "cid10_augmentations.json"
OUT = ROOT / "app" / "agent" / "data" / "cid10.json"

FILES = {
    "CID-10-CATEGORIAS.CSV": "CAT",
    "CID-10-SUBCATEGORIAS.CSV": "SUBCAT",
}


def _load_csvs() -> dict[str, str]:
    if not SRC.exists():
        raise SystemExit(
            f"Diretorio {SRC} nao existe. Extrair docs/reference/CID10CSV.zip primeiro:\n"
            "  rm -rf docs/reference/cid10_tmp\n"
            "  unzip -q docs/reference/CID10CSV.zip -d docs/reference/cid10_tmp"
        )
    out: dict[str, str] = {}
    for fname, code_col in FILES.items():
        with (SRC / fname).open(encoding="latin-1") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                code = (row.get(code_col) or "").strip().upper()
                desc = (row.get("DESCRICAO") or "").strip()
                if code and desc:
                    out[code] = desc
    return out


def _load_augmentations() -> dict[str, str]:
    if not AUG.exists():
        return {}
    raw = json.loads(AUG.read_text(encoding="utf-8"))
    return {k.upper(): v for k, v in raw.items() if not k.startswith("_") and isinstance(v, str)}


def main() -> None:
    base = _load_csvs()
    aug = _load_augmentations()

    added = 0
    skipped = 0
    for code, desc in aug.items():
        if code in base:
            skipped += 1  # nao sobrescreve autoridade DATASUS
        else:
            base[code] = desc
            added += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(base, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    size_kb = OUT.stat().st_size / 1024
    print(f"OK — {len(base)} codigos gravados em {OUT.relative_to(ROOT)} ({size_kb:.0f} KB).")
    print(f"     base DATASUS 2007: {len(base) - added} codigos")
    print(f"     augmentations pos-2007: +{added} codigos adicionados, {skipped} ignorados (ja existiam)")
    print(f"\nAmostra (incl. COVID/Zika):")
    for k in ("A00", "I10", "C50", "K04", "M545", "U071", "U099", "A925"):
        if k in base:
            print(f"  {k:6} {base[k]}")


if __name__ == "__main__":
    main()
