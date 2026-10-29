"""What the PDF and the HTML view share: the entries' Markdown prepared for pandoc, one pandoc run
per output format (with the lab's CSL style and the two Lua filters), and the results split back
into entries and wiki pages.

Prepared Markdown: every entry becomes a Div `.lb-entry`, every wiki page a Div `.lb-wiki`;
`[[links]]` become links to `logbook:entry/<id>#<block>` or `logbook:wiki/<page>`; block ids get
the entry id in front (`#<id>--<block>`), so they are unique in the whole book; figures become
Divs `.lb-fig` with a key into a table the filters read from the metadata.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from . import bib as bibmod
from . import gitutil, state
from .book import Book
from .entry import Entry, load_yaml

_FENCE_WORD_ATTR = re.compile(r"^(:{3,})\s*([A-Za-z][\w-]*)\s*\{([^}]*)\}\s*$")
_FENCE_WORD = re.compile(r"^(:{3,})\s*([A-Za-z][\w-]*)\s*$")
_FENCE_ATTR = re.compile(r"^(:{3,})\s*\{([^}]*)\}\s*$")
_WIKILINK = re.compile(r"\[\[([^\]|\n]+)(?:\|([^\]\n]*))?\]\]")
_IMAGE_LINE = re.compile(r'^\s*!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)\s*(\{[^}]*\})?\s*$')
_SVG_SIZE = re.compile(r'<svg[^>]*?\swidth="([\d.]+)(pt|px)?"[^>]*?\sheight="([\d.]+)(pt|px)?"', re.S)
_SVG_VIEWBOX = re.compile(r'<svg[^>]*?viewBox="[\d.\s-]*?\s([\d.]+)\s+([\d.]+)"', re.S)
_STRIP_MARK = re.compile(r"labfig info_strip_in=([0-9.]+)")


def data_file(name: str) -> Path:
    return Path(str(resources.files("lablogbook").joinpath(f"data/{name}")))


class RenderError(RuntimeError):
    pass


# ---------------------------------------------------------------------------- figures --------
@dataclass
class Fig:
    key: str
    src: Path              # the file the entry names (PDF normally)
    svg: Path | None
    png: Path | None
    caption: str
    alt: str
    strip_in: float        # labfig information strip to cut, inches at the file's size
    w: float = 4.0         # visible aspect ratio, from the SVG (or 3:2 when unknown)
    h_visible: float = 3.0
    label: str | None = None

    def for_meta(self, typst_path: str) -> dict:
        return {"typst_path": typst_path, "strip_in": f"{self.strip_in:g}", "alt": self.alt,
                "caption": self.caption, "w": f"{self.w:g}", "h_visible": f"{self.h_visible:g}",
                **({"label": self.label} if self.label else {})}


def strip_height(path: Path) -> float:
    """The labfig strip of a figure, in inches: from its record, else its SVG, else 0."""
    stem = path.with_suffix("")
    rec = stem.with_suffix(".yaml")
    if rec.exists():
        try:
            data = load_yaml(rec.read_text(encoding="utf-8")) or {}
            if data.get("info_strip_in") is not None:
                return float(data["info_strip_in"])
        except Exception:
            pass
    svg = stem.with_suffix(".svg")
    if svg.exists():
        m = _STRIP_MARK.search(svg.read_text(encoding="utf-8", errors="ignore")[:20000])
        if m:
            return float(m.group(1))
    return 0.0


def svg_size_pt(svg: Path) -> tuple[float, float] | None:
    head = svg.read_text(encoding="utf-8", errors="ignore")[:4000]
    m = _SVG_SIZE.search(head)
    if m:
        k = 0.75 if m.group(2) == "px" else 1.0
        return float(m.group(1)) * k, float(m.group(3)) * k
    m = _SVG_VIEWBOX.search(head)
    return (float(m.group(1)), float(m.group(2))) if m else None


def png_size(png: Path) -> tuple[int, int] | None:
    head = png.read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def plain(md: str) -> str:
    """Caption or alt text as plain text: Markdown's emphasis, code and link marks taken out
    (figures show their caption as text in both outputs)."""
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md or "")
    s = re.sub(r"(\*\*|__)(.+?)\1", r"\2", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    return re.sub(r"\\([\\`*_\[\]<>#])", r"\1", s)


def make_fig(key: str, src: Path, caption: str, alt: str, label: str | None = None) -> Fig:
    caption, alt = plain(caption), plain(alt)
    stem = src.with_suffix("")
    svg = src if src.suffix.lower() == ".svg" else (stem.with_suffix(".svg") if stem.with_suffix(".svg").exists() else None)
    png = src if src.suffix.lower() in (".png", ".jpg", ".jpeg") else (stem.with_suffix(".png") if stem.with_suffix(".png").exists() else None)
    strip = strip_height(src) if (svg or src.suffix.lower() == ".pdf") else 0.0
    f = Fig(key, src, svg, png, caption, alt, strip, label=label)
    size = svg_size_pt(svg) if svg else None
    if size:
        f.w, f.h_visible = size[0], max(size[1] - strip * 72, 1.0)
    px = png_size(png) if (png and png.suffix.lower() == ".png" and not size) else None
    if px:   # no SVG: the view shows the PNG, at its own aspect
        dpi = px[0] / (size[0] / 72) if size else 300.0
        f.w, f.h_visible = float(px[0]), max(px[1] - strip * dpi, 1.0)
    return f


# ---------------------------------------------------------------------------- the book -------
@dataclass
class Logged:
    when: str | None         # ISO time of the commit that added the entry (the merge, on main)
    sha: str | None
    pr: int | None           # pull request number from a squash-merge subject "(#123)"


@dataclass
class Prepared:
    book: Book
    entries: list[Entry]                         # chronological
    st: state.State
    logged: dict[str, Logged]
    names: dict[str, str]                        # handle -> display name
    titles: dict[str, str]                       # entry id -> title
    wiki: dict[str, Path]                        # page -> file (all pages)
    wiki_titles: dict[str, str]
    figs: dict[str, Fig] = field(default_factory=dict)
    bib: dict[str, bibmod.Record] = field(default_factory=dict)

    def name(self, handle: str) -> str:
        return self.names.get(handle, handle)

    def logged_text(self, e: Entry) -> str | None:
        if e.header.get("logged"):
            return str(e.header["logged"])
        lg = self.logged.get(e.id)
        return lg.when if lg else None


def logged_times(book: Book) -> dict[str, Logged]:
    top = gitutil.toplevel(book.root)
    if top is None or not book.entries_dir.exists():
        return {}
    try:
        out = gitutil._git(top, "log", "--diff-filter=A", "--format=%x00%cI%x00%H%x00%s", "--name-only",
                           "--", str(book.entries_dir))
    except gitutil.GitError:
        return {}
    res: dict[str, Logged] = {}
    when = sha = subj = None
    for line in out.splitlines():
        if line.startswith("\0"):
            _, when, sha, subj = line.split("\0", 3)
            continue
        if line.endswith(".md"):
            m = re.search(r"\(#(\d+)\)\s*$", subj or "")
            res[Path(line).stem] = Logged(when, sha, int(m.group(1)) if m else None)   # oldest wins (log is newest first)
    return res


_WIKI_HEAD = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n", re.S)


def wiki_split(text: str) -> tuple[dict, str, int]:
    """A wiki page's optional YAML header, its Markdown and the header's number of lines.

    Wiki pages need no header; one is read for `reviewed: [ferpa, health]` only (the checker's
    override after reading, as in entries)."""
    m = _WIKI_HEAD.match(text)
    if not m:
        return {}, text, 0
    try:
        meta = load_yaml(m.group(1)) or {}
    except Exception:   # noqa: BLE001 - a broken header is ignored like an absent one
        meta = {}
    return (meta if isinstance(meta, dict) else {}), text[m.end():], m.group(0).count("\n")


def wiki_text(path: Path) -> str:
    return wiki_split(path.read_text(encoding="utf-8"))[1]


def wiki_pages(book: Book) -> tuple[dict[str, Path], dict[str, str]]:
    pages, titles = {}, {}
    if book.wiki_dir.exists():
        for f in sorted(book.wiki_dir.rglob("*.md")):
            page = f.relative_to(book.wiki_dir).with_suffix("").as_posix()
            pages[page] = f
            m = re.search(r"^#\s+(.+)$", wiki_text(f), re.M)
            titles[page] = m.group(1).strip() if m else page
    return pages, titles


def prepare(book: Book, entries: list[Entry] | None = None) -> Prepared:
    chosen = sorted(entries if entries is not None else book.entries.values(),
                    key=lambda e: (e.date, str(e.header.get("time") or ""), e.id))
    names = {h: p.name for h, p in (book.people or {}).items()}
    pages, wtitles = wiki_pages(book)
    p = Prepared(book, chosen, state.compute(book.entries), logged_times(book), names,
                 {i: str(e.header.get("title", i)) for i, e in book.entries.items()}, pages, wtitles)
    if book.bib_path.exists():
        try:
            p.bib = {r.key: r for r in bibmod.parse(book.bib_path.read_text(encoding="utf-8"))}
        except bibmod.BibError:
            p.bib = {}
    return p


# ---------------------------------------------------------------------- Markdown for pandoc --
def _prefix_attrs(attrs: str, eid: str | None) -> str:
    if not eid:
        return attrs
    return re.sub(r"#([A-Za-z][\w-]*)", lambda m: f"#{eid}--{m.group(1)}", attrs)


def _link_text(p: Prepared, target: str) -> tuple[str, str]:
    """(logbook: url, default text) for a [[target]]."""
    if target.startswith("wiki:"):
        page = target[5:].strip().removesuffix(".md")
        return f"logbook:wiki/{page}", p.wiki_titles.get(page, page)
    eid, _, anchor = target.partition("#")
    title = p.titles.get(eid, eid)
    return f"logbook:entry/{eid}{'#' + anchor if anchor else ''}", title + (f" (#{anchor})" if anchor else "")


def _md_escape(s: str) -> str:
    return re.sub(r"([\\`*_\[\]<>#])", r"\\\1", s)


def prepare_markdown(p: Prepared, text: str, eid: str | None, base: Path, header_figs: list[dict] | None = None) -> str:
    """One entry's body (or a wiki page) ready for pandoc."""
    out, in_code = [], False
    used_fig_files = set()
    figs_by_file = {f["file"]: f for f in (header_figs or [])}
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
            out.append(line)
            continue
        if in_code:
            out.append(line)
            continue
        m = _FENCE_WORD_ATTR.match(line)
        if m:
            line = f"{m.group(1)} {{.{m.group(2)} {_prefix_attrs(m.group(3), eid)}}}"
        else:
            m = _FENCE_WORD.match(line)
            if m:
                line = f"{m.group(1)} {{.{m.group(2)}}}"
            else:
                m = _FENCE_ATTR.match(line)
                if m:
                    line = f"{m.group(1)} {{{_prefix_attrs(m.group(2), eid)}}}"
        im = _IMAGE_LINE.match(line)
        if im:
            rel = im.group(2)
            meta = figs_by_file.get(rel, {})
            key = f"{eid or 'wiki'}/{p.book.rel(base / rel)}"
            alt_m = re.search(r'alt="([^"]*)"', im.group(3) or "")
            p.figs[key] = make_fig(key, base / rel, meta.get("caption") or im.group(1),
                                   meta.get("alt") or (alt_m.group(1) if alt_m else im.group(1)))
            used_fig_files.add(rel)
            out += ["", f'::: {{.lb-fig key="{key}"}}', ":::", ""]
            continue
        # [[links]] outside inline code
        parts = re.split(r"(`[^`]*`)", line)
        for i in range(0, len(parts), 2):
            def repl(mm):
                url, text_ = _link_text(p, mm.group(1).strip())
                return f"[{_md_escape(mm.group(2).strip()) if mm.group(2) else _md_escape(text_)}]({url})"
            parts[i] = _WIKILINK.sub(repl, parts[i])
        out.append("".join(parts))
    for f in header_figs or []:
        if f["file"] in used_fig_files:
            continue
        key = f"{eid}/{p.book.rel(base / f['file'])}"
        p.figs[key] = make_fig(key, base / f["file"], f.get("caption", ""), f.get("alt", ""))
        out += ["", f'::: {{.lb-fig key="{key}"}}', ":::", ""]
    return "\n".join(out)


