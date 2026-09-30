import json
import io
import os

import pytest

from router.cli import main


REQUEST_LIMIT = 1_048_576


@pytest.fixture(autouse=True)
def private_skill_fixture_umask():
    previous = os.umask(0o022)
    try:
        yield
    finally:
        os.umask(previous)


def test_version_status_doctor_and_dry_run_are_read_only(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    state = tmp_path / "state"
    monkeypatch.setenv("MY_GUY_HOME", str(state))
    root = tmp_path / ".codex" / "skills"

    assert main(["--version"]) == 0
    assert "my-guy" in capsys.readouterr().out
    assert main(["status", "codex", "--root", str(root), "--json"]) == 1
    status = json.loads(capsys.readouterr().out)
    assert status["state"] == "missing"
    assert status["target"] == str(root / "my-guy" / "SKILL.md")
    assert status["summary"] and status["next_actions"]
    assert not state.exists() and not root.exists()

    assert main(["install", "codex", "--root", str(root), "--dry-run"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["state"] == "missing"
    assert not state.exists() and not root.exists()

    assert main(["doctor", "--harness", "codex", "--root", str(root)]) == 1
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["package_version"]
    assert doctor["installation"]["state"] == "missing"
    assert "unverified" in doctor["routing_readiness"]


def test_install_requires_explicit_custom_root_and_rejects_host_mismatch(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "state"))
    custom = tmp_path / "custom-skills"
    assert main(["install", "codex", "--root", str(custom)]) == 2
    assert "allow-custom-root" in capsys.readouterr().err
    assert main(["install", "codex", "--root", str(custom), "--allow-custom-root"]) == 0
    assert json.loads(capsys.readouterr().out)["target"] == str(custom / "my-guy" / "SKILL.md")

    wrong = tmp_path / ".claude" / "skills"
    assert main(["install", "codex", "--root", str(wrong), "--allow-custom-root"]) == 2
    assert "claude" in capsys.readouterr().err
    assert not wrong.exists()

    alias = wrong / ".." / "skills"
    assert main(["install", "codex", "--root", str(alias), "--allow-custom-root"]) == 2
    assert "claude" in capsys.readouterr().err


def test_route_stdin_keeps_shell_text_as_data(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("sys.stdin", io.StringIO("Review security authentication $(touch /tmp/should-not-run)"))
    assert main(["route", "--stdin", "--json"]) == 0
    assert "$(touch /tmp/should-not-run)" in json.loads(capsys.readouterr().out)["request"]
    assert main(["route", "--stdin", "and", "more"]) == 2
    assert "cannot be combined" in capsys.readouterr().err


@pytest.mark.parametrize("source", ["stdin", "positional"])
def test_route_accepts_exact_raw_request_limit(monkeypatch, tmp_path, capsys, source):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "state"))
    request = "x" * REQUEST_LIMIT
    if source == "stdin":
        monkeypatch.setattr("sys.stdin", io.StringIO(request))
        args = ["route", "--stdin", "--json"]
    else:
        args = ["route", "--json", request]

    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["request"] == request


@pytest.mark.parametrize("source", ["stdin", "positional"])
def test_route_rejects_oversized_raw_request_before_stripping(monkeypatch, tmp_path, capsys, source):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "state"))
    request = "Review security authentication" + " " * REQUEST_LIMIT + "Do not route this request"
    if source == "stdin":
        monkeypatch.setattr("sys.stdin", io.StringIO(request))
        args = ["route", "--stdin", "--json"]
    else:
        args = ["route", "--json", request]

    assert main(args) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "exceeds 1,048,576 characters" in output.err
    assert len(output.err) < 200


def test_route_rejects_one_char_over_limit_and_whitespace_only(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("sys.stdin", io.StringIO("x" * (REQUEST_LIMIT + 1)))
    assert main(["route", "--stdin"]) == 2
    assert "exceeds 1,048,576 characters" in capsys.readouterr().err

    monkeypatch.setattr("sys.stdin", io.StringIO(" " * REQUEST_LIMIT))
    assert main(["route", "--stdin"]) == 2
    assert "non-empty" in capsys.readouterr().err

    monkeypatch.setattr("sys.stdin", io.StringIO(" " * (REQUEST_LIMIT + 1)))
    assert main(["route", "--stdin"]) == 2
    assert "exceeds 1,048,576 characters" in capsys.readouterr().err


def test_doctor_requires_a_discovered_trusted_capability(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "state"))
    root = tmp_path / "empty-skills"
    root.mkdir()
    assert main(["config", "--add-root", "reviewed", str(root), "local"]) == 0
    capsys.readouterr()
    assert main(["doctor"]) == 1
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["status"] == "needs_capabilities"
    assert doctor["summary"] and doctor["next_actions"]
    assert doctor["trusted_capability_count"] == 0
    skill = root / "security" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("---\nname: security\ndescription: Review authentication security.\n---\n")
    assert main(["doctor"]) == 0
    assert json.loads(capsys.readouterr().out)["trusted_capability_count"] == 1


