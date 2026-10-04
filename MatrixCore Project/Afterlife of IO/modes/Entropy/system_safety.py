"""System-local spawn and stellar-impact rules for Entropy Pass 21.

This module has no pygame dependency so collision and reset behavior can be
verified without creating a display or audio device.
"""
from __future__ import annotations

import math
from typing import Iterable, Tuple

SYSTEM_SPAWN_POSITION = (0.0, 0.0, 0.0)
SYSTEM_SPAWN_ORIENTATION = (1.0, 0.0, 0.0, 0.0)


def stellar_collision_radius(star_radius: float) -> float:
    """Return the solid stellar surface used by swept impact checks."""
    return max(1200.0, float(star_radius) * 1.08)


def _vec3(value: Iterable[float]) -> tuple[float, float, float]:
    vals = tuple(float(v) for v in value)
    if len(vals) != 3:
        raise ValueError("expected a 3D vector")
    return vals[0], vals[1], vals[2]


def star_impact_detected(
    previous_position: Iterable[float],
    current_position: Iterable[float],
    star_position: Iterable[float],
    star_radius: float,
) -> bool:
    """Return True when a movement segment touches the stellar surface.

    Using the complete movement segment prevents a fast ship from crossing the
    star between frames without ever ending a frame inside its radius.
    """
    start = _vec3(previous_position)
    end = _vec3(current_position)
    center = _vec3(star_position)
    radius = stellar_collision_radius(star_radius)

    sx, sy, sz = start[0] - center[0], start[1] - center[1], start[2] - center[2]
    ex, ey, ez = end[0] - center[0], end[1] - center[1], end[2] - center[2]
    if sx * sx + sy * sy + sz * sz <= radius * radius:
        return True
    if ex * ex + ey * ey + ez * ez <= radius * radius:
        return True

    dx, dy, dz = end[0] - start[0], end[1] - start[1], end[2] - start[2]
    seg_len_sq = dx * dx + dy * dy + dz * dz
    if seg_len_sq <= 1e-12:
        return False

    to_center = (center[0] - start[0], center[1] - start[1], center[2] - start[2])
    t = (to_center[0] * dx + to_center[1] * dy + to_center[2] * dz) / seg_len_sq
    t = max(0.0, min(1.0, t))
    closest = (start[0] + dx * t, start[1] + dy * t, start[2] + dz * t)
    distance_sq = (
        (closest[0] - center[0]) ** 2
        + (closest[1] - center[1]) ** 2
        + (closest[2] - center[2]) ** 2
    )
    return distance_sq <= radius * radius


def reset_ship_to_system_spawn(ship) -> Tuple[float, float, float]:
    """Restore the default flight transform without erasing run progression."""
    ship.pos = SYSTEM_SPAWN_POSITION
    ship.vel = (0.0, 0.0, 0.0)
    ship.yaw = 0.0
    ship.pitch = 0.0
    ship.roll = 0.0
    ship.yaw_rate = 0.0
    ship.pitch_rate = 0.0
    ship.roll_rate = 0.0
    if hasattr(ship, "set_orientation"):
        ship.set_orientation(SYSTEM_SPAWN_ORIENTATION)
    else:
        ship.orientation = SYSTEM_SPAWN_ORIENTATION
    ship.hyperspace = False
    ship.hyper_t = 0.0
    ship.hyper_cooldown = max(1.0, float(getattr(ship, "hyper_cooldown", 0.0)))
    ship.speed = 0.0
    ship.speed_norm = 0.0
    ship.boost_norm = 0.0
    ship.hyper_norm = 0.0
    ship.local_clearance = 0.0
    ship.heat = min(float(getattr(ship, "heat", 0.15)), 0.35)
    if hasattr(ship, "state_dirty"):
        ship.state_dirty = True
    return SYSTEM_SPAWN_POSITION
