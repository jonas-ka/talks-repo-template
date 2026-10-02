// Karthein Lab lecture-notes theme: accessible course documents (lecture notes, problem
// sets, syllabi) in the lab style, PDF/UA-1 tagged, with an HTML export for Canvas.
//
// Usage (courses/<course>/lectures/L01-.../notes.typ):
//   #import "/themes/karthein-notes.typ": *
//   #show: notes.with(
//     course: "PHYS 206", title: "Kinematics in One Dimension", number: 1, date: "2027-01-19",
//     author: "Your Name", alts: yaml("notes.alts.yaml"),
//   )
//   = Section
//   Text with plain math $v = (dif x)/(dif t)$ ...
//
// Three modes, chosen with `--input mode=...` (default `student`):
//   student    the complete notes: what is posted (PDF/UA-1 + HTML)
//   lecture    the same text with `work` and `blank` turned into empty space for handwriting
//              (the file that goes on the iPad), wider line spacing
//   solutions  `solution[...]` blocks shown (problem sets; `student` hides them)
//
// Equations: write plain `$...$`. `talks alts <file>` collects them into `<stem>.alts.yaml`
// with a spoken draft each; the reviewed text comes back through `alts:` (speak-math.typ).
// An equation written with `eq(alt: ...)` carries its own text. The build (UA-1) refuses
// an equation that has neither, so nothing unlabelled is ever posted.
//
// Compile from the repo root:
//   typst compile --root . --pdf-standard ua-1 --input mode=student <file>.typ
//   typst compile --root . --features html --format html --input mode=student <file>.typ

#import "tokens.typ": *
#import "speak-math.typ": speak, apply-alts, math-body, spoken-eq

#let mode = sys.inputs.at("mode", default: "student")
#let is-lecture = mode == "lecture"
#let is-solutions = mode == "solutions"

// `target()` tells paged (PDF) from HTML export inside `context`.
#let on-html(body-html, body-paged) = context { if target() == "html" { body-html } else { body-paged } }

// ---------------------------------------------------------------- catalog access
// Same contract as the slide theme: file, alt text and caption from assets/catalog.yaml;
// superseded assets are refused at compile time.
#let catalog = yaml("/assets/catalog.yaml")
#let superseded = catalog.filter(e => e.at("supersedes", default: none) != none).map(e => e.supersedes)

#let asset(id) = {
  let hits = catalog.filter(e => e.id == id)
  assert(hits.len() == 1, message: "catalog id not found: " + id)
  hits.first()
}

// ---------------------------------------------------------------- figures
/// A numbered figure with mandatory alt text and a caption:
///   #fig("/assets/figures/x.svg", alt: "...", width: 70%, caption: [Free-body diagram of the block.])
#let fig(path, alt: none, width: 80%, caption: none, label: none) = {
  assert(alt != none, message: "every figure needs alt text")
  let f = figure(image(path, width: width, alt: alt), caption: caption)
  if label != none { [#f #label] } else { f }
}

/// A catalog figure: #cat-fig("plot-...", width: 60%, caption: [...]) (caption from the catalog when none)
#let cat-fig(id, width: 80%, caption: auto, label: none) = {
  let e = asset(id)
  assert(id not in superseded, message: "asset " + id + " is superseded; use its successor")
  let path = e.at("svg", default: none)
  if path == none { path = e.at("file", default: none) }
  assert(path != none, message: "asset " + id + " has no file; run `talks generate` to materialize it")
  let cap = if caption == auto { e.at("caption", default: none) } else { caption }
  fig("/assets/" + path, alt: e.alt, width: width, caption: cap, label: label)
}

// ---------------------------------------------------------------- equations
/// An equation with its own alt text (`auto` = spoken form). `numbered: true` gives "(1)".
#let eq(alt: auto, numbered: false, body) = spoken-eq(alt: alt, block: true, numbering: if numbered { "(1)" } else { none }, body)

// ---------------------------------------------------------------- panels
#let _label(text-body, tone) = text(weight: "bold", fill: text-color.at(tone), text-body)

