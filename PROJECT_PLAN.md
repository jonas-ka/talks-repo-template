# talks-repo — Project Plan and Handoff

Reproducible research-talk slides from a short brief plus a shared library of figures, plots, and equations, seeded by ingesting 60+ past talks.

## 1. Context

- **Who:** <Your Name>, assistant professor of nuclear physics, <Your University> <Your Institute>. AMO/nuclear physics: ion traps, lasers, MR-ToF mass spectrometry, radioactive atoms and molecules. Previously postdoc at MIT.
- **Situation:** Gives many similar research talks. 60+ past decks exist in Keynote, Google Slides, PowerPoint, and PDF. Currently uses Google Slides but presents PDFs. Works on a Mac.
- **Goal:** A repo where a new talk is generated from a brief (time, title, abstract, audience notes), drawing on a curated asset library and automatically incorporating research updates since the last talk on that topic.
- **Repo:** `~/Projects/talks-repo`, git-initialised, Python project set up with `uv`, pushed to a private GitHub repo `talks-repo` (remote `origin`).
- **Working preferences:** Answer questions before making changes. Ask permission before editing or deleting anything. Explain in plain language first and define terms as they appear. Commit as you go.

## 2. Inputs

- **CV (source of the talks list):** Google Doc, shared "anyone with link":
  `https://docs.google.com/document/d/1RyrDpyE_UKVQuS4SSUP2Ewjmf4fQ8-ivwwLT3N4M6Sg/edit?usp=sharing`
  Fetch it as plain text or DOCX via the export endpoint, e.g. `https://docs.google.com/document/d/1RyrDpyE_UKVQuS4SSUP2Ewjmf4fQ8-ivwwLT3N4M6Sg/export?format=txt` (or `format=docx` to preserve structure). No API credentials needed for a public doc.
- **<Your University> talks (current job):**
  `<input-folder-1>`
- **MIT postdoc talks:**
  `<input-folder-2>`
- **PhD-era talks (CERN / Heidelberg, 2016–2020):**
  `<input-folder-3>`
  Subfolders are named `YYMM.Event-Place`. Mostly Keynote plus PDF exports, a few PowerPoint files, no Google Slides. The two `_Keynote-Master-CERN-*.key` files at the top level are the CERN-era Keynote theme, not talks.
- All three folders are **read-only inputs**. Never modify, move, or delete anything in them.
- **Priority:** <UNI> talks first, MIT talks second, CERN-era talks last. For the CERN-era decks only the plots matter, not the slides or their content.
- The trip folders also hold **other people's decks** (downloaded talks, templates, collaboration-meeting contributions). Stage C marks these `own: false`; they are never matched to talks or mined for figures.
- These are **trip folders, not talk folders**: subfolders are organised by trip/event and also contain travel documents (itineraries, receipts, boarding passes, visa letters, posters, abstracts, photos). Some subfolders contain no talk at all (conferences attended without speaking, collaboration visits, beam times). Do not assume every folder or every PDF is a deck.
- A talk is typically present in **two forms**: the editable source (Keynote or Google Slides, occasionally PowerPoint) and a PDF export of it. Both should be captured and linked to the same talk; the editable source is the figure source, the PDF is the visual reference.
- Note: Google Slides files appear on disk only as `.gslides` pointer files (a URL, no content). Their content must come from a Drive API export or a manual download.

## 3. Repo layout

```
talks-repo/
├── CLAUDE.md                # style rules, schemas, workflow, safety rules for Claude Code
├── PROJECT_PLAN.md          # this document
├── pyproject.toml           # uv-managed Python project
├── talks.yaml               # the spine: one entry per talk ever given (see §5)
├── files.yaml               # index of all discovered slide files and their match to talks
├── updates.md               # dated log of new results since the last talk
├── assets/
│   ├── figures/             # curated, deduplicated figures (one file each)
│   ├── equations/           # LaTeX snippets, one per equation, with provenance
│   ├── sources/             # original plotting scripts / data where available
│   └── catalog.yaml         # metadata per asset (see §4)
├── blocks/                  # reusable slide modules (see §6)
├── themes/                  # visual identity (Typst theme)
├── talks/
│   └── <YYYY-MM-slug>/
│       ├── brief.yaml       # time, title, abstract, audience notes
│       ├── main.typ         # assembled deck
│       └── out.pdf          # compiled (ignored by git)
├── archive/
│   └── <talk-id>/           # deck.pdf, deck.pptx (if obtainable), manifest.yaml
├── review/                  # generated review sheets (HTML/CSV) for human checking
├── work/                    # intermediate extraction dumps (ignored by git)
└── scripts/                 # ingest, export, extract, classify, build
```

