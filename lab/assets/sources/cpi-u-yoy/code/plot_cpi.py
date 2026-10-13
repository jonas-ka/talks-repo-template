"""US CPI-U, 12-month percent change, monthly (figure `plot-us-cpi-u-yoy-2023-2026`, version 2).

Data: BLS series CUUR0000SA0 (CPI-U, all items, US city average, not seasonally adjusted),
public API v2, pulled 2026-10-01 and kept next to this script as
`../data/CUUR0000SA0_2022-2026_bls-api.json`. Run from anywhere (`--fetch` pulls again):

    uv run --with matplotlib --with numpy python plot_cpi.py            # from the saved JSON
    uv run --with matplotlib --with numpy python plot_cpi.py --fetch    # POST to the BLS API v2

The 12-month change is (CPI_m / CPI_{m-12} - 1) x 100. A month without a published index
(October 2025, the lapse in appropriations) is left as a gap, and so is every 12-month value
that would need it; nothing is interpolated.

Style: the lab style file (`themes/karthein.mplstyle`: STIX Two Text, the lab colours, full
black box, 15 pt bold labels and 13 pt ticks at 6 x 4 in), so the figure serves slides and
papers alike; the rules in docs/FIGURES_README.md for what a style file cannot set (legend
inside without a frame, black annotations in empty regions, text never on data). Output, from
the same figure object: PDF (editable text) and SVG in assets/figures/, the SVG with text as
outlines so that it looks the same wherever Typst renders it; `--png` adds a 300 dpi PNG.
Version 1 (2026-10-01, 4.8 x 2.9 in, 10 pt type, title and grid) is in the git history.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]     # the lab-templates root (lab/ in a consumer)
DATA = HERE.parent / "data" / "CUUR0000SA0_2022-2026_bls-api.json"
OUT = ROOT / "assets" / "figures" / "plot-us-cpi-u-yoy-2023-2026"
STYLE = ROOT / "themes" / "karthein.mplstyle"
START = (2023, 9)          # first month shown
RAISE = 3.0                # proposed raise, percent

BLUE, RED = "#00A2FF", "#FF2D55"   # palette.yaml plot colours: the data, the raise


def fetch() -> dict:
    import urllib.request

    body = json.dumps({"seriesid": ["CUUR0000SA0"], "startyear": "2022", "endyear": str(date.today().year)}).encode()
    req = urllib.request.Request("https://api.bls.gov/publicAPI/v2/timeseries/data/", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.load(r)
    DATA.write_text(json.dumps(j, indent=1), encoding="utf-8")
    return j


def series(j: dict) -> tuple[dict[tuple[int, int], float], list[tuple[int, int]]]:
    vals, blank = {}, []
    for r in j["Results"]["series"][0]["data"]:
        if not r["period"].startswith("M") or r["period"] == "M13":
            continue
        k = (int(r["year"]), int(r["period"][1:]))
        try:
            vals[k] = float(r["value"])
        except ValueError:          # "-": no published index
            blank.append(k)
    return vals, blank


def main() -> None:
    j = fetch() if "--fetch" in sys.argv else json.loads(DATA.read_text(encoding="utf-8"))
    vals, blank = series(j)
    months = sorted(vals)
    yoy = {k: (vals[k] / vals[(k[0] - 1, k[1])] - 1) * 100 for k in months if (k[0] - 1, k[1]) in vals}
    shown = [k for k in months if k >= START]
    # a continuous monthly axis, NaN where the 12-month change does not exist (gap kept)
    first, last = shown[0], shown[-1]
    axis = [(y, m) for y in range(first[0], last[0] + 1) for m in range(1, 13) if first <= (y, m) <= last]
    x = np.array([y + (m - 0.5) / 12 for y, m in axis])
    yv = np.array([yoy.get(k, np.nan) for k in axis])
    print("month    YoY %")
    for k, v in zip(axis, yv):
        print(f"{k[0]}-{k[1]:02d}  {'  gap' if np.isnan(v) else f'{v:5.2f}'}")

    plt.style.use(STYLE)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(x, yv, "o-", color=BLUE, label="CPI-U, 12-month change")
    ax.axhline(RAISE, color=RED, lw=1.4, ls=(0, (5, 3)), label=f"Proposed raise ({RAISE:.0f} %)")
    ax.legend(loc="upper left")
    # the gap, labelled in the empty region above the 2025 values
    for g in (k for k, v in zip(axis, yv) if np.isnan(v)):
        gx = g[0] + (g[1] - 0.5) / 12
        ax.annotate(f"no index for {date(*g, 1):%b %Y}\n(federal shutdown)", xy=(gx, RAISE - 0.05),
                    xytext=(gx - 0.55, 3.85), ha="center", va="center", color="black",
                    arrowprops=dict(arrowstyle="-", color="black", lw=0.8, relpos=(0.78, 0), shrinkA=3, shrinkB=2))
    # the latest value, beside the end of the curve
    ax.text(x[-1] + 0.1, yv[-1], f"{yoy[last]:.1f} %\n{date(*last, 1):%b %Y}", ha="left", va="center", color="black")
    ax.set_xlabel("Year")
    ax.set_ylabel("12-month change (%)")
    years = sorted({y for y, _ in axis if (y, 1) >= first})
    ax.set_xticks(years)
    ax.set_xlim(x[0] - 0.08, x[-1] + 0.72)   # room for the end label beside the curve
    ax.set_ylim(1.8, 4.9)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT.with_suffix(".pdf"))
    with plt.rc_context({"svg.fonttype": "path"}):
        fig.savefig(OUT.with_suffix(".svg"))
    if "--png" in sys.argv:
        fig.savefig(OUT.with_suffix(".png"), dpi=300)
    print("wrote", OUT.with_suffix(".pdf"), "and .svg")


if __name__ == "__main__":
    main()
