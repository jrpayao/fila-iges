# Deploy — ofertas-vagas (CapRover · `captain.payao.tech`)

App único no CapRover chamado **`ofertas-vagas`**, rodando **API (FastAPI) + UI (Streamlit)**
no mesmo container. A UI é a face pública (porta 8501); a API roda interna em `127.0.0.1:8000`.

Arquivos de build (raiz do repo):
- `Dockerfile` — imagem combinada.
- `start.sh` — sobe uvicorn (interno) + streamlit (público).
- `captain-definition` — aponta para `./Dockerfile`.

> Os dois apps antigos (`Dockerfile.api` / `Dockerfile.ui` / `captain-definition.*.json`)
> ficam no repo como legado do motor SISREG-ES; **não** são usados neste deploy.

## 1. Criar o app no CapRover

No painel: **Apps → Create New App → `ofertas-vagas`** (deixe "Has Persistent Data" marcado).

## 2. Configurar a porta e os volumes

Em **ofertas-vagas → App Configs**:

- **Container HTTP Port**: `8501`  ← obrigatório (o Streamlit escuta nessa porta).
- **Persistent Directories** (cache não rebaixa a API a cada restart + guarda os logs):
  | Path in App | Label |
  |---|---|
  | `/app/data` | `ofertas-vagas-data` |
  | `/app/logs` | `ofertas-vagas-logs` |

## 3. Variáveis de ambiente

Em **App Configs → Environmental Variables** (segredos NÃO vão na imagem):

```
OPENAI_API_KEY=sk-...
IGES_VAGAS_CLIENT_ID=...
IGES_VAGAS_CLIENT_SECRET=...
```

Já vêm com default no Dockerfile (sobrescreva se quiser):
`IGES_VAGAS_URL`, `VAGAS_CACHE_PATH=/app/data/vagas_cache.sqlite`,
`QUERY_LOG_DIR=/app/logs`, `AUDIT_JSONL_PATH=/app/logs/audit.jsonl`, `APP_MODE=poc`.

Opcional (proteger a API com Basic Auth): `API_AUTH_ENABLED=true`, `API_AUTH_USER`, `API_AUTH_PASS`.

## 4. HTTPS

Em **ofertas-vagas → HTTP Settings**: habilite HTTPS + force redirect. Domínio:
`ofertas-vagas.captain.payao.tech` (ou um custom).

## 5. Deploy

Da raiz do repo, com a CLI do CapRover autenticada no servidor:

```bash
caprover deploy -a ofertas-vagas
```

(ou **Deploy from GitHub** apontando para a branch `feat/motor-vagas-sisreg` — o CapRover
usa o `captain-definition` da raiz automaticamente.)

## 6. Primeiro acesso

No **primeiro chat**, o app baixa as competências da API de vagas (jan/2025 → mês atual)
e monta o cache em `/app/data` — pode levar ~30–60s nessa primeira pergunta. Como o
diretório é persistente, os restarts seguintes sobem com o cache pronto.

## Notas

- Um container, dois processos (uvicorn + streamlit). Para escalar separado, dá para
  voltar ao modelo de dois apps (`Dockerfile.api` / `Dockerfile.ui`).
- Logs diários de perguntas em `/app/logs/perguntas-AAAA-MM-DD.jsonl` (uso interno).
- Sem PII: a fonte de vagas é agregada; os logs guardam só a pergunta do gestor.
- Se o build falhar por causa do `pytest` no `requirements.txt`, pode removê-lo (é dev-only).
