from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


SUPPORTED_HARNESSES = frozenset({"agents", "claude", "codex", "opencode"})


@dataclass(frozen=True)
class InstallResult:
    action: str
    harness: str
    target: str
    digest: str | None


class SkillInstaller:
    """Reversible installer for the portable my-guy SKILL.md front door."""

    def __init__(self, state_dir: Path, source: Path | None = None) -> None:
        self.state_dir = state_dir
        self.source = source or Path(__file__).parent / "resources" / "my-guy" / "SKILL.md"

    def install(self, harness: str, root: Path) -> InstallResult:
        return self._write(harness, root, "install")

    def upgrade(self, harness: str, root: Path) -> InstallResult:
        target = self._target(harness, root)
        if not target.exists() and not target.with_suffix(".md.disabled").exists():
            raise FileNotFoundError("my-guy is not installed for this harness")
        return self._write(harness, root, "upgrade")

    def disable(self, harness: str, root: Path) -> InstallResult:
        target = self._target(harness, root)
        disabled = target.with_suffix(".md.disabled")
        self._guard(target)
        if not target.exists():
            raise FileNotFoundError("enabled my-guy skill is not installed")
        self._snapshot(harness, target, disabled)
        os.replace(target, disabled)
        return InstallResult("disable", harness, str(disabled), self._digest(disabled))

    def rollback(self, harness: str, root: Path) -> InstallResult:
        target = self._target(harness, root)
        disabled = target.with_suffix(".md.disabled")
        history = self._history(harness, target)
        snapshots = sorted(history.glob("*.json"))
        if not snapshots:
            raise FileNotFoundError("no lifecycle snapshot is available")
        manifest_path = snapshots[-1]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self._guard(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        staged: dict[str, Path] = {}
        try:
            for key, path in (("enabled", target), ("disabled", disabled)):
                record = manifest.get(key)
                if not record:
                    continue
                if not isinstance(record, dict) or set(record) != {"file", "digest"}:
                    raise ValueError("invalid lifecycle snapshot manifest")
                backup = manifest_path.parent / record["file"]
                if backup.parent != manifest_path.parent or not backup.is_file() or backup.is_symlink():
                    raise FileNotFoundError("lifecycle snapshot backup is missing or unsafe")
                if self._digest(backup) != record["digest"]:
                    raise ValueError("lifecycle snapshot digest mismatch")
                descriptor, temporary = tempfile.mkstemp(prefix=".rollback-", dir=target.parent)
                os.close(descriptor)
                temporary_path = Path(temporary)
                shutil.copy2(backup, temporary_path)
                staged[key] = temporary_path
            for key, path in (("enabled", target), ("disabled", disabled)):
                if key in staged:
                    os.replace(staged.pop(key), path)
                elif path.exists():
                    path.unlink()
        finally:
            for temporary_path in staged.values():
                temporary_path.unlink(missing_ok=True)
        manifest_path.unlink()
        return InstallResult("rollback", harness, str(target), self._digest(target) if target.exists() else None)

    def _write(self, harness: str, root: Path, action: str) -> InstallResult:
        target = self._target(harness, root)
        disabled = target.with_suffix(".md.disabled")
        self._guard(target)
        self._snapshot(harness, target, disabled)
        target.parent.mkdir(parents=True, exist_ok=True)
        content = self.source.read_bytes()
        fd, temporary = tempfile.mkstemp(prefix=".my-guy-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o644)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        if disabled.exists():
            disabled.unlink()
        return InstallResult(action, harness, str(target), self._digest(target))

    def _target(self, harness: str, root: Path) -> Path:
        if harness not in SUPPORTED_HARNESSES:
            raise ValueError(f"unsupported local-skill harness: {harness}")
        if "\x00" in str(root):
            raise ValueError("invalid install root")
        root = root.expanduser().absolute()
        if root in {Path("/"), Path.home()}:
            raise ValueError("install root must be a dedicated skills directory")
        return root / "my-guy" / "SKILL.md"

    @staticmethod
    def _guard(target: Path) -> None:
        for candidate in (target, *target.parents):
            if candidate.exists() and candidate.is_symlink():
                raise PermissionError("refusing to modify a symlinked skill target")

    def _snapshot(self, harness: str, target: Path, disabled: Path) -> None:
        history = self._history(harness, target)
        history.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        manifest: dict[str, dict[str, str]] = {}
        for key, path in (("enabled", target), ("disabled", disabled)):
            if path.exists():
                name = f"{stamp}-{key}.bak"
                shutil.copy2(path, history / name)
                manifest[key] = {"file": name, "digest": self._digest(history / name)}
        manifest_path = history / f"{stamp}.json"
        descriptor = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, sort_keys=True)

    def _history(self, harness: str, target: Path) -> Path:
        if harness not in SUPPORTED_HARNESSES:
            raise ValueError(f"unsupported local-skill harness: {harness}")
        scope = hashlib.sha256(str(target.parent.parent.absolute()).encode("utf-8")).hexdigest()[:16]
        return self.state_dir / "history" / harness / scope

    @staticmethod
    def _digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
