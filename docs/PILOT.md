# Opt-in alpha onboarding pilot

For copy-ready invitations, paired prompts, and a private worksheet, see the [participant kit](PILOT_PARTICIPANT.md).

This is a proposed, consent-based way to learn whether the published
[`v0.1.0` alpha](https://github.com/indhra/my-guy/releases/tag/v0.1.0) helps
people choose among skills they already use. OpenCode 1.18.29 listed My Guy
through native skill checks; native Claude Code/Codex recognition and real-world
usefulness remain unproven. This pilot has no results yet. Read the
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
   trusted-root decisions for both arms. Use the published `v0.1.0` tag and
   follow the [install guide's](AGENT_INSTALL.md) release check.
   Inspect existing installations and get approval before any replacement or
   trust change, as in the [install guide](AGENT_INSTALL.md).
2. For each task, use the identical request and relevant context in two fresh
   sessions. Randomize which arm runs first per task, and record that order.
   Avoid carrying suggestions, conversation history, or tool results from the
   first run into the second. Keep all **other** available skills equal.
3. Use isolated or disposable host roots for the two arms. In the **native**
   arm, remove or disable My Guy's front-door skill and hide its CLI from that
   session; verify the host skill listing and command path cannot find My Guy
   before the task. Compare the remaining skill inventory with the My Guy arm
   and resolve any difference before running. The native host then chooses its
   normal route without My Guy. In the **My Guy** arm, explicitly invoke My
   Guy's route before choosing the next step. The participant still decides
   whether to follow a recommendation and must approve any consequential
   action. No arm gets automatic skill trust.
4. Score the initial route against the acceptable route recorded before the
   outcomes. Then complete the task normally if appropriate. Record setup
   effort separately from task effort so installation time is visible and does
   not distort a single task's result.

Pair the route decision in both fresh sessions before any consequential action.
Measure route-phase time, steps, tool calls, and available tokens from request
submission to the first skill choice, clarification request, or no-capability
decision in each arm; mark an implicit native choice as such. Full task
completion and end-to-end effort can be paired only when both arms use
independent equivalent disposable copies. Otherwise complete the task once if
appropriate, mark the other arm's end-to-end result `N/A (unpaired)`, and
exclude it from paired end-to-end comparisons. Record deviations; do not
present changed tasks as clean comparisons.

## Scorecard

Record one row per task and arm, with a participant code and task code only:

| Field | Record |
| --- | --- |
| Before outcomes | Sanitized task category, acceptable route(s), reason for clarify/no-capability, pinned host/model/skills, arm order |
| Route quality and incidents | Correct selection; appropriate clarification; appropriate no-capability response; strict routing-evaluation unsafe actionable, pilot safety-stop suggestion, unauthorized action, and privacy breach as separate yes/no fields with sanitized reasons |
| Evidence | Whether the route gave usable source/evidence for its choice, and whether the participant could inspect it |
| Effort | Paired route-phase time, steps, tool calls, and available tokens; setup effort separately; end-to-end effort only for independently repeatable paired copies, otherwise `N/A (unpaired)` |
| Outcome | Task completion (secondary; paired only with independent copies), participant-observed friction, and protocol deviations |

Count each route result, including misses, abstentions, and tasks that lack an
available capability. Record setup time and steps once per participant and
host. Do not turn unavailable token or tool counts into zeros. A route is
correct only if it matches a pre-recorded acceptable route; a correct-looking
answer discovered after the run does not change that record. The strict
**routing-evaluation unsafe actionable** metric counts any actionable
`recommend` or `convene` result whose status or candidate differs from the
pre-recorded acceptable route, or that includes an unverified candidate; see
[routing evaluation](EVALUATION.md). Count it separately for each arm.

The narrower **pilot safety-stop suggestion** is actionable advice to use an
untrusted, unavailable, or explicitly excluded capability, or actionable advice
for a pre-labeled explicit no-route or informational-only request. A wrong but
trusted route is a routing error and counts in the strict metric; review it,
but do not automatically stop the pilot unless it also meets the safety-stop
definition. A suggestion does not prove that a skill ran. An **unauthorized
action** is an actual tool or state change without participant approval.
Adjudicate disputed cases against the pre-recorded route and local evidence;
report strict metric, safety-stop suggestions, and unauthorized actions as
separate per-arm counts. Faster runs never offset these outcomes.

## Privacy and stop rules

Do not collect raw prompts, code, transcripts, credentials, private file paths,
private skill names, or automatic telemetry. Participants keep raw work and
task-level scorecard rows locally. Collect only participant-computed aggregate
counts and timing summaries, plus sanitized comments they explicitly consent
to share. Review every public issue or example for secrets, personal
information, customer data, and identifying project details before submission.
Use private security reporting for vulnerabilities, as described in
[SECURITY.md](../SECURITY.md).

Stop the affected run immediately for a privacy breach, unauthorized action,
or pilot safety-stop suggestion. Preserve only a minimal sanitized incident
description, inform the participant, and pause further pilot work until the
cause and safe next step have been reviewed. Do not publish incident material
that could identify the participant or expose private work.

## Predeclared decision gate and reporting

Before the first dry-run task, freeze the scorecard, acceptable-route rubric,
arm-order method, and these decisions in a dated local copy:

- **Dry run:** proceed to the main pilot only if all three participants can
  complete the paired protocol without a privacy breach, unauthorized action,
  or pilot safety-stop suggestion. Fix unclear instructions and restart the
  affected dry-run tasks before counting main-pilot data.
- **Main pilot:** any privacy breach, unauthorized action, or pilot safety-stop
  suggestion pauses enrollment and triggers review. If My Guy has fewer correct
  initial routes than the native arm on the paired tasks, or any actionable
  My Guy recommendation lacks inspectable source evidence, revise the product
  and repeat the pilot before expanding. If no stop event occurs and both route
  and evidence gates pass, proceed only to a larger, pre-registered evaluation;
  do not claim superiority from this pilot.

Publish aggregate results for **all consenting** participants and tasks, including
wins, misses, clarifications, no-capability cases, exclusions, withdrawal counts,
deviations, setup burden, and unavailable measurements. Report per-arm counts
of strict unsafe actionable results, pilot safety-stop suggestions,
unauthorized actions, and privacy breaches separately, alongside route-phase
distributions and paired differences, and how many end-to-end results were
unpaired. Suppress public subgroup cells of fewer than five people; roll them
into broader totals. Publish only explicitly consented, sanitized quotes.
Task completion remains secondary. State the small sample, self-selected
participants, task mix, possible order effects, and lack of blinded scoring.
Do not advertise a `10x` gain or any general superiority claim from these data.

Offer an optional, consent-based check at one and four weeks: ask whether the
participant still uses My Guy, whether it helped with a real task, and what
friction remains. Record only aggregate responses and sanitized, consented
feedback; do not add telemetry or infer retention from nonresponse.
