"""Bounded, read-only inventory of local agents and enabled plugin skills."""

from __future__ import annotations

import json
import os
import re
import tomllib
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from .config import RouterConfig, SkillRoot
from .models import Capability
from .path_safety import unsafe_skill_file, unsafe_skill_root

MAX_METADATA_BYTES = 1_048_576
# This is an entry budget (files and directories), not a result budget.
MAX_FILES_PER_ROOT = 10_000
IGNORED = {".git", ".trash", "trash", "node_modules", "__pycache__"}


def _safe_text(path: Path) -> str | None:
    try:
        if path.is_symlink() or path.stat().st_size > MAX_METADATA_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _json(path: Path) -> dict:
    text = _safe_text(path)
    if text is None:
        return {}
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def _toml(path: Path) -> dict:
    text = _safe_text(path)
    if text is None:
        return {}
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return {}


def _jsonc(path: Path) -> dict:
    text = _safe_text(path)
    if text is None:
        return {}

    # Remove JSONC comments without treating comment markers inside strings as
    # syntax. The second pass removes trailing commas outside strings.
    stripped: list[str] = []
    quoted = escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if quoted:
            stripped.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            index += 1
        elif char == '"':
            quoted = True
            stripped.append(char)
            index += 1
        elif text[index:index + 2] == "//":
            newline = text.find("\n", index)
            if newline < 0:
                break
            stripped.append("\n")
            index = newline + 1
        elif text[index:index + 2] == "/*":
            end = text.find("*/", index + 2)
            if end < 0:
                return {}
            stripped.extend("\n" for char in text[index:end + 2] if char == "\n")
            index = end + 2
        else:
            stripped.append(char)
            index += 1

    source = "".join(stripped)
    next_visible = [""] * len(source)
    following = ""
    for position in range(len(source) - 1, -1, -1):
        next_visible[position] = following
        if not source[position].isspace():
            following = source[position]

    clean: list[str] = []
    quoted = escaped = False
    for position, char in enumerate(source):
        if char == '"' and not escaped:
            quoted = not quoted
        if char == "," and not quoted and next_visible[position] in {"}", "]"}:
            escaped = char == "\\" and not escaped if quoted else False
            continue
        clean.append(char)
        escaped = char == "\\" and not escaped if quoted else False

    try:
        value = json.loads("".join(clean))
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def _files(root: Path, suffixes: set[str]) -> tuple[Path, ...]:
    if root.is_symlink() or not root.is_dir():
        return ()
    found: list[Path] = []
    scanned_entries = 0
    pending = [root]
    while pending:
        directory = pending.pop()
        entries: list[tuple[str, bool, bool]] = []
        try:
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    scanned_entries += 1
                    if scanned_entries > MAX_FILES_PER_ROOT:
                        # Never return a partial inventory after budget exhaustion.
                        return ()
                    is_directory = entry.is_dir(follow_symlinks=False)
                    is_file = entry.is_file(follow_symlinks=False)
                    entries.append((entry.name, is_directory, is_file))
        except OSError:
            # A partially readable tree is not a complete actionable inventory.
            return ()

        children: list[Path] = []
        for name, is_directory, is_file in sorted(entries, key=lambda item: item[0]):
            path = directory / name
            if is_directory:
                if name.lower() not in IGNORED:
                    children.append(path)
            elif is_file and path.suffix.lower() in suffixes:
                found.append(path)
        # Stack order keeps traversal deterministic and depth-first.
        pending.extend(reversed(children))
    return tuple(found)


def _description_from_markdown(text: str) -> tuple[str | None, str | None]:
    from .discovery import _frontmatter

    metadata = _frontmatter(text)
    return metadata.get("name"), metadata.get("description")


def _keywords(text: str) -> tuple[str, ...]:
    from .discovery import _keywords as extract_keywords

    return tuple(extract_keywords(text))


