"""Stage G: build assets/catalog.yaml from the reviewed images and equations, and
propose the first blocks from recurring slide sequences.

Catalog entries (schema in CLAUDE.md) come from work/extract/images.json (unique
images and where they are used) joined with review/stage-e/classified.yaml (kind,
caption, alt, topics, level). first_used / last_used come from the talks' dates.
`supersedes_candidates` lists older look-alike figures (same kind, similar hash)
for the author to confirm; `supersedes` itself is only ever set by hand.

Figures of kind plot / schematic / table / equation are copied into assets/figures/
in their best available format (vector PDF preferred). Photos, screenshots and
logos are catalogued with `file: null` and an `archive_ref` pointing at the
archived deck they live in; `--copy-all` copies them too.

Re-running keeps every field of an existing entry that the author may have edited
(id, caption, alt, topics, level, supersedes, source, notes) and only refreshes
usage data (first_used, last_used, uses).
"""

import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

from talks_repo import REPO_ROOT, REVIEW_DIR, TALKS_YAML, manifest
from talks_repo.extract import ARCHIVE_DIR, EXTRACT_DIR, hamming, read_container

CATALOG = REPO_ROOT / "assets" / "catalog.yaml"
FIGURES = REPO_ROOT / "assets" / "figures"
EQUATIONS = REPO_ROOT / "assets" / "equations"
COPY_KINDS = {"plot", "schematic", "table", "equation"}
CATALOG_KINDS = {"plot", "schematic", "photo", "equation", "logo", "screenshot", "table"}
SUPERSEDE_DISTANCE = 40   # phash distance (256-bit) below which two figures of one kind look related
_HAND_FIELDS = ("id", "caption", "alt", "topics", "level", "supersedes", "source", "notes", "kind", "file")
_STOP = {"the", "of", "a", "an", "and", "in", "for", "with", "vs", "versus", "at", "on", "to", "from", "as", "by"}


def slugify(text: str, max_words: int = 4) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    words = [w for w in re.findall(r"[a-z0-9]+", ascii_text.lower()) if w not in _STOP]
    return "-".join(words[:max_words])


def _talk_dates(talks: list[dict[str, Any]]) -> dict[str, str]:
    return {t["id"]: str(t.get("date", ""))[:7] for t in talks}


def _load_classified() -> dict[str, Any]:
    p = REVIEW_DIR / "stage-e" / "classified.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {} if p.exists() else {}


def _lookup(classified: dict[str, Any], im: dict[str, Any]) -> dict[str, Any] | None:
    for key in [im["id"], *im.get("variants", [])]:
        c = classified.get(key)
        if c and not c.get("error"):
            return c
    return None


# --------------------------------------------------------------------------- figures


