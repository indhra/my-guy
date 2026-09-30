# Architecture

## Flow

`request → discover/sync → rank → clarify/recommend/convene → approval → structured handoff`

The package has four boundaries:

1. **Directory:** checked-in seed capabilities plus read-only, namespaced `SKILL.md` discovery in SQLite.
2. **Decision:** transparent lexical evidence, confidence gating, and trust filtering.
3. **Coordination:** quorum-based synthesis that preserves unavailable specialists and dissent.
4. **Execution boundary:** exact request/route/capability binding and adapter allowlists. Current adapters return typed handoffs only.

## Trust model

- `verified`: provenance was verified by a future verifier. No automatic verifier exists yet.
- `local`: the operator explicitly trusts the source.
- `unverified`: searchable, but unable to create an actionable route or execute.

Installed roots default to `unverified`. Discovery content is data, never instructions. Stable namespaces and collision rejection prevent shadowing.

## Host-aware inventory

The in-progress inventory expansion records capability kind (`skill` or `agent`) and host availability for Codex, Claude Code, and OpenCode. Host metadata has three states: `null` means unknown or not yet verified, an empty list means known unavailable on these hosts, and a non-empty list names the supported hosts. Conventional recognized roots can establish host scope; custom roots need explicit host metadata. Shared `.agents/skills` roots are host-neutral and may be explicitly associated with supported hosts.

Plugin discovery is static and read-only. Claude Code plugin paths are constrained to managed plugin storage; manifest-provided absolute paths are not trusted as scan roots. Inventory of enabled installations does not execute plugin code or guarantee that runtime registrations are visible. Cross-host matches may be reported for review. A prepared handoff is emitted only when the catalog has known, non-empty host availability; the record still requires operator approval and does not launch a host or provider.

Legacy catalog rows migrate with unknown host scope (`hosts = NULL`), rather than being assumed to work on every host. A later successful inventory sync can replace that unknown value with observed host metadata.

## Provider integrations and agent hosts

OpenRouter is a provider gateway, not a supported local agent host. The published `v0.1.0` adapter rendered a provider handoff without making a network call. The post-release host-aware change deliberately disables that behavior until an operator explicitly maps the provider handoff to one of the supported agent hosts: Codex, Claude Code, or OpenCode. No mapping is implicit or configured by this change. An otherwise eligible, approved, and allowlisted but unmapped request raises `HostMappingRequired` with the message `OpenRouter handoffs are disabled until mapped to a supported agent host.` Unknown host scope (`null`) does not enable a handoff; it also reaches this refusal. Explicitly empty host scope is rejected earlier as unavailable. No handoff is rendered and no provider request is sent. Mapping must preserve host-availability, approval, and invocation checks.

## Approval model

An approval binding covers the original decision, exact execution request, candidate set, reason, capability ID, and invocation. It prevents accidental replay onto a changed operation inside the trusted process. It is not cryptographic authorization against code that can import the library and mint its own binding; a remote service must add authenticated identity, durable audit, and server-held keys.

## Evolution model

Feedback is opt-in and excludes raw requests. Per-installation keyed fingerprints reduce cross-installation correlation. Aggregates produce review suggestions after a minimum sample threshold. Humans approve versioned registry or threshold changes, and Git/lifecycle snapshots provide rollback. Runtime self-modification is out of scope.
