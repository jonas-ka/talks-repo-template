"""`logbook export`, `logbook month`, `logbook digest`: the PDFs and the summary made from a
selection of entries."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from . import pdf, render, state
from .book import Book
from .entry import Entry
from .selection import Filter


def export(book: Book, f: Filter, out: Path, requested_by: str | None = None, approved_by: str | None = None,
           note: str | None = None, anonymise: bool = False) -> tuple[Path | None, int]:
    entries = f.apply(book)
    if not entries:
        return None, 0
    today = book.now().date().isoformat()
    parts = [f"Export of {len(entries)} entries ({f.describe(book)}), made on {today}."]
    if requested_by:
        parts.append(f"Requested by {requested_by}.")
    if approved_by:
        parts.append(f"Approved by {approved_by}.")
    if note:
        parts.append(f"Purpose: {note}.")
    if anonymise:
        parts.append("Authors are shown by role, not by name.")
    parts.append("Entries are shown as they were written; corrections are later entries.")
    path = pdf.build(book, out, entries, title=f"{book.config.get('title', 'Log book')}: export",
                     # the template labels the subtitle "Project:"; the whole selection is in the summary
                     subtitle=", ".join(f.projects) if f.projects else "all projects",
                     summary=" ".join(parts), keep_source=False, anonymise=anonymise)
    return path, len(entries)


def logged_month(book: Book, month: str) -> list[Entry]:
    """Entries logged (merged) in `month` (YYYY-MM); an entry not yet in git counts by its date."""
    logged = render.logged_times(book)
    out = []
    for e in book.entries.values():
        when = e.header.get("logged") or (logged[e.id].when if e.id in logged else None) or e.date
        if str(when)[:7] == month:
            out.append(e)
    return sorted(out, key=lambda e: (e.date, str(e.header.get("time") or ""), e.id))


def previous_month(today: dt.date | None = None) -> str:
    d = (today or dt.date.today()).replace(day=1) - dt.timedelta(days=1)
    return d.strftime("%Y-%m")


def month_pdf(book: Book, month: str, out_dir: Path) -> tuple[Path | None, int]:
    entries = logged_month(book, month)
    if not entries:
        return None, 0
    name = dt.date.fromisoformat(month + "-01").strftime("%B %Y")
    out = out_dir / f"Logbook-{month}.pdf"
    path = pdf.build(book, out, entries, title=f"{book.config.get('title', 'Log book')}, {name}",
                     subtitle=f"Entries logged in {name}",
                     summary=f"The {len(entries)} entries logged in {name}, as they were written. The full record is the repository.",
                     keep_source=False)
    return path, len(entries)


def digest(book: Book, today: str | None = None, days: int = 7) -> str:
    """The weekly summary (Markdown, for an issue): new entries, open items, expiring calibrations."""
    t = dt.date.fromisoformat(today) if today else book.now().date()
    since = (t - dt.timedelta(days=days)).isoformat()
    logged = render.logged_times(book)
    names = {h: p.name for h, p in (book.people or {}).items()}
    nm = lambda h: names.get(h, h)
    new = [e for e in book.entries.values() if str(e.header.get("logged") or (logged[e.id].when if e.id in logged else e.date))[:10] >= since]
    lines = [f"Log book, week ending {t.isoformat()}: **{len(new)} new entries**.", ""]
    by_project: dict[str, list[Entry]] = {}
    for e in sorted(new, key=lambda e: e.id):
        by_project.setdefault(e.header.get("project", "?"), []).append(e)
    for proj, es in sorted(by_project.items()):
        lines.append(f"### {proj}")
        lines += [f"- {e.date} · {e.header.get('title')} ({', '.join(nm(a) for a in e.authors)}) `{e.id}`" for e in es]
        lines.append("")
    st = state.compute(book.entries)
    items = st.ranked_open_items(book.entries, t, book.config["open_items"]["asap_days"])
    lines.append(f"### Open items ({len(items)}), most urgent first")
    for x in items:
        e = x["entry"]
        flag = "**overdue** " if x["overdue"] else ""
        lines.append(f"- {flag}{x['priority']}, {x['kind']}, open {x['age']} d: {e.header.get('title')} `{x['key']}` "
                     f"({', '.join(nm(a) for a in e.authors)})")
    soon = (t + dt.timedelta(days=30)).isoformat()
    expiring = [e for e in book.entries.values() if e.header.get("valid_until") and t.isoformat() <= str(e.header["valid_until"]) <= soon]
    if expiring:
        lines += ["", "### Calibrations and maintenance expiring within 30 days"]
        lines += [f"- {e.header['valid_until']}: {e.header.get('title')} `{e.id}`" for e in sorted(expiring, key=lambda e: str(e.header["valid_until"]))]
    return "\n".join(lines) + "\n"
