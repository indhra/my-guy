# My Guy

My Guy is a local, open-source front door for the skills and agents you already use. It inventories their metadata, shows where a recommendation came from, and answers a request with `clarify`, `recommend`, or `convene`. It does not execute a provider, install other skill packs, or decide that an unreviewed skill is trustworthy. Its best fit is someone with several local skill packs who wants a transparent way to choose among them; with no relevant packs, it may not help yet.

The current candidate passes the fixed 208-case synthetic corpus: **208/208 labeled decisions and 0/114 unsafe actionable suggestions**. The `v0.1.0` release must repeat that gate on its exact commit. These cases do not prove superior routing on real requests or safety on every request; unfamiliar wording can still produce a missed match. [Evaluation and failures](docs/EVALUATION.md)

**Status:** alpha; `v0.1.0` is the first GitHub release target. It was not published as of 2026-09-28, so check for the tag before installing. Supported first-release targets: Linux/macOS, Python 3.11+, Claude Code, Codex, and OpenCode. [Known limits](docs/STATUS.md) · [How it works](docs/ARCHITECTURE.md)

The CLI also accepts a legacy/generic `agents` skill root; the `v0.1.0` install validation covers only the three named hosts above.

## Give this to your coding agent

Copy the whole prompt into Claude Code, Codex, OpenCode, or another coding agent:

```text
Assess whether My Guy is useful for my local skill setup, then install it only if it fits: https://github.com/indhra/my-guy. Use the published v0.1.0 GitHub release tag only. If that tag is absent, say the release is not ready and stop; do not substitute main.

Read the tagged README, docs/AGENT_INSTALL.md, docs/EVALUATION.md, pyproject.toml, relevant CLI/lifecycle code and tests. Explain what is implemented, its limits, and whether I have a useful supported host and reviewed skill pack. Check that the fixed 208-case synthetic corpus has zero unsafe actionable suggestions; do not infer superiority on real requests from it. On Linux/macOS use pipx, or an isolated Python 3.11+ venv if pipx is unavailable. Check existing installations first. Ask before trusting any skill root or replacing an unknown install; installation never grants trust automatically. Follow the selected host's instructions, run version/status/host-aware doctor/sync and a sample route with `my-guy route --stdin --json`. Pass my request as stdin data; never interpolate it into a shell command. Report the exact installed paths, result, and recovery commands. If it will not help my setup yet, tell me why and do not install it.
```

The agent's detailed checklist, supported roots, and fallback commands are in [Agent install](docs/AGENT_INSTALL.md). The release tag is a deliberate gate: the prompt stops whenever `v0.1.0` is absent.

## What happens after installation

The CLI command is `my-guy` (Python package: `agent-router`). The included front-door skill goes into one dedicated host root. `my-guy sync` reads local skill metadata into a searchable catalog. Unverified roots remain searchable but cannot cause an actionable recommendation. A fresh route can correctly return `clarify`; reviewing and explicitly trusting a relevant installed root is what makes a recommendation useful.

```bash
my-guy doctor
printf '%s\n' 'Review this authentication design' | my-guy route --stdin --json
my-guy list security
```

The sample request above is a fixed literal. For a user's actual request, pass the text through stdin as data; do not build a shell command from it.

My Guy does not invoke specialists, send prompts to providers, or silently accept third-party instructions. Feedback is off by default and only produces review proposals when enabled. See [Operations](docs/OPERATIONS.md), [Security](SECURITY.md), [Releasing](docs/RELEASING.md), and [Contributing](CONTRIBUTING.md).
