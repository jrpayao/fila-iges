# Data Model — Dicionário SISREG (normalizado)

**Origem**: Manual SISREG v2.1 (CGRA/MS, jun/2023), seções 5.1–5.3.  
**Status**: extraído do PDF; mapping real do ES deve ser confrontado em homologação (R-01 da spec).

## 1. Índices

| Alias ES (path) | Endpoint base DF concreto | Granularidade | Volume típico esperado |
|---|---|---|---|
| `solicitacao-ambulatorial-df-brasilia` | `https://sisreg-es.saude.gov.br/solicitacao-ambulatorial-df-brasilia/_search` | 1 documento por solicitação ambulatorial (snapshot da fila) | ≥ 10.000 |
| `marcacao-ambulatorial-df-brasilia` | `https://sisreg-es.saude.gov.br/marcacao-ambulatorial-df-brasilia/_search` | 1 documento por marcação/agendamento (inclui histórico de status) | muito alto |
| `solicitacao-hospitalar-df-brasilia` | `https://sisreg-es.saude.gov.br/solicitacao-hospitalar-df-brasilia/_search` | 1 documento por solicitação de internação | médio |

**Descobertas 2026-05-20** (via doc real + `GET /_mapping`):
- Path usa **aliases-texto** `{uf}=df` e `{municipio}=brasilia` — **NÃO** códigos IBGE.
- Índices físicos: `solicitacao-ambulatorial` (sem versão), `marcacao-ambulatorial` (sem versão), **`solicitacao-hospitalar-v3`** (com versão!). Aliases são a interface estável; nunca codar contra nome físico.
- **As 3 famílias têm convenções de mapping DIFERENTES** (ver §1.5).

**Códigos numéricos para filter**:
- `codigo_uf_regulador` = `"53"` (IBGE DF)
- `codigo_central_reguladora` = `"530010"` (DF Central) — descoberto via doc real, substitui exemplos `32C164` do manual (que eram Espírito Santo).

## 1.5 Famílias de mapping (descoberto via `GET /_mapping`)

Os 3 índices não seguem o mesmo padrão — cada um exige sintaxe diferente em `term`/`terms`/agg `field`:

### Família ambulatorial (`solicitacao-ambulatorial`, `marcacao-ambulatorial`)
Usa `dynamic_templates`:
- `codigo_*` → **`keyword` direto** (sem subfield `.keyword`)
- `cpf_*` → keyword direto
- `uf_*` → keyword direto
- `data_*`, `dt_*` → `date`
- `no_*`, `nome_*`, `descricao_*` → `text` com analyzer `brazilian` + subfield `.keyword`
- `st_*` (só marcacao) → keyword direto
- `cep_*`, `telefone`, `tipo_logradouro_*`, `numero_*` (campos explícitos) → keyword direto
- `sigla_situacao` em `solicitacao-ambulatorial` → **keyword direto**; em `marcacao-ambulatorial` → **text+keyword**
- `laudo` → **`nested`** (com `data_observacao`, `operador`, `situacao`, etc.)
- `procedimentos` → **`nested` SÓ em `solicitacao-ambulatorial`** (com `codigo_interno`, `codigo_sigtap`, `descricao_*`)
- `status_solicitacao` → text+keyword

### Família hospitalar-v3 (`solicitacao-hospitalar-v3`)
Mapping estático (sem dynamic templates):
- Praticamente **tudo** texto é `text+keyword` (precisa `.keyword` para `term`/`terms`/sort/terms agg)
- `data_*`, `dt_*` → `date`
- Numéricos: `codigo_classificacao_risco`, `codigo_natureza_lesao`, `codigo_solicitacao`, `numero_aih`, `numero_digito_aih` → `long`
- `valor_proc_aih` → `float`
- **Sem `laudo`**, **sem `procedimentos` nested** — estrutura toda flat.
- Campo de status se chama **`status`** (não `status_solicitacao` como no manual).
- Campo de CID se chama **`codigo_cid`** + `descricao_cid` (não `codigo_cid_solicitado` como ambulatorial).
- Campos exclusivos: `carater` (URGENTE/ELETIVA), `numero_aih*`, `valor_proc_aih`, `data_alta`, `data_internacao`, `data_previsao_alta`, `data_reserva`, `hora_*`, `nome_clinica`, `nome_leito`, `nome_responsavel`, `telefone_responsavel`, `sintomas`, `exames`, `justificativa_impedimento`, `operador_alta`, `operador_internacao`.

### Regra prática para query

| O que você quer | Ambulatorial | Hospitalar-v3 |
|---|---|---|
| `term codigo_uf_regulador: "53"` | sem `.keyword` ✅ | precisa `.keyword` |
| `terms codigo_cid_solicitado` (agg) | sem `.keyword` ✅ | n/a (campo é `codigo_cid` lá) |
| `terms codigo_cid.keyword` (agg) | n/a | precisa `.keyword` |
| `terms descricao_cid_solicitado.keyword` (agg) | precisa `.keyword` | n/a |
| `term status_solicitacao.keyword: "..."` | precisa `.keyword` | (lá é `status.keyword`) |
| `range data_solicitacao` | funciona direto (é `date`) | funciona direto |