def _agents(name: str, root: Path, host: str, trust: str = "unverified") -> tuple[Capability, ...]:
    if unsafe_skill_root(root):
        return ()
    files = _files(root, {".md", ".toml"})
    toml_stems = {path.stem for path in files if path.suffix.lower() == ".toml"}
    counts: Counter[str] = Counter()
    found: list[Capability] = []
    for path in files:
        if unsafe_skill_file(path):
            continue
        if path.name == "AGENTS.md" or path.name.endswith(".compact.md"):
            continue
        if path.suffix.lower() == ".md" and path.stem in toml_stems:
            continue
        if path.suffix.lower() == ".toml":
            metadata = _toml(path)
            agent_name = metadata.get("name", path.stem)
            description = metadata.get("description")
        else:
            content = _safe_text(path)
            if content is None:
                continue
            agent_name, description = _description_from_markdown(content)
            agent_name = agent_name or path.stem
        if not isinstance(agent_name, str) or not isinstance(description, str) or not description.strip():
            continue
        agent_name, description = agent_name.strip(), description.strip()
        counts[agent_name] += 1
        suffix = "" if counts[agent_name] == 1 else ":" + sha256(str(path).encode()).hexdigest()[:10]
        try:
            found.append(Capability(
                id=f"{name}:{agent_name}{suffix}",
                source=f"{name}:{path}",
                description=description,
                domains=(),
                triggers=_keywords(f"{agent_name} {description}"),
                invocation=f"agent:{agent_name}",
                trust=trust,
                kind="agent",
                hosts=(host,),
            ))
        except ValueError:
            continue
    return tuple(found)


def _skill_hosts(
    root: SkillRoot, *, home: Path, project: Path
) -> tuple[str, ...] | None:
    """Use explicit host metadata or an exact, recognized root layout."""
    if root.hosts:
        return root.hosts
    canonical_roots = {
        (home / ".codex" / "skills").resolve(): ("codex",),
        (project / ".codex" / "skills").resolve(): ("codex",),
        (home / ".claude" / "skills").resolve(): ("claude",),
        (project / ".claude" / "skills").resolve(): ("claude",),
        (home / ".config" / "opencode" / "skills").resolve(): ("opencode",),
        (project / ".opencode" / "skills").resolve(): ("opencode",),
    }
    return canonical_roots.get(Path(root.path).resolve())


def _opencode_config_agents(home: Path, project: Path) -> tuple[Capability, ...]:
    paths = (
        home / ".config" / "opencode" / "opencode.jsonc",
        home / ".config" / "opencode" / "opencode.json",
        project / "opencode.jsonc",
        project / "opencode.json",
        project / ".opencode" / "opencode.jsonc",
        project / ".opencode" / "opencode.json",
    )
    effective: dict[str, tuple[Path, str]] = {}
    for path in paths:
        data = _jsonc(path)
        for key in ("agent", "agents"):
            entries = data.get(key, {})
            if not isinstance(entries, dict):
                continue
            for agent_name, value in entries.items():
                if not isinstance(agent_name, str) or not isinstance(value, dict):
                    continue
                description = value.get("description")
                if isinstance(description, str) and description.strip():
                    effective[agent_name] = (path, description.strip())
    found: list[Capability] = []
    for agent_name, (path, description) in sorted(effective.items()):
        try:
            found.append(Capability(
                id=f"opencode-config-agent:{agent_name}",
                source=f"opencode-config-agent:{path}#{agent_name}",
                description=description,
                domains=(),
                triggers=_keywords(f"{agent_name} {description}"),
                invocation=f"agent:{agent_name}",
                trust="unverified",
                kind="agent",
                hosts=("opencode",),
            ))
        except ValueError:
            continue
    return tuple(found)


