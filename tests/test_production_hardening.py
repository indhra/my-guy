import json
from pathlib import Path

import pytest

from router.feedback import FeedbackStore
from router.lifecycle import SkillInstaller
from router.catalog import CapabilityCatalog
from router.cli import main


def test_feedback_files_are_private_and_fingerprints_are_keyed(tmp_path):
    first = FeedbackStore(tmp_path / "first.sqlite3")
    second = FeedbackStore(tmp_path / "second.sqlite3")
    for store in (first, second):
        store.record("guessable request", "security", "accepted", consent=True)
    first_digest = first.connection.execute("SELECT request_digest FROM route_feedback").fetchone()[0]
    second_digest = second.connection.execute("SELECT request_digest FROM route_feedback").fetchone()[0]
    assert first_digest != second_digest
    assert (tmp_path / "first.sqlite3").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "first.sqlite3.key").stat().st_mode & 0o777 == 0o600
    first.close()
    second.close()


def test_corrupt_rollback_snapshot_preserves_current_installation(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("one", encoding="utf-8")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    installer.install("codex", root)
    source.write_text("two", encoding="utf-8")
    installer.upgrade("codex", root)
    target = root / "my-guy" / "SKILL.md"
    history_root = tmp_path / "state" / "history" / "codex"
    history = next(history_root.iterdir())
    latest = sorted(history.glob("*.json"))[-1]
    record = json.loads(latest.read_text(encoding="utf-8"))["enabled"]
    (history / record["file"]).unlink()
    with pytest.raises(FileNotFoundError):
        installer.rollback("codex", root)
    assert target.read_text(encoding="utf-8") == "two"


def test_checked_in_and_packaged_registries_match():
    project = Path(__file__).parents[1]
    checked_in = json.loads((project / "registry" / "capabilities.json").read_text())
    packaged = json.loads((project / "router" / "resources" / "capabilities.json").read_text())
    assert checked_in == packaged


def test_catalog_file_is_private(tmp_path):
    path = tmp_path / "catalog.sqlite3"
    catalog = CapabilityCatalog(path)
    assert path.stat().st_mode & 0o777 == 0o600
    catalog.close()


def test_installer_rejects_broad_root(tmp_path, monkeypatch):
    source = tmp_path / "source.md"
    source.write_text("safe", encoding="utf-8")
    installer = SkillInstaller(tmp_path / "state", source)
    with pytest.raises(ValueError):
        installer.install("codex", Path("/"))


def test_cli_rejects_insecure_existing_state_directory(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state"
    state.mkdir(mode=0o755)
    monkeypatch.setenv("MY_GUY_HOME", str(state))
    assert main(["sync"]) == 2
    assert "must not be group/world accessible" in capsys.readouterr().err
