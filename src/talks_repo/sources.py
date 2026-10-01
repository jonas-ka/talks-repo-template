"""Figure sources: notebooks and Python scripts scattered over the author's Drive.

    talks sources inventory   walk the source roots on Drive (API), download every
                              .ipynb / .py (cached in work/sources/<root>/...)
    talks sources analyze     find the data files each one reads, resolve them on
                              Drive, detect figure output -> review/sources-references.csv
    talks sources copy        (after review) copy code + data to the shared drive with
                              paths rewritten, append-only
    talks sources run         execute self-contained notebooks headless and export every
                              figure as SVG + PDF + 300 dpi PNG

Roots (My Drive): Colab Notebooks, Code/Colab Notebooks, articles/_jonas-author.
Nothing in the roots is ever modified.
"""

import io
import json
import re
import time
from pathlib import Path
from typing import Any, Iterator

from talks_repo import REPO_ROOT, REVIEW_DIR, WORK_DIR

SRC_DIR = WORK_DIR / "sources"
INVENTORY = SRC_DIR / "inventory.json"
ROOTS = {
    "colab": ["Colab Notebooks"],
    "code-colab": ["Code", "Colab Notebooks"],
    "articles": ["articles", "_jonas-author"],
}
FOLDER = "application/vnd.google-apps.folder"
COLAB = "application/vnd.google.colaboratory"
CODE_EXT = (".ipynb", ".py")
DATA_EXT = (".csv", ".tsv", ".txt", ".dat", ".npy", ".npz", ".h5", ".hdf5", ".hdf", ".xlsx", ".xls", ".json",
            ".pkl", ".pickle", ".root", ".fits", ".parquet", ".mat", ".yaml", ".yml", ".asc", ".lst", ".tof",
            ".mpa", ".mcs", ".spe", ".chn", ".png", ".jpg", ".jpeg", ".pdf", ".svg", ".gif", ".tif", ".tiff",
            ".sav", ".npy", ".feather", ".xml", ".ini", ".cfg", ".log", ".out", ".dta", ".bin", ".zip",
            ".otf", ".ttf", ".woff", ".woff2", ".mplstyle", ".sty")
_MAX_DOWNLOAD = 50_000_000


# --------------------------------------------------------------------------- Drive helpers


def _drive():
    from googleapiclient.discovery import build
    from talks_repo import gslides

    return build("drive", "v3", credentials=gslides.credentials(), cache_discovery=False)


def _execute(request, tries: int = 6):
    """Drive calls with retries on timeouts and 5xx (the articles tree is deep)."""
    for attempt in range(tries):
        try:
            return request.execute(num_retries=2)
        except Exception as exc:  # noqa: BLE001
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)


def find_folder(drive, parts: list[str], parent: str = "root") -> str | None:
    for name in parts:
        safe = name.replace("'", "\\'")
        r = _execute(drive.files().list(q=f"'{parent}' in parents and name = '{safe}' and mimeType = '{FOLDER}' and trashed=false",
                                        fields="files(id,name)", pageSize=5))["files"]
        if not r:
            return None
        parent = r[0]["id"]
    return parent


def walk(drive, folder_id: str, rel: str = "") -> Iterator[dict[str, Any]]:
    token = None
    while True:
        r = _execute(drive.files().list(q=f"'{folder_id}' in parents and trashed=false", pageSize=1000, pageToken=token,
                                        fields="nextPageToken, files(id,name,mimeType,size,modifiedTime)"))
        for f in r.get("files", []):
            path = f"{rel}/{f['name']}" if rel else f["name"]
            if f["mimeType"] == FOLDER:
                yield {**f, "path": path, "folder_id": folder_id}
                yield from walk(drive, f["id"], path)
            else:
                yield {**f, "path": path, "folder_id": folder_id}
        token = r.get("nextPageToken")
        if not token:
            return


_EXPORTABLE = {"application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
               "application/vnd.google-apps.document": ("text/plain", ".txt")}


def download(drive, file_id: str, dest: Path, mime: str | None = None) -> Path | None:
    """Download a file's bytes; Google-native Sheets/Docs are exported (CSV/TXT), other
    native types (Forms, Sites, ...) are skipped and return None."""
    from googleapiclient.http import MediaIoBaseDownload

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    if mime and mime.startswith("application/vnd.google-apps"):
        if mime not in _EXPORTABLE:
            return None
        export_mime, ext = _EXPORTABLE[mime]
        dest = dest.with_suffix(ext)
        if dest.exists():
            return dest
    for attempt in range(4):
        try:
            if mime in _EXPORTABLE:
                req = drive.files().export_media(fileId=file_id, mimeType=_EXPORTABLE[mime][0])
            else:
                req = drive.files().get_media(fileId=file_id)
            buf = io.BytesIO()
            dl = MediaIoBaseDownload(buf, req)
            done = False
            while not done:
                _, done = dl.next_chunk(num_retries=2)
            dest.write_bytes(buf.getvalue())
            return dest
        except Exception:  # noqa: BLE001
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    return dest


# --------------------------------------------------------------------------- inventory


def is_code(f: dict[str, Any]) -> bool:
    return f["name"].lower().endswith(CODE_EXT) or f["mimeType"] == COLAB


