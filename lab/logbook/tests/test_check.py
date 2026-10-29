"""The checker against the example book and against deliberately broken copies of it."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from lablogbook import bib, check
from lablogbook.book import open_book

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "logbook"
TODAY = "2026-10-06"
RUN = "2026-10-01-0930-aa-first-transmission-scan"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def book_dir(tmp_path: Path) -> Path:
    """A copy of the example book in its own git repository, one commit on main."""
    d = tmp_path / "book"
    shutil.copytree(EXAMPLE, d)
    git(d, "init", "-q", "-b", "main")
    git(d, "config", "user.email", "test@example.org")
    git(d, "config", "user.name", "Test")
    git(d, "add", "-A")
    git(d, "commit", "-q", "-m", "base")
    return d


def run(d: Path, *paths: str, **kw) -> check.Report:
    opts = check.Options(paths=[d / p for p in paths], today=kw.pop("today", TODAY), **kw)
    return check.run(open_book(d), opts)


def codes(report: check.Report, level: str | None = None) -> set[str]:
    return {f.code for f in report.findings if level is None or f.level == level}


def write_entry(d: Path, eid: str, header: str, body: str = "Text.\n") -> str:
    p = d / "entries" / eid[:4] / f"{eid}.md"
    p.write_text(f"---\n{header.strip()}\n---\n\n{body}", encoding="utf-8")
    return str(p.relative_to(d))


def note(eid: str, extra: str = "", authors: str = "[aa]", project: str = "Example experiment") -> str:
    date = eid[:10]
    return f"date: {date}\nauthors: {authors}\nkind: note\nproject: {project}\ntitle: A test entry\n{extra}"


# ------------------------------------------------------------------------------ the example --
def test_example_book_is_clean():
    r = check.run(open_book(EXAMPLE), check.Options(today=TODAY))
    assert [f.render() for f in r.findings if f.level in ("fail", "hold", "warn")] == []
    assert r.exit_code == 0


# ------------------------------------------------------------------------------ format -------
def test_schema_missing_and_unknown_fields(book_dir):
    eid = "2026-10-06-0800-aa-schema"
    p = write_entry(book_dir, eid, "date: 2026-10-06\nauthors: [aa]\nkind: note\nproject: Example experiment\ncolour: blue")
    r = run(book_dir, p)
    msgs = " ".join(f.message for f in r.findings if f.code == "schema")
    assert "missing field 'title'" in msgs and "unknown field" in msgs
    assert r.exit_code == 1


def test_name_must_match_header(book_dir):
    p = write_entry(book_dir, "2026-10-06-0800-aa-name", note("2026-10-05-0800-aa-name"))
    assert "name" in codes(run(book_dir, p), "fail")


def test_handle_must_be_first_author(book_dir):
    p = write_entry(book_dir, "2026-10-06-0800-bb-handle", note("2026-10-06-0800-bb-handle", authors="[aa, bb]"))
    assert "name" in codes(run(book_dir, p), "fail")


def test_registries(book_dir):
    p = write_entry(book_dir, "2026-10-06-0800-aa-reg",
                    note("2026-10-06-0800-aa-reg", "subproject: Nowhere\napparatus: [laser]\n", authors="[aa, zz]"))
    c = codes(run(book_dir, p), "fail")
    assert {"author", "project", "apparatus"} <= c


def test_kind_requires_and_recommends(book_dir):
    p = write_entry(book_dir, "2026-10-06-0800-aa-corr",
                    "date: 2026-10-06\nauthors: [aa]\nkind: correction\nproject: Example experiment\ntitle: Fix")
    assert "kind" in codes(run(book_dir, p), "fail")
    p = write_entry(book_dir, "2026-10-06-0900-aa-run",
                    "date: 2026-10-06\nauthors: [aa]\nkind: run\nproject: Example experiment\ntitle: A run")
    r = run(book_dir, p)
    assert "kind" in codes(r, "warn") and r.exit_code == 0


def test_late_and_future_dates(book_dir):
    p = write_entry(book_dir, "2026-09-20-0800-aa-late", note("2026-09-20-0800-aa-late"))
    assert "late" in codes(run(book_dir, p), "fail")
    p2 = write_entry(book_dir, "2026-09-20-0900-aa-late2", note("2026-09-20-0900-aa-late2", "backfilled: 2026-10-06\n"))
    assert "late" not in codes(run(book_dir, p2))
    p3 = write_entry(book_dir, "2026-10-20-0800-aa-future", note("2026-10-20-0800-aa-future"))
    assert "date" in codes(run(book_dir, p3), "fail")


# ------------------------------------------------------------------------------ compliance ---
@pytest.mark.parametrize("text,code", [
    ("Her number is 123456789.", "ferpa-uin"),
    ("SSN 123-45-6789 was on the form.", "ferpa-ssn"),
    ("The midterm grades were low.", "ferpa-grades"),
    ("Talked to student Zelda Quill about it.", "ferpa-student-name"),
    ("Mail went to someone.else@tamu.edu today.", "ferpa-email"),
    ("He was on sick leave after the injury.", "health-words"),
])
def test_ferpa_and_health_fail_and_can_be_reviewed(book_dir, text, code):
    eid = "2026-10-06-0800-aa-ferpa"
    p = write_entry(book_dir, eid, note(eid), text + "\n")
    r = run(book_dir, p)
    assert code in codes(r, "fail"), r.render()
    cat = "health" if code.startswith("health") else "ferpa"
    p = write_entry(book_dir, eid, note(eid, f"reviewed: {cat}\n"), text + "\n")
    r = run(book_dir, p)
    assert code in codes(r, "warn") and code not in codes(r, "fail")


def test_ci_output_never_shows_the_matched_text(book_dir):
    eid = "2026-10-06-0800-aa-mask"
    p = write_entry(book_dir, eid, note(eid), "Her number is 123456789.\n")
    r = run(book_dir, p, ci=True)
    assert "123456789" not in r.render(ci=True)
    assert "123456789" in r.render(ci=False)       # locally the author sees the line
    assert "123456789" not in r.to_json()


def test_secrets_paths_and_drive_ids(book_dir):
    token = "ghp_" + "a1B2" * 9
    home = "/" + "Users/someone/data.csv"
    drive = "https://drive.google.com/drive/folders/" + "A" * 28
    eid = "2026-10-06-0800-aa-secret"
    p = write_entry(book_dir, eid, note(eid), f"{token}\n{home}\n{drive}\n")
    r = run(book_dir, p)
    assert {"secret-github", "path-home"} <= codes(r, "fail")
    assert "drive-id" in codes(r, "info") and "drive-id" not in codes(r, "fail")   # links allowed, with a reminder
    cfg = book_dir / "logbook.yaml"
    cfg.write_text(cfg.read_text().replace("forbid_drive_ids: false", "forbid_drive_ids: true"))
    assert "drive-id" in codes(run(book_dir, p), "fail")


def test_vendor_wording_warns(book_dir):
    eid = "2026-10-06-0800-aa-vendor"
    p = write_entry(book_dir, eid, note(eid), "The vendor's proprietary settings are in the manual.\n")
    r = run(book_dir, p)
    assert "vendor-words" in codes(r, "warn") and r.exit_code == 0


# ------------------------------------------------------------------------------ files --------
def test_pdf_attachment_is_held_until_confirmed(book_dir):
    (book_dir / "entries/2026/attachments").mkdir()
    (book_dir / "entries/2026/attachments/wiring.pdf").write_bytes(b"%PDF-1.4\n")
    eid = "2026-10-06-0800-aa-attach"
    p = write_entry(book_dir, eid, note(eid, "attachments:\n  - file: attachments/wiring.pdf\n"))
    r = run(book_dir, p)
    assert "export-control" in codes(r, "hold") and r.exit_code == 3
    p = write_entry(book_dir, eid, note(eid, "attachments:\n  - {file: attachments/wiring.pdf, export_control_confirmed: true}\n"))
    assert run(book_dir, p).exit_code == 0


def test_figures(book_dir):
    figs = book_dir / "entries/2026/figures"
    (figs / "plot-noversion.pdf").write_bytes(b"%PDF-1.4\n")
    (figs / "plot-noversion.svg").write_text("<svg/>")
    (figs / "plot-nosvg-v1.pdf").write_bytes(b"%PDF-1.4\n")
    (figs / "photo-setup.jpg").write_bytes(b"\xff\xd8")
    fig = "  - {{file: figures/{f}, caption: A caption, alt: A long enough alt text{k}}}\n"
    eid = "2026-10-06-0800-aa-figs"
    header = note(eid, "figures:\n" + fig.format(f="plot-noversion.pdf", k="") + fig.format(f="plot-nosvg-v1.pdf", k="")
                  + fig.format(f="photo-setup.jpg", k=", kind: photo") + fig.format(f="missing-v1.pdf", k=""))
    r = run(book_dir, write_entry(book_dir, eid, header))
    msgs = [f.message for f in r.findings]
    assert any("needs its SVG" in m for m in msgs)
    assert any("no version in the name" in m for m in msgs)
    assert any("file not found" in m for m in msgs)
    assert "export-control" in codes(r, "hold")


def test_size_limit(book_dir):
    (book_dir / "entries/2026/data/big.csv").write_bytes(b"0" * 6_000_000)
    eid = "2026-10-06-0800-aa-big"
    p = write_entry(book_dir, eid, note(eid, "data:\n  - {file: data/big.csv, source: somewhere}\n"))
    assert "size" in codes(run(book_dir, p), "fail")


def test_epics_snapshot(book_dir):
    snap = book_dir / "entries/2026/epics/bad.json"
    snap.write_text('{"format": "lab-epics-snapshot/1", "group": "source-tune", "pvs": [{"name": "OTHER:PV", "value": 1}]}')
    eid = "2026-10-06-0800-aa-epics"
    p = write_entry(book_dir, eid, note(eid, "epics:\n  - {file: epics/bad.json, group: source-tune}\n"))
    assert any("not in group" in f.message for f in run(book_dir, p).findings)


# ------------------------------------------------------------------------------ links --------
def test_links_resolves_and_citations(book_dir):
    eid = "2026-10-06-0800-aa-links"
    header = note(eid, f"resolves: [{RUN}#issue-drift, {RUN}#nothing]\nrelated: [2026-01-01-0000-aa-nope]\n")
    body = "See [[2026-01-01-0000-zz-missing]] and [@Unknown2020] and [@Author2019].\n"
    r = run(book_dir, write_entry(book_dir, eid, header, body))
    msgs = " ".join(f.message for f in r.findings)
    assert "already resolved" in msgs and "no issue or todo #nothing" in msgs
    assert "no such entry" in msgs and "related: no entry" in msgs
    assert "@Unknown2020 is not in the reference list" in msgs and "Author2019" not in msgs


def test_open_todo_can_be_resolved_once(book_dir):
    eid = "2026-10-06-0800-aa-resolve"
    p = write_entry(book_dir, eid, note(eid, f"resolves: [{RUN}#todo-repeat]\n"))
    assert run(book_dir, p).exit_code == 0


def test_bib_duplicate_and_missing_doi(book_dir):
    b = book_dir / "wiki/references.bib"
    b.write_text(b.read_text() + "\n@article{Solo2021, author = {X, Y}, year = {2020}}\n")
    r = run(book_dir, "wiki/references.bib")
    assert any("used twice" in f.message for f in r.findings if f.level == "fail")


# ------------------------------------------------------------------------------ pull requests --
def pr(d: Path, submitter: str) -> check.Report:
    git(d, "checkout", "-q", "-B", "feature")
    git(d, "add", "-A")
    git(d, "commit", "-q", "-m", "change")
    return check.run(open_book(d), check.Options(base="main", submitter=submitter, today=TODAY, ci=True))


def test_new_entry_by_its_author_passes(book_dir):
    eid = "2026-10-06-0800-bb-new"
    write_entry(book_dir, eid, note(eid, authors="[bb]"))
    r = pr(book_dir, "b-builder-example")
    assert r.exit_code == 0, r.render()
    assert "coauthors" in codes(r, "info")      # aa and cc worked on the project recently


def test_first_author_must_be_the_submitter(book_dir):
    eid = "2026-10-06-0800-aa-notmine"
    write_entry(book_dir, eid, note(eid))
    assert "authorship" in codes(pr(book_dir, "b-builder-example"), "fail")


def test_admin_may_submit_on_behalf(book_dir):
    eid = "2026-10-06-0800-aa-behalf"
    write_entry(book_dir, eid, note(eid))
    assert pr(book_dir, "c-chair-example").exit_code == 0


def test_unknown_submitter_fails(book_dir):
    eid = "2026-10-06-0800-aa-stranger"
    write_entry(book_dir, eid, note(eid))
    assert "authorship" in codes(pr(book_dir, "someone-else"), "fail")


@pytest.mark.parametrize("change", ["edit", "delete", "rename", "figure"])
def test_existing_entries_never_change(book_dir, change):
    f = book_dir / "entries/2026" / f"{RUN}.md"
    if change == "edit":
        f.write_text(f.read_text().replace("38 %", "40 %"))
    elif change == "delete":
        f.unlink()
    elif change == "rename":
        f.rename(f.with_name("2026-10-01-0930-aa-renamed.md"))
    else:
        (book_dir / "entries/2026/data/transmission-scan-r017.csv").write_text("changed\n")
    assert "append-only" in codes(pr(book_dir, "c-chair-example"), "fail")


def test_redaction_by_admin_may_change_an_entry(book_dir):
    f = book_dir / "entries/2026" / f"{RUN}.md"
    f.write_text(f.read_text().replace("The source ran", "[redacted 2026-10-06, see 2026-10-06-0800-cc-redaction] The source ran"))
    write_entry(book_dir, "2026-10-06-0800-cc-redaction",
                f"date: 2026-10-06\nauthors: [cc]\nkind: redaction\nproject: Example experiment\n"
                f"title: Redaction of {RUN}\nredacts: {RUN}\nlevel: 2")
    r = pr(book_dir, "c-chair-example")
    assert "append-only" not in codes(r) and r.exit_code == 0, r.render()


def test_redaction_by_member_fails(book_dir):
    f = book_dir / "entries/2026" / f"{RUN}.md"
    f.write_text(f.read_text() + "\n")
    write_entry(book_dir, "2026-10-06-0800-aa-redaction",
                f"date: 2026-10-06\nauthors: [aa]\nkind: redaction\nproject: Example experiment\n"
                f"title: Redaction of {RUN}\nredacts: {RUN}\nlevel: 2")
    c = codes(pr(book_dir, "a-author-example"), "fail")
    assert "append-only" in c or "redaction" in c


def test_tooling_only_by_admin_but_wiki_by_anyone(book_dir):
    (book_dir / "people.yaml").write_text((book_dir / "people.yaml").read_text() + "\n")
    (book_dir / "wiki/apparatus/beamline.md").write_text("# Example beamline\n\nNow four legs.\n")
    r = pr(book_dir, "a-author-example")
    bad = {f.path for f in r.findings if f.code == "protected"}
    assert bad == {"people.yaml"}


def test_unreferenced_new_file_warns(book_dir):
    (book_dir / "entries/2026/data/orphan.csv").write_text("x\n1\n")
    assert any("no entry refers" in f.message for f in pr(book_dir, "a-author-example").findings)


# ------------------------------------------------------------------------------ standalone ---
def test_standalone_book_accepts_free_names(tmp_path):
    d = tmp_path / "solo"
    (d / "entries/2026").mkdir(parents=True)
    write_entry(d, "2026-10-06-0800-me-start",
                "date: 2026-10-06\nauthors: [A. Colleague]\nkind: note\nproject: Anything\ntitle: Started")
    r = check.run(open_book(d), check.Options(today=TODAY))
    assert r.exit_code == 0, r.render()


# ------------------------------------------------------------------------------ citations ----
def test_citation_format():
    recs = {r.key: r for r in bib.parse((EXAMPLE / "wiki/references.bib").read_text())}
    assert bib.format_citation(recs["Author2019"]) == "Author A.++ Phys. Rev. Lett. 123, 456 (2019)"
    assert bib.format_citation(recs["Solo2021"]) == "Solo H. Nat. Phys. 17, 101 (2021)"
    assert bib.format_citation(recs["Writer2001"]) == "Writer A.++ Ion Traps in Practice (Example Press, 2001)"
    assert bib.doi_url(recs["Author2019"]) == "https://doi.org/10.5555/example.2019.456"


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")
def test_csl_style_gives_the_same_text(tmp_path):
    from importlib import resources
    csl = resources.files("lablogbook").joinpath("data/karthein-lab.csl")
    md = tmp_path / "t.md"
    md.write_text("[@Author2019]; [@Solo2021]; [@Writer2001]\n")
    out = subprocess.run(["pandoc", str(md), "--citeproc", "--bibliography", str(EXAMPLE / "wiki/references.bib"),
                          "--csl", str(csl), "-t", "plain", "--wrap=none"], capture_output=True, text=True, check=True).stdout
    assert "Author A.++ Phys. Rev. Lett. 123, 456 (2019)" in out
    assert "Solo H. Nat. Phys. 17, 101 (2021)" in out
    assert "Writer A.++ Ion Traps in Practice (Example Press, 2001)" in out


def test_wiki_page_reviewed_header(tmp_path):
    from lablogbook import check, render
    from lablogbook.book import open_book
    root = tmp_path / "b"
    (root / "wiki" / "safety").mkdir(parents=True)
    page = root / "wiki" / "safety" / "laser.md"
    page.write_text("# Laser safety\n\nEye injuries from a stray beam are the main risk.\n")
    r = check.run(open_book(root), check.Options())
    assert r.exit_code == 1 and any(f.code == "health-words" for f in r.findings)
    page.write_text("---\nreviewed: [health]\n---\n# Laser safety\n\nEye injuries from a stray beam are the main risk.\n")
    r = check.run(open_book(root), check.Options())
    assert r.exit_code == 0
    hit = [f for f in r.findings if f.code == "health-words"]
    assert hit and hit[0].level == "warn" and hit[0].line == 6
    meta, body, n = render.wiki_split(page.read_text())
    assert meta == {"reviewed": ["health"]} and body.startswith("# Laser safety") and n == 3


def test_migrated_entries_are_late_by_their_logged_date(book_dir):
    mig = "migrated_from: src@0123456789ab\nlogged: \"2026-09-02T10:00:00-05:00\"\n"
    write_entry(book_dir, "2026-09-01-0900-aa-migrated", note("2026-09-01-0900-aa-migrated", mig))
    r = pr(book_dir, "c-chair-example")                     # an admin migrates on the author's behalf
    assert "late" not in codes(r) and "migrated" not in codes(r), r.render()


def test_migrated_fields_do_not_excuse_a_late_entry_from_a_member(book_dir):
    mig = "migrated_from: src@0123456789ab\nlogged: \"2026-09-02T10:00:00-05:00\"\n"
    write_entry(book_dir, "2026-09-01-0900-aa-dodge", note("2026-09-01-0900-aa-dodge", mig))
    assert "migrated" in codes(pr(book_dir, "a-author-example"), "fail")


def test_privacy_settings_choose_domains_and_id_pattern(book_dir):
    import yaml as _yaml
    cfg = book_dir / "logbook.yaml"
    base = cfg.read_text()
    text = "Asked jdoe@lab.example.gov and pat@mit.edu; badge 12345678 and run 123456789."
    p = write_entry(book_dir, "2026-10-12-0900-aa-privacy", note("2026-10-12-0900-aa-privacy"), text + "\n")
    c = codes(run(book_dir, p), "fail")                        # defaults: every .edu, nine digits
    assert "ferpa-email" in c and "ferpa-uin" in c
    cfg.write_text(base + "privacy:\n  email_domains: [example.gov]\n  id_pattern: '(?<!\\d)\\d{8}(?!\\d)'\n")
    r = run(book_dir, p)
    hits = [f for f in r.findings if f.code in ("ferpa-email", "ferpa-uin")]
    assert {f.code for f in hits} == {"ferpa-email", "ferpa-uin"}
    assert len([f for f in hits if f.code == "ferpa-email"]) == 1                    # example.gov, not mit.edu
    cfg.write_text(base + "privacy:\n  email_domains: []\n  id_pattern: null\n")
    assert not {"ferpa-email", "ferpa-uin"} & codes(run(book_dir, p))


def test_unreadable_or_unclosed_blocks_fail_in_a_new_entry(book_dir):
    p = write_entry(book_dir, "2026-10-12-0900-aa-blocks", note("2026-10-12-0900-aa-blocks"),
                    "Text.\n\n::: todo {#todo-1\n- x\n:::\n\n::: finding\nNever closed.\n")
    fails = [f for f in run(book_dir, p).findings if f.code == "block" and f.level == "fail"]
    assert len(fails) == 2


# ------------------------------------------------------------------------------ priorities --


def test_priorities_on_blocks_and_from_later_entries(book_dir):
    eid = "2026-10-06-0900-aa-priorities"
    bad = "2026-10-06-0910-aa-bad-priorities"
    write_entry(book_dir, eid, note(eid, f"priority:\n  {RUN}#todo-repeat: low\n"),
                "::: todo {#todo-now priority=asap}\nThe valve.\n:::\n")
    worse = "2026-10-06-0920-aa-no-such-level"
    write_entry(book_dir, bad, note(bad, f"priority:\n  {RUN}#todo-nothing: high\n"),
                "::: finding {priority=high}\nNot an open item.\n:::\n")
    write_entry(book_dir, worse, note(worse, f"priority:\n  {RUN}#todo-repeat: urgent\n"))
    r = run(book_dir, f"entries/2026/{eid}.md")
    assert "priority" not in codes(r) and "block" not in codes(r) and "schema" not in codes(r)
    msgs = [f.message for f in run(book_dir, f"entries/2026/{bad}.md").findings if f.level == "fail"]
    assert any("todo-nothing" in m for m in msgs)                      # no such open item
    assert any("only an issue or todo with an id" in m for m in msgs)  # a finding has no priority
    assert "schema" in codes(run(book_dir, f"entries/2026/{worse}.md"), "fail")   # not a level
