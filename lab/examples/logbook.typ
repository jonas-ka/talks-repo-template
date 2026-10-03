// Lab-notebook template example. Compile from the repository root:
//   typst compile --root . --pdf-standard ua-1 examples/logbook.typ build/logbook.pdf
#import "/notes/labnotes-template.typ": *

#show: labnotes.with(
  title: "Example Log Book",
  project: "An example project",
  subproject: "the repository this log book lives in",
  author: "A. Author",
  started: "1 October 2026",
  summary: [Decisions, findings, numbers and open items, oldest first.],
)

= Project background

#context-box[*Purpose.* What the project is for and where things live.]

#day("2026-10-01", "First day")[

#note("Set-up", "Repository created", tags: ("decision",))[
  #decision[One repository per project, with this log book in `notes/`.]
  #finding[The template compiles under PDF/UA-1.]
  #todo[
    - Fill in the background section.
  ]
]
]
