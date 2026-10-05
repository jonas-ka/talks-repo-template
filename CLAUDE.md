<!-- This is the working CLAUDE.md of the author's private talks repository, exported by
     `talks make-template` with names, paths and ids replaced by <placeholders>. Fill in the
     placeholders, delete what does not apply to you, and keep adding your own lessons: this
     file is what Claude Code reads at the start of every session. The reasoning behind it is
     in RECIPE.md. -->

# talks-repo

Reproducible research-talk slides for <Your Name> (nuclear/AMO physics, <Your University>
<Your Institute>). A new talk is generated from a short brief plus a curated asset
library, seeded by ingesting 60+ past decks. Full plan and rationale: `PROJECT_PLAN.md`.
Read that file before starting any pipeline stage.

## Start here

The ingestion stages (A–G) are finished; a session now usually makes **one talk**, and each
talk gets its own chat. `/new-talk <slug or description>` runs the whole routine
(`.claude/commands/new-talk.md`): brief → `uv run talks generate <slug>` → layout pass on every
page render → report → `talks publish` only when the author says so → log-book entry → commit. The
sections that matter for that: Hard rules, Working style, the `brief.yaml` and block-header
schemas, Slide style (or Posters), Generation workflow, Templates (lab/). Courses and the CV
have their own repositories (`phys206-mechanics`, `phys698-nucl-exp`, `karthein-cv`); themes
live in `lab/` (`jonas-ka/lab-templates`). Pipeline work (new stages, exporters, the template)
belongs in a chat of its own, not in a talk's.

## Hard rules

- **Input folders are read-only.** Never write, move, rename, or delete inside:
  - `<input-folder-1>`
  - `<input-folder-2>`
  - `<input-folder-3>`
- **Ask before deleting or replacing** anything in `archive/` or `assets/`.
- **The lab's shared drive is append-only.** `<LabName>/Figures` and `<LabName>/Photos`
  (Google shared drive, id `<shared-drive-id>`) may be written to through the Drive
  API with `files.create` only, with one exception: a figure's previous version moves into
  its own dated subfolder when a newer version is synced (see the figure library below).
  Never update, rename, trash or delete anything there, never move anything else, and never
  overwrite an existing name: if a name exists, add a suffix. Prefer
  the API over the local CloudStorage mirror, which may hold undownloaded placeholders.
  Layout: one folder per plot or catalog entry directly under `Figures/` or `Photos/`:
  the figure as `<id>.pdf`, `<id>.svg` and `<id>.png` (300 dpi) whenever a vector exists,
  `code/` and `data/` (from `source_dir`, or `code_files`/`data_files` paths that may point
  into a sibling repo for large inputs), and `figure.yaml`, which carries no alt text or
  caption: those are written by the author; the repo catalog keeps ours. The lab uses these
  folders for talks, posters and papers, as they are or modified from the code and data.
  `Figures/README.md` tells lab members how to add a figure by hand. Its canonical source is
  `lab/docs/FIGURES_README.md` in the `lab-templates` repository since 2026-10-02 (before:
  `fastsims/lab/docs/FIGURES_README.md`; the copies in fastsims and ion-optics-surrogate are to be
  replaced by the subtree). Since 2026-10-01 it also fixes the **figure style rules** (lab four colours, black
  bold axis labels, full box, legend inside without frame or labels at the curves, black
  annotation text) and **versioning**: the top level of a figure folder holds the latest version,
  earlier ones move into `v<N>_<YYYY-MM-DD>_<name>/`, variants into `…-poster-version/` in the
  same folder; `figure.yaml` carries `version` and `supersedes`. `talks sync-drive` does this
  (the author, 2026-10-01): when the catalog `version` is newer than the folder's top-level
  `figure.yaml`, the top-level files and `code/`, `data/` move into the dated subfolder and the
  new version is created on top. That move, inside the figure's own folder, is the only write
  besides `files.create`; nothing else is ever moved, renamed or deleted. Copies of the README
  also sit in `Photos/` and `How-tos/Lab-notebook-template/` (with the log-book guide and
  template); re-upload all of them when the canonical file changes.
- **Credentials are never committed or echoed**: `credentials.json`, `token.json`, `.env`,
  API keys. They are read from the environment or `.env` only.
