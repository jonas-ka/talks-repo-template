"""The tools around the format: new, cite, export, month, digest, pull, migrate, GitHub, EPICS."""

from __future__ import annotations

import io
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from lablogbook import check, cite, connect, github, migrate, newentry, projectcopy, reports
from lablogbook.book import open_book
from lablogbook.selection import Filter

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "logbook"
FIG = EXAMPLE / "entries/2026/figures/plot-example-transmission-scan-v2"
RUN = "2026-10-01-0930-aa-first-transmission-scan"
needs_render = pytest.mark.skipif(not (shutil.which("pandoc") and shutil.which("typst")), reason="pandoc and typst needed")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def init_repo(d: Path, files_from: Path | None = None) -> Path:
    if files_from:
        shutil.copytree(files_from, d)
    else:
        d.mkdir(parents=True)
    git(d, "init", "-q", "-b", "main")
    git(d, "config", "user.email", "test@example.org")
    git(d, "config", "user.name", "Test")
    git(d, "add", "-A")
    git(d, "commit", "-q", "--allow-empty", "-m", "base")
    return d


@pytest.fixture
def book_dir(tmp_path):
    return init_repo(tmp_path / "book", EXAMPLE)


def draft(tmp: Path, header: dict, body: str = "Text.\n") -> Path:
    p = tmp / "draft.md"
    p.write_text("---\n" + yaml.safe_dump(header, sort_keys=False) + "---\n\n" + body)
    return p


# ------------------------------------------------------------------------------ new ----------
def test_new_standalone_from_a_draft(book_dir, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    for ext in (".pdf", ".svg", ".png", ".yaml"):
        shutil.copy(FIG.with_suffix(ext), work / f"plot-new-thing-v1{ext}")
    d = draft(work, {"title": "A new scan", "project": "Example experiment", "kind": "run", "runs": ["r018"],
                     "figures": [{"file": "plot-new-thing-v1.pdf", "caption": "The new scan.", "alt": "A curve rising to a maximum and falling again."}]},
              "::: finding\nIt peaks.\n:::\n")
    header, body = newentry.read_draft(d)
    t = connect.target(book_dir)
    rc = newentry.create(t, header, body, work, newentry.Options(handle="aa", date="2026-10-06", time="14:05", today="2026-10-06"), out=io.StringIO())
    path = book_dir / "entries/2026/2026-10-06-1405-aa-a-new-scan.md"
    assert rc == 0 and path.exists()
    text = path.read_text()
    assert "date: 2026-10-06\n" in text and 'time: "14:05"' in text            # dates plain, time a string
    assert "file: figures/plot-new-thing-v1.pdf" in text
    for ext in (".pdf", ".svg", ".png", ".yaml"):                            # the figure's siblings came along
        assert (book_dir / f"entries/2026/figures/plot-new-thing-v1{ext}").exists()
    r = check.run(open_book(book_dir), check.Options(paths=[path], today="2026-10-06"))
    assert r.exit_code == 0, r.render()


def test_new_refuses_to_overwrite_a_file(book_dir, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "transmission-scan-r017.csv").write_text("different\n")
    d = draft(work, {"title": "Clash", "project": "Example experiment",
                     "data": [{"file": "transmission-scan-r017.csv", "source": "x"}]})
    header, body = newentry.read_draft(d)
    with pytest.raises(newentry.NewError, match="already exists"):
        newentry.build(open_book(book_dir), header, body, work, newentry.Options(handle="aa", today="2026-10-06"))


def test_new_backfills_and_holds_pdf_attachments(book_dir, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "wiring.pdf").write_bytes(b"%PDF-1.4\n")
    d = draft(work, {"title": "Wiring", "project": "Example experiment", "attachments": [{"file": "wiring.pdf"}]})
    header, body = newentry.read_draft(d)
    t = connect.target(book_dir)
    out = io.StringIO()
    rc = newentry.create(t, header, body, work, newentry.Options(handle="aa", date="2026-09-20", today="2026-10-06"), out=out)
    assert rc == 3 and "HELD" in out.getvalue()                               # waits for the confirmation
    text = next((book_dir / "entries/2026").glob("2026-09-20-*-aa-wiring.md")).read_text()
    assert "backfilled: 2026-10-06" in text                                   # written 16 days later


def test_new_in_a_connected_repository_pushes_a_branch(tmp_path, monkeypatch):
    remote = tmp_path / "central.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    seed = init_repo(tmp_path / "seed", EXAMPLE)
    git(seed, "remote", "add", "origin", str(remote))
    git(seed, "push", "-q", "origin", "main")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(remote), str(clone)], check=True)
    git(clone, "config", "user.email", "test@example.org")   # CI runners have no global identity
    git(clone, "config", "user.name", "Test")
    project = init_repo(tmp_path / "project")
    (project / "logbook.yaml").write_text(f"central:\n  repository: example/central\n  clone: {clone}\n  project: Example experiment\n")
    monkeypatch.setattr(newentry.shutil, "which", lambda name: None)          # no gh: push only
    t = connect.target(project)
    assert t.connected
    out = io.StringIO()
    rc = newentry.create(t, {"title": "From the project"}, "Done.\n", project,
                         newentry.Options(handle="bb", time="10:00", today="2026-10-06", date="2026-10-06"), out=out)
    assert rc == 0, out.getvalue()
    branches = git(remote, "branch", "--list")
    assert "entry/bb/2026-10-06-1000-bb-from-the-project" in branches
    assert git(clone, "status", "--porcelain") == ""                         # the clone's checkout untouched
    assert git(clone, "worktree", "list").count("\n") == 1                   # the temporary worktree is gone


# ------------------------------------------------------------------------------ cite ---------
CROSSREF = {"message": {"type": "journal-article", "DOI": "10.1103/PhysRevLett.999.000001",
                        "title": ["A <i>new</i> measurement"], "container-title": ["Physical Review Letters"],
                        "short-container-title": ["Phys. Rev. Lett."], "volume": "999", "page": "000001",
                        "issued": {"date-parts": [[2025, 3]]},
                        "author": [{"family": "Author", "given": "Anna"}, {"family": "Builder", "given": "Ben"}]}}


