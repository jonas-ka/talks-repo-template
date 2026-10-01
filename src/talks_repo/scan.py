"""Wide scan for the plotting code behind catalog figures.

Inputs: notebooks/scripts found anywhere (local disk, iCloud, Google Drive) and copied
read-only into work/scan/<origin>/...; the catalog with the original filenames of its
figures (work/scan/catalog-figure-names.json).

Two ways to link a source to a catalog figure:
  1. a plot stored in a notebook's output cells matches the figure by perceptual hash
  2. a savefig() filename in the code matches the figure's original filename
Output: review/scan-matches.csv and work/scan/matches.json.
"""

import csv
import io
import json
import re
from pathlib import Path
from typing import Any

from talks_repo import REPO_ROOT, REVIEW_DIR, WORK_DIR
from talks_repo.extract import hamming
from talks_repo.sources import code_text, notebook_outputs

SCAN_DIR = WORK_DIR / "scan"
_GENERIC = re.compile(r"^(image\d*|pasted-image.*|slide\d+_img\d+|img\d*|picture ?\d*|unnamed.*|fig(ure)?[-_ ]?\d*|plot\d*|untitled\d*)$", re.I)
_SAVE = re.compile(r"savefig\(\s*(?:r|f)?['\"]([^'\"]+)['\"]")
_SAVE_VAR = re.compile(r"savefig\(\s*([A-Za-z_]\w*)")


