import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings


def event(name: str, **fields: Any) -> str:
    """Append an audit event to JSONL. Returns the request_id."""
    request_id = fields.pop("request_id", None) or str(uuid.uuid4())
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": name,
        "request_id": request_id,
        "app_mode": settings.app_mode,
        **fields,
    }
    path = Path(settings.audit_jsonl_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return request_id