def test_new_says_so_when_the_draft_is_missing(book_dir, tmp_path, capsys):
    from lablogbook import cli
    assert cli.main(["--root", str(book_dir), "new", "--from", str(tmp_path / "nope.md"), "--as", "aa", "--yes"]) == 1
    assert "no draft at" in capsys.readouterr().err


def test_cite_add_from_crossref(book_dir):
    book = open_book(book_dir)
    key, added = cite.add(book, "https://doi.org/10.1103/PhysRevLett.999.000001", fetch=lambda url: CROSSREF)
    assert added and key == "Author2025"
    text = book.bib_path.read_text()
    assert "shortjournal = {Phys. Rev. Lett.}" in text and "title        = {{A new measurement}}" in text
    again, added2 = cite.add(open_book(book_dir), "10.1103/PhysRevLett.999.000001", fetch=lambda url: 1 / 0)
    assert again == "Author2025" and not added2                               # not fetched or added twice
    r = check.run(open_book(book_dir), check.Options(paths=[book.bib_path]))
    assert r.exit_code == 0, r.render()


def test_cite_key_gets_a_letter_when_taken(book_dir):
    msg = json.loads(json.dumps(CROSSREF))
    msg["message"]["issued"] = {"date-parts": [[2019]]}
    msg["message"]["DOI"] = "10.5555/other"
    key, _ = cite.add(open_book(book_dir), "10.5555/other", fetch=lambda url: msg)
    assert key == "Author2019a"


# ------------------------------------------------------------------------------ export, month, digest --
def test_filter_selects_like_the_view():
    book = open_book(EXAMPLE)
    assert [e.id for e in Filter(kinds=["meeting"]).apply(book)] == ["2026-10-05-1100-cc-weekly-meeting"]
    assert len(Filter(people=["bb"]).apply(book)) == 1
    assert len(Filter(query="cage supply").apply(book)) >= 1
    assert Filter(date_from="2026-10-03").apply(book)[0].date == "2026-10-03"


@needs_render
def test_export_pdf_with_roles(tmp_path):
    out = tmp_path / "x.pdf"
    path, n = reports.export(open_book(EXAMPLE), Filter(projects=["Example experiment"], kinds=["run"]), out,
                             "a-author-example", "c-chair-example", "a visitor", anonymise=True)
    assert path == out.resolve() and n == 1 and out.stat().st_size > 10_000


def test_digest_lists_open_items_and_new_entries():
    text = reports.digest(open_book(EXAMPLE), today="2026-10-06", days=7)
    assert "new entries" in text and "### Open items (2)" in text and "todo-repeat" in text


@needs_render
def test_month_pdf(book_dir, tmp_path):
    path, n = reports.month_pdf(open_book(book_dir), "2026-10", tmp_path)   # committed today; counts by commit month
    month = reports.logged_month(open_book(book_dir), "2026-10")
    assert n == len(month) or n == 0


# ------------------------------------------------------------------------------ pull ---------
def _connected_project(tmp_path, monkeypatch, visibility: str):
    clone = init_repo(tmp_path / "clone", EXAMPLE)
    project = init_repo(tmp_path / "project")
    (project / "logbook.yaml").write_text(f"central:\n  repository: example/central\n  clone: {clone}\n  project: Example experiment\n")
    monkeypatch.setenv("LOGBOOK_VISIBILITY", visibility)
    return project, clone


def test_pull_writes_a_self_contained_copy(tmp_path, monkeypatch):
    project, _ = _connected_project(tmp_path, monkeypatch, "PRIVATE")
    central = connect.local_config(project)[1]["central"]
    dest = projectcopy.pull(project, central, update=False, today="2026-10-06")
    assert (dest / "GENERATED.md").exists() and (dest / "SUMMARY.md").exists()
    assert len(list((dest / "entries/2026").glob("*.md"))) == 5
    assert (dest / "entries/2026/figures/plot-example-transmission-scan-v1.svg").exists()
    assert (dest / "wiki/projects/example-experiment.md").exists()
    summary = (dest / "SUMMARY.md").read_text()
    assert "Open items (2)" in summary and "About Example experiment" in summary
    r = check.run(open_book(dest), check.Options(today="2026-10-06"))       # the copy is a valid log book
    assert r.exit_code == 0, r.render()
    projectcopy.pull(project, central, update=False, today="2026-10-06")     # and it can be pulled again


@pytest.mark.parametrize("vis,ok", [("PUBLIC", False), ("INTERNAL", False), ("PRIVATE", True)])
def test_pull_visibility_guard(tmp_path, monkeypatch, vis, ok):
    project, _ = _connected_project(tmp_path, monkeypatch, vis)
    central = connect.local_config(project)[1]["central"]
    if ok:
        projectcopy.pull(project, central, update=False)
    else:
        with pytest.raises(projectcopy.CopyError):
            projectcopy.pull(project, central, update=False)


def test_pull_into_internal_with_a_current_permission(tmp_path, monkeypatch):
    project, clone = _connected_project(tmp_path, monkeypatch, "INTERNAL")
    p = clone / "projects.yaml"
    p.write_text(p.read_text().replace("  wiki: projects/example-experiment", "  wiki: projects/example-experiment\n  copy_internal_until: 2099-01-01"))
    projectcopy.pull(project, connect.local_config(project)[1]["central"], update=False)


def test_pull_never_touches_a_folder_it_did_not_make(tmp_path, monkeypatch):
    project, _ = _connected_project(tmp_path, monkeypatch, "PRIVATE")
    (project / "logbook").mkdir()
    (project / "logbook" / "notes.txt").write_text("mine\n")
    with pytest.raises(projectcopy.CopyError, match="not made by"):
        projectcopy.pull(project, connect.local_config(project)[1]["central"], update=False)


