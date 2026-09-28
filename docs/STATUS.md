# Project status

Updated: 2026-09-28. The first public GitHub release, `v0.1.0`, is being prepared; it is not published yet. The last verified public `main` baseline for this work is commit `54c951b`.

## Implemented on the pre-release baseline

- Harness-neutral capability model, bounded local `SKILL.md` metadata discovery, SQLite catalog, and source-aware routing to `clarify`, `recommend`, or `convene`.
- Explicit trust filtering, collision and stale-entry handling, confidence gates, preserved dissent, and adapter allowlists.
- Structured handoffs for Codex, Claude Code, OpenCode, and OpenRouter. They do not invoke a provider or make a model/network call.
- `my-guy` CLI and a bundled front-door skill with reversible host install, upgrade, disable, and rollback.
- Opt-in feedback ledger that does not store raw requests and only proposes reviewed changes.

The earlier local alpha review recorded 58 passing tests and closed its critical/high findings. The current candidate passed 200 local tests and its fixed 208-case synthetic routing corpus scored 208/208 labeled decisions with 0/114 unsafe actionable suggestions. These are local results; the exact release commit still needs CI and install acceptance.

## Release acceptance still required

- Agent-facing instructions and CLI output must agree on install, ownership, status, readiness, trust, and recovery behavior.
- Build and test both distribution formats on Python 3.11–3.13 for Linux and macOS; run the packaged CLI outside the source checkout.
- Complete URL-only agent trials for Claude Code, Codex, and OpenCode, including the no-useful-pack and missing-tag paths.
- Repeat the zero-unsafe-actionable gate on the published fixed 208-case synthetic corpus for the exact release commit. [Evaluation](EVALUATION.md) records the earlier failures and fixes; passing this bounded gate does not establish better routing on real requests or rule out missed matches.
- Review exact `main` commit, `v0.1.0` tag, release artifacts, SHA-256 checksums, and GitHub Release separately before publishing.

## Honest limits

My Guy recommends; it does not execute a provider or authenticate another process. Fresh seed entries and discovered roots are unverified, so a first route can correctly say `clarify`. It does not install third-party skill packs or silently trust them. The CLI accepts a legacy/generic `agents` harness, but first-release host validation covers Claude Code, Codex, and OpenCode only. There is no Windows support claim for the first release, no PyPI distribution, no embedding backend, and no production fleet telemetry. Security and provider execution need separate designs and approval before they can be claimed.
