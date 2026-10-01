"""Stage F: equations to LaTeX, from the best source available.

Sources, in order of trust:
  1. keynote-iwa     LaTeX typed into Keynote's equation editor, read from the
                     Snappy-compressed protobuf index of the .key package and
                     mapped to visible slide numbers via the document's slide order
                     and the hidden-slide positions of the PPTX export.
  2. gslides-notes   LaTeX the author keeps in the speaker notes of Google Slides decks.
  3. claude-vision   the `latex` field of Stage E's classification for images of
                     kind "equation" (fallback; must be verified).

Every unique equation is rendered with Typst + mitex so the review sheet shows the
render next to the source crop (the image classified as an equation on the same
slide, when there is one). Results: assets/equations/<id>.tex (with provenance
header) and review/stage-f-equations.csv + .html.
"""

import hashlib
import json
import re
import subprocess
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import yaml

from talks_repo import REPO_ROOT, REVIEW_DIR, WORK_DIR, resolve_ref
from talks_repo.extract import ARCHIVE_DIR, EXTRACT_DIR, hamming

EQ_DIR = REPO_ROOT / "assets" / "equations"
RENDER_DIR = WORK_DIR / "equations"
MITEX = "@preview/mitex:0.2.7"
_TEX = re.compile(r"\\[A-Za-z]{2,}|[_^]\{")


# --------------------------------------------------------------------------- IWA / protobuf


def iwa_decompress(data: bytes) -> bytes:
    import cramjam

    out = bytearray()
    pos = 0
    while pos < len(data):
        n = int.from_bytes(data[pos + 1 : pos + 4], "little")
        out += bytes(cramjam.snappy.decompress_raw(data[pos + 4 : pos + 4 + n]))
        pos += 4 + n
    return bytes(out)


def _varint(buf: bytes, i: int) -> tuple[int, int]:
    v = shift = 0
    while i < len(buf):
        b = buf[i]
        i += 1
        v |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            return v, i
    raise ValueError("truncated varint")


def _fields(buf: bytes) -> Iterator[tuple[int, int, Any]]:
    i = 0
    while i < len(buf):
        tag, i = _varint(buf, i)
        fno, wt = tag >> 3, tag & 7
        if wt == 0:
            v, i = _varint(buf, i)
        elif wt == 1:
            v, i = buf[i : i + 8], i + 8
        elif wt == 2:
            n, i = _varint(buf, i)
            v, i = buf[i : i + n], i + n
            if len(v) != n:
                raise ValueError("truncated bytes")
        elif wt == 5:
            v, i = buf[i : i + 4], i + 4
        else:
            raise ValueError("bad wire type")
        yield fno, wt, v


def _strings(buf: bytes, depth: int = 0) -> Iterator[str]:
    try:
        items = list(_fields(buf))
    except Exception:  # noqa: BLE001
        return
    for _, wt, v in items:
        if wt != 2 or not v:
            continue
        try:
            s = v.decode("utf-8")
            if s.isprintable() and len(s) >= 2:
                yield s
        except UnicodeDecodeError:
            pass
        if depth < 8 and len(v) > 2:
            yield from _strings(v, depth + 1)


def _archives(buf: bytes) -> Iterator[bytes]:
    """IWA payload = repeated [len][ArchiveInfo][message bytes...]."""
    i = 0
    while i < len(buf):
        n, i = _varint(buf, i)
        info = buf[i : i + n]
        i += n
        for fno, wt, v in _fields(info):
            if fno == 2 and wt == 2:
                for f2, w2, v2 in _fields(v):
                    if f2 == 3 and w2 == 0:
                        yield buf[i : i + v2]
                        i += v2


def _encode_varint(v: int) -> bytes:
    b = bytearray()
    while True:
        x = v & 0x7F
        v >>= 7
        if v:
            b.append(x | 0x80)
        else:
            b.append(x)
            return bytes(b)


