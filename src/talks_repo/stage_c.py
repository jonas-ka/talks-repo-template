"""Stage C orchestration: walk, analyze, score, pair, match, write manifests and sheets."""

import csv
from collections import defaultdict
from dataclasses import fields
from pathlib import Path
from typing import Any

from talks_repo import FILES_YAML, FOLDERS_YAML, INPUT_ROOTS, REVIEW_DIR, TALKS_YAML, InputRoot
from talks_repo import discover, manifest

FILES_HEADER = """\
Every deck-like file found in the read-only input folders. Schema in CLAUDE.md.
Built by `talks discover`. Paths are relative to their root (tamu | mit | phd).
Edit `status` (unreviewed | confirmed | rejected | no_talk) and `talk_id` by hand;
re-running keeps entries whose status is not `unreviewed`."""

FOLDERS_HEADER = """\
Top-level trip folders in each input root and whether they hold a deck.
Folders with status `no_talk` are skipped in later stages. Flip to `has_talk`
if a folder is wrongly marked."""

_ERA_ORDER = {"UNI": 0, "MIT": 1, "PhD": 2}


def _from_entry(entry: dict[str, Any]) -> discover.FileRecord:
    known = {f.name for f in fields(discover.FileRecord)}
    data = {k: v for k, v in entry.items() if k in known}
    data.setdefault("flags", [])
    data.setdefault("reasons", [])
    return discover.FileRecord(**data)


def run(root_names: list[str] | None, fetch_cloud: bool, force: bool) -> dict[str, Any]:
    roots = [r for r in INPUT_ROOTS if not root_names or r.name in root_names]
    previous = {f"{e['root']}:{e['path']}": e for e in manifest.load(FILES_YAML)}
    talks = manifest.load(TALKS_YAML)

    records: list[discover.FileRecord] = []
    counts: dict[str, int] = defaultdict(int)
    for root in roots:
        for rec in discover.walk_root(root):
            old = previous.get(rec.ref)
            if old is not None:
                _carry_over(rec, old, force)
            if not rec.analyzed and (fetch_cloud or not rec.cloud_only):
                discover.analyze(rec, root.path / rec.path)
                counts["analyzed"] += 1
            elif not rec.analyzed:
                rec.flags.append("cloud-only-not-analyzed")
                counts["cloud_skipped"] += 1
            discover.score(rec)
            records.append(rec)

    # Keep entries from roots that were not walked this run.
    walked = {r.name for r in roots}
    kept = [_from_entry(e) for ref, e in previous.items() if e["root"] not in walked]
    all_records = records + kept

    groups = discover.pair(all_records)
    candidates = discover.assign_matches(groups, talks)
    folders = _folder_status(roots, all_records)
    talk_flags = _update_talks(talks, groups, force)

    all_records.sort(key=lambda r: (INPUT_ROOTS.index(_root(r.root)), r.folder, r.path))
    manifest.save(FILES_YAML, [r.to_entry() for r in all_records], FILES_HEADER)
    manifest.save(FOLDERS_YAML, folders, FOLDERS_HEADER)
    manifest.save(TALKS_YAML, talks, manifest.TALKS_HEADER)

    sheets = _write_sheets(all_records, groups, candidates, talks, folders, talk_flags)
    counts.update(
        files=len(all_records),
        decks=sum(1 for r in all_records if r.deck_class == "deck"),
        own_decks=sum(1 for r in all_records if r.deck_class == "deck" and r.own),
        borderline=sum(1 for r in all_records if r.deck_class == "unknown"),
        groups=len(groups),
        matched_groups=sum(1 for g in groups.values() if g[0].talk_id),
        talks_with_files=sum(1 for t in talks if t.get("source_file") or t.get("pdf_file")),
        folders_no_talk=sum(1 for f in folders if f["status"] == "no_talk"),
    )
    counts["sheets"] = sheets  # type: ignore[assignment]
    return counts


def _root(name: str) -> InputRoot:
    return next(r for r in INPUT_ROOTS if r.name == name)


def _carry_over(rec: discover.FileRecord, old: dict[str, Any], force: bool) -> None:
    if old.get("analyzed") and not force:
        for key in ("pages", "first_title", "gdrive_id", "analyzed", "landscape", "aspect",
                    "chars_per_page", "page_size"):
            setattr(rec, key, old.get(key))
    if old.get("status", "unreviewed") != "unreviewed":
        rec.status = old["status"]
        rec.talk_id = old.get("talk_id")
        rec.match_confidence = old.get("match_confidence")


