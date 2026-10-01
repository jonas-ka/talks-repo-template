"""Command-line entry point: `uv run talks <stage>`."""

import csv
from pathlib import Path
from typing import Annotated

import typer

from talks_repo import REVIEW_DIR, TALKS_YAML, WORK_DIR
from talks_repo import cv as cv_stage
from talks_repo import manifest

app = typer.Typer(help="Pipeline stages for talks-repo.", no_args_is_help=True)


@app.callback()
def _root() -> None:
    """Pipeline stages for talks-repo. Each stage is resumable."""

# Fields Stage A owns. --force rewrites these; fields added by later stages
# (duration, audience, files, archive, ...) are never touched by Stage A.
_STAGE_A_FIELDS = ("date", "title", "event", "qualifier", "award", "location", "type", "era")


@app.command("ingest-cv")
def ingest_cv(
    offline: Annotated[
        bool, typer.Option(help="Use the cached work/cv.txt instead of downloading.")
    ] = False,
    force: Annotated[
        bool, typer.Option(help="Rewrite CV-derived fields of entries that already exist.")
    ] = False,
) -> None:
    """Stage A: parse the CV's Presentations section into talks.yaml."""
    WORK_DIR.mkdir(exist_ok=True)
    cache = WORK_DIR / "cv.txt"
    if offline:
        if not cache.exists():
            raise typer.BadParameter(f"--offline given but {cache} does not exist")
        text = cache.read_text(encoding="utf-8")
    else:
        text = cv_stage.fetch_cv_text()
        cache.write_text(text, encoding="utf-8")

    parsed, unparsed = cv_stage.parse_cv(text)
    ids = cv_stage.make_ids(parsed)

    existing = manifest.load(TALKS_YAML)
    by_index = {e["cv_index"]: e for e in existing if e.get("cv_index") is not None}
    added = updated = kept = 0
    for talk in parsed:
        fresh = cv_stage.to_entry(talk, ids[talk.cv_index])
        current = by_index.get(talk.cv_index)
        if current is None:
            existing.append(fresh)
            added += 1
        elif force:
            for key in _STAGE_A_FIELDS:
                current[key] = fresh[key]
            updated += 1
        else:
            kept += 1
    existing.sort(key=lambda e: (str(e.get("date", "")), e.get("cv_index", 0)))
    manifest.save(TALKS_YAML, existing, manifest.TALKS_HEADER)

    sheet = _write_review_sheet(parsed, ids, unparsed)

    flagged = sum(1 for t in parsed if t.flags)
    typer.echo(f"Parsed {len(parsed)} presentations, {len(unparsed)} lines unparsed.")
    typer.echo(f"talks.yaml: {added} added, {updated} updated, {kept} kept unchanged.")
    typer.echo(f"Review sheet: {sheet.relative_to(TALKS_YAML.parent)} ({flagged} flagged rows).")


@app.command("discover")
def discover_cmd(
    root: Annotated[
        list[str] | None,
        typer.Option(help="Only walk these roots (tamu, mit, phd). Default: all."),
    ] = None,
    fetch_cloud: Annotated[
        bool, typer.Option(help="Open cloud-only Google Drive files (forces their download).")
    ] = False,
    force: Annotated[
        bool, typer.Option(help="Re-analyze every file and rewrite source_file/pdf_file in talks.yaml.")
    ] = False,
) -> None:
    """Stage C: find deck files in the input folders, pair them, and match them to talks."""
    from talks_repo import stage_c

    counts = stage_c.run(root, fetch_cloud, force)
    sheets = counts.pop("sheets")
    typer.echo(
        f"Files: {counts['files']} recorded, {counts.get('analyzed', 0)} analyzed this run, "
        f"{counts.get('cloud_skipped', 0)} cloud-only skipped."
    )
    typer.echo(
        f"Decks: {counts['decks']} ({counts['own_decks']} own, {counts['borderline']} borderline) "
        f"in {counts['groups']} groups, {counts['matched_groups']} groups matched to talks."
    )
    typer.echo(
        f"Talks with files: {counts['talks_with_files']}. Folders without a deck: {counts['folders_no_talk']}."
    )
    for sheet in sheets:
        typer.echo(f"Review sheet: {sheet}")


