# fila-eletiva — Vagas SISREG DF

Plataforma conversacional sobre a **oferta de vagas do SISREG** (Sistema de Regulação /
Ministério da Saúde) na rede do **IGES-DF**, em parceria com a **ZELLO**. O usuário
pergunta em português; o agente planeja, agrega o dado e responde com prosa + gráfico,
sempre com número rastreável (nada de alucinação numérica).

> **Fonte v3 (atual)**: API de vagas SISREG publicada pelo IGES. Substitui as fontes
> anteriores (SISREG-ES e a exploração MV/Oracle). Ver [memory/constitution.md](memory/constitution.md)
> — **Emenda v3.0** — e [specs/002-vagas-sisreg/spec.md](specs/002-vagas-sisreg/spec.md).

## O que dá pra perguntar

É um produto de **capacidade / oferta** (não de fila/espera). Exemplos:

- *"Quais procedimentos têm mais vagas disponíveis neste mês?"*
- *"Quanto da capacidade está bloqueada no HUB?"*
- *"Como evoluiu a oferta de ressonância magnética ao longo dos meses?"*
- *"Qual a distribuição das vagas ativas por tipo (1ª vez / retorno / reserva)?"*
- *"Compare o Hospital de Base com os demais em oferta de vagas."*

**Fora do escopo da fonte**: tempo de espera, tamanho de fila, demanda, faltas. Perguntas
assim são respondidas com a capacidade relacionada + ressalva explícita ("a fonte cobre a
oferta de vagas, não o tempo de espera").

## Fonte de dados

`GET https://api.igesdf.org.br/iges/dados_vagas_sisreg?mes=MM&ano=AAAA`

- Auth por **headers** `client_id` + `client_secret`. GET-only.
- Retorno: lista JSON (~850 regs/competência). Competência sem dado → HTML de erro (tratado).
- Histórico ≥ jan/2025. Snapshot mensal (`data_extracao`). **Sem PII.**
- Um registro = procedimento × hospital × competência, com `vagas_disponiveis`,
  `ativ_{1,retorno,reserva}`, `bloq_{1,retorno,reserva}`.

## Arquitetura

Pipeline (reusa o "motor v2": Envelope, chart, audit, api, UI):

```
pergunta → Planner (LLM, structured output) → VagasPlan
        → resolver (procedimento SIGTAP / hospital CNES / competência)
        → primitivas sobre DataFrame (pandas)
        → Envelope (fonte única do número, P4)
        → Synthesizer (LLM, lê só o Envelope) → prosa + gráfico
```

Camadas em [app/vagas/](app/vagas/):

| Módulo | Papel |
|---|---|
| `client.py` | HTTP GET-only, auth por header, guard de content-type |
| `store.py` | cache SQLite por competência + carga em DataFrame tipado |
| `catalog.py` | métricas (vagas_disponiveis/ativas/bloqueadas, taxa_bloqueio, mix) + dimensões |
| `resolver.py` | resolve procedimento/hospital/competência (data-driven + aliases HUB/HBDF/…) |
| `primitives.py` | total / taxa_bloqueio / breakdown / mix_tipo_vaga / timeseries / compare → Envelope |
| `plan.py`, `prompts.py`, `planner.py`, `synthesizer.py` | planejamento e narrativa (OpenAI) |
| `orchestrator.py` | costura o pipeline; clarificação (P10); audit (P15) |

O dado é pequeno (~15k linhas) e sem PII → **sem Oracle, sem Vanna, sem text-to-SQL**: cabe
inteiro em memória, agregado por pandas, com governança por construção.

```
app/
├── vagas/            # motor v3 (fonte de vagas)
├── agent/            # motor v2 reaproveitado (envelope, chart, prompts…)
├── engine.py         # adapter fino → app.vagas.orchestrator (v3-vagas)
├── api.py            # FastAPI: POST /chat, GET /health, GET /audit
└── config.py         # settings (.env) — IGES_VAGAS_*
ui/streamlit_app.py   # chat
specs/002-vagas-sisreg/spec.md
memory/constitution.md
scripts/              # smokes + bateria de regressão
```

## Rodando localmente

1. **Ambiente + deps**
   ```bash
   python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **Credenciais** — copie `.env.example` para `.env` e preencha `IGES_VAGAS_CLIENT_ID` /
   `IGES_VAGAS_CLIENT_SECRET` e `OPENAI_API_KEY`. (`.env` é gitignored.)
3. **Popular o cache** (baixa jan/2025 → competência atual):
   ```bash
   python scripts/smoke_vagas.py
   ```
   (o `get_df` também faz auto-bootstrap se o cache estiver vazio.)
4. **API + UI**
   ```bash
   uvicorn app.api:app --port 8000
   streamlit run ui/streamlit_app.py        # noutro terminal
   ```

## Testes / regressão

- `scripts/battery_vagas.py` — bateria de capacidade (8 categorias, **20/20**), com gate.
- `scripts/smoke_vagas*.py` — smokes por fase (data → primitivas → agente → engine).

## Princípios (constituição)

Número nasce de agregação rastreável (P1); resposta declara competência + fonte (P2/P8);
Envelope é fonte única (P4); tudo é `snapshot` (P5); sem PII (P6, trivial nesta fonte);
sem recomendação clínica individual (P7); vocabulário fechado (P9); clarificação só quando
necessária (P10); auditoria fim-a-fim (P15); spec-first (P16). Detalhes e a **Emenda v3.0**
em [memory/constitution.md](memory/constitution.md).

## Histórico de arquitetura

- **v2 (SISREG-ES)** — motor de catálogo + primitivas sobre Elasticsearch. Arquivado na
  branch `feat/agente-analitico`.
- **MV/Oracle (explorado, engavetado)** — text-to-SQL sobre o HIS MV; descartado por
  complexidade/PII em favor da API de vagas.
- **v3 (atual)** — motor de vagas sobre a API IGES. Branch `feat/motor-vagas-sisreg`.

## Pendências

- Testes pytest formais (hoje: smokes + bateria).
- Provider **Claude** (Emenda E7): plugável quando houver `ANTHROPIC_API_KEY` (hoje roda OpenAI).
