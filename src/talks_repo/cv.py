"""Stage A: parse the Presentations section of the CV into talk entries.

The CV is a public Google Doc. Its plain-text export lists one presentation per
line in the form

    67.<tabs>2026/08<spaces>Event name (qualifier), "Title," City, ST, Country

Qualifiers seen: invited, Invited Panel, invited colloquium, invited seminar,
invited symposium, award, and combinations. Quotes are a mix of straight and
curly, and a few lines use an opening quote where a closing one belongs.
Everything the parser is unsure about ends up in the `flags` list so the review
sheet shows it.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import httpx

CV_DOC_ID = "1RyrDpyE_UKVQuS4SSUP2Ewjmf4fQ8-ivwwLT3N4M6Sg"
CV_EXPORT_URL = f"https://docs.google.com/document/d/{CV_DOC_ID}/export?format=txt"

_ENTRY_RE = re.compile(r"^\s*(\d+)\.\s+(\d{4})/(\d{2})\s+(.*\S)\s*$")
_QUOTES = "\"“”"
_QUALIFIER_RE = re.compile(
    r"invited|award|panel|seminar|colloquium|symposium|plenary|keynote|poster", re.I
)
_SECTION_RE = re.compile(r"^(Presentations)\s*$")
_END_RE = re.compile(r"^_{3,}\s*$")

# Era boundaries by date (month precision). The CV lists three phases:
# PhD at CERN/Heidelberg through 2020, MIT postdoc 2021-2024, UNI from 2025.
_ERAS = [("UNI", "2025-01"), ("MIT", "2021-01"), ("PhD", "0000-00")]

_STOPWORDS = {"the", "of", "for", "and", "at", "on", "in", "with", "a", "an", "to"}


@dataclass
class ParsedTalk:
    cv_index: int
    date: str  # YYYY-MM
    event: str
    qualifier: str | None
    title: str
    location: str | None
    award: str | None
    type: str
    type_confidence: float
    era: str
    raw: str
    flags: list[str] = field(default_factory=list)


def fetch_cv_text(url: str = CV_EXPORT_URL) -> str:
    response = httpx.get(url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    return response.text


def presentation_lines(text: str) -> list[str]:
    """Return the lines of the Presentations section, in document order."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if _SECTION_RE.match(line)), None)
    if start is None:
        raise ValueError("No 'Presentations' heading found in the CV export")
    out: list[str] = []
    for line in lines[start + 1 :]:
        if _END_RE.match(line):
            break
        if line.strip():
            out.append(line)
    return out


def parse_line(line: str) -> ParsedTalk | None:
    match = _ENTRY_RE.match(line)
    if not match:
        return None
    index, year, month, rest = match.groups()
    flags: list[str] = []
    date = f"{year}-{month}"

    # Split at the first and second quote characters, whatever their shape.
    positions = [i for i, ch in enumerate(rest) if ch in _QUOTES]
    if len(positions) < 2:
        flags.append("no-quoted-title")
        event_part, title, location_part = rest, "", ""
    else:
        first, second = positions[0], positions[1]
        event_part = rest[:first]
        title = rest[first + 1 : second]
        location_part = rest[second + 1 :]
        if rest[second] in "\"“" and rest[first] in "“":
            flags.append("malformed-quotes")
        if len(positions) > 2:
            flags.append("extra-quotes")

    event_part = event_part.strip().rstrip(",").strip()
    title = title.strip().rstrip(",").strip()
    location_part = location_part.strip().lstrip(",").strip()

    # A trailing parenthesis is a qualifier only if it uses qualifier words;
    # otherwise it is an event acronym like "(DPG18)" and stays in the event.
    qualifier = None
    qual_match = re.search(r"\(([^()]*)\)\s*$", event_part)
    if qual_match and _QUALIFIER_RE.search(qual_match.group(1)):
        qualifier = qual_match.group(1).strip()
        event_part = event_part[: qual_match.start()].strip().rstrip(",").strip()

    award = None
    location: str | None = location_part or None
    if qualifier and "award" in qualifier.lower() and location_part:
        parts = [p.strip() for p in location_part.split(",")]
        award_parts = [p for p in parts if "award" in p.lower()]
        if award_parts:
            award = award_parts[0]
            remaining = [p for p in parts if p is not award_parts[0]]
            location = ", ".join(remaining) or None
        flags.append("award-entry")
    if not location:
        flags.append("no-location")
    if not event_part:
        flags.append("no-event")

    talk_type, confidence = classify_type(event_part, qualifier, title)
    if confidence < 0.7:
        flags.append("type-uncertain")

    era = next(name for name, start in _ERAS if date >= start)

    return ParsedTalk(
        cv_index=int(index),
        date=date,
        event=event_part,
        qualifier=qualifier,
        title=title,
        location=location,
        award=award,
        type=talk_type,
        type_confidence=confidence,
        era=era,
        raw=line.strip(),
        flags=flags,
    )


