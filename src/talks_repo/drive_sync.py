"""Mirror the reviewed catalog into the lab's shared Google Drive, create-only.

    talks sync-drive [--kind plot ...] [--id ...] [--limit N] [--dry-run]

Layout (lab-templates docs/FIGURES_README.md, since v2026.10.10): one folder per figure under
LabName/Figures/ (photos, logos, screenshots under Photos/), every version side by side as
`<name>-v<N>.pdf/.svg/.png` with a record `<name>-v<N>.yaml`; poster and talk variants in the main
figure's folder as `<name>-poster-v<N>.*`; code copied per version (`code/<script>-v<N>.py`); each
data file once (changed data under a new name); `figure.yaml` (caption, alt text: the author's) only
when the folder has none. The catalog numbers versions by their place in the `supersedes` chain;
the Drive keeps its own numbering, because figures are also versioned there directly (labfig
redraws): a catalog version not yet on the Drive gets the next free Drive number, and its record
names the catalog id and catalog version (`exported_from`). Nothing on the Drive is ever
overwritten, moved, renamed or deleted: a catalog version that is already there (as its own folder
from the older layout, version 1 in its own folder, or named in a record) is skipped. A dated index CSV is written at Figures/index-<date>.csv.
"""

import csv
import io
import json
import re
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
    """The only Drive write is files.create (folders and files). Listing is read-only."""

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
                fields="nextPageToken, files(id,name,mimeType,size,modifiedTime,md5Checksum)",
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
            if any(part in ("__pycache__", ".ipynb_checkpoints") or part.startswith(".") for part in rel.parts):
                continue
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


def _chain(cat: list[dict[str, Any]]) -> dict[str, tuple[str, int]]:
    """id -> (root id, version): the version is the entry's place in its `supersedes` chain.
    An entry with `drive_root: true` starts its own chain (a redrawn figure replacing an unrelated one)."""
    by_id = {e["id"]: e for e in cat}
    out: dict[str, tuple[str, int]] = {}
    for e in cat:
        cur, n, seen = e, 1, {e["id"]}
        while (not cur.get("drive_root") and isinstance(cur.get("supersedes"), str)
               and cur["supersedes"] in by_id and cur["supersedes"] not in seen):
            cur = by_id[cur["supersedes"]]
            seen.add(cur["id"])
            n += 1
        out[e["id"]] = (cur["id"], n)
    return out


def _placement(root: str, roots: set[str], area_folders: dict[str, Any]) -> tuple[str, str]:
    """(Drive folder, file stem) for a figure whose chain starts at `root`: a poster or talk
    variant goes into its main figure's folder when that figure exists."""
    m = re.fullmatch(r"(.+)-(poster|talk)(-[a-z0-9]+)*", root)
    if m and (m.group(1) in roots or m.group(1) in area_folders):
        return m.group(1), root
    return root, root


def _versioned(name: str, stem: str, entry_id: str, version: int) -> str:
    """The Drive name of one payload file: figure files `<stem>-v<N>.<ext>`, code `code/<x>-v<N>.<ext>`,
    data and figure.yaml unchanged."""
    if name == "figure.yaml" or name.startswith("data/"):
        return name
    if name.startswith("code/"):
        q = Path(name[5:])
        return f"code/{q.parent.as_posix() + '/' if q.parent.as_posix() != '.' else ''}{q.stem}-v{version}{q.suffix}"
    q = Path(name)
    return f"{stem}-v{version}{q.suffix}" if q.stem == entry_id else name


def _record(e: dict[str, Any], stem: str, version: int, folder: str, files: list[str],
            code: list[str], data: list[tuple[str, str]], catalog_version: int = 1) -> bytes:
    """The version's record, in labfig's format (lab/matplotlib/labfig.py), so `labfig where-used`
    finds it by the data's checksums."""
    import subprocess
    import sys
    from datetime import datetime

    sys.path.insert(0, str(REPO_ROOT / "lab" / "matplotlib"))
    from labfig import _record_text

    commit = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return _record_text({
        "figure": stem, "version": version, "files": files,
        "saved": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": e.get("source"), "origin": e.get("origin"), "first_used": e.get("first_used"),
        "exported_from": {"repository": "talks-repo", "file": "assets/catalog.yaml", "id": e["id"],
                          "catalog_version": catalog_version, "commit": commit or None},
        "code": {"copies": code} if code else None,
        "data": {"files": [{"path": n, "sha256": h} for n, h in data]} if data else None,
        "drive": {"folder": folder},
        "note": "copied from the talks-repo catalog by `talks sync-drive`; drawn before lab-templates' labfig, so it has no information strip",
    }).encode()


