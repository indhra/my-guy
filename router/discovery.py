import re
from collections import Counter
from hashlib import sha256
from pathlib import Path

from .config import SkillRoot
from .models import Capability


MAX_SKILL_BYTES = 1_048_576
MAX_SKILLS_PER_ROOT = 10_000


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    values: dict[str, str] = {}
    lines = match.group(1).splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        key, separator, value = line.partition(":")
        if separator:
            key = key.strip()
            value = value.strip().strip('"\'')
            if value in {"|", ">"}:
                block: list[str] = []
                index += 1
                while index < len(lines) and (not lines[index].strip() or lines[index][:1].isspace()):
                    block.append(lines[index].strip())
                    index += 1
                values[key] = " ".join(part for part in block if part)
                continue
            values[key] = value
        index += 1
    return values


def discover_skills(roots: list[str | Path]) -> tuple[Capability, ...]:
    """Discover bounded skill metadata without executing skill instructions."""
    import os

    capabilities: list[Capability] = []
    for root in roots:
        root_path = Path(root).expanduser()
        if not root_path.is_dir() or root_path.is_symlink():
            continue
        found = 0
        directories = 0
        for directory, subdirs, files in os.walk(root_path, followlinks=False):
            directories += 1
            if directories > MAX_SKILLS_PER_ROOT:
                break
            subdirs[:] = sorted(name for name in subdirs
                                if name.lower() not in {".git", ".trash", "trash", "node_modules", "__pycache__"}
                                and not (Path(directory) / name).is_symlink())
            if "SKILL.md" not in files:
                continue
            path = Path(directory) / "SKILL.md"
            if path.is_symlink():
                continue
            found += 1
            if found > MAX_SKILLS_PER_ROOT:
                break
            try:
                if path.stat().st_size > MAX_SKILL_BYTES:
                    continue
                metadata = _frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            name = metadata.get("name")
            description = metadata.get("description")
            if not name or not description:
                continue
            try:
                capabilities.append(Capability(
                    id=name, source=str(path.parent), description=description,
                    domains=(), triggers=tuple(_keywords(f"{name} {description}")),
                    invocation=f"skill:{name}",
                ))
            except ValueError:
                continue
    return tuple(capabilities)


def discover_named_roots(roots: tuple[SkillRoot, ...]) -> tuple[Capability, ...]:
    """Discover namespaced capabilities so identical skill names cannot shadow each other."""
    capabilities: list[Capability] = []
    for root in roots:
        raw = discover_skills([root.path])
        mirrors: dict[tuple[str, str, str], Capability] = {}
        for capability in raw:
            key = (capability.id, capability.invocation, capability.description)
            current = mirrors.get(key)
            if current is None or (len(capability.source), capability.source) < (
                len(current.source),
                current.source,
            ):
                mirrors[key] = capability
        discovered = tuple(mirrors.values())
        counts = Counter(capability.id for capability in discovered)
        for capability in discovered:
            suffix = ""
            if counts[capability.id] > 1:
                suffix = ":" + sha256(capability.source.encode("utf-8")).hexdigest()[:10]
            capabilities.append(
                Capability(
                    id=f"{root.name}:{capability.id}{suffix}",
                    source=f"{root.name}:{capability.source}",
                    description=capability.description,
                    domains=capability.domains,
                    triggers=capability.triggers,
                    invocation=capability.invocation,
                    trust=root.trust,
                )
            )
    return tuple(capabilities)


def _keywords(text: str) -> list[str]:
    stopwords = {"a", "an", "and", "for", "from", "in", "of", "the", "to", "use", "when"}
    words = re.findall(r"[a-z0-9]+", text.lower())
    return list(dict.fromkeys(word for word in words if len(word) > 3 and word not in stopwords))


# Keep the public discovery API in one module while the bounded inventory
# scanners live separately from the original skill parser.
from .inventory import discover_inventory  # noqa: E402