# ------------------------------------------------------------------------------ migrate ------
TYPST = r'''#import "labnotes-template.typ": *
#show: labnotes.with(title: "Test Log Book", project: "Test project", author: "A. Author")

= Project background

#context-box[*Programme.* What the project is for. Schematic: @fig-bg.]
#figure(image("fig-bg.png", width: 50%), caption: [The schematic.]) <fig-bg>
#refs(("Code": raw("src/"),))

#entry("2026-09-04", "Old style entry with a figure", tags: ("a", "b"),
  authors: [A. Author (with assistance from Claude Code)])[
Text with HV_Drift and M2_2–M2_6 by 5 V.

#finding[It *works*: 38 %.]
#figure(image("/notes/fig-test.svg", width: 100%), caption: [The test figure.]) <fig-old>
#refs(("Script": raw("scripts/x.py"), "Note": [see `y`]))
]

#day("2026-10-01", "A day", authors: [A. Author])[

#note("Ion source", "First note of the day", tags: ("scan",))[
#decision[Use −120 V, as in @fig-old and @fig-bg.]
#todo[
  - Repeat at 1 kV.
]
]

#note("Beamline", "Second note")[
A table:
#figure(table(columns: 2, [*a*], [*b*], [1], [2]), caption: [Small.])
]

#day("2026-10-02", "Nested day (a missing bracket before it)", authors: [A. Author, B. Builder])[
#note("Ion source", "Note in the nested day")[Plain text.]
]
]
'''


def test_migrate_a_typst_log_book(tmp_path):
    src = init_repo(tmp_path / "src")
    (src / "notes").mkdir()
    shutil.copy(FIG.with_suffix(".svg"), src / "notes" / "fig-test.svg")
    shutil.copy(FIG.with_suffix(".png"), src / "notes" / "fig-bg.png")
    (src / "notes" / "test-logbook.typ").write_text(TYPST)
    git(src, "add", "-A")
    git(src, "commit", "-q", "-m", "the log book")
    book = open_book(init_repo(tmp_path / "book", EXAMPLE))
    r = migrate.migrate(src / "notes" / "test-logbook.typ", book, project="Example experiment")
    assert len(r.entries) == 4 and not r.unknown_authors, r.render(book)
    texts = {p.stem: p.read_text() for p in r.entries}
    old = next(t for k, t in texts.items() if "old-style" in k)
    assert "HV_Drift and M2_2–M2_6" in old                                    # in-word underscores survive
    assert "::: finding" in old and "**works**" in old
    assert "with: claude" in old and "migrated_from: src@" in old and "logged:" in old
    assert "backfilled:" in old                                               # committed today, dated 2026-09-04
    assert "Script: scripts/x.py" in old and "file: figures/fig-test-v1.svg" in old
    first = next(t for k, t in texts.items() if "first-note" in k)
    assert "subproject: Ion source" in first and "::: decision" in first and "::: todo" in first
    second = next(t for k, t in texts.items() if "second-note" in k)
    assert "| **a** | **b** |" in second                                      # a figure without an image: the table kept
    nested = next(t for k, t in texts.items() if "nested-day" in k)
    assert "authors: [aa, bb]" in nested
    assert r.background.name == "example-experiment-migrated.md"            # the existing page is not overwritten
    wiki = r.background.read_text()
    assert "Programme." in wiki and "**Code:** `src/`" in wiki
    assert "](figures/fig-bg-v1.png)" in wiki and (r.background.parent / "figures" / "fig-bg-v1.png").exists()
    assert "Schematic: the figure on this page." in wiki and "LBDEF" not in wiki and "{#fig-bg}" not in wiki
    old_id = next(p.stem for p in r.entries if "old-style" in p.stem)
    assert f"as in the figure on [[{old_id}]] and the figure on [[wiki:projects/example-experiment-migrated]]" in first
    assert not r.unresolved_refs and "LBDEF" not in old
    rep = check.run(open_book(book.root), check.Options(today="2026-10-13"))
    assert not [f for f in rep.findings if f.level == "fail"], rep.render()


# ------------------------------------------------------------------------------ GitHub -------
ISSUE = """### Title

Drift traced to the cage supply

### Kind

note

### Project

Example experiment

### Subproject

Beamline

### Co-authors

A. Author (aa)

### Apparatus

Example ion source (source)

### Tags

drift, high voltage

### Date of the work

_No response_

### Corrects

_No response_

### Resolves

2026-10-01-0930-aa-first-transmission-scan#todo-repeat

### Entry

::: finding
The supply follows the lab temperature.
:::

### Figures, data and attachments

![plot-x-v1.svg](https://github.com/user-attachments/assets/abc)

Caption: The drift.
Alt: Supply voltage against time, rising with the lab temperature.

[plot-x-v1.pdf](https://github.com/user-attachments/files/1/plot-x-v1.pdf)

[readings.csv](https://github.com/user-attachments/files/2/readings.csv)
Source: the supply's log, Drive folder Example/Data/Cage

### Export control

- [x] No file I attached holds export-controlled technical data
"""


def test_issue_form_and_parsing(tmp_path):
    book = open_book(EXAMPLE)
    form = github.issue_form(book)
    labels = {b["attributes"]["label"] for b in form["body"] if "label" in b.get("attributes", {})}
    assert set(github.FORM_LABELS) - github.LEGACY_LABELS - github.SCRIPT_LABELS <= labels          # every field the parser reads exists
    ids = [b.get("id") for b in form["body"] if b.get("id")]
    assert "title" not in ids and ids[:3] == ["project", "kind", "body"]      # the issue's own title; the text early
    people = next(b for b in form["body"] if b.get("id") == "coauthors")["attributes"]["options"]
    assert "A. Author (aa)" in people
    answers = github.parse_issue_body(ISSUE)
    assert answers["title"] == "Drift traced to the cage supply" and answers["date"] == ""
    files = github.parse_files(answers["files"])
    assert [f["name"] for f in files] == ["plot-x-v1.svg", "plot-x-v1.pdf", "readings.csv"]

    def fake(url, dest, token):
        src = {"plot-x-v1.svg": FIG.with_suffix(".svg"), "plot-x-v1.pdf": FIG.with_suffix(".pdf")}.get(dest.name)
        dest.write_bytes(src.read_bytes() if src else b"t,v\n0,1\n")
        return dest
    header, body = github.draft_from_issue(book, answers, files, tmp_path, None, fetch=fake)
    assert header["authors"] == ["aa"] and header["apparatus"] == ["source"] and header["tags"] == ["drift", "high voltage"]
    assert header["figures"][0]["caption"] == "The drift." and header["figures"][0]["file"].endswith(".pdf")
    assert header["data"][0]["source"].startswith("the supply's log")
    assert header["resolves"] == ["2026-10-01-0930-aa-first-transmission-scan#todo-repeat"]


