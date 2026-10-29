"""A central log book on GitHub: the "New entry" issue form, entries made from submitted forms,
and the workflow files (`logbook init-github` writes them into `.github/`).

The form is generated from the registries (projects, people, apparatus, kinds), so its menus
match the book; run `logbook init-github` again after a registry changes.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from importlib import resources
from pathlib import Path

import yaml

from .book import Book
from .entry import DEFAULT_PRIORITY

NO_RESPONSE = "_No response_"
FORM_LABELS = {  # issue-form label -> field
    "Title": "title", "Kind": "kind", "Project": "project", "Subproject": "subproject", "Co-authors": "coauthors",
    "Apparatus": "apparatus", "Tags": "tags", "Date of the work": "date", "Corrects": "corrects",
    "Resolves": "resolves", "Entry": "body", "Open items": "todos", "Figures and files": "files", "Figures, data and attachments": "files",
    "Export control": "export_control",
    "Order": "order", "Items": "items",   # not in the form: sections a script writes for an order
}
# labels of earlier versions of the form, still read from issues filed with them
LEGACY_LABELS = {"Title", "Figures, data and attachments"}
# sections a script writes (an order), not fields of the form
SCRIPT_LABELS = {"Order", "Items"}


class IssueError(RuntimeError):
    pass


_PRIORITY_PREFIX = re.compile(r"^(asap|high|medium|low)\s*[:\-–]\s*", re.I)   # "ASAP: …" in the form


def issue_form(book: Book) -> dict:
    people = [f"{p.name} ({h})" for h, p in sorted((book.people or {}).items(), key=lambda x: x[1].name)]
    projects = list(book.projects or {}) or ["(add projects to projects.yaml)"]
    apparatus = [f"{v.get('name', k)} ({k})" for k, v in (book.apparatus or {}).items()]
    body = [
        {"type": "markdown", "attributes": {"value": (
            "The title box above is the entry's title. One piece of work per entry: what you did, what you found "
            "(with the numbers), what you decided, what is open. Never grades, student records, health information "
            "or manuals: link those where they live.")}},
        {"type": "dropdown", "id": "project", "attributes": {"label": "Project", "options": projects}, "validations": {"required": True}},
        {"type": "dropdown", "id": "kind", "attributes": {"label": "Kind", "default": 0,
         "options": [k for k, v in book.kinds.items() if (v or {}).get("form", True)]}},
        {"type": "textarea", "id": "body", "attributes": {"label": "Entry", "description": (
            "Markdown. Blocks: a line `::: finding`, the text, a line `:::` (also decision, issue, todo); "
            "`::: todo {#todo-1}` makes an open item. Link entries as [[entry-id]].")},
         "validations": {"required": True}},
        {"type": "textarea", "id": "todos", "attributes": {"label": "Open items", "description": (
            "One per line. Each becomes an open item that a later entry can resolve. Start a line with "
            "`ASAP:`, `High:` or `Low:` to give it that priority (otherwise medium).")}},
        {"type": "textarea", "id": "files", "attributes": {"label": "Figures and files", "description": (
            "Drag files here, one paragraph each, with `Caption: …` and `Alt: …` under a figure "
            "(a plot: its PDF and SVG) and `Source: …` under a data file.")}},
        {"type": "checkboxes", "id": "export_control", "attributes": {"label": "Export control", "options": [
            {"label": "No file I attached holds export-controlled technical data (manuals, vendor documents, controlled drawings)."}]}},
        {"type": "markdown", "attributes": {"value": "#### Optional"}},
        {"type": "input", "id": "subproject", "attributes": {"label": "Subproject"}},
    ]
    if apparatus:
        body.append({"type": "dropdown", "id": "apparatus", "attributes": {"label": "Apparatus", "multiple": True, "options": apparatus}})
    if people:
        body.append({"type": "dropdown", "id": "coauthors", "attributes": {
            "label": "Co-authors", "description": "Others who took part; you are the first author.", "multiple": True, "options": people}})
    body += [
        {"type": "input", "id": "tags", "attributes": {"label": "Tags", "description": "Comma separated."}},
        {"type": "input", "id": "date", "attributes": {"label": "Date of the work", "description": "YYYY-MM-DD, if not today."}},
        {"type": "input", "id": "corrects", "attributes": {"label": "Corrects", "description": "The id of the entry this one corrects."}},
        {"type": "input", "id": "resolves", "attributes": {"label": "Resolves", "description": "Open items this entry settles: <entry-id>#<item-id>, comma separated."}},
    ]
    return {"name": "New log-book entry", "description": "Write an entry for the log book.",
            "labels": ["new-entry"], "body": body}


def parse_issue_body(text: str) -> dict:
    """The answers of a submitted issue form: {field: text}."""
    out, cur, buf = {}, None, []
    for line in (text or "").splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m and m.group(1) in FORM_LABELS:
            if cur:
                out[cur] = "\n".join(buf).strip()
            cur, buf = FORM_LABELS[m.group(1)], []
        elif cur:
            buf.append(line)
    if cur:
        out[cur] = "\n".join(buf).strip()
    return {k: ("" if v == NO_RESPONSE else v) for k, v in out.items()}


_LINK = re.compile(r"!?\[([^\]]*)\]\((https://[^)\s]+)\)|(https://github\.com/user-attachments/\S+)")


FILE_LABELS = {"caption": "caption", "alt": "alt", "alt text": "alt", "source": "source"}


def file_notes(text: str) -> tuple[dict, list[str]]:
    """The files field's caption/alt/source written without a file of their own (they belong to an
    image in the text), and the labels it did not understand ("Atl: …")."""
    loose, unknown = {}, []
    for para in re.split(r"\n\s*\n", text or ""):
        if _LINK.search(para):
            continue
        for m in re.finditer(r"^\s*([A-Za-z][A-Za-z ]{0,20}?)\s*:\s*(.+)$", para, re.M):
            key = FILE_LABELS.get(m.group(1).strip().lower())
            if key:
                loose.setdefault(key, m.group(2).strip())
            else:
                unknown.append(m.group(1).strip())
    return loose, unknown


def parse_files(text: str) -> list[dict]:
    """Paragraphs of the files field: [{url, name, caption, alt, source}]."""
    items = []
    for para in re.split(r"\n\s*\n", text or ""):
        def field(k):
            mm = re.search(rf"^\s*{'(?:alt|alt text)' if k == 'alt' else k}\s*:\s*(.+)$", para, re.M | re.I)
            return mm.group(1).strip() if mm else None
        m = _LINK.search(para)
        if not m:   # "Caption: …" in a paragraph of its own belongs to the file above it
            if items:
                for k in ("caption", "alt", "source"):
                    items[-1][k] = items[-1][k] or field(k)
            continue
        url = m.group(2) or m.group(3)
        name = (m.group(1) or "").strip() or url.rsplit("/", 1)[-1]
        items.append({"url": url, "name": name, "caption": field("caption"), "alt": field("alt"), "source": field("source")})
    return items


MEDIA_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/svg+xml": ".svg",
             "image/webp": ".webp", "application/pdf": ".pdf", "text/csv": ".csv"}


def download(url: str, dest: Path, token: str | None) -> Path:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
            kind = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    except urllib.error.HTTPError as e:
        raise IssueError(f"could not download {url.split('?')[0]} (HTTP {e.code})") from None
    if kind == "text/html":   # a sign-in page, not the file
        raise IssueError(f"could not download {url.split('?')[0]} (GitHub sent a web page instead)")
    if not dest.suffix and kind in MEDIA_EXT:   # attachment links carry no file name
        dest = dest.with_suffix(MEDIA_EXT[kind])
    dest.write_bytes(data)
    return dest


_ASSET_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def signed_images(repo: str, number: int) -> dict[str, str]:
    """{asset id: signed link} for the images of an issue. In a private repository an image's
    github.com/user-attachments link is not served to a token; the issue's rendered HTML has a
    short-lived signed link to each image (private-user-images.githubusercontent.com)."""
    try:
        html = _gh("api", f"repos/{repo}/issues/{number}", "-H", "Accept: application/vnd.github.full+json",
                   "-q", ".body_html", check=False)
    except Exception:   # noqa: BLE001 - without the HTML, images are fetched as before
        return {}
    out = {}
    for src in re.findall(r'<img[^>]*\bsrc="(https://private-user-images\.githubusercontent\.com/[^"]+)"', html or ""):
        m = _ASSET_ID.search(src)
        if m:
            out.setdefault(m.group(0), src.replace("&amp;", "&"))
    return out


def fetch_with_signed(signed: dict[str, str]):
    """A `fetch` for draft_from_issue: an image through its signed link (no token needed), anything
    else as before; photos then lose their metadata and, when large, are scaled down."""
    from . import photos

    def fetch(url: str, dest: Path, token: str | None) -> Path:
        m = _ASSET_ID.search(url)
        path = download(signed[m.group(0)], dest, None) if m and m.group(0) in signed else download(url, dest, token)
        return photos.prepare(path)[0]
    return fetch


_BODY_IMAGE = re.compile(r'<img\b[^>]*?\bsrc="(https://github\.com/user-attachments/[^"]+)"[^>]*>|'
                         r"!\[([^\]]*)\]\((https://github\.com/user-attachments/[^)\s]+)\)")


def body_images(body: str, loose: dict) -> tuple[str, list[dict]]:
    """Images dragged into the entry's text: taken out of the text and returned as files, named
    after their caption; the files field's loose caption, alt and source go with the first one."""
    items = []
    def take(m):
        url = m.group(1) or m.group(3)
        alt = re.search(r'\balt="([^"]*)"', m.group(0)) if m.group(1) else None
        n = len(items) + 1
        meta = loose if n == 1 else {}
        cap = meta.get("caption")
        stem = re.sub(r"[^a-z0-9]+", "-", (cap or f"figure {n}").lower()).strip("-")[:40] or f"figure-{n}"
        items.append({"url": url, "name": f"fig-{stem}", "caption": cap,
                      "alt": meta.get("alt") or (alt.group(1) if alt and alt.group(1) not in ("", "Image") else None)
                      or (m.group(2) or None), "source": meta.get("source")})
        return ""
    return _BODY_IMAGE.sub(take, body), items


