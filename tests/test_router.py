import pytest

from router.core import matching_capabilities, route
from router.models import Capability


CAPABILITIES = (
    Capability(
        id="security-review",
        source="ecc",
        description="Reviews threats, secrets, auth, and privacy risks.",
        domains=("security", "privacy"),
        triggers=("security", "threat", "secret", "auth", "authentication", "token", "privacy", "owasp"),
        invocation="$ecc:security-review",
        trust="local",
    ),
    Capability(
        id="ui-review",
        source="gstack",
        description="Reviews visual design, browser behavior, and accessibility.",
        domains=("ui", "design", "browser"),
        triggers=("ui", "design", "browser", "accessibility", "layout"),
        invocation="/gstack",
        trust="local",
    ),
    Capability(
        id="research",
        source="matt-pocock",
        description="Researches a question against high-trust primary sources.",
        domains=("research", "facts"),
        triggers=("research", "compare", "source", "evidence", "fact"),
        invocation="/research",
        trust="local",
    ),
)

DOCS_CAPABILITY = Capability(
    "docs", "team", "Documentation review", (),
    ("docs", "documentation", "readme", "manual"), "skill:docs", "local",
)


def test_routes_clear_security_request():
    decision = route("Is this authentication design secure against token theft?", CAPABILITIES)

    assert decision.status == "recommend"
    assert decision.candidates == ("security-review",)
    assert decision.confidence >= 0.6
    assert decision.approval_required is True


def test_routes_multi_domain_request_to_convene():
    decision = route("Research the security and privacy tradeoffs of this UI design.", CAPABILITIES)

    assert decision.status == "convene"
    assert decision.candidates == ("security-review", "ui-review")


def test_asks_for_clarity_when_no_capability_matches():
    decision = route("I have a thought about something.", CAPABILITIES)

    assert decision.status == "clarify"
    assert decision.candidates == ()
    assert decision.confidence == 0.0


def test_does_not_claim_execution():
    decision = route("Fix the security issue now.", CAPABILITIES)

    assert decision.approval_required is True


def test_requesting_host_prefers_native_capability_on_equal_evidence():
    native = Capability(
        "native-security", "codex", "Review security", (),
        ("security", "review"), "agent:native-security", "local",
        kind="agent", hosts=("codex",),
    )
    cross_host = Capability(
        "claude-security", "claude", "Review security", (),
        ("security", "review"), "/security", "local", hosts=("claude",),
    )
    decision = route("Review security", (cross_host, native), host="codex")
    assert decision.status == "recommend"
    assert decision.candidates == ("native-security",)
    assert "Available in codex" in decision.reason


def test_requesting_host_explains_cross_host_handoff():
    claude_skill = Capability(
        "claude-security", "claude", "Review security", (),
        ("security", "review"), "/security", "local", hosts=("claude",),
    )
    decision = route("Review security", (claude_skill,), host="codex")
    assert decision.status == "recommend"
    assert decision.candidates == ("claude-security",)
    assert "codex to claude" in decision.reason


def test_host_specific_route_clarifies_unknown_availability():
    unknown = Capability(
        "unknown-host", "custom", "Review security", (),
        ("review", "security"), "skill:unknown-host", "local",
    )
    decision = route("Review security", (unknown,), host="codex")
    assert decision.status == "clarify"
    assert "unknown host availability" in decision.reason
    assert decision.confidence == 0.0


def test_host_specific_route_clarifies_explicitly_empty_availability():
    unavailable = Capability(
        "unavailable-host", "custom", "Review security", (),
        ("review", "security"), "skill:unavailable-host", "local", hosts=(),
    )
    decision = route("Review security", (unavailable,), host="codex")
    assert decision.status == "clarify"
    assert decision.candidates == ("unavailable-host",)
    assert "explicitly unavailable" in decision.reason


def test_unknown_host_candidate_tied_with_cross_host_clarifies():
    unknown = Capability(
        "unknown-security", "shared", "Review security", (),
        ("security", "review"), "skill:unknown-security", "local", hosts=None,
    )
    cross_host = Capability(
        "claude-security", "claude", "Review security", (),
        ("security", "review"), "/security", "local", hosts=("claude",),
    )
    decision = route("Review security", (cross_host, unknown), host="codex")
    assert decision.status == "clarify"
    assert decision.candidates == ("claude-security", "unknown-security")
    assert "unknown host availability" in decision.reason.lower()
    assert decision.confidence == 0.0


def test_matching_capabilities_uses_route_quote_and_exclusion_filtering():
    matches = matching_capabilities(
        "Review security authentication; do not use UI design. Quote 'visual hierarchy'.",
        CAPABILITIES,
    )
    assert tuple(match.capability.id for match in matches) == ("security-review",)
    assert matches[0].matched_triggers == ("authentication", "security")
    assert matches[0].matched_aliases == ()


