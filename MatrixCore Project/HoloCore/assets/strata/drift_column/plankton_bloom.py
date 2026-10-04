"""Strata drop-in: plankton bloom (Drift Column).

A loose blob of small wireframe spheres joined by faint filaments, turning
slowly in the open column.
"""
from __future__ import annotations

import math
from random import Random

from holocore_line_kit import finish, new_lines, polyline, wire_sphere

STRATA_OBJECT = {"id": "plankton_bloom", "weight": 1.0, "per_cell": 1.4}

_PALETTE = [(0.30, 1.00, 0.95), (0.55, 0.85, 1.00), (0.85, 0.60, 1.00), (0.40, 1.00, 0.70)]


def build(parent, x, y, z, rng: Random, metadata: dict):
    base = _PALETTE[int(rng.random() * len(_PALETTE)) % len(_PALETTE)]
    ls = new_lines("plankton_bloom_lines", 1.1)
    centres = []
    for _ in range(rng.randint(10, 16)):
        c = (rng.gauss(0.0, 5.5), rng.gauss(0.0, 5.5), rng.gauss(0.0, 4.0))
        r = rng.uniform(0.5, 2.0)
        wire_sphere(ls, c[0], c[1], c[2], r, (*base, rng.uniform(0.45, 0.75)), lat=3, lon=5, segs=10)
        centres.append(c)
    for i in range(1, len(centres)):
        a, b = centres[i - 1], centres[i]
        mid = ((a[0] + b[0]) / 2 + rng.uniform(-1.5, 1.5), (a[1] + b[1]) / 2 + rng.uniform(-1.5, 1.5), (a[2] + b[2]) / 2)
        polyline(ls, (a, mid, b), (*base, 0.18))
    node = finish(parent, "strata_plankton_bloom", [ls], x, y, z)
    node.setScale(rng.uniform(0.9, 1.6))
    node.setPythonTag("spin", rng.uniform(3.0, 8.0) * (1 if rng.random() < 0.5 else -1))
    return node


def update(node, time_value: float) -> None:
    node.setH(float(time_value) * float(node.getPythonTag("spin") or 4.0))
    node.setP(math.sin(float(time_value) * 0.13) * 8.0)
