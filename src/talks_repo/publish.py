"""Publish a deck's deliverables to the author's Talks-and-Travel folder on Google Drive.

The sources stay in this repository; the files people open (the UA-1 PDF, the PPTX for
Google Slides, the HTML slideshow) go where the author keeps every trip:

    My Drive/1-Areas/Research/Talks-and-Travel/<YYMM.Event>/<deck stem>/

`<YYMM.Event>` is the existing trip folder whose name starts with the deck's `YYMM.` and
mentions the event (matched loosely, case-insensitive, hyphens and spaces ignored), or a new
folder `YYMM.<Event>` when there is none; `--folder` names it explicitly. Inside it the deck
gets its own subfolder named after the deck stem (`2611.TRIUMF-Colloquium-YourName/`),
as the older trips do. Everything goes through the Drive API with `files.create` only: an
existing name is never overwritten, a second upload of the same name gets `-2`, `-3`, ...

    talks publish <slug>               PDF + PPTX + HTML of the newest deck in talks/<slug>/
    talks publish <slug> --dry-run     say what would be created
    talks publish <slug> --folder "2611.TRIUMF-colloquium"

The local CloudStorage mirror of "My Drive" is not used (it may be unreadable or hold
placeholders); the folder id is looked up by path from the Drive root.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from talks_repo import REPO_ROOT
from talks_repo.drive_sync import FOLDER, Drive, _MIME

TALKS_AND_TRAVEL = ("1-Areas", "Research", "Talks-and-Travel")


def _children(drive: Drive, parent: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    token = None
    while True:
        r = drive.svc.files().list(q=f"'{parent}' in parents and trashed=false", pageSize=1000, pageToken=token,
                                   fields="nextPageToken, files(id,name,mimeType)",
                                   supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        for f in r.get("files", []):
            out.setdefault(f["name"], f)
        token = r.get("nextPageToken")
        if not token:
            return out


def talks_and_travel(drive: Drive) -> str:
    node = "root"
    for name in TALKS_AND_TRAVEL:
        kids = _children(drive, node)
        if name not in kids:
            raise FileNotFoundError(f"My Drive/{'/'.join(TALKS_AND_TRAVEL)}: '{name}' not found")
        node = kids[name]["id"]
    return node


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def match_trip_folder(folders: dict[str, dict[str, Any]], yymm: str, event: str) -> str | None:
    """The trip folder for this deck: starts with `YYMM.` and shares a word with the event."""
    cands = [n for n, f in folders.items() if f["mimeType"] == FOLDER and n.startswith(yymm + ".")]
    if not cands:
        return None
    words = [w for w in re.split(r"[^A-Za-z0-9]+", event) if len(w) >= 3]
    scored = []
    for n in cands:
        nn = _norm(n)
        score = sum(1 for w in words if _norm(w) in nn)
        if score:
            scored.append((score, -len(n), n))
    if scored:
        return max(scored)[2]
    return cands[0] if len(cands) == 1 else None


def deliverables(slug: str) -> tuple[str, list[Path], dict[str, Any]]:
    """The deck stem and its PDF/PPTX/HTML, from the newest PDF in talks/<slug>/."""
    import yaml

    folder = REPO_ROOT / "talks" / slug
    pdfs = sorted(folder.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not pdfs:
        raise FileNotFoundError(f"no PDF in {folder}; compile the deck first")
    stem = pdfs[0].stem
    files = [p for p in (folder / f"{stem}{ext}" for ext in (".pdf", ".pptx", ".html")) if p.exists()]
    brief = yaml.safe_load((folder / "brief.yaml").read_text(encoding="utf-8")) if (folder / "brief.yaml").exists() else {}
    return stem, files, brief


def publish(slug: str, folder: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    stem, files, brief = deliverables(slug)
    yymm = stem.split(".")[0]
    event = str(brief.get("event") or stem.split(".", 1)[1].rsplit("-", 1)[0])
    drive = Drive()
    root = talks_and_travel(drive)
    trips = _children(drive, root)
    trip_name = folder or match_trip_folder(trips, yymm, event)
    created_trip = False
    if trip_name is None:
        trip_name = f"{yymm}.{re.sub(r'[^A-Za-z0-9]+', '-', event).strip('-')}"
    if trip_name in trips:
        trip_id = trips[trip_name]["id"]
    else:
        created_trip = True
        trip_id = drive.ensure_folder(root, trip_name, existing=trips, dry_run=dry_run)
    sub = _children(drive, trip_id) if not dry_run or not created_trip else {}
    deck_id = sub[stem]["id"] if stem in sub else drive.ensure_folder(trip_id, stem, existing=sub, dry_run=dry_run)
    present = _children(drive, deck_id) if (stem in sub) else {}
    uploaded: list[str] = []
    for p in files:
        name = p.name
        k = 2
        while name in present:                      # never overwrite: a new upload gets a suffix
            name = f"{p.stem}-{k}{p.suffix}"
            k += 1
        drive.upload(deck_id, name, p.read_bytes(), _MIME.get(p.suffix.lower(), "application/octet-stream"), dry_run=dry_run)
        uploaded.append(name)
    return {"trip": trip_name, "trip_created": created_trip, "deck_folder": stem, "uploaded": uploaded,
            "bytes": sum(p.stat().st_size for p in files), "dry_run": dry_run,
            "path": f"My Drive/{'/'.join(TALKS_AND_TRAVEL)}/{trip_name}/{stem}/"}
