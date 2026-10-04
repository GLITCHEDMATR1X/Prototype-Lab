"""Shared, pure layout helpers for the HoloVerse ring civilizations.

Used by the Ice (Pass 282.54) and Desert (Pass 282.55) rings.  No Panda3D
here, so layouts can be tested headless; ``region_mesh_kit`` turns ``Piece``
records into meshes.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from holoverse.urban_conflict import OObstacle, resolve_move

__all__ = [
    "CORRIDOR_DEGREES", "CORRIDOR_LANE_HALF", "RING_EDGE_MARGIN", "TAU",
    "CircleObstacle", "OObstacle", "Piece",
    "Villager", "angle_delta", "base_z", "corridor_distance", "hash_key", "local", "make_villagers",
    "resolve_move", "ring_spot_is_clear", "villager_pose",
]

TAU = math.tau
CORRIDOR_DEGREES = (-90.0, 0.0, 90.0, 180.0)
CORRIDOR_LANE_HALF = 42.0     # the clear road down every travel corridor
RING_EDGE_MARGIN = 45.0


@dataclass
class Piece:
    """One mesh primitive.

    op:  prism | dome | sweep | obox | disc | ellipsoid | pyramid
    mat: crystal | snow | plain | emissive | obsidian | sandstone | foliage
    """
    op: str
    args: tuple
    rgb: tuple
    mat: str = "plain"
    kw: dict = field(default_factory=dict)


@dataclass
class CircleObstacle:
    x: float
    y: float
    r: float
    top: float

    def contains(self, px: float, py: float, pad: float) -> bool:
        return math.hypot(px - self.x, py - self.y) <= self.r + pad


def angle_delta(a: float, b: float) -> float:
    return abs((a - b + math.pi) % TAU - math.pi)


def local(x, y, heading, lx, ly):
    c, s = math.cos(heading), math.sin(heading)
    return x + lx * c - ly * s, y + lx * s + ly * c


def corridor_distance(x: float, y: float, degrees=CORRIDOR_DEGREES) -> float:
    """Perpendicular distance to the nearest outward travel corridor ray."""
    best = 1e30
    for deg in degrees:
        a = math.radians(deg)
        ux, uy = math.cos(a), math.sin(a)
        if x * ux + y * uy <= 0.0:
            continue
        best = min(best, abs(-x * uy + y * ux))
    return best


def ring_spot_is_clear(x, y, radius, r0, r1, keep_clear=(), placed=(), pad=6.0):
    """Ring margins, corridors, keep-clear circles and already placed footprints."""
    rr = math.hypot(x, y)
    if rr - radius < r0 + RING_EDGE_MARGIN or rr + radius > r1 - RING_EDGE_MARGIN:
        return False
    if corridor_distance(x, y) < CORRIDOR_LANE_HALF + radius:
        return False
    for cx, cy, cr in keep_clear:
        if math.hypot(x - cx, y - cy) < cr + radius:
            return False
    for px, py, pr in placed:
        if math.hypot(x - px, y - py) < pr + radius + pad:
            return False
    return True


def base_z(height_fn, x, y, r, sink=0.6):
    """Lowest ground under a footprint, minus a small sink so nothing floats."""
    zs = [height_fn(x, y)]
    for k in range(6):
        a = TAU * k / 6.0
        zs.append(height_fn(x + math.cos(a) * r, y + math.sin(a) * r))
    return min(zs) - sink


def hash_key(text: str) -> int:
    """Stable 32-bit FNV-1a (Python's hash() changes between runs)."""
    h = 2166136261
    for ch in text:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h


# --------------------------------------------------------------------------
# Town folk (deterministic poses; no state to drift or save)
# --------------------------------------------------------------------------
@dataclass
class Villager:
    uid: str
    mode: str            # stroll | visit
    radius: float
    speed: float
    phase: float
    door: tuple | None = None
    tint: int = 0


def make_villagers(key: str, doors, count: int, stroll_bands):
    """Every third villager visits a door; the rest stroll a plaza band."""
    rng = random.Random(hash_key(key))
    out = []
    for i in range(count):
        if doors and i % 3 == 2:
            door = doors[i % len(doors)]
            out.append(Villager(f"{key}v{i}", "visit", 0.0, rng.uniform(1.0, 1.3), rng.uniform(0.0, 40.0), door, i % 4))
        else:
            sign = -1.0 if i % 2 else 1.0
            band = stroll_bands[rng.randrange(len(stroll_bands))]
            out.append(Villager(f"{key}v{i}", "stroll", rng.uniform(*band), sign * rng.uniform(1.0, 1.45), rng.uniform(0.0, TAU), None, i % 4))
    return out


def villager_pose(cx: float, cy: float, v: Villager, t: float, plaza_ring: float = 30.0):
    """(x, y, heading, walking) for a villager of the town centred on (cx, cy)."""
    if v.mode == "stroll":
        ang = v.phase + (v.speed / v.radius) * t
        x, y = cx + math.cos(ang) * v.radius, cy + math.sin(ang) * v.radius
        heading = ang + (math.pi * 0.5 if v.speed > 0 else -math.pi * 0.5)
        return x, y, heading, True
    # Visit: walk from the plaza ring to a door, pause there, walk back.
    dx, dy = v.door
    ang = math.atan2(dy - cy, dx - cx)
    sx, sy = cx + math.cos(ang) * plaza_ring, cy + math.sin(ang) * plaza_ring
    dist = math.hypot(dx - sx, dy - sy)
    walk = max(0.5, dist / v.speed)
    cycle = walk * 2.0 + 14.0
    c = (t + v.phase) % cycle
    if c < walk:
        f = c / walk
        return sx + (dx - sx) * f, sy + (dy - sy) * f, math.atan2(dy - sy, dx - sx), True
    if c < walk + 8.0:
        return dx, dy, math.atan2(dy - sy, dx - sx), False      # at the door, chatting
    if c < walk * 2.0 + 8.0:
        f = (c - walk - 8.0) / walk
        return dx + (sx - dx) * f, dy + (sy - dy) * f, math.atan2(sy - dy, sx - dx), True
    return sx, sy, ang + math.pi * 0.5, False
