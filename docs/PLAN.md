# Agent Router Plan

## Goal

Provide one front door that clarifies intent, discovers relevant skills and agents, routes one or more specialists, preserves disagreement, and stops at an explicit approval boundary.

## Delivered foundation

1. **Evidence and transparent core:** harness-neutral capability records, checked-in seed registry, SQLite catalog, lexical evidence, and `clarify` / `recommend` / `convene` decisions.
2. **Trust and synchronization:** bounded read-only discovery, stable identities, collision and symlink protections, trust filtering, stale-entry reconciliation, and opt-in review-only feedback.
3. **Host-aware static inventory:** Codex, Claude Code, and OpenCode skill and agent metadata, supported enabled Codex/Claude Code plugin installations, and explicit host-scoped custom roots.
4. **Prepared handoff:** requesting-host routing, cross-host match evidence, and structured handoff records that require separate operator approval. Codex, Claude Code, OpenCode, and OpenRouter adapters remain handoff renderers; they do not execute providers.
5. **Compatibility and evidence:** old catalog fields migrate with safe capability defaults; host, plugin-state, trust, routing, handoff, and migration fixtures are covered. Current local suite: **81 passed**.

## Remaining work

- Complete independent architecture and security review, and close high-severity findings before stable release.
- Improve routing evaluation and confidence calibration using reviewed fixtures and source evidence.
- Consider an optional semantic retrieval backend only if it preserves the same capability and evidence contract.
- Design real specialist/provider execution separately, with authenticated identity, authorization, rate limits, and an explicit approval protocol. Do not infer execution support from prepared handoffs.
- Add telemetry or fleet management only after privacy and deployment requirements are defined.

## Non-goals

- Replacing specialist skills or claiming a complete inventory of every runtime capability.
- Executing edits, tools, external actions, or provider requests as part of a route.
- Claiming consensus when only one specialist responds.
- Making provider-specific behavior part of the core routing contract.

## Acceptance gates

- Each actionable route exposes its source, trust, kind, and host scope.
- Unknown or unverified provenance cannot become an actionable route; unknown host scope cannot be sent through a host-restricted adapter.
- Low-confidence or ambiguous requests clarify; cross-host results are explicitly marked as prepared handoffs requiring operator approval.
- Inventory and routing fixtures cover supported host roots, active-plugin filtering, migrations, collisions, and adversarial metadata.
- Installation lifecycle, recovery, inventory limits, and known static-inventory gaps are documented.
