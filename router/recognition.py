"""Static Agent Skills format checks for the installed front-door skill.

Each supported harness discovers skills as ``<root>/<name>/SKILL.md``. These
checks verify what is verifiable on disk; whether a running harness actually
lists the skill remains a runtime observation reported separately.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from .discovery import _frontmatter
from .path_safety import unsafe_skill_file

_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME_LENGTH = 64
DEFAULT_DESCRIPTION_MAX = 1024
AGENT_SKILLS_FIELDS = frozenset(
    {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
)
SUPPORTED_HARNESSES = frozenset({"claude", "codex", "opencode", "agents"})


@dataclass(frozen=True)
class RecognitionCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class RecognitionReport:
    harness: str
    target: str
    state: str
    checks: tuple[RecognitionCheck, ...]
    summary: str
    warnings: tuple[str, ...]


def recognition_check(harness: str, root: Path) -> RecognitionReport:
    """Validate an installed front-door skill against the Agent Skills format."""
    if harness not in SUPPORTED_HARNESSES:
        raise ValueError(f"unsupported harness for recognition: {harness}")
    target = Path(root).expanduser() / "my-guy" / "SKILL.md"
    checks: list[RecognitionCheck] = []
    warnings: tuple[str, ...] = ()

    def report(state: str, summary: str) -> RecognitionReport:
        return RecognitionReport(
            harness, str(target), state, tuple(checks), summary, warnings
        )

    if not target.is_file():
        return report("missing", "No SKILL.md is installed for this host root.")
    if reason := unsafe_skill_file(target):
        return report("unsafe", f"Skill file is unsafe: {reason}.")
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return report("unsafe", f"Skill file is unreadable: {error}.")
    if len(text.encode("utf-8", errors="replace")) > 1_048_576:
        checks.append(RecognitionCheck("size", False, "SKILL.md exceeds the 1 MiB metadata bound"))
    metadata = _frontmatter(text)
    checks.append(
        RecognitionCheck("frontmatter", bool(metadata), "SKILL.md has a parseable frontmatter block")
    )
    name = metadata.get("name", "")
    checks.append(
        RecognitionCheck(
            "name",
            bool(name) and len(name) <= MAX_NAME_LENGTH and bool(_NAME_PATTERN.fullmatch(name)),
            "frontmatter name is a valid lowercase skill identifier",
        )
    )
    checks.append(
        RecognitionCheck(
            "name_matches_directory",
            name == target.parent.name,
            "frontmatter name matches the skill directory name",
        )
    )
    description = metadata.get("description", "")
    checks.append(
        RecognitionCheck(
            "description",
            bool(description) and len(description) <= DEFAULT_DESCRIPTION_MAX,
            "description is present and 1–1024 characters",
        )
    )
    unknown = sorted(set(metadata) - AGENT_SKILLS_FIELDS)
    warnings = tuple(f"unknown frontmatter key: {key}" for key in unknown)
    if all(check.passed for check in checks):
        return report(
            "recognized",
            "SKILL.md conforms to Agent Skills format checks "
            "(name matches directory, lowercase identifier ≤64 chars, "
            "description 1–1024 chars).",
        )
    failed = ", ".join(check.name for check in checks if not check.passed)
    return report("invalid", f"SKILL.md fails Agent Skills format checks: {failed}.")
