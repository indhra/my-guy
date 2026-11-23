"""Bounded, read-only inventory of agent metadata and enabled plugin installs."""

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

MAX_METADATA_BYTES = 1_048_576
MAX_FILES_PER_ROOT = 10_000
HOSTS = ("codex", "claude", "opencode")
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
    # JSONC permits comments and trailing commas. Strip them only outside strings.
    chars: list[str] = []
    quoted = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if quoted:
            chars.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            chars.append(char)
        elif text[index:index + 2] == "//":
            index = text.find("\n", index)
            if index < 0:
                break
            chars.append("\n")
        elif text[index:index + 2] == "/*":
            end = text.find("*/", index + 2)
            if end < 0:
                return {}
            index = end + 1
        else:
            chars.append(char)
        index += 1
    stripped = "".join(chars)
    clean: list[str] = []
    next_visible = [""] * len(stripped)
    following = ""
    for index in range(len(stripped) - 1, -1, -1):
        next_visible[index] = following
        if not stripped[index].isspace():
            following = stripped[index]
    quoted = escaped = False
    for index, char in enumerate(stripped):
        if char == '"' and not escaped:
            quoted = not quoted
        if char == "," and not quoted and next_visible[index] in ("}", "]"):
            continue
        clean.append(char)
        escaped = char == "\\" and not escaped if quoted else False
    try:
        value = json.loads("".join(clean))
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}
def _files(root: Path, suffixes: set[str]) -> tuple[Path, ...]:
    if not root.is_dir() or root.is_symlink():
        return ()
    found: list[Path] = []
    directories = 0
    for directory, subdirs, files in os.walk(root, followlinks=False):
        directories += 1
        if directories > MAX_FILES_PER_ROOT:
            break
        subdirs[:] = sorted(name for name in subdirs if name.lower() not in IGNORED
                            and not (Path(directory) / name).is_symlink())
        for name in sorted(files):
            file = Path(directory) / name
            if file.suffix.lower() in suffixes and not file.is_symlink() and file.is_file():
                found.append(file)
                if len(found) >= MAX_FILES_PER_ROOT:
                    return tuple(found)
    return tuple(found)


def _description_from_markdown(text: str) -> tuple[str | None, str | None]:
    # Parse frontmatter only. Agent instruction bodies are untrusted and ignored.
    from .discovery import _frontmatter

    metadata = _frontmatter(text)
    return metadata.get("name"), metadata.get("description")


def _keywords(value: str) -> tuple[str, ...]:
    from .discovery import _keywords as extract

    return tuple(extract(value))


def _agents(name: str, root: Path, host: str, trust: str = "unverified") -> tuple[Capability, ...]:
    files = _files(root, {".md", ".toml"})
    toml_stems = {file.stem for file in files if file.suffix.lower() == ".toml"}
    counts: Counter[str] = Counter()
    found: list[Capability] = []
    for file in files:
        if file.name == "AGENTS.md" or file.name.endswith(".compact.md"):
            continue
        if file.suffix.lower() == ".md" and file.stem in toml_stems:
            continue
        if file.suffix.lower() == ".toml":
            metadata = _toml(file)
            agent_name, description = metadata.get("name", file.stem), metadata.get("description")
        else:
            content = _safe_text(file)
            if content is None:
                continue
            agent_name, description = _description_from_markdown(content)
            agent_name = agent_name or file.stem
        if not isinstance(agent_name, str) or not isinstance(description, str) or not description.strip():
            continue
        agent_name, description = agent_name.strip(), description.strip()
        counts[agent_name] += 1
        suffix = "" if counts[agent_name] == 1 else ":" + sha256(str(file).encode()).hexdigest()[:10]
        try:
            found.append(Capability(
                id=f"{name}:{agent_name}{suffix}", source=f"{name}:{file}",
                description=description, domains=(),
                triggers=_keywords(f"{agent_name} {description}"),
                invocation=f"agent:{agent_name}", trust=trust,
                kind="agent", hosts=(host,),
            ))
        except ValueError:
            continue
    return tuple(found)


