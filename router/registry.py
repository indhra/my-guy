import json
from pathlib import Path

from .models import Capability


def load_registry(path: str | Path) -> tuple[Capability, ...]:
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(
        Capability(
            id=record["id"],
            source=record["source"],
            description=record["description"],
            domains=tuple(record["domains"]),
            triggers=tuple(record["triggers"]),
            invocation=record["invocation"],
            trust=record.get("trust", "unverified"),
            kind=record.get("kind", "skill"),
            hosts=tuple(record["hosts"]) if record.get("hosts") is not None else None,
        )
        for record in records
    )
