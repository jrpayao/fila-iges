"""Agent layer — orquestracao analitica do projeto fila-eletiva.

Substitui app/llm/ + app/es/templates/ da v1.

Arquitetura:
    pergunta -> Resolver (entidades) -> Planner (Plan: lista de primitivas)
             -> Safety (P9) -> Orchestrator executa primitivas -> Envelope
             -> Synthesizer (prosa) + skills.chart + skills.export

Spec: docs/reference/spec-agente-analitico-fila-eletiva.md
Constituicao: memory/constitution.md (v2.0)
"""

__version__ = "2.0.0-poc"
