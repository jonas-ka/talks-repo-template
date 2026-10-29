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
#import "figure-strip.typ": strip-image, entry-strip, resolve-strip
// Spoken math: `speak(body)` drafts an equation's alt text; `eq(alt: auto)` uses it.
#import "speak-math.typ": speak, apply-alts, math-body, spoken-eq

// Sponsor logos in the footer only where a block asks for them (`#sponsors(true)`
// written by the generator before blocks with `// sponsors: true`).
#let sponsor-state = state("sponsors", false)
#let sponsors(on) = sponsor-state.update(on)

// What built this deck, printed small on the title slide (the author, 2026-10-07): the version of the
// templates (lab-templates `VERSION`; in a consumer this file sits in lab/themes/, so
// `../VERSION` is lab/VERSION) and the git revision of the repository the deck was compiled
// from, passed as `--input rev=<git describe --always --dirty>` by `talks generate`.
#let template-version = read("../VERSION").trim()
#let build-rev = sys.inputs.at("rev", default: none)
#let build-line = {
  [#template-version]
  if build-rev != none [ · git #build-rev]
}

#let logos = (
  tamu: "/themes/logos/tamu-box.svg",   // the official maroon box (marcomm.tamu.edu logo downloads)
  cyclotron: "/themes/logos/cyclotron-institute.png",
  lab: "/themes/logos/karthein-lab.png",
  sponsors: "/themes/logos/doe-genesis.png",
)

// ---------------------------------------------------------------- helpers
// Footer citations (the author, 2026-10-23): one size everywhere, every reference linked (DOI, arXiv, repository or
// web page), references kept apart by a spaced middle dot, words as short as possible
// ("Data: Nörtershäuser (TU Darmstadt)", "Code: nuclear-chart-plotter"). A citation never shrinks:
// one longer than `cite-max` stops the build.
#let cite-size = 10pt
#let cite-max = (logos: 440pt, plain: 540pt)   // centred between the email and the sponsor logos or page number
#let cite-sep = [#h(0.75em)·#h(0.75em)]
/// A citation for the footer centre: #cite-line[Rickey ++ PRA 113, 042824 (2026)]
#let cite-line(body) = text(fill: link-text, size: cite-size, body)
/// Several references, kept apart: #refs(doi("10.1103/...")[Cao ++ PRC 102, 024311 (2020)], [...])
#let refs(..items) = items.pos().join(cite-sep)
/// A reference linked to its DOI: #doi("10.1038/nature12073")[Gaffney ++ Nature 497, 199 (2013)]
#let doi(id, body) = link("https://doi.org/" + id, body)
/// A preprint linked to arXiv: #arxiv("2605.09139")[Brinson ++ arXiv:2605.09139]
#let arxiv(id, body) = link("https://arxiv.org/abs/" + id, body)
// the words of a piece of content, for messages
#let plain(c) = if type(c) == str { c } else if type(c) != content { "" } else if c.has("text") { plain(c.text) } else if c.has("children") { c.children.map(plain).join() } else if c.has("body") { plain(c.body) } else if c.func() == [ ].func() { " " } else { "" }