def inventory(roots: list[str] | None = None) -> dict[str, Any]:
    drive = _drive()
    inv = json.loads(INVENTORY.read_text()) if INVENTORY.exists() else {}
    for key, parts in ROOTS.items():
        if roots and key not in roots:
            continue
        if key in inv and inv[key].get("complete"):
            continue
        fid = find_folder(drive, parts)
        files = list(walk(drive, fid)) if fid else []
        code = [f for f in files if is_code(f)]
        for c in code:
            if int(c.get("size") or 0) <= _MAX_DOWNLOAD:
                download(drive, c["id"], SRC_DIR / key / c["path"])
        inv[key] = {"root_id": fid, "root": "/".join(parts), "files": files, "code": code, "complete": True}
        INVENTORY.write_text(json.dumps(inv, indent=1))
    return inv


# --------------------------------------------------------------------------- analysis


_STR = re.compile(r"""(?:r|f|rb|b)?(['"])((?:(?!\1).){2,300})\1""")
_EXT_RE = re.compile(r"\.(" + "|".join(e.lstrip(".") for e in DATA_EXT) + r")$", re.I)
_READ_CALLS = re.compile(r"(read_csv|read_excel|read_table|read_hdf|read_json|read_pickle|read_parquet|loadtxt|genfromtxt|"
                         r"np\.load|open\(|h5py\.File|uproot\.open|fits\.open|imread|Image\.open|pd\.read_|scipy\.io\.loadmat|glob\.glob)")
_FIG_CALLS = re.compile(r"(savefig|plt\.show|\.plot\(|plt\.figure|subplots\(|px\.|go\.Figure|sns\.|bokeh|hist\(|imshow|errorbar\()")
_COLAB = re.compile(r"google\.colab|drive\.mount|/content/drive")
_COLAB_PATH = re.compile(r"/content/(?:drive/)?(?:MyDrive|My Drive)/([^'\"\n]+)")
_PIP = re.compile(r"^\s*[!%]pip install (.+)$", re.M)


def code_text(path: Path) -> tuple[str, str]:
    """(source text, kind) for a .py or .ipynb file; notebook code cells joined."""
    if path.suffix == ".py":
        return path.read_text(encoding="utf-8", errors="replace"), "py"
    try:
        nb = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return "", "broken"
    cells = []
    for c in nb.get("cells", []):
        if c.get("cell_type") == "code":
            src = c.get("source", "")
            cells.append("".join(src) if isinstance(src, list) else src)
    return "\n".join(cells), "ipynb"


def notebook_outputs(path: Path) -> list[bytes]:
    """PNG images stored in a notebook's output cells (rendered plots)."""
    import base64

    try:
        nb = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    out = []
    for c in nb.get("cells", []):
        for o in c.get("outputs", []) or []:
            data = o.get("data", {})
            for mime in ("image/png", "image/jpeg"):
                if mime in data:
                    b = data[mime]
                    b = "".join(b) if isinstance(b, list) else b
                    try:
                        out.append(base64.b64decode(b))
                    except Exception:  # noqa: BLE001
                        pass
    return out


def file_references(text: str) -> list[dict[str, Any]]:
    """String literals that look like data/image files, with a guess of how they are used."""
    refs: dict[str, dict[str, Any]] = {}
    for m in _STR.finditer(text):
        s = m.group(2).strip()
        if "\n" in s or len(s) > 260:
            continue
        colab = _COLAB_PATH.search(s)
        if _EXT_RE.search(s) or colab or s.startswith(("/content", "./", "../", "data/")):
            if s.startswith(("http://", "https://")):
                continue
            kind = "colab-drive" if colab else ("absolute" if s.startswith("/") else "relative")
            refs.setdefault(s, {"ref": s, "kind": kind, "drive_path": colab.group(1) if colab else None,
                                "is_output": False})
    # references that appear as savefig targets are outputs, not inputs
    for m in re.finditer(r"savefig\(\s*(?:r|f)?['\"]([^'\"]+)['\"]", text):
        if m.group(1) in refs:
            refs[m.group(1)]["is_output"] = True
    return list(refs.values())


