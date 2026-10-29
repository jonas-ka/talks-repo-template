"""`logbook migrate <log book>.typ`: a Typst log book (`#day`/`#note`, older `#entry`) becomes
Markdown entries.

- One entry per `#note` (date from its `#day`; the day's title is dropped, days are computed)
  and one per old `#entry`.
- Callouts (`#decision`, `#finding`, `#issue`, `#todo`, `#context-box`) become fenced divs;
  `#refs((…))` the `refs` header field; `#figure(image("…"), caption: […])` a `figures` item with
  the file copied next to the entry (named `-v1` when it has no version; an SVG and a PNG are made
  from a PDF-only figure when PyMuPDF is available, else the entry says the SVG is missing);
  everything else goes through pandoc's Typst reader.
- The authors line becomes handles (people.yaml names, or `--author NAME=handle`); "with
  assistance from Claude" becomes `with: claude`; "(backfilled …)" is kept.
- **Git history gives the logged-at time:** the first commit that added the note's title
  (`git log -S`) is recorded as `logged` and `migrated_from: <repo>@<commit>`; a note logged more
  than the allowed days after its date gets `backfilled:`.
- `= Project background` becomes the wiki page `wiki/projects/<slug>.md`.

Nothing is committed: the result is reviewed (and checked) before it goes into a log book.
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .book import Book
from .entry import slugify
from .newentry import dump_entry

CALLOUTS = {"decision": "decision", "finding": "finding", "issue": "issue", "todo": "todo", "context-box": "context"}


class MigrateError(RuntimeError):
    pass


# ------------------------------------------------------------------------------ Typst scanning --
@dataclass
class Call:
    name: str
    start: int          # index of '#'
    end: int            # index after the last ']' or ')'
    args: str | None    # text inside (...)
    bodies: list[str]   # texts inside each [...]
    body_starts: list[int]


def _skip_string(s: str, i: int) -> int:
    i += 1
    while i < len(s) and s[i] != '"':
        i += 2 if s[i] == "\\" else 1
    return i + 1


def _skip_raw(s: str, i: int) -> int:
    n = len(re.match(r"`+", s[i:]).group(0))
    j = s.find("`" * n, i + n)
    return len(s) if j < 0 else j + n


def _match_args(s: str, i: int) -> int:
    """s[i] == '(' → index after the matching ')' (code mode: strings, nested (), [content])."""
    depth = 0
    while i < len(s):
        c = s[i]
        if c == '"':
            i = _skip_string(s, i)
            continue
        if c == "[":
            i = _match_content(s, i)
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        elif s.startswith("//", i):
            i = s.find("\n", i)
            i = len(s) if i < 0 else i
            continue
        i += 1
    raise MigrateError("unbalanced parentheses")


def _match_content(s: str, i: int) -> int:
    """s[i] == '[' → index after the matching ']' (markup: raw, escapes, comments, nested calls)."""
    depth = 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "`":
            i = _skip_raw(s, i)
            continue
        if s.startswith("//", i) and (i == 0 or s[i - 1] != ":"):
            j = s.find("\n", i)
            i = len(s) if j < 0 else j
            continue
        if s.startswith("/*", i):
            j = s.find("*/", i)
            i = len(s) if j < 0 else j + 2
            continue
        if c == "#":
            m = re.match(r"#[A-Za-z_][\w.-]*", s[i:])
            if m and i + m.end() < len(s) and s[i + m.end()] == "(":
                i = _match_args(s, i + m.end())
                continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise MigrateError("unbalanced brackets")


def calls(s: str, names: set[str] | None = None) -> list[Call]:
    """Top-level calls `#name(args)[body]…` in markup `s` (not inside other calls' content)."""
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "`":
            i = _skip_raw(s, i)
            continue
        if s.startswith("//", i) and (i == 0 or s[i - 1] != ":"):
            j = s.find("\n", i)
            i = len(s) if j < 0 else j
            continue
        if c == "#":
            m = re.match(r"#([A-Za-z_][\w.-]*)", s[i:])
            if m:
                name, j = m.group(1), i + m.end()
                args = None
                if j < len(s) and s[j] == "(":
                    k = _match_args(s, j)
                    args, j = s[j + 1:k - 1], k
                bodies, starts = [], []
                while j < len(s) and s[j] == "[":
                    k = _match_content(s, j)
                    bodies.append(s[j + 1:k - 1])
                    starts.append(j + 1)
                    j = k
                if names is None or name in names:
                    out.append(Call(name, i, j, args, bodies, starts))
                i = max(j, i + 1)
                continue
        i += 1
    return out


def strings(args: str) -> list[str]:
    """The positional string literals of an argument list, in order."""
    out, i = [], 0
    depth = 0
    while i < len(args):
        c = args[i]
        if c == '"' and depth == 0:
            j = _skip_string(args, i)
            out.append(bytes(args[i + 1:j - 1], "utf-8").decode("unicode_escape") if "\\" in args[i + 1:j - 1] else args[i + 1:j - 1])
            i = j
            continue
        if c in "([":
            k = _match_args(args, i) if c == "(" else _match_content(args, i)
            i = k
            continue
        if re.match(r"\w+\s*:", args[i:]) and depth == 0:   # a named argument: skip it
            m = re.match(r"\w+\s*:\s*", args[i:])
            i += m.end()
            j = i
            if j < len(args) and args[j] in "([":
                i = _match_args(args, j) if args[j] == "(" else _match_content(args, j)
            elif j < len(args) and args[j] == '"':
                i = _skip_string(args, j)
            else:
                while i < len(args) and args[i] != ",":
                    i += 1
            continue
        i += 1
    return out


def named(args: str, key: str) -> str | None:
    """The raw text of a named argument `key: …` (without brackets for content/arrays)."""
    m = re.search(rf"(?<![\w-]){re.escape(key)}\s*:\s*", args or "")
    if not m:
        return None
    j = m.end()
    if j < len(args) and args[j] == "[":
        k = _match_content(args, j)
        return args[j + 1:k - 1]
    if j < len(args) and args[j] == "(":
        k = _match_args(args, j)
        return args[j + 1:k - 1]
    if j < len(args) and args[j] == '"':
        k = _skip_string(args, j)
        return args[j + 1:k - 1]
    e = re.match(r"[^,)]*", args[j:]).group(0)
    return e.strip()


# ------------------------------------------------------------------------------ conversion ------
def _pandoc(typst: str) -> subprocess.CompletedProcess:
    return subprocess.run(["pandoc", "-f", "typst", "-t", "markdown-smart-simple_tables-multiline_tables-grid_tables-raw_attribute",
                           "--wrap=none"], input=typst, capture_output=True, text=True)


def pandoc_md(typst: str) -> str:
    """Typst markup → Markdown. Typst lets `_` and `*` stand inside words (HV_Drift, M2_2–M2_6);
    pandoc's reader takes them for emphasis, so a failed block is retried with those escaped, and
    as a last resort kept as plain text (nothing is dropped)."""
    if not typst.strip():
        return ""
    r = _pandoc(typst)
    if r.returncode:
        r = _pandoc(re.sub(r"(?<=[\w)])([_*])(?=[\w(])", r"\\\1", typst))
    if r.returncode:
        plain = re.sub(r"([\\`*_{}\[\]<>#|])", r"\\\1", typst.strip())
        return plain
    return r.stdout.strip()


@dataclass
class Body:
    md: str
    refs: dict = field(default_factory=dict)      # plain text, for an entry's header
    figures: list = field(default_factory=list)   # (path as written, caption md)
    refs_md: dict = field(default_factory=dict)   # the same as Markdown, for a wiki page


def convert(content: str, base: Path) -> Body:
    """Typst markup of one note/entry → Markdown, with callouts, refs and figures taken out."""
    found = calls(content, set(CALLOUTS) | {"refs", "figure"})
    out, refs, refs_md, figs, pos = [], {}, {}, [], 0
    for c in found:
        out.append(pandoc_md(content[pos:c.start]))
        pos = c.end
        if c.name in CALLOUTS:
            inner = convert(c.bodies[0] if c.bodies else "", base)
            refs.update(inner.refs)
            refs_md.update(inner.refs_md)
            figs += inner.figures
            out.append(f"::: {CALLOUTS[c.name]}\n{inner.md}\n:::")
        elif c.name == "refs":
            refs.update(parse_refs(c.args or ""))
            refs_md.update(parse_refs(c.args or "", markdown=True))
        elif c.name == "figure":
            m = re.search(r'\bimage\(\s*"([^"]+)"', c.args or "")   # code mode: image(...) without '#'
            path = m.group(1) if m else None
            cap = named(c.args or "", "caption") or ""
            if path:
                figs.append((path, pandoc_md(cap).replace("\n", " ")))
                out.append(f"![{pandoc_md(cap).replace(chr(10), ' ')}]({path})")
            else:   # a figure without an image (a table, say): pandoc converts the whole of it
                out.append(pandoc_md(content[c.start:c.end]))
    out.append(pandoc_md(content[pos:]))
    md = "\n\n".join(x for x in out if x.strip())
    return Body(re.sub(r"\n{3,}", "\n\n", md), refs, figs, refs_md)


def parse_refs(args: str, markdown: bool = False) -> dict:
    """`#refs(("Label": [content] or raw("…") or "…", …))` → {label: text}: plain text for an
    entry's `refs` header, or Markdown (code kept as code, links as links) for a wiki page."""
    inner = args.strip()
    if inner.startswith("(") and inner.endswith(")"):
        inner = inner[1:-1]
    out, i = {}, 0
    while i < len(inner):
        m = re.compile(r'\s*,?\s*"((?:[^"\\]|\\.)*)"\s*:\s*').match(inner, i)
        if not m:
            break
        key, j = m.group(1), m.end()
        if j < len(inner) and inner[j] == "[":
            k = _match_content(inner, j)
            val = pandoc_md(inner[j + 1:k - 1]).replace("\n", " ")
        elif inner.startswith("raw(", j):
            k = _match_args(inner, j + 3)
            val = (strings(inner[j + 4:k - 1]) or [""])[0]
            val = f"`{val}`" if markdown else val
        elif j < len(inner) and inner[j] == '"':
            k = _skip_string(inner, j)
            val = inner[j + 1:k - 1]
        elif inner.startswith("link(", j):   # link("url")[text] -> "text (url)"
            k = _match_args(inner, j + 4)
            url = (strings(inner[j + 5:k - 1]) or [""])[0]
            text = ""
            if k < len(inner) and inner[k] == "[":
                e = _match_content(inner, k)
                text, k = pandoc_md(inner[k + 1:e - 1]).replace("\n", " ").strip(), e
            if markdown:
                val = f"[{text}]({url})" if text and text != url else f"<{url}>"
            else:
                val = f"{text} ({url})" if text and text != url else url
        else:
            k = j
            while k < len(inner) and inner[k] != ",":
                k += 1
            val = inner[j:k].strip()
        out[key] = val.strip() if markdown else _plain_ref(val)
        i = k
    return out


def _plain_ref(md: str) -> str:
    """A reference as plain text: code marks and emphasis removed, but what is inside code
    (file names like `test_scaling.py`, `stage-*.csv`) kept as it is."""
    parts = re.split(r"(`[^`]*`)", md)
    return "".join(p[1:-1] if p.startswith("`") and p.endswith("`") else re.sub(r"(?<!\w)[*_]+|[*_]+(?!\w)", "", p)
                   for p in parts).replace("\\", "").strip()


# ------------------------------------------------------------------------------ authors, history --
def authors_of(text: str, book: Book, mapping: dict[str, str]) -> tuple[list[str], bool, str | None, list[str]]:
    """(handles, with_claude, backfilled date, unknown names) from an authors line."""
    plain = re.sub(r"[#*_\[\]]", "", text or "")
    with_claude = bool(re.search(r"assistance from Claude", plain, re.I))
    bf = re.search(r"backfilled\s+(\d{4}-\d{2}-\d{2})", plain)
    plain = re.sub(r"\([^)]*\)", "", plain)
    # names start with a capital; notes such as "table drafted with Claude" are not names
    names = [n.strip() for n in re.split(r",|\band\b|;", plain)
             if n.strip() and n.strip()[0].isupper() and "claude" not in n.lower()]
    handles, unknown = [], []
    people = book.people or {}
    for n in names:
        h = mapping.get(n)
        if not h:
            for p in people.values():
                if p.name == n or (n.split()[-1] == p.name.split()[-1] and n[0] == p.name[0]):
                    h = p.handle
                    break
        if not h and book.people is None:
            h = n
        if h:
            handles.append(h)
        else:
            unknown.append(n)
    return list(dict.fromkeys(handles)), with_claude, bf.group(1) if bf else None, unknown


def first_commit(repo: Path, path: Path, needle: str) -> tuple[str, str] | None:
    """(sha, committer date ISO) of the oldest commit that added `needle` to the file."""
    r = subprocess.run(["git", "-C", str(repo), "log", "--reverse", "--format=%H %cI", "-S", needle, "--", str(path)],
                       capture_output=True, text=True)
    line = r.stdout.strip().splitlines()[:1]
    return tuple(line[0].split(" ", 1)) if line else None


# ------------------------------------------------------------------------------ the migration --
@dataclass
class Report:
    entries: list[Path] = field(default_factory=list)
    background: Path | None = None
    unknown_authors: set = field(default_factory=set)
    alt_from_caption: int = 0
    svg_missing: list = field(default_factory=list)
    no_history: int = 0
    missing_files: list = field(default_factory=list)
    unresolved_refs: list = field(default_factory=list)
    existing: int = 0                                   # new_only: entries the book had already
    changed: list = field(default_factory=list)         # new_only: of those, the ones whose text differs

    def render(self, book: Book) -> str:
        lines = [f"migrated {len(self.entries)} entries into {book.rel(book.entries_dir)}/"]
        if self.existing:
            lines.append(f"{self.existing} entr(ies) already in the book, left as they are")
        if self.changed:
            lines.append("CHANGED SINCE THE EARLIER MIGRATION (entries are never rewritten: write a correction if it "
                         "matters): " + ", ".join(self.changed))
        if self.background:
            lines.append(f"project background: {book.rel(self.background)}")
        if self.unresolved_refs:
            lines.append(f"REFERENCES TO LABELS NOT FOUND (left as text): {', '.join(sorted(set(self.unresolved_refs)))}")
        if self.unknown_authors:
            lines.append(f"UNKNOWN AUTHORS (add to people.yaml or pass --author NAME=handle): {', '.join(sorted(self.unknown_authors))}")
        if self.alt_from_caption:
            lines.append(f"{self.alt_from_caption} figure(s) had no alt text: the caption was used; review them")
        if self.svg_missing:
            lines.append(f"{len(self.svg_missing)} figure(s) without an SVG (install PyMuPDF to make them): {', '.join(self.svg_missing[:5])}")
        if self.missing_files:
            lines.append(f"FIGURE FILES NOT FOUND (the entries show them as broken links): {', '.join(self.missing_files)}")
        if self.no_history:
            lines.append(f"{self.no_history} entr(ies) not found in git history: logged-at time missing")
        lines.append("Nothing is committed. Review the entries, run `logbook check`, then submit them in one pull request.")
        return "\n".join(lines)


def _slug(s: str) -> str:
    return slugify(s)


def _figure_files(src: Path, dest_dir: Path, report: Report) -> str:
    """Copy a figure (adding -v1 to unversioned names, making SVG/PNG from a PDF); its new name."""
    stem = src.stem if re.search(r"-v\d+$", src.stem) else f"{src.stem}-v1"
    dest_dir.mkdir(parents=True, exist_ok=True)
    main = dest_dir / f"{stem}{src.suffix.lower()}"
    if not main.exists():
        shutil.copy2(src, main)
    for ext in (".svg", ".png", ".pdf"):
        sib = src.with_suffix(ext)
        if sib.exists() and not (dest_dir / f"{stem}{ext}").exists():
            shutil.copy2(sib, dest_dir / f"{stem}{ext}")
    if src.suffix.lower() == ".pdf" and not (dest_dir / f"{stem}.svg").exists():
        try:
            import pymupdf   # optional: uv run --with pymupdf …
            doc = pymupdf.open(src)
            (dest_dir / f"{stem}.svg").write_text(doc[0].get_svg_image(text_as_path=True), encoding="utf-8")
            if not (dest_dir / f"{stem}.png").exists():
                doc[0].get_pixmap(dpi=300).save(dest_dir / f"{stem}.png")
        except ImportError:
            report.svg_missing.append(src.name)
    return main.name


# The title of the last #day a frozen Typst log book gets ("moved to …"); never migrated.
FROZEN_DAY = "This log book has moved"


def repo_name_of(repo: Path) -> str:
    """The repository's name: from its `origin` remote (a clone in another folder keeps it), else its folder."""
    url = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"],
                         capture_output=True, text=True).stdout.strip()
    name = re.sub(r"\.git$", "", url.rstrip("/")).rsplit("/", 1)[-1].rsplit(":", 1)[-1] if url else ""
    return name or repo.name


