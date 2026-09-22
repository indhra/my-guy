import json

from router.cli import main


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
