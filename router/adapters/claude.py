from dataclasses import dataclass


@dataclass(frozen=True)
class ClaudeHandoff:
    harness: str
    invocation: str
    request: str
    instruction: str


class ClaudeAdapter:
    """Render approved skill invocations for Claude Code."""

    harness = "claude"

    def __init__(self, allowed_invocations: frozenset[str]) -> None:
        self.allowed_invocations = allowed_invocations

    def invoke(self, invocation: str, request: str) -> ClaudeHandoff:
        if invocation not in self.allowed_invocations:
            raise PermissionError("Claude adapter does not allow this invocation")
        return ClaudeHandoff(
            harness=self.harness,
            invocation=invocation,
            request=request,
            instruction=f"Invoke `{invocation}` in Claude Code for the approved request; preserve evidence and uncertainty.",
        )
