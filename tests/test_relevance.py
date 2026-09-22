from router.config import SkillRoot
from router.core import route
from router.discovery import discover_named_roots
from router.models import Capability


def test_exact_mirrored_skills_are_collapsed(tmp_path):
    for directory in ("one", "two"):
        skill = tmp_path / directory / "SKILL.md"
        skill.parent.mkdir()
        skill.write_text("---\nname: review\ndescription: Same mirrored skill.\n---\n")
    results = discover_named_roots((SkillRoot("local", str(tmp_path)),))
    assert len(results) == 1
    assert results[0].id == "local:review"


def test_convene_excludes_weaker_incidental_matches():
    strong_security = Capability(
        "security",
        "ecc",
        "Security",
        (),
        ("security", "authentication"),
        "skill:security",
        "local",
    )
    strong_design = Capability(
        "design",
        "gstack",
        "Design",
        (),
        ("design", "browser"),
        "skill:design",
        "local",
    )
    weak = Capability("weak", "local", "Weak", (), ("security",), "skill:weak", "local")
    decision = route(
        "security authentication design browser",
        (strong_security, strong_design, weak),
    )
    assert decision.status == "convene"
    assert decision.candidates == ("design", "security")
