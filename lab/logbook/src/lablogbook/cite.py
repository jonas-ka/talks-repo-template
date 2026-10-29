"""`logbook cite add <doi|isbn>`: a reference into the lab's reference list (`wiki/references.bib`).

DOIs come from Crossref (with the journal's short title), ISBNs from Open Library. The key is
`LastnameYYYY`, with a letter when the key is taken. A DOI that is already in the list is not
added twice; its key is returned.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from importlib import resources
from pathlib import Path

from . import bib as bibmod
from .book import Book
from .entry import load_yaml

UA = "lab-templates-logbook (https://github.com/jonas-ka/lab-templates)"


class CiteError(RuntimeError):
    pass


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:   # noqa: BLE001 - network, HTTP, JSON: one message
        raise CiteError(f"could not fetch {url}: {e}") from None


def journals() -> dict:
    return load_yaml(resources.files("lablogbook").joinpath("data/journals.yaml").read_text(encoding="utf-8")) or {}


def _clean(s: str) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", "", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def _tex(s: str) -> str:
    return s.replace("\\", "").replace("{", "").replace("}", "").replace("&", r"\&").replace("%", r"\%")


def from_crossref(msg: dict) -> tuple[str, dict]:
    typ = {"journal-article": "article", "book": "book", "monograph": "book", "book-chapter": "incollection",
           "proceedings-article": "inproceedings", "posted-content": "misc"}.get(msg.get("type", ""), "misc")
    authors = [f"{a.get('family', '')}, {a.get('given', '')}".strip(", ") for a in msg.get("author", []) if a.get("family")]
    year = ((msg.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    journal = _clean((msg.get("container-title") or [""])[0])
    # The lab's list wins: Crossref's "short" title is sometimes the full one.
    short = journals().get(journal) or _clean((msg.get("short-container-title") or [""])[0])
    f = {"author": " and ".join(authors), "title": "{" + _tex(_clean((msg.get("title") or [""])[0])) + "}",
         "journal": _tex(journal) if typ == "article" else "", "shortjournal": _tex(short) if typ == "article" else "",
         "booktitle": _tex(journal) if typ in ("incollection", "inproceedings") else "",
         "publisher": _tex(_clean(msg.get("publisher", ""))) if typ == "book" else "",
         "volume": msg.get("volume", ""), "number": msg.get("issue", ""),
         "pages": (msg.get("page") or msg.get("article-number") or "").replace("-", "--"),
         "year": str(year or ""), "doi": msg.get("DOI", "")}
    return typ, {k: v for k, v in f.items() if v}


def from_openlibrary(data: dict, isbn: str) -> tuple[str, dict]:
    authors = []
    for a in data.get("authors", []):
        try:
            n = _get(f"https://openlibrary.org{a['key']}.json").get("name", "")
        except CiteError:
            n = ""
        if n:
            parts = n.split()
            authors.append(f"{parts[-1]}, {' '.join(parts[:-1])}" if len(parts) > 1 else n)
    year = re.search(r"\d{4}", data.get("publish_date", "") or "")
    f = {"author": " and ".join(authors), "title": "{" + _tex(data.get("title", "")) + "}",
         "publisher": _tex((data.get("publishers") or [""])[0]), "year": year.group(0) if year else "", "isbn": isbn}
    return "book", {k: v for k, v in f.items() if v}


def make_key(fields: dict, taken: set[str]) -> str:
    first = fields.get("author", "Anon").split(" and ")[0].split(",")[0]
    last = unicodedata.normalize("NFD", first)
    last = re.sub(r"[^A-Za-z]", "", "".join(c for c in last if not unicodedata.combining(c))) or "Anon"
    base = last[0].upper() + last[1:] + fields.get("year", "")
    key, n = base, 0
    while key in taken:
        key = base + "abcdefghijklmnopqrstuvwxyz"[n]
        n += 1
    return key


def format_record(typ: str, key: str, fields: dict) -> str:
    order = ["author", "title", "journal", "shortjournal", "booktitle", "publisher", "volume", "number", "pages", "year", "doi", "isbn"]
    w = max(len(k) for k in fields)
    lines = [f"  {k.ljust(w)} = {{{fields[k]}}}" for k in order if k in fields]
    return f"@{typ}{{{key},\n" + ",\n".join(lines) + "\n}\n"


def add(book: Book, ident: str, fetch=_get) -> tuple[str, bool]:
    """(key, added). `ident` is a DOI (10.xxx/…, or a doi.org URL) or an ISBN."""
    ident = ident.strip()
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", ident, flags=re.I)
    path = book.bib_path
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    records = bibmod.parse(text) if text else []
    if doi.startswith("10."):
        for r in records:
            if r.fields.get("doi", "").lower() == doi.lower():
                return r.key, False
        typ, fields = from_crossref(fetch(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")["message"])
    else:
        isbn = re.sub(r"[^0-9Xx]", "", ident)
        if len(isbn) not in (10, 13):
            raise CiteError(f"not a DOI or an ISBN: {ident}")
        for r in records:
            if re.sub(r"[^0-9Xx]", "", r.fields.get("isbn", "")) == isbn:
                return r.key, False
        typ, fields = from_openlibrary(fetch(f"https://openlibrary.org/isbn/{isbn}.json"), isbn)
    key = make_key(fields, {r.key for r in records})
    path.parent.mkdir(parents=True, exist_ok=True)
    sep = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    path.write_text(text + sep + format_record(typ, key, fields), encoding="utf-8")
    return key, True
