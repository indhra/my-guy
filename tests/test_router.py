from router.core import route
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