def draft_from_issue(book: Book, answers: dict, files: list[dict], workdir: Path, token: str | None,
                     fetch=download) -> tuple[dict, str]:
    """(header, body) of a draft for `logbook new`, files downloaded into `workdir`."""
    h: dict = {"title": answers.get("title", "").strip(), "kind": answers.get("kind") or "note",
               "project": answers.get("project", "").strip()}
    for k in ("subproject", "date", "time", "corrects"):
        if answers.get(k):
            h[k] = answers[k].strip()
    if answers.get("tags"):
        h["tags"] = [t.strip() for t in answers["tags"].split(",") if t.strip()]
    if answers.get("resolves"):
        h["resolves"] = [t.strip() for t in answers["resolves"].split(",") if t.strip()]
    if answers.get("coauthors"):
        h["authors"] = re.findall(r"\((\w+)\)", answers["coauthors"])
    if answers.get("apparatus"):
        h["apparatus"] = re.findall(r"\(([\w-]+)\)", answers["apparatus"])
    body = answers.get("body", "")
    if answers.get("items"):   # an order: its items, as JSON, become the header's items and the table
        from . import orders
        items = orders.parse_items(answers["items"])
        h["kind"] = orders.KIND
        h["order"] = (answers.get("order") or "").strip() or h["title"]
        h["items"] = items
        body = orders.body(items, body, (book.config.get("orders") or {}).get("currency", "$"))
    loose, _unknown = file_notes(answers.get("files", ""))
    body, from_text = body_images(body, loose if not files else {})
    files = list(files) + from_text
    todos = [x.strip(" -*\t") for x in (answers.get("todos") or "").splitlines() if x.strip(" -*\t")]
    taken = set(re.findall(r"#(todo-\d+)", body))
    k = 1
    for item in todos:
        while f"todo-{k}" in taken:
            k += 1
        taken.add(f"todo-{k}")
        m = _PRIORITY_PREFIX.match(item)
        level, item = (m.group(1).lower(), item[m.end():].strip()) if m else (None, item)
        attrs = f"#todo-{k}" + (f" priority={level}" if level and level != DEFAULT_PRIORITY else "")
        body = body.rstrip() + f"\n\n::: todo {{{attrs}}}\n- {item}\n:::\n"
    confirmed = "[x]" in answers.get("export_control", "").lower()
    by_stem: dict[str, list[dict]] = {}
    for f in files:
        local = fetch(f["url"], workdir / re.sub(r"[^\w.-]", "_", f["name"]), token) or workdir / f["name"]
        f["local"] = local
        by_stem.setdefault(local.stem, []).append(f)
    for stem, group in by_stem.items():
        exts = {g["local"].suffix.lower(): g for g in group}
        meta = next((g for g in group if g.get("caption") or g.get("alt")), group[0])
        if exts.keys() & {".pdf", ".svg", ".png", ".jpg", ".jpeg"} and not (len(exts) == 1 and ".pdf" in exts and not meta.get("caption")):
            main = exts.get(".pdf") or exts.get(".svg") or exts.get(".png") or exts.get(".jpg") or exts.get(".jpeg")
            kind = "plot" if (".svg" in exts or ".pdf" in exts) else "photo"
            item = {"file": str(main["local"]), "caption": meta.get("caption") or stem, "alt": meta.get("alt") or ""}
            if kind != "plot":
                item["kind"] = kind
                if confirmed:
                    item["export_control_confirmed"] = True
            h.setdefault("figures", []).append(item)
        else:
            for ext, g in exts.items():
                if ext in (".csv", ".json", ".txt", ".npz", ".tsv"):
                    h.setdefault("data", []).append({"file": str(g["local"]), "source": g.get("source") or "see the entry"})
                else:
                    a = {"file": str(g["local"])}
                    if confirmed:
                        a["export_control_confirmed"] = True
                    h.setdefault("attachments", []).append(a)
    return h, body


