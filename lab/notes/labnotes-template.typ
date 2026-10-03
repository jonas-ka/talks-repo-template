// ============================================================================
//  Karthein Lab — log-book template  (labnotes-template.typ)
//  Reusable for any project. Import it at the top of a log book:
//
//    #import "labnotes-template.typ": *
//    #show: labnotes.with(title: "...", project: "...", ...)
//
//  Building blocks:
//    #entry(date, title, tags: (...))[ ... ]   one dated log entry
//    #context-box[ ... ]                          background / setup
//    #decision[ ... ]                             a decision and why
//    #finding[ ... ]                              an observation / result
//    #issue[ ... ]                                a problem hit, cause, fix
//    #todo[ ... ]                                 open item
//    #refs(( "label": "path or URL", ... ))       where things live
//
//  New entries go at the BOTTOM of the log book (chronological order).
// ============================================================================

// Lab brand colours (from LabNameLogo.svg)
#let lab-red    = rgb("#FF004F")
#let lab-yellow = rgb("#FFC900")
#let lab-green  = rgb("#00DC00")
#let lab-blue   = rgb("#00A5FF")
#let lab-ink    = rgb("#1A1A1A")
#let lab-grey   = rgb("#6B6B6B")

// ---------------------------------------------------- contents (grouped) --
// Since 2026-10-01 a day is one major entry (`#day`) and everything else done that day is a minor
// `#note` appended under it, tagged with its project. The contents list every major entry (old
// `#entry`s and `#day`s) and, under a day, its notes grouped by project -- in the order the
// projects first appear that day; the text itself stays strictly chronological (append-only).
#let log-outline() = context {
  heading(level: 1, outlined: false, bookmarked: false)[Entries]
  let majors = query(heading.where(level: 1, outlined: true))
  for (i, h) in majors.enumerate() {
    let loc = h.location()
    let pg = counter(page).at(loc).first()
    block(above: 0.45em, below: 0.25em, link(loc)[#h.body #box(width: 1fr, repeat[.]) #pg])
    let sel = selector(<lognote>).after(loc)
    if i + 1 < majors.len() { sel = sel.before(majors.at(i + 1).location()) }
    let notes = query(sel)
    if notes.len() > 0 {
      let projects = ()
      for n in notes { if n.value.project not in projects { projects.push(n.value.project) } }
      for p in projects {
        block(above: 0.2em, below: 0.2em, inset: (left: 1.2em))[
          #set text(9pt)
          #text(weight: "bold", fill: lab-blue)[#p:]
          #for (k, n) in notes.filter(n => n.value.project == p).enumerate() [
            #if k > 0 [ · ]#link(n.location())[#n.value.title] #text(fill: lab-grey)[(#counter(page).at(n.location()).first())]
          ]
        ]
      }
    }
  }
}

// ---------------------------------------------------------------- document --
#let labnotes(
  title: "Log book",
  project: none,
  subproject: none,
  author: "Your Name",
  affiliation: "Your Institute, Your University",
  started: none,
  summary: none,
  body,
) = {
  set document(title: title, author: author)
  set page(
    paper: "us-letter",
    margin: (x: 2.2cm, y: 2.4cm),
    header: context {
      if counter(page).get().first() > 1 [
        #set text(8pt, fill: lab-grey)
        #title #h(1fr) #if project != none [#project] #if subproject != none [ · #subproject]
        #v(-4pt)
        #line(length: 100%, stroke: 0.4pt + lab-grey)
      ]
    },
    footer: context [
      #set text(8pt, fill: lab-grey)
      #author #h(1fr) #counter(page).display("1 / 1", both: true)
    ],
  )
  set text(font: ("Libertinus Serif", "New Computer Modern", "Linux Libertine"), size: 10.5pt, fill: lab-ink)
  set par(justify: true, leading: 0.62em)
  set heading(numbering: none)
  show heading.where(level: 1): it => block(above: 1.4em, below: 0.8em)[
    #set text(13pt, weight: "bold")
    #it.body
  ]
  show heading.where(level: 2): it => block(above: 1.1em, below: 0.6em)[
    #set text(11pt, weight: "bold", fill: lab-ink)
    #it.body
  ]
  show link: set text(fill: lab-blue)
  show raw.where(block: false): set text(size: 0.92em)

  // Title block
  block(width: 100%, inset: (bottom: 8pt), stroke: (bottom: 1.5pt + lab-blue))[
    #set text(20pt, weight: "bold")
    #title
    #v(2pt)
    #set text(10pt, weight: "regular", fill: lab-grey)
    #if project != none [*Project:* #project]
    #if subproject != none [ #h(0.6em) *Subproject:* #subproject] \
    *Author:* #author, #affiliation
    #if started != none [ \ *Log started:* #started]
  ]
  if summary != none {
    block(width: 100%, inset: 9pt, radius: 3pt, fill: lab-blue.lighten(90%))[
      #set text(9.5pt)
      *Summary.* #summary
    ]
  }
  v(0.6em)
  log-outline()
  body
}

