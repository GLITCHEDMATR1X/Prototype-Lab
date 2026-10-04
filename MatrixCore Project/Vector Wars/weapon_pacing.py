"""Secondary-weapon cadence authority for Vector Wars.

The values are arcade-scale gameplay timing, not literal real-world reload times.
Reference intent:
- Aircraft cannon fire remains the fast continuous layer; the M61A1 is documented
  by the U.S. Air Force at up to 6,000 rounds/minute.
- Guided missiles/torpedoes are discrete secondary attacks. Navy material describes
  the MK 54 as a lightweight torpedo delivered from aircraft/surface platforms.
- Vector Wars deliberately uses torpedoes against surface warships; that target role
  is a gameplay abstraction, not a simulation claim.
"""
from __future__ import annotations

SECONDARY_COOLDOWN = {
    "AIR": 1.25,
    "GROUND": 1.60,
    "OCEAN": 2.40,
}


def secondary_cooldown(front: str) -> float:
    return float(SECONDARY_COOLDOWN.get(str(front).strip().upper(), SECONDARY_COOLDOWN["AIR"]))


def generic_missile_allowed(front: str) -> bool:
    """Ground/Air use the generic homing missile; Ocean owns torpedoes instead."""
    return str(front).strip().upper() != "OCEAN"


def validate_secondary_identity() -> list[str]:
    issues: list[str] = []
    if not (0.0 < SECONDARY_COOLDOWN["AIR"] <= SECONDARY_COOLDOWN["GROUND"] < SECONDARY_COOLDOWN["OCEAN"]):
        issues.append("secondary cadence must progress AIR <= GROUND < OCEAN")
    if generic_missile_allowed("OCEAN"):
        issues.append("ocean must not use generic homing missile authority")
    if not generic_missile_allowed("AIR") or not generic_missile_allowed("GROUND"):
        issues.append("air and ground must retain generic missile authority")
    return issues