/// A figure with mandatory alt text, from the catalog:
///   #fig("/assets/figures/x.svg", alt: "...", width: 60%)
/// It never grows taller than `max-height` (the slide body under the header is ~300pt),
/// so a tall figure scales down instead of pushing the slide onto a second page.
/// `strip`: the height of an information strip below the figure (labfig.py), cut off here;
/// `auto` finds it in the file (SVG), `0pt` keeps the file whole.
/// `photo`: the caption follows the photo rule (`captions` in tokens.typ); `caption-on` overrides it.
#let fig(path, alt: none, width: 100%, max-height: 290pt, caption: none, strip: auto, photo: false, caption-on: auto) = {
  let strip = resolve-strip(path, strip)
  assert(alt != none, message: "every figure needs alt text (catalog `alt`)")
  // No `figure` element: slides need no figure numbers, and numbered figures inside
  // pause steps keep Typst's layout from converging.
  block(width: width, {
    box(width: 100%, height: max-height, if strip > 0pt {
      align(center + horizon, strip-image(path, strip: strip, alt: alt, width: 100%, height: 100%))
    } else {
      image(path, width: 100%, height: 100%, fit: "contain", alt: alt)
    })
    if caption != none {
      context if caption-shown(photo, caption-on) {
        v(2pt)
        align(center, text(size: 11pt, style: "italic", fill: muted, caption))
      }
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
/// A photo (catalog `kind: photo`) takes its catalog caption unless given one; `caption: none` leaves it out.
#let cat-fig(id, width: 100%, max-height: 290pt, caption: auto, caption-on: auto) = {
  let e = asset(id)
  assert(id not in superseded, message: "asset " + id + " is superseded; use its successor")
  let photo = e.at("kind", default: none) == "photo"
  let caption = if caption == auto { if photo { e.at("caption", default: none) } } else { caption }
  let path = e.at("svg", default: none)
  if path == none { path = e.at("file", default: none) }
  assert(path != none, message: "asset " + id + " has no file; run `talks generate` to materialize it")
  fig("/assets/" + path, alt: e.alt, width: width, max-height: max-height, caption: caption, strip: entry-strip(e),
    photo: photo, caption-on: caption-on)
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

/// `footer-citation`: content, shown on every step of the slide, or a list of `(steps, content)`
/// pairs (steps as in `only`: 2, "2-", "1-3"), so a citation appears with the step that shows
/// what it cites (the author, 2026-10-20). Matching citations on one step are joined with `cite-sep`.
#let slide(title: auto, footer-citation: none, ..args) = touying-slide-wrapper(self => {
  let info = self.info
  let header = none
  let citation-at(sub) = if type(footer-citation) == array {
    let hits = footer-citation.filter(((steps, _)) => utils.check-visible(sub, steps)).map(((_, c)) => c)
    if hits.len() > 0 { hits.join(cite-sep) }
  } else { footer-citation }
  // Footer: a thin rule like the header, then email left, citation centred, sponsor logos
  // and page number right. Everything is placed at fixed positions so nothing moves
  // from slide to slide; the page number sits in a fixed-width box. A function of `self`, so
  // Touying draws it per step (`self.subslide`).
  let footer(self) = pad(x: 18pt, stack(
    dir: ttb,
    spacing: 4pt,
    line(length: 100%, stroke: 0.6pt + band.darken(20%)),
    box(width: 100%, height: 16pt, {
      if info.at("email", default: none) != none {
        place(left + horizon, text(size: 11pt, weight: "bold", fill: ink, utils.call-or-display(self, info.email)))
      }
      place(right + horizon, box(width: 24pt, align(right, context text(size: 11pt, weight: "bold", fill: ink, utils.slide-counter.display()))))
      if self.store.sponsors {
        place(right + horizon, dx: -34pt, context if sponsor-state.get() {
          image(logos.sponsors, height: 14pt, alt: "U.S. Department of Energy and Genesis Mission logos")
        })
      }
    }),
  ))
  // The citation is slide content, not part of the footer: the footer is a PDF artifact (not
  // read aloud, and PDF/UA-1 refuses links in it). It is placed at the footer's centre line,
  // 30.6 pt below the body, always at `cite-size`: one too long for `cite-max` fails the build.
  let citation-box(self) = {
    let citation = citation-at(self.subslide)
    if citation != none {
      place(bottom + center, dy: 30.6pt, box(height: 16pt, align(horizon, context {
        let c = cite-line(citation)
        let w = measure(c).width
        let maxw = if self.store.sponsors and sponsor-state.get() { cite-max.logos } else { cite-max.plain }
        assert(w <= maxw, message: "footer citation " + str(calc.round(w.pt())) + " pt wide, over "
          + str(maxw.pt()) + " pt; shorten it: " + plain(citation))
        c
      })))
    }
  }
  // The header goes into the per-subslide preamble: it repeats on every pause step and
  // leaves positional bodies free for Touying's column composer.
  let preamble(self) = citation-box(self) + if title == auto {
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
          v(40pt)
          // the presenter's honorific (default the author's); `honorific: none` in config-info for other presenters
          let hon = info.at("honorific", default: [Prof. Dr. ])
          text(size: 14pt, weight: "bold", fill: ink, (if hon != none { hon }) + info.author + [ -- ] + info.institution)
          v(10pt)
          text(size: 13pt, style: "italic", fill: ink, info.date + if "event" in info and info.event != none { [ -- ] + info.event })
        },
        box(width: 180pt),   // keeps the title clear of the logo below
      )
      // Your Institute logo on the bottom edge of the band, the lab logo at the top of the
      // white area beneath it (the author, 2026-10-20).
      place(bottom + right, image(logos.cyclotron, width: 180pt, alt: "Your University Your Institute logo"))
    })
    place(top + right, dx: -18pt, dy: 58% + 10pt, image(logos.lab, width: 130pt, alt: "Karthein Lab, Your University logo"))
    if contents.len() > 0 {
      block(inset: (x: 18pt, top: 22pt), {
        text(size: 15pt, weight: "bold", [Content:])
        v(6pt)
        set text(size: 14pt)
        list(..contents)
      })
    }
  }
  let body = body + place(bottom + right, dx: -18pt, dy: -12pt, text(size: 9.5pt, fill: muted, build-line))
  let self = utils.merge-dicts(self, config-page(header: none, footer: none, margin: 0pt))
  touying-slide(self: self, body)
})

// ---------------------------------------------------------------- theme
/// `email`: the presenter's address, shown at the left of every slide footer (none: no address).
/// It can also be given as `config-info(email: ...)`.
#let karthein-theme(aspect-ratio: "16-9", handout: false, sponsors: false, email: none, ..args, body) = {
  set document(title: "", author: "")  // overridden by the deck via config-info below
  set text(font: ("STIX Two Text", "Helvetica Neue"), size: 14pt, fill: ink, lang: "en")
  show math.equation: set text(font: "STIX Two Math")
  set par(leading: 0.6em)
  // Running text is justified (the author, 2026-10-07): a paragraph or bullet that wraps fills the
  // column; one-line text is unaffected. Explicitly aligned content (centred captions,
  // diagram labels) and tables stay as they are set.
  set par(justify: true)
  // Letter spacing takes part of the stretch, so narrow columns get no wide word gaps.
  set par(justification-limits: (spacing: (min: 100% * 2 / 3, max: 130%), tracking: (min: -0.01em, max: 0.02em)))
  show align: set par(justify: false)
  show table: set par(justify: false)
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
