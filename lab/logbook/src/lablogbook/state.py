"""What later entries say about earlier ones, computed from the whole book (never written into
the old files): resolutions, corrections, redactions, related links and backlinks."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import datetime as dt

from .entry import DEFAULT_PRIORITY, OPENABLE, PRIORITIES, Entry


@dataclass
class State:
    resolved_by: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))   # "id#anchor" -> resolver ids
    corrected_by: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    redacted_by: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    related: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))          # both directions
    backlinks: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))        # [[id]] in text
    reprioritised: dict[str, list[tuple[tuple, str, str]]] = field(default_factory=lambda: defaultdict(list))
    # "id#anchor" -> [(order, entry id, level)] from later entries' `priority:`, oldest first

    def open_items(self, entries: dict[str, Entry]) -> list[tuple[Entry, str, str]]:
        """(entry, anchor, block name) for every issue/todo with an id that nothing resolves yet."""
        out = []
        for e in sorted(entries.values(), key=lambda x: x.id):
            for b in e.blocks:
                if b.name in OPENABLE and b.anchor and not self.resolved_by.get(f"{e.id}#{b.anchor}"):
                    out.append((e, b.anchor, b.name))
        return out

    def priority(self, entries: dict[str, Entry], key: str) -> tuple[str, str | None]:
        """(level, the entry that set it last, or None for the item's own or the default)."""
        if self.reprioritised.get(key):
            _, by, level = self.reprioritised[key][-1]
            return level, by
        tid, _, anchor = key.partition("#")
        b = entries[tid].anchors().get(anchor) if tid in entries else None
        own = b.priority if b and b.priority in PRIORITIES else None
        return own or DEFAULT_PRIORITY, None

    def ranked_open_items(self, entries: dict[str, Entry], today: dt.date, asap_days: int = 2) -> list[dict]:
        """The open items in the order to work on them: an item that has been ASAP for longer than
        `asap_days` first (overdue; counted from the entry that made it ASAP), then by priority,
        then the oldest first."""
        out = []
        for e, anchor, kind in self.open_items(entries):
            key = f"{e.id}#{anchor}"
            level, by = self.priority(entries, key)
            age = (today - dt.date.fromisoformat(e.date)).days
            since = entries[by].date if by in entries else e.date
            out.append({"entry": e, "anchor": anchor, "kind": kind, "key": key, "priority": level, "set_by": by,
                        "since": since, "age": age,
                        "overdue": level == "asap" and (today - dt.date.fromisoformat(since)).days > asap_days})
        rank = {p: i for i, p in enumerate(PRIORITIES)}
        return sorted(out, key=lambda x: (not x["overdue"], -rank[x["priority"]], -x["age"], x["key"]))


def _order(e: Entry) -> tuple:
    return (e.date, str(e.header.get("time") or ""), e.id)


def compute(entries: dict[str, Entry], exclude: set[str] = frozenset()) -> State:
    """State from all entries except those in `exclude` (the ones being checked, so that an
    entry does not count as already resolving what it resolves)."""
    s = State()
    for e in entries.values():
        if e.id in exclude:
            continue
        h = e.header
        for target in h.get("resolves") or []:
            s.resolved_by[target].append(e.id)
        if h.get("corrects"):
            s.corrected_by[h["corrects"]].append(e.id)
        if h.get("redacts"):
            s.redacted_by[h["redacts"]].append(e.id)
        for target, level in (h.get("priority") or {}).items() if isinstance(h.get("priority"), dict) else []:
            if str(level).lower() in PRIORITIES:
                s.reprioritised[target].append((_order(e), e.id, str(level).lower()))
        for r in h.get("related") or []:
            s.related[e.id].add(r)
            s.related[r].add(e.id)
        for target, _ in e.links():
            if not target.startswith("wiki:"):
                s.backlinks[target.split("#")[0]].add(e.id)
    for v in s.reprioritised.values():
        v.sort()
    return s