# ------------------------------------------------------------------------------ init-github --
def templates() -> dict[str, str]:
    root = resources.files("lablogbook").joinpath("data/github")
    out = {}
    for sub in ("workflows",):
        for f in root.joinpath(sub).iterdir():
            if f.name.endswith(".yml"):
                out[f".github/{sub}/{f.name}"] = f.read_text(encoding="utf-8")
    return out


def init_github(book: Book, force: bool = False) -> list[str]:
    """Write the issue form and the workflows into the book's repository; returns what was written."""
    written = []
    files = templates()
    form = yaml.safe_dump(issue_form(book), sort_keys=False, allow_unicode=True, width=10_000)
    files[".github/ISSUE_TEMPLATE/new-entry.yml"] = "# Generated by `logbook init-github` from the registries; run it again after they change.\n" + form
    files[".github/ISSUE_TEMPLATE/config.yml"] = "blank_issues_enabled: true\n"
    files[".github/CODEOWNERS"] = codeowners(book)
    for rel, text in files.items():
        p = book.root / rel
        if p.exists() and rel.endswith("CODEOWNERS"):
            continue   # a book's own CODEOWNERS is never replaced, not even with --force
        if p.exists() and not force and not rel.endswith("new-entry.yml"):
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        written.append(rel)
    return written