def build_entries(copy_all: bool = False) -> tuple[list[dict[str, Any]], dict[str, int]]:
    talks = manifest.load(TALKS_YAML)
    dates = _talk_dates(talks)
    classified = _load_classified()
    index = json.loads((EXTRACT_DIR / "images.json").read_text(encoding="utf-8"))
    existing = {e["image_id"]: e for e in (yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or []) if e.get("image_id")}
    counts: dict[str, int] = Counter()
    entries: list[dict[str, Any]] = []
    used_ids: set[str] = set(e["id"] for e in existing.values())
    FIGURES.mkdir(parents=True, exist_ok=True)

    for im in index["images"]:
        c = _lookup(classified, im)
        if c is None:
            counts["unclassified"] += 1
            continue
        kind = c.get("kind")
        if kind not in CATALOG_KINDS:
            counts[f"skipped-{kind}"] += 1
            continue
        uses = sorted(im["uses"], key=lambda u: dates.get(u.rpartition("#")[0], ""))
        use_dates = sorted(d for d in (dates.get(u.rpartition("#")[0], "") for u in uses) if d)
        first_talk, _, first_slide = uses[0].rpartition("#") if uses else ("", "", "")
        old = existing.get(im["id"])
        if old:
            entry = dict(old)
        else:
            base = f"{kind}-{slugify(c.get('caption') or im.get('name') or kind) or im['id'][:6]}"
            entry_id, n = base, 1
            while entry_id in used_ids:
                n += 1
                entry_id = f"{base}-{n}"
            used_ids.add(entry_id)
            entry = {
                "id": entry_id,
                "image_id": im["id"],
                "file": None,
                "kind": kind,
                "topic": c.get("topics") or [],
                "level": [c.get("level") or "general"],
                "caption": c.get("caption") or "",
                "alt": c.get("alt") or "",
                "source": None,
                "supersedes": None,
                "notes": "",
            }
        # Usage data is always refreshed.
        entry["first_used"] = use_dates[0] if use_dates else None
        entry["last_used"] = use_dates[-1] if use_dates else None
        entry["n_uses"] = len(uses)
        entry["origin"] = {"talk": first_talk, "slide": int(first_slide)} if first_talk else None
        entry["uses"] = uses
        entry["vector"] = bool(im.get("vector"))
        entry["archive_ref"] = im["container"].replace(str(REPO_ROOT) + "/", "")
        conf = c.get("confidence")
        entry["confidence"] = round(float(conf), 2) if isinstance(conf, (int, float)) and 0 <= conf <= 1 else None
        entry["_phash"] = im.get("phash")
        if (kind in COPY_KINDS or copy_all) and not entry.get("file"):
            target = FIGURES / f"{entry['id']}{im['ext']}"
            if not target.exists():
                try:
                    target.write_bytes(read_container(im["container"]))
                    counts["copied"] += 1
                except Exception:  # noqa: BLE001
                    counts["copy-failed"] += 1
                    target = None
            if target:
                entry["file"] = str(target.relative_to(REPO_ROOT / "assets"))
        # Typst's tagged-PDF export cannot embed PDFs: keep an SVG twin of every vector figure.
        if entry.get("file") and entry["file"].endswith(".pdf"):
            svg = (REPO_ROOT / "assets" / entry["file"]).with_suffix(".svg")
            if not svg.exists():
                try:
                    import pymupdf

                    with pymupdf.open(REPO_ROOT / "assets" / entry["file"]) as doc:
                        svg.write_text(doc[0].get_svg_image(), encoding="utf-8")
                    counts["svg-twins"] += 1
                except Exception:  # noqa: BLE001
                    counts["svg-failed"] += 1
            entry["svg"] = str(svg.relative_to(REPO_ROOT / "assets")) if svg.exists() else None
        entries.append(entry)
        counts[kind] += 1

    # Hand-added entries (no image_id, not equations: figures added for a talk without a
    # past deck behind them) are carried over untouched.
    for e in yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or []:
        if not e.get("image_id") and e.get("kind") != "equation" and e["id"] not in {x["id"] for x in entries}:
            entries.append(dict(e))
            counts["hand-added"] += 1

    _propose_supersedes(entries)
    for e in entries:
        e.pop("_phash", None)
    entries.sort(key=lambda e: (e["kind"], -(e["n_uses"] or 0), e["id"]))
    return entries, counts


def _propose_supersedes(entries: list[dict[str, Any]]) -> None:
    """Older look-alike figures of the same kind become supersedes_candidates of the newer."""
    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in entries:
        if e.get("_phash") and e.get("kind") in ("plot", "schematic", "table"):
            by_kind[e["kind"]].append(e)
    for group in by_kind.values():
        for a in group:
            cands = []
            for b in group:
                if a is b or not a["last_used"] or not b["last_used"]:
                    continue
                if b["last_used"] < a["last_used"] and hamming(a["_phash"], b["_phash"]) <= SUPERSEDE_DISTANCE:
                    cands.append(b["id"])
            if cands:
                a["supersedes_candidates"] = cands[:5]
            else:
                a.pop("supersedes_candidates", None)


# --------------------------------------------------------------------------- equations


