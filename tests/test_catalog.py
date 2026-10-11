import sqlite3

from router.catalog import CapabilityCatalog
from router.models import Capability


def test_legacy_database_migrates_missing_host_metadata_as_unknown(tmp_path):
    database = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(database)
    connection.execute(
        """CREATE TABLE capabilities (
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
    connection.execute(
        """INSERT INTO capabilities
           (id, source, description, domains, triggers, invocation, trust)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "legacy-security", "local", "Security review", "[]", '["security"]',
            "skill:security", "local",
        ),
    )
    connection.commit()
    connection.close()

    catalog = CapabilityCatalog(database)
    capability = catalog.active()[0]
    assert capability.id == "legacy-security"
    assert capability.kind == "skill"
    assert capability.hosts is None
    catalog.close()


def test_catalog_roundtrips_unknown_empty_and_known_hosts():
    catalog = CapabilityCatalog()
    capabilities = (
        Capability("unknown", "local", "Unknown host", (), ("security",), "skill:unknown"),
        Capability(
            "unavailable", "local", "No hosts", (), ("security",),
            "skill:unavailable", "local", kind="agent", hosts=(),
        ),
        Capability(
            "codex-only", "local", "Codex host", (), ("security",),
            "skill:codex-only", "local", kind="agent", hosts=("codex",),
        ),
    )

    catalog.upsert(capabilities)
    result = {item.id: item for item in catalog.search("security")}
    assert result["unknown"].hosts is None
    assert result["unavailable"].hosts == ()
    assert result["unavailable"].kind == "agent"
    assert result["codex-only"].hosts == ("codex",)
    assert result["codex-only"].kind == "agent"

    catalog.reconcile_snapshot(capabilities)
    active = {item.id: item for item in catalog.active()}
    assert {key: value.hosts for key, value in active.items()} == {
        "unknown": None,
        "unavailable": (),
        "codex-only": ("codex",),
    }
    catalog.close()
