from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Protocol

from .approval import ApprovalRequired
from .models import Capability, RouteDecision


@dataclass(frozen=True)
class ApprovalToken:
    decision_digest: str

    @classmethod
    def for_execution(
        cls, decision: RouteDecision, capability: Capability, request: str
    ) -> "ApprovalToken":
        payload = json.dumps(
            {
                "capability_id": capability.id,
                "candidates": decision.candidates,
                "decision_request": decision.request,
                "invocation": capability.invocation,
                "reason": decision.reason,
                "request": request,
                "status": decision.status,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return cls(sha256(payload.encode("utf-8")).hexdigest())

    def matches(self, decision: RouteDecision, capability: Capability, request: str) -> bool:
        return self == self.for_execution(decision, capability, request)


class InvocationAdapter(Protocol):
    allowed_invocations: frozenset[str]

    def invoke(self, invocation: str, request: str) -> object:
        ...


def execute(
    decision: RouteDecision,
    capability: Capability,
    request: str,
    approval: ApprovalToken | None,
    adapter: InvocationAdapter,
) -> object:
    """Delegate only to an allowlisted adapter after trust and approval checks."""
    if capability.trust not in {"verified", "local"}:
        raise PermissionError("unverified capabilities cannot be executed")
    if decision.status == "clarify":
        raise PermissionError("clarification decisions cannot be executed")
    if capability.id not in decision.candidates:
        raise PermissionError("capability is not one of the approved route candidates")
    if approval is None or not approval.matches(decision, capability, request):
        raise ApprovalRequired("matching explicit approval is required before execution")
    if capability.invocation not in adapter.allowed_invocations:
        raise PermissionError("adapter does not allow this invocation")
    return adapter.invoke(capability.invocation, request)
