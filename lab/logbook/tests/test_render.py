"""The PDF and the HTML view of the example book."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lablogbook import htmlview as html, pdf, render
from lablogbook.book import open_book

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "logbook"
LAB = Path(__file__).resolve().parents[2]
RUN = "2026-10-01-0930-aa-first-transmission-scan"
needs_pandoc = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")
needs_typst = pytest.mark.skipif(shutil.which("typst") is None, reason="typst not installed")


def data_of(page: str) -> dict:
    return json.loads(re.search(r'<script id="lb-data" type="application/json">(.*?)</script>', page, re.S).group(1))


def test_fence_forms_are_normalised_and_ids_prefixed():
    p = render.prepare(open_book(EXAMPLE))
    md = render.prepare_markdown(p, "::: issue {#x}\nA\n:::\n\n::: {.todo #y}\nB\n:::\n\n::: finding\nC\n:::", "E1", EXAMPLE)
    assert "::: {.issue #E1--x}" in md and "::: {.todo #E1--y}" in md and "::: {.finding}" in md


def test_links_become_logbook_links_but_not_in_code():
    p = render.prepare(open_book(EXAMPLE))
    md = render.prepare_markdown(p, f"See [[{RUN}#issue-drift]] and `[[not-a-link]]` and [[wiki:apparatus/source|the source]].", "E1", EXAMPLE)
    assert f"(logbook:entry/{RUN}#issue-drift)" in md
    assert "`[[not-a-link]]`" in md
    assert "[the source](logbook:wiki/apparatus/source)" in md


def test_figure_strip_and_aspect():
    f = render.make_fig("k", EXAMPLE / "entries/2026/figures/plot-example-transmission-scan-v2.pdf", "c", "alt text")
    assert f.strip_in == pytest.approx(0.4)
    assert f.svg is not None and f.w > 0 and f.h_visible > 0
    full = render.svg_size_pt(f.svg)
    assert f.h_visible == pytest.approx(full[1] - 0.4 * 72)


@needs_pandoc
@needs_typst
def test_pdf_builds_under_pdf_ua(tmp_path):
    out = LAB / "build" / "test-example-logbook.pdf"
    try:
        pdf.build(open_book(EXAMPLE), out)
        assert out.stat().st_size > 20_000
        src = out.with_suffix(".typ").read_text()
        assert f"<e-{RUN}>" in src and f"<e-{RUN}--issue-drift>" in src   # link targets
        assert "#issue[" in src and "#finding[" in src                    # the template's callouts
        assert "strip: 0.4in" in src and ".svg" in src                     # strip cut, SVG for PDF/UA
        assert "Corrected by" in src and "Resolves" in src
        assert "= References" in src and "Author A.++ Phys. Rev. Lett. 123, 456 (2019)" in src
    finally:
        out.unlink(missing_ok=True)
        out.with_suffix(".typ").unlink(missing_ok=True)


@needs_pandoc
def test_html_folder_build(tmp_path):
    index = html.build(open_book(EXAMPLE), tmp_path / "site")
    page = index.read_text()
    assert "@@" not in page
    d = data_of(page)
    e = {x["id"]: x for x in d["entries"]}
    run = e[RUN]
    assert 'id="e-' + RUN + '--issue-drift"' in run["html"]
    assert 'class="lb-cite"' in run["html"] and "https://doi.org/10.5555/example.2019.456" in run["html"]
    assert run["resolved"]["issue-drift"] and not run["resolved"]["todo-repeat"]     # one resolved, one open
    assert run["correctedBy"] == ["2026-10-03-1000-aa-scan-step-was-2-v-not-5-v"]
    assert run["epics"][0]["pvs"][1]["name"] == "SRC:Extract"
    assert "Finding" not in run["text"].split("rebuilt")[0]                           # labels not in search text
    figs = re.findall(r'src="(files/[^"]+)"', run["html"])
    assert figs and all((tmp_path / "site" / f).exists() for f in figs) and figs[0].endswith(".svg")
    pngs = re.findall(r'data-png="(files/[^"]+)"', run["html"])        # fallback for browsers without SVG paths
    assert pngs and all((tmp_path / "site" / f).exists() for f in pngs) and pngs[0].endswith(".png")
    assert all(x["data"][0]["url"].startswith("files/") for x in d["entries"] if x["data"])
    assert {w["page"] for w in d["wiki"]} >= {"projects/example-experiment", "apparatus/source"}
    assert len(d["references"]) == 3


@needs_pandoc
def test_html_single_file_embeds_figures(tmp_path):
    out = html.build(open_book(EXAMPLE), tmp_path / "view.html", single=True)
    page = out.read_text()
    assert "data:image/svg+xml;base64," in page and 'src="files/' not in page
    assert not (tmp_path / "files").exists()


@needs_pandoc
def test_cli_build(tmp_path):
    r = subprocess.run(["logbook", "--root", str(EXAMPLE), "build", "--single", str(tmp_path / "v.html")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "v.html").exists()


def test_logo_proportions_decide_the_banner(tmp_path):
    import struct, zlib
    def png(w, h):
        ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
        chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")
    (tmp_path / "wide.png").write_bytes(png(2048, 487))
    (tmp_path / "square.png").write_bytes(png(64, 64))
    (tmp_path / "wide.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1510.13 350"></svg>')
    assert html._image_size(tmp_path / "wide.png") == (2048, 487)
    assert html._image_size(tmp_path / "square.png") == (64, 64)
    assert html._image_size(tmp_path / "wide.svg") == (1510.13, 350)
    assert html._image_size(tmp_path / "missing.png") == (0, 0)


@needs_pandoc
@needs_typst
def test_math_gets_alt_text_under_pdf_ua(tmp_path):
    book = tmp_path / "book"
    shutil.copytree(EXAMPLE, book)
    (book / "entries" / "2026" / "2026-10-07-0900-aa-flight-time.md").write_text(
        "---\ndate: 2026-10-07\ntime: \"09:00\"\nauthors: [aa]\nkind: note\nproject: Example experiment\n"
        "title: Flight time\n---\n\nAn ion of mass $m$ needs\n\n$$t = L \\sqrt{\\frac{m}{2qU}}$$\n")
    out = book / "build" / "out.pdf"
    pdf.build(open_book(book), out)            # PDF/UA-1 fails on an equation without alt text
    src = out.with_suffix(".typ").read_text()
    assert 'alt: "m"' in src and "math.equation(block: true" in src


def test_task_list_boxes_are_drawn_under_pdf_ua(tmp_path):
    book = tmp_path / "book"
    shutil.copytree(EXAMPLE, book)
    (book / "entries" / "2026" / "2026-10-07-0900-aa-checklist.md").write_text(
        "---\ndate: 2026-10-07\ntime: \"09:00\"\nauthors: [aa]\nkind: note\nproject: Example experiment\n"
        "title: Checklist\n---\n\n- [ ] left to do\n- [x] done\n")
    out = book / "build" / "out.pdf"
    pdf.build(open_book(book), out)            # no embedded font has U+2610 and U+2612
    src = out.with_suffix(".typ").read_text()
    assert "\u2610" not in src and "\u2612" not in src and src.count("#box(width: 0.75em") == 2


def test_captions_are_plain_text():
    assert render.plain("The **pinhole**, *very* narrow (`fig-x`); see [the doc](https://x.y); 2*3*4") == \
        "The pinhole, very narrow (fig-x); see the doc; 2*3*4"


@needs_pandoc
@needs_typst
def test_headings_in_an_entry_are_renumbered_without_gaps(tmp_path):
    book = tmp_path / "book"
    shutil.copytree(EXAMPLE, book)
    (book / "entries" / "2026" / "2026-10-07-0900-aa-procedure.md").write_text(
        "---\ndate: 2026-10-07\ntime: \"09:00\"\nauthors: [aa]\nkind: note\nproject: Example experiment\n"
        "title: Procedure\n---\n\nText.\n\n## Procedure\n\nSteps.\n\n#### Detail\n\nMore.\n")
    pdf.build(open_book(book), book / "build" / "out.pdf")   # PDF/UA-1 fails on a skipped heading level
