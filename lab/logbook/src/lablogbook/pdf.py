"""The log book (or a selection of it) as a PDF: one Typst document with the lab notebook
template (`notes/labnotes-template.typ`), compiled under PDF/UA-1.

Days are `#day`s, entries `#note`s, the callouts the template's; each entry and each block with
an id carries a label, so links in the PDF jump to them. The project pages of the wiki come
first, the references last.
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
from pathlib import Path

from . import render
from .book import Book
from .entry import Entry

PKG = Path(__file__).resolve()
LAB = PKG.parents[3]          # lab-templates (or a consumer's lab/): logbook/src/lablogbook/pdf.py
TEMPLATE = LAB / "notes" / "labnotes-template.typ"
STRIP = LAB / "themes" / "figure-strip.typ"


def ts(s) -> str:
    """A Typst string literal."""
    s = "" if s is None else str(s)
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def tc(s) -> str:
    """Text as Typst content: [#"..."]."""
    return f"[#{ts(s)}]"


def _label(eid: str, anchor: str | None = None) -> str:
    return f"e-{eid}" + (f"--{anchor}" if anchor else "")


def _link(p: render.Prepared, eid: str, anchor: str | None = None, text: str | None = None) -> str:
    t = text or p.titles.get(eid, eid) + (f" (#{anchor})" if anchor else "")
    if eid in {e.id for e in p.entries}:
        return f"#link(<{_label(eid, anchor)}>)[#{ts(t)}]"
    return f"#emph[#{ts(t)}]"   # not in this PDF (a selection)


def _fmt_logged(s: str | None) -> str:
    if not s:
        return "not yet logged"
    try:
        t = dt.datetime.fromisoformat(s)
        off = t.strftime("%z")   # +0000, -0500
        zone = "UTC" if off in ("", "+0000") else f"UTC{off[0]}{int(off[1:3])}" + (f":{off[3:]}" if off[3:] != "00" else "")
        return f"logged {t.strftime('%Y-%m-%d %H:%M')} {zone}"
    except ValueError:
        return f"logged {s}"


def _meta_line(p: render.Prepared, e: Entry) -> str:
    h = e.header
    who = ", ".join(p.name(a) for a in e.authors)
    if h.get("with"):
        who += f" (with assistance from {'Claude Code' if h['with'] == 'claude' else h['with']})"
    bits = [who, h.get("kind", "note")]
    if h.get("subproject"):
        bits.append(h["subproject"])
    if h.get("apparatus"):
        bits.append("on " + ", ".join(h["apparatus"]))
    bits.append(_fmt_logged(p.logged_text(e)))
    if h.get("backfilled"):
        bits.append(f"backfilled {h['backfilled']}")
    return " · ".join(str(b) for b in bits)


def _table(header: list[str], rows: list[list[str]]) -> str:
    cells = ", ".join(f"[*{c}*]" for c in header)
    body = ", ".join(", ".join(tc(c) for c in r) for r in rows)
    return (f"#table(columns: {len(header)}, stroke: none, inset: (x: 4pt, y: 2.5pt), "
            f"fill: (_, row) => if row == 0 {{ luma(235) }} else if calc.even(row) {{ luma(247) }}, "
            f"table.header({cells}), {body})")


def _entry_parts(p: render.Prepared, e: Entry, body: str) -> str:
    h, st, out = e.header, p.st, []
    # what later entries say about this one
    for cid in st.corrected_by.get(e.id, []):
        out.append(f"#lb-banner(lab-red)[*Corrected by* {_link(p, cid)}.]")
    for rid in st.redacted_by.get(e.id, []):
        out.append(f"#lb-banner(lab-grey)[*Redacted:* see {_link(p, rid)}.]")
    if h.get("corrects"):
        out.append(f"#lb-banner(lab-red)[*Corrects* {_link(p, h['corrects'])}.]")
    if h.get("resolves"):
        links = ", ".join(_link(p, *t.split("#", 1)) for t in h["resolves"])
        out.append(f"#lb-banner(lab-green)[*Resolves* {links}.]")
    if h.get("parameters"):
        out.append(_table(["Parameter", "Value", "Unit"],
                          [[x["name"], x["value"], x.get("unit", "")] for x in h["parameters"]]))
    if h.get("runs"):
        out.append("*Runs:* " + ", ".join(f"#{ts(r)}" for r in h["runs"]))
    if h.get("attendees"):
        out.append("*Attendees:* #" + ts(", ".join(p.name(a) for a in h["attendees"])))
    out.append(body)
    for snap in h.get("epics") or []:
        path = e.folder / snap["file"]
        try:
            import json
            pvs = json.loads(path.read_text(encoding="utf-8")).get("pvs", [])
        except (OSError, ValueError):
            pvs = []
        title = f"EPICS snapshot · {snap['group']}" + (f" · {snap['label']}" if snap.get("label") else "")
        out.append(f"#block(above: 1.4em, below: 0.4em)[#text(9pt, weight: \"bold\")[#{ts(title)}]]")
        out.append(_table(["PV", "Value", "Unit", "Severity"],
                          [[x.get("name", ""), x.get("value", ""), x.get("unit", ""), x.get("severity", "")] for x in pvs]))
    refs = {}
    for d in h.get("data") or []:
        refs["Data"] = refs.get("Data", []) + [f"{d['file']} (raw: {d['source']})"]
    for a in h.get("attachments") or []:
        refs["Attachment"] = refs.get("Attachment", []) + [a["file"] + (f" ({a['description']})" if a.get("description") else "")]
    for k, v in (h.get("refs") or {}).items():
        refs[k] = refs.get(k, []) + [v]
    if refs:
        br = " \\ "   # a Typst line break between values
        items = ", ".join(ts(k) + ": [" + br.join("#raw(" + ts(x) + ")" for x in v) + "]" for k, v in refs.items())
        out.append(f"#refs(({items},))")
    see = sorted(set(h.get("related") or []) | st.related.get(e.id, set()) | st.backlinks.get(e.id, set()))
    see = [s for s in see if s != e.id and s in p.titles]
    if see:
        out.append("#text(8.5pt, fill: lab-grey)[*See also:* " + " · ".join(_link(p, s) for s in see) + "]")
    return "\n\n".join(out)


def typst_source(p: render.Prepared, root: Path, title: str, subtitle: str | None, summary: str | None) -> str:
    book = p.book
    wiki = [w for w in sorted(p.wiki) if w.startswith("projects/")]
    used_projects = {proj for e in p.entries for proj in e.projects}
    proj_pages = {}
    for name, info in (book.projects or {}).items():
        if name in used_projects and info.get("wiki") in p.wiki:
            proj_pages[info["wiki"]] = name
    wiki = [w for w in wiki if not book.projects or w in proj_pages]
    md = render.document(p, wiki)
    rel = lambda f: "/" + f.resolve().relative_to(root.resolve()).as_posix()
    meta = {"doi": {k: render.bibmod.doi_url(r) for k, r in p.bib.items() if render.bibmod.doi_url(r)},
            # PDF/UA-1 export cannot embed PDF images: the SVG (which every plot has) goes in
            "fig": {k: f.for_meta(rel(f.svg or f.png or f.src)) for k, f in p.figs.items()},
            "wiki_in": wiki}
    out = render.pandoc(md, "typst", meta, book.bib_path if book.bib_path.exists() else None,
                        ["--metadata", "suppress-bibliography=true"])
    parts = render.split(out, ("// ", ""))
    refs_md = render.reference_list(p, "typst", render.used_keys(p))

    first = p.entries[0].date if p.entries else None
    lines = [
        "// Generated by lab-templates logbook (lablogbook.pdf). Do not edit: rebuild with `logbook build`.",
        f"#import {ts(rel(TEMPLATE))}: *",
        f"#import {ts(rel(STRIP))}: strip-image",
        "#let lb-banner(colour, body) = block(width: 100%, inset: (x: 7pt, y: 4pt), radius: 2pt, "
        "stroke: (left: 2pt + colour), fill: colour.lighten(93%), below: 0.6em)[#set text(9pt); #body]",
        "#let incident(body) = block(width: 100%, inset: (x: 9pt, y: 7pt), radius: 2pt, stroke: (left: 2.5pt + lab-red), "
        "fill: lab-red.lighten(92%), breakable: true)[#text(8pt, weight: \"bold\", fill: lab-red.darken(25%), tracking: 0.5pt)[INCIDENT] \\ #body]",
        "#show: labnotes.with(",
        f"  title: {ts(title)},",
        f"  project: {ts(subtitle) if subtitle else 'none'},",
        f"  author: {ts(book.config.get('author') or (p.name(p.entries[0].authors[0]) if p.entries else ''))},",
        f"  affiliation: {ts(book.config['affiliation']) if book.config.get('affiliation') else 'none'},",
        f"  started: {ts(first) if first else 'none'},",
        f"  summary: {tc(summary) if summary else 'none'},",
        ")",
    ]
    if wiki:
        lines.append("= Projects")
        for w in wiki:
            lines.append(f"#metadata(\"wiki\") <w-{w.replace('/', '-')}>")
            lines.append(parts.get(("WIKI", w), ""))
    by_day: dict[str, list[Entry]] = {}
    for e in p.entries:
        by_day.setdefault(e.date, []).append(e)
    for day, es in by_day.items():
        projects = []
        for e in es:
            projects += [x for x in e.projects if x not in projects]
        lines.append(f"#day({ts(day)}, {ts(' · '.join(projects))})[")
        for e in es:
            h = e.header
            body = parts.get(("ENTRY", e.id), "")
            tags = "(" + "".join(f"{ts(t)}, " for t in (h.get("tags") or [])) + ")"
            lines.append(f"#metadata(\"entry\") <{_label(e.id)}>")
            lines.append(f"#note({ts(h['project'])}, {ts(h['title'])}, tags: {tags}, authors: {tc(_meta_line(p, e))})[")
            lines.append(_entry_parts(p, e, body))
            lines.append("]")
        lines.append("]")
    if refs_md.strip():
        lines.append("= References")
        lines.append("#set text(9.5pt)")
        lines.append(refs_md)
    return "\n\n".join(lines) + "\n"


def find_root(book: Book) -> Path:
    """The Typst root: the folder that holds both the log book and lab-templates."""
    a, b = book.root.resolve(), LAB.resolve()
    common = Path(*[x for x, y in zip(a.parts, b.parts) if x == y] or ["/"])
    for cand in [common, *common.parents]:
        if (cand / ".git").exists():
            return cand
    return common


def build(book: Book, out: Path, entries: list[Entry] | None = None, title: str | None = None,
          subtitle: str | None = None, summary: str | None = None, keep_source: bool = True,
          anonymise: bool = False) -> Path:
    """`anonymise`: authors and attendees appear as "Author 1", "Author 2", … (the text itself is
    not changed: names written in an entry's text stay)."""
    if not shutil.which("typst"):
        raise render.RenderError("typst is needed for the PDF (https://typst.app; brew install typst)")
    p = render.prepare(book, entries)
    if anonymise:
        order = []
        for e in p.entries:
            for h in e.authors + list(e.header.get("attendees") or []):
                if h not in order:
                    order.append(h)
        p.names = {h: f"Author {i}" for i, h in enumerate(order, 1)}
    root = find_root(book)
    src = typst_source(p, root, title or book.config.get("title", "Log book"), subtitle, summary)
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    typ = out.with_suffix(".typ")
    if not typ.is_relative_to(root.resolve()):   # the source must sit inside Typst's root; the PDF may go anywhere
        (root / "build").mkdir(exist_ok=True)
        typ = root / "build" / f".logbook-{out.stem}.typ"
        keep_source = False
    typ.write_text(src, encoding="utf-8")
    pdf_only = [f.src for f in p.figs.values() if f.src.suffix.lower() == ".pdf" and not (f.svg or f.png)]
    standard = [] if pdf_only else ["--pdf-standard", "ua-1"]
    if pdf_only:
        print(f"note: {len(pdf_only)} figure(s) exist only as PDF (e.g. {book.rel(pdf_only[0])}); "
              "the PDF is built without PDF/UA-1, which cannot embed PDF images. Save an SVG next to it.")
    r = subprocess.run(["typst", "compile", "--root", str(root), *standard, str(typ), str(out)],
                       capture_output=True, text=True)
    errors = [ln for ln in r.stderr.splitlines() if not re.search(r"unknown font family: linux libertine", ln, re.I)]
    if r.returncode:
        raise render.RenderError("typst failed:\n" + "\n".join(errors)[:4000] + f"\n(source kept in {typ})")
    if not keep_source:
        typ.unlink()
    return out
