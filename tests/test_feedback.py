import pytest

from router.feedback import FeedbackStore


def test_feedback_is_opt_in_and_does_not_store_raw_request(tmp_path):
    store = FeedbackStore(tmp_path / "feedback.sqlite3")
    request = "private customer request"
    with pytest.raises(PermissionError):
        store.record(request, "security", "accepted", consent=False)
    store.record(request, "security", "accepted", consent=True)
    row = store.connection.execute("SELECT request_digest FROM route_feedback").fetchone()
    assert row[0] != request
    assert request.encode() not in (tmp_path / "feedback.sqlite3").read_bytes()
    store.close()


def test_feedback_only_creates_review_proposals_after_threshold():
    store = FeedbackStore()
    for index in range(5):
        outcome = "failed" if index < 3 else "accepted"
        store.record(f"request {index}", "security", outcome, consent=True)
    proposal = store.proposals()[0]
    assert proposal.capability_id == "security"
    assert proposal.samples == 5
    assert proposal.recommendation == "review triggers and provenance"
    store.close()
