# Changelog

Consumers read this before `scripts/lab-templates.sh pull <tag>`.

## v2026.10.41 (2026-10-29)

- **Captions: photos only by default** (tokens.typ). `cat-fig` gives a photo (catalog `kind: photo`)
  its catalog caption and hides the captions of every other kind; `fig(..., photo: true)` and
  `caption-line(..., photo: true)` mark a photo. `#captions(true)` shows every caption again (the old
  behaviour), `#captions(false)` none; `caption-on: true | false` (or `caption-line(on:)`) is a
  per-figure exception. **Consumers** whose plots relied on captions add `#captions(true)`.
- **Footer citations at one size** (10 pt, `cite-size`), never scaled down: one wider than `cite-max`
  (440 pt beside the sponsor logos, 540 pt without) stops the build with its text. **This can break
  a deck that compiled before**: shorten the citation. New helpers `doi(id)[...]`, `arxiv(id)[...]`
  and `refs(a, b, ...)` (references kept apart by a spaced middle dot, `cite-sep`; citations per
  build step are joined with it too).
- **Title slide:** `config-info(honorific: ...)` sets the presenter's honorific (default "Prof. Dr. ",
  `none` for none); name and event sit 12 pt lower.
- **Style guides:** physical quantities in italics (*N*, *Z*, *μ*), in figures as on slides
  (STYLE.md, FIGURES_README.md).

## v2026.10.40 (2026-10-21)

- **Title slide:** the build line reads "v2026.10.37 · git 670dc43"; the word "Template" in front of
  the version is gone.

## v2026.10.39 (2026-10-21)

- **The form no longer offers the kind `order`:** only a script writes an order (with its
  items as JSON); someone who chose it for a check-off got two failed checks. A kind marked
  `form: false` in `kinds.yaml` is left out of the "New entry" form. **Run `logbook init-github`.**
- The checker says "an order entry", not "a order entry".
## v2026.10.38 (2026-10-21)

- **Purchases: a Vendor column** (also searched, and in "Download CSV"). An item's own `vendor`
  (new, optional) or, without it, the shop its link names (amazon.com → Amazon,
  mcmaster.com → McMaster-Carr) or the supplier its quote's file name names ("YYMM.ISEG-quote-…",
  "YYMM.Pumps-quote-Pfeiffer-…"). A book renames or hides derived names in `logbook.yaml`:
  `orders: {vendors: {"MV": "MV Power", "Ablation": null}}`.

## v2026.10.37 (2026-10-20)