// Panels do not break across pages unless asked (`breakable: true` for a long example): a
// title alone at the bottom of a page is the first thing the layout pass finds.
#let _panel(tone, label, title, body, breakable: false) = on-html(
  block(width: 100%, inset: 10pt, stroke: (left: 3pt + line-color.at(tone)), fill: panel.at(tone), {
    _label(label, tone); if title != none { [ · *#title*] }; linebreak(); body
  }),
  block(width: 100%, inset: (x: 12pt, y: 9pt), radius: radius.md, fill: panel.at(tone), stroke: 1pt + line-color.at(tone), above: 10pt, below: 10pt, breakable: breakable, {
    set par(justify: false)
    _label(label, tone)
    if title != none { h(6pt); text(weight: "bold", title) }
    v(3pt)
    body
  }),
)

/// A definition (blue): #definition(title: [Velocity])[...]
#let definition(title: none, breakable: false, body) = _panel("blue", [Definition], title, body, breakable: breakable)
/// The idea to remember (yellow): #concept[...]
#let concept(title: none, breakable: false, body) = _panel("yellow", [Key idea], title, body, breakable: breakable)
/// A worked example (green): #example(title: [A ball thrown upward])[... #work[...] ...]
#let example(title: none, breakable: false, body) = _panel("green", [Example], title, body, breakable: breakable)
/// A warning or a common mistake (red). The course calls them "Don't Panic" moments.
#let caution(title: none, breakable: false, body) = _panel("red", [Don't panic], title, body, breakable: breakable)
/// A question for the room (clicker or show of hands); the answer goes in `solution`.
#let checkpoint(title: none, breakable: false, body) = _panel("yellow", [Check yourself], title, body, breakable: breakable)
/// What to take away (grey band).
#let summary(body) = on-html(
  block(width: 100%, inset: 10pt, fill: band, [*Summary* #linebreak() #body]),
  block(width: 100%, inset: (x: 12pt, y: 9pt), radius: radius.md, fill: band, above: 10pt, below: 10pt, { text(weight: "bold", fill: brand)[Summary]; v(3pt); body }),
)

// ---------------------------------------------------------------- lecture-mode space
/// Space for handwriting in lecture mode; nothing in the other modes.
#let blank(height: 4cm) = if is-lecture { on-html([], block(width: 100%, height: height, breakable: false)) }

/// Typed working that is replaced by empty space in lecture mode (`height` of that space):
///   #work(height: 6cm)[ $ a = F/m = ... $ ]
#let work(height: 5cm, body) = if is-lecture {
  on-html([], block(width: 100%, height: height, breakable: false, stroke: (paint: band.darken(25%), thickness: 0.5pt, dash: "dotted"), radius: radius.sm))
} else { body }

/// A solution: shown in `solutions` mode only (problem sets); hidden in `student` and `lecture`.
#let solution(breakable: true, body) = if is-solutions { _panel("green", [Solution], none, body, breakable: breakable) }

/// A problem set item: numbered, with points.
#let problem-counter = counter("problem")
#let problem(points: none, title: none, body) = {
  problem-counter.step()
  block(above: 14pt, below: 8pt, breakable: true, {
    text(weight: "bold", fill: brand)[Problem #context problem-counter.display()]
    if title != none { [ · *#title*] }
    if points != none { h(1fr); text(fill: muted, size: 10pt)[#points points] }
    v(4pt)
    body
  })
}

/// Two columns (paged); one after the other in HTML, which has no grid.
#let two-col(left, right, columns: (1fr, 1fr), gutter: 14pt) = on-html({ left; right }, grid(columns: columns, column-gutter: gutter, left, right))

// ---------------------------------------------------------------- document
/// The document. `kind`: "Lecture" (number + title in the header), "Problem Set", "Syllabus", ...
#let notes(
  course: "PHYS 206",
  kind: "Lecture",
  number: none,
  title: [],
  date: none,
  author: "Your Name",
  institution: "Your University",
  alts: (),
  lang: "en",
  body,
) = {
  let heading-line = if number != none { [#kind #number: #title] } else { [#kind: #title] }
  let doc-title = course + " " + (if number != none { kind + " " + str(number) + ": " } else { kind + ": " }) + title
  set document(title: doc-title, author: author)
  set text(font: ("STIX Two Text", "Helvetica Neue"), size: if is-lecture { 12pt } else { 11pt }, fill: ink, lang: lang)
  show math.equation: set text(font: "STIX Two Math")
  set par(justify: true, leading: if is-lecture { 0.85em } else { 0.65em }, spacing: if is-lecture { 1.3em } else { 1em })
  set page(
    paper: "us-letter",
    margin: (x: 1in, top: 1.05in, bottom: 0.95in),
    header: context {
      if counter(page).get().first() > 1 {
        set text(size: 9.5pt, fill: muted)
        grid(columns: (1fr, auto), [*#course* · #heading-line], if date != none { date } else { [] })
        v(-4pt); line(length: 100%, stroke: 0.5pt + band.darken(20%))
      }
    },
    footer: context {
      set text(size: 9.5pt, fill: muted)
      line(length: 100%, stroke: 0.5pt + band.darken(20%)); v(-4pt)
      grid(columns: (1fr, auto, 1fr), author, [Page #counter(page).display() of #counter(page).final().first()], align(right)[#institution])
    },
  )
  set heading(numbering: "1.1")
  show heading.where(level: 1): it => block(above: 18pt, below: 10pt, {
    text(size: 15pt, weight: "bold", fill: brand, it)
  })
  show heading.where(level: 2): it => block(above: 14pt, below: 7pt, text(size: 12.5pt, weight: "bold", it))
  show heading.where(level: 3): it => block(above: 10pt, below: 5pt, text(size: 11.5pt, weight: "bold", style: "italic", it))
  set list(indent: 8pt, spacing: 0.7em)
  set enum(indent: 8pt, spacing: 0.7em)
  show link: set text(fill: link-text)
  show link: underline
  show figure.caption: it => block(above: 6pt, text(size: 10pt, fill: muted, it))
  set figure(gap: 8pt)
  show raw: set text(font: ("Menlo", "DejaVu Sans Mono"), size: 9.5pt)
  set table(stroke: (x, y) => (bottom: 0.5pt + band.darken(20%)), inset: 6pt)
  show table.cell.where(y: 0): set text(weight: "bold", fill: brand)

  // Title block: the course, the lecture number and title as the one level-1 heading the
  // tag tree needs first, the date and the mode (lecture copies say so).
  block(below: 14pt, {
    text(size: 10.5pt, fill: muted, weight: "bold")[#course · #institution]
    linebreak()
    heading(level: 1, numbering: none, outlined: false, text(size: 20pt, fill: brand, [#kind #if number != none [#number]: #title]))
    v(2pt)
    text(size: 10.5pt, fill: muted)[#author#if date != none [ · #date]#if is-lecture [ · lecture copy]#if is-solutions [ · *solutions*]]
    v(6pt); line(length: 100%, stroke: 1pt + brand)
  })

  apply-alts(alts, body)
}
