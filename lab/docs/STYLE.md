# The style, on one page

Slides, posters and figures share one palette, one type family and one set of tokens. The
machine-readable sources are `themes/palette.yaml` (colours with measured WCAG contrast
ratios), the token block at the top of `themes/karthein.typ` (panels, line colours, radii,
shadows), `themes/karthein-poster.typ` (poster sizes and card styles) and
`themes/karthein.mplstyle` (matplotlib). This page is the human summary.

## Colours

| role | hex | use |
|---|---|---|
| ink | `#000000` | body text, axes, frames |
| muted | `#333333` | secondary text, captions, footer |
| band | `#F0F0F0` | header bands, table header rows, neutral panels |
| brand | `#500000` | slide titles, section titles, emphasis labels |
| yellow | `#FFCC00` | plot colour 1 |
| red | `#FF2D55` | plot colour 2 |
| blue | `#00A2FF` | plot colour 3 |
| green | `#61D935` | plot colour 4 |

The four plot colours are the lab's, colour-blind-safe in this order; they are **fills and
lines, not text**. For coloured *text* and thin lines use the darkened variants that pass
WCAG on white (`plot_text`, `plot_lines` in `palette.yaml`; `text-color` / `line-color` in the
theme): red `#A60033`, yellow `#634E00`, green `#005F00`, blue `#005685` for text. Colour
never carries meaning alone: add a marker, a label or a line style.

Panels (tinted boxes) are `panel.<tone>` fills with a `line-color.<tone>` 1–2 pt stroke, e.g.
blue `#EDF9FF` / `#0070AD`. Radii: 4, 8, 12 pt (`radius.sm/md/lg`). Shadows are layered
translucent rounded rectangles (Typst has no blur); the poster card style is a 1.5 pt
hairline plus the `smd-off` shadow (14 pt blur, 9 pt down).

## Type

STIX Two Text for text, STIX Two Math for formulas (both free). Slides: titles 18 pt bold in
Title Case, body 13–14 pt, captions 11 pt italic muted on one line, footnotes 9.5 pt, slide
numbers and the e-mail 11 pt bold. Posters (A0): body 30 pt, captions 24 pt, section titles
50 pt, title ~100 pt, nothing below ~20 pt; multi-line paragraphs justified, captions, stats
and bullets ragged. `*strong*` in the slide theme is bold *italic* (the theme's `alert`);
upright bold is `text(weight: "bold")`.

## Slides

One figure per slide, minimal text, no bullet walls; paragraph and bullet gaps of 10–13 pt
at body size; the body fills the page (no blank band above the footer, columns ending at
similar heights); figures and captions aligned with the text column. Header: title, mark,
hairline rule; footer: hairline rule, e-mail, citation in teal (`#007682` at body size),
sponsor logos only where a block asks for them, page number. Tagged PDF (UA-1) always;
every figure and equation has alt text.

Running text (paragraphs, bullets, column text) is **justified**; letter spacing takes part of
the stretch (`justification-limits`: word spacing 67–130 %, tracking −0.01 to +0.02 em), so
narrow columns get no wide gaps. Explicitly aligned content (centred captions, diagram labels)
and tables are not justified. **Text budget:** a slide with more than 120 words of body text
(type of 11.5 pt and up; captions and figure labels do not count) is text-heavy and loses at
least 10 % of its words in the layout pass; `talks layout` counts them and names the target.
The **title slide** says what built the deck, small at the bottom right: the template version
(`VERSION`) and the git revision of the repository it was compiled from (`--input rev=`).

## Posters

A grey header band (title, subtitle in brand colour, authors, collaborators in italics,
logos at one visible height, centred), rows of white cards with aligned top and bottom edges
(`card-row`), one gutter (18 mm) between columns, rows, stacked cards and above the footer,
the page filled so that the bottom margin comes out near the 28 mm side margins; the
occasion, acknowledgements and contact in the footer.

## Lecture notes and course documents

`themes/karthein-notes.typ`: US Letter, STIX Two Text 11 pt (12 pt with wider leading in the
*lecture* copy for the iPad), 1 in margins, the course and lecture in a muted running header,
"Page x of y" in the footer, headings in brand maroon (15 / 12.5 / 11.5 pt), numbered
"1.1". Tinted panels for definitions (blue), key ideas and check-yourself questions (yellow),
examples and solutions (green), "Don't panic" warnings (red), a grey summary band. Figures
are numbered with a 10 pt muted caption; links teal and underlined. Three modes from one
source: `student` (posted), `lecture` (`work`/`blank` become empty space to write in),
`solutions`. Every equation has alt text: `eq(alt: ...)` for key equations, the `.alts.yaml`
sidecar (`talks alts`) for plain `$...$`; the HTML export carries MathML.

## Figures

`plt.style.use("themes/karthein.mplstyle")` gives: STIX fonts, the four lab colours in order
(then black, grey), black bold axis labels and regular ticks, a full box of four spines, no
grid by default, legends inside without a frame. The rules that a style file cannot enforce:
one colour per *thing* kept across panels and figures; annotations in black with the colour
on the marker or line; **text never on data** (labels in empty regions, end labels beside the
curve end, else a leader line); `plt.subplots` for every figure; save PDF + SVG + PNG
(300 dpi) from the same figure object with `bbox_inches="tight"`; captions one line.
