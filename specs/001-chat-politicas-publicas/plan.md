# Plan 001 — Implementação técnica

**Vinculado a**: [spec.md](spec.md) · **Status**: draft v0.1 · **Data**: 2026-05-20

## 1. Arquitetura em alto nível

```
┌─────────────┐     pergunta NL     ┌──────────────────────────────────────────┐
│   Chat UI   │ ──────────────────▶ │  FastAPI · POST /chat                   │
└─────────────┘                     │  ┌────────────────────────────────────┐  │
       ▲                            │  │ 1. Auth (OIDC)                     │  │
       │       resposta+tabela      │  │ 2. Rate limit                      │  │
       └────────────────────────────│  │ 3. Audit start                     │  │
                                    │  │ 4. NL→tool-call (Claude Opus 4.7)  │  │ ◀─┐
                                    │  │ 5. Validação Pydantic do tool-call │  │  │
                                    │  │ 6. Render DSL a partir do template │  │  │
                                    │  │ 7. Execução no ES (elasticsearch-  │  │  │ tool
                                    │  │    py, GET ONLY, allowlist índices)│  │  │ schemas
                                    │  │ 8. Anonymizer (drop campos PII)    │  │  │
                                    │  │ 9. Narrator (Claude Haiku 4.5)     │  │  │
                                    │  │10. Audit end (sem PII)             │  │  │
                                    │  └────────────────────────────────────┘  │  │
                                    └──────────────────────────────────────────┘  │
                                                  │                               │
                                                  ▼                               │
                                    ┌─────────────────────────────┐               │
                                    │ contracts/elasticsearch.md  │ ──────────────┘
                                    │   (templates DSL allowlist) │
                                    └─────────────────────────────┘
                                                  │
                                                  ▼
                                    ┌─────────────────────────────┐
                                    │   sisreg-es.saude.gov.br    │
                                    │  /solicitacao-ambulatorial- │
                                    │  53-{municipio}             │
                                    │  /marcacao-ambulatorial-... │
                                    │  /solicitacao-hospitalar-...│
                                    └─────────────────────────────┘
```

## 2. Stack

**Modo POC ativo até 2026-07-19** — provedor LLM é OpenAI. Migração para Claude (P8 default) é item obrigatório de `tasks.md`.

| Camada | Escolha POC | Escolha Produção (≥ 2026-07-20) | Versão | Justificativa |
|---|---|---|---|---|
| Linguagem | Python | Python | ≥ 3.11 | Match comp & maturidade LLM/ES libs. |
| Web framework | FastAPI | FastAPI | ≥ 0.110 | Pydantic v2 nativo (essencial p/ tool-call validation). |
| LLM SDK | `openai` | `anthropic` | atual | Ambos têm function-calling estruturado. |
| Modelos | `gpt-4o` (planner) + `gpt-4o-mini` (narrator) | `claude-opus-4-7` (planner) + `claude-haiku-4-5-20251001` (narrator) | fixos | POC: tempo-de-prototipagem; Prod: reasoning forte + custo otimizado. |
| ES client | `elasticsearch` (oficial) | 8.x compatível | Suporte a SQL e DSL. |
| Validação | `pydantic` | v2 | Modelos para tool-call inputs e outputs. |
| Logs | `structlog` | atual | JSON estruturado. |
| Métricas | `prometheus_client` | atual | Padrão DevOps. |
| Tracing | `opentelemetry-sdk` | atual | Tracing distribuído. |
| Testes | `pytest` + `respx` + `testcontainers` | atual | Mock HTTP + ES local em container. |
| Lint/Fmt | `ruff` + `mypy --strict` | atual | |
| Auth | OIDC (Keycloak IGES) via `authlib` | atual | Federação corporativa. |

**Frontend**: decisão adiada para `research.md` (Q1 da spec). Pré-protótipo pode usar `httpie`/curl + endpoint Swagger autogerado.

## 3. Layout de módulos