- **Superseded assets never appear in new talks.** If catalog entry B lists
  `supersedes: A`, then A is dead for generation.
- **Every figure and equation has `alt` text.** The build refuses assets without it.
- **The repo stays private.** Unpublished plots are never pushed anywhere public. What is
  public is the *method*: `uv run talks make-template ../talks-repo-template` regenerates the
  public template repository (pipeline, themes, docs, CLAUDE.md with placeholders, a worked
  example) from an allow-list, scrubs names, paths and ids, and refuses to finish if a private
  pattern survives; `--push` commits and pushes it to github.com/<you>/talks-repo-template
  (public, marked as a template) with the source commit in the message. The template is never
  edited by hand; change this repo and regenerate, after every change to themes, docs or
  CLAUDE.md that colleagues should see.
  Deliverables (PDF, PPTX, HTML) go to the author's Drive with `talks publish <slug>`
  (`My Drive/1-Areas/Research/Talks-and-Travel/<YYMM.Event>/<deck>/`, create only).

## Priorities

- **<UNI> talks first**, MIT talks second, CERN-era (PhD) talks last.
- For the CERN-era decks the **plots** matter, not the slides or their text. Extract
  figures from them; do not spend effort on blocks, timing, or matching quality there.

## Working style

- The log book in `notes/` records what happened, when and why (decisions, numbers,
  open items); append an entry after substantial work and compile it
  (`lab/docs/LOGBOOK_GUIDE.md`).

- Answer questions before making changes. Ask permission before editing or deleting.
- Explain in plain language first; define terms as they appear.
- Commit after each completed pipeline stage. Small commits, descriptive messages.
- Every pipeline stage is manifest-driven and resumable: re-running skips finished items.
- Every stage writes a review sheet into `review/` that the author checks and corrects before
  the next stage runs. Corrections flow back into the YAML manifests, never only into
  the sheet.

## Layout

```
CLAUDE.md            this file
PROJECT_PLAN.md      plan, stage descriptions, rationale
pyproject.toml       uv-managed Python project; package in src/talks_repo/
talks.yaml           the spine: one entry per talk ever given
files.yaml           every discovered file in the input folders and its match to a talk
updates.md           dated log of new results since the last talk on a topic
assets/figures/      curated, deduplicated figures, one file each
assets/equations/    LaTeX snippets, one per equation, with provenance
assets/sources/      original plotting scripts / data where available
assets/catalog.yaml  metadata per asset
blocks/              reusable slide modules (*.typ) with a tagged header
themes/              Typst/Touying slide theme, poster theme (karthein-poster.typ), palette, logos
talks/<slug>/        brief.yaml, main.typ, report.md, YYMM.<Event>-YourName.pdf + .html (ignored);
                     posters: poster.typ + PDF (ignored)
archive/<talk-id>/   deck.pdf, deck.pptx (ignored), manifest.yaml
review/              generated review sheets; CSVs tracked, HTML contact sheets ignored
work/                intermediate extraction dumps (ignored)
notes/               log book (talks-repo-logbook.typ + PDF), guide, template copy, figures
scripts/             AppleScript files for Keynote / PowerPoint export; logbook_figures.py
spikes/              throwaway experiments, e.g. the accessibility spike
src/talks_repo/      all Python: one module per stage, exposed as `talks <stage>`
```

## Tooling

- Python via uv: `uv run talks <subcommand>`. Add dependencies with `uv add`, never by
  editing `pyproject.toml` by hand.
- Typst is installed with Homebrew, not uv. Version must be >= 0.14 (currently 0.15.1).
- Slide format is **Typst + Touying** (decided). If the accessibility spike shows Touying
  breaks UA-1 validation, fall back to plain Typst with a small hand-written template.
- Compile every deck with `typst compile --pdf-standard ua-1 talks/<slug>/main.typ`.
  A validation failure is a build failure.
- Keynote and PowerPoint conversions run through AppleScript (`osascript`) and need an
  interactive Mac session. Ask the author for a time slot before running a batch.
