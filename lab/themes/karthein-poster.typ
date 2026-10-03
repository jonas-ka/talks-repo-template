// Karthein Lab poster theme (A0 portrait by default), matching the slide theme's palette,
// fonts and diagrams. First used for the Your University System AI Research & Innovation Meeting
// poster (talks/2026-10-tamus-ai-poster).
//
// Usage (talks/<slug>/poster.typ):
//   #import "/themes/karthein-poster.typ": *
//   #show: poster.with(title: "…")                       // page, fonts, heading styles
//   #poster-header(title: […], subtitle: […], authors: […], collaborators: […])   // logos: one visible height, centred
//   #card-row(columns: (1fr, 1fr), sec[…][…], sec[…][…])   // cards with aligned edges
//   #v(poster-gutter)
//   #card-row(columns: (1fr,), sec[…][…])                     // a full-width band
//   #poster-footer(acknowledgements: […])
//
// Compile from the repo root (accessible PDF, like the decks):
//   typst compile --root . --pdf-standard ua-1 talks/<slug>/poster.typ talks/<slug>/<Name>.pdf
//
// Rules of thumb for A0 (841 x 1189 mm), read at 1-2 m:
// - body 30 pt, captions and notes 24 pt, section titles 50 pt, title ~100 pt; nothing
//   below ~20 pt. The slide theme's figure captions are 11 pt, so use `pfig`, not a
//   `cat-fig` caption.
// - Vector wherever a source exists: text, Typst diagrams, SVG plots, SVG logos
//   (themes/logos/*.svg). Photos stay raster (>= 2000 px wide). Tagged PDF (UA-1) refuses
//   embedded PDF images: convert a PDF logo or figure to SVG with PyMuPDF first.
// - Slide diagrams (Typst functions in blocks/) are reused by import and scaled with
//   `fit`; give them their slide base size (`text(size: 14pt, …)`) so scaled labels do not
//   inherit the poster's 30 pt.
// - Sections are unbreakable blocks: if a row does not fit, the whole row moves to a new
//   page. Compile and check the page count after every change (one page expected).
// - Rows are `card-row`s: every card in a row gets the row's height (top and bottom edges
//   aligned, stacked cards share the extra), and every gap is `poster-gutter`.

#import "/themes/karthein.typ": ink, muted, band, brand, panel, fill-color, line-color, text-color, radius, logos, cat-fig, fig, asset, superseded

#let poster-margin = 28mm
/// One gap for the whole poster: below the header, between columns, rows, stacked cards
/// and above the footer.
#let poster-gutter = 18mm

/// Page, fonts, lists and heading styles for an A0 portrait poster.
#let poster(title: "", author: "Your Name", width: 841mm, height: 1189mm, body) = {
  set document(title: title, author: author)
  set text(font: ("STIX Two Text", "Helvetica Neue"), size: 30pt, fill: ink, lang: "en")
  show math.equation: set text(font: "STIX Two Math")
  set par(leading: 0.55em, justify: false)
  set list(marker: text(fill: brand, [●]), indent: 4pt, body-indent: 14pt, spacing: 0.7em)
  set page(width: width, height: height, margin: (x: poster-margin, top: 0mm, bottom: 12mm))
  show heading.where(level: 2): it => block(below: 14pt, it.body)
  body
}

