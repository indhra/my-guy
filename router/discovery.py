import re
import stat
from collections import Counter
from hashlib import sha256
from heapq import nsmallest
from pathlib import Path

from .config import SkillRoot
from .path_safety import has_symlink_component, unsafe_skill_file, unsafe_skill_root
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


def _skill_capability(path: Path, *, source: str, require_safe_files: bool) -> Capability | None:
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            return None
        if require_safe_files and unsafe_skill_file(path):
            return None
        if path.stat().st_size > MAX_SKILL_BYTES:
            return None
        metadata = _frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    name = metadata.get("name")
    description = metadata.get("description")
    if not name or not description:
        return None
    try:
        return Capability(
            id=name,
            source=source,
            description=description,
            domains=(),
            triggers=tuple(_keywords(f"{name} {description}")),
            invocation=f"skill:{name}",
        )
    except ValueError:
        return None


def discover_skills(roots: list[str | Path], *, require_safe_files: bool = False) -> tuple[Capability, ...]:
    """Discover skill metadata without executing skill instructions."""
    capabilities: list[Capability] = []
    for root in roots:
        root_path = Path(root).expanduser()
        if has_symlink_component(root_path) or not root_path.exists():
            continue
        for count, path in enumerate(sorted(root_path.rglob("SKILL.md"))):
            if count >= MAX_SKILLS_PER_ROOT:
                break
            if has_symlink_component(path):
                continue
            capability = _skill_capability(
                path, source=str(path.parent), require_safe_files=require_safe_files
            )
            if capability is not None:
                capabilities.append(capability)
    return tuple(capabilities)


def _trusted_skill_aliases(root: SkillRoot, roots: tuple[SkillRoot, ...]) -> tuple[Capability, ...]:
    """Read direct aliases only when both the alias and its target roots are trusted."""
    if root.trust != "local":
        return ()
    root_path = Path(root.path).expanduser()
    if unsafe_skill_root(root_path):
        return ()
    target_roots: set[Path] = set()
    for candidate in roots:
        if candidate.name == root.name or candidate.trust != "local":
            continue
        candidate_path = Path(candidate.path).expanduser()
        if not unsafe_skill_root(candidate_path):
            target_roots.add(candidate_path.resolve())
    if not target_roots:
        return ()
    try:
        entries = nsmallest(MAX_SKILLS_PER_ROOT, root_path.iterdir())
    except OSError:
        return ()
    capabilities: list[Capability] = []
    for alias in entries:
        if not alias.is_symlink():
            continue
        try:
            target = alias.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if target.parent not in target_roots or not target.is_dir():
            continue
        capability = _skill_capability(
            target / "SKILL.md",
            source=f"{alias} -> {target}",
            require_safe_files=True,
        )
        if capability is not None:
            capabilities.append(capability)
    return tuple(capabilities)


def unsafe_skill_files(root: Path) -> tuple[tuple[str, str], ...]:
    """Return rejected skill files for readiness diagnostics."""
    if unsafe_skill_root(root) or not root.is_dir():
        return ()
    issues: list[tuple[str, str]] = []
    for count, path in enumerate(sorted(root.rglob("SKILL.md"))):
        if count >= MAX_SKILLS_PER_ROOT:
            break
        if reason := unsafe_skill_file(path):
            issues.append((str(path), reason))
    return tuple(issues)


def discover_named_roots(roots: tuple[SkillRoot, ...]) -> tuple[Capability, ...]:
    """Discover namespaced capabilities so identical skill names cannot shadow each other."""
    capabilities: list[Capability] = []
    for root in roots:
        if root.trust == "local" and unsafe_skill_root(Path(root.path)):
            continue
        raw = (
            *discover_skills([root.path], require_safe_files=root.trust == "local"),
            *_trusted_skill_aliases(root, roots),
        )
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
