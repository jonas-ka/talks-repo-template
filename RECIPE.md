# The recipe: reproducible talks with Claude Code

This is how the pipeline in this repository came to be, in the order it happened, with the
prompts that worked and the mistakes that taught something. It took about two weeks of
sessions in September 2026, starting from sixty-odd old decks in three folders. Nothing in it
needs a large team; it needs a clear brief, a few hard rules, and a habit of reviewing.

## 0. Before the first prompt: write CLAUDE.md

Claude Code reads `CLAUDE.md` at the start of every session. Ours began as one page and
grew with every lesson. The parts that paid off most:

- **Hard rules** that never bend: input folders are read-only; the shared drive is append-only;
  credentials are never committed or echoed; every figure has alt text or the build fails;
  a superseded figure can never appear in a new talk; the repo stays private.
- **Working style**: answer questions before making changes; ask before deleting; explain
  in plain language and define terms; commit after each stage; every stage writes a review
  sheet the author corrects before the next stage runs, and corrections flow back into the
  manifests, never only into the sheet.
- **Schemas** for every YAML file (the talk spine, the file inventory, the catalog, the brief,
  the block header), written down once so every stage agrees.
- **Lessons**, appended as they came: the Typst/Touying pitfalls below, the font quirks, the
  layout rule.

Prompt that started it: *"Read PROJECT_PLAN.md. Before any pipeline stage, tell me what you
will do and which files you will write; ask before deleting anything; keep every stage
resumable from its manifest."*

## 1. Ingest what exists (Stages A–D)

1. **The spine** (`talks.yaml`): one entry per talk ever given, from the CV's presentation list.
   *"Parse the Presentations section of my CV into talks.yaml with the schema in CLAUDE.md;
   keep the CV index as the merge key."*
2. **Discover** every deck-like file in the input folders (`files.yaml`): type, pages, first
   title, geometry, text density, whether it is the author's own, cloud-only placeholders
   flagged rather than downloaded. Then **match** files to talks with a confidence and a review
   sheet. *"Match files to talks; write review/stage-c-matches.csv; I will correct it, then
   you apply my corrections to files.yaml."*
3. **Enrich** durations, audiences and formats from the event web pages.
4. **Export** every matched deck to `archive/<talk-id>/` (PDF; the editable original stays
   where it is; Keynote via AppleScript, Google Slides via the API).

Lesson: priorities first. We said "newest institution first, PhD-era decks last and only for
their plots", and the pipeline took a third of the time it would have otherwise.

## 2. Extract and describe every figure (Stages E–G)

- **Extract** slides, pictures and *build sequences* (the author's habit of animating by
  duplicating a slide with small changes: a run of near-identical slides becomes one block
  with build stages).
- **Classify** every picture with Claude's vision API (plot / schematic / photo / equation /
  logo / screenshot, a caption, alt text, the LaTeX of an equation when visible) in one batch.
- **Equations** come from the sources first: Keynote keeps the LaTeX inside its package;
  Google Slides decks carry it in the speaker notes; vision is the last resort.
- **Catalog** (`assets/catalog.yaml`): one entry per unique figure, deduplicated across decks
  by perceptual hash, with provenance (talk, slide, archive path), caption, alt text, uses,
  `supersedes` suggestions for look-alikes. Vector originals stay vector (PDF) with an SVG
  twin for Typst, which refuses embedded PDFs in tagged output.

Prompt pattern that kept quality up: *"Write the review sheet first; I will mark wrong
captions and swaps; apply my marks to the catalog and show me the diff."* The draft captions
were right nine times in ten; the tenth was worth the review (two cyclotron photos had their
labels swapped — caught because the author's own slide labelled them).

## 3. The theme

Derived from the author's three most recent decks, not invented: fonts (STIX Two Text /
Math), the lab palette with measured WCAG contrast ratios (`themes/palette.yaml`), the
style-guide tokens (panel tints, line colours, radii, shadows), slide header and footer,
sponsor logos only where a block declares them, slide titles in Title Case, one figure per
slide, captions one line at 11 pt. Everything compiles with `--pdf-standard ua-1`: a failed
validation is a failed build. A poster theme followed from the same tokens (A0, 30 pt body,
cards in rows with aligned edges, one gutter everywhere).

## 4. Blocks

A block is one Typst file with a tagged header (`id`, `title`, `topic`, `level`, `minutes`,
`order`, `requires`, `assets`, `section`, `sponsors`, `source`) and one or a few slides.
Figures are placed by catalog id (`#cat-fig("id")`), so alt text and file come from the
catalog and a superseded id fails the build. Blocks were first proposed by the pipeline from
recurring slide titles across the archived decks, then written by hand for new material.

## 5. A new talk

`talks/<slug>/brief.yaml` (title, date, event, duration, audience, topics, abstract, notes)
→ `talks generate <slug>`: blocks whose level fits the audience and whose minutes fit the
budget, `requires` resolved transitively, `main.typ` written, the PDF compiled (UA-1) and the
HTML exported, `report.md` with the block list, the timing, the asset problems, the research
updates since the last talk on these topics, and the **layout flags** of every page. Then the
author edits `main.typ` or the blocks, and the generator never overwrites edits without
`--force`.

## 6. The layout pass (the rule we added after a month of top-down slides)