/// Grey header band across the full page width: title (the document's level-1 heading),
/// subtitle, authors, collaborators; logos stacked on the right.
#let poster-header(
  title: [], subtitle: none, authors: [], collaborators: none,
  logo-height: 22mm,
  logo-width: 120mm,
  logo-fit: "height",   // "height": one visible height (default); "width": one width
  // (path, alt, visible fraction): the visible mark of each logo is drawn `logo-height`
  // tall; the third value is how much of the file's height the mark occupies (measured),
  // so files with internal padding are scaled up to match.
  logos-right: (
    ("/themes/logos/cyclotron-institute.svg", "Your University Your Institute logo", 0.77),
    ("/themes/logos/karthein-lab-sticker.svg", "Karthein Lab, Your University logo", 0.92),
    ("/themes/logos/doe.png", "U.S. Department of Energy logo", 1.0),
    ("/themes/logos/genesis-mission.png", "Genesis Mission logo", 0.99),
  ),
) = {
  block(width: 100%, inset: (top: 12mm, bottom: 9mm), outset: (x: poster-margin), fill: band, above: 0pt, below: 0pt, {
    grid(columns: (1fr, auto), column-gutter: 22mm, align: (left + horizon, right + horizon),
      {
        heading(level: 1, outlined: false, text(size: 104pt, weight: "bold", fill: ink, title))
        if subtitle != none { v(7mm); text(size: 56pt, fill: brand, subtitle) }
        v(6mm)
        text(size: 32pt, authors)
        if collaborators != none { v(1mm); text(size: 30pt, style: "italic", fill: muted, collaborators) }
      },
      // Logos: one common visible height, centred in the column.
      // The logo column is as wide as its widest logo; each logo is centred in it.
      align(center, stack(dir: ttb, spacing: 5mm, ..logos-right.map(((path, alt, fill)) => align(center,
        if logo-fit == "width" { image(path, width: logo-width, alt: alt) } else { image(path, height: logo-height / fill, alt: alt) })))),
    )
  })
  v(poster-gutter)   // the same gap as between the rows
}

/// Shadow styles for section cards, after the style guide's shadow tokens (offset, blur,
/// opacity) scaled ~3x for A0. Typst cannot blur, so a shadow is `layers` translucent
/// rounded rectangles of growing size and falling opacity.
#let shadow-styles = (
  "none": none,
  sm:    (dx: 0pt, dy: 3pt,  blur: 6pt,  alpha: 10%),
  smd:   (dx: 0pt, dy: 4pt,  blur: 14pt, alpha: 11%),   // between sm and md, nearly centred
  smd-off: (dx: 0pt, dy: 9pt, blur: 14pt, alpha: 11%), // the same, shifted down: 5 pt above, 23 pt below (default)
  md:    (dx: 0pt, dy: 6pt,  blur: 24pt, alpha: 12%),
  lg:    (dx: 0pt, dy: 36pt, blur: 96pt, alpha: 14%),
  side:  (dx: 12pt, dy: 12pt, blur: 12pt, alpha: 12%),   // offset to the lower right
  hard:  (dx: 8pt, dy: 8pt,  blur: 0pt,  alpha: 18%),    // one flat drop shadow
)
#let card-inset = 8mm
#let soft-shadow(w, h, spec, radius: radius.lg, layers: 16) = {
  if spec == none { return none }
  let ink-shadow = rgb("#1A1A18")
  if spec.blur == 0pt {
    place(top + left, dx: spec.dx, dy: spec.dy, rect(width: w, height: h, radius: radius, fill: ink-shadow.transparentize(100% - spec.alpha), stroke: none))
  } else {
    for i in range(layers) {
      let f = (i + 1) / layers                 // 1/layers … 1
      let grow = spec.blur * (1 - f)          // outermost layer first, faintest
      let a = spec.alpha / layers * 1.6
      place(top + left, dx: spec.dx - grow, dy: spec.dy - grow,
        rect(width: w + 2 * grow, height: h + 2 * grow, radius: radius + grow, fill: ink-shadow.transparentize(100% - a), stroke: none))
    }
  }
}

/// A hairline border for section cards (the style chosen in the 2026-09-29 trial,
/// together with the `smd-off` shadow).
#let hairline = 1.5pt + band.darken(30%)

/// The inside of a section card: maroon title, grey rule, content.
#let section-inner(title, body) = {
  heading(level: 2, text(size: 50pt, weight: "bold", fill: brand, title))
  v(4pt)   // the rule stays clear of the descenders
  line(length: 100%, stroke: 2pt + band.darken(25%))
  v(12pt)
  body
}