- **The official <Your University> logo in the slide header.** `themes/logos/tamu-box.svg` (the maroon box
  from marcomm.tamu.edu's logo downloads, cropped to the box and ®, vector) replaces the Texas
  outline `tamu-mark.png`. **Consumers** copy `tamu-box.svg` into their `themes/logos/`.
- **Citations per build step:** `footer-citation` also takes a list of `(steps, citation)` pairs,
  steps as in `only` (`(("2", [...]), ("3-", [...]))`), so a citation appears with the step that
  shows what it cites; plain content still shows on every step (docs/STYLE.md).
- **Citations are tagged slide content** at the footer's centre line instead of part of the
  footer: the footer is a PDF artifact, not read aloud, and under UA-1 a link there is refused.
  Citations may now carry links.
- **Title slide:** the institute logo sits on the band's bottom edge, the lab logo below it.

## v2026.10.36 (2026-10-19)

Found with a form entry that never arrived:

- **Images from the form in a private repository:** GitHub does not serve an attachment's
  `github.com/user-attachments/…` link to a token, so the form's workflow failed with "HTTP
  Error 404". It now takes each image through the signed link in the issue's rendered HTML. A
  failed download names the file, and a web page served instead of the file is caught.
- **Photos from the form lose their metadata** (EXIF: camera, time, GPS location), and one over
  2 MB is scaled down (at most 2400 px on the long side, JPEG) so it stays under the limits.
  This needs Pillow, now a dependency.
- **A form entry is dated when it was submitted**, not when the workflow reads it (a rerun days
  later kept today's date).
- **Missing alt text:** the issue's comment says how to add it, for an image in the text or a
  file in "Figures and files".

## v2026.10.35 (2026-10-16)

- **Purchases page: "Download CSV"** saves the items shown (after the filter and "Open only")
  as a table for Excel or Google Sheets: order, item, quantity, unit cost, total, ordered date,
  status, when and in which entry an item arrived, quote or link, and the order's entry.

## v2026.10.34 (2026-10-16)

- **Orders** (`docs/LOGBOOK_FORMAT.md`, "Orders"): a new kind `order` lists its items in the
  header (`order`, `items`); every item not yet arrived is a low-priority open item
  `#item-<n>` until a later entry resolves it. The view gets a **Purchases** page (every item,
  newest order first, open or arrived, "Resolve" per item and "All arrived" per order); `logbook
  orders [--open] [--json]`; the form takes an order from a script (`### Order` and `### Items`,
  JSON). The site's workflow publishes `orders.json` on the branch `logbook-status`, so it now
  needs `contents: write`. **Run `logbook init-github --force`.**

## v2026.10.33 (2026-10-15)

- **`logbook migrate`: references keep their file names.** `#refs((…))` values lost every `_`
  and `*` (`tests/test_scaling.py` became `tests/testscaling.py`), and `link("…")[…]` came out
  as Typst code. They are now plain text in an entry's `refs` (code marks removed, what is
  inside them kept; a link as "text (url)") and Markdown on a wiki page (code kept as code,
  links as links). A project background's "Where things live" no longer gets the heading
  twice, nor every value wrapped in one code span. Books migrated before keep what was
  written: re-check `refs` of migrated entries.
- **Export PDF:** the header line "Project:" names the selected projects only (it read
  "project Lab; dated …"); the whole selection stays in the summary.

## v2026.10.32 (2026-10-15)

- **Priorities for open items** (`docs/LOGBOOK_FORMAT.md`, "Blocks"): `low`, `medium` (the
  default), `high`, `asap`, on the block (`::: todo {#todo-x priority=high}`) or changed by a
  later entry (`priority: {<entry-id>#todo-x: low}`). Open items are listed most urgent first: an
  item ASAP for longer than `open_items.asap_days` (default 2) on top, marked overdue, then by
  priority, then the oldest. In the view (with a priority filter and an order), in
  `logbook open-items [--priority …]` and in the digest; the PDF shows a written priority. The
  form: a line under "Open items" starting with `ASAP:`, `High:` or `Low:`. The checker fails an
  unknown level, a `priority` naming no open item, and `priority=` on another kind of block.
  **Run `logbook init-github`** (the form's help text).

## v2026.10.31 (2026-10-15)

**Changes what some documents show; read before pulling.**

- **No personal defaults in the templates.** The slide footer shows the **presenter's** address:
  `karthein-theme(email: ...)` (or `config-info(email: ...)`) now defaults to none instead of one
  person's address, and a deck without it shows no address. The poster footer's `contact` and
  `website` default to none as well. The log-book template's `author` has no default and must be
  given. **To keep a document as it was,** pass the address (`email: [name\@example.edu]`,
  `contact: "name@example.edu"`, `website: "..."`) or the author explicitly.
- **Figure scripts run with uv.** `labfig.save` refuses to write a figure version from a script that
  was not started with `uv run` (dependencies pinned in the script's inline metadata or the
  project's uv.lock), so the environment can be rebuilt; the record keeps it (`environment:`
  Python and package versions, the inline metadata or the uv.lock checksum). Drafts and notebooks
  (Colab) are exempt. **Outside the lab, or to keep an old workflow,** set `LABFIG_ALLOW_NO_UV=1`.
- **Raw data linked both ways.** `labfig.save(..., raw=[...])` records where the raw data lives
  (repository and path, Drive path, URL or description; no absolute paths) and appends a line to a
  `FIGURES.yaml` next to every local raw location (figure, version, Drive folder, record), so the
  data points back to its figures. `python labfig.py where-used <data>` lists the figures made from
  a data file or folder (from `FIGURES.yaml`, and with `--archive` from the records' checksums).
- The example script pins its dependencies inline and runs as `uv run plot_cpi.py`; its raw source
  (the BLS API) is in `raw=`. The example figure itself is unchanged (version 3).
- `docs/FIGURES_README.md`, `README.md`: the uv rule, the raw-data links.

## v2026.10.30 (2026-10-15)

- `scripts/sync_drive.py` compares each file with its **newest** copy on the Drive (the plain
  name or a versioned one, `<name>-vYYYY.MM.N`), not only with the plain name, so an unchanged
  file is no longer uploaded again under a new version name. Still create-only.

## v2026.10.29 (2026-10-15)

- **The PDF with a task list builds on any machine:** pandoc writes `- [ ]` and `- [x]` as the
  characters ☐ and ☒, which none of the template's fonts has, and PDF/UA refuses the fallback
  font, so the PDF failed wherever no system font has them (a Mac). The boxes are now drawn.
- **`logbook deliver --to <folder>`:** copies each attested monthly PDF (the `snapshot/YYYY-MM`
  releases; `--full` also the whole book) that is not yet in the folder, e.g. a synced Drive
  folder; `--launch-agent <label>` prints a macOS LaunchAgent that runs it daily. Uses `gh`.

## v2026.10.28 (2026-10-15)

Found in the pilot:

- **Entries from the form now appear on the site:** a merge by the workflow's own token starts
  no other workflow, so the site never rebuilt for them. The form's workflow waits for its entry
  to merge and starts the site's build; the site also rebuilds once a day. **Run
  `logbook init-github --force`.**
- **The form:** an "Open items" field (one per line, each becomes a `todo` a later entry can
  resolve, no block syntax needed); images dragged into the text are downloaded and stored as
  figures (before, they stayed links to GitHub's attachment store, which the site cannot load);
  a caption, alt text and source written in the files field without a file go with them;
  `Alt text:` is read as `Alt:`; labels the form does not understand ("Atl:") are reported on
  the issue; downloads get their file extension from their media type.
- **`logbook check`:** a block line that cannot be read (`::: todo {#todo-1` without its `}`)
  or a block never closed fails for a new entry (a warning for one already in the book).
- **`logbook pull`:** the figures the copied wiki pages show are copied too (the PDF and the
  view failed with "No such file or directory"); the copy's `.gitignore` keeps its PDF and
  one-file view out of git.
- `docs/LOGBOOK_SETUP.md`: troubleshooting (a `.venv` in an iCloud-synced folder with Python
  3.14: `UV_NO_EDITABLE=1`, or keep repositories out of iCloud).

## v2026.10.27 (2026-10-15)

A central log book from scratch, for any lab (`docs/LOGBOOK_SETUP.md`):

- **`logbook init <dir>`**: settings, registries, a wiki skeleton, a README, a Makefile and
  starter policy documents (`docs/COMPLIANCE.md`, `docs/REDACTION.md`) in which every
  institution-specific fact is a marked `TODO(...)`; it overwrites nothing.
- **`logbook github-settings --repo O/N --admin LOGIN`** prints a script for the repository's
  owner: squash-only merges with the description as message, auto-merge, Actions allowed to open
  pull requests, the label `new-entry`, the environments `export` and `attest`, the ruleset on
  `main` (its check required from GitHub Actions; the admin role as bypass), private Pages
  (turned off again, and the script stops, where Pages cannot be private).
- `logbook init-github` also writes `CODEOWNERS` (the admins own everything outside `entries/`
  and `wiki/`), never replacing one that exists.
- **The checker's local rules in `logbook.yaml`**: `privacy.email_domains` (institutional
  addresses of non-members are flagged; default every `.edu`, replacing the fixed
  university domain) and `privacy.id_pattern` (student or staff ID numbers; default nine
  digits; `null` turns it off). **A book that relied on the fixed domain sets
  `privacy: {email_domains: [<its domain>]}`** before pulling this tag, or it flags every `.edu` address.
- `docs/LOGBOOK_SETUP.md`: decisions to make first (hosting and who reads it, private Pages,
  policy, AI tools), creating the book, GitHub, a starting point for GitLab (not yet tested),
  and what was learned (subtree lines in squash merges, stacked pull requests, custom domains).

## v2026.10.26 (2026-10-14)

- `docs/FIGURES_README.md`, `matplotlib/labfig.py`: **when a figure version is frozen.** Once it
  is committed to git, on the Drive or used in a document (talk, poster, paper, log-book entry);
  before that it may be redrawn under the same number (delete its files first; `save` still
  refuses to overwrite), and `draft=True` is the way to work on it. Documentation only.

## v2026.10.25 (2026-10-14)

- **"New entry" form, shorter:** the issue's own title is the entry's title (the separate Title
  field is gone, as is the "Entry: " prefix); project, kind and the text come first, then files
  and the export-control confirmation; subproject, apparatus, co-authors, tags, date, corrects
  and resolves sit under "Optional"; shorter help texts. Issues filed with the earlier form are
  still read. **Run `logbook init-github`** in a book to get it.
- **Prefilled links in the view:** "New entry here" on a project page (the project) and on an
  apparatus page (the apparatus), "Resolve" on every open item (the item, project, subproject
  and a title), "Correct" now also sets the kind and subproject. GitHub fills the form's fields
  from the link.
- **`logbook migrate --new-only`:** a carry-over after an earlier migration of the same log book:
  only the entries the book does not have yet; existing ones are left alone and listed when their
  text changed since. The source's name in `migrated_from` comes from its `origin` remote, so a
  clone in another folder no longer writes that folder's name. The freeze note ("This log book
  has moved") is never migrated.

## v2026.10.24 (2026-10-13)

Found with the first migration pull requests on GitHub:

- `logbook check` in a pull request: a migrated entry (`migrated_from` and `logged`) is late only
  if it was late when its source was committed; before, every migrated entry older than two days
  failed. Only an admin may submit migrated entries, so the fields cannot excuse a late entry.
- `logbook migrate`: a note not found in git history and older than `late_days` gets
  `backfilled:` with the day of the migration.

## v2026.10.23 (2026-10-13)

- `logbook migrate`: a figure path starting with `/` is read from the repository root, as Typst
  reads it (`image("/notes/fig.png")`); before, such figures were reported missing.

## v2026.10.22 (2026-10-13)

Found migrating the ion-source log book:

- `logbook migrate`: a reference to a figure (`@fig-source`) becomes a link to the entry or wiki
  page that holds the figure ("the figure on …"), not a citation that fails the check; the
  figure's label is removed. Images in the project background are copied next to the wiki page
  (`wiki/projects/figures/`); before, the page pointed at a file that was not there.
- `logbook build`: an entry's or wiki page's own headings are renumbered without gaps (`##` then
  `####` become levels 3 and 4 under a note); a skipped level made the PDF/UA-1 build fail.
- Figure captions and alt text are shown as plain text in both outputs, so Markdown in them
  (`**bold**`, `` `code` ``, links) no longer shows its marks.

## v2026.10.21 (2026-10-13)

Found with the lab's first entry through the form on GitHub:

- **`timezone:` in `logbook.yaml`** (IANA name, e.g. `America/Chicago`): new entries, the
  checker's "today", the view and the reports use it. Without it, an entry from the form was
  dated by the runner's UTC clock (19:59 in Texas became the next day, 00:59).
- **Entry from the form, once:** the workflow runs one at a time per issue, and an issue that is
  closed or whose entry has merged is left alone. Opening an issue with its label fires two
  events, which raced; an edit after the merge would have made a second entry.
- The workflow closes the issue itself when the entry is set to merge ("Closes #N" is not
  applied to a merge by the workflow's token), and the merge commit names the author as
  co-author. **Run `logbook init-github --force`** in a central book to get the new workflow.

## v2026.10.20 (2026-10-13)

- `logbook build`: formulas in entries and wiki pages get their TeX source as alt text in the
  PDF. Before, any `$…$` made the PDF/UA-1 build fail ("missing alt text").
- `logbook new`: a short header item stays on one line (`tags: [a, b]`, a parameter), a longer
  one (a figure with its caption and alt text) is written as an indented block, so headers read
  well on GitHub. Entry ids end after a whole word (`…-at-3-kv`, not `…-with-a-fi`); the same for
  `logbook migrate`.
- `logbook cite add`: the lab's journal list (`data/journals.yaml`) wins over Crossref's short
  title, which is sometimes the full one (International Journal of Mass Spectrometry).

## v2026.10.19 (2026-10-13)

- HTML view: an image logo sits on a small light card, so a logo with dark lines on a
  transparent background stays visible in the dark theme. A wide logo (a word mark, wider than
  1.6 times its height) is shown as a banner across the top of the sidebar; before, it was
  squeezed into a 30-pixel square.
- HTML view: "1 entry", not "1 entries".
- Wiki pages may start with a YAML header `reviewed: [ferpa, health]`, the checker's override
  after reading, as in entries (`docs/LOGBOOK_FORMAT.md`, "The wiki and the references"). The
  header is not shown in the PDF, the view or a project's copy.

## v2026.10.18 (2026-10-13)

- **The log book's tools** (`docs/LOGBOOK_FORMAT.md`, "The tools"; `logbook <command> --help`):
  - `logbook new`: an entry from a draft or from flags. Names the file, fills in date, time,
    `logged` and `backfilled`, copies figures and files next to it, runs the checker, proposes
    co-authors, asks for the export-control confirmation. In a repository connected to a central
    book (`central:` in its `logbook.yaml`) it submits the entry as a pull request that merges
    itself, from a temporary checkout, without touching your clone. `--epics <group>` stores a
    snapshot of a PV group with the entry.
  - `logbook cite add <DOI or ISBN>`: a reference from Crossref or Open Library into
    `wiki/references.bib`, journal titles abbreviated, no duplicates.
  - `logbook export` (a selection as a PDF, with who asked and who approved; `--anonymise`),
    `logbook month` (`Logbook-YYYY-MM.pdf`), `logbook digest` (the weekly summary).
  - `logbook pull`: a project repository's generated copy of its projects (`logbook/`, with
    `SUMMARY.md`, the PDF and the one-file view). Never into a public repository; into an
    internal one only with a dated permission in `projects.yaml` (`copy_internal_until`).
  - `logbook migrate <log.typ>`: a Typst log book into entries (callouts into blocks, figures
    copied as version 1 with SVG and PNG, the background into a wiki page, `logged` from git).
    Nothing is committed; a report lists what needs a look. Extra: `--extra migrate` (pymupdf).
  - `logbook epics snapshot|restore`: EPICS settings read into a snapshot, and a stored
    snapshot written back after the differences are shown and confirmed. Extra: `--extra epics`
    (caproto).
- **On GitHub** (`docs/LOGBOOK_FORMAT.md`, "On GitHub"): `logbook init-github` writes the "New
  entry" issue form (menus from the registries) and six workflows into `.github/`: the required
  check `entry-checks`, entries from submitted forms, the HTML view on GitHub Pages, the weekly
  digest, the monthly snapshot release (approved in the environment `attest`), and exports
  (approved in the environment `export`). They are copied, not referenced: run it again after an
  update. No secrets; inputs reach the scripts only through environment variables.
- `logbook build`: the Python module for the view is now `htmlview` (it shadowed the standard
  library's `html`); output unchanged.
- `make logbook` and CI run the tests with the EPICS and migration extras (the EPICS test starts
  a soft IOC on the loopback interface).

## v2026.10.17 (2026-10-13)

- **`logbook build`: the log book as a PDF and as an HTML view** (`docs/LOGBOOK_FORMAT.md`,
  "Building"). Both are made from the Markdown entries through pandoc with two Lua filters and
  the lab's CSL style; citations link to their DOIs, `[[links]]` and block ids become links in
  both.
  - **PDF**: the lab notebook template (`notes/labnotes-template.typ`), one `#day` per date and
    one `#note` per entry, the template's callouts, the project pages of the wiki first and the
    reference list last; parameters, EPICS snapshots, files and repository references as tables;
    "corrected by", "resolves" and "see also" computed from later entries. Figures go in as their
    SVG with the `labfig` strip cut off (PDF/UA-1 cannot embed PDF images); a figure that exists
    only as a PDF makes the build fall back to plain PDF, with a note.
  - **HTML view**, for daily use in the lab, in the lab's colours: a sidebar (projects,
    apparatus, wiki pages; folds away), entries as cards with a thumbnail of their first figure
    and a "Full entries" switch to read the selection in one scroll, compact entry headers,
    callouts in the notebook template's colours, related entries in a separate box, author
    avatars, filter menus: search over text, settings and EPICS values; filters
    by project and subproject, person, apparatus, kind, tag, dates, open items, figures, release
    candidates (kept in the address, so a filtered view can be shared); entries by day; an entry
    page with its open/resolved blocks, correction and resolution banners, EPICS snapshots that
    can be compared with another snapshot of the same group, files, thread of related entries and
    backlinks; an open-items board; project and apparatus pages (wiki text, current calibrations,
    incidents, snapshots); people; wiki; references. Light and dark, keyboard (`/` searches),
    phone width. Two builds: a folder (`--html`, for GitHub Pages) and one self-contained file
    (`--single`). Buttons for a new entry, a correction, the discussion and an export appear when
    `logbook.yaml` names the repository (`site: {repository: owner/name}`). Figures are
    their SVG; the Claude app's built-in browser (which cannot paint SVG paths; recognised by its
    user agent) and any browser failing a canvas test get the PNG next to each SVG.
- `notes/labnotes-template.typ`: no stray comma after the author when no affiliation is given
  (output unchanged otherwise).
- Example book: `author`/`affiliation` in `logbook.yaml`; the example figure's version 2 (label
  moved off the curve) in a new entry linked to the one that shows version 1.
- `make logbook` also builds the example's PDF and view into `build/`; CI installs pandoc 3.12.

## v2026.10.16 (2026-10-13)

- **Log-book entries as Markdown files** (`logbook/`, new; `docs/LOGBOOK_FORMAT.md`): one file
  per entry, `entries/YYYY/YYYY-MM-DD-HHMM-<handle>-<slug>.md`, with a YAML header (only date,
  authors, kind, project and title required) and the notebook's callouts as fenced divs
  (`::: finding`, `::: issue {#id}`, …). Kinds note, run, calibration, maintenance, incident,
  meeting, correction, redaction; links between entries written once (`[[id]]`, `related`,
  `corrects`, `resolves: [id#block]` for open issues and todos), computed both ways; a wiki
  folder; a BibTeX reference list cited as `[@Key]` and rendered as
  `Author A.++ Phys. Rev. Lett. 123, 456 (2019)` (CSL style `karthein-lab.csl`); figures as
  `labfig` versions, processed data, attachments, EPICS snapshots (`lab-epics-snapshot/1`).
- **`logbook check`**, the submission checker (Python, `uv run --project lab/logbook logbook
  check`): schema, names and dates, registries, links and open items, citations, files and
  sizes, secrets and home paths, Google Drive links (a note: fine while their sharing stays
  restricted; `forbid_drive_ids: true` makes them fail), FERPA and health patterns (override `reviewed:` after reading,
  recorded), export-control hold for PDF attachments and non-plot figures, and for a pull
  request: append-only entries, tooling changed only by an admin, the submitter as first
  author, proposed co-authors. `--ci` never prints the matched text. `logbook open-items`,
  `logbook schema`. Rendering (PDF, HTML view) and the rest of the CLI follow.
- **Standalone by default**: works in any repository without configuration; a central log book
  adds `logbook.yaml` and registries of people, projects and apparatus. Example:
  `examples/logbook/` (made-up people, Crossref test DOIs). The Typst log books (`#day`,
  `#note`, `#entry`) are unchanged.
- `make logbook` and a CI step run the tests and check the example (needs uv).

## v2026.10.15 (2026-10-13)

- `labfig.save` restores the axes positions the script left before laying out each file, so every
  file gets exactly one layout pass at its own resolution, from the same starting state, as a
  script's own `savefig(bbox_inches="tight")` would. A constrained layout that never settles no
  longer drifts from PDF to SVG to PNG (v2026.10.14 let the PNG, drawn last, come out 2 % off for
  the FastSims flight-potential figure). The three files of a version are now consistent.

## v2026.10.14 (2026-10-13)

- `labfig.save` lays out and measures each file at its own resolution (the PNG at 300 dpi, PDF
  and SVG at `savefig.dpi`) and freezes that layout for the save, exactly as savefig's
  `bbox_inches="tight"` does. v2026.10.13 froze the layout of one draw at screen resolution, which
  shifted legends slightly in some figures. Redrawn lab figures now match their old versions
  to within 0.1 % in aspect ratio.

## v2026.10.13 (2026-10-13)

- `labfig.save` freezes the figure's layout while it writes the files (as savefig's
  `bbox_inches="tight"` does). A constrained layout that does not settle (equal-aspect axes with a
  colour bar) moved on every draw, so the strip could cut through the x label and PDF, SVG and
  PNG came out slightly different. Found redrawing the FastSims bender figure; checked there.