def _skill_hosts(root: SkillRoot) -> tuple[str, ...]:
    if root.hosts:
        return root.hosts
    parts = tuple(part.lower() for part in Path(root.path).parts)
    if ".codex" in parts:
        return ("codex",)
    if ".claude" in parts:
        return ("claude",)
    if ".opencode" in parts or "opencode" in parts:
        return ("opencode",)
    if ".agents" in parts:
        return HOSTS
    return ()


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
            for name, value in entries.items():
                if not isinstance(name, str) or not isinstance(value, dict):
                    continue
                description = value.get("description")
                if isinstance(description, str) and description.strip():
                    effective[name] = (path, description.strip())
    found: list[Capability] = []
    for name, (path, description) in sorted(effective.items()):
        try:
            found.append(Capability(
                id=f"opencode-config-agent:{name}", source=f"opencode-config-agent:{path}#{name}",
                description=description, domains=(), triggers=_keywords(f"{name} {description}"),
                invocation=f"agent:{name}", trust="unverified", kind="agent", hosts=("opencode",),
            ))
        except ValueError:
            continue
    return tuple(found)


def _plugin_roots(home: Path, project: Path) -> tuple[tuple[str, Path, str], ...]:
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
            enabled.update({key: value for key, value in values.items()
                            if isinstance(key, str) and isinstance(value, bool)})
    installed = _json(claude_home / "plugins" / "installed_plugins.json")
    plugins = installed.get("plugins", {})
    if isinstance(enabled, dict) and isinstance(plugins, dict):
        for plugin_id, active in sorted(enabled.items()):
            if not isinstance(plugin_id, str) or active is not True:
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
                if not path.is_absolute() or path.is_symlink() or not path.is_dir():
                    continue
                if scope in {"project", "local"}:
                    bound = entry.get("projectPath")
                    if not isinstance(bound, str) or Path(bound).resolve() != project.resolve():
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
            if (not separator or plugin in {".", ".."} or marketplace in {".", ".."}
                    or not re.fullmatch(r"[A-Za-z0-9._-]+", plugin)
                    or not re.fullmatch(r"[A-Za-z0-9._-]+", marketplace)):
                continue
            version_root = cache / marketplace / plugin
            if (version_root.is_symlink() or not version_root.is_dir()
                    or not version_root.resolve().is_relative_to(cache.resolve())):
                continue
            versions = sorted((path for path in version_root.iterdir()
                               if path.is_dir() and not path.is_symlink()
                               and path.resolve().is_relative_to(cache.resolve())), reverse=True)
            if versions:
                key = sha256(plugin_id.encode()).hexdigest()[:10]
                result.append((f"codex-plugin-{key}", versions[0], "codex"))
    return tuple(result)


def discover_inventory(config: RouterConfig, *, home: Path | None = None,
                       project: Path | None = None) -> tuple[Capability, ...]:
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
            found.extend(replace(item, hosts=_skill_hosts(root)) for item in discover_named_roots((root,)))
    roots = (
        ("codex-agent", home / ".codex" / "agents", "codex"),
        ("claude-agent", home / ".claude" / "agents", "claude"),
        ("opencode-agent", home / ".config" / "opencode" / "agents", "opencode"),
        ("project-codex-agent", project / ".codex" / "agents", "codex"),
        ("project-claude-agent", project / ".claude" / "agents", "claude"),
        ("project-opencode-agent", project / ".opencode" / "agents", "opencode"),
    )
    for name, root, host in roots:
        if root.resolve() not in configured_agent_paths:
            found.extend(_agents(name, root, host))
    found.extend(_opencode_config_agents(home, project))
    for name, path, host in _plugin_roots(home, project):
        skill_paths = (path / "skills", path / ".codex-plugin" / "migrated-command-skills") if host == "codex" else (path / "skills",)
        for index, skill_path in enumerate(skill_paths):
            if skill_path.is_dir() and not skill_path.is_symlink():
                root = SkillRoot(f"{name}-{index}", str(skill_path))
                found.extend(replace(item, hosts=(host,)) for item in discover_named_roots((root,)))
        agent_paths = (path / "agents", path / ".codex" / "agents") if host == "codex" else (path / "agents",)
        for index, agent_path in enumerate(agent_paths):
            found.extend(_agents(f"{name}-{index}", agent_path, host))
    return tuple(found)
