# Agent Router Status

Updated: 2026-09-25
Branch: `work/agent-inventory-routing`

## Delivered

- Harness-neutral capability records, checked-in seed registry, and SQLite catalog.
- Bounded, read-only inventory of skill metadata and static agent definitions for Codex, Claude Code, and OpenCode.
- Static discovery of supported enabled Codex and Claude Code plugin installs; OpenCode agent definitions are read from files and JSON/JSONC configuration.
- Per-capability host and kind metadata, trust filtering, cross-host matching, and prepared handoffs that require a separate approval before any execution.
- Transparent `clarify`, `recommend`, and `convene` decisions, evidence reporting, and stale catalog reconciliation.
- Typed Codex, Claude Code, OpenCode, and OpenRouter handoff adapters. They do not start providers or run specialist instructions.
- Reversible front-door skill lifecycle, opt-in review-only feedback, and adversarial coverage for metadata, trust, approval, and path boundaries.

## Verification

- Local suite: **81 passed**.
- CLI smoke: an explicitly trusted, host-scoped agent can be inventoried and recommended for a matching request.
- Inventory and adapter fixtures cover standard host roots, active-plugin filtering, metadata limits, catalog migration, and prepared cross-host output.
- No provider subprocesses or network calls are made by adapters.

## Limits

- Inventory is static and bounded; it is not a universal or complete view of runtime capabilities.
- OpenCode plugins can register or transform agents and other capabilities at runtime. Those results are not visible to this filesystem scanner and are out of scope ([OpenCode plugin documentation](https://opencode.ai/v2/docs/build/plugins)).
- Discovery treats metadata and instructions as untrusted data. New and discovered roots default to `unverified`; an operator may explicitly register a reviewed root as `local`.
- Handoffs are prepared records only. Provider execution, provider identity verification, authenticated approval, and durable remote audit are not implemented.
- Retrieval uses the transparent lexical baseline; there is no embedding backend or production telemetry service.

## Next release gates

1. Complete independent architecture and security review; resolve high-severity findings.
2. Keep provider execution disabled until provider identity, authenticated approval, rate limits, and authorization tests exist.
3. Run the supported Python-version and package-build matrix on the release candidate.
4. Record hosted CI and review state before tagging; do not auto-merge or auto-publish.