## 4. Key design decisions

- **Slide format: Typst + Touying** (decided). Fast compiles, excellent math, precise layout, easy theming, and built-in Tagged PDF / PDF/UA-1 output (see §11). Touying is the better-maintained successor of Polylux; if the §11 accessibility spike shows Touying's overlay mechanics break UA-1 validation, fall back to plain Typst with a small hand-written slide template. Typst itself is installed separately (`brew install typst`, must be ≥ 0.14 for accessibility support), not via uv.
- **Blocks, not decks from scratch:** talks are assembled from reusable slide modules tagged with topic, audience level, duration, and dependencies.
- **Asset catalog** (`assets/catalog.yaml`), one entry per figure or equation:
  ```yaml
  - id: mrtof-schematic-v3
    file: figures/mrtof-schematic-v3.svg
    kind: plot | schematic | photo | equation | logo
    topic: [mr-tof, instrumentation]
    level: [general, expert]
    first_used: 2023-04
    last_used: 2026-03
    supersedes: mrtof-schematic-v2
    caption: "..."
    alt: "Schematic of the MR-ToF: ion bunch oscillating between two electrostatic mirrors ..."   # required, see §11
    source: "Karthein et al., PRL 2024, Fig. 1"
    origin: {talk: 2023-04-aps-april, slide: 7}
  ```
  Superseded assets must never appear in new talks. `alt` is mandatory for every figure and equation; the build refuses assets without it.
- **Update loop:** `updates.md` holds dated entries for new results. Generating a talk compares its date against the last talk on the same topic and proposes new or revised blocks.
- **Figures are not extracted from PDFs.** Vector plots shatter into paths, rasters are flattened, grouped figures split. Extract from native files instead: PPTX (`ppt/media/` plus slide-to-image mapping via `python-pptx`); Keynote and Google Slides are converted to PPTX first. PDFs serve as the visual reference and for slide-text extraction.
- **Runs locally on the Mac.** Keynote conversion and the mounted Drive folder require it; Claude Code in VS Code is the driver.

### `.gitignore` and what stays out of git
Commit source only: `.typ`/`.md`, `CLAUDE.md`, YAML manifests and catalog, scripts, themes, curated figures in `assets/`.
Ignore: `.venv/`, `__pycache__/`, `.DS_Store`, `*.key` and `*.pptx` originals (they live in Drive; the archive keeps exported PDFs), compiled `talks/*/out.pdf` and any `build/`, `work/` and other intermediate dumps, and **all credentials** (`credentials.json`, `token.json`, `.env`).
`archive/` came to 2.7 GB after Stage D (1.6 GB of PDFs), beyond GitHub's free 1 GB LFS quota, so archive PDFs, PPTX, and Slides media are **not committed**; only `manifest.yaml` and `slides.json` are. The archive is regenerated with `uv run talks export` (Keynote batch ≈ 15 min). If `assets/figures/` grows past a few hundred MB, use Git LFS there. Keep the repo **private** until the archive has been reviewed; never publish unpublished plots.

## 5. Phase 0 — Ingestion pipeline

Guiding idea: build one spine file, `talks.yaml`, with one entry per talk, and let each stage add fields. Every stage also writes a human-readable **review sheet** (CSV or simple HTML) into `review/` that the author checks and corrects before the next stage runs. All stages are **manifest-driven and resumable**: re-running skips completed items.

**Stage A — Talks list from the CV.**
Export the CV, parse each talk/trip entry into `talks.yaml` v1:
`id` (e.g. `2024-03-aps-april`), `date`, `title`, `event`, `host`, `location`, `type` (invited / contributed / seminar / colloquium / public / poster), `era` (MIT / <UNI>).
Review sheet: entries the parser couldn't handle.

