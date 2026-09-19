from router.discovery import discover_skills


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