## v2026.10.12 (2026-10-13)

From redrawing the lab's Drive figures with `labfig`:
- `labfig.save` works on a figure the script already closed (`plt.close(fig)` drops the canvas
  in matplotlib 3.11; `save` gives it an Agg canvas again; the drawing is unchanged).
- The record keeps the **command line** the script was run with (`command:`; absolute paths
  made relative to the figure folder or shortened to the file name) and an optional `note=`
  for anything else needed to redraw exactly (e.g. an environment setting).
- `code=` takes a list: the script and the modules it imports are all copied per version
  (`code/<stem>-vN.py`); the record lists the copies (`code.copies`).

## v2026.10.11 (2026-10-13)

- **Themes find the information strip themselves:** `fig` and `cat-fig` (slides, notes, posters)
  now cut the strip of any figure saved with `labfig`, also without a catalog `info_strip` field:
  they read the SVG and find the marker `labfig info_strip_in=0.4`, which `labfig.save` now writes
  into the PDF, SVG and PNG metadata, or, for files from v2026.10.10, the link to this repository
  in the strip. `strip: auto` is the new default of `fig`; `0pt` keeps a file whole; a catalog
  `info_strip` still wins. Files without a strip are shown as before. (PDF-only and PNG-only
  catalog entries need the field: Typst cannot search those files.)
