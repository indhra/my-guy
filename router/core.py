import re
from collections.abc import Iterable

from .models import Capability, RouteDecision

MIN_RECOMMEND_CONFIDENCE = 0.7
TRUSTED_FOR_ROUTING = frozenset({"verified", "local"})


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def route(
    request: str, capabilities: Iterable[Capability], *, host: str | None = None
) -> RouteDecision:
    """Return a recommendation without invoking tools or changing files.

    This first slice intentionally uses transparent token matches. A later
    adapter may add semantic classification, but it must preserve this
    approval boundary and expose its evidence.
    """
    if host is not None and host not in {"codex", "claude", "opencode"}:
        raise ValueError(f"unsupported requesting host: {host}")
    text = _tokens(request)
    scored: list[tuple[int, Capability, set[str]]] = []
    for capability in capabilities:
        matched = text.intersection(capability.triggers)
        if matched:
            scored.append((len(matched), capability, matched))

    scored.sort(
        key=lambda item: (
            -item[0],
            0 if host is None or host in item[1].hosts else 1,
            item[1].id,
        )
    )
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
    if host is not None:
        available = [item for item in trusted if item[1].hosts]
        if not available:
            return RouteDecision(
                status="clarify",
                request=request,
                candidates=tuple(item[1].id for item in trusted if item[0] == trusted[0][0]),
                reason="Matching capabilities have no known host availability; configure their hosts before routing.",
                confidence=0.0,
            )
        trusted = available
    scored = trusted
    selected = [
        item for item in scored
        if item[0] == scored[0][0]
        and (host is None or (host in item[1].hosts) == (host in scored[0][1].hosts))
    ]
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
        availability = ""
        if host is not None:
            if host in capability.hosts:
                availability = f" Available in {host}."
            else:
                availability = (
                    f" Cross-host handoff required from {host} to "
                    f"{capability.hosts[0]}."
                )
        return RouteDecision(
            status="recommend",
            request=request,
            candidates=(capability.id,),
            reason=(
                f"Matched {', '.join(sorted(matched))}; source={capability.source}; "
                f"invoke {capability.invocation}.{availability}"
            ),
            confidence=confidence,
        )

    candidate_ids = tuple(item[1].id for item in selected)
    examples = ", ".join(item[1].id for item in selected[:3])
    return RouteDecision(
        status="convene",
        request=request,
        candidates=candidate_ids,
        reason=(
            f"{len(selected)} capabilities share the top match score; convene specialists. "
            f"Examples: {examples}."
        ),
        confidence=min(0.9, 0.4 + (0.1 * len(selected))),
    )
