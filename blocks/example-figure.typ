// id: example-figure
// title: A catalogued figure on a slide
// topic: [example]
// level: [public, undergrad, nuclear, AMO, expert]
// minutes: 2
// order: 20
// requires: []
// assets: [plot-us-cpi-u-yoy-2023-2026]
// section: A figure from the catalog
// source: template example; the figure's script and data are in assets/sources/cpi-u-yoy/
#import "/themes/karthein.typ": *

#slide(title: [A Figure From the Catalog, With Its Alt Text], composer: (1fr, 1.05fr),
  footer-citation: [U.S. Bureau of Labor Statistics, CPI-U (CUUR0000SA0)])[
  #set par(spacing: 0pt)
  #set text(size: 15pt)
  #v(8pt)
  #set list(spacing: 16pt)
  - `#cat-fig("plot-us-cpi-u-yoy-2023-2026")` places the figure; file, caption and alt text
    come from `assets/catalog.yaml`
  - The build refuses a figure without alt text, and one that a newer figure supersedes
  - The plotting script and the fetched data sit next to it in `assets/sources/`, so anyone
    can redraw it
  - Compiled with `--pdf-standard ua-1`: a tagged, accessible PDF, every time
  #v(22pt)
  #block(width: 100%, inset: 9pt, radius: radius.md, fill: panel.blue, stroke: 1pt + line-color.blue,
    text(size: 12.5pt)[*Layout pass:* `talks layout example-talk` measures the blank band and the column balance of every page; the numbers say where to look, the render decides.])
][
  #v(10pt)
  #cat-fig("plot-us-cpi-u-yoy-2023-2026", max-height: 268pt, caption: [US CPI-U, 12-month change, Sep 2023 -- Aug 2026])
]
