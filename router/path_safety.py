"""Filesystem checks shared by trusted discovery and lifecycle operations."""

from __future__ import annotations

import os
import stat
from pathlib import Path


def has_symlink_component(path: Path) -> bool:
    """Inspect the raw path so `..` cannot erase a symlink from the check."""
    candidate = path.expanduser().absolute()
    return any(part.is_symlink() for part in (candidate, *candidate.parents))


def unsafe_skill_root(path: Path) -> str | None:
    """Return why other local users could replace or inject skill files."""
    if has_symlink_component(path):
        return "symlinked skill root"
    canonical = Path(os.path.normpath(str(path.expanduser().absolute())))
    # The filesystem root may be uid-mapped inside a sandbox/container.
    trusted_owners = {os.geteuid(), Path("/").stat().st_uid}
    child: Path | None = None
    for candidate in (canonical, *canonical.parents):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            child = candidate
            continue
        except OSError:
            return "inaccessible skill root or ancestor"
        if not stat.S_ISDIR(info.st_mode):
            return "skill root ancestor is not a directory"
        if info.st_uid not in trusted_owners:
            return "foreign-owned skill root or ancestor"
        if info.st_mode & 0o022:
            # A sticky parent protects an existing child owned by this user (or
            # root), but does not protect an absent child from being claimed.
            if candidate == canonical or not info.st_mode & stat.S_ISVTX or child is None:
                return "shared-writable skill root or ancestor"
            try:
                child_info = child.lstat()
            except OSError:
                return "shared-writable skill root or ancestor"
            if child_info.st_uid not in trusted_owners:
                return "shared-writable skill root or ancestor"
        child = candidate
    return None


def unsafe_skill_file(path: Path) -> str | None:
    """Reject skill metadata a different local user can replace or edit."""
    if has_symlink_component(path):
        return "symlinked skill file"
    if reason := unsafe_skill_root(path.parent):
        return reason
    try:
        info = path.lstat()
    except OSError:
        return "missing or inaccessible skill file"
    if not stat.S_ISREG(info.st_mode):
        return "skill file is not a regular file"
    if info.st_uid not in {os.geteuid(), Path("/").stat().st_uid}:
        return "foreign-owned skill file"
    if info.st_mode & 0o022:
        return "shared-writable skill file"
    return None


def unsafe_private_state_path(path: Path, state_dir: Path, *, directory: bool = False) -> str | None:
    """Check trusted installer metadata within its private state tree."""
    if has_symlink_component(path) or has_symlink_component(state_dir):
        return "symlinked state metadata path"
    root = Path(os.path.normpath(str(state_dir.expanduser().absolute())))
    candidate = Path(os.path.normpath(str(path.expanduser().absolute())))
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return "state metadata escapes its private directory"
    if reason := unsafe_skill_root(root):
        return f"unsafe state directory: {reason}"
    components = (root, *(root / Path(*relative.parts[:index]) for index in range(1, len(relative.parts) + 1)))
    for component in components:
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return "inaccessible state metadata path"
        is_file = component == candidate and not directory
        if info.st_uid != os.geteuid():
            return "foreign-owned state metadata"
        if is_file:
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
                return "unsafe state metadata file"
        elif not stat.S_ISDIR(info.st_mode) or (info.st_mode & (0o077 if component == root else 0o022)):
            return "unsafe state metadata directory"
    return None
