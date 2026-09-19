from dataclasses import dataclass
from collections.abc import Iterable

from .core import route
from .models import Capability, RouteDecision


@dataclass(frozen=True)
class EvaluationCase:
    name: str
    request: str
    expected_status: str
    expected_candidates: tuple[str, ...]
    min_confidence: float = 0.0
    max_confidence: float = 1.0


@dataclass(frozen=True)
class EvaluationFailure:
    case: str
    decision: RouteDecision
    reason: str


@dataclass(frozen=True)
class EvaluationReport:
    total: int
    passed: int
    failures: tuple[EvaluationFailure, ...]

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 1.0


def evaluate(
    cases: Iterable[EvaluationCase], capabilities: Iterable[Capability]
) -> EvaluationReport:
    capabilities = tuple(capabilities)
    failures: list[EvaluationFailure] = []
    total = 0
    passed = 0
    for case in cases:
        total += 1
        decision = route(case.request, capabilities)
        reasons: list[str] = []
        if decision.status != case.expected_status:
            reasons.append(f"status={decision.status!r}, expected {case.expected_status!r}")
        if decision.candidates != case.expected_candidates:
            reasons.append(
                f"candidates={decision.candidates!r}, expected {case.expected_candidates!r}"
            )
        if not case.min_confidence <= decision.confidence <= case.max_confidence:
            reasons.append(f"confidence={decision.confidence:.2f} outside expected range")
        if reasons:
            failures.append(EvaluationFailure(case.name, decision, "; ".join(reasons)))
        else:
            passed += 1
    return EvaluationReport(total, passed, tuple(failures))
