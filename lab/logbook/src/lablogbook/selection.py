"""Choosing entries: the same filters as the HTML view, for `export`, `month` and `pull`."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .book import Book
from .entry import Entry


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).replace("−", "-").lower()


@dataclass
class Filter:
    projects: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    apparatus: list[str] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    query: str | None = None
    ids: list[str] = field(default_factory=list)
    release_only: bool = False

    def describe(self, book: Book) -> str:
        bits = []
        if self.ids:
            bits.append(f"{len(self.ids)} chosen entries")
        if self.projects:
            bits.append("project " + ", ".join(self.projects))
        if self.people:
            names = [book.people[h].name if book.people and h in book.people else h for h in self.people]
            bits.append("by " + ", ".join(names))
        if self.apparatus:
            bits.append("on " + ", ".join(self.apparatus))
        if self.kinds:
            bits.append("kind " + ", ".join(self.kinds))
        if self.tags:
            bits.append("tagged " + ", ".join(self.tags))
        if self.date_from or self.date_to:
            bits.append(f"dated {self.date_from or '…'} to {self.date_to or '…'}")
        if self.query:
            bits.append(f"matching “{self.query}”")
        if self.release_only:
            bits.append("release candidates")
        return "; ".join(bits) or "all entries"

    def match(self, e: Entry) -> bool:
        h = e.header
        if self.ids and e.id not in self.ids:
            return False
        if self.projects and not set(self.projects) & set(e.projects):
            return False
        if self.people and not set(self.people) & set(e.authors):
            return False
        if self.apparatus and not set(self.apparatus) & set(h.get("apparatus") or []):
            return False
        if self.kinds and h.get("kind") not in self.kinds:
            return False
        if self.tags and not set(self.tags) & set(h.get("tags") or []):
            return False
        if self.date_from and e.date < self.date_from:
            return False
        if self.date_to and e.date > self.date_to:
            return False
        if self.release_only and h.get("release") != "candidate":
            return False
        if self.query:
            hay = norm(" ".join([e.id, e.text]))
            for term in re.findall(r'"([^"]+)"|(\S+)', self.query):
                t = norm(term[0] or term[1])
                if t and t not in hay:
                    return False
        return True

    def apply(self, book: Book) -> list[Entry]:
        return sorted((e for e in book.entries.values() if self.match(e)), key=lambda e: (e.date, str(e.header.get("time") or ""), e.id))