- **Google Slides import:** `uv run talks pptx <slug>` rebuilds every page of the deck's PDF as
  a PPTX slide with *live text*: each text line becomes a native text box (font, size, weight,
  colour kept; STIX Two Text is on Google Fonts), photos and raster figures become picture
  shapes, and only the vector art (rules, panels, diagrams, SVG plots, logos) is rendered as a
  300 ppi background. Import with File > Import slides; text is searchable and reusable there,
  the Typst source stays the original. `--flat` gives one picture per page (posters),
  `--pages 1,3-4`, `--png` keeps the renders, a PDF path works too. Bold is recovered from
  glyph advances (Typst embeds a variable font's regular and bold under one name).
- The input folders live in Google Drive and iCloud Drive. Files can be cloud-only
  placeholders; opening one forces a download. `talks discover` skips those and flags
  them. Ask the author to download a folder rather than pulling it from a script.
- Google Slides files exist on disk only as `.gslides` pointers. Content comes from a
  Drive export (API or manual download; decided after Stage C counts them).
- Claude's vision API is used for image classification, captions, alt text, and as the
  equation OCR of last resort.

## Where figures come from (Stages D and E)

- **Vector first.** A plot stays a PDF (or SVG/EMF) whenever an original exists; never
  replace a vector original with a raster export. `assets/figures/` keeps the best
  available format, and the catalog records it.
- **Typst needs SVG.** Tagged PDF (UA-1) export refuses embedded PDF images, so every PDF
  figure in `assets/figures/` has an SVG twin of the same stem (made by PyMuPDF, vectors
  kept). Decks embed the `.svg`; the `.pdf` stays as the original.
- **Equations need alt text in Typst too:** `#math.equation(alt: "...")[$...$]`; a bare
  `$...$` fails UA-1 validation.
- **Keynote:** the PPTX export rasterises inserted PDFs, but the originals survive inside
  the `.key` package (`Data/` entries). Stage E takes media from the package and uses the
  PPTX export only to map each file to its slide (match by perceptual hash of a render).
- **Google Slides:** read through the Slides API (`archive/<id>/slides.json` + `media/`),
  not the PPTX export, which is unreliable. Slides stores raster only, so the vector path
  for those plots is the original plotting script or data in `assets/sources/`.
- **Duplicate-slide animations.** the author builds "animations" as consecutive copies of a
  slide with small changes, so the PDF shows each step. Stage E treats a run of
  near-identical consecutive slides as one build sequence: one block, one figure asset
  taken from the last (complete) stage, and the intermediate stages recorded as
  `build_stages`. Generation reproduces them with Typst `pause`, and the handout keeps
  only the final stage.

## Where equations come from (Stage F)

Most equations do not need OCR. Check these sources in order and record which one
produced each result:

1. **Keynote decks**: the equation editor stores the LaTeX source in the package's
   `Index/Slide-*.iwa` files (Snappy-compressed protobuf). `talks equations` decodes
   them, orders slides by their first reference in `Index/Document.iwa`, and skips the
   hidden positions taken from the PPTX export to get visible slide numbers. Each
   equation is also rendered to `Data/equation-*.pdf` inside the package (vector).
2. **Google Slides decks**: the LaTeX is in the **speaker notes** of the slide that shows
   the equation (`$...$` spans, or whole lines with TeX commands). Notes survive in PPTX
   downloads of Slides decks too, so they are read from every deck's per-slide manifest.
3. **PowerPoint decks**: native OMML equations convert to LaTeX deterministically
   (not implemented yet; no OMML seen so far).
4. **Fallback**: the `latex` field of Stage E's vision classification, only for slides
   with no sourced equation. Mathpix is not used.

Every unique equation is rendered with Typst + the `mitex` package (renders LaTeX inside
Typst; use 0.2.7, older versions break on bra-kets with Typst 0.15) and shown next to the
source crop on `review/stage-f-equations.html`. Results land in `assets/equations/<id>.tex`
with a provenance header; `status: unreviewed` until the author checks them.

## Schemas

### talks.yaml (one entry per talk)

```yaml
- id: 2024-10-aps-dnp-2024       # YYYY-MM-slug, unique; safe to rename by hand before Stage C
  cv_index: 51                    # number in the CV's Presentations list; Stage A's merge key
  date: "2024-10"                 # YYYY-MM from the CV; Stage C may refine to YYYY-MM-DD
  title: "..."
  event: "APS DNP 2024"           # event acronyms like "(TCP22)" stay in the event name
  qualifier: invited              # the CV's parenthetical, e.g. "invited seminar", or null
  award: "Young Scientist Award"  # or null
  host: "American Physical Society"   # Stage B
  location: "Boston, MA, USA"
  type: invited                   # invited | contributed | seminar | colloquium | public | poster
  era: <UNI>                       # PhD (through 2020) | MIT (2021-2024) | <UNI> (2025-)
  duration_min: 30                # Stage B
  audience: nuclear               # general | nuclear | amo | mixed | public | students
  format: parallel                # plenary | parallel | seminar
  source_url: "..."               # where duration/audience came from
  confidence: 0.8                 # 0-1, Stage B; low values go on the gaps sheet
  source_file: "..."              # Stage C: editable original (relative to input root) or null
  pdf_file: "..."                 # Stage C: PDF export or null
  archive: archive/2024-03-aps-april   # Stage D, or null
  notes: ""
  cv: false                       # optional: keep this talk out of the CV (internal meetings); default true
```

`talks.yaml` is also the presentations source of the CV repository (`~/Projects/karthein-cv`,
`cv build` reads it); every talk appended here appears in the CV unless `cv: false`.

### files.yaml (every deck-like file in the input folders)

File references elsewhere (talks.yaml `source_file`, `pdf_file`) use the form
`root:relative/path`, e.g. `mit:2406.PLATAN-Jyväskylä/2406.PLATAN-YourName.key`.

```yaml
- path: "2406.PLATAN-Jyväskylä/2406.PLATAN-YourName.key"   # relative to its root
  root: mit                       # tamu | mit | phd (the three input folders, priority order)
  folder: "2406.PLATAN-Jyväskylä" # top-level trip folder, "" for loose files
  type: .key                      # .key | .pptx | .ppt | .pdf | .gslides
  mtime: "2024-06-10"
  size: 48211233
  cloud_only: false               # placeholder not downloaded; analysis skipped
  analyzed: true
  pages: 41                       # slide or page count, null if unknown
  first_title: "..."              # largest text on slide 1
  landscape: true
  aspect: 1.778
  chars_per_page: 310.5           # PDFs only
  page_size: "960x540"            # PDFs only, points
  gdrive_id: null                 # .gslides only, for the Stage D export
  own: true                       # the author's deck, not someone else's saved in the folder
  is_deck: 1.0                    # 0-1 score from type, name, geometry, text density
  deck_class: deck                # deck | poster | document | template | unknown
  group_id: mit-g072              # same deck in different forms (source + PDF export)
  talk_id: 2024-06-platan24       # or null
  match_confidence: 0.99
  status: unreviewed              # unreviewed | confirmed | rejected | no_talk
  flags: []
```

Only `own` decks are matched to talks and, later, mined for figures. Other people's
decks saved in trip folders (`own: false`) are never used as asset sources.

### folders.yaml (every top-level trip folder)

`root`, `folder`, `date` (YYYY-MM from the folder name), `n_files`, `n_decks`,
`talk_ids`, `status` (unreviewed | no_talk | has_talk). Folders without a deck get
`no_talk` automatically and are skipped in later stages.

### assets/catalog.yaml (one entry per figure or equation)

```yaml
- id: mrtof-schematic-v3
  file: figures/mrtof-schematic-v3.svg
  kind: plot                      # plot | schematic | photo | equation | logo
  topic: [mr-tof, instrumentation]
  level: [general, expert]
  first_used: 2023-04
  last_used: 2026-03
  supersedes: mrtof-schematic-v2  # or null
  caption: "..."
  alt: "Schematic of the MR-ToF: ion bunch oscillating between two electrostatic mirrors ..."
  source: "Karthein et al., PRL 2024, Fig. 1"
  origin: {talk: 2023-04-aps-april, slide: 7}
```

`alt` describes content and message ("Mass difference vs. isotope; the trend flattens at
N = 28"), not the file. For equations, `file` points into `equations/` and `alt` reads the
equation aloud.

Fields added by `talks catalog` (Stage G) beyond the example: `image_id` (Stage E cluster
id), `n_uses` and `uses` (`talk#slide` list), `origin` (first use), `vector`,
`archive_ref` (where the bytes live in the archive), `confidence` (classifier), and
`supersedes_candidates` (older look-alike figures of the same kind; a suggestion only).
Only plots, schematics, tables and equations are copied into `assets/figures/`; photos,
screenshots and logos have `file: null` and are fetched from `archive_ref` when a talk
needs them (`talks catalog --copy-all` copies them too). Hand-edited fields (id,
caption, alt, topic, level, source, supersedes, notes, kind, file) survive re-runs.
Hand-added figures (no `image_id`) that exist only as SVG must be un-ignored by name in
`.gitignore` (the `assets/figures/*.svg` rule is for regenerable twins of PDFs); PDF originals
are tracked and get their SVG twin from `talks catalog` or by hand (`svg:` field).

### Block header (first lines of blocks/*.typ, as a comment)

```typst
// id: intro-mrtof
// title: Multi-reflection time-of-flight mass spectrometry   # shown in the title-slide contents
// topic: [mr-tof, instrumentation]
// level: [undergrad, nuclear, AMO, expert]   # public | undergrad | nuclear | AMO | expert
// minutes: 3
// order: 30                 # default position in the deck (lower = earlier)
// requires: []              # block ids pulled in automatically
// assets: [mrtof-schematic-v3]   # catalog ids used; photos get materialised from the archive
// always: true              # optional: included regardless of topics (e.g. acknowledgements)
// section: New capabilities # optional: title-slide contents list sections, not block titles
// sponsors: true           # optional: DOE + Genesis logos in the footer of this block's slides
// source: 2026-08-radis-workshop slides 26-30
#import "/themes/karthein.typ": *
#slide(title: [...], footer-citation: [...], composer: (1fr, 1fr))[ ... ][ #cat-fig("id") ]
```

A block is a Typst file that is `#include`d; slides use `#slide(title: ...)` (or `==`),
figures `#cat-fig(id)` (alt text and file from the catalog; superseded ids fail the build),
equations `#cat-eq(id)`. Write `\~` for an approximate tilde (a bare `~` is a non-breaking
space) and keep math out of plain text unless wrapped in `#eq(alt: ...)`.

### talks/<slug>/brief.yaml

```yaml
title: "..."
date: 2026-11-02
event: "..."
duration_min: 25            # blocks get duration minus 3 (title + questions)
audience: nuclear           # general | nuclear | amo | mixed | public | students
topics: [mr-tof, molecules] # matched against block topics
abstract: |
  ...
notes: |
  Audience notes, requests from the host, what to emphasise.
sponsors: true              # DOE + Genesis logos in the footer
spine: true                 # false for test decks: do not append to talks.yaml
reserved_min: 3             # optional: minutes kept for title + questions (short slots: 0)
exclude: [group-acknowledgements]   # optional: block ids never used, even `always` ones
```

`talks generate <slug>` selects blocks, materialises their assets, writes `main.typ`,
compiles one PDF named `YYMM.<Event>-YourName.pdf` (UA-1, with the build steps) plus the
HTML version of the same name, and writes `report.md` with the block list,
timing, asset problems, and `updates.md` entries newer than the last talk on the topics.

## Slide style

- Slide titles are always in Title Case.
- One PDF per talk, named `YYMM.<Event>-YourName.pdf`, always with an HTML export
  of the same name next to it. No separate handout.
- A deck without a title slide (a single slide for a group meeting) is fine: the theme
  promotes the first slide title to heading level 1, which PDF/UA-1 requires.
- Sponsor logos (DOE, Genesis Mission) appear only on slides of blocks that declare
  `// sponsors: true` (the Genesis blocks), never elsewhere.
- Colours, radii, shadows: the lab style guide's `tokens.json` (v3; its Drive folder
  `How-tos/_Karthein-Lab-Style-Guide` no longer exists, the tokens live on as `line-color`,
  `text-color`, `panel`, `fill-color`, `radius`, `lifted()` in the theme; the palette sheet is
  in `Figures/_logos-and-palette/`). Captions are one
  line at 11 pt, never smaller.
- Touying reveal markers (`only`, `uncover`, `pause`) must sit at the top level of a slide
  or composer column, not inside boxes or function bodies; `layout` reports the full body
  height including the header, so use fixed column heights (~296 pt).
- One figure per slide, minimal text, no bullet walls.
- **Final layout pass on every new or changed slide.** Content is not written top-down and
  left there: render the page, look at it, and adjust until it is presentable. Paragraphs
  and bullets get visible spacing (10-13 pt at body size; `#set par(spacing: 0pt)` removes
  the default, so add `v()` or `block(below:)` explicitly); the body fills the slide (no
  blank band above the footer, columns ending at similar heights; enlarge the figure,
  the type or the spacing rather than leave it); figures and captions aligned with the text
  column, one caption line. `uv run talks layout <slug>` measures the blank bottom band
  and the column imbalance per page and flags > 18 % / > 25 %; `talks generate` puts the
  same flags in `report.md`. Intermediate build steps may be flagged; the last step counts.
- Fonts, colours, and logo placement are defined in `themes/` (fixed at the theme step;
  until then, do not invent them).
- Prefer the newest version of a figure. Never use a superseded asset.
- Plot palettes are colour-blind-safe; the approved palette and its measured contrast
  ratios are recorded in `lab/themes/palette.yaml`; `lab/themes/karthein.mplstyle` applies the figure
  style in matplotlib; `lab/docs/STYLE.md` is the one-page summary of the whole style. Fonts: STIX
  Two Text and STIX Two Math.
- Theme: `themes/karthein.typ` (Touying). Slide titles via `==` or `#slide(title: ...)`;
  figures via `#fig(path, alt: ...)`, equations via `#eq(alt: ...)[$...$]`; compile with
  `typst compile --root . --pdf-standard ua-1`.

## Posters

Posters are not generated from blocks: each is one hand-written `talks/<slug>/poster.typ` on
the poster theme `themes/karthein-poster.typ` (A0 portrait by default; palette, fonts and
logos shared with the slide theme). First used for the <Your University> System AI Research &
Innovation Meeting (`talks/2026-10-tamus-ai-poster`).

- Structure: `#show: poster.with(title: …)`, `#poster-header(…)` (grey band, title,
  subtitle, authors, collaborators, logos on the right at one visible height, centred),
  rows of cards, `#poster-footer(…)`. A row is `#card-row(columns: (1fr, 1fr), sec[…][…],
  sec[…][…])`; a cell may be an array of `sec`s stacked in one column. Every card in a row
  gets the row's height (top and bottom edges aligned; stacked cards share the extra
  equally), and every gap, between columns, rows (`#v(poster-gutter)`) and stacked cards,
  is `poster-gutter` (18 mm); the footer follows the last row at the same gap, and the
  page is filled so that the remaining bottom margin comes out near the 28 mm side margins.
  Cards are white with a hairline and the `smd-off` shadow
  (chosen 2026-09-29; other `shadow-styles` remain available). `section[…][…]` on its own
  is a single card at its natural height.
