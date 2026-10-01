"""Stage E: slide-level extraction from the archived decks.

Per talk, writes archive/<id>/extract.json (tracked; text only) describing every
slide: title, texts, speaker notes, pictures with hashes and positions, the
build-sequence group (the author's hand-made animations are consecutive near-identical
slides), and a native-shapes flag for figures drawn with shapes instead of images.

Image sources, best quality first:
  * Keynote package `Data/` entries (vector PDFs and full-size originals),
    mapped to slides by matching against the PPTX export's pictures.
  * PPTX pictures (ppt/media) with their slide numbers.
  * Google Slides API media (already per slide, from slides.json).

Thumbnails and copies of unique images go to work/extract/ (ignored, regenerable).
The global picture index across talks is work/extract/images.json; the review
sheet is review/stage-e-images.csv plus an HTML contact sheet.
"""

import hashlib
import io
import json
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from talks_repo import REPO_ROOT, REVIEW_DIR, WORK_DIR, resolve_ref

ARCHIVE_DIR = REPO_ROOT / "archive"
EXTRACT_DIR = WORK_DIR / "extract"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".tiff", ".tif", ".bmp", ".webp", ".pdf", ".svg", ".emf"}
_QUALITY = {".pdf": 0, ".svg": 0, ".emf": 1, ".tiff": 2, ".tif": 2, ".png": 3, ".webp": 4, ".bmp": 4,
            ".jpeg": 5, ".jpg": 5, ".gif": 6}
PHASH_SAME = 6       # hamming distance for "same picture" across talks (recrop/recompress)
KEYNOTE_MATCH = 24   # looser: a Keynote original vs. Keynote's own rasterised export of it
BUILD_MAX_REMOVED = 0.01  # a build step removes almost no ink (area fraction) ...
BUILD_MAX_ADDED = 0.30    # ... and adds at most this much
THUMB_PX = 320


@dataclass
class Picture:
    sha: str                      # sha256 of the bytes
    phash: str | None
    ext: str
    bytes: int
    width: int | None
    height: int | None
    origin: str                   # "pptx" | "keynote-data" | "gslides"
    name: str                     # media file name / Data entry / alt title
    slide: int | None = None
    bbox: list[float] | None = None   # [x, y, w, h] as fractions of the slide
    container: str = ""           # where the bytes live: "<path>::<entry>" or a file path


@dataclass
class Slide:
    index: int
    title: str | None
    texts: list[str]
    notes: str
    pictures: list[str]           # sha list, in z-order
    n_shapes: int = 0             # non-picture shapes (autoshapes, freeforms, lines)
    native_figure: bool = False   # many shapes, no pictures: drawn diagram to redraw
    thumb: str | None = None
    build_group: int | None = None
    build_stage: int | None = None
    build_final: bool = True
    pdf_text: str = ""


# --------------------------------------------------------------------------- hashing


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pil_image(data: bytes, ext: str):
    from PIL import Image

    if ext == ".pdf":
        import pymupdf

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.page_count == 0:
                return None
            pix = doc[0].get_pixmap(dpi=72, alpha=False)
            return Image.open(io.BytesIO(pix.tobytes("png")))
    if ext in (".svg", ".emf"):
        return None
    img = Image.open(io.BytesIO(data))
    img.load()
    if getattr(img, "n_frames", 1) > 1:
        img.seek(0)
    return img.convert("RGB")


def phash_of(data: bytes, ext: str) -> tuple[str | None, int | None, int | None]:
    import imagehash

    try:
        img = _pil_image(data, ext)
    except Exception:  # noqa: BLE001
        return None, None, None
    if img is None:
        return None, None, None
    return str(imagehash.phash(img, hash_size=16)), img.width, img.height


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


# --------------------------------------------------------------------------- PPTX


def _walk_shapes(shapes):
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk_shapes(shape.shapes)
        else:
            yield shape


