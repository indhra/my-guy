import os

import pytest

from router.config import SkillRoot
from router.discovery import discover_named_roots, discover_skills


@pytest.fixture(autouse=True)
def private_skill_fixture_umask():
    previous = os.umask(0o022)
    try:
        yield
    finally:
        os.umask(previous)


def test_private_trusted_root_under_shared_parent_is_not_discovered(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    shared.chmod(0o777)
    root = shared / "private"
    skill = root / "security" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: security\ndescription: Review authentication security.\n---\n")

    assert discover_named_roots((SkillRoot("reviewed", str(root), "local"),)) == ()


def test_mutable_or_nonregular_skill_file_cannot_gain_local_trust(tmp_path):
    skill = tmp_path / "security" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("---\nname: security\ndescription: Review authentication security.\n---\n")
    roots = (SkillRoot("reviewed", str(tmp_path), "local"),)
    for mode in (0o664, 0o666):
        skill.chmod(mode)
        assert discover_named_roots(roots) == ()

    skill.unlink()
    os.mkfifo(skill)
    assert discover_named_roots(roots) == ()
    skill.unlink()
    real = tmp_path / "real.md"
    real.write_text("---\nname: security\ndescription: Review authentication security.\n---\n")
    skill.symlink_to(real)
    assert discover_named_roots(roots) == ()


def test_discovers_frontmatter_without_executing_skill(tmp_path):
    skill = tmp_path / "security-review" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text(
        "---\nname: security-review\ndescription: Review authentication and privacy threats.\n---\n"
        "Do not execute this body.\n",
        encoding="utf-8",
    )

    discovered = discover_skills([tmp_path])

    assert len(discovered) == 1
    assert discovered[0].id == "security-review"
    assert discovered[0].source.endswith("security-review")
    assert "authentication" in discovered[0].triggers


def test_ignores_missing_or_malformed_skill_metadata(tmp_path):
    (tmp_path / "missing.md").write_text("not a skill", encoding="utf-8")
    malformed = tmp_path / "bad" / "SKILL.md"
    malformed.parent.mkdir()
    malformed.write_text("---\nname: bad\n---\n", encoding="utf-8")

    assert discover_skills([tmp_path]) == ()


def test_multiline_description_and_root_namespace_are_preserved(tmp_path):
    skill = tmp_path / "review" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text(
        "---\nname: review\ndescription: |\n  Reviews security and privacy.\n  Preserves evidence.\n---\n",
        encoding="utf-8",
    )
    result = discover_named_roots((SkillRoot("ecc", str(tmp_path), "local"),))[0]
    assert result.id == "ecc:review"
    assert result.trust == "local"
    assert result.description == "Reviews security and privacy. Preserves evidence."


def test_invalid_third_party_skill_name_is_isolated(tmp_path):
    skill = tmp_path / "bad" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("---\nname: bad name!\ndescription: malformed external metadata\n---\n")
    assert discover_skills([tmp_path]) == ()


def test_duplicate_names_get_stable_non_shadowing_ids(tmp_path):
    for directory in ("one", "two"):
        skill = tmp_path / directory / "SKILL.md"
        skill.parent.mkdir()
        skill.write_text(
            f"---\nname: review\ndescription: Review code safely from {directory}.\n---\n"
        )
    results = discover_named_roots((SkillRoot("local", str(tmp_path)),))
    assert len(results) == 2
    assert len({item.id for item in results}) == 2
    assert all(item.id.startswith("local:review:") for item in results)


def test_trusted_symlink_root_does_not_become_routable(tmp_path):
    real = tmp_path / "real"
    skill = real / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: review\ndescription: Review security.\n---\n")
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    assert discover_named_roots((SkillRoot("linked", str(linked), "local"),)) == ()


def test_shared_writable_trusted_root_does_not_become_routable(tmp_path):
    root = tmp_path / "shared"
    skill = root / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: review\ndescription: Review security.\n---\n")
    root.chmod(0o777)
    assert discover_named_roots((SkillRoot("shared", str(root), "local"),)) == ()
