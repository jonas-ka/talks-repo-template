"""The attested monthly PDFs, copied into a folder (e.g. a synced Drive folder) from the book's
`snapshot/YYYY-MM` releases. A release exists only once the PI approved the monthly run, so the
copy is the attested record. Uses `gh`, signed in; no credentials of its own."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from . import connect
from .book import Book


def repository(book: Book) -> str | None:
    return (book.config.get("site") or {}).get("repository")


def snapshots(repo: str) -> list[str]:
    """The months (YYYY-MM) that have a published snapshot release, oldest first."""
    rows = json.loads(connect.run(["gh", "release", "list", "--repo", repo, "--limit", "500",
                                   "--json", "tagName,isDraft"]) or "[]")
    return sorted(r["tagName"].split("/", 1)[1] for r in rows
                  if r["tagName"].startswith("snapshot/") and not r["isDraft"])


def deliver(repo: str, to: Path, full: bool = False) -> list[Path]:
    """Copy each month's PDF (and, with `full`, the whole book as of that month) not yet in `to`.
    A file is written under a temporary name and renamed, so a sync client never sees half of it."""
    to.mkdir(parents=True, exist_ok=True)
    written = []
    for month in snapshots(repo):
        for name in [f"Logbook-{month}.pdf"] + ([f"Logbook-full-{month}.pdf"] if full else []):
            dest = to / name
            if dest.exists():
                continue
            with tempfile.TemporaryDirectory() as tmp:
                connect.run(["gh", "release", "download", f"snapshot/{month}", "--repo", repo,
                             "--pattern", name, "--dir", tmp])
                part = to / f".{name}.part"
                shutil.copyfile(Path(tmp) / name, part)
                os.replace(part, dest)
            written.append(dest)
    return written


def launch_agent(label: str, book_root: Path, to: Path, hour: int = 9, full: bool = False) -> str:
    """A macOS LaunchAgent that runs `logbook deliver` once a day. A day missed while the Mac
    sleeps runs at the next wake; months missed while it was off are caught up on the next run."""
    uv = shutil.which("uv") or "uv"
    log = Path.home() / "Library" / "Logs" / f"{label}.log"
    args = [uv, "run", "--project", str(book_root / "lab" / "logbook"), "logbook", "--root", str(book_root),
            "deliver", "--to", str(to)] + (["--full"] if full else [])
    a = "\n".join(f"    <string>{escape(x)}</string>" for x in args)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!-- Written by `logbook deliver --launch-agent` (lab-templates): daily at {hour}:00, the attested
     monthly PDFs of {escape(str(book_root))} into {escape(str(to))}.
     Install: save as ~/Library/LaunchAgents/{label}.plist, then
     launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/{label}.plist -->
<plist version="1.0">
<dict>
  <key>Label</key><string>{escape(label)}</string>
  <key>ProgramArguments</key>
  <array>
{a}
  </array>
  <key>WorkingDirectory</key><string>{escape(str(book_root))}</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>{escape(os.path.dirname(uv))}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>{hour}</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>{escape(str(log))}</string>
  <key>StandardErrorPath</key><string>{escape(str(log))}</string>
</dict>
</plist>
"""
