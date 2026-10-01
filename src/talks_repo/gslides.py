"""Google Slides via the Slides and Drive APIs (read-only).

Why the API and not the PPTX export: the export is unreliable, and the API hands
over exactly what Stage E needs anyway. For every slide it returns the image
objects with a download URL for the original bytes, the text boxes, the alt
text (LaTeX add-ons store the equation source there), and the speaker notes,
which is where the author keeps the LaTeX for equations rendered as pictures.

Setup (one time): README.md, section "Google API access". credentials.json and
token.json live in the repo root and are git-ignored.
"""

import json
import re
from pathlib import Path
from typing import Any

import httpx

from talks_repo import REPO_ROOT

# Slides read-only; Drive read/write because `talks sync-drive` creates files in the lab's
# shared drive (append-only by code: files.create is the only write call in the repo).
SCOPES = [
    "https://www.googleapis.com/auth/presentations.readonly",
    "https://www.googleapis.com/auth/drive",
]
CREDENTIALS = REPO_ROOT / "credentials.json"
TOKEN = REPO_ROOT / "token.json"

_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/svg+xml": ".svg",
        "image/webp": ".webp", "image/bmp": ".bmp", "image/tiff": ".tif"}


def credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        if not CREDENTIALS.exists():
            raise FileNotFoundError(
                f"{CREDENTIALS} missing. Create an OAuth desktop client in Google Cloud Console "
                "(README.md, 'Google API access') and save it there."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
        creds = flow.run_local_server(port=0)
    TOKEN.write_text(creds.to_json())
    return creds


def slides_service(creds=None):
    from googleapiclient.discovery import build

    return build("slides", "v1", credentials=creds or credentials(), cache_discovery=False)


def doc_id_from_pointer(pointer: Path) -> str:
    data = json.loads(pointer.read_text(encoding="utf-8"))
    doc_id = data.get("doc_id")
    if not doc_id:
        raise ValueError(f"{pointer} has no doc_id")
    return doc_id


# --------------------------------------------------------------------------- structure


def _text_of(element: dict[str, Any]) -> str:
    shape = element.get("shape") or {}
    text = shape.get("text") or {}
    out = []
    for run in text.get("textElements", []):
        if "textRun" in run:
            out.append(run["textRun"].get("content", ""))
    return "".join(out).strip()


def _table_text(element: dict[str, Any]) -> str:
    table = element.get("table") or {}
    cells = []
    for row in table.get("tableRows", []):
        for cell in row.get("tableCells", []):
            for run in (cell.get("text") or {}).get("textElements", []):
                if "textRun" in run:
                    cells.append(run["textRun"].get("content", "").strip())
    return " | ".join(c for c in cells if c)


def _iter_elements(elements: list[dict[str, Any]]):
    """Walk page elements, descending into groups."""
    for el in elements:
        if "elementGroup" in el:
            yield from _iter_elements(el["elementGroup"].get("children", []))
        else:
            yield el


def notes_text(slide: dict[str, Any]) -> str:
    notes_page = slide.get("slideProperties", {}).get("notesPage") or {}
    notes_id = notes_page.get("notesProperties", {}).get("speakerNotesObjectId")
    for el in _iter_elements(notes_page.get("pageElements", [])):
        if el.get("objectId") == notes_id:
            return _text_of(el)
    return ""


def describe(presentation: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-slide structure: texts, notes, images (with download URLs, not yet fetched)."""
    slides = []
    for index, slide in enumerate(presentation.get("slides", []), start=1):
        texts, images = [], []
        for el in _iter_elements(slide.get("pageElements", [])):
            if "image" in el:
                img = el["image"]
                size = el.get("size", {})
                images.append({
                    "object_id": el.get("objectId"),
                    "content_url": img.get("contentUrl"),
                    "source_url": img.get("sourceUrl"),
                    "alt_title": el.get("title"),
                    "alt_description": el.get("description"),
                    "width_emu": size.get("width", {}).get("magnitude"),
                    "height_emu": size.get("height", {}).get("magnitude"),
                })
            elif "shape" in el:
                t = _text_of(el)
                if t:
                    texts.append(t)
            elif "table" in el:
                t = _table_text(el)
                if t:
                    texts.append(t)
        slides.append({
            "index": index,
            "object_id": slide.get("objectId"),
            "skipped": bool(slide.get("slideProperties", {}).get("isSkipped")),
            "texts": texts,
            "notes": notes_text(slide),
            "images": images,
        })
    return slides


# --------------------------------------------------------------------------- export


def download_images(slides: list[dict[str, Any]], media_dir: Path) -> int:
    """Fetch original image bytes. contentUrl links are short-lived and need no auth."""
    media_dir.mkdir(exist_ok=True)
    n = 0
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for slide in slides:
            for k, img in enumerate(slide["images"], start=1):
                url = img.pop("content_url", None)
                if not url:
                    img["file"] = None
                    continue
                r = client.get(url)
                if r.status_code != 200:
                    img["file"] = None
                    img["error"] = f"HTTP {r.status_code}"
                    continue
                ext = _EXT.get(r.headers.get("content-type", "").split(";")[0].strip(), ".bin")
                name = f"slide{slide['index']:03d}_img{k}{ext}"
                (media_dir / name).write_bytes(r.content)
                img["file"] = f"media/{name}"
                img["bytes"] = len(r.content)
                n += 1
    return n


def export_document(doc_id: str, fmt: str, out: Path, creds) -> None:
    """Export via the docs.google.com endpoint, which has no 10 MB limit unlike files.export."""
    url = f"https://docs.google.com/presentation/d/{doc_id}/export/{fmt}"
    headers = {"Authorization": f"Bearer {creds.token}"}
    with httpx.Client(timeout=300, follow_redirects=True) as client:
        r = client.get(url, headers=headers)
        r.raise_for_status()
        out.write_bytes(r.content)


def export_presentation(pointer: Path, out_dir: Path, manifest: dict[str, Any]) -> None:
    doc_id = doc_id_from_pointer(pointer)
    creds = credentials()
    presentation = slides_service(creds).presentations().get(presentationId=doc_id).execute()
    slides = describe(presentation)
    n_images = download_images(slides, out_dir / "media")
    (out_dir / "slides.json").write_text(json.dumps({
        "presentation_id": doc_id,
        "title": presentation.get("title"),
        "n_slides": len(slides),
        "slides": slides,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    export_document(doc_id, "pdf", out_dir / "deck.pdf", creds)
    manifest["outputs"]["deck.pdf"] = "google-slides-pdf-export"
    manifest["outputs"]["slides.json"] = f"slides-api ({len(slides)} slides, {n_images} images, notes included)"
    manifest["outputs"]["media/"] = "slides-api original image bytes"
    manifest["steps"].append("Slides API presentations.get -> slides.json + media/")
    manifest["steps"].append("docs.google.com export -> deck.pdf")
    try:
        export_document(doc_id, "pptx", out_dir / "deck.pptx", creds)
        manifest["outputs"]["deck.pptx"] = "google-slides-pptx-export (unreliable formatting; use slides.json + media/ instead)"
    except httpx.HTTPError as exc:
        manifest["steps"].append(f"pptx export failed: {exc}")
    notes = sum(1 for s in slides if s["notes"])
    latex = sum(1 for s in slides if re.search(r"\\[a-zA-Z]+|\$", s["notes"]))
    manifest["notes"] = {"slides_with_notes": notes, "slides_with_latex_in_notes": latex}
