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
    ),
    Capability(
        id="ui-review",
        source="gstack",
        description="Reviews visual design, browser behavior, and accessibility.",
        domains=("ui", "design", "browser"),
        triggers=("ui", "design", "browser", "accessibility", "layout"),
        invocation="/gstack",
    ),
    Capability(
        id="research",
        source="matt-pocock",
        description="Researches a question against high-trust primary sources.",
        domains=("research", "facts"),
        triggers=("research", "compare", "source", "evidence", "fact"),
        invocation="/research",
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
    assert decision.candidates == ("security-review", "ui-review", "research")


def test_asks_for_clarity_when_no_capability_matches():
    decision = route("I have a thought about something.", CAPABILITIES)

    assert decision.status == "clarify"
    assert decision.candidates == ()
    assert decision.confidence == 0.0


def test_does_not_claim_execution():
    decision = route("Fix the security issue now.", CAPABILITIES)

    assert decision.approval_required is True


def test_clarifies_when_only_weak_generic_language_matches():
    decision = route("Can you help me with this?", CAPABILITIES)

    assert decision.status == "clarify"
