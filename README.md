# fila-eletiva

Plataforma conversacional sobre a fila do **SISREG** (Sistema de Regulação / Ministério da Saúde) para subsidiar política pública de saúde no **Distrito Federal**, sob o **IGES-DF** em parceria com a **ZELLO**.

A interação é via chat — análogo conceitual: **Databricks AI/BI Genie** — sobre os dados indexados no Elasticsearch do MS (`sisreg-es.saude.gov.br`).

## Cenário-âncora

> *"Me diga os tops CIDs de atendimento nos últimos 10 dias."*

O modelo de linguagem recebe a pergunta, gera uma consulta Elasticsearch DSL restrita por allowlist, executa via API SISREG, agrega os resultados (sem PII) e devolve uma resposta narrativa + dado tabular.

## Metodologia: Spec-Driven Development

Este repositório segue **SDD**. A spec é a fonte da verdade — código deriva dela.

```
fila-eletiva/
├── memory/
│   └── constitution.md                    # Princípios não-negociáveis
├── specs/
│   └── 001-chat-politicas-publicas/
│       ├── spec.md                        # WHAT/WHY
│       ├── plan.md                        # HOW técnico
│       ├── data-model.md                  # Dicionário derivado do manual SISREG
│       ├── contracts/
│       │   └── elasticsearch.md           # Templates DSL aprovados
│       ├── research.md                    # (pendente) Decisões com tradeoffs
│       └── tasks.md                       # (pendente) Quebra implementável
├── docs/
│   └── reference/
│       ├── manual_api_ms.pdf              # Original CGRA/MS v2.1
│       └── manual_api_ms.txt              # Extração textual
└── README.md
```

## Estado atual

- [x] Análise do manual oficial SISREG v2.1 (CGRA/MS, jun/2023)
- [x] `constitution.md` — invariantes do projeto (v1.1-POC até 2026-07-19)
- [x] `spec.md` — funcionalidade, personas, escopo
- [x] `plan.md` — arquitetura técnica
- [x] `data-model.md` — dicionário de dados normalizado + mappings reais
- [x] `contracts/elasticsearch.md` — 11 templates DSL implementados
- [x] **Motor implementado** (`app/`): pipeline multi-agente 5-LLM + 3 camadas mecânicas
  - 5 agentes: Router, Planner, Validator, Narrator, Critic
  - Retry loops: Planner↔Validator e Narrator↔Critic (max 2 attempts cada)
  - 11 templates: 10 especializados + 1 free_text_search com safety guard
- [x] **FastAPI** (`app/api.py`): POST /chat, GET /health, GET /audit
- [x] **UI Streamlit** (`ui/streamlit_app.py`): chat com histórico + sidebar
- [ ] `research.md` — registro de decisões com tradeoffs
- [ ] `tasks.md` — quebra em tarefas implementáveis (inclui migração POC→Prod)
- [ ] Testes pytest (anonymize, safety, registry, render)

## ⚠️ Modo POC ativo até 2026-07-19

Esta release está em **Modo POC** com overrides explícitos em P2, P3 e P8 da constituição. Detalhes em [memory/constitution.md](memory/constitution.md). **Release gates** antes do primeiro request com PII real:

1. **DPA OpenAI** com opt-out de treinamento assinado.
2. **Aprovação formal** de uso de PII pelo jurídico IGES + CGRA.
3. **Audit log** funcional (sem audit, sem POC).
4. **`.env.local`** fora do repo, chave rotacionada.

## Decisões já fixadas (2026-05-20)

| Tópico | Decisão POC | Decisão Produção (a partir de 2026-07-20) |
|---|---|---|
| Escopo de dados | DF (subnacional) — endpoint `-{uf}-{municipio}` | idem |
| Tratamento de PII | **`POC_VISIBLE_PII`** liberado para LLM em cenários individuais; **`ALWAYS_MASKED_PII`** segue mascarado. Banner obrigatório. | LLM **nunca** vê PII. |
| DSL | Templates allowlist + `free_text_search` com safety guard | Templates allowlist exclusiva. |
| Stack | Python 3.11+ · FastAPI · **OpenAI API** · elasticsearch-py | Python 3.11+ · FastAPI · **Claude API** · elasticsearch-py |
| Modelo LLM | `gpt-4o` (planner) · `gpt-4o-mini` (narrator) | `claude-opus-4-7` (planner) · `claude-haiku-4-5-20251001` (narrator) |
| Janela POC | **60 dias** — expira **2026-07-19** | n/a |
| Dado-fonte | **SISREG-DF real** (exige release gates) | SISREG-DF real |

## Próximo passo

Revisar `specs/001-chat-politicas-publicas/spec.md` e `plan.md`. Após aprovação:
1. Gerar `research.md` registrando alternativas descartadas e por quê.
2. Gerar `tasks.md` com a quebra implementável (TDD-first), **incluindo o item obrigatório de migração POC→Produção (Claude default) com data 2026-07-19**.
3. Resolver **release gates** acima (DPA OpenAI, aprovação jurídica).
4. Inicializar `app/` apenas então.
