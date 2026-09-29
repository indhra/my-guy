from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import asdict, replace
from importlib import metadata
from importlib import resources
from pathlib import Path

from .catalog import CapabilityCatalog
from .config import RouterConfig, SkillRoot, app_home, has_symlink_component, load_config, save_config
from .core import route
from .discovery import discover_named_roots, unsafe_skill_files
from .feedback import FeedbackStore
from .lifecycle import SUPPORTED_HARNESSES, SkillInstaller, standard_skill_roots
from .path_safety import unsafe_skill_root
from .registry import load_registry
from .sync import sync_capabilities


COMMANDS = frozenset({"route", "sync", "list", "config", "install", "upgrade", "disable", "rollback", "uninstall", "status", "feedback", "proposals", "doctor"})
MAX_REQUEST_LENGTH = 1_048_576


def _package_version() -> str:
    try:
        return metadata.version("agent-router")
    except metadata.PackageNotFoundError:
        return "source checkout (package metadata unavailable)"


def _validate_host_root(harness: str, root: Path, *, allow_custom_root: bool) -> None:
    defaults = standard_skill_roots()
    if has_symlink_component(root):
        raise PermissionError("refusing a symlinked skill root")
    normalized = root.expanduser().resolve(strict=False)
    for other, standard in defaults.items():
        if other != harness and normalized == standard.expanduser().resolve(strict=False):
            raise ValueError(f"{normalized} is the standard {other} skill root, not {harness}")
    if normalized != defaults[harness].expanduser().resolve(strict=False) and not allow_custom_root:
        raise ValueError("custom skill root requires explicit --allow-custom-root")


def _parent_ready(path: Path) -> bool:
    candidate = path.parent
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate.is_dir() and os.access(candidate, os.W_OK | os.X_OK)


def _paths() -> tuple[Path, Path, Path]:
    home = app_home()
    return home / "config.json", home / "catalog.sqlite3", home / "feedback.sqlite3"


def _state_home_issue(home: Path) -> str | None:
    if home.is_symlink():
        return "my-guy state directory must not be a symlink"
    if home.exists():
        if not home.is_dir():
            return "MY_GUY_HOME must name a directory"
        if home.stat().st_mode & 0o077:
            return "my-guy state directory must not be group/world accessible"
    if reason := unsafe_skill_root(home):
        return f"my-guy state directory has an unsafe path: {reason}"
    return None


def _secure_state_home() -> Path:
    home = app_home()
    issue = _state_home_issue(home)
    if issue:
        raise PermissionError(issue)
    if not home.exists():
        home.mkdir(parents=True, mode=0o700)
    if issue := _state_home_issue(home):
        raise PermissionError(issue)
    return home


def _seed_capabilities():
    seed = resources.files("router").joinpath("resources/capabilities.json")
    with resources.as_file(seed) as path:
        return load_registry(path)


def _sync(config: RouterConfig, catalog: CapabilityCatalog) -> tuple[int, tuple[str, ...]]:
    capabilities = (*_seed_capabilities(), *discover_named_roots(config.roots))
    stale = sync_capabilities(catalog, capabilities)
    return len(capabilities), stale