def test_doctor_reports_retargeted_trusted_root(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "state"))
    root = tmp_path / "trusted"
    skill = root / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: review\ndescription: Review security.\n---\n")
    assert main(["config", "--add-root", "trusted", str(root), "local"]) == 0
    capsys.readouterr()
    moved = tmp_path / "moved"
    root.rename(moved)
    root.symlink_to(moved, target_is_directory=True)
    assert main(["doctor"]) == 1
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["trusted_capability_count"] == 0
    assert doctor["roots"][0]["safe"] is False
    assert "symlinked" in " ".join(doctor["next_actions"])


def test_doctor_reports_shared_writable_trusted_root(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "state"))
    root = tmp_path / "trusted"
    skill = root / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: review\ndescription: Review security.\n---\n")
    assert main(["config", "--add-root", "trusted", str(root), "local"]) == 0
    capsys.readouterr()
    root.chmod(0o777)
    assert main(["doctor"]) == 1
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["trusted_capability_count"] == 0
    assert doctor["roots"][0]["safe"] is False
    assert "writable" in " ".join(doctor["next_actions"])


def test_doctor_reports_mutable_trusted_skill_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "state"))
    root = tmp_path / "trusted"
    skill = root / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: review\ndescription: Review security authentication.\n---\n")
    skill.chmod(0o666)

    assert main(["config", "--add-root", "trusted", str(root), "local"]) == 0
    capsys.readouterr()
    assert main(["doctor"]) == 1
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["trusted_capability_count"] == 0
    assert doctor["status"] == "blocked"
    assert any(str(skill) in action and "writable" in action for action in doctor["next_actions"])


def test_state_home_beneath_shared_writable_ancestor_is_rejected(monkeypatch, tmp_path, capsys):
    shared = tmp_path / "shared"
    shared.mkdir()
    shared.chmod(0o777)
    state = shared / "private-state"
    state.mkdir(mode=0o700)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(state))

    assert main(["route", "Review", "security"]) == 2
    assert "shared-writable" in capsys.readouterr().err
    assert main(["doctor"]) == 1
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["state_home_safe"] is False
    assert any("shared-writable" in action for action in doctor["next_actions"])


def test_state_home_beneath_symlinked_ancestor_is_rejected(monkeypatch, tmp_path, capsys):
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    link = tmp_path / "linked"
    link.symlink_to(real, target_is_directory=True)
    monkeypatch.setenv("MY_GUY_HOME", str(link / "state"))

    assert main(["route", "Review", "security"]) == 2
    assert "symlinked" in capsys.readouterr().err


def test_status_and_doctor_report_install_root_that_became_unsafe(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "state"))
    root = tmp_path / ".codex" / "skills"
    args = ["codex", "--root", str(root)]
    assert main(["install", *args]) == 0
    capsys.readouterr()
    root.chmod(0o777)

    assert main(["status", *args, "--json"]) == 1
    status = json.loads(capsys.readouterr().out)
    assert status["state"] == "unsafe"
    assert "shared-writable" in status["summary"]
    assert main(["doctor", "--harness", "codex", "--root", str(root)]) == 1
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["installation"]["state"] == "unsafe"
    assert doctor["status"] != "ready"


@pytest.mark.parametrize("disabled", [False, True])
def test_status_and_doctor_report_mutable_installed_skill(monkeypatch, tmp_path, capsys, disabled):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "state"))
    root = tmp_path / ".codex" / "skills"
    args = ["codex", "--root", str(root)]
    assert main(["install", *args]) == 0
    capsys.readouterr()
    if disabled:
        assert main(["disable", *args]) == 0
        capsys.readouterr()
    target = root / "my-guy" / "SKILL.md"
    if disabled:
        target = target.with_suffix(".md.disabled")
    target.chmod(0o664)

    assert main(["status", *args, "--json"]) == 1
    status = json.loads(capsys.readouterr().out)
    assert status["state"] == "unsafe"
    assert not status["owned"]
    assert main(["doctor", "--harness", "codex", "--root", str(root)]) == 1
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["installation"]["state"] == "unsafe"
    assert doctor["status"] != "ready"


