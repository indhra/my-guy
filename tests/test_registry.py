from pathlib import Path

from router.catalog import CapabilityCatalog
from router.registry import load_registry


def test_loads_checked_in_registry():
    registry = load_registry(Path(__file__).parents[1] / "registry" / "capabilities.json")

    assert {capability.id for capability in registry} == {
        "security-review",
        "ui-review",
        "research",
    }


def test_catalog_search_returns_all_matches_without_an_implicit_limit():
    catalog = CapabilityCatalog()
    catalog.upsert(load_registry(Path(__file__).parents[1] / "registry" / "capabilities.json"))

    results = catalog.search("privacy security research")

    assert {capability.id for capability in results} == {"security-review", "research"}
    assert catalog.search("privacy security research", limit=1)[0].id == "security-review"
    try:
        catalog.search("security", limit=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative limits must be rejected")
    catalog.close()


def test_registry_preserves_trust_and_rejects_source_collisions():
    catalog = CapabilityCatalog()
    catalog.upsert(load_registry(Path(__file__).parents[1] / "registry" / "capabilities.json"))
    assert catalog.search("security")[0].trust == "local"

    from router.models import Capability

    try:
        catalog.upsert(
            [Capability("security-review", "untrusted", "shadow", ("security",), ("security",), "bad")]
        )
    except ValueError:
        pass
    else:
        raise AssertionError("source collisions must be rejected")
    catalog.close()


def test_catalog_rejects_same_batch_source_collisions():
    from router.models import Capability

    catalog = CapabilityCatalog()
    entries = [
        Capability("duplicate", "one", "first", (), ("first",), "skill:one"),
        Capability("duplicate", "two", "second", (), ("second",), "skill:two"),
    ]

    try:
        catalog.upsert(entries)
    except ValueError:
        pass
    else:
        raise AssertionError("same-batch source collisions must be rejected")
    catalog.close()
