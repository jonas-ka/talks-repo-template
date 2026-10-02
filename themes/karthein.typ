// Karthein Lab talk theme for Touying 0.6.x.
// Derived from the 2026 RadIs, NAMO and APS Global decks (see README.md, palette.yaml).
//
// Usage (talks/<slug>/main.typ):
//   #import "../../themes/karthein.typ": *
//   #show: karthein-theme.with(
//     config-info(title: [..], author: [..], date: [..], institution: [..]),
//     handout: false,   // true: one page per slide, no pause steps (posted PDFs)
//     sponsors: true,   // DOE + Genesis Mission logos in the footer
//   )
//   #title-slide(contents: ([Production], [Science Opportunities]))
//   == Slide title
//   ...
//
// Every new slide ends with a layout pass: render it, check that paragraphs and bullets
// have visible spacing (add `v()`/`block(below:)`; `set par(spacing: 0pt)` removes the
// default), that the body fills the page with no blank band above the footer and columns
// of similar height, and that figures and captions line up with the text. `talks layout`
// measures the blank band and the imbalance per page.
//
// Figure paths are root-relative ("/assets/figures/x.svg") because they are resolved
// inside this file. Compile from the repo root:
//   typst compile --root . --pdf-standard ua-1 talks/<slug>/main.typ

#import "@preview/touying:0.6.1": *

// Palette, panels, radii, `lifted`, `caption-line`: shared with the poster and notes themes.
#import "tokens.typ": *
// Spoken math: `speak(body)` drafts an equation's alt text; `eq(alt: auto)` uses it.
#import "speak-math.typ": speak, apply-alts, math-body, spoken-eq

// Sponsor logos in the footer only where a block asks for them (`#sponsors(true)`
// written by the generator before blocks with `// sponsors: true`).
#let sponsor-state = state("sponsors", false)
#let sponsors(on) = sponsor-state.update(on)

#let logos = (
  tamu: "logos/tamu-mark.png",
  cyclotron: "logos/cyclotron-institute.png",
  lab: "logos/karthein-lab.png",
  sponsors: "logos/doe-genesis.png",
)

// ---------------------------------------------------------------- helpers
/// A citation for the footer centre: #cite-line[Rickey ++ PRA 113, 042824 (2026)]
#let cite-line(body) = text(fill: link-text, size: 11pt, body)

/// A figure with mandatory alt text, from the catalog:
///   #fig("/assets/figures/x.svg", alt: "...", width: 60%)
/// It never grows taller than `max-height` (the slide body under the header is ~300pt),
/// so a tall figure scales down instead of pushing the slide onto a second page.
#let fig(path, alt: none, width: 100%, max-height: 290pt, caption: none) = {
  assert(alt != none, message: "every figure needs alt text (catalog `alt`)")
  // No `figure` element: slides need no figure numbers, and numbered figures inside
  // pause steps keep Typst's layout from converging.
  block(width: width, {
    box(width: 100%, height: max-height, image(path, width: 100%, height: 100%, fit: "contain", alt: alt))
    if caption != none {
      v(2pt)
      align(center, text(size: 11pt, style: "italic", fill: muted, caption))
    }
  })
}

// ---------------------------------------------------------------- comparison tables
/// Coloured verdict marks for comparison tables: `mark("yes")`, `mark("no")`, `mark("part")`.
#let mark(kind) = {
  let (sym, col) = (yes: ("✓", text-color.green), no: ("✗", text-color.red), part: ("~", text-color.yellow)).at(kind)
  text(weight: "bold", fill: col, sym)
}

/// A comparison table: first column = row labels (bold), header row in brand colour,
/// hairline rules, small type. `highlight` = row indices (0-based, data rows) tinted;
/// `strong-row` = indices set in bold (totals). Cells are plain content; use `mark(...)`.
#let cmp-table(header, rows, columns: auto, size: 12pt, inset: (x: 7pt, y: 7pt), highlight: (), strong-row: (), highlight-fill: panel.blue) = {
  let ncol = header.len()
  let cols = if columns == auto { (1.1fr,) + (1fr,) * (ncol - 1) } else { columns }
  set text(size: size)
  set par(leading: 0.45em, justify: false)
  table(
    columns: cols,
    inset: inset,
    align: left + horizon,
    stroke: (x, y) => (bottom: 0.5pt + band.darken(20%)),
    fill: (x, y) => if y == 0 { band } else if (y - 1) in highlight { highlight-fill } else { none },
    table.header(..header.map(h => text(weight: "bold", fill: brand, h))),
    ..rows.enumerate().map(((i, r)) => r.enumerate().map(((j, c)) => {
      let c = if j == 0 { text(weight: "bold", c) } else { c }
      if i in strong-row { text(weight: "bold", c) } else { c }
    })).flatten(),
  )
}

/// A footnote line at the bottom of a slide body: small and muted.
#let footnote-line(body) = text(size: 9.5pt, fill: muted, body)

