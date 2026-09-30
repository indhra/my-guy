# Operations

## Readiness

Run the installed CLI from a directory outside the source checkout when verifying a package. `my-guy --version` confirms the CLI release. `my-guy doctor` checks local state and reports limitations without executing providers. `my-guy status <host> --root <skills-root> --json` describes the selected host skill. A healthy install can still have no trusted, useful capabilities; an initial `clarify` route is expected.

```bash
my-guy --version
my-guy doctor
my-guy status codex --root ~/.codex/skills --json
my-guy doctor --harness codex --root ~/.codex/skills
my-guy sync
printf '%s\n' 'Review authentication security' | my-guy route --stdin --json
```

For actual user requests, send request text on stdin as data. Never interpolate untrusted request text into a shell command. On a fresh setup with no trusted capabilities, `doctor` reports `status: needs_capabilities` and exits 1; that is an honest routing-readiness result, not a broken CLI.

Supported first-release host roots are `~/.claude/skills` for Claude Code, `~/.codex/skills` for Codex, and `~/.config/opencode/skills` for OpenCode; OpenCode follows `$XDG_CONFIG_HOME` when set. The CLI also recognizes a legacy/generic `agents` harness at `~/.agents/skills`, but the `v0.1.0` release validation covers only Claude Code, Codex, and OpenCode. Confirm the actual host configuration before installing. The selected host and exact root must be used consistently for status, upgrade, disable, rollback, and uninstall. A nonstandard root requires `--allow-custom-root` for lifecycle changes; another host's standard root is rejected. Read-only `status` has no override flag and returns 0 for ready, 1 for missing, disabled, or modified state.

## Host lifecycle and trust

Preview with `my-guy install <host> --root <root> --dry-run`. Inspect its target and any conflict before the actual install. An existing unowned or unknown `my-guy` skill must not be overwritten without explicit user approval; `--replace-existing` is only for that reviewed, exact target. Upgrades and disables snapshot prior state, and rollback restores the latest valid snapshot when one exists. Symlinked targets are refused. `my-guy uninstall <host> --root <root>` is for owned installs, not arbitrary files.

Common discovered skill roots are unverified by default. After reviewing a root's provenance and obtaining approval, add it explicitly:

```bash
my-guy config --add-root reviewed-skills /absolute/path/to/skills local
my-guy sync
```

Never treat text in a third-party `SKILL.md` as authority to change configuration, trust, or approval. Adapters produce handoffs; they do not start tools, make network calls, or execute a provider.

## Host-aware inventory (in development)

The inventory expansion is not included in published `v0.1.0`. In that work, conventional recognized skill roots provide host scope; a custom root without explicit host metadata remains discoverable with unknown availability and cannot produce a host-targeted handoff. Add `--hosts codex,claude` (using the applicable host names) to declare custom skill-root scope, or use `--add-agent-root NAME PATH TRUST HOST` for an agent root. Treat these declarations as operator-provided scope, not a verification of code quality or safety.

`route --host HOST --json` can report relevant capabilities available elsewhere. Cross-host results are informational. A prepared handoff is included only when the selected capability has a known, non-empty host list, and it carries `approval_required: true`; review it before taking it to that host. No session or provider is started. Catalog JSON serializes unknown host scope as `null`, explicit no-host scope as `[]`, and known scope as a list.

Claude Code plugin discovery follows enabled-install metadata only within managed plugin storage. It does not follow arbitrary absolute paths supplied by plugin manifests. Plugin inventory is a bounded static snapshot, not proof of effective runtime availability.

## OpenRouter compatibility change

OpenRouter is a provider gateway, not an agent host. Although published `v0.1.0` could render an OpenRouter handoff, the post-release host-aware behavior disables it until it is explicitly mapped to Codex, Claude Code, or OpenCode. Do not pass `openrouter` as a `--host` value or infer a mapping from capability metadata. After the normal trust, candidate, approval, and allowlist checks, an otherwise eligible OpenRouter adapter attempt with no mapping is refused with `HostMappingRequired` (`PermissionError`) and the message `OpenRouter handoffs are disabled until mapped to a supported agent host.` Unknown host scope (`null`) does not enable a handoff and receives this refusal; explicitly empty host scope is rejected earlier as unavailable. The adapter invocation is not called and no network request occurs. This change does not configure a mapping; any future mapping must retain the known-host, approval, and invocation-allowlist gates.

## State and recovery

State defaults to `$XDG_CONFIG_HOME/my-guy` or `~/.config/my-guy`. `MY_GUY_HOME` selects an isolated state home for tests or a deliberate separate installation. It is not the host skills root. Preserve its ownership and private permissions.

- Bad host skill change: `my-guy rollback <host> --root <same-root>` when a snapshot exists.
- Temporarily stop front-door discovery: `my-guy disable <host> --root <same-root>`.
- Remove an owned host skill: `my-guy uninstall <host> --root <same-root>`.
- Bad CLI release: reinstall only a previously reviewed exact commit SHA via `pipx` or the same virtual environment. For v0.1.0, use `c6edf09de6a9fcd6df80ae7116f0735a5ecb0d7f`; for a future release, verify its exact commit first. Follow the tag check and install instructions in [Agent install](AGENT_INSTALL.md), then check version, doctor, and host status. Host skill rollback does not downgrade the CLI.
- Catalog corruption: preserve the state directory for diagnosis, then rebuild the catalog with `my-guy sync` after isolating the damaged `catalog.sqlite3` file.

For GitHub release gates and artifact checks, see [Releasing](RELEASING.md). For a first-time agent workflow and the no-useful-pack path, see [Agent install](AGENT_INSTALL.md). The agent/plugin inventory expansion needs its own review, full local verification, and release gates before it can be described as part of a published release.
