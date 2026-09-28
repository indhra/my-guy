import hashlib
import json
import os
from pathlib import Path

import pytest

from router.lifecycle import SkillInstaller


@pytest.fixture(autouse=True)
def private_skill_fixture_umask():
    previous = os.umask(0o022)
    try:
        yield
    finally:
        os.umask(previous)


def test_inspection_is_read_only_and_reports_lifecycle_states(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("one", encoding="utf-8")
    state_dir = tmp_path / "state"
    root = tmp_path / "skills"
    installer = SkillInstaller(state_dir, source)

    missing = installer.inspect("codex", root)
    assert missing.state == "missing"
    assert missing.digest is None
    assert missing.bundled_digest
    assert missing.next_actions
    assert not state_dir.exists()
    assert not root.exists()

    installed = installer.install("codex", root)
    ready = installer.inspect("codex", root)
    assert ready.state == "ready"
    assert ready.enabled and ready.owned
    assert ready.digest == installed.digest == ready.bundled_digest
    assert ready.target == str(root / "my-guy" / "SKILL.md")

    target = Path(installed.target)
    target.write_text("user edit", encoding="utf-8")
    changed = installer.inspect("codex", root)
    assert changed.state == "modified"
    assert not changed.owned
    assert changed.digest != changed.bundled_digest


def test_owned_outdated_skill_reports_upgrade_without_replacement_approval(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("old", encoding="utf-8")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    installer.install("codex", root)
    source.write_text("new", encoding="utf-8")

    status = installer.inspect("codex", root)
    assert status.state == "modified" and status.owned
    assert any("upgrade" in action for action in status.next_actions)
    installer.upgrade("codex", root)
    assert installer.inspect("codex", root).state == "ready"


def test_unknown_or_modified_target_requires_explicit_replacement(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("new", encoding="utf-8")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = root / "my-guy" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("someone else's skill", encoding="utf-8")

    with pytest.raises(PermissionError, match="replace-existing"):
        installer.install("codex", root)
    assert target.read_text(encoding="utf-8") == "someone else's skill"
    assert not (tmp_path / "state").exists()

    installer.install("codex", root, replace_existing=True)
    assert target.read_text(encoding="utf-8") == "new"
    history = installer._history("codex", target)
    snapshots_before = tuple(history.glob("*.json"))
    installer.install("codex", root)
    assert target.read_text(encoding="utf-8") == "new"
    assert tuple(history.glob("*.json")) == snapshots_before
    installer.rollback("codex", root)
    assert target.read_text(encoding="utf-8") == "someone else's skill"
    assert not installer.inspect("codex", root).owned


def test_owned_uninstall_can_be_rolled_back_and_refuses_local_edits(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("owned", encoding="utf-8")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = Path(installer.install("claude", root).target)

    target.write_text("edited", encoding="utf-8")
    with pytest.raises(PermissionError, match="modified"):
        installer.uninstall("claude", root)
    assert target.read_text(encoding="utf-8") == "edited"
    target.write_text("owned", encoding="utf-8")

    installer.uninstall("claude", root)
    assert installer.inspect("claude", root).state == "missing"
    assert not target.exists()
    installer.rollback("claude", root)
    assert installer.inspect("claude", root).state == "ready"
    assert target.read_text(encoding="utf-8") == "owned"


def test_disabled_owned_install_is_reported_and_can_be_uninstalled(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("owned", encoding="utf-8")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    installer.install("opencode", root)
    installer.disable("opencode", root)
    status = installer.inspect("opencode", root)
    assert status.state == "disabled" and status.owned
    installer.uninstall("opencode", root)
    assert installer.inspect("opencode", root).state == "missing"
    installer.rollback("opencode", root)
    assert installer.inspect("opencode", root).state == "disabled"


def test_rollback_rejects_symlinked_history_without_touching_install(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("owned", encoding="utf-8")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = Path(installer.install("codex", root).target)
    history = installer._history("codex", target)
    moved = tmp_path / "moved-history"
    history.rename(moved)
    history.symlink_to(moved, target_is_directory=True)

    with pytest.raises(PermissionError, match="symlinked"):
        installer.rollback("codex", root)
    assert target.read_text(encoding="utf-8") == "owned"


def test_install_upgrade_disable_and_rollback_are_reversible(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("version one", encoding="utf-8")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"

    installed = installer.install("codex", root)
    target = Path(installed.target)
    assert target.read_text() == "version one"

    source.write_text("version two", encoding="utf-8")
    installer.upgrade("codex", root)
    assert target.read_text() == "version two"
    installer.rollback("codex", root)
    assert target.read_text() == "version one"

    installer.disable("codex", root)
    assert not target.exists()
    assert target.with_suffix(".md.disabled").exists()
    installer.rollback("codex", root)
    assert target.exists()


def test_installer_rejects_unknown_harness_and_symlink_target(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("safe", encoding="utf-8")
    installer = SkillInstaller(tmp_path / "state", source)
    with pytest.raises(ValueError):
        installer.install("openrouter", tmp_path / "skills")

    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(PermissionError):
        installer.install("codex", linked)


def test_rollback_history_is_scoped_to_exact_install_root(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("one", encoding="utf-8")
    installer = SkillInstaller(tmp_path / "state", source)
    first = tmp_path / "first"
    second = tmp_path / "second"
    installer.install("codex", first)
    source.write_text("two", encoding="utf-8")
    installer.install("codex", second)
    installer.rollback("codex", second)
    assert (first / "my-guy" / "SKILL.md").read_text() == "one"
    assert not (second / "my-guy" / "SKILL.md").exists()


def test_dotdot_root_uses_same_receipt_scope(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("safe")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    installer.install("codex", root)
    assert installer.inspect("codex", root / ".." / "skills").owned


def test_shared_writable_root_is_rejected(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("safe")
    root = tmp_path / "shared"
    root.mkdir(mode=0o777)
    root.chmod(0o777)
    installer = SkillInstaller(tmp_path / "state", source)
    with pytest.raises(PermissionError, match="shared-writable"):
        installer.install("codex", root)


def test_shared_writable_root_remains_rejected_with_private_child(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("safe")
    root = tmp_path / "shared"
    child = root / "my-guy"
    child.mkdir(parents=True, mode=0o700)
    child.chmod(0o700)
    root.chmod(0o777)
    installer = SkillInstaller(tmp_path / "state", source)
    with pytest.raises(PermissionError, match="shared-writable"):
        installer.install("codex", root)


def test_private_install_root_under_shared_parent_is_rejected(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("safe")
    shared = tmp_path / "shared"
    shared.mkdir()
    shared.chmod(0o777)
    root = shared / "private"
    root.mkdir(mode=0o700)
    installer = SkillInstaller(tmp_path / "state", source)

    with pytest.raises(PermissionError, match="shared-writable"):
        installer.install("codex", root)
    assert not (root / "my-guy" / "SKILL.md").exists()


@pytest.mark.parametrize("mode", [0o777, 0o775])
def test_inspect_reports_root_that_became_unsafe_after_install(tmp_path, mode):
    source = tmp_path / "source.md"
    source.write_text("safe")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    installer.install("codex", root)
    root.chmod(mode)

    status = installer.inspect("codex", root)
    assert status.state == "unsafe"
    assert status.enabled
    assert not status.owned
    assert "shared-writable" in status.summary
    with pytest.raises(PermissionError, match="shared-writable"):
        installer.upgrade("codex", root)


def test_inspect_reports_symlinked_root_after_install(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("safe")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    installer.install("codex", root)
    moved = tmp_path / "moved"
    root.rename(moved)
    root.symlink_to(moved, target_is_directory=True)

    status = installer.inspect("codex", root)
    assert status.state == "unsafe"
    assert "symlinked" in status.summary


@pytest.mark.parametrize("prior", ["absent", "owned", "unknown", "disabled"])
@pytest.mark.parametrize("failure_after_replace", [False, True])
def test_receipt_replace_failure_restores_exact_prior_state(monkeypatch, tmp_path, prior, failure_after_replace):
    source = tmp_path / "source.md"
    source.write_text("version one")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = root / "my-guy" / "SKILL.md"
    disabled = target.with_suffix(".md.disabled")
    if prior == "owned":
        installer.install("codex", root)
    elif prior == "unknown":
        target.parent.mkdir(parents=True)
        target.write_text("unknown prior content")
    elif prior == "disabled":
        installer.install("codex", root)
        installer.disable("codex", root)
    source.write_text("version two")
    receipt = installer._receipt_path("codex", target)
    before = tuple(path.read_bytes() if path.exists() else None for path in (target, disabled, receipt))
    snapshots_before = len(tuple(installer._history("codex", target).glob("*.json")))
    original_replace = os.replace
    failed = False

    def receipt_failure(src, dst):
        nonlocal failed
        if Path(dst) == receipt and not failed:
            failed = True
            if failure_after_replace:
                original_replace(src, dst)
            raise OSError("injected receipt replace failure")
        return original_replace(src, dst)

    monkeypatch.setattr("router.lifecycle.os.replace", receipt_failure)
    action = installer.install if prior in {"absent", "unknown"} else installer.upgrade
    kwargs = {"replace_existing": True} if prior == "unknown" else {}
    with pytest.raises(OSError, match="injected receipt replace failure"):
        action("codex", root, **kwargs)
    monkeypatch.setattr("router.lifecycle.os.replace", original_replace)

    after = tuple(path.read_bytes() if path.exists() else None for path in (target, disabled, receipt))
    assert after == before
    assert len(tuple(installer._history("codex", target).glob("*.json"))) > snapshots_before
    status = installer.inspect("codex", root)
    assert status.state == {
        "absent": "missing", "owned": "modified", "unknown": "modified", "disabled": "disabled",
    }[prior]
    assert status.owned == (prior in {"owned", "disabled"})
    if prior in {"absent", "owned", "disabled"}:
        installer.rollback("codex", root)


def test_receipt_stage_failure_does_not_mutate_target(monkeypatch, tmp_path):
    source = tmp_path / "source.md"
    source.write_text("new")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = root / "my-guy" / "SKILL.md"

    def failed_stage(*args):
        raise OSError("injected receipt stage failure")

    monkeypatch.setattr(installer, "_stage_receipt", failed_stage)
    with pytest.raises(OSError, match="injected receipt stage failure"):
        installer.install("codex", root)
    assert not target.exists()
    assert installer.inspect("codex", root).state == "missing"


def test_receipt_recovery_failure_reports_snapshot(monkeypatch, tmp_path):
    source = tmp_path / "source.md"
    source.write_text("old")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = Path(installer.install("codex", root).target)
    receipt = installer._receipt_path("codex", target)
    source.write_text("new")
    original_replace = os.replace
    target_replacements = 0

    def fail_commit_and_recovery(src, dst):
        nonlocal target_replacements
        if Path(dst) == target:
            target_replacements += 1
            if target_replacements == 2:
                raise OSError("injected target recovery failure")
        if Path(dst) == receipt:
            raise OSError("injected receipt commit failure")
        return original_replace(src, dst)

    monkeypatch.setattr("router.lifecycle.os.replace", fail_commit_and_recovery)
    with pytest.raises(RuntimeError, match="recovery also failed.*snapshot"):
        installer.upgrade("codex", root)
    assert tuple(installer._history("codex", target).glob("*.json"))
    assert tuple(target.parent.glob(".my-guy-prior-*"))
    assert tuple(receipt.parent.glob(".my-guy-prior-*"))


@pytest.mark.parametrize("disabled", [False, True])
@pytest.mark.parametrize("mode", [0o664, 0o666])
def test_mutable_installed_skill_is_unsafe_and_cannot_be_changed(tmp_path, disabled, mode):
    source = tmp_path / "source.md"
    source.write_text("safe")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = Path(installer.install("codex", root).target)
    if disabled:
        installer.disable("codex", root)
        target = target.with_suffix(".md.disabled")
    target.chmod(mode)

    status = installer.inspect("codex", root)
    assert status.state == "unsafe"
    assert not status.owned
    assert "shared-writable skill file" in status.summary
    for action in (installer.install, installer.upgrade, installer.rollback):
        with pytest.raises(PermissionError, match="unsafe"):
            action("codex", root)
    assert target.stat().st_mode & 0o777 == mode


@pytest.mark.parametrize("unsafe_part", ["receipt_directory", "receipt_file"])
def test_untrusted_receipt_cannot_claim_modified_skill(tmp_path, unsafe_part):
    source = tmp_path / "source.md"
    source.write_text("bundled")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = Path(installer.install("codex", root).target)
    target.write_text("unknown skill")
    receipt = installer._receipt_path("codex", target)
    forged = json.dumps({"harness": "codex", "target": str(target),
                         "digest": hashlib.sha256(target.read_bytes()).hexdigest()})
    if unsafe_part == "receipt_directory":
        receipt.parent.chmod(0o777)
        replacement = receipt.parent / "replacement.json"
        replacement.write_text(forged)
        os.replace(replacement, receipt)
    else:
        receipt.chmod(0o666)
        receipt.write_text(forged)
    assert installer.inspect("codex", root).owned is False
    with pytest.raises(PermissionError):
        installer.upgrade("codex", root)
    assert target.read_text() == "unknown skill"


@pytest.mark.parametrize("unsafe_part", ["history_directory", "manifest", "backup"])
def test_untrusted_history_cannot_drive_rollback(tmp_path, unsafe_part):
    source = tmp_path / "source.md"
    source.write_text("one")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = Path(installer.install("codex", root).target)
    source.write_text("two")
    installer.upgrade("codex", root)
    history = installer._history("codex", target)
    manifest = sorted(history.glob("*.json"))[-1]
    if unsafe_part == "history_directory":
        history.chmod(0o777)
        replacement = history / "replacement.json"
        replacement.write_text(json.dumps({"receipt": None}))
        os.replace(replacement, manifest)
    elif unsafe_part == "manifest":
        manifest.write_text(json.dumps({"receipt": None}))
        manifest.chmod(0o666)
    else:
        backup = history / json.loads(manifest.read_text())["enabled"]["file"]
        backup.chmod(0o666)
    with pytest.raises(PermissionError):
        installer.rollback("codex", root)
    assert target.read_text() == "two"
    assert manifest.exists()


def test_state_metadata_created_private_even_with_open_umask(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("bundled")
    installer = SkillInstaller(tmp_path / "state", source)
    old = os.umask(0)
    try:
        target = Path(installer.install("codex", tmp_path / "skills").target)
    finally:
        os.umask(old)
    state = tmp_path / "state"
    for directory in (state, state / "receipts", state / "receipts" / "codex", installer._history("codex", target)):
        assert directory.stat().st_mode & 0o777 == 0o700
    for metadata in state.rglob("*"):
        if metadata.is_file():
            assert metadata.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("history", ["active", "disabled"])
@pytest.mark.parametrize("failure", ["stage", "replace_before", "replace_after"])
def test_rollback_receipt_failure_restores_pre_rollback_state_and_can_retry(
    monkeypatch, tmp_path, history, failure,
):
    source = tmp_path / "source.md"
    source.write_text("version one")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = Path(installer.install("codex", root).target)
    disabled = target.with_suffix(".md.disabled")
    if history == "active":
        source.write_text("version two")
        installer.upgrade("codex", root)
    else:
        installer.disable("codex", root)
    receipt = installer._receipt_path("codex", target)
    before = tuple(path.read_bytes() if path.exists() else None for path in (target, disabled, receipt))
    manifest = sorted(installer._history("codex", target).glob("*.json"))[-1]

    if failure == "stage":
        original_stage = installer._stage_receipt
        failed = False

        def fail_stage(*args):
            nonlocal failed
            if not failed:
                failed = True
                assert tuple(path.read_bytes() if path.exists() else None for path in (target, disabled)) != before[:2]
                raise OSError("injected rollback receipt stage failure")
            return original_stage(*args)

        monkeypatch.setattr(installer, "_stage_receipt", fail_stage)
    else:
        original_replace = os.replace
        failed = False

        def fail_replace(src, dst):
            nonlocal failed
            if Path(dst) == receipt and not failed:
                failed = True
                if failure == "replace_after":
                    original_replace(src, dst)
                raise OSError("injected rollback receipt replace failure")
            return original_replace(src, dst)

        monkeypatch.setattr("router.lifecycle.os.replace", fail_replace)

    with pytest.raises(OSError, match="injected rollback receipt"):
        installer.rollback("codex", root)
    assert tuple(path.read_bytes() if path.exists() else None for path in (target, disabled, receipt)) == before
    assert manifest.exists()
    installer.rollback("codex", root)
    assert not manifest.exists()


def test_rollback_recovery_failure_keeps_snapshot_and_prior_backups(monkeypatch, tmp_path):
    source = tmp_path / "source.md"
    source.write_text("old")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = Path(installer.install("codex", root).target)
    source.write_text("new")
    installer.upgrade("codex", root)
    receipt = installer._receipt_path("codex", target)
    original_replace = os.replace
    target_replacements = 0

    def fail_commit_and_recovery(src, dst):
        nonlocal target_replacements
        if Path(dst) == target:
            target_replacements += 1
            if target_replacements == 2:
                raise OSError("injected rollback recovery failure")
        if Path(dst) == receipt:
            raise OSError("injected rollback receipt failure")
        return original_replace(src, dst)

    monkeypatch.setattr("router.lifecycle.os.replace", fail_commit_and_recovery)
    with pytest.raises(RuntimeError, match="recovery also failed.*snapshot"):
        installer.rollback("codex", root)
    assert tuple(installer._history("codex", target).glob("*.json"))
    assert tuple(target.parent.glob(".my-guy-prior-*"))
    assert tuple(receipt.parent.glob(".my-guy-prior-*"))


def test_root_swap_after_snapshot_does_not_redirect_install(monkeypatch, tmp_path):
    source = tmp_path / "source.md"
    source.write_text("safe")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    root.mkdir(mode=0o700)
    original_snapshot = installer._snapshot

    def swap_root(*args):
        original_snapshot(*args)
        root.rename(tmp_path / "moved")
        root.mkdir(mode=0o700)

    monkeypatch.setattr(installer, "_snapshot", swap_root)
    with pytest.raises(PermissionError, match="changed during"):
        installer.install("codex", root)
    assert not (root / "my-guy" / "SKILL.md").exists()


def test_target_changed_after_snapshot_is_not_overwritten(monkeypatch, tmp_path):
    source = tmp_path / "source.md"
    source.write_text("safe")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = root / "my-guy" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("reviewed")
    original_snapshot = installer._snapshot

    def changed_after_snapshot(*args):
        original_snapshot(*args)
        target.write_text("changed after review")

    monkeypatch.setattr(installer, "_snapshot", changed_after_snapshot)
    with pytest.raises(PermissionError, match="changed during"):
        installer.install("codex", root, replace_existing=True)
    assert target.read_text() == "changed after review"


def test_owned_target_changed_after_inspect_is_not_removed(monkeypatch, tmp_path):
    source = tmp_path / "source.md"
    source.write_text("safe")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = Path(installer.install("codex", root).target)
    original_safe_parent = installer._safe_parent

    def changed_after_inspect(path):
        original_safe_parent(path)
        target.write_text("changed after inspect")

    monkeypatch.setattr(installer, "_safe_parent", changed_after_inspect)
    with pytest.raises(PermissionError, match="changed during"):
        installer.uninstall("codex", root)
    assert target.read_text() == "changed after inspect"


@pytest.mark.parametrize("action", ["disable", "uninstall"])
def test_owned_mutation_rechecks_target_after_snapshot(monkeypatch, tmp_path, action):
    source = tmp_path / "source.md"
    source.write_text("safe")
    installer = SkillInstaller(tmp_path / "state", source)
    root = tmp_path / "skills"
    target = Path(installer.install("codex", root).target)
    original_snapshot = installer._snapshot

    def changed_after_snapshot(*args):
        original_snapshot(*args)
        target.write_text("changed after review")

    monkeypatch.setattr(installer, "_snapshot", changed_after_snapshot)
    with pytest.raises(PermissionError, match="changed during"):
        getattr(installer, action)("codex", root)
    assert target.read_text() == "changed after review"
