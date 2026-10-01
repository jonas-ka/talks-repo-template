"""Mirror the reviewed catalog into the lab's shared Google Drive, append-only.

    talks sync-drive [--kind plot ...] [--id ...] [--limit N] [--dry-run]

Target (CLAUDE.md hard rule: files.create only, never update/rename/move/delete):
    LabName/Figures/<catalog-id>/   plots, schematics, tables, equations
    LabName/Photos/<catalog-id>/    photos, logos, screenshots
One folder per entry at the top level, with the original file, the SVG twin (vector
figures), a PNG preview, the plotting source (assets/sources/<id>/ when present) and
figure.yaml with topics, level, provenance and uses (no alt text or caption: those are
the author's). A dated index CSV is written at Figures/index-<date>.csv. Existing names are never overwritten: an entry
folder that exists is completed with missing files only.
"""

import csv
import io
import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from talks_repo import REPO_ROOT
from talks_repo.extract import read_container

SHARED_DRIVE_ID = "<shared-drive-id>"   # LabName
FOLDER = "application/vnd.google-apps.folder"
FIGURE_KINDS = {"plot", "schematic", "table", "equation"}
PHOTO_KINDS = {"photo", "logo", "screenshot"}
CATALOG = REPO_ROOT / "assets" / "catalog.yaml"


class Drive:
    """The only Drive write used is files.create. Listing is read-only."""

    def __init__(self) -> None:
        from googleapiclient.discovery import build
        from talks_repo import gslides

        self.svc = build("drive", "v3", credentials=gslides.credentials(), cache_discovery=False)

    def list_children(self, parent: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        token = None
        while True:
            r = self.svc.files().list(
                q=f"'{parent}' in parents and trashed=false", corpora="drive", driveId=SHARED_DRIVE_ID,
                includeItemsFromAllDrives=True, supportsAllDrives=True, pageSize=1000, pageToken=token,
                fields="nextPageToken, files(id,name,mimeType,size,modifiedTime)",
            ).execute()
            for f in r.get("files", []):
                out.setdefault(f["name"], f)
            token = r.get("nextPageToken")
            if not token:
                return out

    def top_folder(self, name: str) -> str:
        top = self.list_children(SHARED_DRIVE_ID)
        return top[name]["id"]

    def ensure_folder(self, parent: str, name: str, existing: dict[str, dict[str, Any]] | None = None, dry_run: bool = False) -> str:
        existing = existing if existing is not None else self.list_children(parent)
        if name in existing and existing[name]["mimeType"] == FOLDER:
            return existing[name]["id"]
        if dry_run:
            return f"dry-run:{name}"
        f = self.svc.files().create(
            body={"name": name, "mimeType": FOLDER, "parents": [parent]}, supportsAllDrives=True, fields="id"
        ).execute()
        return f["id"]

    def download(self, file_id: str) -> bytes:
        from googleapiclient.http import MediaIoBaseDownload

        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, self.svc.files().get_media(fileId=file_id, supportsAllDrives=True))
        done = False
        while not done:
            _, done = dl.next_chunk()
        return buf.getvalue()

    def move(self, file_id: str, from_parent: str, to_parent: str, dry_run: bool = False) -> None:
        """The one write besides `files.create`: a file moves from a figure folder's top level
        into that figure's dated version subfolder (the author, 2026-10-01). Nothing else is ever moved."""
        if dry_run:
            return
        self.svc.files().update(fileId=file_id, addParents=to_parent, removeParents=from_parent,
                                supportsAllDrives=True, fields="id,parents").execute()

    def upload(self, parent: str, name: str, data: bytes, mime: str, dry_run: bool = False) -> str | None:
        import time

        from googleapiclient.http import MediaIoBaseUpload

        if dry_run:
            return None
        for attempt in range(6):  # Drive returns transient 5xx now and then
            try:
                media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=len(data) > 5_000_000)
                f = self.svc.files().create(
                    body={"name": name, "parents": [parent]}, media_body=media, supportsAllDrives=True, fields="id"
                ).execute(num_retries=3)
                return f["id"]
            except Exception:  # noqa: BLE001
                if attempt == 5:
                    raise
                time.sleep(2 ** attempt)
        return None


