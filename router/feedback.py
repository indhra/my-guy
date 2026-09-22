from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


OUTCOMES = frozenset({"accepted", "corrected", "failed"})


@dataclass(frozen=True)
class FeedbackProposal:
    capability_id: str
    samples: int
    accepted: int
    corrected: int
    failed: int
    recommendation: str


class FeedbackStore:
    """Opt-in outcome ledger. Raw requests are never stored."""

    def __init__(self, database: str | Path = ":memory:") -> None:
        self.database = database
        if database != ":memory:":
            path = Path(database)
            created_parent = not path.parent.exists()
            path.parent.mkdir(parents=True, exist_ok=True)
            if created_parent:
                os.chmod(path.parent, 0o700)
            key_path = path.with_suffix(path.suffix + ".key")
            if key_path.exists():
                self._key = key_path.read_bytes()
                if len(self._key) != 32:
                    raise ValueError("feedback key must be exactly 32 bytes")
                os.chmod(key_path, 0o600)
            else:
                self._key = secrets.token_bytes(32)
                descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(self._key)
            self.connection = sqlite3.connect(str(path))
            os.chmod(path, 0o600)
        else:
            self._key = secrets.token_bytes(32)
            self.connection = sqlite3.connect(":memory:")
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS route_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                request_digest TEXT NOT NULL,
                capability_id TEXT NOT NULL,
                outcome TEXT NOT NULL,
                correction TEXT
            )"""
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def record(
        self,
        request: str,
        capability_id: str,
        outcome: str,
        *,
        consent: bool,
        correction: str | None = None,
    ) -> None:
        if not consent:
            raise PermissionError("feedback collection is disabled until the user opts in")
        if outcome not in OUTCOMES:
            raise ValueError(f"unsupported feedback outcome: {outcome}")
        if not request.strip() or not capability_id.strip():
            raise ValueError("request and capability_id are required")
        digest = hmac.new(self._key, request.encode("utf-8"), hashlib.sha256).hexdigest()
        self.connection.execute(
            """INSERT INTO route_feedback
               (created_at, request_digest, capability_id, outcome, correction)
               VALUES (?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                digest,
                capability_id,
                outcome,
                correction[:500] if correction else None,
            ),
        )
        self.connection.commit()

    def proposals(self, minimum_samples: int = 5) -> tuple[FeedbackProposal, ...]:
        if minimum_samples < 1:
            raise ValueError("minimum_samples must be positive")
        rows = self.connection.execute(
            """SELECT capability_id, COUNT(*) AS samples,
                      SUM(outcome = 'accepted') AS accepted,
                      SUM(outcome = 'corrected') AS corrected,
                      SUM(outcome = 'failed') AS failed
               FROM route_feedback GROUP BY capability_id HAVING COUNT(*) >= ?
               ORDER BY capability_id""",
            (minimum_samples,),
        ).fetchall()
        proposals = []
        for capability_id, samples, accepted, corrected, failed in rows:
            recommendation = (
                "review triggers and provenance"
                if corrected + failed > accepted
                else "retain current routing; gather more reviewed evidence"
            )
            proposals.append(
                FeedbackProposal(capability_id, samples, accepted, corrected, failed, recommendation)
            )
        return tuple(proposals)
