"""HTML slideshow export: one inline SVG per slide, so animated GIFs keep moving.

Typst's SVG export embeds raster images with their original bytes (a GIF stays
`data:image/gif`), and browsers animate GIFs inside inline SVG. PDF cannot do
that. The result is a single self-contained index.html next to out.pdf:

    talks html <slug>            presentation (pause steps as separate slides)
    talks html <slug> --handout  one slide per page

Keys: arrow keys / space / PageUp / PageDown / Home / End, click or tap to advance,
`f` for fullscreen, `?` for help. The current slide is in the URL hash.
"""

import base64
import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

from talks_repo import REPO_ROOT

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { color-scheme: dark; }
  html, body { margin: 0; height: 100%; background: #1c1c1e; overflow: hidden; font-family: system-ui, sans-serif; }
  #deck { position: fixed; inset: 0; display: grid; place-items: center; }
  .slide { display: none; width: min(100vw, calc(100vh * 16 / 9)); height: min(100vh, calc(100vw * 9 / 16));
           background: #fff; box-shadow: 0 0 40px rgba(0,0,0,.6); }
  .slide.active { display: block; }
  .slide svg { width: 100%; height: 100%; display: block; }
  #hud { position: fixed; right: 12px; bottom: 8px; color: #bbb; font-size: 13px; opacity: .7; user-select: none; }
  #help { position: fixed; left: 50%; top: 50%; transform: translate(-50%,-50%); background: #2c2c2e; color: #eee;
          padding: 18px 24px; border-radius: 10px; display: none; line-height: 1.6; box-shadow: 0 0 30px rgba(0,0,0,.7); }
  #help.show { display: block; }
  kbd { background: #444; border-radius: 4px; padding: 0 6px; }
</style>
</head>
<body>
<div id="deck">
__SLIDES__
</div>
<div id="hud"><span id="pos">1</span> / __N__</div>
<div id="help"><b>__TITLE__</b><br>
<kbd>→</kbd> <kbd>space</kbd> <kbd>click</kbd> next &nbsp; <kbd>←</kbd> previous &nbsp; <kbd>Home</kbd>/<kbd>End</kbd> first/last<br>
<kbd>f</kbd> fullscreen &nbsp; <kbd>?</kbd> this help</div>
<script type="application/json" id="images">__IMAGES__</script>
<script>
(() => {
  const images = JSON.parse(document.getElementById('images').textContent);
  const slides = Array.from(document.querySelectorAll('.slide'));
  const fill = (s) => s.querySelectorAll('image[data-img]').forEach(img => {
    const uri = images[img.getAttribute('data-img')];
    if (uri) { img.setAttribute('href', ''); img.setAttribute('href', uri); }  // (re)assign: GIFs restart
  });
  const pos = document.getElementById('pos'), help = document.getElementById('help');
  let i = Math.min(slides.length - 1, Math.max(0, (parseInt(location.hash.slice(1), 10) || 1) - 1));
  const show = (n) => {
    i = Math.min(slides.length - 1, Math.max(0, n));
    slides.forEach((s, k) => s.classList.toggle('active', k === i));
    pos.textContent = i + 1;
    history.replaceState(null, '', '#' + (i + 1));
    fill(slides[i]);
    if (slides[i + 1]) fill(slides[i + 1]);  // pre-assign the next slide
  };
  const next = () => show(i + 1), prev = () => show(i - 1);
  addEventListener('keydown', (e) => {
    if (['ArrowRight', ' ', 'PageDown', 'ArrowDown'].includes(e.key)) { e.preventDefault(); next(); }
    else if (['ArrowLeft', 'PageUp', 'ArrowUp', 'Backspace'].includes(e.key)) { e.preventDefault(); prev(); }
    else if (e.key === 'Home') show(0);
    else if (e.key === 'End') show(slides.length - 1);
    else if (e.key === 'f') (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen());
    else if (e.key === '?') help.classList.toggle('show');
    else if (e.key === 'Escape') help.classList.remove('show');
  });
  document.getElementById('deck').addEventListener('click', (e) => (e.clientX < innerWidth / 5 ? prev() : next()));
  let x0 = null;
  addEventListener('touchstart', (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  addEventListener('touchend', (e) => { if (x0 === null) return; const dx = e.changedTouches[0].clientX - x0; if (Math.abs(dx) > 40) (dx < 0 ? next() : prev()); x0 = null; });
  addEventListener('hashchange', () => show((parseInt(location.hash.slice(1), 10) || 1) - 1));
  show(i);
})();
</script>
</body>
</html>
"""


def _hoist_images(svgs: list[str]) -> tuple[list[str], dict[str, str]]:
    """Replace every embedded image's data URI with a key; the bytes live once in a JSON
    lookup and are assigned when the slide is shown. Halves the file for decks with
    build steps and lets GIFs restart from frame 0 on each showing."""
    lookup: dict[str, str] = {}
    keys: dict[str, str] = {}
    # Typst writes `xlink:href`; match the namespaced and the plain form.
    pattern = re.compile(r'(?:xlink:)?href="(data:image/[a-z+.-]+;base64,[A-Za-z0-9+/=]+)"')

    def repl(m: re.Match) -> str:
        uri = m.group(1)
        key = keys.get(uri)
        if key is None:
            key = "i" + hashlib.sha1(uri.encode()).hexdigest()[:10]
            keys[uri] = key
            lookup[key] = uri
        return f'data-img="{key}"'

    return [pattern.sub(repl, svg) for svg in svgs], lookup


def export_html(main: Path, out: Path, handout: bool, title: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        pattern = Path(tmp) / "slide-{0p}.svg"
        cmd = ["typst", "compile", "--root", str(REPO_ROOT), "--format", "svg"]
        if handout:
            cmd += ["--input", "handout=true"]
        cmd += [str(main), str(pattern)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=REPO_ROOT)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip()[:2000])
        files = sorted(Path(tmp).glob("slide-*.svg"))
        svgs = [f.read_text(encoding="utf-8") for f in files]
    # Strip XML prologs; give each SVG a viewBox-preserving size handled by CSS.
    svgs = [re.sub(r"^<\?xml[^>]*\?>\s*", "", s) for s in svgs]
    svgs = [re.sub(r'<svg([^>]*?)\s(width|height)="[^"]*"', r"<svg\1", s, count=2) for s in svgs]
    gifs = sum(s.count("data:image/gif") for s in svgs)
    svgs, lookup = _hoist_images(svgs)
    sections = "\n".join(
        f'<section class="slide" aria-label="Slide {i}" role="img">{svg}</section>' for i, svg in enumerate(svgs, 1)
    )
    import json

    html = (_TEMPLATE.replace("__TITLE__", title).replace("__N__", str(len(svgs)))
            .replace("__SLIDES__", sections).replace("__IMAGES__", json.dumps(lookup)))
    out.write_text(html, encoding="utf-8")
    return {"slides": len(svgs), "bytes": out.stat().st_size, "gif_embeds": gifs, "unique_images": len(lookup)}