**Stage B — Event enrichment.**
For each talk, web-lookup of the event (conference programme, seminar page, Indico timetable) to fill `duration_min`, `audience` (general physics / nuclear / AMO / mixed / public / students), `format` (plenary / parallel / seminar), `source_url`, `confidence`. Low-confidence entries go to a **gaps sheet** for the author to fill in by hand (expect 30–50%, since old event pages disappear). Run as a supervised batch.

**Stage C — File discovery, deck detection, and matching.**
Walk both input folders and build `files.yaml`: path, type (`.key`, `.pptx`, `.pdf`, `.gslides`), modification date, slide/page count, first-slide title where cheaply readable.

*Deck detection first.* Because the folders hold travel paperwork as well as slides, every file gets an `is_deck` score before any matching. Signals: file type (`.key`, `.gslides`, `.pptx` are almost always decks; `.pdf` needs checking); PDF page geometry (landscape 16:9 or 4:3 pages with consistent size → deck; portrait A4/Letter → document); page count (decks typically 15–80 pages; a 1–3 page PDF is a receipt, abstract, or boarding pass); text density per page (decks have little text, large fonts); filename keywords (`talk`, `slides`, `seminar`, `colloquium`, `presentation` vs. `invoice`, `itinerary`, `boarding`, `hotel`, `abstract`, `poster`). Posters are landscape single pages and should be classified as `poster`, not deck. Borderline cases go on the review sheet.

*Pairing.* Group files that are the same deck in different forms: a Keynote/Slides/PPTX source and its PDF export, matched by folder, title, slide count, and date. Each talk entry then records `source_file` (editable) and `pdf_file` separately; if only one exists, the other is null. Drafts and versions ("final", "final_v2", "backup") are listed as candidates on the review sheet so the author picks the canonical pair.

*Matching to talks.* Fuzzy-match deck groups to `talks.yaml` using folder name, date proximity (folder or file date vs. talk date), and title similarity to the first slide. Flag: subfolders with no deck (expected — trips without a talk; record them as `no_talk` so they are skipped on re-runs), decks matching no CV entry (talks missing from the CV — add them), and CV talks with no deck found (search by title across both folders before declaring them lost).

**Stage D — Export into `archive/<talk-id>/`.**
Canonical outputs: `deck.pdf` and, where obtainable, `deck.pptx`, plus `manifest.yaml` recording the original filename and conversion path.
Conversions: Keynote → PPTX and PDF via AppleScript (Keynote opens each file; run unattended in a batch; Keynote must be open with no dialog or theme chooser showing, or the open events time out); PowerPoint → PDF via PowerPoint AppleScript; Google Slides → **Slides API** (decided): `slides.json` with per-slide text, speaker notes, and image alt text, plus `media/` with the original image bytes, plus the PDF export as visual reference. The PPTX export is kept only as a courtesy copy since its formatting is unreliable. Idempotent: skip talks whose archive folder already has outputs.

Figures stay **vector** where an original exists: Keynote packages hold the inserted PDFs under `Data/`; Stage E takes those and uses the PPTX export only to map them to slides. Consecutive near-identical slides are the author's hand-made "animations" and are treated as one build sequence (see CLAUDE.md).

**Stage E — Slide-level extraction.**
From each PPTX: every image in `ppt/media/` and a per-slide manifest mapping images and text to slide numbers. From each PDF: per-slide text and a rendered thumbnail. Deduplicate across all talks: exact hash first, then perceptual hash for recrops and recompressions. Classify every unique image (plot / schematic / photo / equation / logo / screenshot / decoration) with Claude's vision API in a batch, drafting a caption and topic tags at the same time. Review sheet: contact-sheet HTML grouped by class. Flag figures that exist only as native Keynote/Slides shapes (no image file) for later redrawing.

**Stage F — Equations to LaTeX.**
Convert images classified as equations. Options by quality: Mathpix API (best, paid), Claude vision (good, already in pipeline), pix2tex/LaTeX-OCR (free, local, weaker on multi-line). Default: Claude vision, with Mathpix as fallback for failures. **Verification is essential:** re-render each LaTeX result (Typst or KaTeX) side by side with the source crop in a review sheet. Decks made natively in PowerPoint may contain OMML equations, which convert to LaTeX deterministically without OCR. Results go to `assets/equations/` with provenance (talk, slide).

