"""Ship resources and upgrades for Entropy Pass 17.

The module is deliberately independent from rendering code so progression can
be validated without opening a window and can be shared by space, surface, and
ship-interior modes.
"""
from __future__ import annotations

from typing import Dict, Tuple

UPGRADE_ORDER = ("warp", "scanner", "hull", "surface")
MAX_UPGRADE_LEVEL = 3

UPGRADE_LABELS = {
    "warp": "WARP DRIVE",
    "scanner": "SIGNAL SCANNER",
    "hull": "HULL / SHIELD",
    "surface": "SURFACE RIG",
}

UPGRADE_COSTS = {
    "warp": (0, 5, 8, 12),
    "scanner": (0, 4, 7, 10),
    "hull": (0, 5, 8, 12),
    "surface": (0, 4, 7, 10),
}


def ensure_progression(ship) -> None:
    """Create/migrate the compact progression state on an existing Ship."""
    if ship is None:
        return
    if not isinstance(getattr(ship, "cargo", None), dict):
        ship.cargo = {}
    ship.cargo["salvage"] = max(0, int(ship.cargo.get("salvage", 0)))
    ship.cargo["fuel_cells"] = max(0, int(ship.cargo.get("fuel_cells", 0)))
    # Pass 18.1: relic cores are recovered directly from marked surface ruins.
    # One core can fabricate any one existing upgrade level.
    ship.cargo["relic_cores"] = max(0, int(ship.cargo.get("relic_cores", 0)))

    levels = getattr(ship, "upgrade_levels", None)
    if not isinstance(levels, dict):
        levels = {}
    ship.upgrade_levels = {
        track: max(0, min(MAX_UPGRADE_LEVEL, int(levels.get(track, 0))))
        for track in UPGRADE_ORDER
    }
    apply_progression_effects(ship, preserve_hull=True)


def level(ship, track: str) -> int:
    if ship is None:
        return 0
    ensure_progression(ship)
    return int(ship.upgrade_levels.get(track, 0))


def resource_amount(ship, resource: str) -> int:
    if ship is None:
        return 0
    ensure_progression(ship)
    return max(0, int(ship.cargo.get(resource, 0)))


def add_resource(ship, resource: str, amount: int) -> int:
    ensure_progression(ship)
    amount = max(0, int(amount))
    ship.cargo[resource] = resource_amount(ship, resource) + amount
    ship.state_dirty = True
    return int(ship.cargo[resource])


def next_upgrade_cost(ship, track: str) -> int | None:
    current = level(ship, track)
    if current >= MAX_UPGRADE_LEVEL:
        return None
    return int(UPGRADE_COSTS[track][current + 1])


def apply_progression_effects(ship, preserve_hull: bool = True) -> None:
    levels = getattr(ship, "upgrade_levels", {})
    warp_level = max(0, min(MAX_UPGRADE_LEVEL, int(levels.get("warp", 0))))
    hull_level = max(0, min(MAX_UPGRADE_LEVEL, int(levels.get("hull", 0))))

    old_max = max(1, int(getattr(ship, "hull_hp_max", 100)))
    old_hp = max(0, int(getattr(ship, "hull_hp", old_max)))
    new_max = 100 + hull_level * 25
    ship.hull_hp_max = new_max
    if preserve_hull:
        ship.hull_hp = min(new_max, old_hp)
    else:
        ship.hull_hp = min(new_max, old_hp + max(0, new_max - old_max))

    ship.fuel_max = 100 + warp_level * 20
    ship.fuel = min(int(getattr(ship, "fuel", 60)), ship.fuel_max)
    ship.fuel_quality = min(0.92, 0.50 + warp_level * 0.12)
    ship.shield_recharge_rate = 0.70 + hull_level * 0.24


def purchase_upgrade(ship, track: str) -> Tuple[bool, str]:
    if track not in UPGRADE_ORDER:
        return False, "UNKNOWN UPGRADE TRACK"
    ensure_progression(ship)
    current = level(ship, track)
    if current >= MAX_UPGRADE_LEVEL:
        return False, f"{UPGRADE_LABELS[track]} ALREADY MAXIMUM"
    cost = next_upgrade_cost(ship, track)
    relic_cores = resource_amount(ship, "relic_cores")
    salvage = resource_amount(ship, "salvage")
    if cost is None:
        return False, f"{UPGRADE_LABELS[track]} ALREADY MAXIMUM"
    if relic_cores > 0:
        ship.cargo["relic_cores"] = relic_cores - 1
        payment = "1 LEGACY CORE"
    elif salvage >= cost:
        ship.cargo["salvage"] = salvage - cost
        payment = f"{cost} SALVAGE"
    else:
        return False, (f"NEED {cost} SALVAGE  /  SALVAGE {salvage}" if relic_cores <= 0 else f"NEED 1 LEGACY CORE OR {cost} SALVAGE  /  LEGACY CORES {relic_cores}  SALVAGE {salvage}")

    ship.upgrade_levels[track] = current + 1
    apply_progression_effects(ship, preserve_hull=(track != "hull"))
    # Hull installation preserves existing damage while filling the newly
    # installed capacity once through apply_progression_effects().
    ship.state_dirty = True
    return True, f"{UPGRADE_LABELS[track]} LEVEL {current + 1} INSTALLED  /  USED {payment}"