def classify_type(event: str, qualifier: str | None, title: str) -> tuple[str, float]:
    """Map the CV wording to the talks.yaml `type` vocabulary with a confidence."""
    q = (qualifier or "").lower()
    e = event.lower()
    if "colloquium" in q or "colloquium" in e:
        return "colloquium", 0.95
    if "seminar" in q or "seminar" in e or "journal club" in e or "forum" in e:
        return "seminar", 0.9 if "invited" in q or "seminar" in e else 0.7
    if "saturday morning physics" in e or "mipep" in e or "enhancement program" in e:
        return "public", 0.9
    if "school" in e and "award" in q:
        # The CV's Awards section records these as poster presentation awards.
        return "poster", 0.8
    if "invited" in q:
        return "invited", 0.9
    if "site visit" in e or "institutional review" in e or "review at" in e:
        return "contributed", 0.6
    if any(k in e for k in ("meeting", "workshop", "conference", "summit", "school")):
        return "contributed", 0.75
    return "contributed", 0.5


def slugify(text: str, max_words: int = 4) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    words = re.findall(r"[a-z0-9]+", ascii_text.lower())
    words = [w for w in words if w not in _STOPWORDS]
    return "-".join(words[:max_words]) or "talk"


def make_ids(talks: list[ParsedTalk]) -> dict[int, str]:
    """Assign `YYYY-MM-slug` ids, adding -2, -3 on collisions. Keyed by cv_index."""
    ids: dict[int, str] = {}
    used: set[str] = set()
    for talk in sorted(talks, key=lambda t: (t.date, t.cv_index)):
        base = f"{talk.date}-{slugify(talk.event)}"
        candidate, n = base, 1
        while candidate in used:
            n += 1
            candidate = f"{base}-{n}"
        used.add(candidate)
        ids[talk.cv_index] = candidate
    return ids


def to_entry(talk: ParsedTalk, talk_id: str) -> dict[str, Any]:
    """Build the talks.yaml entry with every schema key present, in schema order."""
    return {
        "id": talk_id,
        "cv_index": talk.cv_index,
        "date": talk.date,
        "title": talk.title,
        "event": talk.event,
        "qualifier": talk.qualifier,
        "award": talk.award,
        "host": None,
        "location": talk.location,
        "type": talk.type,
        "era": talk.era,
        "duration_min": None,
        "audience": None,
        "format": None,
        "source_url": None,
        "confidence": None,
        "source_file": None,
        "pdf_file": None,
        "archive": None,
        "notes": "",
    }


def parse_cv(text: str) -> tuple[list[ParsedTalk], list[str]]:
    """Return parsed talks and the raw lines that did not parse at all."""
    talks: list[ParsedTalk] = []
    unparsed: list[str] = []
    for line in presentation_lines(text):
        parsed = parse_line(line)
        if parsed is None:
            unparsed.append(line.strip())
        else:
            talks.append(parsed)
    return talks, unparsed