@app.command("enrich")
def enrich_cmd(
    skip_era: Annotated[
        list[str] | None,
        typer.Option(help="Eras whose folders are not scanned for programmes (rules only). Default: PhD."),
    ] = None,
) -> None:
    """Stage B: fill duration, audience, format from rules and local programme PDFs."""
    from talks_repo import FILES_YAML, enrich

    skip = set(skip_era) if skip_era is not None else {"PhD"}
    talks = manifest.load(TALKS_YAML)
    files = manifest.load(FILES_YAML)
    rows = []
    for talk in talks:
        report = enrich.enrich_talk(talk, files, skip_programs=talk.get("era") in skip)
        rows.append({"id": talk["id"], "era": talk.get("era"), "date": talk.get("date"),
                     "event": talk.get("event"), "type": talk.get("type"),
                     "duration_min": talk.get("duration_min"), "audience": talk.get("audience"),
                     "format": talk.get("format"), "source_url": talk.get("source_url") or "", **report})
    manifest.save(TALKS_YAML, talks, manifest.TALKS_HEADER)

    order = {"UNI": 0, "MIT": 1, "PhD": 2}
    rows.sort(key=lambda r: (order.get(str(r["era"]), 9), r["confidence"] >= 0.7, str(r["date"])))
    REVIEW_DIR.mkdir(exist_ok=True)
    sheet = REVIEW_DIR / "stage-b-gaps.csv"
    cols = ["needs", "confidence", "id", "era", "date", "event", "type", "duration_min", "audience",
            "format", "rule", "programme_snippet", "programme_file", "source_url", "filled"]
    with sheet.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    gaps = sum(1 for r in rows if r["confidence"] < 0.7)
    hits = sum(1 for r in rows if r["programme_snippet"])
    typer.echo(f"{len(rows)} talks enriched; {hits} with a programme snippet; {gaps} below 0.7 confidence.")
    typer.echo(f"Gaps sheet: {sheet.relative_to(TALKS_YAML.parent)}")


