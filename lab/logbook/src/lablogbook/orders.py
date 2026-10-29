"""Purchases in the log book. An order is an entry of kind `order` whose header lists its items;
every item that has not arrived is an open item (`::: todo {#item-N priority=low}`) until a later
entry resolves it ("Resolve" in the view, or `resolves:`). `status()` is what the view's
Purchases page and the status file (`logbook orders --json`) show."""

from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from . import state as state_mod
from .book import Book

KIND = "order"
NUMBERS = ("qty", "unit_cost", "total")


def anchor(n: int) -> str:
    return f"item-{n}"


def _num(v):
    """A number as written in a sheet ("$1,234.50", 3.0) → 1234.5, 3; text that is not a number stays text."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return int(v) if float(v).is_integer() else v
    s = re.sub(r"[,$€£\s]", "", str(v))
    try:
        f = float(s)
    except ValueError:
        return str(v).strip()
    return int(f) if f.is_integer() else f


def normalise(items: list) -> list[dict]:
    """Items as the header keeps them: n (1, 2, … unless given), item, qty, unit_cost, total,
    info, ordered, and arrived (true, or the date) for one that has already arrived."""
    out = []
    for i, it in enumerate(items or [], start=1):
        x = {"n": int(it.get("n") or i), "item": str(it.get("item") or "").strip()}
        for k in NUMBERS:
            v = _num(it.get(k))
            if v is not None:
                x[k] = v
        for k in ("info", "ordered", "vendor"):
            if it.get(k) not in (None, ""):
                x[k] = str(it[k]).strip()
        if it.get("arrived"):
            x["arrived"] = it["arrived"] if isinstance(it["arrived"], str) else True
        out.append(x)
    return out


# how common shops write their own names (anything else: the site's name, capitalised)
SHOP_NAMES = {"amazon": "Amazon", "mcmaster": "McMaster-Carr", "thorlabs": "Thorlabs", "digikey": "DigiKey",
              "mouser": "Mouser", "newark": "Newark", "farnell": "Farnell", "ebay": "eBay", "lesker": "Kurt J. Lesker",
              "ikea": "IKEA", "ui": "Ubiquiti", "homedepot": "Home Depot", "lowes": "Lowe's", "edmundoptics": "Edmund Optics",
              "newport": "Newport", "swagelok": "Swagelok", "adafruit": "Adafruit", "sparkfun": "SparkFun",
              "onlinemetals": "OnlineMetals", "apple": "Apple", "bhphotovideo": "B&H", "jetpens": "JetPens",
              "lindedirect": "Linde", "8020": "80/20", "oshpark": "OSH Park", "mcnichols": "McNichols",
              "walmart": "Walmart", "costco": "Costco", "uline": "Uline", "grainger": "Grainger", "xometry": "Xometry",
              "pfeiffer": "Pfeiffer", "edwards": "Edwards", "keysight": "Keysight", "tektronix": "Tektronix"}
FILE_EXT = {"pdf", "png", "jpg", "jpeg", "gif", "xlsx", "xls", "docx", "doc", "csv", "txt", "zip", "heic", "pptx"}
NOT_A_SHOP = {"google", "drive", "docs", "dropbox", "box", "sharepoint", "onedrive", "github"}
_QUOTE_WORD = r"(?:quote|quotation|order|invoice|reimbursement|receipt)"
_NOT_A_NAME = {"quote", "quotation", "order", "items", "invoice", "the", "lab"}


def _shop(name: str) -> str:
    return SHOP_NAMES.get(name.lower(), name if not name.islower() else name[:1].upper() + name[1:])


def vendor(item: dict, names: dict | None = None) -> str | None:
    """An item's vendor: its own `vendor`, else the one its quote or link names, renamed by the
    book's `orders.vendors` ({"Ablation": null, "MV": "MV Power"}: null when it is not a vendor)."""
    if item.get("vendor"):
        return item["vendor"]
    v = vendor_of(item.get("info"))
    if v is not None and names and v in names:
        return names[v] or None
    return v


