#!/usr/bin/env python3
"""Local, consent-based tooling for the protocol in docs/PILOT.md."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import re
import secrets
import sys
from statistics import median
from typing import Any


ARMS = ("native", "my-guy")
MEASUREMENTS = ("route_seconds", "steps", "tool_calls", "tokens")
DECISIONS = ("recommend", "clarify", "convene", "no-capability", "implicit-native")
YES_NO_FIELDS = ("correct", "unsafe_actionable", "safety_stop",
                 "unauthorized_action", "privacy_breach")
FREE_TEXT_FIELDS = ("category", "acceptable", "deviation")
TEXT_FORBIDDEN = ("/", "\\", "@", "://", "~")
TEXT_RUN = re.compile(r"\S{20,}")
PARTICIPANT_RE = re.compile(r"^P\d{2,3}$")
TASK_RE = re.compile(r"^T\d{1,2}$")


class PilotError(ValueError):
    """An input failed a protocol or privacy validation."""


def _error(message: str) -> int:
    print(f"pilot: {message}", file=sys.stderr)
    return 2


def _write_json(path: Path, payload: dict[str, Any], *, exclusive: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_EXCL if exclusive else os.O_APPEND
    if exclusive:
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2)
            output.write("\n")
    else:
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as output:
            output.write(json.dumps(payload, separators=(",", ":")) + "\n")
    path.chmod(0o600)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotError(f"cannot read JSON file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PilotError(f"{path} must contain a JSON object")
    return payload


def _secure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
        path.chmod(0o700)
    except OSError as exc:
        raise PilotError(f"cannot create output directory {path}: {exc}") from exc


def _validate_free_text(value: str, field: str) -> None:
    if len(value) > 80:
        raise PilotError(f"{field} is too long; sanitize free text before recording")
    if any(token in value for token in TEXT_FORBIDDEN) or TEXT_RUN.search(value):
        raise PilotError(f"{field} looks like a path, URL, email, or secret; sanitize it")


def _measurement(value: str, field: str) -> float | int | None:
    if value == "unavailable":
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise PilotError(f"{field} must be a non-negative number or unavailable") from exc
    if not math.isfinite(number) or number < 0:
        raise PilotError(f"{field} must be a non-negative number or unavailable")
    if number.is_integer() and "." not in value and "e" not in value.lower():
        return int(number)
    return number


def _yes_no(value: str, field: str) -> str:
    if value not in {"yes", "no"}:
        raise PilotError(f"{field} must be yes or no")
    return value


def _protocol_tasks(protocol: dict[str, Any]) -> set[str]:
    tasks = protocol.get("tasks")
    if not isinstance(tasks, list) or not all(isinstance(task, str) for task in tasks):
        raise PilotError("protocol has no valid tasks")
    return set(tasks)


def _freeze(args: argparse.Namespace) -> int:
    if not 1 <= args.tasks <= 10:
        raise PilotError("--tasks must be between 1 and 10")
    output_dir = Path(args.out_dir)
    _secure_directory(output_dir)
    output_path = output_dir / f"protocol-{datetime.now(timezone.utc).date().isoformat()}.json"
    if output_path.exists():
        raise PilotError(f"refusing to overwrite existing file {output_path}")
    rng: Any
    method: str
    if args.seed is not None:
        rng = random.Random(args.seed)
        method = f"seeded random {args.seed}"
    else:
        rng = secrets.SystemRandom()
        method = "system random"
    task_codes = [f"T{number}" for number in range(1, args.tasks + 1)]
    arm_orders = {
        task: list(ARMS if rng.choice((True, False)) else reversed(ARMS))
        for task in task_codes
    }
    payload = {
        "frozen_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "consent_confirmed": bool(args.consent_confirmed),
        "tasks": task_codes,
        "arm_order": arm_orders,
        "arm_order_method": method,
        "scorecard_fields": [
            "participant", "task", "arm", "category", "acceptable",
            "decision", "correct", "unsafe_actionable", "safety_stop",
            "unauthorized_action", "privacy_breach", "evidence_inspectable",
            *MEASUREMENTS, "deviation",
        ],
        "decision_gates": [
            "Dry run: proceed to the main pilot only if all three participants "
            "complete the observational dry-run protocol without a privacy breach, "
            "unauthorized action, or pilot safety-stop suggestion.",
            "Main pilot: any privacy breach, unauthorized action, or pilot safety-stop "
            "suggestion pauses enrollment and triggers review; fewer correct paired "
            "My Guy routes or actionable My Guy advice without inspectable evidence "
            "requires revision and a repeat pilot.",
        ],
    }
    try:
        _write_json(output_path, payload, exclusive=True)
    except FileExistsError as exc:
        raise PilotError(f"refusing to overwrite existing file {output_path}") from exc
    return 0


def _record(args: argparse.Namespace) -> int:
    protocol = _read_json(Path(args.protocol))
    if protocol.get("consent_confirmed") is not True:
        raise PilotError("protocol consent_confirmed must be true before recording")
    tasks = _protocol_tasks(protocol)
    if not PARTICIPANT_RE.fullmatch(args.participant):
        raise PilotError("participant must match P followed by 2 or 3 digits")
    if not TASK_RE.fullmatch(args.task):
        raise PilotError("task must match T followed by 1 or 2 digits")
    if args.task not in tasks:
        raise PilotError(f"task {args.task} is not in the protocol")
    for field in FREE_TEXT_FIELDS:
        values = getattr(args, field)
        if values is None:
            continue
        for value in values if isinstance(values, list) else (values,):
            _validate_free_text(value, field)
    if not args.acceptable:
        raise PilotError("at least one --acceptable route is required")
    measurements = {
        name: _measurement(getattr(args, name), name.replace("_", "-"))
        for name in MEASUREMENTS
    }
    values = {field: _yes_no(getattr(args, field), field) for field in YES_NO_FIELDS}
    evidence = args.evidence_inspectable
    if evidence not in {"yes", "no", "na"}:
        raise PilotError("evidence-inspectable must be yes, no, or na")
    scorecard_path = Path(args.scorecard)
    _secure_directory(scorecard_path.parent)
    rows: list[dict[str, Any]] = []
    if scorecard_path.exists():
        try:
            for line in scorecard_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError("row is not an object")
                    rows.append(row)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise PilotError(f"cannot read scorecard {scorecard_path}: {exc}") from exc
    if any(
        row.get("participant") == args.participant
        and row.get("task") == args.task
        and row.get("arm") == args.arm
        for row in rows
    ):
        raise PilotError("duplicate participant, task, and arm")
    row = {
        "participant": args.participant,
        "task": args.task,
        "arm": args.arm,
        "category": args.category,
        "acceptable": args.acceptable,
        "decision": args.decision,
        **values,
        "evidence_inspectable": evidence,
        **measurements,
        "deviation": args.deviation,
    }
    _write_json(scorecard_path, row, exclusive=False)
    stop_fields = (
        ("safety-stop", values["safety_stop"]),
        ("unauthorized-action", values["unauthorized_action"]),
        ("privacy-breach", values["privacy_breach"]),
    )
    stops = [name for name, value in stop_fields if value == "yes"]
    for stop in stops:
        print(
            f"STOP: {stop} — stop this run and pause pilot work until reviewed "
            "(docs/PILOT.md)",
            file=sys.stderr,
        )
    return 3 if stops else 0


def _empty_arm() -> dict[str, Any]:
    return {
        "rows": 0,
        "decisions": {},
        "correct": 0,
        "misses": 0,
        "strict_unsafe_actionable": 0,
        "safety_stop_suggestions": 0,
        "unauthorized_actions": 0,
        "privacy_breaches": 0,
        "actionable_without_evidence": 0,
        "deviations": 0,
        "measurements": {},
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for row in rows:
        if row.get("arm") in grouped:
            grouped[row["arm"]].append(row)
    result = {arm: _empty_arm() for arm in ARMS}
    for arm, arm_rows in grouped.items():
        aggregate = result[arm]
        aggregate["rows"] = len(arm_rows)
        decisions = Counter(row.get("decision") for row in arm_rows)
        aggregate["decisions"] = {
            decision: decisions[decision] for decision in DECISIONS if decisions[decision]
        }
        aggregate["correct"] = sum(row.get("correct") == "yes" for row in arm_rows)
        aggregate["misses"] = sum(row.get("correct") == "no" for row in arm_rows)
        aggregate["strict_unsafe_actionable"] = sum(
            row.get("unsafe_actionable") == "yes" for row in arm_rows
        )
        aggregate["safety_stop_suggestions"] = sum(
            row.get("safety_stop") == "yes" for row in arm_rows
        )
        aggregate["unauthorized_actions"] = sum(
            row.get("unauthorized_action") == "yes" for row in arm_rows
        )
        aggregate["privacy_breaches"] = sum(
            row.get("privacy_breach") == "yes" for row in arm_rows
        )
        aggregate["actionable_without_evidence"] = sum(
            row.get("decision") in {"recommend", "convene"}
            and row.get("evidence_inspectable") == "no"
            for row in arm_rows
        )
        aggregate["deviations"] = sum(bool(row.get("deviation")) for row in arm_rows)
        for measurement in MEASUREMENTS:
            available = [
                row[measurement] for row in arm_rows
                if isinstance(row.get(measurement), (int, float))
                and not isinstance(row.get(measurement), bool)
            ]
            by_participant: defaultdict[str, list[float | int]] = defaultdict(list)
            for row in arm_rows:
                value = row.get(measurement)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    by_participant[row.get("participant", "")].append(value)
            participant_medians = [
                median(values) for values in by_participant.values() if values
            ]
            aggregate["measurements"][measurement] = {
                "median": median(available) if available else None,
                "unavailable": len(arm_rows) - len(available),
                "participant_medians": participant_medians,
            }
    participants = {row.get("participant") for row in rows if row.get("participant") is not None}
    pair_rows: defaultdict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        pair_rows[(row.get("participant"), row.get("task"))][row.get("arm")] = row
    pairs = [pair for pair in pair_rows.values() if all(arm in pair for arm in ARMS)]
    native_correct = sum(pair["native"].get("correct") == "yes" for pair in pairs)
    my_guy_correct = sum(pair["my-guy"].get("correct") == "yes" for pair in pairs)
    if not pairs:
        route_gate = "unmet (zero scorable pairs)"
    else:
        route_gate = "pass" if my_guy_correct >= native_correct else "fail"
    stop_events = sum(
        result[arm][field]
        for arm in ARMS
        for field in ("safety_stop_suggestions", "unauthorized_actions", "privacy_breaches")
    )
    result.update({
        "participants": len(participants),
        "paired": {
            "scorable_pairs": len(pairs),
            "native_correct": native_correct,
            "my_guy_correct": my_guy_correct,
            "route_gate": route_gate,
        },
        "evidence_gate": (
            "pass" if result["my-guy"]["actionable_without_evidence"] == 0 else "fail"
        ),
        "stop_events": stop_events,
        "notice": "Small self-selected sample; no superiority claim (docs/PILOT.md).",
    })
    return result


def _load_rows(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PilotError(f"cannot read scorecard {path}: {exc}") from exc
    rows = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PilotError(f"invalid scorecard row {line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise PilotError(f"invalid scorecard row {line_number}: expected object")
        rows.append(row)
    return rows


def _summarize(args: argparse.Namespace) -> int:
    print(json.dumps(_aggregate(_load_rows(Path(args.scorecard))), indent=2))
    return 0


def _pool(args: argparse.Namespace) -> int:
    summaries = [_read_json(Path(path)) for path in args.summaries]
    pooled: dict[str, Any] = {
        "participants": sum(int(summary.get("participants", 0)) for summary in summaries),
        "native": _empty_arm(),
        "my-guy": _empty_arm(),
        "paired": {
            "scorable_pairs": 0,
            "native_correct": 0,
            "my_guy_correct": 0,
        },
        "stop_events": sum(int(summary.get("stop_events", 0)) for summary in summaries),
        "notice": "Small self-selected sample; no superiority claim (docs/PILOT.md).",
    }
    for arm in ARMS:
        output = pooled[arm]
        for field in (
            "rows", "correct", "misses", "strict_unsafe_actionable",
            "safety_stop_suggestions", "unauthorized_actions", "privacy_breaches",
            "actionable_without_evidence", "deviations",
        ):
            output[field] = sum(int(summary.get(arm, {}).get(field, 0)) for summary in summaries)
        decisions: Counter[str] = Counter()
        for summary in summaries:
            decisions.update(summary.get(arm, {}).get("decisions", {}))
        output["decisions"] = dict(sorted(decisions.items()))
        output["measurements"] = {}
        for measurement in MEASUREMENTS:
            medians: list[float | int] = []
            unavailable = 0
            for summary in summaries:
                data = summary.get(arm, {}).get("measurements", {}).get(measurement, {})
                unavailable += int(data.get("unavailable", 0))
                values = data.get("participant_medians")
                if isinstance(values, list):
                    medians.extend(value for value in values if isinstance(value, (int, float)))
                elif data.get("median") is not None:
                    medians.append(data["median"])
            output["measurements"][measurement] = {
                "median_of_participant_medians": median(medians) if medians else None,
                "unavailable": unavailable,
            }
    for summary in summaries:
        paired = summary.get("paired", {})
        for field in ("scorable_pairs", "native_correct", "my_guy_correct"):
            pooled["paired"][field] += int(paired.get(field, 0))
    if pooled["paired"]["scorable_pairs"] == 0:
        pooled["paired"]["route_gate"] = "unmet (zero scorable pairs)"
    else:
        pooled["paired"]["route_gate"] = (
            "pass"
            if pooled["paired"]["my_guy_correct"] >= pooled["paired"]["native_correct"]
            else "fail"
        )
    pooled["evidence_gate"] = (
        "pass" if pooled["my-guy"]["actionable_without_evidence"] == 0 else "fail"
    )
    print(json.dumps(pooled, indent=2))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("out_dir")
    freeze.add_argument("--tasks", type=int, required=True)
    freeze.add_argument("--seed", type=int)
    freeze.add_argument("--consent-confirmed", action="store_true")
    freeze.set_defaults(handler=_freeze)

    record = subparsers.add_parser("record")
    record.add_argument("scorecard")
    record.add_argument("--protocol", required=True)
    record.add_argument("--participant", required=True)
    record.add_argument("--task", required=True)
    record.add_argument("--arm", choices=ARMS, required=True)
    record.add_argument("--category", required=True)
    record.add_argument("--acceptable", action="append", required=True)
    record.add_argument("--decision", choices=DECISIONS, required=True)
    for field in YES_NO_FIELDS:
        record.add_argument(f"--{field.replace('_', '-')}", required=True)
    record.add_argument("--evidence-inspectable", required=True)
    for field in MEASUREMENTS:
        record.add_argument(f"--{field.replace('_', '-')}", required=True)
    record.add_argument("--deviation")
    record.set_defaults(handler=_record)

    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("scorecard")
    summarize.set_defaults(handler=_summarize)

    pool = subparsers.add_parser("pool")
    pool.add_argument("summaries", nargs="+")
    pool.set_defaults(handler=_pool)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    try:
        return args.handler(args)
    except (PilotError, OSError, ValueError, KeyError) as exc:
        return _error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