**Stage G — Catalog build and handoff.**
Generate `assets/catalog.yaml` from the reviewed images and equations, with `first_used`/`last_used` from the manifests and `supersedes` suggestions where the perceptual hash shows the same plot evolving. From the archive text, identify recurring slide sequences as candidates for the first blocks.

## 6. Phase 1 — Talk generation

- **Theme:** a Typst theme matching the current visual style, using 2–3 of the best archived PDFs as reference.
- **Blocks** (`blocks/*.typ`): each has a header with topic tags, audience level (public / undergrad / nuclear / AMO / expert), duration in minutes, and dependencies (e.g. `results-x` requires `intro-mrtof`). Start with ~10 blocks reverse-engineered from the most recent talk; expect ~20–30 to cover most talks.
- **Generation workflow:** read `talks/<slug>/brief.yaml` → check `updates.md` against the last talk on the topic → select blocks satisfying audience and duration budget → order them → write `main.typ` → compile → report the block list, timing estimate, and any assets flagged as superseded. the author reviews and adjusts.
- **New talks are appended to `talks.yaml`** so the spine stays complete.

## 6a. Preservation and the lab figure library (added 2026-09-18)

- **Frozen talk folders.** `talks freeze <slug>` copies every asset the deck uses (rasters scaled to 1600 px, SVG twins and vector PDFs unchanged), the figure sources, the blocks, the theme and the logos into `talks/<slug>/`, with a frozen catalog and a manifest (git commit, file hashes). The folder compiles on its own with `typst compile --root talks/<slug>`, so a deck can be rebuilt even if originals, theme or blocks change later.
- **Lab library on the shared drive.** `talks sync-drive` mirrors the reviewed catalog into `<LabName>/Figures/_catalog/<id>/` (plots, schematics, tables, equations) and `<LabName>/Photos/_catalog/<id>/` (photos, logos, screenshots): original file, SVG twin, PNG preview, plotting source when present, `README.yaml` with caption/alt/topics/provenance, plus a dated `index-<date>.csv`. **Append-only**: the only Drive write is `files.create`; existing files are never modified, renamed or deleted, and existing folders are completed with missing files only. The loose files already in those folders stay untouched. This repo's catalog remains the source of truth; Drive is the mirror.
- **HTML slideshow.** `talks html <slug>` exports one inline SVG per slide into a self-contained `index.html`, so animated GIFs play (PDF cannot). Vector figures stay vector.
- **Figure sources.** Convention: `assets/sources/<figure-id>/make.py` plus data, referenced from the catalog entry's `source_dir`; freeze and sync carry it along.
- **Harvesting existing sources (2026-09-18).** `talks sources inventory|analyze|copy|run` walks three Drive roots (`Colab Notebooks`, `Code/Colab Notebooks`, `articles/_jonas-author`) through the API, downloads every notebook and Python script, finds the data files each one reads (siblings, Colab `/content/drive/...` paths anywhere on Drive including shared drives, whole folders, fonts) and tells inputs from outputs, then copies code + data to `<LabName>/Figures/_sources/<root>/<path>/` with the paths rewritten and a provenance header (append-only; originals untouched). Self-contained figure notebooks are executed headless with Colab stubs and a patched `savefig` that also writes SVG, PDF and 300 dpi PNG into `exports/<script>/` next to the code. `.ipynb_checkpoints` and the ML coursework are skipped. Notebooks needing interactive Google auth (gspread) cannot run headless. Plots stored in notebook outputs are matched to catalog figures by perceptual hash (`review/sources-figure-matches.csv`).

## 7. `CLAUDE.md` contents

Style rules (fonts, colours, one figure per slide, minimal text); the accessibility rules from §11 (UA-1 build, alt text, contrast, heading order); the schemas for `talks.yaml`, `files.yaml`, `catalog.yaml`, block headers, and `brief.yaml`; the generation workflow; the rule that superseded assets are never used; input folders are read-only; ask before deleting or replacing anything in `archive/` or `assets/`; credentials never committed; commit after each completed stage.

## 8. Build order

