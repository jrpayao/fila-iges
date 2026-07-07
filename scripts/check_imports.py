"""Validacao rapida de imports + schema."""
from app.agent import plan, envelope, orchestrator, prompts, primitives, resolver

print("ALL IMPORTS OK")
print("composition annotation:", plan.Plan.model_fields["composition"].annotation)
print("sub_envelopes annotation:", envelope.Envelope.model_fields["sub_envelopes"].annotation)
print("Has compare CNES path?", "u.cnes" in open("app/agent/orchestrator.py").read())
print("Has diagnostic compose?", 'composition == "diagnostic"' in open("app/agent/orchestrator.py").read())
