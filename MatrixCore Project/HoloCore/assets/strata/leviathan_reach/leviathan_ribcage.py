"""Strata drop-in: leviathan ribcage (Leviathan Reach).

The wireframe remains of something enormous: a curved spine of vertebra
rings with paired ribs, 90-160 m long, turning very slowly in the high column.
"""
from __future__ import annotations

import math
from random import Random

from holocore_line_kit import finish, new_lines, polyline, ring

STRATA_OBJECT = {"id": "leviathan_ribcage", "weight": 1.0, "per_cell": 0.30}


def build(parent, x, y, z, rng: Random, metadata: dict):
    accent = tuple(metadata.get("accent") or (0.74, 0.44, 1.0))
    bone = (0.88, 0.86, 1.0)
    length = rng.uniform(90.0, 160.0)
    count = rng.randint(14, 22)
    bend = rng.uniform(6.0, 16.0)
    spine = []
    for i in range(count + 1):
        t = i / count
        spine.append((-length * 0.5 + length * t, 0.0, math.sin(t * math.pi) * bend))
    ls = new_lines("leviathan_bones", 1.3)
    glow = new_lines("leviathan_glow", 3.6)
    polyline(ls, spine, (*bone, 0.75))
    polyline(glow, spine, (*accent, 0.18))
    for i, (sx, sy, sz) in enumerate(spine):
        t = i / count
        girth = math.sin(t * math.pi) ** 0.7
        ring(ls, sx, sy, sz, 1.6 + 1.4 * girth, 1.6 + 1.4 * girth, (*bone, 0.45), segs=10, plane="yz")
        if 0.12 < t < 0.88:
            rib = 9.0 + 16.0 * girth
            for side in (-1.0, 1.0):
                pts = []
                for k in range(9):
                    a = math.pi * 0.5 * k / 8.0
                    pts.append((sx - k * 0.35, side * math.sin(a) * rib, sz - (1.0 - math.cos(a)) * rib * 1.1))
                polyline(ls, pts, (*bone, 0.55))
                polyline(glow, pts, (*accent, 0.10))
    node = finish(parent, "strata_leviathan_ribcage", [glow, ls], x, y, z)
    node.setH(rng.uniform(0.0, 360.0))
    node.setR(rng.uniform(-12.0, 12.0))
    node.setPythonTag("turn", rng.uniform(0.6, 1.4) * (1 if rng.random() < 0.5 else -1))
    node.setPythonTag("h0", node.getH())
    return node


def update(node, time_value: float) -> None:
    node.setH(float(node.getPythonTag("h0") or 0.0) + float(time_value) * float(node.getPythonTag("turn") or 1.0))
