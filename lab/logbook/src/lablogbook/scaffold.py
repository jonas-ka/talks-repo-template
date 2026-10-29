"""`logbook init`: a new central log book, ready for its first entry.

Writes the settings, the registries, a wiki skeleton, starter policy documents, a README and a
Makefile into an empty (or new) folder. Every fact that belongs to the lab or its institution is
asked for on the command line or left as a marked blank (`TODO(...)`), never guessed. Nothing is
committed or pushed; the next steps (`lab/`, GitHub or GitLab) are in `docs/LOGBOOK_SETUP.md`.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path


class InitError(RuntimeError):
    pass


@dataclass
class Lab:
    title: str = "Lab log book"
    lab: str = "TODO(lab name)"
    institution: str = "TODO(institution)"
    pi_name: str = "TODO(PI name)"
    pi_handle: str = "pi"
    pi_login: str | None = None          # the PI's account on GitHub or GitLab
    pi_email: str | None = None
    timezone: str = "UTC"
    email_domains: tuple[str, ...] = ("edu",)
    project: str = "General"
    repository: str | None = None        # owner/name on the forge, once it exists


def _yaml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def files(lab: Lab) -> dict[str, str]:
    """Path -> content of every file of a new book."""
    if not re.fullmatch(r"[a-z][a-z0-9]{0,15}", lab.pi_handle):
        raise InitError("the PI's handle is lower-case letters and digits, starting with a letter (e.g. jk)")
    today = dt.date.today().isoformat()
    person = "{" + ", ".join([f"handle: {lab.pi_handle}", f"name: {_yaml_str(lab.pi_name)}"] +
                             ([f"github: {lab.pi_login}"] if lab.pi_login else []) +
                             ([f"email: {lab.pi_email}"] if lab.pi_email else []) + ["role: admin"]) + "}"
    site = f"site: {{repository: {lab.repository}}}" if lab.repository else \
        "# site: {repository: owner/name}   # the book on GitHub: buttons for a new entry, a correction, an export"
    out: dict[str, str] = {}
    out["logbook.yaml"] = f"""# {lab.title}: the central log book of {lab.lab} ({lab.institution}).
# Every key: lab/docs/LOGBOOK_FORMAT.md. Changed by the PI only.
title: {_yaml_str(lab.title)}
author: {_yaml_str(lab.lab)}
affiliation: {_yaml_str(lab.institution)}
timezone: {lab.timezone}              # IANA name; the workflows run on UTC machines
# logo: assets/logo.png                # shown at the top of the view's sidebar (PNG or SVG)
{site}
late_days: 2                           # entries written later than this after the work carry `backfilled`
coauthor_days: 14                      # people on the same project this recently are proposed as co-authors
forbid_drive_ids: false                # true: Google Drive links in entries fail the check
privacy:
  email_domains: [{", ".join(lab.email_domains)}]   # addresses of non-members here are flagged ("edu": every .edu)
  # id_pattern: '(?<!\\d)\\d{{9}}(?!\\d)'   # the shape of student or staff ID numbers; null turns the rule off
"""
    out["people.yaml"] = f"""# Who writes in this log book. Changed by the PI only.
#   handle: lower case, used in file names and `authors`
#   github: the account that submits (on GitLab: the username); the first author must be the submitter
#   role: admin may submit on behalf of others and change everything outside entries/ and wiki/
#   access: central (default) or project (reads only a project repository's copy, `logbook/`)
- {person}
"""
    out["projects.yaml"] = f"""# Projects. Subprojects are added as they come up. Changed by the PI only.
#   repository: where the project's code lives (`logbook pull` there writes its copy of the entries)
#   copy_internal_until: YYYY-MM-DD lets an internal (organisation-visible) repository hold a copy until then
- name: {_yaml_str(lab.project)}
  subprojects: []
  wiki: projects/{re.sub(r"[^a-z0-9]+", "-", lab.project.lower()).strip("-") or "general"}
- name: Lab
  subprojects: [Log book, Safety, Procedures]
  wiki: howto/log-book
"""
    out["apparatus.yaml"] = """# The lab's apparatus: an entry names what it was done on (`apparatus: [source]`).
# epics_groups: named PV lists for `logbook new --epics <group>` and `logbook epics restore`.
# Changed by the PI only. Example:
# - id: source
#   name: Ion source
#   wiki: apparatus/source
#   epics_groups:
#     source-tune: [SRC:HV, SRC:Extract]
[]
"""
    slug = re.sub(r"[^a-z0-9]+", "-", lab.project.lower()).strip("-") or "general"
    out[f"wiki/projects/{slug}.md"] = f"""# {lab.project}

What the project is for, its goals, who works on it, and where things live (code, data, Drive
folders with restricted sharing). A new member reads this page first. TODO(write it)
"""
    out["wiki/howto/log-book.md"] = f"""# The log book: how to write in it

