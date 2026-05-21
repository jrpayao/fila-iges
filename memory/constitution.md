# Constituição — Projeto fila-eletiva

**Versão**: 1.1-POC — 2026-05-20  
**Modo ativo**: **POC** — válido até **2026-07-19**  
**Após 2026-07-19**: constituição volta automaticamente ao Modo Produção (princípios sem overrides).

Princípios não-negociáveis. Qualquer PR que viole um destes itens deve ser rejeitado ou exigir emenda formal a este documento.

---

## Modo POC — overrides explícitos

Esta versão da constituição está em **Modo POC** com relaxações limitadas em **P2**, **P3** e **P8**, vigentes **somente até 2026-07-19**. Cada override está descrito dentro do princípio correspondente.

| Categoria | Princípios |
|---|---|
| **Inviolável em qualquer modo** | P1, P4, P5, P6, P7, P9 |
| **Relaxado no POC com regras de mitigação** | P2, P3, P8 |

**Release gates obrigatórios antes do primeiro request POC com PII real**:

1. **DPA OpenAI assinado** com cláusula de **opt-out de treinamento** sobre o projeto/organização.
2. **Aprovação formal** do uso de PII no POC pelo jurídico do IGES-DF e pela CGRA.
3. **Audit log** funcional (P4) — POC sem audit é proibido, mesmo em dev.
4. **`.env.local` fora do repo**, chave nunca em código-fonte ou git history.

**Migração para Modo Produção em 2026-07-19** exige:
- (a) retorno de **P8** ao default (Claude).
- (b) retorno de **P2** ao default (anonymizer ativo, zero PII no LLM).
- (c) retorno de **P3** ao default (allowlist exclusiva, sem `free_text_search`).
- (d) aprovação formal por CGRA + jurídico IGES.

---

## P1. Somente-leitura sobre SISREG

A API SISREG é, por design oficial, GET-only (manual v2.1, seção 1). Esta plataforma **nunca** emite verbos diferentes de `GET` ao endpoint `sisreg-es.saude.gov.br`. Qualquer construção de cliente HTTP deve **falhar fechado** ao receber instrução de POST/PUT/DELETE.

**Por quê**: dado de regulação assistencial é dado primário de gestão — escrita acidental é incidente grave com pacientes reais.

**Modo POC**: sem override. Princípio se mantém integral.

---

## P2. PII no LLM

### Modo Produção (default, vigente a partir de 2026-07-20)
Campos PII (`cns_usuario`, `cpf_usuario`, `no_usuario`, `no_mae_usuario`, `telefone`, `endereco_paciente_residencia`, `cep_paciente_residencia`, `numero_paciente_residencia`, `complemento_paciente_residencia`, `bairro_paciente_residencia`, `cpf_medico_solicitante`, `cpf_profissional_executante`, `cpf_profissional_solicitante`, `dt_nascimento_usuario`) são **proibidos** em qualquer prompt, contexto, log ou retorno serializado que vá para o modelo.

A camada de **anonymizer** roda obrigatoriamente entre o resultado do ES e o LLM-narrator. Testes garantem que nenhum dos campos acima aparece em prompts gravados em audit.

### Override POC (vigente até 2026-07-19)

PII pode atravessar a fronteira do LLM **SE TODAS** as condições abaixo forem verdadeiras:

1. **Ambiente restrito**: aplicação em rede interna IGES; única saída externa permitida é o endpoint OpenAI (`api.openai.com`). Sem proxy reverso pro mundo.
2. **DPA OpenAI** com opt-out de treinamento ativo (release gate acima).
3. **Categorização de PII em duas listas** (ver `specs/.../data-model.md` §3):
   - `POC_VISIBLE_PII`: `no_usuario`, `cns_usuario`, `no_mae_usuario`, `telefone`, `dt_nascimento_usuario`, `sexo_usuario` — **permitidos** ao LLM em POC, exclusivamente para cenários individuais como "últimos N pacientes atendidos".
   - `ALWAYS_MASKED_PII`: `cpf_usuario`, `cpf_medico_solicitante`, `cpf_profissional_*`, `endereco_paciente_residencia`, `cep_paciente_residencia`, `numero_paciente_residencia`, `complemento_paciente_residencia`, `bairro_paciente_residencia`, `tipo_logradouro_paciente_residencia`, `nome_medico_solicitante`, `nome_responsavel`, `telefone_responsavel`, `numero_crm` — **continuam mascarados mesmo em POC**.
4. **Justificativa textual** do operador acompanha cada request que ativa o caminho com PII (ex.: "investigando falta de comparecimento na fila de oftalmologia"). Sem justificativa, request é rejeitado.
5. **Resposta marcada** com banner *"CONTÉM PII — uso interno IGES, distribuição proibida"* no header da narrativa.
6. **Audit reforçado**: requests com `pii_exposure=true` ficam num índice separado com retenção mínima de 365 dias.

