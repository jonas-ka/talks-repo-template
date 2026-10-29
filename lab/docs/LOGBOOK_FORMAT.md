# Log-book entries as Markdown files: the format

A log book in which **every entry is one Markdown file** with a YAML header, kept in git and
checked before it is submitted. It records what happened, when and why: decisions, findings
with their numbers, problems and their fixes, open items. The repository and its documents say
how things *are*; the log book says what *happened*.

This is the format, the checker (`logbook/`, since v2026.10.16), the PDF and HTML view built
from the entries (since v2026.10.17), and the tools to write, cite, export, copy and migrate
entries with the GitHub setup that goes with them (since v2026.10.18). The Typst log books
(`#day`, `#note`, `#entry`, `docs/LOGBOOK_GUIDE.md`) keep working unchanged; moving one to this
format is offered by a migration tool, never forced. A complete example: `examples/logbook/`.

## Standalone or central

- **Standalone** (the default): any repository, entries in `entries/YYYY/`, any author names,
  any project names. Nothing else is needed.
- **Central** (several people, one repository): `logbook.yaml` at the root and three registries,
  `people.yaml`, `projects.yaml`, `apparatus.yaml` (examples in `examples/logbook/`). Then
  authors are handles from `people.yaml`, projects, sub-projects and apparatus must exist, and a
  pull request may only add entries whose first author is the person submitting. Nothing in the
  format or the checker needs a particular organisation, Drive or account.

## One entry

`entries/2026/2026-10-01-0930-aa-first-transmission-scan.md`: the file name is the entry's
**id**, `YYYY-MM-DD-HHMM-<handle>-<slug>`, in the folder of its year. Date and time are those of
the work (local time); the handle is the first author's; the slug is a few words of the title.

```markdown
---
date: 2026-10-01
time: "09:30"
authors: [aa]                 # first = the person submitting; more if others took part
with: claude                  # optional: written with assistance from Claude Code
kind: run                     # see "Kinds"
project: Example experiment
subproject: Ion source        # optional
apparatus: [source, beamline] # optional
title: First transmission scan of the extraction voltage
tags: [transmission]
runs: ["DAQ run r017"]
parameters:
  - {name: SRC:HV_Offset, value: 3000, unit: V}
figures:
  - file: figures/plot-example-transmission-scan-v1.pdf
    caption: "Transmission against extraction voltage (run r017)."
    alt: "Line plot of transmission ... maximum of 38 percent at -120 V ..."
data:
  - file: data/transmission-scan-r017.csv
    describes: plot-example-transmission-scan-v1
    source: "DAQ run r017; raw traces in the Drive folder Example/Data/Transmission/r017"
epics:
  - {file: epics/source-tune-2026-10-01T0930.json, group: source-tune}
---

Context in plain text, with [@Author2019] cited and [[2026-09-30-1600-bb-cage-rewired]] linked.

::: finding
Transmission peaks at −120 V with 38 %.
:::

::: issue {#issue-drift}
*Symptom.* The peak moves by 5 V in 20 minutes. Cause unknown. Open.
:::
```

Only `date`, `authors`, `kind`, `project` and `title` are required: a quick note stays quick.
The full list of header fields, with their meaning, is the JSON Schema
(`logbook/src/lablogbook/data/entry.schema.json`, or `logbook schema`).

**Never changed after it is merged.** A wrong number or conclusion is corrected by a new entry
(`kind: correction`, `corrects: <id>`) that says what was wrong; the views show the correction
with the old entry. Removing something that must not be stored is a `redaction` by an admin,
which names the kind of content and the reason, never the content.

