import re
from collections.abc import Iterable
from typing import NamedTuple

from .models import Capability, RouteDecision
from .query import exclusion_tokens, explicit_abstention, matched_aliases, routing_spans, uncertain_exclusion

MIN_RECOMMEND_CONFIDENCE = 0.7
TRUSTED_FOR_ROUTING = frozenset({"verified", "local"})


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _evidence(matched: set[str], aliases: tuple[tuple[str, str], ...]) -> str:
    parts = [*sorted(matched), *(f"alias '{phrase}' -> {trigger}" for phrase, trigger in aliases)]
    return ", ".join(parts)


class CapabilityMatch(NamedTuple):
    score: int
    capability: Capability
    matched_triggers: tuple[str, ...]
    matched_aliases: tuple[tuple[str, str], ...]


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

    if explicit_abstention(request):
        return RouteDecision(
            status="clarify",
            request=request,
            candidates=(),
            reason="Request asks for no route or for a choice before routing.",
            confidence=0.0,
        )

    if uncertain_exclusion(request):
        return RouteDecision(
            status="clarify",
            request=request,
            candidates=(),
            reason="Exclusion scope is uncertain; clarify the requested and excluded work before routing.",
            confidence=0.0,
        )
    clean_request, excluded_text = routing_spans(request)
    text = _tokens(clean_request)
    aliases = matched_aliases(clean_request)
    excluded = exclusion_tokens(excluded_text)
    excluded_alias_triggers = {trigger for _, trigger in matched_aliases(excluded_text)}
    scored: list[tuple[int, Capability, set[str], tuple[tuple[str, str], ...]]] = []
    excluded_matches = False
    for capability in capabilities:
        matched = text.intersection(capability.triggers)
        applicable_aliases = tuple(alias for alias in aliases if alias[1] in capability.triggers)
        if matched or applicable_aliases:
            domain_tokens = set().union(*(_tokens(domain) for domain in capability.domains))
            if (excluded.intersection(set(capability.triggers) | domain_tokens)
                    or excluded_alias_triggers.intersection(capability.triggers)):
                excluded_matches = True
                continue
            score = len(matched) + 2 * len(applicable_aliases)
            scored.append((score, capability, matched, applicable_aliases))

    scored.sort(
        key=lambda item: (
            -item[0],
            0
            if host is None
            or (item[1].hosts is not None and host in item[1].hosts)
            else 1,
            item[1].id,
        )
    )
    if not scored:
        return RouteDecision(
            status="clarify",
            request=request,
            candidates=(),
            reason=("Explicit exclusions overlap every matching capability; clarify before routing."
                    if excluded_matches else "No registered capability matched the request."),
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
    best_trusted_score = trusted[0][0]
    blocked = [
        item for item in scored
        if item[1].trust not in TRUSTED_FOR_ROUTING and item[0] >= best_trusted_score
    ]
    if blocked:
        leading_trusted = [item for item in trusted if item[0] == best_trusted_score]
        return RouteDecision(
            status="clarify",
            request=request,
            candidates=tuple(item[1].id for item in (*leading_trusted, *blocked)),
            reason="Unverified capability matched the leading trusted route; verify provenance or clarify the request.",
            confidence=0.0,
        )
    scored = trusted
    # A host-specific request can prefer a native route among equally strong
    # matches. If availability is unknown for every top match, clarify rather
    # than inferring that a legacy capability belongs to this host.
    if host is not None:
        best_score = scored[0][0]
        top = [item for item in scored if item[0] == best_score]
        unknown = [item for item in top if item[1].hosts is None]
        known = [item for item in top if item[1].hosts is not None]
        if unknown:
            return RouteDecision(
                status="clarify",
                request=request,
                candidates=tuple(item[1].id for item in top),
                reason=(
                    "A top-scoring capability has unknown host availability; "
                    "configure explicit host coverage before routing."
                ),
                confidence=0.0,
            )
        if not known:
            return RouteDecision(
                status="clarify",
                request=request,
                candidates=tuple(item[1].id for item in top),
                reason="Matching capabilities have unknown host availability; rediscover or configure hosts before routing.",
                confidence=0.0,
            )
        available = [item for item in known if item[1].hosts]
        native = [item for item in available if host in item[1].hosts]
        selected = native or available
        if not selected:
            if unknown:
                return RouteDecision(
                    status="clarify",
                    request=request,
                    candidates=tuple(item[1].id for item in unknown),
                    reason="Matching capabilities have unknown host availability; rediscover or configure hosts before routing.",
                    confidence=0.0,
                )
            return RouteDecision(
                status="clarify",
                request=request,
                candidates=tuple(item[1].id for item in known),
                reason="Matching capabilities are explicitly unavailable on every supported host.",
                confidence=0.0,
            )
    else:
        selected = [item for item in scored if item[0] == scored[0][0]]
    if len(selected) == 1:
        score, capability, matched, matched_phrases = selected[0]
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
                f"Matched {_evidence(matched, matched_phrases)}; source={capability.source}; "
                f"invoke {capability.invocation}.{availability}"
            ),
            confidence=confidence,
        )

    candidate_ids = tuple(item[1].id for item in selected)
    evidence = "; ".join(
        f"{item[1].id} (source={item[1].source}): {_evidence(item[2], item[3])}" for item in selected
    )
    return RouteDecision(
        status="convene",
        request=request,
        candidates=candidate_ids,
        reason=f"Multiple capabilities matched; convene specialists. Evidence: {evidence}.",
        confidence=min(0.9, 0.4 + (0.1 * len(selected))),
    )


def _match_capabilities(
    request: str, capabilities: Iterable[Capability]
) -> tuple[tuple[CapabilityMatch, ...], bool]:
    if explicit_abstention(request) or uncertain_exclusion(request):
        return (), False

    clean_request, excluded_text = routing_spans(request)
    text = _tokens(clean_request)
    aliases = matched_aliases(clean_request)
    excluded = exclusion_tokens(excluded_text)
    excluded_alias_triggers = {trigger for _, trigger in matched_aliases(excluded_text)}
    scored: list[CapabilityMatch] = []
    excluded_matches = False
    for capability in capabilities:
        matched = text.intersection(capability.triggers)
        applicable_aliases = tuple(alias for alias in aliases if alias[1] in capability.triggers)
        if not matched and not applicable_aliases:
            continue
        domain_tokens = set().union(*(_tokens(domain) for domain in capability.domains))
        if (
            excluded.intersection(set(capability.triggers) | domain_tokens)
            or excluded_alias_triggers.intersection(capability.triggers)
        ):
            excluded_matches = True
            continue
        score = len(matched) + 2 * len(applicable_aliases)
        scored.append(
            CapabilityMatch(score, capability, tuple(sorted(matched)), applicable_aliases)
        )
    scored.sort(key=lambda item: (-item.score, item.capability.id))
    return tuple(scored), excluded_matches


def matching_capabilities(
    request: str, capabilities: Iterable[Capability]
) -> tuple[CapabilityMatch, ...]:
    """Return evidence-filtered matches with the same query semantics as route().

    Quoted, excluded, informational, and explicit-abstention text is omitted.
    This supports evidence display; callers must still apply route's trust and
    host-availability gates before presenting an actionable handoff.
    """
    return _match_capabilities(request, capabilities)[0]