- `scripts/propagate.sh`: after a consumer's build check, the files the check rewrote (build
  reports, "generated on" lines) are restored, so the next run does not skip that repository
  for "uncommitted changes". The tree was clean before the pull, so nothing else is touched.

## v2026.10.10 (2026-10-13)

- **Information strip below figures** (`matplotlib/labfig.py`, new): `labfig.save(fig, path,
  author=, created=, modified_by=, modified=, drive_folder=, drive_url=)` writes PDF, SVG and a
  300 dpi PNG from the same figure and adds a 0.4 in band under a dashed cut line: who made the
  figure and when, who changed it last and when, the lab-templates version and git id (linked
  to the repository; in a consumer, the upstream commit of the last subtree pull), and the Drive
  folder (name as text, linked in PDF and SVG). Cut it off in documents. `labfig.style()`
  applies the lab style (STIXGeneral where STIX Two is missing, e.g. Colab). The Drive link is
  passed in by whoever saves the figure, never stored here.
- **Themes cut the strip off:** a catalog entry with `info_strip: 0.4` is shown without its
  bottom 0.4 in by `cat-fig` (slides, notes, posters), and `fig(..., strip: 0.4in)` does it for a
  path (`themes/figure-strip.typ`, new). Entries without the field are shown whole, as before.
