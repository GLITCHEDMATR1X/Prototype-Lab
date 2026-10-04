"""Relative movement/pacing authority for Vector Wars.

These are gameplay scales, not literal real-world unit conversions.  The goal is
phase identity: AIR should feel decisively faster than GROUND, while OCEAN keeps
substantial momentum without reaching fighter-like traversal speed.

Reference anchors used when choosing the relationships:
- USAF/National Museum F-16A: 1,345 mph maximum speed.
- US Navy DDG-51 destroyer: in excess of 30 knots.
- US Navy MH-60 Seahawk: 180 knots maximum airspeed.

Vector Wars compresses those differences heavily for playability.
"""
from __future__ import annotations

PLAYER_SPEED_SCALE = {
    "GROUND": 0.48,
    "AIR": 1.00,
    # Ocean planar handling has its own cruise authority below.  This scale still
    # prevents the generic Ship.update step from injecting fighter-like velocity.
    "OCEAN": 0.66,
}

OCEAN_CRUISE_BASE = 64.0
OCEAN_THROTTLE_GAIN = 42.0
OCEAN_BOOST_GAIN = 20.0
OCEAN_REVERSE_BRAKE = 150.0
OCEAN_MIN_REVERSE_SPEED = 12.0


def player_speed_scale(front: str) -> float:
    return float(PLAYER_SPEED_SCALE.get(str(front).strip().upper(), 1.0))


def ocean_cruise_target(*, throttle: float, boost: bool, current_forward_speed: float, dt: float) -> float:
    """Return arcade-scale speedboat target speed for the current input."""
    throttle = float(throttle)
    if throttle < 0.0:
        return max(OCEAN_MIN_REVERSE_SPEED, float(current_forward_speed) - OCEAN_REVERSE_BRAKE * max(0.0, float(dt)))
    return OCEAN_CRUISE_BASE + max(0.0, throttle) * OCEAN_THROTTLE_GAIN + (OCEAN_BOOST_GAIN if boost else 0.0)


def validate_phase_identity() -> list[str]:
    issues: list[str] = []
    if not (0.0 < PLAYER_SPEED_SCALE["GROUND"] < PLAYER_SPEED_SCALE["AIR"]):
        issues.append("ground player speed scale must remain below air")
    if not (0.0 < PLAYER_SPEED_SCALE["OCEAN"] < PLAYER_SPEED_SCALE["AIR"]):
        issues.append("ocean generic speed scale must remain below air")
    ocean_max = ocean_cruise_target(throttle=1.0, boost=True, current_forward_speed=0.0, dt=1/60)
    if ocean_max >= 142.0:  # slowest existing AIR player variant
        issues.append("ocean maximum cruise should remain below the slowest air variant")
    if ocean_max <= 64.0:
        issues.append("ocean boost/throttle must actually increase cruise speed")
    return issues
