from dataclasses import dataclass
from typing import Literal


RouteStatus = Literal["recommend", "clarify", "convene"]


@dataclass(frozen=True)
class Capability:
    id: str
    source: str
    description: str
    domains: tuple[str, ...]
    triggers: tuple[str, ...]
    invocation: str
    trust: str = "unverified"


@dataclass(frozen=True)
class RouteDecision:
    status: RouteStatus
    request: str
    candidates: tuple[str, ...]
    reason: str
    confidence: float
    approval_required: bool = True
