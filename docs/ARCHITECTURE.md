# Architecture

## Request flow

`request → inventory/sync → host-aware rank → clarify/recommend/convene → prepared handoff → explicit approval`

The router has four boundaries:

1. **Inventory:** checked-in capabilities plus bounded, read-only local metadata scans. Files are parsed as data; skill and agent instructions are never executed.
2. **Decision:** lexical evidence, confidence gates, host availability, and trust determine whether to clarify, recommend, or convene.
3. **Coordination:** synthesis preserves unavailable specialists and dissent. It does not claim agreement from a single response.
4. **Handoff:** adapters validate invocation allowlists and render structured handoff data. They do not start a provider or specialist.

## Inventory and host scope

The supported hosts are Codex, Claude Code, and OpenCode. A capability records its kind (`skill` or `agent`), source, trust, and hosts. Default and explicit roots are host-scoped; shared `.agents/skills` roots apply to all three hosts. A custom skill root needs `--hosts` when its host cannot be inferred from its path. A custom agent root always requires one explicit host.

| Host | Static inventory |
| --- | --- |
| Codex | Standard skill and agent roots; enabled plugin installations found through Codex configuration and its local plugin cache. |
| Claude Code | Standard skill and agent roots; plugins enabled by user, project, or project-local settings and present in the installed-plugin manifest. Project-scoped installs must match the current project. |
| OpenCode | Standard skill and agent roots plus static agent entries in global or project JSON/JSONC configuration. |

Scans are read-only, bounded, skip symlinks, and read only the metadata needed for routing. They do not execute plugin code. This makes inventory useful evidence, not a completeness guarantee. OpenCode plugins can register or transform runtime capabilities through plugin APIs; a static filesystem scan cannot see those effective runtime results ([OpenCode plugin documentation](https://opencode.ai/v2/docs/build/plugins)).

When `route --host HOST` finds a relevant capability hosted elsewhere, the JSON response can include cross-host matches and a `prepared` handoff with a target host. It contains the request, source, invocation, and an approval requirement. The user must take that prepared record to the target host; the router does not launch or invoke it. Unknown-host capabilities cannot be targeted by a host-restricted adapter.

## Trust model

- `verified`: reserved for provenance verified by a future verifier; none is implemented.
- `local`: the operator explicitly registers a reviewed source.
- `unverified`: discovered or configured without explicit trust; visible for search, but not actionable.

New discoveries default to `unverified`. An explicit `config --add-root ... local --hosts ...` or `config --add-agent-root ... local HOST` records the operator's trust choice. This is a local policy assertion, not cryptographic verification. Skill and agent bodies remain untrusted instructions and are not loaded for execution.

## Catalog and migration

SQLite stores the current capability snapshot and marks missing entries stale. The catalog adds `kind` and `hosts` columns when an older database is opened. Legacy rows migrate as skills available to Codex, Claude Code, and OpenCode. Existing configuration files remain readable: conventional root paths infer their host; custom roots should be reconfigured with an explicit host list. Inventory re-sync updates records without discarding the old catalog first.

## Approval boundary

An approval binding covers the route, candidate set, capability, invocation, and exact request. It prevents accidental substitution inside the trusted process. It is not authentication against malicious code in that process. Provider execution remains disabled until identity, authenticated approval, authorization, rate limits, and durable audit are designed and tested.

## Feedback evolution

Feedback is opt-in and stores keyed request fingerprints rather than raw requests. Aggregate proposals are review-only. Humans approve versioned registry changes; runtime self-modification is out of scope.