- Building blocks: `card-row`/`sec`, `section`, `stat` (big number in a palette panel;
  `stat-row((big, small, tone), …)` for a row of them at one height),
  `note` (24 pt caption), `pfig(id, height, caption)` (catalog figure with a poster-size
  caption), `pphoto(id, height, caption)` (photo cropped to a fixed frame), `fit(body,
  limit:)` (scales a slide diagram to the available width).
- Slide diagrams are reused by importing their functions from `blocks/` (e.g.
  `twin-loop`, `pipeline`) and wrapping them in `fit`, with the slide base size set
  (`text(size: 14pt, …)`) so scaled labels do not inherit the poster's 30 pt.
- Type sizes at A0: body 30 pt, captions 24 pt, section titles 50 pt, title ~100 pt; nothing
  below ~20 pt. Multi-line body paragraphs are justified (`par(justify: true)[…]`); captions,
  stat panels and bullet lists are not. The slide theme's figure captions are 11 pt, so use `pfig` on posters.
- **Vector wherever a source exists**: text, Typst diagrams, SVG plots, SVG logos
  (`themes/logos/cyclotron-institute.svg`, `karthein-lab-sticker.svg`). Photos stay raster
  at >= 2000 px. UA-1 refuses embedded PDF images, so convert PDF logos or figures to SVG
  with PyMuPDF (`page.get_svg_image(text_as_path=True)`). Still raster: the DOE and
  Genesis Mission logos (`doe.png`, `genesis-mission.png`, split from `doe-genesis.png`;
  no vector source found yet).
