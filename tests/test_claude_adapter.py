from router.adapters.claude import ClaudeAdapter
from router.execution import ApprovalToken, execute
from router.models import Capability, RouteDecision


def test_claude_adapter_renders_approved_handoff():
    decision = RouteDecision("recommend", "Research this.", ("research",), "source=matt", 0.9)
    capability = Capability("research", "matt", "Research", (), ("research",), "/research", "local")
    handoff = execute(
        decision,
        capability,
        decision.request,
        ApprovalToken.for_decision(decision),
        ClaudeAdapter(frozenset({"/research"})),
    )

    assert handoff.harness == "claude"
    assert handoff.invocation == "/research"
