"""Static recognition checks for the installed front-door skill.

Each supported host discovers skills as ``<root>/<name>/SKILL.md`` whose
frontmatter satisfies host-specific rules: the ``name`` must match its
directory, ``description`` is required and bounded, and unknown frontmatter
keys can break a stricter host's parser. These checks verify what is
verifiable on disk; whether a running host actually lists the skill remains a
runtime observation reported separately.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from .discovery import _frontmatter
from .path_safety import unsafe_skill_file

_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME_LENGTH = 64
DEFAULT_DESCRIPTION_MAX = 1024


@dataclass(frozen=True)
class HostSpec:
    harness: str
    allowed_frontmatter_keys: frozenset[str]
    description_max: int = DEFAULT_DESCRIPTION_MAX


HOST_SPECS: dict[str, HostSpec] = {
    "claude": HostSpec(
        "claude",
        frozenset({"name", "description", "license", "allowed-tools", "metadata"}),
    ),
    "codex": HostSpec("codex", frozenset({"name", "description"})),
    "opencode": HostSpec("opencode", frozenset({"name", "description"})),
    "agents": HostSpec("agents", frozenset({"name", "description"})),
}


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


def recognition_check(harness: str, root: Path) -> RecognitionReport:
    """Validate an installed front-door skill against the host's format rules."""
    spec = HOST_SPECS[harness]
    target = Path(root).expanduser() / "my-guy" / "SKILL.md"
    checks: list[RecognitionCheck] = []

    def report(state: str, summary: str) -> RecognitionReport:
        return RecognitionReport(harness, str(target), state, tuple(checks), summary)

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
            bool(description) and len(description) <= spec.description_max,
            f"description is present and at most {spec.description_max} characters",
        )
    )
    unknown = sorted(set(metadata) - spec.allowed_frontmatter_keys)
    checks.append(
        RecognitionCheck(
            "frontmatter_keys",
            not unknown,
            f"no frontmatter keys outside the {harness} set"
            + (f" (unexpected: {', '.join(unknown)})" if unknown else ""),
        )
    )
    if all(check.passed for check in checks):
        return report("recognized", f"SKILL.md conforms to the {harness} skill format.")
    failed = ", ".join(check.name for check in checks if not check.passed)
    return report("invalid", f"SKILL.md fails {harness} recognition checks: {failed}.")


def host_spec(harness: str) -> HostSpec:
    if harness not in HOST_SPECS:
        raise ValueError(f"unsupported host for recognition: {harness}")
    return HOST_SPECS[harness]
