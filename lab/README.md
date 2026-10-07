# lab-templates

The Karthein Lab's document templates and style, in one place: Typst themes for slides,
posters, lecture notes, the CV and the lab notebook; the palette and design tokens; the
matplotlib style and the figure-template notebook; and the guides (style on one page, the
figure library, the lab notebook, teaching). Every repository that produces documents uses
these files **from here**, pinned to a version, instead of keeping its own copy.

```
themes/        karthein.typ (Touying slides), karthein-poster.typ (A0), karthein-notes.typ (lecture notes,
               problem sets, syllabi; student/lecture/solutions modes), cv-theme.typ, tokens.typ (palette,
               panels, radii, shadows), speak-math.typ (spoken alt text for equations), palette.yaml,
               karthein.mplstyle, logos/ (placeholders: real marks live in each private repository)
notes/         labnotes-template.typ (the lab notebook)
docs/          STYLE.md, FIGURES_README.md, LOGBOOK_GUIDE.md, COURSES.md
matplotlib/    <LabName>-figure-template.ipynb
examples/      one small document per theme; CI compiles them (PDF/UA-1)
scripts/       lab-templates.sh (for consumers: add / pull / push / status), sync_drive.py (README copies to Drive)
```

## Using the templates in a repository

Consumers carry this repository as a **git subtree** in `lab/` (plain files: Typst, Drive and
colleagues see nothing special) and keep one-line shims at their old paths
(`themes/karthein.typ` → `#import "/lab/themes/karthein.typ": *`), so nothing else changes.

```sh
# once, in the consumer repository (clean working tree)
scripts/lab-templates.sh add v2026.10.1
# later: update to a tag, after reading CHANGELOG.md
scripts/lab-templates.sh pull v2026.10.2
# a theme edit made inside the consumer goes upstream
scripts/lab-templates.sh push
scripts/lab-templates.sh status      # which version this repository has
```

`lab/VERSION` records the version in use. Versions are tags `vYYYY.MM.N`; a consumer is never
updated silently, because a theme change re-flows every document built on it. The maintainer
updates all consumers at once with `scripts/propagate.sh <tag>` (pull, build check, commit,
push per repository, using the local credentials).

Themes read two things from the consumer: `/assets/catalog.yaml` (figures with alt text, via
`cat-fig`) and `/themes/logos/<name>` (the real logos, never in this public repository).

## Rules

- Edit a theme **here** (or inside a consumer and `push`), never in a copy.
- Every change compiles the examples (`make check` or the CI) before it is tagged.
- `docs/FIGURES_README.md` is the canonical figure-library README; `scripts/sync_drive.py`
  uploads it, with the notebook template and guide, to the lab's Drive folders, create-only
  with a versioned name.
- Logos are placeholders here; consumers keep theirs in `themes/logos/`, which the update
  never touches.

Licence: MIT for code, CC BY 4.0 for themes and documents (attribution: Karthein Lab, Texas
A&M University). Logos are not included.
