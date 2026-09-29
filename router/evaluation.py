from dataclasses import dataclass
from collections.abc import Iterable
import re

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
    category: str = "general"


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
    status_correct: int = 0
    candidate_correct: int = 0
    actionable: int = 0
    actionable_with_evidence: int = 0
    unsafe_actionable: int = 0

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 1.0

    @property
    def status_accuracy(self) -> float:
        return self.status_correct / self.total if self.total else 1.0

    @property
    def candidate_accuracy(self) -> float:
        return self.candidate_correct / self.total if self.total else 1.0

    @property
    def evidence_coverage(self) -> float | None:
        return self.actionable_with_evidence / self.actionable if self.actionable else None

    @property
    def unsafe_actionable_rate(self) -> float | None:
        return self.unsafe_actionable / self.actionable if self.actionable else None


def _has_evidence(decision: RouteDecision, by_id: dict[str, Capability]) -> bool:
    if not decision.candidates:
        return False
    for candidate_id in decision.candidates:
        capability = by_id.get(candidate_id)
        if capability is None:
            return False
        if decision.status == "recommend":
            if len(decision.candidates) != 1 or not decision.reason.startswith("Matched "):
                return False
            if f"; source={capability.source}; invoke {capability.invocation}." not in decision.reason:
                return False
            matched_text = decision.reason.removeprefix("Matched ").split(";", 1)[0]
        else:
            marker = f"{candidate_id} (source={capability.source}): "
            if "Evidence: " not in decision.reason or marker not in decision.reason:
                return False
            matched_text = decision.reason.split(marker, 1)[1].split(";", 1)[0]
        if not any(re.search(rf"\b{re.escape(trigger)}\b", matched_text, re.IGNORECASE) for trigger in capability.triggers):
            return False
    return True


def evaluate(
    cases: Iterable[EvaluationCase], capabilities: Iterable[Capability]
) -> EvaluationReport:
    capabilities = tuple(capabilities)
    by_id = {capability.id: capability for capability in capabilities}
    failures: list[EvaluationFailure] = []
    total = 0
    passed = 0
    status_correct = 0
    candidate_correct = 0
    actionable = 0
    actionable_with_evidence = 0
    unsafe_actionable = 0
    for case in cases:
        total += 1
        decision = route(case.request, capabilities)
        reasons: list[str] = []
        if decision.status == case.expected_status:
            status_correct += 1
        else:
            reasons.append(f"status={decision.status!r}, expected {case.expected_status!r}")
        if decision.candidates == case.expected_candidates:
            candidate_correct += 1
        else:
            reasons.append(
                f"candidates={decision.candidates!r}, expected {case.expected_candidates!r}"
            )
        if not case.min_confidence <= decision.confidence <= case.max_confidence:
            reasons.append(f"confidence={decision.confidence:.2f} outside expected range")
        if decision.status in {"recommend", "convene"}:
            actionable += 1
            if _has_evidence(decision, by_id):
                actionable_with_evidence += 1
            else:
                reasons.append("actionable decision lacks candidate provenance, trigger, or invocation evidence")
            if (
                decision.status != case.expected_status
                or decision.candidates != case.expected_candidates
                or any(by_id.get(candidate_id) is None or by_id[candidate_id].trust == "unverified" for candidate_id in decision.candidates)
            ):
                unsafe_actionable += 1
        if reasons:
            failures.append(EvaluationFailure(case.name, decision, "; ".join(reasons)))
        else:
            passed += 1
    return EvaluationReport(
        total, passed, tuple(failures), status_correct, candidate_correct,
        actionable, actionable_with_evidence, unsafe_actionable,
    )
