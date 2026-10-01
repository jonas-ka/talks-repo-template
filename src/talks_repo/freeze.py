"""Freeze a generated talk into a self-contained folder.

    talks freeze <slug>

Copies everything the deck depends on into talks/<slug>/ so it compiles on its own
(`typst compile --root talks/<slug> talks/<slug>/main.typ`) even if the catalog, the
theme, the blocks or the original files change later:

    assets/figures/<id>.<ext>   every catalog asset the deck uses; rasters scaled down
                                to MAX_SIDE px (photos JPEG, others PNG), SVGs as is
    assets/sources/<id>/        the figure's plotting code and data, when the catalog
                                entry has a `source_dir`
    assets/catalog.yaml         only the entries used, file paths pointing into the folder
    blocks/*.typ, themes/       the blocks used, the theme and its logos
    main.typ                    imports rewritten to the local copies
    freeze.yaml                 manifest: catalog ids, sha256 of each copied file, git commit
"""

import hashlib
import io
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from talks_repo import REPO_ROOT, manifest
from talks_repo.catalog import CATALOG, CATALOG_HEADER

MAX_SIDE = 1600
PHOTO_KINDS = {"photo"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _scaled_copy(src: Path, dst_dir: Path, entry_id: str, kind: str) -> Path:
    """Copy a figure file, downscaling rasters. SVG/PDF/TeX are copied unchanged."""
    ext = src.suffix.lower()
    if ext in (".svg", ".pdf", ".tex", ".gif"):
        dst = dst_dir / f"{entry_id}{ext}"
        shutil.copy2(src, dst)
        return dst
    from PIL import Image

    im = Image.open(src)
    im.load()
    if max(im.size) > MAX_SIDE:
        im.thumbnail((MAX_SIDE, MAX_SIDE))
    if kind in PHOTO_KINDS and im.mode in ("RGB", "L"):
        dst = dst_dir / f"{entry_id}.jpg"
        im.convert("RGB").save(dst, format="JPEG", quality=88, optimize=True)
    else:
        dst = dst_dir / f"{entry_id}.png"
        im.save(dst, format="PNG", optimize=True)
    return dst


def used_ids(main: Path, blocks: list[Path]) -> set[str]:
    ids: set[str] = set()
    for path in [main, *blocks]:
        text = path.read_text(encoding="utf-8")
        ids.update(re.findall(r'cat-(?:fig|eq)\("([^"]+)"', text))
        for m in re.finditer(r"^//\s*assets:\s*\[(.*)\]", text, re.M):
            ids.update(a.strip() for a in m.group(1).split(",") if a.strip())
    return ids


def freeze(slug: str) -> dict[str, Any]:
    tdir = REPO_ROOT / "talks" / slug
    main = tdir / "main.typ"
    if not main.exists():
        raise FileNotFoundError(f"{main} missing; run `talks generate {slug}` first")
    text = main.read_text(encoding="utf-8")
    block_files = [REPO_ROOT / "blocks" / Path(p).name for p in re.findall(r'#include "/blocks/([^"]+)"', text)]

    # 1. blocks and theme
    (tdir / "blocks").mkdir(exist_ok=True)
    for b in block_files:
        btext = b.read_text(encoding="utf-8").replace('#import "/themes/karthein.typ"', '#import "/themes/karthein.typ"')
        (tdir / "blocks" / b.name).write_text(btext, encoding="utf-8")
    theme_src = REPO_ROOT / "themes"
    theme_dst = tdir / "themes"
    theme_dst.mkdir(exist_ok=True)
    for f in ["karthein.typ", "palette.yaml", "README.md"]:
        shutil.copy2(theme_src / f, theme_dst / f)
    (theme_dst / "logos").mkdir(exist_ok=True)
    for f in (theme_src / "logos").iterdir():
        shutil.copy2(f, theme_dst / "logos" / f.name)

    # 2. assets used, scaled
    cat = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or []
    by_id = {e["id"]: e for e in cat}
    ids = used_ids(main, block_files)
    fig_dir = tdir / "assets" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    frozen_entries: list[dict[str, Any]] = []
    files: dict[str, str] = {}
    missing: list[str] = []
    for aid in sorted(ids):
        e = by_id.get(aid)
        if e is None:
            missing.append(aid)
            continue
        entry = dict(e)
        rel = e.get("svg") or e.get("file")
        if rel:
            src = REPO_ROOT / "assets" / rel
            if src.exists():
                dst = _scaled_copy(src, fig_dir, aid, e.get("kind", ""))
                entry["file"] = f"figures/{dst.name}"
                entry["svg"] = f"figures/{dst.name}" if dst.suffix == ".svg" else None
                files[f"assets/figures/{dst.name}"] = _sha(dst)
                if e.get("file") and e["file"].endswith(".pdf") and (REPO_ROOT / "assets" / e["file"]).exists():
                    pdf_dst = fig_dir / f"{aid}.pdf"
                    shutil.copy2(REPO_ROOT / "assets" / e["file"], pdf_dst)  # vector original alongside
                    files[f"assets/figures/{pdf_dst.name}"] = _sha(pdf_dst)
            else:
                missing.append(f"{aid} (file {rel} not found)")
        src_dir = e.get("source_dir")
        if src_dir and (REPO_ROOT / "assets" / src_dir).exists():
            dst = tdir / "assets" / "sources" / aid
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(REPO_ROOT / "assets" / src_dir, dst)
            entry["source_dir"] = f"sources/{aid}"
        frozen_entries.append(entry)
    manifest.save(tdir / "assets" / "catalog.yaml", frozen_entries, CATALOG_HEADER + "\nFROZEN COPY for this talk: only the entries used, files scaled for preservation.")

    # 3. main.typ keeps root-relative imports; they now resolve inside the talk folder.
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT).stdout.strip()
    (tdir / "freeze.yaml").write_text(yaml.safe_dump({
        "slug": slug, "frozen": datetime.now().isoformat(timespec="seconds"), "git_commit": commit,
        "blocks": [b.name for b in block_files], "assets": sorted(ids), "missing": missing, "files": files,
        "compile": f"typst compile --root talks/{slug} --pdf-standard ua-1 talks/{slug}/main.typ",
    }, sort_keys=False), encoding="utf-8")

    # 4. prove it: compile with the talk folder as root
    result = subprocess.run(
        ["typst", "compile", "--root", str(tdir), "--pdf-standard", "ua-1", str(main), str(tdir / "frozen.pdf")],
        capture_output=True, text=True, timeout=600, cwd=REPO_ROOT,
    )
    size = sum((tdir / p).stat().st_size for p in files) / 1e6
    return {"assets": len(frozen_entries), "missing": missing, "blocks": len(block_files), "files_mb": round(size, 1),
            "standalone_compile": result.returncode == 0, "error": result.stderr[:1500] if result.returncode else ""}
