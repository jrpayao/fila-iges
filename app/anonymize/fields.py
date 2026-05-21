"""Listas de campos PII conforme constituição P2 (memory/constitution.md).

ALWAYS_MASKED_PII: bloqueado em QUALQUER modo (POC inclusive).
POC_VISIBLE_PII: liberado apenas em POC quando pii_exposure=True.
"""

ALWAYS_MASKED_PII: frozenset[str] = frozenset({
    # CPFs (todos)
    "cpf_usuario",
    "cpf_medico_solicitante",
    "cpf_profissional_solicitante",
    "cpf_profissional_executante",
    # Endereço completo
    "endereco_paciente_residencia",
    "bairro_paciente_residencia",
    "cep_paciente_residencia",
    "numero_paciente_residencia",
    "complemento_paciente_residencia",
    "tipo_logradouro_paciente_residencia",
    # Profissional nominal (mantém código, nome sai)
    "nome_medico_solicitante",
    "nome_profissional_executante",
    "numero_crm",
    # Responsável (hospitalar)
    "nome_responsavel",
    "telefone_responsavel",
    # Operadores nominais
    "nome_operador_solicitante",
    "nome_operador_autorizador",
    "nome_operador_autorizacao",
    "nome_operador_cancelamento",
    "nome_operador_videofonista",
})

POC_VISIBLE_PII: frozenset[str] = frozenset({
    "no_usuario",
    "cns_usuario",
    "no_mae_usuario",
    "telefone",
    "dt_nascimento_usuario",
    "sexo_usuario",
})