**Por quê**: o POC precisa demonstrar valor para coordenadores que pensam em casos concretos. Mas LGPD não evapora porque é POC — o override formaliza o trade-off em vez de varrê-lo para baixo do tapete.

---

## P3. DSL via template, não texto livre

### Modo Produção (default)
O LLM **não escreve DSL como string**. O LLM escolhe um *template* da allowlist (`contracts/elasticsearch.md`) e preenche seus parâmetros via *tool calling estruturado* validado por Pydantic. Qualquer tentativa de injetar DSL livre é rejeitada na camada `safety.py`.

### Override POC (vigente até 2026-07-19)

Além dos templates allowlist, fica permitido **um único** template adicional `free_text_search` (ver T-FREE em `contracts/elasticsearch.md`), com DSL gerada pelo LLM mas validada por **safety guard com allowlist negativa**:

- ✅ Permitido: verbo `GET` em `_search`; índices da DF (`sisreg-*-53-*`); `query`, `aggs`, `_source`, `sort`, `size`.
- ❌ Bloqueado: qualquer verbo diferente de GET; endpoints `_delete_by_query`, `_update_by_query`, `_reindex`, `_sql`, `_scripts`, `_ingest`; cláusulas com `script`, `script_score`, `runtime_mappings`; `size > 50`; índices fora do DF; PII em filtros bool (uso `cpf_usuario:"..."` é bloqueado mesmo no POC).
- 🔒 Cada execução desse template gera audit com flag `template=free_text_search` + DSL completo + pergunta original.

**Por quê**: exploração inicial precisa flexibilidade. A safety guard limita o blast radius sem matar a flexibilidade.

---

## P4. Auditoria fim-a-fim é obrigatória

Toda interação registra: `request_id`, `timestamp`, `usuário autenticado`, `pergunta original`, `template escolhido + parâmetros`, `DSL final`, `índice consultado`, `hit count`, `tempo de execução`, `versão do prompt`, `provedor LLM + modelo + versão`, `pii_exposure` (bool). Logs estruturados (JSON), retenção mínima 90 dias em produção / 365 dias para requests com PII no POC.

**Modo POC**: sem override — pelo contrário, retenção **aumenta** para 365 dias em requests com PII.

---

## P5. Toda resposta narrativa cita sua origem

A narrativa do LLM **deve** declarar explicitamente: `(a)` qual índice foi consultado, `(b)` qual janela temporal, `(c)` quantos documentos compõem a agregação, `(d)` filtros aplicados, `(e)` em POC: se houve `pii_exposure=true`. Sem essa âncora, a resposta é desinformação travestida de relatório.

---

## P6. Spec-first

Mudança comportamental começa em `specs/`. Não se altera código sem alterar a spec correspondente — e PRs trazem o diff dos dois lados. Templates DSL novos exigem entrada em `contracts/elasticsearch.md` antes de existir no código.

---

## P7. Cenários de ES verificados contra o dicionário

Todo template DSL referencia explicitamente os campos do **dicionário oficial** (manual seção 5, espelhado em `data-model.md`). Divergências entre dicionário e mapping real do ES são registradas em `research.md` e tratadas como bug do ambiente, não como exceção do código.

---

## P8. Provedor de LLM

### Modo Produção (default, vigente a partir de 2026-07-20)
`claude-opus-4-7` para NL→tool-call (planning); `claude-haiku-4-5-20251001` para narrativa. Versão fica fixa em config — nunca "latest". Upgrade de modelo é PR auditável que toca `plan.md`.

### Override POC (vigente até 2026-07-19)
Provedor primário é **OpenAI**:
- `gpt-4o` (ou modelo equivalente vigente em maio/2026) para planner/tool-calling.
- `gpt-4o-mini` (ou equivalente) para narrator.
- Chave **exclusivamente** via env var `OPENAI_API_KEY` carregada de `.env.local` (não versionado).
- Telemetria de custo separada da prod.
- Migração para Claude (P8 default) é **item obrigatório** em `tasks.md` antes da release v1.

---

## P9. Sem dependência de credencial federal

Toda configuração assume credencial **subnacional DF**. Suporte a `-nacional` só entra com spec adicional aprovada pela CGRA, e nunca como default.

**Modo POC**: sem override.

---

**Histórico de versão**:
- v1.0 — 2026-05-20 — versão inicial (Claude default, PII proibido).
- v1.1-POC — 2026-05-20 — overrides POC em P2/P3/P8 com expiração em 2026-07-19.
