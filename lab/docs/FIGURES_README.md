# Karthein Lab figure library — how to add (back up) a figure

This folder is the lab's shared figure library. Every plot, schematic or diagram anyone
in the group makes for a talk, a poster or a paper lives here, **one folder per figure**,
with everything needed to reuse it as it is or to change it: the compiled figure in three
formats, the code that made it, and the data it was made from. Talks and posters built
with the group's talk pipeline (`talks-repo`) pull figures from here; the pipeline also
mirrors its own figures into this folder automatically.

## One folder per figure, every version kept

```
Figures/
  plot-<topic>-<what-it-shows>/                 one folder per figure, named like the figure
    plot-<topic>-<what-it-shows>-v1.pdf          version 1: vector original
    plot-<topic>-<what-it-shows>-v1.svg          the same as SVG
    plot-<topic>-<what-it-shows>-v1.png          the same at 300 dpi
    plot-<topic>-<what-it-shows>-v1.yaml         its record (written by labfig, below)
    plot-<topic>-<what-it-shows>-v2.pdf / .svg / .png / .yaml    version 2; the newest is the highest number
    plot-<topic>-<what-it-shows>-poster-v2.pdf / … / .yaml       a variant of version 2
    figure.yaml                                  caption, alt text, topic (written by people)
    code/                                        the script or notebook, one copy per version (a few kB)
    data/                                        the data the figure draws, each data set once
```

Folder and file names: hyphens, no spaces, lower case except names that are written with
capitals (FastSims, H200), starting with the kind:
`plot-` (data plot), `schematic-` (drawing, diagram), `table-`, `photo-` (photos go to
`../Photos/`). Example: `plot-speed-comparisons-legacy-FastSims-Surrogate-M4Pro-H200`, `schematic-mr-tof-principle`.

**Nothing in a figure folder is ever overwritten, moved or renamed.** A version, once saved,
stays as it is; a change adds the next version beside it. Folders made before 2026-10-13 keep
their old layout (latest at the top level, older ones in `v<N>_<date>_<name>/`); their next
version follows this one.

## Adding a new figure, step by step

1. **Make the figure** in a Colab notebook or a script (see
   `_<LabName>-figure-template-README.ipynb` here for the lab style: STIX font, the lab
   colours `#FFCC00 #FF2D55 #00A2FF #61D935`, colour-blind-safe order, one message per
   figure). Save it with the lab's figure helper `labfig` (lab-templates `matplotlib/labfig.py`):

   ```python
   labfig.save(fig, f"Figures/{name}/{name}", version=1, author="A. Author", created="2026-10-13",
               data=[f"Figures/{name}/data/{name}.csv"],
               drive_folder=f"Figures/{name}", drive_url="<the folder's link>")
   ```

   It writes, in the figure's folder:
   - `<name>-v1.pdf/.svg/.png`, the figure in three formats from the same figure object, with
     the **information strip** below it (next point);
   - `<name>-v1.yaml`, the **record**: author, dates, version, the lab-templates version, the
     script's repository and commit, the data files with their fingerprints, the Drive folder;
   - `code/<script>-v1.py`, a **copy of the script** that drew it (from a notebook, pass
     `code="<path of the notebook>"`; `code=None` for a script already in git, whose commit the
     record keeps anyway).

   **A version is never overwritten:** `labfig.save` refuses to write a version whose files
   exist and names the next free number. While you are still working on the figure, save with
   `draft=True` (`<name>-draft.*`, overwritten freely, no record). **A version is frozen once
   it has left your desk:** committed to git, put on the Drive, or used in a document (a talk,
   poster, paper, log-book entry). Until then it may still be redrawn under the same number;
   from then on every change is the next version. If unsure, save a draft.

   **The information strip** is a band under a dashed line at the bottom of every file: who
   made the figure and when, who changed it last and when (`modified_by`, `modified`), its
   version; the lab-templates version and git id it was made with (linked to the repository),
   the data fingerprint, and the Drive folder (the name as text; linked in PDF and SVG, a PNG
   cannot hold links). It keeps the figure's origin with the file wherever it travels. **Cut it
   off when the figure goes into a paper, talk or poster:** it is the bottom 0.4 in, under the
   dashed line (crop in the slide or layout program, or `trim` in LaTeX). The lab's Typst themes
   cut it automatically: they find it in the SVG (labfig writes a marker into the files'
   metadata), and a catalog entry can also say `info_strip: 0.4`. `info=False` saves without it.

   **The data fingerprint** is a checksum (SHA-256) over the names and contents of the files
   given as `data=`; the strip shows its first 7 characters ("Data: 3f2a9c1"). The same data
   gives the same fingerprint, any change a different one: it shows which versions share data,
   and `labfig.fingerprint(path)` checks whether data found later is exactly what a figure was
   made from. `data_id="VISION job 585537"` adds a label, or stands alone for data too large to
   read on every save.

