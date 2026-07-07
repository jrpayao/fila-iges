"""Smoke do resolver de unidades apos refactor (JSON 328 unidades)."""
from app.agent import resolver as R

CASES = [
    # texto, esperado_cnes, esperado_match_via
    ("HBDF", "0010456", "alias"),
    ("HB", "0010456", "alias"),
    ("Hospital de Base", "0010456", "alias"),
    ("HRT", "0010499", "alias"),
    ("HRAN", "0010464", "alias"),
    ("HUB", "0010510", "alias"),
    ("HRC", "0010480", "alias"),       # antes nao tinha CNES
    ("HRG", "0010472", "alias"),       # antes nao tinha CNES
    ("HRGu", "2814897", "alias"),      # antes nao tinha CNES
    ("HMIB", "0010537", "alias"),      # antes nao tinha CNES
    ("HSL", "2815966", "alias"),       # novo (Santa Lucia)
    ("HCB", "6876617", "alias"),       # novo
    ("HRSAM", "2672197", "alias"),     # novo
    ("HRSM", "5717515", "alias"),      # novo
    ("0010456", "0010456", "cnes"),    # CNES direto
    ("Sobradinho", "0010502", "alias"),  # alias extra
]

ok = 0
fail = 0
ambiguous_expected = ["AIO", "OFTALMED", "POL TAG", "POL CEI", "POL PLA", "UBS 01 AS"]

for raw, expected_cnes, expected_via in CASES:
    try:
        r = R.resolve_unidade(raw)
        if r.cnes == expected_cnes and r.matched_via == expected_via:
            ok += 1
            print(f"  [OK] '{raw}' -> {r.nome_oficial} (CNES {r.cnes}, via {r.matched_via})")
        else:
            fail += 1
            print(f"  [FAIL] '{raw}' -> CNES={r.cnes} via={r.matched_via} (esperava {expected_cnes}/{expected_via})")
    except R.AmbiguityError as e:
        fail += 1
        print(f"  [FAIL-AMB] '{raw}': {e.candidates[:3]}")
    except R.UnresolvedError as e:
        fail += 1
        print(f"  [FAIL-UNR] '{raw}': {e}")

print(f"\n--- Casos esperados de ambiguidade (P10) ---")
for raw in ambiguous_expected:
    try:
        r = R.resolve_unidade(raw)
        print(f"  [no-amb] '{raw}' -> {r.nome_oficial} (sem ambiguidade — talvez ok dependendo do catalogo)")
    except R.AmbiguityError as e:
        print(f"  [AMB OK] '{raw}' -> {len(e.candidates)} candidatos (P10 OK)")
    except R.UnresolvedError as e:
        print(f"  [UNR ?] '{raw}': {e}")

print(f"\nRESULTADO: {ok}/{len(CASES)} casos esperados OK, {fail} falhas")
print(f"Total unidades carregadas: {len(R._unidades_data())}")
print(f"Total aliases unicos: {len(R._unidades_by_alias())}")
