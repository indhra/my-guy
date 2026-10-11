import pytest

from router.adapters.opencode import OpenCodeAdapter
from router.adapters.openrouter import OpenRouterAdapter
from router.approval import ApprovalRequired
from router.execution import ApprovalToken, HostMappingRequired, execute
from router.models import Capability, RouteDecision


def test_opencode_adapter_is_provider_shape_neutral():
    decision = RouteDecision("recommend", "Review UI.", ("ui",), "source=gstack", 0.9)
    capability = Capability(
        "ui", "gstack", "UI review", (), ("ui",), "/gstack", "local",
        hosts=("opencode",),
    )
    result = execute(decision, capability, decision.request, ApprovalToken.for_execution(decision, capability, decision.request), OpenCodeAdapter(frozenset({"/gstack"})))

    assert result.harness == "opencode"
    assert "configured OpenCode host" in result.instruction


def test_openrouter_handoff_requires_host_mapping_and_never_invokes_adapter():
    decision = RouteDecision("recommend", "Research.", ("research",), "source=matt", 0.9)
    capability = Capability("research", "matt", "Research", (), ("research",), "/research", "local")
    adapter = OpenRouterAdapter(frozenset({"/research"}))
    calls = []
    adapter.invoke = lambda *args: calls.append(args)

    with pytest.raises(HostMappingRequired, match="mapped to a supported agent host"):
        execute(
            decision,
            capability,
            decision.request,
            ApprovalToken.for_execution(decision, capability, decision.request),
            adapter,
        )
    assert calls == []


def test_direct_openrouter_invocation_requires_host_mapping():
    adapter = OpenRouterAdapter(frozenset({"/research"}))

    with pytest.raises(HostMappingRequired, match="mapped to a supported agent host"):
        adapter.invoke("/research", "Research this.")


def test_direct_openrouter_invocation_still_checks_allowlist_first():
    adapter = OpenRouterAdapter(frozenset())

    with pytest.raises(PermissionError, match="does not allow this invocation"):
        adapter.invoke("/research", "Research this.")


def test_openrouter_host_mapping_refusal_preserves_approval_and_allowlist_gates():
    decision = RouteDecision("recommend", "Research.", ("research",), "source=matt", 0.9)
    capability = Capability("research", "matt", "Research", (), ("research",), "/research", "local")
    adapter = OpenRouterAdapter(frozenset())

    with pytest.raises(ApprovalRequired):
        execute(decision, capability, decision.request, None, adapter)
    with pytest.raises(PermissionError, match="does not allow"):
        execute(
            decision,
            capability,
            decision.request,
            ApprovalToken.for_execution(decision, capability, decision.request),
            adapter,
        )