# ------------------------------------------------------------------------------ from-issue ----
def _gh(*args: str, check: bool = True) -> str:
    from . import connect
    return connect.run(["gh", *args], check=check)


def rebuild_site_after_merge(url: str, repo: str, out, tries: int | None = None, pause: float = 10) -> bool:
    """A merge by the workflow's own token starts no other workflow, so the site would not rebuild
    for an entry from the form: wait for the merge, then start the site's workflow (a
    workflow_dispatch is the one event such a token may start). True when it was started."""
    import time
    for _ in range(tries if tries is not None else int(os.environ.get("LOGBOOK_MERGE_WAIT", "36"))):
        state = _gh("pr", "view", url, "--repo", repo, "--json", "state", "-q", ".state", check=False).strip()
        if state == "MERGED":
            _gh("workflow", "run", "logbook-site.yml", "--repo", repo, "--ref", "main", check=False)
            print("merged; site build started", file=out)
            return True
        if state == "CLOSED":
            return False
        time.sleep(pause)
    return False


def from_issue(book: Book, number: int, submitter: str, repo: str, out) -> int:
    """Run inside a checkout of the central log book (the entry-from-issue workflow)."""
    from . import check, connect, newentry
    from .book import open_book

    issue = json.loads(_gh("issue", "view", str(number), "--repo", repo, "--json", "body,title,state,createdAt"))
    branch = f"entry/issue-{number}"
    # One issue, one entry: an issue that is closed, or whose entry has merged, is done. (Opening an
    # issue with its label fires two events; an edit after the merge must not make a second entry.)
    merged = _gh("pr", "list", "--repo", repo, "--head", branch, "--state", "merged", "--json", "number",
                 "-q", "length", check=False).strip()
    if issue.get("state", "OPEN") != "OPEN" or merged not in ("", "0"):
        print(f"issue #{number} is already done", file=out)
        return 0
    answers = parse_issue_body(issue.get("body", ""))
    if not answers.get("date") and issue.get("createdAt"):   # dated when it was submitted, not when it is read
        import datetime as dt
        from zoneinfo import ZoneInfo
        at = dt.datetime.fromisoformat(issue["createdAt"].replace("Z", "+00:00"))
        if book.config.get("timezone"):
            at = at.astimezone(ZoneInfo(book.config["timezone"]))
        answers["date"], answers["time"] = at.strftime("%Y-%m-%d"), at.strftime("%H:%M")
    _loose, unknown = file_notes(answers.get("files", ""))
    note = ("\n\nNot understood in \"Figures and files\": " + ", ".join(f"`{u}:`" for u in unknown) +
            " (the labels are Caption, Alt and Source).") if unknown else ""
    if not answers.get("title"):   # the form uses the issue's own title (since v2026.10.25)
        answers["title"] = re.sub(r"^\s*(new\s+)?entry:\s*", "", issue.get("title", ""), flags=re.I).strip()
    person = book.person_by_login(submitter)

    def tell(text: str) -> None:
        _gh("issue", "comment", str(number), "--repo", repo, "--body", text, check=False)

    if book.people is not None and person is None:
        tell(f"@{submitter} is not in people.yaml, so this cannot become an entry yet. Ask the PI to add you.")
        return 1
    root = book.root
    connect.run(["git", "-C", str(root), "fetch", "-q", "origin", "main"])
    connect.run(["git", "-C", str(root), "switch", "-q", "-C", branch, "origin/main"])
    with tempfile.TemporaryDirectory() as tmp:
        try:
            header, body = draft_from_issue(book, answers, parse_files(answers.get("files", "")), Path(tmp),
                                            os.environ.get("GH_TOKEN"), fetch=fetch_with_signed(signed_images(repo, number)))
            opts = newentry.Options(handle=person.handle if person else submitter)
            path, h, body = newentry.build(open_book(root), header, body, Path(tmp), opts)
        except Exception as e:   # noqa: BLE001 - the author sees what went wrong on the issue
            tell(f"This form could not be turned into an entry: {e}\n\nEdit the issue to try again.")
            return 1
    name = person.name if person else submitter
    email = (person.email if person and person.email else f"{submitter}@users.noreply.github.com")
    connect.run(["git", "-C", str(root), "add", "-A", str(book.entries_dir)])
    connect.run(["git", "-C", str(root), "-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-q",
                 "-m", f"Entry: {h['title']}\n\nFrom issue #{number} by @{submitter}."])
    report = check.run(open_book(root), check.Options(base="origin/main", submitter=submitter, ci=True))
    if report.exit_code:
        if any(".alt" in f.message for f in report.findings if f.level == "fail"):
            note += ("\n\n**Every figure needs a description (alt text)** for readers who cannot see it. For an "
                     "image dragged into the text, edit the issue and replace `alt=\"Image\"` in its `<img …>` tag "
                     "with what the image shows; for a file in \"Figures and files\", add a line `Alt: …` (and "
                     "`Caption: …`) under it.")
        tell("The entry did not pass the checks. Edit the issue to fix it; the form is read again.\n\n```\n"
             + report.render(ci=True) + "\n```" + note)
        print(report.render(ci=True), file=out)
        return report.exit_code
    connect.run(["git", "-C", str(root), "push", "-q", "-f", "origin", branch])
    sha = connect.run(["git", "-C", str(root), "rev-parse", "HEAD"]).strip()
    url = _gh("pr", "create", "--repo", repo, "--head", branch, "--base", "main", "--title", f"Entry: {h['title']}",
              "--body", f"From #{number}, written by @{submitter}.\n\nCo-authored-by: {name} <{email}>",
              check=False).strip()
    if not url:
        url = _gh("pr", "view", branch, "--repo", repo, "--json", "url", "-q", ".url", check=False).strip()
    _gh("api", f"repos/{repo}/statuses/{sha}", "-f", "state=success", "-f", "context=entry-checks",
        "-f", f"description=checked in entry-from-issue as @{submitter}", check=False)
    _gh("pr", "merge", "--repo", repo, "--auto", "--squash", url, check=False)
    # A merge by the workflow's token does not apply "Closes #N", so the issue is closed here.
    _gh("issue", "close", str(number), "--repo", repo, "--comment",
        f"Entry `{path.stem}` passed the checks: {url} (it merges itself)." + note, check=False)
    rebuild_site_after_merge(url, repo, out)
    print(f"pull request: {url}", file=out)
    return 0