def _norm(stem: str) -> str:
    s = stem.lower()
    s = re.sub(r"\.[a-z0-9]+$", "", s)
    s = re.sub(r"-\d{4,6}$", "", s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def catalog_names() -> dict[str, str]:
    names = json.loads((SCAN_DIR / "catalog-figure-names.json").read_text())
    return {_norm(k): v for k, v in names.items() if not _GENERIC.match(k)}


def catalog_hashes() -> list[tuple[str, str]]:
    import yaml

    idx = {im["id"]: im for im in json.loads((WORK_DIR / "extract" / "images.json").read_text())["images"]}
    out = []
    for e in yaml.safe_load((REPO_ROOT / "assets" / "catalog.yaml").read_text()):
        if e.get("kind") in ("plot", "schematic", "table") and e.get("image_id") in idx and idx[e["image_id"]].get("phash"):
            out.append((e["id"], idx[e["image_id"]]["phash"]))
    return out


def save_stems(text: str) -> set[str]:
    stems = {Path(m).name for m in _SAVE.findall(text)}
    # savefig(var) where var = '...' or f'...' assigned earlier
    for var in _SAVE_VAR.findall(text):
        for m in re.finditer(rf"^\s*{re.escape(var)}\s*=\s*(?:r|f)?['\"]([^'\"]+)['\"]", text, re.M):
            stems.add(Path(m.group(1)).name)
    return {_norm(s) for s in stems if s}


def scan_sources(origins: dict[str, Path]) -> list[dict[str, Any]]:
    """origins: label -> directory holding copied sources (paths inside mirror the origin)."""
    import imagehash
    from PIL import Image

    names = catalog_names()
    hashes = catalog_hashes()
    rows: list[dict[str, Any]] = []
    for label, root in origins.items():
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in (".ipynb", ".py") or ".ipynb_checkpoints" in path.parts:
                continue
            rel = path.relative_to(root).as_posix()
            text, kind = code_text(path)
            if kind == "broken" or not text:
                continue
            # 1. output plots by hash
            if kind == "ipynb":
                for k, data in enumerate(notebook_outputs(path), 1):
                    try:
                        h = str(imagehash.phash(Image.open(io.BytesIO(data)).convert("RGB"), hash_size=16))
                    except Exception:  # noqa: BLE001
                        continue
                    best = min(((hamming(h, ph), cid) for cid, ph in hashes), default=None)
                    if best and best[0] <= 14:
                        rows.append({"origin": label, "source": rel, "method": "output-hash", "detail": f"output #{k}",
                                     "catalog_id": best[1], "score": best[0]})
            # 2. savefig names
            for stem in save_stems(text):
                if stem in names:
                    rows.append({"origin": label, "source": rel, "method": "savefig-name", "detail": stem,
                                 "catalog_id": names[stem], "score": 0})
                else:
                    from rapidfuzz import fuzz

                    best = max(((fuzz.ratio(stem, n), n) for n in names), default=(0, ""))
                    if best[0] >= 92 and len(stem) >= 8:
                        rows.append({"origin": label, "source": rel, "method": "savefig-name~", "detail": f"{stem} ~ {best[1]}",
                                     "catalog_id": names[best[1]], "score": round(100 - best[0])})
    # de-duplicate (source, catalog_id)
    seen: set[tuple[str, str, str]] = set()
    unique = []
    for r in sorted(rows, key=lambda r: (r["score"], r["source"])):
        key = (r["origin"], r["source"], r["catalog_id"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    REVIEW_DIR.mkdir(exist_ok=True)
    with (REVIEW_DIR / "scan-matches.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["origin", "source", "method", "detail", "catalog_id", "score"])
        w.writeheader()
        w.writerows(unique)
    (SCAN_DIR / "matches.json").write_text(json.dumps(unique, indent=1))
    return unique


# --------------------------------------------------------------------------- publish matched sources

def _origin_path(origin: str, rel: str) -> str:
    """Human-readable location of a scanned source."""
    if origin == "local":
        return str(Path.home() / rel)
    return f"Google Drive: {rel}"


_IMPORT = re.compile(r"^\s*(?:from\s+([A-Za-z_]\w*)\s+import|import\s+([A-Za-z_]\w*))", re.M)


def _sibling_modules(text: str, dirs: list[Path]) -> list[Path]:
    """Local helper modules imported by the code (x.py next to it)."""
    out = []
    for m in _IMPORT.finditer(text):
        name = m.group(1) or m.group(2)
        for d in dirs:
            cand = d / f"{name}.py"
            if cand.is_file():
                out.append(cand)
                break
    return out


def _find_nearby(name: str, dirs: list[Path], depth: int = 3) -> Path | None:
    """A file by basename in any of the source's folders or their subfolders (read-only)."""
    for d in dirs:
        for pattern in ("*/" * k + name for k in range(depth + 1)):
            for hit in d.glob(pattern):
                if hit.is_file():
                    return hit
    return None


def _local_data(source_file: Path, text: str, other_dirs: list[Path] | None = None) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Data files referenced by a local notebook/script, resolved on disk (read-only):
    relative to the file, then relative to every other place the same file was found,
    then by basename in those folders' subtrees (old absolute paths, other cwd)."""
    from talks_repo.sources import _output_strings, file_references

    dirs = [source_file.parent, *(other_dirs or [])]
    outputs = _output_strings(text)
    data, rewrites = [], {}
    seen: set[str] = set()
    for mod in _sibling_modules(text, dirs):
        dest = f"code/{mod.name}"  # next to the code, so `import x` keeps working
        if dest not in seen:
            data.append({"local": mod, "dest": dest, "source_path": str(mod)})
            seen.add(dest)
    for r in file_references(text):
        ref = r["ref"]
        if r["is_output"] or ref in outputs or "*" in ref or "{" in ref:
            continue
        cand = None
        for d in dirs:
            c = Path(ref) if ref.startswith("/") else d / ref
            if c.exists():
                cand = c
                break
        if cand is None:
            cand = _find_nearby(Path(ref).name, dirs)
            if cand is None:
                continue
        try:
            if cand.is_file() and cand.stat().st_size <= 50_000_000:
                bare = "/" not in ref.strip("./")
                # a bare filename may be joined to a directory variable in the code: stage it
                # next to the code unchanged (and under data/ on the drive) instead of rewriting
                dest = f"data/{cand.name}"
                if dest not in seen:
                    data.append({"local": cand, "dest": dest, "source_path": str(cand), "bare": bare})
                    seen.add(dest)
                if ref != dest and not bare:
                    rewrites[ref] = dest
            elif cand.is_dir():
                for f in sorted(cand.iterdir()):
                    if f.is_file() and f.stat().st_size <= 50_000_000 and not f.name.startswith("."):
                        dest = f"data/{cand.name}/{f.name}"
                        if dest not in seen:
                            data.append({"local": f, "dest": dest, "source_path": str(f)})
                            seen.add(dest)
                rewrites[ref] = f"data/{cand.name}" + ("/" if ref.endswith("/") else "")
        except OSError:
            continue
    return data, rewrites


def _drive_data(rel: str, text: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Data files referenced by a Drive notebook/script: siblings in its Drive folder."""
    from talks_repo.sources import Resolver, _drive, _output_strings, file_references

    cands = {c["path"]: c for c in json.loads((SCAN_DIR / "drive-candidates.json").read_text())}
    rec = cands.get(rel)
    if rec is None:
        return [], {}
    resolver = Resolver(_drive())
    siblings = {f["name"]: f for f in resolver.folder_files((rec.get("parents") or [""])[0])} if rec.get("parents") else {}
    outputs = _output_strings(text)
    data, rewrites = [], {}
    FOLDER = "application/vnd.google-apps.folder"
    folder_id = (rec.get("parents") or [""])[0]
    all_siblings = {f["name"]: f for f in resolver.folder_files(folder_id)} if folder_id else {}
    sub_folders = {}
    if folder_id:
        from talks_repo.sources import _execute
        r_ = _execute(resolver.drive.files().list(q=f"'{folder_id}' in parents and mimeType = '{FOLDER}' and trashed=false",
                                                  fields="files(id,name)", pageSize=200, includeItemsFromAllDrives=True, supportsAllDrives=True))
        sub_folders = {f["name"]: f for f in r_.get("files", [])}
    for m in _IMPORT.finditer(text):
        name = (m.group(1) or m.group(2)) + ".py"
        if name in all_siblings:
            data.append({"src": all_siblings[name], "dest": f"code/{name}", "source_path": f"Google Drive: {str(Path(rel).parent)}/{name}"})

    def add_folder(folder_rec, dest_dir, source_prefix):
        for f in resolver.folder_files(folder_rec["id"]):
            data.append({"src": f, "dest": f"{dest_dir}/{f['name']}", "source_path": f"{source_prefix}/{f['name']}"})

    for r in file_references(text):
        ref = r["ref"]
        if r["is_output"] or ref in outputs or "*" in ref or "{" in ref:
            continue
        name = Path(ref).name
        if r["kind"] == "colab-drive":
            dp = r["drive_path"].rstrip("/")
            hit = resolver.resolve(dp)
            if hit is None:
                continue
            if hit["mimeType"] == FOLDER:
                add_folder(hit, f"data/{hit['name']}", f"Google Drive: {dp}")
                rewrites[ref] = f"data/{hit['name']}" + ("/" if ref.endswith("/") else "")
            else:
                data.append({"src": hit, "dest": f"data/{hit['name']}", "source_path": f"Google Drive: {dp}"})
                rewrites[ref] = f"data/{hit['name']}"
        elif name in all_siblings and "/" not in ref.strip("./"):
            data.append({"src": all_siblings[name], "dest": f"data/{name}", "source_path": f"Google Drive: {str(Path(rel).parent)}/{name}", "bare": True})
        else:
            parts = [p for p in Path(ref).parts if p not in (".", "..")]
            if parts and parts[0] in sub_folders:
                sub = sub_folders[parts[0]]
                files = {f["name"]: f for f in resolver.folder_files(sub["id"])}
                if len(parts) == 1:
                    add_folder(sub, f"data/{sub['name']}", f"Google Drive: {str(Path(rel).parent)}/{sub['name']}")
                    rewrites[ref] = f"data/{sub['name']}" + ("/" if ref.endswith("/") else "")
                elif parts[-1] in files:
                    data.append({"src": files[parts[-1]], "dest": f"data/{sub['name']}/{parts[-1]}",
                                 "source_path": f"Google Drive: {str(Path(rel).parent)}/{sub['name']}/{parts[-1]}"})
                    rewrites[ref] = f"data/{sub['name']}/{parts[-1]}"
    return data, rewrites


def publish_matches(run: bool = True, timeout: int = 900, dry_run: bool = False) -> dict[str, Any]:
    import hashlib
    import shutil

    import yaml

    from talks_repo.drive_sync import Drive, _MIME
    from talks_repo.sources import SRC_DIR, _drive, _prepare_notebook, download, rewrite_code

    matches = json.loads((SCAN_DIR / "matches.json").read_text())
    cat = {e["id"]: e for e in yaml.safe_load((REPO_ROOT / "assets" / "catalog.yaml").read_text())}
    origins = {"drive": SCAN_DIR / "drive", "local": SCAN_DIR / "local"}

    # one entry per distinct source file content; remember every location it was found at
    by_hash: dict[str, dict[str, Any]] = {}
    for m in matches:
        path = origins[m["origin"]] / m["source"]
        if not path.exists():
            continue
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        entry = by_hash.setdefault(h, {"paths": [], "figures": {}, "primary": None})
        loc = (m["origin"], m["source"])
        if loc not in entry["paths"]:
            entry["paths"].append(loc)
        entry["figures"].setdefault(m["catalog_id"], []).append({"method": m["method"], "detail": m["detail"], "score": m["score"]})
    order = {"local": 0, "drive": 1}
    for entry in by_hash.values():
        entry["primary"] = sorted(entry["paths"], key=lambda p: (order[p[0]], "CloudStorage" in p[1], p[1]))[0]

    d = Drive()
    drive_api = _drive()
    figures_root = d.top_folder("Figures")
    top = d.list_children(figures_root)
    stats = {"sources": len(by_hash), "figure_folders": 0, "files": 0, "skipped": 0, "runs_ok": 0, "runs_failed": 0, "exports": 0}
    report = []

    for h, entry in by_hash.items():
        origin, rel = entry["primary"]
        src_file = origins[origin] / rel
        text, kind = code_text(src_file)
        if origin == "local":
            others = [Path.home() / r_ for o_, r_ in entry["paths"] if o_ == "local" and r_ != rel]
            data, rewrites = _local_data(Path.home() / rel, text, other_dirs=[p_.parent for p_ in others])
        else:
            data, rewrites = _drive_data(rel, text)
        code_bytes = rewrite_code(src_file, kind, rewrites, _origin_path(origin, rel))

        # headless run once per source; exports keyed by stem
        exports: dict[str, Path] = {}
        run_status = "not run"
        if run and kind in ("ipynb", "py"):
            work = SCAN_DIR / "run" / h[:12]
            if work.exists():
                shutil.rmtree(work)
            work.mkdir(parents=True)
            for df in data:
                dest = work / (Path(df["dest"]).name if (df["dest"].startswith("code/") or df.get("bare")) else df["dest"])
                dest.parent.mkdir(parents=True, exist_ok=True)
                if "local" in df:
                    dest.write_bytes(df["local"].read_bytes())
                else:
                    got = download(drive_api, df["src"]["id"], SRC_DIR / "_data" / df["src"]["id"] / df["src"]["name"], df["src"].get("mimeType"))
                    if got:
                        dest.write_bytes(got.read_bytes())
            try:
                import nbformat
                from nbclient import NotebookClient

                nb = _prepare_notebook(src_file, kind, rewrites)
                NotebookClient(nb, timeout=timeout, kernel_name="talks-repo", resources={"metadata": {"path": str(work)}}).execute()
                run_status = "ok"
                stats["runs_ok"] += 1
            except Exception as exc:  # noqa: BLE001
                lines = [l for l in str(exc).strip().splitlines() if l.strip() and not set(l.strip()) <= set("-")]
                run_status = "error: " + (lines[-1] if lines else type(exc).__name__)[:200]
                stats["runs_failed"] += 1
            for f in sorted((work / "exports").glob("*")) if (work / "exports").exists() else []:
                exports[f.stem] = f

        for cid, hows in entry["figures"].items():
            e = cat.get(cid)
            if e is None:
                continue
            existed = cid in top
            fid = d.ensure_folder(figures_root, cid, existing=top, dry_run=dry_run)
            top.setdefault(cid, {"id": fid, "name": cid, "mimeType": "application/vnd.google-apps.folder"})
            present = d.list_children(fid) if (existed and not dry_run) else {}
            if not existed:
                stats["figure_folders"] += 1

            def put(parent: str, name: str, payload: bytes, listing: dict[str, Any]) -> None:
                if name in listing:
                    stats["skipped"] += 1
                    return
                d.upload(parent, name, payload, _MIME.get(Path(name).suffix.lower(), "application/octet-stream"), dry_run=dry_run)
                listing[name] = {"id": "new"}
                stats["files"] += 1

            # the reference figure as used in the talks (from the catalog)
            for key in ("file", "svg"):
                if e.get(key) and (REPO_ROOT / "assets" / e[key]).exists():
                    p = REPO_ROOT / "assets" / e[key]
                    put(fid, f"{cid}-as-used{p.suffix}", p.read_bytes(), present)
            # exports of the run: the matching stem, else everything
            wanted = {_norm(hw["detail"].split(" ~ ")[0]) for hw in hows if hw["method"].startswith("savefig")}
            chosen = [p for stem, p in exports.items() if _norm(stem) in wanted] or list(exports.values())
            n_exp = 0
            for p in chosen:
                for ext in (".svg", ".pdf", ".png"):
                    q = p.with_suffix(ext)
                    if q.exists():
                        put(fid, q.name, q.read_bytes(), present)
                        n_exp += 1
            stats["exports"] += n_exp
            code_dir = d.ensure_folder(fid, "code", existing=present, dry_run=dry_run)
            present.setdefault("code", {"id": code_dir})
            put(code_dir, src_file.name, code_bytes, d.list_children(code_dir) if (existed and not dry_run) else {})
            data_meta = []
            if data:
                data_dir = d.ensure_folder(fid, "data", existing=present, dry_run=dry_run)
                present.setdefault("data", {"id": data_dir})
                dl = d.list_children(data_dir) if (existed and not dry_run) else {}
                sub_cache: dict[str, tuple[str, dict[str, Any]]] = {}
                code_listing = d.list_children(code_dir) if (existed and not dry_run) else {}
                for df in data:
                    parts = Path(df["dest"]).parts[1:]  # strip 'data/' or 'code/'
                    parent, listing = data_dir, dl
                    if df["dest"].startswith("code/"):
                        parent, listing = code_dir, code_listing
                    if len(parts) > 1:
                        if parts[0] not in sub_cache:
                            sid = d.ensure_folder(data_dir, parts[0], existing=dl, dry_run=dry_run)
                            sub_cache[parts[0]] = (sid, d.list_children(sid) if (existed and not dry_run) else {})
                        parent, listing = sub_cache[parts[0]]
                    if "local" in df:
                        payload = df["local"].read_bytes()
                    else:
                        got = download(drive_api, df["src"]["id"], SRC_DIR / "_data" / df["src"]["id"] / df["src"]["name"], df["src"].get("mimeType"))
                        if got is None:
                            continue
                        payload = got.read_bytes()
                    put(parent, parts[-1], payload, listing)
                    data_meta.append({"file": df["dest"], "source_path": df["source_path"]})
            meta = {
                "catalog_id": cid,
                "kind": e.get("kind"),
                "as_used_in_talks": {"first_used": e.get("first_used"), "last_used": e.get("last_used"), "uses": e.get("uses")},
                "code": {"file": f"code/{src_file.name}", "source_path": _origin_path(origin, rel),
                         "also_found_at": [_origin_path(o, r) for o, r in entry["paths"] if (o, r) != (origin, rel)] or None,
                         "paths_rewritten": rewrites or None, "match": hows},
                "data": data_meta or None,
                "run": {"status": run_status, "exports": [p.name for p in chosen] if exports else None,
                        "how": "talks scan publish: headless matplotlib run, SVG + PDF + PNG 300 dpi"},
                "alt": None, "caption": None, "note": "alt text and caption to be written by the author",
            }
            import time as _time
            yaml_name = "figure.yaml" if "figure.yaml" not in present else f"figure-update-{_time.strftime('%Y-%m-%d')}.yaml"
            put(fid, yaml_name, yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).encode(), present)
            report.append({"catalog_id": cid, "source": _origin_path(origin, rel), "run": run_status, "exports": n_exp, "data": len(data_meta)})
    (SCAN_DIR / "publish-report.json").write_text(json.dumps(report, indent=1))
    return stats