def read_pptx(path: Path) -> tuple[list[Slide], list[Picture]]:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    prs = Presentation(str(path))
    sw, sh = prs.slide_width or 1, prs.slide_height or 1
    slides: list[Slide] = []
    pictures: list[Picture] = []
    seen: dict[str, Picture] = {}
    index = 0
    for slide in prs.slides:
        if slide._element.get("show") == "0":
            continue  # skipped in Keynote; the PDF export leaves these out too
        index += 1
        texts, pics, n_shapes = [], [], 0
        title = None
        try:
            if slide.shapes.title is not None and slide.shapes.title.has_text_frame:
                title = slide.shapes.title.text_frame.text.strip() or None
        except Exception:  # noqa: BLE001
            title = None
        for shape in _walk_shapes(slide.shapes):
            is_pic = shape.shape_type in (MSO_SHAPE_TYPE.PICTURE, MSO_SHAPE_TYPE.PLACEHOLDER) and hasattr(shape, "image")
            if is_pic:
                try:
                    blob = shape.image.blob
                    ext = "." + shape.image.ext.lower().replace("jpeg", "jpg")
                except Exception:  # noqa: BLE001
                    continue
                sha = sha256(blob)
                bbox = None
                if shape.left is not None and shape.width is not None:
                    bbox = [round(shape.left / sw, 3), round(shape.top / sh, 3),
                            round(shape.width / sw, 3), round(shape.height / sh, 3)]
                if sha not in seen:
                    ph, w, h = phash_of(blob, ext)
                    # The real zip entry (ppt/media/imageN.ext), not python-pptx's placeholder name.
                    rid = getattr(shape._element, "blip_rId", None)
                    partname = str(shape.part.related_part(rid).partname).lstrip("/") if rid else ""
                    seen[sha] = Picture(sha, ph, ext, len(blob), w, h, "pptx", Path(partname).name or "image",
                                        slide=index, bbox=bbox, container=f"{path}::{partname}")
                    pictures.append(seen[sha])
                pics.append(sha)
            else:
                if shape.has_text_frame and shape.text_frame.text.strip():
                    t = re.sub(r"\s+", " ", shape.text_frame.text).strip()
                    if t != title:
                        texts.append(t)
                if shape.shape_type not in (MSO_SHAPE_TYPE.TEXT_BOX, MSO_SHAPE_TYPE.PLACEHOLDER):
                    n_shapes += 1
        notes = ""
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        s = Slide(index, title, texts, notes, pics, n_shapes=n_shapes)
        s.native_figure = not pics and n_shapes >= 6
        slides.append(s)
    return slides, pictures


# --------------------------------------------------------------------------- Keynote package


def read_keynote_data(key_path: Path) -> list[Picture]:
    """Every media entry under Data/ in the .key package (zip or directory)."""
    out: list[Picture] = []
    if key_path.is_dir():
        entries = [(p.relative_to(key_path).as_posix(), p.read_bytes) for p in (key_path / "Data").rglob("*") if p.is_file()]
    else:
        zf = zipfile.ZipFile(key_path)
        entries = [(n, (lambda n=n: zf.read(n))) for n in zf.namelist() if n.startswith("Data/")]
    for name, reader in entries:
        ext = Path(name).suffix.lower()
        if ext not in IMAGE_EXT:
            continue
        data = reader()
        if len(data) < 2000:
            continue  # icons, bullets
        ph, w, h = phash_of(data, ext)
        out.append(Picture(sha256(data), ph, ext, len(data), w, h, "keynote-data",
                           Path(name).name, container=f"{key_path}::{name}"))
    return out


def map_keynote_to_slides(data_pics: list[Picture], pptx_pics: list[Picture], slides: list[Slide]) -> int:
    """Give Keynote originals the slide of the PPTX picture they match. Returns matches."""
    by_sha = {p.sha: p for p in pptx_pics}
    matched = 0
    for d in data_pics:
        target = by_sha.get(d.sha)
        if target is None and d.phash:
            best = min(((hamming(d.phash, p.phash), p) for p in pptx_pics if p.phash), key=lambda x: x[0], default=None)
            if best and best[0] <= KEYNOTE_MATCH:
                target = best[1]
        if target is not None:
            d.slide, d.bbox = target.slide, target.bbox
            matched += 1
            # The original replaces the export in the slide's picture list.
            for s in slides:
                s.pictures = [d.sha if sha == target.sha else sha for sha in s.pictures]
    return matched


# --------------------------------------------------------------------------- Google Slides


