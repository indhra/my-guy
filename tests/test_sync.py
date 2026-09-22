from router.catalog import CapabilityCatalog
from router.models import Capability
from router.sync import sync_capabilities


def test_sync_marks_missing_entries_stale_without_deleting_them():
    catalog = CapabilityCatalog()
    first = Capability("first", "local", "First skill", (), ("first",), "skill:first", "local")
    second = Capability("second", "local", "Second skill", (), ("second",), "skill:second", "local")

    assert sync_capabilities(catalog, [first, second], "2026-09-20T00:00:00Z") == ()
    stale = sync_capabilities(catalog, [first], "2026-09-20T01:00:00Z")

    assert stale == ("second",)
    assert {entry.id for entry in catalog.search("second")} == {"second"}
    assert {entry.id for entry in catalog.active()} == {"first"}
    catalog.close()


def test_sync_reconciles_skill_relocation_without_collision():
    catalog = CapabilityCatalog()
    old = Capability("review", "/old/review", "Review", (), ("review",), "skill:review")
    new = Capability("review", "/new/review", "Review", (), ("review",), "skill:review")
    sync_capabilities(catalog, [old])
    assert sync_capabilities(catalog, [new]) == ()
    assert catalog.active()[0].source == "/new/review"
    catalog.close()