// ---------------------------------------------------------------- catalog access
// Blocks reference figures by catalog id. The catalog supplies the file (SVG twin for
// vector originals), the alt text, and the caption; superseded assets are refused at
// compile time (CLAUDE.md hard rule).
#let catalog = yaml("/assets/catalog.yaml")
#let superseded = catalog.filter(e => e.at("supersedes", default: none) != none).map(e => e.supersedes)

#let asset(id) = {
  let hits = catalog.filter(e => e.id == id)
  assert(hits.len() == 1, message: "catalog id not found: " + id)
  hits.first()
}

/// A catalog figure: #cat-fig("plot-charge-radii-oxygen-isotopes", width: 60%)
#let cat-fig(id, width: 100%, max-height: 290pt, caption: none) = {
  let e = asset(id)
  assert(id not in superseded, message: "asset " + id + " is superseded; use its successor")
  let path = e.at("svg", default: none)
  if path == none { path = e.at("file", default: none) }
  assert(path != none, message: "asset " + id + " has no file; run `talks generate` to materialize it")
  fig("/assets/" + path, alt: e.alt, width: width, max-height: max-height, caption: caption)
}

/// A catalog equation (LaTeX rendered through mitex, alt from the catalog):
///   #cat-eq("equation-6254f63972")
#let cat-eq(id, block: true) = {
  let e = asset(id)
  import "@preview/mitex:0.2.7": mitex, mi
  math.equation(block: block, alt: e.alt, if block { mitex(e.latex) } else { mi(e.latex) })
}

/// An equation with mandatory alt text: #eq(alt: "nu c equals ...")[$nu_c = ...$]
/// `alt: auto` takes the spoken form of the math (`speak` in speak-math.typ); check it.
#let eq(alt: none, block: true, body) = spoken-eq(alt: alt, block: block, body)

// ---------------------------------------------------------------- molecular Hamiltonian
// The effective molecular Hamiltonian used across the introduction: optional frame around
// the QED terms (green) or the hyperfine term (blue), and a scale row `scale-gap` below
// the equation. Every scale is a zero-size box placed under its term, so neither the
// frame nor the layout is disturbed by the row.
#let h-mol-scale-gap = 12pt
#let h-mol-alt = "The effective molecular Hamiltonian H mol equals H electronic plus H rotational plus H vibrational plus further terms plus H hyperfine plus H parity violating plus H C P violating. Typical energies in electronvolts: about 10 to the 0, about 10 to the minus 2, about 10 to the minus 5, about 10 to the minus 8, below 10 to the minus 12, below 10 to the minus 15."
#let h-mol-under(sub, sc, scales) = if scales {
  $attach(limits(H), br: #sub, b: #box(width: 0pt, height: 0pt, place(top + left, dx: -28pt, dy: h-mol-scale-gap, block(width: 60pt, align(center, text(size: 11pt, fill: ink-muted, sc))))))$
} else { $H_#sub$ }
#let h-mol-frame(body, color) = box(inset: (x: 5pt, y: 3pt), radius: radius.md, stroke: if color == none { none } else { 1.2pt + color }, body)
/// #h-mol(frame: "qed" | "hfs" | none, scales: true)
#let h-mol(frame: none, scales: false) = {
  let u(sub, sc) = h-mol-under(sub, sc, scales)
  let qed = $#u("e", $tilde.op 10^0$) + #u("rot", $tilde.op 10^(-2)$) + #u("vib", $tilde.op 10^(-5)$)$
  let hfs = u("HFS", $tilde.op 10^(-8)$)
  let unit = if scales { [#h(1.2em) #box(width: 0pt, height: 0pt, place(top + left, dy: h-mol-scale-gap, block(width: 40pt, text(size: 11pt, style: "italic", fill: ink-muted)[in eV])))] } else { none }
  eq(alt: h-mol-alt + if frame == "qed" { " The first three terms, the QED part, are framed in green." } else if frame == "hfs" { " The hyperfine term is framed in blue." } else { "" })[$
    H_"mol" = #h-mol-frame(qed, if frame == "qed" { line-color.green } else { none }) + dots + #h-mol-frame(hfs, if frame == "hfs" { line-color.blue } else { none })
    + #u("PV", $< 10^(-12)$) + #u("CPV", $< 10^(-15)$) #unit
  $]
}

// ---------------------------------------------------------------- slides
/// PDF/UA-1 wants the first heading of a document at level 1. The title slide provides
/// it; a deck without one (a single slide for a group meeting) gets it from its first
/// slide title instead.
#let h1-seen = state("h1-seen", false)

/// The slide header: title text (a level-2 heading, so it stays tagged) + A&M mark + rule.
#let slide-header(title) = {
  grid(
    columns: (1fr, auto),
    align: (left + horizon, right + horizon),
    // A real heading element (Touying hides its own copy), so the PDF outline stays tagged.
    // Slide titles are 18 pt whichever level they get (the level-1 show rule is 24 pt).
    context heading(level: if h1-seen.get() { 2 } else { 1 }, outlined: false, bookmarked: false, text(size: 18pt, title)),
    image(logos.tamu, height: 22pt, alt: "Your University mark"),
  )
  h1-seen.update(true)
  v(-4pt)
  line(length: 100%, stroke: 0.6pt + band.darken(20%))
  v(6pt)
}

#let slide(title: auto, footer-citation: none, ..args) = touying-slide-wrapper(self => {
  let info = self.info
  let header = none
  // Footer: a thin rule like the header, then email left, citation centred, sponsor logos
  // and page number right. Everything is placed at fixed positions so nothing moves
  // from slide to slide; the page number sits in a fixed-width box.
  let footer = pad(x: 18pt, stack(
    dir: ttb,
    spacing: 4pt,
    line(length: 100%, stroke: 0.6pt + band.darken(20%)),
    box(width: 100%, height: 16pt, {
      place(left + horizon, text(size: 11pt, weight: "bold", fill: ink, utils.call-or-display(self, info.email)))
      if footer-citation != none {
        // A long citation is scaled down rather than allowed to run into the email
        // on the left or the sponsor logos and page number on the right.
        place(center + horizon, context {
          let c = cite-line(footer-citation)
          let w = measure(c).width
          let maxw = 420pt
          if w > maxw { scale(maxw / w * 100%, reflow: true, c) } else { c }
        })
      }
      place(right + horizon, box(width: 24pt, align(right, context text(size: 11pt, weight: "bold", fill: ink, utils.slide-counter.display()))))
      if self.store.sponsors {
        place(right + horizon, dx: -34pt, context if sponsor-state.get() {
          image(logos.sponsors, height: 14pt, alt: "U.S. Department of Energy and Genesis Mission logos")
        })
      }
    }),
  ))
  // The header goes into the per-subslide preamble: it repeats on every pause step and
  // leaves positional bodies free for Touying's column composer.
  let preamble(self) = if title == auto {
    // Touying hands the slide its source headings; the `==` one is the slide title.
    let hs = self.at("headings", default: ()).filter(h => h.depth == 2)
    if hs.len() > 0 { slide-header(hs.last().body) } else { none }
  } else { slide-header(title) }
  let self = utils.merge-dicts(
    self,
    config-page(header: header, footer: footer, footer-descent: 10pt, margin: (top: 12pt, bottom: 36pt, x: 18pt)),
    config-common(subslide-preamble: preamble),
  )
  touying-slide(self: self, ..args)
})