The log book records what happened, when and why: decisions, findings with their numbers,
problems and their fixes, open items. The wiki (these pages) says how things *are*; the log
book says what *happened*.

## Writing an entry

- **From the web** (GitHub): the repository's Issues, "New entry". Fill in the form and drag
  figures and files in; a workflow turns it into an entry and adds it when the checks pass.
- **From the terminal**, in a clone of this repository or of a project repository connected to
  it: `uv run --project lab/logbook logbook new --from draft.md`, where the draft is Markdown with
  a short YAML header (title, project, kind). `logbook new --help` lists the options.
- **With an AI assistant**, if the lab's policy allows it (`docs/COMPLIANCE.md`): it uses the same
  command and the same checks.

Every entry names its project and, for work on the machine, the apparatus. You are the first
author; the tool proposes the people who worked on the same project recently as co-authors.

## The rules

- **Entries are never changed.** A mistake is corrected by a new entry of kind `correction`
  that says what was wrong. Wiki pages can be edited any time.
- **Nothing private about a person**, and nothing the lab's policy keeps out
  (`docs/COMPLIANCE.md`).
- **No manuals or vendor documents.** Link to them where they live, with restricted sharing.
  Any PDF you attach is held until you confirm it is not one of them.
- Big raw data stays where it is; the entry stores the processed data its figures show and
  says where the raw data is.

The format: `lab/docs/LOGBOOK_FORMAT.md`.
"""
    out["wiki/procedures/index.md"] = """# Procedures

How the lab does recurring work, step by step: one page per procedure here, edited like every
wiki page. An entry says when a procedure was followed and what came of it. TODO(list them)
"""
    out["wiki/safety/index.md"] = """# Safety

The lab's safety rules and where the official ones live. Incidents are log-book entries of kind
`incident`, named after the apparatus; they never contain health information about anyone.
TODO(write it)
"""
    out["wiki/references.bib"] = "% The reference list. Add a reference with: logbook cite add <DOI or ISBN>\n"
    out["docs/COMPLIANCE.md"] = f"""# Compliance: what goes into the log book and what never does

For everyone who writes here, people and AI assistants alike. Read it once before your first
entry. **This is a starting point written by `logbook init` on {today}: every `TODO(...)` is a
fact only {lab.lab} and {lab.institution} can supply; settle them with the PI and, where it
says so, with the institution's IT, privacy and export-control offices before the first entry.**
Data steward: {lab.pi_name}.

## Classification

