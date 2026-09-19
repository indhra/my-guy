# Agent Router Plan

## Goal

Provide one memorable front door that clarifies intent, discovers relevant
capabilities, routes to one or more specialists, synthesizes disagreement, and
asks for approval before execution.

## End-to-end phases

1. **Foundation and evidence** — research existing routers and record sources.
   Done. This prevents reinventing an existing workflow.
2. **Transparent core** — capability model, seed registry, read-only advisor,
   and SQLite catalog. Done. This gives us a testable baseline before any
   automation.
3. **Trust hardening** — validate provenance, trust levels, invocation
   references, collisions, limits, normalization, and unreadable files.
   Required before routing can influence execution.
4. **Routing evaluation** — expand fixtures for clear, ambiguous, adversarial,
   cross-domain, and no-match requests. Add confidence calibration and source
   evidence. This measures whether routing is correct rather than plausible.
5. **Discovery and synchronization** — ingest local and installed skills,
   agents, `AGENTS.md`, and supported manifests with stale-entry detection.
   This makes the directory stay current after installation.
6. **Retrieval backends** — keep SQLite lexical search as the baseline, then
   add an optional semantic backend with identical result/evidence contracts.
   This improves recall without making embeddings mandatory.
7. **Convene mode** — bounded specialist fan-out, preserved disagreement,
   timeout/failure handling, and explicit synthesis. No fake consensus.
   Pure synthesis contract is now implemented; adapter fan-out remains later.
8. **Approval and execution boundary** — implement an adapter-neutral approval
   protocol. Only adapters may invoke tools, and only after approval.
   Core allowlisting and matching approval tokens are now implemented.
9. **Harness adapters** — Codex, Claude, OpenCode, OpenRouter, and project
   instruction surfaces. Each adapter runs the same fixtures and remains thin.
10. **Adversarial review and release** — prompt-injection tests, architecture
    review, security review, install/rollback tests, documentation, and a
    versioned release.

## Non-goals

- Replacing specialist skills.
- Automatically executing edits or external actions.
- Claiming consensus when only one specialist responded.
- Making provider-specific behavior part of the core contract.

## Acceptance gates

- Every route cites the matched capability and source.
- Low-confidence or conflicting routes ask a clarifying question.
- Execution always stops at an explicit approval gate.
- The same fixtures pass through every adapter.

## Definition of done

- A user can invoke one front door from each supported harness.
- The router can clarify, recommend, or convene with cited evidence.
- The catalog reflects installed capabilities and marks stale/untrusted ones.
- No specialist or tool is invoked without the approval protocol.
- All adapters pass the shared routing and adversarial fixture suite.
- Installation, upgrade, disable, and rollback are documented and tested.

## Directory contract

Each entry has a stable name, source, description, trigger vocabulary,
invocation reference, and trust level. Search has no hidden top-N cutoff;
callers choose a limit when they want one. The first backend is SQLite with
transparent lexical scoring. Future semantic search must return the same entry
shape plus evidence for its ranking.

## Measured evolution

Collect opt-in route outcomes, user corrections, specialist usefulness,
disagreement, and failure reasons. Recalibrate thresholds and registry
metadata through reviewed, versioned, reversible changes. The router must not
rewrite its own policy or install capabilities autonomously.
