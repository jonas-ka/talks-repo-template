# Courses: lecture notes, problem sets and slide lectures with the same theme

A course is **its own repository made from the template** (GitHub: *Use this template*,
private), not a folder in the talks repository. The reasons: a course is 25–40 documents
redone every time it is taught, it is shared with a TA or co-instructor, students get the
PDFs through the learning-management system, solutions must stay private, and Claude Code
reads a short course-specific `CLAUDE.md` instead of the talk pipeline's long one. The
*style* stays in one place (`themes/`), and the course repository pulls theme updates from
the template (`scripts/update_from_template.sh`).

The example in `courses/example-course/` builds out of the box:

```sh
uv run talks course build --course courses/example-course     # PDFs (UA-1) in every mode + HTML + report.md
uv run talks alts courses/example-course/lectures/L01-kinematics/notes.typ   # equation alt text sidecar
uv run talks course publish --course courses/example-course --dry-run       # what would go to Drive
```

## Two kinds of course documents

1. **Lecture notes, problem sets, syllabus**: one Typst file each on the notes theme
   (`themes/karthein-notes.typ`), compiled in up to three *modes* from the same source:
   - `student`: the complete document, what is posted (PDF/UA-1 and HTML with MathML);
   - `lecture`: the same text with `#work[...]` and `#blank()` turned into empty space, for
     teaching by hand on a tablet; the handwritten lecture and the posted notes never diverge;
   - `solutions`: `#solution[...]` blocks shown (problem sets; `student` hides them).
2. **Slide lectures**: a deck per lecture from blocks, like a talk. The brief lists the blocks
   explicitly (`blocks: [intro-binding-energy, liquid-drop, ...]`) instead of topics, so the
   generator takes exactly these in this order, pulls in their `requires`, and reports the
   time against `duration_min`.

## Layout of a course repository

```
CLAUDE.md               the course: audience, schedule, rules (short; the template's is for talks)
course.yaml             course, semester, documents (globs + modes + html), publish path
syllabus/syllabus.typ   on the notes theme (kind: "Syllabus")
lectures/L01-<slug>/    notes.typ (+ notes.alts.yaml, figures) or brief.yaml + main.typ for slides
problem-sets/PS01/      ps.typ with #problem and #solution
exams/                  private; never published
assets/                 catalog.yaml + figures (same schema as talks; copy entries from the talks repo)
blocks/                 slide blocks for slide lectures
themes/                 the theme, pulled from the template
notes/                  the course log book
review/                 report.md of the build, review sheets
resources/README.md     where the source material lives (read-only folders), with no copies in git
```

## Equation alt text

PDF/UA-1 refuses an equation without alt text, and notes have hundreds. The rule: **plain
`$...$` in the source**, alt text in a sidecar:

```sh
uv run talks alts lectures/L01-kinematics/notes.typ
```

writes `notes.alts.yaml` with one entry per distinct equation (`src`, `alt`, `status`). New
entries get a *spoken draft* from `themes/speak-math.typ` ("x equals x nought plus v nought t
plus one half a t squared"), `status: draft`. Review them (fix the text, set `reviewed`),
commit the sidecar with the notes. `talks course build` refreshes the sidecar before every
compile, so a new equation never fails the build: it gets a draft and is counted in
`report.md` ("alt text draft 3/41") until reviewed. Equations that left the file are marked
`stale`, never deleted. Key equations written as `#eq(alt: "...")[$ ... $]` carry their own
text; `#eq[...]` without `alt` takes the spoken form.

What good alt text sounds like (the university's accessibility training): say what a reader
would say, define symbols the first time, no "image of"; a long derivation can have a one-line
alt ("the derivation of the range formula") when the steps are in the text.

## Writing a lecture

- Start from `courses/example-course/lectures/L01-kinematics/notes.typ`: `#show: notes.with(...)`,
  then `=` sections. One idea per panel; a `#definition`, a `#concept`, an `#example` with its
  `#work` where the derivation happens live, a `#caution` for the classic mistake, a
  `#checkpoint` for the room, a `#summary` at the end.
- `#work(height: 6cm)[typed solution]`: the typed solution is what students read; the height
  is the space you write in during the lecture. `#blank(height: 4cm)` is space only.
- Figures: `#cat-fig("id", width: 70%, caption: [...])` from the catalog (alt text comes
  along), or `#fig("/assets/figures/x.svg", alt: "...", caption: [...])`; both are numbered.
- The layout pass applies to documents too: compile, look at the pages, fix widows, panel
  breaks and figure placement before posting.

## Publishing

`course.yaml` → `publish: "1-Areas/Teaching/<Semester>/<Course>"` (a path under *My Drive*)
and `publish_modes`. `talks course publish` creates one subfolder per document folder and
uploads the PDFs of those modes and the HTML, through `files.create` only: an existing name
gets `-2`, nothing is overwritten. The Drive folder is what the learning-management system
and the tablet read; the repository is the source.

## Accessibility checklist for posted course files

- PDF compiled with `--pdf-standard ua-1` (the build does this; a failure is an error).
- Every figure and equation has alt text (catalog `alt`, `eq(alt:)`, the `.alts.yaml` sidecar).
- Headings sequential (`=`, `==`, `===`), lists as lists, tables with a header row.
- Colour never carries meaning alone; links have descriptive text.
- Before posting, run the LMS's checker (Canvas: Ally) or Acrobat's accessibility check
  once per document type, keep the report in `review/`.
