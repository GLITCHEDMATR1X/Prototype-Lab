from __future__ import annotations

import json
import os
from pathlib import Path

from phase_progression import WarPhase
from ground_operation import GroundOperationStage

SCHEMA_VERSION = 1


def _clamp_int(value, low: int, high: int) -> int:
    try:
        value = int(value)
    except Exception:
        value = low
    return max(low, min(high, value))


def load_campaign_save(path: Path) -> dict | None:
    """Load and minimally validate a campaign save. Invalid data never blocks boot."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return None
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA_VERSION:
        return None
    if str(raw.get("phase", "")) not in {p.value for p in WarPhase}:
        return None
    return raw


def write_campaign_save(path: Path, phase_progression, ground_operation, air_operation, ocean_operation) -> None:
    """Write campaign progress with same-directory atomic replacement."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA_VERSION,
        "phase": phase_progression.active_phase.value,
        "campaign_complete": bool(phase_progression.campaign_complete),
        "ground": {
            "street_destroyed": int(ground_operation.street_destroyed),
            "giants_destroyed": int(ground_operation.giants_destroyed),
        },
        "air": {
            "fighter_kills": int(air_operation.fighter_kills),
            "ufo_kills": int(air_operation.ufo_kills),
        },
        "ocean": {
            "warship_kills": int(ocean_operation.warship_kills),
            "helicopter_kills": int(ocean_operation.helicopter_kills),
        },
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def clear_campaign_save(path: Path) -> None:
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass


def restore_campaign_save(raw: dict | None, phase_progression, ground_operation, air_operation, ocean_operation, combat_outcomes) -> bool:
    """Restore safe campaign progress and enforce phase/progress invariants."""
    if not raw:
        return False

    phase = WarPhase(str(raw.get("phase")))
    campaign_complete = bool(raw.get("campaign_complete", False))
    if campaign_complete:
        phase = WarPhase.OCEAN

    ground = raw.get("ground") if isinstance(raw.get("ground"), dict) else {}
    air = raw.get("air") if isinstance(raw.get("air"), dict) else {}
    ocean = raw.get("ocean") if isinstance(raw.get("ocean"), dict) else {}

    ground_operation.street_destroyed = _clamp_int(ground.get("street_destroyed", 0), 0, ground_operation.STREET_GOAL)
    ground_operation.giants_destroyed = _clamp_int(ground.get("giants_destroyed", 0), 0, ground_operation.GIANT_GOAL)
    air_operation.fighter_kills = _clamp_int(air.get("fighter_kills", 0), 0, air_operation.FIGHTER_GOAL)
    air_operation.ufo_kills = _clamp_int(air.get("ufo_kills", 0), 0, air_operation.UFO_GOAL)
    ocean_operation.warship_kills = _clamp_int(ocean.get("warship_kills", 0), 0, ocean_operation.WARSHIP_GOAL)
    ocean_operation.helicopter_kills = _clamp_int(ocean.get("helicopter_kills", 0), 0, ocean_operation.HELICOPTER_GOAL)

    # A later campaign phase is proof that earlier phases were already completed.
    if phase in {WarPhase.AIR, WarPhase.OCEAN}:
        ground_operation.street_destroyed = ground_operation.STREET_GOAL
        ground_operation.giants_destroyed = ground_operation.GIANT_GOAL
    if phase is WarPhase.OCEAN:
        air_operation.fighter_kills = air_operation.FIGHTER_GOAL
        air_operation.ufo_kills = air_operation.UFO_GOAL
    if campaign_complete:
        ocean_operation.warship_kills = ocean_operation.WARSHIP_GOAL
        ocean_operation.helicopter_kills = ocean_operation.HELICOPTER_GOAL

    if ground_operation.street_destroyed >= ground_operation.STREET_GOAL:
        ground_operation.stage = GroundOperationStage.GIANT_HUNT
    else:
        ground_operation.stage = GroundOperationStage.STREET_ASSAULT
    if ground_operation.giants_destroyed >= ground_operation.GIANT_GOAL and ground_operation.street_destroyed >= ground_operation.STREET_GOAL:
        ground_operation.stage = GroundOperationStage.COMPLETE
        ground_operation.completed_operations = 1

    air_operation.complete = (
        air_operation.fighter_kills >= air_operation.FIGHTER_GOAL
        and air_operation.ufo_kills >= air_operation.UFO_GOAL
    )
    ocean_operation.complete = (
        ocean_operation.warship_kills >= ocean_operation.WARSHIP_GOAL
        and ocean_operation.helicopter_kills >= ocean_operation.HELICOPTER_GOAL
    )

    phase_progression.active_phase = phase
    phase_progression.ground_transition_count = 1 if phase in {WarPhase.AIR, WarPhase.OCEAN} else 0
    phase_progression.air_transition_count = 1 if phase is WarPhase.OCEAN else 0
    phase_progression.campaign_complete = campaign_complete
    phase_progression.campaign_completion_count = 1 if campaign_complete else 0

    if ground_operation.complete:
        combat_outcomes.mark_complete("GROUND")
    else:
        combat_outcomes.begin_attempt("GROUND")
    if air_operation.complete:
        combat_outcomes.mark_complete("AIR")
    else:
        combat_outcomes.begin_attempt("AIR")
    if ocean_operation.complete:
        combat_outcomes.mark_complete("OCEAN")
    else:
        combat_outcomes.begin_attempt("OCEAN")
    return True