def analyze() -> list[dict[str, Any]]:
    inv = json.loads(INVENTORY.read_text())
    rows: list[dict[str, Any]] = []
    for key, root in inv.items():
        by_folder: dict[str, set[str]] = {}
        by_path: dict[str, dict[str, Any]] = {}
        for f in root["files"]:
            by_folder.setdefault(f["folder_id"], set()).add(f["name"])
            by_path[f["path"].lower()] = f
        for c in root["code"]:
            local = SRC_DIR / key / c["path"]
            if not local.exists():
                continue
            text, kind = code_text(local)
            refs = file_references(text)
            found, missing, outputs = [], [], []
            siblings = by_folder.get(c["folder_id"], set())
            for r in refs:
                if r["is_output"]:
                    outputs.append(r["ref"])
                    continue
                name = Path(r["ref"]).name
                if r["kind"] == "colab-drive":
                    dp = r["drive_path"].rstrip("/")
                    # the Colab path is relative to My Drive; our roots are subtrees of it
                    hit = next((f for p, f in by_path.items() if dp.lower().endswith(p) or p.endswith(dp.lower())), None)
                    (found if hit else missing).append(r["ref"])
                elif name in siblings or Path(r["ref"]).as_posix().lower() in by_path:
                    found.append(r["ref"])
                elif "*" in r["ref"] or "{" in r["ref"]:
                    found.append(r["ref"] + " (pattern)")
                else:
                    missing.append(r["ref"])
            n_out_imgs = len(notebook_outputs(local)) if kind == "ipynb" else 0
            rows.append({
                "root": key, "path": c["path"], "kind": kind, "size_kb": round(int(c.get("size") or 0) / 1e3),
                "modified": c.get("modifiedTime", "")[:10],
                "produces_figures": bool(_FIG_CALLS.search(text)), "savefig": text.count("savefig("),
                "embedded_plots": n_out_imgs, "colab_specific": bool(_COLAB.search(text)),
                "pip_installs": "; ".join(_PIP.findall(text))[:120],
                "reads": len(found) + len(missing), "found": len(found), "missing": len(missing),
                "found_refs": " | ".join(found)[:400], "missing_refs": " | ".join(missing)[:400],
                "output_refs": " | ".join(outputs)[:200],
            })
    rows.sort(key=lambda r: (-r["produces_figures"], r["missing"], -r["embedded_plots"]))
    REVIEW_DIR.mkdir(exist_ok=True)
    import csv

    with (REVIEW_DIR / "sources-references.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (SRC_DIR / "analysis.json").write_text(json.dumps(rows, indent=1))
    return rows


# --------------------------------------------------------------------------- copy (append-only)

SKIP_DIRS = (".ipynb_checkpoints",)
COURSEWORK = ("ML/",)   # lecture examples and homework: not lab figures; copied only with --include-coursework


def _rewrite(text: str, mapping: dict[str, str]) -> str:
    """Replace every mapped path once, longest keys first, in a single pass so that a
    replacement is never rewritten again by a shorter key."""
    if not mapping:
        return text
    keys = sorted(mapping, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(k) for k in keys))
    return pattern.sub(lambda m: mapping[m.group(0)], text)


_MOUNTS = {"/content", "/content/drive", "/content/drive/My Drive", "/content/drive/MyDrive", "/content/drive/Shareddrives"}
_OUT_CALLS = re.compile(r"(savefig|to_csv|to_excel|to_pickle|np\.save|savetxt|write_image|imwrite|makedirs|mkdir)\s*\(")


class Resolver:
    """Resolve a Colab-style Drive path anywhere on Drive (My Drive or a shared drive)."""

    def __init__(self, drive) -> None:
        self.drive = drive
        self.cache: dict[str, dict[str, Any] | None] = {}
        self.shared: dict[str, str] | None = None

    def _shared_drive_id(self, name: str) -> str | None:
        if self.shared is None:
            r = _execute(self.drive.drives().list(pageSize=100))
            self.shared = {d["name"].lower(): d["id"] for d in r.get("drives", [])}
        return self.shared.get(name.lower())

    def resolve(self, drive_path: str) -> dict[str, Any] | None:
        """Path relative to My Drive (or 'Shareddrives/<drive>/...') -> file/folder record or None."""
        key = drive_path.strip("/")
        if key in self.cache:
            return self.cache[key]
        parts = [p for p in key.split("/") if p]
        parent = "root"
        if parts and parts[0].lower() in ("shareddrives", "shared drives"):
            did = self._shared_drive_id(parts[1]) if len(parts) > 1 else None
            if not did:
                self.cache[key] = None
                return None
            parent, parts = did, parts[2:]
        rec = {"id": parent, "name": parts[-1] if parts else "root", "mimeType": FOLDER}
        for part in parts:
            safe = part.replace("'", "\\'")
            r = _execute(self.drive.files().list(q=f"'{parent}' in parents and name = '{safe}' and trashed=false",
                                                 fields="files(id,name,mimeType,size)", pageSize=5,
                                                 includeItemsFromAllDrives=True, supportsAllDrives=True))["files"]
            if not r:
                self.cache[key] = None
                return None
            rec = r[0]
            parent = rec["id"]
        self.cache[key] = rec
        return rec

    def folder_files(self, folder_id: str) -> list[dict[str, Any]]:
        r = _execute(self.drive.files().list(q=f"'{folder_id}' in parents and trashed=false", pageSize=200,
                                             fields="files(id,name,mimeType,size)",
                                             includeItemsFromAllDrives=True, supportsAllDrives=True))
        return [f for f in r.get("files", []) if f["mimeType"] != FOLDER and int(f.get("size") or 0) <= _MAX_DOWNLOAD]


