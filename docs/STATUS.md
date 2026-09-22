# Agent Router Status

Updated: 2026-09-22
Branch: `work/router-foundation`

## Delivered

- Harness-neutral capability model, checked-in registry, and SQLite telephone directory.
- Read-only, bounded `SKILL.md` discovery with multiline metadata support, stable namespaces, collision protection, and unverified-by-default roots.
- Transparent routing with `clarify`, `recommend`, and `convene` outcomes.
- Trust filtering, confidence gates, quorum synthesis, visible failures, and preserved dissent.
- Exact execution binding, adapter allowlists, and structured Codex, Claude, OpenCode, and OpenRouter handoffs.
- `my-guy` CLI and portable front-door skill.
- Reversible install, upgrade, disable, and rollback for local skill hosts.
- Opt-in, raw-request-free feedback ledger producing review-only proposals.
- Packaging metadata, MIT license, CI matrix, architecture and operations documentation.
- Adversarial coverage for malicious metadata, forged/replayed approval, shadowing, symlink targets, and privacy defaults.

## Evidence

- Current local suite: `58 passed`.
- Live clean-install CLI smoke returns `clarify` for an unverified seed; an explicitly trusted installed security skill returns `recommend`.
- Provider adapters do not start subprocesses or perform network calls.

## Honest limits before a stable release

- No real provider execution or identity verification.
- No universal one-click installation because each host owns a different skill root and OpenRouter is not a skill host.
- No embedding backend; semantic interface labels itself `lexical-fallback`.
- No production telemetry backend or fleet administration.
- Visual design review is not applicable: this repository has no rendered UI.
- Alpha until independent end-to-end, architecture, and security reviews close all high-severity findings.

## Next release gates

1. Open a pull request when a remote and target branch are available.
2. Keep provider execution disabled until identity, authenticated approval, rate limits, and provider-specific authorization tests exist.
3. Run a full screenshot-based GStack design review only if a rendered UI is introduced.