def _folder_status(roots: list[InputRoot], records: list[discover.FileRecord]) -> list[dict[str, Any]]:
    previous = {(e["root"], e["folder"]): e for e in manifest.load(FOLDERS_YAML)}
    by_folder: dict[tuple[str, str], list[discover.FileRecord]] = defaultdict(list)
    for r in records:
        by_folder[(r.root, r.folder)].append(r)
    out: list[dict[str, Any]] = []
    walked = {r.name for r in roots}
    for root in INPUT_ROOTS:
        if root.name in walked:
            names = sorted(p.name for p in root.path.iterdir() if p.is_dir() and not p.name.lower().endswith(".key"))
        else:
            names = sorted(k[1] for k in previous if k[0] == root.name)
        for name in names:
            members = by_folder.get((root.name, name), [])
            decks = [m for m in members if m.deck_class == "deck"]
            old = previous.get((root.name, name), {})
            status = old.get("status", "unreviewed")
            if status == "unreviewed" and not decks and not any(m.deck_class == "unknown" for m in members):
                status = "no_talk"
            talk_ids = sorted({m.talk_id for m in members if m.talk_id})
            out.append({
                "root": root.name,
                "folder": name,
                "date": discover._year_month(name),
                "n_files": len(members),
                "n_decks": len(decks),
                "talk_ids": talk_ids,
                "status": status,
            })
    return out


def _update_talks(
    talks: list[dict[str, Any]], groups: dict[str, list[discover.FileRecord]], force: bool
) -> dict[str, list[str]]:
    """Fill source_file / pdf_file for talks matched by exactly one group. Returns flags per talk."""
    by_talk: dict[str, list[list[discover.FileRecord]]] = defaultdict(list)
    for members in groups.values():
        if members[0].talk_id:
            by_talk[members[0].talk_id].append(members)
    flags: dict[str, list[str]] = defaultdict(list)
    for talk in talks:
        if force:
            talk["source_file"] = talk["pdf_file"] = None  # Stage C owns these until the author confirms
        matched = by_talk.get(talk["id"], [])
        if not matched:
            if not talk.get("source_file") and not talk.get("pdf_file"):
                flags[talk["id"]].append("no-deck-found")
            continue
        if len(matched) > 1:
            # Prefer the group in the root that belongs to the talk's era, then confidence.
            ranked = sorted(
                matched,
                key=lambda g: (
                    _root(g[0].root).era == talk.get("era"),
                    any(m.type in discover.SOURCE_EXT for m in g),
                    g[0].match_confidence or 0.0,
                ),
                reverse=True,
            )
            top, runner = ranked[0], ranked[1]
            same_era = _root(top[0].root).era == _root(runner[0].root).era
            margin = (top[0].match_confidence or 0.0) - (runner[0].match_confidence or 0.0)
            if same_era and margin < 0.08:
                flags[talk["id"]].append(f"multiple-groups:{len(matched)}")
                continue
            flags[talk["id"]].append(f"other-groups:{len(matched) - 1}")
            matched = [top]
        members = matched[0]
        if any(m.status == "rejected" for m in members):
            continue
        sources = [m for m in members if m.type in discover.SOURCE_EXT]
        pdfs = [m for m in members if m.type == ".pdf"]
        if len(sources) > 1 or len(pdfs) > 1:
            flags[talk["id"]].append("multiple-versions")
        source = _pick(sources, discover.SOURCE_EXT)
        pdf = _pick(pdfs, (".pdf",))
        if force or not talk.get("source_file"):
            talk["source_file"] = source.ref if source else None
        if force or not talk.get("pdf_file"):
            talk["pdf_file"] = pdf.ref if pdf else None
        conf = members[0].match_confidence
        if conf is not None and conf < 0.75:
            flags[talk["id"]].append("low-confidence")
    return flags


