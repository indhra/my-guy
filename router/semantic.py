import re
from dataclasses import dataclass
from collections.abc import Iterable

from .models import Capability


@dataclass(frozen=True)
class SearchHit:
    capability: Capability
    score: float
    evidence: tuple[str, ...]
    backend: str


class SemanticSearch:
    """Optional semantic interface with a transparent lexical fallback.

    A future embedding provider can implement the same `search` contract.
    This class deliberately has no network or model dependency.
    """

    def __init__(self, backend: str = "lexical-fallback") -> None:
        if backend != "lexical-fallback":
            raise ValueError("only the lexical-fallback backend is implemented")
        self.backend = backend

    def search(
        self,
        query: str,
        capabilities: Iterable[Capability],
        limit: int | None = None,
    ) -> tuple[SearchHit, ...]:
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative or None")
        query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        ranked: list[SearchHit] = []
        for capability in capabilities:
            searchable = set(
                re.findall(
                    r"[a-z0-9]+",
                    " ".join(
                        [capability.id, capability.description, *capability.domains, *capability.triggers]
                    ).lower(),
                )
            )
            evidence = tuple(sorted(query_tokens.intersection(searchable)))
            if evidence:
                ranked.append(
                    SearchHit(capability, len(evidence) / max(len(query_tokens), 1), evidence, self.backend)
                )
        ranked.sort(key=lambda hit: (-hit.score, hit.capability.id))
        return tuple(ranked if limit is None else ranked[:limit])
