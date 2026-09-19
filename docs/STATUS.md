# Agent Router Status

Updated: 2026-09-20
Branch: `work/router-foundation`

## Completed

- Researched and verified upstream GStack, Matt Pocock skills, and ECC.
- Confirmed their routers are bounded to their own ecosystems.
- Created a standalone project with branch and Git history.
- Defined the harness-neutral router goal and approval boundary.
- Added a transparent `Capability` model and checked-in seed registry.
- Added read-only `SKILL.md` discovery with source provenance.
- Added a SQLite-backed telephone directory (`CapabilityCatalog`).
- Added `recommend`, `clarify`, and `convene` routing outcomes.
- Added trust filtering, collision checks, exact token matching, confidence
  gating, and an approval helper.
- Added reusable routing evaluation cases with per-case accuracy and
  confidence bounds.

## Review result

- Initial code review findings were fixed through the hardening cycle.
- Security review closed unverified influence at the core route boundary.
- Final focused test run: `16 passed`.
- Bytecode compilation was attempted, but this environment disallows writing
  `__pycache__`; that is an environment limitation, not a test failure.

## Current verdict

Working prototype, not production-ready. It does not yet invoke specialists,
perform semantic retrieval, synchronize installed capabilities, or expose
Codex, Claude, OpenCode, or OpenRouter adapters.

No execution adapter should be added until adapter-level approval tests exist.

## Next queue

1. Automatic discovery synchronization and stale-entry handling.
3. Optional semantic-search backend.
4. Bounded convene-mode synthesis with preserved disagreement.
5. Adapter-neutral approval protocol and execution boundary.
6. Codex, Claude, OpenCode, OpenRouter, and project adapters.
7. Adversarial review, release, install, upgrade, disable, and rollback tests.

## Measured evolution

Later phases will collect opt-in route outcomes, user corrections, specialist
usefulness, disagreement, and failure reasons. Changes to thresholds and
registry metadata will be reviewed, versioned, and reversible. The router will
not rewrite its own policy or install capabilities autonomously.

## Non-goals

- Do not replace specialist skills.
- Do not execute edits or external actions without approval.
- Do not claim consensus when a specialist was not consulted.
- Do not make provider-specific behavior part of the core contract.

## Latest cycle

- Added routing evaluation with 16 baseline cases passing before sync work.
- Added synchronization that marks missing capabilities stale without deleting
  them.
- Current focused test count: `17 passed`.

- Added a dependency-free semantic-search interface with lexical fallback,
  ranking evidence, and an explicit backend label.
- Current focused test count after semantic search: `19 passed`.
