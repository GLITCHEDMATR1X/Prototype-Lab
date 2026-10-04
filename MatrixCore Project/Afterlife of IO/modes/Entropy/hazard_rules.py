"""Surface hazard gameplay rules for Entropy Pass 26.

The four hazard families were already assigned to every terrain in Pass 25.
This module gives each family one compact, readable gameplay behavior without
adding new currencies, equipment slots, or permanent failure states.

All functions are renderer-independent so the rules can be regression-tested
without pygame/Panda3D.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if value < lo else hi if value > hi else value


FAMILIES = ("HEAT", "COLD", "BIOLOGICAL", "ANOMALOUS")

# Surface Rig doubles as environmental protection. This strengthens an existing
# upgrade instead of creating a fifth progression track.
RIG_HAZARD_RESISTANCE = (0.00, 0.12, 0.24, 0.38)

HAZARD_SHORT_RULE = {
    "HEAT": "THERMAL LOAD RISES AWAY FROM SHIP",
    "COLD": "CRYO DRAG INCREASES WITH DISTANCE",
    "BIOLOGICAL": "SPORE BLOOMS PERIODICALLY SLOW TRAVEL",
    "ANOMALOUS": "DISTANT DATA SIGNALS DRIFT",
    "UNKNOWN": "NO VERIFIED HAZARD PROFILE",
}

HAZARD_COLORS = {
    "HEAT": (255, 154, 92),
    "COLD": (142, 218, 255),
    "BIOLOGICAL": (150, 236, 146),
    "ANOMALOUS": (220, 154, 255),
    "UNKNOWN": (178, 190, 202),
}


@dataclass(frozen=True)
class HazardFrame:
    family: str
    severity: float
    move_multiplier: float
    signal_angle_offset: float
    signal_distance_multiplier: float
    label: str
    instruction: str
    pulse_active: bool = False


def _protected(severity: float, surface_rig_level: int) -> float:
    lvl = max(0, min(3, int(surface_rig_level)))
    return clamp(float(severity) * (1.0 - RIG_HAZARD_RESISTANCE[lvl]))


def evaluate_hazard(
    family: str,
    *,
    distance_from_ship: float,
    elapsed_seconds: float,
    seed: int = 0,
    surface_rig_level: int = 0,
    storm_intensity: float = 0.0,
    target_distance: float | None = None,
) -> HazardFrame:
    """Return this frame's compact surface-hazard behavior.

    Hazards intentionally remain non-lethal. Entropy's hard failure pressure is
    still the collapsing star/black-hole sequence; surface hazards shape route
    choice and urgency without introducing a second health-management game.
    """
    family = str(family or "UNKNOWN").upper()
    distance = max(0.0, float(distance_from_ship))
    elapsed = max(0.0, float(elapsed_seconds))
    storm = clamp(float(storm_intensity))
    tdist = None if target_distance is None else max(0.0, float(target_distance))

    severity = 0.0
    move = 1.0
    angle = 0.0
    distance_mul = 1.0
    pulse = False

    if family == "HEAT":
        # The landed ship is the thermal refuge. The penalty begins far enough
        # out that immediate planetfall never feels sticky.
        raw = clamp((distance - 24.0) / 82.0 + storm * 0.18)
        severity = _protected(raw, surface_rig_level)
        move = 1.0 - 0.20 * severity
        label = f"THERMAL LOAD {round(severity * 100):02d}%"
        instruction = "SHIP PROXIMITY COOLS THE RIG" if severity >= 0.28 else "THERMAL LOAD NOMINAL"

    elif family == "COLD":
        raw = clamp((distance - 18.0) / 96.0 + storm * 0.12)
        severity = _protected(raw, surface_rig_level)
        move = 1.0 - 0.26 * severity
        label = f"CRYO DRAG {round(severity * 100):02d}%"
        instruction = "DISTANCE REDUCES MOBILITY" if severity >= 0.22 else "MOBILITY NOMINAL"

    elif family == "BIOLOGICAL":
        # A deterministic bloom cycle avoids per-frame randomness and makes the
        # hazard learnable. About four seconds of every fourteen are active.
        phase = (elapsed + (int(seed) % 37) * 0.173) % 14.0
        if 7.0 <= phase <= 11.0:
            local = 1.0 - abs(phase - 9.0) / 2.0
            raw = 0.36 + 0.64 * clamp(local)
            pulse = True
        else:
            raw = 0.08
        severity = _protected(raw, surface_rig_level)
        move = 1.0 - (0.18 * severity if pulse else 0.0)
        label = f"SPORE BLOOM {round(severity * 100):02d}%" if pulse else "SPORE BLOOM DORMANT"
        instruction = "BLOOM SLOWS SURFACE TRAVEL" if pulse else "NEXT BLOOM CYCLING"

    elif family == "ANOMALOUS":
        # Close-range readings resolve cleanly. At long range the objective
        # chevron and displayed distance wander together, forcing the player to
        # close in rather than trusting a perfect GPS marker across the map.
        far = 0.0 if tdist is None else clamp((tdist - 20.0) / 90.0)
        severity = _protected(far, surface_rig_level)
        wave = math.sin(elapsed * 1.55 + (int(seed) % 997) * 0.013)
        angle = wave * 0.34 * severity
        distance_mul = 1.0 + math.sin(elapsed * 1.12 + (int(seed) % 613) * 0.021) * 0.26 * severity
        move = 1.0
        label = f"SIGNAL DRIFT {round(severity * 100):02d}%"
        instruction = "CLOSE RANGE RESOLVES THE ARCHIVE" if severity >= 0.12 else "SIGNAL LOCKED"

    else:
        label = "HAZARD UNKNOWN"
        instruction = HAZARD_SHORT_RULE["UNKNOWN"]

    return HazardFrame(
        family=family,
        severity=clamp(severity),
        move_multiplier=max(0.65, min(1.0, float(move))),
        signal_angle_offset=float(angle),
        signal_distance_multiplier=max(0.72, min(1.28, float(distance_mul))),
        label=label,
        instruction=instruction,
        pulse_active=bool(pulse),
    )
