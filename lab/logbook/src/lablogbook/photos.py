"""Photos and screenshots for the log book: metadata removed (a phone photo carries where it was
taken), and a large one scaled down so that it stays under the size limits."""

from __future__ import annotations

from pathlib import Path

RASTER = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff"}
LONG_SIDE = 2400          # pixels: plenty for a lab photo on screen and in the PDF


def prepare(path: Path, max_mb: float = 2.0) -> tuple[Path, str | None]:
    """Strip the metadata of a raster image in place; scale it down (and write a JPEG) when it is
    larger than `max_mb`. Returns the file (its name may change to .jpg) and what was done, or
    None when the file is not a raster image Pillow can read."""
    if path.suffix.lower() not in RASTER:
        return path, None
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return path, None
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)          # keep the orientation the camera recorded
            big = path.stat().st_size > max_mb * 1024 * 1024
            w, h = im.size
            if big and max(w, h) > LONG_SIDE:
                im.thumbnail((LONG_SIDE, LONG_SIDE))
            if im.mode not in ("RGB", "RGBA", "L", "LA"):
                im = im.convert("RGBA" if "A" in im.mode or im.mode == "P" else "RGB")
            # a new image from the pixels alone: no EXIF, GPS, maker notes or text chunks
            clean = Image.frombytes(im.mode, im.size, im.tobytes())
            out = path
            if big and path.suffix.lower() not in (".jpg", ".jpeg"):
                out = path.with_suffix(".jpg")
            if out.suffix.lower() in (".jpg", ".jpeg"):
                clean = clean.convert("RGB")
                clean.save(out, "JPEG", quality=85 if big else 92, optimize=True)
                # still too large (a very detailed picture): smaller steps until it fits
                for side, quality in ((2000, 80), (1600, 75), (1280, 70)):
                    if not big or out.stat().st_size <= max_mb * 1024 * 1024:
                        break
                    step = clean.copy()
                    step.thumbnail((side, side))
                    step.save(out, "JPEG", quality=quality, optimize=True)
            else:
                clean.save(out)
    except Exception:   # noqa: BLE001 - not an image after all: leave it to the checker
        return path, None
    if out != path:
        path.unlink(missing_ok=True)
    note = "metadata removed"
    if big:
        with Image.open(out) as done:
            note = f"scaled to {max(done.size)} px on the long side, {out.stat().st_size / 1e6:.1f} MB, metadata removed"
    return out, note
