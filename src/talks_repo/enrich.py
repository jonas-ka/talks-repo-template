"""Stage B: fill duration_min, audience, format, source_url, confidence for each talk.

Three sources, cheapest first, never overwriting a value the author set by hand:

1. Rules from the talk's type, qualifier, and event name (confidence 0.4-0.6).
2. Agenda / programme / schedule documents in the same trip folder: the lines
   around "Karthein" often carry the slot times (confidence 0.85).
3. Web lookups, done outside this module and written into talks.yaml by hand or
   with `talks set`.

Talks whose confidence stays below 0.7 go on the gaps sheet for the author.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from talks_repo import INPUT_ROOTS, resolve_ref

STAGE_B_FIELDS = ("duration_min", "audience", "format")

_PROGRAM_WORDS = ("agenda", "program", "programme", "schedule", "timetable", "booklet", "abstracts",
                  "flyer", "announcement", "poster-session", "sessions")
_NUCLEAR_LABS = ("frib", "argonne", "anl", "lbnl", "cyclotron", "lns", "isolde", "cern", "isoltrap",
                 "nustar", "gsi", "triumf", "ornl", "oak ridge", "jyv", "becola", "cris", "mrtof")
_AMO_WORDS = ("trapped charged particles", "tcp", "penning", "iqse", "isqe", "quantum", "amo", "platan")
_PUBLIC_WORDS = ("saturday morning physics", "high school", "public", "outreach", "festival")
_TEACHER_WORDS = ("mipep", "enhancement program", "teachers", "summer school", "nnpss", "lecture")


@dataclass
class Guess:
    duration_min: int | None
    audience: str | None
    format: str | None
    confidence: float
    why: str


def guess_from_rules(talk: dict[str, Any]) -> Guess:
    event = str(talk.get("event", "")).lower()
    qual = str(talk.get("qualifier") or "").lower()
    ttype = str(talk.get("type", ""))
    text = f"{event} {qual}"

    if ttype == "poster":
        return Guess(None, "nuclear", "parallel", 0.6, "poster")
    if ttype == "public" or any(w in text for w in _PUBLIC_WORDS):
        return Guess(60, "public", "seminar", 0.5, "public lecture")
    if any(w in text for w in _TEACHER_WORDS):
        return Guess(60, "students", "seminar", 0.45, "lecture for students/teachers")
    if ttype == "colloquium" or "colloquium" in text:
        return Guess(60, "general", "seminar", 0.6, "colloquium")
    if "journal club" in event:
        return Guess(30, "nuclear", "seminar", 0.5, "journal club")
    if ttype == "seminar" or "seminar" in text or "forum" in event:
        aud = "nuclear" if any(w in event for w in _NUCLEAR_LABS) else "mixed"
        if any(w in event for w in _AMO_WORDS):
            aud = "amo"
        return Guess(60, aud, "seminar", 0.5, "seminar")
    if "site visit" in event or "review" in event or "visit" in event:
        return Guess(20, "mixed", "parallel", 0.4, "review/visit")
    if "collaboration meeting" in event or "meeting" in event:
        return Guess(20, "nuclear", "parallel", 0.4, "collaboration meeting")
    if "award" in qual or "dissertation" in event:
        return Guess(30, "nuclear", "plenary", 0.45, "award talk")
    if "panel" in qual:
        return Guess(15, "mixed", "plenary", 0.4, "panel")
    if any(w in text for w in _AMO_WORDS):
        aud = "amo"
    elif any(w in event for w in ("aps global", "march meeting", "physical society")) and "dnp" not in event:
        aud = "general"
    else:
        aud = "nuclear"
    if ttype == "invited":
        fmt = "plenary" if "plenary" in qual else "parallel"
        return Guess(30, aud, fmt, 0.45, "invited conference talk")
    if "dnp" in event:
        return Guess(12, "nuclear", "parallel", 0.55, "DNP contributed (10+2)")
    if any(w in event for w in ("workshop", "conference", "school", "summit", "days")):
        return Guess(20, aud, "parallel", 0.4, "contributed workshop/conference talk")
    return Guess(20, aud, "parallel", 0.3, "default")


# --------------------------------------------------------------------------- local programmes

_TIME_RANGE = re.compile(r"(\d{1,2})[:.](\d{2})\s*(?:[-–—]|to)\s*(\d{1,2})[:.](\d{2})")
_MINUTES = re.compile(r"\b(\d{1,3})\s*(?:\+\s*\d{1,2}\s*)?(?:min|mins|minutes|')\b", re.I)
_TIME_SUFFIX = re.compile(r"(\d{1,2})[:.](\d{2})\s*(am|pm)?", re.I)


@dataclass
class ProgramHit:
    file_ref: str
    snippet: str
    duration_min: int | None


def program_documents(talk: dict[str, Any], files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """PDF documents in the talk's trip folder(s) whose names suggest a programme."""
    folders: set[tuple[str, str]] = set()
    for key in ("source_file", "pdf_file"):
        ref = talk.get(key)
        if ref:
            root, _, rel = ref.partition(":")
            parts = Path(rel).parts
            if len(parts) > 1:
                folders.add((root, parts[0]))
    if not folders:
        return []
    out = []
    for f in files:
        if (f["root"], f["folder"]) in folders and f["type"] == ".pdf" and f.get("deck_class") in ("document", "unknown"):
            name = Path(f["path"]).name.lower()
            if "karthein" in name:
                continue  # his own abstract, CV, or receipt
            out.append({**f, "_program_named": any(w in name for w in _PROGRAM_WORDS)})
    # Programme-named documents first; others are accepted only if slot times are found.
    return sorted(out, key=lambda f: not f["_program_named"])


