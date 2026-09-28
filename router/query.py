"""Conservative, auditable interpretation of a routing request."""

import re


_QUOTE_PAIRS = {"'": "'", '"': '"', "`": "`", "“": "”", "‘": "’"}
_ABSTAIN_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:do not|don't)\s+(?:route|suggest|recommend|choose|pick|select)\b",
        r"\bno\s+(?:routing|routes?|recommendations?|suggestions?)\b",
        r"\bi am testing prompt injection\b",
        r"\bplease ask me which\b",
        r"\bshould i prioritize\b",
        r"^\s*no review requested\b",
    )
)
_NEGATIVE_DESIRE = re.compile(r"\b(?:do not|don't)\s+(?:want|need|wish|ask|intend)\b", re.IGNORECASE)
_ROUTING_INTENT = re.compile(
    r"\b(?:rout(?:e|es|ing)|recommend(?:ations?)?|suggest(?:ions?)?|choose|pick|select)\b",
    re.IGNORECASE,
)
_KEEP_CUE = re.compile(r"\bkeep(?:ing)?\b", re.IGNORECASE)
_OUT_CUE = re.compile(r"\bout\b", re.IGNORECASE)
_PREFERENCE_BOUNDARY = re.compile(r"[;.!?\n]")
_EXCLUSION_START = (
    r"(?:please\s+)?(?:avoid|avoiding|exclude|excluding|except(?:\s+for)?|"
    r"skip(?:ping)?|omit(?:ting)?|without|no\b(?!\s+matter\b)|not\b(?!\s+only\b)|"
    r"do not (?:use|include|review)|don't (?:use|include|review))\b"
)
_INFORMATIONAL_START = (
    r"(?:explain|describe|summarize|translate|define|definition|meaning|understand|"
    r"learn(?:\s+about)?|tell\s+me(?:\s+about)?|"
    r"(?:give|show)\s+me\s+(?:a\s+|the\s+)?(?:definition|meaning)|"
    r"help\s+me\s+(?:understand|learn)|"
    r"what|how|why|where|when|who|whom|whose|which)\b"
)
_REQUEST_PREFIX = re.compile(
    r"^\s*(?:(?:can|could|would|will|should)\s+you\s+|"
    r"i\s+(?:need|want|would like)\s+(?:you\s+)?to\s+|"
    r"i'd\s+like\s+(?:you\s+)?to\s+|please\s+|just\s+|also\s+)+",
    re.IGNORECASE,
)
_EXCLUSION_HEAD = re.compile(rf"^{_EXCLUSION_START}", re.IGNORECASE)
_LEAVE_OUT_HEAD = re.compile(r"^leav(?:e|ing)\b.*\bout\b", re.IGNORECASE)
_INFORMATIONAL_HEAD = re.compile(rf"^{_INFORMATIONAL_START}", re.IGNORECASE)
_ROUTING_ACTION_START = (
    r"(?:review|audit|assess|analyze|evaluate|check|inspect|research|recommend|route|"
    r"compare|design|improve|fix|find)\b"
)
_ROUTING_ACTION_HEAD = re.compile(
    rf"^{_ROUTING_ACTION_START}\s+(?!(?:and|or)\b)\S", re.IGNORECASE,
)
_NEGATIVE_CONSTRAINT_HEAD = re.compile(r"^(?:do not|don't)\b", re.IGNORECASE)
_NON_TASK_EXAMPLE = re.compile(r"\b(?:quoted (?:example|data)|not another task)\b", re.IGNORECASE)
_SCOPE_EXCLUSION = re.compile(
    r"\b(?:out of scope|outside (?:the )?scope)\b", re.IGNORECASE,
)
# These cues do not establish a reliable boundary between requested and excluded
# domains. Abstain for the whole request instead of guessing the modifier's scope.
_UNCERTAIN_EXCLUSION = re.compile(
    r"\b(?:omitted|excluded|skipped|left\s+(?:out|aside)|disregard(?:ed|ing)?|"
    r"pass(?:ing)?\s+over)\b",
    re.IGNORECASE,
)
# Bound scope lookahead work. A longer uncertain clause remains whole and is
# excluded by _SCOPE_EXCLUSION, so the bound cannot expose excluded evidence.
_CLAUSE_BOUNDARY = re.compile(
    rf"[;,]|(?<=[.!?])\s+(?=[a-z])|\b(?:but|while|however|whereas|then)\b|"
    rf"\band\b(?=\s+(?:also\s+)?(?:(?:please\s+)?(?:{_EXCLUSION_START}|{_INFORMATIONAL_START}|leav(?:e|ing)\b)|"
    rf"(?:please\s+)?{_ROUTING_ACTION_START}))|"
    r"\band\b(?=\s+[^;,.!?]{0,256}\b(?:out of scope|outside (?:the )?scope)\b)|"
    r"(?=\b(?:without|excluding|avoiding|skipping|omitting|omit|leaving|leave|except|not asking for)\b)",
    re.IGNORECASE,
)
_EXCLUSION_WORDS = frozenset({
    "a", "an", "and", "another", "asking", "avoid", "avoiding", "but", "data",
    "do", "dont", "don't", "exclude", "excluding", "example", "except", "for",
    "include", "is", "leave", "leaving", "no", "not", "of", "omit", "omitting",
    "or", "please", "quoted", "review", "out", "outside", "route", "scope",
    "skip", "skipping", "suggest", "task", "the",
    "to", "use", "with", "without",
})

