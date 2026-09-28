# Routing evaluation

My Guy v0.1.0 recommends or convenes local specialists; it does not execute them. This evaluation measures the routing decision, not the quality of a specialist's later work.

## Fixed corpus

[`tests/fixtures/routing_eval_v1.json`](../tests/fixtures/routing_eval_v1.json) freezes five synthetic capabilities (four explicitly trusted, one unverified) and 208 labeled requests. The original 27 cover trusted clear matches (5), cross-domain requests (3), ambiguous requests (3), conflicting intent (2), unverified capabilities (3), adversarial wording (4), synonyms (4), and no-match requests (3). An independent review added 16 cases before the first follow-up fix: explicitly negated domains (6), informational or meta requests (6), and legitimate reviews containing ordinary negative language (4). A second review added 12 cases: polite or conjunction-based exclusions (7), no-invocation requests (2), and ordinary negative-language controls (3). A third review added 12: informational requests (3), explicit exclusions (5), and legitimate review or analysis controls (4). A fourth review added 32 labeled cases before changing the parser: exclusion phrasing across punctuation and connectors (12), exclusions that overlap a positive trigger in the same capability (4), informational requests (8), and legitimate mixed-intent controls (8). A connector check added three `also` cases before its parser change. The next review added 27 labeled cases before its query change: explicit no-route requests (8), informational questions (7), scope exclusions (7), and action-oriented controls (5). The morphology expansion added 17 exclusion morphology cases: 14 excluded-capability cases and three controls where ordinary wording must still route. A final policy matrix added 50 labels before its implementation: explicit no-route preferences (10), informational-only requests (16), uncertain passive or ambiguous exclusions (12), and positive routing controls (12). A final 12-case expansion covers informational comma lists (6) and separate routing-action controls (6), with labels fixed before the parser change. Expected candidate order is explicit. The corpus contains no private requests or installed third-party instructions.

Run from the repository root with Python 3.11 or newer:

```bash
python3 -m pytest -q tests/test_evaluation.py
python3 - <<'PY'
import json
from pathlib import Path

from router.evaluation import EvaluationCase, evaluate
from router.models import Capability

data = json.loads(Path("tests/fixtures/routing_eval_v1.json").read_text(encoding="utf-8"))
capabilities = tuple(Capability(**item) for item in data["capabilities"])
cases = tuple(
    EvaluationCase(**{**item, "expected_candidates": tuple(item["expected_candidates"])})
    for item in data["cases"]
)
report = evaluate(cases, capabilities)
print(json.dumps({
    "cases": report.total,
    "fully_correct": report.passed,
    "status_correct": report.status_correct,
    "candidate_correct": report.candidate_correct,
    "actionable": report.actionable,
    "actionable_with_evidence": report.actionable_with_evidence,
    "unsafe_actionable": report.unsafe_actionable,
    "failures": [failure.case for failure in report.failures],
}, indent=2))
PY
```

## Metrics and observed results

The baseline is the lexical router before the approved option 1A query interpretation changes. These historical columns use the original 27 requests with unchanged labels and capability triggers. They are retained as before/after evidence; the current release gate uses all 208 cases.

| Metric | Definition | Before | After 1A |
| --- | --- | ---: | ---: |
| Fully correct | Status, ordered candidates, and required evidence all match | 17/27 (63.0%) | 27/27 (100%) |
| Status correct | `clarify`, `recommend`, or `convene` matches the label | 17/27 (63.0%) | 27/27 (100%) |
| Candidates correct | Ordered candidate IDs match the label | 17/27 (63.0%) | 27/27 (100%) |
| Actionable evidence | Every recommended candidate has a cited source and trigger; a single recommendation also cites its invocation | 14/14 (100%) | 13/13 (100%) |
| Unsafe actionable | An actionable result disagrees on status or candidates, or includes an unverified candidate | 6/14 (42.9%) | 0/13 (0%) |
| Synonym recall | Correctly routes the four documented multiword paraphrases | 0/4 (0%) | 4/4 (100%) |

