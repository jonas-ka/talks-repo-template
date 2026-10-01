"""Figures for notes/talks-repo-logbook.typ, drawn at log-book size (7.2 in wide).

Every figure is assembled from PDFs that the repo itself produces (decks, poster), so it
stays vector and can be regenerated:

    uv run python scripts/logbook_figures.py
"""

from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "notes"
W_IN = 7.2  # figure width in inches


def grid_from_pages(src: Path, pages: list[int], cols: int, out: Path, gap: float = 6.0) -> None:
    """Tile pages of `src` (0-based) into one vector PDF page, `cols` per row."""
    doc = pymupdf.open(src)
    # Photos inside the slides are embedded at full resolution; a log-book tile needs
    # ~100 dpi. Text, plots and diagrams stay vector.
    try:
        doc.rewrite_images(dpi_threshold=130, dpi_target=110, quality=70, set_to_gray=False)
    except Exception as exc:  # noqa: BLE001  (older PyMuPDF)
        print("image rewrite skipped:", exc)
    pw, ph = doc[0].rect.width, doc[0].rect.height
    width = W_IN * 72
    cell_w = (width - gap * (cols - 1)) / cols
    cell_h = cell_w * ph / pw
    rows = (len(pages) + cols - 1) // cols
    out_doc = pymupdf.open()
    page = out_doc.new_page(width=width, height=rows * cell_h + gap * (rows - 1))
    for k, p in enumerate(pages):
        r, c = divmod(k, cols)
        rect = pymupdf.Rect(c * (cell_w + gap), r * (cell_h + gap), c * (cell_w + gap) + cell_w, r * (cell_h + gap) + cell_h)
        page.show_pdf_page(rect, doc, p)
        page.draw_rect(rect, color=(0.75, 0.75, 0.75), width=0.4)
    out_doc.save(out, garbage=3, deflate=True)
    print(out.name, f"{len(pages)} pages from {src.name}")


def main() -> None:
    colloq = next((ROOT / "talks/2026-11-triumf-colloquium").glob("*.pdf"))
    grid_from_pages(colloq, list(range(2, 9)), 3, NOTES / "fig-triumf-intro.pdf")    # slide 3, steps 1-7
    grid_from_pages(colloq, [9, 10, 11, 13, 15, 16], 3, NOTES / "fig-triumf-hfs.pdf")  # hyperfine slides
    radis = next((ROOT / "talks/2026-09-test-radis").glob("*.pdf"), None)
    if radis is not None:
        grid_from_pages(radis, [0, 1, 2, 3], 2, NOTES / "fig-theme-radis.pdf")
    poster = ROOT / "talks/2026-10-tamus-ai-poster/UNI-System-AI-Poster-YourName.pdf"
    if poster.exists() and not (NOTES / "fig-poster-draft.pdf").exists():
        grid_from_pages(poster, [0], 1, NOTES / "fig-poster-draft.pdf")   # the 2026-09-29 draft, kept as history
    if poster.exists():
        grid_from_pages(poster, [0], 1, NOTES / "fig-poster-revised.pdf")
    nvidia = next((ROOT / "talks/2026-09-nvidia-vision").glob("*.pdf"), None)
    if nvidia is not None:
        grid_from_pages(nvidia, [0, 2, 4, 6, 8, 10], 3, NOTES / "fig-nvidia-aws.pdf")


if __name__ == "__main__":
    main()
