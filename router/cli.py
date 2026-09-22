from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import asdict, replace
from importlib import resources
from pathlib import Path

from .catalog import CapabilityCatalog
from .config import RouterConfig, SkillRoot, app_home, load_config, save_config
from .core import route
from .discovery import discover_named_roots
from .feedback import FeedbackStore
from .lifecycle import SUPPORTED_HARNESSES, SkillInstaller
from .registry import load_registry
from .sync import sync_capabilities


COMMANDS = frozenset({"route", "sync", "list", "config", "install", "upgrade", "disable", "rollback", "feedback", "proposals", "doctor"})


def _parent_ready(path: Path) -> bool:
    candidate = path.parent
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate.is_dir() and os.access(candidate, os.W_OK | os.X_OK)


def _paths() -> tuple[Path, Path, Path]:
    home = app_home()
    return home / "config.json", home / "catalog.sqlite3", home / "feedback.sqlite3"


def _secure_state_home() -> Path:
    home = app_home()
    if home.exists():
        if not home.is_dir():
            raise ValueError("MY_GUY_HOME must name a directory")
        if home.stat().st_mode & 0o077:
            raise PermissionError("my-guy state directory must not be group/world accessible")
    else:
        home.mkdir(parents=True, mode=0o700)
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
    sub = parser.add_subparsers(dest="command", required=True)

    route_parser = sub.add_parser("route", help="route a request without invoking specialists")
    route_parser.add_argument("request", nargs=argparse.REMAINDER)
    route_parser.add_argument("--json", action="store_true")

    sub.add_parser("sync", help="refresh the local capability directory")
    list_parser = sub.add_parser("list", help="list or search directory entries")
    list_parser.add_argument("query", nargs="*")
    list_parser.add_argument("--include-stale", action="store_true")

    config_parser = sub.add_parser("config", help="show or modify local configuration")
    config_parser.add_argument("--feedback", choices=("on", "off"))
    config_parser.add_argument("--add-root", nargs=3, metavar=("NAME", "PATH", "TRUST"))

    for action in ("install", "upgrade", "disable", "rollback"):
        action_parser = sub.add_parser(action, help=f"{action} the portable front-door skill")
        action_parser.add_argument("harness", choices=sorted(SUPPORTED_HARNESSES))
        action_parser.add_argument("--root", required=True, type=Path)

    feedback = sub.add_parser("feedback", help="record an opt-in routing outcome")
    feedback.add_argument("capability_id")
    feedback.add_argument("outcome", choices=("accepted", "corrected", "failed"))
    feedback.add_argument("request", nargs=argparse.REMAINDER)
    feedback.add_argument("--correction")
    proposals = sub.add_parser("proposals", help="show review-only evolution proposals")
    proposals.add_argument("--minimum-samples", type=int, default=5)
    sub.add_parser("doctor", help="check local readiness without making changes")
    return parser


def _main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in COMMANDS and not argv[0].startswith("-"):
        argv.insert(0, "route")
    args = build_parser().parse_args(argv)
    config_path, catalog_path, feedback_path = _paths()
    config = load_config(config_path)

    if args.command == "config":
        if args.feedback:
            config = replace(config, feedback_enabled=args.feedback == "on")
        if args.add_root:
            name, path, trust = args.add_root
            root = SkillRoot(name, path, trust)
            config = replace(config, roots=tuple(item for item in config.roots if item.name != name) + (root,))
        if args.feedback or args.add_root:
            save_config(config, config_path)
        print(json.dumps(asdict(config), indent=2))
        return 0

    if args.command in {"install", "upgrade", "disable", "rollback"}:
        installer = SkillInstaller(_secure_state_home())
        result = getattr(installer, args.command)(args.harness, args.root)
        print(json.dumps(asdict(result), indent=2))
        return 0

    if not config.enabled:
        print("my-guy is disabled in local configuration", file=sys.stderr)
        return 2

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
        checks = {
            "enabled": config.enabled,
            "config": str(config_path),
            "catalog_parent_ready": _parent_ready(catalog_path),
            "roots": [{"name": root.name, "path": root.path, "exists": Path(root.path).is_dir(), "trust": root.trust} for root in config.roots],
            "provider_execution": "not-implemented; adapters render handoffs only",
        }
        print(json.dumps(checks, indent=2))
        return 0 if checks["catalog_parent_ready"] else 1

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
        request = " ".join(args.request).removeprefix("-- ").strip()
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
