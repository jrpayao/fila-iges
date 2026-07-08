# Spec 002 — Motor de vagas SISREG (IGES)

**Versão**: 0.1 — 2026-07-07
**Status**: em implementação (Fase 1 concluída)
**Constituição**: [Emenda v3.0](../../memory/constitution.md#emenda-v30--2026-07-07--virada-de-fonte-api-de-vagas-sisreg-iges)

## WHAT / WHY

Plataforma conversacional que dá **inteligência sobre a capacidade de vagas SISREG**
ofertada pela rede IGES-DF: quanto se oferece, onde, de quê, quanto está bloqueado
e como isso evolui no tempo. Substitui os motores anteriores (SISREG-ES e MV/Oracle).

**Cenário-âncora**: *"Quais procedimentos têm mais vagas disponíveis neste mês e
quanto da capacidade está bloqueada?"*

## Fonte de dados

`GET https://api.igesdf.org.br/iges/dados_vagas_sisreg?mes=MM&ano=AAAA`

- Auth por header `client_id` + `client_secret`. GET-only.
- Retorno: lista JSON, ~850 registros/competência. Competência sem dado → HTML de erro.
- Histórico disponível ≥ jan/2025. Snapshot mensal (`data_extracao`).
- **Sem PII.**

### Schema do registro (16 campos)

| Campo | Papel | Notas |
|---|---|---|
| `cod_procedimento`, `procedimento` | dimensão | SIGTAP (código + nome; nome traz `[FISICO]` e grupo) |
| `hospital_cnes`, `hospital` | dimensão | 75 unidades |
| `mes_comp`, `ano_comp` | dimensão temporal | competência (AAAAMM derivado) |
| `tipo` | dimensão | `GLOBAL` (observado) |
| `vagas_disponiveis` | **medida** | oferta total disponível |
| `ativ_1`, `ativ_retorno`, `ativ_reserva` | medida | vagas ativas por tipo (1ª vez / retorno / reserva) |
| `bloq_1`, `bloq_retorno`, `bloq_reserva` | medida | vagas bloqueadas por tipo |
| `data_extracao` | metadado | instante do snapshot |
| `id` | chave técnica | — |

## Escopo

**Dentro**: capacidade/oferta, bloqueios, mix 1ª-vez/retorno/reserva, rankings,
distribuições, lacunas de acesso (procedimento com 0 vaga), tendência entre competências.

**Fora** (limite da fonte): tempo de espera, tamanho de fila, demanda, faltas,
conduta clínica individual (P7). Perguntas de fila/espera recebem ressalva de escopo.

## Métricas (catálogo v3 — a definir na Fase 2)

Derivadas do schema, todas `snapshot`:
- `vagas_disponiveis` (soma)
- `vagas_ativas` = `ativ_1 + ativ_retorno + ativ_reserva`
- `vagas_bloqueadas` = `bloq_1 + bloq_retorno + bloq_reserva`
- `taxa_bloqueio` = `vagas_bloqueadas / (ativas + bloqueadas)` (derivada, %)
- mix por tipo de vaga (1ª vez / retorno / reserva)

Dimensões fechadas: `procedimento`, `grupo_procedimento`, `hospital`, `tipo_vaga`, `competencia`.

## Arquitetura

Reaproveita o motor v2 (`app/agent/`): `Planner → Plan → primitivas → compose →
Envelope → Synthesizer`. Troca apenas a camada de dados e o catálogo:

- `app/vagas/client.py` — HTTP GET-only, auth header, guard de content-type (HTML→sem dado). ✅
- `app/vagas/store.py` — cache SQLite por competência + carga em DataFrame tipado. ✅
- `app/agent/metrics.py` — catálogo de vagas (Fase 2).
- `app/agent/primitives.py` — executar sobre DataFrame (pandas), não ES (Fase 2).
- `app/agent/resolver.py` — resolver procedimento (SIGTAP) + hospital (CNES) (Fase 2).

## Critérios de aceite

- Bateria de perguntas de capacidade com pass rate ≥ 90% (Fase 4).
- Todo número no Envelope rastreável à agregação sobre o DataFrame (P1).
- Resposta cita competência + fonte (P2/P8).
- Pergunta de fila/espera → ressalva de escopo, não número inventado.

## Faseamento

- [x] **Fase 1** — adapter de dados (client + store + smoke). 19 competências, 15.888 regs.
- [ ] **Fase 2** — catálogo + primitivas sobre DataFrame + resolver.
- [ ] **Fase 3** — planner/prompts repontados + synthesizer.
- [ ] **Fase 4** — bateria de capacidade + gate.
- [ ] **Fase 5** — UI/API apontando pro motor de vagas.