def document(p: Prepared, wiki: list[str]) -> str:
    """All entries and the chosen wiki pages as one Markdown document, in order."""
    chunks = []
    for page in wiki:
        f = p.wiki[page]
        body = prepare_markdown(p, wiki_text(f), None, f.parent)
        chunks.append(f'\n:::::: {{.lb-wiki data-id="{page}"}}\n\n{body}\n\n::::::\n')
    for e in p.entries:
        body = prepare_markdown(p, e.body, e.id, e.folder, e.header.get("figures") or [])
        chunks.append(f'\n:::::: {{.lb-entry data-id="{e.id}"}}\n\n{body}\n\n::::::\n')
    return "\n".join(chunks)


# --------------------------------------------------------------------------- pandoc ----------
def pandoc(markdown: str, to: str, meta: dict, bibliography: Path | None, extra: list[str] = ()) -> str:
    exe = shutil.which("pandoc")
    if not exe:
        raise RenderError("pandoc is needed to render the log book (https://pandoc.org; brew install pandoc)")
    with tempfile.TemporaryDirectory() as tmp:
        src, dfile = Path(tmp) / "in.md", Path(tmp) / "lb-data.json"
        src.write_text(markdown, encoding="utf-8")
        dfile.write_text(json.dumps(meta), encoding="utf-8")   # read by post.lua: strings stay literal
        cmd = [exe, str(src), "-f", "markdown+fenced_divs+tex_math_dollars-implicit_figures", "-t", to,
               "--wrap=preserve", "--lua-filter", str(data_file("pre.lua"))]
        if bibliography:
            cmd += ["--citeproc", "--bibliography", str(bibliography), "--csl", str(data_file("karthein-lab.csl"))]
        cmd += ["--lua-filter", str(data_file("post.lua")), *extra]
        import os
        r = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "LB_DATA": str(dfile)})
        if r.returncode:
            raise RenderError(f"pandoc failed: {r.stderr.strip()[:2000]}")
        return r.stdout


