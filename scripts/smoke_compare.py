"""Smoke do compare apos fixes: paciente_avisado + CNES dos novos hospitais."""
from app.agent.orchestrator import _normalize_focus_value

# Test focus_value normalization
cases = [
    ("paciente_avisado", "Sim", "1"),
    ("paciente_avisado", "avisado", "1"),
    ("paciente_avisado", "Não", "0"),
    ("paciente_avisado", "nao avisado", "0"),
    ("paciente_avisado", None, "1"),  # default
    ("paciente_avisado", "", "1"),    # default
    ("tipo_vaga", "primeira vez", "1"),
    ("tipo_vaga", "retorno", "2"),
    ("tipo_vaga", None, "1"),
    ("tipo_regulacao", "regulado", "R"),
    ("tipo_regulacao", "fila", "F"),
    ("unidade_executante", "HRT", "HRT"),  # nao normaliza, fica raw
    ("unidade_executante", None, None),     # nao binaria, nao defaulta
]

ok = 0
fail = 0
for dim, raw, expected in cases:
    actual = _normalize_focus_value(dim, raw)
    mark = "OK" if actual == expected else "FAIL"
    print(f"  [{mark}] ({dim!r}, {raw!r}) -> {actual!r} (esperado {expected!r})")
    if actual == expected:
        ok += 1
    else:
        fail += 1

print(f"\n{ok}/{len(cases)} OK, {fail} FAIL")
