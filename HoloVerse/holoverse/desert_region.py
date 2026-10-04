"""Deterministic Desert terrain and macro-shape data for HoloVerse.

Pass 282.36 keeps Ember Hangar's repaired gameplay frozen while rebuilding the
Desert as a readable landscape.  This module owns stable dune relief and
visual-only macro placements.  world.py remains the single terrain/collision
and Panda3D rendering authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from typing import Sequence

DESERT_VISUAL_SEED = 28236
DESERT_MACRO_STRUCTURES_PER_SECTOR = 8
DESERT_STRUCTURE_CORRIDOR_HALF_WIDTH = 0.076
DESERT_STRUCTURE_EMBER_CLEARANCE = 96.0
DESERT_STRUCTURE_LANDING_CLEARANCE = 84.0
DESERT_STRUCTURE_SEAM_MARGIN_T = 0.080

# A small number of continuous wave families is cheaper and more natural than
# evaluating hundreds of independent mound centers for every terrain vertex.
# (heading radians, wavelength metres, amplitude, phase, lateral warp scale)
DESERT_DUNE_WAVES = (
    (0.34, 118.0, 1.00, 0.30, 420.0),
    (0.92, 176.0, 0.58, 2.10, 620.0),
    (-0.28, 244.0, 0.34, 1.18, 780.0),
)


def _smoothstep01(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return t * t * (3.0 - 2.0 * t)


def desert_dune_relief_at(x: float, y: float, r0: float, r1: float) -> float:
    """Return continuous normalized dune relief for the compact Desert ring.

    Crests are broad enough to read from ground level, while a secondary wave
    family breaks perfect repetition.  Shared ring seam and corridor easing is
    still applied by world.py, so this function never owns traversal authority.
    """
    x = float(x); y = float(y)
    radius = math.hypot(x, y)
    span = max(1.0, float(r1) - float(r0))
    ring_t = max(0.0, min(1.0, (radius - float(r0)) / span))

    total = 0.0
    weight = 0.0
    for heading, wavelength, amp, phase, warp_scale in DESERT_DUNE_WAVES:
        c = math.cos(float(heading)); s = math.sin(float(heading))
        along = x * c + y * s
        across = -x * s + y * c
        warp = math.sin(across / float(warp_scale) * math.tau + float(phase) * 0.45) * 0.55
        wave = math.sin((along / float(wavelength)) * math.tau + float(phase) + warp)
        # Sharpen the windward crest while leaving broad leeward slopes.
        normalized = 0.5 + 0.5 * wave
        crest = _smoothstep01(normalized) ** 1.65
        total += crest * float(amp)
        weight += float(amp)

    dunes = total / max(1e-6, weight)
    # Slow radial modulation avoids an obvious endless wallpaper frequency.
    broad = 0.5 + 0.5 * math.sin(ring_t * math.tau * 2.35 + math.atan2(y, x) * 1.4)
    return 0.12 + dunes * 1.68 + broad * 0.22


def _angle_delta(a: float, b: float) -> float:
    return abs((float(a) - float(b) + math.pi) % math.tau - math.pi)


def _xy(radius: float, angle: float) -> tuple[float, float]:
    return math.cos(angle) * radius, math.sin(angle) * radius


@dataclass(frozen=True)
class DesertMacroStructure:
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


def generate_desert_macro_structures(
    sector_idx: int,
    r0: float,
    r1: float,
    *,
    sector_count: int = 48,
    corridor_degrees: Sequence[float] = (-90.0, 0.0, 90.0, 180.0),
    ember_radius: float = 2728.0,
    landing_radius: float = 2672.0,
    anchor_angle_deg: float = -90.0,
) -> list[DesertMacroStructure]:
    """Return stable Desert silhouettes for one sector.

    The grammar favors natural landforms.  One buried ruin remains per sector
    as a sparse HoloVerse/civilization accent rather than the dominant shape.
    All placements avoid authored travel corridors and Ember's approach.
    """
    sector_idx = int(sector_idx) % int(sector_count)
    a0 = math.tau * sector_idx / float(sector_count)
    a1 = math.tau * (sector_idx + 1) / float(sector_count)
    span = max(1.0, float(r1) - float(r0))
    anchor = math.radians(float(anchor_angle_deg))
    ember_xy = _xy(float(ember_radius), anchor)
    landing_xy = _xy(float(landing_radius), anchor)
    corridor_angles = [math.radians(float(v)) % math.tau for v in corridor_degrees]
    rng = random.Random(DESERT_VISUAL_SEED + sector_idx * 32452843)

    kinds = [
        "mesa", "mesa",
        "rock_spire", "rock_spire",
        "boulder_field", "boulder_field", "boulder_field",
        "buried_ruin",
    ]
    rng.shuffle(kinds)

    items: list[DesertMacroStructure] = []
    attempts = 0
    cursor = 0
    seam = max(0.03, min(0.18, float(DESERT_STRUCTURE_SEAM_MARGIN_T)))
    while cursor < len(kinds) and attempts < 320:
        attempts += 1
        kind = kinds[cursor]
        radial_t = rng.uniform(seam, 1.0 - seam)
        radius = float(r0) + span * radial_t
        angle = rng.uniform(a0 + 0.014, a1 - 0.014)
        if min((_angle_delta(angle, ca) for ca in corridor_angles), default=math.pi) < DESERT_STRUCTURE_CORRIDOR_HALF_WIDTH:
            continue
        x, y = _xy(radius, angle)

        if kind == "mesa":
            footprint = rng.uniform(16.0, 27.0)
            height = rng.uniform(22.0, 43.0)
            variant = rng.randrange(4)
        elif kind == "rock_spire":
            footprint = rng.uniform(6.0, 11.0)
            height = rng.uniform(20.0, 42.0)
            variant = rng.randrange(4)
        elif kind == "boulder_field":
            footprint = rng.uniform(9.0, 16.0)
            height = rng.uniform(5.0, 12.0)
            variant = rng.randrange(4)
        else:
            footprint = rng.uniform(12.0, 20.0)
            height = rng.uniform(8.0, 16.0)
            variant = rng.randrange(4)

        if math.hypot(x - ember_xy[0], y - ember_xy[1]) - footprint < DESERT_STRUCTURE_EMBER_CLEARANCE:
            continue
        if math.hypot(x - landing_xy[0], y - landing_xy[1]) - footprint < DESERT_STRUCTURE_LANDING_CLEARANCE:
            continue

        items.append(DesertMacroStructure(
            sector=sector_idx,
            index=cursor,
            kind=kind,
            x=float(x), y=float(y),
            radius=float(footprint),
            height=float(height),
            heading=float(rng.uniform(0.0, math.tau)),
            variant=int(variant),
        ))
        cursor += 1
    return items


def audit_desert_macro_structures(
    r0: float,
    r1: float,
    *,
    sector_count: int = 48,
    corridor_degrees: Sequence[float] = (-90.0, 0.0, 90.0, 180.0),
    ember_radius: float = 2728.0,
    landing_radius: float = 2672.0,
    anchor_angle_deg: float = -90.0,
) -> dict:
    counts = {"mesa": 0, "rock_spire": 0, "boulder_field": 0, "buried_ruin": 0}
    min_corridor = math.inf
    min_ember = math.inf
    min_landing = math.inf
    anchor = math.radians(float(anchor_angle_deg))
    ember_xy = _xy(float(ember_radius), anchor)
    landing_xy = _xy(float(landing_radius), anchor)
    corridors = [math.radians(float(v)) % math.tau for v in corridor_degrees]
    rows = []
    for sector in range(int(sector_count)):
        items = generate_desert_macro_structures(
            sector, r0, r1,
            sector_count=sector_count,
            corridor_degrees=corridor_degrees,
            ember_radius=ember_radius,
            landing_radius=landing_radius,
            anchor_angle_deg=anchor_angle_deg,
        )
        rows.append({"sector": sector, "item_count": len(items)})
        for item in items:
            counts[item.kind] = counts.get(item.kind, 0) + 1
            angle = math.atan2(item.y, item.x) % math.tau
            min_corridor = min(min_corridor, min(_angle_delta(angle, ca) for ca in corridors))
            min_ember = min(min_ember, math.hypot(item.x - ember_xy[0], item.y - ember_xy[1]) - item.radius)
            min_landing = min(min_landing, math.hypot(item.x - landing_xy[0], item.y - landing_xy[1]) - item.radius)
    total = sum(counts.values())
    return {
        "sector_count": int(sector_count),
        "counts": counts,
        "total": total,
        "expected": int(sector_count) * DESERT_MACRO_STRUCTURES_PER_SECTOR,
        "min_corridor_angle_rad": min_corridor,
        "min_ember_edge_clearance": min_ember,
        "min_landing_edge_clearance": min_landing,
        "safe": (
            total == int(sector_count) * DESERT_MACRO_STRUCTURES_PER_SECTOR
            and min_corridor >= DESERT_STRUCTURE_CORRIDOR_HALF_WIDTH - 1e-9
            and min_ember >= DESERT_STRUCTURE_EMBER_CLEARANCE - 1e-9
            and min_landing >= DESERT_STRUCTURE_LANDING_CLEARANCE - 1e-9
        ),
        "rows": rows,
    }


def audit_desert_dunes(r0: float, r1: float, *, radial_samples: int = 72, angular_samples: int = 360) -> dict:
    vals = []
    for ri in range(int(radial_samples) + 1):
        radius = float(r0) + (float(r1) - float(r0)) * ri / float(max(1, radial_samples))
        for ai in range(int(angular_samples)):
            a = math.tau * ai / float(max(1, angular_samples))
            vals.append(desert_dune_relief_at(math.cos(a) * radius, math.sin(a) * radius, r0, r1))
    return {
        "sample_count": len(vals),
        "min_relief": min(vals) if vals else 0.0,
        "max_relief": max(vals) if vals else 0.0,
        "mean_relief": sum(vals) / max(1, len(vals)),
        "wave_family_count": len(DESERT_DUNE_WAVES),
    }
