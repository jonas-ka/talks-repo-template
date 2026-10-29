"""PDF snapshots of HTML widgets (`html-widget` in blocks/_html-widget.typ).

`talks html` lays a live widget over its box; the PDF shows the block's static fallback. For the
widgets in SNAPSHOT, `refresh(main)` renders the widget in headless Chromium (Playwright) at its
box size with the deck's brief, prints it to PDF and converts that to SVG with PyMuPDF: text,
markers and cards stay vector, map tiles are embedded images. It writes
talks/<slug>/generated/<id>.svg and <id>.json (fetch time, the values shown, alt text) and returns
the typst `--input widget-<id>=<path stem>` arguments that make `html-widget` show the snapshot.
A widget marks its root `data-done` when it has finished loading and leaves what it shows in
`root.snapshot`.
"""

import datetime as dt
import json
import re
from pathlib import Path

from talks_repo import REPO_ROOT

SNAPSHOT = ("map-weather",)
# CSS px per pt: a 16:9 slide (793.7 pt wide) on a 1920-px screen, the size the live widget is seen at
PX_PER_PT = 1920 / 793.7
_INCLUDE = re.compile(r'#include\s+"/(blocks/[^"]+\.typ)"')


def _used(main: Path) -> list[str]:
    """Snapshot widget ids used by the deck's own source or its included blocks."""
    text = main.read_text(encoding="utf-8")
    sources = [text] + [(REPO_ROOT / rel).read_text(encoding="utf-8") for rel in _INCLUDE.findall(text) if (REPO_ROOT / rel).exists()]
    return [i for i in SNAPSHOT if any(f'html-widget("{i}"' in s for s in sources)]


def _alt_map_weather(s: dict, asof: str) -> str:
    places = s.get("places") or []
    alt = "Map showing " + " and ".join(f"{p['name']} in {p['place']}" if p.get("place") else p["name"] for p in places)
    if s.get("km"):
        alt += f", joined by a dashed line labelled {round(s['km']):,} km"
    alt += "."
    if s.get("weather"):
        alt += f" Weather forecast by Open-Meteo as of {asof}."
    for w in s.get("weather") or []:
        parts = [f"now {w['now']['words']}, {round(w['now']['temp'])} °C"] if w.get("now") else []
        parts += [f"{d['label']} {d['words']}, {d['min']} to {d['max']} °C" for d in w["days"]] or [w.get("note", "no forecast")]
        alt += f" {w.get('place') or w['name']}: {'; '.join(parts)}."
    return alt


ALT = {"map-weather": _alt_map_weather}


def _render(page_html: str, w_px: int, h_px: int) -> tuple[bytes, dict]:
    """Load the page, wait for the widget and its images, print one page to PDF."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:  # noqa: BLE001  # Playwright's Chromium not installed: the system Chrome
            browser = p.chromium.launch(channel="chrome")
        try:
            page = browser.new_page(viewport={"width": w_px, "height": h_px})
            page.emulate_media(media="screen")
            page.set_content(page_html, wait_until="load")
            page.wait_for_function("() => { const w = document.querySelector('.widget'); return !w || w.querySelector('[data-done]'); }",
                                   timeout=45000)
            if not page.query_selector(".widget [data-done]"):
                raise RuntimeError("the widget gave up (offline?)")
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_function("() => [...document.images].every(i => i.complete) && document.fonts.status === 'loaded'", timeout=30000)
            page.wait_for_timeout(600)   # Leaflet fades tiles in
            data = page.evaluate("() => document.querySelector('.widget [data-done]').snapshot || {}")
            pdf = page.pdf(width=f"{w_px}px", height=f"{h_px}px", print_background=True, page_ranges="1",
                           margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        finally:
            browser.close()
    return pdf, data


def snapshot(wid: str, w_pt: float, h_pt: float, brief_path: Path, out_dir: Path) -> Path:
    """Render one widget; returns the path stem of <id>.svg / <id>.json."""
    import pymupdf

    from talks_repo import html_export

    now = dt.datetime.now().astimezone()
    asof = f"{now.day} {now:%b %Y}"
    brief = json.loads(html_export._brief_json(brief_path) or "{}") or {}
    brief["asof"] = asof
    brief_json = json.dumps(brief, default=str).replace("<", "\\u003c")
    src = (REPO_ROOT / "assets" / "interactive" / f"{wid}.html").read_text(encoding="utf-8").replace("__BRIEF__", brief_json)
    w_px, h_px = round(w_pt * PX_PER_PT), round(h_pt * PX_PER_PT)
    page_html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"></head><body style="margin:0;background:#fff">'
                 f'<div class="widget" style="position:relative;width:{w_px}px;height:{h_px}px">{src}</div></body></html>')
    pdf, data = _render(page_html, w_px, h_px)
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        svg = doc[0].get_svg_image(text_as_path=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / wid
    stem.with_suffix(".svg").write_text(svg, encoding="utf-8")
    meta = {"id": wid, "fetched": now.isoformat(timespec="seconds"), "asof": asof, "box_pt": [w_pt, h_pt],
            "data": data, "alt": ALT[wid](data, asof)}
    stem.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return stem


def refresh(main: Path, handout: bool = False) -> tuple[list[str], list[str]]:
    """Re-render every snapshot widget the deck uses. Returns the typst inputs and log lines. If a
    render fails (e.g. offline), an earlier snapshot is kept (it carries its own date); without one
    the block's static fallback stays."""
    try:
        main.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return [], []
    ids = _used(main)
    if not ids:
        return [], []
    from talks_repo import html_export

    out_dir = main.parent / "generated"
    inputs: list[str] = []
    log: list[str] = []
    try:
        boxes = {w["id"]: w for ws in html_export._widgets(main, handout).values() for w in ws}
    except Exception as exc:  # noqa: BLE001
        boxes = {}
        log.append(f"widget query failed: {str(exc)[:200]}")
    for wid in ids:
        stem = out_dir / wid
        try:
            box = boxes[wid]
            snapshot(wid, box["w"], box["h"], main.parent / "brief.yaml", out_dir)
            log.append(f"{wid}: snapshot refreshed -> {stem.relative_to(REPO_ROOT)}.svg")
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__
            if not (stem.with_suffix(".svg").exists() and stem.with_suffix(".json").exists()):
                log.append(f"{wid}: snapshot failed ({msg}); the PDF shows the static fallback")
                continue
            log.append(f"{wid}: snapshot failed ({msg}); keeping the one from {json.loads(stem.with_suffix('.json').read_text())['asof']}")
        inputs += ["--input", f"widget-{wid}=/{stem.relative_to(REPO_ROOT).as_posix()}"]
    return inputs, log
