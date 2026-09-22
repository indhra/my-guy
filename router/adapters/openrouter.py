from dataclasses import dataclass


@dataclass(frozen=True)
class OpenRouterHandoff:
    harness: str
    invocation: str
    request: str
    instruction: str


class OpenRouterAdapter:
    """Render a provider-neutral OpenRouter handoff; performs no network call."""

    harness = "openrouter"

    def __init__(self, allowed_invocations: frozenset[str]) -> None:
        self.allowed_invocations = allowed_invocations

    def invoke(self, invocation: str, request: str) -> OpenRouterHandoff:
        if invocation not in self.allowed_invocations:
            raise PermissionError("OpenRouter adapter does not allow this invocation")
        return OpenRouterHandoff(
            self.harness,
            invocation,
            request,
            f"Send the approved request to the configured OpenRouter host using `{invocation}`; preserve evidence and uncertainty.",
        )