def scan_program(doc: dict[str, Any], title: str = "", surname: str = "karthein") -> ProgramHit | None:
    """Find the programme line for the author's talk: the occurrence of his surname whose
    surrounding lines best match the talk title (he may also appear as chair or organiser)."""
    import pymupdf
    from rapidfuzz import fuzz

    path = resolve_ref(f"{doc['root']}:{doc['path']}")
    try:
        with pymupdf.open(path) as pdf:
            if pdf.page_count > 60:
                return None
            lines: list[str] = []
            for page in pdf:
                lines.extend(page.get_text("text").splitlines())
    except Exception:  # noqa: BLE001
        return None
    hits = [i for i, line in enumerate(lines) if surname in line.lower()]
    if not hits:
        return None
    best: tuple[float, list[str]] | None = None
    for i in hits:
        context = [l.strip() for l in lines[max(0, i - 4) : i + 5] if l.strip()]
        similarity = fuzz.partial_token_set_ratio(title.lower(), " ".join(context).lower()) / 100 if title else 0.0
        has_time = duration_from_text(" ".join(context)) is not None
        score = similarity + (0.2 if has_time else 0.0)
        if best is None or score > best[0]:
            best = (score, context)
    assert best is not None
    score, context = best
    if len(hits) > 1 and title and score < 0.5:
        return None  # several mentions, none near the talk title: probably chair/organiser lines
    snippet = " | ".join(context)[:400]
    return ProgramHit(f"{doc['root']}:{doc['path']}", snippet, duration_from_text(" ".join(context)))


def duration_from_text(text: str) -> int | None:
    m = _TIME_RANGE.search(text)
    if m:
        h1, m1, h2, m2 = (int(v) for v in m.groups())
        minutes = (h2 * 60 + m2) - (h1 * 60 + m1)
        if minutes < 0:
            minutes += 12 * 60
        if 5 <= minutes <= 180:
            return minutes
    m = _MINUTES.search(text)
    if m and 5 <= int(m.group(1)) <= 180:
        return int(m.group(1))
    return None


# --------------------------------------------------------------------------- apply


def enrich_talk(talk: dict[str, Any], files: list[dict[str, Any]], skip_programs: bool) -> dict[str, Any]:
    """Fill missing Stage B fields. Returns a report row for the gaps sheet."""
    guess = guess_from_rules(talk)
    hit = None
    if not skip_programs:
        for doc in program_documents(talk, files):
            candidate = scan_program(doc, str(talk.get("title", "")))
            if candidate and (doc["_program_named"] or candidate.duration_min):
                hit = candidate
                break

    filled: list[str] = []
    if hit and hit.duration_min and not talk.get("duration_min"):
        talk["duration_min"] = hit.duration_min
        filled.append("duration_min<-programme")
    for key in STAGE_B_FIELDS:
        if talk.get(key) in (None, ""):
            value = getattr(guess, key)
            if value is not None:
                talk[key] = value
                filled.append(f"{key}<-rule")
    if hit and not talk.get("source_url"):
        talk["source_url"] = f"local:{hit.file_ref}"

    manual = [k for k in STAGE_B_FIELDS if talk.get(k) not in (None, "") and f"{k}<-rule" not in filled and f"{k}<-programme" not in filled]
    if talk.get("confidence") is None:
        conf = guess.confidence
        if hit and hit.duration_min:
            conf = max(conf, 0.85)
        if len(manual) == len(STAGE_B_FIELDS):
            conf = 1.0
        talk["confidence"] = round(conf, 2)

    needs = [k for k in STAGE_B_FIELDS if talk.get(k) in (None, "")]
    if talk["confidence"] < 0.7:
        needs = list(dict.fromkeys(needs + [k for k in STAGE_B_FIELDS if f"{k}<-rule" in filled]))
    return {
        "needs": " ".join(needs),
        "confidence": talk["confidence"],
        "rule": guess.why,
        "programme_snippet": hit.snippet if hit else "",
        "programme_file": hit.file_ref if hit else "",
        "filled": " ".join(filled),
    }
