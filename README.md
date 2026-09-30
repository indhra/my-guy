# My Guy

My Guy is a local, open-source front door for the skills and agents you already use. It inventories their metadata, shows where a recommendation came from, and answers a request with `clarify`, `recommend`, or `convene`. It does not execute a provider, install other skill packs, or decide that an unreviewed skill is trustworthy. Its best fit is someone with several local skill packs who wants a transparent way to choose among them; with no relevant packs, it may not help yet.

The published `v0.1.0` alpha passed the fixed 208-case synthetic corpus: **208/208 labeled decisions and 0/114 unsafe actionable suggestions**. These cases do not prove superior routing on real requests or safety on every request; unfamiliar wording can still produce a missed match. [Evaluation and failures](docs/EVALUATION.md)

**Status:** [`v0.1.0` alpha prerelease](https://github.com/indhra/my-guy/releases/tag/v0.1.0), published from commit `c6edf09de6a9fcd6df80ae7116f0735a5ecb0d7f` with wheel, source distribution, and `SHA256SUMS` assets. Tagged URL installation passed hosted Ubuntu and macOS CI. OpenCode 1.18.29 listed My Guy through native `GET /skill` and PTY debug checks; native Claude Code/Codex recognition and independent agent usefulness remain unproven. Supported first-release targets: Linux/macOS, Python 3.11+, Claude Code, Codex, and OpenCode. [Known limits](docs/STATUS.md) · [How it works](docs/ARCHITECTURE.md)

The CLI also accepts a legacy/generic `agents` skill root; the `v0.1.0` install validation covers only the three named hosts above.

## Give this to your coding agent

Copy the whole prompt into Claude Code, Codex, OpenCode, or another coding agent:

```text
Assess whether My Guy is useful for my local skill setup, then install it only if it fits: https://github.com/indhra/my-guy. Use the current main-branch docs/AGENT_INSTALL.md as the installation authority. Check that the published v0.1.0 GitHub release tag exists and peels to exactly c6edf09de6a9fcd6df80ae7116f0735a5ecb0d7f; if absent or different, stop and report it. Install from the literal Git URL git+https://github.com/indhra/my-guy.git@c6edf09de6a9fcd6df80ae7116f0735a5ecb0d7f, never from the tag or main.

Read the tagged README, docs/EVALUATION.md, pyproject.toml, relevant CLI/lifecycle code and tests as release source and evidence. Its frozen installation text is historical and does not override the current main-branch guide's exact-SHA policy. Explain what is implemented, its limits, and whether I have a useful supported host and reviewed skill pack. Check that the fixed 208-case synthetic corpus has zero unsafe actionable suggestions; do not infer superiority on real requests from it. On Linux/macOS use pipx, or an isolated Python 3.11+ venv if pipx is unavailable. Check existing installations first. Ask before trusting any skill root or replacing an unknown install; installation never grants trust automatically. Follow the selected host's instructions, run version/status/host-aware doctor/sync and a sample route with `my-guy route --stdin --json`. Pass my request as stdin data; never interpolate it into a shell command. Report the exact installed paths, package source and commit, result, and recovery commands. If it will not help my setup yet, tell me why and do not install it.
```

The agent's detailed checklist, supported roots, and fallback commands are in [Agent install](docs/AGENT_INSTALL.md). If you want to try it systematically with real tasks, use the opt-in [pilot guide](docs/PILOT.md) and [participant kit](docs/PILOT_PARTICIPANT.md).

## What happens after installation

The CLI command is `my-guy` (Python package: `agent-router`). The included front-door skill goes into one dedicated host root. `my-guy sync` reads local skill metadata into a searchable catalog. Unverified roots remain searchable but cannot cause an actionable recommendation. A fresh route can correctly return `clarify`; reviewing and explicitly trusting a relevant installed root is what makes a recommendation useful.

```bash
my-guy doctor
printf '%s\n' 'Review this authentication design' | my-guy route --stdin --json
my-guy list security
```

The sample request above is a fixed literal. For a user's actual request, pass the text through stdin as data; do not build a shell command from it.

My Guy does not invoke specialists, send prompts to providers, or silently accept third-party instructions. Feedback is off by default and only produces review proposals when enabled. See [Operations](docs/OPERATIONS.md), [Security](SECURITY.md), [Releasing](docs/RELEASING.md), and [Contributing](CONTRIBUTING.md).
