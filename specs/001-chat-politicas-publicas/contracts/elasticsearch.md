# Contratos — Templates DSL aprovados

Este documento é a **allowlist** referida em `memory/constitution.md` P3. Qualquer DSL executada contra `sisreg-es.saude.gov.br` deve ser renderizada a partir de **exatamente um** dos templates abaixo. LLM nunca escreve DSL livre fora do `free_text_search` (que tem safety guard).

## Endpoint base (DF, confirmado 2026-05-20)

`https://sisreg-es.saude.gov.br/<tipo>-df-brasilia/_search` — UF e município no path são **aliases-texto** (constante `DF_INDEX_SUFFIX = "df-brasilia"`).

| Alias (path) | Índice físico | Mapping family |
|---|---|---|
| `solicitacao-ambulatorial-df-brasilia` | `solicitacao-ambulatorial` | dynamic_templates (codigo_* keyword direto) |
| `marcacao-ambulatorial-df-brasilia` | `marcacao-ambulatorial` | dynamic_templates (codigo_* keyword direto) |
| `solicitacao-hospitalar-df-brasilia` | `solicitacao-hospitalar-v3` | estático (tudo text+keyword) |

## Regra `.keyword` por família

| Tipo de campo | Ambulatorial | Hospitalar-v3 |
|---|---|---|
| `codigo_*` | keyword direto (SEM `.keyword`) | text+keyword (COM `.keyword`) |
| `descricao_*`, `nome_*`, `no_*` | text+keyword (use `.keyword` p/ terms) | text+keyword |
| `status_solicitacao` / `status` | text+keyword | text+keyword (campo é `status`) |
| `data_*`, `dt_*` | date | date |
| `laudo`, `procedimentos` | nested (precisa `nested query`) | n/a |
| `codigo_classificacao_risco` | keyword | long |
| `valor_proc_aih` | n/a | float |

## Auth, verbos e regras transversais

- **Verbo único permitido**: `GET` (POST `/_search` com body é convenção REST e não muta).
- **Auth**: HTTP Basic via env `SISREG_USER`/`SISREG_PASS`.
- **`size`** máximo de hits = 500 em templates fixos; **50** em `free_text_search`. Agregações usam `size: 0`.
- **Timeout** = 5 s (RNF-01).
- **`_source`** sempre projetado.
- **Filtro DF defensivo**: `term codigo_uf_regulador` (ambulatorial) ou `term codigo_uf_regulador.keyword` (hospitalar) com valor `"53"`.
- **Anonimização**:
  - Sempre: drop de `ALWAYS_MASKED_PII`.
  - POC + `pii_exposure=true`: deixa passar `POC_VISIBLE_PII`.
  - Produção (≥ 2026-07-20): drop também de `POC_VISIBLE_PII`.

## Templates implementados (11)

Resumo. Cada um tem módulo em `app/es/templates/<nome>.py`.

| # | Nome | Índice | Janela? | O que retorna |
|---|---|---|---|---|
| 1 | `top_cids` | solicitacao-ambulatorial | sim | Top N CIDs solicitados |
| 2 | `top_cids_marcacao` | marcacao-ambulatorial | sim | Top N CIDs em marcação (atendidos/agendados/cancelados/todos) |
| 3 | `top_cids_hospitalar` | solicitacao-hospitalar | sim | Top N CIDs em internações |
| 4 | `top_unidades_solicitantes` | ambulatorial (sol ou marc) | sim | Top N unidades solicitantes |
| 5 | `top_unidades_executantes` | marcacao ou hospitalar | sim | Top N unidades executantes |
| 6 | `top_procedimentos` | solicitacao-ambulatorial | sim | Top N procedimentos (nested) |
| 7 | `distribuicao_risco` | ambulatorial | sim | Buckets por classificação de risco |
| 8 | `distribuicao_status` | ambulatorial | sim | Buckets por status_solicitacao |
| 9 | `distribuicao_carater_hospitalar` | solicitacao-hospitalar | sim | URGENTE x ELETIVA |
| 10 | `fila_snapshot` | solicitacao-ambulatorial | **não** | Estado atual da fila |
| 11 | `free_text_search` | qualquer | livre | DSL livre validado por safety guard |

Detalhes individuais abaixo.

---

## T1 — `top_cids`

**Cenário-âncora US-01**. Top N CIDs solicitados em janela ambulatorial.

```http
GET solicitacao-ambulatorial-df-brasilia/_search
```

