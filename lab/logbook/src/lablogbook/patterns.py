"""What the checker looks for in text an author wrote. Patterns, not meaning: a hit means "read
this line again", and passing the check does not make an entry compliant.

Each rule: (code, category, regex, message). Categories:
  secret, path          always fail
  drive                 a note (links are fine; their sharing must stay restricted), or fail where forbid_drive_ids is set
  ferpa, health         fail; `reviewed: ferpa|health` in the header turns them into recorded warnings
  vendor                warning (proprietary or export-control wording; re-read before submitting)

Some literals are split ("/" + "Users/") because lab-templates' own CI refuses them in its files.
"""

from __future__ import annotations

import re

_HOME = "/" + "Users/"
_HOME_LINUX = "/" + "home/"
_DRIVE_MIRROR = "Google" + "Drive-"
_PEM = "-----" + "BEGIN"

RULES: list[tuple[str, str, re.Pattern, str]] = [
    # --- secrets ---------------------------------------------------------------------------
    ("secret-pem", "secret", re.compile(re.escape(_PEM) + r"[A-Z ]*(PRIVATE KEY|CERTIFICATE)"), "a private key or certificate"),
    ("secret-google", "secret", re.compile(r"AIza[0-9A-Za-z_-]{20,}|ya29\.[0-9A-Za-z_-]{20,}"), "a Google API key or token"),
    ("secret-anthropic", "secret", re.compile(r"sk-ant-[0-9A-Za-z_-]{20,}"), "an Anthropic API key"),
    ("secret-openai", "secret", re.compile(r"\bsk-(?:proj-)?[0-9A-Za-z]{32,}"), "an API key"),
    ("secret-github", "secret", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{30,}|github_pat_[0-9A-Za-z_]{40,}"), "a GitHub token"),
    ("secret-aws", "secret", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "an AWS access key"),
    ("secret-slack", "secret", re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}"), "a Slack token"),
    ("secret-assignment", "secret", re.compile(r"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token|secret[_-]?key|client[_-]?secret)\s*[:=]\s*['\"]?[^\s'\"]{8,}"), "a password or key written out"),
    # --- paths and Drive ids --------------------------------------------------------------
    ("path-home", "path", re.compile(re.escape(_HOME) + r"[^/\s]+/|" + re.escape(_HOME_LINUX) + r"[^/\s]+/|[A-Z]:\\Users\\"), "an absolute path into someone's home folder"),
    ("path-drive-mirror", "path", re.compile(re.escape(_DRIVE_MIRROR) + r"[^/\s]+"), "a Google Drive mirror path (it names the account)"),
    ("drive-id", "drive", re.compile(r"(?:drive|docs)\.google\.com/[^\s)>\]]*?(?:/d/|/folders/|[?&]id=)[A-Za-z0-9_-]{20,}"), "a Google Drive link"),
    # --- FERPA ------------------------------------------------------------------------------
    ("ferpa-uin", "ferpa", re.compile(r"(?<![\w+-])(?<!\d\.)\d{9}(?!\w|\.\d|-\d)"), "a nine-digit number (could be a student ID)"),
    ("ferpa-ssn", "ferpa", re.compile(r"(?<![\w-])\d{3}-\d{2}-\d{4}(?![\w-])"), "a number shaped like a social security number"),
    ("ferpa-grades", "ferpa", re.compile(r"(?i)\b(?:grades?|gpa|(?:academic|official|unofficial)\s+transcripts?|transcripts?\s+of\s+records|exam\s+scores?|test\s+scores?|final\s+marks?|enrol(?:l)?ments?)\b"), "a word about grades, transcripts of records or enrolment"),
    # --- health -----------------------------------------------------------------------------
    ("health-words", "health", re.compile(r"(?i)\b(?:diagnos(?:is|es|ed)|medical|medication|prescription|illness|sick\s+(?:leave|day)|injur(?:y|ies|ed)|hospital(?:i[sz]ed)?|disabilit(?:y|ies)|therapy|pregnan(?:t|cy))\b"), "a word about health"),
    # --- vendor / export control -----------------------------------------------------------
    ("vendor-words", "vendor", re.compile(r"(?i)\b(?:proprietary|confidential|under\s+(?:an?\s+)?nda|non-disclosure|itar|eccn|export[- ]controlled|controlled\s+technical\s+data)\b"), "proprietary or export-control wording"),
]

# "student Jane Doe", "Jane Doe (student)", "graduate student Jane"
STUDENT_NAME = re.compile(r"\b(?:under)?(?:graduate\s+)?students?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)|\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\((?:an?\s+)?(?:under)?(?:graduate\s+)?student\)")

ADDRESS = re.compile(r"\b[\w.+-]+@((?:[\w-]+\.)+[a-z]{2,})\b", re.I)


def institutional(host: str, domains: list[str]) -> bool:
    """True when an address's host is one of `domains` or below one ("edu" covers every .edu host)."""
    host = host.lower()
    return any(host == d or host.endswith("." + d) for d in (x.lower().lstrip(".") for x in domains))
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")

# Capitalised words that follow "student" without being a name.
NOT_NAMES = {"Union", "Center", "Centre", "Services", "Affairs", "Council", "Government", "Body", "Association",
             "Researchers", "Workers", "Worker", "Researcher", "Assistant", "Assistants", "Version", "The", "A", "An"}


DEFAULT_ID_PATTERN = next(rx.pattern for code, _c, rx, _m in RULES if code == "ferpa-uin")


def scan_line(line: str, id_pattern: "re.Pattern | None | bool" = True) -> list[tuple[str, str, str]]:
    """(code, category, message) for every rule that matches the line. `id_pattern`: True keeps
    the built-in ID rule (nine digits), a compiled pattern replaces it, None turns it off."""
    hits = [(code, cat, msg) for code, cat, rx, msg in RULES if code != "ferpa-uin" and rx.search(line)]
    rx = re.compile(DEFAULT_ID_PATTERN) if id_pattern is True else id_pattern
    if rx is not None and rx.search(line):
        hits.insert(0, ("ferpa-uin", "ferpa", "a number shaped like a student or staff ID"))
    return hits
