from pathlib import Path

import pytest

from router.lifecycle import SkillInstaller


def test_install_upgrade_disable_and_rollback_are_reversible(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("version one", encoding="utf-8")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"

    installed = installer.install("codex", root)
    target = Path(installed.target)
    assert target.read_text() == "version one"

    source.write_text("version two", encoding="utf-8")
    installer.upgrade("codex", root)
    assert target.read_text() == "version two"
    installer.rollback("codex", root)
    assert target.read_text() == "version one"

    installer.disable("codex", root)
    assert not target.exists()
    assert target.with_suffix(".md.disabled").exists()
    installer.rollback("codex", root)
    assert target.exists()


def test_installer_rejects_unknown_harness_and_symlink_target(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("safe", encoding="utf-8")
    installer = SkillInstaller(tmp_path / "state", source)
    with pytest.raises(ValueError):
        installer.install("openrouter", tmp_path / "skills")

    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(PermissionError):
        installer.install("codex", linked)


def test_rollback_history_is_scoped_to_exact_install_root(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("one", encoding="utf-8")
    installer = SkillInstaller(tmp_path / "state", source)
    first = tmp_path / "first"
    second = tmp_path / "second"
    installer.install("codex", first)
    source.write_text("two", encoding="utf-8")
    installer.install("codex", second)
    installer.rollback("codex", second)
    assert (first / "my-guy" / "SKILL.md").read_text() == "one"
    assert not (second / "my-guy" / "SKILL.md").exists()
