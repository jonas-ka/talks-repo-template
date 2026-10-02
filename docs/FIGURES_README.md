# Karthein Lab figure library — how to add (back up) a figure

This folder is the lab's shared figure library. Every plot, schematic or diagram anyone
in the group makes for a talk, a poster or a paper lives here, **one folder per figure**,
with everything needed to reuse it as it is or to change it: the compiled figure in three
formats, the code that made it, and the data it was made from. Talks and posters built
with the group's talk pipeline (`talks-repo`) pull figures from here; the pipeline also
mirrors its own figures into this folder automatically.

## One folder per figure

```
Figures/
  plot-<topic>-<what-it-shows>/        one folder, named like the figure
    plot-<topic>-<what-it-shows>.pdf   vector original (or .svg if that is the original)
    plot-<topic>-<what-it-shows>.svg   the same figure as SVG
    plot-<topic>-<what-it-shows>.png   the same figure at 300 dpi
    figure.yaml                        what it is, where it comes from, caption, alt text
    code/                              the notebook or script that draws it
    data/                              the numbers it draws (CSV, npz, …) or a note where they are
```

Folder and file names: lower case, hyphens, no spaces, starting with the kind:
`plot-` (data plot), `schematic-` (drawing, diagram), `table-`, `photo-` (photos go to
`../Photos/`). Example: `plot-speed-comparisons-legacy-FastSims-Surrogate-M4Pro-H200`, `schematic-mr-tof-principle`.

## Adding a new figure, step by step

1. **Make the figure** in a Colab notebook or a script (see
   `_<LabName>-figure-template-README.ipynb` here for the lab style: STIX font, the lab
   colours `#FFCC00 #FF2D55 #00A2FF #61D935`, colour-blind-safe order, one message per
   figure). Save all three formats from the same figure object:

   ```python
   for ext, kw in (("pdf", {}), ("svg", {}), ("png", {"dpi": 300})):
       fig.savefig(f"{name}.{ext}", bbox_inches="tight", **kw)
   ```

2. **Create the folder** `Figures/<name>/` and put the three files in it.
3. **Add `code/`** with the notebook or script (a copy is fine; note the git commit if it
   lives in a repository) and **`data/`** with the input files. If the data is too large
   for Drive or lives elsewhere (a lab computer, a repository, a cluster), put a short
   `data/WHERE.md` saying exactly where and how to get it.