/// A white card of a given width (and height, or its natural height) with a shadow
/// (`style`: a key of `shadow-styles`), a `border`, and an optional `tag` (style trials).
#let card(inner, width, height: auto, style: "smd-off", border: hairline, tag: none) = {
  let content = block(width: width, height: height, inset: card-inset, radius: radius.lg, fill: white,
    stroke: if border == none { none } else { border }, inner)
  let h = if height == auto { measure(content).height } else { height }
  box(width: width, height: h, {
    soft-shadow(width, h, shadow-styles.at(style))
    place(top + left, content)
    if tag != none {
      place(top + right, dx: -6mm, dy: 5mm, box(inset: (x: 5pt, y: 3pt), radius: radius.sm, fill: band,
        text(size: 20pt, fill: muted, tag)))
    }
  })
}

/// A titled section on its own: a card as tall as its content, never split across a page.
/// For sections side by side use `card-row`, which aligns their top and bottom edges.
#let section(title, body, framed: true, style: "smd-off", border: hairline, tag: none) = {
  if not framed {
    return block(width: 100%, breakable: false, above: 0pt, below: 0pt, section-inner(title, body))
  }
  block(width: 100%, breakable: false, above: 0pt, below: 0pt,
    layout(sz => card(section-inner(title, body), sz.width, style: style, border: border, tag: tag)))
}

/// A section for `card-row`: title and body, sized by the row.
#let sec(title, body) = (title: title, body: body)

/// A row of section cards with aligned top and bottom edges. `columns` are fractions; each
/// positional cell is one `sec(...)` or an array stacked in that column, whose entries are
/// either a `sec(...)`, an array of `sec(...)`s set side by side in equal widths (a sub-row,
/// as tall as its tallest card), or `sub-row(columns: (..), ..secs)` for unequal widths. Every card is measured at its width, the tallest cell sets
/// the row height, and a column with several entries shares the extra height equally between
/// them, so every column ends on the same line. All gaps are `gutter`.
/// A sub-row of sections side by side in a `card-row` column, with its own `columns` fractions.
#let sub-row(columns: none, ..secs) = (sub: secs.pos(), columns: columns)

#let card-row(columns: (1fr, 1fr), gutter: poster-gutter, style: "smd-off", border: hairline, ..cells) = {
  let cells = cells.pos().map(c => if type(c) == array { c } else { (c,) })
  // an array entry is a sub-row of equal widths
  cells = cells.map(cell => cell.map(e => if type(e) == array { (sub: e, columns: none) } else { e }))
  assert(cells.len() == columns.len(), message: "card-row: one cell per column")
  let natural(s, w) = measure(block(width: w, inset: card-inset, section-inner(s.title, s.body))).height
  let is-sub(e) = type(e) == dictionary and "sub" in e
  let sub-widths(e, w) = {
    let cols = if e.columns == none { e.sub.len() * (1fr,) } else { e.columns }
    let fr = cols.map(c => c / 1fr)
    let avail = w - gutter * (cols.len() - 1)
    fr.map(f => avail * f / fr.sum())
  }
  block(width: 100%, breakable: false, above: 0pt, below: 0pt, layout(sz => {
    let fr = columns.map(c => c / 1fr)
    let total = fr.sum()
    let avail = sz.width - gutter * (columns.len() - 1)
    let widths = fr.map(f => avail * f / total)
    // natural height of every entry at its width (a sub-row: its tallest card)
    let heights = cells.zip(widths).map(((cell, w)) => cell.map(e =>
      if is-sub(e) { calc.max(..e.sub.zip(sub-widths(e, w)).map(((s, sw)) => natural(s, sw))) } else { natural(e, w) }))
    let totals = heights.map(hs => hs.sum() + gutter * (hs.len() - 1))
    let row-h = calc.max(..totals)
    grid(columns: widths, column-gutter: gutter, align: top,
      ..cells.zip(widths, heights, totals).map(((cell, w, hs, tot)) => {
        let extra = (row-h - tot) / cell.len()
        stack(dir: ttb, spacing: gutter, ..cell.zip(hs).map(((e, h)) =>
          if is-sub(e) {
            let sws = sub-widths(e, w)
            grid(columns: sws, column-gutter: gutter,
              ..e.sub.zip(sws).map(((s, sw)) => card(section-inner(s.title, s.body), sw, height: h + extra, style: style, border: border)))
          } else {
            card(section-inner(e.title, e.body), w, height: h + extra, style: style, border: border)
          }))
      }),
    )
  }))
}