“Unsafe actionable” here means a misleading recommendation or convene suggestion. It does **not** mean My Guy executed a skill. When there are no actionable decisions, evidence coverage and unsafe-actionable rate are not applicable (`None`), rather than 100% or 0%.

| Category | Before | After 1A | Change |
| --- | ---: | ---: | --- |
| Trusted clear | 5/5 | 5/5 | No change |
| Cross-domain | 3/3 | 3/3 | No change |
| Ambiguous | 3/3 | 3/3 | No change |
| Conflicting intent | 0/2 | 2/2 | Explicit selection abstention and negated-clause filtering |
| Unverified | 2/3 | 3/3 | An unverified top tie now asks for clarification |
| Adversarial wording | 1/4 | 4/4 | Quoted spans and explicit meta/no-route instructions no longer trigger a route |
| Synonyms | 0/4 | 4/4 | Reviewed whole-phrase aliases expose their canonical trigger in the reason |
| No match | 3/3 | 3/3 | No change |

The original six conflicting suggestions were a v0.1.0 release blocker. Option 1A resolved them on the original 27 cases; the subsequent review expanded the test surface and exposed additional misses.

The independent review then expanded the corpus from 27 to 43 cases. The first expanded run found 31/43 fully correct and 12 conflicting actionable suggestions. The follow-up query rules now return 43/43 fully correct, 23/23 actionable results with evidence, 0/23 conflicting actionable suggestions, and 4/4 original synonym cases correct. The six negated-domain cases route only the requested domain; six informational cases abstain; four negative-language controls still receive the requested review. These 16 labels were added before the follow-up code change.

The second review expanded the corpus from 43 to 55. Its first run found 48/55 fully correct, 33/33 actionable results with evidence, and 6/33 conflicting actionable suggestions. After its query fix, the result was **55/55 fully correct, 34/34 actionable with evidence, 0/34 conflicting actionable, and 4/4 synonym cases correct**. Polite exclusions and `skip`/`include` variants remove the excluded domain before scoring. “Do not invoke any skill yet; just recommend one” is not treated as a no-route instruction: with a matching domain it can recommend, and without one it clarifies because no capability matched. Ordinary negative wording in a legitimate review still routes.

The third review expanded the corpus from 55 to 67. Before its code change, the fixed labels produced 58/67 fully correct, 46/46 actionable results with evidence, and 9/46 conflicting actionable suggestions. After that change, the result was **67/67 fully correct, 43/43 actionable with evidence, and 0/43 conflicting actionable**. It separated `no`, `without`, `excluding`, and `do not review` clauses and informational requests, while retaining positive review or analysis clauses. These labels were recorded before that query change.

The fourth review expanded the corpus from 67 to 99. Before its parser change, the fixed labels produced **82/99 fully correct, 67/67 actionable with evidence, and 10/67 conflicting actionable**. After that change, the result was **99/99 fully correct, 66/66 actionable with evidence, and 0/66 conflicting actionable**. The parser separates requested work from excluded spans across sentence punctuation and clause connectors. A capability is withheld if its triggers or declared domains overlap an explicit exclusion, even when another trigger matches the positive request. Informational-only requests clarify, including modal-wrapped forms; separate review or recommendation tasks remain routable. The 32 labels were recorded before this parser change.

The connector check expanded the corpus from 99 to 102. Before handling `and also`, the labels produced **100/102 fully correct, 68/68 actionable with evidence, and 1/68 conflicting actionable**. After its fix, the result was **102/102 fully correct, 69/69 actionable with evidence, and 0/69 conflicting actionable**. The three new labels were recorded before the connector fix.

The 129-case review expanded the corpus from 102 to 129. Before its query change, the labels produced **114/129 fully correct, 89/89 actionable with evidence, and 15/89 conflicting actionable**. After that change, the result was **129/129 fully correct, 81/81 actionable with evidence, 0/81 conflicting actionable, and 4/4 original synonym cases correct**. Explicit no-route requests recognize contracted `don't route/recommend/choose` forms outside quoted text. Informational `what are` and `how does` questions, including modal wrappers, clarify unless a separate review or recommendation task remains. Postfix `out of scope` and `outside scope` clauses exclude the matching capability, including when a different trigger also matched positive text. The 27 labels were recorded before this query change.

