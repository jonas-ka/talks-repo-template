# How to use the FastSims log book (for Claude Code)

The FastSims log book is a Typst document that records **decisions, findings,
issues and open items** for the DOE Genesis FastSims subproject, in
chronological order. It complements the repo: the repo (CLAUDE.md, TODO.md,
docs/) says how things *are*; the log book says *what happened, when, and why*.

## Where it lives

The repository's `notes/` folder, versioned and pushed with the code
(it used to live on Google Drive and moved here on 2026-09-28).

| file | role |
|---|---|
| `genesis-fastsims-logbook.typ` | the log book — **edit this** |
| `labnotes-template.typ` | shared template (layout, lab colours, building blocks) — don't edit unless asked |
| `fig-*.pdf` | figures referenced by the log book (vector) |
| `genesis-fastsims-logbook.pdf` | the compiled log book, committed alongside the source |
| `FastSims-handoff-*.md` | handoff summaries between sessions |

Compile (Typst ≥ 0.11; `brew install typst` if missing), from that folder:

```sh
# from the repository root: the template is imported through a shim into lab/ (lab-templates)
typst compile --root . notes/<name>-logbook.typ
```

Always compile after editing and fix any error before finishing.

## Structure

1. `#show: labnotes.with(...)` — title block (project, author, start date, summary).
2. `= Project background` — living context (programme, superposition idea,
   beamline, source, code and data flow, "where things live"). This section may
   be *updated* when facts change.
3. Dated entries, **oldest first, newest last**. Since 2026-10-01: **one major entry per day**
   (`#day`), with every piece of work that day as a minor `#note` under it (below).

## Day entries and notes (since 2026-10-01)

A day is **one major entry**. The first log of a date opens it with `#day`; everything else done
that day is a `#note` *inside* it, tagged with its **project** (a short, stable name for a line
of work: `COMSOL basis`, `VISION`, `Surrogate`, `Systematics`, `Talks & figures`, `Log book &
guides`, …). Write the notes in the order the work happened, appending to the end of the day:
the text stays a strict chronological record. The **contents** list each day once and, under it,
one line per project with that project's notes as bullets, so two lines of work in parallel show
as two groups, not ten entries.

```typst
#day("YYYY-MM-DD", "What the day was about (update the title as the day goes on)",
  authors: [J. Karthein (with assistance from Claude Code)])[

#note("VISION", "Short title of this piece of work", tags: ("campaign", "usage"))[
#finding[...]
#decision[...]
]

#note("Surrogate", "Next piece of work, later the same day")[
...
]
]
```

- A new date opens a new `#day`; never add a second `#day` for the same date.
- The day's closing `]` stays at the end of the file. Insert a new `#note` before it.
- The day's *title* may be updated as the day goes on (it is a summary, not history). Notes are
  never moved or rewritten; correct one with a later note that says what was wrong.
- Keep project names stable from day to day, so the contents read like a project index.
- Entries before 2026-10-01 stay as the old one-`#entry`-per-topic form; `#entry` still works,
  so older log books compile unchanged and switch to days on their next date.

## Building blocks (from the template)

```typst
#day("YYYY-MM-DD", "Day title", authors: [...])[ #note("Project", "Title", tags: (...))[ ... ] ]

#entry("YYYY-MM-DD", "Short title",              // the pre-2026-10-01 form
  tags: ("COMSOL", "tracker", "sampling"),
  authors: [J. Karthein (with assistance from Claude Code)])[

== Subheading
Plain text for context.

#decision[What was decided and why.]
#finding[What was observed or measured, with numbers.]
#issue[*Symptom.* Cause. Fix.]
#todo[- Open item one
  - Open item two]
#context-box[Background that a reader needs.]
#refs(("Label": [value or path], "Script": raw("scripts/foo.py")))
#figure(image("fig-name.pdf", width: 100%), caption: [...])
]
```

Use `raw("...")` or backticks for paths, file names, electrode names and code.

## Rules

- **Append, don't rewrite history.** A new day gets a new `#day`; a new topic that day is a new
  `#note` inside it (before 2026-10-01: a new `#entry` per topic).
  Past entries are only changed to mark something resolved, e.g.
  `_Resolved 2026-09-27 (see entry …)_`, never to silently change what was
  written then. Corrections go in a new entry that says what was wrong.
- **Keep numbers.** Throughput, errors, DOFs, run times, file sizes — the log
  is where they survive.
- **Record the reason**, not only the result: why a decision was taken, what
  the alternative was.
- **Link, don't duplicate.** Point to repo files (`docs/COMSOL_EXPORT.md`,
  scripts, commits) instead of copying their content.
- **Open items** go in a `#todo` at the end of each entry; when they are done,
  mark them resolved in the later entry that settles them.
- **Authors line:** `J. Karthein (with assistance from Claude Code)` for work
  done in the Claude Code session; `J. Karthein` for decisions he supplied.
- **Figures:** vector PDF, `notes/fig-<topic>.pdf`, drawn **at log-book size**
  (about 7.2 in wide, 6–9 pt type) so the text stays legible — a poster-size
  figure scaled to the page shrinks its text to ~4 pt. Rasterize only dense
  content (field maps, hundreds of trajectories) inside the PDF, keeping axes and
  text vector. Make them with `scripts/logbook_figures.py` (one function per
  figure) or a plotting script's `--compact` mode, so they can be regenerated.
  The two early screenshots stay JPEG.
- **VISION GPU-hours:** after every run on VISION, log the run's GPU-hours and the cumulative
  total (`scripts/vision_usage.py`); fair-share priority drops with use.
- **No secrets:** no account details, tokens, SSH keys or anything from
  `docs/VISION.md` beyond the project name.
- After a substantial session, also write a short `FastSims-handoff-YYYY-MM-DD.md`
  in the same folder for the next session (status, what the other side needs to
  know, asks).
- **Commit** the `.typ`, the compiled PDF and new figures with explicit paths.

## Backfilling earlier work

Work from 2026-09-04 to 2026-09-25 was backfilled on 2026-09-28. If anything
else ever needs backfilling:

- Write one entry per coherent piece of work, **dated when it happened**
  (the git history and TODO.md's "Done recently" give dates).
- Insert backfilled entries where they belong chronologically, and put
  `(backfilled YYYY-MM-DD)` in each authors line.
- Update `started:` in the title block to the date of the earliest entry.
- Keep them concise: what was done, key numbers, decisions and their reasons,
  what was left open. Link to the repo docs for detail.