def read_gslides(talk_dir: Path) -> tuple[list[Slide], list[Picture]]:
    data = json.loads((talk_dir / "slides.json").read_text(encoding="utf-8"))
    slides, pictures = [], []
    seen: dict[str, Picture] = {}
    for s in data["slides"]:
        pics = []
        for img in s["images"]:
            if not img.get("file"):
                continue
            path = talk_dir / img["file"]
            blob = path.read_bytes()
            ext = path.suffix.lower()
            sha = sha256(blob)
            if sha not in seen:
                ph, w, h = phash_of(blob, ext)
                seen[sha] = Picture(sha, ph, ext, len(blob), w, h, "gslides",
                                    img.get("alt_title") or path.name, slide=s["index"], container=str(path))
                pictures.append(seen[sha])
            pics.append(sha)
        texts = list(s["texts"])
        title = texts[0] if texts else None
        slides.append(Slide(s["index"], title, texts[1:] if texts else [], s.get("notes", ""), pics))
    return slides, pictures


# --------------------------------------------------------------------------- PDF pass


def pdf_pass(pdf: Path, slides: list[Slide], thumb_dir: Path) -> list[float]:
    """Per-slide text and thumbnails from deck.pdf. Returns, for each page after the
    first, the fraction of pixels that changed relative to the previous page."""
    import numpy as np
    import pymupdf
    from PIL import Image

    thumb_dir.mkdir(parents=True, exist_ok=True)
    diffs: list[tuple[float, float]] = []  # (ink removed, ink added) as area fractions
    previous = None
    with pymupdf.open(pdf) as doc:
        for i, page in enumerate(doc, start=1):
            zoom = THUMB_PX / max(page.rect.width, 1)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            out = thumb_dir / f"slide{i:03d}.png"
            pix.save(out)
            gray = np.asarray(Image.open(out).convert("L"), dtype=np.int16)
            background = int(np.median(gray))
            ink = np.abs(gray - background) > 40
            if previous is not None and previous.shape == ink.shape:
                removed = float((previous & ~ink).mean())
                added = float((~previous & ink).mean())
                diffs.append((removed, added))
            elif previous is not None:
                diffs.append((1.0, 1.0))
            previous = ink
            if i - 1 < len(slides):
                slides[i - 1].thumb = str(out.relative_to(REPO_ROOT))
                slides[i - 1].pdf_text = re.sub(r"\s+", " ", page.get_text("text")).strip()[:2000]
    return diffs


def _is_build_step(a: Slide, b: Slide, diff: tuple[float, float]) -> bool:
    """b continues a's build if almost no ink vanished (additive change) and the
    title did not change (when both are known)."""
    removed, added = diff
    if a.title and b.title and a.title != b.title:
        return False
    return removed <= BUILD_MAX_REMOVED and added <= BUILD_MAX_ADDED


def mark_builds(slides: list[Slide], diffs: list[tuple[float, float]]) -> int:
    """Consecutive additive slides form one build group (the author's hand-made animations);
    the last slide is the final stage."""
    group = 0
    n = 0
    i = 0
    while i < len(slides):
        j = i
        while j + 1 < len(slides) and j < len(diffs) and _is_build_step(slides[j], slides[j + 1], diffs[j]):
            j += 1
        if j > i:
            group += 1
            for stage, k in enumerate(range(i, j + 1), start=1):
                slides[k].build_group, slides[k].build_stage, slides[k].build_final = group, stage, k == j
            n += 1
        i = j + 1
    return n


# --------------------------------------------------------------------------- per talk


