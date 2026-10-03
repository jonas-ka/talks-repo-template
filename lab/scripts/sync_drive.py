"""Upload the figure-library README, the lab-notebook template and guide to the lab's Drive
folders, create-only: an existing name is never overwritten; a changed file goes up under a
versioned name (`README-v2026.10.2.md`). Nothing is renamed, moved or deleted.

    uv run --with google-api-python-client --with google-auth-oauthlib scripts/sync_drive.py [--dry-run]

Credentials: an OAuth token file (`token.json` of the talks repository) at $LAB_DRIVE_TOKEN or
~/Projects/talks-repo/token.json; the shared drive id at $LAB_SHARED_DRIVE_ID (the private
repositories know it). Neither is stored here.
"""

from __future__ import annotations

import hashlib
import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text().strip()
TARGETS = {  # Drive folder path (under the shared drive root) -> files (local path, Drive name)
    "Figures": [("docs/FIGURES_README.md", "README.md"), ("matplotlib/LabName-figure-template.ipynb", "_LabName-figure-template-README.ipynb")],
    "Photos": [("docs/FIGURES_README.md", "README.md")],
    "How-tos/Lab-notebook-template": [("docs/FIGURES_README.md", "README.md"), ("notes/labnotes-template.typ", "labnotes-template.typ"), ("docs/LOGBOOK_GUIDE.md", "LOGBOOK_GUIDE.md")],
}
MIME = {".md": "text/markdown", ".typ": "text/plain", ".ipynb": "application/json"}


def main(dry_run: bool) -> int:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload

    token = Path(os.environ.get("LAB_DRIVE_TOKEN", Path.home() / "Projects/talks-repo/token.json"))
    drive_id = os.environ.get("LAB_SHARED_DRIVE_ID", "")
    if not token.exists() or not drive_id:
        print("need the token file and LAB_SHARED_DRIVE_ID (see the docstring)", file=sys.stderr)
        return 2
    svc = build("drive", "v3", credentials=Credentials.from_authorized_user_file(str(token)), cache_discovery=False)

    def children(parent: str) -> dict[str, dict]:
        out, tok = {}, None
        while True:
            r = svc.files().list(q=f"'{parent}' in parents and trashed=false", corpora="drive", driveId=drive_id,
                                 includeItemsFromAllDrives=True, supportsAllDrives=True, pageSize=1000, pageToken=tok,
                                 fields="nextPageToken, files(id,name,mimeType,md5Checksum)").execute()
            for f in r.get("files", []):
                out.setdefault(f["name"], f)
            tok = r.get("nextPageToken")
            if not tok:
                return out

    for path, files in TARGETS.items():
        node = drive_id
        for name in path.split("/"):
            kids = children(node)
            if name not in kids:
                print(f"{path}: folder '{name}' not found; skipped")
                node = None
                break
            node = kids[name]["id"]
        if node is None:
            continue
        present = children(node)
        for local, drive_name in files:
            data = (ROOT / local).read_bytes()
            md5 = hashlib.md5(data).hexdigest()
            if drive_name in present and present[drive_name].get("md5Checksum") == md5:
                print(f"{path}/{drive_name}: unchanged")
                continue
            name = drive_name
            if name in present:   # never overwrite: the new version gets the tag in its name
                stem, ext = os.path.splitext(drive_name)
                name = f"{stem}-{VERSION}{ext}"
                k = 2
                while name in present:
                    name = f"{stem}-{VERSION}-{k}{ext}"
                    k += 1
            print(f"{path}/{name}: {'would upload' if dry_run else 'uploading'} ({len(data)} bytes)")
            if not dry_run:
                media = MediaIoBaseUpload(io.BytesIO(data), mimetype=MIME.get(Path(local).suffix, "application/octet-stream"))
                svc.files().create(body={"name": name, "parents": [node]}, media_body=media, supportsAllDrives=True, fields="id").execute()
    return 0


if __name__ == "__main__":
    sys.exit(main("--dry-run" in sys.argv))
