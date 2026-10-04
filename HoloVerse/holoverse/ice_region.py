"""Deterministic Ice terrain and macro-shape data for HoloVerse Pass 282.37.

This module gives the Ice ring broad glacial relief and large readable frozen
silhouettes while keeping Frost Circuit's central race band clear.  world.py
remains the single terrain/collision and Panda3D rendering authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from typing import Sequence

from holoverse.frost_track import FROST_TRACK_HALF_WIDTH, FROST_TRACK_WORLD_CLEARANCE, nearest_centerline_distance

ICE_VISUAL_SEED = 28237
ICE_MACRO_STRUCTURES_PER_SECTOR = 8
ICE_STRUCTURE_CORRIDOR_HALF_WIDTH = 0.076
ICE_STRUCTURE_MIRROR_CLEARANCE = 92.0
ICE_STRUCTURE_LANDING_CLEARANCE = 82.0
ICE_STRUCTURE_SEAM_MARGIN_T = 0.075
ICE_TRACK_CLEARANCE = FROST_TRACK_WORLD_CLEARANCE

# Broad frozen relief waves: heading, wavelength, amplitude, phase.
ICE_GLACIAL_WAVES = (
    (0.16, 226.0, 0.86, 0.35),
    (0.78, 318.0, 0.54, 1.70),
    (-0.46, 462.0, 0.31, 2.55),
)


def _smoothstep01(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return t * t * (3.0 - 2.0 * t)


def _angle_delta(a: float, b: float) -> float:
    return abs((float(a) - float(b) + math.pi) % math.tau - math.pi)


def _xy(radius: float, angle: float) -> tuple[float, float]:
    return math.cos(angle) * radius, math.sin(angle) * radius


def ice_glacial_relief_at(x: float, y: float, r0: float, r1: float, track_radius: float) -> float:
    """Return normalized broad glacial relief for the compact Ice ring.

    The middle Frost Circuit band is deliberately calmer so the track remains
    readable and the hovercraft does not inherit severe accidental terrain
    jumps. Shared ring seam/corridor easing remains owned by world.py.
    """
    x = float(x); y = float(y)
    radius = math.hypot(x, y)
    total = 0.0
    weight = 0.0
    for heading, wavelength, amp, phase in ICE_GLACIAL_WAVES:
        c = math.cos(heading); s = math.sin(heading)
        along = x * c + y * s
        across = -x * s + y * c
        warp = math.sin(across / 620.0 * math.tau + phase * 0.4) * 0.42
        wave = math.sin(along / wavelength * math.tau + phase + warp)
        # Fold the waveform into long glacier ridges rather than smooth dunes.
        ridge = (1.0 - abs(wave)) ** 1.65
        total += ridge * amp
        weight += amp
    relief = total / max(1e-6, weight)
    broad = 0.5 + 0.5 * math.sin(radius * 0.0072 + math.atan2(y, x) * 2.2)
    raw = 0.14 + relief * 1.46 + broad * 0.18

    # Calmer Frost Circuit ribbon; the same shared centerline also owns macro
    # structure clearance so rendering and race gameplay cannot drift apart.
    track_distance = nearest_centerline_distance(x, y)
    track_mix = _smoothstep01((track_distance - FROST_TRACK_HALF_WIDTH * 0.70) / 92.0)
    calm = 0.18 + relief * 0.16
    return calm * (1.0 - track_mix) + raw * track_mix


@dataclass(frozen=True)
class IceMacroStructure:
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


def generate_ice_macro_structures(
    sector_idx: int,
    r0: float,
    r1: float,
    *,
    track_radius: float,
    sector_count: int = 48,
    corridor_degrees: Sequence[float] = (-90.0, 0.0, 90.0, 180.0),
    mirror_radius: float = 3484.0,
    landing_radius: float = 3428.0,
    anchor_angle_deg: float = -90.0,
) -> list[IceMacroStructure]:
    """Return stable large frozen structures for one Ice sector."""
    sector_idx = int(sector_idx) % int(sector_count)
    a0 = math.tau * sector_idx / float(sector_count)
    a1 = math.tau * (sector_idx + 1) / float(sector_count)
    span = max(1.0, float(r1) - float(r0))
    anchor = math.radians(float(anchor_angle_deg))
    mirror_xy = _xy(float(mirror_radius), anchor)
    landing_xy = _xy(float(landing_radius), anchor)
    corridor_angles = [math.radians(float(v)) % math.tau for v in corridor_degrees]
    rng = random.Random(ICE_VISUAL_SEED + sector_idx * 49979687)

    kinds = [
        "glacial_ridge", "glacial_ridge",
        "crystal_spire", "crystal_spire",
        "ice_shelf", "ice_shelf",
        "pressure_ridge",
        "crevasse_fin",
    ]
    rng.shuffle(kinds)

    items: list[IceMacroStructure] = []
    attempts = 0
    cursor = 0
    seam = max(0.03, min(0.18, float(ICE_STRUCTURE_SEAM_MARGIN_T)))
    while cursor < len(kinds) and attempts < 520:
        attempts += 1
        kind = kinds[cursor]
        radial_t = rng.uniform(seam, 1.0 - seam)
        radius = float(r0) + span * radial_t
        angle = rng.uniform(a0 + 0.014, a1 - 0.014)
        if min((_angle_delta(angle, ca) for ca in corridor_angles), default=math.pi) < ICE_STRUCTURE_CORRIDOR_HALF_WIDTH:
            continue
        x, y = _xy(radius, angle)

        if kind == "glacial_ridge":
            footprint = rng.uniform(18.0, 28.0); height = rng.uniform(14.0, 25.0); variant = rng.randrange(4)
        elif kind == "crystal_spire":
            footprint = rng.uniform(8.0, 13.0); height = rng.uniform(26.0, 48.0); variant = rng.randrange(5)
        elif kind == "ice_shelf":
            footprint = rng.uniform(17.0, 27.0); height = rng.uniform(9.0, 17.0); variant = rng.randrange(4)
        elif kind == "pressure_ridge":
            footprint = rng.uniform(17.0, 25.0); height = rng.uniform(13.0, 24.0); variant = rng.randrange(4)
        else:
            footprint = rng.uniform(10.0, 17.0); height = rng.uniform(15.0, 29.0); variant = rng.randrange(4)

        # Clearance is edge-to-centerline, not merely center-to-center.  This
        # keeps the full macro footprint outside the protected race envelope.
        if nearest_centerline_distance(x, y) - footprint < ICE_TRACK_CLEARANCE:
            continue

        if math.hypot(x - mirror_xy[0], y - mirror_xy[1]) - footprint < ICE_STRUCTURE_MIRROR_CLEARANCE:
            continue
        if math.hypot(x - landing_xy[0], y - landing_xy[1]) - footprint < ICE_STRUCTURE_LANDING_CLEARANCE:
            continue

        items.append(IceMacroStructure(
            sector=sector_idx,
            index=cursor,
            kind=kind,
            x=float(x), y=float(y), radius=float(footprint), height=float(height),
            heading=float(rng.uniform(0.0, math.tau)), variant=int(variant),
        ))
        cursor += 1
    return items
