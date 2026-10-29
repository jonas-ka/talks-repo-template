"""`logbook new`: a draft becomes an entry.

The draft is a Markdown file with a YAML header like an entry's, without what the tool fills in
(date and time default to now, the id, the first author). Files the header names (figures, data,
attachments, EPICS snapshots) are given relative to the draft and are copied next to the entry;
a figure brings its siblings (`.pdf`, `.svg`, `.png`, the labfig record `.yaml`). Nothing is ever
overwritten: a file of the same name with other content is refused.

In a repository connected to a central log book the entry is written in a temporary git worktree
of the central clone (the clone's own checkout is never touched), checked, committed on a branch
`entry/<handle>/<id>`, pushed, and proposed as a pull request that merges itself once the checks
pass. Standalone, the entry is simply written into `entries/`.
"""

from __future__ import annotations

import datetime as dt
import filecmp
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import check, connect
from .book import Book, open_book
from .entry import load_yaml, new_id

SECTION_DIR = {"figures": "figures", "data": "data", "attachments": "attachments", "epics": "epics"}
ORDER = ["date", "time", "tz", "authors", "with", "kind", "project", "subproject", "also", "apparatus", "title", "tags",
         "attendees", "runs", "parameters", "order", "items", "valid_until", "corrects", "redacts", "level", "related", "resolves", "priority",
         "figures", "data", "attachments", "epics", "refs", "backfilled", "migrated_from", "logged", "reviewed", "release"]


class NewError(RuntimeError):
    pass


@dataclass
class Options:
    handle: str | None = None
    date: str | None = None
    time: str | None = None
    coauthors: list[str] = field(default_factory=list)
    interactive: bool = False
    confirm_export_control: bool = False
    submit: bool = True             # connected: push and open the pull request
    dry_run: bool = False
    today: str | None = None


def read_draft(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end < 0:
            raise NewError(f"{path}: the header is not closed by a '---' line")
        return load_yaml(text[4:end + 1]) or {}, text[end + 5:]
    return {}, text


class _Dumper(yaml.SafeDumper):
    """Writes dates as plain 2026-10-13 (the log book reads them back as strings)."""


_Dumper.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeDumper.yaml_implicit_resolvers.copy().items()
}


def _str(d, s):
    style = '"' if re.fullmatch(r"\d{2}:\d{2}", s) else None   # a time stays a string
    return d.represent_scalar("tag:yaml.org,2002:str", s, style=style)


_Dumper.add_representer(str, _str)

FLOW_MAX = 90   # a mapping or list of plain values this short stays on one line


def _short(data) -> bool:
    values = data.values() if isinstance(data, dict) else data
    if any(isinstance(v, (dict, list)) for v in values):
        return False
    one_line = yaml.dump(data, Dumper=yaml.SafeDumper, default_flow_style=True, width=10_000, allow_unicode=True)
    return len(one_line.strip()) <= FLOW_MAX


def _map(d, data):
    return d.represent_mapping("tag:yaml.org,2002:map", data.items(), flow_style=_short(data))


def _seq(d, data):
    return d.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=_short(data))


_Dumper.add_representer(dict, _map)
_Dumper.add_representer(list, _seq)


def dump_entry(header: dict, body: str) -> str:
    h = {k: header[k] for k in ORDER if k in header and header[k] not in (None, [], {}, "")}
    h.update({k: v for k, v in header.items() if k not in h and v not in (None, [], {}, "")})
    y = yaml.dump(h, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=10_000)
    return f"---\n{y}---\n\n{body.strip()}\n"


