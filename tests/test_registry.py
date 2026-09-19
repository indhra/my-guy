from pathlib import Path

from router.registry import load_registry


def test_loads_checked_in_registry():
    registry = load_registry(Path(__file__).parents[1] / "registry" / "capabilities.json")

    assert {capability.id for capability in registry} == {
        "security-review",
        "ui-review",
        "research",
    }
