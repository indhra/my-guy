from router.convene import SpecialistResponse, synthesize


def test_convene_reports_consensus_and_keeps_responses():
    result = synthesize(
        [
            SpecialistResponse("security", "defer", ("token risk",), 0.9),
            SpecialistResponse("design", "defer", ("missing user flow",), 0.8),
        ]
    )

    assert result.status == "consensus"
    assert result.consensus == "defer"
    assert len(result.responses) == 2


def test_convene_preserves_strongest_dissent_without_fake_consensus():
    result = synthesize(
        [
            SpecialistResponse("security", "ship", confidence=0.7),
            SpecialistResponse("design", "hold", confidence=0.9),
            SpecialistResponse("research", "hold", confidence=0.8),
        ]
    )

    assert result.status == "disagreement"
    assert result.consensus == "hold"
    assert result.strongest_dissent == "ship"


def test_convene_reports_unavailable_when_all_specialists_fail():
    result = synthesize([SpecialistResponse("security", "ship", available=False)])

    assert result.status == "insufficient-evidence"
    assert result.consensus is None
    assert len(result.responses) == 1


def test_convene_does_not_call_one_response_consensus():
    result = synthesize([SpecialistResponse("security", "ship", confidence=0.99)])

    assert result.status == "insufficient-evidence"
    assert result.consensus is None