def _pick(files: list[discover.FileRecord], order: tuple[str, ...]) -> discover.FileRecord | None:
    """Preferred type first, then highest deck score, then newest modification date."""
    if not files:
        return None
    ranked = sorted(files, key=lambda f: (order.index(f.type) if f.type in order else 99, -f.is_deck))
    best_type, best_score = ranked[0].type, ranked[0].is_deck
    ties = [f for f in ranked if f.type == best_type and f.is_deck == best_score]
    return max(ties, key=lambda f: f.mtime)


# --------------------------------------------------------------------------- review sheets


def _write_sheets(
    records: list[discover.FileRecord],
    groups: dict[str, list[discover.FileRecord]],
    candidates: dict[str, list[discover.Candidate]],
    talks: list[dict[str, Any]],
    folders: list[dict[str, Any]],
    talk_flags: dict[str, list[str]],
) -> list[str]:
    REVIEW_DIR.mkdir(exist_ok=True)
    written: list[str] = []

    path = REVIEW_DIR / "stage-c-files.csv"
    cols = ["root", "folder", "path", "type", "own", "cloud_only", "pages", "is_deck", "deck_class",
            "group_id", "talk_id", "match_confidence", "status", "first_title", "reasons", "flags"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in records:
            w.writerow({
                "root": r.root, "folder": r.folder, "path": r.path, "type": r.type, "own": r.own,
                "cloud_only": r.cloud_only, "pages": r.pages if r.pages is not None else "",
                "is_deck": f"{r.is_deck:.2f}", "deck_class": r.deck_class,
                "group_id": r.group_id or "", "talk_id": r.talk_id or "",
                "match_confidence": "" if r.match_confidence is None else f"{r.match_confidence:.2f}",
                "status": r.status, "first_title": r.first_title or "",
                "reasons": " ".join(r.reasons), "flags": " ".join(r.flags),
            })
    written.append(str(path.relative_to(REVIEW_DIR.parent)))

    path = REVIEW_DIR / "stage-c-talks.csv"
    cols = ["flags", "id", "era", "date", "event", "title", "source_file", "pdf_file",
            "match_confidence", "group_files", "candidates"]
    group_by_talk: dict[str, list[str]] = defaultdict(list)
    for gid, members in groups.items():
        if members[0].talk_id:
            group_by_talk[members[0].talk_id].append(gid)
    ordered = sorted(talks, key=lambda t: (_ERA_ORDER.get(str(t.get("era")), 9), str(t.get("date"))), reverse=False)
    ordered.sort(key=lambda t: _ERA_ORDER.get(str(t.get("era")), 9))
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for t in ordered:
            gids = group_by_talk.get(t["id"], [])
            files = "; ".join(f"{gid}: " + ", ".join(m.ref for m in groups[gid]) for gid in gids)
            conf = next((groups[g][0].match_confidence for g in gids if groups[g][0].match_confidence), None)
            w.writerow({
                "flags": " ".join(talk_flags.get(t["id"], [])), "id": t["id"], "era": t.get("era"),
                "date": t.get("date"), "event": t.get("event"), "title": t.get("title"),
                "source_file": t.get("source_file") or "", "pdf_file": t.get("pdf_file") or "",
                "match_confidence": "" if conf is None else f"{conf:.2f}", "group_files": files,
                "candidates": "",
            })
        # Deck groups that matched no CV entry: talks missing from the CV, or wrong matches.
        for gid, members in groups.items():
            if members[0].talk_id or all(m.deck_class != "deck" for m in members):
                continue
            if not any(m.own for m in members):
                continue  # other people's decks: listed in files.csv, never matched
            cands = "; ".join(f"{c.talk_id} ({c.score:.2f}, {c.why})" for c in candidates.get(gid, []))
            w.writerow({
                "flags": "deck-without-match", "id": "", "era": _root(members[0].root).era,
                "date": discover.group_date(members)[0], "event": members[0].folder,
                "title": next((m.first_title for m in members if m.first_title), ""),
                "group_files": f"{gid}: " + ", ".join(m.ref for m in members), "candidates": cands,
            })
    written.append(str(path.relative_to(REVIEW_DIR.parent)))

    path = REVIEW_DIR / "stage-c-folders.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["root", "folder", "date", "n_files", "n_decks", "talk_ids", "status"])
        w.writeheader()
        for f in folders:
            w.writerow({**f, "talk_ids": " ".join(f["talk_ids"])})
    written.append(str(path.relative_to(REVIEW_DIR.parent)))
    return written
