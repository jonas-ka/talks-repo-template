# How to use the talks-repo log book (for Claude Code)

The log book is a Typst document that records **decisions, findings, numbers, issues
and open items** for `talks-repo`, in chronological order. The repo (CLAUDE.md,
PROJECT_PLAN.md, README.md) says how things *are*; the log book says *what happened,
when, and why*. It follows the same template and rules as the FastSims log book in
`~/Projects/ion-optics-surrogate/notes/` (guide there: `LOGBOOK_GUIDE.md`).

**Since 2026-10-01: one `#day` entry per date, with project-grouped `#note`s under it** (append
only; the contents group each day's notes by project). See "Day entries and notes" in
`~/Projects/ion-optics-surrogate/notes/LOGBOOK_GUIDE.md`; the template here is a copy of that one.

## Where it lives

The repository's `notes/` folder, versioned with the code.

| file | role |
|---|---|
| `talks-repo-logbook.typ` | the log book — **edit this** |
| `labnotes-template.typ` | copy of the shared lab template (layout, colours, building blocks); the original lives in `ion-optics-surrogate/notes/` — don't edit unless asked |
| `fig-*.pdf` | figures referenced by the log book (vector where the source is vector) |
| `talks-repo-logbook.pdf` | the compiled log book, committed alongside the source |
| `talks-repo-handoff-*.md` | handoff summaries between sessions (optional) |

Compile from this folder (Typst ≥ 0.14):

```sh
typst compile talks-repo-logbook.typ
```

Always compile after editing and fix any error before finishing.

## Structure

1. `#show: labnotes.with(...)` — title block (project, author, start date, summary).
2. `= Project background` — living context (purpose, hard rules, the pipeline, where
   things live). This section may be *updated* when facts change.
3. Dated entries, **oldest first, newest last**.

## Building blocks (from the template)

```typst
#entry("YYYY-MM-DD", "Short title",
  tags: ("Stage E", "catalog"),
  authors: [J. Karthein (with assistance from Claude Code)])[

== Subheading
Plain text for context.

#decision[What was decided and why.]
#finding[What was observed or measured, with numbers.]
#issue[*Symptom.* Cause. Fix.]
#todo[- Open item one
  - Open item two]
#context-box[Background that a reader needs.]
#refs(("Commit": raw("abc1234"), "Deck": raw("talks/<slug>/")))
#figure(image("fig-name.pdf", width: 100%), caption: [...])
]
```

Use `raw("...")` or backticks for paths, file names, ids and code.

## Rules

- **Append, don't rewrite history.** A new day or topic gets a new `#entry`. Past entries
  are only changed to mark something resolved, e.g. `_Resolved 2026-10-02 (see entry …)_`.
  Corrections go in a new entry that says what was wrong.
- **Keep numbers.** Counts, costs, page counts, sizes, timings, the minute budget of a
  deck — the log is where they survive.
- **Record the reason**, not only the result: why a decision was taken, what the
  alternative was, what the author asked for in his own words where that matters.
- **Link, don't duplicate.** Point to repo files, blocks, briefs, reports and commits.
- **Open items** go in a `#todo` at the end of each entry; when done, mark them resolved
  in the later entry that settles them.
- **Authors line:** `J. Karthein (with assistance from Claude Code)` for work done in a
  Claude Code session; `J. Karthein` for decisions he supplied; add
  `(backfilled YYYY-MM-DD)` when an entry is written after the fact.
- **Figures:** vector PDF, `notes/fig-<topic>.pdf`, built by `scripts/logbook_figures.py`
  (tiles of deck or poster pages with embedded photos downsampled to ~110 dpi, text and
  plots kept vector). Regenerate with `uv run python scripts/logbook_figures.py`.
- **No secrets:** no credentials, tokens or Drive ids that are not already public.
- After a substantial session, write a short `talks-repo-handoff-YYYY-MM-DD.md` here if
  the next session needs state that is not in the repo.
- **Commit** the `.typ`, the compiled PDF and new figures with explicit paths.

## Backfilling earlier work

Work from 2026-09-17 to 2026-09-29 was backfilled on 2026-09-29 from the Claude Code
conversation and the git history. If anything else needs backfilling: one entry per
coherent piece of work, dated when it happened (git dates), inserted chronologically,
`(backfilled YYYY-MM-DD)` in the authors line, concise, linked to the repo for detail.
