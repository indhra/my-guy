# My Guy / Agent Router

One memorable front door for installed skills and agents. It turns a vague request into an evidence-backed `clarify`, `recommend`, or `convene` decision without silently invoking anything.

> Status: alpha. The core, CLI, discovery, lifecycle, trust controls, and opt-in feedback loop are tested. Provider execution and a universal one-click installer are intentionally not claimed.

## Why it exists

Skill collections such as ECC, GStack, and other agent packs each know their own capabilities. My Guy builds a local telephone directory above them, preserves provenance, and routes to relevant specialists. It is a coordinator, not a replacement specialist.

## Install and use

Python 3.11+ is required.

```bash
python -m pip install .
my-guy "Review this authentication design for security and privacy"
my-guy route --json -- "I have a vague product idea"
my-guy list security
my-guy sync
my-guy doctor
```

For an isolated global CLI, install the checked-out project with `pipx install .`.

## Portable front-door skill

Install the included `my-guy` skill into a harness root you explicitly choose:

```bash
my-guy install codex --root ~/.codex/skills
my-guy install claude --root ~/.claude/skills
my-guy install opencode --root ~/.config/opencode/skills
```

Lifecycle operations are reversible and scoped to the exact root:

```bash
my-guy upgrade codex --root ~/.codex/skills
my-guy disable codex --root ~/.codex/skills
my-guy rollback codex --root ~/.codex/skills
```

OpenRouter is an API/model gateway, not a local skill host. Its adapter renders a structured handoff but does not pretend to install a skill or make a network call.

## Directory and trust

Common skill roots are discovered as `unverified`. That makes entries searchable but prevents actionable routing. Trust a root only after reviewing its provenance:

```bash
my-guy config --add-root team-skills /absolute/path/to/skills local
```

Duplicate names receive stable source-derived IDs, so one package cannot silently shadow another. Invalid or oversized third-party metadata is isolated rather than executed.

## Privacy-preserving evolution

Feedback is off by default. Opting in stores a per-installation keyed request fingerprint, capability ID, outcome, and optional short correction. Raw requests are not stored. The system produces review proposals only; it never rewrites policy or installs capabilities autonomously.

```bash
my-guy config --feedback on
my-guy feedback security-review accepted -- "Review authentication security"
my-guy proposals --minimum-samples 5
```

## Safety boundaries

- Discovery reads `SKILL.md` metadata only; it never executes skill bodies.
- Unverified entries cannot produce actionable routes.
- Adapters render handoffs and enforce invocation allowlists; they do not spawn subprocesses or call networks.
- Approval bindings prevent accidental substitution inside the trusted process. They are not authentication against malicious code in that process.
- Consensus requires two available specialist responses; dissent and failures remain visible.

See [architecture](docs/ARCHITECTURE.md), [operations](docs/OPERATIONS.md), and [status](docs/STATUS.md).