def _decision_payload(decision, capabilities) -> dict:
    by_id = {capability.id: capability for capability in capabilities}
    return {
        **asdict(decision),
        "evidence": [
            {
                "id": candidate,
                "source": by_id[candidate].source,
                "invocation": by_id[candidate].invocation,
                "trust": by_id[candidate].trust,
            }
            for candidate in decision.candidates
            if candidate in by_id
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="my-guy", description="Evidence-backed capability router")
    parser.add_argument("--version", action="store_true", help="show the installed package version")
    sub = parser.add_subparsers(dest="command")

    route_parser = sub.add_parser("route", help="route a request without invoking specialists")
    route_parser.add_argument("request", nargs=argparse.REMAINDER)
    route_parser.add_argument("--json", action="store_true")
    route_parser.add_argument("--stdin", action="store_true", help="read request text from stdin")

    sub.add_parser("sync", help="refresh the local capability directory")
    list_parser = sub.add_parser("list", help="list or search directory entries")
    list_parser.add_argument("query", nargs="*")
    list_parser.add_argument("--include-stale", action="store_true")

    config_parser = sub.add_parser("config", help="show or modify local configuration")
    config_parser.add_argument("--feedback", choices=("on", "off"))
    config_parser.add_argument("--add-root", nargs=3, metavar=("NAME", "PATH", "TRUST"))

    for action in ("install", "upgrade", "disable", "rollback", "uninstall", "status"):
        action_parser = sub.add_parser(action, help=f"{action} the portable front-door skill")
        action_parser.add_argument("harness", choices=sorted(SUPPORTED_HARNESSES))
        action_parser.add_argument("--root", required=True, type=Path)
        if action in {"install", "upgrade"}:
            action_parser.add_argument("--replace-existing", action="store_true")
        if action == "install":
            action_parser.add_argument("--dry-run", action="store_true")
        if action != "status":
            action_parser.add_argument("--allow-custom-root", action="store_true")
        else:
            action_parser.add_argument("--json", action="store_true")

    feedback = sub.add_parser("feedback", help="record an opt-in routing outcome")
    feedback.add_argument("capability_id")
    feedback.add_argument("outcome", choices=("accepted", "corrected", "failed"))
    feedback.add_argument("request", nargs=argparse.REMAINDER)
    feedback.add_argument("--correction")
    proposals = sub.add_parser("proposals", help="show review-only evolution proposals")
    proposals.add_argument("--minimum-samples", type=int, default=5)
    doctor = sub.add_parser("doctor", help="check local readiness without making changes")
    doctor.add_argument("--harness", choices=sorted(SUPPORTED_HARNESSES))
    doctor.add_argument("--root", type=Path)
    return parser


def _main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in COMMANDS and not argv[0].startswith("-"):
        argv.insert(0, "route")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"my-guy {_package_version()}")
        return 0
    if args.command is None:
        parser.error("a command is required")
    config_path, catalog_path, feedback_path = _paths()
    config = load_config(config_path)

    if args.command == "config":
        if args.feedback:
            config = replace(config, feedback_enabled=args.feedback == "on")
        if args.add_root:
            name, path, trust = args.add_root
            if trust == "local" and (reason := unsafe_skill_root(Path(path))):
                raise PermissionError(f"trusted skill root is unsafe: {reason}")
            root = SkillRoot(name, path, trust)
            config = replace(config, roots=tuple(item for item in config.roots if item.name != name) + (root,))
        if args.feedback or args.add_root:
            _secure_state_home()
            save_config(config, config_path)
        print(json.dumps(asdict(config), indent=2))
        return 0

    if args.command == "status":
        status = SkillInstaller(app_home()).inspect(args.harness, args.root)
        if args.json:
            print(json.dumps(asdict(status), indent=2))
        else:
            print(f"{status.state.upper()}: {status.summary}")
            print(f"Target: {status.target}")
            for action in status.next_actions:
                print(f"Next: {action}")
        return 0 if status.state == "ready" else 1

    if args.command in {"install", "upgrade", "disable", "rollback", "uninstall"}:
        _validate_host_root(args.harness, args.root, allow_custom_root=args.allow_custom_root)
        if args.command == "install" and args.dry_run:
            status = SkillInstaller(app_home()).inspect(args.harness, args.root)
            plan = {**asdict(status), "planned_action": "install",
                    "requires_approval": status.state == "modified" and not status.owned}
            print(json.dumps(plan, indent=2))
            return 1 if plan["requires_approval"] and not args.replace_existing else 0
        installer = SkillInstaller(_secure_state_home())
        if args.command in {"install", "upgrade"}:
            result = getattr(installer, args.command)(args.harness, args.root,
                                                       replace_existing=args.replace_existing)
        else:
            result = getattr(installer, args.command)(args.harness, args.root)
        print(json.dumps(asdict(result), indent=2))
        return 0

    if args.command == "feedback":
        _secure_state_home()
        request = " ".join(args.request).strip()
        store = FeedbackStore(feedback_path)
        try:
            try:
                store.record(request, args.capability_id, args.outcome, consent=config.feedback_enabled, correction=args.correction)
            except (PermissionError, ValueError) as error:
                print(str(error), file=sys.stderr)
                return 2
        finally:
            store.close()
        print("feedback recorded without storing the raw request")
        return 0

    if args.command == "proposals":
        _secure_state_home()
        store = FeedbackStore(feedback_path)
        try:
            print(json.dumps([asdict(item) for item in store.proposals(args.minimum_samples)], indent=2))
        finally:
            store.close()
        return 0

    if args.command == "doctor":
        if bool(args.harness) != bool(args.root):
            raise ValueError("doctor requires both --harness and --root")
        discovered = discover_named_roots(config.roots)
        trusted = [capability for capability in discovered if capability.trust == "local"]
        unsafe_roots = [(root, unsafe_skill_root(Path(root.path))) for root in config.roots
                        if root.trust == "local" and unsafe_skill_root(Path(root.path))]
        unsafe_files = [item for root in config.roots if root.trust == "local"
                        for item in unsafe_skill_files(Path(root.path))]
        state_issue = _state_home_issue(app_home())
        checks = {
            "enabled": config.enabled,
            "config": str(config_path),
            "package_version": _package_version(),
            "catalog_parent_ready": _parent_ready(catalog_path),
            "state_home_safe": state_issue is None,
            "roots": [{"name": root.name, "path": root.path, "exists": Path(root.path).is_dir(),
                       "trust": root.trust, "safe": unsafe_skill_root(Path(root.path)) is None} for root in config.roots],
            "trusted_root_count": len({item.source.split(":", 1)[0] for item in trusted}),
            "trusted_capability_count": len(trusted),
            "unsafe_trusted_skill_files": [
                {"path": path, "reason": reason} for path, reason in unsafe_files
            ],
            "routing_readiness": ("Discovered trusted capabilities are available; routing still depends on request relevance."
                                  if trusted else "Only unverified or missing roots are available; routing may correctly clarify."),
            "provider_execution": "not-implemented; adapters render handoffs only",
        }
        if args.harness:
            checks["installation"] = asdict(SkillInstaller(app_home()).inspect(args.harness, args.root))
        actions = []
        if unsafe_roots:
            actions.extend(f"Review unsafe trusted root {root.name}: {reason}." for root, reason in unsafe_roots)
        if unsafe_files:
            actions.extend(f"Review unsafe trusted skill {path}: {reason}." for path, reason in unsafe_files)
        if state_issue:
            actions.append(state_issue + ". Choose a private state directory before routing.")
        if not trusted:
            actions.append("Review a real local skill root, then add it as trusted and run sync.")
        if args.harness and checks["installation"]["state"] != "ready":
            actions.extend(checks["installation"]["next_actions"])
        if not checks["catalog_parent_ready"]:
            actions.append("Choose a writable private state directory.")
        if not config.enabled:
            actions.append("Enable My Guy in local configuration.")
        checks["status"] = ("disabled" if not config.enabled else
                            "needs_installation" if args.harness and checks["installation"]["state"] != "ready" else
                            "blocked" if state_issue or unsafe_roots or unsafe_files or not checks["catalog_parent_ready"] else
                            "needs_capabilities" if not trusted else "ready")
        checks["summary"] = ("Ready to route reviewed capabilities." if checks["status"] == "ready" else
                             "My Guy needs setup before trusted routing is ready.")
        checks["next_actions"] = actions
        print(json.dumps(checks, indent=2))
        return 0 if checks["status"] == "ready" else 1

    if not config.enabled:
        print("my-guy is disabled in local configuration", file=sys.stderr)
        return 2

    _secure_state_home()
    catalog = CapabilityCatalog(catalog_path)
    try:
        count, stale = _sync(config, catalog)
        if args.command == "sync":
            print(json.dumps({"discovered": count, "stale": stale}, indent=2))
            return 0
        capabilities = catalog.active()
        if args.command == "list":
            query = " ".join(args.query).strip()
            pool = catalog.all() if args.include_stale else capabilities
            if query:
                active_ids = {item.id for item in pool}
                selected = tuple(item for item in catalog.search(query) if item.id in active_ids)
            else:
                selected = pool
            print(json.dumps([asdict(item) for item in selected], indent=2))
            return 0
        if args.stdin and args.request:
            raise ValueError("--stdin cannot be combined with a positional request")
        raw_request = (sys.stdin.read(MAX_REQUEST_LENGTH + 1) if args.stdin else
                       " ".join(args.request).removeprefix("-- "))
        if len(raw_request) > MAX_REQUEST_LENGTH:
            raise ValueError("route request exceeds 1,048,576 characters")
        request = raw_request.strip()
        if not request:
            print("a non-empty request is required", file=sys.stderr)
            return 2
        decision = route(request, capabilities)
        payload = _decision_payload(decision, capabilities)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"{decision.status.upper()} ({decision.confidence:.2f})")
            print(decision.reason)
            for evidence in payload["evidence"]:
                print(f"- {evidence['id']} [{evidence['trust']}] via {evidence['invocation']} ({evidence['source']})")
        return 0
    finally:
        catalog.close()


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f"my-guy: {error}", file=sys.stderr)
        return 2