1. `CLAUDE.md`, `.gitignore`, repo skeleton, `pyproject.toml` with initial dependencies. Commit.
2. Stage A end to end (small, immediately useful).
3. Stage C before Stage B — knowing which talks have files shows where enrichment effort matters.
4. Stage D for Keynote and PDF first; add Google Slides once API-vs-manual is decided.
5. Stages E–F on a handful of talks; review the sheets; then run on everything.
6. Stage G.
7. Accessibility spike (§11), then theme, first blocks, generation script; test on a real upcoming talk.
8. Update loop and refinement.

## 9. Open decisions and what the author provides

- ~~Typst vs. Marp~~ → decided: Typst + Touying (see §4 and §11).
- Confirm with <Your University>'s IT Accessibility office that a PDF/UA-1-tagged PDF meets SAP 29.01.04.M0.02 for posted talk slides.
- Google Slides export: Drive API (OAuth setup) vs. manual download.
- A Mac session where Keynote can run unattended for an hour or so.
- Optional Mathpix API key for equation OCR fallback.
- Filling the gaps sheets (durations, audiences) and picking canonical files in review.

## 10. Known risks

Dead event pages (handled by gaps sheet); figures drawn natively in Keynote/Slides with no image file (flagged for redrawing); version ambiguity between drafts (Stage C review); plots whose best source is the original script or data — store those in `assets/sources/` so they can be regenerated in the new theme.

## 11. Accessibility requirements

**Why.** <Your University> is a public university subject to the ADA, Sections 504/508 of the Rehabilitation Act, and Texas Administrative Code Chapters 206 and 213. The DOJ's ADA Title II rule (effective April 2024, compliance deadline April 2026) requires web-based digital resources — including electronic documents — to meet **WCAG 2.1 AA**, superseding the older WCAG 2.0 AA in the Texas rules; <Your University> has adopted WCAG 2.1 AA (SAP 29.01.04.M0.02). Any talk PDF that is posted (course site, lab website, conference server, Indico) is in scope. Decks shown only live are lower-risk, but the pipeline should produce compliant output by default so nothing needs retrofitting.

**Technical target.** PDF/UA-1 (ISO 14289-1), which Typst ≥ 0.14 supports natively: Typst writes Tagged PDF by default, and with `--pdf-standard ua-1` it validates at compile time and refuses to emit a non-conforming file. PDF/UA-2 (better native math) is not yet supported by Typst; until it is, equations carry alt text like figures.

**Rules for the repo**
1. Every deck is compiled with `typst compile --pdf-standard ua-1`; a failed validation fails the build. Every deck sets a document title and language.
2. `assets/catalog.yaml` has a mandatory `alt` field for every figure and equation. Stage E's vision pass drafts alt text alongside captions; the author reviews both. Alt text describes the content and the message ("Mass difference vs. isotope; the trend flattens at N = 28"), not the file.
3. The theme's palette is checked once against WCAG AA contrast ratios (4.5:1 body text, 3:1 large text and graphics); colours never carry meaning alone (use markers or labels too). Prefer colour-blind-safe plot palettes; record the approved palette in `themes/`.
4. Heading levels are sequential per slide (Typst's tagging expects this); reading order follows the visual order.
5. Overlays/"pause" steps produce repeated pages; for posted PDFs, build a `handout` mode with one page per slide so screen readers don't hear each slide N times.
6. Decoration-only images are marked decorative, not given alt text.
7. Before posting a deck publicly, run it through Adobe Acrobat's accessibility checker or veraPDF/PAC as a final check; keep the report alongside `out.pdf`.

**Accessibility spike (done 2026-09-17, `spikes/accessibility/`).** The two-slide Touying 0.6.1 deck with a figure, an equation, a link and two `pause` steps compiles and validates with `--pdf-standard ua-1` on Typst 0.15.1. **Decision: Touying.** Two constraints found: UA-1 mode refuses embedded PDF images (SVG required, so the catalog keeps an SVG twin of every vector figure, made with PyMuPDF), and equations need alt text as well as images (`#math.equation(alt: ...)`). Track the Typst changelog for UA-2 support.

**Not a legal opinion.** Confirm with the <Your University> IT Accessibility office that UA-1-tagged PDFs satisfy their requirements for posted slides.
