# Project status

Updated: 2026-09-30. [`v0.1.0`](https://github.com/indhra/my-guy/releases/tag/v0.1.0) is a published alpha prerelease from commit `c6edf09de6a9fcd6df80ae7116f0735a5ecb0d7f`. The GitHub Release is the publication record; the dated PR evidence below remains historical.

## Implemented in v0.1.0

- Harness-neutral capability model, bounded local `SKILL.md` metadata discovery, SQLite catalog, and source-aware routing to `clarify`, `recommend`, or `convene`.
- Explicit trust filtering, collision and stale-entry handling, confidence gates, preserved dissent, and adapter allowlists.
- Structured handoffs for Codex, Claude Code, OpenCode, and OpenRouter. They do not invoke a provider or make a model/network call.
- `my-guy` CLI with a bundled front-door skill and reversible host install, upgrade, disable, and rollback.
- Opt-in feedback ledger that does not store raw requests and only proposes reviewed changes.

An earlier local alpha review recorded 58 passing tests and closed its critical/high findings. The candidate passed 200 local tests. The fixed 208-case synthetic routing corpus scored 208/208 labeled decisions with 0/114 unsafe actionable suggestions. This bounded result does not establish safety or better routing on real requests.

## Candidate evidence recorded on 2026-09-29

- PR [#1](https://github.com/indhra/my-guy/pull/1) commit [`354a5d8`](https://github.com/indhra/my-guy/commit/354a5d8cd6843e45b1d099f488725d2e985cc46b) passed all six Linux/macOS × Python 3.11–3.13 jobs in both [push CI](https://github.com/indhra/my-guy/actions/runs/36530074467) and [PR CI](https://github.com/indhra/my-guy/actions/runs/36530077813). Each job built a wheel and source distribution and passed installed-artifact smoke checks outside the checkout.
- A fresh Linux virtual environment installed the GitHub URL pinned to that commit and reported `my-guy 0.1.0`. A disposable Codex host install reached `ready`; without an approved trusted skill root, doctor correctly reported `needs_capabilities` and the example route returned `clarify`. This is commit-pinned evidence, not a tagged-release or `pipx` trial.
- These checks covered the PR candidate. They were separate from the later tagged release validation.

## Published release evidence

- The annotated `v0.1.0` tag resolves to `c6edf09de6a9fcd6df80ae7116f0735a5ecb0d7f`. The alpha prerelease provides `agent_router-0.1.0-py3-none-any.whl`, `agent_router-0.1.0.tar.gz`, and `SHA256SUMS`.
- [CI](https://github.com/indhra/my-guy/actions/runs/36555263444) passed on the release commit. The [tagged install validation](https://github.com/indhra/my-guy/actions/runs/36566743690) passed tagged URL install and disposable CLI lifecycle checks on Ubuntu and macOS with Python 3.11.
- These CLI checks do not establish native Claude Code, Codex, or OpenCode application recognition, independent agent usefulness, or superior routing on real requests. URL-only agent trials and a consent-based pilot remain future evidence. [Evaluation](EVALUATION.md) records earlier failures and fixes; passing its synthetic gate cannot rule out missed matches.

## Honest limits

My Guy recommends; it does not execute providers or authenticate another process. Fresh seed entries and discovered roots are unverified, so the first route can correctly say `clarify`. It does not install third-party skill packs or silently trust them. The CLI accepts the legacy/generic `agents` harness, but first-release host validation covers Claude Code, Codex, and OpenCode only. There is no Windows support claim for the first release, no PyPI distribution, no embedding backend, and no production fleet telemetry. Security and provider execution need separate designs and approval before they can be claimed.
