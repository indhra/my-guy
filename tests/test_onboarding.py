import os

import pytest

from router import onboarding
from router.config import RouterConfig, SkillRoot
from router.lifecycle import SkillInstaller
from router.onboarding import collect_roots, guided_init


def _write_skill(root, name, description):
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\nBody.\n",
        encoding="utf-8",
    )


def _installer(tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700, exist_ok=True)
    return SkillInstaller(state)


def _harness_roots(tmp_path, root):
    return {
        "claude": root,
        "codex": tmp_path / "codex-skills",
        "opencode": tmp_path / "opencode-skills",
        "agents": tmp_path / "agents-skills",
    }


def test_collect_roots_unions_configured_and_detected_defaults(tmp_path, monkeypatch):
    detected = tmp_path / "codex" / "skills"
    detected.mkdir(parents=True)
    monkeypatch.setattr(
        onboarding, "default_roots",
        lambda **kw: (SkillRoot("codex", str(detected), hosts=("codex",)),),
    )

    roots = collect_roots(RouterConfig())

    assert [root.name for root in roots] == ["codex"]
    assert roots[0].trust == "unverified"


def test_collect_roots_does_not_shadow_a_configured_name(tmp_path, monkeypatch):
    configured = tmp_path / "custom" / "claude-root"
    configured.mkdir(parents=True)
    monkeypatch.setattr(
        onboarding, "default_roots",
        lambda **kw: (SkillRoot("claude", str(tmp_path / "elsewhere"), hosts=("claude",)),),
    )
    config = RouterConfig(roots=(SkillRoot("claude", str(configured), hosts=("claude",)),))

    roots = collect_roots(config)

    assert len(roots) == 1
    assert roots[0].path == str(configured)


def test_verified_bundled_only_root_is_reported_without_auto_trust(tmp_path, monkeypatch):
    root = tmp_path / "claude" / "skills"
    root.mkdir(parents=True)
    installer = _installer(tmp_path)
    installer.install("claude", root)
    monkeypatch.setattr(
        onboarding, "standard_skill_roots", lambda: _harness_roots(tmp_path, root)
    )
    monkeypatch.setattr(onboarding, "default_roots", lambda **kw: ())
    config = RouterConfig(roots=(SkillRoot("claude", str(root), hosts=("claude",)),))

    new_config, report = guided_init(config, installer=installer)

    assert new_config.roots[0].trust == "unverified"
    assert report.roots[0].trusted_by is None
    assert report.roots[0].front_door_verified is True
    assert report.trusted_roots == 0
    assert report.next_actions == ()


def test_explicit_trust_honors_verified_bundled_root(tmp_path, monkeypatch):
    root = tmp_path / "claude" / "skills"
    root.mkdir(parents=True)
    installer = _installer(tmp_path)
    installer.install("claude", root)
    monkeypatch.setattr(
        onboarding, "standard_skill_roots", lambda: _harness_roots(tmp_path, root)
    )
    monkeypatch.setattr(onboarding, "default_roots", lambda **kw: ())
    config = RouterConfig(roots=(SkillRoot("claude", str(root), hosts=("claude",)),))

    new_config, report = guided_init(
        config, installer=installer, trust_names=("claude",)
    )

    assert new_config.roots[0].trust == "local"
    assert report.roots[0].trusted_by == "operator"
    assert report.roots[0].front_door_verified is True
    assert report.next_actions == ()


def test_modified_bundled_root_is_not_front_door_verified(tmp_path, monkeypatch):
    root = tmp_path / "claude" / "skills"
    root.mkdir(parents=True)
    installer = _installer(tmp_path)
    installer.install("claude", root)
    (root / "my-guy" / "SKILL.md").write_text("modified", encoding="utf-8")
    monkeypatch.setattr(
        onboarding, "standard_skill_roots", lambda: _harness_roots(tmp_path, root)
    )
    monkeypatch.setattr(onboarding, "default_roots", lambda **kw: ())
    config = RouterConfig(roots=(SkillRoot("claude", str(root), hosts=("claude",)),))

    new_config, report = guided_init(config, installer=installer)

    assert new_config.roots[0].trust == "unverified"
    assert report.roots[0].front_door_verified is False
    assert report.roots[0].next_action is not None


def test_verified_bundled_root_with_sibling_requires_review(tmp_path, monkeypatch):
    root = tmp_path / "claude" / "skills"
    root.mkdir(parents=True)
    installer = _installer(tmp_path)
    installer.install("claude", root)
    _write_skill(root, "other-pack", "An unreviewed third-party skill.")
    monkeypatch.setattr(
        onboarding, "standard_skill_roots", lambda: _harness_roots(tmp_path, root)
    )
    monkeypatch.setattr(onboarding, "default_roots", lambda **kw: ())
    config = RouterConfig(roots=(SkillRoot("claude", str(root), hosts=("claude",)),))

    _, report = guided_init(config, installer=installer)

    assert report.roots[0].front_door_verified is False
    assert report.roots[0].next_action is not None


