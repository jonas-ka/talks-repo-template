"""US CPI-U, 12-month percent change, monthly (figure `plot-us-cpi-u-yoy-2023-2026`, version 2).

Data: BLS series CUUR0000SA0 (CPI-U, all items, US city average, not seasonally adjusted),
public API v2, pulled 2026-10-01 and kept next to this script as
`../data/CUUR0000SA0_2022-2026_bls-api.json`. Run with `--fetch` to pull again:

    uv run python plot_cpi.py            # from the saved JSON
    uv run python plot_cpi.py --fetch    # POST to https://api.bls.gov/publicAPI/v2/timeseries/data/

The 12-month change is (CPI_m / CPI_{m-12} - 1) x 100. A month without a published index
(October 2025, the lapse in appropriations) is left as a gap, and so is every 12-month value
that would need it; nothing is interpolated. Output: the PDF (vector) in assets/figures/ (`--png` adds a
300 dpi PNG); the SVG twin for Typst is made from the PDF with PyMuPDF.
Style: the lab palette (themes/palette.yaml), STIX Two Text.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data" / "CUUR0000SA0_2022-2026_bls-api.json"
OUT = HERE.parent.parent.parent / "figures" / "plot-us-cpi-u-yoy-2023-2026"
START = (2023, 9)          # first month shown
RAISE = 3.0                # proposed raise, percent

BLUE, BLUE_TEXT = "#00A2FF", "#007BC1"
RED_LINE, RED_TEXT = "#FF2D55", "#E2284B"
INK, MUTED = "#000000", "#333333"


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

    # lab style (docs/FIGURES_README.md, 2026-10-01): full box, black bold axis labels, legend
    # inside without frame or text labels at the curves, colour only on data, black annotations
    matplotlib.rcParams.update({"font.family": "STIX Two Text", "mathtext.fontset": "stix", "font.size": 10,
                                "axes.labelweight": "bold", "axes.edgecolor": INK, "xtick.color": INK, "ytick.color": INK})
    fig, ax = plt.subplots(figsize=(4.8, 2.9), constrained_layout=True)
    ax.plot(x, yv, "o-", color=BLUE, ms=3.2, lw=1.6, label="CPI-U, 12-month change")
    ax.axhline(RAISE, color=RED_LINE, lw=1.3, ls=(0, (5, 3)))
    # labels sit in empty regions, never on the data (figure style rules)
    ax.text(2024.55, RAISE + 0.09, f"Proposed raise: {RAISE:.0f} %", color=INK, fontsize=9.5, va="bottom")
    # mark the gap
    gaps = [k for k, v in zip(axis, yv) if np.isnan(v)]
    for g in gaps:
        gx = g[0] + (g[1] - 0.5) / 12
        ax.annotate("no CPI published\n(Oct 2025 shutdown)", xy=(gx, 2.92), xytext=(gx - 0.42, 3.95), fontsize=8, color=INK,
                    ha="center", va="center", arrowprops=dict(arrowstyle="-", color=INK, lw=0.7, shrinkB=2))
    # label the latest value
    ly, lm = last
    ax.text(x[-1] + 0.07, yv[-1], f"{yoy[last]:.1f} %\n{date(ly, lm, 1):%b %Y}", fontsize=9.5, color=INK, ha="left", va="center", weight="bold")
    ax.set_ylabel("12-month change (%)")
    ax.set_ylim(1.8, 4.8)
    years = sorted({y for y, _ in axis})
    ax.set_xticks(sorted({y for y, _ in axis if (y, 1) >= first}))
    ax.set_xticklabels([str(y) for y in sorted({y for y, _ in axis if (y, 1) >= first})])
    ax.set_xlim(x[0] - 0.05, x[-1] + 0.62)   # room for the end label beside the curve
    ax.grid(axis="y", color="#E6E6E6", lw=0.6)
    ax.set_title("US consumer prices (CPI-U), monthly", fontsize=10.5, loc="center", color=INK, weight="bold")
    ax.set_xlabel("month")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT.with_suffix(".pdf"))
    if "--png" in sys.argv:          # the library sync renders the 300 dpi PNG from the PDF
        fig.savefig(OUT.with_suffix(".png"), dpi=300)
    print("wrote", OUT.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
