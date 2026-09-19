from dataclasses import dataclass
from typing import ClassVar
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

    TRUST_LEVELS: ClassVar[frozenset[str]] = frozenset({"verified", "local", "unverified"})

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.source.strip() or not self.invocation.strip():
            raise ValueError("capability id, source, and invocation are required")
        if self.trust not in self.TRUST_LEVELS:
            raise ValueError(f"unsupported trust level: {self.trust}")
        object.__setattr__(self, "triggers", tuple(trigger.lower() for trigger in self.triggers))


@dataclass(frozen=True)
class RouteDecision:
    status: RouteStatus
    request: str
    candidates: tuple[str, ...]
    reason: str
    confidence: float
    approval_required: bool = True
