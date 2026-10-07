// Karthein Lab exam theme: written exams with a cover page (name boxes, equation sheet, graders'
// table), problems in parts with their points and answer space, and a solutions mode with the
// worked solution and the grading rubric. PDF/UA-1 like every lab theme.
//
// Usage:
//   #import "/themes/karthein-exam.typ": *
//   #show: exam.with(
//     course: "PHYS-206-DP", term: "Spring 2027", title: "Midterm Exam",
//     instructor: "Prof. Karthein", sections: "525-530", date: "March 24, 1:50 pm – 2:40 pm",
//     equations: eq-sheet(...), alts: yaml("exam.alts.yaml"),
//   )
//   #problem(title: [Projectile])[A ball is thrown ...]
//   #part(points: 4, space: 5cm)[Draw the free-body diagram.][
//     $F = m a$ #pts(1)[law] ...            // the solution: shown in solutions mode only
//   ]
//
// Modes (`--input mode=...`): `exam` (default; blank answer space) and `solutions` (the typed
// solution in the space and the rubric marks `pts`, green and circled). The graders' table on
// the cover is computed from the parts' points, so a problem's total cannot drift.
//
// Compile from the repository root:
//   typst compile --root . --pdf-standard ua-1 --input mode=solutions exams/midterm-A.typ

#import "tokens.typ": *
#import "speak-math.typ": apply-alts, spoken-eq

#let exam-mode = sys.inputs.at("mode", default: "exam")
#let is-solutions = exam-mode == "solutions"

#let rubric-green = rgb("#2E7D32")        // 5.1:1 on white
#let solution-ink = rgb("#0B3D91")        // 9.6:1 on white

// ---------------------------------------------------------------- equations
/// An equation with its own alt text (`auto` = spoken form).
#let eq(alt: auto, body) = spoken-eq(alt: alt, block: true, numbering: none, body)

// ---------------------------------------------------------------- the equation sheet
/// One titled group of the equation sheet: #eq-group([Vectors])[ ... ]
#let eq-group(title, body) = block(width: 100%, below: 6pt, {
  text(weight: "bold", style: "italic", size: 10.5pt, title)
  v(2pt)
  // display fractions need their real height, or they touch the neighbouring lines
  set text(size: 9pt, top-edge: "bounds", bottom-edge: "bounds")
  set par(leading: 0.45em, spacing: 0.55em)
  body
})

/// The equation sheet: a black title bar and two columns.
///   eq-sheet(left: [#eq-group([Vectors])[...] ...], right: [...])
/// `right-align: center` centers the right column (a list of stand-alone equations, as on the
/// PHYS 207 sheet). Fractions on a sheet read better in display size: `$display((dif x)/(dif t))$`.
#let eq-sheet(title: [USEFUL EQUATIONS], left: [], right: [], right-align: left) = block(width: 100%, stroke: 0.8pt + ink, breakable: false, {
  block(width: 100%, fill: ink, inset: (y: 4pt), align(center, text(fill: white, weight: "bold", size: 10.5pt, tracking: 0.4pt, title)))
  grid(columns: (1fr, 1fr), stroke: (x, y) => if x == 0 { (right: 0.5pt + ink) },
    inset: 7pt, left, align(right-align, right))
})

// ---------------------------------------------------------------- problems and parts
#let _problem = counter("exam-problem")
#let _part = counter("exam-part")