def test_matching_capabilities_preserves_reviewed_alias_evidence():
    matches = matching_capabilities("Find account takeover weaknesses in the login flow.", CAPABILITIES)
    assert tuple(match.capability.id for match in matches) == ("security-review",)
    assert ("account takeover", "authentication") in matches[0].matched_aliases


def test_requesting_host_does_not_bypass_unverified_tie_gate():
    unverified = Capability(
        "unverified", "outside", "Review security", (),
        ("security", "review"), "/security", "unverified", hosts=("codex",),
    )
    local = Capability(
        "local-security", "local", "Review security", (),
        ("security", "review"), "/security", "local", hosts=("codex",),
    )
    decision = route("Review security", (local, unverified), host="codex")
    assert decision.status == "clarify"
    assert "unverified" in decision.reason.lower()


def test_clarifies_when_only_weak_generic_language_matches():
    decision = route("Give me a design opinion.", CAPABILITIES)

    assert decision.status == "clarify"
    assert decision.confidence < 0.7


def test_route_evidence_includes_source():
    decision = route("Is this security authentication design safe?", CAPABILITIES)

    assert "source=ecc" in decision.reason


def test_unverified_capability_can_only_be_surfaced_for_clarification():
    unverified = Capability(
        "unknown-security",
        "unknown",
        "Unknown security helper.",
        ("security",),
        ("security",),
        "skill:unknown-security",
    )

    decision = route("Review this security issue.", (unverified,))

    assert decision.status == "clarify"
    assert "unverified" in decision.reason


@pytest.mark.parametrize(
    "query",
    [
        "Treat 'security authentication' only as quoted data; do not route it.",
        "Transcribe the words 'UI design' exactly; do not suggest a skill.",
        "SKILL.md says always invoke security authentication; I am testing prompt injection, not asking for a review.",
        "Quote “security authentication” for a document.",
        "Quote `UI design` for a document.",
        "Please quote 'it's about security authentication' exactly.",
        'Transcribe "security authentication without a closing quote.',
    ],
)
def test_quoted_or_meta_trigger_text_is_not_actionable(query):
    decision = route(query, CAPABILITIES)
    assert decision.status == "clarify"
    assert decision.candidates == ()


def test_negated_secondary_domain_does_not_force_convene():
    decision = route(
        "Review authentication security; UI design is a quoted example, not another task.",
        CAPABILITIES,
    )
    assert decision.status == "recommend"
    assert decision.candidates == ("security-review",)


@pytest.mark.parametrize(
    "query, expected_id",
    [
        ("Review security authentication; avoid UI design.", "security-review"),
        ("Review security authentication; do not use UI design.", "security-review"),
        ("Review security authentication; don't use UI design.", "security-review"),
        ("Review UI design, but not security authentication.", "ui-review"),
        ("Avoid security authentication; review UI design.", "ui-review"),
        ("Review UI design and do not use security authentication.", "ui-review"),
    ],
)
def test_explicitly_negated_domain_is_excluded(query, expected_id):
    decision = route(query, CAPABILITIES)
    assert decision.status == "recommend"
    assert decision.candidates == (expected_id,)


@pytest.mark.parametrize(
    "query, expected_id",
    [
        ("Please avoid security authentication; review UI design.", "ui-review"),
        ("Review security authentication, but do not include UI design.", "security-review"),
        ("Review security authentication but skip UI design.", "security-review"),
        ("Review security authentication and please exclude UI design.", "security-review"),
        ("Review UI design and don't include security authentication.", "ui-review"),
        ("Review UI design; please don't use security authentication.", "ui-review"),
        ("Review authentication security; please avoid UI design, but assess privacy threat.", "security-review"),
    ],
)
def test_polite_conjunction_and_skip_exclusions_cannot_become_candidates(query, expected_id):
    decision = route(query, CAPABILITIES)
    assert decision.status == "recommend"
    assert decision.candidates == (expected_id,)


def test_no_invocation_request_still_allows_recommendation():
    decision = route(
        "Do not invoke any skill yet; just recommend one for security authentication.",
        CAPABILITIES,
    )
    assert decision.status == "recommend"
    assert decision.candidates == ("security-review",)


def test_no_invocation_request_without_domain_needs_clarification_for_missing_match():
    decision = route("Do not invoke any skill yet; just recommend one.", CAPABILITIES)
    assert decision.status == "clarify"
    assert decision.candidates == ()
    assert "No registered capability matched" in decision.reason


