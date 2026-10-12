from pathlib import Path
from importlib import resources

import pytest

from router.lifecycle import SUPPORTED_HARNESSES
from router.recognition import HOST_SPECS, recognition_check


def _bundled_skill() -> str:
    return resources.files("router").joinpath("resources/my-guy/SKILL.md").read_text(
        encoding="utf-8"
    )


def _install_text(root: Path, text: str, *, directory: str = "my-guy") -> Path:
    target = root / directory / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text(text, encoding="utf-8")
    return target


def test_recognition_specs_cover_every_harness():
    assert set(HOST_SPECS) == set(SUPPORTED_HARNESSES)


def test_bundled_skill_is_recognized_on_every_host(tmp_path):
    for harness in sorted(HOST_SPECS):
        root = tmp_path / harness / "skills"
        _install_text(root, _bundled_skill())
        report = recognition_check(harness, root)
        assert report.state == "recognized", (harness, report.summary)
        assert all(check.passed for check in report.checks)


def test_missing_skill_reports_missing(tmp_path):
    report = recognition_check("claude", tmp_path / "skills")

    assert report.state == "missing"
    assert report.checks == ()


def test_skill_in_the_wrong_directory_reports_missing(tmp_path):
    root = tmp_path / "skills"
    _install_text(root, _bundled_skill(), directory="wrong-name")

    assert recognition_check("claude", root).state == "missing"


def test_frontmatter_name_must_match_skill_directory(tmp_path):
    root = tmp_path / "skills"
    _install_text(root, _bundled_skill().replace("name: my-guy", "name: other-guy"))
    report = recognition_check("claude", root)

    assert report.state == "invalid"
    assert any(
        check.name == "name_matches_directory" and not check.passed
        for check in report.checks
    )


def test_missing_description_is_invalid(tmp_path):
    root = tmp_path / "skills"
    _install_text(root, "---\nname: my-guy\n---\n\nBody.\n")
    report = recognition_check("codex", root)

    assert report.state == "invalid"
    assert any(
        check.name == "description" and not check.passed for check in report.checks
    )


def test_oversized_description_is_invalid(tmp_path):
    root = tmp_path / "skills"
    _install_text(
        root,
        "---\nname: my-guy\ndescription: " + "x" * 1025 + "\n---\n\nBody.\n",
    )
    report = recognition_check("claude", root)

    assert report.state == "invalid"
    assert any(
        check.name == "description" and not check.passed for check in report.checks
    )


def test_host_specific_frontmatter_keys(tmp_path):
    root = tmp_path / "skills"
    _install_text(
        root,
        "---\nname: my-guy\ndescription: Front door.\nallowed-tools: Bash(my-guy:*)\n---\n\nBody.\n",
    )

    assert recognition_check("claude", root).state == "recognized"
    report = recognition_check("codex", root)
    assert report.state == "invalid"
    assert any(
        check.name == "frontmatter_keys" and not check.passed for check in report.checks
    )
