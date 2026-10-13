# lab-templates

The Karthein Lab's document templates and style, in one place: Typst themes for slides,
posters, lecture notes, exams, the CV and the lab notebook; the palette and design tokens; the
matplotlib style and the figure-template notebook; and the guides (style on one page, the
figure library, the lab notebook, teaching). Every repository that produces documents uses
these files **from here**, pinned to a version, instead of keeping its own copy.

```
themes/        karthein.typ (Touying slides), karthein-poster.typ (A0), karthein-notes.typ (lecture notes,
               problem sets, syllabi; student/lecture/solutions modes), karthein-exam.typ (written exams,
               with a solutions/rubric mode), cv-theme.typ, tokens.typ (palette, panels, radii, shadows),
               speak-math.typ (spoken alt text for equations), palette.yaml, karthein.mplstyle,
               logos/ (placeholders: real marks live in each private repository)
notes/         labnotes-template.typ (the lab notebook)
docs/          STYLE.md, FIGURES_README.md, LOGBOOK_GUIDE.md, COURSES.md
matplotlib/    <LabName>-figure-template.ipynb
assets/        catalog.yaml, figures/, sources/: the one public example figure (BLS data), with the
               script and data that draw it, so the examples compile
examples/      one small document per theme; CI compiles them (PDF/UA-1)
scripts/       lab-templates.sh (for consumers: add / pull / push / status / check),
               propagate.sh (maintainer: a tag into every consumer), sync_drive.py (README copies to Drive)
CHANGELOG.md   what changed in each tag; VERSION holds the current one
```

## What you need

- **Typst 0.15.1** (the version the CI uses). Typst downloads the packages on the first compile:
  `@preview/touying:0.6.1` (slides) and `@preview/mitex:0.2.7` (LaTeX math in slides).
- **Fonts:** STIX Two Text and STIX Two Math for every theme (free, stixfonts.org; macOS ships
  both). The lab notebook uses Libertinus Serif, which is built into Typst.
- **matplotlib** for `themes/karthein.mplstyle` and the figure notebook; `make` for `make check`.

Check a change with `make check`: it compiles every `examples/*.typ` with `--pdf-standard ua-1`
into `build/`.

## Using the templates in a repository

Consumers carry this repository as a **git subtree** in `lab/` (plain files: Typst, Drive and
colleagues see nothing special) and keep one-line shims at their old paths
(`themes/karthein.typ` → `#import "/lab/themes/karthein.typ": *`), so nothing else changes.

```sh
# once, in the consumer repository (clean working tree), with a copy of scripts/lab-templates.sh
scripts/lab-templates.sh add <tag>
# from then on use the copy in lab/, which every pull keeps current
sh lab/scripts/lab-templates.sh check            # is a newer tag out?
sh lab/scripts/lab-templates.sh pull latest      # update to the newest tag (or: pull <tag>)
sh lab/scripts/lab-templates.sh push             # a theme edit made inside the consumer goes upstream
sh lab/scripts/lab-templates.sh status           # which version this repository has
```

`lab/VERSION` records the version in use. Versions are tags `vYYYY.MM.N`. Themes read two
things from the consumer: `/assets/catalog.yaml` (figures with alt text, via `cat-fig`) and
`/themes/logos/<name>` (the real logos, never in this public repository). This repository has
its own placeholder copies of both so that the examples compile.

## Staying up to date

**Every consumer checks for a newer template before it builds.** Put this line first in the
build: the `Makefile` target, the build command (`talks`, `cv`, …) or the CI job.

```sh
sh lab/scripts/lab-templates.sh check
```

When the repository is current it prints one line. When a newer tag is out it says which one,
where the changes are listed, and the command that updates (`pull latest`). It never pulls on
its own and never fails the build; offline it says it did not check. A template update
re-flows every document built on it, so the update is made on purpose: read the changelog,
pull, rebuild, look at the result, commit. The maintainer does this for all consumers at once
with `scripts/propagate.sh <tag>` (pull, build check, commit, push per repository, using the
local credentials).

In a `Makefile`:

```make
pdf: lab-check
lab-check:
	@sh lab/scripts/lab-templates.sh check
```

In a Python command: `subprocess.run(["sh", "lab/scripts/lab-templates.sh", "check"])`.

## Rules

- Edit a theme **here** (or inside a consumer and `push`), never in a copy.
- Every change compiles the examples (`make check` or the CI) before it is tagged.
- `docs/FIGURES_README.md` is the canonical figure-library README; `scripts/sync_drive.py`
  uploads it, with the notebook template and guide, to the lab's Drive folders, create-only
  with a versioned name.
- Logos are placeholders here; consumers keep theirs in `themes/logos/`, which the update
  never touches.

Licence: MIT (`LICENSE`), for the code, the themes and the documents alike. Logos are not
included.
