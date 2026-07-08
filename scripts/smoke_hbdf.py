"""Smoke pos-v2.3: 'HBDF tem pendentes' agora deve usar unidade_solicitante."""
import httpx, json
r = httpx.post("http://127.0.0.1:8000/chat",
               json={"pergunta": "Quantas solicitacoes o HBDF tem pendentes?"},
               timeout=60.0).json()
prov = r["proveniencia"]
plan = prov.get("plan") or {}
step0 = (plan.get("steps") or [{}])[0]
print("narrativa[0:300]:", r["narrativa"][:300])
print()
print("total_documents:", prov.get("total_documents"))
print("filters resolvidos no envelope:", prov.get("filters"))
print("filters do step (raw do planner):", step0.get("filters"))
print("composition:", plan.get("composition"))
