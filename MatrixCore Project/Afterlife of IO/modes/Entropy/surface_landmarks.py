"""Deterministic, non-colliding surface landmark layouts for Entropy.

Pass 27 adds large visual anchors to the twelve existing surface families without
turning landmarks into another gameplay system.  They are presentation-only:
no collision, no resource reward, and no objective ownership.  Their job is to
make a surface easier to recognize and navigate under the existing collapse
clock.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable, Sequence


@dataclass(frozen=True)
class LandmarkProfile:
    kind: str
    title: str
    subtitle: str


@dataclass(frozen=True)
class LandmarkSpec:
    x: float
    y: float
    seed: int
    kind: str
    title: str
    subtitle: str
    scale: float
    primary: bool


LANDMARK_PROFILES = {
    "desert": LandmarkProfile("sun_ring", "SUN RING", "ERODED SOLAR ARRAY"),
    "ice": LandmarkProfile("cryo_needles", "CRYO NEEDLES", "FROZEN TRANSMISSION SPIRES"),
    "jungle": LandmarkProfile("root_cathedral", "ROOT CATHEDRAL", "OVERGROWN ARCHIVE FRAME"),
    "volcanic": LandmarkProfile("caldera_crown", "CALDERA CROWN", "THERMAL EXTRACTION RING"),
    "crystal": LandmarkProfile("prism_choir", "PRISM CHOIR", "FRACTURED SIGNAL LATTICE"),
    "oceanic": LandmarkProfile("flood_pylons", "FLOOD PYLONS", "DROWNED RELAY FIELD"),
    "fungal": LandmarkProfile("spore_crown", "SPORE CROWN", "BIOLOGICAL UPLINK GROWTH"),
    "rust": LandmarkProfile("foundry_ribs", "FOUNDRY RIBS", "COLLAPSED INDUSTRIAL SPAN"),
    "salt": LandmarkProfile("mirror_obelisk", "MIRROR OBELISK", "SALT-GLASS SURVEY MARKER"),
    "abyss": LandmarkProfile("void_lantern", "VOID LANTERN", "DORMANT DEEP-SIGNAL BEACON"),
    "storm": LandmarkProfile("storm_mast", "STORM MAST", "ATMOSPHERIC DISCHARGE TOWER"),
    "roseglass": LandmarkProfile("roseglass_fan", "ROSEGLASS FAN", "SHATTERED SPECTRAL ARRAY"),
}

LANDMARK_TERRAINS = tuple(LANDMARK_PROFILES)


def _clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def _xy(item) -> tuple[float, float]:
    if hasattr(item, "x") and hasattr(item, "y"):
        return float(item.x), float(item.y)
    if isinstance(item, Sequence) and len(item) >= 2:
        return float(item[0]), float(item[1])
    raise TypeError(f"unsupported landmark exclusion point: {item!r}")


def _clear_of(candidate: tuple[float, float], points: Iterable, radius: float) -> bool:
    x, y = candidate
    for item in points:
        px, py = _xy(item)
        if math.hypot(x - px, y - py) < radius:
            return False
    return True


def generate_landmarks(
    seed: int,
    terrain: str,
    ship_pos: tuple[float, float],
    structures: Iterable,
    *,
    world_size: float = 384.0,
    count: int = 3,
) -> tuple[LandmarkSpec, ...]:
    """Return deterministic visual anchors with generous gameplay clearances.

    The generated anchors are intentionally kept away from the landed ship and
    authored ruins.  They never affect collision; these distances merely keep
    the large visuals from obscuring important interaction points.
    """
    profile = LANDMARK_PROFILES.get(str(terrain))
    if profile is None or count <= 0:
        return ()

    sx, sy = float(ship_pos[0]), float(ship_pos[1])
    structure_points = tuple(structures)
    rng = random.Random(int(seed) ^ 0x1A4D4B)
    margin = 30.0
    anchors: list[LandmarkSpec] = []

    # The first anchor is intentionally closer/larger so most players encounter
    # at least one memorable silhouette during a normal 60-second surface run.
    distance_bands = ((48.0, 72.0), (78.0, 112.0), (104.0, 148.0), (64.0, 132.0))
    base_angle = rng.uniform(0.0, math.tau)

    attempts = 0
    max_attempts = 180
    while len(anchors) < count and attempts < max_attempts:
        idx = len(anchors)
        attempts += 1
        lo, hi = distance_bands[min(idx, len(distance_bands) - 1)]
        # Golden-angle separation plus jitter avoids obvious radial symmetry.
        angle = base_angle + idx * 2.399963229728653 + rng.uniform(-0.38, 0.38)
        distance = rng.uniform(lo, hi)
        x = _clamp(sx + math.cos(angle) * distance, margin, world_size - margin)
        y = _clamp(sy + math.sin(angle) * distance, margin, world_size - margin)
        candidate = (x, y)

        if math.hypot(x - sx, y - sy) < 38.0:
            continue
        if not _clear_of(candidate, structure_points, 24.0):
            continue
        if not _clear_of(candidate, anchors, 42.0):
            continue

        primary = idx == 0
        anchors.append(
            LandmarkSpec(
                x=x,
                y=y,
                seed=(int(seed) + 0x2710 + idx * 977) & 0x7FFFFFFF,
                kind=profile.kind,
                title=profile.title,
                subtitle=profile.subtitle,
                scale=(1.20 + rng.uniform(-0.05, 0.10)) if primary else (0.82 + rng.uniform(-0.07, 0.12)),
                primary=primary,
            )
        )

    # Defensive fallback.  It should almost never run, but a landmark pass must
    # never fail planet generation just because an unusually dense ruin layout
    # consumed all random candidates.
    fallback_angles = (0.35, 2.55, 4.65, 1.45, 3.55, 5.75)
    for angle in fallback_angles:
        if len(anchors) >= count:
            break
        distance = 70.0 + len(anchors) * 26.0
        x = _clamp(sx + math.cos(base_angle + angle) * distance, margin, world_size - margin)
        y = _clamp(sy + math.sin(base_angle + angle) * distance, margin, world_size - margin)
        candidate = (x, y)
        if not _clear_of(candidate, structure_points, 22.0) or not _clear_of(candidate, anchors, 36.0):
            continue
        idx = len(anchors)
        anchors.append(
            LandmarkSpec(
                x=x,
                y=y,
                seed=(int(seed) + 0x2710 + idx * 977) & 0x7FFFFFFF,
                kind=profile.kind,
                title=profile.title,
                subtitle=profile.subtitle,
                scale=1.18 if idx == 0 else 0.86,
                primary=idx == 0,
            )
        )

    return tuple(anchors)


def nearest_landmark(landmarks: Iterable[LandmarkSpec], x: float, y: float) -> tuple[LandmarkSpec | None, float]:
    best = None
    best_distance = 1e9
    for landmark in landmarks:
        distance = math.hypot(float(x) - landmark.x, float(y) - landmark.y)
        if distance < best_distance:
            best = landmark
            best_distance = distance
    return best, best_distance
