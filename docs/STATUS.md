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

## Review queue

- Code-quality review.
- Security and trust-boundary review.
- Fix any high-severity findings before adding breadth.

## Next queue

1. Ingest discovered skills into the catalog automatically.
2. Add explicit trust/provenance validation and stale-entry handling.
3. Add semantic-search adapter behind the same catalog contract.
4. Add bounded convene-mode synthesis with disagreement preserved.
5. Add harness adapters and installation/rollback tests.
6. Add adversarial routing fixtures and approval-gate tests.

## Non-goals still in force

- Do not replace specialist skills.
- Do not execute edits or external actions without approval.
- Do not claim consensus when a specialist was not consulted.
- Do not make provider-specific behavior part of the core contract.