_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".svg": "image/svg+xml",
         ".pdf": "application/pdf", ".tif": "image/tiff", ".tiff": "image/tiff", ".tex": "text/plain",
         ".yaml": "text/yaml", ".csv": "text/csv", ".py": "text/x-python", ".ipynb": "application/json",
         ".txt": "text/plain", ".md": "text/markdown", ".json": "application/json", ".bmp": "image/bmp", ".webp": "image/webp"}


PNG_DPI = 300


def _svg_to_pdf(svg: bytes) -> bytes | None:
    """Render an SVG to a PDF page of its own size with Typst (no other converter needed)."""
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "figure.svg").write_bytes(svg)
        (d / "main.typ").write_text('#set page(width: auto, height: auto, margin: 0pt)\n#image("figure.svg")\n', encoding="utf-8")
        r = subprocess.run(["typst", "compile", "--root", td, str(d / "main.typ"), str(d / "figure.pdf")],
                           capture_output=True, text=True)
        if r.returncode != 0 or not (d / "figure.pdf").exists():
            return None
        return (d / "figure.pdf").read_bytes()


def _pdf_to_png(pdf: bytes, dpi: int = PNG_DPI) -> bytes | None:
    try:
        import pymupdf

        with pymupdf.open(stream=pdf, filetype="pdf") as doc:
            return doc[0].get_pixmap(dpi=dpi, alpha=False).tobytes("png")
    except Exception:  # noqa: BLE001
        return None


def _pdf_to_svg(pdf: bytes) -> bytes | None:
    try:
        import pymupdf

        with pymupdf.open(stream=pdf, filetype="pdf") as doc:
            return doc[0].get_svg_image(text_as_path=True).encode()
    except Exception:  # noqa: BLE001
        return None


