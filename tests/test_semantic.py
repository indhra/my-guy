import pytest

from router.models import Capability
from router.semantic import SemanticSearch


CAPABILITIES = (
    Capability("security", "ecc", "Security and authentication review.", ("security",), ("security", "authentication"), "skill:security", "local"),
    Capability("design", "gstack", "UI and browser design review.", ("ui",), ("ui", "design"), "skill:design", "local"),
)


def test_dependency_free_search_returns_evidence_and_backend():
    hits = SemanticSearch().search("authentication security", CAPABILITIES)

    assert hits[0].capability.id == "security"
    assert hits[0].evidence == ("authentication", "security")
    assert hits[0].backend == "lexical-fallback"


def test_semantic_search_has_no_hidden_limit_and_rejects_negative_limit():
    search = SemanticSearch()
    assert len(search.search("security ui", CAPABILITIES)) == 2
    with pytest.raises(ValueError):
        search.search("security", CAPABILITIES, limit=-1)


def test_backend_label_cannot_claim_unimplemented_semantics():
    with pytest.raises(ValueError):
        SemanticSearch(backend="embedding")