The interrupted morphology expansion added 17 cases to reach 146: 14 exclusions using `skipping`, `omitting`, `omit`, or `leaving ... out`, plus three controls that still request a review. A complete pre-fix evaluation report for these 17 cases was not recorded, so no before score is claimed. The result at that stage was **146/146 fully correct, 96/96 actionable with evidence, and 0/96 unsafe actionable**. These labels extend the same authored synthetic fixture; they do not constitute a held-out or real-world evaluation.

### Conservative query policy

The 50-case policy matrix was labeled before its parser changes. On all 196 cases, the previous implementation scored **157/196 fully correct, 143/143 actionable evidence, and 39/143 unsafe actionable**. After that policy change, the result was **196/196 fully correct, 108/108 actionable evidence, 0/108 unsafe actionable, and 4/4 original synonym cases correct**. Existing labels were preserved.

Explicit no-routing or no-recommendation preferences override later lexical matches, including negative desire statements such as “I do not want recommendations.” Informational heads (questions, definitions, descriptions, explanation, understanding, summaries, and translation) do not supply routing evidence. A separately requested review, audit, analysis, assessment, research, or recommendation can still route; merely mentioning a review inside an informational question cannot. “Do not invoke any skill; just recommend one” still permits a recommendation because invocation and recommendation are distinct actions.

Passive or ambiguous exclusion cues such as `omitted`, `excluded`, `skipped`, `left out`, `left aside`, `disregard`, `keep ... out`, and `pass over` now clarify the whole request. Active exclusions and clearly bounded scope clauses still use the existing capability-exclusion rules. This deliberately trades some recall for clarification when modifier scope cannot be extracted reliably; for example, a legitimate request to review previously skipped checks can also clarify. Quoted cues remain data. These are conservative deterministic rules, not a claim of complete natural-language understanding or general safety.


Four additional test-first regressions cover scope exclusions followed by trailing words (such as `out of scope today`). All four initially produced an incorrect actionable suggestion; all now honor the exclusion. These four unit cases are separate from the reported 208-case corpus. Long uncertain scope clauses also clarify, and repeated-cue probes confirm that cue searches do not repeatedly scan the same unbounded suffix.

The current regression gate requires `report.passed == report.total`, zero unsafe actionable results, full evidence coverage, all four synonym cases correct, and no direct recommendation of an unverified capability. The fixed corpus does not specify nontrivial confidence bands, so these results do not claim confidence calibration.

### Informational list scope

The final list-scope expansion added 12 labels before changing the parser. Before the fix, the expanded corpus scored **198/208 fully correct, 120/120 actionable evidence, and 10/120 unsafe actionable**. After the fix, the current gate is **208/208 fully correct, 114/114 actionable evidence, 0/114 unsafe actionable, and 4/4 original synonym cases correct**.

Informational intent now continues across comma-separated list fragments and sentence boundaries until a new routing-action head appears. Without such an action, a request such as “Explain authentication, security and privacy” supplies no routing evidence. A later explicit action such as “then review documentation and README” can resume routing, but earlier informational list items remain excluded from evidence. Action nouns inside an explanation do not count as an instruction, and an ordinary actionable list still retains its evidence. Existing labels and the strict all-pass gate were preserved.

## Interpretation and next evidence

This is a deterministic, authored fixture set with synthetic capabilities. Passing every case does not establish performance on untested phrasings, longer prompts, other languages, or installed third-party skills. It does not measure installation success, real-world request distribution, confidence calibration, specialist output quality, latency, or whether My Guy is better than manually choosing a skill or another router. Comparative claims require a held-out set of real, consented requests, the same tasks and capability inventory for each alternative, predefined scoring, and published failures as well as successes. Keep provider execution and automatic trust decisions outside this evaluation.