def _entry_bytes(e: dict[str, Any]) -> list[tuple[str, bytes]]:
    """(filename, bytes) pairs to upload for one entry.

    Every figure folder gets the compiled figure in the three formats people need, so
    anyone can use it as it is or start from the vector: `<id>.pdf`, `<id>.svg` and
    `<id>.png` at 300 dpi (from whichever of PDF/SVG is the original; a raster original
    is kept as it is, plus a PNG copy if it is not one). Then `figure.yaml` (provenance,
    no caption or alt: the author writes those), and `code/` and `data/` from the entry's
    `source_dir` (files under `data/` go to `data/`, everything else to `code/`; `plots/`
    is skipped because the figure files are already here)."""
    out: list[tuple[str, bytes]] = []
    original: bytes | None = None
    ext = ""
    if e.get("file"):
        p = REPO_ROOT / "assets" / e["file"]
        if p.exists():
            original = p.read_bytes()
            ext = p.suffix.lower()
    elif e.get("archive_ref"):
        ref = e["archive_ref"]
        container = ref if ref.startswith("/") else str(REPO_ROOT / ref)
        try:
            original = read_container(container)
            ext = Path(container.split("::")[-1]).suffix.lower() or ".png"
        except Exception:  # noqa: BLE001
            pass
    if original:
        out.append((f"{e['id']}{ext}", original))
    have = {Path(n).suffix for n, _ in out}
    pdf = original if ext == ".pdf" else None
    svg = original if ext == ".svg" else None
    if e.get("svg") and svg is None:
        p = REPO_ROOT / "assets" / e["svg"]
        if p.exists():
            svg = p.read_bytes()
    if pdf is not None and svg is None:
        svg = _pdf_to_svg(pdf)
    if svg is not None and pdf is None:
        pdf = _svg_to_pdf(svg)
    if pdf is not None and ".pdf" not in have:
        out.append((f"{e['id']}.pdf", pdf))
    if svg is not None and ".svg" not in have:
        out.append((f"{e['id']}.svg", svg))
    if pdf is not None:
        png = _pdf_to_png(pdf)
        if png is not None:
            out.append((f"{e['id']}.png", png))
    elif original and ext not in (".png", ".jpg", ".jpeg"):
        # a raster in another format (tiff, bmp, ...): add a PNG copy
        try:
            from talks_repo.extract import _pil_image

            img = _pil_image(original, ext)
            if img is not None:
                buf = io.BytesIO()
                img.convert("RGB").save(buf, format="PNG", optimize=True)
                out.append((f"{e['id']}.png", buf.getvalue()))
        except Exception:  # noqa: BLE001
            pass
    readme = {"version": int(e.get("version") or 1)}
    readme |= {k: e.get(k) for k in ("id", "kind", "topic", "level", "source", "first_used",
                                     "last_used", "n_uses", "origin", "uses", "vector", "supersedes", "latex", "notes")}
    readme["archive_ref"] = e.get("archive_ref")
    readme["alt"] = None
    readme["caption"] = None
    readme["note"] = "alt text and caption to be written by the author"
    readme["files"] = ("<id>.pdf, <id>.svg, <id>.png (300 dpi) are the same figure; code/ and data/ "
                       "hold the plotting script and its inputs where they exist")
    readme["exported_from"] = "talks-repo assets/catalog.yaml"
    out.append(("figure.yaml", yaml.safe_dump(readme, sort_keys=False, allow_unicode=True).encode()))
    if e.get("source_dir") and (REPO_ROOT / "assets" / e["source_dir"]).is_dir():
        root = REPO_ROOT / "assets" / e["source_dir"]
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root)
            top = rel.parts[0] if len(rel.parts) > 1 else ""
            if top == "plots":
                continue
            if top == "data":
                out.append((f"data/{rel.relative_to('data').as_posix()}", p.read_bytes()))
            elif top == "code":
                out.append((f"code/{rel.relative_to('code').as_posix()}", p.read_bytes()))
            else:
                out.append((f"code/{rel.as_posix()}", p.read_bytes()))
    # Files that live outside the repo (a sibling repository, a large export): uploaded
    # from their path, never copied into git. Paths are absolute or relative to the repo root.
    for key, sub in (("code_files", "code"), ("data_files", "data")):
        paths = [Path(f) if Path(f).is_absolute() else (REPO_ROOT / f) for f in e.get(key) or []]
        paths = [fp for fp in paths if fp.is_file()]
        names = [fp.name for fp in paths]
        for fp in paths:
            # the same basename from two folders (exports/v3 and exports/v4): keep the folder name
            name = f"{fp.parent.name}-{fp.name}" if names.count(fp.name) > 1 else fp.name
            out.append((f"{sub}/{name}", fp.read_bytes()))
    return out


def _drive_version(drive: "Drive", present: dict[str, dict[str, Any]]) -> int | None:
    """The version recorded in the folder's top-level figure.yaml (1 if the file has none);
    None when there is no figure.yaml, i.e. nothing to version."""
    f = present.get("figure.yaml")
    if f is None:
        return None
    try:
        meta = yaml.safe_load(drive.download(f["id"])) or {}
        return int(meta.get("version") or 1)
    except Exception:  # noqa: BLE001
        return 1


def _archive_version(drive: "Drive", folder_id: str, present: dict[str, dict[str, Any]], old_version: int,
                     fig_id: str, dry_run: bool = False) -> int:
    """Move every top-level file and the code/ and data/ folders of a figure folder into
    v<old>_<YYYY-MM-DD>_<id>/, dated by the newest top-level file. Version subfolders
    (v<N>_...) and other subfolders stay where they are."""
    items = [v for n, v in present.items() if not (v["mimeType"] == FOLDER and not n in ("code", "data"))]
    if not items:
        return 0
    newest = max((v.get("modifiedTime") or "") for v in items)[:10] or date.today().isoformat()
    sub = f"v{old_version}_{newest}_{fig_id}"
    sub_id = drive.ensure_folder(folder_id, sub, existing=present, dry_run=dry_run)
    n = 0
    for v in items:
        drive.move(v["id"], folder_id, sub_id, dry_run=dry_run)
        n += 1
    return n