def _output_strings(text: str) -> set[str]:
    """String literals that are only ever used as output targets (savefig dirs, csv dumps)."""
    outputs: set[str] = set()
    assigned: dict[str, str] = {}
    for m in re.finditer(r"^\s*([A-Za-z_]\w*)\s*=\s*(?:r|f)?(['\"])((?:(?!\2).)+)\2\s*$", text, re.M):
        assigned.setdefault(m.group(1), m.group(3))
    for var, value in assigned.items():
        uses = [m.start() for m in re.finditer(rf"\b{re.escape(var)}\b", text)]
        if not uses:
            continue
        out_use = any(_OUT_CALLS.search(text[max(0, u - 80):u + 200]) for u in uses[1:])
        in_use = any(_READ_CALLS.search(text[max(0, u - 120):u + 120]) for u in uses[1:])
        if out_use and not in_use:
            outputs.add(value)
    for m in re.finditer(r"(?:savefig|to_csv|to_excel|np\.save|savetxt)\(\s*(?:r|f)?['\"]([^'\"]+)['\"]", text):
        outputs.add(m.group(1))
    return outputs


def plan_copy(include_coursework: bool = False) -> list[dict[str, Any]]:
    """For every notebook/script: destination folder, data files/folders to fetch, path rewrites."""
    inv = json.loads(INVENTORY.read_text())
    resolver = Resolver(_drive())
    plans: list[dict[str, Any]] = []
    for key, root in inv.items():
        by_folder: dict[str, dict[str, dict[str, Any]]] = {}
        for f in root["files"]:
            by_folder.setdefault(f["folder_id"], {})[f["name"]] = f
        for c in root["code"]:
            if any(s in c["path"] for s in SKIP_DIRS):
                continue
            if not include_coursework and any(c["path"].startswith(p) for p in COURSEWORK):
                continue
            local = SRC_DIR / key / c["path"]
            if not local.exists():
                continue
            text, kind = code_text(local)
            if kind == "broken":
                continue
            siblings = by_folder.get(c["folder_id"], {})
            outputs = _output_strings(text)
            data_files: list[dict[str, Any]] = []
            rewrites: dict[str, str] = {}
            missing: list[str] = []
            seen_dest: set[str] = set()

            def add(rec: dict[str, Any], dest: str) -> None:
                if dest not in seen_dest:
                    data_files.append({"src": rec, "dest": dest})
                    seen_dest.add(dest)

            for r in file_references(text):
                ref = r["ref"]
                if r["is_output"] or ref in outputs or ref.rstrip("/") in _MOUNTS:
                    continue
                name = Path(ref).name
                if r["kind"] == "colab-drive":
                    dp = r["drive_path"].rstrip("/")
                    if "{" in dp or "*" in dp:
                        dp = str(Path(dp).parent)   # pattern: take the folder
                    rec = resolver.resolve(dp)
                    if rec is None:
                        missing.append(ref)
                    elif rec["mimeType"] == FOLDER:
                        for f in resolver.folder_files(rec["id"]):
                            add(f, f"data/{rec['name']}/{f['name']}")
                        rewrites[ref] = f"data/{rec['name']}/" if ref.endswith("/") else f"data/{rec['name']}"
                    else:
                        add(rec, f"data/{rec['name']}")
                        rewrites[ref] = f"data/{rec['name']}"
                elif name in siblings and siblings[name]["mimeType"] != FOLDER:
                    add(siblings[name], name)
                    if ref != name:
                        rewrites[ref] = name
                elif "*" in ref or "{" in ref:
                    continue
                elif r["kind"] == "relative":
                    parts = [p for p in Path(ref).parts if p not in (".", "..")]
                    if parts and parts[0] in siblings and siblings[parts[0]]["mimeType"] == FOLDER:
                        sub = siblings[parts[0]]
                        for f in resolver.folder_files(sub["id"]):
                            if len(parts) == 1 or f["name"] == parts[-1]:
                                add(f, f"{sub['name']}/{f['name']}")
                    else:
                        missing.append(ref)
                else:
                    missing.append(ref)
            dest_dir = f"_sources/{key}/{Path(c['path']).parent.as_posix()}".rstrip("/.")
            plans.append({"root": key, "path": c["path"], "kind": kind, "file_id": c["id"], "dest_dir": dest_dir,
                          "data_files": data_files, "rewrites": rewrites, "missing": missing,
                          "size_mb": round(sum(int(d["src"].get("size") or 0) for d in data_files) / 1e6, 1)})
    (SRC_DIR / "copy-plan.json").write_text(json.dumps(plans, indent=1))
    return plans


def rewrite_code(local: Path, kind: str, rewrites: dict[str, str], origin: str) -> bytes:
    """The copied code with data paths rewritten and a provenance header/cell."""
    header = (f"# Copied from Google Drive '{origin}' by talks-repo on {time.strftime('%Y-%m-%d')}.\n"
              f"# Data files were copied alongside; paths rewritten: {json.dumps(rewrites) if rewrites else 'none'}.\n"
              "# The original file was not modified.\n")
    if kind == "py":
        return (header + _rewrite(local.read_text(encoding='utf-8', errors='replace'), rewrites)).encode()
    nb = json.loads(local.read_text(encoding="utf-8", errors="replace"))
    for c in nb.get("cells", []):
        if c.get("cell_type") == "code":
            src = c.get("source", "")
            joined = "".join(src) if isinstance(src, list) else src
            c["source"] = _rewrite(joined, rewrites)
    nb.setdefault("cells", []).insert(0, {"cell_type": "markdown", "metadata": {}, "source": header.replace("# ", "")})
    return json.dumps(nb, indent=1, ensure_ascii=False).encode()


