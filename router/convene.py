from dataclasses import dataclass
from collections.abc import Iterable


@dataclass(frozen=True)
class SpecialistResponse:
    specialist: str
    position: str
    evidence: tuple[str, ...] = ()
    confidence: float = 0.0
    available: bool = True

    def __post_init__(self) -> None:
        if not self.specialist.strip() or not self.position.strip():
            raise ValueError("specialist and position are required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class ConveneResult:
    status: str
    consensus: str | None
    strongest_dissent: str | None
    responses: tuple[SpecialistResponse, ...]
    reason: str


def synthesize(responses: Iterable[SpecialistResponse]) -> ConveneResult:
    """Synthesize supplied specialist responses without invoking specialists."""
    responses = tuple(responses)
    available = tuple(response for response in responses if response.available)
    if len(available) < 2:
        return ConveneResult(
            "insufficient-evidence",
            None,
            None,
            responses,
            "At least two available specialists are required; failures remain visible.",
        )

    groups: dict[str, list[SpecialistResponse]] = {}
    for response in available:
        groups.setdefault(response.position.strip(), []).append(response)
    ranked = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    winning_position, winning_responses = ranked[0]
    dissent_groups = ranked[1:]
    dissent = (
        max(
            dissent_groups,
            key=lambda item: (max(response.confidence for response in item[1]), item[0]),
        )[0]
        if dissent_groups
        else None
    )
    if len(ranked) == 1:
        return ConveneResult(
            "consensus",
            winning_position,
            None,
            responses,
            "All available specialists returned the same position.",
        )
    if len(winning_responses) == len(available):
        status = "consensus"
    else:
        status = "disagreement"
    return ConveneResult(
        status,
        winning_position if len(winning_responses) > len(available) / 2 else None,
        dissent,
        responses,
        "Specialist positions differ; disagreement is preserved.",
    )
