# Operations

## Readiness

Run:

```bash
python -m pytest -q
python -m router doctor
python -m router route --json -- "Review authentication security"
```

`doctor` reports missing directories and the non-executing provider boundary without changing state.

## Install lifecycle

Always pass the intended harness skill root explicitly. Install and upgrade snapshot the prior file. Disable renames `SKILL.md` so normal discovery stops seeing it. Rollback restores the most recent exact-root snapshot. Symlinked targets are refused.

State defaults to `$XDG_CONFIG_HOME/my-guy` or `~/.config/my-guy`; set `MY_GUY_HOME` for isolation or CI.

## Release checklist

1. Clean feature branch; never release from a protected branch.
2. Full tests pass on Python 3.11, 3.12, and 3.13.
3. Build wheel and source distribution without network access.
4. Run CLI, lifecycle, malformed-metadata, collision, approval replay, and feedback privacy smoke tests.
5. Complete architecture and security reviews; record unresolved limits in `docs/STATUS.md`.
6. Tag only after human review. Never auto-merge or auto-publish.

## Recovery

- Bad skill update: `my-guy rollback <harness> --root <exact-root>`.
- Stop discovery: `my-guy disable <harness> --root <exact-root>`.
- Corrupt catalog: move `catalog.sqlite3` aside and run `my-guy sync`; the registry and metadata rebuild it.
- Feedback removal: delete `feedback.sqlite3`; raw requests were never stored.
