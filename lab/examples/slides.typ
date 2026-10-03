// Slide theme example (Touying). Compile from the repository root:
//   typst compile --root . --pdf-standard ua-1 examples/slides.typ build/slides.pdf
#import "/themes/karthein.typ": *

#show: karthein-theme.with(
  config-info(title: [The Slide Theme], author: [A. Author], institution: [Your Institute], date: [2026], event: [Example]),
  sponsors: false,
  email: [you\@example.edu],
)

#title-slide(contents: ([A figure from the catalog], [An equation with spoken alt text]))

#slide(title: [A Figure From the Catalog], composer: (1fr, 1.1fr))[
  #set par(spacing: 0pt)
  #v(10pt)
  #set text(size: 15pt)
  #set list(spacing: 14pt)
  - `cat-fig` takes file, caption and alt text from `/assets/catalog.yaml`
  - a superseded figure fails the build
  - compiled with `--pdf-standard ua-1`
][
  #v(10pt)
  #cat-fig("plot-us-cpi-u-yoy-2023-2026", max-height: 270pt, caption: [Caption on one line.])
]

#slide(title: [An Equation With Spoken Alt Text])[
  #v(30pt)
  #eq(alt: auto)[$ x(t) = x_0 + v_0 t + 1/2 a t^2 $]
  #v(20pt)
  #align(center, text(size: 14pt, fill: muted)[`eq(alt: auto)` reads: "#speak($x(t) = x_0 + v_0 t + 1/2 a t^2$.body)"])
]