- **Figure versions in the file name, never overwritten:** `labfig.save(..., version=N)` writes
  `<name>-vN.pdf/.svg/.png`, shows "Version N" on the strip's first line, and refuses to write
  a version whose files exist (the error names the next free number); `draft=True` writes
  `<name>-draft.*` for work in progress. `labfig.versions(path)` lists the existing versions.
- **What made each version, kept without duplicating anything large:** the record
  `<name>-vN.yaml` (author, dates, version, template id, the script's repository and commit
  without credentials, data files with checksums, Drive folder; relative paths only), a copy of
  the script in `code/<script>-vN.py` (`code=None` for scripts in git, `code=<path>` for a
  notebook), and the **data fingerprint** (`data=[files]`, SHA-256 over names and contents;
  first 7 characters on the strip, `labfig.fingerprint()` to check data later; `data_id=` adds
  a label). `save` warns when a data file an earlier version used has changed in place.
- `docs/FIGURES_README.md`: one folder per figure with every version side by side (nothing
  overwritten, moved or renamed; replaces moving the old version into `v<N>_<date>_<name>/`,
  which older folders keep); changed data gets a new file name; a new folder only for a
  different figure; variants as `<name>-poster-vN`; `figure.yaml` keeps caption, alt text and
  topic.
- Example figure and `plot_cpi.py` saved with `labfig`, now version 3 (`…-v3.pdf/.svg/.yaml`;
  the strip is a visual change), with the data fingerprint, `info_strip: 0.4` in the catalog;
  the Colab notebook loads `labfig` from this repository and saves with it; its intro follows
  the current figure rules. `docs/FIGURES_README.md`, `docs/STYLE.md`, `README.md` describe the
  strip.

