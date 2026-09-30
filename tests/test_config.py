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


def test_skill_roots_round_trip_host_and_kind_metadata(tmp_path):
    path = tmp_path / "nested" / "config.json"
    root = SkillRoot(
        "codex-agents", str(tmp_path), "local", kind="agent", hosts=("codex",)
    )
    save_config(RouterConfig(roots=(root,)), path)
    assert load_config(path).roots == (root,)


def test_skill_root_host_metadata_is_validated():
    with pytest.raises(ValueError):
        SkillRoot("unknown-host", "/tmp", hosts=("bogus",))
    with pytest.raises(ValueError):
        SkillRoot("duplicate-host", "/tmp", hosts=("codex", "codex"))
    with pytest.raises(ValueError):
        SkillRoot("ambiguous-agent", "/tmp", kind="agent", hosts=("codex", "claude"))
    with pytest.raises(ValueError):
        SkillRoot("unknown-agent", "/tmp", kind="agent", hosts=None)


def test_skill_root_rejects_symlinked_path_component(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        SkillRoot("linked", str(linked / "skills"))


def test_load_config_rejects_symlinked_root_path(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {"roots": [{"name": "linked", "path": str(linked / "skills"), "trust": "local"}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="symlinks"):
        load_config(path)


def test_default_roots_declare_host_coverage(monkeypatch, tmp_path):
    xdg_home = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_home))
    project = tmp_path / "project"
    root_paths = (
        tmp_path / ".agents" / "skills",
        tmp_path / ".codex" / "skills",
        tmp_path / ".claude" / "skills",
        xdg_home / "opencode" / "skills",
        project / ".agents" / "skills",
        project / ".codex" / "skills",
        project / ".claude" / "skills",
        project / ".opencode" / "skills",
    )
    for root_path in root_paths:
        root_path.mkdir(parents=True)
    roots = default_roots(home=tmp_path, project=project)
    by_name = {root.name: root for root in roots}
    assert by_name["agents"].hosts is None
    assert by_name["codex"].hosts == ("codex",)
    assert by_name["opencode"].hosts == ("opencode",)
    assert by_name["project-agents"].hosts is None


def test_config_rejects_duplicate_or_invalid_roots():
    with pytest.raises(ValueError):
        SkillRoot("../escape", "/tmp")
    with pytest.raises(ValueError):
        RouterConfig(roots=(SkillRoot("same", "/one"), SkillRoot("same", "/two")))
    with pytest.raises(ValueError):
        SkillRoot("relative", "skills")
