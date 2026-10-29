"""The log book as an HTML view for daily use: search, filters, entries, open items, projects,
apparatus, people, wiki and references, all in one page (`data/view/`), with the book's data
embedded as JSON.

Two builds of the same page:
- a folder (`index.html` + `files/`), for a web server such as GitHub Pages;
- one self-contained file (figures embedded), for a project's copy or for opening from a clone.
"""

from __future__ import annotations

import base64
import datetime as dt
import html as htmlmod
import json
import os
import re
import shutil
from pathlib import Path

from . import __version__, orders, render
from .book import Book
from .entry import OPENABLE, Entry

VIEW = render.data_file("view")


def _plain(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S)
    text = re.sub(r'<div class="callout-label">.*?</div>', " ", text, flags=re.S)   # "Finding", "Decision", ...
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", htmlmod.unescape(text)).strip()


def _block_texts(e: Entry, bib: dict | None = None) -> dict[str, tuple[str, str]]:
    """anchor -> (block name, its text, plain) for blocks with an id, read from the Markdown."""
    out, lines = {}, e.body.splitlines()
    i = 0
    while i < len(lines):
        b = next((b for b in e.blocks if b.line == e.body_line + i), None)
        if b and b.anchor:
            j, chunk, depth = i + 1, [], 1
            while j < len(lines) and depth:
                if re.match(r"^:{3,}\s*$", lines[j]):
                    depth -= 1
                    if not depth:
                        break
                elif re.match(r"^:{3,}\s*\S", lines[j]):
                    depth += 1
                chunk.append(lines[j])
                j += 1
            text = " ".join(chunk)
            text = re.sub(r"\[(?:[^\[\]]*?)@([\w:.-]+)[^\[\]]*\]",
                          lambda m: render.bibmod.format_citation(bib[m.group(1)]) if bib and m.group(1) in bib else m.group(0), text)
            text = re.sub(r"[*_`]|\[\[([^\]|]+)(\|[^\]]*)?\]\]", lambda m: m.group(1) or "", text)
            out[b.anchor] = (b.name, re.sub(r"\s+", " ", text).strip(" -"))
        i += 1
    return out


def _site(book: Book) -> dict | None:
    s = book.config.get("site") or {}
    if not s.get("repository"):
        return None
    host = s.get("host", "https://github.com").rstrip("/")
    repo = s["repository"]
    return {"repo": f"{host}/{repo}", "branch": s.get("branch", "main"),
            "new_entry": s.get("new_entry", f"{host}/{repo}/issues/new?template=new-entry.yml"),
            "export": s.get("export", f"{host}/{repo}/actions/workflows/export.yml"),
            "entries": book.config["entries"], "wiki": book.config["wiki"]}


