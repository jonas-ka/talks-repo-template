"""Read and write the YAML manifests (talks.yaml, files.yaml).

Manifests are lists of dicts. Keys keep their insertion order so the files stay
readable and diffs stay small.
"""

from pathlib import Path
from typing import Any

import yaml


class _Dumper(yaml.SafeDumper):
    """Block style everywhere except short inline dicts like `origin`."""


def _represent_none(dumper: yaml.SafeDumper, _: None) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:null", "null")


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.Node:
    # Values that look like dates or numbers would silently change type on
    # reload, so quote them explicitly.
    style = None
    if value and (value[0].isdigit() or "\n" in value):
        style = '"' if "\n" not in value else "|"
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(type(None), _represent_none)
_Dumper.add_representer(str, _represent_str)


def load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a YAML list, got {type(data).__name__}")
    return data


def save(path: Path, entries: list[dict[str, Any]], header: str) -> None:
    body = yaml.dump(
        entries,
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        width=1_000_000,  # never fold long titles across lines
        default_flow_style=False,
    )
    if not entries:
        body = "[]\n"
    comment = "".join(f"# {line}\n" if line else "#\n" for line in header.splitlines())
    path.write_text(comment + body, encoding="utf-8")


TALKS_HEADER = """\
The spine: one entry per talk ever given. Schema in CLAUDE.md.
Stage A fills cv_index/date/title/event/type/era/location from the CV;
later stages add fields. Edit by hand freely; re-running a stage keeps
existing entries unless --force is given."""
