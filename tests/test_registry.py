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
    catalog.close()
