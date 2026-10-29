"""EPICS settings stored with an entry: one JSON file per snapshot of a named group of process
variables (PVs). Reading and restoring live values comes with the CLI; this module defines and
checks the file.

    {"format": "lab-epics-snapshot/1",
     "group": "source-tune",
     "taken": "2026-10-13T17:35:02-05:00",
     "pvs": [{"name": "HV_Offset", "value": 3000.0, "unit": "V",
              "timestamp": "2026-10-13T17:35:01-05:00", "severity": "NO_ALARM"}]}

No host names or addresses are stored: they describe the facility's network, not the physics.
"""

from __future__ import annotations

import json
from pathlib import Path

FORMAT = "lab-epics-snapshot/1"
SEVERITIES = {"NO_ALARM", "MINOR", "MAJOR", "INVALID"}


def check_snapshot(path: Path, group: str, allowed: list[str] | None) -> list[str]:
    """Problems with a snapshot file, as messages (empty = fine)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"does not parse as JSON ({str(e).splitlines()[0]})"]
    problems = []
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        return [f"is not a {FORMAT} file (field 'format')"]
    if data.get("group") != group:
        problems.append(f"holds group {data.get('group')!r}, the entry says {group!r}")
    pvs = data.get("pvs")
    if not isinstance(pvs, list) or not pvs:
        return problems + ["has no PVs"]
    for i, pv in enumerate(pvs):
        if not isinstance(pv, dict) or not pv.get("name") or "value" not in pv:
            problems.append(f"PV #{i + 1} needs a name and a value")
            continue
        if pv.get("severity") and pv["severity"] not in SEVERITIES:
            problems.append(f"PV {pv['name']}: unknown alarm severity {pv['severity']!r}")
        if allowed is not None and pv["name"] not in allowed:
            problems.append(f"PV {pv['name']} is not in group {group!r} (apparatus.yaml)")
    return problems