```
app/
├── api/
│   ├── chat.py                 # POST /chat
│   ├── audit.py                # GET /audit
│   ├── health.py               # GET /health
│   └── deps.py                 # dependências FastAPI (auth, db, settings)
├── llm/
│   ├── router.py               # gpt-4o-mini → classifica intent (data_query/meta/out_of_scope)
│   ├── planner.py              # gpt-4o → tool call (template + params/dsl) + retry
│   ├── validator.py            # gpt-4o → revisão semântica do DSL pré-execução
│   ├── narrator.py             # gpt-4o-mini → narrativa final + retry
│   ├── critic.py               # gpt-4o-mini → revisão P2/P5/estilo da narrativa
│   └── prompts.py              # ROUTER_/PLANNER_/VALIDATOR_/NARRATOR_/CRITIC_SYSTEM versionados
├── es/
│   ├── client.py               # wrapper elasticsearch (GET-only, allowlist)
│   ├── templates/              # 1 template = 1 módulo. Allowlist via registry.py
│   │   ├── _helpers.py             # constantes (STATUS_*, RISCO_*) + utils compartilhados
│   │   ├── top_cids.py             # top CIDs solicitados (ambulatorial)
│   │   ├── top_cids_marcacao.py    # top CIDs em marcação (atendidos/agendados/cancelados/todos)
│   │   ├── top_cids_hospitalar.py  # top CIDs em internações
│   │   ├── top_unidades_solicitantes.py  # top unidades solicitantes
│   │   ├── top_unidades_executantes.py   # top unidades executantes (marc / hosp)
│   │   ├── top_procedimentos.py    # top procedimentos (nested em procedimentos[])
│   │   ├── distribuicao_risco.py   # buckets por classificacao_risco (Prioridade 0-3)
│   │   ├── distribuicao_status.py  # buckets por status_solicitacao
│   │   ├── distribuicao_carater_hospitalar.py  # URGENTE x ELETIVA (hospitalar)
│   │   ├── fila_snapshot.py        # estado atual da fila (sem range)
│   │   └── free_text_search.py     # POC ONLY — DSL livre validada por safety guard
│   ├── safety.py               # valida tool-call → bloqueia tudo fora do template
│   │                             # + allowlist negativa do free_text_search (POC)
│   ├── mappings.py             # cache lru das mappings dos 3 índices (injetado no prompt)
│   └── registry.py             # dicionário template_id → módulo + schema
├── anonymize/
│   ├── fields.py               # POC_VISIBLE_PII + ALWAYS_MASKED_PII (P2 POC override)
│   ├── redactor.py             # mascara ALWAYS_MASKED; deixa POC_VISIBLE passar se mode=poc
│   ├── banner.py               # injeta "CONTÉM PII — uso interno IGES" em respostas com pii_exposure
│   └── tests_data.py           # fixture com PII p/ smoke
├── audit/
│   ├── logger.py               # structlog setup
│   ├── store.py                # persistência (SQLite local p/ dev; Postgres prod)
│   └── exporter.py             # CSV/JSON dump
└── config.py                   # Pydantic Settings (env vars)

tests/
├── unit/
├── integration/                # respx p/ ES mock; anthropic VCR
└── e2e/                        # testcontainers ES + cassetes Claude
```

## 4. Fluxo detalhado de uma pergunta

```
1. Cliente envia POST /chat { "pergunta": "top 10 CIDs últimos 10 dias" }
2. Auth verifica OIDC; rate-limit OK.
3. audit.start(request_id, user, pergunta)
4. planner.py invoca Claude Opus 4.7 com:
     - system: planner_v1.md (descreve templates disponíveis)
     - tool defs: app.llm.tools.TOOL_SCHEMAS (gerado de es.registry)
     - user: pergunta
5. Claude responde com tool_use: { name: "top_cids", input: {indice: "solicitacao-ambulatorial",
     janela_dias: 10, top_n: 10, campo_cid: "codigo_cid_solicitado.keyword"} }
6. safety.py:
     - valida nome contra registry
     - valida input contra Pydantic model do template
     - rejeita se aparecer qualquer campo PII como filtro/projection
7. es.client.search(index_resolved, dsl_renderizado, timeout=5s)
8. anonymize.redactor.scrub(resultado)
     - aggs: passa direto (já é agregado, sem PII)
     - hits crus: drop dos campos PII listados em anonymize.fields
9. narrator.py invoca Claude Haiku 4.5 com:
     - system: narrator_v1.md (cite janela, índice, total — P5)
     - input: resultado anonimizado + metadados (template, params)
10. Resposta agregada:
     {
       "narrativa": "Nos últimos 10 dias (de 2026-05-10 a 2026-05-20)...",
       "dados": [{"cid": "I10", "descricao": "Hipertensão essencial", "count": 1284, "pct": 12.3}, ...],
       "proveniencia": {
         "indice": "sisreg-solicitacao-ambulatorial-53-...",
         "template": "top_cids",
         "janela": {"de": "2026-05-10", "ate": "2026-05-20"},
         "total_documentos": 10432,
         "request_id": "...",
         "executado_em": "2026-05-20T13:55:00Z"
       }
     }
11. audit.end(request_id, dsl, hits_count, latency)
```

## 5. Tool calling: contrato Pydantic

