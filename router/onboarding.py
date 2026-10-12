"""Guided first-run setup for the local capability directory.

``my-guy init`` detects configured and standard skill roots, reports what was
found, and prepares the catalog. Trust stays explicit: roots whose entire
skill inventory is the receipt-verified bundled front-door skill may be marked
``local`` automatically (their provenance is verified by our own installer),
and the operator may name additional roots to trust. Everything else reports
the review step and the exact command that grants trust; nothing is silently
trusted.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from .config import RouterConfig, SkillRoot, default_roots
from .discovery import discover_skills
from .lifecycle import SkillInstaller, standard_skill_roots
from .path_safety import unsafe_skill_root


@dataclass(frozen=True)
class RootReport:
    name: str
    path: str
    exists: bool
    skill_count: int
    trust: str
    trusted_by: str | None
    next_action: str | None


@dataclass(frozen=True)
class InitReport:
    roots: tuple[RootReport, ...]
    total_skills: int
    trusted_roots: int
    next_actions: tuple[str, ...]


def _standard_harness_for(root: SkillRoot) -> str | None:
    """The supported harness whose canonical root this is, if any."""
    target = Path(root.path).expanduser().resolve(strict=False)
    for harness, standard in standard_skill_roots().items():
        if target == standard.expanduser().resolve(strict=False):
            return harness
    return None


def collect_roots(config: RouterConfig) -> tuple[SkillRoot, ...]:
    """Configured roots unioned with detected standard roots, config winning."""
    by_name = {root.name: root for root in config.roots}
    known_paths = {root.path for root in config.roots}
    for root in default_roots():
        if root.name not in by_name and root.path not in known_paths:
            by_name[root.name] = root
    return tuple(by_name.values())


def _verified_bundled_only(
    root: SkillRoot, installer: SkillInstaller, discovered_count: int
) -> bool:
    """True when the root holds only our receipt-verified bundled skill.

    The front-door skill's provenance is proven by the installer receipt and
    digest, and the root must contain no other skills: trust is root-scoped,
    so any unverified sibling would become routable too.
    """
    harness = _standard_harness_for(root)
    if harness is None or discovered_count != 1:
        return False
    status = installer.inspect(harness, Path(root.path))
    return bool(
        status.state == "ready"
        and status.owned
        and status.digest is not None
        and status.digest == status.bundled_digest
    )


def guided_init(
    config: RouterConfig,
    *,
    installer: SkillInstaller,
    trust_names: tuple[str, ...] = (),
    prompter: Callable[[SkillRoot, int], bool] | None = None,
) -> tuple[RouterConfig, InitReport]:
    """Assess each root, apply permitted trust, and describe next actions.

    ``trust_names`` names roots the operator explicitly trusts (same effect as
    ``config --add-root NAME PATH local``). ``prompter`` is called once per
    remaining unverified root that contains skills; returning True grants
    trust. Verified-bundled roots are trusted automatically. The returned
    config must be saved by the caller before syncing.
    """
    roots = collect_roots(config)
    by_name = {root.name: root for root in roots}
    unknown = set(trust_names) - by_name.keys()
    if unknown:
        raise ValueError(f"unknown skill roots: {', '.join(sorted(unknown))}")

    reports: list[RootReport] = []
    updated: dict[str, SkillRoot] = {}
    for root in roots:
        path = Path(root.path)
        exists = path.is_dir()
        discovered = discover_skills([root.path]) if exists else ()
        skill_count = len(discovered)
        trust = root.trust
        trusted_by: str | None = None
        next_action: str | None = None

        if not exists:
            next_action = "Skill root does not exist yet; create it or remove it from config."
        elif trust != "local":
            if _verified_bundled_only(root, installer, skill_count):
                trust, trusted_by = "local", "bundled-verified"
            elif root.name in trust_names:
                if reason := unsafe_skill_root(path):
                    raise PermissionError(f"trusted skill root is unsafe: {reason}")
                trust, trusted_by = "local", "operator"
            elif skill_count and prompter is not None and prompter(root, skill_count):
                if reason := unsafe_skill_root(path):
                    raise PermissionError(f"trusted skill root is unsafe: {reason}")
                trust, trusted_by = "local", "prompt"
            elif skill_count:
                hosts_flag = f" --hosts {','.join(root.hosts)}" if root.hosts else ""
                next_action = (
                    f"Review the skills under {root.path}, then run: "
                    f"my-guy config --add-root {root.name} {root.path} local{hosts_flag}"
                )
            else:
                next_action = "No SKILL.md files found under this root."

        if trust != root.trust:
            updated[root.name] = replace(root, trust=trust)
        reports.append(
            RootReport(root.name, root.path, exists, skill_count, trust, trusted_by, next_action)
        )

    trusted_roots = sum(report.trust == "local" for report in reports)
    total_skills = sum(report.skill_count for report in reports)
    next_actions = tuple(
        report.next_action for report in reports if report.next_action is not None
    )
    merged = tuple(updated.get(root.name, root) for root in roots)
    return replace(config, roots=merged), InitReport(
        tuple(reports), total_skills, trusted_roots, next_actions
    )