def _slug_handle(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", h.lower()) or "x"


def _copy(src: Path, dest: Path) -> None:
    if dest.exists():
        if filecmp.cmp(src, dest, shallow=False):
            return
        raise NewError(f"{dest.name} already exists with other content: give the new file a new name (a figure: the next version)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def place_files(book: Book, header: dict, body: str, base: Path, year: str) -> str:
    """Copy the files the header names next to the entry; rewrite their paths. Returns the body
    with image paths rewritten too."""
    folder = book.entries_dir / year
    moved = {}
    for section, sub in SECTION_DIR.items():
        for item in header.get(section) or []:
            if not isinstance(item, dict) or not item.get("file"):
                continue
            src = Path(item["file"]).expanduser()
            if not src.is_absolute():
                in_book = (folder / src)
                src = in_book if in_book.exists() and in_book.resolve().is_relative_to(book.entries_dir.resolve()) else (base / src)
            src = src.resolve()
            if not src.exists():
                raise NewError(f"{section}: file not found: {item['file']}")
            if src.is_relative_to(folder.resolve()):
                rel = src.relative_to(folder.resolve()).as_posix()      # already in place
            else:
                rel = f"{sub}/{src.name}"
                _copy(src, folder / rel)
                if section == "figures":   # the figure's siblings: PDF, SVG, PNG, labfig record
                    for ext in (".pdf", ".svg", ".png", ".yaml"):
                        sib = src.with_suffix(ext)
                        if sib.exists() and sib != src:
                            _copy(sib, folder / sub / sib.name)
            moved[item["file"]] = rel
            item["file"] = rel
    for old, new in moved.items():
        body = body.replace(f"]({old})", f"]({new})")
    return body


def build(book: Book, header: dict, body: str, base: Path, opts: Options) -> tuple[Path, dict, str]:
    """Write the entry into `book`. Returns (path, header, body)."""
    now = book.now()
    today = opts.today or now.date().isoformat()
    h = dict(header)
    handle = opts.handle or connect.user_handle(book)
    if not handle:
        raise NewError("who is writing? set `handle:` in ~/.config/logbook/config.yaml, or pass --as <handle>")
    if book.people is not None and handle not in book.people:
        raise NewError(f"'{handle}' is not in the log book's people.yaml")
    h["date"] = str(opts.date or h.get("date") or today)
    h["time"] = str(opts.time or h.get("time") or now.strftime("%H:%M"))
    authors = [handle] + [a for a in list(h.get("authors") or []) + opts.coauthors if a != handle]
    h["authors"] = list(dict.fromkeys(authors))
    for req in ("title", "project"):
        if not h.get(req):
            raise NewError(f"the draft needs a {req}")
    h.setdefault("kind", "note")
    if (dt.date.fromisoformat(today) - dt.date.fromisoformat(h["date"])).days > book.config["late_days"] and not h.get("backfilled"):
        h["backfilled"] = today
    hhmm = h["time"].replace(":", "")
    eid = new_id(h["date"], hhmm, _slug_handle(handle), h["title"])
    year = h["date"][:4]
    path = book.entries_dir / year / f"{eid}.md"
    while path.exists():   # two entries in the same minute: the next minute
        t = (dt.datetime.strptime(hhmm, "%H%M") + dt.timedelta(minutes=1)).strftime("%H%M")
        hhmm, h["time"] = t, f"{t[:2]}:{t[2:]}"
        eid = new_id(h["date"], hhmm, _slug_handle(handle), h["title"])
        path = book.entries_dir / year / f"{eid}.md"
    body = place_files(book, h, body, base, year)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_entry(h, body), encoding="utf-8")
    return path, h, body


def _ask(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def review(book: Book, path: Path, header: dict, body: str, opts: Options) -> check.Report:
    """Check the new entry; ask about co-authors and export control when interactive."""
    for _ in range(2):   # a second pass after answers changed the header
        b = open_book(book.root)
        report = check.run(b, check.Options(paths=[path], today=opts.today))
        changed = False
        for f in report.findings:
            if f.code == "coauthors" and opts.interactive and book.people is not None:
                for h in re.findall(r"\((\w+)\)", f.message):
                    if h not in header["authors"] and _ask(f"Add {book.people[h].name if h in book.people else h} as a co-author?"):
                        header["authors"].append(h)
                        changed = True
            if f.level == "hold":
                fname = f.message.split(":")[0]
                ok = opts.confirm_export_control or (opts.interactive and _ask(
                    f"{fname}: is it free of export-controlled technical data? If in doubt answer no, "
                    "and link the file where it lives (restricted sharing) instead of attaching it."))
                if ok:
                    for section in ("figures", "attachments"):
                        for item in header.get(section) or []:
                            if item.get("file") == fname:
                                item["export_control_confirmed"] = True
                                changed = True
        if not changed:
            return report
        path.write_text(dump_entry(header, body), encoding="utf-8")
    return check.run(open_book(book.root), check.Options(paths=[path], today=opts.today))


def create(t: connect.Target, header: dict, body: str, base: Path, opts: Options, out=sys.stdout) -> int:
    if t.connected and not header.get("project") and t.central.get("project"):
        header = {**header, "project": t.central["project"]}   # the repository's default project
    if not t.connected:
        path, h, body = build(t.book, header, body, base, opts)
        report = review(t.book, path, h, body, opts)
        print(report.render(), file=out)
        print(f"written: {t.book.rel(path)}", file=out)
        if report.exit_code and opts.dry_run:
            path.unlink()
        return report.exit_code

    clone = t.book.root
    connect.run(["git", "-C", str(clone), "fetch", "-q", "origin", "main"])
    tmp = Path(tempfile.mkdtemp(prefix="logbook-entry-"))
    work = tmp / "book"
    branch = None
    try:
        connect.run(["git", "-C", str(clone), "worktree", "add", "-q", "--detach", str(work), "origin/main"])
        book = open_book(work)
        path, h, body = build(book, header, body, base, opts)
        report = review(book, path, h, body, opts)
        print(report.render(), file=out)
        if report.exit_code:
            print("not submitted: fix the draft (see above) and run `logbook new` again", file=out)
            return report.exit_code
        eid = path.stem
        if opts.dry_run or not opts.submit:
            print(f"checked, not submitted (dry run): {eid}", file=out)
            return 0
        branch = f"entry/{h['authors'][0]}/{eid}"
        connect.run(["git", "-C", str(work), "switch", "-q", "-c", branch])
        connect.run(["git", "-C", str(work), "add", "-A", str(book.entries_dir)])
        connect.run(["git", "-C", str(work), "commit", "-q", "-m", f"Entry: {h['title']}\n\n{eid}"])
        connect.run(["git", "-C", str(work), "push", "-q", "-u", "origin", branch])
        repo = t.central.get("repository")
        if shutil.which("gh") and repo:
            url = connect.run(["gh", "pr", "create", "--repo", repo, "--head", branch, "--base", "main",
                               "--title", f"Entry: {h['title']}",
                               "--body", f"New log-book entry `{eid}`, submitted with `logbook new`."]).strip()
            connect.run(["gh", "pr", "merge", "--repo", repo, "--auto", "--squash", url], check=False)
            print(f"submitted: {url} (merges itself when the checks pass)", file=out)
        else:
            print(f"pushed {branch}; open a pull request for it on GitHub", file=out)
        return 0
    finally:
        connect.run(["git", "-C", str(clone), "worktree", "remove", "--force", str(work)], check=False)
        if branch:
            connect.run(["git", "-C", str(clone), "branch", "-D", branch], check=False)
        shutil.rmtree(tmp, ignore_errors=True)
