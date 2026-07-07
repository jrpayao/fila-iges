# Constituição — Projeto fila-eletiva

**Versão**: 2.0 — 2026-05-21
**Modo ativo**: **POC** — válido até **2026-07-19**
**Após 2026-07-19**: constituição mantém todos os princípios; somente o provedor LLM volta ao default (Claude).

Princípios não-negociáveis. Qualquer PR que viole um destes itens deve ser rejeitado ou exigir emenda formal a este documento. Esta versão substitui a v1.1-POC; a base é a [Spec do Agente Analítico](../docs/reference/spec-agente-analitico-fila-eletiva.md).

---

## P1. Todo número nasce de uma query

Nenhum valor numérico é inventado, estimado de cabeça ou "lembrado". Se não há query rastreável que o sustente, o agente **não afirma**. Toda resposta com número carrega `source_index` e a query/Plan que o gerou em audit.

**Por quê**: alucinação numérica em gestão pública é incidente. Um número errado vira decisão errada.

## P2. Toda resposta declara contexto

Janela temporal, filtros aplicados e método/fonte sempre explícitos na resposta narrativa. O Envelope (P4) carrega esses dados e o synthesizer é obrigado a citá-los.

**Mínimo**: `window.label`, `filters` aplicados, `source_index`.

## P3. Previsão é projeção transparente

Com índices descritivos read-only, "previsão" = `estoque_fila ÷ vazão_média` ou similar, **rotulada como estimativa**, com `method_note` explícita ("mantido o ritmo atual e sem repriorização"). Nunca número cravado, nunca modelo escondido. Forecast estatístico (sazonalidade, tendência) está **fora de escopo** desta fase.

## P4. Uma fonte única de número — o Envelope

Prosa, gráfico e export leem o **mesmo Envelope** (`app/agent/envelope.py`). O gráfico nunca recalcula. O export nunca reformata números. Se o Envelope diz `1.841 (2.85%)`, esses três artefatos mostram exatamente isso.

## P5. Estoque ≠ Fluxo

Snapshot (`solicitacao-ambulatorial`, fila viva) **nunca** é somado a evento de período (`marcacao-ambulatorial`, conversão/falta). A semântica é sempre declarada no Envelope (`source_index` + `metric.kind`). Métricas têm tipo `snapshot` ou `flow`.

**Antiprático**: somar "fila atual = 395k" com "agendamentos no mês = 64k" como se fossem do mesmo universo.

## P6. Privacidade (LGPD) é absoluta

Respostas de gestão são **sempre agregadas**. Nunca expor:
- `cpf_usuario`, `cns_usuario`, `no_usuario`, `no_mae_usuario`, `telefone`
- `endereco_paciente_residencia`, `bairro_*`, `cep_*`, `numero_*`, `complemento_*`, `tipo_logradouro_*`
- `cpf_medico_*`, `cpf_profissional_*`, `nome_medico_*`, `nome_profissional_*`, `numero_crm`
- `nome_responsavel`, `telefone_responsavel`, `nome_operador_*`

Agregação com piso mínimo de contagem (≥ 5 documentos por bucket) para evitar reidentificação por baixa cardinalidade. PII Scanner mecânico + PII Auditor LLM continuam ativos no pipeline pós-síntese.

## P7. Sem recomendação clínica individual

O agente opera no nível **operacional/gestão de fila**. Nunca em conduta clínica de paciente. Pergunta sobre o que prescrever / tratar é recusada como fora de escopo.

## P8. Export carimba proveniência

Todo arquivo exportado (CSV/XLSX/PDF) carrega cabeçalho de proveniência: `source_index`, `window`, `filters`, `metric`, `method_note`, `generated_at` e aviso **"Modo POC — uso interno IGES, distribuição proibida"** em destaque.

## P9. Vocabulário fechado de operações

O agente só emite Plans sobre as métricas/primitivas deste catálogo:
- **Métricas** (17): `app/agent/metrics.py` — `estoque_fila`, `entrada_solicitacoes`, `agendamentos`, `atendimentos`, `faltas`, `cancelamentos`, `taxa_falta`, `taxa_conversao`, `taxa_cancelamento`, `tempo_espera_total`, `tempo_regulacao`, `tempo_marcacao`, `tempo_execucao`, `efeito_aviso`, `previsao_atendimento`, `mix_tipo_vaga`, `cancel_por_perfil`.
- **Primitivas** (6): `count`, `breakdown`, `timeseries`, `stats`, `lead_time`, `compare`.
- **Dimensões** fechadas: `prioridade`, `cid`, `grupo_procedimento`, `unidade_solicitante`, `unidade_executante`, `tipo_regulacao`, `tipo_vaga`, `perfil_cancelamento`, `municipio`, `bairro`, `tempo`.
- **Filtros** fechados: idem dimensões.

**Nunca** executa DSL/SQL livre fornecido pelo usuário. **Nunca** inventa nome de métrica.

## P10. Clarificação só quando necessária

