// Poster theme example (A0 portrait). Compile from the repository root:
//   typst compile --root . --pdf-standard ua-1 examples/poster.typ build/poster.pdf
#import "/themes/karthein-poster.typ": *

#show: poster.with(title: "Example Poster")

#poster-header(
  title: [Example Poster],
  subtitle: [One row of cards, one row of numbers],
  authors: [*A. Author* and the Lab · Your Institute],
  collaborators: [in collaboration with B. Colleague (Elsewhere)],
)

#card-row(columns: (1fr, 1fr),
  sec[The Question][
    #par(justify: true)[Cards in a row share the row's height; every gap is `poster-gutter`. Body text is 30 pt,
    captions 24 pt, nothing below 20 pt.]
    #v(8mm)
    #stat-row(
      ([3], [formats per figure], "blue"),
      ([300 dpi], [for the PNG copy], "yellow"),
    )
  ],
  sec[The Figure][
    #pfig("plot-us-cpi-u-yoy-2023-2026", 420pt, [A catalog figure with its alt text.])
  ],
)

#poster-footer(
  event: [Example meeting, 2026],
  acknowledgements: [Supported by nobody in particular.],
  website: "example.edu",
  contact: "you@example.edu",
)
