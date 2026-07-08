"""Probe cobertura de data fields nos 2 indices ambulatoriais."""
from app.es.client import SisregESClient
from datetime import date, timedelta

today = date.today()
gte = (today - timedelta(days=30)).isoformat()
lte = today.isoformat()

CAMPOS = [
    "data_solicitacao", "data_aprovacao", "data_marcacao", "data_atualizacao",
    "data_confirmacao", "data_cancelamento", "data_negacao", "data_devolucao",
    "data_envio_regulador", "data_regulacao",
]

with SisregESClient() as es:
    for idx in ("solicitacao-ambulatorial-df-brasilia", "marcacao-ambulatorial-df-brasilia"):
        print(f"\n=== {idx} === ({gte} a {lte})")
        for f in CAMPOS:
            body = {
                "size": 0,
                "query": {"bool": {"must": [
                    {"term": {"codigo_uf_regulador": "53"}},
                    {"range": {f: {"gte": gte, "lte": lte}}},
                ]}},
                "track_total_hits": True,
            }
            try:
                r = es._client.post(f"/{idx}/_search", json=body).json()
                if "error" in r:
                    print(f"  {f:25s} FIELD_MISSING")
                else:
                    n = r['hits']['total']['value']
                    print(f"  {f:25s} {n:>10,}")
            except Exception as e:
                print(f"  {f:25s} EXC: {e}")