- Sections are unbreakable; if a row does not fit it moves to a new page. Compile after each
  change and check that the poster is one page:
  `typst compile --root . --pdf-standard ua-1 talks/<slug>/poster.typ talks/<slug>/<Name>.pdf`.
- Add the poster to `talks.yaml` by hand (`type: poster`); the generator does not see it.

## Courses (lecture notes, problem sets)

Courses are separate repositories made from the public template (`lab/docs/COURSES.md`); this
repository holds the theme and the example (`courses/example-course/`). The notes theme
`themes/karthein-notes.typ` compiles one source in three modes (`--input mode=student|lecture|
solutions`): the posted notes, the handwriting copy for the iPad (`work`/`blank` become empty
space), and problem-set solutions. `talks course build --course <dir>` reads `course.yaml`,
refreshes equation alt text, compiles every mode (UA-1) plus HTML (MathML), writes
`report.md`; `talks course publish` copies the results to a `My Drive` path, create-only.
Equation alt text: plain `$...$` stays in the source; `talks alts <file>` keeps a
`<stem>.alts.yaml` sidecar (spoken drafts from `themes/speak-math.typ`, `status: draft` until
reviewed) that the theme applies with `where(body:)` show-set rules. `eq(alt: auto)` in both
themes takes the spoken form. Briefs may list `blocks:` explicitly (lectures as decks).
Palette and tokens live in `themes/tokens.typ`, imported by all themes.

