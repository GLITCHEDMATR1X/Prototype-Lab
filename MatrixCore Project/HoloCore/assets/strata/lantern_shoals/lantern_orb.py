"""Strata drop-in: lantern orb (Lantern Shoals).

A wireframe lantern sphere with a brighter core and trailing filaments,
pulsing softly; shoals of them light the middle of the column.
"""
from __future__ import annotations

import math
from random import Random

from holocore_line_kit import finish, new_lines, polyline, wire_sphere

STRATA_OBJECT = {"id": "lantern_orb", "weight": 1.0, "per_cell": 2.2}

_PALETTE = [(1.00, 0.86, 0.45), (0.45, 1.00, 0.80), (1.00, 0.55, 0.85), (0.60, 0.85, 1.00)]


def build(parent, x, y, z, rng: Random, metadata: dict):
    col = _PALETTE[int(rng.random() * len(_PALETTE)) % len(_PALETTE)]
    r = rng.uniform(2.6, 5.4)
    shell = new_lines("lantern_orb_shell", 1.1)
    wire_sphere(shell, 0.0, 0.0, 0.0, r, (*col, 0.55), lat=6, lon=10, segs=20)
    core = new_lines("lantern_orb_core", 1.8)
    wire_sphere(core, 0.0, 0.0, 0.0, r * 0.32, (1.0, 1.0, 0.95, 0.9), lat=3, lon=6, segs=10)
    glow = new_lines("lantern_orb_glow", 4.2)
    wire_sphere(glow, 0.0, 0.0, 0.0, r * 0.34, (*col, 0.25), lat=3, lon=4, segs=10)
    for k in range(rng.randint(4, 7)):
        a = math.tau * k / 6.0 + rng.uniform(-0.3, 0.3)
        length = rng.uniform(r * 2.0, r * 4.5)
        pts = [(math.cos(a) * r * 0.5 + math.sin(t * 3.0 + k) * 0.6, math.sin(a) * r * 0.5, -r * 0.9 - length * t)
               for t in (i / 10.0 for i in range(11))]
        polyline(shell, pts, (*col, 0.35))
    node = finish(parent, "strata_lantern_orb", [glow, shell, core], x, y, z)
    node.setPythonTag("pulse_phase", rng.uniform(0.0, math.tau))
    return node


def update(node, time_value: float) -> None:
    p = float(node.getPythonTag("pulse_phase") or 0.0)
    s = 1.0 + 0.05 * math.sin(float(time_value) * 1.1 + p)
    node.setScale(s)
    node.setH(float(time_value) * 3.0 + p * 30.0)
