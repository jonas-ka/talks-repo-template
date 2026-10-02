"""Course documents on the notes theme: `talks course build` and `talks course publish`.

A course lives in `courses/<slug>/` (or is a repository of its own made from the template)
and is described by `course.yaml`:

    course: PHYS 206
    title: Newtonian Mechanics for Engineering and Science
    semester: Spring 2027
    instructor: Your Name
    documents:                       # what to build, by glob relative to the course folder
      - glob: lectures/*/notes.typ
        modes: [student, lecture]    # one PDF per mode (--input mode=...)
        html: true                   # HTML export of the student mode (MathML equations)
      - glob: problem-sets/*/ps.typ
        modes: [student, solutions]
    publish: "1-Areas/Teaching/2027-Spring/PHYS 206"   # My Drive path for `talks course publish`
    publish_modes: [student, lecture]                  # which PDFs go to Drive (HTML of student too)

`build` refreshes each document's equation alt text (`talks alts`, drafts for new equations),
compiles every mode with `--pdf-standard ua-1` (a validation failure fails that document),
exports HTML where asked, and writes `report.md` in the course folder: pages per mode, how
many equations still have draft alt text, errors. Outputs are named
`<COURSE>-<folder>[-<mode>].pdf` next to the source (`PHYS206-L01-kinematics-lecture.pdf`),
student mode without suffix. Re-runs skip documents whose outputs are newer than their
sources (`--force` rebuilds).

`publish` copies the built files into the Drive folder, one subfolder per document folder,
through `files.create` only (an existing name gets a `-2` suffix, nothing is overwritten).
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from talks_repo import REPO_ROOT
from talks_repo import alts as alts_mod

THEME_FILES = ("themes/karthein-notes.typ", "themes/speak-math.typ", "themes/tokens.typ", "assets/catalog.yaml")


def load(course_dir: Path) -> tuple[Path, dict[str, Any]]:
    course_dir = course_dir if course_dir.is_absolute() else REPO_ROOT / course_dir
    cfg_path = course_dir / "course.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"{cfg_path} not found")
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return course_dir, cfg


def course_slug(cfg: dict[str, Any]) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(cfg.get("course", "course")))


def documents(course_dir: Path, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for spec in cfg.get("documents") or []:
        for typ in sorted(course_dir.glob(str(spec["glob"]))):
            out.append({"typ": typ, "modes": list(spec.get("modes") or ["student"]), "html": bool(spec.get("html", False))})
    return out


def output_name(cfg: dict[str, Any], typ: Path, mode: str, ext: str = ".pdf") -> str:
    folder = typ.parent.name if typ.parent.name not in ("", ".") else typ.stem
    suffix = "" if mode == "student" else f"-{mode}"
    return f"{course_slug(cfg)}-{folder}{suffix}{ext}"


def _newer_than(outputs: list[Path], inputs: list[Path]) -> bool:
    if not outputs or not all(p.exists() for p in outputs):
        return False
    newest_in = max(p.stat().st_mtime for p in inputs if p.exists())
    return min(p.stat().st_mtime for p in outputs) >= newest_in


def _pages(pdf: Path) -> int:
    import pymupdf

    with pymupdf.open(pdf) as d:
        return d.page_count


def build_document(cfg: dict[str, Any], doc: dict[str, Any], force: bool = False) -> dict[str, Any]:
    typ: Path = doc["typ"]
    side = alts_mod.sidecar_for(typ)
    alts_result = alts_mod.update(typ)
    outputs = [typ.parent / output_name(cfg, typ, m) for m in doc["modes"]]
    if doc["html"]:
        outputs.append(typ.parent / output_name(cfg, typ, "student", ".html"))
    inputs = [typ, side] + [REPO_ROOT / t for t in THEME_FILES] + [p for p in typ.parent.glob("*") if p.suffix in (".typ", ".yaml", ".svg", ".png", ".jpg") and p != typ]
    res: dict[str, Any] = {"file": str(typ.relative_to(REPO_ROOT)), "alts": alts_result["counts"], "modes": {}, "html": None, "errors": [], "skipped": False}
    if not force and _newer_than(outputs, inputs):
        res["skipped"] = True
        for m in doc["modes"]:
            res["modes"][m] = {"pdf": output_name(cfg, typ, m), "pages": _pages(typ.parent / output_name(cfg, typ, m))}
        if doc["html"]:
            res["html"] = output_name(cfg, typ, "student", ".html")
        return res
    for m in doc["modes"]:
        out = typ.parent / output_name(cfg, typ, m)
        r = subprocess.run(["typst", "compile", "--root", str(REPO_ROOT), "--pdf-standard", "ua-1", "--input", f"mode={m}", str(typ), str(out)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            res["errors"].append(f"{m}: " + r.stderr.strip()[:1500])
            continue
        res["modes"][m] = {"pdf": out.name, "pages": _pages(out)}
    if doc["html"]:
        out = typ.parent / output_name(cfg, typ, "student", ".html")
        r = subprocess.run(["typst", "compile", "--root", str(REPO_ROOT), "--features", "html", "--format", "html", "--input", "mode=student", str(typ), str(out)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            res["errors"].append("html: " + r.stderr.strip()[:1500])
        else:
            res["html"] = out.name
    return res


def decks(course_dir: Path, cfg: dict[str, Any]) -> list[Path]:
    """Slide lectures: folders with a brief.yaml matched by `decks:` (a glob), generated like talks."""
    g = cfg.get("decks")
    return sorted(p.parent for p in course_dir.glob(str(g))) if g else []


def build_deck(folder: Path, force: bool = True) -> dict[str, Any]:
    from talks_repo import generate as gen

    rel = str(folder.relative_to(REPO_ROOT))
    try:
        # equation alt text for the deck's blocks: one `alts.yaml` in the lecture folder, which
        # the generated main.typ applies (plain `$...$` on slides stays plain)
        import yaml as _yaml

        brief = _yaml.safe_load((folder / "brief.yaml").read_text(encoding="utf-8")) or {}
        blocks = gen.load_blocks()
        chosen, _ = gen.select_blocks(brief, blocks)
        if chosen:
            alts_mod.update(chosen[0].path, extra=[b.path for b in chosen[1:]], sidecar=folder / "alts.yaml")
        r = gen.generate(rel, force=force)
    except (FileExistsError, FileNotFoundError, KeyError) as exc:
        return {"file": rel + "/brief.yaml", "deck": True, "errors": [str(exc)], "modes": {}, "html": None, "skipped": False,
                "alts": {"equations": 0, "reviewed": 0, "draft": 0, "empty": 0, "stale": 0}}
    errors = [] if r["compiled"] else [r["compile_error"]]
    return {"file": rel + "/brief.yaml", "deck": True, "errors": errors, "skipped": False,
            "modes": {"slides": {"pdf": r["pdf"], "pages": r["pages"]}} if r["compiled"] else {},
            "html": (r["pdf"].rsplit(".", 1)[0] + ".html") if r["compiled"] and r.get("html") and "error" not in r["html"] else None,
            "minutes": r["minutes"], "budget": r["budget"], "layout_flags": r["layout_flags"], "blocks": [b["id"] for b in r["blocks"]],
            "alts": {"equations": 0, "reviewed": 0, "draft": 0, "empty": 0, "stale": 0}}


def build(course_dir: Path, only: str | None = None, force: bool = False) -> dict[str, Any]:
    course_dir, cfg = load(course_dir)
    docs = documents(course_dir, cfg)
    if only:
        docs = [d for d in docs if only in str(d["typ"].relative_to(course_dir))]
    results = [build_document(cfg, d, force=force) for d in docs]
    for folder in decks(course_dir, cfg):
        if only and only not in str(folder.relative_to(course_dir)):
            continue
        results.append(build_deck(folder))
    report = [f"# {cfg.get('course', '')} build report", "", f"{datetime.now():%Y-%m-%d %H:%M}, {len(results)} document(s)", ""]
    for r in results:
        a = r["alts"]
        flag = "" if not r["errors"] else "  **FAILED**"
        report.append(f"## {r['file']}{flag}")
        report.append("")
        for m, info in r["modes"].items():
            report.append(f"- {m}: `{info['pdf']}` ({info['pages']} pages)")
        if r["html"]:
            report.append(f"- html: `{r['html']}`")
        if r.get("deck"):
            if r["modes"]:
                report.append(f"- blocks: {', '.join(r['blocks'])} ({r['minutes']:.0f} of {r['budget']:.0f} min)")
            for l in r.get("layout_flags", []):
                report.append(f"- layout: {l}")
        else:
            report.append(f"- equations: {a['equations']}, alt text reviewed {a['reviewed']}, draft {a['draft']}, missing {a['empty']}"
                          + (f", stale {a['stale']}" if a["stale"] else "") + (" (unchanged, skipped)" if r["skipped"] else ""))
        for e in r["errors"]:
            report.append(f"- error: {e.splitlines()[0] if e else e}")
        report.append("")
    (course_dir / "report.md").write_text("\n".join(report), encoding="utf-8")
    return {"course": cfg.get("course"), "results": results, "report": str((course_dir / "report.md").relative_to(REPO_ROOT)) if course_dir.is_relative_to(REPO_ROOT) else str(course_dir / "report.md")}


# --------------------------------------------------------------------------- publish


def _my_drive_folder(drive: Any, path: str, create: bool, dry_run: bool) -> tuple[str, list[str]]:
    """Folder id for a `My Drive` path, creating missing levels (files.create) when asked."""
    from talks_repo.publish import _children

    node, created = "root", []
    for name in [p for p in path.split("/") if p]:
        kids = _children(drive, node)
        if name in kids:
            node = kids[name]["id"]
        elif create:
            node = drive.ensure_folder(node, name, existing=kids, dry_run=dry_run)
            created.append(name)
            if dry_run:
                return node, created
        else:
            raise FileNotFoundError(f"My Drive/{path}: '{name}' not found")
    return node, created


def publish(course_dir: Path, dry_run: bool = False, only: str | None = None) -> dict[str, Any]:
    from talks_repo.drive_sync import _MIME, Drive
    from talks_repo.publish import _children

    course_dir, cfg = load(course_dir)
    target = str(cfg.get("publish") or "")
    if not target:
        raise ValueError("course.yaml has no `publish:` path (under My Drive)")
    modes = list(cfg.get("publish_modes") or ["student"])
    drive = Drive()
    root_id, created = _my_drive_folder(drive, target, create=True, dry_run=dry_run)
    uploaded: list[str] = []
    jobs: list[tuple[Path, list[Path]]] = []
    for d in documents(course_dir, cfg):
        typ: Path = d["typ"]
        if only and only not in str(typ.relative_to(course_dir)):
            continue
        files = [typ.parent / output_name(cfg, typ, m) for m in d["modes"] if m in modes]
        if d["html"] and "student" in modes:
            files.append(typ.parent / output_name(cfg, typ, "student", ".html"))
        jobs.append((typ.parent, files))
    for folder in decks(course_dir, cfg):      # slide lectures: the deck's PDF and HTML
        if only and only not in str(folder.relative_to(course_dir)):
            continue
        pdfs = sorted(folder.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        if pdfs:
            jobs.append((folder, [pdfs[0], pdfs[0].with_suffix(".html")]))
    for folder, files in jobs:
        files = [f for f in files if f.exists()]
        if not files:
            continue
        sub_name = folder.name
        kids = _children(drive, root_id) if not str(root_id).startswith("dry-run") else {}
        sub_id = kids[sub_name]["id"] if sub_name in kids else drive.ensure_folder(root_id, sub_name, existing=kids, dry_run=dry_run)
        present = _children(drive, sub_id) if sub_name in kids else {}
        for f in files:
            name, k = f.name, 2
            while name in present:
                name = f"{f.stem}-{k}{f.suffix}"
                k += 1
            drive.upload(sub_id, name, f.read_bytes(), _MIME.get(f.suffix.lower(), "application/octet-stream"), dry_run=dry_run)
            uploaded.append(f"{sub_name}/{name}")
    return {"path": f"My Drive/{target}", "created_folders": created, "uploaded": uploaded, "dry_run": dry_run}