def keynote_equations(key_path: Path, pptx_path: Path) -> tuple[dict[int, list[str]], list[str]]:
    """LaTeX per visible slide index from a Keynote package. Returns (mapping, warnings)."""
    warnings: list[str] = []
    if key_path.is_dir():
        read = lambda n: (key_path / n).read_bytes()  # noqa: E731
        names = [p.relative_to(key_path).as_posix() for p in key_path.rglob("*.iwa")]
    else:
        zf = zipfile.ZipFile(key_path)
        read = zf.read
        names = zf.namelist()
    per_id: dict[int, list[str]] = {}
    ids: list[int] = []
    for n in names:
        m = re.match(r"Index/Slide-(\d+)\.iwa$", n)
        if not m:
            continue
        sid = int(m.group(1))
        ids.append(sid)
        found: set[str] = set()
        for msg in _archives(iwa_decompress(read(n))):
            for s in _strings(msg):
                if "\\" in s and _TEX.search(s):
                    found.add(s.strip())
        if found:
            per_id[sid] = sorted(found)
    if not per_id:
        return {}, warnings
    doc = iwa_decompress(read("Index/Document.iwa"))
    positions = {sid: doc.find(_encode_varint(sid)) for sid in ids}
    missing = [sid for sid, p in positions.items() if p < 0]
    if missing:
        warnings.append(f"{len(missing)} slide ids not found in Document.iwa")
    order = [sid for sid in sorted(ids, key=lambda s: positions[s]) if positions[sid] >= 0]

    hidden: set[int] = set()
    n_pptx = None
    if pptx_path.exists():
        from pptx import Presentation

        slides = list(Presentation(str(pptx_path)).slides)
        n_pptx = len(slides)
        hidden = {i for i, s in enumerate(slides, 1) if s._element.get("show") == "0"}
        if n_pptx != len(order):
            warnings.append(f"slide count mismatch: {len(order)} in package index vs {n_pptx} in pptx; mapping may be off by one")
    visible_of: dict[int, int] = {}
    vis = 0
    for pos in range(1, len(order) + 1):
        if pos not in hidden:
            vis += 1
            visible_of[pos] = vis
    out: dict[int, list[str]] = defaultdict(list)
    for sid, eqs in per_id.items():
        if sid not in order:
            continue
        pos = order.index(sid) + 1
        v = visible_of.get(pos)
        if v is None:
            continue  # on a skipped slide
        out[v].extend(eqs)
    return dict(out), warnings


# --------------------------------------------------------------------------- other sources


_NOTES_EQ = re.compile(r"\$\$(.+?)\$\$|\$(.+?)\$", re.S)


def notes_equations(notes: str) -> list[str]:
    """LaTeX in speaker notes: $...$ / $$...$$ spans, else whole lines with TeX commands."""
    if not notes or "\\" not in notes:
        return []
    found = [(a or b).strip() for a, b in _NOTES_EQ.findall(notes)]
    if found:
        return found
    return [line.strip() for line in notes.splitlines() if "\\" in line and _TEX.search(line)]


# --------------------------------------------------------------------------- collection


@dataclass
class Equation:
    latex: str
    id: str
    sources: list[dict[str, Any]] = field(default_factory=list)  # {source, talk, slide, image}
    render: str | None = None
    crop: str | None = None
    render_ok: bool = False
    verified_distance: int | None = None


def normalize(latex: str) -> str:
    s = latex.strip().strip("$").strip()
    s = re.sub(r"\\[>,;!:]", " ", s)          # thin spaces
    s = re.sub(r"\s+", " ", s)
    return s


def eq_id(latex: str) -> str:
    return hashlib.sha256(normalize(latex).encode()).hexdigest()[:10]


