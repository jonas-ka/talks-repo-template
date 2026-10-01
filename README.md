# talks-repo template

Reproducible research talks with **Typst + Touying**, a **curated figure library**, and
**Claude Code** as the pair of hands. A new deck is generated from a short brief
(audience, minutes, topics) out of reusable slide blocks; every figure carries its source,
its alt text and its version; every PDF is tagged and accessible (PDF/UA-1); the same
command also writes an HTML slideshow and a PPTX with live text for Google Slides.

This repository is the *method*, exported from a working private repository by
`talks make-template`: the pipeline, the slide and poster themes with the palette and type
tokens, the rules Claude Code works by (`CLAUDE.md`), the log-book and figure-library
guides, and a two-slide example that builds. No one's actual talks are in here; your own
go into `talks/`, `blocks/` and `assets/` once you adopt it.

**Read [RECIPE.md](RECIPE.md) first** — it is the "how I made this work with Claude Code"
that the code cannot tell you.

## Quick start

```sh
# requirements: Python 3.12+, uv, Typst >= 0.14 (brew install typst), the STIX Two fonts
uv sync
uv run talks generate example-talk      # -> talks/example-talk/<date>.Example-Meeting-YourName.pdf + .html
uv run talks layout example-talk        # the layout check per page
uv run talks pptx example-talk          # PPTX with live text boxes, for Google Slides
open talks/example-talk/report.md       # blocks, timing, assets, layout flags
```

If `typst` complains about fonts: STIX Two Text and STIX Two Math are free
(https://www.stixfonts.org); install them system-wide.

## What is in the box

```
CLAUDE.md          the rules, schemas and lessons Claude Code works by (edit the placeholders)
PROJECT_PLAN.md    the plan and the rationale of every stage
RECIPE.md          the narrative: how to set this up with Claude Code, step by step, with prompts
src/talks_repo/    the pipeline: discover -> archive -> extract -> classify -> catalog -> generate,
                   layout check, html and pptx export, drive sync, template export
themes/            karthein.typ (slides), karthein-poster.typ (A0 posters), palette.yaml (colours
                   with measured contrast ratios), logos/ (placeholders: put your own marks here)
blocks/            reusable slide modules; two examples
assets/            catalog.yaml (one entry per figure), figures/, sources/ (scripts + data)
talks/             one folder per talk: brief.yaml -> main.typ -> PDF/HTML/PPTX + report.md
docs/              LOGBOOK_GUIDE.md + labnotes-template.typ (the lab notebook), FIGURES_README.md
                   (the figure library: folder layout, versions, variants, style rules)
scripts/           AppleScript exporters for Keynote and PowerPoint; log-book figure tiles
```

## Adopting it

1. Replace the placeholders in `CLAUDE.md` (`<Your Name>`, `<Your University>`, the input
   folders, the shared drive) and put your logos in `themes/logos/` under the names used there.
2. Point `talks discover` at the folders holding your old decks (Keynote, PowerPoint, PDF,
   Google Slides), then run the stages in `README`'s order; every stage writes a review sheet
   into `review/` and is resumable.
3. Keep `CLAUDE.md` honest: when Claude Code learns something about your setup, it goes in
   there; when something *happened*, it goes in the log book (`docs/LOGBOOK_GUIDE.md`).

## Pipeline commands

```
uv run talks ingest-cv        # Stage A: CV -> talks.yaml
uv run talks discover         # Stage C: input folders -> files.yaml, folders.yaml
uv run talks enrich           # Stage B: durations, audiences, formats
uv run talks export           # Stage D: decks -> archive/<talk-id>/
uv run talks extract          # Stage E: slides, pictures, build sequences
uv run talks classify submit  # Stage E: vision classification (Batch API); then `collect`
uv run talks equations        # Stage F: LaTeX from Keynote packages, notes, vision
uv run talks catalog          # Stage G: assets/catalog.yaml + figure copies
uv run talks generate <slug>  # brief.yaml -> main.typ -> PDF (UA-1) + HTML, report.md
uv run talks layout <slug>    # blank band and column imbalance per page
uv run talks pptx <slug>      # live-text PPTX for Google Slides (--flat for pictures only)
uv run talks html <slug>      # HTML slideshow
uv run talks freeze <slug>    # self-contained talk folder for preservation
uv run talks sync-drive       # mirror the catalog into a shared figure library (append-only, versioned)
uv run talks publish <slug>   # copy the deliverables to your talks folder on Drive
uv run talks make-template    # this repository, regenerated from the private one
```

## Licence and credit

Code: MIT. Documents and themes: CC BY 4.0 — attribution to the Karthein Lab, Texas A&M
University. Logos are not included. Built by Jonas Karthein with Claude Code, September 2026.
