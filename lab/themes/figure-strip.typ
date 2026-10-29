// The information strip that `matplotlib/labfig.py` saves below a figure (who made it, when,
// with which template, where it lives) is for the file, not for the document: the themes cut
// it off. A catalog entry can say how tall its strip is (`info_strip: 0.4`, inches at the file's
// natural size); otherwise the strip is found in the SVG itself (`detect-strip`). Files
// without a strip are shown whole, as before.

/// The image at `path` without its bottom `strip` (a length at the file's natural size), as
/// large as fits in `width` x `height` (each a length, ratio, relative length, or auto),
/// keeping its aspect ratio.
#let strip-image(path, strip: 0pt, alt: none, width: auto, height: auto) = layout(size => {
  let nat = measure(image(path))
  let (vw, vh) = (nat.width, nat.height - strip)
  let resolve(v, full) = if v == auto { none } else if type(v) == ratio { full * v } else if type(v) == relative { v.length + full * v.ratio } else { v }
  let w = resolve(width, size.width)
  let h = resolve(height, size.height)
  let k = if w != none and h != none { calc.min(w / vw, h / vh) } else if w != none { w / vw } else if h != none { h / vh } else { 1.0 }
  // The image gets its full height explicitly: given only a width, Typst limits it to the clip
  // box's height and crops it centred ("cover"), cutting top and bottom instead of the strip.
  box(width: vw * k, height: vh * k, clip: true,
    place(top + left, image(path, width: nat.width * k, height: nat.height * k, fit: "stretch", alt: alt)))
})

/// The strip height found in an SVG file itself: labfig writes the marker
/// "labfig info_strip_in=0.4" into the file's metadata (since v2026.10.11); files from
/// v2026.10.10 carry no marker but link to the lab-templates repository in their strip.
/// Other files (and PDF or PNG files, which Typst cannot search) give 0pt.
#let detect-strip(path) = {
  if not lower(path).ends-with(".svg") { return 0pt }
  let s = read(path)
  let m = s.match(regex("labfig info_strip_in=([0-9.]+)"))
  if m != none { float(m.captures.at(0)) * 1in } else if s.contains("lab-templates/tree/") { 0.4in } else { 0pt }
}

/// The strip to cut: an explicit length, or `auto` = found in the file.
#let resolve-strip(path, strip) = if strip == auto { detect-strip(path) } else { strip }

/// The strip height of a catalog entry: its `info_strip` field, else `auto` (found in the file).
#let entry-strip(e) = if "info_strip" in e { e.info_strip * 1in } else { auto }
