# Releasing My Guy

Before publishing the first tag, merge the tagged-install validation PR. After
the annotated `v0.1.0` tag exists, manually dispatch **Tagged install validation**
on `main` with `expected_sha` set to the exact 40-character `main` commit SHA.
The workflow fails unless the dispatch commit and the annotated tag both match
that SHA. It installs `git+https://github.com/indhra/my-guy.git@v0.1.0` from
the URL via pipx and venv on Ubuntu and macOS (Python 3.11), verifies package
provenance and runs disposable Claude/Codex/OpenCode CLI lifecycles. It does not
prove native host application recognition or independent agent usefulness.

The first release channel is GitHub Releases. The Python distribution is named `agent-router`; the command is `my-guy`. Release publication, repository settings, and tags require separate human approval. No workflow publishes automatically.

Before tagging, the maintainer should confirm that `main` requires a reviewed PR and passing CI, release tags cannot be moved casually, private vulnerability reporting works, and Dependabot alerts, CodeQL, secret scanning, and push protection have been reviewed in GitHub settings. Repository-setting changes are separate approved actions; this document does not make them happen.

## Candidate gate

1. Merge the reviewed feature branch through a PR. Check that required Linux/macOS CI jobs pass on the exact `main` commit. Check live GitHub `main` and local `main` hashes match before building.
2. Verify `pyproject.toml` reports `0.1.0`, the proposed tag is `v0.1.0`, and neither a tag nor a GitHub Release with that name already exists. Update dated status and changelog text with release facts in this candidate commit. If the tag or release already exists, stop; never move a public tag.
3. Review [status](STATUS.md), the agent install prompt, the package contents, open security issues, and any unsupported claims. Run the published fixed 208-case synthetic corpus from [routing evaluation](EVALUATION.md) and require **208/208 labeled decisions and 0/114 unsafe actionable suggestions** with independently reviewed labels. A failing case blocks v0.1.0; do not weaken labels or redefine the metric to pass. This finite corpus does not prove safety or superiority on real requests and cannot rule out false negatives. Confirm GitHub private vulnerability reporting is enabled so the link in `SECURITY.md` works for external reporters. The code remains recommendation-only and never grants trust automatically.
4. Build a wheel and source distribution from the exact candidate commit. Run the full tests and `bash scripts/smoke_install.sh dist/*.whl` and `bash scripts/smoke_install.sh dist/*.tar.gz`. The smoke helper installs into an isolated temporary environment and runs the packaged `my-guy` command outside the source checkout for all three host roots.
5. Run an independent URL-only agent trial for Claude Code, Codex, and OpenCode. Confirm each agent can assess usefulness, find the tagged instructions, detect a missing pack, request approval before trusting a root or replacing an unknown install, install the correct host skill, and report rollback. Record real Linux and macOS evidence. A missing `v0.1.0` tag must result in a clear stop.

## Publish after approval

1. Obtain explicit approval for the exact commit SHA, release notes, and public tag. Create an annotated `v0.1.0` tag pointing to that `main` SHA. Recheck the remote tag points to the same commit. Never rewrite or force-push a published tag.
2. Build or retrieve the tested wheel and source distribution for that commit. Confirm the release directory contains exactly the intended `0.1.0` wheel and source distribution, with no stale files. Generate SHA-256 checksums for those exact artifacts, verify them, and attach wheel, source distribution, and checksums to a human-reviewed GitHub Release. Record the tag, commit SHA, Python versions, supported OS/hosts, and known limits in the notes.
3. From fresh Linux and macOS environments, run the pinned `pipx` install and isolated-venv fallback in [agent install](AGENT_INSTALL.md). Confirm `my-guy --version`, host status, doctor, and an expected `clarify` route without trusted skills. Check a reviewed trusted root produces useful evidence only after explicit approval.
4. Publish or announce the release only after the package and release assets pass those checks. Keep the GitHub Release and README aligned with the tested tag.

On Linux, `sha256sum dist/* > SHA256SUMS` creates a checksums file; on macOS use `shasum -a 256 dist/* > SHA256SUMS`. Run the relevant verification command before uploading. Checksums detect accidental mismatch; they are not a substitute for protecting the release account and tag.

## Bad release and subsequent versions

Do not delete or repoint a public tag. Post an advisory or clear release note describing the affected version, publish a corrected patch release from a reviewed commit, and update the recommended pinned tag after the patch is verified. Users can restore an earlier known-good CLI version via `pipx` or their virtual environment. If the first release has no earlier good tag, guide users to remove the CLI and its owned host skill until the patch is ready. Skill rollback is separate and uses `my-guy rollback <host> --root <same-root>` when a snapshot exists. Keep the support window and deprecations explicit in release notes. PyPI, Trusted Publishing/OIDC, Windows, provider execution, and SBOM/provenance automation are future decisions, not prerequisites for this first GitHub release.
