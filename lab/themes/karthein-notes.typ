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

// Writing time of the meeting (see "the class script" below).
#let _write-min = state("write-min", 0)
#let _count(min) = if min != none { _write-min.update(x => x + min); [#metadata(min) <write-min>] }

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
  block(width: 100%, inset: (x: 12pt, y: 9pt), radius: radius.md, fill: band, above: 10pt, below: 10pt, breakable: false, { text(weight: "bold", fill: brand)[Summary]; v(3pt); body }),
)

// ---------------------------------------------------------------- lecture-mode space
/// Space for handwriting in lecture mode; nothing in the other modes.
#let blank(height: 4cm) = if is-lecture { on-html([], block(width: 100%, height: height, breakable: false)) }

/// Typed working that is replaced by empty space in lecture mode (`height` of that space):
///   #work(height: 6cm, title: [Range of the shell])[ $ a = F/m = ... $ ]
/// `title` names the box in the lecture copy, so the writer knows what goes in it; it is not
/// shown in the student copy (the surrounding text already says).
#let work(height: 5cm, title: none, min: none, body) = { _count(min); if is-lecture {
  on-html([], block(width: 100%, height: height, breakable: false, stroke: (paint: band.darken(25%), thickness: 0.5pt, dash: "dotted"), radius: radius.sm, inset: 6pt,
    if title != none { text(size: 9pt, fill: muted, style: "italic", title) }))
} else { block(width: 100%, above: 8pt, below: 8pt, body) } }

/// Prose for the student copy only: explanation, context, an analogy. Dropped in the lecture
/// copy, where it would only be read aloud. Plain in HTML.
///   #aside[The same equation governs a car's braking distance ...]
#let aside(body) = if not is-lecture { on-html(body, block(width: 100%, inset: (left: 10pt), stroke: (left: 1.5pt + band.darken(20%)), text(size: 10.5pt, body))) }

