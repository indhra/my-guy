import os
from pathlib import Path

import router.inventory as inventory
from router.config import RouterConfig, SkillRoot
from router.discovery import discover_inventory


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    cursor = path.parent
    while cursor != cursor.parent and cursor != cursor.anchor:
        if cursor != Path("/tmp") and cursor.is_relative_to(Path("/tmp")):
            cursor.chmod(0o700)
        cursor = cursor.parent
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def test_inventory_discovers_agent_metadata_without_duplicate_companions(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    _write(
        home / ".codex" / "agents" / "reviewer.toml",
        'name = "reviewer"\ndescription = "Review code safely."\n',
    )
    _write(
        home / ".codex" / "agents" / "reviewer.md",
        "---\nname: reviewer\ndescription: Duplicate companion.\n---\n",
    )
    _write(
        home / ".codex" / "agents" / "reviewer.compact.md",
        "---\nname: reviewer\ndescription: Compact duplicate.\n---\n",
    )

    agents = discover_inventory(RouterConfig(), home=home, project=project)

    assert [(item.kind, item.invocation, item.hosts) for item in agents] == [
        ("agent", "agent:reviewer", ("codex",)),
    ]
    assert agents[0].trust == "unverified"


def test_inventory_entry_budget_counts_irrelevant_files(tmp_path, monkeypatch):
    root = tmp_path / "agents"
    for index in range(5):
        _write(root / f"00-noise-{index}.bin", "not metadata")
    _write(root / "99-agent.md", "---\nname: late\ndescription: Late agent.\n---\n")
    monkeypatch.setattr(inventory, "MAX_FILES_PER_ROOT", 3)

    assert inventory._files(root, {".md"}) == ()


def test_inventory_flat_directory_stops_consuming_after_budget(tmp_path, monkeypatch):
    root = tmp_path / "flat"
    root.mkdir()
    for index in range(200):
        (root / f"noise-{index:03}.bin").touch()

    budget = 12
    consumed = 0
    original_scandir = os.scandir

    class CountingScandir:
        def __init__(self, path):
            self.iterator = original_scandir(path)

        def __enter__(self):
            self.iterator.__enter__()
            return self

        def __exit__(self, *args):
            return self.iterator.__exit__(*args)

        def __iter__(self):
            return self

        def __next__(self):
            nonlocal consumed
            entry = next(self.iterator)
            consumed += 1
            return entry

    monkeypatch.setattr(inventory, "MAX_FILES_PER_ROOT", budget)
    monkeypatch.setattr(inventory.os, "scandir", CountingScandir)

    assert inventory._files(root, {".md"}) == ()
    assert consumed == budget + 1


def test_inventory_skips_unsafe_agent_root(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    root = home / ".codex" / "agents"
    _write(root / "reviewer.toml", 'name = "reviewer"\ndescription = "Review safely."\n')
    root.chmod(0o777)

    assert discover_inventory(RouterConfig(), home=home, project=project) == ()


def test_codex_plugin_uses_highest_natural_version_and_skips_disabled(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    config = home / ".codex" / "config.toml"
    _write(
        config,
        '[plugins."active@market"]\nenabled = true\n'
        '[plugins."disabled@market"]\nenabled = false\n',
    )
    cache = home / ".codex" / "plugins" / "cache" / "market"
    for version, agent_name in (("1.9.0", "old"), ("1.10.0", "new")):
        _write(
            cache / "active" / version / "skills" / agent_name / "SKILL.md",
            f"---\nname: {agent_name}\ndescription: {agent_name} version.\n---\n",
        )
    _write(
        cache / "disabled" / "99.0.0" / "skills" / "disabled" / "SKILL.md",
        "---\nname: disabled\ndescription: Disabled plugin.\n---\n",
    )

    items = discover_inventory(RouterConfig(), home=home, project=project)

    assert [item.invocation for item in items] == ["skill:new"]
    assert items[0].hosts == ("codex",)


def test_configured_skills_and_reviewed_agent_roots_keep_explicit_hosts(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    skill = home / ".claude" / "skills" / "review" / "SKILL.md"
    agent_root = home / ".codex" / "agents"
    _write(skill, "---\nname: review\ndescription: Review changes.\n---\n")
    _write(agent_root / "reviewer.toml", 'name = "reviewer"\ndescription = "Review safely."\n')
    config = RouterConfig(roots=(
        SkillRoot("claude", str(skill.parent.parent), "local", hosts=("claude",)),
        SkillRoot("reviewed", str(agent_root), "local", kind="agent", hosts=("codex",)),
    ))

    items = discover_inventory(config, home=home, project=project)

    assert {(item.kind, item.invocation, item.hosts, item.trust) for item in items} == {
        ("skill", "skill:review", ("claude",), "local"),
        ("agent", "agent:reviewer", ("codex",), "local"),
    }


def test_claude_plugin_enablement_obeys_project_local_override(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    plugin = home / ".claude" / "plugins" / "cache" / "review" / "1"
    _write(plugin / "skills" / "review" / "SKILL.md", "---\nname: review\ndescription: Review work.\n---\n")
    _write(
        home / ".claude" / "plugins" / "installed_plugins.json",
        '{"plugins":{"review@market":[{"scope":"project","projectPath":'
        f'"{project}","installPath":"{plugin}"' + "}]}}",
    )
    _write(home / ".claude" / "settings.json", '{"enabledPlugins":{"review@market":true}}')
    _write(project / ".claude" / "settings.json", '{"enabledPlugins":{"review@market":false}}')

    assert discover_inventory(RouterConfig(), home=home, project=project) == ()
    _write(project / ".claude" / "settings.local.json", '{"enabledPlugins":{"review@market":true}}')
    items = discover_inventory(RouterConfig(), home=home, project=project)
    assert [item.invocation for item in items] == ["skill:review"]
    assert items[0].hosts == ("claude",)
    assert discover_inventory(RouterConfig(), home=home, project=tmp_path / "elsewhere") == ()


def test_claude_plugin_install_path_requires_managed_or_explicit_trusted_root(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    plugin = tmp_path / "custom-storage" / "review"
    _write(plugin / "skills" / "review" / "SKILL.md", "---\nname: review\ndescription: Review work.\n---\n")
    _write(
        home / ".claude" / "plugins" / "installed_plugins.json",
        '{"plugins":{"review@market":[{"scope":"user",'
        f'"installPath":"{plugin}"' + "}]}}",
    )
    _write(home / ".claude" / "settings.json", '{"enabledPlugins":{"review@market":true}}')

    assert inventory._plugin_roots(home, project, RouterConfig()) == ()

    trusted = RouterConfig(roots=(
        SkillRoot("claude-plugin-store", str(plugin.parent), "local", hosts=("claude",)),
    ))
    items = discover_inventory(trusted, home=home, project=project)
    assert [(item.invocation, item.hosts, item.trust) for item in items] == [
        ("skill:review", ("claude",), "local"),
    ]


def test_skill_hosts_infer_only_exact_canonical_layouts(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    canonical = home / ".codex" / "skills"
    custom = tmp_path / "opencode" / ".claude" / "skills"
    _write(canonical / "review" / "SKILL.md", "---\nname: review\ndescription: Review.\n---\n")
    _write(custom / "review" / "SKILL.md", "---\nname: review\ndescription: Review.\n---\n")

    inferred = discover_inventory(
        RouterConfig(roots=(SkillRoot("canonical", str(canonical)),)), home=home, project=project
    )
    unknown = discover_inventory(
        RouterConfig(roots=(SkillRoot("misleading", str(custom)),)), home=home, project=project
    )

    assert inferred[0].hosts == ("codex",)
    assert unknown[0].hosts is None


def test_opencode_jsonc_agent_is_static_and_project_config_wins(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    _write(
        home / ".config" / "opencode" / "opencode.jsonc",
        '{"agent":{"planner":{"description":"Home planner"}}}',
    )
    _write(
        project / "opencode.jsonc",
        '{\n // Static metadata only\n "agents": {"planner": {"description": "Project planner",},},\n}',
    )

    items = discover_inventory(RouterConfig(), home=home, project=project)

    assert len(items) == 1
    assert (items[0].kind, items[0].invocation, items[0].hosts) == (
        "agent", "agent:planner", ("opencode",),
    )
    assert items[0].description == "Project planner"
    assert items[0].trust == "unverified"


def test_codex_plugin_cache_symlink_cannot_escape(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    _write(outside / "plugin" / "1" / "skills" / "escape" / "SKILL.md", "---\nname: escape\ndescription: Escape.\n---\n")
    cache = home / ".codex" / "plugins" / "cache"
    cache.mkdir(parents=True)
    (cache / "market").symlink_to(outside, target_is_directory=True)
    _write(home / ".codex" / "config.toml", '[plugins."plugin@market"]\nenabled = true\n')

    assert discover_inventory(RouterConfig(), home=home, project=project) == ()