#let title-slide(contents: (), ..args) = touying-slide-wrapper(self => {
  let info = self.info + args.named()
  let body = {
    set align(top + left)
    block(width: 100%, height: 58%, fill: band, inset: (x: 18pt, top: 44pt, bottom: 10pt), {
      grid(
        columns: (1fr, auto),
        column-gutter: 12pt,
        {
          // The deck title is the level-1 heading, so the tagged outline starts correctly.
          heading(level: 1, outlined: false, info.title)
          h1-seen.update(true)
          v(28pt)
          text(size: 14pt, weight: "bold", fill: ink, info.author + [ -- ] + info.institution)
          v(10pt)
          text(size: 13pt, style: "italic", fill: ink, info.date + if "event" in info and info.event != none { [ -- ] + info.event })
        },
        align(bottom + right, stack(
          dir: ttb, spacing: 8pt,
          image(logos.cyclotron, width: 180pt, alt: "Your University Your Institute logo"),
          image(logos.lab, width: 130pt, alt: "Karthein Lab, Your University logo"),
        )),
      )
    })
    if contents.len() > 0 {
      block(inset: (x: 18pt, top: 22pt), {
        text(size: 15pt, weight: "bold", [Content:])
        v(6pt)
        set text(size: 14pt)
        list(..contents)
      })
    }
  }
  let self = utils.merge-dicts(self, config-page(header: none, footer: none, margin: 0pt))
  touying-slide(self: self, body)
})

// ---------------------------------------------------------------- theme
#let karthein-theme(aspect-ratio: "16-9", handout: false, sponsors: false, email: [you\@example.edu], ..args, body) = {
  set document(title: "", author: "")  // overridden by the deck via config-info below
  set text(font: ("STIX Two Text", "Helvetica Neue"), size: 14pt, fill: ink, lang: "en")
  show math.equation: set text(font: "STIX Two Math")
  set par(leading: 0.6em)
  set list(marker: text(size: 9pt, [●]), indent: 6pt, body-indent: 10pt)
  show link: set text(fill: link-text)
  show heading.where(level: 1): it => text(size: 24pt, weight: "bold", fill: ink, it.body)
  show heading.where(level: 2): it => text(size: 18pt, weight: "bold", fill: ink, it.body)
  show: touying-slides.with(
    config-page(paper: "presentation-" + aspect-ratio, margin: 0pt),
    config-common(
      slide-fn: slide,
      handout: handout,
      datetime-format: "[month repr:short]. [day], [year]",
    ),
    config-store(sponsors: sponsors),
    config-info(email: email),
    config-methods(alert: (self: none, it) => text(weight: "bold", style: "italic", it)),
    ..args,
  )
  body
}
