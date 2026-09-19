# Agent Router Status

Updated: 2026-09-20
Branch: `work/router-foundation`

## Completed

- Researched and verified upstream GStack, Matt Pocock skills, and ECC.
- Confirmed their routers are bounded to their own ecosystems.
- Created a standalone project with branch and Git history.
- Defined the harness-neutral router goal and approval boundary.
- Added a transparent `Capability` model.
- Added a checked-in seed registry for security, UI, and research capabilities.
- Added read-only `SKILL.md` discovery with source provenance.
- Added a SQLite-backed telephone directory (`CapabilityCatalog`).
- Added `recommend`, `clarify`, and `convene` routing outcomes.
- Added tests for clear routing, ambiguity, discovery, catalog search, and the
  no-implicit-limit rule.
- Current validation: `9 passed` with `python3 -m pytest -p no:cacheprovider -q`.

## Current verdict

Working prototype, not production-ready. The code is transparent and locally
tested, but it does not yet invoke specialists, perform semantic retrieval,
verify external skills, or expose Codex/Claude/OpenCode/OpenRouter adapters.

## Review findings (2026-09-20)

Security review: **OPEN_THREATS**. Do not ship an execution adapter yet.

- Invocation metadata is currently unconstrained and only displayed as text.
- Discovered skill metadata is untrusted but still routable.
- Registry trust values are not yet loaded or enforced.
- Catalog search does not filter or rank by trust/provenance.
- `approval_required` is a declaration, not an enforced gate.

Code review also found: route evidence omits source, weak matches do not
clarify, trust is discarded while loading JSON, duplicate IDs overwrite,
negative limits are accepted, substring ranking is noisy, one unreadable skill
can abort discovery, and caller-supplied trigger case is not normalized.

These are queued as the next hardening cycle.

Positive controls: routing performs no tool calls, discovery reads metadata
only, SQL writes use parameters, and approval defaults to true.

## Review queue

- Code-quality review.
- Security and trust-boundary review.
- Fix any high-severity findings before adding breadth.

## Next queue

1. Trust hardening and review fixes.
2. Routing evaluation and confidence calibration.
3. Automatic discovery synchronization and stale-entry handling.
4. Optional semantic-search backend.
5. Bounded convene-mode synthesis.
6. Adapter-neutral approval protocol.
7. Codex, Claude, OpenCode, OpenRouter, and project adapters.
8. Adversarial review, release, install, upgrade, disable, and rollback tests.

## Non-goals still in force

- Do not replace specialist skills.
- Do not execute edits or external actions without approval.
- Do not claim consensus when a specialist was not consulted.
- Do not make provider-specific behavior part of the core contract.

Evolution is a later phase: opt-in feedback, reviewed recalibration, versioned
changes, and no autonomous policy or capability installation.
