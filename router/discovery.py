import re
from pathlib import Path

from .models import Capability


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip().strip('"\'')
    return values


def discover_skills(roots: list[str | Path]) -> tuple[Capability, ...]:
    """Discover skill metadata without executing skill instructions."""
    capabilities: list[Capability] = []
    for root in roots:
        root_path = Path(root).expanduser()
        if not root_path.exists():
            continue
        for path in sorted(root_path.rglob("SKILL.md")):
            if path.is_symlink():
                continue
            try:
                metadata = _frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            name = metadata.get("name")
            description = metadata.get("description")
            if not name or not description:
                continue
            source = str(path.parent)
            capabilities.append(
                Capability(
                    id=name,
                    source=source,
                    description=description,
                    domains=(),
                    triggers=tuple(_keywords(f"{name} {description}")),
                    invocation=f"skill:{name}",
                )
            )
    return tuple(capabilities)


def _keywords(text: str) -> list[str]:
    stopwords = {"a", "an", "and", "for", "from", "in", "of", "the", "to", "use", "when"}
    words = re.findall(r"[a-z0-9]+", text.lower())
    return list(dict.fromkeys(word for word in words if len(word) > 3 and word not in stopwords))
