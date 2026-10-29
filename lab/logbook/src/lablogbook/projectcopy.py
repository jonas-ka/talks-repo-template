"""`logbook pull`: the per-project copy of a central log book.

In a repository whose logbook.yaml names a central log book, `logbook pull` writes `logbook/`:
the entries of the repository's projects with their files, the wiki pages they need, the
reference list and registries (so the copy is itself a log book that `logbook check` accepts),
the PDF, the one-file HTML view, `SUMMARY.md` (read this first) and `GENERATED.md`. The copy is
generated: the next pull replaces it, so it is never edited.

Guards: never into a public repository; into an internal one only while projects.yaml grants it
(`copy_internal_until: <date>` for each copied project); never inside `lab/`; not when the
repository's visibility cannot be found out (offline).
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

from . import connect, pdf, render, state
from . import htmlview
from .book import open_book
from .entry import load_yaml
from .selection import Filter

MARKER = "GENERATED.md"


class CopyError(RuntimeError):
    pass


_IMG_MD = __import__("re").compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?")
_IMG_HTML = __import__("re").compile(r"<img\b[^>]*?\bsrc=\"([^\"]+)\"")


def _local_images(text: str) -> list[str]:
    """Relative image paths a Markdown page uses (`![…](figures/x.png)`, `<img src="…">`)."""
    out = []
    for m in list(_IMG_MD.finditer(text)) + list(_IMG_HTML.finditer(text)):
        path = m.group(1)
        if "://" not in path and not path.startswith(("/", "#", "data:")) and ".." not in path.split("/"):
            out.append(path)
    return list(dict.fromkeys(out))


def _guard(here: Path, dest: Path, central_book, projects: list[str], today: str) -> None:
    if dest.resolve().is_relative_to((here / "lab").resolve()):
        raise CopyError("the copy never goes inside lab/ (the public templates are generated from it)")
    vis = connect.repo_visibility(here)
    if vis is None:
        raise CopyError("cannot find out whether this repository is public (offline, or no `gh`): not copying")
    if vis == "PUBLIC":
        raise CopyError("this repository is public: the log book is never copied into a public repository")
    if vis == "INTERNAL":
        reg = central_book.projects or {}
        missing = [p for p in projects if str((reg.get(p) or {}).get("copy_internal_until") or "") < today]
        if missing:
            raise CopyError(f"this repository is internal (every member of the organisation can read it); "
                            f"no current permission (copy_internal_until in projects.yaml) for: {', '.join(missing)}")


def _wipe(dest: Path) -> None:
    if not dest.exists():
        return
    if not (dest / MARKER).exists() and any(dest.iterdir()):
        raise CopyError(f"{dest} exists and was not made by `logbook pull` (no {MARKER}); not touching it")
    shutil.rmtree(dest)


def pull(here: Path, central: dict, update: bool = True, today: str | None = None, out=None) -> Path:
    today = today or dt.date.today().isoformat()
    clone = Path(str(central.get("clone", ""))).expanduser().resolve()
    if update:
        connect.run(["git", "-C", str(clone), "pull", "-q", "--ff-only"], check=False)
    book = open_book(clone)
    projects = list(central.get("projects") or ([central["project"]] if central.get("project") else []))
    if not projects:
        raise CopyError("logbook.yaml: central.projects (or central.project) names what to copy")
    dest = (here / central.get("copy", "logbook")).resolve()
    _guard(here, dest, book, projects, today)
    entries = Filter(projects=projects).apply(book)
    sha = connect.run(["git", "-C", str(clone), "rev-parse", "--short", "HEAD"], check=False).strip()

    _wipe(dest)
    dest.mkdir(parents=True)
    cfg = dict(book.config)
    for f in ["logbook.yaml", *[book.config["registries"][k] for k in ("people", "projects", "apparatus", "kinds")]]:
        if (clone / f).exists():
            shutil.copy2(clone / f, dest / f)
    # the entries and every file they name (a figure with its siblings)
    for e in entries:
        rel = e.path.relative_to(book.root)
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(e.path, dest / rel)
        for _, f, _ in e.files():
            src = e.folder / f
            for s in [src] + [src.with_suffix(x) for x in (".pdf", ".svg", ".png", ".yaml")]:
                if s.exists():
                    d = dest / s.relative_to(book.root)
                    d.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(s, d)
    # the wiki pages they need: the projects', the apparatus', the ones they link to; the references
    pages = set()
    for p in projects:
        if (book.projects or {}).get(p, {}).get("wiki"):
            pages.add(book.projects[p]["wiki"])
    for e in entries:
        for a in e.header.get("apparatus") or []:
            if (book.apparatus or {}).get(a, {}).get("wiki"):
                pages.add(book.apparatus[a]["wiki"])
        pages.update(t[5:].strip().removesuffix(".md") for t, _ in e.links() if t.startswith("wiki:"))
    for page in sorted(pages):
        src = book.wiki_dir / f"{page}.md"
        if src.exists():
            d = dest / cfg["wiki"] / f"{page}.md"
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, d)
            for rel in _local_images(src.read_text(encoding="utf-8")):   # the page's own figures
                s = (src.parent / rel).resolve()
                if s.is_file() and s.is_relative_to(book.wiki_dir.resolve()):
                    target = d.parent / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(s, target)
                    for ext in (".svg", ".png", ".pdf"):   # a figure's siblings, as for entries
                        sib = s.with_suffix(ext)
                        if sib.exists() and sib != s:
                            shutil.copy2(sib, target.with_suffix(ext))
    if book.bib_path.exists():
        d = dest / cfg["bibliography"]
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(book.bib_path, d)

    copy = open_book(dest)
    (dest / MARKER).write_text(
        f"# Generated: do not edit\n\nThis folder is a copy of the central log book ({central.get('repository', clone.name)} at "
        f"{sha}), made by `logbook pull` on {today} for: {', '.join(projects)}. The next pull replaces it.\n\n"
        "New entries are written to the central log book (`logbook new --from draft.md`), never here; "
        "they appear in this copy with the next pull.\n", encoding="utf-8")
    (dest / "SUMMARY.md").write_text(summary(copy, projects, central, sha, today), encoding="utf-8")
    # the PDF and the one-file view are rebuilt by every pull and are large: they stay out of git
    (dest / ".gitignore").write_text("# rebuilt by every `logbook pull`; never committed\nlogbook.pdf\nlogbook.html\n",
                                     encoding="utf-8")
    try:
        pdf.build(copy, dest / "logbook.pdf", keep_source=False)
        htmlview.build(copy, dest / "logbook.html", single=True)
    except Exception as err:   # noqa: BLE001 - the text copy is what matters most; say what failed
        if out:
            print(f"note: the PDF or HTML view of the copy was not built: {err}", file=out)
    return dest


def summary(copy, projects: list[str], central: dict, sha: str, today: str) -> str:
    """What a reader (or Claude Code after a compaction) needs first."""
    lines = [f"# Log book: {', '.join(projects)}", "",
             f"Copy of the central log book `{central.get('repository', '')}` at {sha}, pulled {today}. "
             "Entries are in `entries/YYYY/`, one Markdown file each; `logbook.pdf` and `logbook.html` show them all. "
             "Write new entries with `logbook new` (they go to the central log book), never in this folder.", ""]
    for p in projects:
        page = (copy.projects or {}).get(p, {}).get("wiki")
        f = copy.wiki_dir / f"{page}.md" if page else None
        if f and f.exists():
            lines += [f"## About {p}", "", render.wiki_text(f).split("\n", 1)[-1].strip(), ""]
    st = state.compute(copy.entries)
    items = st.open_items(copy.entries)
    lines += [f"## Open items ({len(items)})", ""]
    lines += [f"- {kind} `{e.id}#{a}`: {e.header.get('title')}" for e, a, kind in sorted(items, key=lambda x: x[0].date)] or ["- none"]
    recent = sorted(copy.entries.values(), key=lambda e: e.id, reverse=True)[:15]
    lines += ["", "## Latest entries", ""]
    lines += [f"- {e.date} {e.header.get('title')} (`{copy.rel(e.path)}`)" for e in recent]
    return "\n".join(lines) + "\n"