```python
# Esboço — ver app/llm/tools.py
class TopCidsParams(BaseModel):
    indice: Literal["solicitacao-ambulatorial", "marcacao-ambulatorial", "solicitacao-hospitalar"]
    janela_dias: int = Field(ge=1, le=365)
    top_n: int = Field(ge=1, le=50, default=10)
    campo_data: Literal["data_solicitacao", "data_aprovacao", "data_confirmacao", "data_marcacao"]
    campo_cid: Literal["codigo_cid_solicitado.keyword", "codigo_cid_agendado.keyword", "codigo_cid.keyword"]
```

`safety.py` rejeita qualquer tool input que não passe no Pydantic model — sem mensagem de "tente de novo": isso desliga a chamada e devolve "não consigo responder isso ainda" (RF-02).

## 6. Auth ao SISREG (Basic Auth)

**Confirmado em 2026-05-20** via response 401 do endpoint: `WWW-Authenticate: Basic realm="security" charset="UTF-8"` — o ES usa **HTTP Basic Auth** (plugin X-Pack Security padrão), não Bearer.

- Credenciais via env: `SISREG_USER` + `SISREG_PASS`.
- Cliente `app/es/client.py` monta `Authorization: Basic <base64(user:pass)>` automaticamente (parâmetro `basic_auth` do `elasticsearch.Elasticsearch`).
- Senhas **nunca** logadas — `structlog` deve censurar headers `Authorization`.
- Rotação de senha = atualizar `.env.local`; sem deploy.
- Endpoint canônico de teste: `GET /_security/_authenticate` → retorna `{username, roles, ...}` se OK.

## 6b. Modo POC — fluxo com PII (override de P2)

Quando o usuário pede um cenário individual ("últimos 5 atendidos"), o planner emite tool-call com flag `pii_exposure=true` e justificativa textual obrigatória. Fluxo:

```
1. POST /chat { pergunta, justificativa }   ← justificativa OBRIGATÓRIA quando pii_exposure
2. planner identifica intent individual → tool-call com flag pii_exposure=true
3. safety.py valida:
     - app_mode == "poc" (rejeita se "producao")
     - hoje <= POC_EXPIRES_AT (2026-07-19)
     - justificativa não-vazia, ≥ 20 chars
4. ES query executada (template ou free_text_search)
5. anonymize.redactor:
     - SEMPRE drop ALWAYS_MASKED_PII (CPF, endereço completo, CEP, CRM, etc.)
     - SE app_mode=poc E pii_exposure=true: deixa passar POC_VISIBLE_PII (nome, CNS, mãe, telefone, nascimento, sexo)
6. narrator recebe payload com PII permitido + flag
7. anonymize.banner prepend "[CONTÉM PII — uso interno IGES, distribuição proibida]" na narrativa
8. audit.log com pii_exposure=true, justificativa, prompt, payload → índice de retenção 365d
9. Resposta inclui:
     {
       "narrativa": "[CONTÉM PII — uso interno IGES, distribuição proibida]\n...",
       "pii_exposure": true,
       "justificativa_operador": "...",
       "dados": [...],
       "proveniencia": {..., "modo": "poc", "modo_expira_em": "2026-07-19"}
     }
```

Após `POC_EXPIRES_AT`, qualquer request com `pii_exposure=true` é rejeitado com 403 e mensagem "Modo POC expirado — migre para produção (ver constituição P2/P8)".

## 7. Tratamento de erros

| Erro | Resposta ao usuário | Log |
|---|---|---|
| Tool-call não mapeia template | "Não consigo responder isso ainda. Pode reformular?" | nível INFO, contagem em métrica. |
| Pydantic falha em parâmetros | Idem acima. | nível INFO. |
| ES timeout (>5 s) | "Consulta demorou demais — refine a janela." | nível WARN. |
| ES 4xx (auth/índice errado) | "Indisponível no momento." | nível ERROR + alerta. |
| ES 5xx | Idem. | ERROR + alerta. |
| Claude rate-limit | Retry com backoff (até 2x); senão "indisponível". | WARN. |
| Anonymizer detecta vazamento PII | **Aborta** a request, devolve 500 genérico. | ERROR crítico, page on-call. |

## 8. Testes (TDD)

- **Unidade**: cada template renderiza DSL determinística para inputs fixos.
- **Integração**: `respx` mocka ES; planner + safety + execução end-to-end com Claude VCR.
- **Anonymize**: snapshot test garante que nenhum campo PII listado escapa do redactor.
- **Constitution check**: teste que injeta DSL livre via prompt-injection e verifica que safety rejeita.

## 9. Critério de "pronto p/ release v1"

- 9 templates implementados (6 do manual + 3 extensões).
- Cobertura ≥ 85% no `app/anonymize/` e `app/es/safety.py`.
- Auditoria persistida + endpoint funcional.
- Ambiente de homologação rodando contra SISREG-DF com credencial real, validado por CGRA.
- Doc de operação em `docs/operations/`.