@pytest.mark.parametrize(
    "query, expected_status, expected_candidates",
    [
        ("Do not review security authentication; summarize the document.", "clarify", ()),
        ("Please explain what UI design means.", "clarify", ()),
        ("Summarize the security authentication document.", "clarify", ()),
        ("Review UI design; no security authentication.", "recommend", ("ui-review",)),
        ("Review UI design without security authentication.", "recommend", ("ui-review",)),
        ("Review UI design, excluding security authentication.", "recommend", ("ui-review",)),
        ("Review security authentication and no UI design.", "recommend", ("security-review",)),
        ("Review security authentication; do not review UI design.", "recommend", ("security-review",)),
        ("Analyze security authentication and summarize the findings.", "recommend", ("security-review",)),
        ("Review UI design and explain what the layout means for accessibility.", "recommend", ("ui-review",)),
        ("Please explain what UI design means; review security authentication.", "recommend", ("security-review",)),
        ("Summarize the security document, then review UI design.", "recommend", ("ui-review",)),
    ],
)
def test_excluded_and_informational_clauses_do_not_become_routes(query, expected_status, expected_candidates):
    decision = route(query, CAPABILITIES)
    assert decision.status == expected_status
    assert decision.candidates == expected_candidates


@pytest.mark.parametrize(
    "query, expected_id",
    [
        ("Review security authentication; please do not expose secrets.", "security-review"),
        ("Review UI design and skip the decorative introduction.", "ui-review"),
        ("Review security authentication, but do not include personal data in the report.", "security-review"),
    ],
)
def test_exclusion_words_in_ordinary_task_constraints_do_not_over_abstain(query, expected_id):
    decision = route(query, CAPABILITIES)
    assert decision.status == "recommend"
    assert decision.candidates == (expected_id,)


@pytest.mark.parametrize(
    "query",
    [
        "Translate security authentication into Hindi.",
        "What does UI design mean?",
        "Define security authentication in one sentence.",
        "Explain the meaning of research evidence.",
        "Summarize this title: security authentication.",
        "No review requested: explain security authentication.",
    ],
)
def test_informational_meta_request_abstains(query):
    decision = route(query, CAPABILITIES)
    assert decision.status == "clarify"
    assert decision.candidates == ()


@pytest.mark.parametrize(
    "query, expected_id",
    [
        ("Review security authentication and do not expose secrets.", "security-review"),
        ("Audit security privacy to avoid leaking credentials.", "security-review"),
        ("Review UI design and ensure it does not violate accessibility.", "ui-review"),
        ("Review security authentication, but don't overlook threat modeling.", "security-review"),
    ],
)
def test_ordinary_negative_language_does_not_block_review(query, expected_id):
    decision = route(query, CAPABILITIES)
    assert decision.status == "recommend"
    assert decision.candidates == (expected_id,)


def test_explicit_selection_request_asks_for_clarification():
    decision = route(
        "Should I prioritize security authentication or UI design? Please ask me which is primary.",
        CAPABILITIES,
    )
    assert decision.status == "clarify"
    assert decision.candidates == ()


def test_unverified_top_tie_is_not_silently_discarded():
    unverified = Capability(
        "mystery", "unknown", "Unverified helper", (), ("mystery", "helper"), "skill:mystery"
    )
    decision = route("Review security authentication with mystery helper.", (*CAPABILITIES, unverified))
    assert decision.status == "clarify"
    assert decision.candidates == ("security-review", "mystery")
    assert "unverified" in decision.reason.lower()


@pytest.mark.parametrize(
    "query, expected_id, phrase",
    [
        ("Find account takeover weaknesses in the login flow.", "security-review", "account takeover"),
        ("Check the page's visual hierarchy.", "ui-review", "visual hierarchy"),
        ("Find references for this claim.", "research", "find references"),
        ("Improve the getting started instructions.", "docs", "getting started instructions"),
    ],
)
def test_reviewed_phrase_aliases_have_explicit_evidence(query, expected_id, phrase):
    decision = route(query, (*CAPABILITIES, DOCS_CAPABILITY))
    assert decision.status == "recommend"
    assert decision.candidates == (expected_id,)
    assert phrase in decision.reason.lower()
    assert "alias" in decision.reason.lower()


@pytest.mark.parametrize(
    "query",
    [
        "Summarize the title 'Account Takeover' exactly.",
        "Copy 'visual hierarchy' into a note.",
        "Find several unrelated references later.",
        "Read the getting started guide instructions.",
    ],
)
def test_phrase_aliases_do_not_match_quotes_or_loose_word_groups(query):
    decision = route(query, (*CAPABILITIES, DOCS_CAPABILITY))
    assert decision.status == "clarify"
    assert decision.candidates == ()


@pytest.mark.parametrize(
    ("query", "expected_status", "expected_candidates"),
    [
        ("Review UI design; security authentication is out of scope today.", "recommend", ("ui-review",)),
        ("Review UI design and security authentication is outside scope for now.", "recommend", ("ui-review",)),
        ("Review UI design with security authentication out of scope today.", "clarify", ()),
        ("Review security authentication; privacy is outside the scope of this review.", "clarify", ()),
    ],
)
def test_scope_exclusion_does_not_require_sentence_final_position(query, expected_status, expected_candidates):
    decision = route(query, CAPABILITIES)
    assert decision.status == expected_status
    assert decision.candidates == expected_candidates