## 2. Campos por cenário de uso

### 2.1 CID — códigos clínicos
| Índice | Campo do CID | Campo descrição |
|---|---|---|
| `solicitacao-ambulatorial` | `codigo_cid_solicitado` (4 chars, "X00" ou "X000") | `descricao_cid_solicitado` |
| `marcacao-ambulatorial` | `codigo_cid_solicitado` **e** `codigo_cid_agendado` | `descricao_cid_solicitado`, `descricao_cid_agendado` |
| `solicitacao-hospitalar` | `codigo_cid` | `descricao_cid` |

**Observação de mapping**: o manual classifica como *Texto*. Para `terms` aggregation, precisaremos do sub-campo `.keyword` (padrão do ES dinâmico) — confrontar com `GET /<index>/_mapping`.

### 2.2 Datas relevantes
| Campo | Significado | Usado por template |
|---|---|---|
| `data_solicitacao` | Quando a solicitação foi feita | T-Novas, T-Fila, T-TopCids (entrada) |
| `data_aprovacao` | Quando a regulação aprovou | T-Agendadas |
| `data_confirmacao` | Quando o agendamento foi confirmado | T-Atendidas |
| `data_marcacao` | Quando a marcação foi feita | T-TopCids (atendimento) |
| `dt_atualizacao` | Última atualização (ambulatorial) | snapshot |
| `data_internacao` | Quando o paciente foi internado | hospitalar |
| `data_alta` | Quando teve alta | hospitalar |
| `data_cancelamento` | Quando foi cancelado | T-Canceladas |

Formato: `YYYY-MM-DDThh24:MI:SS.USZ` (compatível com `range` query nativo do ES).

### 2.3 Status
| Campo | Tipo | Notas |
|---|---|---|
| `status_solicitacao` | Texto | Use `status_solicitacao.keyword` em `terms` query. Valores possíveis: ver §4. |
| `sigla_situacao` | Texto 1 char | `P`,`R`,`D`,`N`,`A`,`C` — ver §5. |

### 2.4 Classificação de risco
| Campo | Tipo | Valores |
|---|---|---|
| `codigo_classificacao_risco` | Numero (1 dígito) | `1=Emergência`, `2=Urgência`, `3=Não urgente`, `4=Eletivo` |

### 2.5 Unidade solicitante / executante
| Campo | Tipo | Uso |
|---|---|---|
| `codigo_unidade_solicitante` | Texto CNES (7) | Agg de unidades |
| `nome_unidade_solicitante` | Texto | Display |
| `codigo_unidade_executante` | Texto CNES (7) | Agg (marcação) |
| `nome_unidade_executante` | Texto | Display |
| `codigo_unidade_desejada` | Texto CNES ou vazio | Solicitação ambulatorial |

### 2.6 Procedimento
| Campo | Tipo | Notas |
|---|---|---|
| `codigo_interno_procedimento` | Texto 7 | Código interno SISREG |
| `descricao_interna_procedimento` | Texto | Display |
| `codigo_sigtap_procedimento` | Texto 10 | SIGTAP padrão MS |
| `descricao_sigtap_procedimento` | Texto | Display |
| `codigo_grupo_procedimento` | Texto 7 | Agrupamento |
| `nome_grupo_procedimento` | Texto | Display |

### 2.7 Tipo de regulação / fila / vaga
| Campo | Valores |
|---|---|
| `codigo_tipo_regulacao` | `R`=Regulado, `F`=Fila de espera |
| `codigo_tipo_fila` | `1`=Regulado, `2`=Não regulado |
| `codigo_tipo_vaga_solicitada` | `1`=Primeira vez, `2`=Retorno |
| `codigo_tipo_vaga_consumida` | `0`, `1`, `2` (sem definição no manual — Q em research) |

### 2.8 Caráter (hospitalar)
| Campo | Valores |
|---|---|
| `carater` | `URGENTE`, `ELETIVA` |

## 3. Campos PII

A classificação segue **P2 da constituição** com duas listas para o **Modo POC** (vigente até 2026-07-19):

### 3.1 `POC_VISIBLE_PII` — permitido ao LLM **somente** durante POC

Liberados para cenários individuais como *"últimos N atendidos"*. Após 2026-07-19 voltam para a categoria proibida (P2 default).

| Campo | Tipo | Onde aparece |
|---|---|---|
| `no_usuario` | Nome paciente | todos |
| `cns_usuario` | Identificador SUS (15 dígitos) | todos |
| `no_mae_usuario` | Nome mãe | todos |
| `telefone` | Contato paciente | todos |
| `dt_nascimento_usuario` | Data de nascimento | todos |
| `sexo_usuario` | MASCULINO / FEMININO | todos |