def copy_to_drive(plans: list[dict[str, Any]], dry_run: bool = False, limit: int | None = None) -> dict[str, int]:
    from talks_repo.drive_sync import Drive, _MIME

    drive_api = _drive()
    d = Drive()
    figures = d.top_folder("Figures")
    stats = {"code": 0, "data": 0, "skipped_existing": 0, "bytes": 0}
    folder_cache: dict[str, str] = {}
    listing_cache: dict[str, dict[str, Any]] = {}

    def ensure_path(rel: str) -> str:
        parent = figures
        acc = ""
        for part in [p for p in rel.split("/") if p]:
            acc = f"{acc}/{part}"
            if acc in folder_cache:
                parent = folder_cache[acc]
                continue
            if parent not in listing_cache:
                listing_cache[parent] = d.list_children(parent) if not dry_run else {}
            fid = d.ensure_folder(parent, part, existing=listing_cache[parent], dry_run=dry_run)
            listing_cache[parent].setdefault(part, {"id": fid, "name": part, "mimeType": FOLDER})
            folder_cache[acc] = fid
            parent = fid
        return parent

    for n, p in enumerate(plans):
        if limit and n >= limit:
            break
        folder = ensure_path(p["dest_dir"])
        if folder not in listing_cache:
            listing_cache[folder] = d.list_children(folder) if not dry_run else {}
        present = listing_cache[folder]
        local = SRC_DIR / p["root"] / p["path"]
        name = Path(p["path"]).name
        if name in present:
            stats["skipped_existing"] += 1
        else:
            data = rewrite_code(local, p["kind"], p["rewrites"], f"My Drive/{json.loads(INVENTORY.read_text())[p['root']]['root']}/{p['path']}")
            d.upload(folder, name, data, "application/json" if p["kind"] == "ipynb" else "text/x-python", dry_run=dry_run)
            present[name] = {"id": "new", "name": name, "mimeType": "file"}
            stats["code"] += 1
            stats["bytes"] += len(data)
        for df in p["data_files"]:
            target_folder = folder
            dest_name = df["dest"]
            if "/" in dest_name:
                sub, dest_name = dest_name.split("/", 1)
                target_folder = ensure_path(f"{p['dest_dir']}/{sub}")
                if target_folder not in listing_cache:
                    listing_cache[target_folder] = d.list_children(target_folder) if not dry_run else {}
            tp = listing_cache.setdefault(target_folder, {})
            if dest_name in tp:
                stats["skipped_existing"] += 1
                continue
            if int(df["src"].get("size") or 0) > _MAX_DOWNLOAD:
                continue
            if not dry_run:
                tmp = download(drive_api, df["src"]["id"], SRC_DIR / "_data" / df["src"]["id"] / df["src"]["name"], df["src"].get("mimeType"))
                if tmp is None:
                    stats.setdefault("skipped_native", 0)
                    stats["skipped_native"] += 1
                    continue
                if tmp.suffix != Path(dest_name).suffix:
                    dest_name = str(Path(dest_name).with_suffix(tmp.suffix))
                d.upload(target_folder, dest_name, tmp.read_bytes(), _MIME.get(Path(dest_name).suffix.lower(), "application/octet-stream"))
                stats["bytes"] += tmp.stat().st_size
            tp[dest_name] = {"id": "new", "name": dest_name, "mimeType": "file"}
            stats["data"] += 1
    return stats


# --------------------------------------------------------------------------- run + export

