# Setting up a central log book from scratch

A central log book is one git repository for a lab's log-book entries: one Markdown file per
entry, never changed once merged, checked before it goes in, and rendered as a PDF and as a
searchable view. The tools are in this repository (`logbook/`); the format is
[`LOGBOOK_FORMAT.md`](LOGBOOK_FORMAT.md). This page takes a new lab from nothing to its first
entry. It assumes nothing about the lab, its institution or its hosting.

## What you need

git; [uv](https://docs.astral.sh/uv/); [pandoc](https://pandoc.org) 3.x and
[Typst](https://typst.app) 0.15 (the PDF and the view); for GitHub, the `gh` command line,
signed in as the repository's admin.

## Decide first

These are the lab's decisions, not the tools'. Settle them before the first entry: the record
is append-only, so anything that should not have gone in stays in history until it is purged.

1. **Where it lives, and who can read it.** The repository is private. Find out who else can
   read private repositories on that host (on an institutional GitHub organisation or GitLab
   server, usually its administrators) and which classes of data the host is cleared for.
2. **The private view.** The searchable view is a static web site. On GitHub it is published
   with Pages, which can be private only on **GitHub Enterprise Cloud**; on GitLab, Pages can be
   limited to project members if the server's administrators turned on Pages access control.
   Without either, do not publish the view: everyone builds and opens it locally
   (`make build`, then `build/logbook.html`).
3. **What may go in.** `logbook init` writes `docs/COMPLIANCE.md` and `docs/REDACTION.md` as
   starting points with every institution-specific fact left as `TODO(...)`: the data class,
   the laws on student records and health data that apply, export control and the
   institution's markings for limited-distribution information, retention. Fill them in with the
   institution's privacy, IT and export-control offices.
4. **AI assistants.** Entries can be written with an AI assistant, and an assistant can read the
   book; whatever it reads goes to its provider. Find out which tools the institution allows
   with this data, under which agreement, and write it into `docs/COMPLIANCE.md`.
5. **The checker's local rules.** In `logbook.yaml`, `privacy.email_domains` names the
   institution's e-mail domains (addresses of non-members there are flagged; the default flags
   every `.edu` address) and `privacy.id_pattern` the shape of its student or staff ID numbers
   (default: nine digits standing alone).

## Create the book

```sh
mkdir lab-notes && cd lab-notes && git init -b main
git commit --allow-empty -m "A new log book"
# the tools and templates, as a git subtree in lab/, pinned to a tag (the newest: CHANGELOG.md)
git remote add lab-templates https://github.com/jonas-ka/lab-templates.git
git fetch lab-templates tag v2026.10.39
git subtree add --prefix lab lab-templates v2026.10.39 --squash -m "lab-templates v2026.10.39 in lab/"
# settings, registries, wiki skeleton, policy starters, README, Makefile
uv run --project lab/logbook logbook init . --title "Example Lab Notes" --lab "Example Lab" \
    --institution "Example University" --pi-name "A. Author" --pi-handle aa --pi-login a-author \
    --timezone America/Chicago --email-domain example.edu --project "Beamline"
make check && make build
```

Then: fill in every `TODO(...)` (`grep -rn TODO .` outside `lab/`), add the lab's people to
`people.yaml`, its projects and apparatus to `projects.yaml` and `apparatus.yaml`, put the
lab's logo in `assets/` and name it in `logbook.yaml`, and commit. `lab/` is never edited here:
`lab/scripts/lab-templates.sh check` reports a newer tag, `pull <tag>` updates it.

## On GitHub

1. Create the repository, private, in the organisation (`gh repo create org/Lab-Notes --private`),
   push `main`, and set `site: {repository: org/Lab-Notes}` in `logbook.yaml`.
2. `uv run --project lab/logbook logbook init-github` writes the "New entry" form, the six
   workflows and `CODEOWNERS` into `.github/` (see LOGBOOK_FORMAT.md, "On GitHub"). Commit and
   push. Run it again after a registry change (the form's menus come from them) and after a
   lab-templates update (`--force` replaces changed workflow files).
3. `uv run --project lab/logbook logbook github-settings --repo org/Lab-Notes --admin <PI login> --team <team> > github-settings.sh`,
   read it, then run it as the repository's admin. It sets squash-only merges with the pull
   request's description as the commit message, auto-merge, Actions allowed to open pull
   requests, the label `new-entry`, the environments `export` and `attest` with the PI as
   reviewer, the ruleset on `main` (pull requests only; the check `entry-checks`, required to
   come from GitHub Actions; no force pushes or deletions; linear history; code-owner review),
   and private Pages. Where Pages cannot be private, it turns Pages off and stops.
4. Check it: a pull request that changes an existing entry fails `entry-checks` and cannot
   merge; a wiki edit merges by itself; an entry submitted through the form becomes a pull
   request that merges itself; the site asks for a GitHub sign-in. Checks that need a second
   account: a direct push to `main` by a non-admin is refused; a non-admin's change outside
   `entries/` and `wiki/` waits for the code owner.

Two GitHub facts behind these settings: a ruleset's bypass list takes roles, teams and apps,
not single people, so the bypass is the repository's admin role (the PI, and the organisation's
owners, who are admins anyway); and a pull request opened by a workflow starts no other
workflow, which is why the form's workflow runs the checker itself.

## On GitLab

The format, the checker, the PDF and the view, `logbook new --dry-run`, `migrate`, `cite` and
the EPICS tools work unchanged. What is GitHub-specific: the issue form and its workflow,
`init-github`, `github-settings`, and the submission step of `logbook new` in a connected
repository (it opens a pull request with `gh`). Until lab-templates has a GitLab layer, a
starting point **not yet tested** on a GitLab server:

```yaml
# .gitlab-ci.yml (sketch): the check on every merge request, the view on main
entry-checks:
  image: ghcr.io/astral-sh/uv:python3.12-bookworm
  rules: [{if: '$CI_PIPELINE_SOURCE == "merge_request_event"'}]
  script:
    - git fetch origin "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"
    - uv run --project lab/logbook logbook check --base "origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME" --submitter "$GITLAB_USER_LOGIN" --ci
pages:
  image: ghcr.io/astral-sh/uv:python3.12-bookworm
  rules: [{if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'}]
  script:
    - apt-get update -qq && apt-get install -y -qq pandoc   # pandoc 3.x: check the version
    - uv run --project lab/logbook logbook build --html public
  artifacts: {paths: [public]}
```

with `main` protected (no direct pushes, no force pushes), merge requests that merge only when
the pipeline succeeds, squash merges, Pages limited to project members, and `github:` in
`people.yaml` holding each person's GitLab user name. Entries are written with `logbook new`
in a clone and submitted as a merge request.

## Troubleshooting

- **`ModuleNotFoundError: lablogbook` on a Mac, with Python 3.14, in a repository inside an
  iCloud-synced folder** (`~/Documents`, `~/Desktop`): iCloud marks the `.pth` files of the
  `.venv` as hidden, and Python 3.14 skips hidden `.pth` files, so the tools, installed in
  editable mode, cannot be imported. Best: keep repositories out of iCloud-synced folders (git
  and iCloud also disagree about `.git`). Otherwise install the tools normally:
  `export UV_NO_EDITABLE=1` in the shell's profile (or `uv run --no-editable …`).
- **An entry from the form merged, but the site does not show it:** a merge done by a
  workflow's own token starts no other workflow; since v2026.10.28 the form's workflow starts
  the site's build itself after the merge, and the site also rebuilds once a day. Run
  `logbook init-github --force` in a book set up before that.

## Later

- **Project repositories write into the book**: `central:` in their own `logbook.yaml`
  (LOGBOOK_FORMAT.md, "Writing from a project repository"); `logbook pull` gives them a copy.
- **Existing Typst log books** come in with `logbook migrate <log.typ> --into <book>`, one pull
  request per log book. Entries written in the old book after that come over with
  `--new-only`. Then freeze the old book: a last `#day` titled "This log book has moved" (never
  migrated), and the project repository's `logbook.yaml` and instructions pointing at the book.
- **The monthly PDFs in a synced folder** (Google Drive, OneDrive, …): `logbook deliver --to
  <folder>` copies each attested month from the snapshot releases that is not there yet;
  `logbook deliver --to <folder> --launch-agent org.example.logbook` prints a macOS LaunchAgent
  that runs it daily (read it, save it in `~/Library/LaunchAgents/`, `launchctl bootstrap`).
- **Updating `lab/` with a squash merge**: git-subtree finds the last update from its commit
  message, which a squash merge replaces by the pull request's description. Put the two lines
  of the update commit (`git-subtree-dir: lab`, `git-subtree-split: <sha>`) in the description,
  or the next `pull` conflicts.
- **Stacked pull requests**: deleting a base branch closes the pull requests that target it.
  Merge the base without deleting its branch, retarget the others to `main`, then delete it.
- **A custom domain for the view** (e.g. `notes.lab.example.org`): set it in the Pages
  settings first, then a CNAME to `<organisation>.github.io` at the DNS provider, not proxied
  (on Cloudflare: "DNS only"), or GitHub cannot issue the certificate. If no certificate arrives
  within the hour, remove the domain in the Pages settings and add it again. A browser that saw
  the address while it was proxied may insist on HTTPS until the certificate is there.
