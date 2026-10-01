"""Stage E part 2: classify every unique image with Claude's vision.

For each entry of work/extract/images.json a Message Batch request carries the
image plus the context it appeared in (talk titles, slide title and texts, the
original filename or alt text). The model returns a fixed JSON object: kind,
caption, accessibility alt text, topic tags, audience level, and for equations a
LaTeX transcription. Results accumulate in review/stage-e/classified.yaml
(tracked), keyed by image id, so re-runs only send images not yet classified.

Workflow: `talks classify submit` -> batch id stored in work/extract/batches/
          `talks classify collect` -> results merged into classified.yaml
Auth: ANTHROPIC_API_KEY from the environment or the git-ignored .env file.
"""

import base64
import io
import json
import os
import time
from pathlib import Path
from typing import Any

import yaml

from talks_repo import REPO_ROOT, REVIEW_DIR, WORK_DIR
from talks_repo.extract import ARCHIVE_DIR, EXTRACT_DIR, _pil_image, read_container

MODEL = "claude-opus-5"
CLASSIFIED = REVIEW_DIR / "stage-e" / "classified.yaml"
BATCH_DIR = EXTRACT_DIR / "batches"
MAX_SIDE = 1280          # plenty for classification; keeps batches small
BATCH_BYTES = 200_000_000  # stay under the 256 MB Batches API limit
BATCH_MAX = 2000
MIN_SIDE = 24            # smaller than this is a bullet or spacer: skipped as decoration

KINDS = ["plot", "schematic", "photo", "equation", "logo", "screenshot", "table", "text", "decoration"]
TOPICS = [
    "mr-tof", "penning-trap", "pi-icr", "mass-measurements", "laser-spectroscopy", "cris", "isoltrap",
    "neptune", "action-spectrometer", "radioactive-molecules", "parity-violation", "fundamental-symmetries",
    "charge-radii", "moments", "nuclear-structure", "100sn", "indium", "isomers", "shell-closure",
    "neutrino-mass", "astrophysics", "r-process", "ion-optics", "ion-source", "beamline", "cyclotron-institute",
    "frib", "isolde", "lera", "ai-ml", "digital-twin", "bayesian-optimization", "facility", "instrumentation",
    "electronics", "vacuum", "lab-photo", "people", "outreach", "teaching", "funding", "timeline", "map",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": KINDS},
        "caption": {"type": "string", "description": "One sentence a physicist would put under the figure."},
        "alt": {"type": "string", "description": "Accessibility alt text: what is shown and what it says (the message), 1-2 sentences. For equations, read the equation aloud."},
        "topics": {"type": "array", "items": {"type": "string"}, "description": "2-5 tags, preferring the given vocabulary; add a new tag only if none fits."},
        "level": {"type": "string", "enum": ["general", "expert"], "description": "general: understandable for a public or undergraduate audience; expert: needs nuclear/AMO background."},
        "latex": {"type": "string", "description": "For kind=equation: the LaTeX transcription. Otherwise empty."},
        "text_in_image": {"type": "string", "description": "Axis labels, legend entries, or key numbers visible, comma separated. Empty if none."},
        "confidence": {"type": "number", "description": "0-1, how sure you are about kind and caption."},
    },
    "required": ["kind", "caption", "alt", "topics", "level", "latex", "text_in_image", "confidence"],
    "additionalProperties": False,
}

SYSTEM = f"""You classify images extracted from research-talk slides by Your Name, a nuclear/AMO
physicist (ion traps, MR-ToF mass spectrometry, laser spectroscopy of radioactive atoms and molecules,
parity violation, AI for experiment control). Each image comes with the slide context it appeared in.

Kinds: {", ".join(KINDS)}. "plot" is a data or simulation graph; "schematic" is a drawn diagram of an
apparatus, level scheme, or concept; "screenshot" is a captured software window or web page; "text" is
an image that only contains typeset text; "decoration" is a shape, arrow, gradient, icon or spacer with
no content of its own. Preferred topic tags: {", ".join(TOPICS)}.
Write captions and alt text in plain English, naming the physical quantity and the message when a plot
shows one. Never invent numbers that are not visible."""