- The log book's data class under the institution's policy: TODO(e.g. "internal").
- Where it is hosted and what that host is cleared for: TODO(the platform, who besides the lab
  can read it, e.g. the organisation's administrators; which data classes it may hold).
- Nothing from here is published. An export for someone outside the lab goes through the PI
  (Export, below).

## What belongs in an entry

What you did, what you found (with the numbers), what you decided and why, what went wrong
and how it was fixed, what is still open. Names of lab members on their own work. Plots, the
processed data they show, settings, run ids, links to code and to where raw data and manuals
live.

## What never goes in

| never | because | instead |
|---|---|---|
| Records about an identifiable student as a student (grades, scores, enrolment) | TODO(the education-records law that applies, e.g. FERPA) | teaching notes about the course, not about students |
| ID numbers, social security numbers, dates of birth, home addresses, personal phone numbers | sensitive personal information | nothing; the name is enough |
| Health information about anyone, including injuries in an incident | TODO(health-privacy law and the host's clearance) | "incident reported to <safety office> on <date>" |
| Export-controlled technical data, controlled unclassified information and anything the institution marks for limited distribution | TODO(export control and the institution's markings, e.g. EAR, ITAR, CUI) | a link to the document where it lives, with its sharing restricted |
| Proprietary vendor information, unreleased code held back for licensing | contracts and licensing | a one-line pointer to where it is kept |
| Passwords, tokens, keys, account details of shared machines | security | "credentials in the usual place" |
| Absolute paths of anyone's home folder | they leak account details | relative paths |
| Raw data | size; it has its own home | `data[].source` pointing at where it lives |

## What the checker does

`logbook check` runs in `logbook new`, in the web form's workflow and on every pull request; a
pull request cannot merge while it fails. It finds patterns, not meaning: secrets and home
paths fail; ID-shaped numbers (`privacy.id_pattern` in `logbook.yaml`), words about grades or
health, and institutional addresses of non-members (`privacy.email_domains`) fail until the
author adds `reviewed: ferpa` or `reviewed: health` after reading; PDF attachments and figures
that are not plots are held until the author confirms them (`export_control_confirmed: true`).

## If something got in that should not have

Do not repair it yourself and do not repeat it anywhere. Tell the PI the **entry id** and the
kind of problem; the PI follows `docs/REDACTION.md`. A password or key is also changed at once:
a secret in git history counts as public.

## AI assistants

Whatever an AI assistant reads leaves the lab's machines and goes to its provider.
TODO(which AI tools the institution allows with this data, under which agreement; whether lab
data may be used to train models; who confirmed it and when). The same rules apply to what you
give an assistant as to what goes into an entry.

## Export

Anyone may request an export of a selection; only the PI approves, and every request is logged.
The PDF is for the person named in the request.

## Retention

Nothing is ever deleted (except under `docs/REDACTION.md`). TODO(how long records are kept, by
which rule: the funding agency, the data management plan, the institution).

## People who leave, and outside collaborators

Access is removed on the last day; entries and the names on them stay. Outside collaborators
either get access to the whole book or read their project's copy; the PI decides per person
(`people.yaml`, `access:`) after TODO(the export-control check for foreign nationals, if any).
"""
    out["docs/REDACTION.md"] = f"""# Redaction: the only way anything leaves the log book

For the PI ({lab.pi_name}), the only person who can do it (the only one allowed to bypass the
protection of `main`). Everyone else reports the entry id to the PI and nothing more
(`docs/COMPLIANCE.md`).

## Pick the level

| level | when | what happens | history |
|---|---|---|---|
| **1. Correction** | wrong, but allowed to be stored | a new entry with `kind: correction` and `corrects: <id>`, written by anyone | untouched; the old entry shows "corrected by" |
| **2. Removal** | allowed to exist in history but should no longer be shown; a secret that has already been changed | the PI removes the passage (or the file) from `main` and adds a `kind: redaction` entry | the content stays in git history |
| **3. Purge** | must not be stored anywhere: student records, health information, controlled data, a secret that cannot be changed | level 2 plus a rewrite of history and a hunt through every copy | rewritten; everyone re-clones |

When in doubt between 2 and 3, it is 3.

## The redaction entry (levels 2 and 3)

Written by the PI, in the same commit as the removal:

```markdown
---
date: <today>
authors: [{lab.pi_handle}]
kind: redaction
project: <the redacted entry's project>
title: Redaction of <entry id>
redacts: <entry id>
level: 2                 # or 3
---

What was removed: <the kind of content, never the content>.
Why: <the rule it broke>.
What remains: <"the rest of the entry, unchanged" | "nothing; the entry is removed">.
```

The passage is replaced in the redacted entry by `[redacted <date>, see <redaction entry id>]`,
or the whole file is removed. The check on `main` accepts a changed or deleted entry only in a
commit that adds a redaction entry naming it.

## Level 3, step by step

Do level 2 first, then: rewrite history in a fresh mirror clone (`git filter-repo`), check it
with `git log -p -S '<a fragment>'` over all refs, force-push all branches and tags; ask the
host's support to remove cached views and pull- or merge-request refs; and hunt the copies:
the request's diff and comments, the web form's issue, CI logs and artifacts, snapshot
releases, exported or monthly PDFs, per-project copies (`logbook/` in project repositories),
everyone's clones, and AI-assistant transcripts on the machines that read it. Record in the
redaction entry that level 3 was completed and when.

## What is never done

No redaction to change what a result was (that is a correction); no silent removal; no
redaction by anyone but the PI.
"""
    out["README.md"] = f"""# {lab.title}

The log book of {lab.lab} ({lab.institution}): one Markdown file per entry, never changed once
merged, checked before it goes in, rendered as a PDF and as a searchable view for lab members.

- **How to write an entry:** `wiki/howto/log-book.md`.
- **What may go in:** `docs/COMPLIANCE.md`. **How anything leaves:** `docs/REDACTION.md`.
- **Format and tools:** `lab/docs/LOGBOOK_FORMAT.md`; set-up: `lab/docs/LOGBOOK_SETUP.md`.

```sh
make check   # every entry, the wiki and the references
make build   # build/logbook.pdf and the view (build/site/, build/logbook.html)
```
"""
    out["Makefile"] = """# Everyday commands. The tools live in lab/ (lab-templates, pinned to a tag).
L = uv run --project lab/logbook logbook

check:          ## every entry, the wiki and the references
\t$(L) check

build:          ## build/logbook.pdf, the view in build/site/ and as one file build/logbook.html
\t$(L) build --pdf build/logbook.pdf --html build/site --single build/logbook.html

templates:      ## which lab-templates version lab/ holds, and whether a newer one is out
\tlab/scripts/lab-templates.sh status
\tlab/scripts/lab-templates.sh check

.PHONY: check build templates
"""
    out[".gitignore"] = "build/\n.DS_Store\n.env\ncredentials.json\ntoken.json\n"
    out[f"entries/{today[:4]}/.gitkeep"] = ""
    return out


def init(target: Path, lab: Lab, force: bool = False) -> list[Path]:
    """Write a new book into `target`; refuses to overwrite any file unless `force`."""
    content = files(lab)
    target.mkdir(parents=True, exist_ok=True)
    clash = [p for p in content if (target / p).exists()]
    if clash and not force:
        raise InitError("these files exist already (pass --force to overwrite): " + ", ".join(sorted(clash)))
    written = []
    for rel, text in content.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        written.append(p)
    return written