def book_data(book: Book, p: render.Prepared, bodies: dict, wiki_html: dict, refs_html: dict) -> dict:
    st = p.st
    today = book.now().date().isoformat()
    entries = []
    for e in p.entries:
        h = e.header
        body = bodies.get(e.id, "")
        blocks = _block_texts(e, p.bib)
        epics = []
        for snap in h.get("epics") or []:
            try:
                pvs = json.loads((e.folder / snap["file"]).read_text(encoding="utf-8")).get("pvs", [])
            except (OSError, ValueError):
                pvs = []
            epics.append({"group": snap["group"], "label": snap.get("label"), "file": snap["file"], "pvs": pvs})
        resolved, priority = {}, {}
        for b in e.blocks:
            if b.anchor and b.name in OPENABLE:
                resolved[b.anchor] = st.resolved_by.get(f"{e.id}#{b.anchor}", [])
                level, by = st.priority(book.entries, f"{e.id}#{b.anchor}")
                priority[b.anchor] = {"level": level, "by": by,
                                      "since": book.entries[by].date if by in book.entries else e.date}
        lg = p.logged.get(e.id)
        entries.append({
            "id": e.id, "date": e.date, "time": h.get("time"), "logged": p.logged_text(e),
            "pr": lg.pr if lg else None,
            "authors": e.authors, "with": h.get("with"), "kind": h.get("kind"),
            "project": h.get("project"), "subproject": h.get("subproject"), "also": h.get("also") or [],
            "apparatus": h.get("apparatus") or [], "title": h.get("title"), "tags": h.get("tags") or [],
            "runs": h.get("runs") or [], "parameters": h.get("parameters") or [], "attendees": h.get("attendees") or [],
            "valid_until": h.get("valid_until"), "backfilled": h.get("backfilled"), "release": h.get("release"),
            "migrated_from": h.get("migrated_from"),
            "html": body, "text": _plain(body),
            "figures": len(h.get("figures") or []),
            "epics": epics,
            "data": [{"file": d["file"], "source": d.get("source"), "url": f"@@FILE:{book.rel(e.folder / d['file'])}@@"}
                     for d in h.get("data") or []],
            "attachments": [{"file": a["file"], "description": a.get("description"),
                             "url": f"@@FILE:{book.rel(e.folder / a['file'])}@@"} for a in h.get("attachments") or []],
            "refs": h.get("refs") or {},
            "corrects": h.get("corrects"), "correctedBy": st.corrected_by.get(e.id, []),
            "redacts": h.get("redacts"), "redactedBy": st.redacted_by.get(e.id, []),
            "resolves": h.get("resolves") or [], "resolved": resolved, "priority": priority,
            "reprioritises": h.get("priority") if isinstance(h.get("priority"), dict) else {},
            "related": sorted(st.related.get(e.id, set())), "backlinks": sorted(st.backlinks.get(e.id, set())),
            "blocks": {a: {"name": n, "text": t} for a, (n, t) in blocks.items()},
            "cites": sorted({k for k, _ in e.citations()}),
            "path": book.rel(e.path),
        })
    cited = {}
    for x in entries:
        for k in x["cites"]:
            cited.setdefault(k, []).append(x["id"])
    refs = []
    for key, r in sorted(p.bib.items()):
        refs.append({"key": key, "cite": render.bibmod.format_citation(r), "doi": render.bibmod.doi_url(r),
                     "html": refs_html.get(key), "citedBy": cited.get(key, [])})
    wiki = []
    wiki_back = {}
    for e in p.entries:
        for t, _ in e.links():
            if t.startswith("wiki:"):
                wiki_back.setdefault(t[5:].strip().removesuffix(".md"), set()).add(e.id)
    for page in sorted(p.wiki):
        wiki.append({"page": page, "title": p.wiki_titles.get(page, page), "html": wiki_html.get(page, ""),
                     "text": _plain(wiki_html.get(page, "")), "backlinks": sorted(wiki_back.get(page, set()))})
    projects = []
    names = list(book.projects or {})
    for e in p.entries:
        for x in e.projects:
            if x not in names:
                names.append(x)
    for n in names:
        info = (book.projects or {}).get(n, {})
        subs = list(info.get("subprojects") or [])
        for e in p.entries:
            if e.header.get("project") == n and e.header.get("subproject") and e.header["subproject"] not in subs:
                subs.append(e.header["subproject"])
        projects.append({"name": n, "subprojects": subs, "wiki": info.get("wiki")})
    apparatus = [{"id": k, "name": v.get("name", k), "wiki": v.get("wiki")} for k, v in (book.apparatus or {}).items()]
    for e in p.entries:
        for a in e.header.get("apparatus") or []:
            if a not in {x["id"] for x in apparatus}:
                apparatus.append({"id": a, "name": a, "wiki": None})
    people = {h: {"name": p.name(h)} for e in p.entries for h in e.authors + list(e.header.get("attendees") or [])}
    shown = {e.id for e in p.entries}   # an export's view shows only its own orders
    logo, logo_wide = None, False
    if book.config.get("logo"):
        lp = (book.root / book.config["logo"]).resolve()
        if lp.exists():
            logo = _data_uri(lp)
            w, h = _image_size(lp)
            logo_wide = bool(w and h and w > 1.6 * h)
    return {"title": book.config.get("title", "Log book"), "logo": logo, "logo_wide": logo_wide, "generated": book.now().isoformat(timespec="minutes"),
            "orders": [r for r in orders.status(book, st) if r["entry"] in shown],
            "currency": (book.config.get("orders") or {}).get("currency", "$"),
            "today": today, "asapDays": book.config["open_items"]["asap_days"], "version": __version__, "site": _site(book), "people": people, "projects": projects,
            "apparatus": apparatus, "kinds": list(book.kinds), "entries": entries, "wiki": wiki, "references": refs}


