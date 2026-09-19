from collections.abc import Iterable
from datetime import datetime, timezone

from .catalog import CapabilityCatalog
from .discovery import discover_skills
from .models import Capability


def sync_capabilities(
    catalog: CapabilityCatalog,
    capabilities: Iterable[Capability],
    observed_at: str | None = None,
) -> tuple[str, ...]:
    """Upsert capabilities and return previously known IDs absent this scan."""
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    capabilities = tuple(capabilities)
    catalog.upsert(capabilities)
    catalog.connection.execute(
        """CREATE TABLE IF NOT EXISTS capability_observations (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            last_seen TEXT NOT NULL
        )"""
    )
    catalog.connection.executemany(
        """INSERT INTO capability_observations (id, source, last_seen)
           VALUES (?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET source=excluded.source, last_seen=excluded.last_seen""",
        [(capability.id, capability.source, observed_at) for capability in capabilities],
    )
    catalog.connection.commit()
    current_ids = {capability.id for capability in capabilities}
    if current_ids:
        placeholders = ",".join("?" for _ in current_ids)
        known = catalog.connection.execute(
            f"SELECT id FROM capability_observations WHERE id NOT IN ({placeholders})",
            tuple(current_ids),
        ).fetchall()
    else:
        known = catalog.connection.execute("SELECT id FROM capability_observations").fetchall()
    return tuple(row["id"] for row in known)


def sync_skill_roots(
    catalog: CapabilityCatalog,
    roots: list[str],
    observed_at: str | None = None,
) -> tuple[str, ...]:
    return sync_capabilities(catalog, discover_skills(roots), observed_at)