## v2026.10.9 (2026-10-13)

- Notes theme (`themes/karthein-notes.typ`), from `phys689-nucl-exp`: `notes(page: (:))` passes
  extra `set page` arguments into the theme's page setup, e.g. `page: (width: 11in, height: auto)`
  for one continuous landscape page (explicit width and height take precedence over `paper` in
  Typst); the default is unchanged.
- `scripts/propagate.sh`: the talks-repo build check compiles the newest `talks/*.group-meeting`
  deck instead of a fixed folder (talk folders are now named `YYMM.DD.<name>`, the author 2026-10-13);
  the poster theme's header comment names the renamed poster folder.
- `CLAUDE.md`: colleagues outside the lab use this repository, so a tag must not break documents
  that compiled under the previous one, and defaults stay free of lab infrastructure (lab
  behaviour opt-in); the log-book tooling to come is standalone by default.

## v2026.10.8 (2026-10-13)

- **Example figure redrawn** (`plot-us-cpi-u-yoy-2023-2026`, version 2): `plot_cpi.py` now starts
  from `karthein.mplstyle` at 6 × 4 in (15 / 13 pt), legend inside without a frame, no title or
  grid, black annotations in empty regions; PDF and SVG come from the same figure object (the
  SVG with text as outlines, so it looks the same in every Typst build). The alt text's values
  corrected (lows 2.3–2.4 %, peak about 4.2 %).
