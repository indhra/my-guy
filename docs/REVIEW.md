# Production Review

Date: 2026-09-22

## Independent audit

The requested single medium-effort audit initially scored the alpha `58/100` and found six release blockers:

1. Stale catalog entries remained routable.
2. Moving a skill changed its source path and broke synchronization.
3. Bundled reference entries were trusted without proving installation.
4. Pipe-delimited approval hashing allowed ambiguous field boundaries.
5. Feedback databases and deterministic request hashes had weak privacy defaults.
6. Rollback deleted the current install before validating backups.

All six were reproduced, fixed, and covered by regressions. Exact mirrored skill copies are now collapsed and routing returns all top-scoring matches without an arbitrary numeric cutoff.

## ECC agent architecture audit

```json
{
  "schema_version": "ecc.agent-architecture-audit.report.v1",
  "executive_verdict": {
    "overall_health": "controlled_alpha",
    "primary_failure_mode": "none open at critical or high severity",
    "most_urgent_fix": "add real provider identity and execution contracts before enabling execution"
  },
  "scope": {
    "target_name": "agent-router / my-guy",
    "model_stack": ["provider-neutral; no runtime model calls"],
    "layers_to_audit": ["prompt", "history", "memory", "retrieval", "tool routing", "tool execution", "interpretation", "rendering", "repair loops", "persistence"]
  },
  "findings": [],
  "ordered_fix_plan": []
}
```

Evidence:

- Tool requirements are code-gated by trust, decision status, exact binding, and adapter allowlists.
- No model, subprocess, network, hidden retry, repair, or response-rewrite call exists in the runtime.
- Stale state is retained as evidence but excluded from `catalog.active()` routing.
- Internal flow uses typed dataclasses and JSON output rather than free-form hidden protocols.
- Session history and long-term memory layers do not exist; feedback is a separate opt-in aggregate ledger.

## ECC security review

Verdict: **PASS for the implemented non-executing alpha boundary; not approval for provider execution.**

- No hardcoded secrets or secret-like Git history matches found.
- User-controlled SQL values use parameters; the only SQL formatting selects a constant internal clause.
- Capability IDs, metadata lengths, trust values, config schema, absolute roots, lifecycle harnesses, and feedback outcomes are allowlisted or bounded.
- Discovery never executes skill content, rejects symlinked files, caps files and file size, and isolates malformed entries.
- State directories are `0700`; catalog, config, feedback DB, feedback key, and snapshot manifests are `0600` where applicable.
- Feedback is disabled by default and uses a per-installation HMAC fingerprint instead of raw requests or portable unsalted hashes.
- Rollback validates manifest shape, backup location, and digest before atomically replacing current files.
- No application dependencies are declared. The host-level `pip check` warning for Ubuntu's unrelated `python-debian` package is outside this project.

Residual security boundary: approval bindings prevent accidental substitution inside trusted code. They do not authenticate hostile code in the same Python process. Any future remote/provider executor needs authenticated identity, server-held keys, rate limits, durable audit, and provider-specific authorization tests.

## GStack design review scope

Visual review is **not applicable**. The repository ships a Python CLI/library and portable Markdown skill, with no HTML, CSS, JavaScript UI, live URL, or rendered surface. The design-review skill requires screenshot evidence and forbids inventing it. CLI experience was reviewed instead: concise status, confidence, evidence, stable JSON, bounded relevant candidates, and actionable errors.

## Verification

- `58 passed`
- source compile check passes with bytecode redirected to `/tmp`
- wheel builds and installs in an isolated virtual environment
- clean install returns `clarify` for unverified references
- explicitly trusted installed ECC root returns `recommend` with source and invocation evidence
- state directory mode `0700`; catalog mode `0600`

## Release verdict

High-severity findings are closed for the current feature set. This is a hardened alpha core, not yet a production provider-execution service or a universal host installer. The remaining gaps are clearly documented limits rather than hidden claims.