def _body(text: str) -> str:
    """An entry file's text without its header."""
    return text.split("\n---\n", 1)[-1].strip() if text.startswith("---") else text.strip()


def migrate(source: Path, book: Book, project: str | None = None, mapping: dict[str, str] | None = None,
            default_kind: str = "note", confirm_export_control: bool = False, new_only: bool = False) -> Report:
    """`new_only`: only the entries the book does not have yet (a carry-over after an earlier migration
    of the same log book); an entry that exists is left alone, and reported when its text differs."""
    source = source.resolve()
    text = source.read_text(encoding="utf-8")
    repo = Path(subprocess.run(["git", "-C", str(source.parent), "rev-parse", "--show-toplevel"],
                               capture_output=True, text=True).stdout.strip() or source.parent)
    repo_name = repo_name_of(repo)
    mapping = mapping or {}
    report = Report()

    def resolve(path: str) -> Path:
        """A path as Typst reads it: `/…` from the project root (the repository), else from the file."""
        return repo / path.lstrip("/") if path.startswith("/") else source.parent / path
    # the project: --project, else the title block's `project:`; a #note's own project name
    # (a line of work inside the project) becomes the entry's subproject
    m = re.search(r'\bproject:\s*"([^"]+)"', text)
    proj = project or (m.group(1) if m else source.stem)

    # Typst labels (`<fig-source>` after a figure) and references to them (`@fig-source`): pandoc
    # would read a reference as a citation. Both become placeholders that survive pandoc; after
    # the migration a reference becomes a link to the entry or wiki page that holds the label.
    labels = list(dict.fromkeys(re.findall(r"(?<=[\])])[ \t]*<([A-Za-z][\w:.-]*)>", text)))
    for i, lab in enumerate(labels):
        text = re.sub(rf"(?<=[\])])([ \t]*)<{re.escape(lab)}>", f"\\1 LBDEF{i}LBDEF", text)
        text = re.sub(rf"@{re.escape(lab)}\b", f"LBREF{i}LBREF", text)
    where: dict[int, str] = {}           # label index -> "wiki:projects/x" or an entry id
    compare: list[tuple[Path, str]] = []  # new_only: (existing entry, what the migration would write now)
    written: list[Path] = []

    def take_labels(md: str, target: str) -> str:
        for k in re.findall(r"LBDEF(\d+)LBDEF", md):
            where[int(k)] = target
        return re.sub(r"\s*LBDEF\d+LBDEF", "", md)

    # the project background: from "= Project background" to the first entry or day
    top = calls(text, {"day", "entry"})
    bg = re.search(r"^=\s+Project background\s*$", text, re.M)
    if bg and new_only:   # a carry-over leaves the wiki page alone, but learns where its labels live
        b = convert(text[bg.end():(top[0].start if top else len(text))], source.parent)
        page = book.wiki_dir / "projects" / f"{_slug(proj)}.md"
        if page.with_name(f"{_slug(proj)}-migrated.md").exists():
            page = page.with_name(f"{_slug(proj)}-migrated.md")
        take_labels(b.md, "wiki:" + page.relative_to(book.wiki_dir).with_suffix("").as_posix())
    if bg and not new_only:
        end = top[0].start if top else len(text)
        b = convert(text[bg.end():end], source.parent)
        page = book.wiki_dir / "projects" / f"{_slug(proj)}.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        home = str(Path.home())
        refs = "".join(f"- **{k}:** {v.replace(home, '~')}\n" for k, v in b.refs_md.items())
        if refs and not re.search(r"^#+\s+Where things live\s*$", b.md, re.M):
            # a background's #refs table: kept as a list (the wiki has no header for it)
            refs = "\n## Where things live\n\n" + refs
        if page.exists():   # never overwrite a page: the background goes next to it, to be merged by hand
            page = page.with_name(f"{_slug(proj)}-migrated.md")
        md = take_labels(b.md, "wiki:" + page.relative_to(book.wiki_dir).with_suffix("").as_posix())
        for path, _cap in b.figures:   # images of the background go next to the wiki page
            src = resolve(path)
            if not src.exists():
                report.missing_files.append(path)
                continue
            newname = _figure_files(src, page.parent / "figures", report)
            md = md.replace(f"]({path})", f"](figures/{newname})")
        page.write_text(f"# {proj}\n\n*Project background, migrated from `{source.name}` ({repo_name}).*\n\n{md}\n{refs}", encoding="utf-8")
        report.background = page
        written.append(page)

    def days_and_entries(s: str):
        """Top-level #day and #entry calls, and #day calls nested in a day's body (a missing ']'
        in the source nests the next day inside the previous one; Typst tolerates that)."""
        for c in calls(s, {"day", "entry"}):
            yield c
            if c.name == "day" and c.bodies:
                yield from days_and_entries_nested(c.bodies[0])

    def days_and_entries_nested(s: str):
        for c in calls(s, {"day"}):
            yield c
            if c.bodies:
                yield from days_and_entries_nested(c.bodies[0])

    seq: dict[str, int] = {}
    for c in days_and_entries(text):
        args = c.args or ""
        s = strings(args)
        if c.name == "day":
            date = s[0] if s else None
            day_authors = named(args, "authors") or ""
            notes = calls(c.bodies[0] if c.bodies else "", {"note"})
            items = [(n, strings(n.args or ""), named(n.args or "", "authors") or day_authors, n.bodies[0] if n.bodies else "") for n in notes]
        else:
            date = s[0] if s else None
            items = [(c, s[1:], named(args, "authors") or "", c.bodies[0] if c.bodies else "")]
        if c.name == "day" and len(s) > 1 and s[1].strip().lower() == FROZEN_DAY.lower():
            continue   # the note that freezes a migrated log book is not an entry
        for n, ns, auth, body_text in items:
            if c.name == "day":
                sub, title = (ns[0], ns[1]) if len(ns) >= 2 else (None, ns[0] if ns else "")
            else:
                sub, title = None, (ns[0] if ns else "")
            tags = strings(named(n.args or "", "tags") or "")
            handles, with_claude, bf, unknown = authors_of(auth, book, mapping)
            report.unknown_authors.update(unknown)
            if not handles:
                handles = [next(iter(book.people)) if book.people else "unknown"]
            b = convert(body_text, source.parent)
            hist = first_commit(repo, source, title) if title else None
            header = {"date": date, "authors": handles, "kind": default_kind, "project": proj, "title": title}
            if sub and sub != proj:
                header["subproject"] = sub
            if with_claude:
                header["with"] = "claude"
            if tags:
                header["tags"] = tags
            if b.refs:
                header["refs"] = b.refs
            if hist:
                sha, when = hist
                header["logged"] = when
                header["migrated_from"] = f"{repo_name}@{sha[:12]}"
                late = (dt.date.fromisoformat(when[:10]) - dt.date.fromisoformat(date)).days
                if late > book.config["late_days"]:
                    header["backfilled"] = bf or when[:10]
                elif late == 0:
                    header["time"] = dt.datetime.fromisoformat(when).strftime("%H:%M")
            else:   # not found in git history: logged now, by the migration
                report.no_history += 1
                today = book.now().date()
                if bf:
                    header["backfilled"] = bf
                elif (today - dt.date.fromisoformat(date)).days > book.config["late_days"]:
                    header["backfilled"] = today.isoformat()
            year = date[:4]
            folder = book.entries_dir / year
            md = b.md
            figs = []
            for path, cap in b.figures:
                src = resolve(path)
                if not src.exists():
                    report.missing_files.append(path)
                    continue
                newname = _figure_files(src, folder / "figures", report)
                kind = "plot" if src.suffix.lower() in (".pdf", ".svg") else "screenshot"
                item = {"file": f"figures/{newname}", "caption": cap or newname,
                        "alt": f"Figure: {cap}" if len(cap) >= 4 else f"Figure {newname}"}
                if kind != "plot":
                    item["kind"] = kind
                    if confirm_export_control:
                        item["export_control_confirmed"] = True
                report.alt_from_caption += 1
                figs.append(item)
                md = md.replace(f"]({path})", f"](figures/{newname})")
            if figs:
                header["figures"] = figs
            hhmm = header.get("time", "").replace(":", "")
            if not hhmm:
                seq[date] = seq.get(date, -1) + 1
                hhmm = f"{seq[date]:04d}"
            eid = f"{date}-{hhmm}-{re.sub(r'[^a-z0-9]', '', handles[0].lower())}-{_slug(title)}"
            path = folder / f"{eid}.md"
            if new_only and path.exists():   # migrated before: keep it; compared at the end, once labels are known
                report.existing += 1
                compare.append((path, take_labels(md, path.stem)))
                continue
            k = 1
            while path.exists():
                path = folder / f"{eid}-{k}.md"
                k += 1
            folder.mkdir(parents=True, exist_ok=True)
            md = take_labels(md, path.stem)
            path.write_text(dump_entry(header, md), encoding="utf-8")
            report.entries.append(path)
            written.append(path)

    def link(i: int, here: str) -> str:
        if i not in where:
            report.unresolved_refs.append(labels[i])
            return f"figure `{labels[i]}` (in the original log book)"
        return "the figure on this page" if where[i] == here else f"the figure on [[{where[i]}]]"

    for path, md in compare:   # new_only: did the source change an entry migrated before?
        now = re.sub(r"LBREF(\d+)LBREF", lambda m: link(int(m.group(1)), path.stem), md)
        if _body(path.read_text(encoding="utf-8")) != now.strip():
            report.changed.append(book.rel(path))

    for f in written:   # references, now that every label's place is known
        s = f.read_text(encoding="utf-8")
        here = ("wiki:" + f.relative_to(book.wiki_dir).with_suffix("").as_posix()
                if f.is_relative_to(book.wiki_dir) else f.stem)
        if "LBREF" in s:
            f.write_text(re.sub(r"LBREF(\d+)LBREF", lambda m: link(int(m.group(1)), here), s), encoding="utf-8")
    return report