def collect(talks: list[dict[str, Any]]) -> tuple[dict[str, Equation], list[str]]:
    equations: dict[str, Equation] = {}
    log: list[str] = []
    classified = {}
    cpath = REVIEW_DIR / "stage-e" / "classified.yaml"
    if cpath.exists():
        classified = yaml.safe_load(cpath.read_text(encoding="utf-8")) or {}
    index = {}
    ipath = EXTRACT_DIR / "images.json"
    if ipath.exists():
        index = {im["id"]: im for im in json.loads(ipath.read_text(encoding="utf-8"))["images"]}

    def add(latex: str, source: str, talk: str, slide: int | None, image: str | None = None) -> None:
        if not latex or len(normalize(latex)) < 2:
            return
        key = eq_id(latex)
        eq = equations.setdefault(key, Equation(normalize(latex), key))
        eq.sources.append({"source": source, "talk": talk, "slide": slide, "image": image})

    for talk in talks:
        tdir = ARCHIVE_DIR / talk["id"]
        extract = tdir / "extract.json"
        if not extract.exists():
            continue
        ex = json.loads(extract.read_text(encoding="utf-8"))
        src = talk.get("source_file") or ""
        n_before = len(equations)
        if src.endswith(".key"):
            try:
                mapping, warnings = keynote_equations(resolve_ref(src), tdir / "deck.pptx")
            except Exception as exc:  # noqa: BLE001
                log.append(f"{talk['id']}: keynote parse failed: {type(exc).__name__}: {exc}")
                mapping, warnings = {}, []
            for w in warnings:
                log.append(f"{talk['id']}: {w}")
            for slide, eqs in mapping.items():
                for latex in eqs:
                    add(latex, "keynote-iwa", talk["id"], slide)
        for s in ex["slides"]:
            for latex in notes_equations(s.get("notes", "")):
                add(latex, "gslides-notes" if src.endswith(".gslides") else "notes", talk["id"], s["index"])
        log.append(f"{talk['id']}: {len(equations) - n_before} new equations from sources")

    # Vision fallback: equation images whose slide has no sourced equation yet.
    sourced_slides = {(s["talk"], s["slide"]) for eq in equations.values() for s in eq.sources}
    for image_id, c in classified.items():
        if c.get("kind") != "equation" or not c.get("latex") or image_id not in index:
            continue
        for use in index[image_id]["uses"]:
            talk_id, _, idx = use.rpartition("#")
            if (talk_id, int(idx)) in sourced_slides:
                continue
            add(c["latex"], "claude-vision", talk_id, int(idx), image_id)
    # Attach a source crop: an equation-classified image used on one of the equation's slides.
    slide_images: dict[tuple[str, int], list[str]] = defaultdict(list)
    for image_id, c in classified.items():
        if c.get("kind") == "equation" and image_id in index:
            for use in index[image_id]["uses"]:
                talk_id, _, idx = use.rpartition("#")
                slide_images[(talk_id, int(idx))].append(image_id)
    for eq in equations.values():
        for s in eq.sources:
            cands = [s["image"]] if s.get("image") else slide_images.get((s["talk"], s["slide"]), [])
            for cid in cands:
                thumb = index.get(cid, {}).get("thumb")
                if thumb:
                    eq.crop = thumb
                    break
            if eq.crop:
                break
    return equations, log


# --------------------------------------------------------------------------- render + verify


def render(eq: Equation) -> bool:
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    out = RENDER_DIR / f"{eq.id}.png"
    eq.render = str(out.relative_to(REPO_ROOT))
    if out.exists():
        eq.render_ok = True
        return True
    src = RENDER_DIR / f"{eq.id}.typ"
    body = eq.latex.replace("`", "\\`")
    src.write_text(
        f'#import "{MITEX}": mitex\n#set page(width: auto, height: auto, margin: 8pt)\n'
        f"#set text(size: 18pt)\n#mitex(`{body}`)\n",
        encoding="utf-8",
    )
    result = subprocess.run(["typst", "compile", "--format", "png", "--ppi", "160", str(src), str(out)],
                            capture_output=True, text=True, timeout=120)
    eq.render_ok = result.returncode == 0 and out.exists()
    if not eq.render_ok:
        (RENDER_DIR / f"{eq.id}.err").write_text(result.stderr[:2000])
    return eq.render_ok


