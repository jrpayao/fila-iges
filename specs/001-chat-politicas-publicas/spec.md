# Spec 001 — Chat para política pública sobre fila SISREG

**Status**: draft v0.1 · **Owner**: Cláudio Júnior (Linedata @ IGES-DF) · **Data**: 2026-05-20

## 1. Visão

Disponibilizar à gestão do IGES-DF um **chat de análise** sobre a fila do SISREG-DF (regulação ambulatorial e hospitalar). O usuário formula perguntas em linguagem natural e recebe respostas agregadas, narrativas e tabulares, com origem rastreada — sem nunca expor PII de pacientes à camada conversacional.

A inspiração de UX é o **Databricks AI/BI Genie**: pergunta livre → query estruturada → tabela + gráfico + narrativa.

## 2. Personas

| Persona | Necessidade |
|---|---|
| **Coordenador CGRA** | "Quais especialidades estão estourando a fila esta semana?" — visão tática diária. |
| **Gestor IGES** | "Como evoluiu o tempo médio de espera por classificação de risco no trimestre?" — visão executiva. |
| **Analista de epidemiologia** | "Quais CIDs concentram cancelamento por solicitante nos últimos 30 dias?" — investigação. |
| **Auditor** | Trilha de toda pergunta feita, quem fez e o que foi devolvido. |

Pacientes individuais **não são persona**. Consultas com PK individual (CNS, CPF) ficam **fora de escopo** desta spec — exigem produto separado com auth forte.

## 3. Histórias de usuário (US)

### US-01 — Top CIDs em janela (cenário-âncora)
> Como coordenador CGRA, quero perguntar *"Top 10 CIDs solicitados nos últimos 10 dias"* e ver uma lista ordenada com código, descrição, contagem e percentual, para priorizar fluxos de regulação.

**Aceitação**: resposta em ≤ 5 s p95; cita índice, janela e total; sem PII; tabela CSV exportável.

### US-02 — Distribuição por classificação de risco
> Como gestor IGES, quero perguntar *"Como está a distribuição de risco da fila ambulatorial hoje?"* e ver porcentagens por nível (Prioridade 0–3).

### US-03 — Status atual da fila por unidade solicitante
> Como coordenador CGRA, quero perguntar *"Quais unidades solicitantes têm mais solicitações pendentes na fila de espera?"* e ver ranking das top N unidades.

### US-04 — Janela temporal de cancelamentos
> Como analista, quero perguntar *"Quais procedimentos foram mais cancelados pelo solicitante na última semana?"* para investigar churn de demanda.

### US-05 — Comparativo de janelas
> Como gestor, quero perguntar *"Compare top CIDs deste mês com o mês passado"* e ver delta.

### US-06 — Drill-down narrativo (sem PII)
> Como coordenador, ao ver um top CID inusual quero perguntar *"O que mais sabemos desse CID nessa janela?"* e ver: distribuição por risco, por unidade solicitante, por status — sempre agregado.

### US-07 — Auditoria
> Como auditor, quero ver todas as perguntas, prompts gerados e DSLs executados num período, para conformidade.

## 4. Requisitos funcionais (RF)

| ID | Descrição |
|---|---|
| **RF-01** | O sistema aceita pergunta em **português** via endpoint `POST /chat`. |
| **RF-02** | O sistema mapeia a pergunta para **um template DSL aprovado** (ver `contracts/elasticsearch.md`). Pergunta fora da capacidade dos templates devolve "não consigo responder isso ainda" — não improvisa. |
| **RF-03** | Parâmetros do template (janela, top N, filtros) são derivados via *tool calling* validado por Pydantic. |
| **RF-04** | Toda DSL é executada na **camada de execução**, nunca no LLM. |
| **RF-05** | O resultado é **anonimizado/agregado** antes de ser oferecido ao narrator-LLM (ver constituição P2). |
| **RF-06** | A resposta inclui: (a) narrativa, (b) dados tabulares estruturados, (c) bloco de proveniência (índice, janela, contagem total, template, request_id). |
| **RF-07** | Endpoint `GET /audit?from=…&to=…` retorna trilha (sem PII) para auditor. |
| **RF-08** | Endpoint `GET /health` reporta status: API SISREG alcançável, Claude API alcançável, latência média. |
| **RF-09** | Templates suportados na v1: **11 templates** allowlist (`top_cids`, `top_cids_marcacao`, `top_cids_hospitalar`, `top_unidades_solicitantes`, `top_unidades_executantes`, `top_procedimentos`, `distribuicao_risco`, `distribuicao_status`, `distribuicao_carater_hospitalar`, `fila_snapshot`, `free_text_search`). Detalhes em [`contracts/elasticsearch.md`](contracts/elasticsearch.md). |
| **RF-10** | Pipeline multi-agente: Router → (Planner ↔ Validator com retry) → safety → ES → anonymize → (Narrator ↔ Critic com retry). 5 agentes LLM + 3 camadas mecânicas. Audit completo (~9-12 eventos por request). |

