"""Deterministic Mushroom macro-structure presentation data for HoloVerse.

Pass 282.34 promotes Mushroom to a full active ring and gives it solid fungal
architecture without inventing a second placement authority.  This module owns
stable structure placement only; world.py owns Panda3D geometry and terrain
height remains the grounding/collision authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from typing import Sequence

MUSHROOM_STRUCTURE_SEED = 28234
MUSHROOM_STRUCTURES_PER_SECTOR = 8
MUSHROOM_STRUCTURE_CORRIDOR_HALF_WIDTH = 0.074
MUSHROOM_STRUCTURE_SOLACE_CLEARANCE = 82.0
MUSHROOM_STRUCTURE_LANDING_CLEARANCE = 72.0
MUSHROOM_STRUCTURE_SEAM_MARGIN_T = 0.085


def _angle_delta(a: float, b: float) -> float:
    return abs((float(a) - float(b) + math.pi) % math.tau - math.pi)


def _xy(radius: float, angle: float) -> tuple[float, float]:
    return math.cos(angle) * radius, math.sin(angle) * radius


@dataclass(frozen=True)
class MushroomStructure:
    sector: int
    index: int
    kind: str
    x: float
    y: float
    radius: float
    height: float
    heading: float
    variant: int

    def as_dict(self) -> dict:
        return asdict(self)


def generate_mushroom_structures(
    sector_idx: int,
    r0: float,
    r1: float,
    *,
    sector_count: int = 48,
    corridor_degrees: Sequence[float] = (-90.0, 0.0, 90.0, 180.0),
    solace_radius: float = 1972.0,
    landing_radius: float = 1918.0,
    anchor_angle_deg: float = -90.0,
) -> list[MushroomStructure]:
    """Return stable large fungal structures for one Mushroom sector.

    Structures deliberately avoid the four authored radial corridors and the
    Solace/landing approach.  They are large visual masses, so the clearance
    budget is larger than for Green Hills meadow props.
    """
    sector_idx = int(sector_idx) % int(sector_count)
    a0 = math.tau * sector_idx / float(sector_count)
    a1 = math.tau * (sector_idx + 1) / float(sector_count)
    span = max(1.0, float(r1) - float(r0))
    anchor = math.radians(float(anchor_angle_deg))
    solace_xy = _xy(float(solace_radius), anchor)
    landing_xy = _xy(float(landing_radius), anchor)
    corridor_angles = [math.radians(float(v)) % math.tau for v in corridor_degrees]
    rng = random.Random(MUSHROOM_STRUCTURE_SEED + sector_idx * 15485863)

    # Every sector gets the same high-level grammar, shuffled so silhouettes do
    # not form obvious radial stripes.
    kinds = [
        "cap_tower", "cap_tower",
        "shelf_column", "shelf_column",
        "spire", "spire",
        "root_mass",
        "arch",
    ]
    rng.shuffle(kinds)

    items: list[MushroomStructure] = []
    attempts = 0
    cursor = 0
    seam = max(0.02, min(0.18, float(MUSHROOM_STRUCTURE_SEAM_MARGIN_T)))
    while cursor < len(kinds) and attempts < 240:
        attempts += 1
        kind = kinds[cursor]
        radial_t = rng.uniform(seam, 1.0 - seam)
        radius = float(r0) + span * radial_t
        angle = rng.uniform(a0 + 0.014, a1 - 0.014)
        nearest_corridor = min((_angle_delta(angle, ca) for ca in corridor_angles), default=math.pi)
        if nearest_corridor < MUSHROOM_STRUCTURE_CORRIDOR_HALF_WIDTH:
            continue

        x, y = _xy(radius, angle)

        if kind == "cap_tower":
            footprint = rng.uniform(7.0, 12.5)
            height = rng.uniform(18.0, 32.0)
            variant = rng.randrange(4)
        elif kind == "shelf_column":
            footprint = rng.uniform(5.0, 9.0)
            height = rng.uniform(15.0, 28.0)
            variant = rng.randrange(4)
        elif kind == "spire":
            footprint = rng.uniform(4.0, 7.0)
            height = rng.uniform(22.0, 38.0)
            variant = rng.randrange(4)
        elif kind == "root_mass":
            footprint = rng.uniform(6.0, 10.0)
            height = rng.uniform(5.0, 10.0)
            variant = rng.randrange(4)
        else:  # arch
            footprint = rng.uniform(9.0, 14.0)
            height = rng.uniform(16.0, 27.0)
            variant = rng.randrange(4)

        # Include the footprint when enforcing the guide/landing clearance.
        if math.hypot(x - solace_xy[0], y - solace_xy[1]) - footprint < MUSHROOM_STRUCTURE_SOLACE_CLEARANCE:
            continue
        if math.hypot(x - landing_xy[0], y - landing_xy[1]) - footprint < MUSHROOM_STRUCTURE_LANDING_CLEARANCE:
            continue

        items.append(MushroomStructure(
            sector=sector_idx,
            index=cursor,
            kind=kind,
            x=float(x),
            y=float(y),
            radius=float(footprint),
            height=float(height),
            heading=float(rng.uniform(0.0, math.tau)),
            variant=int(variant),
        ))
        cursor += 1
    return items


def audit_mushroom_structures(
    r0: float,
    r1: float,
    *,
    sector_count: int = 48,
    corridor_degrees: Sequence[float] = (-90.0, 0.0, 90.0, 180.0),
    solace_radius: float = 1972.0,
    landing_radius: float = 1918.0,
    anchor_angle_deg: float = -90.0,
) -> dict:
    counts = {"cap_tower": 0, "shelf_column": 0, "spire": 0, "root_mass": 0, "arch": 0}
    min_corridor_angle = math.inf
    min_solace = math.inf
    min_landing = math.inf
    anchor = math.radians(float(anchor_angle_deg))
    solace_xy = _xy(float(solace_radius), anchor)
    landing_xy = _xy(float(landing_radius), anchor)
    corridors = [math.radians(float(v)) % math.tau for v in corridor_degrees]
    rows = []

    for sector in range(int(sector_count)):
        items = generate_mushroom_structures(
            sector, r0, r1,
            sector_count=sector_count,
            corridor_degrees=corridor_degrees,
            solace_radius=solace_radius,
            landing_radius=landing_radius,
            anchor_angle_deg=anchor_angle_deg,
        )
        rows.append({"sector": sector, "item_count": len(items)})
        for item in items:
            counts[item.kind] = counts.get(item.kind, 0) + 1
            angle = math.atan2(item.y, item.x) % math.tau
            min_corridor_angle = min(min_corridor_angle, min(_angle_delta(angle, ca) for ca in corridors))
            min_solace = min(min_solace, math.hypot(item.x - solace_xy[0], item.y - solace_xy[1]) - item.radius)
            min_landing = min(min_landing, math.hypot(item.x - landing_xy[0], item.y - landing_xy[1]) - item.radius)

    total = sum(counts.values())
    return {
        "sector_count": int(sector_count),
        "counts": counts,
        "total": total,
        "expected_max": int(sector_count) * MUSHROOM_STRUCTURES_PER_SECTOR,
        "min_corridor_angle_rad": min_corridor_angle,
        "min_solace_edge_clearance": min_solace,
        "min_landing_edge_clearance": min_landing,
        "safe": (
            total == int(sector_count) * MUSHROOM_STRUCTURES_PER_SECTOR
            and min_corridor_angle >= MUSHROOM_STRUCTURE_CORRIDOR_HALF_WIDTH - 1e-9
            and min_solace >= MUSHROOM_STRUCTURE_SOLACE_CLEARANCE - 1e-9
            and min_landing >= MUSHROOM_STRUCTURE_LANDING_CLEARANCE - 1e-9
        ),
        "rows": rows,
    }
