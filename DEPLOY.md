# Deploy no CapRover — `captain.payao.tech`

Arquitetura: **2 apps separadas** no CapRover.

| App | Função | Exposição | Porta interna |
|---|---|---|---|
| `fila-eletiva-api` | FastAPI backend (engine multi-agente) | Privada (recomendado) | 80 |
| `fila-eletiva-ui` | Streamlit UI | Pública via HTTPS | 80 |

A UI chama a API via DNS interno do CapRover: `http://srv-captain--fila-eletiva-api`. Nenhum tráfego entre containers passa pela internet.

---

## Pré-requisitos (uma vez por máquina)

1. **CapRover CLI**:
   ```bash
   npm install -g caprover
   ```

2. **Login**:
   ```bash
   caprover login --caproverUrl https://captain.payao.tech
   ```
   Salva token em `~/.caprover/config`.

3. **Criar as 2 apps no painel** (https://captain.payao.tech):
   - Apps → New App → `fila-eletiva-api` → Create
   - Apps → New App → `fila-eletiva-ui` → Create

---

## Env vars (configurar no painel CapRover, NÃO no código)

### `fila-eletiva-api` → App Configs → Environmental Variables

| Variável | Valor | Notas |
|---|---|---|
| `OPENAI_API_KEY` | `sk-proj-...` (chave **viva**) | rotacione antes do deploy se já trafegou em chat |
| `OPENAI_PLANNER_MODEL` | `gpt-4o` | |
| `OPENAI_VALIDATOR_MODEL` | `gpt-4o` | |
| `OPENAI_NARRATOR_MODEL` | `gpt-4o-mini` | |
| `OPENAI_ROUTER_MODEL` | `gpt-4o-mini` | |
| `OPENAI_CRITIC_MODEL` | `gpt-4o-mini` | |
| `SISREG_BASE_URL` | `https://sisreg-es.saude.gov.br` | |
| `SISREG_USER` | `claudio.payao` | |
| `SISREG_PASS` | `Datasus@2026` | considere rotacionar |
| `SISREG_UF_CODE_IBGE` | `53` | |
| `SISREG_CENTRAIS_REGULADORAS` | `530010` | |
| `SISREG_REQUEST_TIMEOUT_SECONDS` | `10` | |
| `APP_MODE` | `poc` | |
| `POC_EXPIRES_AT` | `2026-07-19` | |
| `AUDIT_JSONL_PATH` | `/data/audit.jsonl` | usar com volume persistente |
| `API_AUTH_ENABLED` | `true` | **recomendado em deploy público** |
| `API_AUTH_USER` | `iges-admin` (escolha) | |
| `API_AUTH_PASS` | (senha forte) | |

### `fila-eletiva-ui` → App Configs → Environmental Variables

| Variável | Valor | Notas |
|---|---|---|
| `API_BASE_URL` | `http://srv-captain--fila-eletiva-api` | DNS interno do CapRover (sem HTTPS, é rede privada) |
| `API_AUTH_USER` | mesma do API | se API_AUTH_ENABLED=true na API |
| `API_AUTH_PASS` | mesma do API | |

---

## Volume persistente para audit (recomendado na API)

CapRover → app `fila-eletiva-api` → App Configs → Persistent Directories → Add:
- **Path in App**: `/data`
- **Label**: `audit-data`

Depois `AUDIT_JSONL_PATH=/data/audit.jsonl` persiste entre restarts.

---

## HTTPS e domínio

- CapRover serve HTTPS automaticamente via Let's Encrypt no subdomínio padrão.
- Para `fila-eletiva-api`: na aba **HTTP Settings**, **DESMARQUE** `Has Public HTTP Connection` (mantém só rede interna). 
- Para `fila-eletiva-ui`: **MANTENHA** `Has Public HTTP Connection` e **MARQUE** `Force HTTPS`.

URLs finais:
- API (interna): `http://srv-captain--fila-eletiva-api/` (acessível só por outras apps no CapRover)
- UI (pública): `https://fila-eletiva-ui.captain.payao.tech/`

---

## Deploy

Da raiz do projeto, com `caprover` CLI logado:

```bash
# Em ordem (API primeiro pra UI achar o DNS interno na primeira chamada)
bash scripts/deploy_api.sh
bash scripts/deploy_ui.sh
```

Cada script:
1. Copia `captain-definition.{api,ui}.json` → `captain-definition`.
2. Roda `caprover deploy --appName fila-eletiva-{api,ui}`.
3. Limpa o `captain-definition` temporário.

Alternativa via dashboard: cada app → **Deployment** → **Tarball Upload** → fazer `tar czf` da raiz incluindo `captain-definition.json` renomeado pra `captain-definition`.

---

## Verificação pós-deploy

```bash
# Health (de fora — bate na UI primeiro, que internamente bate na API)
curl https://fila-eletiva-ui.captain.payao.tech/_stcore/health
# Esperado: ok

# Abrir UI no browser
open https://fila-eletiva-ui.captain.payao.tech/
# Sidebar deve mostrar "API status: OK", "ES alcançável: OK", "OpenAI alcançável: OK"
```

---

## Logs e troubleshooting

No painel CapRover: **Apps → app → App Logs** (tail em tempo real).

| Sintoma | Diagnóstico | Fix |
|---|---|---|
| UI mostra "API offline" na sidebar | API_BASE_URL errada ou API não bootou | Conferir env `API_BASE_URL=http://srv-captain--fila-eletiva-api` e logs da API |
| API retorna 401 em todas chamadas | Basic Auth ativado mas UI sem credencial | Garantir `API_AUTH_USER`/`API_AUTH_PASS` iguais nas 2 apps |
| API falha no boot com "Field required" | env var faltando | Conferir lista acima — `OPENAI_API_KEY`, `SISREG_USER`, `SISREG_PASS` são obrigatórios |
| `503` ao subir | Health check falhando | Aguardar `start-period` (10-15s). Se persistir, ver logs |
| Build falha em `pip install` | rede CapRover lenta ou pacote indisponível | Re-deploy; verificar status do PyPI |
| ES 401 nas queries | senha SISREG errada/expirada | Atualizar env `SISREG_PASS` no painel + restart |

---

## Rollback

CapRover guarda histórico de imagens. **Apps → app → Deployment → Versions** → **Revert** na versão anterior.

---

## Custo e escala

- Default CapRover: 1 instância por app, sem auto-scale.
- Pra escalar: **App Configs → Instance Count**. Stateless, multiplica trivialmente.
- Atenção ao audit.jsonl em multi-instância: cada instância escreve no seu próprio volume (a menos que use volume compartilhado tipo NFS). Em produção, migrar para Postgres ou similar.

---

## Hardening pendente (depois do MVP)

1. **OIDC/SAML** no lugar de Basic Auth (integrar com Keycloak IGES).
2. **Rate limit** por usuário no API (FastAPI middleware ou nginx no CapRover).
3. **Circuit breaker** de orçamento OpenAI (cortar requests ao atingir 90% do limite mensal).
4. **Migrar OpenAI → Claude** antes de `POC_EXPIRES_AT=2026-07-19` (P8 da constituição).
5. **Audit centralizado** (Postgres ou ES próprio) em vez de JSONL local.