- **Figure sizes, decided:** `themes/karthein.mplstyle` now sets 15 pt bold axis labels and 13 pt
  ticks and legend at 6 × 4 in (it had 11 / 9.5 pt, against the guide and the template notebook).
  One size for slides and papers: about 12 / 11 pt beside text on a slide, 9 / 8 pt in a paper
  column. Figures drawn with the style file come out larger when redrawn.
- `docs/FIGURES_README.md`: start each script with `karthein.mplstyle` (not the `fastsims`-only
  `lab_style`); `figure.yaml` gains `version` and `variant`, and `supersedes` has one meaning;
  names may keep capitals where the name has them (FastSims, H200); coloured text uses the
  `plot_text` colours. `docs/STYLE.md` states the sizes.
- `scripts/lab-templates.sh check`: says whether a newer tag is out and how to update; never
  pulls and never fails a build (offline it says it did not check). Consumers run it first in
  every build. `pull latest` updates to the newest tag. The script now works on the repository
  root wherever it sits, so consumers use `lab/scripts/lab-templates.sh`, which every pull keeps
  current; the copy in a consumer's `scripts/` is only needed for the first `add`.
- `README.md`: the file tree as it is (exam theme, `assets/`, `propagate.sh`), what you need
  (Typst 0.15.1, packages, fonts), `<tag>` in the commands, "Staying up to date"; licence MIT
  for everything (the earlier "CC BY 4.0 for themes and documents" had no licence file).
- `assets/sources/cpi-u-yoy/`: the script and saved BLS data of the example figure, which
  `assets/catalog.yaml` pointed to but which were only in `phys206-mechanics`.
- CI: the private-material scan also reads `.ipynb`, `.json`, `.svg` and `.yml` files.
  `update-consumers.yml`: `cyclotron-talks` added.

## v2026.10.7 (2026-10-07)

- `scripts/lab-templates.sh pull` works in a repository made from `talks-repo-template`: there
  `lab/` is a plain copy without subtree history, so the first pull replaces it by the subtree
  (one commit removing the copy, then `git subtree add`); later pulls are ordinary.

## v2026.10.6 (2026-10-07)

Slide theme (`themes/karthein.typ`), requested by the author:

- **Title slide** shows what built the deck, 9.5 pt muted at the bottom right: "Template
  v2026.10.6 · git 4316cb6" — the version from `VERSION` (read relative to the theme, so
  `lab/VERSION` in a consumer) and the revision from `--input rev=` (`talks generate`, `talks
  html` and `talks course build` pass `git describe --always --dirty`; without it only the
  version is shown).