/// A figure drawn live in class: the finished drawing in the student copy (a file with alt text),
/// an empty box of the same height with the caption in the lecture copy.
///   #sketch("fig-train.svg", alt: "...", height: 5cm, caption: [Everything we know, on the picture.])
#let sketch(path, alt: none, hint: none, height: 5cm, width: 80%, caption: none, label: none, min: none) = {
  assert(alt != none, message: "every sketch needs alt text")
  _count(min)
  // the lecture copy prints a short hint (default: the alt text's first sentence), not the whole alt
  let h = if hint != none { hint } else { alt.split(". ").first() }
  if is-lecture {
    // not a `figure`: an empty block has no alt text and UA-1 would refuse it
    on-html([], block(width: 100%, above: 10pt, below: 10pt, breakable: false, align(center, {
      block(width: width, height: height, stroke: (paint: band.darken(25%), thickness: 0.5pt, dash: "dotted"), radius: radius.sm,
        align(top + left, pad(6pt, text(size: 9pt, fill: muted, style: "italic")[draw: #h])))
      if caption != none { v(6pt); text(size: 10pt, fill: muted, caption) }
    })))
  } else { fig(path, alt: alt, width: width, caption: caption, label: label) }
}

/// A lecture demonstration, placed where its physics is done: thumbnail (alt text required: the
/// PLC has none), PIRA code and name, the prediction question, one line on what was seen, and a
/// link to a video for students who missed it.
///   #demo(code: "1C20.10", name: [Penny and feather in a vacuum], photo: "/demos/thumbs/1C20.10.jpg",
///         alt: "...", video: "https://...", predict: [Which lands first in air? In vacuum?])[one line]
#let demo(code: none, name: [], photo: none, alt: none, video: none, predict: none, body) = {
  assert(photo == none or alt != none, message: "a demo photo needs alt text")
  // The lecture copy is the teacher's printed script: the prediction, then what to say after
  // the demo (italic); the student copy has both and the video link.
  let text-part = {
    _label([Demo], "yellow"); if code != none { text(fill: muted)[ #code] }; [ · *#name*]
    if predict != none { linebreak(); [*Predict first:* #predict] }
    if is-lecture { linebreak(); text(style: "italic", fill: muted)[*After:* #body] } else { linebreak(); [*What happens:* #body] }
    if video != none and not is-lecture { linebreak(); text(size: 10pt)[Missed it? #link(video)[Video: #name]] }
  }
  on-html(
    block(width: 100%, inset: 10pt, stroke: (left: 3pt + line-color.at("yellow")), fill: panel.at("yellow"), {
      if photo != none { image(photo, width: 30%, alt: alt) }; text-part }),
    block(width: 100%, inset: (x: 12pt, y: 9pt), radius: radius.md, fill: panel.at("yellow"), stroke: 1pt + line-color.at("yellow"), above: 10pt, below: 10pt, breakable: false,
      if photo != none {
        grid(columns: (3.2cm, 1fr), column-gutter: 10pt, align(top, image(photo, width: 100%, alt: alt)), align(top, { set par(justify: false); text-part }))
      } else { set par(justify: false); text-part }),
  )
}

/// A Poll Everywhere question (the Friday quiz): the question and options in every copy, the
/// answer only in `solutions` mode (built, never published) and in the answers copy posted after
/// the quiz.
///   #poll(answer: [b: gravity acts the whole time])[At the top of its flight the ball's acceleration is (a) zero (b) 9.8 m/s² down ...]
#let poll(answer: none, body) = {
  _panel("blue", [Quiz], none, { body; if is-solutions and answer != none { v(4pt); [*Answer:* #answer] } })
}

// ---------------------------------------------------------------- the class script
// One document per class meeting. The lecture copy is the teacher's printed script: every word
// is there, and the typography says what is SAID (italic, dotted rule) and what is WRITTEN on the
// board (framed, labelled with its minutes). The student copy is the same text as ordinary prose.
// Each `write`, `draw`, `recap`, `work` and `sketch` with `min:` adds to the meeting's writing
// time, printed in the lecture copy's title block against `notes(budget:)` and queryable:
//   typst query --root . --input mode=lecture <file>.typ "<write-min>"
#let _tag(kind, min, title) = text(size: 8.5pt, fill: brand, {
  text(weight: "bold", tracking: 0.6pt, kind); if min != none [ · #min min]
  if title != none { text(fill: muted)[ · #title] }
})

/// What is said, not written. Lecture copy: italic behind a dotted rule. Student copy: prose.
///   #say[Watch the sign: the force points toward lower potential energy.]
#let say(body) = if is-lecture {
  block(width: 100%, above: 7pt, below: 7pt, inset: (left: 9pt), stroke: (left: (paint: muted, thickness: 0.8pt, dash: "dotted")),
    text(style: "italic", fill: muted, body))
} else { body }

/// A stage direction for the teacher only (pause, show of hands, turn to the demo): printed in
/// the lecture copy as a small bracketed line, absent from the student copy.
///   #cue[Pause 20 s: show of hands, is the work positive or negative?]
#let cue(body) = if is-lecture {
  block(width: 100%, above: 6pt, below: 6pt, text(size: 9.5pt, fill: muted, style: "italic")[▸ #body])
}

/// What is written on the board, live, at the students' speed. Lecture copy: framed, labelled
/// "WRITE · n min". Student copy: the same content, plain.
///   #write(min: 3, title: [the dot product in components])[ $ arrow(a) dot arrow(b) = a_x b_x + a_y b_y $ ]
#let write(min: none, title: none, breakable: false, body) = {
  _count(min)
  if is-lecture {
    block(width: 100%, above: 8pt, below: 8pt, breakable: breakable, inset: (x: 10pt, y: 8pt), radius: radius.sm,
      stroke: (left: 2.5pt + brand, top: 0.5pt + brand.lighten(55%), right: 0.5pt + brand.lighten(55%), bottom: 0.5pt + brand.lighten(55%)), {
        set text(style: "normal", fill: ink)
        _tag([WRITE], min, title); v(1pt); body
      })
  } else {
    // student copy: what was on the board, set off from the prose by a hairline rule
    on-html(body, block(width: 100%, above: 8pt, below: 8pt, breakable: breakable, inset: (left: 10pt, y: 2pt), stroke: (left: 1pt + brand.lighten(50%)), body))
  }
}

/// A figure drawn live: the finished figure in both copies; the lecture copy labels it
/// "DRAW · n min" (default 2) so the drawing time is part of the meeting's budget.
#let draw(path, alt: none, min: 2, width: 70%, caption: none, label: none) = {
  _count(min)
  if is-lecture {
    block(width: 100%, above: 8pt, below: 8pt, breakable: false, inset: (x: 10pt, y: 8pt), radius: radius.sm,
      stroke: (left: 2.5pt + brand, top: 0.5pt + brand.lighten(55%), right: 0.5pt + brand.lighten(55%), bottom: 0.5pt + brand.lighten(55%)), {
        _tag([DRAW], min, none); fig(path, alt: alt, width: width, caption: caption, label: label)
      })
  } else { fig(path, alt: alt, width: width, caption: caption, label: label) }
}

/// The opening recap (Wednesday: Monday's class, 2 min; Friday: the chapter, 3 min): a summary
/// written on the board in both copies' wording.
#let recap(min: 2, title: none, body) = _panel("blue", [Recap], title, write(min: min, body))

/// The Friday quiz from its YAML (quizzes/W<nn>.yaml: questions with `q`, `options` where the
/// correct one starts with `***`, `why`, `type: open-ended`). Answers are printed in every copy
/// unless `answers: false` (a question with `feedback: true`, the one-minute paper, never has one): the lecture copy shows the results to discuss, and the student copy
/// is posted after the class.
///   #quiz(yaml("/quizzes/W06.yaml"))    #quiz(yaml("/quizzes/W01.yaml"), only: (1, 2))
#let quiz(data, answers: true, only: none) = {
  let letters = "abcdefgh".clusters()
  // `only: (1, 2, 4)` keeps those questions (1-based), e.g. for a short quiz
  let qs = if only == none { data.questions } else { only.map(i => data.questions.at(i - 1)) }
  let opts-of(q) = q.at("options", default: none)
  let question(q) = {
    q.q
    let opts = opts-of(q)
    if opts != none {
      linebreak()
      opts.enumerate().map(((i, o)) => [(#letters.at(i)) #o.trim("*", at: start)]).join(h(1em))
    }
  }
  let answer(q) = {
    let opts = opts-of(q)
    let right = if opts != none { opts.enumerate().filter(((i, o)) => o.starts-with("***")).map(((i, o)) => [(#letters.at(i)) #o.trim("*", at: start)]) } else { () }
    if right.len() > 0 { right.join([, ]); [. ] }
    q.at("why", default: "")
  }
  if is-lecture and answers {
    // projected: the questions alone, the answers on the next page (shown after the poll closes)
    _panel("blue", [Quiz], [Poll Everywhere, ungraded], enum(numbering: "1.", ..qs.map(question)))
    pagebreak(weak: true)
    _panel("blue", [Quiz results], [after the poll closes], enum(numbering: "1.", ..qs.map(q => { question(q); if not q.at("feedback", default: false) { linebreak(); text(fill: muted)[*Answer:* #answer(q)] } })))
  } else {
    _panel("blue", [Quiz], [Poll Everywhere, ungraded], enum(numbering: "1.", ..qs.map(q => {
      question(q)
      if answers and not q.at("feedback", default: false) { linebreak(); text(size: 10pt, fill: muted)[*Answer:* #answer(q)] }
    })))
  }
}

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
  // one document per class meeting (all optional):
  chapter: none,     // the book chapter(s), e.g. 7 or "3–4"
  week: none,        // teaching week
  day: none,         // "Monday", "Wednesday", "Friday": printed with the date
  budget: none,      // the meeting's writing budget in minutes (lecture copy: total vs budget)
  plan: none,        // the meeting's time plan, ((12, [demos]), (36, [lecture])), lecture copy only
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
  // Paged: the title block is the one level-1 heading (PDF H1) and sections written as `=` are
  // offset to level 2, numbered without the title's level ("1", "1.1"). HTML: Typst maps heading
  // level n to h(n+1), so the title is emitted as an h1 element and sections stay at level 1.
  show heading.where(level: 2): it => block(above: 18pt, below: 10pt, {
    text(size: 15pt, weight: "bold", fill: brand, it)
  })
  show heading.where(level: 3): it => block(above: 14pt, below: 7pt, text(size: 12.5pt, weight: "bold", it))
  show heading.where(level: 4): it => block(above: 10pt, below: 5pt, text(size: 11.5pt, weight: "bold", style: "italic", it))
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
    context if target() == "html" { html.elem("h1", heading-line) } else {
      heading(level: 1, numbering: none, outlined: false, text(size: 20pt, fill: brand, heading-line))
    }
    v(2pt)
    let when = if date != none and date.match(regex("^\\d{4}-\\d{2}-\\d{2}$")) != none {
      let (y, m, d) = date.split("-").map(int)
      datetime(year: y, month: m, day: d).display("[day padding:none] [month repr:long] [year]")
    } else { date }
    let rev = sys.inputs.at("rev", default: none)
    if budget != none [#metadata(budget) <write-budget>]
    text(size: 10.5pt, fill: muted, {
      author
      if chapter != none [ · Chapter #chapter]
      if week != none [ · week #week]
      if day != none [ · #day]
      if when != none [ · #when]
      if is-lecture [ · *lecture copy*]
      if is-solutions [ · *solutions*]
      if rev != none [ · rev #raw(rev)]
    })
    if is-lecture and (budget != none or plan != none) {
      linebreak()
      text(size: 10pt, fill: muted, {
        if plan != none {
          plan.map(((m, what)) => [#what #m]).join([ · ])
          [ (#plan.map(p => p.at(0)).sum() min)]
          if budget != none [ #h(0.6em) | #h(0.6em)]
        }
        if budget != none {
          context {
            let total = _write-min.final()
            [writing *#total min* of #budget]
            if total > budget { text(fill: text-color.at("red"), weight: "bold")[ · over by #(total - budget) min] }
          }
        }
      })
      linebreak()
      text(size: 9.5pt, fill: muted, if day == "Friday" [This copy is projected: _▸_ lines are instructions for the room; write into the empty boxes. The solutions are in the student copy.] else [_Italic behind a dotted rule:_ say it. #h(0.3em) *WRITE* / *DRAW* frames: write or draw it on the board, live. #h(0.3em) _▸ cue:_ for you only.])
    }
    v(6pt); line(length: 100%, stroke: 1pt + brand)
  })

  context if target() == "html" {
    set heading(numbering: "1.1")
    apply-alts(alts, body)
  } else {
    set heading(offset: 1)
    set heading(numbering: (..n) => numbering("1.1", ..n.pos().slice(1)))
    apply-alts(alts, body)
  }
}