def verify(eq: Equation) -> None:
    """Perceptual distance between the render and the source crop, when both exist."""
    if not (eq.render_ok and eq.crop):
        return
    import imagehash
    from PIL import Image

    try:
        a = imagehash.phash(Image.open(REPO_ROOT / eq.render).convert("L"), hash_size=16)
        b = imagehash.phash(Image.open(REPO_ROOT / eq.crop).convert("L"), hash_size=16)
        eq.verified_distance = int(a - b)
    except Exception:  # noqa: BLE001
        eq.verified_distance = None


# --------------------------------------------------------------------------- outputs


def write_assets(equations: dict[str, Equation]) -> int:
    EQ_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for eq in equations.values():
        path = EQ_DIR / f"{eq.id}.tex"
        if path.exists():
            continue
        lines = [f"% id: {eq.id}", f"% status: unreviewed", f"% render_ok: {eq.render_ok}"]
        for s in eq.sources:
            lines.append(f"% source: {s['source']}  talk: {s['talk']}  slide: {s['slide']}")
        path.write_text("\n".join(lines) + "\n" + eq.latex + "\n", encoding="utf-8")
        n += 1
    return n


def write_review(equations: dict[str, Equation], log: list[str]) -> list[str]:
    import csv

    REVIEW_DIR.mkdir(exist_ok=True)
    rows = sorted(equations.values(), key=lambda e: (e.render_ok, -(len(e.sources))))
    csv_path = REVIEW_DIR / "stage-f-equations.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "render_ok", "sources", "n_uses", "talks", "verified_distance", "latex"])
        w.writeheader()
        for eq in rows:
            w.writerow({
                "id": eq.id, "render_ok": eq.render_ok,
                "sources": " ".join(sorted({s["source"] for s in eq.sources})),
                "n_uses": len(eq.sources), "talks": " ".join(sorted({s["talk"] for s in eq.sources})),
                "verified_distance": "" if eq.verified_distance is None else eq.verified_distance,
                "latex": eq.latex,
            })
    html = REVIEW_DIR / "stage-f-equations.html"
    cells = []
    for eq in rows:
        render = f'<img src="../{eq.render}">' if eq.render_ok else '<span class=bad>render failed</span>'
        crop = f'<img src="../{eq.crop}">' if eq.crop else "<small>no source crop</small>"
        uses = "<br>".join(f"{s['source']} · {s['talk']} #{s['slide']}" for s in eq.sources[:6])
        dist = "" if eq.verified_distance is None else f" · distance {eq.verified_distance}"
        cells.append(
            f"<div class=row><div class=col><b>render</b><br>{render}</div><div class=col><b>source crop</b><br>{crop}</div>"
            f"<div class=col><b>{eq.id}</b>{dist}<br><code>{eq.latex}</code><br><small>{uses}</small></div></div>"
        )
    html.write_text(
        "<!doctype html><meta charset=utf-8><title>Stage F equations</title><style>"
        "body{font-family:system-ui;margin:16px} .row{display:flex;gap:16px;border-top:1px solid #ddd;padding:10px 0}"
        ".col{flex:1;min-width:0} img{max-width:100%;max-height:120px;border:1px solid #ccc;background:#fff}"
        "code{white-space:pre-wrap;word-break:break-all} .bad{color:#b00}</style>"
        f"<h1>Equations ({len(rows)})</h1>{''.join(cells)}<h2>Log</h2><pre>{chr(10).join(log)}</pre>",
        encoding="utf-8",
    )
    return [str(csv_path.relative_to(REPO_ROOT)), str(html.relative_to(REPO_ROOT))]
