"""Tests for the consent-gated local pilot scorecard tooling."""

import json
import stat
from datetime import datetime, timezone

from scripts.pilot import main


def freeze(tmp_path, *, consent=True, tasks=2):
    out_dir = tmp_path / "protocols"
    args = ["freeze", str(out_dir), "--tasks", str(tasks), "--seed", "7"]
    if consent:
        args.append("--consent-confirmed")
    assert main(args) == 0
    return out_dir / f"protocol-{datetime.now(timezone.utc).date().isoformat()}.json"


def record_args(scorecard, protocol, *, participant="P01", task="T1", arm="native",
                category="code review", acceptable=("clarify",), decision="clarify",
                correct="yes", evidence="yes", route_seconds="2",
                steps="3", tool_calls="4", tokens="5", deviation=None, **flags):
    args = [
        "record", str(scorecard), "--protocol", str(protocol),
        "--participant", participant, "--task", task, "--arm", arm,
        "--category", category,
    ]
    for route in acceptable:
        args.extend(["--acceptable", route])
    args.extend(["--decision", decision])
    for field in ("correct", "unsafe-actionable", "safety-stop",
                  "unauthorized-action", "privacy-breach"):
        key = field.replace("-", "_")
        default = correct if key == "correct" else "no"
        args.extend([f"--{field}", flags.get(key, default)])
    args.extend([
        "--evidence-inspectable", evidence,
        "--route-seconds", route_seconds, "--steps", steps,
        "--tool-calls", tool_calls, "--tokens", tokens,
    ])
    if deviation is not None:
        args.extend(["--deviation", deviation])
    return args


def test_freeze_is_deterministic_and_refuses_overwrite(tmp_path, capsys):
    protocol = freeze(tmp_path)
    payload = json.loads(protocol.read_text())
    assert payload["arm_order"] == {
        "T1": ["my-guy", "native"],
        "T2": ["native", "my-guy"],
    }
    assert stat.S_IMODE(protocol.stat().st_mode) == 0o600
    assert stat.S_IMODE(protocol.parent.stat().st_mode) == 0o700
    assert main(["freeze", str(protocol.parent), "--tasks", "2", "--seed", "7"]) == 2
    assert "overwrite" in capsys.readouterr().err


def test_record_requires_consent_and_known_task(tmp_path, capsys):
    protocol = freeze(tmp_path, consent=False)
    scorecard = tmp_path / "scorecard.jsonl"
    args = record_args(scorecard, protocol)
    assert main(args) == 2
    assert "consent" in capsys.readouterr().err
    protocol = freeze(tmp_path / "other", tasks=1)
    args = record_args(scorecard, protocol, task="T2")
    assert main(args) == 2
    assert "not in the protocol" in capsys.readouterr().err


def test_record_rejects_path_email_and_long_token_text(tmp_path, capsys):
    protocol = freeze(tmp_path)
    scorecard = tmp_path / "scorecard.jsonl"
    for category in ("private/path", "person@example.test", "x" * 20):
        assert main(record_args(scorecard, protocol, category=category)) == 2
        assert "sanitize" in capsys.readouterr().err


def test_unavailable_is_stored_as_null_and_duplicate_is_rejected(tmp_path, capsys):
    protocol = freeze(tmp_path)
    scorecard = tmp_path / "scorecard.jsonl"
    args = record_args(scorecard, protocol, route_seconds="unavailable")
    assert main(args) == 0
    row = json.loads(scorecard.read_text().splitlines()[0])
    assert row["route_seconds"] is None
    assert main(args) == 2
    assert "duplicate" in capsys.readouterr().err


def test_stop_flag_records_row_and_returns_three(tmp_path, capsys):
    protocol = freeze(tmp_path)
    scorecard = tmp_path / "scorecard.jsonl"
    args = record_args(scorecard, protocol, **{"safety_stop": "yes"})
    assert main(args) == 3
    assert len(scorecard.read_text().splitlines()) == 1
    assert "STOP: safety-stop" in capsys.readouterr().err


def test_summarize_aggregates_without_leaking_codes_or_free_text(tmp_path, capsys):
    protocol = freeze(tmp_path)
    scorecard = tmp_path / "scorecard.jsonl"
    assert main(record_args(
        scorecard, protocol, category="secret category", acceptable=("clarify",),
    )) == 0
    assert main(record_args(
        scorecard, protocol, participant="P01", arm="my-guy",
        category="another secret", acceptable=("clarify",), decision="recommend",
        correct="no", evidence="no", route_seconds="unavailable",
    )) == 0
    assert main(["summarize", str(scorecard)]) == 0
    output = capsys.readouterr().out
    summary = json.loads(output)
    assert summary["participants"] == 1
    assert summary["native"]["rows"] == 1
    assert summary["my-guy"]["actionable_without_evidence"] == 1
    assert summary["evidence_gate"] == "fail"
    assert "secret category" not in output
    assert "P01" not in output
    assert "T1" not in output


def test_zero_pairs_and_failing_route_gate(tmp_path, capsys):
    protocol = freeze(tmp_path)
    scorecard = tmp_path / "scorecard.jsonl"
    assert main(record_args(scorecard, protocol)) == 0
    assert main(["summarize", str(scorecard)]) == 0
    assert "unmet (zero scorable pairs)" in capsys.readouterr().out
    assert main(record_args(
        scorecard, protocol, participant="P02", arm="my-guy", correct="no",
    )) == 0
    assert main(record_args(
        scorecard, protocol, participant="P02", arm="native", correct="yes",
    )) == 0
    assert main(["summarize", str(scorecard)]) == 0
    assert json.loads(capsys.readouterr().out)["paired"]["route_gate"] == "fail"


def test_pool_sums_two_summaries(tmp_path, capsys):
    protocol = freeze(tmp_path)
    summaries = []
    for index, participant in enumerate(("P01", "P02")):
        scorecard = tmp_path / f"scorecard-{index}.jsonl"
        assert main(record_args(scorecard, protocol, participant=participant)) == 0
        assert main(["summarize", str(scorecard)]) == 0
        summary_path = tmp_path / f"summary-{index}.json"
        summary_path.write_text(capsys.readouterr().out)
        summaries.append(str(summary_path))
    assert main(["pool", *summaries]) == 0
    pooled = json.loads(capsys.readouterr().out)
    assert pooled["participants"] == 2
    assert pooled["native"]["rows"] == 2
    assert pooled["paired"]["route_gate"] == "unmet (zero scorable pairs)"
