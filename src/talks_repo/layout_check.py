"""Layout check of a compiled deck: how well each slide uses its space.

Slides written top-down tend to leave a blank band above the footer or one column
much shorter than the other. This module measures, per page of the deck's PDF:

* the body region (between the header rule and the footer rule of the theme),
* the lowest content edge in the left and right halves (text, images, vector drawings),
* the empty band at the bottom as a share of the body height,
* the imbalance between the two halves, and
* the words of body text (spans of at least `BODY_PT`, so captions, footnotes and figure
  labels do not count): a slide above `TEXT_HEAVY_WORDS` is text-heavy and is flagged
  with a target 10 % below its count (the author, 2026-10-07: "reduce the text density on the
  text-heavy slides by 10 %"); cutting it again on the next pass continues until it is
  under the threshold.

    talks layout <slug>            table per page, flags where a slide needs a second look
    talks layout <slug> --png      also writes page renders to talks/<slug>/png/ for the eye

Thresholds (`EMPTY_MAX`, `IMBALANCE_MAX`) are advisory: a title-like slide or a single
short statement may be fine. The numbers say where to look; the render decides.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf

from talks_repo import REPO_ROOT

EMPTY_MAX = 0.18       # more than this share of the body height blank at the bottom
IMBALANCE_MAX = 0.25   # left and right halves ending more than this share apart
TEXT_HEAVY_WORDS = 120  # body words above which a slide is text-heavy: 12 of 155 content slides on 2026-10-07 (median 43, p90 101, max 179)
TEXT_CUT = 0.10         # a text-heavy slide loses at least this share of its words
BODY_PT = 11.5          # spans at least this large count as body text
FOOTER_BAND = 40.0     # pt above the page bottom that belongs to the footer
HEADER_BAND = 50.0     # pt below the page top that belongs to the header


@dataclass
class PageLayout:
    page: int
    body_top: float
    body_bottom: float
    left_bottom: float
    right_bottom: float
    empty: float          # share of the body height blank at the bottom
    imbalance: float      # |left - right| / body height
    n_text_lines: int
    n_images: int
    words: int = 0              # body words (spans >= BODY_PT inside the body region)

    title_slide: bool = False   # the theme's title slide: a grey band over the top half; not judged

    @property
    def flags(self) -> list[str]:
        f = []
        if self.title_slide:
            return f
        if self.empty > EMPTY_MAX:
            f.append(f"{self.empty:.0%} of the body blank at the bottom")
        if self.imbalance > IMBALANCE_MAX:
            short = "right" if self.right_bottom < self.left_bottom else "left"
            f.append(f"{short} column ends {self.imbalance:.0%} of the body higher")
        if self.words > TEXT_HEAVY_WORDS:
            f.append(f"text-heavy ({self.words} words > {TEXT_HEAVY_WORDS}): cut to <= {self.word_target} words")
        return f

    @property
    def word_target(self) -> int:
        """10 % fewer words than now (never above the threshold's own count)."""
        return int(self.words * (1 - TEXT_CUT))


def _rules(page: pymupdf.Page) -> tuple[float, float]:
    """Header and footer rule positions: the two widest thin horizontal drawings."""
    W, H = page.rect.width, page.rect.height
    wide = [d["rect"] for d in page.get_drawings()
            if d["rect"].width > 0.8 * W and d["rect"].height < 2]
    top = min((r.y1 for r in wide if r.y0 < HEADER_BAND * 1.6), default=HEADER_BAND)
    bottom = max((r.y0 for r in wide if r.y0 > H - FOOTER_BAND * 1.6), default=H - FOOTER_BAND)
    return top, bottom


def measure_page(page: pymupdf.Page, pno: int) -> PageLayout:
    W = page.rect.width
    top, bottom = _rules(page)
    body_h = max(bottom - top, 1.0)
    boxes: list[pymupdf.Rect] = []
    n_text = 0
    words = 0
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            r = pymupdf.Rect(line["bbox"])
            if r.y0 > top + 2 and r.y1 < bottom - 2 and "".join(s["text"] for s in line["spans"]).strip():
                boxes.append(r)
                n_text += 1
                words += len(" ".join(sp["text"] for sp in line["spans"] if sp["size"] >= BODY_PT).split())
    images = [pymupdf.Rect(i["bbox"]) for i in page.get_image_info()]
    images = [r for r in images if r.y0 > top + 2 and r.y1 < bottom - 2]
    boxes += images
    for d in page.get_drawings():
        r = d["rect"]
        if r.y0 > top + 2 and r.y1 < bottom - 2 and r.width > 2 and r.height > 2:
            boxes.append(r)
    title = any(d["rect"].width > 0.9 * W and d["rect"].height > 0.4 * page.rect.height and d.get("fill") is not None
                for d in page.get_drawings())
    mid = W / 2
    left = [r.y1 for r in boxes if r.x0 < mid]
    right = [r.y1 for r in boxes if r.x1 > mid]
    lb = max(left, default=top)
    rb = max(right, default=top)
    content_bottom = max(lb, rb)
    return PageLayout(pno, top, bottom, lb, rb, (bottom - content_bottom) / body_h,
                      abs(lb - rb) / body_h, n_text, len(images), words=words, title_slide=title)


def check(pdf: Path, png: bool = False) -> list[PageLayout]:
    doc = pymupdf.open(pdf)
    out = []
    png_dir = pdf.parent / "png"
    if png:
        png_dir.mkdir(exist_ok=True)
    for i, page in enumerate(doc, start=1):
        out.append(measure_page(page, i))
        if png:
            page.get_pixmap(dpi=110).save(png_dir / f"{pdf.stem}-layout-p{i:02d}.png")
    return out


def report(pages: list[PageLayout]) -> str:
    lines = [f"{'page':>4}  {'empty':>6}  {'L end':>6}  {'R end':>6}  {'imbal':>6}  {'lines':>5}  {'words':>5}  {'imgs':>4}  note"]
    for p in pages:
        lines.append(f"{p.page:>4}  {p.empty:>6.0%}  {p.left_bottom:>6.0f}  {p.right_bottom:>6.0f}  "
                     f"{p.imbalance:>6.0%}  {p.n_text_lines:>5}  {p.words:>5}  {p.n_images:>4}  {'; '.join(p.flags)}")
    flagged = [p for p in pages if p.flags]
    lines.append(f"{len(flagged)} of {len(pages)} pages flagged (empty > {EMPTY_MAX:.0%}, imbalance > {IMBALANCE_MAX:.0%}, "
                 f"or text-heavy > {TEXT_HEAVY_WORDS} body words); positions in pt from the page top.")
    return "\n".join(lines)
