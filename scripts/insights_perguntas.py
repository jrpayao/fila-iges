"""Relatorio dos insights sobre as perguntas (le o log diario). CLI.

    $py scripts/insights_perguntas.py [dias]
"""

from __future__ import annotations

import sys

from app import query_log


def main() -> int:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    s = query_log.summarize(days=days)
    print("=" * 66)
    print(f"INSIGHTS DAS PERGUNTAS — ultimos {days} dias")
    print("=" * 66)
    print(f"Total de perguntas: {s['total_perguntas']}")
    if not s["total_perguntas"]:
        print("(sem registros — o log e alimentado a cada pergunta no chat)")
        return 0
    print(f"Por dia: {s['por_dia']}")
    print(f"Status: {s['por_status']}  "
          f"(recusa {s['taxa_recusa_pct']}% · clarificacao {s['taxa_clarificacao_pct']}% · erro {s['taxa_erro_pct']}%)")

    def bloco(titulo, pares):
        print(f"\n{titulo}")
        for k, v in pares:
            print(f"  {v:>4}x  {str(k)[:56]}")

    bloco("Metricas mais pedidas:", s["top_metricas"])
    bloco("Primitivas mais usadas:", s["top_primitivas"])
    bloco("Procedimentos mais perguntados:", s["top_procedimentos"])
    bloco("Hospitais mais perguntados:", s["top_hospitais"])

    lac = s["lacunas"]
    print("\n" + "-" * 66)
    print("LACUNAS (o que os usuarios querem e nao entregamos plenamente):")
    print(f"  Perguntas de demanda/fila (fonte so tem oferta): {lac['perguntas_de_demanda_fila']}")
    print(f"  Recusas (fora de escopo): {lac['recusas']}")
    if lac["campos_nao_resolvidos"]:
        print("  Termos nao resolvidos (resolver falhou):")
        for k, v in lac["campos_nao_resolvidos"]:
            print(f"    {v:>3}x  {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