- **Justified running text**: `set par(justify: true)` for the slide body, with
  `justification-limits` (word spacing 67–130 %, tracking −0.01 to +0.02 em) so narrow columns
  do not open wide gaps; explicitly aligned content (`align(...)`: centred captions, diagram
  labels) and tables are exempt. One-line text is unaffected. A per-paragraph rule "only from
  three lines on" is not possible in Typst 0.15: bullets, composer columns and box text are not
  paragraph elements, so no show rule reaches them; two-line text is justified too. Checked on
  six decks (159 pages): no page count changed, diagrams and tables unchanged.
- `docs/STYLE.md`: justification, the **text budget** (more than 120 body words = text-heavy,
  cut by at least 10 % in the layout pass; counted by `talks layout`), the build line.

## v2026.10.5 (2026-10-05)

- `speak-math.typ`, from the instructor's review of the PHYS 206 alt texts: a function value with
  a digit reads literally, `v_x(0)` "v sub x of 0", `v^2(0)` "v of 0 squared" (no "at time zero" /
  "at point"); subscript cm/CM "center of mass"; long exponents "to the power of …, end exponent";
  a big operator whose subscript has no "=" and no upper limit reads "over" ("the sum over i of",
  "the closed integral over C of").

## v2026.10.4 (2026-10-05)

- `karthein-exam.typ` (from writing the PHYS 206 midterms and finals): `problem(source:)`, a
  "Source and changes" note shown in the key only; the key says "Solutions and grading rubric"
  in the subtitle line (the title never wraps, so the cover keeps its layout); equation-sheet
  lines sized by their bounds (display fractions no longer touch); a part's points line and its
  closing rule stay together on one page.
- `speak-math.typ`: `1\/2 g t^2` reads "one half g t squared" (a slash between small numbers is a
  spoken fraction); ∼ reads "goes like".

## v2026.10.3 (2026-10-05)

- New `themes/karthein-exam.typ`: written exams (cover page with name boxes, equation sheet and
  a graders' table computed from the parts' points; problems in parts with answer space and
  points; `mode=solutions` adds the typed solutions and green rubric marks `pts(n)[note]`).
  Example `examples/exam.typ`.
- `karthein-notes.typ`, the class script (one document per class meeting): `say` (italic in the
  lecture copy, prose in the student copy), `write(min:)`/`draw(min:)` frames, `cue` (lecture
  copy only), `recap(min:)`, `quiz(yaml, only:)` (answers on the next page in the lecture copy;
  `feedback: true` questions print none), `work`/`sketch` with `min:`; `notes(chapter:, week:,
  day:, budget:, plan:)` prints the meeting line, the writing total against the budget and the
  time plan; the git revision from `--input rev=` on the first page; demo panels show their
  explanation in the lecture copy and "What happens" in the student copy; `aside`, `sketch`,
  `demo`, `poll`, `work(title:)` (from the PHYS 206 lectures).
- `speak-math.typ`: many readings for mechanics (work labels "W done by gravity", `W^N`, unit
  vectors, `·`/`×` between vectors as dot/cross incl. brackets and magnitude bars, limits,
  `v^2(0)` "at time zero", `max`/`min` subscripts, ⟂/∥, American unit spellings, …).
- New consumer `cyclotron-talks` (notes theme: host guidelines) in `scripts/propagate.sh` and CLAUDE.md.

## v2026.10.2 (2026-10-03)

- CLAUDE.md and the CI scan: the lab's public contact address may appear; the scan checks home-folder and Drive-mirror prefixes and key patterns.
- LOGBOOK_GUIDE: log books compile from the repository root (`typst compile --root . notes/<name>-logbook.typ`), since the template is reached through a shim into `lab/`.

## v2026.10.1 (2026-10-02)

First version, assembled from the canonical copies in `talks-repo` (themes, STYLE, COURSES),
`fastsims` (lab-notebook template, LOGBOOK_GUIDE, FIGURES_README) and `karthein-cv`
(`cv-theme.typ`):

- `themes/karthein.typ` (Touying slides), `karthein-poster.typ`, `karthein-notes.typ`
  (student / lecture / solutions modes), `cv-theme.typ`, `tokens.typ` (shared palette, panels,
  radii, shadows; all themes import it), `speak-math.typ` (spoken alt text, `apply-alts`).
- Logo paths in the slide theme are root-relative (`/themes/logos/...`): the consumer's logos
  stay where they are when the theme lives in `lab/`.
- `notes/labnotes-template.typ`, `docs/*.md`, `matplotlib/<LabName>-figure-template.ipynb`.
- `examples/` compile under PDF/UA-1 in CI; `scripts/lab-templates.sh` for consumers;
  `scripts/sync_drive.py` for the Drive copies.
