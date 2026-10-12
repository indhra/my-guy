import re
from collections.abc import Iterable
from typing import NamedTuple

from .models import Capability, RouteDecision
from .query import exclusion_tokens, explicit_abstention, matched_aliases, routing_spans, uncertain_exclusion
from .semantic import LEXICAL_BACKEND, SemanticSearch

MAX_REASON_CANDIDATES = 20
MIN_RECOMMEND_CONFIDENCE = 0.7
# A semantic-only match counts like a single alias hit: enough to cross the
# confidence gate on its own, but never stronger than direct token evidence.
SEMANTIC_SCORE = 2
SEMANTIC_MIN_SIMILARITY = 0.55
TRUSTED_FOR_ROUTING = frozenset({"verified", "local"})


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _evidence(matched: set[str], aliases: tuple[tuple[str, str], ...]) -> str:
    parts = [*sorted(matched), *(f"alias '{phrase}' -> {trigger}" for phrase, trigger in aliases)]
    return ", ".join(parts)


def _match_evidence(
    matched: set[str], aliases: tuple[tuple[str, str], ...], semantic_note: str
) -> str:
    base = _evidence(matched, aliases)
    if base and semantic_note:
        return f"{base}, {semantic_note}"
    return base or semantic_note


class CapabilityMatch(NamedTuple):
    score: int
    capability: Capability
    matched_triggers: tuple[str, ...]
    matched_aliases: tuple[tuple[str, str], ...]


def route(
    request: str,
    capabilities: Iterable[Capability],
    *,
    host: str | None = None,
    semantic: SemanticSearch | None = None,
) -> RouteDecision:
    """Return a recommendation without invoking tools or changing files.

    Transparent token matches are the primary evidence. An explicitly
    configured non-lexical ``semantic`` backend may add candidates and
    corroborating notes, but every candidate still passes the same exclusion,
    trust, host-availability, and confidence gates.
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
    capabilities = tuple(capabilities)
    scored: list[tuple[int, Capability, set[str], tuple[tuple[str, str], ...]]] = []
    excluded_matches = False

    def excluded_capability(capability: Capability) -> bool:
        domain_tokens = set().union(*(_tokens(domain) for domain in capability.domains))
        return bool(
            excluded.intersection(set(capability.triggers) | domain_tokens)
            or excluded_alias_triggers.intersection(capability.triggers)
        )

    for capability in capabilities:
        matched = text.intersection(capability.triggers)
        applicable_aliases = tuple(alias for alias in aliases if alias[1] in capability.triggers)
        if matched or applicable_aliases:
            if excluded_capability(capability):
                excluded_matches = True
                continue
            score = len(matched) + 2 * len(applicable_aliases)
            scored.append((score, capability, matched, applicable_aliases))

    semantic_notes: dict[str, str] = {}
    if semantic is not None and semantic.backend != LEXICAL_BACKEND:
        scored_ids = {item[1].id for item in scored}
        for hit in semantic.search(clean_request, capabilities):
            if hit.score < SEMANTIC_MIN_SIMILARITY:
                break
            capability = hit.capability
            note = f"semantic {hit.score:.2f} ({hit.backend})"
            if capability.id in scored_ids:
                semantic_notes[capability.id] = note
                continue
            if excluded_capability(capability):
                excluded_matches = True
                continue
            scored.append((SEMANTIC_SCORE, capability, set(), ()))
            scored_ids.add(capability.id)
            semantic_notes[capability.id] = note

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
    best_score = scored[0][0]
    top = [item for item in scored if item[0] == best_score]
    unknown = [item for item in top if item[1].hosts is None]
    available = [item for item in top if item[1].hosts]
    # A host-specific request prefers a native route among equally strong
    # matches. Unknown availability blocks only non-native fallbacks, since a
    # legacy capability must not be inferred to belong to this host.
    if host is not None:
        native = [item for item in available if host in item[1].hosts]
        if native:
            selected = native
        elif unknown:
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
        else:
            selected = available
    else:
        # Unknown host scope stays routable without a host; an explicitly empty
        # host tuple is unusable everywhere.
        selected = [item for item in top if item[1].hosts != ()]
    if not selected:
        return RouteDecision(
            status="clarify",
            request=request,
            candidates=tuple(item[1].id for item in top),
            reason="Matching capabilities are explicitly unavailable on every supported host.",
            confidence=0.0,
        )
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
                f"Matched {_match_evidence(matched, matched_phrases, semantic_notes.get(capability.id, ''))}; "
                f"source={capability.source}; "
                f"invoke {capability.invocation}.{availability}"
            ),
            confidence=confidence,
        )

    candidate_ids = tuple(item[1].id for item in selected)
    evidence = "; ".join(
        f"{item[1].id} (source={item[1].source}): "
        f"{_match_evidence(item[2], item[3], semantic_notes.get(item[1].id, ''))}"
        for item in selected[:MAX_REASON_CANDIDATES]
    )
    if len(selected) > MAX_REASON_CANDIDATES:
        evidence += f"; ... and {len(selected) - MAX_REASON_CANDIDATES} more"
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
