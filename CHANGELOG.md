# Changelog

The [GitHub Releases](https://github.com/indhra/my-guy/releases) page is the publication record. [`v0.1.0`](https://github.com/indhra/my-guy/releases/tag/v0.1.0) is a published alpha prerelease from commit `c6edf09de6a9fcd6df80ae7116f0735a5ecb0d7f`, with wheel, source distribution, and `SHA256SUMS` assets.

## v0.1.0 alpha prerelease — 2026-09-29

- Added the `my-guy` CLI (`agent-router` Python package) for source-aware, harness-neutral routing to `clarify`, `recommend`, or `convene` using local skill metadata.
- Added explicit trust filtering, reversible front-door skill lifecycle, read-only status and doctor checks, and opt-in feedback that does not store raw requests.
- Published first-release installation for Linux and macOS with Python 3.11+ and dedicated Claude Code, Codex, and OpenCode skill roots. Tagged URL installation passed hosted Ubuntu and macOS CI; this does not prove native host application recognition. The CLI also accepts a generic `agents` root, which is outside first-release host validation.
- The release commit passed the fixed synthetic 208-case routing gate with 0/114 unsafe actionable suggestions. This does not measure real-world superiority or rule out missed matches.
- Known alpha limits: no automatic trust, third-party skill-pack installation, provider execution, Windows support, or PyPI release. See the release notes for the tested commit, supported scope, installation evidence, checksums, and remaining limits.
