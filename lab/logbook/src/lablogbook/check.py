"""The submission checker: the same code runs in `logbook check` on a laptop, in the web form's
workflow and in CI on every pull request.

Levels: fail (cannot be merged), hold (waits for the author's export-control confirmation),
warn (read again; merges), info (for the author, e.g. proposed co-authors).
In CI (`ci=True`) a finding never shows the text it matched, only file, line and kind of hit, so
a slip does not spread into logs.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import asdict, dataclass, field
from importlib import resources
from pathlib import Path

import jsonschema

from . import bib as bibmod
from . import entry as entry_mod
from . import epics, gitutil, patterns, state
from . import render as render_mod
from .patterns import institutional
from .book import Book
from .entry import ID_RE, OPENABLE, CALLOUTS, Entry, EntryError

LEVELS = ("fail", "hold", "warn", "info")


@dataclass
class Finding:
    level: str
    code: str
    path: str
    line: int | None
    message: str
    excerpt: str | None = None   # the offending line; local runs only

    def render(self, ci: bool = False) -> str:
        loc = f"{self.path}:{self.line}" if self.line else self.path
        out = f"{loc}: {self.level.upper()} {self.code}: {self.message}"
        if self.excerpt and not ci:
            out += f"\n    | {self.excerpt.strip()[:160]}"
        return out


@dataclass
class Options:
    base: str | None = None             # git ref: check what HEAD changes relative to it (a pull request)
    head: str = "HEAD"
    paths: list[Path] = field(default_factory=list)   # explicit files; else the changes; else everything
    submitter: str | None = None        # GitHub login of whoever submits (pull-request author)
    today: str | None = None            # YYYY-MM-DD; default: today
    ci: bool = False


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)

    def add(self, level, code, path, line, message, excerpt=None):
        self.findings.append(Finding(level, code, path, line, message, excerpt))

    @property
    def exit_code(self) -> int:
        levels = {f.level for f in self.findings}
        return 1 if "fail" in levels else 3 if "hold" in levels else 0

    def render(self, ci: bool = False) -> str:
        order = {lvl: i for i, lvl in enumerate(LEVELS)}
        lines = [f.render(ci) for f in sorted(self.findings, key=lambda f: (order[f.level], f.path, f.line or 0))]
        n = {lvl: sum(f.level == lvl for f in self.findings) for lvl in LEVELS}
        summary = f"checked {len(self.checked)} file(s): {n['fail']} failed, {n['hold']} held, {n['warn']} warnings, {n['info']} notes"
        if n["hold"]:
            summary += ("\nHELD: a PDF attachment or a figure that is not a plot waits for the author to confirm it holds "
                        "no export-controlled technical data (export_control_confirmed: true). If in doubt, do not "
                        "confirm: link the file where it lives (restricted sharing) instead of attaching it, or ask the PI.")
        return "\n".join(lines + [summary])

    def to_json(self) -> str:
        return json.dumps({"exit_code": self.exit_code, "checked": self.checked,
                           "findings": [asdict(f) | {"excerpt": None} for f in self.findings]}, indent=2)


# ------------------------------------------------------------------------------- helpers --
def _schema() -> dict:
    return json.loads(resources.files("lablogbook").joinpath("data/entry.schema.json").read_text(encoding="utf-8"))


def _header_line(e: Entry, key: str) -> int | None:
    for i, line in enumerate(e.text.splitlines()[: e.body_line], start=1):
        if re.match(rf"^{re.escape(key)}\s*:", line):
            return i
    return None


def _schema_message(err: jsonschema.ValidationError) -> tuple[str, str]:
    """(top-level field, message) without echoing values."""
    where = [str(p) for p in err.absolute_path]
    fld = where[0] if where else ""
    dotted = ".".join(where) or "header"
    v = err.validator
    if v == "required":
        missing = re.findall(r"'([^']+)' is a required property", err.message)
        return fld, f"{dotted}: missing field '{missing[0] if missing else '?'}'"
    if v == "additionalProperties":
        extra = re.findall(r"'([^']+)'", err.message)
        return fld, f"{dotted}: unknown field(s) {', '.join(repr(x) for x in extra)}"
    if v == "pattern":
        return fld, f"{dotted}: has the wrong form"
    if v == "type":
        return fld, f"{dotted}: must be {err.validator_value}"
    if v == "enum":
        return fld, f"{dotted}: must be one of {err.validator_value}"
    if v in ("minLength", "minItems"):
        return fld, f"{dotted}: too short"
    if v == "maxLength":
        return fld, f"{dotted}: too long"
    if v == "uniqueItems":
        return fld, f"{dotted}: has duplicates"
    return fld, f"{dotted}: violates '{v}'"


def _days(a: str, b: str) -> int:
    return (dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days


def _size_mb(p: Path) -> float:
    return p.stat().st_size / 1e6


def _reviewed(e: Entry) -> set[str]:
    r = e.header.get("reviewed")
    return {r} if isinstance(r, str) else set(r or [])


# ---------------------------------------------------------------------------- the checks --
def scan_text(book: Book, rel: str, text: str, report: Report, reviewed: set[str] = frozenset(),
              ci: bool = False) -> None:
    """Compliance patterns over every line of a text an author wrote (entry or wiki page)."""
    names = {p.name for p in (book.people or {}).values()} | {p.handle for p in (book.people or {}).values()}
    surnames = {n.split()[-1] for n in names if n}
    emails = {(p.email or "").lower() for p in (book.people or {}).values()}
    privacy = book.config.get("privacy") or {}
    domains = privacy.get("email_domains", ["edu"]) or []
    idp = privacy.get("id_pattern", patterns.DEFAULT_ID_PATTERN)
    id_rx = re.compile(idp) if idp else None
    for i, line in enumerate(text.splitlines(), start=1):
        hits = patterns.scan_line(line, id_rx)
        for code, cat, msg in hits:
            if cat == "drive" and not book.config.get("forbid_drive_ids", False):
                report.add("info", code, rel, i, "a Google Drive link: fine in this log book as long as the file's sharing "
                           "stays restricted (never 'anyone with the link')", line)
                continue
            if cat in ("ferpa", "health") and cat in reviewed:
                report.add("warn", code, rel, i, f"{msg}; reviewed by the author (override recorded)", line)
            elif cat == "vendor":
                report.add("warn", code, rel, i, f"{msg}: proprietary vendor information and export-controlled "
                           "data never go into the log book; re-read this line", line)
            else:
                report.add("fail", code, rel, i, msg + (f" (if harmless after reading: add 'reviewed: {cat}' to the header)"
                                                        if cat in ("ferpa", "health") else ""), line)
        for m in patterns.STUDENT_NAME.finditer(line):
            who = (m.group(1) or m.group(2) or "").strip()
            first = who.split()[0] if who else ""
            if who and first not in patterns.NOT_NAMES and who not in names and who.split()[-1] not in surnames:
                level = "warn" if "ferpa" in reviewed else "fail"
                report.add(level, "ferpa-student-name", rel, i,
                           "a person named as a student who is not a lab member" +
                           ("; reviewed by the author" if level == "warn" else
                            " (if harmless after reading: add 'reviewed: ferpa' to the header)"), line)
        for m in patterns.ADDRESS.finditer(line):
            if not institutional(m.group(1), domains):
                continue
            if book.people is not None and m.group(0).lower() not in emails:
                level = "warn" if "ferpa" in reviewed else "fail"
                report.add(level, "ferpa-email", rel, i, "a university e-mail address of someone who is not in people.yaml", line)


def check_entry(book: Book, e: Entry, st: state.State, report: Report, opts: Options, new: bool) -> None:
    rel = book.rel(e.path)
    h = e.header
    today = opts.today or book.now().date().isoformat()

    # --- schema -------------------------------------------------------------------------------
    schema_ok = True
    for err in sorted(jsonschema.Draft202012Validator(_schema()).iter_errors(h), key=lambda x: list(x.absolute_path)):
        fld, msg = _schema_message(err)
        report.add("fail", "schema", rel, _header_line(e, fld) if fld else 1, msg)
        schema_ok = False

    # --- name, folder, id -----------------------------------------------------------------------
    m = ID_RE.match(e.id)
    if not m:
        report.add("fail", "name", rel, None, "file name must be YYYY-MM-DD-HHMM-<handle>-<slug>.md (lower case, hyphens)")
    else:
        expected = (book.entries_dir / m.group("date")[:4] / f"{e.id}.md").resolve()
        if e.path.resolve() != expected:
            report.add("fail", "name", rel, None, f"belongs in {book.rel(expected)}")
        if isinstance(h.get("date"), str) and h["date"] != m.group("date"):
            report.add("fail", "name", rel, _header_line(e, "date"), "the date in the file name and the header differ")
        if isinstance(h.get("time"), str) and h["time"].replace(":", "") != m.group("hhmm"):
            report.add("fail", "name", rel, _header_line(e, "time"), "the time in the file name and the header differ")
        if book.people is not None and e.authors and m.group("handle") != e.authors[0]:
            report.add("fail", "name", rel, None, "the handle in the file name must be the first author's")
    if not schema_ok:
        return   # the rest assumes a well-formed header

    # --- dates ----------------------------------------------------------------------------------
    date = h["date"]
    try:
        dt.date.fromisoformat(date)
    except ValueError:
        report.add("fail", "date", rel, _header_line(e, "date"), "not a real date")
        return
    if _days(date, today) > 1:
        report.add("fail", "date", rel, _header_line(e, "date"), "dated in the future")
    # a migrated entry was written when its source was committed (`logged`), not today; only an
    # admin migrates, so the fields cannot be used to dodge the rule
    migrated = bool(h.get("migrated_from") and h.get("logged"))
    if new and migrated and opts.submitter and book.people is not None and not book.is_admin(opts.submitter):
        report.add("fail", "migrated", rel, _header_line(e, "migrated_from"), "only an admin submits migrated entries")
    written = str(h["logged"])[:10] if migrated else today
    if new and _days(written, date) > book.config["late_days"] and not h.get("backfilled"):
        report.add("fail", "late", rel, _header_line(e, "date"),
                   f"written more than {book.config['late_days']} days after the work: add 'backfilled: {written}'")
    if h.get("backfilled") and _days(h["backfilled"], date) < 0:
        report.add("fail", "date", rel, _header_line(e, "backfilled"), "backfilled before the date of the work")

    # --- kind -----------------------------------------------------------------------------------
    kind = book.kinds.get(h["kind"])
    if kind is None:
        report.add("fail", "kind", rel, _header_line(e, "kind"), f"unknown kind; known: {', '.join(sorted(book.kinds))}")
    else:
        for f in kind.get("requires") or []:
            if h.get(f) in (None, [], ""):
                report.add("fail", "kind", rel, _header_line(e, "kind"), f"{'an' if str(h['kind'])[:1] in 'aeiou' else 'a'} {h['kind']} entry needs '{f}'")
        for f in kind.get("recommends") or []:
            if h.get(f) in (None, [], ""):
                report.add("warn", "kind", rel, _header_line(e, "kind"), f"a {h['kind']} entry usually has '{f}'")
    if h["kind"] == "redaction" and opts.submitter and book.people is not None and not book.is_admin(opts.submitter):
        report.add("fail", "redaction", rel, None, "only an admin may submit a redaction")

    # --- registries -------------------------------------------------------------------------------
    if book.people is not None:
        for a in e.authors:
            if a not in book.people:
                report.add("fail", "author", rel, _header_line(e, "authors"), f"author '{a}' is not in people.yaml")
    if book.projects is not None:
        for p in e.projects:
            if p not in book.projects:
                report.add("fail", "project", rel, _header_line(e, "project"), f"project '{p}' is not in projects.yaml")
        sp = h.get("subproject")
        if sp and h["project"] in book.projects and sp not in book.subprojects(h["project"]):
            report.add("fail", "project", rel, _header_line(e, "subproject"), f"'{sp}' is not a subproject of '{h['project']}'")
    if book.apparatus is not None:
        for a in h.get("apparatus") or []:
            if a not in book.apparatus:
                report.add("fail", "apparatus", rel, _header_line(e, "apparatus"), f"apparatus '{a}' is not in apparatus.yaml")

    # --- links between entries ----------------------------------------------------------------------
    for key in ("corrects", "redacts"):
        t = h.get(key)
        if t and (t not in book.entries or t == e.id):
            report.add("fail", "link", rel, _header_line(e, key), f"{key}: no earlier entry '{t}'")
    for t in h.get("related") or []:
        if t not in book.entries or t == e.id:
            report.add("fail", "link", rel, _header_line(e, "related"), f"related: no entry '{t}'")
    for target, line in e.links():
        if target.startswith("wiki:"):
            page = target[5:].strip().removesuffix(".md")
            if not (book.wiki_dir / f"{page}.md").exists():
                report.add("warn", "link", rel, line, f"wiki page '{page}' does not exist (yet)")
            continue
        tid, _, anchor = target.partition("#")
        if tid not in book.entries:
            report.add("fail", "link", rel, line, f"[[{tid}]]: no such entry")
        elif anchor and anchor not in book.entries[tid].anchors():
            report.add("fail", "link", rel, line, f"[[{target}]]: that entry has no block #{anchor}")
    for target in h.get("resolves") or []:
        tid, _, anchor = target.partition("#")
        t = book.entries.get(tid)
        if t is None:
            report.add("fail", "resolves", rel, _header_line(e, "resolves"), f"no entry '{tid}'")
            continue
        block = t.anchors().get(anchor)
        if block is None or block.name not in OPENABLE:
            report.add("fail", "resolves", rel, _header_line(e, "resolves"), f"'{tid}' has no issue or todo #{anchor}")
        elif st.resolved_by.get(target):
            report.add("fail", "resolves", rel, _header_line(e, "resolves"),
                       f"#{anchor} of '{tid}' is already resolved by {', '.join(st.resolved_by[target])}")

    for target in (h.get("priority") or {}) if isinstance(h.get("priority"), dict) else []:
        tid, _, anchor = str(target).partition("#")
        t = book.entries.get(tid)
        block = t.anchors().get(anchor) if t else None
        if block is None or block.name not in OPENABLE:
            report.add("fail", "priority", rel, _header_line(e, "priority"), f"'{target}': no such issue or todo")
        elif st.resolved_by.get(target):
            report.add("warn", "priority", rel, _header_line(e, "priority"),
                       f"'{target}' is already resolved by {', '.join(st.resolved_by[target])}; its priority no longer matters")

    if h.get("kind") == "order" and isinstance(h.get("items"), list):
        ns = [x.get("n") for x in h["items"] if isinstance(x, dict)]
        if len(ns) != len(set(ns)):
            report.add("fail", "order", rel, _header_line(e, "items"), "two items with the same n")
        anchors = e.anchors()
        for x in h["items"]:
            if isinstance(x, dict) and not x.get("arrived") and f"item-{x.get('n')}" not in anchors:
                report.add("warn", "order", rel, _header_line(e, "items"),
                           f"item {x.get('n')} has not arrived but has no open item #item-{x.get('n')}")

    # --- blocks ----------------------------------------------------------------------------------
    for b in e.blocks:
        if b.priority is not None and (b.priority not in entry_mod.PRIORITIES or b.name not in OPENABLE or not b.anchor):
            report.add("fail" if new else "warn", "block", rel, b.line,
                       f"priority={b.priority}: only an issue or todo with an id has a priority, one of "
                       + ", ".join(entry_mod.PRIORITIES))
    for line_no, msg in entry_mod.block_problems(e.body, e.body_line):
        # a new entry is fixed before it goes in; one already in the book cannot change any more
        report.add("fail" if new else "warn", "block", rel, line_no, msg)
    seen = {}
    for b in e.blocks:
        if b.name not in CALLOUTS:
            report.add("warn", "block", rel, b.line, f"'::: {b.name}' is not a known block ({', '.join(CALLOUTS)})")
        if b.name in OPENABLE and not b.anchor:
            report.add("warn", "block", rel, b.line,
                       f"give this {b.name} an id, e.g. '::: {b.name} {{#{b.name}-1}}', so a later entry can resolve it")
        if b.anchor:
            if b.anchor in seen:
                report.add("fail", "block", rel, b.line, f"block id #{b.anchor} is used twice")
            seen[b.anchor] = b

    # --- files -------------------------------------------------------------------------------------
    limits = book.config["limits"]
    allowed_pvs = {}
    for a in (book.apparatus or {}).values():
        for g, pvs in (a.get("epics_groups") or {}).items():
            allowed_pvs.setdefault(g, []).extend(pvs or [])
    for section, f, item in e.files():
        p = (e.folder / f)
        line = _header_line(e, section)
        if not p.resolve().is_relative_to(book.entries_dir.resolve()):
            report.add("fail", "file", rel, line, f"{f}: must stay inside {book.config['entries']}/")
            continue
        if not p.exists():
            report.add("fail", "file", rel, line, f"{f}: file not found")
            continue
        size = _size_mb(p)
        if size > limits["fail_mb"]:
            report.add("fail", "size", rel, line, f"{f}: {size:.1f} MB, over the {limits['fail_mb']} MB limit")
        elif size > limits["warn_mb"]:
            report.add("warn", "size", rel, line, f"{f}: {size:.1f} MB; over {limits['warn_mb']} MB, rasterise dense content inside the PDF")
        if section == "figures":
            kind = item.get("kind", "plot")
            stem = p.with_suffix("")
            if kind == "plot":
                if not stem.with_suffix(".svg").exists():
                    report.add("fail", "figure", rel, line, f"{f}: a plot needs its SVG next to it ({stem.name}.svg) for the HTML view")
                if not stem.with_suffix(".pdf").exists():
                    report.add("warn", "figure", rel, line, f"{f}: no PDF next to it; the PDF build will use the SVG")
                if stem.name.endswith("-draft"):
                    report.add("fail", "figure", rel, line, f"{f}: a draft may be overwritten; save a version (labfig version=N)")
                elif not re.search(r"-v\d+$", stem.name):
                    report.add("warn", "figure", rel, line, f"{f}: no version in the name; save with labfig (…-vN)")
            elif not item.get("export_control_confirmed"):
                report.add("hold", "export-control", rel, line,
                           f"{f}: a {kind} waits for the author's export-control confirmation (export_control_confirmed: true)")
        if section == "attachments" and p.suffix.lower() == ".pdf" and not item.get("export_control_confirmed"):
            report.add("hold", "export-control", rel, line,
                       f"{f}: a PDF attachment waits for the author's export-control confirmation (export_control_confirmed: true)")
        if section == "epics":
            group = item["group"]
            allowed = allowed_pvs.get(group) if book.apparatus is not None else None
            if book.apparatus is not None and group not in allowed_pvs:
                report.add("fail", "epics", rel, line, f"{f}: no PV group '{group}' in apparatus.yaml")
            for problem in epics.check_snapshot(p, group, allowed):
                report.add("fail", "epics", rel, line, f"{f} {problem}")

    # --- citations -----------------------------------------------------------------------------------
    cites = e.citations()
    if cites:
        keys = _bib_keys(book)
        for key, line in cites:
            if keys is None:
                report.add("fail", "cite", rel, line, f"@{key}: no reference list ({book.config['bibliography']})")
                break
            if key not in keys:
                report.add("fail", "cite", rel, line, f"@{key} is not in the reference list: add the reference first (logbook cite add <doi>)")

    # --- compliance ----------------------------------------------------------------------------------
    scan_text(book, rel, e.text, report, _reviewed(e), opts.ci)

    # --- co-authors (new entries in a central book) ------------------------------------------------
    if new and book.people is not None:
        window = book.config["coauthor_days"]
        recent = set()
        for o in book.entries.values():
            if o.id != e.id and set(o.projects) & set(e.projects):
                try:
                    if 0 <= _days(date, o.date) <= window:
                        recent.update(o.authors)
                except ValueError:
                    pass
        others = sorted(recent - set(e.authors))
        if others:
            names = ", ".join(f"{book.people[h].name} ({h})" if h in book.people else h for h in others)
            report.add("info", "coauthors", rel, _header_line(e, "authors"),
                       f"also working on {', '.join(e.projects)} in the last {window} days: {names}. Add them to 'authors' if they took part.")


_BIB_CACHE: dict[Path, set[str] | None] = {}


def _bib_keys(book: Book) -> set[str] | None:
    if book.bib_path not in _BIB_CACHE:
        if not book.bib_path.exists():
            _BIB_CACHE[book.bib_path] = None
        else:
            try:
                _BIB_CACHE[book.bib_path] = {r.key for r in bibmod.parse(book.bib_path.read_text(encoding="utf-8"))}
            except bibmod.BibError:
                _BIB_CACHE[book.bib_path] = set()
    return _BIB_CACHE[book.bib_path]


def check_bib(book: Book, report: Report, new_keys: set[str] | None) -> None:
    rel = book.rel(book.bib_path)
    try:
        records = bibmod.parse(book.bib_path.read_text(encoding="utf-8"))
    except bibmod.BibError as err:
        report.add("fail", "bib", rel, None, f"does not parse: {err}")
        return
    seen: dict[str, int] = {}
    for r in records:
        if r.key in seen:
            report.add("fail", "bib", rel, r.line, f"key {r.key} is used twice (first on line {seen[r.key]})")
        seen[r.key] = r.line
        if not (r.fields.get("doi") or r.fields.get("isbn")):
            if new_keys is None:
                report.add("warn", "bib", rel, r.line, f"{r.key} has neither a DOI nor an ISBN")
            elif r.key in new_keys:
                report.add("fail", "bib", rel, r.line, f"{r.key}: a new reference needs a DOI or an ISBN")


def _within(book: Book, top: Path, path: str) -> Path | None:
    p = (top / path).resolve()
    return p if p.is_relative_to(book.root.resolve()) else None


def run(book: Book, opts: Options) -> Report:
    report = Report()
    _BIB_CACHE.clear()
    for f, err in book.broken.items():
        if not opts.paths or f.resolve() in {p.resolve() for p in opts.paths}:
            report.add("fail", "parse", book.rel(f), 1, err)

    new_ids: set[str] = set()
    wiki_files: list[Path] = []
    bib_new_keys: set[str] | None = None
    check_bib_now = False

    if opts.base:
        top = gitutil.toplevel(book.root) or book.root
        entries_root = book.entries_dir.resolve()
        wiki_root = book.wiki_dir.resolve()
        changes = gitutil.changes(top, opts.base, opts.head)
        added_redactions = {}
        for c in changes:
            p = _within(book, top, c.path)
            if p and p.suffix == ".md" and p.is_relative_to(entries_root) and c.status in "AC":
                try:
                    ne = entry_mod.parse(p)
                    if ne.header.get("kind") == "redaction" and ne.header.get("redacts"):
                        added_redactions[ne.header["redacts"]] = ne.id
                except (EntryError, OSError):
                    pass
        redacted_files = set()
        for rid in added_redactions:
            path = (book.entries_dir / rid[:4] / f"{rid}.md").resolve()
            redacted_files.add(path)
            old_e = book.entries.get(rid)
            if old_e is None:   # the redaction deletes the whole entry: read it as it was
                text = gitutil.file_at(top, opts.base, path.relative_to(top.resolve()).as_posix())
                try:
                    old_e = entry_mod.parse(path, text) if text else None
                except EntryError:
                    old_e = None
            if old_e is not None:
                redacted_files.update((path.parent / f).resolve() for _, f, _ in old_e.files())
        protected_touched = []
        added_assets: list[Path] = []
        for c in changes:
            p = _within(book, top, c.path)
            old = _within(book, top, c.old) if c.old else None
            if p is None and old is None:
                continue
            target = p or old
            rel = book.rel(target)
            report.checked.append(rel)
            if target.is_relative_to(entries_root) or (old and old.is_relative_to(entries_root)):
                if c.status in "AC":
                    if target.suffix == ".md":
                        new_ids.add(target.stem)
                    else:
                        added_assets.append(target)
                    continue
                touched = [x for x in (old, p) if x is not None and x.is_relative_to(entries_root)]
                if all(x in redacted_files for x in touched) and touched:
                    if opts.submitter and book.people is not None and not book.is_admin(opts.submitter):
                        report.add("fail", "append-only", rel, None, "only an admin may change an entry under a redaction")
                    else:
                        report.add("info", "redaction", rel, None, "changed under a redaction entry in this change set")
                    continue
                verb = {"M": "changes", "D": "deletes", "R": "renames", "T": "changes"}.get(c.status, "changes")
                report.add("fail", "append-only", rel, None,
                           f"{verb} an existing entry or one of its files; entries are never changed: write a correction entry (kind: correction, corrects: <id>)")
            elif target.is_relative_to(wiki_root):
                if target.resolve() == book.bib_path.resolve():
                    check_bib_now = True
                    old_text = gitutil.file_at(top, opts.base, c.path) or ""
                    try:
                        old_keys = {r.key for r in bibmod.parse(old_text)}
                    except bibmod.BibError:
                        old_keys = set()
                    try:
                        bib_new_keys = {r.key for r in bibmod.parse(target.read_text(encoding="utf-8"))} - old_keys
                    except (bibmod.BibError, OSError):
                        bib_new_keys = set()
                elif target.suffix == ".md" and target.exists():
                    wiki_files.append(target)
            else:
                protected_touched.append(rel)
        if protected_touched and book.people is not None:
            if not opts.submitter:
                report.add("info", "protected", protected_touched[0], None,
                           f"{len(protected_touched)} file(s) outside entries/ and wiki/ changed; who may change them is checked in CI")
            elif not book.is_admin(opts.submitter):
                for rel in protected_touched:
                    report.add("fail", "protected", rel, None, "only an admin may change files outside entries/ and wiki/")
        # authorship of a pull request: the submitter is the first author of every new entry
        if opts.submitter and book.people is not None:
            person = book.person_by_login(opts.submitter)
            for nid in sorted(new_ids):
                e = book.entries.get(nid)
                if e is None:
                    continue
                if person is None:
                    report.add("fail", "authorship", book.rel(e.path), None, f"the submitter '{opts.submitter}' is not in people.yaml")
                elif e.authors and e.authors[0] != person.handle and person.role != "admin":
                    report.add("fail", "authorship", book.rel(e.path), _header_line(e, "authors"),
                               f"the first author must be the person submitting ({person.handle})")
        scope = [book.entries[i] for i in sorted(new_ids) if i in book.entries]
        referenced = {(e.folder / f).resolve() for e in book.entries.values() for _, f, _ in e.files()}
        for a in added_assets:
            stem = a.with_suffix("")
            siblings = {stem.with_suffix(x).resolve() for x in (".pdf", ".svg", ".png", ".yaml")}
            if a.resolve() not in referenced and not (siblings & referenced):
                report.add("warn", "file", book.rel(a), None, "added, but no entry refers to it")
    elif opts.paths:
        scope = []
        for p in opts.paths:
            p = p.resolve()
            if p.is_relative_to(book.wiki_dir.resolve()) and p.suffix == ".md":
                wiki_files.append(p)
            elif p == book.bib_path.resolve():
                check_bib_now = True
            else:
                found = [e for e in book.entries.values() if e.path.resolve() == p]
                if found:
                    scope += found
                    new_ids.update(e.id for e in found)
                elif p not in book.broken:
                    report.add("fail", "parse", book.rel(p), None, "not an entry of this log book")
            report.checked.append(book.rel(p))
    else:
        scope = sorted(book.entries.values(), key=lambda e: e.id)
        wiki_files = sorted(book.wiki_dir.rglob("*.md")) if book.wiki_dir.exists() else []
        check_bib_now = book.bib_path.exists()
        report.checked += [book.rel(e.path) for e in scope] + [book.rel(w) for w in wiki_files]

    st = state.compute(book.entries, exclude={e.id for e in scope})
    for e in scope:
        check_entry(book, e, st, report, opts, new=e.id in new_ids)
    for w in wiki_files:
        rel = book.rel(w)
        meta, body, head = render_mod.wiki_split(w.read_text(encoding="utf-8"))
        r = meta.get("reviewed")
        text = "\n" * head + body          # line numbers stay those of the file
        scan_text(book, rel, text, report, reviewed={r} if isinstance(r, str) else set(r or []), ci=opts.ci)
        for m in entry_mod._WIKILINK.finditer(text):
            target = m.group(1).strip()
            if not target.startswith("wiki:") and target.split("#")[0] not in book.entries:
                report.add("warn", "link", rel, text.count("\n", 0, m.start()) + 1, f"[[{target}]]: no such entry")
    if check_bib_now and book.bib_path.exists():
        check_bib(book, report, bib_new_keys)
    return report
