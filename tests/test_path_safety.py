from pathlib import Path
from tempfile import TemporaryDirectory

from router.path_safety import unsafe_skill_root


STICKY_TMP = Path("/tmp").resolve(strict=True)


def test_private_root_under_sticky_tmp_is_safe():
    with TemporaryDirectory(prefix="my-guy-path-", dir=STICKY_TMP) as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        assert unsafe_skill_root(root) is None


def test_group_writable_root_without_private_ancestor_is_unsafe():
    with TemporaryDirectory(prefix="my-guy-path-", dir=STICKY_TMP) as temporary:
        base = Path(temporary)
        base.chmod(0o755)
        root = base / "skills"
        root.mkdir(mode=0o775)
        root.chmod(0o775)
        assert "shared-writable" in unsafe_skill_root(root)


def test_private_root_under_nonsticky_shared_parent_is_unsafe(tmp_path):
    shared = tmp_path.resolve(strict=True) / "shared"
    shared.mkdir()
    shared.chmod(0o777)
    root = shared / "private"
    root.mkdir(mode=0o700)

    assert "shared-writable" in unsafe_skill_root(root)


def test_private_root_under_group_writable_parent_is_unsafe(tmp_path):
    shared = tmp_path.resolve(strict=True) / "shared"
    shared.mkdir()
    shared.chmod(0o775)
    root = shared / "private"
    root.mkdir(mode=0o700)

    assert "shared-writable" in unsafe_skill_root(root)


def test_missing_root_directly_under_sticky_tmp_is_unsafe():
    # Another user can claim a predictable absent name before installation.
    assert "shared-writable" in unsafe_skill_root(STICKY_TMP / "my-guy-missing-root-for-test")