RUN_DIR = SRC_DIR / "run"
_PRELUDE = r'''
# --- injected by talks-repo: headless run, every figure also saved as SVG + PDF + 300 dpi PNG
import sys, types, os
try:
    import google as _g            # the real namespace package (google.auth etc. keep working)
except ImportError:
    _g = types.ModuleType("google"); sys.modules["google"] = _g
_c = types.ModuleType("google.colab"); _d = types.ModuleType("google.colab.drive")
_d.mount = lambda *a, **k: None; _c.drive = _d; _c.files = types.SimpleNamespace(download=lambda *a, **k: None, upload=lambda *a, **k: {})
_c.auth = types.SimpleNamespace(authenticate_user=lambda *a, **k: None); _c.output = types.SimpleNamespace(clear=lambda *a, **k: None)
_g.colab = _c; sys.modules["google.colab"] = _c; sys.modules["google.colab.drive"] = _d
try:  # scipy >= 1.12 removed scipy.misc.derivative; old notebooks still import it
    import scipy.misc as _sm
except Exception:
    _sm = types.ModuleType("scipy.misc"); sys.modules["scipy.misc"] = _sm
    import scipy as _scipy; _scipy.misc = _sm
if not hasattr(_sm, "derivative"):
    def _derivative(func, x0, dx=1.0, n=1, args=(), order=3):
        if n == 1: return (func(x0 + dx, *args) - func(x0 - dx, *args)) / (2 * dx)
        if n == 2: return (func(x0 + dx, *args) - 2 * func(x0, *args) + func(x0 - dx, *args)) / dx**2
        raise NotImplementedError("derivative shim supports n=1,2")
    _sm.derivative = _derivative
import matplotlib; matplotlib.use("Agg")
matplotlib.rcParams["text.usetex"] = False   # no TeX installation here; mathtext instead
_orig_rc_update = matplotlib.rcParams.update
def _rc_update(*a, **k):
    _orig_rc_update(*a, **k); matplotlib.rcParams["text.usetex"] = False
matplotlib.rcParams.update = _rc_update
import matplotlib.text as _mtext   # plt.rc('text', usetex=True) and per-Text usetex: force off
_mtext.Text.get_usetex = lambda self: False
_orig_set_usetex = _mtext.Text.set_usetex
_mtext.Text.set_usetex = lambda self, v=None: _orig_set_usetex(self, False)
try:  # scipy >= 1.17 removed sph_harm; old notebooks still call it
    import scipy.special as _sp
    if not hasattr(_sp, "sph_harm") and hasattr(_sp, "sph_harm_y"):
        _sp.sph_harm = lambda m, n, theta, phi, *a, **k: _sp.sph_harm_y(n, m, phi, theta, *a, **k)
except Exception: pass
import matplotlib.pyplot as _plt
from matplotlib.figure import Figure as _Fig
_EXPORTS = os.path.join(os.getcwd(), "exports"); os.makedirs(_EXPORTS, exist_ok=True)
# Colab notebooks write under /content: redirect those paths into the working directory
import builtins as _bi
_CONTENT = os.path.join(os.getcwd(), "content")
def _redir(p):
    return os.path.join(_CONTENT, str(p)[len("/content/"):]) if isinstance(p, (str, os.PathLike)) and str(p).startswith("/content/") else p
_orig_open, _orig_makedirs, _orig_exists = _bi.open, os.makedirs, os.path.exists
def _open(file, *a, **k):
    f = _redir(file)
    mode = a[0] if a else k.get("mode", "r")
    if isinstance(f, (str, os.PathLike)) and any(m in str(mode) for m in "wax") and os.path.dirname(str(f)):
        os.makedirs(os.path.dirname(str(f)), exist_ok=True)   # scripts expect their output folders to exist
    return _orig_open(f, *a, **k)
matplotlib.use = lambda *a, **k: None   # scripts that force Qt/TkAgg keep the headless backend
try:
    import pandas as _pd
    _orig_read_csv = _pd.read_csv
    def _read_csv(*a, **k):
        if k.pop("delim_whitespace", False): k.setdefault("sep", r"\s+")
        return _orig_read_csv(*a, **k)
    _pd.read_csv = _read_csv
    _orig_to_csv = _pd.DataFrame.to_csv
    def _to_csv(self, path_or_buf=None, *a, **k):
        if isinstance(path_or_buf, (str, os.PathLike)) and os.path.dirname(str(path_or_buf)):
            os.makedirs(os.path.dirname(str(path_or_buf)), exist_ok=True)
        return _orig_to_csv(self, path_or_buf, *a, **k)
    _pd.DataFrame.to_csv = _to_csv
except Exception: pass
_bi.open = _open
os.makedirs = lambda p, *a, **k: _orig_makedirs(_redir(p), *a, **k)
_orig_savefig = _Fig.savefig
_n = [0]
def _export(fig, stem):
    for ext, kw in ((".svg", {}), (".pdf", {}), (".png", {"dpi": 300})):
        try: _orig_savefig(fig, os.path.join(_EXPORTS, stem + ext), bbox_inches="tight", **kw)
        except Exception as e: print("export failed", stem, ext, e)
def _patched_savefig(self, fname, *a, **k):
    stem = os.path.splitext(os.path.basename(str(fname)))[0] if isinstance(fname, (str, os.PathLike)) else f"figure-{_n[0]}"
    _n[0] += 1
    _export(self, stem)
    try: return _orig_savefig(self, fname, *a, **k)
    except Exception as e: print("original savefig skipped:", e)
_Fig.savefig = _patched_savefig
_plt.show = lambda *a, **k: None
def _export_open_figures():
    for num in _plt.get_fignums():
        _export(_plt.figure(num), f"figure-{num}")
'''
_EPILOGUE = "\n_export_open_figures()\n"


def _prepare_notebook(local: Path, kind: str, rewrites: dict[str, str]) -> Any:
    """Notebook object ready to execute: prelude cell, shell/magic lines neutralised, epilogue."""
    import nbformat

    if kind == "py":
        code = _rewrite(local.read_text(encoding="utf-8", errors="replace"), rewrites)
        nb = nbformat.v4.new_notebook()
        nb.cells = [nbformat.v4.new_code_cell(code)]
    else:
        nb = nbformat.reads(local.read_text(encoding="utf-8", errors="replace"), as_version=4)
    for c in nb.cells:
        if c.cell_type != "code":
            continue
        lines = []
        for line in _rewrite(c.source, rewrites).splitlines():
            s = line.strip()
            if s.startswith(("!", "%")) and not s.startswith("%matplotlib"):
                lines.append("# [skipped by talks-repo] " + line)
            elif s.startswith("%matplotlib"):
                lines.append("# " + line)
            else:
                lines.append(line)
        c.source = "\n".join(lines)
        c.outputs = []
        c.execution_count = None
    nb.cells.insert(0, nbformat.v4.new_code_cell(_PRELUDE))
    nb.cells.append(nbformat.v4.new_code_cell(_EPILOGUE))
    nb.metadata["kernelspec"] = {"name": "talks-repo", "display_name": "talks-repo (uv)", "language": "python"}
    return nb