# ------------------------------------------------------------------------- GitHub settings --
RULESET = {
    "name": "main: append-only log book",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    # GitHub rulesets take roles, teams and apps as bypass actors, not single people: the
    # repository admin role (5) is the PI (and the organisation's owners, who are admins anyway).
    "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}],
    "rules": [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {"type": "required_linear_history"},
        {"type": "pull_request", "parameters": {
            "required_approving_review_count": 0, "dismiss_stale_reviews_on_push": False,
            "require_code_owner_review": True, "require_last_push_approval": False,
            "required_review_thread_resolution": False, "allowed_merge_methods": ["squash"]}},
        # the check must come from GitHub Actions (app 15368), not from anyone's token
        {"type": "required_status_checks", "parameters": {
            "strict_required_status_checks_policy": False,
            "required_status_checks": [{"context": "entry-checks", "integration_id": 15368}]}},
    ],
}


def settings_script(repo: str, admin_login: str, team: str | None = None) -> str:
    """A shell script, for the repository's owner to read and run, that sets the repository up
    for a central log book (STRATEGY: ruleset, merges, Actions, Pages, label, environments)."""
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) or not re.fullmatch(r"[\w-]+", admin_login):
        raise ValueError("repo is owner/name and the login a GitHub user name")
    ruleset = json.dumps(RULESET, indent=2)
    org = repo.split("/")[0]
    team_line = (f'gh api -X PUT "orgs/{org}/teams/{team}/repos/$REPO" -f permission=push   # the lab team writes\n'
                 if team else "# gh api -X PUT \"orgs/<org>/teams/<team>/repos/$REPO\" -f permission=push   # a team that writes\n")
    return f"""#!/bin/sh
# Settings for a central log book on GitHub ({repo}), written by `logbook github-settings`.
# Read it, then run it as the repository's admin: sh github-settings.sh. Needs gh, signed in.
# Each step can be run on its own; nothing here is a secret. lab/docs/LOGBOOK_SETUP.md explains each.
set -eu
REPO={repo}

# 1. Merges: squash only (one commit per entry, linear history); the pull request's description
#    becomes the commit message (it carries the author's co-author line and, for a lab/ update,
#    the git-subtree lines); auto-merge on; branches deleted after merge.
gh api -X PATCH "repos/$REPO" -F allow_auto_merge=true -F allow_squash_merge=true -F allow_merge_commit=false \\
  -F allow_rebase_merge=false -F delete_branch_on_merge=true -f squash_merge_commit_title=PR_TITLE \\
  -f squash_merge_commit_message=PR_BODY > /dev/null

# 2. Actions: read-only token by default (the workflows ask for what they need) and allowed to
#    open pull requests (the "New entry" form's workflow does).
gh api -X PUT "repos/$REPO/actions/permissions/workflow" -f default_workflow_permissions=read \\
  -F can_approve_pull_request_reviews=true

# 3. Who writes.
{team_line}
# 4. The label the form sets; the form's workflow acts only on issues that carry it.
gh label create new-entry -R "$REPO" --color 500000 --description "A submitted New entry form" 2>/dev/null || true

# 5. Environments: exports and the monthly snapshot wait for the PI's approval.
ID=$(gh api "users/{admin_login}" -q .id)
for env in export attest; do
  printf '{{"reviewers":[{{"type":"User","id":%s}}],"prevent_self_review":false}}' "$ID" |
    gh api -X PUT "repos/$REPO/environments/$env" --input - > /dev/null
done

# 6. The ruleset on main: pull requests only, the check entry-checks from GitHub Actions,
#    no force pushes, no deletions, linear history, code-owner review (CODEOWNERS leaves
#    entries/ and wiki/ to everyone); the admin role bypasses.
gh api -X POST "repos/$REPO/rulesets" --input - > /dev/null <<'JSON'
{ruleset}
JSON
# 7. Pages from Actions, private: only people who can read the repository see the view.
#    Private Pages need GitHub Enterprise Cloud. Where the site cannot be private, Pages is
#    turned off again and the script stops: a lab book is never public (LOGBOOK_SETUP.md says
#    what to do instead).
gh api -X POST "repos/$REPO/pages" -f build_type=workflow > /dev/null 2>&1 || true
if ! gh api -X PUT "repos/$REPO/pages" -F public=false > /dev/null 2>&1 || \
   [ "$(gh api "repos/$REPO/pages" -q .public)" != "false" ]; then
  gh api -X DELETE "repos/$REPO/pages" > /dev/null 2>&1 || true
  echo "Pages cannot be private for $REPO (needs GitHub Enterprise Cloud): Pages is off; everything else is set."
  exit 1
fi
echo "done: $REPO is set up as a central log book"
"""


def codeowners(book: Book) -> str:
    admins = [p.github for p in (book.people or {}).values() if p.role == "admin" and p.github]
    owners = " ".join(f"@{a}" for a in admins) or "@TODO-admin-login"
    return ("# Everything outside entries/ and wiki/ is changed by the admins (the PI); entries and wiki pages\n"
            "# need no review: their pull requests merge when the check entry-checks passes.\n"
            f"*          {owners}\n/entries/\n/wiki/\n")