Não é entrevista. Pergunta de volta **apenas** em:
1. Entidade não resolve (CID/unidade sem match)
2. Ambiguidade real (2+ candidatos, ex.: "HRT vs HRAN")
3. Parâmetro obrigatório ausente **sem default seguro**

UX = chips (2–4 opções + "outro/não sei"). Máx. 3 perguntas. Usuário pode pular → agente usa defaults declarados. **Nunca perguntar o que o índice já responde.**

**Defaults seguros**: janela = últimos 30 dias · prioridade = todas · status = grupo coerente com a métrica.

## P11. Off-topic redefinido

**Off-topic = não tem relação com a fila de regulação SISREG-DF**. Análise, diagnóstico e recomendação de gestão **sobre a fila** são **on-topic**. Perguntas como *"como diminuir a fila?"*, *"por que tanta gente falta?"*, *"qual a previsão para CID X no HRT?"* — todas **válidas**.

Permanecem off-topic: cardápio, clima, conduta clínica individual, perguntas sem nenhum vínculo com a fila/SISREG.

## P12. Cross-index só na aplicação

O Elasticsearch não faz join nativo. Correlação entre `solicitacao-ambulatorial` e `marcacao-ambulatorial` (ex.: solicitação → marcação → falta) é reconciliada **na camada de aplicação** por `codigo_solicitacao`. Nunca via script-Painless ou agregação cross-index custom.

---

## Princípios estruturais herdados (v1, ainda válidos)

### P13. ES é estritamente somente-leitura (verbo `GET`)
Manual SISREG v2.1 §1. Cliente HTTP **falha fechado** em qualquer verbo diferente de GET. POST a `_search` é exceção pois é convenção REST do ES (passa body, não muta).

### P14. DF only — `DF_INDEX_SUFFIX = "df-brasilia"`
Constante fixa. Todo índice consultado termina nesse sufixo. Filtro defensivo `codigo_uf_regulador = "53"` (ambulatorial) ou `.keyword` (hospitalar) sempre presente.

### P15. Auditoria fim-a-fim obrigatória
Cada Plan emitido + cada primitiva executada + cada Envelope produzido + cada síntese narrada deixa entrada em `audit.jsonl` com `request_id` correlacionando tudo. Retenção: 90 dias default, 365 dias para requests que tocaram PII (P6 com pii_exposure).

### P16. Spec-first
Mudança comportamental começa em `specs/`. PR traz diff dos dois lados.

---

## Override POC vigente até 2026-07-19

| Princípio | Default | Override POC |
|---|---|---|
| **P9** allowlist | catálogo fechado de métricas+primitivas | + uma primitiva `free_search` que aceita Plan custom com `metric=null`, validada por safety guard mecânico. Auditada. |
| **Provedor LLM** | Claude (`claude-opus-4-7` planner, `claude-haiku-4-5` synthesizer) | OpenAI (`gpt-4o` planner, `gpt-4o-mini` synthesizer). Chave via `OPENAI_API_KEY`. Migração para Claude é item bloqueante da release v1. |

Após `2026-07-19`:
- `free_search` é removido do registry
- Provedor padrão volta a ser Claude
- `pii_exposure` flag não é mais aceito (P6 estritamente sem PII)

---

## Cumprimento

| Princípio | Onde no código | Como testar |
|---|---|---|
| P1 | `Envelope.metric` + `audit.event("primitive.executed", ...)` | grep audit por response sem `source_index` |
| P2 | `Synthesizer` cita `window.label` + `filters` no 1º parágrafo | `tests/test_synthesizer.py` |
| P3 | `metrics.previsao_atendimento.method_note` sempre preenchido | unit test |
| P4 | `Envelope` é o único input de `chart`, `export`, `synthesizer` | property test: prosa.numbers == envelope.data.values |
| P5 | `metric.kind ∈ {snapshot, flow}`; orquestrador recusa Plan que soma snapshot+flow | unit test |
| P6 | `anonymize/redactor.scrub()` + `scanner` + `pii_auditor` | `tests/test_pii_*.py`, snapshot test |
| P7 | system prompt synthesizer + critic | manual review |
| P8 | `skills/export.py` adiciona header obrigatório | unit test do PDF/CSV |
| P9 | `agent/safety.py` valida Plan contra `metrics.NAMES + primitives.NAMES` | unit test |
| P10 | `Resolver` retorna `Clarification` quando ambiguidade | tests com fixtures de unidade ambígua |
| P11 | system prompt do Orchestrator + tests com "como diminuir a fila?" | smoke test |
| P12 | `primitives.py` cross-reference faz `codigo_solicitacao` no app | unit test |

---

**Histórico de versão**:
- v1.0 — 2026-05-20 — versão inicial (templates fixos, Claude default).
- v1.1-POC — 2026-05-20 — overrides POC em P2/P3/P8.
- **v2.0 — 2026-05-21** — virada arquitetural: catálogo semântico + primitivas + Envelope, conforme [spec do agente analítico](../docs/reference/spec-agente-analitico-fila-eletiva.md). Mantém overrides POC até 2026-07-19.
