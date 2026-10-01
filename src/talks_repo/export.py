"""Stage D: export every attached deck into archive/<talk-id>/.

Outputs per talk:
  deck.pdf        visual reference (copied from the PDF export, or converted)
  deck.pptx       editable copy for figure extraction (Keynote -> PPTX, or copied)
  slides.json     Google Slides only: per-slide text, speaker notes, image list
  media/          Google Slides only: original image bytes from the Slides API
  manifest.yaml   what came from where, and how

Idempotent: a talk whose outputs exist is skipped unless --force. The input
folders are never written to; Keynote and PowerPoint open the originals and
export elsewhere, closing without saving.
"""

import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from talks_repo import REPO_ROOT, resolve_ref

ARCHIVE_DIR = REPO_ROOT / "archive"
SCRIPTS_DIR = REPO_ROOT / "scripts"
_ERA_ORDER = {"UNI": 0, "MIT": 1, "PhD": 2}


class ExportError(RuntimeError):
    pass


def _neg_date(iso: str) -> str:
    """Sort key that puts the newest date first: each digit inverted."""
    return "".join(str(9 - int(c)) if c.isdigit() else c for c in iso)


def talk_dir(talk_id: str) -> Path:
    return ARCHIVE_DIR / talk_id


def _osascript(script: str, *args: str, timeout: int = 900) -> str:
    result = subprocess.run(
        ["osascript", str(SCRIPTS_DIR / script), *args],
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0 or "ok" not in result.stdout:
        raise ExportError(f"{script} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def _keynote_documents() -> list[str]:
    result = subprocess.run(
        ["osascript", "-e", 'tell application "Keynote" to get name of every document'],
        capture_output=True, text=True, timeout=60,
    )
    return [n.strip() for n in result.stdout.split(",") if n.strip()]


def keynote_to_pdf_pptx(src: Path, pdf: Path, pptx: Path, open_timeout: int = 180) -> None:
    """Open via Launch Services (like a double-click), wait for the window, then export."""
    import time

    before = set(_keynote_documents())
    subprocess.run(["open", "-a", "Keynote", str(src)], check=True, timeout=60)
    deadline = time.monotonic() + open_timeout
    doc_name = None
    while time.monotonic() < deadline:
        time.sleep(3)
        new = [n for n in _keynote_documents() if n not in before]
        if new:
            doc_name = new[0]
            break
    if doc_name is None:
        raise ExportError(f"Keynote did not open {src.name} within {open_timeout}s (dialog showing?)")
    _osascript("keynote_export.applescript", doc_name, str(pdf), str(pptx))


def powerpoint_to_pdf(src: Path, pdf: Path) -> None:
    _osascript("powerpoint_export.applescript", str(src), str(pdf))


def export_talk(talk: dict[str, Any], force: bool = False, kinds: set[str] | None = None) -> dict[str, Any]:
    """Export one talk. Returns the manifest (also written to disk). kinds limits the
    source types handled this run, e.g. {".key", ".pdf"} to leave Slides for later."""
    out = talk_dir(talk["id"])
    source = talk.get("source_file")
    pdf_ref = talk.get("pdf_file")
    src_type = Path(source).suffix.lower() if source else None
    if kinds is not None and (src_type or ".pdf") not in kinds:
        return {"status": "skipped-kind"}
    if not source and not pdf_ref:
        return {"status": "nothing-attached"}

    deck_pdf, deck_pptx = out / "deck.pdf", out / "deck.pptx"
    manifest_path = out / "manifest.yaml"
    if manifest_path.exists() and not force:
        return {"status": "already-exported", **yaml.safe_load(manifest_path.read_text())}

    out.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "talk_id": talk["id"],
        "exported": datetime.now().isoformat(timespec="seconds"),
        "source_file": source,
        "pdf_file": pdf_ref,
        "outputs": {},
        "steps": [],
    }

    if src_type == ".gslides":
        from talks_repo import gslides

        gslides.export_presentation(resolve_ref(source), out, manifest)
    elif src_type == ".key":
        keynote_to_pdf_pptx(resolve_ref(source), deck_pdf, deck_pptx)
        manifest["steps"].append("Keynote AppleScript export -> deck.pdf, deck.pptx")
        manifest["outputs"]["deck.pptx"] = "converted-from-keynote"
        manifest["outputs"]["deck.pdf"] = "converted-from-keynote"
    elif src_type in (".pptx", ".ppt"):
        shutil.copy2(resolve_ref(source), deck_pptx)
        manifest["outputs"]["deck.pptx"] = "copied"
        manifest["steps"].append("copied source pptx")

    # the author's own PDF export is what the audience saw. For Keynote sources it goes
    # next to the converted deck.pdf (whose page numbers line up with deck.pptx);
    # otherwise it is deck.pdf itself.
    if pdf_ref:
        target = out / "original.pdf" if src_type == ".key" else deck_pdf
        shutil.copy2(resolve_ref(pdf_ref), target)
        manifest["outputs"][target.name] = "copied original pdf export"
        manifest["steps"].append(f"copied original pdf export -> {target.name}")
    elif not deck_pdf.exists() and deck_pptx.exists():
        powerpoint_to_pdf(deck_pptx, deck_pdf)
        manifest["outputs"]["deck.pdf"] = "converted-from-pptx"
        manifest["steps"].append("PowerPoint AppleScript export -> deck.pdf")

    manifest["status"] = "exported"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True))
    return manifest


def run(talks: list[dict[str, Any]], roots: list[str] | None, ids: list[str] | None,
        kinds: set[str] | None, force: bool, limit: int | None, max_errors: int = 3) -> list[tuple[str, str]]:
    """Export talks in priority order: UNI, MIT, PhD, newest first within each era
    (old Keynote files may not open in current Keynote). Returns (talk_id, status) pairs."""
    ordered = sorted(talks, key=lambda t: (_ERA_ORDER.get(str(t.get("era")), 9), _neg_date(str(t.get("date")))))
    results: list[tuple[str, str]] = []
    done = 0
    consecutive_errors = 0
    for talk in ordered:
        if ids and talk["id"] not in ids:
            continue
        ref = talk.get("source_file") or talk.get("pdf_file")
        if not ref:
            continue
        if roots and ref.partition(":")[0] not in roots:
            continue
        try:
            manifest = export_talk(talk, force=force, kinds=kinds)
            status = manifest["status"]
        except (ExportError, subprocess.TimeoutExpired, OSError) as exc:
            status = f"error: {exc}"
            if talk_dir(talk["id"]).exists():
                (talk_dir(talk["id"]) / "error.txt").write_text(str(exc))
        results.append((talk["id"], status))
        if status.startswith("error"):
            consecutive_errors += 1
            if max_errors and consecutive_errors >= max_errors:
                results.append(("(stopped)", f"{max_errors} consecutive errors; fix the cause or raise --max-errors"))
                break
        elif status == "exported":
            consecutive_errors = 0
            done += 1
            if limit and done >= limit:
                break
    return results
