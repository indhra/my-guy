# Operations

## Verify a checkout

```bash
python3 -m pytest -q
python3 -m router doctor
python3 -m router sync
python3 -m router route --host codex --json -- "Review authentication security"
```

`doctor` reports readiness and inventory counts without changing provider state. `sync` refreshes the local capability catalog. Text route output shows up to 10 candidates and 3 cross-host matches, with counts and hints when results are omitted. Default `route --json` includes up to 20 candidates with their evidence entries and, with `--host`, up to 20 cross-host matches. It reports candidate totals and truncation, plus separate cross-host totals and truncation when a host is supplied. The prepared handoff remains present when a recommendation is available. Use `route --json --all` for exhaustive arrays; `--all` requires `--json`.

The JSON fields are `candidate_total` and `candidates_truncated`; with `--host`, `cross_host_match_total` and `cross_host_matches_truncated` are also included. `reason` stays concise and summarizes broad matches rather than embedding every candidate. The complete route evidence remains available through the candidate and evidence arrays.

## Configure inventory roots

Conventional existing home and project skill roots are detected for Codex, Claude Code, and OpenCode. Shared `.agents/skills` roots apply to all three. For custom locations, declare the host scope rather than allowing an unknown host to be inferred:

```bash
my-guy config --add-root team-skills /absolute/path/to/skills unverified --hosts codex,claude
my-guy config --add-agent-root team-agents /absolute/path/to/agents unverified codex
```

Review a source before explicitly promoting it to local trust. For example, replace `unverified` with `local` only after review. Agent roots require exactly one host. Unknown-host inventory remains non-actionable for host-restricted routing.

Codex and Claude Code plugin scans include supported enabled installs described by local host configuration and install metadata. Disabled plugins are omitted; Claude project-scoped plugin records must belong to the current project. OpenCode inventory reads static agent files and JSON/JSONC definitions, not plugin runtime registrations or transforms. Discovery is read-only and bounded; review the host's own runtime view when completeness matters.

## Prepared handoffs

`route --host codex|claude|opencode --json` reports the requesting host and host availability. A cross-host recommendation includes a prepared target-host handoff and `approval_required: true`. It is a record for the operator to review and carry to the target host. It does not open a session, invoke an agent, run skill instructions, or call a provider.

## Catalog migration and recovery

Opening an older SQLite catalog adds the `kind` and `hosts` fields in place. Existing rows default to `skill` and all three supported hosts. Existing config roots without host fields remain readable; common host paths are inferred, while custom paths need an explicit `--hosts` entry or an explicit agent root. Run `my-guy sync` after changing roots or host/plugin installations to reconcile the snapshot.

- Bad front-door skill update: `my-guy rollback <harness> --root <exact-root>`.
- Stop front-door discovery: `my-guy disable <harness> --root <exact-root>`.
- Rebuild a damaged catalog: move `catalog.sqlite3` aside, then run `my-guy sync`.
- Remove feedback history: delete `feedback.sqlite3`; raw requests are not stored.

## Release checks

1. Work on a feature branch and preserve the explicit approval gate for provider execution.
2. Run the full test suite and supported Python-version matrix.
3. Build wheel and source distributions without network access.
4. Exercise host-scoped inventory, active-plugin filtering, old-catalog migration, trust filtering, cross-host handoff output, lifecycle rollback, and approval replay fixtures.
5. Record unresolved limits and review findings in `docs/STATUS.md`. Tag only after human review; do not auto-merge or auto-publish.
