"""A log book: a folder of entries, optionally with a wiki, registries and a configuration.

Standalone (nothing configured): entries in `entries/`, any author names, any projects. A central
log book adds `logbook.yaml` at its root and the registries it names; then authors are handles
from people.yaml, projects and apparatus must exist, and the authorship check knows who may
submit on behalf of others.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from . import entry as entry_mod
from .entry import Entry, EntryError, load_yaml

DEFAULTS = {
    "title": "Log book",
    "author": None,          # title block of the PDF; default: the first entry's first author
    "affiliation": None,
    "logo": None,            # image shown top left in the HTML view (path from the book's root); PNG or SVG
    "entries": "entries",
    "wiki": "wiki",
    "bibliography": "wiki/references.bib",
    "registries": {"people": "people.yaml", "projects": "projects.yaml",
                   "apparatus": "apparatus.yaml", "kinds": "kinds.yaml"},
    "limits": {"warn_mb": 2, "fail_mb": 5},
    "late_days": 2,          # an entry dated earlier than this before it is logged needs `backfilled`
    "coauthor_days": 14,     # people who logged on the same project this recently are proposed
    "forbid_drive_ids": False,  # True: Drive links in entries and wiki fail (figure files are never scanned)
    "timezone": None,           # IANA name (America/Chicago): dates and times of new entries, also on a UTC runner
    # institutional addresses of people not in people.yaml are flagged; "edu" covers every .edu
    # host, a book names its own (example.edu, lab.example.gov); id_pattern: student or staff ID numbers
    # (a regular expression; null turns the rule off; default: nine digits standing alone)
    "privacy": {"email_domains": ["edu"]},
    "open_items": {"asap_days": 2},
    "orders": {"currency": "$"},        # the symbol in front of an order's prices   # an item ASAP for longer than this goes to the top, marked overdue
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


@dataclass
class Person:
    handle: str
    name: str
    github: str | None = None
    email: str | None = None
    role: str = "member"       # admin may submit on behalf of others and change tooling
    access: str = "central"    # central | project (reads the per-project copy only)


@dataclass
class Book:
    root: Path
    config: dict
    people: dict[str, Person] | None = None          # None = standalone, any names
    projects: dict[str, dict] | None = None
    apparatus: dict[str, dict] | None = None
    kinds: dict[str, dict] = field(default_factory=dict)
    entries: dict[str, Entry] = field(default_factory=dict)
    broken: dict[Path, str] = field(default_factory=dict)   # files under entries/ that do not parse

    # ---- paths -----------------------------------------------------------------------------
    @property
    def entries_dir(self) -> Path:
        return self.root / self.config["entries"]

    @property
    def wiki_dir(self) -> Path:
        return self.root / self.config["wiki"]

    @property
    def bib_path(self) -> Path:
        return self.root / self.config["bibliography"]

    def now(self) -> dt.datetime:
        """The current time in the book's time zone (`timezone:` in logbook.yaml), else the machine's."""
        tz = self.config.get("timezone")
        if tz:
            from zoneinfo import ZoneInfo
            return dt.datetime.now(ZoneInfo(tz))
        return dt.datetime.now().astimezone()

    def rel(self, p: Path) -> str:
        try:
            return p.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return str(p)

    # ---- people ----------------------------------------------------------------------------
    def person_by_login(self, login: str | None) -> Person | None:
        if not login or not self.people:
            return None
        low = login.lower()
        for p in self.people.values():
            if (p.github or "").lower() == low or p.handle == low:
                return p
        return None

    def is_admin(self, login: str | None) -> bool:
        p = self.person_by_login(login)
        return bool(p and p.role == "admin")

    def project_names(self) -> set[str]:
        return set(self.projects or {})

    def subprojects(self, project: str) -> set[str]:
        return set((self.projects or {}).get(project, {}).get("subprojects") or [])


def _read_registry(path: Path, key: str) -> dict[str, dict] | None:
    if not path.exists():
        return None
    data = load_yaml(path.read_text(encoding="utf-8")) or []
    if isinstance(data, dict):            # name: {fields} form
        return {str(k): (v or {}) for k, v in data.items()}
    return {str(item[key]): item for item in data}   # list of {key: ..., ...} form


def default_kinds() -> dict[str, dict]:
    text = resources.files("lablogbook").joinpath("data/kinds.yaml").read_text(encoding="utf-8")
    return load_yaml(text)


def find_root(start: Path) -> Path:
    """The book root: the nearest folder with logbook.yaml, else the git top level, else start."""
    start = start.resolve()
    for d in [start, *start.parents]:
        if (d / "logbook.yaml").exists():
            return d
    for d in [start, *start.parents]:
        if (d / ".git").exists():
            return d
    return start


def open_book(root: str | Path | None = None, load_entries: bool = True) -> Book:
    root = find_root(Path(root or "."))
    cfg_file = root / "logbook.yaml"
    cfg = _merge(DEFAULTS, load_yaml(cfg_file.read_text(encoding="utf-8")) or {}) if cfg_file.exists() else dict(DEFAULTS)
    reg = cfg["registries"]
    book = Book(root=root, config=cfg)
    people = _read_registry(root / reg["people"], "handle")
    if people is not None:
        book.people = {h: Person(handle=h, name=str(v.get("name", h)), github=v.get("github"),
                                 email=v.get("email"), role=v.get("role", "member"),
                                 access=v.get("access", "central")) for h, v in people.items()}
    book.projects = _read_registry(root / reg["projects"], "name")
    book.apparatus = _read_registry(root / reg["apparatus"], "id")
    book.kinds = default_kinds()
    extra = _read_registry(root / reg["kinds"], "name")
    if extra:
        book.kinds.update(extra)
    if load_entries:
        for f in sorted(book.entries_dir.rglob("*.md")) if book.entries_dir.exists() else []:
            try:
                e = entry_mod.parse(f)
                book.entries[e.id] = e
            except (EntryError, UnicodeDecodeError) as err:
                book.broken[f] = str(err)
    return book
