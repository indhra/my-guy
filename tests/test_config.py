import json

import pytest

from router.config import RouterConfig, SkillRoot, default_roots, load_config, save_config
from router.lifecycle import standard_skill_roots


def test_opencode_default_root_uses_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    xdg_skills = tmp_path / "xdg" / "opencode" / "skills"
    xdg_skills.mkdir(parents=True)

    roots = default_roots(home=tmp_path, project=tmp_path)
    assert any(root.name == "opencode" and root.path == str(xdg_skills) for root in roots)
    assert str(standard_skill_roots()["opencode"]) == str(xdg_skills)


def test_opencode_default_root_falls_back_to_home_config(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    monkeypatch.setenv("HOME", str(tmp_path))
    fallback = tmp_path / ".config" / "opencode" / "skills"
    fallback.mkdir(parents=True)

    roots = default_roots(home=tmp_path, project=tmp_path)
    assert any(root.name == "opencode" and root.path == str(fallback) for root in roots)
    assert standard_skill_roots()["opencode"] == fallback


def test_config_round_trip_is_private_and_validated(tmp_path):
    path = tmp_path / "config.json"
    expected = RouterConfig(feedback_enabled=True, roots=(SkillRoot("codex", "/skills", "local"),))
    save_config(expected, path)
    assert load_config(path) == expected
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())["schema_version"] == 1


def test_config_rejects_duplicate_or_invalid_roots():
    with pytest.raises(ValueError):
        SkillRoot("../escape", "/tmp")
    with pytest.raises(ValueError):
        RouterConfig(roots=(SkillRoot("same", "/one"), SkillRoot("same", "/two")))
    with pytest.raises(ValueError):
        SkillRoot("relative", "skills")
