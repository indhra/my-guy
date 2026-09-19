import pytest

from router.approval import ApprovalRequired, require_approval
from router.models import RouteDecision


def test_execution_requires_explicit_approval():
    decision = RouteDecision("recommend", "request", ("security-review",), "reason", 0.9)

    with pytest.raises(ApprovalRequired):
        require_approval(decision, approved=False)

    require_approval(decision, approved=True)


def test_caller_cannot_disable_approval_flag():
    decision = RouteDecision("recommend", "request", ("security-review",), "reason", 0.9, False)

    with pytest.raises(ApprovalRequired):
        require_approval(decision, approved=False)
