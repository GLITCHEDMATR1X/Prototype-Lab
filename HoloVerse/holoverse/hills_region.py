"""Deterministic Green Hills meadow presentation data for HoloVerse.

Pass 282.32 keeps the region readable as an open meadow instead of cloning the
Forest understory.  The generator is data-only: runtime.py/world.py owns the
actual Panda3D geometry and collision remains terrain-authoritative.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from typing import Sequence

HILLS_MEADOW_SEED = 28232
HILLS_MEADOW_ITEMS_PER_SECTOR = 16
HILLS_MEADOW_CORRIDOR_HALF_WIDTH = 0.072
HILLS_MEADOW_NYX_CLEARANCE = 52.0
HILLS_MEADOW_LANDING_CLEARANCE = 46.0

# Pass 282.45: the opaque low-poly tree forms formerly backing Forest
# move to Green Hills.  Keep this sparse so Hills remains an open-meadow
# region and so the full Forest preview around the Hub sheds that triangle cost.
HILLS_SOLID_TREES_PER_SECTOR = 4
HILLS_SOLID_TREE_SEED = 28245
HILLS_SOLID_TREE_CORRIDOR_HALF_WIDTH = 0.082
HILLS_SOLID_TREE_NYX_CLEARANCE = 66.0
HILLS_SOLID_TREE_LANDING_CLEARANCE = 60.0
HILLS_SOLID_TREE_MIN_SPACING = 24.0
HILLS_SOLID_TREE_VARIANTS = ("canopy", "spire", "tower", "split")

# Pass 282.33: broad repeating landform authority.  These are intentionally
# much larger than meadow props so Green Hills reads as a terrain region first.
# Three staggered polar bands repeat around the annulus; deterministic jitter
# keeps the silhouettes natural without changing between launches.
HILLS_REPEAT_BANDS = (
    # radial_t, repeat_count, radial_half_width_m, tangent_half_width_m, phase_rad
    (0.22, 18, 118.0, 138.0, 0.18),
    (0.50, 22, 128.0, 148.0, 0.92),
    (0.78, 26, 112.0, 128.0, 0.46),
)
HILLS_REPEAT_PEAK_MIN = 1.02
HILLS_REPEAT_PEAK_MAX = 1.72
HILLS_REPEAT_RADIAL_JITTER = 0.032
HILLS_REPEAT_ANGLE_JITTER = 0.16


def _stable_unit(a: int, b: int, salt: int) -> float:
    # Integer-only hash so terrain identity is stable across Python versions.
    value = (int(a) * 73856093) ^ (int(b) * 19349663) ^ (int(salt) * 83492791)
    value = (value ^ (value >> 13)) * 1274126177
    value ^= value >> 16
    return (value & 0xFFFFFFFF) / 4294967295.0


# Precompute stable per-center identity once.  Runtime height queries should not
# spend time hashing deterministic values that never change.
_HILLS_REPEAT_PRECOMPUTED = []
for _band_idx, (_band_t, _repeat_count, _radial_half, _tangent_half, _phase) in enumerate(HILLS_REPEAT_BANDS):
    _rows = []
    _cell = math.tau / float(_repeat_count)
    for _idx in range(int(_repeat_count)):
        _rows.append((
            (_stable_unit(_band_idx, _idx, 17) * 2.0 - 1.0) * HILLS_REPEAT_RADIAL_JITTER,
            (_stable_unit(_band_idx, _idx, 29) * 2.0 - 1.0) * HILLS_REPEAT_ANGLE_JITTER * _cell,
            HILLS_REPEAT_PEAK_MIN + (HILLS_REPEAT_PEAK_MAX - HILLS_REPEAT_PEAK_MIN) * _stable_unit(_band_idx, _idx, 43),
        ))
    _HILLS_REPEAT_PRECOMPUTED.append(tuple(_rows))
_HILLS_REPEAT_PRECOMPUTED = tuple(_HILLS_REPEAT_PRECOMPUTED)


def repeating_hills_relief_at(x: float, y: float, r0: float, r1: float) -> float:
    """Return deterministic broad hill relief in nominal hill-height units.

    The function is continuous in world space.  It does not own ring seam or
    corridor suppression; world.py applies those shared terrain authorities.
    Identity values are precomputed, and only the two centers adjacent to the
    current angular cell are evaluated per band.
    """
    x = float(x); y = float(y); r0 = float(r0); r1 = float(r1)
    radius = math.hypot(x, y)
    span = max(1.0, r1 - r0)
    angle = math.atan2(y, x) % math.tau
    strongest = 0.0
    second = 0.0

    for band_idx, (band_t, repeat_count, radial_half, tangent_half, phase) in enumerate(HILLS_REPEAT_BANDS):
        repeat_count = int(repeat_count)
        cell = math.tau / float(repeat_count)
        cell_pos = (angle - float(phase)) / cell
        # Hill tangential footprints are intentionally narrower than half of a
        # repeated cell.  Therefore only the nominal nearest repeated center
        # can contribute; evaluating neighbors would add cost without changing
        # the visible surface.
        idx = int(round(cell_pos)) % repeat_count
        radial_inv2 = 1.0 / (float(radial_half) * float(radial_half))
        tangent_inv2 = 1.0 / (float(tangent_half) * float(tangent_half))
        radial_jitter, angle_jitter, amp = _HILLS_REPEAT_PRECOMPUTED[band_idx][idx]
        center_t = max(0.08, min(0.92, float(band_t) + radial_jitter))
        center_r = r0 + span * center_t
        center_a = (float(phase) + idx * cell + angle_jitter) % math.tau
        da = ((angle - center_a + math.pi) % math.tau) - math.pi
        dr = radius - center_r
        tangent_distance = da * center_r
        q = dr * dr * radial_inv2 + tangent_distance * tangent_distance * tangent_inv2
        if q < 1.0:
            u = 1.0 - q
            mound = u * u * (3.0 - 2.0 * u)
            score = amp * mound
            if score > strongest:
                second = strongest
                strongest = score
            elif score > second:
                second = score

    shoulder = strongest + second * 0.22
    low_roll = 0.07 * (0.5 + 0.5 * math.sin(angle * 3.0 + radius * 0.0061))
    return max(0.0, shoulder + low_roll)

def audit_repeating_hills(r0: float, r1: float, *, angular_samples: int = 720, radial_samples: int = 96) -> dict:
    values = []
    seam_values = []
    for ri in range(int(radial_samples) + 1):
        radius = float(r0) + (float(r1) - float(r0)) * ri / float(max(1, radial_samples))
        for ai in range(int(angular_samples)):
            angle = math.tau * ai / float(max(1, angular_samples))
            v = repeating_hills_relief_at(math.cos(angle) * radius, math.sin(angle) * radius, r0, r1)
            values.append(v)
            if ri in (0, int(radial_samples)):
                seam_values.append(v)
    return {
        'sample_count': len(values),
        'min_relief': min(values) if values else 0.0,
        'max_relief': max(values) if values else 0.0,
        'mean_relief': sum(values) / max(1, len(values)),
        # World seam authority applies the final zero envelope; this confirms
        # the repeating field itself stays finite before that shared envelope.
        'raw_seam_max': max(seam_values) if seam_values else 0.0,
        'band_count': len(HILLS_REPEAT_BANDS),
        'nominal_hill_count': sum(int(row[1]) for row in HILLS_REPEAT_BANDS),
    }


def _angle_delta(a: float, b: float) -> float:
    return abs((float(a) - float(b) + math.pi) % math.tau - math.pi)


def _xy(radius: float, angle: float) -> tuple[float, float]:
    return math.cos(angle) * radius, math.sin(angle) * radius


@dataclass(frozen=True)
class HillsMeadowItem:
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


def generate_hills_meadow_items(
    sector_idx: int,
    r0: float,
    r1: float,
    *,
    sector_count: int = 48,
    corridor_degrees: Sequence[float] = (-90.0, 0.0, 90.0, 180.0),
    nyx_radius: float = 1222.2,
    landing_radius: float = 1167.8,
    anchor_angle_deg: float = -90.0,
) -> list[HillsMeadowItem]:
    """Return stable, visual-only meadow shapes for one Green Hills sector.

    The ring stays open: all items avoid the four radial travel corridors and
    the Nyx/landing approach points.  No collision data is emitted here.
    """
    sector_idx = int(sector_idx) % int(sector_count)
    a0 = math.tau * sector_idx / float(sector_count)
    a1 = math.tau * (sector_idx + 1) / float(sector_count)
    span = max(1.0, float(r1) - float(r0))
    anchor = math.radians(float(anchor_angle_deg))
    nyx_xy = _xy(float(nyx_radius), anchor)
    landing_xy = _xy(float(landing_radius), anchor)
    corridor_angles = [math.radians(float(v)) % math.tau for v in corridor_degrees]
    rng = random.Random(HILLS_MEADOW_SEED + sector_idx * 104729)
    items: list[HillsMeadowItem] = []

    # An open-meadow distribution: more low grass/stone than shrubs, unlike Forest.
    kinds = (['grass'] * 6) + (['shrub'] * 4) + (['stone'] * 3) + (['seedhead'] * 3)
    rng.shuffle(kinds)

    attempts = 0
    cursor = 0
    while cursor < len(kinds) and attempts < 160:
        attempts += 1
        kind = kinds[cursor]
        # Keep a small radial seam margin so silhouettes never sit directly on a region edge.
        radial_t = rng.uniform(0.075, 0.925)
        radius = float(r0) + span * radial_t
        angle = rng.uniform(a0 + 0.012, a1 - 0.012)
        nearest_corridor = min((_angle_delta(angle, ca) for ca in corridor_angles), default=math.pi)
        if nearest_corridor < HILLS_MEADOW_CORRIDOR_HALF_WIDTH:
            continue

        x, y = _xy(radius, angle)
        if math.hypot(x - nyx_xy[0], y - nyx_xy[1]) < HILLS_MEADOW_NYX_CLEARANCE:
            continue
        if math.hypot(x - landing_xy[0], y - landing_xy[1]) < HILLS_MEADOW_LANDING_CLEARANCE:
            continue

        if kind == 'grass':
            footprint = rng.uniform(1.0, 1.8)
            height = rng.uniform(1.0, 2.5)
            variant = rng.randrange(3)
        elif kind == 'shrub':
            footprint = rng.uniform(2.0, 3.4)
            height = rng.uniform(1.5, 3.1)
            variant = rng.randrange(3)
        elif kind == 'stone':
            footprint = rng.uniform(1.4, 2.8)
            height = rng.uniform(0.7, 1.9)
            variant = rng.randrange(3)
        else:  # seedhead
            footprint = rng.uniform(0.55, 1.0)
            height = rng.uniform(2.8, 5.2)
            variant = rng.randrange(3)

        items.append(HillsMeadowItem(
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


@dataclass(frozen=True)
class HillsSolidTreeItem:
    sector: int
    index: int
    x: float
    y: float
    radius: float
    height: float
    variant: str

    def as_dict(self) -> dict:
        return asdict(self)


def generate_hills_solid_tree_items(
    sector_idx: int,
    r0: float,
    r1: float,
    *,
    sector_count: int = 48,
    corridor_degrees: Sequence[float] = (-90.0, 0.0, 90.0, 180.0),
    nyx_radius: float = 1222.2,
    landing_radius: float = 1167.8,
    anchor_angle_deg: float = -90.0,
) -> list[HillsSolidTreeItem]:
    """Return sparse solid-tree placements for Green Hills.

    These are visual-only.  Placement reuses the same corridor/Nyx/landing
    authority as the meadow and additionally rejects overlap with the existing
    meadow props so the moved tree family reads as intentional composition.
    """
    sector_idx = int(sector_idx) % int(sector_count)
    a0 = math.tau * sector_idx / float(sector_count)
    a1 = math.tau * (sector_idx + 1) / float(sector_count)
    span = max(1.0, float(r1) - float(r0))
    anchor = math.radians(float(anchor_angle_deg))
    nyx_xy = _xy(float(nyx_radius), anchor)
    landing_xy = _xy(float(landing_radius), anchor)
    corridor_angles = [math.radians(float(v)) % math.tau for v in corridor_degrees]
    rng = random.Random(HILLS_SOLID_TREE_SEED + sector_idx * 130363)
    meadow = generate_hills_meadow_items(
        sector_idx, r0, r1, sector_count=sector_count, corridor_degrees=corridor_degrees,
        nyx_radius=nyx_radius, landing_radius=landing_radius, anchor_angle_deg=anchor_angle_deg,
    )
    items: list[HillsSolidTreeItem] = []
    attempts = 0
    while len(items) < int(HILLS_SOLID_TREES_PER_SECTOR) and attempts < 220:
        attempts += 1
        radius_world = float(r0) + span * rng.uniform(0.12, 0.88)
        angle = rng.uniform(a0 + 0.016, a1 - 0.016)
        if min((_angle_delta(angle, ca) for ca in corridor_angles), default=math.pi) < HILLS_SOLID_TREE_CORRIDOR_HALF_WIDTH:
            continue
        x, y = _xy(radius_world, angle)
        crown_radius = rng.uniform(5.0, 8.2)
        height = rng.uniform(15.0, 27.0)
        if math.hypot(x - nyx_xy[0], y - nyx_xy[1]) - crown_radius < HILLS_SOLID_TREE_NYX_CLEARANCE:
            continue
        if math.hypot(x - landing_xy[0], y - landing_xy[1]) - crown_radius < HILLS_SOLID_TREE_LANDING_CLEARANCE:
            continue
        if any(math.hypot(x - item.x, y - item.y) < HILLS_SOLID_TREE_MIN_SPACING + crown_radius + item.radius * 0.35 for item in items):
            continue
        if any(math.hypot(x - item.x, y - item.y) < crown_radius + float(item.radius) + 1.5 for item in meadow):
            continue
        variant = HILLS_SOLID_TREE_VARIANTS[(sector_idx + len(items) + rng.randrange(len(HILLS_SOLID_TREE_VARIANTS))) % len(HILLS_SOLID_TREE_VARIANTS)]
        items.append(HillsSolidTreeItem(
            sector=sector_idx, index=len(items), x=float(x), y=float(y),
            radius=float(crown_radius), height=float(height), variant=str(variant),
        ))
    return items


def audit_hills_solid_trees(
    r0: float,
    r1: float,
    *,
    sector_count: int = 48,
    corridor_degrees: Sequence[float] = (-90.0, 0.0, 90.0, 180.0),
    nyx_radius: float = 1222.2,
    landing_radius: float = 1167.8,
    anchor_angle_deg: float = -90.0,
) -> dict:
    counts = {name: 0 for name in HILLS_SOLID_TREE_VARIANTS}
    min_corridor = math.inf
    min_nyx = math.inf
    min_landing = math.inf
    min_spacing = math.inf
    anchor = math.radians(float(anchor_angle_deg))
    nyx_xy = _xy(float(nyx_radius), anchor)
    landing_xy = _xy(float(landing_radius), anchor)
    corridors = [math.radians(float(v)) % math.tau for v in corridor_degrees]
    rows = []
    for sector in range(int(sector_count)):
        items = generate_hills_solid_tree_items(
            sector, r0, r1, sector_count=sector_count, corridor_degrees=corridor_degrees,
            nyx_radius=nyx_radius, landing_radius=landing_radius, anchor_angle_deg=anchor_angle_deg,
        )
        rows.append({'sector': sector, 'count': len(items)})
        for idx, item in enumerate(items):
            counts[item.variant] = counts.get(item.variant, 0) + 1
            angle = math.atan2(item.y, item.x) % math.tau
            min_corridor = min(min_corridor, min(_angle_delta(angle, ca) for ca in corridors))
            min_nyx = min(min_nyx, math.hypot(item.x - nyx_xy[0], item.y - nyx_xy[1]) - item.radius)
            min_landing = min(min_landing, math.hypot(item.x - landing_xy[0], item.y - landing_xy[1]) - item.radius)
            for other in items[idx+1:]:
                min_spacing = min(min_spacing, math.hypot(item.x-other.x, item.y-other.y))
    total = sum(row['count'] for row in rows)
    return {
        'sector_count': int(sector_count), 'trees_per_sector': int(HILLS_SOLID_TREES_PER_SECTOR),
        'total': int(total), 'expected_total': int(sector_count) * int(HILLS_SOLID_TREES_PER_SECTOR),
        'variant_counts': counts, 'min_corridor_angle_rad': min_corridor,
        'min_nyx_edge_clearance': min_nyx, 'min_landing_edge_clearance': min_landing,
        'min_intra_sector_spacing': min_spacing, 'rows': rows,
        'safe': (total == int(sector_count) * int(HILLS_SOLID_TREES_PER_SECTOR)
                 and min_corridor >= HILLS_SOLID_TREE_CORRIDOR_HALF_WIDTH - 1e-9
                 and min_nyx >= HILLS_SOLID_TREE_NYX_CLEARANCE - 1e-9
                 and min_landing >= HILLS_SOLID_TREE_LANDING_CLEARANCE - 1e-9),
    }


def audit_hills_meadow(
    r0: float,
    r1: float,
    *,
    sector_count: int = 48,
    corridor_degrees: Sequence[float] = (-90.0, 0.0, 90.0, 180.0),
    nyx_radius: float = 1222.2,
    landing_radius: float = 1167.8,
    anchor_angle_deg: float = -90.0,
) -> dict:
    counts = {'grass': 0, 'shrub': 0, 'stone': 0, 'seedhead': 0}
    min_corridor_angle = math.inf
    min_nyx = math.inf
    min_landing = math.inf
    anchor = math.radians(float(anchor_angle_deg))
    nyx_xy = _xy(float(nyx_radius), anchor)
    landing_xy = _xy(float(landing_radius), anchor)
    corridors = [math.radians(float(v)) % math.tau for v in corridor_degrees]
    rows = []
    for sector in range(int(sector_count)):
        items = generate_hills_meadow_items(
            sector, r0, r1,
            sector_count=sector_count,
            corridor_degrees=corridor_degrees,
            nyx_radius=nyx_radius,
            landing_radius=landing_radius,
            anchor_angle_deg=anchor_angle_deg,
        )
        rows.append({'sector': sector, 'item_count': len(items)})
        for item in items:
            counts[item.kind] = counts.get(item.kind, 0) + 1
            angle = math.atan2(item.y, item.x) % math.tau
            min_corridor_angle = min(min_corridor_angle, min(_angle_delta(angle, ca) for ca in corridors))
            min_nyx = min(min_nyx, math.hypot(item.x - nyx_xy[0], item.y - nyx_xy[1]) - item.radius)
            min_landing = min(min_landing, math.hypot(item.x - landing_xy[0], item.y - landing_xy[1]) - item.radius)
    return {
        'sector_count': int(sector_count),
        'counts': counts,
        'total': sum(counts.values()),
        'expected_max': int(sector_count) * HILLS_MEADOW_ITEMS_PER_SECTOR,
        'min_corridor_angle_rad': min_corridor_angle,
        'min_nyx_edge_clearance': min_nyx,
        'min_landing_edge_clearance': min_landing,
        'safe': (
            min_corridor_angle >= HILLS_MEADOW_CORRIDOR_HALF_WIDTH - 1e-9
            and min_nyx >= HILLS_MEADOW_NYX_CLEARANCE - 3.5
            and min_landing >= HILLS_MEADOW_LANDING_CLEARANCE - 3.5
        ),
        'rows': rows,
    }
