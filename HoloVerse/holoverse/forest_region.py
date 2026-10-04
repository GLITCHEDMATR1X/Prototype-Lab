"""Deterministic forest-ring detail placement for HoloVerse.

This module deliberately has no Panda3D imports so the live forest coverage
contract can be audited without launching the renderer.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, asdict
from typing import Iterable, Sequence

FOREST_DETAIL_PATCHES_PER_SECTOR = 5
FOREST_DETAIL_PLANTS_PER_PATCH = 5
FOREST_DETAIL_PATCH_RADIUS_MIN = 15.5
FOREST_DETAIL_PATCH_RADIUS_MAX = 20.5
FOREST_DETAIL_PATCH_RADIUS_FLOOR = 12.0
FOREST_DETAIL_CORRIDOR_HALF_WIDTH = 0.072
FOREST_DETAIL_CORRIDOR_MAX_WEIGHT = 0.12
# Clearances below are measured from the OUTER EDGE of a dense pocket, not
# merely from its center.  This matters because the live product has long
# radial travel lanes and the Vanta/teleport approach must remain visually open.
FOREST_DETAIL_VANTA_CLEARANCE = 66.0
FOREST_DETAIL_LANDING_CLEARANCE = 56.0
FOREST_DETAIL_CORRIDOR_EDGE_MARGIN = 0.012
FOREST_DETAIL_SEED = 28221  # deterministic identity preserved across scale pass


@dataclass(frozen=True)
class ForestDetailPatch:
    sector: int
    index: int
    angle: float
    radius: float
    patch_radius: float
    scale: float
    phase: float
    template: int

    def as_dict(self) -> dict:
        return asdict(self)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _smootherstep(value: float) -> float:
    t = _clamp(float(value), 0.0, 1.0)
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _angle_delta(a: float, b: float) -> float:
    return abs((float(a) - float(b) + math.pi) % math.tau - math.pi)


def corridor_weight(angle: float, corridor_degrees: Sequence[float], lane_half_width: float = FOREST_DETAIL_CORRIDOR_HALF_WIDTH) -> float:
    best = 0.0
    lane_half_width = max(0.010, float(lane_half_width))
    for deg in corridor_degrees:
        d = _angle_delta(float(angle), math.radians(float(deg)))
        if d < lane_half_width:
            best = max(best, 1.0 - _smootherstep(d / lane_half_width))
    return _clamp(best, 0.0, 1.0)


def _xy(radius: float, angle: float) -> tuple[float, float]:
    return math.cos(angle) * float(radius), math.sin(angle) * float(radius)


def _distance_to_polar(radius: float, angle: float, other_radius: float, other_angle: float) -> float:
    x, y = _xy(radius, angle)
    ox, oy = _xy(other_radius, other_angle)
    return math.hypot(x - ox, y - oy)


def generate_forest_detail_patches(
    sector_idx: int,
    r0: float,
    r1: float,
    *,
    sector_count: int = 48,
    corridor_degrees: Sequence[float] = (-90.0, 0.0, 90.0, 180.0),
    patches_per_sector: int = FOREST_DETAIL_PATCHES_PER_SECTOR,
    vanta_radius: float = 1010.0,
    landing_radius: float = 962.0,
    anchor_angle_deg: float = -90.0,
) -> list[ForestDetailPatch]:
    """Return stable canopy-pocket placements for one forest sector.

    Every sector receives the same *coverage budget*, but the locations, scale,
    phase and template vary deterministically.  The four radial travel corridors
    and the Vanta/teleport approach remain deliberately open.
    """
    sector_idx = int(sector_idx) % int(sector_count)
    width = math.tau / float(sector_count)
    a0 = sector_idx * width
    span = max(1.0, float(r1) - float(r0))
    anchor_angle = math.radians(float(anchor_angle_deg))
    rng = random.Random(FOREST_DETAIL_SEED + sector_idx * 104729)

    # Five radial bands intentionally mirror the old five-plant verdant-canopy
    # pocket, but distribute that authored density across the full sector.
    radial_t = [0.17, 0.33, 0.50, 0.67, 0.83]
    angular_u = [0.22, 0.70, 0.42, 0.82, 0.30]
    rotate = sector_idx % len(angular_u)
    angular_u = angular_u[rotate:] + angular_u[:rotate]

    patches: list[ForestDetailPatch] = []
    for idx in range(max(1, int(patches_per_sector))):
        # Choose the footprint before placement so the entire pocket, not just
        # its center, can be validated against travel/arrival clearances.
        base_patch_radius = rng.uniform(FOREST_DETAIL_PATCH_RADIUS_MIN, FOREST_DETAIL_PATCH_RADIUS_MAX)
        t = radial_t[idx % len(radial_t)] + rng.uniform(-0.028, 0.028)
        target_radius = float(r0) + span * _clamp(t, 0.08, 0.92)
        base_u = angular_u[idx % len(angular_u)] + rng.uniform(-0.045, 0.045)

        # Try the accepted 282.21 footprint first.  When the entire world is
        # compressed inward, a pocket near a radial corridor subtends more
        # angle even though its physical size is unchanged.  Only if the full
        # footprint cannot satisfy the same corridor/guide clearances do we
        # reduce that one pocket, preserving plant count and density.
        patch_radius_candidates = (
            base_patch_radius,
            max(FOREST_DETAIL_PATCH_RADIUS_FLOOR, base_patch_radius * 0.90),
            max(FOREST_DETAIL_PATCH_RADIUS_FLOOR, base_patch_radius * 0.80),
            max(FOREST_DETAIL_PATCH_RADIUS_FLOOR, base_patch_radius * 0.70),
        )
        angle_candidates = (
            base_u, base_u + 0.12, base_u - 0.12, base_u + 0.22, base_u - 0.22,
            base_u + 0.32, base_u - 0.32, 0.50, 0.18, 0.82, 0.30, 0.70, 0.08, 0.92,
        )
        radius_candidates = (
            target_radius,
            target_radius - span * 0.10, target_radius + span * 0.10,
            target_radius - span * 0.18, target_radius + span * 0.18,
            float(r0) + span * 0.92, float(r0) + span * 0.82,
            float(r0) + span * 0.72, float(r0) + span * 0.62,
            float(r0) + span * 0.52, float(r0) + span * 0.42,
            float(r0) + span * 0.32, float(r0) + span * 0.22,
            float(r0) + span * 0.10,
        )
        chosen_angle = None
        chosen_radius = None
        chosen_patch_radius = None
        for patch_radius in patch_radius_candidates:
            for raw_radius in radius_candidates:
                radius = _clamp(raw_radius, float(r0) + span * 0.08, float(r0) + span * 0.92)
                for raw_u in angle_candidates:
                    u = _clamp(raw_u, 0.08, 0.92)
                    angle = a0 + width * u
                    footprint_angle = math.asin(min(0.95, patch_radius / max(1.0, radius)))
                    nearest_corridor = min((_angle_delta(angle, math.radians(float(deg))) for deg in corridor_degrees), default=math.pi)
                    if nearest_corridor <= FOREST_DETAIL_CORRIDOR_HALF_WIDTH + footprint_angle + FOREST_DETAIL_CORRIDOR_EDGE_MARGIN:
                        continue
                    if corridor_weight(angle, corridor_degrees) > FOREST_DETAIL_CORRIDOR_MAX_WEIGHT:
                        continue
                    if _distance_to_polar(radius, angle, vanta_radius, anchor_angle) - patch_radius < FOREST_DETAIL_VANTA_CLEARANCE:
                        continue
                    if _distance_to_polar(radius, angle, landing_radius, anchor_angle) - patch_radius < FOREST_DETAIL_LANDING_CLEARANCE:
                        continue
                    too_close = False
                    for previous in patches:
                        px, py = _xy(previous.radius, previous.angle)
                        cx, cy = _xy(radius, angle)
                        if math.hypot(cx - px, cy - py) < (patch_radius + previous.patch_radius) * 0.86:
                            too_close = True
                            break
                    if too_close:
                        continue
                    chosen_angle = angle
                    chosen_radius = radius
                    chosen_patch_radius = patch_radius
                    break
                if chosen_angle is not None:
                    break
            if chosen_angle is not None:
                break
        if chosen_angle is None or chosen_radius is None or chosen_patch_radius is None:
            raise RuntimeError(f"forest detail patch has no safe placement: sector={sector_idx} patch={idx}")
        patch_radius = float(chosen_patch_radius)

        patches.append(
            ForestDetailPatch(
                sector=sector_idx,
                index=idx,
                angle=float(chosen_angle),
                radius=float(chosen_radius),
                patch_radius=float(patch_radius),
                scale=rng.uniform(0.90, 1.12),
                phase=rng.uniform(0.0, math.tau),
                template=(sector_idx * 7 + idx * 3) % 4,
            )
        )
    return patches


def audit_forest_detail_coverage(
    r0: float,
    r1: float,
    *,
    sector_count: int = 48,
    corridor_degrees: Sequence[float] = (-90.0, 0.0, 90.0, 180.0),
    vanta_radius: float = 1010.0,
    landing_radius: float = 962.0,
) -> dict:
    sectors = []
    min_corridor_clearance = float("inf")
    min_corridor_edge_clearance = float("inf")
    min_vanta_clearance = float("inf")
    min_landing_clearance = float("inf")
    min_vanta_edge_clearance = float("inf")
    min_landing_edge_clearance = float("inf")
    anchor_angle = math.radians(-90.0)
    for sector in range(int(sector_count)):
        patches = generate_forest_detail_patches(
            sector,
            r0,
            r1,
            sector_count=sector_count,
            corridor_degrees=corridor_degrees,
            vanta_radius=vanta_radius,
            landing_radius=landing_radius,
        )
        sector_rows = []
        for patch in patches:
            cw = corridor_weight(patch.angle, corridor_degrees)
            vanta_dist = _distance_to_polar(patch.radius, patch.angle, vanta_radius, anchor_angle)
            landing_dist = _distance_to_polar(patch.radius, patch.angle, landing_radius, anchor_angle)
            footprint_angle = math.asin(min(0.95, patch.patch_radius / max(1.0, patch.radius)))
            nearest_corridor = min((_angle_delta(patch.angle, math.radians(float(deg))) for deg in corridor_degrees), default=math.pi)
            corridor_edge_clearance = nearest_corridor - footprint_angle - FOREST_DETAIL_CORRIDOR_HALF_WIDTH
            vanta_edge = vanta_dist - patch.patch_radius
            landing_edge = landing_dist - patch.patch_radius
            min_corridor_clearance = min(min_corridor_clearance, cw)
            min_corridor_edge_clearance = min(min_corridor_edge_clearance, corridor_edge_clearance)
            min_vanta_clearance = min(min_vanta_clearance, vanta_dist)
            min_landing_clearance = min(min_landing_clearance, landing_dist)
            min_vanta_edge_clearance = min(min_vanta_edge_clearance, vanta_edge)
            min_landing_edge_clearance = min(min_landing_edge_clearance, landing_edge)
            sector_rows.append({**patch.as_dict(), "corridor_weight": cw, "corridor_edge_clearance_rad": corridor_edge_clearance, "vanta_distance": vanta_dist, "landing_distance": landing_dist, "vanta_edge_clearance": vanta_edge, "landing_edge_clearance": landing_edge})
        sectors.append({"sector": sector, "patch_count": len(patches), "patches": sector_rows})
    return {
        "sector_count": int(sector_count),
        "patches_per_sector": FOREST_DETAIL_PATCHES_PER_SECTOR,
        "plants_per_patch": FOREST_DETAIL_PLANTS_PER_PATCH,
        "total_patch_count_full_ring": sum(row["patch_count"] for row in sectors),
        "total_detail_plants_full_ring": sum(row["patch_count"] for row in sectors) * FOREST_DETAIL_PLANTS_PER_PATCH,
        "max_corridor_weight": max((p["corridor_weight"] for row in sectors for p in row["patches"]), default=0.0),
        "min_corridor_edge_clearance_rad": min_corridor_edge_clearance,
        "min_vanta_clearance": min_vanta_clearance,
        "min_landing_clearance": min_landing_clearance,
        "min_vanta_edge_clearance": min_vanta_edge_clearance,
        "min_landing_edge_clearance": min_landing_edge_clearance,
        "sectors": sectors,
    }

# Pass 282.31: deterministic, visual-only forest understory.  These items live
# *inside* the already-validated dense forest pockets, so the travel corridors,
# Vanta approach and landing approach keep the same authority as Pass 282.21.
FOREST_UNDERSTORY_SEED = 28231
FOREST_UNDERSTORY_BUSHES_PER_PATCH = 2
FOREST_UNDERSTORY_FERNS_PER_PATCH = 2
FOREST_UNDERSTORY_GRASS_PER_PATCH = 3
FOREST_UNDERSTORY_DEADFALL_EVERY = 2


@dataclass(frozen=True)
class ForestUnderstoryItem:
    sector: int
    patch: int
    index: int
    kind: str
    x: float
    y: float
    radius: float
    height: float
    heading: float
    variant: int
    local_distance: float
    safe_patch_radius: float

    def as_dict(self) -> dict:
        return asdict(self)


def generate_forest_understory_items(
    sector_idx: int,
    r0: float,
    r1: float,
    *,
    sector_count: int = 48,
    corridor_degrees: Sequence[float] = (-90.0, 0.0, 90.0, 180.0),
    vanta_radius: float = 1010.0,
    landing_radius: float = 962.0,
    anchor_angle_deg: float = -90.0,
) -> list[ForestUnderstoryItem]:
    """Return stable low vegetation contained by validated forest pockets.

    The returned positions are deliberately non-colliding presentation data.
    Each footprint is constrained to the inner 84% of its parent patch, so the
    existing patch-level travel/arrival clearance remains conservative.
    """
    patches = generate_forest_detail_patches(
        sector_idx,
        r0,
        r1,
        sector_count=sector_count,
        corridor_degrees=corridor_degrees,
        vanta_radius=vanta_radius,
        landing_radius=landing_radius,
        anchor_angle_deg=anchor_angle_deg,
    )
    rng = random.Random(FOREST_UNDERSTORY_SEED + (int(sector_idx) % int(sector_count)) * 130363)
    items: list[ForestUnderstoryItem] = []

    for patch in patches:
        cx, cy = _xy(patch.radius, patch.angle)
        radial = (math.cos(patch.angle), math.sin(patch.angle))
        tangent = (-radial[1], radial[0])
        # Stable motif angles distribute the strata around the taller canopy
        # plants instead of making a uniform ring of identical bushes.
        motif = [0.18, 0.59, 0.83, 0.36, 0.71, 0.48, 0.93, 0.27]
        motif = motif[(patch.template + patch.index) % len(motif):] + motif[:(patch.template + patch.index) % len(motif)]
        cursor = 0

        def add(kind: str, distance_t: float, footprint: float, height: float, variant: int):
            nonlocal cursor
            angle = patch.phase + math.tau * motif[cursor % len(motif)] + rng.uniform(-0.16, 0.16)
            cursor += 1
            # Clamp the object inside the safe interior of the already-audited
            # patch footprint.  `footprint` is a conservative XY half-extent.
            safe_radius = float(patch.patch_radius) * 0.84
            local_distance = min(float(patch.patch_radius) * float(distance_t), max(0.0, safe_radius - footprint))
            lx = math.cos(angle) * local_distance
            ly = math.sin(angle) * local_distance
            x = cx + radial[0] * lx + tangent[0] * ly
            y = cy + radial[1] * lx + tangent[1] * ly
            items.append(ForestUnderstoryItem(
                sector=int(patch.sector),
                patch=int(patch.index),
                index=len(items),
                kind=str(kind),
                x=float(x),
                y=float(y),
                radius=float(footprint),
                height=float(height),
                heading=float(angle),
                variant=int(variant),
                local_distance=float(local_distance),
                safe_patch_radius=float(safe_radius),
            ))

        # Shrubs: two distinct silhouettes per pocket.  They are the primary
        # new visual mass and remain short enough to preserve sightlines.
        for i in range(FOREST_UNDERSTORY_BUSHES_PER_PATCH):
            footprint = rng.uniform(2.3, 3.8) * patch.scale
            add('bush', 0.30 + i * 0.30, footprint, rng.uniform(1.9, 3.7) * patch.scale, (patch.template + i) % 3)
        # Ferns: mid layer beneath the shrubs/canopy.
        for i in range(FOREST_UNDERSTORY_FERNS_PER_PATCH):
            footprint = rng.uniform(1.7, 2.7) * patch.scale
            add('fern', 0.38 + i * 0.27, footprint, rng.uniform(1.5, 2.9) * patch.scale, (patch.template + i + 1) % 3)
        # Ground clumps: low silhouette breakup.  These are deliberately sparse
        # enough that the forest floor still reads as navigable.
        for i in range(FOREST_UNDERSTORY_GRASS_PER_PATCH):
            footprint = rng.uniform(0.9, 1.55) * patch.scale
            add('grass', 0.26 + i * 0.20, footprint, rng.uniform(0.8, 1.65) * patch.scale, (patch.template + i + 2) % 3)
        # One piece of deadfall in alternating pockets creates organic history
        # without turning every patch into debris.
        if (patch.index + patch.sector) % FOREST_UNDERSTORY_DEADFALL_EVERY == 0:
            half_len = rng.uniform(3.2, 5.5) * patch.scale
            add('deadfall', 0.48, half_len, rng.uniform(0.45, 0.85) * patch.scale, patch.template % 2)

    return items


def audit_forest_understory(
    r0: float,
    r1: float,
    *,
    sector_count: int = 48,
    corridor_degrees: Sequence[float] = (-90.0, 0.0, 90.0, 180.0),
    vanta_radius: float = 1010.0,
    landing_radius: float = 962.0,
    anchor_angle_deg: float = -90.0,
) -> dict:
    counts = {'bush': 0, 'fern': 0, 'grass': 0, 'deadfall': 0}
    containment_margin = float('inf')
    rows = []
    for sector in range(int(sector_count)):
        items = generate_forest_understory_items(
            sector, r0, r1,
            sector_count=sector_count,
            corridor_degrees=corridor_degrees,
            vanta_radius=vanta_radius,
            landing_radius=landing_radius,
            anchor_angle_deg=anchor_angle_deg,
        )
        for item in items:
            counts[item.kind] = counts.get(item.kind, 0) + 1
            margin = item.safe_patch_radius - (item.local_distance + item.radius)
            containment_margin = min(containment_margin, margin)
        rows.append({'sector': sector, 'item_count': len(items)})
    return {
        'sector_count': int(sector_count),
        'counts': counts,
        'total': sum(counts.values()),
        'min_safe_patch_containment_margin': containment_margin,
        'all_contained': containment_margin >= -1e-6,
        'rows': rows,
    }

