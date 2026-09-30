# Opt-in alpha onboarding pilot

This is a proposed, consent-based way to learn whether the published
[`v0.1.0` alpha](https://github.com/indhra/my-guy/releases/tag/v0.1.0) helps
people choose among skills they already use. It is not evidence of better
routing, native host recognition, or a speed multiplier. Read the
[install guide](AGENT_INSTALL.md), [status](STATUS.md), and [security policy](../SECURITY.md)
before inviting participants. The CLI recommends; it does not execute providers
or make third-party skills trustworthy.

## Enrollment and consent

Recruit 10–20 **distinct** solo developers who already use several local skill
packs. Start with a three-person dry run to check that the instructions,
scoring, and privacy process work; count those results separately and revise
the protocol before the main pilot if needed. Participation is voluntary.
Explain the two arms, local installation and rollback, information collected,
incident stop rules, and publication plan. Obtain explicit consent before setup
or task recording; allow withdrawal before aggregated results are published.
Do not include coworkers' or clients' private material without their permission.

Each participant chooses 3–5 genuine tasks from their own normal work. Do not
invent tasks to favor either arm. Include normal cases where the right answer
may be to clarify or say no useful capability exists. Before either arm runs,
record a short, sanitized task category and acceptable route or routes,
including when clarification or no-capability is appropriate. Keep the actual
request and any private context on the participant's machine.

## Paired run

1. Pin the same host application, model/version, non-My-Guy skill set and
   trusted-root decisions for both arms. Use the published `v0.1.0` tag; check
   that it resolves to `c6edf09de6a9fcd6df80ae7116f0735a5ecb0d7f`.
   Inspect existing installations and get approval before any replacement or
   trust change, as in the [install guide](AGENT_INSTALL.md).
2. For each task, use the identical request and relevant context in two fresh
   sessions. Randomize which arm runs first per task, and record that order.
   Avoid carrying suggestions, conversation history, or tool results from the
   first run into the second. Keep all other available skills equal.
3. In the **native** arm, let the host choose its normal route. Do not invoke
   My Guy, its front-door skill, or its CLI in this arm. In the **My Guy** arm,
   explicitly invoke My Guy's route before choosing the next step. The
   participant still decides whether to follow a recommendation and must
   approve any consequential action. No arm gets automatic skill trust.
4. Score the initial route against the acceptable route recorded before the
   outcomes. Then complete the task normally if appropriate. Record setup
   effort separately from task effort so installation time is visible and does
   not distort a single task's result.

Use the same task in both arms only when doing so is safe and repeatable. For
state-changing work, use two equivalent disposable copies or score routing
before any change, then complete the task only once. Record any deviation; do
not present an unpaired or changed task as a clean comparison.

## Scorecard

Record one row per task and arm, with a participant code and task code only:

| Field | Record |
| --- | --- |
| Before outcomes | Sanitized task category, acceptable route(s), reason for clarify/no-capability, pinned host/model/skills, arm order |
| Route quality | Correct selection; appropriate clarification; appropriate no-capability response; unsafe actionable suggestion (yes/no, brief sanitized reason) |
| Evidence | Whether the route gave usable source/evidence for its choice, and whether the participant could inspect it |
| Effort | Total task time, steps, tool calls, and tokens when the host exposes them; mark unavailable rather than estimate |
| Outcome | Task completion (secondary), participant-observed friction, and protocol deviations |

Count each route result, including misses, abstentions, and tasks that lack an
available capability. Record setup time and steps once per participant and
host. Do not turn unavailable token or tool counts into zeros. A route is
correct only if it matches a pre-recorded acceptable route; a correct-looking
answer discovered after the run does not change that record. Unsafe actionable
suggestions are reported separately and never offset by faster runs.

## Privacy and stop rules

Do not collect raw prompts, code, transcripts, credentials, private file paths,
or automatic telemetry. Participants keep raw work locally. Collect only the
scorecard fields above and sanitized comments they choose to share. Review
every public issue or example for secrets, personal information, customer data,
and identifying project details before submission. Use private security
reporting for vulnerabilities, as described in [SECURITY.md](../SECURITY.md).

Stop the affected run immediately for a privacy breach, unauthorized action,
or unsafe actionable suggestion. Preserve only a minimal sanitized incident
description, inform the participant, and pause further pilot work until the
cause and safe next step have been reviewed. Do not publish incident material
that could identify the participant or expose private work.

## Predeclared decision gate and reporting

Before the first dry-run task, freeze the scorecard, acceptable-route rubric,
arm-order method, and these decisions in a dated local copy:

- **Dry run:** proceed to the main pilot only if all three participants can
  complete the paired protocol without a privacy breach, unauthorized action,
  or unsafe actionable suggestion. Fix unclear instructions and restart the
  affected dry-run tasks before counting main-pilot data.
- **Main pilot:** any privacy breach, unauthorized action, or unsafe actionable
  suggestion pauses enrollment and triggers review. If My Guy has fewer correct
  initial routes than the native arm on the paired tasks, or any actionable
  My Guy recommendation lacks inspectable source evidence, revise the product
  and repeat the pilot before expanding. If no stop event occurs and both route
  and evidence gates pass, proceed only to a larger, pre-registered evaluation;
  do not claim superiority from this pilot.

Publish aggregate results for **all consenting** participants and tasks, including
wins, misses, clarifications, no-capability cases, exclusions, and withdrawal counts,
deviations, setup burden, and unavailable measurements. Report per-arm counts
and distributions as well as paired differences; task completion remains a
secondary outcome. State the small sample, self-selected participants, task
mix, possible order effects, and lack of blinded scoring. Do not advertise a
`10x` gain or any general superiority claim from these data.