/// A problem: "Problem 2: Coulomb Forces" and its statement. The parts follow inside or after.
/// `source:` (shown in the solutions mode only) says where the problem comes from and how it was
/// changed, e.g. [Fall 2023 Exam 2, Problem 3; the incline now has friction, symbols instead of numbers].
#let problem(title: none, source: none, breakable: true, body) = {
  _problem.step()
  _part.update(0)
  block(width: 100%, above: 12pt, below: 6pt, breakable: breakable, {
    text(weight: "bold")[Problem #context _problem.display()#if title != none [: #title]]
    if is-solutions and source != none {
      linebreak()
      block(width: 100%, inset: 5pt, fill: band, radius: 3pt, text(size: 9pt, fill: muted)[*Source and changes:* #source])
    }
    linebreak()
    body
  })
}

/// A rubric mark in the solutions mode: a green circled "+n" with an optional note.
///   #pts(1)[law]   #pts(2)[correct derivative]   #pts(-12)[if nothing drawn]
#let pts(n, ..args) = if is-solutions {
  let note = args.pos().at(0, default: none)
  let label = if n > 0 { "+" + str(n) } else { str(n) }
  box(baseline: 25%, {
    box(stroke: 0.9pt + rubric-green, radius: 6pt, inset: (x: 3.5pt, y: 2pt), text(size: 8.5pt, weight: "bold", fill: rubric-green, label))
    if note != none and note != [] { h(2pt); text(size: 8.5pt, fill: rubric-green, style: "italic", note) }
  })
}

/// A part: the label "a)", the question, a blank answer space of `space` (exam mode) or the typed
/// solution (solutions mode), the points "/4" at the bottom right and a thin rule.
/// `figure:` puts content (a drawing) to the left of the question, as on a printed exam.
///   #part(points: 3, space: 5cm)[Calculate the force. *Show all intermediate steps.*][solution]
#let part(points: 0, space: 4cm, figure: none, figure-width: 38%, question, solution) = {
  _part.step()
  context {
    let p = _problem.get().first()
    [#metadata((problem: p, points: points)) <exam-part>]
  }
  let q = { text(weight: "bold")[#context numbering("a)", _part.get().first())] + h(0.35em); question }
  block(width: 100%, above: 6pt, below: 0pt, breakable: is-solutions, {
    if figure != none {
      grid(columns: (figure-width, 1fr), column-gutter: 14pt, align(left + top, figure), q)
    } else { q }
    if is-solutions {
      block(width: 100%, above: 8pt, inset: (left: 10pt, y: 4pt), stroke: (left: 1.5pt + solution-ink.lighten(40%)), {
        set text(fill: solution-ink)
        solution
      })
      v(4pt)
    } else {
      v(space)
    }
    // the points and the closing rule stay together (never a rule alone on a new page)
    block(width: 100%, breakable: false, {
      align(right, text(size: 10pt)[/#points])
      v(-6pt)
      line(length: 100%, stroke: 0.5pt + band.darken(25%))
    })
  })
}

/// Space for the student's own drawing in a figure (exam mode) and the drawn solution
/// (solutions mode): use inside `figure:` when the answer is a drawing on the printed figure.
#let on-solutions(body) = if is-solutions { body }

// ---------------------------------------------------------------- the document
#let exam(
  course: "PHYS-206-DP",
  term: "Spring 2027",
  title: "Midterm Exam",
  instructor: "Prof. Karthein",
  sections: none,
  date: none,
  short-title: auto,            // the running header: "PHYS-206-DP - Midterm Exam - Karthein"
  author: "Your Name",
  equations: none,
  note: none,                   // a line under the name boxes (e.g. the time allowed, the rules)
  alts: (),
  lang: "en",
  body,
) = {
  let full-title = course + " — " + term + " — " + title
  let running = if short-title == auto { course + " - " + title + " - " + instructor.split(" ").last() } else { short-title }
  set document(title: full-title + (if is-solutions { " (solutions)" } else { "" }), author: author)
  set text(font: ("STIX Two Text", "Helvetica Neue"), size: 11pt, fill: ink, lang: lang)
  show math.equation: set text(font: "STIX Two Math")
  set par(justify: false, leading: 0.62em)
  set page(
    paper: "us-letter",
    margin: (x: 0.75in, top: 0.9in, bottom: 0.75in),
    header: context {
      if counter(page).get().first() > 1 {
        set text(size: 10.5pt)
        grid(columns: (1fr, auto), [*Name:*],
          [*#running* — _Page #counter(page).display() of #counter(page).final().first()_])
        v(-5pt); line(length: 100%, stroke: 0.8pt + ink)
      }
    },
  )

  // the cover page (inside `apply-alts`, so the equation sheet gets its alt texts too)
  let cover = {
  align(center, {
    heading(level: 1, outlined: false, text(size: 20pt, full-title))
    v(2pt)
    text(style: "italic", size: 11pt, {
      // the key says so in the subtitle line, so the title never wraps and the cover keeps its layout
      if is-solutions { text(weight: "bold", style: "normal", fill: rubric-green)[Solutions and grading rubric — ] }
      instructor
      if sections != none [ — Sections #sections]
      if date != none [ — #date]
    })
  })
  v(10pt)
  table(columns: (1fr, 1fr), stroke: 0.8pt + ink, inset: (x: 6pt, top: 6pt, bottom: 26pt), align: left + top,
    [*Last Name:*], [*First Name:*], [*Section Number:*], [*Signature:*])
  if note != none { v(4pt); text(size: 10pt, style: "italic", note) }
  v(14pt)
  if equations != none { equations }
  v(1fr)
  // the graders' table, from the parts' points
  context {
    let parts = query(<exam-part>).map(m => m.value)
    let n = if parts.len() > 0 { calc.max(..parts.map(p => p.problem)) } else { 0 }
    let per = range(1, n + 1).map(i => parts.filter(p => p.problem == i).map(p => p.points).sum(default: 0))
    let total = per.sum(default: 0)
    block(width: 100%, stroke: 0.8pt + ink, breakable: false, {
      block(width: 100%, fill: ink, inset: (y: 4pt), align(center, text(fill: white, weight: "bold", size: 10.5pt, tracking: 0.4pt)[LEAVE BLANK; FOR GRADERS ONLY!]))
      table(columns: (auto,) + (1fr,) * n + (1.2fr,), stroke: 0.4pt + band.darken(30%), align: center + horizon,
        inset: (x: 4pt, y: 5pt),
        [*Problem*], ..range(1, n + 1).map(i => [*#i*]), [*TOTAL*],
        table.cell(inset: (y: 12pt))[*Points*],
        ..per.map(x => table.cell(align: right + bottom, text(size: 8.5pt)[/#x])),
        table.cell(align: right + bottom, text(size: 8.5pt)[/#total]))
    })
  }
  }
  apply-alts(alts, { cover; pagebreak(); body })
}