4. **Write `figure.yaml`** (copy the block below). The caption and the alt text are yours to
   write: the caption is the one line under the figure; the alt text describes what is in
   the picture and what it shows, for readers who cannot see it ("Log-log plot of throughput
   against ions in flight; the H200 curve levels off at 1.6e8, 72 times the laptop").

   ```yaml
   id: plot-speed-comparisons-legacy-FastSims-Surrogate-M4Pro-H200
   kind: plot                 # plot | schematic | table | photo
   topic: [genesis, hpc]      # a few keywords for searching
   caption: "Tracker throughput on one H200 against ions in flight; 72x a laptop CPU."
   alt: "Log-log plot of ion-steps per second against ions in flight. The H200 curve ..."
   source: "fastsims scripts/talk_figures.py, VISION jobs 585537 and 585681"
   author: "J. Karthein"
   date: 2026-09-24
   supersedes: null           # id of an older figure this one replaces, if any
   notes: ""
   ```

5. Done. No index to edit; a dated `index-YYYY-MM-DD.csv` is written here now and then by
   the pipeline.

## Changing an existing figure: one folder per plot (since 2026-10-01)

Each plot has **one folder**, and its top level always holds the **latest version** (`<name>.pdf`,
`.svg`, `.png`, `code/`, `data/`, `figure.yaml`). When the figure changes:

1. Move everything at the top level of the folder, unchanged, into a subfolder named
   **`v<N>_<YYYY-MM-DD>_<name>/`**: the version number and the date that version was made,
   prepended to the figure's name (`v2_2026-09-30_plot-speed-comparisons-legacy-FastSims-Surrogate-M4Pro-H200/`).
2. Put the new version in the top level of the folder, under the plot's name.
3. In the new `figure.yaml`, raise `version` by one and set `supersedes:` to the old version's id
   (`<name>-vN`; version 1 is just `<name>`).

So a folder lists the current figure first and its history in dated subfolders, instead of a
`-v2`, `-v3`, … folder per change.

**Variants** (a poster version, a talk crop) live in the **same folder**, never in a folder of their
own. The top level is the normal (slide/paper) version. Version N's poster version goes in
`v<N>_<YYYY-MM-DD>_<name>-poster-version/`, with files `<name>-poster.{pdf,svg,png}`, its own
`code/`, `data/` and `figure.yaml` (`variant: poster`). The same applies to `-talk-version` and
other variants, so a version and its variants share a number:

```
plot-speed-comparisons-legacy-FastSims-Surrogate-M4Pro-H200/
  plot-speed-comparisons-legacy-FastSims-Surrogate-M4Pro-H200.pdf / .svg / .png, code/, data/, figure.yaml   <- v7, the normal version
  v7_2026-10-01_plot-speed-comparisons-legacy-FastSims-Surrogate-M4Pro-H200-poster-version/                 <- v7, poster version
  v6_2026-10-01_plot-speed-comparisons-legacy-FastSims-Surrogate-M4Pro-H200/                                <- v6, normal
  v6_2026-10-01_plot-speed-comparisons-legacy-FastSims-Surrogate-M4Pro-H200-poster-version/                 <- v6, poster
  ...
```

## Style (general rules, 2026-10-01)

- **`plt.subplots`** for every figure, also multi-panel ones (`sharey=True`, `width_ratios=…`),
  saved with `bbox_inches="tight"` as PDF + SVG + PNG (300 dpi) from the same figure object.
- **Colours: the lab four,** `#FFCC00` yellow, `#FF2D55` red, `#00A2FF` blue, `#61D935` green
  (then black, grey). One colour per *thing*, kept across panels and figures (e.g. the AI model
  is red everywhere).
- **Black** ticks, tick labels, axis labels and frame. No grey text.
- **A full box** around every plot: all four spines. Not only bottom and left axes lines.
- **Bold axis labels** (`fontweight="bold"`), regular tick labels, so the eye separates the two;
  15 pt labels / 13 pt ticks at the template's 6×4 in, scaled with the figure.
- **Legend inside the box, without a border** (`frameon=False`), placed where no data is. Or
  replace it by short text labels next to the curves, which is often easier to read. Never a
  boxed legend floating outside the plot.
- **Annotations** (arrows, gains, times) in black text; the arrow or marker carries the colour.
- **Text never sits on data.** Labels and annotations go where the plot is empty; a label for a
  curve's end goes beside the end (extend the axis range a little to make room); if there is no
  empty region, shorten the label or use a thin leader line to a clear spot. Check the render:
  a label crossing a line or a marker is hard to read.
  Coloured *text* in the lab yellow or green is hard to read on white.
- **Lines that connect panels** are drawn once across the figure (`matplotlib.patches.ConnectionPatch`),
  not as separate pieces per panel.
- STIX fonts (`STIX Two Text` / `STIXGeneral`, mathtext `stix`), as in the template notebook.

## Rules of the folder

- **Nothing is deleted.** Add folders and files; an update *moves* the previous version into its
  dated subfolder (above), it never deletes or overwrites it. Ask the author before removing anything.
- **Vector first.** A plot is a PDF or SVG whenever it was drawn as one; the PNG is a
  convenience copy at 300 dpi, never the only file. Photos stay raster at their full size.
- **Loose files** in `Figures/` itself (not in a folder) are not part of the library. Put
  yours into a folder as above; the `_to-sort` folder is the waiting room.
- **Every figure has a caption and alt text** in `figure.yaml` before it goes into a talk
  or a poster: the university's accessibility rules apply to posted PDFs, and the pipeline
  refuses figures without alt text.

## Coming from talks-repo

Figures made in the group's talk pipeline are mirrored here by `uv run talks sync-drive`
(one command, append-only): the same three formats, `figure.yaml`, and `code/` and `data/`
where the catalog knows them. Their `figure.yaml` has empty `caption` and `alt` fields on
purpose — the author writes them.

Questions: <Your Name>, you@example.edu.