2. **Put the data in `data/`:** the numbers the figure actually draws (CSV, npz, …), usually
   small even when the raw data is not. Raw data too large for Drive, or living elsewhere (a lab
   computer, a repository, a cluster), stays where it is: put a short `data/WHERE.md` saying
   exactly where and how to get it; the fingerprint in the record proves it is the right data.

   **Link the raw data both ways** with `raw=[...]` in `labfig.save` (a folder or file in a
   repository or on the Drive, a URL, or a description like `"VISION /scratch/run42"`):
   - **figure → data:** the record lists each raw location (a repository and the path in it,
     the Drive path, or the description as given);
   - **data → figure:** next to every raw location on this computer, `labfig.save` appends a line
     to a `FIGURES.yaml` (figure, version, Drive folder and link, record). Anyone who finds the
     raw data sees which figures were made from it; commit that file where the data is in git.
   - **Asking later:** `uv run python lab/matplotlib/labfig.py where-used <data file or folder>`
     lists the figures made from it (from `FIGURES.yaml`, and with `--archive <Figures folder>`
     from every record whose data has the same checksum, also for data with no `FIGURES.yaml`,
     e.g. on a cluster).
3. **Write `figure.yaml`** (copy the block below). The caption and the alt text are yours to
   write: the caption is the one line under the figure; the alt text describes what is in
   the picture and what it shows, for readers who cannot see it ("Log-log plot of throughput
   against ions in flight; the H200 curve levels off at 1.6e8, 72 times the laptop"). They
   describe the newest version: update them when a new version shows something else.

   ```yaml
   id: plot-speed-comparisons-legacy-FastSims-Surrogate-M4Pro-H200
   kind: plot                 # plot | schematic | table | photo
   topic: [genesis, hpc]      # a few keywords for searching
   caption: "Tracker throughput on one H200 against ions in flight; 72x a laptop CPU."
   alt: "Log-log plot of ion-steps per second against ions in flight. The H200 curve ..."
   notes: ""
   ```

4. Done. No index to edit; a dated `index-YYYY-MM-DD.csv` is written here now and then by
   the pipeline.

## Changing a figure: the next version

**Every visual change is a new version, and so is every change of its data.** Save it with the
next number, keeping the original `author` and `created` and adding who changed it and when:

```python
labfig.save(fig, f"Figures/{name}/{name}", version=2, author="A. Author", created="2026-10-13",
            modified_by="B. Person", modified="2026-11-02", data=[...], drive_folder=..., drive_url=...)
```

- **Data is never overwritten either.** Changed data goes into `data/` under a new name
  (`run42-recalibrated.csv`), so every version keeps the data it was made from. Unchanged data
  is simply listed again: five versions on the same data store it once. `labfig.save` warns when
  a data file an earlier version used has changed since.
- **A new folder is for a different figure,** not for new data: a different quantity, experiment
  or message gets its own name. New measurements, a corrected calibration or a later month of
  the same plot are the next version of the same figure, so its history stays in one place and
  the newest version is always the highest number.

**Variants** (a poster version, a talk crop) live in the **same folder**, never in a folder of
their own: save them under the figure's name with the variant added, `<name>-poster`, with the
number of the version they belong to (`<name>-poster-v2.*`). A version and its variants share a
number.

## Style (general rules, 2026-10-01)

- **`plt.subplots`** for every figure, also multi-panel ones (`sharey=True`, `width_ratios=…`),
  saved with `labfig.save` as PDF + SVG + PNG (300 dpi) from the same figure object.
- **Colours: the lab four,** `#FFCC00` yellow, `#FF2D55` red, `#00A2FF` blue, `#61D935` green
  (then black, grey). One colour per *thing*, kept across panels and figures (e.g. the AI model
  is red everywhere).
- **Black** ticks, tick labels, axis labels and frame. No grey text.
- **A full box** around every plot: all four spines. Not only bottom and left axes lines.
- **Bold axis labels** (`fontweight="bold"`), regular tick labels, so the eye separates the two;
  15 pt labels / 13 pt ticks at the template's 6×4 in, scaled with the figure. The same figure
  serves slides and papers (on a slide beside text it shows at about 12/11 pt, in a paper
  column at about 9/8 pt); posters get their own variant (below).
- **Physical quantities in italics**, as in print: *N*, *Z*, *A*, *Q*₀, *μ*, *β*₃, *T*, *E*
  (`r"Neutron number $\mathbfit{N}$"` in a bold label, `$N$` elsewhere); units, element symbols,
  labels such as "OES" and subscripts that are words stay upright.
- **Legend inside the box, without a border** (`frameon=False`), placed where no data is. Or
  replace it by short text labels next to the curves, which is often easier to read. Never a
  boxed legend floating outside the plot.
- **Annotations** (arrows, gains, times) in black text; the arrow or marker carries the colour.
  Coloured text, where it is needed, uses the darker `plot_text` colours in `palette.yaml`
  (`#8E7200` yellow, `#3C8620` green, …): the lab yellow and green are hard to read on white.
- **Text never sits on data.** Labels and annotations go where the plot is empty; a label for a
  curve's end goes beside the end (extend the axis range a little to make room); if there is no
  empty region, shorten the label or use a thin leader line to a clear spot. Check the render:
  a label crossing a line or a marker is hard to read.
- **Lines that connect panels** are drawn once across the figure (`matplotlib.patches.ConnectionPatch`),
  not as separate pieces per panel.
- **Run figure scripts with uv:** `uv run plot_x.py`, with the dependencies pinned in the
  script's inline metadata or in the project's `pyproject.toml` and `uv.lock`:

  ```python
  # /// script
  # requires-python = ">=3.11"
  # dependencies = ["matplotlib==3.11.2", "numpy==2.5.4"]
  # ///
  ```

  `labfig.save` refuses to write a version from a script not run by uv, and records the
  environment (Python and package versions, the inline metadata or the `uv.lock` checksum), so
  the figure can be redrawn in the same environment. Colab notebooks and drafts are exempt.
- STIX fonts (`STIX Two Text` / `STIXGeneral`, mathtext `stix`), as in the template notebook.
  **Start every figure script with the lab style:** `labfig.style()` (`matplotlib/labfig.py` in
  lab-templates; in a repository that carries the templates, `sys.path.insert(0, "lab/matplotlib")`
  first; in Colab, the template notebook's first cell does it). It applies `themes/karthein.mplstyle`:
  the fonts, the colours, the black frame and text, the label and tick sizes, frameless legends and
  editable text in PDF; setting size and weight alone falls back to DejaVu Sans. Where STIX Two is not
  installed (Colab), it uses STIXGeneral, which ships with matplotlib.

## Rules of the folder

- **Nothing is deleted, overwritten, moved or renamed.** Add files: a change is the next version
  beside the old ones, changed data a new file. Ask the author before removing anything.
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
purpose — the author writes them. (The pipeline does not yet write the versioned names and
records above; until it does, its folders follow the older layout.)

Questions: <Your Name>, you@example.edu.
