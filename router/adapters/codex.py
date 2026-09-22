from dataclasses import dataclass


@dataclass(frozen=True)
class CodexHandoff:
    harness: str
    invocation: str
    request: str
    instruction: str


class CodexAdapter:
    """Render approved invocations for Codex without spawning a subprocess."""

    harness = "codex"

    def __init__(self, allowed_invocations: frozenset[str]) -> None:
        self.allowed_invocations = allowed_invocations

    def invoke(self, invocation: str, request: str) -> CodexHandoff:
        if invocation not in self.allowed_invocations:
            raise PermissionError("Codex adapter does not allow this invocation")
        return CodexHandoff(
            harness=self.harness,
            invocation=invocation,
            request=request,
            instruction=(
                f"Run the approved capability `{invocation}` for this request. "
                "Return evidence, uncertainty, and any required next approval."
            ),
        )