## Accessibility (PDF/UA-1, WCAG 2.1 AA)

Posted talk PDFs are in scope of <Your University>'s accessibility rules. The pipeline produces
compliant output by default so nothing needs retrofitting. Details in `PROJECT_PLAN.md`
section 11.

1. Compile with `--pdf-standard ua-1`; a failed validation fails the build. Every deck
   sets a document title and language.
2. Every catalog asset has `alt` text. Stage E drafts it alongside the caption; the author
   reviews both.
3. Palette contrast is WCAG AA: 4.5:1 for body text, 3:1 for large text and graphics.
   Colour never carries meaning alone; use markers or labels too.
4. Heading levels are sequential on each slide; reading order follows visual order.
5. Overlays (`pause`) repeat pages. For posted PDFs, build a `handout` mode with one
   page per slide.
6. Decoration-only images are marked decorative and get no alt text.
7. Before a deck is posted publicly, run Adobe Acrobat's accessibility checker or
   veraPDF/PAC and keep the report next to `out.pdf` (the report is tracked, the PDF is not).

The accessibility spike in `spikes/accessibility/` runs before any theme work.

## Generation workflow

1. Read `talks/<slug>/brief.yaml`.
2. Find the most recent talk in `talks.yaml` sharing the brief's topics. Collect every
   `updates.md` entry dated after it.
3. Select blocks whose `level` fits the audience and whose `minutes` fit the duration
   budget. Resolve `requires` and order the blocks.
4. Write `main.typ`, compile the one PDF (UA-1) and the HTML export.
5. Layout pass: `talks layout <slug>` plus a look at every page render; fix spacing,
   fill and alignment in the blocks before anything is sent (see Slide style).
6. Report: block list, timing estimate, updates proposed, any superseded asset that was
   requested, any asset missing `alt`, layout flags.
7. Append the new talk to `talks.yaml` so the spine stays complete.

## Templates (lab/)

Themes, the lab-notebook template, the matplotlib style and the guides live in `lab/`, a git
subtree of the public `jonas-ka/lab-templates`, pinned to the tag in `lab/VERSION`. The files at
the old paths (`themes/*.typ`, `notes/labnotes-template.typ`, `theme/cv-theme.typ`) are one-line
shims and are never edited. A theme fix is made in `lab/` and sent upstream with
`scripts/lab-templates.sh push`; updates come in with `scripts/lab-templates.sh pull <tag>` after
reading `lab/CHANGELOG.md`; never silently. Logos stay in `themes/logos/`. Log books compile from
the repository root: `typst compile --root . notes/<name>-logbook.typ`.
