"""The few git questions the checker asks."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if r.returncode:
        raise GitError(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout


@dataclass
class Change:
    status: str        # A added, M modified, D deleted, R renamed, C copied, T type change
    path: str          # new path (for R/C) relative to the repository root
    old: str | None = None


def changes(root: Path, base: str, head: str = "HEAD") -> list[Change]:
    """What `head` changes relative to its merge base with `base` (what a pull request shows)."""
    out = _git(root, "diff", "--name-status", "--find-renames", "--find-copies", "-z", f"{base}...{head}")
    parts, res, i = out.split("\0"), [], 0
    while i < len(parts) and parts[i]:
        st = parts[i]
        if st[0] in "RC":
            res.append(Change(st[0], parts[i + 2], parts[i + 1]))
            i += 3
        else:
            res.append(Change(st[0], parts[i + 1]))
            i += 2
    return res


def file_at(root: Path, ref: str, path: str) -> str | None:
    try:
        return _git(root, "show", f"{ref}:{path}")
    except GitError:
        return None


def toplevel(path: Path) -> Path | None:
    try:
        return Path(_git(path, "rev-parse", "--show-toplevel").strip())
    except GitError:
        return None