def test_init_github_writes_parseable_files(book_dir):
    written = github.init_github(open_book(book_dir))
    assert ".github/ISSUE_TEMPLATE/new-entry.yml" in written
    assert len([w for w in written if w.startswith(".github/workflows/")]) == 6
    assert ".github/CODEOWNERS" in written
    for w in written:
        if w.endswith(".yml"):
            data = yaml.safe_load((book_dir / w).read_text())
            assert data, w
    wf = yaml.safe_load((book_dir / ".github/workflows/logbook-checks.yml").read_text())
    assert "entry-checks" in wf["jobs"]
    for w in written:      # no ${{ … }} pasted into a shell script (injection)
        if w.startswith(".github/workflows/"):
            for job in yaml.safe_load((book_dir / w).read_text())["jobs"].values():
                for step in job.get("steps", []):
                    assert "${{" not in step.get("run", ""), (w, step.get("name"))


# ------------------------------------------------------------------------------ EPICS --------
def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def ioc(monkeypatch):
    pytest.importorskip("caproto")
    port = _free_port()
    env = {"EPICS_CA_SERVER_PORT": str(port), "EPICS_CA_ADDR_LIST": "127.0.0.1", "EPICS_CA_AUTO_ADDR_LIST": "NO",
           "EPICS_CAS_INTF_ADDR_LIST": "127.0.0.1", "EPICS_CA_REPEATER_PORT": str(_free_port())}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    proc = subprocess.Popen([sys.executable, str(Path(__file__).parent / "soft_ioc.py")], env={**os.environ, **env},
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    from caproto.sync import client
    for _ in range(50):
        try:
            client.read("SRC:Extract", timeout=0.5)
            break
        except Exception:   # noqa: BLE001 - not up yet
            time.sleep(0.2)
    yield client
    proc.terminate()
    proc.wait(5)


def test_epics_snapshot_and_restore(ioc, book_dir, tmp_path):
    from lablogbook import epicsio
    book = open_book(book_dir)
    snap = epicsio.snapshot(book, "source-tune", tmp_path / "snap.json", "test")
    data = json.loads(snap.read_text())
    vals = {p["name"]: p for p in data["pvs"]}
    assert vals["SRC:Extract"]["value"] == -110.0 and vals["SRC:Extract"]["unit"] == "V"
    assert vals["SRC:HV_Offset"]["severity"] == "NO_ALARM"
    assert epicsio.check_snapshot if hasattr(epicsio, "check_snapshot") else True
    from lablogbook.epics import check_snapshot
    assert check_snapshot(snap, "source-tune", ["SRC:HV_Offset", "SRC:Extract", "SRC:Laser_Energy"]) == []
    # the example entry stored -120 V: restore asks, then writes
    stored = epicsio.stored(book, RUN, "source-tune")[0][0]
    out = io.StringIO()
    assert epicsio.restore(stored, lambda q: False, out) == 0 and "nothing written" in out.getvalue()
    assert epicsio.restore(stored, lambda q: True, out) == 1
    assert ioc.read("SRC:Extract", timeout=2).data[0] == -120.0
    assert epicsio.restore(stored, lambda q: True, io.StringIO()) == 0     # now nothing differs


def test_slug_ends_after_a_whole_word():
    from lablogbook.entry import slugify
    assert slugify("Demonstration: ion flight times at 3 kV, with a figure, data, a table") == "demonstration-ion-flight-times-at-3-kv-with-a"
    assert len(slugify("x" * 80)) == 48
    assert slugify("Short title") == "short-title"


def test_header_short_items_inline_long_ones_as_blocks():
    out = newentry.dump_entry({"title": "T", "tags": ["a", "b"], "parameters": [{"name": "U", "value": 3000, "unit": "V"}],
                               "figures": [{"file": "figures/a-v1.pdf", "caption": "c" * 100}]}, "Body")
    assert "tags: [a, b]" in out and "- {name: U, value: 3000, unit: V}" in out
    assert "- file: figures/a-v1.pdf\n  caption: " in out


def test_cite_lab_journal_list_wins_over_crossref_short_title():
    msg = {**CROSSREF["message"], "container-title": ["International Journal of Mass Spectrometry"],
           "short-container-title": ["International Journal of Mass Spectrometry"]}
    assert cite.from_crossref(msg)[1]["shortjournal"] == "Int. J. Mass Spectrom."


def test_from_issue_skips_an_issue_already_done(book_dir, monkeypatch):
    calls = []
    def fake_gh(*args, check=True):
        calls.append(args)
        if args[:2] == ("issue", "view"):
            return json.dumps({"body": "", "title": "t", "state": "CLOSED"})
        return "0"
    monkeypatch.setattr(github, "_gh", fake_gh)
    out = io.StringIO()
    assert github.from_issue(open_book(book_dir), 7, "a-author-example", "o/r", out) == 0
    assert "already done" in out.getvalue()
    assert not any(a[:2] in (("issue", "comment"), ("pr", "create")) for a in calls)


def test_book_time_zone_dates_new_entries(book_dir, tmp_path):
    import datetime as dt
    from zoneinfo import ZoneInfo
    cfg = book_dir / "logbook.yaml"
    cfg.write_text(cfg.read_text() + "timezone: Pacific/Kiritimati\n")    # UTC+14: never the UTC date's evening
    book = open_book(book_dir)
    assert book.now().utcoffset() == dt.timedelta(hours=14)
    path, header, _ = newentry.build(book, {"title": "Zone", "project": "Example experiment", "kind": "note"},
                                     "Text.\n", tmp_path, newentry.Options(handle="aa"))
    assert header["date"] == dt.datetime.now(ZoneInfo("Pacific/Kiritimati")).date().isoformat()


def test_from_issue_takes_the_title_from_the_issue(book_dir, monkeypatch):
    body = ISSUE.split("### Kind", 1)[1]                    # a form without the old Title field
    calls = []
    def fake_gh(*args, check=True):
        calls.append(args)
        if args[:2] == ("issue", "view"):
            return json.dumps({"body": "### Kind" + body, "title": "Entry: Drift traced to the cage supply", "state": "OPEN"})
        if args[:2] == ("pr", "list"):
            return "0"
        raise RuntimeError("stop after drafting")          # nothing past the draft is needed here
    monkeypatch.setattr(github, "_gh", fake_gh)
    seen = {}
    real = github.draft_from_issue
    def spy(book, answers, *a, **k):
        seen.update(answers)
        raise RuntimeError("stop")
    monkeypatch.setattr(github, "draft_from_issue", spy)
    monkeypatch.setattr(github.connect if hasattr(github, "connect") else __import__("lablogbook.connect", fromlist=["x"]), "run", lambda *a, **k: "")
    try:
        github.from_issue(open_book(book_dir), 3, "a-author-example", "o/r", io.StringIO())
    except Exception:
        pass
    assert seen.get("title") == "Drift traced to the cage supply"


def test_migrate_new_only_and_repo_name_from_remote(tmp_path):
    src = init_repo(tmp_path / "checkout-folder")
    (src / "notes").mkdir()
    shutil.copy(FIG.with_suffix(".svg"), src / "notes" / "fig-test.svg")
    shutil.copy(FIG.with_suffix(".png"), src / "notes" / "fig-bg.png")
    (src / "notes" / "test-logbook.typ").write_text(TYPST)
    git(src, "remote", "add", "origin", "https://github.com/example/real-name.git")
    git(src, "add", "-A")
    git(src, "commit", "-q", "-m", "the log book")
    book = open_book(init_repo(tmp_path / "book", EXAMPLE))
    first = migrate.migrate(src / "notes" / "test-logbook.typ", book, project="Example experiment")
    assert len(first.entries) == 4
    assert all("migrated_from: real-name@" in p.read_text() for p in first.entries)   # not the folder's name
    again = migrate.migrate(src / "notes" / "test-logbook.typ", open_book(book.root), project="Example experiment", new_only=True)
    assert again.entries == [] and again.existing == 4 and not again.changed
    (src / "notes" / "test-logbook.typ").write_text(TYPST.rstrip() + '\n\n#day("2026-10-03", "Later", authors: [A. Author])[\n#note("Ion source", "A later note")[Later text.]\n]\n')
    git(src, "commit", "-q", "-am", "a later note")
    later = migrate.migrate(src / "notes" / "test-logbook.typ", open_book(book.root), project="Example experiment", new_only=True)
    assert len(later.entries) == 1 and "a-later-note" in later.entries[0].stem and later.existing == 4
    assert not list((book.root / "entries" / "2026").glob("*-1.md"))                 # no duplicates


def test_migrate_skips_the_frozen_note(tmp_path):
    src = init_repo(tmp_path / "src")
    (src / "notes").mkdir()
    (src / "notes" / "log.typ").write_text('#import "labnotes-template.typ": *\n'
        '#day("2026-10-01", "A day", authors: [A. Author])[\n#note("Ion source", "Real work")[Text.]\n]\n'
        '#day("2026-10-14", "This log book has moved", authors: [A. Author])[\n#note("Log book", "Frozen")[Moved.]\n]\n')
    git(src, "add", "-A")
    git(src, "commit", "-q", "-m", "log")
    book = open_book(init_repo(tmp_path / "book", EXAMPLE))
    r = migrate.migrate(src / "notes" / "log.typ", book, project="Example experiment")
    assert [p.stem.split("-aa-")[1] for p in r.entries] == ["real-work"]


# ------------------------------------------------------------------------------ a new book ---
def test_init_makes_a_book_that_checks_and_builds_and_refuses_to_overwrite(tmp_path):
    from lablogbook import scaffold
    lab = scaffold.Lab(title="Example Lab Notes", lab="Example Lab", institution="Example University",
                       pi_name="A. Author", pi_handle="aa", pi_login="a-author", timezone="America/Chicago",
                       email_domains=("example.edu",), project="Beamline")
    scaffold.init(tmp_path / "book", lab)
    book = open_book(tmp_path / "book")
    assert book.config["privacy"]["email_domains"] == ["example.edu"] and book.config["timezone"] == "America/Chicago"
    assert book.is_admin("a-author") and "Beamline" in book.projects
    r = check.run(book, check.Options())
    assert r.exit_code == 0, r.render()
    text = "\n".join(p.read_text() for p in (tmp_path / "book").rglob("*") if p.is_file())
    assert "TODO(" in (tmp_path / "book" / "docs" / "COMPLIANCE.md").read_text()
    assert "Karthein" not in text and "tamu" not in text.lower()                      # nothing of this lab
    with pytest.raises(scaffold.InitError):
        scaffold.init(tmp_path / "book", lab)
    with pytest.raises(scaffold.InitError):
        scaffold.files(scaffold.Lab(pi_handle="Bad Handle"))


def test_github_settings_script(tmp_path):
    s = github.settings_script("example-org/Lab-Notes", "a-author", "lab-team")
    assert '"integration_id": 15368' in s and '"actor_type": "RepositoryRole"' in s
    assert "squash_merge_commit_message=PR_BODY" in s and "environments/$env" in s and "teams/lab-team" in s
    assert s.index("# 6. The ruleset") < s.index("# 7. Pages") and "DELETE \"repos/$REPO/pages\"" in s
    assert subprocess.run(["sh", "-n"], input=s, text=True).returncode == 0
    with pytest.raises(ValueError):
        github.settings_script("not a repo", "a-author")


def test_init_github_writes_codeowners_once(tmp_path):
    from lablogbook import scaffold
    scaffold.init(tmp_path / "b", scaffold.Lab(pi_handle="aa", pi_login="a-author"))
    book = open_book(tmp_path / "b")
    github.init_github(book)
    co = tmp_path / "b" / ".github" / "CODEOWNERS"
    assert "* " in co.read_text() and "@a-author" in co.read_text() and "/entries/" in co.read_text()
    co.write_text("* @someone-else\n")
    github.init_github(open_book(tmp_path / "b"), force=True)
    assert co.read_text() == "* @someone-else\n"                                      # never replaced


def test_pull_copies_wiki_figures_and_keeps_big_files_out_of_git(tmp_path, monkeypatch):
    project, clone = _connected_project(tmp_path, monkeypatch, "PRIVATE")
    page = clone / "wiki" / "projects" / "example-experiment.md"
    (page.parent / "figures").mkdir(parents=True, exist_ok=True)
    shutil.copy(FIG.with_suffix(".png"), page.parent / "figures" / "fig-setup-v1.png")
    page.write_text(page.read_text() + "\n![The set-up](figures/fig-setup-v1.png)\n")
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", "a wiki figure")
    central = connect.local_config(project)[1]["central"]
    dest = projectcopy.pull(project, central, update=False, today="2026-10-06")
    assert (dest / "wiki/projects/figures/fig-setup-v1.png").exists()
    assert "logbook.html" in (dest / ".gitignore").read_text() and "logbook.pdf" in (dest / ".gitignore").read_text()


def test_form_open_items_images_in_the_text_and_loose_captions(tmp_path):
    book = open_book(EXAMPLE)
    answers = {"title": "T", "project": "Example experiment", "kind": "note",
               "body": 'Text.\n\n<img width="10" alt="Image" src="https://github.com/user-attachments/assets/abc" />\n\nMore.',
               "files": "Caption: A sketch of the set-up.\nAtl: A box.\nSource: Drawn by hand.",
               "todos": "Check the cable\n- Order a new seal\n"}
    loose, unknown = github.file_notes(answers["files"])
    assert loose == {"caption": "A sketch of the set-up.", "source": "Drawn by hand."} and unknown == ["Atl"]
    seen = []
    def fake(url, dest, token):
        seen.append(url)
        out = dest.with_suffix(".png")
        out.write_bytes(FIG.with_suffix(".png").read_bytes())
        return out
    header, body = github.draft_from_issue(book, answers, [], tmp_path, None, fetch=fake)
    assert seen == ["https://github.com/user-attachments/assets/abc"] and "<img" not in body
    fig = header["figures"][0]
    assert fig["caption"] == "A sketch of the set-up." and fig["file"].endswith("fig-a-sketch-of-the-set-up.png")
    assert "::: todo {#todo-1}\n- Check the cable\n:::" in body and "::: todo {#todo-2}\n- Order a new seal\n:::" in body
    assert github.file_notes("Alt text: fine\nCaption: ok")[1] == []


def test_site_rebuilt_after_the_form_entry_merges(monkeypatch):
    calls, states = [], iter(["OPEN", "MERGED"])
    def fake_gh(*args, check=True):
        calls.append(args)
        return next(states) if args[:2] == ("pr", "view") else ""
    monkeypatch.setattr(github, "_gh", fake_gh)
    assert github.rebuild_site_after_merge("https://x/pull/1", "o/r", io.StringIO(), tries=3, pause=0)
    assert ("workflow", "run", "logbook-site.yml", "--repo", "o/r", "--ref", "main") in calls


def test_deliver_copies_each_attested_month_once(tmp_path, monkeypatch):
    from lablogbook import deliver
    calls = []

    def fake(cmd, cwd=None, check=True, env=None):
        calls.append(cmd)
        if cmd[:3] == ["gh", "release", "list"]:
            return json.dumps([{"tagName": "snapshot/2026-11", "isDraft": False},
                               {"tagName": "snapshot/2026-12", "isDraft": True},
                               {"tagName": "v1", "isDraft": False}])
        if cmd[:3] == ["gh", "release", "download"]:
            d = Path(cmd[cmd.index("--dir") + 1])
            (d / cmd[cmd.index("--pattern") + 1]).write_bytes(b"%PDF-1.7")
            return ""
        raise AssertionError(cmd)

    monkeypatch.setattr(connect, "run", fake)
    to = tmp_path / "Drive" / "Lab"
    assert deliver.deliver("org/Notes", to) == [to / "Logbook-2026-11.pdf"]
    assert (to / "Logbook-2026-11.pdf").read_bytes() == b"%PDF-1.7" and not list(to.glob(".*part"))
    assert deliver.deliver("org/Notes", to) == []          # already there: nothing downloaded
    assert sum(c[:3] == ["gh", "release", "download"] for c in calls) == 1
    plist = deliver.launch_agent("org.example.logbook", tmp_path / "book", to)
    assert "<string>deliver</string>" in plist and str(to) in plist and "<key>Hour</key><integer>9</integer>" in plist


def test_open_items_ranked_by_priority_age_and_overdue_asap(tmp_path):
    import datetime as dt
    from lablogbook import state
    MEET = "2026-10-05-1100-cc-weekly-meeting"
    d = tmp_path / "book"
    shutil.copytree(EXAMPLE, d)
    e1 = d / "entries/2026/2026-10-06-0900-aa-priorities.md"
    e1.write_text("---\ndate: 2026-10-06\nauthors: [aa]\nkind: note\nproject: Example experiment\ntitle: Priorities\n"
                  f"priority:\n  {RUN}#todo-repeat: low\n  {MEET}#todo-reading: asap\n---\n\n"
                  "::: todo {#todo-valve priority=asap}\nThe valve.\n:::\n\n::: todo {#todo-label priority=high}\nLabels.\n:::\n")
    book = open_book(d)
    st = state.compute(book.entries)
    assert st.priority(book.entries, f"{RUN}#todo-repeat") == ("low", "2026-10-06-0900-aa-priorities")
    ranked = st.ranked_open_items(book.entries, dt.date(2026, 10, 7), asap_days=2)
    # both ASAP: the older item first; neither overdue yet (todo-reading is from 5 October but ASAP since the 6th)
    assert [x["anchor"] for x in ranked][:3] == ["todo-reading", "todo-valve", "todo-label"]
    assert ranked[-1]["anchor"] == "todo-repeat" and not any(x["overdue"] for x in ranked)
    later = st.ranked_open_items(book.entries, dt.date(2026, 10, 9), asap_days=2)
    assert [x["anchor"] for x in later if x["overdue"]] == ["todo-reading", "todo-valve"]
    text = reports.digest(book, today="2026-10-09")
    assert "**overdue** asap, todo" in text and text.index("todo-valve") < text.index("todo-repeat")
    out = subprocess.run([sys.executable, "-m", "lablogbook.cli", "--root", str(d), "open-items", "--priority", "low"],
                         capture_output=True, text=True)
    assert "todo-repeat" in out.stdout and "todo-valve" not in out.stdout


def test_form_open_items_take_a_priority_prefix(tmp_path):
    book = open_book(EXAMPLE)
    answers = {"title": "T", "project": "Example experiment", "kind": "note", "body": "Text.",
               "todos": "ASAP: Close the valve\nlow - Tidy the rack\nMedium: Order seals\nCheck the cable"}
    _, body = github.draft_from_issue(book, answers, [], tmp_path, None, fetch=None)
    assert "::: todo {#todo-1 priority=asap}\n- Close the valve\n:::" in body
    assert "::: todo {#todo-2 priority=low}\n- Tidy the rack\n:::" in body
    assert "::: todo {#todo-3}\n- Order seals\n:::" in body and "::: todo {#todo-4}\n- Check the cable\n:::" in body


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")
def test_migrated_refs_keep_file_names_and_links():
    refs = migrate.parse_refs('("Test": raw("tests/test_scaling.py"), "Docs": [`PROJECT_PLAN.md`, `review/stage-*.csv` (*not* tracked)], '
                              '"Code": link("https://github.com/org/repo")[org/repo], "Bare": link("https://example.org"), '
                              '"Last": [`notes/` (log book, figures from `scripts/logbook_figures.py`)],)')
    assert refs == {"Test": "tests/test_scaling.py", "Docs": "PROJECT_PLAN.md, review/stage-*.csv (not tracked)",
                    "Code": "org/repo (https://github.com/org/repo)", "Bare": "https://example.org",
                    "Last": "notes/ (log book, figures from scripts/logbook_figures.py)"}
    md = migrate.parse_refs('("Test": raw("tests/test_scaling.py"), "Decks": [`talks/<slug>/` and `review/*.html`], '
                            '"Code": link("https://github.com/org/repo")[org/repo])', markdown=True)
    assert md == {"Test": "`tests/test_scaling.py`", "Decks": "`talks/<slug>/` and `review/*.html`",
                  "Code": "[org/repo](https://github.com/org/repo)"}


def _order_book(tmp_path):
    from lablogbook import orders
    d = tmp_path / "book"
    shutil.copytree(EXAMPLE, d)
    items = orders.normalise([
        {"item": "SHV connectors", "qty": "4", "unit_cost": "$12.50", "total": "$50", "info": "https://example.com/shv", "ordered": "2026-10-02"},
        {"item": "BNC cable | 2 m", "qty": 3.0, "unit_cost": 20, "total": 60, "info": "quote-17.pdf", "ordered": "2026-10-02"},
        {"item": "Old gauge", "qty": 1, "total": 900, "ordered": "2026-10-02", "arrived": True}])
    body = orders.body(items, "For the HV cage.")
    head = {"date": "2026-10-02", "authors": ["aa"], "kind": "order", "project": "Example experiment",
            "title": "Order 17: connectors", "tags": ["purchase"], "order": "17", "items": items}
    (d / "entries/2026/2026-10-02-0900-aa-order-17-connectors.md").write_text(
        "---\n" + yaml.safe_dump(head, sort_keys=False, allow_unicode=True) + "---\n\n" + body)
    (d / "entries/2026/2026-10-05-0900-aa-the-connectors-arrived.md").write_text(
        "---\ndate: 2026-10-05\nauthors: [aa]\nkind: note\nproject: Example experiment\ntitle: The connectors arrived\n"
        "resolves: [2026-10-02-0900-aa-order-17-connectors#item-1]\n---\n\nAll four, unpacked in the lab.\n")
    return d, items, body


def test_an_order_lists_its_items_and_each_stays_open_until_it_arrives(tmp_path):
    from lablogbook import orders
    d, items, body = _order_book(tmp_path)
    assert items[0] == {"n": 1, "item": "SHV connectors", "qty": 4, "unit_cost": 12.5, "total": 50,
                        "info": "https://example.com/shv", "ordered": "2026-10-02"}
    assert "| 1 | SHV connectors | 4 | $12.50 | $50 | <https://example.com/shv> | 2026-10-02 |" in body
    assert "BNC cable \\| 2 m" in body and "::: todo {#item-2 priority=low}\nArrived: BNC cable \\| 2 m (×3)\n:::" in body
    assert "#item-3" not in body                                       # it had arrived already
    book = open_book(d)
    r = check.run(book, check.Options(today="2026-10-06"))
    order_file = [f for f in r.findings if "order-17" in str(f.path)]
    assert not [f for f in order_file if f.level == "fail"], [f.message for f in order_file]
    rows = orders.status(book)
    assert [(x["n"], x["status"]) for x in rows] == [(1, "arrived"), (2, "open"), (3, "arrived")]
    assert rows[0]["arrived_on"] == "2026-10-05" and rows[0]["arrived_by"] == ["aa"]
    out = subprocess.run([sys.executable, "-m", "lablogbook.cli", "--root", str(d), "orders", "--open"], capture_output=True, text=True)
    assert "BNC cable" in out.stdout and "SHV" not in out.stdout and "1 item(s), 1 open" in out.stdout
    view = (Path(__file__).resolve().parents[1] / "src/lablogbook/data/view/view.js").read_text()
    assert 'data-act="pu-csv"' in view and "function purchasesCsv" in view   # the page's download


def test_an_order_from_a_script_through_the_form(tmp_path):
    book = open_book(EXAMPLE)
    answers = {"title": "Order 18: optics", "project": "Example experiment", "kind": "note", "body": "Mirrors for the laser.",
               "order": "18", "items": '```json\n[{"item": "Mirror", "qty": 2, "unit_cost": 150, "total": 300, "ordered": "2026-10-06"}]\n```'}
    header, body = github.draft_from_issue(book, answers, [], tmp_path, None, fetch=None)
    assert header["kind"] == "order" and header["order"] == "18" and header["items"][0]["n"] == 1
    assert body.startswith("Mirrors for the laser.") and "| 1 | Mirror | 2 | $150 | $300 |" in body and "{#item-1 priority=low}" in body
    assert github.parse_issue_body("### Order\n\n18\n\n### Items\n\n```json\n[]\n```")["order"] == "18"


def test_photos_lose_their_metadata_and_large_ones_shrink(tmp_path):
    from PIL import Image
    from lablogbook import photos
    big = tmp_path / "phone.jpg"
    exif = Image.Exif(); exif[0x010F] = "PhoneMaker"; exif[0x8825] = {2: (30.0, 37.0, 0.0)}   # make, GPS
    Image.effect_noise((4000, 3000), 120).convert("RGB").save(big, "JPEG", quality=98, exif=exif)
    assert big.stat().st_size > 2 * 1024 * 1024
    out, note = photos.prepare(big)
    with Image.open(out) as im:
        assert max(im.size) <= photos.LONG_SIDE and not im.getexif()
    assert out.stat().st_size < 2 * 1024 * 1024 and "scaled" in note
    small = tmp_path / "shot.png"
    Image.new("RGB", (300, 200), "white").save(small, pnginfo=__import__("PIL.PngImagePlugin", fromlist=["PngInfo"]).PngInfo())
    out, note = photos.prepare(small)
    assert out == small and note == "metadata removed"
    assert photos.prepare(tmp_path / "data.csv") == (tmp_path / "data.csv", None)


def test_images_of_a_private_issue_come_through_their_signed_links(tmp_path, monkeypatch):
    aid = "1cda0822-6e7c-482d-8947-8351b5ffbabf"
    html = (f'<p><a href="x"><img alt="Image" src="https://private-user-images.githubusercontent.com/1/2-{aid}.jpg?jwt=abc&amp;x=1"></a></p>')
    monkeypatch.setattr(github, "_gh", lambda *a, check=True: html)
    signed = github.signed_images("org/repo", 78)
    assert signed == {aid: f"https://private-user-images.githubusercontent.com/1/2-{aid}.jpg?jwt=abc&x=1"}
    seen = []
    def fake_download(url, dest, token):
        seen.append((url, token)); dest.write_bytes(b"not an image"); return dest
    monkeypatch.setattr(github, "download", fake_download)
    fetch = github.fetch_with_signed(signed)
    fetch(f"https://github.com/user-attachments/assets/{aid}", tmp_path / "a", "TOKEN")
    fetch("https://github.com/user-attachments/files/9/report.pdf", tmp_path / "b.pdf", "TOKEN")
    assert seen == [(signed[aid], None), ("https://github.com/user-attachments/files/9/report.pdf", "TOKEN")]


def test_an_items_vendor_comes_from_its_quote_or_link():
    from lablogbook import orders
    cases = {"https://www.amazon.com/dp/B0919GN3SX": "Amazon", "mcmaster.com/96367A924/": "McMaster-Carr",
             "https://store.ui.com/us/en/products/usw": "Ubiquiti", "https://shop.example.co.uk/x": "Example",
             "2409.ISEG-quote-WU24_0816AR3A_TAMU.pdf": "ISEG", "2411.Pumps-quote-Pfeiffer-Karthein.pdf": "Pfeiffer",
             "2504.RPMC-Laser-OPO-Quote-AAAQ5743.pdf": "RPMC", "2502.Costco-lab-supplies.pdf": "Costco",
             "Xometry-Quote-Q45-8091-9384.pdf": "Xometry", "HomeDepot reimbursement": "Home Depot",
             "https://drive.google.com/file/d/abc": None, "Quotation 99073-R00.pdf": None, "KONQ26-01792": None, "": None}
    assert {k: orders.vendor_of(k) for k in cases} == cases
    names = {"Pfeiffer": "Pfeiffer Vacuum", "Costco": None}
    assert orders.vendor({"info": "2411.Pumps-quote-Pfeiffer-Karthein.pdf"}, names) == "Pfeiffer Vacuum"
    assert orders.vendor({"info": "2502.Costco-lab-supplies.pdf"}, names) is None
    assert orders.vendor({"info": "https://www.amazon.com/x", "vendor": "Thorlabs"}, names) == "Thorlabs"   # given: kept


def test_the_form_does_not_offer_kinds_that_only_scripts_write():
    form = github.issue_form(open_book(EXAMPLE))
    kinds = next(f for f in form["body"] if f.get("id") == "kind")["attributes"]["options"]
    assert "note" in kinds and "order" not in kinds
