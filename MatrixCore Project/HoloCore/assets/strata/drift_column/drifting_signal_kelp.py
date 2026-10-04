"""Strata drop-in: drifting signal kelp (Drift Column).

Kelp with no seabed to hold it: a long wavy wireframe strand with leaf
outlines and a float bulb at the top, swaying as it drifts.
"""
from __future__ import annotations

import math
from random import Random

from holocore_line_kit import finish, new_lines, polyline, wire_sphere

STRATA_OBJECT = {"id": "drifting_signal_kelp", "weight": 1.0, "per_cell": 0.9}

_PALETTE = [(0.20, 1.00, 0.70), (0.10, 0.90, 1.00), (0.60, 1.00, 0.40)]


def build(parent, x, y, z, rng: Random, metadata: dict):
    col = _PALETTE[int(rng.random() * len(_PALETTE)) % len(_PALETTE)]
    length = rng.uniform(36.0, 78.0)
    steps = 26
    phase = rng.uniform(0.0, math.tau)
    spine = []
    for i in range(steps + 1):
        t = i / steps
        spine.append((math.sin(t * 5.0 + phase) * 2.2, math.cos(t * 3.0 + phase) * 1.4, -length * 0.5 + length * t))
    ls = new_lines("drifting_kelp_lines", 1.25)
    polyline(ls, spine, (*col, 0.80))
    glow = new_lines("drifting_kelp_glow", 3.4)
    polyline(glow, spine, (*col, 0.16))
    for i in range(2, steps - 1, 2):
        sx, sy, sz = spine[i]
        side = 1.0 if (i // 2) % 2 == 0 else -1.0
        leaf_len = rng.uniform(3.0, 6.5) * (1.0 - i / (steps * 1.4))
        tip = (sx + side * leaf_len, sy + rng.uniform(-1.0, 1.0), sz + leaf_len * 0.45)
        w = leaf_len * 0.22
        polyline(ls, ((sx, sy, sz), (sx + side * leaf_len * 0.5, sy + w, sz + leaf_len * 0.15), tip,
                      (sx + side * leaf_len * 0.5, sy - w, sz + leaf_len * 0.30), (sx, sy, sz)), (*col, 0.55))
    top = spine[-1]
    wire_sphere(ls, top[0], top[1], top[2] + 1.6, 1.6, (0.85, 1.0, 1.0, 0.7), lat=4, lon=6, segs=12)
    node = finish(parent, "strata_drifting_signal_kelp", [glow, ls], x, y, z)
    node.setH(rng.uniform(0.0, 360.0))
    node.setPythonTag("sway_phase", phase)
    return node


def update(node, time_value: float) -> None:
    p = float(node.getPythonTag("sway_phase") or 0.0)
    t = float(time_value)
    node.setR(math.sin(t * 0.31 + p) * 6.0)
    node.setP(math.cos(t * 0.23 + p) * 4.0)
