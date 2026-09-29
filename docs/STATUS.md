# Project status

Updated: 2026-09-29. This is a dated `v0.1.0` release-candidate snapshot. Check [GitHub Releases](https://github.com/indhra/my-guy/releases) and the `v0.1.0` tag for public availability and the exact release commit; this document is not a publication record. Evidence below comes from the feature branch, not a tagged release.

## Implemented on the release candidate

- Harness-neutral capability model, bounded local `SKILL.md` metadata discovery, SQLite catalog, and source-aware routing to `clarify`, `recommend`, or `convene`.
- Explicit trust filtering, collision and stale-entry handling, confidence gates, preserved dissent, and adapter allowlists.
- Structured handoffs for Codex, Claude Code, OpenCode, and OpenRouter. They do not invoke a provider or make a model/network call.
- `my-guy` CLI with a bundled front-door skill and reversible host install, upgrade, disable, and rollback.
- Opt-in feedback ledger that does not store raw requests and only proposes reviewed changes.

An earlier local alpha review recorded 58 passing tests and closed its critical/high findings. The candidate passed 200 local tests. Its fixed 208-case synthetic routing corpus scored 208/208 labeled decisions with 0/114 unsafe actionable suggestions. This bounded result does not establish safety or better routing on real requests.

## Candidate evidence recorded on 2026-09-29

- PR [#1](https://github.com/indhra/my-guy/pull/1) commit [`354a5d8`](https://github.com/indhra/my-guy/commit/354a5d8cd6843e45b1d099f488725d2e985cc46b) passed all six Linux/macOS × Python 3.11–3.13 jobs in both [push CI](https://github.com/indhra/my-guy/actions/runs/36530074467) and [PR CI](https://github.com/indhra/my-guy/actions/runs/36530077813). Each job built a wheel and source distribution and passed installed-artifact smoke checks outside the checkout.
- A fresh Linux virtual environment installed the GitHub URL pinned to that commit and reported `my-guy 0.1.0`. A disposable Codex host install reached `ready`; without an approved trusted skill root, doctor correctly reported `needs_capabilities` and the example route returned `clarify`. This is commit-pinned evidence, not a tagged-release or `pipx` trial.
- These checks cover the PR candidate. Release acceptance applies independently to the exact `main` commit after the reviewed PR is merged.

## Release acceptance conditions

- A reviewed PR must be merged, and the exact `main` commit must pass required Linux/macOS CI, the fixed 208-case routing gate, and installed wheel/source-distribution checks. PR-branch results above do not establish this release-commit gate.
- Agent-facing instructions and CLI output must agree on install, ownership, status, readiness, trust, and recovery behavior.
- URL-only agent trials must cover Claude Code, Codex, and OpenCode, including no-useful-pack and missing-tag paths.
- The exact `main` commit, annotated `v0.1.0` tag, release artifacts, SHA-256 checksums, and GitHub Release require separate review before publication. Tag and release publication require explicit approval. [Evaluation](EVALUATION.md) records earlier failures and fixes; passing its synthetic gate cannot rule out missed matches.

## Honest limits

My Guy recommends; it does not execute providers or authenticate another process. Fresh seed entries and discovered roots are unverified, so the first route can correctly say `clarify`. It does not install third-party skill packs or silently trust them. The CLI accepts the legacy/generic `agents` harness, but first-release host validation covers Claude Code, Codex, and OpenCode only. There is no Windows support claim for the first release, no PyPI distribution, no embedding backend, and no production fleet telemetry. Security and provider execution need separate designs and approval before they can be claimed.
