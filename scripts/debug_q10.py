"""Investiga porque a #10 caiu em clarification."""

from app.agent.resolver import resolve_cid, resolve_unidade, search_cid, AmbiguityError, UnresolvedError


print("=== resolve_cid('hipertensao essencial') ===")
try:
    r = resolve_cid("hipertensao essencial")
    print(f"  OK: {r}")
except AmbiguityError as e:
    print(f"  AMBIGUO ({len(e.candidates)}):")
    for c in e.candidates[:8]:
        print(f"    {c}")
except UnresolvedError as e:
    print(f"  UNRESOLVED: {e.suggestions}")

print("\n=== resolve_unidade('HBDF') ===")
try:
    u = resolve_unidade("HBDF")
    print(f"  OK: {u}")
except (AmbiguityError, UnresolvedError) as e:
    print(f"  {type(e).__name__}: {e}")

print("\n=== search_cid('hipertensao essencial', limit=5) ===")
for c in search_cid("hipertensao essencial", limit=5):
    print(f"  {c.codigo}: {c.descricao}")