/// A big number with a short explanation, in a lab-palette panel (tone: blue, red, yellow, green).
/// `height: auto` fits the text; `stat-row` sets one height for a row of them.
#let stat(big, small, tone: "blue", height: auto) = box(width: 100%, height: height, inset: (x: 16pt, y: 18pt), radius: radius.lg,
  fill: panel.at(tone), stroke: 2pt + line-color.at(tone),
  align(center + horizon)[#text(size: 58pt, weight: "bold", fill: text-color.at(tone), big) \ #v(-6pt) #text(size: 25pt, small)])

/// A row of equal-width stat panels of equal height: each positional item is
/// `(big, small, tone)`; the tallest panel at the column width sets the height of all.
#let stat-row(gutter: 10mm, ..items) = layout(sz => {
  let items = items.pos()
  let w = (sz.width - gutter * (items.len() - 1)) / items.len()
  let h = calc.max(..items.map(((big, small, tone)) => measure(box(width: w, stat(big, small, tone: tone))).height))
  grid(columns: items.len() * (1fr,), column-gutter: gutter,
    ..items.map(((big, small, tone)) => stat(big, small, tone: tone, height: h)))
})

/// Caption or side note at poster size.
#let note(body) = text(size: 24pt, style: "italic", fill: muted, body)

/// A catalog figure with a poster-size caption.
#let pfig(id, h, cap) = stack(spacing: 6pt, cat-fig(id, max-height: h), align(center, note(cap)))

/// A catalog photo cropped to a fixed frame (full column width, `h` tall, `fit: "cover"`),
/// so photos placed side by side in equal columns get exactly the same size and aspect.
/// The photo of `pphoto` without its caption (for a caption set wider than the photo).
#let pphoto-only(id, h) = {
  let e = asset(id)
  assert(id not in superseded, message: "asset " + id + " is superseded; use its successor")
  box(width: 100%, height: h, radius: radius.sm, clip: true,
    image("/assets/" + e.file, width: 100%, height: 100%, fit: "cover", alt: e.alt))
}

#let pphoto(id, h, cap) = {
  let e = asset(id)
  assert(id not in superseded, message: "asset " + id + " is superseded; use its successor")
  stack(spacing: 6pt,
    box(width: 100%, height: h, radius: radius.sm, clip: true,
      image("/assets/" + e.file, width: 100%, height: 100%, fit: "cover", alt: e.alt)),
    align(center, note(cap)))
}

/// Scale a slide-size diagram to the available width (never above `limit`).
#let fit(body, limit: 3.0) = layout(size => {
  let m = measure(body)
  let f = calc.min(size.width / m.width, limit)
  scale(f * 100%, reflow: true, body)
})

/// Footer: rule; the occasion and the acknowledgements on the left, website and e-mail on
/// the right. It follows the last row at `poster-gutter`, like every other gap; whatever
/// height is left becomes the bottom margin (design the page so it ends near the side
/// margin). If the body is too tall the whole footer moves to a second page, never a
/// split line.
#let poster-footer(event: none, acknowledgements: [], website: "lab.example.edu", contact: "you@example.edu") = {
  v(poster-gutter)
  block(width: 100%, breakable: false, above: 0pt, below: 0pt, {
    set text(size: 22pt)
    set par(leading: 0.4em, spacing: 4mm)
    line(length: 100%, stroke: 2pt + band.darken(25%))
    v(3mm)
    grid(columns: (1fr, auto), column-gutter: 20mm, align: (left + horizon, right + horizon),
      {
        if event != none { par(text(fill: ink, event)) }
        par(text(fill: muted)[*Acknowledgements:* #acknowledgements])
      },
      align(right, text(weight: "bold", {
        if website != none { link("https://" + website, website); linebreak() }
        link("mailto:" + contact, contact)
      })),
    )
  })
}
