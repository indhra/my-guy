from router.evaluation import EvaluationCase, evaluate
from router.models import Capability


CAPABILITIES = (
    Capability("security", "ecc", "Security and authentication review.", ("security",), ("security", "authentication"), "skill:security", "local"),
    Capability("design", "gstack", "UI and browser design review.", ("ui",), ("ui", "design"), "skill:design", "local"),
    Capability("research", "matt", "Research and evidence review.", ("research",), ("research", "evidence"), "skill:research", "local"),
    Capability("unknown", "local-file", "Unverified mystery helper.", ("mystery",), ("mystery",), "skill:unknown"),
)


def test_evaluation_reports_per_case_accuracy_and_confidence():
    report = evaluate(
        [
            EvaluationCase("clear-security", "Review authentication security.", "recommend", ("security",), 0.7),
            EvaluationCase("cross-domain", "Compare security UI research concerns.", "convene", ("design", "research", "security"), 0.0, 0.9),
            EvaluationCase("vague", "I have a thought.", "clarify", (), 0.0, 0.0),
            EvaluationCase("unverified", "Review this mystery helper.", "clarify", ("unknown",), 0.0, 0.0),
        ],
        CAPABILITIES,
    )

    assert report.total == 4
    assert report.passed == 4
    assert report.accuracy == 1.0
    assert report.failures == ()
