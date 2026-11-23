import json

from router.cli import _decision_payload, main
from router.models import Capability, RouteDecision


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


def test_cli_prepares_claude_handoff_for_codex_request(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "home"))
    skills = tmp_path / ".claude" / "skills"
    skill = skills / "threat-review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: threat-review\ndescription: Review security threats.\n---\n"
    )
    assert main(["config", "--add-root", "claude", str(skills), "local"]) == 0
    capsys.readouterr()

    assert main(["route", "--host", "codex", "--json", "Review", "security", "threats"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "recommend"
    assert payload["handoff"]["requesting_host"] == "codex"
    assert payload["handoff"]["target_host"] == "claude"
    assert payload["handoff"]["cross_host"] is True
    assert payload["handoff"]["approval_required"] is True
    assert payload["handoff"]["status"] == "prepared"
    assert payload["evidence"][0]["hosts"] == ["claude"]


def test_cli_list_exposes_capability_kind_and_host(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "home"))
    skills = tmp_path / ".claude" / "skills"
    skill = skills / "threat-review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: threat-review\ndescription: Review security threats.\n---\n")
    assert main(["config", "--add-root", "claude", str(skills), "local"]) == 0
    capsys.readouterr()
    assert main(["list", "threat-review"]) == 0
    entries = json.loads(capsys.readouterr().out)
    assert entries
    assert entries[0]["kind"] == "skill"
    assert entries[0]["hosts"] == ["claude"]
    assert entries[0]["source"]
    assert entries[0]["trust"] == "local"


def test_cli_text_caps_broad_route_but_json_keeps_all_candidates(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "home"))
    capabilities = tuple(
        Capability(
            f"cap-{index:02}", "fixture", "Review security", (),
            ("review", "security"), f"skill:cap-{index:02}", "local",
        )
        for index in range(12)
    )
    monkeypatch.setattr("router.cli._seed_capabilities", lambda: ())
    monkeypatch.setattr("router.cli.discover_inventory", lambda config: capabilities)

    assert main(["route", "Review", "security"]) == 0
    text_output = capsys.readouterr().out
    assert "12 candidates matched; showing the first 10" in text_output
    assert text_output.count("\n- ") == 10
    assert "Use --json" in text_output

    assert main(["route", "--json", "Review", "security"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["candidates"]) == 12
    assert len(payload["evidence"]) == 12


def test_cli_cross_host_alternatives_prioritize_actionable_matches():
    capabilities = (
        Capability("unverified", "outside", "Review security", (),
                   ("review", "security"), "skill:unverified", "unverified", hosts=("claude",)),
        Capability("trusted-weak", "local", "Review", (),
                   ("review",), "skill:trusted-weak", "local", hosts=("claude",)),
        Capability("unknown-host", "custom", "Review security", (),
                   ("review", "security"), "skill:unknown-host", "local", hosts=()),
        Capability("trusted-strong", "local", "Review security", (),
                   ("review", "security"), "skill:trusted-strong", "local", hosts=("claude",)),
    )
    decision = RouteDecision("clarify", "Review security", (), "Needs review", 0.0)
    matches = _decision_payload(decision, capabilities, "codex")["cross_host_matches"]
    assert [match["id"] for match in matches] == [
        "trusted-strong", "trusted-weak", "unknown-host", "unverified"
    ]
    assert [match["actionable"] for match in matches] == [True, True, False, False]
    assert matches[2]["availability"] == "host_unknown"
    assert matches[3]["availability"] == "provenance_required"


def test_cli_config_records_explicit_skill_and_agent_hosts(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "home"))
    skills = tmp_path / "skills"
    agents = tmp_path / "agents"
    assert main(["config", "--add-root", "skills", str(skills), "local",
                 "--hosts", "codex,claude"]) == 0
    capsys.readouterr()
    assert main(["config", "--add-agent-root", "agents", str(agents), "local", "opencode"]) == 0
    config = json.loads(capsys.readouterr().out)
    roots = {root["name"]: root for root in config["roots"]}
    assert roots["skills"]["kind"] == "skill"
    assert roots["skills"]["hosts"] == ["codex", "claude"]
    assert roots["agents"]["kind"] == "agent"
    assert roots["agents"]["hosts"] == ["opencode"]


def test_cli_broad_json_is_bounded_with_opt_in_full_result(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MY_GUY_HOME", str(tmp_path / "home"))
    capabilities = tuple(
        Capability(
            f"cap-{index:04}", "fixture", "Review security", (),
            ("review", "security"), f"skill:cap-{index:04}", "local",
        )
        for index in range(250)
    )
    monkeypatch.setattr("router.cli._seed_capabilities", lambda: ())
    monkeypatch.setattr("router.cli.discover_inventory", lambda config: capabilities)

    assert main(["route", "--json", "Review", "security"]) == 0
    bounded_output = capsys.readouterr().out
    bounded = json.loads(bounded_output)
    assert bounded["candidate_total"] == 250
    assert bounded["candidates_truncated"] is True
    assert len(bounded["candidates"]) == 20
    assert len(bounded["evidence"]) == 20
    assert len(bounded["reason"]) < 300
    assert len(bounded_output) < 12000

    assert main(["route", "--json", "--all", "Review", "security"]) == 0
    complete = json.loads(capsys.readouterr().out)
    assert complete["candidate_total"] == 250
    assert complete["candidates_truncated"] is False
    assert len(complete["candidates"]) == 250
    assert len(complete["evidence"]) == 250


def test_cross_host_json_reports_truncation_without_losing_full_opt_in():
    capabilities = tuple(
        Capability(
            f"claude-{index:02}", "fixture", "Review security", (),
            ("review", "security"), f"skill:claude-{index:02}", "local",
            hosts=("claude",),
        )
        for index in range(25)
    )
    decision = RouteDecision("clarify", "Review security", (), "Needs review", 0.0)
    bounded = _decision_payload(decision, capabilities, "codex")
    complete = _decision_payload(decision, capabilities, "codex", include_all=True)
    assert bounded["cross_host_match_total"] == 25
    assert bounded["cross_host_matches_truncated"] is True
    assert len(bounded["cross_host_matches"]) == 20
    assert complete["cross_host_matches_truncated"] is False
    assert len(complete["cross_host_matches"]) == 25