**Dates.** `date` is when the work was done. An entry written more than two days later
(`late_days`) carries `backfilled: <the day it was written>`. The time an entry was *logged* is
the time its pull request was merged (GitHub's clock), shown next to `date` by the views.

## Kinds

| kind | for | the checker wants |
|---|---|---|
| `note` | any piece of work | |
| `run` | a measurement or beam time | `runs`, `parameters` (recommended) |
| `calibration` | a calibration | `apparatus`, `valid_until` (recommended) |
| `maintenance` | work on the apparatus | `apparatus`, `valid_until` (recommended) |
| `incident` | vacuum loss, HV trip, interlock, damage: never health information | `apparatus` |
| `meeting` | who was there, what was decided | `attendees` (recommended) |
| `correction` | what was wrong in an earlier entry | `corrects` |
| `order` | a purchase order (since v2026.10.34) | `order`, `items` |
| `redaction` | that something was removed, never what | `redacts`, `level` |

A central book adds kinds in its own `kinds.yaml` (same form as
`logbook/src/lablogbook/data/kinds.yaml`).

## Blocks

The body is Markdown. Five blocks carry the lab notebook's callouts, as fenced divs:
`::: decision`, `::: finding`, `::: issue`, `::: todo`, `::: context`, plus `::: incident`.
An `issue` or `todo` with an id (`::: todo {#todo-repeat}`) stays **open** until a later entry
lists it under `resolves: [<entry-id>#todo-repeat]`; the views show both directions, and
`logbook open-items` lists everything still open. Math is `$…$` (LaTeX).

**Priorities** (since v2026.10.32): an open item is `low`, `medium` (the default), `high` or
`asap`, written on the block (`::: todo {#todo-valve priority=asap}`). A later entry changes it
with `priority: {<entry-id>#todo-valve: low}` in its header; the latest entry that names an
item sets its priority, and the item links to it. Open items are listed most urgent first: an
item that has been ASAP for longer than `open_items.asap_days` (in `logbook.yaml`, default 2,
counted from the entry that made it ASAP) at the top, marked overdue; then by priority; then
the oldest first. The view, `logbook open-items [--priority asap]` and the digest use this
order; the view also filters by priority. The PDF shows a block's priority as written.

## Orders (since v2026.10.34)

An order is an entry of kind `order`. Its header names the order (`order: "109"`) and lists the
items: `n` (1, 2, …), `item`, and optionally `qty`, `unit_cost`, `total`, `info` (a quote's file
name or a link), `vendor`, `ordered`, and `arrived` (true, or a date) for an item that had arrived before
the entry was written. The body holds the table of items and one open item per item still
waiting, `::: todo {#item-<n> priority=low}`; `logbook.yaml` `orders: {currency: "$"}` sets the
symbol. Without a `vendor`, the view names the shop of the item's link or the supplier in its quote's file name; `orders: {vendors: {derived: better, …}}` renames one (`null`: not a vendor). An item has arrived once a later entry resolves it ("Resolve" on the item, or "All
arrived" for everything still open in an order). The view's **Purchases** page lists every item
of every order, newest order first, with its status ("Download CSV" saves the rows shown); `logbook orders [--open] [--json]` prints
the same. The site's workflow publishes it as `orders.json` on the branch `logbook-status`, for
tools outside GitHub (a purchasing sheet that ticks off what arrived). A script can submit an
order through the form: an issue whose body has the form's sections plus `### Order` and
`### Items` (a JSON list in a ```json block) becomes such an entry.

## Links

Every link is written once, in the newer entry, and the views compute the other direction.

| link | written as |
|---|---|
| to an entry, or one of its blocks | `[[<entry-id>]]`, `[[<entry-id>#issue-drift]]` in the text |
| related entries (a thread, a newer version of a figure) | `related: [<entry-id>, …]` |
| a correction | `corrects: <entry-id>` |
| an open item settled | `resolves: [<entry-id>#<block-id>]` |
| an open item's priority changed | `priority: {<entry-id>#<block-id>: low \| medium \| high \| asap}` |
| a wiki page | `[[wiki:apparatus/source]]` |
| a reference | `[@Author2019]`, `[see @Author2019; @Solo2021]` |

## The wiki and the references

`wiki/` holds what is true *now*: project pages, apparatus pages, procedures, how-tos. It is
living text (changed through pull requests like any file, with its history in git), checked for
compliance like entries but not append-only. A page needs no header; a page that must name what
the checker flags (a safety page about eye injuries, say) records that it was read with one,
exactly as an entry does (since v2026.10.19):

```markdown
---
reviewed: [health]
---
# Laser safety
```

`wiki/references.bib` is the reference list: BibTeX, every record with a DOI or an ISBN, keys
`LastnameYYYY`, the journal's short title in `shortjournal`, titles' capitals kept with double
braces. A citation whose key is missing fails the check. Citations render as
`Author A.++ Phys. Rev. Lett. 123, 456 (2019)` ("++": and others), linked to the DOI;
`logbook/src/lablogbook/data/karthein-lab.csl` is the style.

## Figures, data, attachments, settings

Paths are relative to the entry's folder (`entries/YYYY/`).

- **Figures** are saved with `labfig` (`matplotlib/labfig.py`) as versions:
  `figures/<name>-vN.pdf`, `.svg`, `.png` and the record `<name>-vN.yaml`. A plot needs its PDF
  (print) and its SVG (HTML view); photos and screenshots may be raster. A changed figure is a
  new version in a new entry (`related:` to the one that showed the old version); an old entry
  keeps showing what it showed. `library:` names the folder in a figure library.
- **Data**: the processed numbers a figure shows (CSV, JSON), with `source:` saying where the
  raw data lives. Raw data never goes into the log book.
- **Attachments**: any other file. A **PDF attachment, or a figure that is not a plot**, is
  *held* until the author confirms, per file, that it holds no export-controlled technical data
  (`export_control_confirmed: true`). If in doubt: do not confirm; link the file where it lives
  (a Drive link with restricted sharing) instead of attaching it.
- **EPICS settings**: `epics/<group>-<time>.json`, a snapshot of a named group of process
  variables (format `lab-epics-snapshot/1`, see `logbook/src/lablogbook/epics.py`); the groups
  are defined per apparatus in `apparatus.yaml`.
- Sizes: over 2 MB warns, over 5 MB fails (`limits` in `logbook.yaml`).

## The checker

```sh
uv run --project lab/logbook logbook check                         # everything
uv run --project lab/logbook logbook check entries/2026/<id>.md    # one entry
uv run --project lab/logbook logbook check --base origin/main --submitter <login> --ci   # a pull request
```

| it checks | if not |
|---|---|
| header against the schema; file name, folder, date, time, handle | fail |
| kind known; its required fields | fail (recommended fields: warning) |
| authors, projects, sub-projects, apparatus in the registries (central book) | fail |
| dated in the future; late without `backfilled` | fail |
| links, `corrects`, `related`, `redacts` point to existing entries; `resolves` and `priority` to an open issue or todo (`priority` to one already resolved: warning); `priority=` only on an issue or todo with an id | fail |
| citations exist in the reference list; new references have a DOI or ISBN | fail |
| files exist, inside `entries/`; sizes; plots have their SVG; drafts are not used; versions in figure names | fail / warning |
| EPICS snapshots parse; PVs belong to the group | fail |
| secrets (keys, tokens, private keys), home-folder paths | fail |
| Google Drive links | note: fine while the file's sharing stays restricted; `forbid_drive_ids: true` in `logbook.yaml` makes them fail |
| FERPA patterns: ID-shaped numbers (`privacy.id_pattern` in `logbook.yaml`; default nine digits), SSN-shaped numbers, grades, transcripts of records, enrolment, someone named as a student who is not a member, an institutional address of a non-member (`privacy.email_domains`; default every `.edu`) | fail; `reviewed: ferpa` in the header after reading turns them into recorded warnings |
| health words | fail; `reviewed: health` likewise |
| proprietary or export-control wording | warning |
| PDF attachments and non-plot figures | **held** until `export_control_confirmed: true` |
| in a pull request: existing entries and their files never change (except under a redaction by an admin); files outside `entries/` and `wiki/` only by an admin; the first author of a new entry is the submitter (an admin may submit on behalf) | fail |
| people who logged on the same project in the last 14 days | note: proposed as co-authors |

It finds patterns, not meaning: passing it does not make an entry compliant, reading it again
does. With `--ci` it never prints the text a finding matched, only file, line and kind of hit.
Exit code 0 fine, 1 failed, 3 held.

## Building: the PDF and the HTML view

```sh
uv run --project lab/logbook logbook build                     # build/logbook.pdf
uv run --project lab/logbook logbook build --html site         # the view as a folder (for GitHub Pages)
uv run --project lab/logbook logbook build --single view.html  # the view as one file, figures inside
```

Needs [pandoc](https://pandoc.org) (3.x) for both and [Typst](https://typst.app) 0.15 for the PDF.

- **The PDF** uses the lab notebook template: the wiki's project pages first, then one day per
  date with its entries, then the references. Links between entries, to blocks and to the
  project pages are live; citations link to their DOIs; "corrected by", "resolves" and "see
  also" come from later entries. It is built under PDF/UA-1, so figures go in as their SVG
  (with the `labfig` strip cut off); a figure that exists only as a PDF makes the build fall back
  to plain PDF and say so.
- **The HTML view** is for daily use, laid out like a notes app (a sidebar with the projects,
  apparatus and wiki pages; page titles; property tables; filter menus): search over the text, the settings and the EPICS values
  (`kind:run`, `by:aa`, `project:…`, `tag:…`, `on:<apparatus>` narrow it); filters by project,
  subproject, person, apparatus, kind, tag and dates, kept in the address so a filtered view can
  be shared; entries by day; each entry with its open and resolved blocks, corrections, EPICS
  snapshots (compare two snapshots of the same group), files, the thread of related entries and
  what links to it; an open-items board; project and apparatus pages from the wiki with current
  calibrations and incidents; people; the wiki; the references. `/` jumps to the search.
  Figures are shown as their SVG; a browser that cannot draw SVG paths (the Claude app's
  built-in browser, for one) is detected when the page opens and gets the PNG saved next to
  each SVG instead.
- **Buttons that act on the repository** (new entry, correct this entry, discuss, source, edit a
  wiki page, request an export) appear when `logbook.yaml` names it:

  ```yaml
  site: {repository: owner/name}       # optional: host (default https://github.com), branch (main)
  ```

  `logo: <path>` in `logbook.yaml` puts the lab's logo at the top of the sidebar (embedded in the page):
  a square one next to the title, a wide one (a word mark) as a banner above it, both on a light card.

## The tools (since v2026.10.18)

Every command runs from any folder inside the log book or a repository connected to it:
`uv run --project lab/logbook logbook <command>`. `logbook <command> --help` lists the options.

| Command | What it does |
|---|---|
| `new` | Writes an entry from a draft (`--from draft.md`, Markdown with a YAML header) or from flags (`--title`, `--project`, `--kind`, `--body`, …). Names the file, fills in the date, time, `logged` and `backfilled`, copies figures and files next to it, runs the checker, and asks about co-authors (people on the same project in the last 14 days) and the export-control confirmation for attachments. `--epics <group>` stores a snapshot of that PV group with the entry. |
| `cite add <DOI or ISBN>` | Looks the work up (Crossref, Open Library) and adds it to `wiki/references.bib` with a key like `Smith2019`; a work already there is not added twice. |
| `export` | A selection (`--project`, `--person`, `--apparatus`, `--kind`, `--tag`, `--from`, `--to`, `--query`, `--id`, `--release`) as a PDF with a cover page saying who asked, who approved, and what was selected. `--anonymise` shows authors as "Author 1", "Author 2". |
| `month` | The PDF of the entries logged in one month (`--month YYYY-MM`, default last month): `Logbook-YYYY-MM.pdf`. |
| `digest` | The weekly summary as Markdown: new entries by project, open items with their age, calibrations about to expire. |
| `pull` | In a connected repository: writes the repository's copy of its projects (see below). |
| `migrate <log.typ>` | Converts a Typst log book (`#day`, `#note`, `#entry`) into entries in `--into <book>`: callouts become blocks, figures are copied as version 1 (with SVG and PNG made from PDFs), the background section becomes a wiki page, the date of each entry's first commit becomes `logged`. Nothing is committed; a report lists what needs a look. Needs `--extra migrate`. `--new-only` after an earlier migration of the same log book: only the entries the book does not have yet, and a list of those whose text changed since. The source's name in `migrated_from` comes from its `origin` remote. A final `#day` titled "This log book has moved" (the freeze) is never migrated. |
| `epics snapshot <group>` / `epics restore <entry>` | Reads a PV group from `apparatus.yaml` into a snapshot file; shows the differences between a stored snapshot and the machine, and writes the stored values only after you confirm. Needs `--extra epics` and the lab's EPICS network. |
| `init-github` | Writes the "New entry" issue form and the workflows into `.github/` (below). |
| `init <dir>` | A new central log book: settings, registries, wiki skeleton, starter policy documents with `TODO`s, README, Makefile (LOGBOOK_SETUP.md). |
| `github-settings --repo O/N --admin LOGIN` | Prints a script that sets a GitHub repository up for a central book (ruleset, merges, Actions, label, environments, private Pages). |
| `check`, `build`, `open-items`, `schema` | As above. |

### Writing from a project repository

A project repository writes into the central book when its own `logbook.yaml` says so:

```yaml
central:
  repository: owner/logbook          # the central book on GitHub
  clone: ~/Projects/logbook          # a local clone of it
  project: FastSims                  # default project for entries written from here
  projects: [FastSims]               # what `logbook pull` copies here (default: [project])
```

Who you are comes from `~/.config/logbook/config.yaml` (`handle: aa`), else from your GitHub
login looked up in `people.yaml`. `logbook new` then works in a temporary checkout of the
central book's `main`: it commits the entry on a branch `entry/<handle>/<id>`, pushes it, opens a
pull request and lets it merge itself once the checks pass. Your clone and your working tree are
not touched. `--no-submit` keeps the branch local; `--dry-run` only checks.

`logbook pull` writes `logbook/` in the project repository: the entries of its projects with
their files, the wiki pages and references they need, the PDF, the one-file HTML view,
`SUMMARY.md` (read this first) and `GENERATED.md`, with the figures its wiki pages show. The copy
is generated and replaced by the next pull; never edit it. Its own `.gitignore` keeps the PDF and
the one-file view (large, rebuilt by every pull) out of git; commit the rest. It refuses a public repository always, an internal one unless
`projects.yaml` gives the project `copy_internal_until: <date>` in the future, and any repository
whose visibility it cannot find out.

## On GitHub (since v2026.10.18)

`logbook init-github` writes these files into the central book's `.github/`. They are copies, not
references to lab-templates: run it again after a lab-templates update (`--force` replaces
workflow files you have changed) and after a change to the registries (the form's menus come
from them).

| File | When | What |
|---|---|---|
| `ISSUE_TEMPLATE/new-entry.yml` | | The "New entry" form: the issue's title is the entry's title; then project, kind, the text, open items (one per line, each a resolvable `todo`; a line starting `ASAP:`, `High:` or `Low:` gives it that priority), files and the export-control confirmation; images dragged into the text are stored as figures (through the signed links of the issue's rendered HTML; photos without their metadata, a large one scaled down), and a caption, alt text and source written in the files field without a file of their own go with them; labels the form does not understand are reported on the issue; subproject, apparatus, co-authors, tags, date, corrects and resolves under "Optional". The view's links fill fields in: "New entry here" on a project or apparatus page, "Correct" on an entry, "Resolve" on an open item. |
| `workflows/logbook-entry-from-issue.yml` | a form is submitted | Turns the form into an entry committed as its author, runs the checker, opens a pull request that merges itself, and reports back on the issue. A pull request opened by a workflow starts no other workflow, so this one runs the checker itself and posts the required check `entry-checks`. After the merge it starts the site's build (a merge by the workflow's token starts no other workflow). |
| `workflows/logbook-checks.yml` | every pull request, every push to main | The check `entry-checks` that the ruleset requires. |
| `workflows/logbook-site.yml` | every push to main, and daily | Builds the HTML view and the PDF and publishes them with GitHub Pages; publishes the purchases' status as `orders.json` on the branch `logbook-status` when the book has orders. |
| `workflows/logbook-digest.yml` | Mondays | The digest as an issue "Week ending …". |
| `workflows/logbook-monthly.yml` | the 1st of each month | The previous month's PDF, the whole book and the sources as a release `snapshot/YYYY-MM`; waits for approval in the environment `attest`. `logbook deliver` copies these PDFs into a folder (a synced Drive folder, say). |
| `workflows/logbook-export.yml` | on request (Actions, "Run workflow") | An export; waits for approval in the environment `export` and logs the request on the issue "Exports". |

The workflows run on GitHub's machines, whose clock is UTC: set `timezone:` in `logbook.yaml`
(an IANA name, e.g. `America/Chicago`) so entries from the form, the view's "today" and the
reports use the lab's date and time. A submitted form makes one entry: the workflow closes the
issue when the entry's pull request is set to merge, and runs again only on an open issue whose
entry has not merged (after an edit that fixes a failed check). The merge commit names the
author as co-author.

What the repository needs, set once by an owner:

- **A ruleset on `main`**: pull requests only, the check `entry-checks` required, no force
  pushes, no deletions; the PI as the only bypass.
- **Auto-merge** allowed, and Actions allowed to create pull requests.
- **Environments** `export` and `attest`, each with the PI as required reviewer.
- **Pages** from "GitHub Actions", visibility private.
- The label `new-entry` (the form sets it; the workflow acts only on issues that carry it).

No workflow contains a secret: they use the workflow's own token, and every value from an issue
or an input reaches the scripts through environment variables, never pasted into a command.
