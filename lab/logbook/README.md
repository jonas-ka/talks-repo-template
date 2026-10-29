# logbook: log-book entries as Markdown files

A log book in which every entry is one Markdown file with a YAML header, kept in git, checked
before it is submitted, and rendered as a PDF with the lab notebook template and as a
searchable HTML view. The format is described in
[`../docs/LOGBOOK_FORMAT.md`](../docs/LOGBOOK_FORMAT.md); a worked example is in
[`../examples/logbook/`](../examples/logbook/).

**Standalone by default.** In any repository, put entries in `entries/YYYY/` and run the
checker; nothing else is needed. A *central* log book (several people, one repository) adds
`logbook.yaml` and registries of people, projects and apparatus; then authorship, projects and
apparatus are checked too.

```sh
# from a repository that carries lab-templates in lab/
uv run --project lab/logbook logbook check                       # every entry, the wiki, the references
uv run --project lab/logbook logbook check entries/2026/<id>.md  # one entry
uv run --project lab/logbook logbook check --base origin/main --submitter <github-login> --ci   # a pull request
uv run --project lab/logbook logbook build                       # build/logbook.pdf (pandoc + typst)
uv run --project lab/logbook logbook build --html site --single view.html   # the HTML view, folder and one file
uv run --project lab/logbook logbook open-items                  # issues and todos nothing has resolved
uv run --project lab/logbook logbook schema                      # the header's JSON Schema
```

Writing and sharing (since v2026.10.18; the format reference has a section on each):

```sh
uv run --project lab/logbook logbook new --from draft.md         # an entry from a draft; submitted if connected
uv run --project lab/logbook logbook cite add 10.1103/PhysRevLett.123.456   # a reference by DOI or ISBN
uv run --project lab/logbook logbook export --project FastSims --from 2026-09-01 --out sel.pdf
uv run --project lab/logbook logbook month                       # last month's entries as a PDF
uv run --project lab/logbook logbook digest                      # the weekly summary
uv run --project lab/logbook logbook pull                        # this repository's copy of its projects
uv run --project lab/logbook --extra migrate logbook migrate log.typ --into <book>   # a Typst log book
uv run --project lab/logbook --extra epics logbook epics snapshot source-tune         # EPICS settings
uv run --project lab/logbook logbook init-github                 # issue form and workflows into .github/
```

Exit code 0: fine (warnings and notes allowed); 1: something fails; 3: held (an attachment
waits for the author's export-control confirmation).

Tests: `uv run --project logbook --extra test --extra epics --extra migrate pytest logbook/tests`
(from lab-templates; the EPICS test starts a soft IOC on the loopback interface).
The existing Typst log books (`#day`, `#note`, `#entry`) keep compiling unchanged; this is an
alternative, not a replacement forced on anyone.
