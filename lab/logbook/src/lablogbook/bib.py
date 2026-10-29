"""The lab reference list: a BibTeX file, read without extra dependencies.

Enough of BibTeX for the checker and the plain-text form of a citation; rendering in the PDF and
the HTML goes through pandoc's citeproc with `data/karthein-lab.csl`, which gives the same text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_START = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", re.S)


class BibError(ValueError):
    pass


@dataclass
class Record:
    type: str
    key: str
    fields: dict[str, str]
    line: int


def _value(text: str, i: int) -> tuple[str, int]:
    """Read one field value starting at text[i] ({...}, "..." or a bare word); return (value, end)."""
    while text[i].isspace():
        i += 1
    if text[i] == "{":
        depth, j = 0, i
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    return text[i + 1:j], j + 1
            j += 1
        raise BibError("unbalanced braces")
    if text[i] == '"':
        j = i + 1
        while j < len(text) and not (text[j] == '"' and text[j - 1] != "\\"):
            j += 1
        return text[i + 1:j], j + 1
    m = re.match(r"[\w.:-]+", text[i:])
    if not m:
        raise BibError(f"unexpected {text[i]!r}")
    return m.group(0), i + m.end()


def parse(text: str) -> list[Record]:
    records = []
    for m in _START.finditer(text):
        typ = m.group(1).lower()
        if typ in ("comment", "preamble", "string"):
            continue
        line = text.count("\n", 0, m.start()) + 1
        fields, i = {}, m.end()
        try:
            while True:
                fm = re.compile(r"\s*([\w-]+)\s*=\s*").match(text, i)
                if not fm:
                    break
                val, i = _value(text, fm.end())
                fields[fm.group(1).lower()] = re.sub(r"\s+", " ", val).strip()
                cm = re.compile(r"\s*,").match(text, i)
                if not cm:
                    break
                i = cm.end()
            if not re.compile(r"\s*\}").match(text, i):
                raise BibError("record not closed after its last field")
        except (BibError, IndexError) as e:
            raise BibError(f"line {line}, @{typ}{{{m.group(2)}: {e}") from None
        records.append(Record(typ, m.group(2), fields, line))
    return records


def _plain(s: str) -> str:
    return re.sub(r"[{}]", "", s).replace("\\&", "&").replace("--", "–")


def _first_author(field: str) -> tuple[str, int]:
    names = [n.strip() for n in re.split(r"\s+and\s+", field) if n.strip()]
    if not names:
        return "", 0
    n = names[0]
    if "," in n:
        last, first = [x.strip() for x in n.split(",", 1)]
    else:
        parts = n.split()
        last, first = parts[-1], " ".join(parts[:-1])
    initial = (_plain(first)[:1] + ".") if first else ""
    return f"{_plain(last)} {initial}".strip(), len(names)


def format_citation(r: Record) -> str:
    """The lab's short form: 'Karthein J.++ Phys. Rev. Lett. 123, 456 (2019)'."""
    f = r.fields
    who, n = _first_author(f.get("author") or f.get("editor") or "")
    who += "++" if n > 1 else ""
    year = f.get("year") or (f.get("date") or "")[:4]
    if r.type == "book":
        pub = ", ".join(x for x in (_plain(f.get("publisher", "")), year) if x)
        return f"{who} {_plain(f.get('title', ''))} ({pub})".strip()
    journal = _plain(f.get("shortjournal") or f.get("journal") or f.get("journaltitle") or "")
    if journal:
        page = re.split(r"[-–]", f.get("pages", ""))[0].strip()
        left = " ".join(x for x in (journal, f.get("volume", "")) if x)
        return f"{who} {', '.join(x for x in (left, page) if x)} ({year})".strip()
    return f"{who} {_plain(f.get('title', ''))} ({year})".strip()


def doi_url(r: Record) -> str | None:
    doi = r.fields.get("doi")
    return f"https://doi.org/{doi}" if doi else None
