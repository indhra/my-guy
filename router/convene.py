from dataclasses import dataclass
from collections.abc import Iterable


@dataclass(frozen=True)
class SpecialistResponse:
    specialist: str
    position: str
    evidence: tuple[str, ...] = ()
    confidence: float = 0.0
    available: bool = True


@dataclass(frozen=True)
class ConveneResult:
    status: str
    consensus: str | None
    strongest_dissent: str | None
    responses: tuple[SpecialistResponse, ...]
    reason: str


def synthesize(responses: Iterable[SpecialistResponse]) -> ConveneResult:
    """Synthesize supplied specialist responses without invoking specialists."""
    responses = tuple(response for response in responses if response.available)
    if not responses:
        return ConveneResult("unavailable", None, None, (), "No specialist response was available.")

    groups: dict[str, list[SpecialistResponse]] = {}
    for response in responses:
        groups.setdefault(response.position.strip(), []).append(response)
    ranked = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    winning_position, winning_responses = ranked[0]
    dissent = next((position for position, _ in ranked[1:]), None)
    if len(ranked) == 1:
        return ConveneResult(
            "consensus",
            winning_position,
            None,
            responses,
            "All available specialists returned the same position.",
        )
    if len(winning_responses) == len(responses):
        status = "consensus"
    else:
        status = "disagreement"
    return ConveneResult(
        status,
        winning_position if len(winning_responses) > len(responses) / 2 else None,
        dissent,
        responses,
        "Specialist positions differ; disagreement is preserved.",
    )
