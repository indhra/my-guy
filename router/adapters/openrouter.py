from dataclasses import dataclass

from ..errors import HostMappingRequired


@dataclass(frozen=True)
class OpenRouterHandoff:
    harness: str
    invocation: str
    request: str
    instruction: str


class OpenRouterAdapter:
    """Disabled provider-neutral adapter pending supported-host mapping."""

    harness = "openrouter"

    def __init__(self, allowed_invocations: frozenset[str]) -> None:
        self.allowed_invocations = allowed_invocations

    def invoke(self, invocation: str, request: str) -> OpenRouterHandoff:
        if invocation not in self.allowed_invocations:
            raise PermissionError("OpenRouter adapter does not allow this invocation")
        raise HostMappingRequired()
