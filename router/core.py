import re
from collections.abc import Iterable

from .models import Capability, RouteDecision

MIN_RECOMMEND_CONFIDENCE = 0.7
TRUSTED_FOR_ROUTING = frozenset({"verified", "local"})


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def route(request: str, capabilities: Iterable[Capability]) -> RouteDecision:
    """Return a recommendation without invoking tools or changing files.

    This first slice intentionally uses transparent token matches. A later
    adapter may add semantic classification, but it must preserve this
    approval boundary and expose its evidence.
    """
    text = _tokens(request)
    scored: list[tuple[int, Capability, set[str]]] = []
    for capability in capabilities:
        matched = text.intersection(capability.triggers)
        if matched:
            scored.append((len(matched), capability, matched))

    scored.sort(key=lambda item: (-item[0], item[1].id))
    if not scored:
        return RouteDecision(
            status="clarify",
            request=request,
            candidates=(),
            reason="No registered capability matched the request.",
            confidence=0.0,
        )
    trusted = [item for item in scored if item[1].trust in TRUSTED_FOR_ROUTING]
    if not trusted:
        return RouteDecision(
            status="clarify",
            request=request,
            candidates=tuple(item[1].id for item in scored if item[0] == scored[0][0]),
            reason="Only unverified capabilities matched; verify provenance before routing.",
            confidence=0.0,
        )
    scored = trusted
    selected = [item for item in scored if item[0] == scored[0][0]]
    if len(selected) == 1:
        score, capability, matched = selected[0]
        confidence = min(0.95, 0.45 + (0.15 * score))
        if confidence < MIN_RECOMMEND_CONFIDENCE:
            return RouteDecision(
                status="clarify",
                request=request,
                candidates=(capability.id,),
                reason=f"Low-confidence match for {capability.id}; clarify before routing.",
                confidence=confidence,
            )
        return RouteDecision(
            status="recommend",
            request=request,
            candidates=(capability.id,),
            reason=(
                f"Matched {', '.join(sorted(matched))}; source={capability.source}; "
                f"invoke {capability.invocation}."
            ),
            confidence=confidence,
        )

    candidate_ids = tuple(item[1].id for item in selected)
    evidence = "; ".join(
        f"{item[1].id} (source={item[1].source}): {', '.join(sorted(item[2]))}" for item in selected
    )
    return RouteDecision(
        status="convene",
        request=request,
        candidates=candidate_ids,
        reason=f"Multiple capabilities matched; convene specialists. Evidence: {evidence}.",
        confidence=min(0.9, 0.4 + (0.1 * len(selected))),
    )