def equation_entries(entries: list[dict[str, Any]]) -> int:
    """Catalog entries for assets/equations/*.tex (provenance from the file header)."""
    talks = manifest.load(TALKS_YAML)
    dates = _talk_dates(talks)
    have = {e["id"] for e in entries}
    # Existing equation entries keep their hand-edited (or generated) fields across re-runs.
    previous = {e["id"]: e for e in (yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or [])
                if CATALOG.exists() and str(e.get("id", "")).startswith("equation-") and e.get("image_id") is None}
    # Alt text and topics of equation images on the same slide, borrowed for the .tex entry.
    by_use: dict[str, dict[str, Any]] = {}
    for e in entries:
        if e.get("kind") == "equation" and e.get("alt"):
            for u in e.get("uses") or []:
                by_use.setdefault(u, e)
    n = 0
    for tex in sorted(EQUATIONS.glob("*.tex")):
        eid = f"equation-{tex.stem}"
        if eid in have:
            continue
        lines = tex.read_text(encoding="utf-8").splitlines()
        sources = [re.search(r"talk: (\S+)\s+slide: (\S+)", l) for l in lines if l.startswith("% source")]
        uses = [f"{m.group(1)}#{m.group(2)}" for m in sources if m]
        use_dates = sorted(d for d in (dates.get(u.rpartition("#")[0], "") for u in uses) if d)
        latex = "\n".join(l for l in lines if not l.startswith("%")).strip()
        twin = next((by_use[u] for u in uses if u in by_use), None)
        old = previous.get(eid, {})
        entries.append({
            "id": eid, "image_id": None, "file": f"equations/{tex.name}", "kind": "equation",
            "topic": old.get("topic") or (list(twin["topic"]) if twin else []),
            "level": old.get("level") or ["expert"],
            "caption": old.get("caption") or (twin["caption"] if twin else latex[:80]),
            "alt": old.get("alt") or (twin["alt"] if twin else ""),
            "source": old.get("source"), "notes": old.get("notes", ""),
            "supersedes": old.get("supersedes"), "first_used": use_dates[0] if use_dates else None,
            "last_used": use_dates[-1] if use_dates else None, "n_uses": len(uses),
            "origin": {"talk": uses[0].rpartition("#")[0], "slide": int(uses[0].rpartition("#")[2])} if uses else None,
            "uses": uses, "vector": True, "latex": latex,
        })
        n += 1
    return n


# --------------------------------------------------------------------------- blocks


def block_candidates(min_talks: int = 3) -> list[dict[str, Any]]:
    """Slide titles (normalised) that recur across talks, with the pictures they carry:
    the raw material for the first reusable blocks."""
    talks = manifest.load(TALKS_YAML)
    dates = _talk_dates(talks)
    groups: dict[str, dict[str, Any]] = {}
    for p in ARCHIVE_DIR.glob("*/extract.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        for s in r["slides"]:
            title = (s.get("title") or "").strip()
            if not title or len(title) < 6 or s.get("build_group") and not s.get("build_final"):
                continue
            key = slugify(title, max_words=6)
            g = groups.setdefault(key, {"title": title, "talks": set(), "slides": 0, "pictures": Counter()})
            g["talks"].add(r["talk_id"])
            g["slides"] += 1
            for sha in s.get("pictures", []):
                g["pictures"][sha[:12]] += 1
    out = []
    for key, g in groups.items():
        if len(g["talks"]) < min_talks:
            continue
        ts = sorted(g["talks"], key=lambda t: dates.get(t, ""))
        out.append({
            "block": key, "title": g["title"], "n_talks": len(g["talks"]), "n_slides": g["slides"],
            "first": dates.get(ts[0], ""), "last": dates.get(ts[-1], ""),
            "talks": " ".join(ts), "top_pictures": " ".join(p for p, _ in g["pictures"].most_common(4)),
        })
    out.sort(key=lambda b: (-b["n_talks"], b["block"]))
    return out


# --------------------------------------------------------------------------- outputs


CATALOG_HEADER = """\
One entry per figure or equation. Schema in CLAUDE.md. Built by `talks catalog`
from the Stage E image index + classification and the Stage F equations.
Hand-edit id, caption, alt, topic, level, source, supersedes, notes: re-runs
keep them and only refresh usage fields. `supersedes` is never set automatically;
`supersedes_candidates` are suggestions. `alt` is mandatory for generation."""


def write_catalog(entries: list[dict[str, Any]]) -> None:
    manifest.save(CATALOG, entries, CATALOG_HEADER)


def write_review(entries: list[dict[str, Any]], blocks: list[dict[str, Any]]) -> list[str]:
    import csv

    REVIEW_DIR.mkdir(exist_ok=True)
    out = []
    p = REVIEW_DIR / "stage-g-catalog.csv"
    cols = ["id", "kind", "file", "vector", "n_uses", "first_used", "last_used", "level", "topic",
            "caption", "alt_missing", "supersedes_candidates", "confidence", "archive_ref"]
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for e in entries:
            w.writerow({**{k: e.get(k) for k in cols}, "topic": " ".join(e.get("topic") or []),
                        "level": " ".join(e.get("level") or []), "alt_missing": not e.get("alt"),
                        "supersedes_candidates": " ".join(e.get("supersedes_candidates") or [])})
    out.append(str(p.relative_to(REPO_ROOT)))
    p = REVIEW_DIR / "stage-g-blocks.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["block", "title", "n_talks", "n_slides", "first", "last", "talks", "top_pictures"])
        w.writeheader()
        w.writerows(blocks)
    out.append(str(p.relative_to(REPO_ROOT)))
    return out
