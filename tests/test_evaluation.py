import json
from pathlib import Path

from router.core import route
from router.evaluation import EvaluationCase, evaluate
from router.models import Capability, RouteDecision


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


def test_evaluation_reports_status_safety_and_evidence_separately(monkeypatch):
    decisions = {
        "safe": RouteDecision("recommend", "safe", ("security",), "Matched security; source=ecc; invoke skill:security.", 0.75),
        "unsafe": RouteDecision("recommend", "unsafe", ("security",), "Matched security; source=ecc; invoke skill:security.", 0.75),
        "no-evidence": RouteDecision("recommend", "no-evidence", ("security",), "Good match.", 0.75),
        "untrusted": RouteDecision("recommend", "untrusted", ("unknown",), "Matched mystery; source=local-file; invoke skill:unknown.", 0.75),
    }
    monkeypatch.setattr("router.evaluation.route", lambda request, capabilities: decisions[request])
    cases = (
        EvaluationCase("safe", "safe", "recommend", ("security",)),
        EvaluationCase("unsafe", "unsafe", "clarify", ()),
        EvaluationCase("no-evidence", "no-evidence", "recommend", ("security",)),
        EvaluationCase("untrusted", "untrusted", "clarify", ("unknown",)),
    )

    report = evaluate(cases, CAPABILITIES)

    assert report.total == 4
    assert report.status_correct == 2
    assert report.status_accuracy == 0.5
    assert report.candidate_correct == 3
    assert report.candidate_accuracy == 0.75
    assert report.unsafe_actionable == 2
    assert report.unsafe_actionable_rate == 0.5
    assert report.actionable == 4
    assert report.actionable_with_evidence == 3
    assert report.evidence_coverage == 0.75
    assert report.passed == 1
    assert {failure.case for failure in report.failures} == {"unsafe", "no-evidence", "untrusted"}


def test_evidence_coverage_is_not_applicable_without_actionable_decisions(monkeypatch):
    monkeypatch.setattr(
        "router.evaluation.route",
        lambda request, capabilities: RouteDecision("clarify", request, (), "No match.", 0.0),
    )

    report = evaluate((EvaluationCase("none", "none", "clarify", ()),), CAPABILITIES)

    assert report.actionable == 0
    assert report.evidence_coverage is None
    assert report.unsafe_actionable == 0
    assert report.unsafe_actionable_rate is None


def test_invocation_name_is_not_sufficient_evidence(monkeypatch):
    monkeypatch.setattr(
        "router.evaluation.route",
        lambda request, capabilities: RouteDecision(
            "recommend", request, ("security",), "source=ecc; invoke skill:security.", 0.75
        ),
    )

    report = evaluate((EvaluationCase("missing-match", "missing-match", "recommend", ("security",)),), CAPABILITIES)

    assert report.actionable_with_evidence == 0
    assert report.passed == 0


def test_fixed_corpus_has_unique_cases_and_reports_known_limits():
    corpus = json.loads((Path(__file__).parent / "fixtures" / "routing_eval_v1.json").read_text(encoding="utf-8"))
    capabilities = tuple(Capability(**item) for item in corpus["capabilities"])
    cases = tuple(EvaluationCase(**{**item, "expected_candidates": tuple(item["expected_candidates"])}) for item in corpus["cases"])

    assert corpus["schema_version"] == 1
    assert len(cases) == 208
    assert len({case.name for case in cases}) == len(cases)
    assert {case.category for case in cases} == {
        "trusted_clear", "cross_domain", "ambiguous", "conflicting", "unverified", "adversarial", "synonym", "no_match",
        "negated_domain", "informational_meta", "negative_control",
        "exclusion_followup", "no_invoke", "informational_followup", "informational_control",
        "exclusion_matrix", "same_capability_exclusion", "informational_matrix", "mixed_intent_control",
        "explicit_no_route", "informational_question", "scope_exclusion", "action_question_control",
        "exclusion_morphology", "morphology_control",
        "no_route_policy", "informational_policy", "uncertain_exclusion_policy", "routing_policy_control",
        "informational_list", "informational_list_control",
    }
    report = evaluate(cases, capabilities)
    assert report.total == len(cases)
    assert report.passed == report.total
    assert report.unsafe_actionable == 0
    assert report.evidence_coverage == 1.0
    synonym_names = {case.name for case in cases if case.category == "synonym"}
    assert synonym_names.isdisjoint({failure.case for failure in report.failures})
    by_id = {capability.id: capability for capability in capabilities}
    decisions = (route(case.request, capabilities) for case in cases)
    assert all(
        by_id[candidate_id].trust != "unverified"
        for decision in decisions if decision.status in {"recommend", "convene"}
        for candidate_id in decision.candidates
    )
