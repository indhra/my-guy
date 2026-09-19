from router.adapters.opencode import OpenCodeAdapter
from router.adapters.openrouter import OpenRouterAdapter
from router.execution import ApprovalToken, execute
from router.models import Capability, RouteDecision


def test_opencode_adapter_is_provider_shape_neutral():
    decision = RouteDecision("recommend", "Review UI.", ("ui",), "source=gstack", 0.9)
    capability = Capability("ui", "gstack", "UI review", (), ("ui",), "/gstack", "local")
    result = execute(decision, capability, decision.request, ApprovalToken.for_decision(decision), OpenCodeAdapter(frozenset({"/gstack"})))

    assert result.harness == "opencode"
    assert "configured OpenCode host" in result.instruction


def test_openrouter_adapter_does_not_make_network_calls():
    decision = RouteDecision("recommend", "Research.", ("research",), "source=matt", 0.9)
    capability = Capability("research", "matt", "Research", (), ("research",), "/research", "local")
    result = execute(decision, capability, decision.request, ApprovalToken.for_decision(decision), OpenRouterAdapter(frozenset({"/research"})))

    assert result.harness == "openrouter"
    assert "configured OpenRouter host" in result.instruction
