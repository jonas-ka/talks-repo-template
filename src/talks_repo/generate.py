"""Phase 1: generate a talk from a brief.

    talks generate <slug>          reads talks/<slug>/brief.yaml, selects blocks, writes
                                   main.typ, compiles one PDF + HTML, reports

Blocks are Typst files in blocks/ with a comment header:
    // id, title, topic: [..], level: [..], minutes, order, requires: [..],
    // assets: [catalog ids], always: true (optional)
Selection: a block qualifies if one of its levels suits the brief's audience and it
shares a topic with the brief (or is `always`). Dependencies (`requires`) are pulled
in. Blocks are added in order of topic overlap until the minute budget
(duration minus 3 for title and questions) is spent. Superseded catalog assets are
refused by the theme at compile time; photos without a copied file are
materialised from the archive into assets/figures/ first.
"""

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from talks_repo import REPO_ROOT, TALKS_YAML, manifest
from talks_repo.extract import read_container

BLOCKS_DIR = REPO_ROOT / "blocks"
TALKS_DIR = REPO_ROOT / "talks"
CATALOG = REPO_ROOT / "assets" / "catalog.yaml"
UPDATES = REPO_ROOT / "updates.md"

# Which block levels suit which brief audience.
AUDIENCE_LEVELS = {
    "public": {"public"},
    "students": {"public", "undergrad"},
    "general": {"public", "undergrad", "nuclear", "AMO"},
    "nuclear": {"undergrad", "nuclear", "expert"},
    "amo": {"undergrad", "AMO", "expert"},
    "mixed": {"undergrad", "nuclear", "AMO"},
}
RESERVED_MINUTES = 3  # title slide + questions


def reserved_minutes(brief: dict[str, Any]) -> float:
    """Minutes kept back for the title slide and questions; a brief may override (short slots)."""
    return float(brief.get("reserved_min", RESERVED_MINUTES))


@dataclass
class Block:
    id: str
    path: Path
    title: str
    topic: list[str]
    level: list[str]
    minutes: float
    order: int
    requires: list[str]
    assets: list[str]
    always: bool = False
    source: str = ""
    section: str = ""   # optional: title-slide contents list sections instead of block titles
    sponsors: bool = False   # sponsor logos in the footer of this block's slides
    overlap: int = 0


