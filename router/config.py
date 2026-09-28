from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .path_safety import has_symlink_component


SCHEMA_VERSION = 1
_ROOT_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class SkillRoot:
    name: str
    path: str
    trust: str = "unverified"

    def __post_init__(self) -> None:
        if not _ROOT_NAME.fullmatch(self.name):
            raise ValueError(f"invalid skill-root name: {self.name!r}")
        if self.trust not in {"local", "unverified"}:
            raise ValueError("discovered roots may be local or unverified")
        if not self.path.strip() or "\x00" in self.path:
            raise ValueError("skill-root path is required")
        normalized = Path(self.path).expanduser()
        if not normalized.is_absolute():
            raise ValueError("skill-root path must be absolute")
        object.__setattr__(self, "path", str(normalized))


@dataclass(frozen=True)
class RouterConfig:
    enabled: bool = True
    feedback_enabled: bool = False
    roots: tuple[SkillRoot, ...] = ()
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported config schema: {self.schema_version}")
        names = [root.name for root in self.roots]
        if len(names) != len(set(names)):
            raise ValueError("skill-root names must be unique")


def app_home() -> Path:
    override = os.environ.get("MY_GUY_HOME")
    if override:
        return Path(override).expanduser()
    config_home = os.environ.get("XDG_CONFIG_HOME")
    return (Path(config_home) if config_home else Path.home() / ".config") / "my-guy"


def default_roots(home: Path | None = None, project: Path | None = None) -> tuple[SkillRoot, ...]:
    home = home or Path.home()
    project = project or Path.cwd()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    candidates = (
        SkillRoot("agents", str(home / ".agents" / "skills")),
        SkillRoot("codex", str(home / ".codex" / "skills")),
        SkillRoot("claude", str(home / ".claude" / "skills")),
        SkillRoot("opencode", str(config_home / "opencode" / "skills")),
        SkillRoot("project-agents", str(project / ".agents" / "skills")),
        SkillRoot("project-codex", str(project / ".codex" / "skills")),
        SkillRoot("project-claude", str(project / ".claude" / "skills")),
        SkillRoot("project-opencode", str(project / ".opencode" / "skills")),
    )
    return tuple(root for root in candidates if Path(root.path).is_dir())


def load_config(path: Path | None = None) -> RouterConfig:
    path = path or app_home() / "config.json"
    if not path.exists():
        return RouterConfig(roots=default_roots())
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config must be a JSON object")
    roots = tuple(SkillRoot(**item) for item in raw.get("roots", ()))
    return RouterConfig(
        enabled=raw.get("enabled", True),
        feedback_enabled=raw.get("feedback_enabled", False),
        roots=roots,
        schema_version=raw.get("schema_version", SCHEMA_VERSION),
    )


def save_config(config: RouterConfig, path: Path | None = None) -> Path:
    path = path or app_home() / "config.json"
    created_parent = not path.parent.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    if created_parent:
        os.chmod(path.parent, 0o700)
    payload = asdict(config)
    payload["roots"] = [asdict(root) for root in config.roots]
    fd, temporary = tempfile.mkstemp(prefix=".config-", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path
