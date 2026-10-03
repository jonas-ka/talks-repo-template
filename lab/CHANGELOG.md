# Changelog

Consumers read this before `scripts/lab-templates.sh pull <tag>`.

## v2026.10.2 (2026-10-03)

- CLAUDE.md and the CI scan: the lab's public contact address may appear; the scan checks home-folder and Drive-mirror prefixes and key patterns.
- LOGBOOK_GUIDE: log books compile from the repository root (`typst compile --root . notes/<name>-logbook.typ`), since the template is reached through a shim into `lab/`.

## v2026.10.1 (2026-10-02)

First version, assembled from the canonical copies in `talks-repo` (themes, STYLE, COURSES),
`fastsims` (lab-notebook template, LOGBOOK_GUIDE, FIGURES_README) and `karthein-cv`
(`cv-theme.typ`):

- `themes/karthein.typ` (Touying slides), `karthein-poster.typ`, `karthein-notes.typ`
  (student / lecture / solutions modes), `cv-theme.typ`, `tokens.typ` (shared palette, panels,
  radii, shadows; all themes import it), `speak-math.typ` (spoken alt text, `apply-alts`).
- Logo paths in the slide theme are root-relative (`/themes/logos/...`): the consumer's logos
  stay where they are when the theme lives in `lab/`.
- `notes/labnotes-template.typ`, `docs/*.md`, `matplotlib/<LabName>-figure-template.ipynb`.
- `examples/` compile under PDF/UA-1 in CI; `scripts/lab-templates.sh` for consumers;
  `scripts/sync_drive.py` for the Drive copies.
