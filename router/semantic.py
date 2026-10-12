"""Optional semantic search with pluggable backends.

The default ``lexical-fallback`` backend is dependency-free and offline. An
opt-in ``openai-embedding`` backend calls an OpenAI-compatible ``/embeddings``
endpoint (a hosted provider or a local server such as Ollama or llama.cpp) so
routing can reuse whatever LLM endpoint the operator already has. Backend
configuration is explicit; a provider failure degrades transparently to the
lexical backend rather than failing the route.
"""

import json
import math
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .models import Capability

LEXICAL_BACKEND = "lexical-fallback"
EMBEDDING_BACKEND = "openai-embedding"
BACKENDS = frozenset({LEXICAL_BACKEND, EMBEDDING_BACKEND})

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_TIMEOUT_SECONDS = 15.0
MAX_EMBEDDING_TEXT_CHARS = 8_192
MAX_EMBEDDING_BATCH = 128

EmbedFn = Callable[[tuple[str, ...]], tuple[tuple[float, ...], ...]]


@dataclass(frozen=True)
class SearchHit:
    capability: Capability
    score: float
    evidence: tuple[str, ...]
    backend: str


class SemanticBackendError(RuntimeError):
    """A configured semantic backend could not answer the query."""


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _capability_text(capability: Capability) -> str:
    return " ".join(
        [capability.id, capability.description, *capability.domains, *capability.triggers]
    )


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0


def openai_embedding_fn(
    *, url: str, model: str, api_key: str | None = None,
    timeout: float = EMBEDDING_TIMEOUT_SECONDS,
) -> EmbedFn:
    """Build an embedder for an OpenAI-compatible ``/embeddings`` endpoint."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    def embed(texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        vectors: list[tuple[float, ...]] = [()] * len(texts)
        for start in range(0, len(texts), MAX_EMBEDDING_BATCH):
            batch = texts[start:start + MAX_EMBEDDING_BATCH]
            payload = json.dumps({
                "model": model,
                "input": [text[:MAX_EMBEDDING_TEXT_CHARS] for text in batch],
            }).encode("utf-8")
            request = urllib.request.Request(url, data=payload, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    body = json.loads(response.read())
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
                raise SemanticBackendError(
                    f"embedding provider request failed: {error}"
                ) from error
            try:
                data = body["data"]
            except (KeyError, TypeError) as error:
                raise SemanticBackendError(
                    "embedding provider returned an unexpected payload"
                ) from error
            for item in data:
                try:
                    index = item["index"]
                    vectors[start + index] = tuple(float(v) for v in item["embedding"])
                except (KeyError, TypeError, ValueError, IndexError) as error:
                    raise SemanticBackendError(
                        "embedding provider returned malformed rows"
                    ) from error
        if any(not vector for vector in vectors):
            raise SemanticBackendError("embedding provider returned missing rows")
        return tuple(vectors)

    return embed


class SemanticSearch:
    """Pluggable semantic interface with a transparent lexical fallback.

    ``lexical-fallback`` ranks capabilities by token-overlap evidence and makes
    no network or model call. ``openai-embedding`` ranks by cosine similarity
    against an explicit, operator-configured endpoint; when the provider fails,
    results degrade to the lexical backend and are labeled as such so the
    reported evidence stays honest.
    """

    def __init__(self, backend: str = LEXICAL_BACKEND, *, embed_fn: EmbedFn | None = None) -> None:
        if backend not in BACKENDS:
            raise ValueError(
                f"unsupported semantic backend: {backend}; expected one of {sorted(BACKENDS)}"
            )
        if backend == EMBEDDING_BACKEND and embed_fn is None:
            raise ValueError(
                "the openai-embedding backend requires an embed function; "
                "configure MY_GUY_EMBEDDING_URL and related variables or pass embed_fn"
            )
        self.backend = backend
        self.embed_fn = embed_fn

    @classmethod
    def from_env(cls, env: dict | None = None) -> "SemanticSearch":
        """Build a search from explicit environment configuration.

        ``MY_GUY_SEMANTIC_BACKEND`` selects the backend (default
        ``lexical-fallback``). ``openai-embedding`` additionally requires
        ``MY_GUY_EMBEDDING_URL`` and accepts ``MY_GUY_EMBEDDING_MODEL`` plus an
        optional ``MY_GUY_EMBEDDING_API_KEY`` (falling back to
        ``OPENAI_API_KEY`` so an existing provider credential can be reused).
        """
        env = os.environ if env is None else env
        backend = env.get("MY_GUY_SEMANTIC_BACKEND", LEXICAL_BACKEND).strip() or LEXICAL_BACKEND
        if backend == LEXICAL_BACKEND:
            return cls()
        if backend != EMBEDDING_BACKEND:
            raise ValueError(
                f"unsupported MY_GUY_SEMANTIC_BACKEND: {backend}; "
                f"expected one of {sorted(BACKENDS)}"
            )
        url = env.get("MY_GUY_EMBEDDING_URL", "").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError(
                "MY_GUY_EMBEDDING_URL must be an http(s) embeddings endpoint "
                "for the openai-embedding backend"
            )
        model = env.get("MY_GUY_EMBEDDING_MODEL", "").strip() or DEFAULT_EMBEDDING_MODEL
        api_key = env.get("MY_GUY_EMBEDDING_API_KEY", "").strip() or env.get(
            "OPENAI_API_KEY", ""
        ).strip() or None
        return cls(
            backend=backend,
            embed_fn=openai_embedding_fn(url=url, model=model, api_key=api_key),
        )

    def _lexical_hits(
        self, query: str, capabilities: tuple[Capability, ...]
    ) -> list[SearchHit]:
        query_tokens = _tokens(query)
        ranked: list[SearchHit] = []
        for capability in capabilities:
            searchable = _tokens(_capability_text(capability))
            evidence = tuple(sorted(query_tokens.intersection(searchable)))
            if evidence:
                ranked.append(
                    SearchHit(
                        capability,
                        len(evidence) / max(len(query_tokens), 1),
                        evidence,
                        LEXICAL_BACKEND,
                    )
                )
        ranked.sort(key=lambda hit: (-hit.score, hit.capability.id))
        return ranked

    def search(
        self,
        query: str,
        capabilities: Iterable[Capability],
        limit: int | None = None,
    ) -> tuple[SearchHit, ...]:
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative or None")
        capabilities = tuple(capabilities)
        if self.backend == LEXICAL_BACKEND or self.embed_fn is None:
            ranked = self._lexical_hits(query, capabilities)
            return tuple(ranked if limit is None else ranked[:limit])
        texts = tuple(_capability_text(capability) for capability in capabilities)
        try:
            vectors = self.embed_fn((query, *texts))
            if len(vectors) != len(texts) + 1:
                raise SemanticBackendError("embedding provider returned missing rows")
        except SemanticBackendError:
            ranked = self._lexical_hits(query, capabilities)
            return tuple(ranked if limit is None else ranked[:limit])
        query_vector, capability_vectors = vectors[0], vectors[1:]
        ranked = [
            SearchHit(
                capability,
                _cosine(query_vector, vector),
                tuple(sorted(_tokens(query).intersection(_tokens(_capability_text(capability))))),
                self.backend,
            )
            for capability, vector in zip(capabilities, capability_vectors)
        ]
        ranked.sort(key=lambda hit: (-hit.score, hit.capability.id))
        return tuple(ranked if limit is None else ranked[:limit])
