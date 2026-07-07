"""Smoke test do resolve_cid + search_cid com a base CID-10 BR + augmentations."""

from app.agent.resolver import (
    AmbiguityError,
    UnresolvedError,
    resolve_cid,
    search_cid,
)


def test_query(q: str) -> None:
    try:
        r = resolve_cid(q)
        print(f"  '{q}' -> {r.codigo:6} {r.descricao}")
    except AmbiguityError as exc:
        print(f"  '{q}' -> AmbiguityError ({len(exc.candidates)}):")
        for c in exc.candidates[:5]:
            print(f"      {c}")
    except UnresolvedError as exc:
        print(f"  '{q}' -> UnresolvedError")


print("=== Codigos pos-2007 (era o GAP) ===")
for code in ["U071", "U072", "U099", "U109", "A925", "U07", "U089"]:
    test_query(code)

print("\n=== Termos COVID em portugues ===")
for q in ["covid", "covid-19", "covid 19", "coronavirus identificado", "zika"]:
    test_query(q)

print("\n=== Sanity: continuamos cobrindo o que ja funcionava ===")
for q in ["I10", "hipertensao essencial primaria", "neoplasia maligna mama"]:
    test_query(q)

print("\n=== search_cid (uso na UI / chips) ===")
for q in ["covid", "tuberculose", "zika"]:
    results = search_cid(q, limit=5)
    print(f"  '{q}' -> {len(results)} resultados")
    for r in results:
        print(f"      {r.codigo:6} {r.descricao}")
