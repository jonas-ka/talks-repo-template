# Karthein Lab talk theme

Derived on 2026-09-17 from three reference decks: the RadIs workshop (2026-08), the NAMO
workshop (2026-08), and APS Global 2026 (2026-03). Colours and fonts: `palette.yaml`.
Typst/Touying implementation: `karthein.typ`. Logos: `logos/`.

## Visual identity, as observed

- 16:9 white slides. Text set in **STIX Two Text**: bold titles, regular body, italic for
  emphasis and for the date/event line. Math in STIX Two Math.
- **Content slide:** bold title top-left (18 pt), <Your University> logo top-right, thin light
  rule under the title. Footer: light grey band with the e-mail address bold on the
  left, the slide's citation centred in teal, the page number bold on the right, and
  sponsor logos (DOE, Genesis Mission) right of centre when relevant.
- **Title slide:** light grey band across the top half with the title in bold, the
  author line in bold, the date and event in italic; <Your Institute> and Karthein
  Lab logos at the right edge of the band; a short "Content:" list below.
- One figure per slide where possible; figures fill the right or full width; bullets
  are short and use the round bullet.
- Teal `#0097A7` marks links and citations; maroon `#500000` appears only as a brand
  accent. Both are recorded with their contrast ratios in `palette.yaml`.

## Accessibility

- Every deck compiles with `--pdf-standard ua-1`, sets `document(title:, author:)` and
  `text(lang: "en")`.
- Body text is at least 14 pt black on white; teal at body size uses the darkened
  `link_text` variant (4.65:1).
- The group plot palette stays as given for marks; series also differ by marker or line
  style, and legends/labels use the `plot_text` variants.
- Images: `image(..., alt: ...)`; equations: `math.equation(alt: ...)`. Alt text comes from
  `assets/catalog.yaml`.
- Handout mode (`handout: true` in the theme config) collapses `#pause` steps to one page
  per slide for posted PDFs.

# Exam theme (`karthein-exam.typ`, since v2026.10.3)

Written exams in the layout of the PHYS 207 Don't Panic final (Fall 2025): a cover page with
the title line ("COURSE — Term — Exam"), the instructor/sections/date line in italic, the name,
section and signature boxes, the equation sheet (black title bar, two columns of titled
groups) and the graders' table (black bar "LEAVE BLANK; FOR GRADERS ONLY!", one column per
problem with its points, the total). Every later page carries "Name:" and "COURSE - Exam -
Instructor — Page n of N". Problems are bold "Problem n: Title" with a statement; parts are
"a)" … with the question, a blank answer space, the points "/n" at the bottom right and a thin
rule. A figure can sit to the left of a part (`figure:`).

`--input mode=solutions` prints the typed solution in each part's space (dark blue, a left
rule) and the rubric marks `#pts(n)[note]` as green circled "+n" with the note, as the graded
key does by hand. The graders' table sums the parts' points, so it cannot disagree with them.
Equations need alt text like everywhere else (`talks alts <file>` writes the sidecar; the
equation sheet is covered too). Example: `examples/exam.typ`.
