"""Who is writing, and where entries go.

A repository that writes to a *central* log book says so in its `logbook.yaml`:

    central:
      repository: owner/name          # the central log book on GitHub
      clone: ~/Projects/logbook       # a local clone of it
      project: FastSims               # default project for entries written from here
      projects: [FastSims]            # what `logbook pull` copies here (default: [project])
      copy: logbook                   # where the copy goes (default: logbook/)

Without `central`, the repository is its own (standalone) log book. Who is writing comes from
`~/.config/logbook/config.yaml` (`handle: aa`), else from the GitHub login (`gh api user`) looked
up in the central book's people.yaml, else from git's user.name.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .book import Book, open_book
from .entry import load_yaml

USER_CONFIG = Path(os.environ.get("LOGBOOK_USER_CONFIG", "~/.config/logbook/config.yaml")).expanduser()


class ConnectError(RuntimeError):
    pass


def run(cmd: list[str], cwd: Path | None = None, check: bool = True, env: dict | None = None) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})
    if check and r.returncode:
        raise ConnectError(f"{' '.join(cmd[:3])} …: {(r.stderr or r.stdout).strip()[:800]}")
    return r.stdout


@dataclass
class Target:
    """Where a new entry is written."""
    book: Book                  # the book the entry belongs to (central clone, or this repository)
    central: dict | None        # the `central` section of the local logbook.yaml, if any
    here: Path                  # the repository the command was run in

    @property
    def connected(self) -> bool:
        return self.central is not None


def local_config(start: Path) -> tuple[Path, dict]:
    """The nearest logbook.yaml (or the git top level with an empty config)."""
    start = start.resolve()
    for d in [start, *start.parents]:
        f = d / "logbook.yaml"
        if f.exists():
            return d, (load_yaml(f.read_text(encoding="utf-8")) or {})
    top = run(["git", "-C", str(start), "rev-parse", "--show-toplevel"], check=False).strip()
    return (Path(top) if top else start), {}


def target(start: Path | None = None) -> Target:
    here, cfg = local_config(Path(start or "."))
    central = cfg.get("central")
    if central:
        clone = Path(os.path.expanduser(str(central.get("clone", "")))).resolve()
        if not (clone / ".git").exists():
            raise ConnectError(f"the central log book's clone {clone} is missing: "
                               f"git clone https://github.com/{central.get('repository')} {clone}")
        return Target(open_book(clone), central, here)
    return Target(open_book(here), None, here)


def user_handle(book: Book) -> str | None:
    if USER_CONFIG.exists():
        h = (load_yaml(USER_CONFIG.read_text(encoding="utf-8")) or {}).get("handle")
        if h:
            return str(h)
    login = github_login()
    p = book.person_by_login(login)
    if p:
        return p.handle
    if book.people is None:   # standalone: a free name
        name = run(["git", "config", "user.name"], check=False).strip()
        return name or None
    return None


def github_login() -> str | None:
    if os.environ.get("LOGBOOK_SUBMITTER"):
        return os.environ["LOGBOOK_SUBMITTER"]
    if not shutil.which("gh"):
        return None
    out = run(["gh", "api", "user", "-q", ".login"], check=False).strip()
    return out or None


def repo_visibility(repo_dir: Path) -> str | None:
    """PUBLIC, PRIVATE or INTERNAL for the repository's origin on GitHub; None if unknown."""
    if os.environ.get("LOGBOOK_VISIBILITY"):          # tests, and machines without gh
        return os.environ["LOGBOOK_VISIBILITY"].upper()
    url = run(["git", "-C", str(repo_dir), "remote", "get-url", "origin"], check=False).strip()
    if not url or not shutil.which("gh"):
        return None
    out = run(["gh", "repo", "view", url, "--json", "visibility", "-q", ".visibility"], check=False).strip()
    return out.upper() or None