def split(output: str, comment: str) -> dict[tuple[str, str], str]:
    """Pandoc output cut at the markers the filter wrote: {(ENTRY|WIKI, id): text}."""
    pat = re.compile(rf"^{re.escape(comment[0])}@@(ENTRY|WIKI) (\S+?){re.escape(comment[1])}\s*$", re.M)
    res, last = {}, None
    pos = 0
    for m in pat.finditer(output):
        if last:
            res[last] = output[pos:m.start()].strip("\n")
        last, pos = (m.group(1), m.group(2)), m.end()
    if last:
        res[last] = output[pos:].strip("\n")
    return res


def used_keys(p: Prepared) -> list[str]:
    keys = []
    for e in p.entries:
        keys += [k for k, _ in e.citations()]
    for page in p.wiki:
        keys += [m for m in re.findall(r"@([A-Z][A-Za-z'-]+\d{4}[a-z]?)", wiki_text(p.wiki[page]))]
    return sorted({k for k in keys if k in p.bib})


def reference_list(p: Prepared, to: str, keys: list[str]) -> str:
    if not keys or not p.book.bib_path.exists():
        return ""
    md = "---\nnocite: |\n  " + ", ".join(f"@{k}" for k in keys) + "\n---\n"
    return pandoc(md, to, {}, p.book.bib_path)
