"""Shared Frost Circuit course geometry authority.

Pass 282.38 replaces the old full-ring circle with a compact, readable local
circuit near Mirror.  Both the race runtime and Ice macro generator consume
this module so the visible track, gameplay waypoints and world clearances can
never disagree about where the course actually is.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Iterable

FROST_TRACK_SCHEMA = 2
FROST_TRACK_ANCHOR_DEG = -90.0
FROST_TRACK_CENTER_RADIUS = 3420.0
FROST_TRACK_HALF_WIDTH = 38.0
FROST_TRACK_WORLD_CLEARANCE = 88.0
FROST_TRACK_SAMPLE_COUNT = 64

# Local coordinates: U follows the tangential axis, V follows the outward
# radial axis.  Control point 0 is the start/finish near Mirror.  The sequence
# deliberately creates a start straight, broad sweeper, tighter lower turn,
# long return arc and a short final bend rather than one continuous circle.
FROST_TRACK_CONTROL_POINTS = (
    (0.0, 82.0),
    (165.0, 100.0),
    (300.0, 42.0),
    (326.0, -78.0),
    (238.0, -165.0),
    (78.0, -194.0),
    (-86.0, -177.0),
    (-244.0, -132.0),
    (-334.0, -28.0),
    (-306.0, 103.0),
    (-178.0, 171.0),
    (-48.0, 142.0),
)


def _basis(anchor_deg: float = FROST_TRACK_ANCHOR_DEG):
    a = math.radians(float(anchor_deg))
    radial = (math.cos(a), math.sin(a))
    tangent = (-radial[1], radial[0])
    return radial, tangent


def local_to_world(u: float, v: float, *, center_radius: float = FROST_TRACK_CENTER_RADIUS, anchor_deg: float = FROST_TRACK_ANCHOR_DEG) -> tuple[float, float]:
    radial, tangent = _basis(anchor_deg)
    cx = radial[0] * float(center_radius)
    cy = radial[1] * float(center_radius)
    return (
        cx + tangent[0] * float(u) + radial[0] * float(v),
        cy + tangent[1] * float(u) + radial[1] * float(v),
    )


def _catmull_rom(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    t2 = t * t
    t3 = t2 * t
    def c(i: int) -> float:
        return 0.5 * (
            (2.0 * p1[i])
            + (-p0[i] + p2[i]) * t
            + (2.0*p0[i] - 5.0*p1[i] + 4.0*p2[i] - p3[i]) * t2
            + (-p0[i] + 3.0*p1[i] - 3.0*p2[i] + p3[i]) * t3
        )
    return c(0), c(1)


@lru_cache(maxsize=8)
def sampled_local_centerline(sample_count: int = FROST_TRACK_SAMPLE_COUNT) -> tuple[tuple[float, float], ...]:
    cps = FROST_TRACK_CONTROL_POINTS
    n = len(cps)
    count = max(n * 2, int(sample_count))
    out: list[tuple[float, float]] = []
    for k in range(count):
        f = (k / float(count)) * n
        i = int(math.floor(f)) % n
        t = f - math.floor(f)
        p0 = cps[(i - 1) % n]
        p1 = cps[i % n]
        p2 = cps[(i + 1) % n]
        p3 = cps[(i + 2) % n]
        out.append(_catmull_rom(p0, p1, p2, p3, t))
    return tuple(out)


@lru_cache(maxsize=8)
def sampled_world_centerline(sample_count: int = FROST_TRACK_SAMPLE_COUNT) -> tuple[tuple[float, float], ...]:
    return tuple(local_to_world(u, v) for u, v in sampled_local_centerline(sample_count))


def nearest_centerline_info(x: float, y: float, *, sample_count: int = FROST_TRACK_SAMPLE_COUNT) -> tuple[float, float, float, float, float]:
    """Return distance, nearest x/y and unit tangent for the course ribbon."""
    pts = sampled_world_centerline(sample_count)
    if not pts:
        return 1e9, float(x), float(y), 0.0, 1.0
    px = float(x); py = float(y)
    best2 = 1e30
    best = (px, py, 0.0, 1.0)
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        ax, ay = a; bx, by = b
        vx = bx - ax; vy = by - ay
        den = vx*vx + vy*vy
        t = 0.0 if den <= 1e-9 else max(0.0, min(1.0, (px-ax)*vx + (py-ay)*vy) / den)
        qx = ax + vx*t; qy = ay + vy*t
        dx = px - qx; dy = py - qy
        d2 = dx*dx + dy*dy
        if d2 < best2:
            best2 = d2
            length = math.sqrt(max(1e-12, den))
            best = (qx, qy, vx/length, vy/length)
    return math.sqrt(best2), best[0], best[1], best[2], best[3]


def nearest_centerline_distance(x: float, y: float, *, sample_count: int = FROST_TRACK_SAMPLE_COUNT) -> float:
    return nearest_centerline_info(x, y, sample_count=sample_count)[0]


def track_length(sample_count: int = FROST_TRACK_SAMPLE_COUNT) -> float:
    pts = sampled_world_centerline(sample_count)
    total = 0.0
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        total += math.hypot(b[0]-a[0], b[1]-a[1])
    return total
