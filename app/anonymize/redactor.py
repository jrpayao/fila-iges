from typing import Any

from app.anonymize.fields import ALWAYS_MASKED_PII, POC_VISIBLE_PII


def scrub(data: Any, *, mode: str = "poc", pii_exposure: bool = False) -> Any:
    """Remove PII recursivamente de uma resposta ES.

    Regras (constituição P2):
    - ALWAYS_MASKED_PII: removido em qualquer modo.
    - POC_VISIBLE_PII: mantido APENAS se mode=poc E pii_exposure=True.
    """
    poc_pii_allowed = mode == "poc" and pii_exposure

    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            if key in ALWAYS_MASKED_PII:
                continue
            if key in POC_VISIBLE_PII and not poc_pii_allowed:
                continue
            result[key] = scrub(value, mode=mode, pii_exposure=pii_exposure)
        return result
    if isinstance(data, list):
        return [scrub(item, mode=mode, pii_exposure=pii_exposure) for item in data]
    return data