### 3.2 `ALWAYS_MASKED_PII` — proibido em **qualquer modo** (inclusive POC)

| Campo | Tipo | Justificativa |
|---|---|---|
| `cpf_usuario` | CPF paciente | Identificador nacional cross-domain; expor em LLM amplia superfície de risco. |
| `endereco_paciente_residencia` | Endereço | Geolocaliza o paciente. |
| `bairro_paciente_residencia` | Endereço | Geolocaliza. |
| `cep_paciente_residencia` | Endereço | Geolocaliza. |
| `numero_paciente_residencia` | Endereço | Geolocaliza. |
| `complemento_paciente_residencia` | Endereço | Geolocaliza. |
| `tipo_logradouro_paciente_residencia` | Endereço | Geolocaliza. |
| `cpf_medico_solicitante` | PII profissional | CPF profissional não compete ao caso clínico. |
| `cpf_profissional_executante` | PII profissional | idem |
| `cpf_profissional_solicitante` | PII profissional | idem |
| `nome_medico_solicitante` | PII profissional | nome profissional em chat amplia exposição. |
| `nome_profissional_executante` | PII profissional | idem |
| `nome_responsavel` | PII responsável legal | Hospitalar — sensível. |
| `telefone_responsavel` | PII responsável legal | idem |
| `numero_crm` | PII profissional | idem |

### 3.3 Não-PII — sempre permitidos

| Campo | Notas |
|---|---|
| `codigo_unidade_*`, `nome_unidade_*` | Entidades públicas SUS/CNES, não-PII. |
| `municipio_paciente_residencia`, `uf_paciente_residencia`, `nome_municipio_nascimento`, `uf_municipio_nascimento` | Granularidade municipal não identifica indivíduo. |
| Todos os códigos de procedimento, CID, status, classificação de risco. | Dados clínicos agregáveis. |

## 4. Tabela de `status_solicitacao` (PDF §6.3 ambulatorial)

| Sigla | Descrição |
|---|---|
| SOL/PEN/REG | SOLICITAÇÃO / PENDENTE / REGULADOR |
| SOL/DEV/REG | SOLICITAÇÃO / DEVOLVIDA / REGULADOR |
| SOL/NEG/REG | SOLICITAÇÃO / NEGADA / REGULADOR |
| SOL/PEN/FILA | SOLICITAÇÃO / PENDENTE / FILA DE ESPERA |
| SOL/REE/REG | SOLICITAÇÃO / REENVIADA / REGULADOR |
| AGE/PEN/EXEC | AGENDAMENTO / PENDENTE CONFIRMAÇÃO / EXECUTANTE |
| AGE/CONF/EXEC | AGENDAMENTO / CONFIRMADO / EXECUTANTE |
| SOL/CAN/SOL | SOLICITAÇÃO / CANCELADA / SOLICITANTE |
| SOL/CAN/REG | SOLICITAÇÃO / CANCELADA / REGULADOR |
| SOL/CAN/COOR | SOLICITAÇÃO / CANCELADA / COORDENADOR |
| AGE/CAN/REG | AGENDAMENTO / CANCELADO / REGULADOR |
| AGE/CAN/SOL | AGENDAMENTO / CANCELADO / SOLICITANTE |
| AGE/CAN/COOR | AGENDAMENTO / CANCELADO / COORDENADOR |
| SOL/AGE/SOL | SOLICITAÇÃO / AGENDADA / SOLICITANTE |
| SOL/AGE/COOR | SOLICITAÇÃO / AGENDADA / COORDENADOR |
| SOL/AUT/REG | SOLICITAÇÃO / AUTORIZADA / REGULADOR |
| INEXISTENTE | SOLICITAÇÃO INEXISTENTE |
| N/D | NÃO DEFINIDO |
| SOL/AGE/FILA | SOLICITAÇÃO / AGENDADA / FILA DE ESPERA |
| AGE/FALTA/EXEC | AGENDAMENTO / FALTA / EXECUTANTE |

## 5. Tabela de `sigla_situacao`

| Sigla | Status |
|---|---|
| P | PENDENTE |
| R | REENVIADA |
| D | DEVOLVIDA |
| N | NEGADA |
| A | APROVADA |
| C | CANCELADA |
| T | TROCA (só hospitalar) |

## 6. Tabela de perfis (PDF §6.1)

| Sigla | Perfil |
|---|---|
| 1 | SOLICITANTE |
| 2 | REGULADOR/AUTORIZADOR |
| 3 | VIDEOFONISTA |
| 4 | EXECUTANTE |
| 5 | EXECUTANTE/SOLICITANTE |
| 6 | ADMINISTRADOR MUNICIPAL |
| 9 | ADMINISTRADOR ESTADUAL |
| 10 | ADMINISTRADOR FEDERAL |
| 13 | EXECUTANTE INT |
| 14 | AUDITOR |
| 17 | COORDENADOR DE UNIDADE |
