from dataclasses import dataclass
from typing import ClassVar
from typing import Literal
import re


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
    kind: str = "skill"
    # Empty means no host provenance has been recorded. Execution policy for
    # legacy entries remains intentionally separate from inventory inference.
    hosts: tuple[str, ...] = ()

    TRUST_LEVELS: ClassVar[frozenset[str]] = frozenset({"verified", "local", "unverified"})

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.source.strip() or not self.invocation.strip():
            raise ValueError("capability id, source, and invocation are required")
        if len(self.id) > 192 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:._/-]*", self.id):
            raise ValueError("capability id contains unsupported characters")
        if len(self.source) > 4096 or len(self.description) > 8192 or len(self.invocation) > 512:
            raise ValueError("capability metadata exceeds safety limits")
        if any(character in self.invocation for character in "\r\n\x00"):
            raise ValueError("invocation must be a single line")
        if len(self.triggers) > 256 or any(len(trigger) > 128 for trigger in self.triggers):
            raise ValueError("capability triggers exceed safety limits")
        if self.trust not in self.TRUST_LEVELS:
            raise ValueError(f"unsupported trust level: {self.trust}")
        if self.kind not in {"skill", "agent"}:
            raise ValueError(f"unsupported capability kind: {self.kind}")
        if not isinstance(self.hosts, tuple) or len(set(self.hosts)) != len(self.hosts) or any(
            host not in {"codex", "claude", "opencode"} for host in self.hosts
        ):
            raise ValueError("capability hosts must be unique supported hosts")
        object.__setattr__(self, "triggers", tuple(trigger.lower() for trigger in self.triggers))


@dataclass(frozen=True)
class RouteDecision:
    status: RouteStatus
    request: str
    candidates: tuple[str, ...]
    reason: str
    confidence: float
    approval_required: bool = True

    def __post_init__(self) -> None:
        if not self.request.strip():
            raise ValueError("route request is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
