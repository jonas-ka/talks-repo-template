---
date: 2026-10-03
time: "10:00"
authors: [aa]
kind: correction
project: Example experiment
subproject: Ion source
title: The scan step was 2 V, not 5 V
corrects: 2026-10-01-0930-aa-first-transmission-scan
---

[[2026-10-01-0930-aa-first-transmission-scan]] gives the scan step as 5 V. The DAQ
configuration of run r017 shows 2 V; the figure and the data file are right, only the
parameter in the header and the text were wrong. The peak position (−120 V) is unchanged.
