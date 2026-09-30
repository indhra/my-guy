class HostMappingRequired(PermissionError):
    """Raised when a handoff target has no mapping to a supported agent host."""

    def __init__(self) -> None:
        super().__init__(
            "OpenRouter handoffs are disabled until mapped to a supported agent host."
        )
