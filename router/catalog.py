import json
import os
import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .models import Capability


class CapabilityCatalog:
    """Searchable telephone directory for installed skills and agents."""

    def __init__(self, database: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(str(database))
        if database != ":memory:":
            os.chmod(Path(database), 0o600)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS capabilities (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                description TEXT NOT NULL,
                domains TEXT NOT NULL,
                triggers TEXT NOT NULL,
                invocation TEXT NOT NULL,
                trust TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )"""
        )
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(capabilities)")}
        if "active" not in columns:
            self.connection.execute(
                "ALTER TABLE capabilities ADD COLUMN active INTEGER NOT NULL DEFAULT 1"
            )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def upsert(self, capabilities: Iterable[Capability]) -> None:
        capabilities = tuple(capabilities)
        seen: dict[str, str] = {}
        for capability in capabilities:
            prior_source = seen.get(capability.id)
            if prior_source and prior_source != capability.source:
                raise ValueError(f"capability id collision across sources: {capability.id}")
            seen[capability.id] = capability.source
            existing = self.connection.execute(
                "SELECT source FROM capabilities WHERE id = ?", (capability.id,)
            ).fetchone()
            if existing and existing["source"] != capability.source:
                raise ValueError(f"capability id collision across sources: {capability.id}")
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
               (id, source, description, domains, triggers, invocation, trust, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)
               ON CONFLICT(id) DO UPDATE SET
                 source=excluded.source,
                 description=excluded.description,
                 domains=excluded.domains,
                 triggers=excluded.triggers,
                 invocation=excluded.invocation,
                 trust=excluded.trust,
                 active=1""",
            rows,
        )
        self.connection.commit()

    def reconcile_snapshot(self, capabilities: Iterable[Capability]) -> None:
        """Atomically activate the current scan and retain older rows as inactive evidence."""
        capabilities = tuple(capabilities)
        ids = [capability.id for capability in capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError("snapshot contains duplicate capability ids")
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
        with self.connection:
            self.connection.execute("UPDATE capabilities SET active = 0")
            self.connection.executemany(
                """INSERT INTO capabilities
                   (id, source, description, domains, triggers, invocation, trust, active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                   ON CONFLICT(id) DO UPDATE SET
                     source=excluded.source,
                     description=excluded.description,
                     domains=excluded.domains,
                     triggers=excluded.triggers,
                     invocation=excluded.invocation,
                     trust=excluded.trust,
                     active=1""",
                rows,
            )

    def search(self, query: str, limit: int | None = None) -> tuple[Capability, ...]:
        """Return all matching entries unless the caller explicitly sets a limit."""
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative or None")
        tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        rows = self.connection.execute("SELECT * FROM capabilities").fetchall()
        ranked: list[tuple[int, sqlite3.Row]] = []
        for row in rows:
            searchable = set(
                re.findall(
                    r"[a-z0-9]+",
                    " ".join([row["id"], row["description"], row["domains"], row["triggers"]]).lower(),
                )
            )
            score = len(tokens.intersection(searchable))
            if score:
                ranked.append((score, row))
        ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
        if limit is not None:
            ranked = ranked[:limit]
        return tuple(self._capability(row) for _, row in ranked)

    def all(self, *, include_stale: bool = True) -> tuple[Capability, ...]:
        where = "" if include_stale else " WHERE active = 1"
        rows = self.connection.execute(f"SELECT * FROM capabilities{where} ORDER BY id").fetchall()
        return tuple(self._capability(row) for row in rows)

    def active(self) -> tuple[Capability, ...]:
        return self.all(include_stale=False)

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