def extract_talk(talk: dict[str, Any], force: bool = False) -> dict[str, Any] | None:
    talk_dir = ARCHIVE_DIR / talk["id"]
    out_path = talk_dir / "extract.json"
    if not (talk_dir / "manifest.yaml").exists():
        return None
    if out_path.exists() and not force:
        return json.loads(out_path.read_text(encoding="utf-8"))

    source = talk.get("source_file") or ""
    src_type = Path(source).suffix.lower()
    pictures: list[Picture] = []
    slides: list[Slide] = []
    steps: list[str] = []

    if src_type == ".gslides" and (talk_dir / "slides.json").exists():
        slides, pictures = read_gslides(talk_dir)
        steps.append(f"slides.json: {len(slides)} slides, {len(pictures)} unique pictures")
    elif (talk_dir / "deck.pptx").exists():
        slides, pictures = read_pptx(talk_dir / "deck.pptx")
        steps.append(f"deck.pptx: {len(slides)} slides, {len(pictures)} unique pictures")
        if src_type == ".key":
            data_pics = read_keynote_data(resolve_ref(source))
            matched = map_keynote_to_slides(data_pics, pictures, slides)
            steps.append(f"keynote Data/: {len(data_pics)} media entries, {matched} mapped to slides")
            pictures.extend(data_pics)

    pdf = talk_dir / "deck.pdf"
    if pdf.exists():
        if not slides:
            import pymupdf

            with pymupdf.open(pdf) as doc:
                slides = [Slide(i, None, [], "", []) for i in range(1, doc.page_count + 1)]
            steps.append("no editable source: slides from deck.pdf only")
        diffs = pdf_pass(pdf, slides, EXTRACT_DIR / talk["id"] / "thumbs")
        pages = len(diffs) + 1
        builds = mark_builds(slides, diffs)
        steps.append(f"deck.pdf: {pages} pages, {builds} build sequences")
        if pages != len(slides):
            steps.append(f"WARNING page count {pages} != slide count {len(slides)}")

    result = {
        "talk_id": talk["id"],
        "source_type": src_type or ".pdf",
        "steps": steps,
        "slides": [asdict(s) for s in slides],
        "pictures": [asdict(p) for p in pictures],
    }
    out_path.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return result


# --------------------------------------------------------------------------- global index


def _quality(p: dict[str, Any]) -> tuple[int, int]:
    return (_QUALITY.get(p["ext"], 9), -(p["bytes"] or 0))