def sync(kinds: set[str] | None, ids: set[str] | None, limit: int | None, dry_run: bool) -> dict[str, Any]:
    import hashlib

    cat = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or []
    chain = _chain(cat)
    roots = {r for r, _ in chain.values()}
    drive = Drive()
    area_ids = {"Figures": drive.top_folder("Figures"), "Photos": drive.top_folder("Photos")}
    existing = {name: drive.list_children(fid) for name, fid in area_ids.items()}
    stats: dict[str, int] = {"entries": 0, "versions_new": 0, "versions_present": 0, "folders_created": 0,
                             "files_uploaded": 0, "files_skipped": 0, "bytes": 0}
    plan: list[str] = []
    index_rows: list[dict[str, Any]] = []
    synced: dict[str, set[str]] = {}          # Drive folder -> catalog ids named in its records
    next_free: dict[tuple[str, str], int] = {}  # (folder, stem) -> next free Drive version
    for e in sorted(cat, key=lambda x: (chain[x["id"]][0], chain[x["id"]][1])):
        kind = e.get("kind")
        if kinds and kind not in kinds:
            continue
        if ids and e["id"] not in ids:
            continue
        area = "Figures" if kind in FIGURE_KINDS else "Photos" if kind in PHOTO_KINDS else None
        if area is None:
            continue
        if limit and stats["entries"] >= limit:
            break
        stats["entries"] += 1
        index_rows.append({"id": e["id"], "kind": kind, "area": area, "caption": e.get("caption", ""),
                           "topics": " ".join(e.get("topic") or []), "first_used": e.get("first_used"),
                           "last_used": e.get("last_used"), "n_uses": e.get("n_uses"), "vector": e.get("vector")})
        root, catalog_version = chain[e["id"]]
        folder, stem = _placement(root, roots, existing[area])
        other = "Photos" if area == "Figures" else "Figures"
        if folder not in existing[area] and (folder in existing[other] or e["id"] in existing[other]):
            area = other                          # already filed under the other area: stay there, no duplicate
            index_rows[-1]["area"] = area
            folder, stem = _placement(root, roots, existing[area])
        # already on the Drive: as its own folder (older layout), as version 1 in its own folder,
        # or named in one of the folder's records (this layout)
        if e["id"] in existing[area] and existing[area][e["id"]]["mimeType"] == FOLDER and e["id"] != folder:
            stats["versions_present"] += 1
            continue
        if catalog_version == 1 and folder == e["id"] and folder in existing[area]:
            stats["versions_present"] += 1
            continue
        fid = existing[area][folder]["id"] if folder in existing[area] else None
        present = drive.list_children(fid) if fid and not fid.startswith("dry-run:") else {}
        if folder not in synced:
            synced[folder] = set()
            for n, f in present.items():
                if n.endswith(".yaml") and re.fullmatch(r".+-v\d+\.yaml", n):
                    m = re.search(r'"id": "([^"]+)"', drive.download(f["id"]).decode("utf-8", "replace"))
                    if m:
                        synced[folder].add(m.group(1))
        if e["id"] in synced[folder]:
            stats["versions_present"] += 1
            continue
        # the older layout's dated version subfolders: v<N>_<date>_<name>[-<variant>-version]/
        variant = stem[len(folder) + 1:] if stem != folder else ""
        old_sub = re.compile(rf"v{catalog_version}_\d{{4}}-\d\d-\d\d_{re.escape(folder)}" + (rf"-{re.escape(variant)}-version" if variant else ""))
        if any(old_sub.fullmatch(n) and f["mimeType"] == FOLDER for n, f in present.items()):
            stats["versions_present"] += 1
            continue
        have = [int(m.group(1)) for n in present if (m := re.fullmatch(re.escape(stem) + r"-v(\d+)\.[A-Za-z0-9]+", n))]
        version = max(have + [next_free.get((folder, stem), 1) - 1]) + 1     # the next free Drive number
        next_free[(folder, stem)] = version + 1
        payload = _entry_bytes(e)
        if not any(n.rsplit(".", 1)[0] == e["id"] for n, _ in payload if "/" not in n):
            continue                               # no figure file to upload
        stats["versions_new"] += 1
        folder_id = drive.ensure_folder(area_ids[area], folder, existing=existing[area], dry_run=dry_run)
        if folder not in existing[area]:
            stats["folders_created"] += 1
            existing[area][folder] = {"id": folder_id, "name": folder, "mimeType": FOLDER}
            plan.append(f"{area}/{folder}/  (new folder)")
        subs: dict[str, dict[str, Any]] = {}
        sub_ids: dict[str, str] = {}
        files, code, data = [], [], []
        uploads: list[tuple[str, str, bytes]] = []          # (sub or "", name, bytes)
        for name, blob in payload:
            vname = _versioned(name, stem, e["id"], version)
            sub, base = (vname.split("/", 1) if "/" in vname else ("", vname))
            if sub and sub not in subs:
                sid = present[sub]["id"] if sub in present else None
                subs[sub] = drive.list_children(sid) if sid and not sid.startswith("dry-run:") else {}
            here = subs[sub] if sub else present
            if sub == "data" and base in here:
                if here[base].get("md5Checksum") == hashlib.md5(blob).hexdigest():
                    data.append((vname, hashlib.sha256(blob).hexdigest()))
                    stats["files_skipped"] += 1
                    continue
                q = Path(base)                       # changed data never replaces: a new name
                base = f"{q.stem}-v{version}{q.suffix}"
                vname = f"data/{base}"
            if base in here:
                stats["files_skipped"] += 1
                continue
            uploads.append((sub, base, blob))
            if sub == "code":
                code.append(vname)
            elif sub == "data":
                data.append((vname, hashlib.sha256(blob).hexdigest()))
            elif base != "figure.yaml":
                files.append(base)
        uploads.append(("", f"{stem}-v{version}.yaml", _record(e, stem, version, f"{area}/{folder}", files, code, data,
                                                               catalog_version=catalog_version)))
        if version != catalog_version:
            plan.append(f"   ({e['id']}: catalog version {catalog_version} -> Drive version {version})")
        for sub, base, blob in uploads:
            target = folder_id
            if sub:
                if sub not in sub_ids:
                    sub_ids[sub] = drive.ensure_folder(folder_id, sub, existing=present, dry_run=dry_run)
                target = sub_ids[sub]
            drive.upload(target, base, blob, _MIME.get(Path(base).suffix.lower(), "application/octet-stream"), dry_run=dry_run)
            plan.append(f"{area}/{folder}/{sub + '/' if sub else ''}{base}")
            stats["files_uploaded"] += 1
            stats["bytes"] += len(blob)
    # dated index, one per area, never overwritten
    for area, parent in area_ids.items():
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
        plan.append(f"{area}/{name}")
    stats["dry_run"] = dry_run
    stats["plan"] = plan
    return stats
