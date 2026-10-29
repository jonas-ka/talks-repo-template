---
date: 2026-10-01
time: "09:30"
tz: America/Chicago
authors: [aa]
with: claude
kind: run
project: Example experiment
subproject: Ion source
apparatus: [source, beamline]
title: First transmission scan of the extraction voltage
tags: [transmission, extraction]
runs: ["DAQ run r017", "archiver 2026-10-01T09:10/09:40"]
parameters:
  - {name: SRC:HV_Offset, value: 3000, unit: V}
  - {name: SRC:Laser_Energy, value: 1.2, unit: mJ}
  - {name: scan step, value: 5, unit: V}
figures:
  - file: figures/plot-example-transmission-scan-v1.pdf
    caption: "Transmission through the beamline against the extraction voltage (run r017)."
    alt: "Line plot of transmission in percent against extraction voltage from -140 V to -100 V. The curve rises from 21 percent to a maximum of 38 percent at -120 V and falls to 20 percent at -100 V."
data:
  - file: data/transmission-scan-r017.csv
    describes: plot-example-transmission-scan-v1
    source: "DAQ run r017; raw traces in the Drive folder Example/Data/Transmission/r017"
epics:
  - file: epics/source-tune-2026-10-01T0930.json
    group: source-tune
    label: best transmission so far
refs:
  Script: examples/logbook/scripts/draw_transmission_scan.py
release: candidate
---

First scan of the extraction voltage after the source was rebuilt, following the method of
[@Author2019]. The source ran on the standard target at 1.2 mJ.

::: finding
Transmission peaks at −120 V with 38 % (step 5 V), 1.6 times the 24 % of the old setting
(−135 V). The settings are stored as the EPICS snapshot of this entry.
:::

::: decision
Use −120 V as the new standard extraction voltage until the next scan.
:::

::: issue {#issue-drift}
*Symptom.* The peak moves by about 5 V within 20 minutes. Cause unknown. Open.
:::

::: todo {#todo-repeat}
- Repeat the scan at 1 kV cage voltage.
:::
