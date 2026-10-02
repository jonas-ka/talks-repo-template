"""Equation alt text for lecture notes: `talks alts <file.typ>`.

PDF/UA-1 refuses an equation without alt text, and lecture notes have hundreds of plain
`$...$` equations. This collects every equation of a Typst file into a sidecar
`<stem>.alts.yaml` next to it:

    - src: "x = x_0 + v_0 t + 1/2 a t^2"
      alt: "x equals x nought plus v nought t plus one half a t squared"
      status: draft          # draft (spoken form from themes/speak-math.typ) | reviewed | stale

The notes theme applies the list (`alts: yaml("notes.alts.yaml")`) with one show-set rule
per equation, so the source stays plain math. Drafts come from Typst itself (`speak` over the
parsed math, run through `typst eval`), reviewed entries are kept on re-runs, and entries
whose equation disappeared from the file are marked `stale` (never deleted). Equations
written with `#eq(alt: ...)[...]` carry their own text and are skipped.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

from talks_repo import REPO_ROOT

# `$...$` not preceded by `[` of an `#eq(...)[` call; raw blocks and comments are cut first.
_EQ = re.compile(r"\$((?:\\\$|[^$])+?)\$")
_RAW = re.compile(r"```.*?```|`[^`\n]*`", re.S)
_COMMENT = re.compile(r"(?m)^\s*//[^\n]*$|/\*.*?\*/", re.S)   # `[^\n]`: with re.S a `.*` would eat the file
_EQ_CALL = re.compile(r"#eq\s*\((?:[^()]|\([^()]*\))*\)\s*\[\s*\$((?:\\\$|[^$])+?)\$\s*\]", re.S)
_SPOKEN_CALL = re.compile(r"#(?:spoken-eq|cat-eq)\s*\(")


def equations_in(text: str) -> list[str]:
    """Distinct equation sources in document order, trimmed, without the ones given alt text in `#eq(...)`."""
    text = _COMMENT.sub("", _RAW.sub("", text))
    own = {m.group(1).strip() for m in _EQ_CALL.finditer(text)}
    text = _EQ_CALL.sub(" ", text)
    out: list[str] = []
    for m in _EQ.finditer(text):
        src = m.group(1).strip()
        if not src or src in own or src in out:
            continue
        out.append(src)
    return out


def spoken_drafts(sources: list[str]) -> list[str]:
    """`speak(math-body(src))` for every source, evaluated by Typst (one process)."""
    if not sources:
        return []
    tmp = REPO_ROOT / "work" / "alts-draft.typ"
    tmp.parent.mkdir(exist_ok=True)
    vals = _eval_speak(sources)
    if vals is None:
        # one source Typst cannot parse should not block the file: evaluate one by one
        vals = [(_eval_speak([s]) or [""])[0] for s in sources]
    return [str(v).strip() for v in vals]


def _eval_speak(sources: list[str]) -> list[str] | None:
    """Run `speak(math-body(src))` in Typst for a list of sources; None when Typst refuses."""
    tmp = REPO_ROOT / "work" / f"alts-draft-{abs(hash(tuple(sources))) % 10**8}.typ"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(
        '#import "/themes/speak-math.typ": speak, math-body\n'
        f"#let srcs = json(bytes({json.dumps(json.dumps(sources))}))\n"
        "#metadata(srcs.map(s => speak(math-body(s)))) <alts>\n",
        encoding="utf-8",
    )
    try:
        r = subprocess.run(["typst", "eval", "query(<alts>).first().value", "--in", str(tmp), "--root", str(REPO_ROOT)],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    except subprocess.TimeoutExpired:
        return None
    finally:
        tmp.unlink(missing_ok=True)
    if r.returncode != 0:
        return None
    try:
        return list(json.loads(r.stdout))
    except json.JSONDecodeError:
        return None


def sidecar_for(typ: Path) -> Path:
    return typ.with_name(typ.stem + ".alts.yaml")


def update(typ: Path) -> dict[str, Any]:
    """Refresh `<stem>.alts.yaml` for one Typst file. Returns counts and the new drafts."""
    typ = typ if typ.is_absolute() else REPO_ROOT / typ
    text = typ.read_text(encoding="utf-8")
    sources = equations_in(text)
    side = sidecar_for(typ)
    existing: list[dict[str, Any]] = yaml.safe_load(side.read_text(encoding="utf-8")) or [] if side.exists() else []
    by_src = {str(e.get("src", "")).strip(): e for e in existing}
    new_srcs = [s for s in sources if s not in by_src or not str(by_src[s].get("alt", "")).strip()]
    drafts = dict(zip(new_srcs, spoken_drafts(new_srcs)))
    out: list[dict[str, Any]] = []
    for s in sources:
        e = by_src.get(s)
        if e is None:
            out.append({"src": s, "alt": drafts.get(s, ""), "status": "draft"})
        else:
            if not str(e.get("alt", "")).strip():
                e["alt"], e["status"] = drafts.get(s, ""), "draft"
            elif e.get("status") == "stale":
                e["status"] = "reviewed" if e.get("reviewed") else "draft"
            out.append(e)
    stale = 0
    for s, e in by_src.items():
        if s not in sources:
            e["status"] = "stale"
            stale += 1
            out.append(e)
    side.write_text(
        "# Equation alt text for " + typ.name + " (talks alts). Edit `alt`, set `status: reviewed`;\n"
        "# `draft` = spoken form from themes/speak-math.typ, `stale` = no longer in the file.\n"
        + yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )
    counts = {"equations": len(sources), "new": len(new_srcs), "stale": stale,
              "draft": sum(1 for e in out if e.get("status") == "draft"),
              "reviewed": sum(1 for e in out if e.get("status") == "reviewed"),
              "empty": sum(1 for e in out if not str(e.get("alt", "")).strip() and e.get("status") != "stale")}
    return {"file": str(typ.relative_to(REPO_ROOT)) if typ.is_relative_to(REPO_ROOT) else str(typ), "sidecar": str(side.name),
            "counts": counts, "drafts": [(s, drafts.get(s, "")) for s in new_srcs]}
