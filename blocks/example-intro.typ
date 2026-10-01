// id: example-intro
// title: What this template gives you
// topic: [example]
// level: [public, undergrad, nuclear, AMO, expert]
// minutes: 2
// order: 10
// requires: []
// assets: []
// section: The pipeline
// source: template example, written for talks-repo-template
#import "/themes/karthein.typ": *
#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge

#let stage(title, body, tone) = box(width: 172pt, inset: (x: 8pt, y: 8pt), radius: radius.md,
  fill: panel.at(tone), stroke: 1.2pt + line-color.at(tone), {
    set align(left); set text(size: 12.5pt); set par(spacing: 3pt)
    text(size: 14pt, weight: "bold", fill: text-color.at(tone), title); parbreak(); body
  })

#slide(title: [One Brief, One Curated Library, One Command])[
  #set par(spacing: 0pt)
  #v(6pt)
  #align(center, diagram(spacing: (10pt, 0pt),
    node((0, 0), stage([Past decks], [scanned, archived, every figure extracted and described], "yellow")),
    edge((0, 0), (1, 0), "-|>"),
    node((1, 0), stage([Catalog], [one entry per figure: file, caption, alt text, provenance, version], "blue")),
    edge((1, 0), (2, 0), "-|>"),
    node((2, 0), stage([Blocks + theme], [reusable slide modules in Typst; accessible PDF (UA-1)], "green")),
    edge((2, 0), (3, 0), "-|>"),
    node((3, 0), stage([New talk], [`brief.yaml`, then blocks chosen by audience and minutes, then PDF, HTML, PPTX], "red")),
  ))
  #v(26pt)
  #set text(size: 15pt)
  *Why a library:* every figure exists once, with its source, its alt text and its version; a
  superseded plot cannot appear in a new talk.
  #v(14pt)
  *Why a brief:* the deck is assembled from the newest material that fits the audience and
  the time slot, and the generator reports the layout flags of every page.
  #v(14pt)
  *Why Claude Code:* `CLAUDE.md` holds the rules, the schemas and the lessons; the log book in
  `docs/` holds what happened and why. The story is in `RECIPE.md`.
  #v(22pt)
  #grid(columns: (1fr, 1fr, 1fr), column-gutter: 14pt,
    ..(("uv run talks generate example-talk", "brief to deck: PDF (UA-1), HTML, report.md"),
       ("uv run talks layout example-talk", "blank band and column balance per page"),
       ("uv run talks pptx example-talk", "live-text PPTX for Google Slides")).map(((cmd, what)) =>
      block(width: 100%, inset: 9pt, radius: radius.md, fill: band, stroke: 1pt + band.darken(20%),
        text(size: 12pt)[#raw(cmd) \ #text(fill: muted, what)])))
  #v(10pt)
  #text(size: 12pt, fill: muted)[This slide is a block: `blocks/example-intro.typ`, with a tagged header the generator reads.]
]