**Parâmetros**:
| Nome | Tipo | Validação |
|---|---|---|
| `janela_dias` | int | 1..365 |
| `top_n` | int | 1..50, default 10 |
| `base_temporal` | enum | `data_solicitacao` (default) ou `data_atualizacao` |

**Body**:
```json
{
  "size": 0,
  "track_total_hits": true,
  "query": {
    "bool": {
      "must": [
        {"term": {"codigo_uf_regulador": "53"}},
        {"range": {"<base_temporal>": {"gte": "now-{janela_dias}d/d", "lte": "now/d"}}}
      ]
    }
  },
  "aggs": {
    "top_cids": {
      "terms": {
        "field": "codigo_cid_solicitado",
        "size": "{top_n}",
        "shard_size": "max(200, top_n*20)",
        "order": {"_count": "desc"}
      },
      "aggs": {
        "enriquecimento": {
          "top_hits": {"size": 1, "_source": ["descricao_cid_solicitado"]}
        }
      }
    }
  }
}
```

---

## T2 — `top_cids_marcacao`

Top N CIDs em marcação ambulatorial, parametrizado por **tipo**.

**Parâmetros**:
| Nome | Tipo | Validação |
|---|---|---|
| `tipo` | enum | `atendidos`, `agendados`, `cancelados`, `todos` |
| `janela_dias` | int | 1..365 |
| `top_n` | int | 1..50, default 10 |
| `qual_cid` | enum | `solicitado` ou `agendado` (default) |

**Status filter por tipo**:
- `atendidos` → `["AGENDAMENTO / CONFIRMADO / EXECUTANTE"]` + `data_confirmacao`
- `agendados` → AGENDADA/AUTORIZADA/PENDENTE CONFIRMAÇÃO + `data_aprovacao`
- `cancelados` → CANCELADA/NEGADA/DEVOLVIDA + `data_solicitacao`
- `todos` → sem filtro + `data_solicitacao`

---

## T3 — `top_cids_hospitalar`

Top N CIDs em solicitações hospitalares (família hospitalar-v3, `codigo_cid.keyword`).

**Parâmetros**:
| Nome | Tipo | Validação |
|---|---|---|
| `janela_dias` | int | 1..365 |
| `top_n` | int | 1..50, default 10 |
| `base_temporal` | enum | `data_solicitacao` (default), `data_internacao`, `data_atualizacao` |

---

## T4 — `top_unidades_solicitantes`

Top N unidades solicitantes em ambulatorial.

**Parâmetros**:
| Nome | Tipo | Validação |
|---|---|---|
| `indice` | enum | `solicitacao-ambulatorial` ou `marcacao-ambulatorial` |
| `tipo` | enum | `todos` (default) ou `cancelados` (só marcacao) |
| `janela_dias` | int | 1..365 |
| `top_n` | int | 1..50 |

Agrega em `codigo_unidade_solicitante` com `top_hits` para `nome_unidade_solicitante`.

---

## T5 — `top_unidades_executantes`

Top N unidades executantes em marcação ou hospitalar.

**Parâmetros**:
| Nome | Tipo | Validação |
|---|---|---|
| `indice` | enum | `marcacao-ambulatorial` ou `solicitacao-hospitalar` |
| `apenas_confirmados` | bool | só marcacao: filtra status=CONFIRMADO |
| `janela_dias` | int | 1..365 |
| `top_n` | int | 1..50 |

Marcação usa `codigo_unidade_executante` (keyword direto). Hospitalar usa `codigo_unidade_executante.keyword`.

---

## T6 — `top_procedimentos`

Top N procedimentos solicitados — **nested agg** em `procedimentos.codigo_sigtap`.

**Parâmetros**:
| Nome | Tipo | Validação |
|---|---|---|
| `janela_dias` | int | 1..365 |
| `top_n` | int | 1..50 |

Body usa `aggs.nested.path = "procedimentos"` + sub-agg `terms` em `procedimentos.codigo_sigtap`. Enriquece com `top_hits` projetando `procedimentos.codigo_sigtap`, `descricao_sigtap`, `codigo_interno`, `descricao_interna`.

---

## T7 — `distribuicao_risco`

Buckets de `codigo_classificacao_risco` (1..4 = Emergência/Urgência/Não urgente/Eletivo).

**Parâmetros**:
| Nome | Tipo | Validação |
|---|---|---|
| `indice` | enum | `solicitacao-ambulatorial` ou `marcacao-ambulatorial` |
| `janela_dias` | int | 1..365, default 30 |

`consolidate()` traduz código → descrição humana usando tabela do manual §5.

---

## T8 — `distribuicao_status`

Buckets de `status_solicitacao.keyword`.