def load_env() -> None:
    env = REPO_ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def client():
    import anthropic

    load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set. Put ANTHROPIC_API_KEY=sk-ant-... into .env (git-ignored).")
    return anthropic.Anthropic()


# --------------------------------------------------------------------------- inputs


def load_classified() -> dict[str, Any]:
    if CLASSIFIED.exists():
        return yaml.safe_load(CLASSIFIED.read_text(encoding="utf-8")) or {}
    return {}


def save_classified(data: dict[str, Any]) -> None:
    CLASSIFIED.parent.mkdir(parents=True, exist_ok=True)
    CLASSIFIED.write_text(yaml.safe_dump(data, sort_keys=True, allow_unicode=True, width=1000), encoding="utf-8")


def lookup(classified: dict[str, Any], im: dict[str, Any]) -> dict[str, Any] | None:
    """The classification of this cluster, whichever member it was stored under."""
    for key in [im["id"], *im.get("variants", [])]:
        if key in classified:
            return classified[key]
    return None


def slide_context() -> dict[tuple[str, int], dict[str, Any]]:
    """(talk_id, slide index) -> title/texts/notes, from every extract.json."""
    ctx: dict[tuple[str, int], dict[str, Any]] = {}
    for p in ARCHIVE_DIR.glob("*/extract.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        for s in r["slides"]:
            ctx[(r["talk_id"], s["index"])] = s
    return ctx


def talk_titles() -> dict[str, str]:
    from talks_repo import TALKS_YAML, manifest

    return {t["id"]: str(t.get("title", "")) for t in manifest.load(TALKS_YAML)}


def encode_image(im: dict[str, Any]) -> tuple[str, str] | None:
    """Return (media_type, base64) for the image, downscaled to MAX_SIDE; None if unusable."""
    data = read_container(im["container"])
    img = _pil_image(data, im["ext"])
    if img is None:
        return None
    if im["ext"] == ".pdf":
        # Re-render vector originals at a useful resolution instead of the 72 dpi probe.
        import pymupdf

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            page = doc[0]
            zoom = min(4.0, MAX_SIDE / max(page.rect.width, page.rect.height, 1))
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            from PIL import Image

            img = Image.open(io.BytesIO(pix.tobytes("png")))
    if max(img.size) < MIN_SIDE:
        return None
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return "image/jpeg", base64.standard_b64encode(buf.getvalue()).decode()


def build_request(im: dict[str, Any], ctx: dict[tuple[str, int], dict[str, Any]], titles: dict[str, str]) -> dict[str, Any] | None:
    try:
        encoded = encode_image(im)
    except Exception:  # noqa: BLE001 - a corrupt image is skipped, not fatal
        encoded = None
    if encoded is None:
        return None
    media_type, data = encoded
    lines = [f"Original file name or alt text: {im.get('name') or 'unknown'}",
             f"Format: {im['ext']} {im.get('width')}x{im.get('height')} px" + (" (vector original)" if im["vector"] else "")]
    for use in im["uses"][:3]:
        talk_id, _, idx = use.rpartition("#")
        s = ctx.get((talk_id, int(idx)))
        lines.append(f"Talk: {titles.get(talk_id, talk_id)} — slide {idx}" + (f": {s['title']}" if s and s.get("title") else ""))
        if s:
            for t in (s.get("texts") or [])[:4]:
                lines.append(f"  slide text: {t[:200]}")
            if s.get("notes"):
                lines.append(f"  speaker notes: {s['notes'][:300]}")
    if im["n_uses"] > 3:
        lines.append(f"(used on {im['n_uses']} slides in total)")
    return {
        "custom_id": im["id"],
        "params": {
            "model": MODEL,
            "max_tokens": 8192,  # thinking tokens count against this; 4096 still truncated ~5% of answers
            "system": SYSTEM,
            "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
                    {"type": "text", "text": "Context:\n" + "\n".join(lines) + "\n\nClassify this image."},
                ],
            }],
        },
    }


