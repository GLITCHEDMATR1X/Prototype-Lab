from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

SPHERE_RADIUS = 6.2
# Pass 282.47 widens the stable 3-D reality field without bringing back
# visible orbital rings.  The larger radial/vertical envelope gives each
# planet more negative space while keeping every current record well inside
# the Observatory targeting distance.
FIELD_LAYOUT_VERSION = "wider_282_47"
FIELD_BASE_RADIUS = 82.0
FIELD_RADIUS_SPAN = 46.0
FIELD_BASE_HEIGHT = 49.0
FIELD_HEIGHT_SPAN = 56.0
FIELD_BAND_RADIUS_STEP = 30.0
FIELD_BAND_HEIGHT_STEP = 15.0
FIELD_MIN_CENTER_SPACING = 28.0
SELF_SPIN_DEG = (4.5, -3.8, 3.2, -2.7, 2.4, -2.1)
GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))

# Compatibility aliases retained for any older developer tooling.  They no
# longer describe visible orbital rings; the live observatory is a 3D field.
SPHERES_PER_ORBIT = 12
FIRST_ORBIT_RADIUS = FIELD_BASE_RADIUS
ORBIT_RADIUS_STEP = FIELD_BAND_RADIUS_STEP
FIRST_ORBIT_HEIGHT = FIELD_BASE_HEIGHT
ORBIT_HEIGHT_STEP = FIELD_BAND_HEIGHT_STEP
ORBIT_SPEED_DEG = ()


@dataclass(frozen=True)
class ObservatorySlot:
    index: int
    band_index: int
    phase: float
    radius: float
    height: float
    x: float
    y: float
    z: float

    @property
    def orbit_index(self) -> int:
        """Legacy developer-tool alias; there are no visible orbit rings."""
        return self.band_index


def _seed(value: str) -> int:
    digest = hashlib.sha256(str(value or "dimension").encode("utf-8", "replace")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _fraction(bits: int, shift: int) -> float:
    return float((bits >> shift) & 0xFFFF) / 65535.0


def build_observatory_slots(keys_or_count) -> list[ObservatorySlot]:
    """Return a sparse, stable 3D field with no shared orbital plane.

    String keys keep a reality near the same authored sky position across
    launches.  New links are resolved against existing positions with a bounded
    deterministic search so planets do not overlap.  An integer is accepted for
    older QA tools and generates synthetic stable keys.
    """
    if isinstance(keys_or_count, int):
        keys = [f"dimension-{idx}" for idx in range(max(0, int(keys_or_count)))]
    else:
        keys = [str(value or f"dimension-{idx}") for idx, value in enumerate(list(keys_or_count or []))]

    slots: list[ObservatorySlot] = []
    placed: list[tuple[float, float, float]] = []
    minimum_sq = FIELD_MIN_CENTER_SPACING * FIELD_MIN_CENTER_SPACING

    for idx, key in enumerate(keys):
        bits = _seed(key)
        band = idx // 10
        base_phase = _fraction(bits, 0) * math.tau
        radius_jitter = _fraction(bits, 16)
        height_jitter = _fraction(bits, 32)
        chosen = None

        for attempt in range(18):
            phase = (base_phase + attempt * GOLDEN_ANGLE + band * 0.29) % math.tau
            radius = (
                FIELD_BASE_RADIUS
                + radius_jitter * FIELD_RADIUS_SPAN
                + band * FIELD_BAND_RADIUS_STEP
                + (attempt // 6) * 11.0
            )
            height = (
                FIELD_BASE_HEIGHT
                + height_jitter * FIELD_HEIGHT_SPAN
                + band * FIELD_BAND_HEIGHT_STEP
                + ((attempt % 3) - 1) * 7.0
            )
            x = math.cos(phase) * radius
            y = math.sin(phase) * radius
            z = height
            if all((x-px)**2 + (y-py)**2 + (z-pz)**2 >= minimum_sq for px, py, pz in placed):
                chosen = (phase, radius, height, x, y, z)
                break

        if chosen is None:
            # Deterministic far-band fallback for unusually dense archives.
            phase = (base_phase + len(slots) * GOLDEN_ANGLE) % math.tau
            radius = FIELD_BASE_RADIUS + FIELD_RADIUS_SPAN + (band + 1) * FIELD_BAND_RADIUS_STEP + idx * 2.5
            height = FIELD_BASE_HEIGHT + FIELD_HEIGHT_SPAN * 0.55 + band * FIELD_BAND_HEIGHT_STEP + (idx % 5) * 8.0
            chosen = (phase, radius, height, math.cos(phase) * radius, math.sin(phase) * radius, height)

        phase, radius, height, x, y, z = chosen
        placed.append((x, y, z))
        slots.append(ObservatorySlot(idx, band, phase, radius, height, x, y, z))
    return slots


def orbit_count_for(count: int) -> int:
    """Legacy QA helper: returns the number of sparse field bands."""
    count = max(0, int(count))
    return 0 if count == 0 else int(math.ceil(count / 10.0))


def minimum_same_ring_center_spacing(count: int) -> float:
    """Legacy-named helper now reports minimum 3D field center spacing."""
    slots = build_observatory_slots(count)
    minimum = float("inf")
    for i, left in enumerate(slots):
        for right in slots[i + 1:]:
            distance = math.sqrt((left.x-right.x)**2 + (left.y-right.y)**2 + (left.z-right.z)**2)
            minimum = min(minimum, distance)
    return 0.0 if minimum == float("inf") else minimum