def _parse_list(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [v.strip() for v in value.split(",") if v.strip()]


def load_blocks() -> dict[str, Block]:
    blocks: dict[str, Block] = {}
    for path in sorted(BLOCKS_DIR.glob("*.typ")):
        header: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("//"):
                break
            m = re.match(r"//\s*([a-z_-]+):\s*(.*)$", line)
            if m:
                header[m.group(1)] = m.group(2).strip()
        if "id" not in header:
            continue
        blocks[header["id"]] = Block(
            id=header["id"], path=path, title=header.get("title", header["id"]),
            topic=_parse_list(header.get("topic", "")), level=_parse_list(header.get("level", "")),
            minutes=float(header.get("minutes", "2")), order=int(header.get("order", "500")),
            requires=_parse_list(header.get("requires", "")), assets=_parse_list(header.get("assets", "")),
            always=header.get("always", "false").lower() == "true", source=header.get("source", ""),
            section=header.get("section", ""), sponsors=header.get("sponsors", "false").lower() == "true",
        )
    return blocks


# --------------------------------------------------------------------------- selection


def select_blocks(brief: dict[str, Any], blocks: dict[str, Block]) -> tuple[list[Block], list[str]]:
    audience = str(brief.get("audience", "nuclear")).lower()
    levels = AUDIENCE_LEVELS.get(audience, AUDIENCE_LEVELS["nuclear"])
    topics = set(brief.get("topics") or [])
    budget = float(brief.get("duration_min", 20)) - reserved_minutes(brief)
    exclude = set(brief.get("exclude") or [])   # block ids never used, `always` ones included
    log: list[str] = []

    # An explicit `blocks:` list (lectures, hand-ordered talks): these blocks in this order,
    # their `requires` pulled in before them, no topic matching and no budget cut.
    explicit = brief.get("blocks")
    if explicit:
        chosen_list: list[Block] = []
        missing = [b for b in explicit if b not in blocks]
        if missing:
            raise KeyError(f"brief.yaml blocks not found in blocks/: {', '.join(missing)}")

        def pull(b: Block) -> None:
            for r in b.requires:
                if r in blocks and blocks[r] not in chosen_list and r not in exclude:
                    pull(blocks[r])
            if b not in chosen_list:
                chosen_list.append(b)

        for bid in explicit:
            if bid not in exclude:
                pull(blocks[bid])
        for b in blocks.values():                 # `always` blocks (acknowledgements) still come along
            if b.always and b not in chosen_list and b.id not in exclude:
                chosen_list.append(b)
        spent = sum(b.minutes for b in chosen_list)
        log.append(f"explicit block list ({len(explicit)} given, {len(chosen_list)} with requires/always); "
                   f"{spent:.1f} of {budget:.0f} min" + (" OVER BUDGET" if spent > budget else ""))
        return chosen_list, log

    candidates = []
    for b in blocks.values():
        if b.id in exclude:
            continue
        if not (set(b.level) & levels):
            continue
        b.overlap = len(set(b.topic) & topics)
        if b.overlap or b.always:
            candidates.append(b)
    candidates.sort(key=lambda b: (-b.overlap, b.order))

    chosen: dict[str, Block] = {}
    spent = 0.0

    def deps(b: Block, seen: set[str]) -> list[Block]:
        """Transitive `requires`, in dependency order, skipping blocks already chosen."""
        out: list[Block] = []
        for r in b.requires:
            if r in blocks and r not in chosen and r not in seen:
                seen.add(r)
                out += deps(blocks[r], seen) + [blocks[r]]
        return out

    def add(b: Block) -> bool:
        nonlocal spent
        needed = deps(b, set())
        cost = b.minutes + sum(n.minutes for n in needed)
        if spent + cost > budget and not b.always:
            return False
        for n in needed:
            chosen[n.id] = n
        chosen[b.id] = b
        spent += cost
        return True

    for b in candidates:
        if b.id in chosen:
            continue
        if not add(b):
            log.append(f"skipped {b.id} ({b.minutes} min): budget")
    ordered = sorted(chosen.values(), key=lambda b: b.order)
    log.insert(0, f"audience {audience} -> levels {sorted(levels)}; topics {sorted(topics)}; budget {budget:.0f} min; used {spent:.1f} min")
    return ordered, log


# --------------------------------------------------------------------------- updates


def relevant_updates(brief: dict[str, Any], talks: list[dict[str, Any]], slug: str = "") -> tuple[list[str], str | None]:
    """updates.md entries dated after the last earlier talk that shares a topic with the brief."""
    topics = set(brief.get("topics") or [])
    inferred = _talk_topics_from_catalog()
    brief_date = str(brief.get("date", ""))[:10]
    last: str | None = None
    for t in talks:
        if t["id"] == slug or (brief_date and str(t.get("date", ""))[:10] >= brief_date):
            continue  # the talk being generated, or later ones
        t_topics = set(t.get("topics") or []) | inferred.get(t["id"], set())
        if t_topics & topics and t.get("date"):
            last = max(last or "", str(t["date"]))
    if not UPDATES.exists():
        return [], last
    found: list[str] = []
    current: list[str] = []
    in_fence = False
    for line in UPDATES.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence   # the format example in updates.md is not an entry
            continue
        if in_fence:
            continue
        m = re.match(r"## (\d{4}-\d{2}-\d{2})\s*[—-]\s*(.*)", line)
        if m:
            if current:
                found.append("\n".join(current))
            current = []
            d, head = m.group(1), m.group(2)
            if last is None or d > last:
                current = [f"{d}: {head}"]
        elif current:
            tm = re.match(r"topics:\s*\[(.*)\]", line)
            if tm and not (set(_parse_list(tm.group(1))) & topics):
                current = []
            elif line.strip():
                current.append("   " + line.strip())
    if current:
        found.append("\n".join(current))
    return found, last


def _talk_topics_from_catalog(min_uses: int = 2) -> dict[str, set[str]]:
    """Topics of archived talks, inferred from the catalog figures they used
    (a topic counts if at least `min_uses` figures of the talk carry it)."""
    if not CATALOG.exists():
        return {}
    counts: dict[str, dict[str, int]] = {}
    for e in yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or []:
        for u in e.get("uses") or []:
            talk = u.rpartition("#")[0]
            for topic in e.get("topic") or []:
                counts.setdefault(talk, {}).setdefault(topic, 0)
                counts[talk][topic] += 1
    return {talk: {t for t, n in c.items() if n >= min_uses} for talk, c in counts.items()}


# --------------------------------------------------------------------------- assets


def materialize(asset_ids: list[str]) -> tuple[list[str], list[str]]:
    """Copy catalog assets that have no file yet (photos, logos) from the archive."""
    cat = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or []
    by_id = {e["id"]: e for e in cat}
    copied, problems = [], []
    changed = False
    for aid in asset_ids:
        e = by_id.get(aid)
        if e is None:
            problems.append(f"{aid}: not in catalog")
            continue
        if e.get("supersedes_by"):
            problems.append(f"{aid}: superseded")
        if e.get("file"):
            continue
        ref = e.get("archive_ref")
        if not ref:
            problems.append(f"{aid}: no archive_ref")
            continue
        container = ref if ref.startswith("/") else str(REPO_ROOT / ref)
        ext = Path(container.split("::")[-1]).suffix.lower() or ".png"
        target = REPO_ROOT / "assets" / "figures" / f"{aid}{ext}"
        try:
            target.write_bytes(read_container(container))
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{aid}: copy failed ({type(exc).__name__})")
            continue
        e["file"] = f"figures/{target.name}"
        copied.append(aid)
        changed = True
    if changed:
        from talks_repo.catalog import CATALOG_HEADER

        manifest.save(CATALOG, cat, CATALOG_HEADER)
    # superseded check against the catalog's `supersedes` fields
    dead = {e["supersedes"] for e in cat if e.get("supersedes")}
    for aid in asset_ids:
        if aid in dead:
            problems.append(f"{aid}: SUPERSEDED (use the successor)")
    return copied, problems


# --------------------------------------------------------------------------- writing + compiling


def write_main(slug: str, brief: dict[str, Any], blocks: list[Block]) -> Path:
    tdir = REPO_ROOT / slug if "/" in slug else TALKS_DIR / slug
    tdir.mkdir(parents=True, exist_ok=True)
    # Title-slide contents: one entry per section (in deck order) when blocks declare
    # sections, otherwise one per block title. Long decks stay readable this way.
    entries: list[str] = []
    for b in blocks:
        if b.always:
            continue
        label = b.section or b.title
        if label not in entries:
            entries.append(label)
    contents = ", ".join(f"[{e}]" for e in entries)
    date_str = str(brief.get("date", ""))
    try:
        d = date.fromisoformat(date_str)
        date_str = d.strftime("%b. %-d, %Y")
    except ValueError:
        pass
    lines = [
        f"// Generated by `talks generate {slug}` on {date.today().isoformat()} from brief.yaml.",
        "// Edit freely; regenerate with --force to overwrite.",
        '#import "/themes/karthein.typ": *',
        "",
        "#show: karthein-theme.with(",
        "  config-info(",
        f"    title: [{brief.get('title', slug)}],",
        f"    author: [{brief.get('author', 'Your Name')}],",
        f"    institution: [Texas A\\&M University],",
        f"    date: [{date_str}],",
        f"    event: [{brief.get('event', '')}],",
        "  ),",
        f"  sponsors: {'true' if brief.get('sponsors', True) else 'false'},",
        '  handout: sys.inputs.at("handout", default: "false") == "true",',
        ")",
        f'#set document(title: "{brief.get("title", slug)}", author: "{brief.get("author", "Your Name")}")',
    ]
    if (tdir / "alts.yaml").exists():   # equation alt text for plain `$...$` on the slides (talks course build)
        lines.append('#show: apply-alts.with(yaml("alts.yaml"))')
    lines += [
        "",
        f"#title-slide(contents: ({contents}{',' if contents else ''}))",
        "",
    ]
    allow_sponsors = bool(brief.get("sponsors", True))
    for b in blocks:
        lines.append(f"// ---- block {b.id} ({b.minutes} min): {b.title}")
        lines.append(f"#sponsors({'true' if allow_sponsors and b.sponsors else 'false'})")
        lines.append(f'#include "/blocks/{b.path.name}"')
        lines.append("")
    main = tdir / "main.typ"
    main.write_text("\n".join(lines), encoding="utf-8")
    return main


def deck_name(brief: dict[str, Any], slug: str) -> str:
    """Output basename in the lab's convention: YYMM.<Event>-YourName, or the brief's `name`."""
    if brief.get("name"):                      # lectures: PHYS206-L01-overview
        return re.sub(r"[^A-Za-z0-9._-]+", "-", str(brief["name"])).strip("-")
    slug = slug.rsplit("/", 1)[-1]
    d = str(brief.get("date", ""))[:7].replace("-", "")[2:] or slug[:7].replace("-", "")[2:]
    event = re.sub(r"[^A-Za-z0-9]+", "-", str(brief.get("event") or slug)).strip("-")
    author = re.sub(r"[^A-Za-z]", "", str(brief.get("author", "Your Name")))
    return f"{d}.{event}-{author}"


def compile_deck(main: Path, handout: bool, name: str = "out") -> tuple[bool, str, Path]:
    out = main.parent / (f"{name}-handout.pdf" if handout else f"{name}.pdf")
    cmd = ["typst", "compile", "--root", str(REPO_ROOT), "--pdf-standard", "ua-1"]
    if handout:
        cmd += ["--input", "handout=true"]
    cmd += [str(main), str(out)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=REPO_ROOT)
    return result.returncode == 0, result.stderr.strip(), out


def page_count(pdf: Path) -> int | None:
    try:
        import pymupdf

        with pymupdf.open(pdf) as doc:
            return doc.page_count
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- driver


def generate(slug: str, force: bool = False) -> dict[str, Any]:
    # `slug` is a folder under talks/, or a path from the repo root when it contains a slash
    # (course lectures: `lectures/L01-overview`)
    tdir = REPO_ROOT / slug if "/" in slug else TALKS_DIR / slug
    brief_path = tdir / "brief.yaml"
    if not brief_path.exists():
        raise FileNotFoundError(f"{brief_path} missing (schema in CLAUDE.md)")
    brief = yaml.safe_load(brief_path.read_text(encoding="utf-8")) or {}
    main = tdir / "main.typ"
    if main.exists() and not force:
        raise FileExistsError(f"{main} exists; use --force to regenerate")

    blocks = load_blocks()
    chosen, log = select_blocks(brief, blocks)
    talks = manifest.load(TALKS_YAML)
    updates, last_talk = relevant_updates(brief, talks, slug=slug)
    asset_ids = [a for b in chosen for a in b.assets]
    copied, problems = materialize(asset_ids)
    main = write_main(slug, brief, chosen)
    name = deck_name(brief, slug)
    for stale in ("out.pdf", "handout.pdf", "index.html", "handout.html"):
        (tdir / stale).unlink(missing_ok=True)
    ok, err, out = compile_deck(main, handout=False, name=name)
    html: dict[str, Any] = {}
    if ok:
        from talks_repo import html_export

        try:
            html = html_export.export_html(main, tdir / f"{name}.html", handout=False, title=str(brief.get("title", slug)))
        except Exception as exc:  # noqa: BLE001
            html = {"error": str(exc)[:500]}

    layout: list[str] = []
    if ok:
        from talks_repo import layout_check

        try:
            pages = layout_check.check(out)
            layout = [f"page {p.page}: {'; '.join(p.flags)}" for p in pages if p.flags]
        except Exception as exc:  # noqa: BLE001
            layout = [f"layout check failed: {str(exc)[:200]}"]

    report = {
        "slug": slug,
        "layout_flags": layout,
        "blocks": [{"id": b.id, "minutes": b.minutes, "title": b.title, "overlap": b.overlap} for b in chosen],
        "minutes": sum(b.minutes for b in chosen),
        "budget": float(brief.get("duration_min", 20)) - reserved_minutes(brief),
        "selection_log": log,
        "assets_materialized": copied,
        "asset_problems": problems,
        "last_talk_on_topics": last_talk,
        "updates_since": updates,
        "compiled": ok, "compile_error": err[:2000] if not ok else "",
        "pages": page_count(out) if ok else None,
        "pdf": out.name, "html": html,
    }
    (tdir / "report.md").write_text(_report_md(report), encoding="utf-8")

    if brief.get("spine", True) and not any(t["id"] == slug for t in talks):
        talks.append({
            "id": slug, "cv_index": None, "date": str(brief.get("date", "")), "title": brief.get("title", ""),
            "event": brief.get("event", ""), "qualifier": None, "award": None, "host": brief.get("host"),
            "location": brief.get("location"), "type": brief.get("type", "invited"), "era": "UNI",
            "duration_min": brief.get("duration_min"), "audience": brief.get("audience"),
            "format": brief.get("format"), "source_url": None, "confidence": 1.0,
            "source_file": f"{slug}/main.typ" if "/" in slug else f"talks/{slug}/main.typ", "pdf_file": None, "archive": None,
            "topics": brief.get("topics") or [], "blocks": [b.id for b in chosen],
            "notes": "generated by talks generate",
        })
        talks.sort(key=lambda t: (str(t.get("date", "")), t.get("cv_index") or 0))
        manifest.save(TALKS_YAML, talks, manifest.TALKS_HEADER)
        report["talks_yaml"] = "appended"
    return report


def _report_md(r: dict[str, Any]) -> str:
    lines = [f"# {r['slug']}", "", f"Blocks ({r['minutes']:.1f} of {r['budget']:.0f} min):", ""]
    for b in r["blocks"]:
        lines.append(f"- {b['id']} ({b['minutes']} min) — {b['title']}")
    lines += ["", "Selection:", ""] + [f"- {l}" for l in r["selection_log"]]
    if r["asset_problems"]:
        lines += ["", "Asset problems:", ""] + [f"- {p}" for p in r["asset_problems"]]
    if r["assets_materialized"]:
        lines += ["", f"Materialized from the archive: {', '.join(r['assets_materialized'])}"]
    lines += ["", f"Last talk on these topics: {r['last_talk_on_topics'] or 'none'}"]
    if r["updates_since"]:
        lines += ["", "Updates since then (consider new or revised blocks):", ""] + [f"- {u}" for u in r["updates_since"]]
    lines += ["", f"Compiled: {r['compiled']} ({r['pages']} pages) -> {r.get('pdf')}; HTML: {r.get('html')}"]
    if r.get("layout_flags"):
        lines += ["", "Layout check (`talks layout`; intermediate build steps may be flagged, the last step counts):", ""]
        lines += [f"- {l}" for l in r["layout_flags"]]
    elif r["compiled"]:
        lines += ["", "Layout check: no page flagged (blank bottom band <= 18 %, columns within 25 %)."]
    if r["compile_error"]:
        lines += ["", "```", r["compile_error"], "```"]
    return "\n".join(lines) + "\n"