**Parâmetros**:
| Nome | Tipo | Validação |
|---|---|---|
| `indice` | enum | `solicitacao-ambulatorial` ou `marcacao-ambulatorial` |
| `janela_dias` | int | 1..365, default 30 |
| `base_temporal` | enum | `data_solicitacao` ou `data_atualizacao` (default) |
| `top_n` | int | 1..30, default 20 |

---

## T9 — `distribuicao_carater_hospitalar`

Buckets de `carater.keyword` (URGENTE x ELETIVA) em internações.

**Parâmetros**:
| Nome | Tipo | Validação |
|---|---|---|
| `janela_dias` | int | 1..365, default 30 |

---

## T10 — `fila_snapshot`

**Sem range temporal** — estado AGORA. Filtra status pendentes (`PENDENTE/REGULADOR`, `PENDENTE/FILA DE ESPERA`, `REENVIADA/REGULADOR`) e agrega por status (e opcionalmente por risco).

**Parâmetros**:
| Nome | Tipo | Validação |
|---|---|---|
| `incluir_distribuicao_por_risco` | bool | default true — agrega também por classificação |

Retorna `total_pendentes_agora`, `por_status[]` e (opcional) `por_risco[]`.

---

## T11 — `free_text_search` (**POC ONLY**, expira em 2026-07-19)

Override constitucional P3. Permite ao LLM emitir DSL livre, validado por **safety guard com allowlist negativa**.

**Parâmetros** (validados em Pydantic):
| Campo | Tipo | Validação |
|---|---|---|
| `indice` | enum | `solicitacao-ambulatorial`, `marcacao-ambulatorial`, `solicitacao-hospitalar` |
| `dsl` | dict | precisa passar `app/es/safety.py:validate` |
| `justificativa` | str | ≥ 20 chars, auditada |

**Regras do safety guard** (`app/es/safety.py`):

| ✅ Permitido | ❌ Bloqueado |
|---|---|
| `GET _search` | qualquer outro verbo/endpoint |
| `query`, `aggs`, `_source`, `sort`, `size` | `script`, `script_score`, `runtime_mappings`, `scripted_metric`, `function_score`, `search_template` |
| `size <= 50` (hits) ou `size: 0` (só aggs) | `size > 50` |
| Filtros em campos não-PII e `POC_VISIBLE_PII` | Filtros em `ALWAYS_MASKED_PII` (mesmo no POC) |
| Índices `sisreg-*-df-brasilia` | Índices fora de DF |

Após `POC_EXPIRES_AT`: template não é registrado, qualquer tentativa retorna 403.

---

## Vocabulário oficial de `status_solicitacao` (helper)

Constante em `app/es/templates/_helpers.py`:

```python
STATUS_ATENDIDOS  = ["AGENDAMENTO / CONFIRMADO / EXECUTANTE"]
STATUS_AGENDADOS  = ["SOLICITAÇÃO / AGENDADA / FILA DE ESPERA",
                     "SOLICITAÇÃO / AGENDADA / SOLICITANTE",
                     "SOLICITAÇÃO / AUTORIZADA / REGULADOR",
                     "SOLICITAÇÃO / AGENDADA / COORDENADOR",
                     "AGENDAMENTO / PENDENTE CONFIRMAÇÃO / EXECUTANTE"]
STATUS_CANCELADOS = ["SOLICITAÇÃO / CANCELADA / SOLICITANTE",
                     "SOLICITAÇÃO / CANCELADA / REGULADOR",
                     "SOLICITAÇÃO / CANCELADA / COORDENADOR",
                     "AGENDAMENTO / CANCELADO / REGULADOR",
                     "AGENDAMENTO / CANCELADO / SOLICITANTE",
                     "AGENDAMENTO / CANCELADO / COORDENADOR",
                     "SOLICITAÇÃO / NEGADA / REGULADOR",
                     "SOLICITAÇÃO / DEVOLVIDA / REGULADOR"]
STATUS_PENDENTES  = ["SOLICITAÇÃO / PENDENTE / REGULADOR",
                     "SOLICITAÇÃO / PENDENTE / FILA DE ESPERA",
                     "SOLICITAÇÃO / REENVIADA / REGULADOR"]
STATUS_FALTA      = ["AGENDAMENTO / FALTA / EXECUTANTE"]
```

**Crítico** — esses valores são **strings literais com `/ ` (barra-espaço) como separador**. Filtrar com componentes separados (`["AGENDAMENTO", "CONFIRMADO", "EXECUTANTE"]`) NÃO casa nada.
