"""Deterministic Urban region macro layout for HoloVerse Pass 282.39.

Pure math/data: no Panda3D imports. The same records are consumed by rendering
and movement collision so visible buildings and collision cannot drift apart.
"""
from __future__ import annotations
from dataclasses import dataclass
import math, random

URBAN_STRUCTURES_PER_SECTOR = 9
URBAN_EXTRA_STRUCTURE_SECTORS = 6
URBAN_TOTAL_STRUCTURES = 48 * URBAN_STRUCTURES_PER_SECTOR + URBAN_EXTRA_STRUCTURE_SECTORS
URBAN_CORRIDOR_DEGREES = (-90.0, 0.0, 90.0, 180.0)

@dataclass(frozen=True)
class UrbanStructure:
    x: float; y: float; z: float
    sx: float; sy: float; sz: float
    heading: float; kind: str; tone: int


def _angle_delta(a: float, b: float) -> float:
    return abs((a - b + math.pi) % (math.tau) - math.pi)


def _corridor_clear(angle: float, half_width: float = 0.060) -> bool:
    return all(_angle_delta(angle, math.radians(d)) > half_width for d in URBAN_CORRIDOR_DEGREES)


def generate_urban_structures(sector_idx: int, r0: float, r1: float, *, sector_count: int = 48):
    sector_idx = int(sector_idx) % int(sector_count)
    rng = random.Random(0x282390 + sector_idx * 7919)
    a0 = math.tau * sector_idx / float(sector_count)
    a1 = math.tau * (sector_idx + 1) / float(sector_count)
    target = URBAN_STRUCTURES_PER_SECTOR + (1 if sector_idx < URBAN_EXTRA_STRUCTURE_SECTORS else 0)
    kinds = ("slab", "midrise", "tower", "utility", "damaged")
    items = []
    attempts = 0
    while len(items) < target and attempts < 240:
        attempts += 1
        # Reserve angular margins for street seams and the four radial travel corridors.
        t_a = rng.uniform(0.12, 0.88)
        ang = a0 + (a1 - a0) * t_a
        if not _corridor_clear(ang):
            continue
        # Three staggered city bands leave broad circumferential avenues between them.
        band = (len(items) + sector_idx) % 3
        base_t = (0.20, 0.50, 0.80)[band]
        rt = max(0.09, min(0.91, base_t + rng.uniform(-0.075, 0.075)))
        radius = r0 + (r1 - r0) * rt
        x, y = math.cos(ang) * radius, math.sin(ang) * radius
        kind = kinds[(sector_idx * 3 + len(items) * 2 + attempts) % len(kinds)]
        if kind == "tower":
            sx, sy, sz = rng.uniform(30, 44), rng.uniform(28, 40), rng.uniform(78, 138)
        elif kind == "midrise":
            sx, sy, sz = rng.uniform(42, 66), rng.uniform(34, 58), rng.uniform(42, 76)
        elif kind == "slab":
            sx, sy, sz = rng.uniform(62, 90), rng.uniform(28, 44), rng.uniform(30, 58)
        elif kind == "utility":
            sx, sy, sz = rng.uniform(28, 48), rng.uniform(26, 46), rng.uniform(22, 42)
        else:
            sx, sy, sz = rng.uniform(45, 72), rng.uniform(38, 64), rng.uniform(34, 68)
        heading = ang + (math.pi * 0.5 if (sector_idx + len(items)) % 2 else 0.0)
        items.append(UrbanStructure(x, y, 0.0, sx, sy, sz, heading, kind, (sector_idx + len(items)) % 4))
    return items


def point_inside_structure(x: float, y: float, item: UrbanStructure, padding: float = 1.0) -> bool:
    dx, dy = float(x) - item.x, float(y) - item.y
    c, s = math.cos(-item.heading), math.sin(-item.heading)
    lx, ly = dx * c - dy * s, dx * s + dy * c
    return abs(lx) <= item.sx * 0.5 + padding and abs(ly) <= item.sy * 0.5 + padding