def test_mixed_root_is_never_auto_trusted(tmp_path, monkeypatch):
    root = tmp_path / "claude" / "skills"
    root.mkdir(parents=True)
    installer = _installer(tmp_path)
    installer.install("claude", root)
    _write_skill(root, "other-pack", "An unreviewed third-party skill.")
    monkeypatch.setattr(
        onboarding, "standard_skill_roots", lambda: _harness_roots(tmp_path, root)
    )
    monkeypatch.setattr(onboarding, "default_roots", lambda **kw: ())
    config = RouterConfig(roots=(SkillRoot("claude", str(root), hosts=("claude",)),))

    new_config, report = guided_init(config, installer=installer)

    assert new_config.roots[0].trust == "unverified"
    assert report.roots[0].trusted_by is None
    assert report.roots[0].skill_count == 2
    assert report.roots[0].next_action == (
        f"Review the skills under {root}, then run: "
        f"my-guy config --add-root claude {root} local --hosts claude"
    )


def test_unverified_root_reports_the_exact_trust_command(tmp_path, monkeypatch):
    root = tmp_path / "pack" / "skills"
    root.mkdir(parents=True)
    _write_skill(root, "alpha", "Alpha skill.")
    _write_skill(root, "beta", "Beta skill.")
    monkeypatch.setattr(onboarding, "default_roots", lambda **kw: ())
    monkeypatch.setattr(
        onboarding, "standard_skill_roots", lambda: _harness_roots(tmp_path, tmp_path / "none")
    )
    config = RouterConfig(roots=(SkillRoot("pack", str(root)),))

    _, report = guided_init(config, installer=_installer(tmp_path))

    assert report.roots[0].trust == "unverified"
    assert "--hosts" not in report.roots[0].next_action
    assert f"my-guy config --add-root pack {root} local" in report.roots[0].next_action


def test_explicit_trust_name_marks_the_root_local(tmp_path, monkeypatch):
    root = tmp_path / "pack" / "skills"
    root.mkdir(parents=True)
    _write_skill(root, "alpha", "Alpha skill.")
    monkeypatch.setattr(onboarding, "default_roots", lambda **kw: ())
    config = RouterConfig(roots=(SkillRoot("pack", str(root)),))

    new_config, report = guided_init(
        config, installer=_installer(tmp_path), trust_names=("pack",)
    )

    assert new_config.roots[0].trust == "local"
    assert report.roots[0].trusted_by == "operator"


def test_unknown_trust_name_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(onboarding, "default_roots", lambda **kw: ())
    with pytest.raises(ValueError):
        guided_init(
            RouterConfig(), installer=_installer(tmp_path), trust_names=("ghost",)
        )


def test_explicit_trust_refuses_an_unsafe_root(tmp_path, monkeypatch):
    root = tmp_path / "pack" / "skills"
    root.mkdir(parents=True)
    _write_skill(root, "alpha", "Alpha skill.")
    os.chmod(root, 0o777)
    monkeypatch.setattr(onboarding, "default_roots", lambda **kw: ())
    config = RouterConfig(roots=(SkillRoot("pack", str(root)),))

    with pytest.raises(PermissionError):
        guided_init(config, installer=_installer(tmp_path), trust_names=("pack",))


def test_prompter_grants_and_declines_trust(tmp_path, monkeypatch):
    root = tmp_path / "pack" / "skills"
    root.mkdir(parents=True)
    _write_skill(root, "alpha", "Alpha skill.")
    monkeypatch.setattr(onboarding, "default_roots", lambda **kw: ())
    config = RouterConfig(roots=(SkillRoot("pack", str(root)),))

    accepted, report = guided_init(
        config, installer=_installer(tmp_path), prompter=lambda _root, _count: True
    )
    assert accepted.roots[0].trust == "local"
    assert report.roots[0].trusted_by == "prompt"

    declined, report = guided_init(
        config, installer=_installer(tmp_path), prompter=lambda _root, _count: False
    )
    assert declined.roots[0].trust == "unverified"
    assert report.roots[0].trusted_by is None


def test_missing_and_empty_roots_are_reported_without_trust(tmp_path, monkeypatch):
    missing = tmp_path / "missing"
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(onboarding, "default_roots", lambda **kw: ())
    config = RouterConfig(
        roots=(SkillRoot("gone", str(missing)), SkillRoot("empty", str(empty)))
    )

    prompted = []
    _, report = guided_init(
        config,
        installer=_installer(tmp_path),
        prompter=lambda root, count: prompted.append(root.name) or True,
    )

    assert prompted == []
    assert report.roots[0].exists is False
    assert "does not exist" in report.roots[0].next_action
    assert report.roots[1].skill_count == 0
    assert "No SKILL.md" in report.roots[1].next_action


def test_already_trusted_root_is_left_alone(tmp_path, monkeypatch):
    root = tmp_path / "pack" / "skills"
    root.mkdir(parents=True)
    _write_skill(root, "alpha", "Alpha skill.")
    monkeypatch.setattr(onboarding, "default_roots", lambda **kw: ())
    config = RouterConfig(roots=(SkillRoot("pack", str(root), "local"),))

    new_config, report = guided_init(config, installer=_installer(tmp_path))

    assert new_config == config
    assert report.roots[0].trust == "local"
    assert report.roots[0].trusted_by is None
