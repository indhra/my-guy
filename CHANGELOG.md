# Changelog

The [GitHub Releases](https://github.com/indhra/my-guy/releases) page is the publication record. This dated candidate entry describes planned release contents; it does not confirm a tag or downloadable release.

## v0.1.0 release candidate — 2026-09-29

- Added the `my-guy` CLI (`agent-router` Python package) for source-aware, harness-neutral routing to `clarify`, `recommend`, or `convene` using local skill metadata.
- Added explicit trust filtering, reversible front-door skill lifecycle, read-only status and doctor checks, and opt-in feedback that does not store raw requests.
- Prepared first-release installation for Linux and macOS with Python 3.11+ and dedicated Claude Code, Codex, and OpenCode skill roots. The CLI also accepts a generic `agents` root, which is outside first-release host validation.
- The candidate passed the fixed synthetic 208-case routing gate with 0/114 unsafe actionable suggestions. This does not measure real-world superiority or rule out missed matches.
- Known alpha limits: no automatic trust, third-party skill-pack installation, provider execution, Windows support, or PyPI release. Release notes must identify the exact tested `main` commit, supported scope, installation evidence, checksums, and remaining limits after approval.
