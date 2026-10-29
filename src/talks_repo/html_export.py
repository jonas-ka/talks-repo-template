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
import io
import re
import subprocess
import tempfile
from pathlib import Path

from talks_repo import REPO_ROOT, rev_inputs

# Longest side of an embedded raster: a half-slide figure on a 4K screen. Larger PNG/JPEG
# images are scaled down; GIFs stay untouched (they may be animated).
MAX_PX = 1800
JPEG_QUALITY = 85

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
  .slide { position: relative; }
  .slide > svg { width: 100%; height: 100%; display: block; }
  .widget { position: absolute; }
  #hud { position: fixed; right: 12px; bottom: 8px; color: #bbb; font-size: 13px; opacity: .7; user-select: none; }
  #help { position: fixed; left: 50%; top: 50%; transform: translate(-50%,-50%); background: #2c2c2e; color: #eee;
          padding: 18px 24px; border-radius: 10px; display: none; line-height: 1.6; box-shadow: 0 0 30px rgba(0,0,0,.7); }
  #help.show { display: block; }
  kbd { background: #444; border-radius: 4px; padding: 0 6px; }
  .pretalk { position: absolute; inset: 0; pointer-events: none; }
  .pt-item { position: absolute; inset: 0; background: #fff; opacity: 0; transition: opacity .8s; display: flex;
             flex-direction: column; align-items: center; justify-content: center; padding: 3% 4% 2%; box-sizing: border-box; }
  .pt-item.show { opacity: 1; }
  .pt-item img { flex: 1; min-height: 0; max-width: 100%; object-fit: contain; }
  .pt-item p { margin: 1.2% 0 0; font: 2.2vmin/1.3 'STIX Two Text', Georgia, serif; color: #000; text-align: center; }
</style>
</head>
<body>
<div id="deck">
__SLIDES__
</div>
<div id="hud"><span id="pos">1</span> / __N__</div>
<div id="help"><b>__TITLE__</b><br>
<kbd>→</kbd> <kbd>space</kbd> <kbd>click</kbd> next &nbsp; <kbd>←</kbd> previous &nbsp; <kbd>Home</kbd>/<kbd>End</kbd> first/last<br>
<kbd>f</kbd> fullscreen &nbsp; <kbd>l</kbd> pre-talk loop on the title slide &nbsp; <kbd>?</kbd> this help</div>
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
  // Pre-talk loop (brief `pretalk:`): on slide 1 the title alternates with pictures until the first
  // key or click, which stops the loop on the title; `l` starts it again.
  const pt = document.getElementById('pretalk');
  const ptItems = pt ? Array.from(pt.querySelectorAll('.pt-item')) : [];
  let ptOn = false, ptTimer = null;
  const ptStop = () => { ptOn = false; clearTimeout(ptTimer); ptItems.forEach(x => x.classList.remove('show')); };
  const ptStart = () => {
    if (!ptItems.length) return;
    ptStop(); ptOn = true;
    let k = 0;
    const title = () => { ptItems.forEach(x => x.classList.remove('show'));
                          ptTimer = setTimeout(item, 1000 * (+pt.dataset.title || 12)); };
    const item = () => {
      if (!ptOn) return;
      const it = ptItems[k], img = it.querySelector('img');
      const uri = img.getAttribute('src'); img.setAttribute('src', ''); img.setAttribute('src', uri);  // GIFs restart
      it.classList.add('show');
      k = (k + 1) % ptItems.length;
      ptTimer = setTimeout(() => { if (ptOn) title(); }, 1000 * (+it.dataset.s || 8));
    };
    title();
  };
  let i = Math.min(slides.length - 1, Math.max(0, (parseInt(location.hash.slice(1), 10) || 1) - 1));
  const show = (n) => {
    i = Math.min(slides.length - 1, Math.max(0, n));
    if (i !== 0) ptStop();
    slides.forEach((s, k) => s.classList.toggle('active', k === i));
    pos.textContent = i + 1;
    history.replaceState(null, '', '#' + (i + 1));
    fill(slides[i]);
    if (slides[i + 1]) fill(slides[i + 1]);  // pre-assign the next slide
  };
  const next = () => show(i + 1), prev = () => show(i - 1);
  addEventListener('keydown', (e) => {
    if (ptOn && !['f', '?', 'Escape'].includes(e.key)) { e.preventDefault(); ptStop(); return; }
    if (e.key === 'l') { if (i === 0) ptStart(); return; }
    if (['ArrowRight', ' ', 'PageDown', 'ArrowDown'].includes(e.key)) { e.preventDefault(); next(); }
    else if (['ArrowLeft', 'PageUp', 'ArrowUp', 'Backspace'].includes(e.key)) { e.preventDefault(); prev(); }
    else if (e.key === 'Home') show(0);
    else if (e.key === 'End') show(slides.length - 1);
    else if (e.key === 'f') (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen());
    else if (e.key === '?') help.classList.toggle('show');
    else if (e.key === 'Escape') help.classList.remove('show');
  });
  document.getElementById('deck').addEventListener('click', (e) => (ptOn ? ptStop() : e.clientX < innerWidth / 5 ? prev() : next()));
  let x0 = null;
  addEventListener('touchstart', (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  addEventListener('touchend', (e) => { if (x0 === null) return; const dx = e.changedTouches[0].clientX - x0; if (Math.abs(dx) > 40) (dx < 0 ? next() : prev()); x0 = null; });
  addEventListener('hashchange', () => show((parseInt(location.hash.slice(1), 10) || 1) - 1));
  show(i);
  if (i === 0) ptStart();
})();
</script>
</body>
</html>
"""


_NESTED = re.compile(r'((?:xlink:)?href=")(data:image/(?:png|jpeg|jpg);base64,[A-Za-z0-9+/=\s]+)(")')


def _shrink(uri: str) -> str:
    """Scale a PNG/JPEG data URI down to MAX_PX and re-encode it; keep whichever is smaller.
    Opaque images may become JPEG, images with transparency lossy WebP; rasters embedded in an
    SVG figure are treated the same way."""
    if uri.startswith("data:image/svg+xml;base64,"):
        svg = base64.b64decode(uri.split(",", 1)[1]).decode("utf-8", errors="replace")
        small = _NESTED.sub(lambda m: m.group(1) + _shrink(re.sub(r"\s", "", m.group(2))) + m.group(3), svg)
        return uri if len(small) >= len(svg) else "data:image/svg+xml;base64," + base64.b64encode(small.encode()).decode()
    m = re.match(r"data:image/(png|jpeg|jpg);base64,(.*)", uri, re.S)
    if not m:
        return uri
    from PIL import Image

    raw = base64.b64decode(m.group(2))
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:
        return uri
    if max(img.size) > MAX_PX:
        img.thumbnail((MAX_PX, MAX_PX), Image.LANCZOS)
    alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
    if alpha and img.mode == "RGBA" and img.getchannel("A").getextrema()[0] == 255:
        alpha = False
    candidates = []
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    candidates.append(("png", buf.getvalue()))
    if alpha:
        buf = io.BytesIO()
        img.convert("RGBA").save(buf, format="WEBP", quality=JPEG_QUALITY, method=6)
        webp = buf.getvalue()
        if len(webp) < 0.5 * len(candidates[0][1]):
            candidates.append(("webp", webp))
    else:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        jpg = buf.getvalue()
        # Plots and diagrams (few colours) stay PNG unless JPEG is much smaller: no ringing on lines.
        if m.group(1) != "png" or len(jpg) < 0.5 * len(candidates[0][1]):
            candidates.append(("jpeg", jpg))
    fmt, data = min(candidates, key=lambda c: len(c[1]))
    if len(data) >= len(raw):
        return uri
    return f"data:image/{fmt};base64," + base64.b64encode(data).decode()


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
            lookup[key] = _shrink(uri)
        return f'data-img="{key}"'

    return [pattern.sub(repl, svg) for svg in svgs], lookup


def _scope_ids(svg: str, prefix: str) -> str:
    """Prefix every id in one slide's SVG and the references to it. All slides share one HTML
    document, and a `url(#x)` or `href="#x"` resolves to the first element with that id in the
    document, often on another slide: clips (e.g. the cut information strip) and glyphs break."""
    ids = set(re.findall(r'(?<=\s)id="([^"]+)"', svg))
    if not ids:
        return svg
    svg = re.sub(r'(?<=\s)id="([^"]+)"', lambda m: f'id="{prefix}{m.group(1)}"', svg)
    svg = re.sub(r'url\(#([^)]+)\)', lambda m: f"url(#{prefix}{m.group(1)})" if m.group(1) in ids else m.group(0), svg)
    return re.sub(r'((?:xlink:)?href)="#([^"]+)"',
                  lambda m: f'{m.group(1)}="#{prefix}{m.group(2)}"' if m.group(2) in ids else m.group(0), svg)


def _widgets(main: Path, handout: bool, inputs: list[str] | None = None) -> dict[int, list[dict]]:
    """Interactive regions marked in the deck (`html-widget` in a block: metadata labelled
    <html-widget> with id, page and box in pt), by page number."""
    import json

    cmd = ["typst", "query", "--root", str(REPO_ROOT), *rev_inputs(), *(inputs or [])]
    if handout:
        cmd += ["--input", "handout=true"]
    cmd += [str(main), "<html-widget>", "--field", "value"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=REPO_ROOT)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[:2000])
    out: dict[int, list[dict]] = {}
    for w in json.loads(result.stdout or "[]"):
        out.setdefault(int(w["page"]), []).append(w)
    return out


def _brief_json(path: Path) -> str:
    """The brief fields a widget may use, as JSON safe inside a <script> element."""
    import json

    import yaml

    brief = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    keep = {k: brief.get(k) for k in ("title", "event", "date", "location", "venue") if brief.get(k) is not None}
    return json.dumps(keep, default=str).replace("<", "\\u003c")


def _overlay(svg: str, widgets: list[dict], brief_json: str = "null") -> str:
    """HTML laid over the slide's SVG at each widget's box (percent of the page). `__BRIEF__` in a
    widget becomes a few fields of the talk's brief.yaml (JSON)."""
    m = re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"', svg)
    if not m:
        return ""
    pw, ph = float(m.group(1)), float(m.group(2))
    parts = []
    for w in widgets:
        src = REPO_ROOT / "assets" / "interactive" / f"{w['id']}.html"
        if not src.exists():
            raise FileNotFoundError(f"html-widget {w['id']!r}: {src} is missing")
        style = (f"left:{100 * w['x'] / pw:.3f}%;top:{100 * w['y'] / ph:.3f}%;"
                 f"width:{100 * w['w'] / pw:.3f}%;height:{100 * w['h'] / ph:.3f}%")
        parts.append(f'<div class="widget" style="{style}">{src.read_text(encoding="utf-8").replace("__BRIEF__", brief_json)}</div>')
    return "".join(parts)


def _pretalk(path: Path) -> str:
    """The pre-talk loop laid over slide 1, from the brief's `pretalk:` (title seconds and a list of
    pictures: `asset:` a catalog id or `file:` a repository path, with `caption`, `alt`, `s`)."""
    import html as _html
    import mimetypes

    import yaml

    brief = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    spec = brief.get("pretalk") or {}
    if not spec.get("items"):
        return ""
    catalog = {e["id"]: e for e in yaml.safe_load((REPO_ROOT / "assets" / "catalog.yaml").read_text(encoding="utf-8"))}
    parts = []
    for it in spec["items"]:
        entry = catalog.get(it.get("asset"), {})
        rel = it.get("file") or ("assets/" + entry["file"] if entry.get("file") else None)
        if not rel or not (REPO_ROOT / rel).exists():
            raise FileNotFoundError(f"pretalk item {it}: no file")
        alt = it.get("alt") or entry.get("alt")
        if not alt:
            raise ValueError(f"pretalk item {it}: no alt text")
        mime = mimetypes.guess_type(rel)[0] or "image/png"
        uri = f"data:{mime};base64," + base64.b64encode((REPO_ROOT / rel).read_bytes()).decode()
        if mime != "image/gif":
            uri = _shrink(uri)
        caption = it.get("caption") or entry.get("caption") or ""
        parts.append(f'<div class="pt-item" data-s="{float(it.get("s", 8))}"><img src="{uri}" alt="{_html.escape(alt)}">'
                     f'<p>{_html.escape(caption)}</p></div>')
    return f'<div class="pretalk" id="pretalk" data-title="{float(spec.get("title_s", 12))}">{"".join(parts)}</div>'


def export_html(main: Path, out: Path, handout: bool, title: str, inputs: list[str] | None = None) -> dict:
    """`inputs`: extra typst inputs, e.g. the widget snapshots shown under the live widgets."""
    with tempfile.TemporaryDirectory() as tmp:
        pattern = Path(tmp) / "slide-{0p}.svg"
        cmd = ["typst", "compile", "--root", str(REPO_ROOT), "--format", "svg", *rev_inputs(), *(inputs or [])]
        if handout:
            cmd += ["--input", "handout=true"]
        cmd += [str(main), str(pattern)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=REPO_ROOT)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip()[:2000])
        files = sorted(Path(tmp).glob("slide-*.svg"))
        svgs = [f.read_text(encoding="utf-8") for f in files]
    widgets = _widgets(main, handout, inputs)
    brief_json = _brief_json(main.parent / "brief.yaml")
    overlays = [_overlay(s, widgets.get(i, []), brief_json) for i, s in enumerate(svgs, 1)]
    if overlays and not handout:
        overlays[0] += _pretalk(main.parent / "brief.yaml")
    # Strip XML prologs; give each SVG a viewBox-preserving size handled by CSS.
    svgs = [re.sub(r"^<\?xml[^>]*\?>\s*", "", s) for s in svgs]
    svgs = [re.sub(r'<svg([^>]*?)\s(width|height)="[^"]*"', r"<svg\1", s, count=2) for s in svgs]
    svgs = [_scope_ids(s, f"s{i}-") for i, s in enumerate(svgs, 1)]
    gifs = sum(s.count("data:image/gif") for s in svgs)
    svgs, lookup = _hoist_images(svgs)
    sections = "\n".join(
        f'<section class="slide" aria-label="Slide {i}" role="img">{svg}{ov}</section>'
        for i, (svg, ov) in enumerate(zip(svgs, overlays), 1)
    )
    import json

    html = (_TEMPLATE.replace("__TITLE__", title).replace("__N__", str(len(svgs)))
            .replace("__SLIDES__", sections).replace("__IMAGES__", json.dumps(lookup)))
    out.write_text(html, encoding="utf-8")
    return {"slides": len(svgs), "bytes": out.stat().st_size, "gif_embeds": gifs, "unique_images": len(lookup)}