def process_fuel_cells(ship) -> Tuple[bool, str]:
    ensure_progression(ship)
    cells = resource_amount(ship, "fuel_cells")
    capacity = max(0, int(ship.fuel_max) - int(ship.fuel))
    if cells <= 0:
        return False, "NO FUEL CELLS IN CARGO"
    if capacity <= 0:
        return False, "FUEL TANK ALREADY FULL"

    # One recovered cell is a compact 12-unit refined charge.
    cells_needed = max(1, (capacity + 11) // 12)
    used = min(cells, cells_needed)
    transferred = min(capacity, used * 12)
    ship.cargo["fuel_cells"] = cells - used
    ship.fuel = min(ship.fuel_max, int(ship.fuel) + transferred)
    ship.state_dirty = True
    return True, f"TRANSFERRED {transferred} FUEL  /  TANK {ship.fuel}/{ship.fuel_max}"


def repair_hull(ship) -> Tuple[bool, str]:
    ensure_progression(ship)
    missing = max(0, int(ship.hull_hp_max) - int(ship.hull_hp))
    if missing <= 0:
        return False, "HULL INTEGRITY ALREADY FULL"
    salvage = resource_amount(ship, "salvage")
    if salvage < 2:
        return False, "REPAIR REQUIRES 2 SALVAGE"
    repaired = min(25, missing)
    ship.cargo["salvage"] = salvage - 2
    ship.hull_hp = min(ship.hull_hp_max, int(ship.hull_hp) + repaired)
    ship.state_dirty = True
    return True, f"REPAIRED {repaired} HULL  /  {ship.hull_hp}/{ship.hull_hp_max}"


def warp_cost_multiplier(ship) -> float:
    return (1.00, 0.86, 0.74, 0.62)[level(ship, "warp")]




def warp_quote(ship, base_cost: int = 18, extra_cost: int = 14) -> Tuple[int, int]:
    """Return the best currently affordable jump count and its fuel cost.

    A zero jump count means the ship cannot afford even the first jump; the
    returned cost is still the minimum fuel required so the HUD can explain
    the decision before the player commits.
    """
    ensure_progression(ship)
    fuel = max(0, int(getattr(ship, "fuel", 0)))
    quality = max(0.0, min(1.0, float(getattr(ship, "fuel_quality", 0.50))))
    max_jumps = 1 + int(quality * 2.4)
    efficiency = (1.0 - 0.22 * quality) * warp_cost_multiplier(ship)
    costs = [max(1, int((int(base_cost) + (j - 1) * int(extra_cost)) * efficiency)) for j in range(1, max_jumps + 1)]
    affordable = [j for j, cost in enumerate(costs, start=1) if fuel >= cost]
    if not affordable:
        return 0, costs[0]
    jumps = affordable[-1]
    return jumps, costs[jumps - 1]

def scanner_level(ship) -> int:
    return level(ship, "scanner")


def surface_speed_multiplier(ship) -> float:
    return (1.00, 1.10, 1.22, 1.35)[level(ship, "surface")]


def upgrade_effect(track: str, lvl: int) -> str:
    lvl = max(0, min(MAX_UPGRADE_LEVEL, int(lvl)))
    if track == "warp":
        return ("BASE RANGE", "+20 FUEL / 14% EFF", "+40 FUEL / 26% EFF", "+60 FUEL / 38% EFF")[lvl]
    if track == "scanner":
        return ("DATA SIGNAL ONLY", "REVEALS FUEL", "REVEALS SALVAGE", "FULL SIGNAL DATA")[lvl]
    if track == "hull":
        return ("100 HULL", "125 HULL", "150 HULL", "175 HULL")[lvl]
    if track == "surface":
        return ("STANDARD RIG", "+10% WALK / 12% HAZARD SHIELD", "+22% WALK / 24% HAZARD SHIELD", "+35% WALK / 38% HAZARD SHIELD")[lvl]
    return ""


def snapshot(ship) -> Dict[str, object]:
    ensure_progression(ship)
    return {
        "salvage": resource_amount(ship, "salvage"),
        "fuel_cells": resource_amount(ship, "fuel_cells"),
        "relic_cores": resource_amount(ship, "relic_cores"),
        "fuel": int(ship.fuel),
        "fuel_max": int(ship.fuel_max),
        "hull": int(ship.hull_hp),
        "hull_max": int(ship.hull_hp_max),
        "upgrade_levels": dict(ship.upgrade_levels),
    }