def sync(kinds: set[str] | None, ids: set[str] | None, limit: int | None, dry_run: bool) -> dict[str, Any]:
    cat = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or []
    drive = Drive()
    roots = {"Figures": drive.top_folder("Figures"), "Photos": drive.top_folder("Photos")}
    catalog_folders = dict(roots)   # flat: one folder per entry directly under Figures/ and Photos/
    existing = {name: drive.list_children(fid) for name, fid in catalog_folders.items()}
    stats: dict[str, int] = {"entries": 0, "folders_created": 0, "files_uploaded": 0, "files_skipped": 0, "bytes": 0}
    index_rows: list[dict[str, Any]] = []
    for e in cat:
        kind = e.get("kind")
        if kinds and kind not in kinds:
            continue
        if ids and e["id"] not in ids:
            continue
        if kind in FIGURE_KINDS:
            area = "Figures"
        elif kind in PHOTO_KINDS:
            area = "Photos"
        else:
            continue
        if limit and stats["entries"] >= limit:
            break
        stats["entries"] += 1
        payload = _entry_bytes(e)
        parent = catalog_folders[area]
        had_folder = e["id"] in existing[area]
        folder_id = drive.ensure_folder(parent, e["id"], existing=existing[area], dry_run=dry_run)
        if not had_folder:
            stats["folders_created"] += 1
            present: dict[str, dict[str, Any]] = {}
            existing[area][e["id"]] = {"id": folder_id, "name": e["id"], "mimeType": FOLDER}
        else:
            present = drive.list_children(folder_id) if not dry_run else {}
            # A newer version of the figure: the top level keeps the latest, so the files there
            # move into v<old>_<date>_<id>/ first (docs/FIGURES_README.md, 2026-10-01).
            version = int(e.get("version") or 1)
            old_version = _drive_version(drive, present)
            if old_version is not None and old_version < version:
                moved = _archive_version(drive, folder_id, present, old_version, e["id"], dry_run=dry_run)
                stats["files_archived"] = stats.get("files_archived", 0) + moved
                present = drive.list_children(folder_id) if not dry_run else {}
        sub_folders: dict[str, str] = {}
        for name, data in payload:
            target = folder_id
            if "/" in name:
                sub, name = name.split("/", 1)
                if "source" in present and sub in ("code", "data"):
                    stats["files_skipped"] += 1   # older layout already there; the drive is append-only
                    continue
                if sub not in sub_folders:
                    sub_folders[sub] = drive.ensure_folder(folder_id, sub, existing=present, dry_run=dry_run)
                target = sub_folders[sub]
            if name in present:
                stats["files_skipped"] += 1
                continue
            drive.upload(target, name, data, _MIME.get(Path(name).suffix.lower(), "application/octet-stream"), dry_run=dry_run)
            stats["files_uploaded"] += 1
            stats["bytes"] += len(data)
        index_rows.append({"id": e["id"], "kind": kind, "area": area, "caption": e.get("caption", ""),
                           "topics": " ".join(e.get("topic") or []), "first_used": e.get("first_used"),
                           "last_used": e.get("last_used"), "n_uses": e.get("n_uses"), "vector": e.get("vector")})
    # dated index, one per area, never overwritten
    for area, parent in catalog_folders.items():
        rows = [r for r in index_rows if r["area"] == area]
        if not rows:
            continue
        name = f"index-{date.today().isoformat()}.csv"
        if name in existing[area]:
            continue
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
        drive.upload(parent, name, buf.getvalue().encode(), "text/csv", dry_run=dry_run)
    stats["dry_run"] = dry_run
    return stats
