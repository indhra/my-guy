from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .path_safety import unsafe_private_state_path, unsafe_skill_file, unsafe_skill_root


SUPPORTED_HARNESSES = frozenset({"agents", "claude", "codex", "opencode"})


def standard_skill_roots() -> dict[str, Path]:
    home = Path.home()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    return {
        "agents": home / ".agents" / "skills",
        "claude": home / ".claude" / "skills",
        "codex": home / ".codex" / "skills",
        "opencode": config_home / "opencode" / "skills",
    }


@dataclass(frozen=True)
class InstallResult:
    action: str
    harness: str
    target: str
    digest: str | None


@dataclass(frozen=True)
class InstallStatus:
    harness: str
    root: str
    target: str
    state: str
    enabled: bool
    owned: bool
    digest: str | None
    disabled_digest: str | None
    bundled_digest: str
    summary: str
    next_actions: tuple[str, ...]


class SkillInstaller:
    """Reversible installer for the portable my-guy SKILL.md front door."""

    def __init__(self, state_dir: Path, source: Path | None = None) -> None:
        self.state_dir = state_dir
        self.source = source or Path(__file__).parent / "resources" / "my-guy" / "SKILL.md"

    def inspect(self, harness: str, root: Path) -> InstallStatus:
        try:
            target = self._target(harness, root)
        except PermissionError as error:
            # Status must describe a retargeted root without reading through it.
            target = Path(os.path.normpath(str(root.expanduser().absolute()))) / "my-guy" / "SKILL.md"
            return self._unsafe_status(harness, target, str(error))
        disabled = target.with_suffix(".md.disabled")
        if reason := unsafe_skill_root(target.parent.parent) or unsafe_skill_root(target.parent):
            return self._unsafe_status(harness, target, reason)
        try:
            self._guard(disabled)
        except PermissionError as error:
            return self._unsafe_status(harness, target, str(error))
        for path in (target, disabled):
            if path.exists() and (reason := unsafe_skill_file(path)):
                return self._unsafe_status(harness, target, f"{path}: {reason}")
        bundled = self._digest(self.source)
        active = target.is_file()
        inactive = disabled.is_file()
        path = target if active else disabled if inactive else None
        digest = self._digest(path) if path else None
        disabled_digest = self._digest(disabled) if inactive else None
        try:
            receipt = self._read_receipt(harness, target)
        except PermissionError as error:
            return self._unsafe_status(harness, target, str(error))
        owned = bool(receipt and digest and receipt["digest"] == digest and active != inactive)
        if active and inactive:
            state, summary = "modified", "Both enabled and disabled skill files exist."
        elif active and owned and digest == bundled:
            state, summary = "ready", "The bundled skill is installed and enabled."
        elif inactive and owned:
            state, summary = "disabled", "The owned skill is disabled."
        elif active and owned:
            state, summary = "modified", "The owned skill differs from this CLI's bundled version."
        elif path:
            state, summary = "modified", "The existing skill is unknown or changed."
        else:
            state, summary = "missing", "No My Guy skill is installed at this root."
        command_root = shlex.quote(str(target.parent.parent))
        custom_flag = (" --allow-custom-root" if target.parent.parent != standard_skill_roots()[harness].absolute() else "")
        if state == "ready":
            actions = ("Ask the host to reload or list skills to verify recognition.",)
        elif state == "disabled":
            actions = (f"Run my-guy rollback {harness} --root {command_root}{custom_flag} to re-enable the skill.",)
        elif state == "missing":
            actions = (f"Run my-guy install {harness} --root {command_root}{custom_flag} after reviewing the target.",)
        elif owned:
            actions = (f"Run my-guy upgrade {harness} --root {command_root}{custom_flag} to install this CLI's bundled skill.",)
        else:
            actions = ("Review the existing file and request explicit approval before --replace-existing.",)
        return InstallStatus(harness, str(target.parent.parent), str(target), state, active, owned,
                             digest, disabled_digest, bundled, summary, actions)

    def _unsafe_status(self, harness: str, target: Path, reason: str) -> InstallStatus:
        return InstallStatus(
            harness, str(target.parent.parent), str(target), "unsafe", target.is_file(), False,
            None, None, self._digest(self.source), f"Installation is unsafe: {reason}.",
            ("Secure the skill files, root, and ancestors, then run my-guy status again.",),
        )

    def install(self, harness: str, root: Path, *, replace_existing: bool = False) -> InstallResult:
        return self._write(harness, root, "install", replace_existing=replace_existing)

    def upgrade(self, harness: str, root: Path, *, replace_existing: bool = False) -> InstallResult:
        target = self._target(harness, root)
        if not target.exists() and not target.with_suffix(".md.disabled").exists():
            raise FileNotFoundError("my-guy is not installed for this harness")
        return self._write(harness, root, "upgrade", replace_existing=replace_existing)

    def disable(self, harness: str, root: Path) -> InstallResult:
        target = self._target(harness, root)
        disabled = target.with_suffix(".md.disabled")
        status = self.inspect(harness, root)
        if status.state == "unsafe":
            raise PermissionError(status.summary)
        if not target.exists():
            raise FileNotFoundError("enabled my-guy skill is not installed")
        if not status.owned:
            raise PermissionError("enabled skill is unknown or modified; review it before changing it")
        self._safe_parent(target)
        expected = self._identities(target, disabled)
        directories = self._directory_identities(target)
        self._assert_status_matches(status, target, disabled, expected)
        self._snapshot(harness, target, disabled)
        self._assert_directories_unchanged(directories)
        self._safe_parent(target)
        self._assert_unchanged(expected)
        os.replace(target, disabled)
        return InstallResult("disable", harness, str(disabled), self._digest(disabled))

    def uninstall(self, harness: str, root: Path) -> InstallResult:
        target = self._target(harness, root)
        disabled = target.with_suffix(".md.disabled")
        status = self.inspect(harness, root)
        if status.state == "unsafe":
            raise PermissionError(status.summary)
        if status.state == "missing":
            raise FileNotFoundError("my-guy is not installed for this harness")
        if not status.owned:
            raise PermissionError("skill is unknown or modified; refusing to uninstall it")
        self._safe_parent(target)
        expected = self._identities(target, disabled)
        directories = self._directory_identities(target)
        self._assert_status_matches(status, target, disabled, expected)
        self._snapshot(harness, target, disabled)
        self._assert_directories_unchanged(directories)
        self._safe_parent(target)
        self._assert_unchanged(expected)
        target.unlink(missing_ok=True)
        self._assert_directories_unchanged(directories)
        self._safe_parent(target)
        self._assert_unchanged({disabled: expected[disabled]})
        disabled.unlink(missing_ok=True)
        self._receipt_path(harness, target).unlink(missing_ok=True)
        return InstallResult("uninstall", harness, str(target), None)

    def rollback(self, harness: str, root: Path) -> InstallResult:
        target = self._target(harness, root)
        disabled = target.with_suffix(".md.disabled")
        status = self.inspect(harness, root)
        if status.state == "unsafe":
            raise PermissionError(status.summary)
        if status.state == "modified" and not status.owned:
            raise PermissionError("skill is unknown or modified; refusing to overwrite it during rollback")
        self._safe_parent(target)
        expected = self._identities(target, disabled)
        directories = self._directory_identities(target)
        self._assert_status_matches(status, target, disabled, expected)
        history = self._history(harness, target)
        self._check_state_path(history, directory=True)
        snapshots = sorted(history.glob("*.json"))
        if not snapshots:
            raise FileNotFoundError("no lifecycle snapshot is available")
        manifest_path = snapshots[-1]
        self._check_state_path(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or set(manifest) - {"enabled", "disabled", "receipt"}:
            raise ValueError("invalid lifecycle snapshot manifest")
        old_receipt = manifest.get("receipt")
        if old_receipt is not None:
            self._validate_receipt(old_receipt, harness, target)
        self._guard(target)
        self._guard(disabled)
        self._guard(self._receipt_path(harness, target))
        self._mkdir_private(target.parent)
        self._assert_directories_unchanged(directories, allow_created=True)
        self._safe_parent(target)
        directories = self._directory_identities(target)
        receipt = self._receipt_path(harness, target)
        prior = {**expected, **self._identities(receipt)}
        staged: dict[str, Path] = {}
        backups: dict[Path, Path | None] = {}
        restored: dict[Path, tuple[int, int, str] | None] = {target: None, disabled: None}
        new_receipt: Path | None = None
        written_receipt = prior[receipt]
        mutation_attempted = False
        recovery_failed = False
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
                if reason := unsafe_private_state_path(backup, self.state_dir):
                    raise PermissionError(f"unsafe lifecycle snapshot backup: {reason}")
                if self._digest(backup) != record["digest"]:
                    raise ValueError("lifecycle snapshot digest mismatch")
                descriptor, temporary = tempfile.mkstemp(prefix=".rollback-", dir=target.parent)
                os.close(descriptor)
                temporary_path = Path(temporary)
                shutil.copy2(backup, temporary_path)
                staged[key] = temporary_path
                restored[path] = self._identities(temporary_path)[temporary_path]
            for path in (target, disabled, receipt):
                backups[path] = self._stage_copy(path, ".my-guy-prior-")
            self._assert_directories_unchanged(directories)
            self._safe_parent(target)
            self._assert_unchanged(prior)
            mutation_attempted = True
            for key, path in (("enabled", target), ("disabled", disabled)):
                self._assert_directories_unchanged(directories)
                self._safe_parent(target)
                self._assert_unchanged({path: expected[path]})
                if key in staged:
                    os.replace(staged[key], path)
                    staged.pop(key)
                elif path.exists():
                    path.unlink()
            self._assert_directories_unchanged(directories)
            self._safe_parent(target)
            self._assert_unchanged({target: restored[target], disabled: restored[disabled], receipt: prior[receipt]})
            if old_receipt is None:
                written_receipt = None
                receipt.unlink(missing_ok=True)
            else:
                new_receipt = self._stage_receipt(harness, target, old_receipt["digest"])
                written_receipt = self._identities(new_receipt)[new_receipt]
                self._assert_unchanged({receipt: prior[receipt]})
                os.replace(new_receipt, receipt)
        except BaseException as error:
            if mutation_attempted:
                try:
                    self._restore_failed_write(
                        target, disabled, receipt, prior,
                        {**restored, receipt: written_receipt}, backups, directories,
                    )
                except Exception as recovery_error:
                    recovery_failed = True
                    retained = ", ".join(str(path) for path in backups.values() if path is not None)
                    raise RuntimeError(
                        f"rollback failed ({error}); recovery also failed ({recovery_error}); "
                        f"manual recovery snapshot: {manifest_path}; prior backups: {retained or 'none'}"
                    ) from error
            raise
        finally:
            for temporary_path in staged.values():
                temporary_path.unlink(missing_ok=True)
            if new_receipt is not None:
                new_receipt.unlink(missing_ok=True)
            if not recovery_failed:
                for backup in backups.values():
                    if backup is not None:
                        backup.unlink(missing_ok=True)
        manifest_path.unlink()
        return InstallResult("rollback", harness, str(target), self._digest(target) if target.exists() else None)

    def _write(self, harness: str, root: Path, action: str, *, replace_existing: bool = False) -> InstallResult:
        target = self._target(harness, root)
        disabled = target.with_suffix(".md.disabled")
        status = self.inspect(harness, root)
        if status.state == "unsafe":
            raise PermissionError(status.summary)
        if status.state == "ready" and action == "install":
            return InstallResult(action, harness, str(target), status.digest)
        if status.state != "missing" and not status.owned and not replace_existing:
            raise PermissionError("existing skill is unknown or modified; explicit --replace-existing approval is required")
        self._safe_parent(target)
        expected = self._identities(target, disabled)
        directories = self._directory_identities(target)
        self._assert_status_matches(status, target, disabled, expected)
        snapshot = self._snapshot(harness, target, disabled)
        self._assert_directories_unchanged(directories)
        self._safe_parent(target)
        self._mkdir_private(target.parent)
        self._assert_directories_unchanged(directories, allow_created=True)
        self._safe_parent(target)
        directories = self._directory_identities(target)
        content = self.source.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        receipt = self._receipt_path(harness, target)
        prior = {**expected, **self._identities(receipt)}
        backups: dict[Path, Path | None] = {}
        new_receipt: Path | None = None
        mutation_attempted = False
        recovery_failed = False
        fd, temporary = tempfile.mkstemp(prefix=".my-guy-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o644)
            new_target_identity = self._identities(Path(temporary))[Path(temporary)]
            for path in (target, disabled, receipt):
                backups[path] = self._stage_copy(path, ".my-guy-prior-")
            new_receipt = self._stage_receipt(harness, target, digest)
            new_receipt_identity = self._identities(new_receipt)[new_receipt]
            self._assert_directories_unchanged(directories)
            self._safe_parent(target)
            self._assert_unchanged(prior)
            mutation_attempted = True
            os.replace(temporary, target)
            if disabled.exists():
                self._assert_directories_unchanged(directories)
                self._safe_parent(target)
                self._assert_unchanged({disabled: expected[disabled]})
                disabled.unlink()
            self._assert_directories_unchanged(directories)
            self._safe_parent(target)
            self._assert_unchanged({target: new_target_identity, disabled: None, receipt: prior[receipt]})
            os.replace(new_receipt, receipt)
        except BaseException as error:
            if mutation_attempted:
                try:
                    self._restore_failed_write(
                        target, disabled, receipt, prior,
                        {target: new_target_identity, disabled: None, receipt: new_receipt_identity},
                        backups, directories,
                    )
                except Exception as recovery_error:
                    recovery_failed = True
                    retained = ", ".join(str(path) for path in backups.values() if path is not None)
                    raise RuntimeError(
                        f"{action} failed ({error}); recovery also failed ({recovery_error}); "
                        f"manual recovery snapshot: {snapshot}; prior backups: {retained or 'none'}"
                    ) from error
            raise
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
            if new_receipt is not None:
                new_receipt.unlink(missing_ok=True)
            if not recovery_failed:
                for backup in backups.values():
                    if backup is not None:
                        backup.unlink(missing_ok=True)
        return InstallResult(action, harness, str(target), digest)

    def _restore_failed_write(
        self, target: Path, disabled: Path, receipt: Path,
        prior: dict[Path, tuple[int, int, str] | None],
        written: dict[Path, tuple[int, int, str] | None],
        backups: dict[Path, Path | None],
        directories: dict[Path, tuple[int, int] | None],
    ) -> None:
        self._assert_directories_unchanged(directories)
        self._safe_parent(target)
        current = self._identities(target, disabled, receipt)
        for path in (target, disabled, receipt):
            if current[path] not in (prior[path], written[path]):
                raise PermissionError(f"{path} changed externally during recovery")
        for path in (target, disabled, receipt):
            if current[path] == prior[path]:
                continue
            backup = backups[path]
            if backup is None:
                path.unlink(missing_ok=True)
            else:
                os.replace(backup, path)
                backups[path] = None

    @staticmethod
    def _stage_copy(path: Path, prefix: str) -> Path | None:
        if not path.exists():
            return None
        descriptor, temporary = tempfile.mkstemp(prefix=prefix, dir=path.parent)
        os.close(descriptor)
        staged = Path(temporary)
        try:
            shutil.copy2(path, staged)
            with staged.open("rb") as handle:
                os.fsync(handle.fileno())
            return staged
        except BaseException:
            staged.unlink(missing_ok=True)
            raise

    def _target(self, harness: str, root: Path) -> Path:
        if harness not in SUPPORTED_HARNESSES:
            raise ValueError(f"unsupported local-skill harness: {harness}")
        if "\x00" in str(root):
            raise ValueError("invalid install root")
        raw_root = root.expanduser().absolute()
        self._guard(raw_root / "my-guy" / "SKILL.md")
        root = Path(os.path.normpath(str(raw_root)))
        if root in {Path("/"), Path.home()}:
            raise ValueError("install root must be a dedicated skills directory")
        target = root / "my-guy" / "SKILL.md"
        self._guard(target)
        return target

    @staticmethod
    def _guard(target: Path) -> None:
        for candidate in (target, *target.parents):
            if candidate.is_symlink():
                raise PermissionError("refusing to modify a symlinked skill target")

    @staticmethod
    def _safe_parent(target: Path) -> None:
        """Refuse roots that another local user can rename during an operation."""
        reason = unsafe_skill_root(target.parent.parent) or unsafe_skill_root(target.parent)
        if reason:
            raise PermissionError(f"refusing a {reason}")

    @staticmethod
    def _directory_identities(target: Path) -> dict[Path, tuple[int, int] | None]:
        result: dict[Path, tuple[int, int] | None] = {}
        for path in (target.parent, target.parent.parent, *target.parent.parent.parents):
            try:
                info = path.lstat()
            except FileNotFoundError:
                result[path] = None
                continue
            result[path] = (info.st_dev, info.st_ino)
            if path != target.parent and info.st_uid == os.geteuid() and not info.st_mode & 0o077:
                break
        return result

    @classmethod
    def _assert_directories_unchanged(cls, expected: dict[Path, tuple[int, int] | None],
                                      *, allow_created: bool = False) -> None:
        for path, identity in expected.items():
            if identity is None and allow_created:
                continue
            try:
                info = path.lstat()
                current = (info.st_dev, info.st_ino)
            except FileNotFoundError:
                current = None
            if current != identity:
                raise PermissionError("skill root changed during lifecycle operation")

    @staticmethod
    def _mkdir_private(path: Path) -> None:
        missing = []
        candidate = path
        while not candidate.exists():
            missing.append(candidate)
            candidate = candidate.parent
        for directory in reversed(missing):
            directory.mkdir(mode=0o700)

    def _identities(self, *paths: Path) -> dict[Path, tuple[int, int, str] | None]:
        result: dict[Path, tuple[int, int, str] | None] = {}
        for path in paths:
            self._guard(path)
            if path.is_relative_to(self.state_dir):
                self._check_state_path(path)
            try:
                info = path.lstat()
            except FileNotFoundError:
                result[path] = None
                continue
            if not stat.S_ISREG(info.st_mode):
                raise PermissionError("skill target is not a regular file")
            result[path] = (info.st_dev, info.st_ino, self._digest(path))
        return result

    def _assert_unchanged(self, expected: dict[Path, tuple[int, int, str] | None]) -> None:
        if self._identities(*expected) != expected:
            raise PermissionError("skill target changed during lifecycle operation")

    @staticmethod
    def _assert_status_matches(status: InstallStatus, target: Path, disabled: Path,
                               expected: dict[Path, tuple[int, int, str] | None]) -> None:
        active = expected[target]
        inactive = expected[disabled]
        primary_digest = active[2] if active else inactive[2] if inactive else None
        if (bool(active) != status.enabled or primary_digest != status.digest or
                (inactive[2] if inactive else None) != status.disabled_digest):
            raise PermissionError("skill target changed during lifecycle operation")

    def _snapshot(self, harness: str, target: Path, disabled: Path) -> Path:
        history = self._history(harness, target)
        self._check_state_path(history, directory=True)
        self._safe_parent(history / "snapshot")
        self._mkdir_private(history)
        self._check_state_path(history, directory=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        manifest: dict[str, object] = {"receipt": self._read_receipt(harness, target)}
        for key, path in (("enabled", target), ("disabled", disabled)):
            if path.exists():
                name = f"{stamp}-{key}.bak"
                shutil.copy2(path, history / name)
                os.chmod(history / name, 0o600)
                manifest[key] = {"file": name, "digest": self._digest(history / name)}
        manifest_path = history / f"{stamp}.json"
        self._check_state_path(manifest_path)
        descriptor = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, sort_keys=True)
        return manifest_path

    def _receipt_path(self, harness: str, target: Path) -> Path:
        scope = hashlib.sha256(str(target.parent.parent.absolute()).encode("utf-8")).hexdigest()[:16]
        return self.state_dir / "receipts" / harness / f"{scope}.json"

    @staticmethod
    def _validate_receipt(receipt: object, harness: str, target: Path) -> None:
        if (not isinstance(receipt, dict) or set(receipt) != {"harness", "target", "digest"}
                or receipt["harness"] != harness or receipt["target"] != str(target)
                or not isinstance(receipt["digest"], str)
                or len(receipt["digest"]) != 64
                or any(char not in "0123456789abcdef" for char in receipt["digest"])):
            raise ValueError("invalid installation receipt")

    def _read_receipt(self, harness: str, target: Path) -> dict[str, str] | None:
        path = self._receipt_path(harness, target)
        self._check_state_path(path)
        if not path.exists():
            return None
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
            self._validate_receipt(receipt, harness, target)
            return receipt
        except (ValueError, UnicodeError):
            return None

    def _stage_receipt(self, harness: str, target: Path, digest: str) -> Path:
        path = self._receipt_path(harness, target)
        self._check_state_path(path)
        self._mkdir_private(path.parent)
        self._check_state_path(path)
        descriptor, temporary = tempfile.mkstemp(prefix=".receipt-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump({"harness": harness, "target": str(target), "digest": digest}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            return Path(temporary)
        except BaseException:
            if os.path.exists(temporary):
                os.unlink(temporary)
            raise

    def _history(self, harness: str, target: Path) -> Path:
        if harness not in SUPPORTED_HARNESSES:
            raise ValueError(f"unsupported local-skill harness: {harness}")
        scope = hashlib.sha256(str(target.parent.parent.absolute()).encode("utf-8")).hexdigest()[:16]
        return self.state_dir / "history" / harness / scope

    @staticmethod
    def _digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _check_state_path(self, path: Path, *, directory: bool = False) -> None:
        if reason := unsafe_private_state_path(path, self.state_dir, directory=directory):
            raise PermissionError(reason)