def _plugin_roots(
    home: Path, project: Path, config: RouterConfig
) -> tuple[tuple[str, Path, str], ...]:
    result: list[tuple[str, Path, str]] = []
    claude_home = home / ".claude"
    enabled: dict[str, bool] = {}
    for settings_path in (
        claude_home / "settings.json",
        project / ".claude" / "settings.json",
        project / ".claude" / "settings.local.json",
    ):
        values = _json(settings_path).get("enabledPlugins", {})
        if isinstance(values, dict):
            enabled.update({key: value for key, value in values.items() if isinstance(key, str) and isinstance(value, bool)})
    installed = _json(claude_home / "plugins" / "installed_plugins.json")
    plugins = installed.get("plugins", {})
    if isinstance(plugins, dict):
        for plugin_id, active in sorted(enabled.items()):
            if active is not True:
                continue
            entries = plugins.get(plugin_id, ())
            if not isinstance(entries, list):
                continue
            for entry in entries[:16]:
                if not isinstance(entry, dict):
                    continue
                scope, install_path = entry.get("scope"), entry.get("installPath")
                if scope not in {"user", "project", "local"} or not isinstance(install_path, str):
                    continue
                path = Path(install_path).expanduser()
                if not path.is_absolute() or unsafe_skill_root(path) or not path.is_dir():
                    continue
                resolved_path = path.resolve()
                managed_storage = (claude_home / "plugins").resolve()
                is_managed = resolved_path.is_relative_to(managed_storage)
                explicitly_trusted = any(
                    root.kind == "skill"
                    and root.trust == "local"
                    and "claude" in root.hosts
                    and resolved_path.is_relative_to(Path(root.path).resolve())
                    for root in config.roots
                )
                if not (is_managed or explicitly_trusted):
                    continue
                if scope in {"project", "local"}:
                    bound = entry.get("projectPath")
                    if not isinstance(bound, str) or Path(bound).resolve() != project.resolve():
                        continue
                # The configured trusted root is scanned above as a normal
                # root; adding this same install path again would duplicate it.
                if explicitly_trusted:
                    continue
                key = sha256(plugin_id.encode()).hexdigest()[:10]
                location = sha256(str(path).encode()).hexdigest()[:10]
                result.append((f"claude-plugin-{key}-{location}", path, "claude"))

    codex_plugins = _toml(home / ".codex" / "config.toml").get("plugins", {})
    if isinstance(codex_plugins, dict):
        cache = home / ".codex" / "plugins" / "cache"
        for plugin_id, value in sorted(codex_plugins.items()):
            if not isinstance(plugin_id, str) or not isinstance(value, dict) or value.get("enabled") is not True:
                continue
            plugin, separator, marketplace = plugin_id.partition("@")
            valid = re.compile(r"[A-Za-z0-9._-]+")
            if not separator or plugin in {".", ".."} or marketplace in {".", ".."}:
                continue
            if not valid.fullmatch(plugin) or not valid.fullmatch(marketplace):
                continue
            version_root = cache / marketplace / plugin
            try:
                cache_resolved = cache.resolve()
                if version_root.is_symlink() or not version_root.is_dir() or not version_root.resolve().is_relative_to(cache_resolved):
                    continue
                versions = [
                    path for path in version_root.iterdir()
                    if path.is_dir() and not path.is_symlink() and path.resolve().is_relative_to(cache_resolved)
                ]
            except OSError:
                continue
            # Natural version ordering (e.g. 1.10 before 1.9), stable on ties.
            def version_key(path: Path) -> tuple[tuple[int, object], ...]:
                return tuple((0, part.lower()) if part.isalpha() else (1, int(part))
                             for part in re.findall(r"[A-Za-z]+|\d+", path.name))

            if not versions:
                continue
            selected = max(versions, key=lambda path: (version_key(path), path.name))
            key = sha256(plugin_id.encode()).hexdigest()[:10]
            result.append((f"codex-plugin-{key}", selected, "codex"))
    return tuple(result)


def discover_inventory(
    config: RouterConfig,
    *,
    home: Path | None = None,
    project: Path | None = None,
) -> tuple[Capability, ...]:
    """Discover configured skills, local agents, and explicitly enabled plugins."""
    from .discovery import discover_named_roots

    home = Path(home) if home is not None else Path.home()
    project = Path(project) if project is not None else Path.cwd()
    found: list[Capability] = []
    configured_agent_paths: set[Path] = set()
    for root in config.roots:
        if root.kind == "agent":
            configured_agent_paths.add(Path(root.path).resolve())
            found.extend(_agents(root.name, Path(root.path), root.hosts[0], root.trust))
        else:
            found.extend(
                replace(item, hosts=_skill_hosts(root, home=home, project=project))
                for item in discover_named_roots((root,))
            )

    agent_roots = (
        ("codex-agent", home / ".codex" / "agents", "codex"),
        ("claude-agent", home / ".claude" / "agents", "claude"),
        ("opencode-agent", home / ".config" / "opencode" / "agents", "opencode"),
        ("project-codex-agent", project / ".codex" / "agents", "codex"),
        ("project-claude-agent", project / ".claude" / "agents", "claude"),
        ("project-opencode-agent", project / ".opencode" / "agents", "opencode"),
    )
    for name, root, host in agent_roots:
        if root.resolve() not in configured_agent_paths:
            found.extend(_agents(name, root, host))

    found.extend(_opencode_config_agents(home, project))
    for name, path, host in _plugin_roots(home, project, config):
        skill_paths = (path / "skills", path / ".codex-plugin" / "migrated-command-skills") if host == "codex" else (path / "skills",)
        for index, skill_path in enumerate(skill_paths):
            if not skill_path.is_dir() or skill_path.is_symlink():
                continue
            skill_root = SkillRoot(f"{name}-{index}", str(skill_path), "unverified", hosts=(host,))
            found.extend(replace(item, hosts=(host,)) for item in discover_named_roots((skill_root,)))
    return tuple(found)
