"""Optional semantic search with pluggable backends.

The default ``lexical-fallback`` backend is dependency-free and offline. An
opt-in ``openai-embedding`` backend calls an OpenAI-compatible ``/embeddings``
endpoint (a hosted provider or a local server such as Ollama or llama.cpp) so
routing can reuse whatever LLM endpoint the operator already has. Backend
configuration is explicit; a provider failure degrades transparently to the
lexical backend rather than failing the route.
"""

import json
import hashlib
import math
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse
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
MAX_EMBEDDING_CAPABILITIES = 512

EmbedFn = Callable[[tuple[str, ...]], tuple[tuple[float, ...], ...]]


@dataclass(frozen=True)
class SearchHit:
    capability: Capability
    score: float
    evidence: tuple[str, ...]
    backend: str


class SemanticBackendError(RuntimeError):
    """A configured semantic backend could not answer the query."""


def _embedding_api_key(env: dict, url: str) -> str | None:
    configured = env.get("MY_GUY_EMBEDDING_API_KEY", "").strip()
    if configured:
        return configured
    if urlparse(url).hostname == "api.openai.com":
        return env.get("OPENAI_API_KEY", "").strip() or None
    return None


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

    def __init__(
        self,
        backend: str = LEXICAL_BACKEND,
        *,
        embed_fn: EmbedFn | None = None,
        cache_path: Path | None = None,
        cache_namespace: str = "",
    ) -> None:
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
        self.cache_path = cache_path
        self.cache_namespace = cache_namespace
        self.last_backend: str | None = None

    @classmethod
    def from_env(
        cls, env: dict | None = None, *, cache_path: Path | None = None
    ) -> "SemanticSearch":
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
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(
                "MY_GUY_EMBEDDING_URL must be an http(s) embeddings endpoint "
                "with a hostname"
            )
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError(
                "MY_GUY_EMBEDDING_URL must use https unless the hostname is localhost"
            )
        model = env.get("MY_GUY_EMBEDDING_MODEL", "").strip() or DEFAULT_EMBEDDING_MODEL
        api_key = _embedding_api_key(env, url)
        return cls(
            backend=backend,
            embed_fn=openai_embedding_fn(url=url, model=model, api_key=api_key),
            cache_path=cache_path,
            cache_namespace=f"{url}\0{model}",
        )

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(
            f"{self.cache_namespace}\0{text}".encode("utf-8")
        ).hexdigest()

    def _load_cache(self) -> dict[str, tuple[float, ...]]:
        if self.cache_path is None:
            return {}
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return {}
            cache: dict[str, tuple[float, ...]] = {}
            for key, vector in payload.items():
                if (
                    isinstance(key, str)
                    and isinstance(vector, list)
                    and vector
                    and all(
                        isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and math.isfinite(value)
                        for value in vector
                    )
                ):
                    cache[key] = tuple(float(value) for value in vector)
            return cache
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}

    def _write_cache(self, cache: dict[str, tuple[float, ...]]) -> None:
        if self.cache_path is None:
            return
        parent = self.cache_path.parent
        parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=parent, prefix=f".{self.cache_path.name}.",
                delete=False,
            ) as output:
                temporary = output.name
                os.chmod(temporary, 0o600)
                json.dump(cache, output, separators=(",", ":"))
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.cache_path)
            os.chmod(self.cache_path, 0o600)
            temporary = None
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

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
        if (
            self.backend == LEXICAL_BACKEND
            or self.embed_fn is None
            or len(capabilities) > MAX_EMBEDDING_CAPABILITIES
        ):
            self.last_backend = LEXICAL_BACKEND
            ranked = self._lexical_hits(query, capabilities)
            return tuple(ranked if limit is None else ranked[:limit])
        texts = tuple(_capability_text(capability) for capability in capabilities)
        cache = self._load_cache()
        keys = tuple(self._cache_key(text) for text in texts)
        missing = tuple(
            (key, text) for key, text in zip(keys, texts) if key not in cache
        )
        try:
            vectors = self.embed_fn((query, *(text for _, text in missing)))
            if len(vectors) != len(missing) + 1:
                raise SemanticBackendError("embedding provider returned missing rows")
        except SemanticBackendError:
            self.last_backend = LEXICAL_BACKEND
            ranked = self._lexical_hits(query, capabilities)
            return tuple(ranked if limit is None else ranked[:limit])
        query_vector = vectors[0]
        for (key, _), vector in zip(missing, vectors[1:]):
            cache[key] = vector
        current_cache = {key: cache[key] for key in keys if key in cache}
        try:
            self._write_cache(current_cache)
        except OSError:
            pass
        self.last_backend = self.backend
        capability_vectors = tuple(cache[key] for key in keys)
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