// ------------------------------------------------------------------- entry --
#let entry(date, title, tags: (), authors: none, body) = {
  heading(level: 1)[#date — #title]
  if tags.len() > 0 or authors != none {
    block(above: -0.4em, below: 0.9em)[
      #set text(8.5pt, fill: lab-grey)
      #if authors != none [#authors #h(0.8em)]
      #for t in tags { box(inset: (x: 4pt, y: 2pt), radius: 2pt, fill: luma(235))[#t] + h(3pt) }
    ]
  }
  body
}

// ------------------------------------------------------- day + note (new) --
// `#day` opens a day (the first log of that date); `#note` adds one piece of work under it.
// Write notes in the order the work happened; the contents group them by `project`.
#let day(date, title, authors: none, body) = {
  heading(level: 1)[#date — #title]
  if authors != none {
    block(above: -0.4em, below: 0.9em)[#set text(8.5pt, fill: lab-grey); #authors]
  }
  body
}

#let note(project, title, tags: (), authors: none, body) = {
  [#metadata((project: project, title: title)) <lognote>]
  heading(level: 2, outlined: false)[#title #h(0.4em) #box(inset: (x: 4pt, y: 1.5pt), radius: 2pt, fill: lab-blue.lighten(85%))[#text(8pt, fill: lab-blue.darken(30%))[#project]]]
  if tags.len() > 0 or authors != none {
    block(above: -0.3em, below: 0.8em)[
      #set text(8.5pt, fill: lab-grey)
      #if authors != none [#authors #h(0.8em)]
      #for t in tags { box(inset: (x: 4pt, y: 2pt), radius: 2pt, fill: luma(235))[#t] + h(3pt) }
    ]
  }
  body
}

// ------------------------------------------------------------ callout boxes --
#let _callout(label, colour, body) = block(
  width: 100%, inset: (x: 9pt, y: 7pt), radius: 2pt,
  stroke: (left: 2.5pt + colour), fill: colour.lighten(92%),
  breakable: true,
)[
  #text(8pt, weight: "bold", fill: colour.darken(25%), tracking: 0.5pt)[#upper(label)] \
  #body
]

#let context-box(body) = _callout("Background", lab-grey, body)
#let decision(body)    = _callout("Decision", lab-blue, body)
#let finding(body)     = _callout("Finding", lab-green, body)
#let issue(body)       = _callout("Issue → cause → fix", lab-red, body)
#let todo(body)        = _callout("Open item", lab-yellow, body)

// --------------------------------------------------------------- reference --
#let refs(items) = table(
  columns: (auto, 1fr),
  stroke: none,
  inset: (x: 4pt, y: 3pt),
  fill: (_, row) => if calc.odd(row) { luma(246) } else { none },
  ..items.pairs().map(((k, v)) => (text(weight: "bold", size: 9pt)[#k], text(size: 9pt)[#v])).flatten(),
)