## 5. Requisitos não-funcionais (RNF)

| ID | Categoria | Métrica |
|---|---|---|
| **RNF-01** | Latência | p50 ≤ 2 s; p95 ≤ 5 s; p99 ≤ 10 s para US-01–US-06. |
| **RNF-02** | Segurança | Toda chamada autenticada (OIDC/Keycloak IGES); rate-limit por usuário; logs sem PII. |
| **RNF-03** | LGPD | Conformidade demonstrável por testes (test-suite verifica ausência de PII em prompts e logs). |
| **RNF-04** | Disponibilidade | 99,5% em horário comercial (segunda a sexta, 7h–19h BRT). |
| **RNF-05** | Observabilidade | Logs estruturados JSON; métricas Prometheus; trace distribuído OpenTelemetry. |
| **RNF-06** | Custo de modelo | Orçamento mensal definido por env var; *circuit breaker* corta requisições ao atingir 90%. |
| **RNF-07** | Auditoria | Retenção 90 dias mínima; export em CSV/JSON. |
| **RNF-08** | Idioma | Português brasileiro em prompts, respostas e mensagens de erro. |

## 6. Escopo

### Em escopo (v1)
- Chat sobre **3 índices SISREG do DF**: marcação ambulatorial, solicitação ambulatorial, solicitação hospitalar.
- 6 cenários do manual + 3 templates de agregação (top CIDs, top unidades, distribuição por risco).
- API REST + UI mínima (single-page chat).
- Autenticação federada IGES.
- Auditoria estruturada.

### Fora de escopo (v1 — possíveis v2+)
- Consultas individuais com PK paciente (CNS/CPF).
- Comparativos inter-estados (`-nacional`).
- Escrita ou ações sobre o SISREG.
- Geração de gráficos automatizada (a UI pode exibir tabela e o usuário plota externamente).
- Integração direta com Mule/APIKit (avaliada em `research.md`, descartada por enquanto).
- Chat sobre dados que não estão no SISREG (e.g., AIH/SIA-SUS, CADWEB).

### Não escopo / explicitamente proibido
- DSL livre escrita por LLM.
- Cache que persista PII.
- Repasse de campos PII a Claude.

## 7. Métricas de sucesso

- **Adoção**: ≥ 10 perguntas/dia em produção após 30 dias (CGRA + IGES).
- **Resolução**: ≥ 80% das perguntas mapeadas a template (taxa de "não consigo responder" abaixo de 20%).
- **Precisão percebida**: NPS interno ≥ 7/10 com coordenadores CGRA após piloto de 60 dias.
- **Conformidade**: 100% das auditorias mensais sem ocorrência de PII em logs.

## 8. Riscos abertos

| # | Risco | Mitigação inicial |
|---|---|---|
| R-01 | Mapping ES não bate com dicionário (manual §5.4) | `research.md`: rodar `GET /<index>/_mapping` em ambiente real e diffar com `data-model.md`. |
| R-02 | Credencial SISREG-DF demora a ser provisionada | Suite de testes contra mock ES local (docker) durante desenvolvimento. |
| R-03 | LLM escolhe template errado para perguntas ambíguas | Fallback: pedir clarificação ao usuário antes de executar. |
| R-04 | Custo Claude estoura orçamento | Cache de prompts; circuit breaker (RNF-06). |
| R-05 | UX de tabelas longas em chat | Paginar; oferecer export. |

## 9. Perguntas em aberto (para `research.md`)

- Q1. Frontend: Streamlit, Next.js, ou integração direta no portal IGES?
- Q2. Onde rodar? On-prem IGES, cloud SUS, ou cloud Linedata?
- Q3. Credencial SISREG: por aplicação ou propagada por usuário?
- Q4. Como o usuário expressa "últimos 10 dias" — é janela rolling de hoje-10d ou semana ISO?
- Q5. O export CSV precisa ser síncrono (no chat) ou assíncrono (e-mail)?
