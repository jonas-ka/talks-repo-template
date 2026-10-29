"""EPICS settings with an entry: take a snapshot of a named group of process variables (PVs),
and write a stored snapshot back.

Groups are defined per apparatus in apparatus.yaml (`epics_groups: {source-tune: [PV, …]}`).
Reading and writing go through caproto (pure Python; `uv run --project lab/logbook --extra epics`),
on a machine on the lab's EPICS network. The file format is `lablogbook.epics` (FORMAT).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .book import Book
from .epics import FORMAT


SEVERITY = {0: "NO_ALARM", 1: "MINOR", 2: "MAJOR", 3: "INVALID"}


class EpicsError(RuntimeError):
    pass


def group_pvs(book: Book, group: str) -> list[str]:
    pvs = []
    for a in (book.apparatus or {}).values():
        pvs += list((a.get("epics_groups") or {}).get(group) or [])
    if not pvs:
        raise EpicsError(f"no PV group '{group}' in apparatus.yaml")
    return list(dict.fromkeys(pvs))


def _client():
    try:
        from caproto.sync import client
    except ImportError:
        raise EpicsError("EPICS access needs caproto: uv run --project lab/logbook --extra epics logbook …") from None
    return client


def _plain(v):
    if hasattr(v, "tolist"):
        v = v.tolist()
    if isinstance(v, list):
        v = v[0] if len(v) == 1 else v
    if isinstance(v, bytes):
        v = v.decode("utf-8", "replace").rstrip("\x00")
    return v


def read_pv(name: str, timeout: float = 2.0) -> dict:
    client = _client()
    try:
        t = client.read(name, data_type="time", timeout=timeout)
        c = client.read(name, data_type="control", timeout=timeout)
    except Exception as e:   # noqa: BLE001 - timeouts, unknown PVs: one message
        raise EpicsError(f"{name}: {e}") from None
    sev = getattr(t.metadata, "severity", None)
    when = getattr(t.metadata, "timestamp", None)
    units = getattr(c.metadata, "units", b"")
    return {"name": name, "value": _plain(t.data),
            "unit": units.decode() if isinstance(units, bytes) else (units or ""),
            "timestamp": dt.datetime.fromtimestamp(when).astimezone().isoformat(timespec="seconds") if when else None,
            "severity": SEVERITY.get(int(sev), str(sev)) if isinstance(sev, int) else getattr(sev, "name", None)}


def snapshot(book: Book, group: str, out: Path, label: str | None = None, timeout: float = 2.0) -> Path:
    pvs = [read_pv(p, timeout) for p in group_pvs(book, group)]
    data = {"format": FORMAT, "group": group, "taken": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            **({"label": label} if label else {}), "pvs": [{k: v for k, v in p.items() if v not in (None, "")} for p in pvs]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return out


def stored(book: Book, entry_id: str, group: str | None = None) -> list[tuple[dict, Path]]:
    e = book.entries.get(entry_id)
    if e is None:
        raise EpicsError(f"no entry '{entry_id}'")
    out = []
    for item in e.header.get("epics") or []:
        if group and item.get("group") != group:
            continue
        f = e.folder / item["file"]
        out.append((json.loads(f.read_text(encoding="utf-8")), f))
    if not out:
        raise EpicsError(f"entry '{entry_id}' has no EPICS snapshot" + (f" of group '{group}'" if group else ""))
    return out


def plan_restore(snap: dict, timeout: float = 2.0) -> list[tuple[str, object, object]]:
    """(PV, now, stored) for every PV whose live value differs from the stored one."""
    diff = []
    for pv in snap["pvs"]:
        now = read_pv(pv["name"], timeout)["value"]
        if now != pv["value"]:
            diff.append((pv["name"], now, pv["value"]))
    return diff


def restore(snap: dict, confirm, out, timeout: float = 2.0) -> int:
    """Show what would change, ask `confirm(question) -> bool`, write. Returns the number written."""
    diff = plan_restore(snap, timeout)
    if not diff:
        print(f"{snap['group']}: every PV already has the stored value", file=out)
        return 0
    w = max(len(n) for n, _, _ in diff)
    print(f"{snap['group']} (snapshot of {snap.get('taken', '?')}):", file=out)
    for name, now, then in diff:
        print(f"  {name.ljust(w)}  now {now!r:>12}  ->  {then!r}", file=out)
    if not confirm(f"Write these {len(diff)} value(s) to the machine?"):
        print("nothing written", file=out)
        return 0
    client = _client()
    for name, _, then in diff:
        try:
            client.write(name, then, notify=True, timeout=timeout)
        except Exception as e:   # noqa: BLE001
            raise EpicsError(f"writing {name}: {e}") from None
    print(f"written: {len(diff)} PV(s)", file=out)
    return len(diff)