def run_sources(plans: list[dict[str, Any]], only: set[str] | None = None, timeout: int = 300) -> list[dict[str, Any]]:
    """Execute figure-producing, self-contained notebooks/scripts; collect exports/."""
    import nbformat
    from nbclient import NotebookClient

    drive = _drive()
    analysis = {r["path"]: r for r in json.loads((SRC_DIR / "analysis.json").read_text())}
    results = []
    for p in plans:
        a = analysis.get(p["path"], {})
        if only and p["path"] not in only:
            continue
        if not a.get("produces_figures") or p["missing"]:
            continue
        local = SRC_DIR / p["root"] / p["path"]
        text, kind = code_text(local)
        if kind == "ipynb":
            lang = json.loads(local.read_text(encoding="utf-8", errors="replace")).get("metadata", {}).get("kernelspec", {}).get("language", "python")
            if "python" not in str(lang).lower():
                results.append({"path": p["path"], "status": f"skipped ({lang})"})
                continue
        work = RUN_DIR / p["root"] / Path(p["path"]).with_suffix("")
        if work.exists():
            import shutil
            shutil.rmtree(work)
        work.mkdir(parents=True)
        for df in p["data_files"]:
            src = download(drive, df["src"]["id"], SRC_DIR / "_data" / df["src"]["id"] / df["src"]["name"], df["src"].get("mimeType"))
            if src is None:
                continue
            dest = work / df["dest"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())
        nb = _prepare_notebook(local, kind, p["rewrites"])
        status, error = "ok", ""
        try:
            NotebookClient(nb, timeout=timeout, kernel_name="talks-repo", resources={"metadata": {"path": str(work)}},
                           allow_errors=False).execute()
        except Exception as exc:  # noqa: BLE001
            status = "error"
            lines = [l for l in str(exc).strip().splitlines() if l.strip() and not set(l.strip()) <= set("-")]
            error = (lines[-1] if lines else type(exc).__name__)[:300]
        nbformat.write(nb, work / "executed.ipynb")
        exports = sorted(f.name for f in (work / "exports").glob("*")) if (work / "exports").exists() else []
        results.append({"path": p["path"], "root": p["root"], "dest_dir": p["dest_dir"], "status": status,
                        "error": error, "exports": exports, "work": str(work.relative_to(REPO_ROOT))})
    # merge with earlier runs so partial (--only) runs do not drop other results
    path = SRC_DIR / "run-results.json"
    previous = {r["path"]: r for r in json.loads(path.read_text())} if path.exists() else {}
    for r in results:
        previous[r["path"]] = r
    merged = list(previous.values())
    path.write_text(json.dumps(merged, indent=1))
    return merged


def upload_exports(results: list[dict[str, Any]], dry_run: bool = False) -> dict[str, int]:
    """exports/ of each executed notebook -> Figures/_sources/<dest_dir>/exports/<stem>/ (append-only)."""
    from talks_repo.drive_sync import Drive, _MIME

    d = Drive()
    figures = d.top_folder("Figures")
    stats = {"uploaded": 0, "skipped": 0}
    cache: dict[str, dict[str, Any]] = {}

    def ensure(rel: str) -> str:
        parent = figures
        for part in [x for x in rel.split("/") if x]:
            if parent not in cache:
                cache[parent] = d.list_children(parent)
            fid = d.ensure_folder(parent, part, existing=cache[parent], dry_run=dry_run)
            cache[parent].setdefault(part, {"id": fid, "name": part, "mimeType": FOLDER})
            parent = fid
        return parent

    for r in results:
        if not r.get("exports"):
            continue
        stem = Path(r["path"]).stem
        folder = ensure(f"{r['dest_dir']}/exports/{stem}")
        if folder not in cache:
            cache[folder] = d.list_children(folder) if not dry_run else {}
        for name in r["exports"]:
            if name in cache[folder]:
                stats["skipped"] += 1
                continue
            data = (REPO_ROOT / r["work"] / "exports" / name).read_bytes()
            d.upload(folder, name, data, _MIME.get(Path(name).suffix.lower(), "application/octet-stream"), dry_run=dry_run)
            cache[folder][name] = {"id": "new", "name": name, "mimeType": "file"}
            stats["uploaded"] += 1
    return stats


# --------------------------------------------------------------------------- flat publish

_SAFE = re.compile(r"[^A-Za-z0-9._+-]+")


def _safe_name(stem: str) -> str:
    return _SAFE.sub("-", stem).strip("-.") or "plot"


