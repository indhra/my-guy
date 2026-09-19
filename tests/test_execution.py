import pytest

from router.approval import ApprovalRequired
from router.execution import ApprovalToken, execute
from router.models import Capability, RouteDecision


class FakeAdapter:
    allowed_invocations = frozenset({"skill:security"})

    def __init__(self):
        self.calls = []

    def invoke(self, invocation, request):
        self.calls.append((invocation, request))
        return "delegated"


def decision():
    return RouteDecision("recommend", "Review security.", ("security",), "source=ecc", 0.9)


def test_execution_requires_matching_approval_and_allowlisted_adapter():
    capability = Capability("security", "ecc", "Security review", (), ("security",), "skill:security", "local")
    adapter = FakeAdapter()

    assert execute(decision(), capability, "Review security.", ApprovalToken.for_decision(decision()), adapter) == "delegated"
    assert adapter.calls == [("skill:security", "Review security.")]


def test_execution_rejects_missing_or_mismatched_approval():
    capability = Capability("security", "ecc", "Security review", (), ("security",), "skill:security", "local")
    adapter = FakeAdapter()

    with pytest.raises(ApprovalRequired):
        execute(decision(), capability, "Review security.", None, adapter)
    other = RouteDecision("recommend", "Different request", ("security",), "source=ecc", 0.9)
    with pytest.raises(ApprovalRequired):
        execute(decision(), capability, "Review security.", ApprovalToken.for_decision(other), adapter)


def test_execution_rejects_unverified_and_unallowlisted_capabilities():
    adapter = FakeAdapter()
    unverified = Capability("unknown", "local-file", "Unknown", (), ("security",), "skill:unknown")
    with pytest.raises(PermissionError):
        execute(decision(), unverified, "Review security.", ApprovalToken.for_decision(decision()), adapter)

    unsupported = Capability("other", "ecc", "Other", (), ("security",), "skill:other", "local")
    with pytest.raises(PermissionError):
        execute(decision(), unsupported, "Review security.", ApprovalToken.for_decision(decision()), adapter)
