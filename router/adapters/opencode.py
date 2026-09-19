from dataclasses import dataclass


@dataclass(frozen=True)
class OpenCodeHandoff:
    harness: str
    invocation: str
    request: str
    instruction: str


class OpenCodeAdapter:
    """Render an OpenCode handoff without assuming a provider command shape."""

    harness = "opencode"

    def __init__(self, allowed_invocations: frozenset[str]) -> None:
        self.allowed_invocations = allowed_invocations

    def invoke(self, invocation: str, request: str) -> OpenCodeHandoff:
        if invocation not in self.allowed_invocations:
            raise PermissionError("OpenCode adapter does not allow this invocation")
        return OpenCodeHandoff(
            self.harness,
            invocation,
            request,
            f"Pass the approved invocation `{invocation}` to the configured OpenCode host; do not broaden scope.",
        )