def plot_folders(results: list[dict[str, Any]], plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry per exported plot: folder name, files, the code that made it, its data."""
    import hashlib

    by_path = {p["path"]: p for p in plans}
    inv = json.loads(INVENTORY.read_text())
    used: dict[str, int] = {}
    seen_plots: set[str] = set()   # the same notebook exists in two roots: publish its plots once
    out = []
    order = {"articles": 0, "code-colab": 1, "colab": 2}
    results = sorted(results, key=lambda r: order.get(r.get("root", ""), 9))
    for r in results:
        if not r.get("exports"):
            continue
        p = by_path.get(r["path"])
        if p is None:
            continue
        work = REPO_ROOT / r["work"]
        stems = sorted({Path(f).stem for f in r["exports"]})
        script_stem = _safe_name(Path(r["path"]).stem)
        for stem in stems:
            png = work / "exports" / f"{stem}.png"   # PNG bytes are deterministic; SVG carries a timestamp
            digest = hashlib.sha256(png.read_bytes()).hexdigest() if png.exists() else None
            if digest and digest in seen_plots:
                continue
            if digest:
                seen_plots.add(digest)
            name = _safe_name(stem)
            if name.startswith("figure-"):
                name = f"{script_stem}-{name}"
            n = used.get(name, 0) + 1
            used[name] = n
            if n > 1:
                name = f"{name}-{n}"
            out.append({
                "folder": name,
                "plots": [f for f in r["exports"] if Path(f).stem == stem],
                "work": work,
                "plan": p,
                "code_source": f"My Drive/{inv[p['root']]['root']}/{p['path']}",
                "data_sources": sorted({f"My Drive/{inv[p['root']]['root']}/{str(Path(p['path']).parent)}" if "/" not in d["dest"] or d["dest"].startswith(Path(p["path"]).parent.name)
                                        else "(resolved from a Colab drive path, see data list)" for d in p["data_files"]}),
                "status": r["status"],
            })
    return out


def publish_plots(dry_run: bool = False) -> dict[str, int]:
    """Figures/<plot>/ = plot files + code/ + data/ + figure.yaml, append-only."""
    import yaml

    from talks_repo.drive_sync import Drive, _MIME

    results = json.loads((SRC_DIR / "run-results.json").read_text())
    plans = json.loads((SRC_DIR / "copy-plan.json").read_text())
    entries = plot_folders(results, plans)
    d = Drive()
    figures = d.top_folder("Figures")
    top = d.list_children(figures)
    drive_api = _drive()
    stats = {"folders": 0, "files": 0, "skipped": 0, "bytes": 0}
    for e in entries:
        p = e["plan"]
        existed = e["folder"] in top
        fid = d.ensure_folder(figures, e["folder"], existing=top, dry_run=dry_run)
        top.setdefault(e["folder"], {"id": fid, "name": e["folder"], "mimeType": FOLDER})
        present = d.list_children(fid) if (existed and not dry_run) else {}
        if not existed:
            stats["folders"] += 1

        def put(parent: str, name: str, data: bytes, listing: dict[str, Any]) -> None:
            if name in listing:
                stats["skipped"] += 1
                return
            d.upload(parent, name, data, _MIME.get(Path(name).suffix.lower(), "application/octet-stream"), dry_run=dry_run)
            listing[name] = {"id": "new", "name": name}
            stats["files"] += 1
            stats["bytes"] += len(data)

        for f in e["plots"]:
            put(fid, f, (e["work"] / "exports" / f).read_bytes(), present)
        code_dir = d.ensure_folder(fid, "code", existing=present, dry_run=dry_run)
        present.setdefault("code", {"id": code_dir, "name": "code", "mimeType": FOLDER})
        code_listing = d.list_children(code_dir) if (existed and not dry_run) else {}
        local = SRC_DIR / p["root"] / p["path"]
        _, kind = code_text(local)
        put(code_dir, Path(p["path"]).name, rewrite_code(local, kind, p["rewrites"], e["code_source"]), code_listing)
        data_entries = []
        if p["data_files"]:
            data_dir = d.ensure_folder(fid, "data", existing=present, dry_run=dry_run)
            present.setdefault("data", {"id": data_dir, "name": "data", "mimeType": FOLDER})
            data_listing = d.list_children(data_dir) if (existed and not dry_run) else {}
            for df in p["data_files"]:
                src = download(drive_api, df["src"]["id"], SRC_DIR / "_data" / df["src"]["id"] / df["src"]["name"], df["src"].get("mimeType"))
                if src is None:
                    continue
                dest_name = Path(df["dest"]).name if src.suffix == Path(df["dest"]).suffix else Path(df["dest"]).with_suffix(src.suffix).name
                put(data_dir, dest_name, src.read_bytes(), data_listing)
                data_entries.append({"file": f"data/{dest_name}", "source_id": df["src"]["id"], "source_name": df["src"]["name"]})
        meta = {
            "plot": e["folder"],
            "files": e["plots"],
            "code": {"file": f"code/{Path(p['path']).name}", "source": e["code_source"],
                     "paths_rewritten": p["rewrites"] or None,
                     "note": "data paths point to data/ (flattened); the original file on Drive is unmodified"},
            "data": data_entries or None,
            "generated": {"date": time.strftime("%Y-%m-%d"), "how": "talks sources run (headless, matplotlib Agg; SVG + PDF + PNG 300 dpi)",
                          "status": e["status"]},
            "alt": None,
            "caption": None,
            "note": "alt text and caption to be written by the author",
        }
        put(fid, "figure.yaml", yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).encode(), present)
    stats["plots"] = len(entries)
    return stats