# Multiword aliases are intentionally narrow. A matched phrase counts as two
# evidence units only when the capability itself advertises the target trigger.
PHRASE_ALIASES: tuple[tuple[str, str], ...] = (
    ("account takeover", "authentication"),
    ("visual hierarchy", "design"),
    ("find references", "research"),
    ("getting started instructions", "documentation"),
)


def explicit_abstention(request: str) -> bool:
    """True when the user explicitly wants no route or wants to choose first."""
    unquoted = _without_quoted_spans(request).replace("’", "'")
    return (
        any(pattern.search(unquoted) for pattern in _ABSTAIN_PATTERNS)
        or _ordered_cues(unquoted, _NEGATIVE_DESIRE, _ROUTING_INTENT)
    )


def uncertain_exclusion(request: str) -> bool:
    """Fail closed when exclusion scope cannot be extracted reliably."""
    unquoted = _without_quoted_spans(request)
    return bool(_UNCERTAIN_EXCLUSION.search(unquoted)) or _ordered_cues(unquoted, _KEEP_CUE, _OUT_CUE)


def _ordered_cues(text: str, first: re.Pattern[str], second: re.Pattern[str]) -> bool:
    """Search each clause once, avoiding quadratic repeated-cue lookaheads."""
    for clause in _PREFERENCE_BOUNDARY.split(text):
        match = first.search(clause)
        if match and second.search(clause, match.end()):
            return True
    return False


def _word_apostrophe(text: str, index: int) -> bool:
    return (
        text[index] == "'"
        and index > 0
        and index + 1 < len(text)
        and text[index - 1].isalnum()
        and text[index + 1].isalnum()
    )


def _without_quoted_spans(text: str) -> str:
    kept: list[str] = []
    index = 0
    while index < len(text):
        opening = text[index]
        if opening not in _QUOTE_PAIRS or _word_apostrophe(text, index):
            kept.append(opening)
            index += 1
            continue
        closing = _QUOTE_PAIRS[opening]
        end = index + 1
        while end < len(text):
            if text[end] == "\\" and end + 1 < len(text):
                end += 2
                continue
            if text[end] == closing and not _word_apostrophe(text, end):
                break
            end += 1
        kept.append(" ")
        index = end + 1  # An unmatched opening quote conservatively hides the remainder.
    return "".join(kept)


def routing_spans(request: str) -> tuple[str, str]:
    """Separate requested work from explicit exclusions before capability scoring."""
    without_quotes = _without_quoted_spans(request).replace("’", "'")
    requested: list[str] = []
    excluded: list[str] = []
    informational_context = False
    for clause in _CLAUSE_BOUNDARY.split(without_quotes):
        clause = clause.strip()
        if not clause:
            continue
        head = _REQUEST_PREFIX.sub("", clause, count=1).strip()
        if (_NON_TASK_EXAMPLE.search(clause) or _EXCLUSION_HEAD.match(head)
                or _LEAVE_OUT_HEAD.match(head)
                or _SCOPE_EXCLUSION.search(head)):
            excluded.append(clause)
        elif _INFORMATIONAL_HEAD.match(head):
            informational_context = True
            continue
        elif _NEGATIVE_CONSTRAINT_HEAD.match(head):
            continue
        else:
            # List fragments inherit the informational intent that introduced
            # them. Only a new action head can resume actionable evidence;
            # nouns such as "security review" or "design and accessibility"
            # cannot turn an explanation into a specialist recommendation.
            action = _ROUTING_ACTION_HEAD.match(head)
            if informational_context and not action:
                continue
            if action:
                informational_context = False
            requested.append(clause)
    return " ".join(requested), " ".join(excluded)


def routing_text(request: str) -> str:
    """Return only clauses that describe work relevant to routing."""
    return routing_spans(request)[0]


def exclusion_tokens(text: str) -> set[str]:
    """Ignore cue words so an excluded 'review' does not veto all reviewers."""
    return set(re.findall(r"[a-z0-9]+", text.lower())) - _EXCLUSION_WORDS


def matched_aliases(text: str) -> tuple[tuple[str, str], ...]:
    """Return only whole-phrase aliases present in unquoted routing text."""
    return tuple(
        (phrase, trigger)
        for phrase, trigger in PHRASE_ALIASES
        if re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text, re.IGNORECASE)
    )
