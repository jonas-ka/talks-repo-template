---
date: 2026-10-02
time: "14:15"
authors: [bb, aa]
kind: note
project: Example experiment
subproject: Beamline
apparatus: [source]
title: Extraction drift traced to the cage supply
tags: [drift, high voltage]
related: [2026-10-01-0930-aa-first-transmission-scan]
resolves: [2026-10-01-0930-aa-first-transmission-scan#issue-drift]
---

Followed up the drift seen in [[2026-10-01-0930-aa-first-transmission-scan#issue-drift]].

::: finding
The cage supply's output follows the lab temperature: 0.8 V per kelvin, logged for 3 hours.
With the supply in its regulated mode the extraction peak stays within 0.5 V for an hour.
:::

::: decision
Run the cage supply in regulated mode from now on; noted on [[wiki:apparatus/source]].
:::