@app.command("export")
def export_cmd(
    root: Annotated[list[str] | None, typer.Option(help="Only talks whose files are in these roots.")] = None,
    talk_id: Annotated[list[str] | None, typer.Option("--id", help="Only these talk ids.")] = None,
    kind: Annotated[
        list[str] | None,
        typer.Option(help="Only these source kinds: key, pptx, pdf, gslides. Default: all."),
    ] = None,
    limit: Annotated[int | None, typer.Option(help="Stop after this many successful exports.")] = None,
    force: Annotated[bool, typer.Option(help="Re-export talks that already have an archive folder.")] = False,
    max_errors: Annotated[int, typer.Option(help="Stop after this many consecutive failures; 0 = never stop.")] = 3,
) -> None:
    """Stage D: export attached decks into archive/<talk-id>/ (UNI first, newest first)."""
    from talks_repo import export

    kinds = {f".{k.lstrip('.')}" for k in kind} if kind else None
    results = export.run(manifest.load(TALKS_YAML), root, talk_id, kinds, force, limit, max_errors)
    from collections import Counter

    for tid, status in results:
        if status not in ("already-exported", "skipped-kind"):
            typer.echo(f"  {tid}: {status}")
    counts = Counter(s.split(":")[0] for _, s in results)
    typer.echo("Summary: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))


@app.command("extract")
def extract_cmd(
    talk_id: Annotated[list[str] | None, typer.Option("--id", help="Only these talk ids.")] = None,
    limit: Annotated[int | None, typer.Option(help="Stop after this many talks (priority order).")] = None,
    force: Annotated[bool, typer.Option(help="Re-extract talks that already have extract.json.")] = False,
) -> None:
    """Stage E: per-slide text, notes, pictures, build sequences; global image index + contact sheet."""
    import json

    from talks_repo import extract

    order = {"UNI": 0, "MIT": 1, "PhD": 2}
    talks = sorted(manifest.load(TALKS_YAML), key=lambda t: (order.get(str(t.get("era")), 9), str(t.get("date"))), reverse=False)
    talks.sort(key=lambda t: order.get(str(t.get("era")), 9))
    results = []
    for talk in talks:
        if talk_id and talk["id"] not in talk_id:
            continue
        r = extract.extract_talk(talk, force=force)
        if r is None:
            continue
        results.append(r)
        typer.echo(f"  {talk['id']}: " + "; ".join(r["steps"]))
        if limit and len(results) >= limit:
            break
    # The index always covers every talk that has an extract.json, not just this run.
    all_results = []
    for p in sorted(extract.ARCHIVE_DIR.glob("*/extract.json")):
        all_results.append(json.loads(p.read_text(encoding="utf-8")))
    index = extract.build_index(all_results)
    made = extract.write_thumbnails(index)
    extract.EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    (extract.EXTRACT_DIR / "images.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    sheets = extract.write_review(index, all_results)
    typer.echo(
        f"Index: {index['n_pictures']} picture uses, {index['n_exact_unique']} distinct files, "
        f"{index['n_images']} unique images across {len(all_results)} talks ({made} new thumbnails)."
    )
    for s in sheets:
        typer.echo(f"Review: {s}")


classify_app = typer.Typer(help="Stage E part 2: classify unique images with Claude vision (Batch API).")
app.add_typer(classify_app, name="classify")


@classify_app.command("submit")
def classify_submit(
    limit: Annotated[int | None, typer.Option(help="Send at most this many images.")] = None,
    dry_run: Annotated[bool, typer.Option(help="Build the requests but do not call the API.")] = False,
) -> None:
    """Send every not-yet-classified image from work/extract/images.json as one batch."""
    from talks_repo import classify

    s = classify.submit(limit=limit, dry_run=dry_run)
    typer.echo(f"{s['requests']} requests built, {s['skipped']} skipped as tiny/unreadable, "
               f"{s['already_classified']} already classified.")
    if s.get("batch_ids"):
        typer.echo(f"Submitted {len(s['batch_ids'])} batch(es): {', '.join(s['batch_ids'])}. "
                   "Collect with: uv run talks classify collect --wait")


@classify_app.command("collect")
def classify_collect(
    wait: Annotated[bool, typer.Option(help="Poll until every pending batch has ended.")] = False,
) -> None:
    """Fetch finished batches into review/stage-e/classified.yaml and refresh the review sheets."""
    from talks_repo import classify

    s = classify.collect(wait=wait)
    typer.echo(f"Collected {s['collected']} results, {s['errored']} errors, {s['still_processing']} batches still processing.")
    if s["collected"]:
        typer.echo("Refresh the sheets with: uv run talks extract")


@app.command("equations")
def equations_cmd() -> None:
    """Stage F: LaTeX from Keynote packages, Slides notes, and vision; render + review sheet."""
    from talks_repo import equations

    talks = manifest.load(TALKS_YAML)
    eqs, log = equations.collect(talks)
    rendered = sum(1 for eq in eqs.values() if equations.render(eq))
    for eq in eqs.values():
        equations.verify(eq)
    new = equations.write_assets(eqs)
    sheets = equations.write_review(eqs, log)
    from collections import Counter

    by_source = Counter(s["source"] for eq in eqs.values() for s in eq.sources)
    typer.echo(f"{len(eqs)} unique equations ({rendered} rendered, {new} new .tex files); uses by source: {dict(by_source)}")
    for s in sheets:
        typer.echo(f"Review: {s}")


@app.command("catalog")
def catalog_cmd(
    copy_all: Annotated[bool, typer.Option(help="Also copy photos, screenshots and logos into assets/figures/.")] = False,
    min_talks: Annotated[int, typer.Option(help="A slide title must recur in this many talks to be a block candidate.")] = 3,
) -> None:
    """Stage G: build assets/catalog.yaml from classified images + equations; propose blocks."""
    from talks_repo import catalog

    entries, counts = catalog.build_entries(copy_all=copy_all)
    n_eq = catalog.equation_entries(entries)
    catalog.write_catalog(entries)
    blocks = catalog.block_candidates(min_talks=min_talks)
    sheets = catalog.write_review(entries, blocks)
    kinds = {k: v for k, v in counts.items() if k in catalog.CATALOG_KINDS}
    typer.echo(f"Catalog: {len(entries)} entries ({n_eq} equations); by kind {kinds}; "
               f"copied {counts.get('copied', 0)} files; unclassified {counts.get('unclassified', 0)}; "
               f"skipped {sum(v for k, v in counts.items() if k.startswith('skipped'))} decoration/text.")
    typer.echo(f"Block candidates: {len(blocks)} recurring slide titles in >= {min_talks} talks.")
    for s in sheets:
        typer.echo(f"Review: {s}")


@app.command("generate")
def generate_cmd(
    slug: Annotated[str, typer.Argument(help="talks/<slug>/ containing brief.yaml")],
    force: Annotated[bool, typer.Option(help="Overwrite an existing main.typ.")] = False,
) -> None:
    """Phase 1: brief.yaml -> block selection -> main.typ -> one PDF (YYMM.<Event>-YourName.pdf) + HTML."""
    from talks_repo import generate

    r = generate.generate(slug, force=force)
    typer.echo(f"Blocks ({r['minutes']:.1f} of {r['budget']:.0f} min): " + ", ".join(b["id"] for b in r["blocks"]))
    for line in r["selection_log"]:
        typer.echo(f"  {line}")
    for p in r["asset_problems"]:
        typer.echo(f"  asset problem: {p}")
    if r["updates_since"]:
        typer.echo(f"  {len(r['updates_since'])} update(s) since the last talk on these topics; see report.md")
    typer.echo(f"Compiled: {r['compiled']} ({r['pages']} pages) -> {r.get('pdf')}; HTML: {r.get('html')}")
    for l in r.get("layout_flags", []):
        typer.echo(f"  layout: {l}")
    if r["compile_error"]:
        typer.echo(r["compile_error"][:1500])
    typer.echo(f"Report: talks/{slug}/report.md")


@app.command("html")
def html_cmd(
    slug: Annotated[str, typer.Argument(help="talks/<slug>/ (or a path to a .typ file)")],
    handout: Annotated[bool, typer.Option(help="One slide per page, no pause steps.")] = False,
) -> None:
    """Export a deck as a self-contained HTML slideshow (animated GIFs keep playing)."""
    from talks_repo import html_export

    p = Path(slug)
    main = p.resolve() if p.suffix == ".typ" else (TALKS_YAML.parent / "talks" / slug / "main.typ")
    out = main.with_name(("handout" if handout else "index") + ".html")
    r = html_export.export_html(main, out, handout=handout, title=slug)
    typer.echo(f"{out.relative_to(TALKS_YAML.parent)}: {r['slides']} slides, {r['bytes']/1e6:.1f} MB, {r['gif_embeds']} GIF embeds")


@app.command("pptx")
def pptx_cmd(
    slug: Annotated[str, typer.Argument(help="talks/<slug>/ (newest PDF there) or a path to a .pdf")],
    ppi: Annotated[int, typer.Option(help="Render resolution of the background (or the page, --flat).")] = 300,
    pages: Annotated[str | None, typer.Option(help="Pages to export, e.g. '1,3-4' (default: all).")] = None,
    flat: Annotated[bool, typer.Option(help="One picture per page instead of live text (posters).")] = False,
    baseline: Annotated[float, typer.Option(help="Move text boxes by this many points (PowerPoint: -1.8).")] = 0.0,
    png: Annotated[bool, typer.Option(help="Also keep the rendered PNGs in talks/<slug>/png/.")] = False,
) -> None:
    """Export a compiled deck as PPTX for Google Slides: live text boxes and pictures over the vector art."""
    from talks_repo import pptx_export

    pdf = pptx_export.deck_pdf(slug)
    r = pptx_export.export_pptx(pdf, ppi=ppi, pages=pages, keep_png=png, flat=flat, baseline=baseline)
    rel = r["pptx"].relative_to(TALKS_YAML.parent) if r["pptx"].is_relative_to(TALKS_YAML.parent) else r["pptx"]
    what = f"{r['px'][0]}x{r['px'][1]} px pictures" if r["flat"] else \
        f"{r['text_boxes']} text boxes, {r['pictures']} pictures; fonts {', '.join(r['fonts'])}"
    typer.echo(f"{rel}: {r['slides']} of {r['pages']} pages, {what}, {r['bytes']/1e6:.1f} MB"
               + (f"; {len(r['png'])} PNGs in {r['png'][0].parent.relative_to(TALKS_YAML.parent)}/" if r["png"] else ""))
    typer.echo("Google Slides: File > Import slides > Upload, pick the .pptx, select the slides.")


@app.command("layout")
def layout_cmd(
    slug: Annotated[str, typer.Argument(help="talks/<slug>/ (newest PDF there) or a path to a .pdf")],
    png: Annotated[bool, typer.Option(help="Also write page renders to talks/<slug>/png/.")] = False,
) -> None:
    """Layout check: blank band at the bottom and column imbalance per slide (the final pass)."""
    from talks_repo import layout_check, pptx_export

    pdf = pptx_export.deck_pdf(slug)
    pages = layout_check.check(pdf, png=png)
    typer.echo(f"{pdf.relative_to(TALKS_YAML.parent) if pdf.is_relative_to(TALKS_YAML.parent) else pdf}")
    typer.echo(layout_check.report(pages))


@app.command("publish")
def publish_cmd(
    slug: Annotated[str, typer.Argument(help="talks/<slug>/ with a compiled deck")],
    folder: Annotated[str | None, typer.Option(help="Trip folder name under Talks-and-Travel (default: matched by YYMM and event, or created).")] = None,
    dry_run: Annotated[bool, typer.Option(help="Say what would be created; write nothing.")] = False,
) -> None:
    """Copy the deck's PDF, PPTX and HTML into My Drive/1-Areas/Research/Talks-and-Travel/<trip>/<deck>/ (create only)."""
    from talks_repo import publish

    r = publish.publish(slug, folder=folder, dry_run=dry_run)
    typer.echo(f"{'DRY RUN: ' if r['dry_run'] else ''}{r['path']}{' (new trip folder)' if r['trip_created'] else ''}")
    typer.echo(f"  {', '.join(r['uploaded'])} ({r['bytes']/1e6:.1f} MB)")


@app.command("make-template")
def make_template_cmd(
    dest: Annotated[str, typer.Argument(help="Destination folder for the public template repository.")],
    force: Annotated[bool, typer.Option(help="Rebuild over a previous template (its .git is kept).")] = False,
    push: Annotated[bool, typer.Option(help="After a clean scan, commit in the template's repo and push it.")] = False,
) -> None:
    """Export the public template: pipeline, themes, docs, a worked example; private content left out, scrubbed and scanned."""
    from pathlib import Path as _P

    try:
        from talks_repo import make_template
    except ImportError:   # the template itself does not ship the exporter
        typer.echo("make-template is only available in the private source repository.")
        raise typer.Exit(code=1)

    s = make_template.build(_P(dest), force=force)
    typer.echo(f"{s['dest']}: {s['files']} files written")
    if s["hits"]:
        for h in s["hits"]:
            typer.echo(f"  PRIVATE PATTERN: {h}")
        raise typer.Exit(code=1)
    typer.echo("scan clean: no private paths, ids or credentials.")
    if push:
        r = make_template.push(_P(dest))
        typer.echo(f"pushed {r['commit']}: {r['message']}" if r["pushed"] else f"not pushed: {r['reason']}")
    else:
        typer.echo("Review the tree; `--push` commits and pushes it to the template repository.")


@app.command("freeze")
def freeze_cmd(slug: Annotated[str, typer.Argument(help="talks/<slug>/ with a generated main.typ")]) -> None:
    """Preservation: copy scaled assets, blocks and theme into the talk folder so it compiles alone."""
    from talks_repo import freeze

    r = freeze.freeze(slug)
    typer.echo(f"Frozen {r['assets']} assets ({r['files_mb']} MB) and {r['blocks']} blocks into talks/{slug}/; "
               f"standalone compile: {r['standalone_compile']}")
    for m in r["missing"]:
        typer.echo(f"  missing: {m}")
    if r["error"]:
        typer.echo(r["error"])


@app.command("sync-drive")
def sync_drive_cmd(
    kind: Annotated[list[str] | None, typer.Option(help="Only these kinds (plot, schematic, photo, ...).")] = None,
    talk_id: Annotated[list[str] | None, typer.Option("--id", help="Only these catalog ids.")] = None,
    limit: Annotated[int | None, typer.Option(help="Stop after this many entries.")] = None,
    dry_run: Annotated[bool, typer.Option(help="List what would be created; write nothing.")] = False,
) -> None:
    """Mirror catalog entries into LabName/Figures|Photos/_catalog on the shared drive (append-only)."""
    from talks_repo import drive_sync

    s = drive_sync.sync(set(kind) if kind else None, set(talk_id) if talk_id else None, limit, dry_run)
    typer.echo(f"{'DRY RUN: ' if dry_run else ''}{s['entries']} entries; {s['folders_created']} folders created, "
               f"{s['files_uploaded']} files uploaded ({s['bytes']/1e6:.1f} MB), {s['files_skipped']} already present"
               + (f", {s['files_archived']} files moved into version subfolders." if s.get("files_archived") else "."))


sources_app = typer.Typer(help="Figure sources: notebooks and scripts on Drive -> shared drive, with data.")
app.add_typer(sources_app, name="sources")


@sources_app.command("inventory")
def sources_inventory(root: Annotated[list[str] | None, typer.Option(help="colab, code-colab, articles")] = None) -> None:
    """Walk the source roots on Drive and download every notebook / script (cached)."""
    from talks_repo import sources

    inv = sources.inventory(root)
    for key, r in inv.items():
        typer.echo(f"  {r['root']}: {len(r['files'])} files, {len(r['code'])} notebooks/scripts")


@sources_app.command("analyze")
def sources_analyze() -> None:
    """Data files each notebook/script reads (found on Drive or missing), figure output -> review sheet."""
    from talks_repo import sources

    rows = sources.analyze()
    figs = [r for r in rows if r["produces_figures"]]
    typer.echo(f"{len(rows)} notebooks/scripts; {len(figs)} produce figures; "
               f"{sum(1 for r in figs if r['missing'] == 0)} of those have all referenced data files on Drive; "
               f"{sum(r['embedded_plots'] for r in rows)} rendered plots embedded in notebook outputs.")
    typer.echo("Review: review/sources-references.csv")


@sources_app.command("copy")
def sources_copy(
    dry_run: Annotated[bool, typer.Option(help="Plan only.")] = False,
    include_coursework: Annotated[bool, typer.Option(help="Also copy the ML lecture/homework notebooks.")] = False,
) -> None:
    """Copy notebooks/scripts with their data files to LabName/Figures/_sources (append-only, paths rewritten)."""
    from talks_repo import sources

    plans = sources.plan_copy(include_coursework=include_coursework)
    typer.echo(f"{len(plans)} files planned; data files {sum(len(p['data_files']) for p in plans)}; "
               f"unresolved refs {sum(len(p['missing']) for p in plans)}")
    typer.echo(str(sources.copy_to_drive(plans, dry_run=dry_run)))


@sources_app.command("run")
def sources_run(
    only: Annotated[list[str] | None, typer.Option(help="Only these source paths.")] = None,
    timeout: Annotated[int, typer.Option(help="Seconds per notebook.")] = 300,
    upload: Annotated[bool, typer.Option(help="Upload exports to the shared drive afterwards.")] = True,
) -> None:
    """Execute self-contained figure notebooks headless; export SVG + PDF + 300 dpi PNG; upload."""
    import json

    from talks_repo import sources

    plans = json.loads((sources.SRC_DIR / "copy-plan.json").read_text())
    results = sources.run_sources(plans, only=set(only) if only else None, timeout=timeout)
    ok = [r for r in results if r["status"] == "ok"]
    typer.echo(f"{len(results)} run: {len(ok)} ok, {sum(1 for r in results if r['status']=='error')} errors, "
               f"{sum(len(r.get('exports', [])) for r in results)} export files")
    for r in results:
        if r["status"] != "ok":
            typer.echo(f"  {r['status']:<8} {r['path'][:60]} {r.get('error', '')[:100]}")
    if upload:
        typer.echo(str(sources.upload_exports(results)))


@sources_app.command("publish")
def sources_publish(dry_run: Annotated[bool, typer.Option(help="Plan only.")] = False) -> None:
    """Figures/<plot>/: plot (svg/pdf/png) + code/ + data/ + figure.yaml, one folder per plot (append-only)."""
    from talks_repo import sources

    typer.echo(str(sources.publish_plots(dry_run=dry_run)))


scan_app = typer.Typer(help="Wide scan for figure code (local disk, iCloud, all of Google Drive) and publish matches.")
app.add_typer(scan_app, name="scan")


@scan_app.command("match")
def scan_match() -> None:
    """Match scanned notebooks/scripts to catalog figures (output-plot hash, savefig names)."""
    from pathlib import Path as _P

    from talks_repo import scan

    rows = scan.scan_sources({"drive": scan.SCAN_DIR / "drive", "local": scan.SCAN_DIR / "local"})
    typer.echo(f"{len(rows)} matches, {len({r['catalog_id'] for r in rows})} catalog figures, "
               f"{len({(r['origin'], r['source']) for r in rows})} sources. Review: review/scan-matches.csv")


@scan_app.command("publish")
def scan_publish(
    run: Annotated[bool, typer.Option(help="Execute the sources headless and upload SVG/PDF/PNG exports.")] = True,
    timeout: Annotated[int, typer.Option(help="Seconds per source run.")] = 900,
    dry_run: Annotated[bool, typer.Option(help="Plan only.")] = False,
) -> None:
    """Figures/<catalog-id>/: as-used figure, code/, data/, exports, figure.yaml with source paths (append-only)."""
    from talks_repo import scan

    typer.echo(str(scan.publish_matches(run=run, timeout=timeout, dry_run=dry_run)))


@app.command("set")
def set_cmd(
    talk_id: Annotated[str, typer.Argument(help="Talk id in talks.yaml.")],
    assignments: Annotated[list[str], typer.Argument(help="field=value pairs, e.g. duration_min=45.")],
) -> None:
    """Set fields on one talk, e.g. after a web lookup. Numbers are converted; 'null' clears."""
    talks = manifest.load(TALKS_YAML)
    talk = next((t for t in talks if t["id"] == talk_id), None)
    if talk is None:
        raise typer.BadParameter(f"no talk with id {talk_id}")
    for item in assignments:
        key, _, raw = item.partition("=")
        if not _:
            raise typer.BadParameter(f"expected field=value, got {item!r}")
        value: object = raw
        if raw == "null":
            value = None
        elif raw.replace(".", "", 1).isdigit():
            value = float(raw) if "." in raw else int(raw)
        talk[key] = value
    manifest.save(TALKS_YAML, talks, manifest.TALKS_HEADER)
    typer.echo(f"{talk_id}: " + ", ".join(assignments))


def _write_review_sheet(
    parsed: list[cv_stage.ParsedTalk], ids: dict[int, str], unparsed: list[str]
) -> Path:
    REVIEW_DIR.mkdir(exist_ok=True)
    path = REVIEW_DIR / "stage-a-talks.csv"
    columns = [
        "flags", "id", "cv_index", "date", "type", "type_confidence", "era",
        "event", "qualifier", "title", "location", "award", "raw",
    ]
    rows = sorted(parsed, key=lambda t: (not t.flags, -t.cv_index))
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for talk in rows:
            writer.writerow({
                "flags": " ".join(talk.flags),
                "id": ids[talk.cv_index],
                "cv_index": talk.cv_index,
                "date": talk.date,
                "type": talk.type,
                "type_confidence": f"{talk.type_confidence:.2f}",
                "era": talk.era,
                "event": talk.event,
                "qualifier": talk.qualifier or "",
                "title": talk.title,
                "location": talk.location or "",
                "award": talk.award or "",
                "raw": talk.raw,
            })
        for line in unparsed:
            writer.writerow({"flags": "unparsed", "raw": line})
    return path


def main() -> None:
    app()