def test_route_prepares_approval_gated_cross_host_handoff(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "home"))
    skills = tmp_path / ".claude" / "skills"
    monkeypatch.setattr("router.cli._seed_capabilities", lambda: ())
    skill = skills / "threat-review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: threat-review\ndescription: Review security threats.\n---\n")

    assert main(["config", "--add-root", "claude", str(skills), "local", "--hosts", "claude"]) == 0
    capsys.readouterr()
    assert main(["route", "--host", "codex", "--json", "Review", "security", "threats"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "recommend"
    assert payload["handoff"]["requesting_host"] == "codex"
    assert payload["handoff"]["target_host"] == "claude"
    assert payload["handoff"]["cross_host"] is True
    assert payload["handoff"]["approval_required"] is True
    assert payload["evidence"][0]["hosts"] == ["claude"]


def test_config_persists_explicit_hosts_for_skill_and_agent_roots(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "home"))
    assert main(["config", "--add-root", "skills", str(tmp_path / "skills"), "local",
                 "--hosts", "codex,claude"]) == 0
    capsys.readouterr()
    assert main(["config", "--add-agent-root", "agents", str(tmp_path / "agents"), "local", "opencode"]) == 0
    roots = {root["name"]: root for root in json.loads(capsys.readouterr().out)["roots"]}
    assert roots["skills"]["kind"] == "skill"
    assert roots["skills"]["hosts"] == ["codex", "claude"]
    assert roots["agents"]["kind"] == "agent"
    assert roots["agents"]["hosts"] == ["opencode"]


def test_route_json_bounds_candidates_and_all_opts_in(monkeypatch, tmp_path, capsys):
    from router.models import Capability

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "home"))
    capabilities = tuple(
        Capability(
            f"cap-{index:03}", "fixture", "Review security", (),
            ("review", "security"), f"skill:cap-{index:03}", "local",
        )
        for index in range(30)
    )
    monkeypatch.setattr("router.cli._seed_capabilities", lambda: ())
    monkeypatch.setattr("router.cli.discover_inventory", lambda config: capabilities)

    assert main(["route", "--json", "Review", "security"]) == 0
    bounded = json.loads(capsys.readouterr().out)
    assert bounded["candidate_total"] == 30
    assert bounded["candidates_truncated"] is True
    assert len(bounded["candidates"]) == 20
    assert len(bounded["evidence"]) == 20

    assert main(["route", "--json", "--all", "Review", "security"]) == 0
    full = json.loads(capsys.readouterr().out)
    assert full["candidates_truncated"] is False
    assert len(full["candidates"]) == 30


def test_route_all_requires_json(capsys):
    assert main(["route", "--all", "Review", "security"]) == 2
    assert "--all requires --json" in capsys.readouterr().err


def test_doctor_private_state_rule_matches_route(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    state = tmp_path / "state"
    monkeypatch.setenv("MY_GUY_HOME", str(state))
    root = tmp_path / "trusted"
    skill = root / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: review\ndescription: Review security.\n---\n")
    assert main(["config", "--add-root", "trusted", str(root), "local"]) == 0
    capsys.readouterr()
    state.chmod(0o755)
    assert main(["doctor"]) == 1
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["status"] == "blocked"
    assert doctor["state_home_safe"] is False
    assert main(["route", "Review", "security"]) == 2
    assert "group/world" in capsys.readouterr().err


def test_cli_owned_uninstall_and_rollback(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "state"))
    root = tmp_path / ".claude" / "skills"
    args = ["claude", "--root", str(root)]
    assert main(["install", *args]) == 0
    capsys.readouterr()
    assert main(["status", *args, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "ready"
    assert main(["uninstall", *args]) == 0
    capsys.readouterr()
    assert main(["status", *args, "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["state"] == "missing"
    assert main(["rollback", *args]) == 0
    capsys.readouterr()
    assert main(["status", *args, "--json"]) == 0


def test_cli_is_a_memorable_front_door(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "home"))
    skills = tmp_path / "skills"
    skill = skills / "security" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: security-review\ndescription: Review authentication security threats.\n---\n"
    )
    assert main(["config", "--add-root", "trusted", str(skills), "local"]) == 0
    capsys.readouterr()
    assert main(["Review", "authentication", "security"]) == 0
    output = capsys.readouterr().out
    assert "RECOMMEND" in output
    assert "security-review" in output


def test_seed_directory_does_not_claim_uninstalled_capabilities(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "home"))
    assert main(["Review", "authentication", "security"]) == 0
    assert "CLARIFY" in capsys.readouterr().out


def test_cli_sync_json_and_feedback_gate(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "home"))
    assert main(["sync"]) == 0
    synced = json.loads(capsys.readouterr().out)
    assert synced["discovered"] >= 3

    assert main(["feedback", "security-review", "accepted", "private", "request"]) == 2
    assert "opts in" in capsys.readouterr().err
