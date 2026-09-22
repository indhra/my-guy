# Research Baseline

Date: 2026-09-20

## Existing building blocks

| Source | Verified capability | Boundary |
| --- | --- | --- |
| [GStack](https://github.com/garrytan/gstack) | Root `gstack` skill routes requests within its suite | Not a cross-ecosystem registry |
| [Matt Pocock skills](https://github.com/mattpocock/skills) | `ask-matt` maps situations to that repository's flows | Explicitly does not discover arbitrary local skills |
| [ECC](https://github.com/affaan-m/everything-claude-code) | `council`, `skill-scout`, fixed orchestration chains | No universal semantic router |

All three repositories were queried through GitHub on 2026-09-20. Their public
metadata reported MIT licenses and active updates on 2026-09-19.

## Local evidence

- GStack: `~/.claude/skills/gstack/SKILL.md`
- Matt router: `~/.claude/plugins/cache/mattpocock/mattpocock-skills/1.2.3/skills/engineering/ask-matt/SKILL.md`
- ECC council: `~/.codex/plugins/cache/ecc/ecc/2.2.1/skills/council/SKILL.md`

## Decision

Build a new, harness-neutral core with thin adapters. Reuse the router
patterns, evaluation ideas, and safety gates above; do not fork any upstream
skill as the system of record.
