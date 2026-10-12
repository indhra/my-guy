import json
import os

import pytest

from router.cli import main as cli_main
from router.core import route
from router.models import Capability
from router.semantic import (
    EMBEDDING_BACKEND,
    LEXICAL_BACKEND,
    MAX_EMBEDDING_CAPABILITIES,
    SemanticBackendError,
    SemanticSearch,
    _embedding_api_key,
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


def test_last_backend_records_success_and_provider_failure():
    search = SemanticSearch()
    assert search.last_backend is None
    search.search("authentication", CAPABILITIES)
    assert search.last_backend == LEXICAL_BACKEND

    def broken(_texts):
        raise SemanticBackendError("unreachable")

    degraded = SemanticSearch(backend=EMBEDDING_BACKEND, embed_fn=broken)
    assert degraded.last_backend is None
    degraded.search("authentication", CAPABILITIES)
    assert degraded.last_backend == LEXICAL_BACKEND

    successful = SemanticSearch(
        backend=EMBEDDING_BACKEND,
        embed_fn=lambda texts: tuple((1.0,) for _ in texts),
    )
    successful.search("authentication", CAPABILITIES)
    assert successful.last_backend == EMBEDDING_BACKEND


def test_degraded_lexical_hits_do_not_change_routing():
    capability = Capability(
        "description-only", "fixture", "Needle appears only in this description.",
        (), ("unrelated",), "skill:description-only", "local",
    )

    def broken(_texts):
        raise SemanticBackendError("unreachable")

    with_semantic = route(
        "needle", (capability,),
        semantic=SemanticSearch(backend=EMBEDDING_BACKEND, embed_fn=broken),
    )
    without_semantic = route("needle", (capability,))
    assert (with_semantic.status, with_semantic.candidates) == (
        without_semantic.status, without_semantic.candidates
    )


def test_embedding_capability_limit_uses_lexical_without_call():
    calls = []

    def embed(texts):
        calls.append(texts)
        return tuple((1.0,) for _ in texts)

    capabilities = tuple(
        Capability(f"cap-{i}", "fixture", "Description", (), ("term",),
                   f"skill:cap-{i}", "local")
        for i in range(MAX_EMBEDDING_CAPABILITIES + 1)
    )
    search = SemanticSearch(backend=EMBEDDING_BACKEND, embed_fn=embed)
    hits = search.search("term", capabilities)
    assert calls == []
    assert search.last_backend == LEXICAL_BACKEND
    assert hits[0].backend == LEXICAL_BACKEND


def test_embedding_cache_only_embeds_missing_capabilities_and_prunes(tmp_path):
    calls = []

    def embed(texts):
        calls.append(texts)
        return tuple((1.0, 0.0) for _ in texts)

    cache = tmp_path / "embeddings.json"
    search = SemanticSearch(
        backend=EMBEDDING_BACKEND, embed_fn=embed, cache_path=cache,
        cache_namespace="endpoint\0model",
    )
    search.search("query", CAPABILITIES[:2])
    assert len(calls[0]) == 3
    search.search("query", CAPABILITIES[:2])
    assert calls[1] == ("query",)
    assert "query" not in cache.read_text()
    assert len(json.loads(cache.read_text())) == 2
    assert os.stat(cache).st_mode & 0o777 == 0o600

    search.search("query", CAPABILITIES[:1])
    assert calls[2] == ("query",)
    assert len(json.loads(cache.read_text())) == 1


def test_corrupt_embedding_cache_is_rebuilt(tmp_path):
    cache = tmp_path / "embeddings.json"
    cache.write_text("{not-json")
    calls = []

    def embed(texts):
        calls.append(texts)
        return tuple((1.0,) for _ in texts)

    SemanticSearch(
        backend=EMBEDDING_BACKEND, embed_fn=embed, cache_path=cache
    ).search("query", CAPABILITIES[:1])
    assert len(calls[0]) == 2
    assert isinstance(json.loads(cache.read_text()), dict)


def test_embedding_api_key_fallback_is_provider_scoped():
    assert _embedding_api_key(
        {"OPENAI_API_KEY": "fallback"}, "https://api.openai.com/v1/embeddings"
    ) == "fallback"
    assert _embedding_api_key(
        {"OPENAI_API_KEY": "fallback"}, "https://provider.example/v1/embeddings"
    ) is None
    assert _embedding_api_key(
        {"MY_GUY_EMBEDDING_API_KEY": "explicit", "OPENAI_API_KEY": "fallback"},
        "https://provider.example/v1/embeddings",
    ) == "explicit"


def test_from_env_defaults_to_lexical_and_rejects_unknown_backends():
    assert SemanticSearch.from_env({}).backend == LEXICAL_BACKEND
    with pytest.raises(ValueError):
        SemanticSearch.from_env({"MY_GUY_SEMANTIC_BACKEND": "magic"})
    with pytest.raises(ValueError):
        SemanticSearch.from_env({"MY_GUY_SEMANTIC_BACKEND": EMBEDDING_BACKEND})
    with pytest.raises(ValueError):
        SemanticSearch.from_env({
            "MY_GUY_SEMANTIC_BACKEND": EMBEDDING_BACKEND,
            "MY_GUY_EMBEDDING_URL": "http://example.com/v1/embeddings",
        })
    assert SemanticSearch.from_env({
        "MY_GUY_SEMANTIC_BACKEND": EMBEDDING_BACKEND,
        "MY_GUY_EMBEDDING_URL": "http://localhost:11434/v1/embeddings",
    }).backend == EMBEDDING_BACKEND


def test_from_env_configures_the_embedding_backend():
    search = SemanticSearch.from_env({
        "MY_GUY_SEMANTIC_BACKEND": EMBEDDING_BACKEND,
        "MY_GUY_EMBEDDING_URL": "https://provider.example/v1/embeddings",
        "MY_GUY_EMBEDDING_MODEL": "embed-x",
        "MY_GUY_EMBEDDING_API_KEY": "key",
    })

    assert search.backend == EMBEDDING_BACKEND


def test_cli_route_json_reports_no_semantic_degradation_by_default(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "state"))
    assert cli_main(["route", "--json", "Review", "security"]) == 0
    assert json.loads(capsys.readouterr().out)["semantic_degraded"] is False


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