def vendor_of(info: str | None) -> str | None:
    """The shop or supplier an item's quote or link names, when it can be told: a link's website
    (amazon.com → Amazon), or a quote file named "YYMM.Supplier-…-quote…" or
    "YYMM.Product-quote-Supplier-…". None when it cannot be told."""
    s = (info or "").strip()
    if not s:
        return None
    bare = re.match(r"^([a-z0-9-]+\.)+([a-z]{2,})(/\S*)?$", s, re.I)   # "mcmaster.com/96367A924/"
    if "://" in s or (bare and bare.group(2).lower() not in FILE_EXT and not re.match(r"^\d{4}\.", s)):
        host = urlsplit(s if "://" in s else "https://" + s).netloc.lower().removeprefix("www.")
        parts = host.split(".")
        name = parts[-3] if len(parts) >= 3 and parts[-2] in ("co", "com", "ac", "org") and len(parts[-1]) == 2 else parts[-2] if len(parts) >= 2 else host
        return None if name in NOT_A_SHOP else _shop(name)
    stem = re.sub(r"^\d{4}\.", "", s)                       # the YYMM. of a quote's file name
    after = re.search(_QUOTE_WORD + r"[-_ ]+([A-Za-z][A-Za-z&]{2,})(?=[-_ .]|$)", stem, re.I)
    if after and after.group(1).lower() not in _NOT_A_NAME:  # "Pumps-quote-Pfeiffer-…": the supplier is after "quote"
        return _shop(after.group(1))
    first = re.match(r"([A-Za-z0-9][A-Za-z0-9&]*?)(?=[-_ .])", stem)
    if first and first.group(1).lower() not in _NOT_A_NAME and re.search(r"[A-Za-z]{2}", first.group(1)) \
            and (re.search(_QUOTE_WORD, stem, re.I) or re.match(r"^\d{4}\.", s)):
        return _shop(first.group(1))                          # "ISEG-quote-…", "Costco-lab-supplies.pdf"
    return None


def parse_items(text: str) -> list[dict]:
    """Items from a JSON list, as a form's "Items" section carries them (a ```json block or bare)."""
    t = re.sub(r"^```\w*\s*|\s*```\s*$", "", (text or "").strip())
    data = json.loads(t) if t else []
    if not isinstance(data, list):
        raise ValueError("Items: a JSON list of {item, qty, unit_cost, total, info, ordered}")
    return normalise(data)


def money(v, symbol: str = "$") -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        s = f"{abs(v):,.2f}"
        return ("−" if v < 0 else "") + symbol + (s[:-3] if s.endswith(".00") else s)
    return "" if v is None else str(v)


def _cell(v) -> str:
    s = "" if v is None else str(v)
    if isinstance(v, float) and v.is_integer():
        s = str(int(v))
    return s.replace("|", "\\|").replace("\n", " ").strip()


def body(items: list[dict], intro: str = "", symbol: str = "$") -> str:
    """The entry's text: an optional introduction, the table of items, and one open item for
    every item that has not arrived."""
    rows = ["| # | Item | Qty | Unit cost | Total | Quote / info | Ordered |",
            "|---:|---|---:|---:|---:|---|---|"]
    for x in items:
        info = x.get("info", "")
        info = f"<{info}>" if re.match(r"^https?://\S+$", info) else _cell(info)
        rows.append("| " + " | ".join([str(x["n"]), _cell(x["item"]), _cell(x.get("qty")),
                                        money(x.get("unit_cost"), symbol), money(x.get("total"), symbol),
                                        info, _cell(x.get("ordered"))]) + " |")
    parts = [intro.strip()] if intro and intro.strip() else []
    parts.append("\n".join(rows))
    waiting = [x for x in items if not x.get("arrived")]
    if waiting:
        parts.append("Each item stays open until a later entry says it arrived (\"Resolve\" on the item in the view).")
        for x in waiting:
            qty = f" (×{_cell(x['qty'])})" if x.get("qty") not in (None, "", 1) else ""
            parts.append(f"::: todo {{#{anchor(x['n'])} priority=low}}\nArrived: {_cell(x['item'])}{qty}\n:::")
    return "\n\n".join(parts) + "\n"


def status(book: Book, st: state_mod.State | None = None) -> list[dict]:
    """Every item of every order, the newest order first: its order, entry, fields, and status
    "open" or "arrived" (with the date, entry and authors of the entry that said so, when one did)."""
    st = st or state_mod.compute(book.entries)
    out = []

    def newest_first(e):
        n = _num(e.header.get("order"))
        return (0, -n, "") if isinstance(n, (int, float)) else (1, "", e.date)   # numbered orders first

    for e in sorted(book.entries.values(), key=newest_first):
        if e.header.get("kind") != KIND:
            continue
        for x in normalise(e.header.get("items") or []):
            key = f"{e.id}#{anchor(x['n'])}"
            row = {"order": str(e.header.get("order", "")), "entry": e.id, "key": key, **x}
            row["vendor"] = vendor(x, (book.config.get("orders") or {}).get("vendors"))
            by = st.resolved_by.get(key) or []
            if x.get("arrived"):
                row["status"] = "arrived"
                if isinstance(x["arrived"], str):
                    row["arrived_on"] = x["arrived"]
            elif by and by[0] in book.entries:
                r = book.entries[by[0]]
                row.update(status="arrived", arrived_on=r.date, arrived_in=r.id, arrived_by=r.authors)
            else:
                row["status"] = "open"
            row.pop("arrived", None)
            out.append(row)
    return out
