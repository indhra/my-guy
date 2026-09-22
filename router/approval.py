from .models import RouteDecision


class ApprovalRequired(PermissionError):
    """Raised when an adapter attempts to execute without explicit approval."""


def require_approval(decision: RouteDecision, approved: bool) -> None:
    if not approved:
        raise ApprovalRequired("explicit approval is required before execution")