def build_index(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Group pictures across talks: exact sha, then perceptual hash. One entry per unique image."""
    all_pics: list[dict[str, Any]] = []
    for r in results:
        for p in r["pictures"]:
            all_pics.append({**p, "talk_id": r["talk_id"]})
    # 1. exact duplicates
    by_sha: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in all_pics:
        by_sha[p["sha"]].append(p)
    reps = [sorted(v, key=_quality)[0] | {"members": v} for v in by_sha.values()]
    # 2. perceptual clusters (union-find over reps with phash)
    parent = list(range(len(reps)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    hashed = [(i, r["phash"]) for i, r in enumerate(reps) if r["phash"]]
    for a in range(len(hashed)):
        ia, ha = hashed[a]
        for b in range(a + 1, len(hashed)):
            ib, hb = hashed[b]
            if hamming(ha, hb) <= PHASH_SAME:
                parent[find(ia)] = find(ib)
    clusters: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for i, r in enumerate(reps):
        clusters[find(i)].append(r)

    images: list[dict[str, Any]] = []
    for members in clusters.values():
        best = sorted(members, key=_quality)[0]
        uses = sorted({(m2["talk_id"], m2["slide"]) for m in members for m2 in m["members"] if m2.get("slide")})
        talks = sorted({t for t, _ in uses})
        name_l = str(best["name"]).lower()
        hint = "equation" if name_l.startswith("equation-") else "logo" if "logo" in name_l else None
        images.append({
            "id": best["sha"][:12],
            "hint": hint,
            "ext": best["ext"],
            "bytes": best["bytes"],
            "width": best["width"],
            "height": best["height"],
            "origin": best["origin"],
            "name": best["name"],
            "container": best["container"],
            "vector": best["ext"] in (".pdf", ".svg", ".emf"),
            "n_variants": len(members),
            "variants": [m["sha"][:12] for m in members if m["sha"] != best["sha"]],
            "talks": talks,
            "uses": [f"{t}#{s}" for t, s in uses],
            "n_uses": len(uses),
            "phash": best["phash"],
        })
    images.sort(key=lambda im: (-im["n_uses"], im["id"]))
    return {"n_pictures": len(all_pics), "n_exact_unique": len(reps), "n_images": len(images), "images": images}


def write_thumbnails(index: dict[str, Any], limit_px: int = 256) -> int:
    """Small preview per unique image into work/extract/unique/ for the contact sheet."""
    from PIL import Image

    out_dir = EXTRACT_DIR / "unique"
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for im in index["images"]:
        target = out_dir / f"{im['id']}.png"
        im["thumb"] = str(target.relative_to(REPO_ROOT))
        if target.exists():
            continue
        try:
            data = read_container(im["container"])
            img = _pil_image(data, im["ext"])
            if img is None:
                continue
            img.thumbnail((limit_px, limit_px))
            img.save(target)
            n += 1
        except Exception:  # noqa: BLE001
            im["thumb"] = None
    return n


def read_container(container: str) -> bytes:
    if "::" in container:
        path, entry = container.split("::", 1)
        p = Path(path)
        if p.is_dir():
            return (p / entry).read_bytes()
        with zipfile.ZipFile(p) as zf:
            return zf.read(entry)
    return Path(container).read_bytes()


# --------------------------------------------------------------------------- review outputs


def write_review(index: dict[str, Any], results: list[dict[str, Any]]) -> list[str]:
    import csv

    import yaml

    REVIEW_DIR.mkdir(exist_ok=True)
    written = []
    classified_path = REVIEW_DIR / "stage-e" / "classified.yaml"
    classified: dict[str, Any] = {}
    if classified_path.exists():
        classified = yaml.safe_load(classified_path.read_text(encoding="utf-8")) or {}

    csv_path = REVIEW_DIR / "stage-e-images.csv"
    cols = ["id", "kind", "hint", "n_uses", "talks", "vector", "ext", "width", "height", "bytes", "origin",
            "name", "caption", "alt", "topics", "level", "latex", "confidence", "uses", "n_variants"]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for im in index["images"]:
            c = next((classified[k] for k in [im["id"], *im.get("variants", [])] if k in classified), {})
            w.writerow({**{k: im.get(k) for k in cols}, "talks": " ".join(im["talks"]), "uses": " ".join(im["uses"]),
                        "kind": c.get("kind", ""), "caption": c.get("caption", ""), "alt": c.get("alt", ""),
                        "topics": " ".join(c.get("topics") or []), "level": c.get("level", ""),
                        "latex": c.get("latex", ""), "confidence": c.get("confidence", "")})
    written.append(str(csv_path.relative_to(REPO_ROOT)))

    html = REVIEW_DIR / "stage-e-contact-sheet.html"
    by_kind: dict[str, list[str]] = defaultdict(list)
    for im in index["images"]:
        c = next((classified[k] for k in [im["id"], *im.get("variants", [])] if k in classified), {})
        thumb = f"../{im['thumb']}" if im.get("thumb") else ""
        badge = "VECTOR" if im["vector"] else im["ext"]
        cap = (f'<br><i>{c["caption"]}</i><br><small>{" ".join(c.get("topics") or [])} · {c.get("level", "")}</small>'
               if c.get("caption") else "")
        by_kind[c.get("kind", "unclassified")].append(
            f'<figure><img src="{thumb}" loading="lazy"><figcaption><b>{im["id"]}</b> {badge} '
            f'{im["width"]}x{im["height"]} · used {im["n_uses"]}x in {len(im["talks"])} talks{cap}<br>'
            f'<small>{im["name"]}</small><br><small>{" ".join(im["uses"][:6])}</small></figcaption></figure>'
        )
    rows = [f"<h2>{kind} ({len(items)})</h2><div class=grid>{''.join(items)}</div>"
            for kind, items in sorted(by_kind.items(), key=lambda kv: (kv[0] == "unclassified", kv[0]))]
    slides_html = []
    for r in results:
        cells = []
        for s in r["slides"]:
            tag = ""
            if s.get("build_group"):
                tag = f' <span class="b">build {s["build_group"]}.{s["build_stage"]}{"*" if s["build_final"] else ""}</span>'
            if s.get("native_figure"):
                tag += ' <span class="n">native shapes</span>'
            src = f"../{s['thumb']}" if s.get("thumb") else ""
            cells.append(f'<figure><img src="{src}" loading="lazy"><figcaption>{s["index"]}{tag}</figcaption></figure>')
        slides_html.append(f"<h2>{r['talk_id']}</h2><div class=grid>{''.join(cells)}</div>")
    html.write_text(
        "<!doctype html><meta charset=utf-8><title>Stage E contact sheet</title><style>"
        "body{font-family:system-ui;margin:16px} .grid{display:flex;flex-wrap:wrap;gap:8px}"
        "figure{margin:0;width:200px;font-size:11px} img{max-width:200px;max-height:160px;border:1px solid #ccc}"
        ".b{background:#ffe;padding:0 3px} .n{background:#fdd;padding:0 3px}</style>"
        f"<h1>Unique images ({index['n_images']})</h1>{''.join(rows)}"
        f"<h1>Slides</h1>{''.join(slides_html)}",
        encoding="utf-8",
    )
    written.append(str(html.relative_to(REPO_ROOT)))
    return written