def _render_parts(book: Book, p: render.Prepared):
    wiki = sorted(p.wiki)
    md = render.document(p, wiki)
    meta = {"doi": {k: render.bibmod.doi_url(r) for k, r in p.bib.items() if render.bibmod.doi_url(r)},
            "fig": {k: f.for_meta("") for k, f in p.figs.items()}, "wiki_in": wiki}
    out = render.pandoc(md, "html5", meta, book.bib_path if book.bib_path.exists() else None,
                        ["--mathml", "--metadata", "suppress-bibliography=true"])
    parts = render.split(out, ("<!--", "-->"))
    bodies = {k[1]: v for k, v in parts.items() if k[0] == "ENTRY"}
    wiki_html = {k[1]: v for k, v in parts.items() if k[0] == "WIKI"}
    refs_html = {}
    keys = sorted(p.bib)
    if keys:
        ref_out = render.reference_list(p, "html5", keys)
        for m in re.finditer(r'<div id="ref-([^"]+)" class="csl-entry"[^>]*>(.*?)</div>', ref_out, re.S):
            refs_html[m.group(1)] = m.group(2).strip()
    return bodies, wiki_html, refs_html


def _image_size(path: Path) -> tuple[float, float]:
    """Width and height of a PNG or SVG, (0, 0) when unknown: a wide logo is shown as a banner."""
    try:
        if path.suffix.lower() == ".png":
            head = path.read_bytes()[:24]
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return float(int.from_bytes(head[16:20], "big")), float(int.from_bytes(head[20:24], "big"))
        elif path.suffix.lower() == ".svg":
            import re
            text = path.read_text(encoding="utf-8", errors="replace")[:4000]
            m = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', text)
            if m:
                return float(m.group(1)), float(m.group(2))
    except (OSError, ValueError):
        pass
    return 0.0, 0.0


def _data_uri(path: Path) -> str:
    mime = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(path.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def build(book: Book, out: Path, single: bool = False, entries: list[Entry] | None = None) -> Path:
    p = render.prepare(book, entries)
    bodies, wiki_html, refs_html = _render_parts(book, p)
    data = book_data(book, p, bodies, wiki_html, refs_html)
    page = (VIEW / "index.html").read_text(encoding="utf-8")
    css = (VIEW / "view.css").read_text(encoding="utf-8")
    js = (VIEW / "view.js").read_text(encoding="utf-8")
    text = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = out.resolve()
    if single:
        out.parent.mkdir(parents=True, exist_ok=True)
        html_file, base = out, out.parent
    else:
        out.mkdir(parents=True, exist_ok=True)
        html_file, base = out / "index.html", out
        files = out / "files"
        if files.exists():
            shutil.rmtree(files)

    def fig_url(key: str, vector: bool = False) -> str:
        """The figure for the page: its SVG (else PNG). `vector`: the link a click opens
        (in the one-file build, the original next to the entry, not a second embedded copy)."""
        f = p.figs.get(key)
        if f is None:
            return ""
        src = f.svg or f.png or f.src
        if single:
            return os.path.relpath(src, base) if vector else _data_uri(src)
        dest = base / "files" / book.rel(src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return "files/" + book.rel(src)

    def file_url(rel: str) -> str:
        src = book.root / rel
        if single:
            return os.path.relpath(src, base)
        dest = base / "files" / rel
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        return "files/" + rel

    def png_url(key: str) -> str:
        """The PNG next to the SVG, for browsers that cannot draw SVG paths (the view tests this)."""
        f = p.figs.get(key)
        if f is None or not f.png or f.png == (f.svg or f.png):
            return ""
        if single:
            return os.path.relpath(f.png, base)   # the file next to the SVG; not embedded twice
        dest = base / "files" / book.rel(f.png)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f.png, dest)
        return "files/" + book.rel(f.png)

    text = re.sub(r"@@FIGPNG:(.+?)@@", lambda m: png_url(htmlmod.unescape(m.group(1))), text)
    text = re.sub(r"@@FIGVEC:(.+?)@@", lambda m: fig_url(htmlmod.unescape(m.group(1)), vector=True), text)
    text = re.sub(r"@@FIG:(.+?)@@", lambda m: fig_url(htmlmod.unescape(m.group(1))), text)
    text = re.sub(r"@@FILE:(.+?)@@", lambda m: file_url(m.group(1)), text)
    page = (page.replace("/*@@CSS@@*/", css).replace("/*@@JS@@*/", js)
                .replace("@@DATA@@", text).replace("@@TITLE@@", htmlmod.escape(data["title"])))
    html_file.write_text(page, encoding="utf-8")
    return html_file