# --------------------------------------------------------------------------- submit / collect


def submit(limit: int | None = None, dry_run: bool = False) -> dict[str, Any]:
    index = json.loads((EXTRACT_DIR / "images.json").read_text(encoding="utf-8"))
    done = load_classified()
    already = len(done)
    ctx, titles = slide_context(), talk_titles()
    requests, skipped = [], []
    for im in index["images"]:
        prior = lookup(done, im)
        if prior is not None and prior.get("error"):
            prior = None  # a failed attempt (truncated, refused, bad JSON) is retried
        if prior is not None:
            if im["id"] not in done:
                done[im["id"]] = prior  # a better variant became the cluster id; carry the result over
                skipped.append(im["id"])
            continue
        if im.get("width") and im.get("height") and max(im["width"], im["height"]) < MIN_SIDE:
            done[im["id"]] = {"kind": "decoration", "caption": "", "alt": "", "topics": [], "level": "general",
                              "latex": "", "text_in_image": "", "confidence": 1.0, "source": "rule:tiny"}
            skipped.append(im["id"])
            continue
        req = build_request(im, ctx, titles)
        if req is None:
            skipped.append(im["id"])
            continue
        requests.append(req)
        if limit and len(requests) >= limit:
            break
    if skipped:
        save_classified(done)
    summary = {"requests": len(requests), "skipped": len(skipped), "already_classified": already}
    if dry_run or not requests:
        return summary
    c = client()
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    chunks: list[list[dict[str, Any]]] = [[]]
    size = 0
    for req in requests:
        n = len(json.dumps(req))
        if chunks[-1] and (size + n > BATCH_BYTES or len(chunks[-1]) >= BATCH_MAX):
            chunks.append([])
            size = 0
        chunks[-1].append(req)
        size += n
    summary["batch_ids"] = []
    for chunk in chunks:
        batch = c.messages.batches.create(requests=chunk)
        (BATCH_DIR / f"{batch.id}.json").write_text(json.dumps({
            "id": batch.id, "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "n": len(chunk),
            "ids": [r["custom_id"] for r in chunk], "status": batch.processing_status,
        }, indent=1))
        summary["batch_ids"].append(batch.id)
    return summary


def pending_batches() -> list[Path]:
    return sorted(p for p in BATCH_DIR.glob("*.json") if json.loads(p.read_text()).get("status") != "collected")


def collect(wait: bool = False, poll_seconds: int = 60) -> dict[str, Any]:
    c = client()
    done = load_classified()
    summary: dict[str, Any] = {"collected": 0, "errored": 0, "still_processing": 0}
    for record_path in pending_batches():
        record = json.loads(record_path.read_text())
        while True:
            batch = c.messages.batches.retrieve(record["id"])
            if batch.processing_status == "ended" or not wait:
                break
            time.sleep(poll_seconds)
        if batch.processing_status != "ended":
            summary["still_processing"] += 1
            continue
        for result in c.messages.batches.results(record["id"]):
            if result.result.type == "succeeded":
                msg = result.result.message
                if msg.stop_reason == "refusal":
                    done[result.custom_id] = {"kind": "unknown", "error": "refusal", "source": "claude"}
                    summary["errored"] += 1
                    continue
                text = next((b.text for b in msg.content if b.type == "text"), "")
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    done[result.custom_id] = {"kind": "unknown", "error": "bad-json", "source": "claude"}
                    summary["errored"] += 1
                    continue
                parsed["source"] = f"claude:{msg.model}"
                done[result.custom_id] = parsed
                summary["collected"] += 1
            else:
                done.setdefault(result.custom_id, {"kind": "unknown", "error": result.result.type, "source": "claude"})
                summary["errored"] += 1
        record["status"] = "collected"
        record_path.write_text(json.dumps(record, indent=1))
    save_classified(done)
    return summary
