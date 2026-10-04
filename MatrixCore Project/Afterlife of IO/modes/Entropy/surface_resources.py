"""Deterministic surface recovery and planet-safety rules for Entropy Pass 20."""
from __future__ import annotations

import math
from typing import Dict, Iterable, Tuple

RESOURCE_KEYS = ("salvage", "fuel_cells")


def planet_is_landable(planet) -> bool:
    """Every intact generated planet is a valid surface destination."""
    return planet is not None and not bool(getattr(planet, "destroyed", False))


def planet_exclusion_radius(planet) -> float:
    """Return the safe atmosphere boundary used for landing or deflection."""
    if planet is None:
        return 0.0
    return max(5200.0, float(getattr(planet, "radius", 0.0)) * 82.0)


def resolve_planet_exclusion(
    position: Iterable[float],
    velocity: Iterable[float],
    planet_position: Iterable[float],
    planet,
    *,
    force_blocked: bool = False,
) -> Tuple[tuple, tuple, bool]:
    """Push a ship out of a world that cannot currently accept planetfall.

    Intact worlds normally transition into the surface scene at this same
    boundary. Destroyed worlds and temporarily blocked entries instead act as
    soft navigation exclusions: position is corrected to the atmosphere edge
    and only the inward velocity component is removed.
    """
    if planet is None or (planet_is_landable(planet) and not force_blocked):
        return tuple(position), tuple(velocity), False

    pos = tuple(float(v) for v in position)
    vel = tuple(float(v) for v in velocity)
    center = tuple(float(v) for v in planet_position)
    delta = (pos[0] - center[0], pos[1] - center[1], pos[2] - center[2])
    distance = math.sqrt(delta[0] ** 2 + delta[1] ** 2 + delta[2] ** 2)
    boundary = planet_exclusion_radius(planet) * 1.035
    if distance >= boundary:
        return pos, vel, False

    if distance <= 1e-6:
        speed = math.sqrt(vel[0] ** 2 + vel[1] ** 2 + vel[2] ** 2)
        if speed > 1e-6:
            normal = (-vel[0] / speed, -vel[1] / speed, -vel[2] / speed)
        else:
            normal = (0.0, 0.0, -1.0)
    else:
        normal = (delta[0] / distance, delta[1] / distance, delta[2] / distance)

    corrected_pos = (
        center[0] + normal[0] * boundary,
        center[1] + normal[1] * boundary,
        center[2] + normal[2] * boundary,
    )
    inward = vel[0] * normal[0] + vel[1] * normal[1] + vel[2] * normal[2]
    if inward < 0.0:
        corrected_vel = (
            (vel[0] - normal[0] * inward) * 0.58,
            (vel[1] - normal[1] * inward) * 0.58,
            (vel[2] - normal[2] * inward) * 0.58,
        )
    else:
        corrected_vel = vel
    return corrected_pos, corrected_vel, True


def harvest_id(category: str, item_seed: int) -> str:
    prefix = {"structure": "s", "prop": "p", "tree": "t", "plant": "g"}.get(str(category), "o")
    return f"{prefix}:{int(item_seed)}"


def harvest_yield(surface_seed: int, item_seed: int, category: str, rig_level: int = 0) -> Dict[str, int]:
    """Return a stable conversion into the existing cargo resources."""
    category = str(category)
    rig_level = max(0, min(3, int(rig_level)))
    mix = (int(surface_seed) * 1103515245 + int(item_seed) * 12345 + len(category) * 7919) & 0xFFFFFFFF
    if category == "structure":
        salvage = 3 + (mix % 3) + rig_level
        fuel = 1 if ((mix >> 5) % 4 == 0 or rig_level >= 3) else 0
    elif category == "prop":
        salvage = 1 + (1 if rig_level >= 2 and mix % 3 == 0 else 0)
        fuel = 1 if (mix % 5 == 0) else 0
    elif category == "tree":
        salvage = 1 if mix % 4 == 0 else 0
        fuel = 1
    else:  # plants and minor surface objects
        salvage = 1 if mix % 7 == 0 else 0
        fuel = 1 if mix % 3 == 0 else 0
        if not salvage and not fuel:
            salvage = 1
    return {"salvage": int(salvage), "fuel_cells": int(fuel)}


def normalize_harvest_map(value) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    cleaned = {}
    for key, ids in value.items():
        if not isinstance(ids, (list, tuple, set)):
            continue
        cleaned[str(key)] = sorted({str(v) for v in ids if str(v)})
    return cleaned
