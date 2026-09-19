import json
import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .models import Capability


class CapabilityCatalog:
    """Searchable telephone directory for installed skills and agents."""

    def __init__(self, database: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(str(database))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS capabilities (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                description TEXT NOT NULL,
                domains TEXT NOT NULL,
                triggers TEXT NOT NULL,
                invocation TEXT NOT NULL,
                trust TEXT NOT NULL
            )"""
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def upsert(self, capabilities: Iterable[Capability]) -> None:
        rows = [
            (
                capability.id,
                capability.source,
                capability.description,
                json.dumps(capability.domains),
                json.dumps(capability.triggers),
                capability.invocation,
                capability.trust,
            )
            for capability in capabilities
        ]
        self.connection.executemany(
            """INSERT INTO capabilities
               (id, source, description, domains, triggers, invocation, trust)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 source=excluded.source,
                 description=excluded.description,
                 domains=excluded.domains,
                 triggers=excluded.triggers,
                 invocation=excluded.invocation,
                 trust=excluded.trust""",
            rows,
        )
        self.connection.commit()

    def search(self, query: str, limit: int | None = None) -> tuple[Capability, ...]:
        """Return all matching entries unless the caller explicitly sets a limit."""
        tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        rows = self.connection.execute("SELECT * FROM capabilities").fetchall()
        ranked: list[tuple[int, sqlite3.Row]] = []
        for row in rows:
            searchable = " ".join(
                [row["id"], row["description"], row["domains"], row["triggers"]]
            ).lower()
            score = sum(1 for token in tokens if token in searchable)
            if score:
                ranked.append((score, row))
        ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
        if limit is not None:
            ranked = ranked[:limit]
        return tuple(self._capability(row) for _, row in ranked)

    @staticmethod
    def _capability(row: sqlite3.Row) -> Capability:
        return Capability(
            id=row["id"],
            source=row["source"],
            description=row["description"],
            domains=tuple(json.loads(row["domains"])),
            triggers=tuple(json.loads(row["triggers"])),
            invocation=row["invocation"],
            trust=row["trust"],
        )