Content written top to bottom and left there leaves a blank band above the footer and
columns of unequal height. The rule, now in `CLAUDE.md`: *every new or changed slide ends
with a render, a look, and adjustments* — paragraph and bullet gaps of 10–13 pt at body size,
the body filling the page, figures and captions aligned, one caption line. `talks layout`
measures the blank band and the column imbalance per page and flags > 18 % / > 25 %. Same
for posters: cards in a row get the row's height, every gap is the same gutter, the page is
filled so the bottom margin matches the sides.

## 7. Exports people can use

- **HTML**: one inline SVG per slide, so animated GIFs keep moving.
- **PPTX for Google Slides** (`talks pptx`): not pictures of slides. Every text line of the
  PDF becomes a native text box (font, size, weight, colour, links), every photo a picture
  shape, and only the vector art is rendered as a background. Bold had to be recovered from
  glyph widths because a variable font embeds regular and bold under one name; word gaps
  between differently styled spans had to be put back because Typst positions words rather
  than emitting spaces. Verified against a PowerPoint render: 61 of 62 lines within 1.5 pt.
- **Publish**: the PDF, PPTX and HTML go to the author's talks folder on Drive, create-only.

## 8. The figure library and the log book

Two side effects turned out to be the most valuable parts for the group.

- **The figure library** on the shared drive: one folder per figure with PDF, SVG, PNG
  (300 dpi), `code/`, `data/` and `figure.yaml`; the latest version at the top level, earlier
  versions in dated subfolders, variants beside them; style rules (lab colours, full box,
  black bold labels, legend inside, text never on data). `docs/FIGURES_README.md`.
- **The log book** (`docs/LOGBOOK_GUIDE.md`, `docs/labnotes-template.typ`): one Typst file,
  one entry per day with notes per project, decision / finding / issue / todo boxes, the
  numbers, the reasons, the dead ends — the material of a methods chapter that lives
  nowhere else. Prompt: *"Write a lab notebook for this repo; backfill it from our
  conversation and the git log; if the chat was compacted, the git log fills the gaps."*
  Then, after every substantial session: *"add a log-book entry."*

## By the numbers (from the log book of the first two weeks)

- Day 1 (17 Sep): plan, `CLAUDE.md`, the spine from the CV (67 presentations, 0 unparsable
  lines, 19 rows flagged and checked), discovery (864 files, 281 decks, 212 the author's own,
  41 of 67 talks attached automatically, 50 after hand corrections), enrichment, the archive
  export, extraction and classification on five test decks, the accessibility spike, the
  theme from three reference decks.
- Day 2 (18 Sep): the full catalog (Phase 0 complete) and the first real deck end to end.
- Keynote export: the batch stopped after three failures until the exporter opened files the
  way a double-click does (`open -a Keynote`): then 32 of 32 decks, 1192 slides, 0 failures.
- Google Slides through the API: 10 decks, 279 slides, 1003 original images, 571 of them
  already carrying alt text (often the original file name — free provenance), 5 speaker notes
  with the LaTeX of the equations exactly as typed.
- Deduplication before spending: 887 picture uses → 493 unique images (exact and perceptual
  hash); the sample classification batch cost $4.58 for 464 images (Batch API, half price),
  mean confidence 0.89; a cluster id that could change when a better original appeared was
  fixed *before* the full run, so nothing was classified twice.
- Equations: 87 unique across 45 talks; 430 uses traced to Keynote's own LaTeX, 58 to speaker
  notes, 10 needed vision; all 87 rendered with Typst + mitex 0.2.7.
- Archive binaries (2.7 GB; 1.6 GB of PDFs) stay out of git and regenerate in fifteen minutes.
- The first poster went through three review rounds in a day (empty band, <20 pt text, low
  resolution rasters, rules through descenders, uneven rows); the fixes became the poster
  theme's rules (card rows, one gutter, fill to the margin, text sizes, pphoto, stat-row).

## Pitfalls worth knowing before they cost you an afternoon

- Touying reveal markers (`only`, `uncover`, `pause`) must sit at the top level of a slide or
  a composer column; inside a box or a function they panic.
- `layout` reports the full body height including the header; use fixed column heights.
- `#set par(spacing: 0pt)` (needed between reveal slots) removes the default paragraph gap
  for the whole column; add `v()` or `block(below:)` explicitly.
- `measure` of a %-width is zero outside `layout`; an image with only a width collapses
  inside a zero-height box; inline math wraps in a zero-width `place`.
- Tagged PDF (UA-1) refuses embedded PDF images and bare `$…$` without alt text; a deck
  without a title slide needs its first slide title promoted to heading level 1.
- `*strong*` in Touying goes through the theme's `alert` (ours is bold italic by design);
  upright bold is `text(weight: "bold")`.
- Typst's font subsets have no `OS/2` or `cmap` tables; a variable font's bold is only
  recognisable by its glyph advances.
- Fonts missing a glyph (✓ ✗) fall back to a system font that other machines do not have;
  map it on export.
- Numbers on slides: print each with its label before it goes on a slide; two numbers read
  off one bare shell output got swapped once ("130 commits" was the count of figure folders).
- Thumbnails of pages are rasters on purpose, sized to ~300 ppi of their *placed* size.
- Cloud-synced folders (Drive, iCloud) hold undownloaded placeholders; a scan must skip and
  flag them, and a person downloads the folder rather than a script pulling gigabytes.
- Keynote's PPTX export rasterises inserted PDFs, but the originals survive inside the `.key`
  package; Google Slides' PPTX and PDF exports are unreliable, the Slides API is not.
- The author's "animations" were consecutive near-identical slides; treat a run as one block
  with build stages, and take the figure from the last stage.
- A session's context gets summarised when it grows; the git log and the log book carry over.
