"""Fonte v3 — API de vagas SISREG publicada pelo IGES.

Camada de acesso ao dado de *oferta* (capacidade de vagas por procedimento x
hospital x competencia). Substitui a camada `app/es/` da fonte legada.

- `client.VagasSisregClient` — HTTP GET-only, auth por header (P13-analogo).
- `store.VagasStore` — cache local por competencia + carga em DataFrame.
"""
