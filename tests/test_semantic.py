import pytest

from router.core import route
from router.models import Capability
from router.semantic import (
    EMBEDDING_BACKEND,
    LEXICAL_BACKEND,
    SemanticBackendError,
    SemanticSearch,
)


CAPABILITIES = (
    Capability("security", "ecc", "Security and authentication review.", ("security",), ("security", "authentication"), "skill:security", "local"),
    Capability("design", "gstack", "UI and browser design review.", ("ui",), ("ui", "design"), "skill:design", "local"),
    Capability("mystery", "local-file", "Unverified mystery helper.", ("mystery",), ("mystery",), "skill:mystery"),
)


def test_dependency_free_search_returns_evidence_and_backend():
    hits = SemanticSearch().search("authentication security", CAPABILITIES)

    assert hits[0].capability.id == "security"
    assert hits[0].evidence == ("authentication", "security")
    assert hits[0].backend == LEXICAL_BACKEND


def test_semantic_search_has_no_hidden_limit_and_rejects_negative_limit():
    search = SemanticSearch()
    assert len(search.search("security ui", CAPABILITIES)) == 2
    with pytest.raises(ValueError):
        search.search("security", CAPABILITIES, limit=-1)


def test_backend_label_cannot_claim_unimplemented_semantics():
    with pytest.raises(ValueError):
        SemanticSearch(backend="embedding")


def test_embedding_backend_requires_an_embed_function():
    with pytest.raises(ValueError):
        SemanticSearch(backend=EMBEDDING_BACKEND)


def _fake_embed(vectors: dict[str, tuple[float, ...]]):
    def embed(texts):
        return tuple(vectors.get(text, (0.0,)) for text in texts)
    return embed


def test_embedding_backend_ranks_by_cosine_similarity():
    query = "check login safety"
    embed = _fake_embed({
        query: (1.0, 0.0),
        "security Security and authentication review. security security authentication": (0.9, 0.1),
        "design UI and browser design review. ui ui design": (0.0, 1.0),
        "mystery Unverified mystery helper. mystery mystery": (0.0, 1.0),
    })
    hits = SemanticSearch(backend=EMBEDDING_BACKEND, embed_fn=embed).search(query, CAPABILITIES)

    assert hits[0].capability.id == "security"
    assert hits[0].score == pytest.approx(0.9 / (0.9**2 + 0.1**2) ** 0.5)
    assert hits[0].backend == EMBEDDING_BACKEND


def test_provider_failure_degrades_to_lexical_with_lexical_label():
    def broken(_texts):
        raise SemanticBackendError("embedding provider request failed: unreachable")

    hits = SemanticSearch(backend=EMBEDDING_BACKEND, embed_fn=broken).search(
        "authentication security", CAPABILITIES
    )

    assert hits[0].capability.id == "security"
    assert hits[0].backend == LEXICAL_BACKEND


def test_from_env_defaults_to_lexical_and_rejects_unknown_backends():
    assert SemanticSearch.from_env({}).backend == LEXICAL_BACKEND
    with pytest.raises(ValueError):
        SemanticSearch.from_env({"MY_GUY_SEMANTIC_BACKEND": "magic"})
    with pytest.raises(ValueError):
        SemanticSearch.from_env({"MY_GUY_SEMANTIC_BACKEND": EMBEDDING_BACKEND})
    with pytest.raises(ValueError):
        SemanticSearch.from_env({
            "MY_GUY_SEMANTIC_BACKEND": EMBEDDING_BACKEND,
            "MY_GUY_EMBEDDING_URL": "ftp://embeddings",
        })


def test_from_env_configures_the_embedding_backend():
    search = SemanticSearch.from_env({
        "MY_GUY_SEMANTIC_BACKEND": EMBEDDING_BACKEND,
        "MY_GUY_EMBEDDING_URL": "https://provider.example/v1/embeddings",
        "MY_GUY_EMBEDDING_MODEL": "embed-x",
        "MY_GUY_EMBEDDING_API_KEY": "key",
    })

    assert search.backend == EMBEDDING_BACKEND


def _semantic_search(score_map: dict[str, float]):
    """An embedding backend whose cosine scores are chosen per capability id."""
    def embed(texts):
        # texts[0] is the query; the rest are capability texts in order.
        vectors = [(1.0, 0.0)]
        for text in texts[1:]:
            capability_id = text.split(" ", 1)[0]
            score = score_map.get(capability_id, 0.0)
            vectors.append((score, (1 - score**2) ** 0.5 if score <= 1 else 0.0))
        return tuple(vectors)

    return SemanticSearch(backend=EMBEDDING_BACKEND, embed_fn=embed)


def test_route_uses_semantic_backend_for_unmatched_wording():
    semantic = _semantic_search({"security": 0.9})
    decision = route("audit the credential vault", CAPABILITIES, semantic=semantic)

    assert decision.status == "recommend"
    assert decision.candidates == ("security",)
    assert "semantic 0.90 (openai-embedding)" in decision.reason


def test_route_without_semantic_still_clarifies_unmatched_wording():
    decision = route("audit the credential vault", CAPABILITIES)

    assert decision.status == "clarify"


def test_semantic_candidate_still_needs_trust():
    semantic = _semantic_search({"mystery": 0.9})
    decision = route("audit the credential vault", CAPABILITIES, semantic=semantic)

    assert decision.status == "clarify"
    assert decision.candidates == ("mystery",)


def test_semantic_hit_respects_exclusions():
    semantic = _semantic_search({"security": 0.9})
    decision = route("compare design ideas but not security", CAPABILITIES, semantic=semantic)

    assert "security" not in decision.candidates
