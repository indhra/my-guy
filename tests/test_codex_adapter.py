from router.adapters.codex import CodexAdapter
from router.execution import ApprovalToken, execute
from router.models import Capability, RouteDecision


def test_codex_adapter_renders_approved_handoff_without_execution():
    decision = RouteDecision("recommend", "Review security.", ("security",), "source=ecc", 0.9)
    capability = Capability("security", "ecc", "Security review", (), ("security",), "skill:security", "local")
    adapter = CodexAdapter(frozenset({"skill:security"}))

    handoff = execute(
        decision,
        capability,
        decision.request,
        ApprovalToken.for_execution(decision, capability, decision.request),
        adapter,
    )

    assert handoff.harness == "codex"
    assert handoff.invocation == "skill:security"
    assert "evidence" in handoff.instruction


def test_codex_adapter_rejects_claude_only_capability():
    import pytest

    decision = RouteDecision("recommend", "Review security.", ("security",), "source=claude", 0.9)
    capability = Capability(
        "security", "claude", "Security review", (), ("security",),
        "/security", "local", hosts=("claude",),
    )
    adapter = CodexAdapter(frozenset({"/security"}))
    approval = ApprovalToken.for_execution(decision, capability, decision.request)
    with pytest.raises(PermissionError, match="host is not available"):
        execute(decision, capability, decision.request, approval, adapter)
