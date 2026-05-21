"""CLI: python -m app "sua pergunta aqui"."""

import json
import sys

from app.engine import ask


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python -m app \"sua pergunta\"", file=sys.stderr)
        return 2
    pergunta = " ".join(sys.argv[1:])
    print(f"\n>>> Pergunta: {pergunta}\n", flush=True)
    print("[1/3] Planner: escolhendo template...", flush=True)
    print("[2/3] ES: executando query...", flush=True)
    print("[3/3] Narrator: redigindo resposta...\n", flush=True)
    try:
        result = ask(pergunta)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    print("=" * 80)
    print(result["narrativa"])
    print("=" * 80)
    print("\n--- Dados consolidados (debug) ---")
    print(json.dumps(result["dados"], ensure_ascii=False, indent=2, default=str))
    print("\n--- Proveniência ---")
    print(json.dumps(result["proveniencia"], ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
