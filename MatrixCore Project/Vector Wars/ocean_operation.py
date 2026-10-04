from __future__ import annotations


class OceanOperation:
    """Deterministic Ocean-phase mission authority, independent of rendering.

    The structure is reference-informed by naval sea-control concepts: remove a
    hostile surface group, then defeat the remaining maritime-air threat. Exact
    target counts are gameplay tuning, not real-world force ratios.
    """

    WARSHIP_GOAL = 4
    HELICOPTER_GOAL = 2

    def __init__(self):
        self.warship_kills = 0
        self.helicopter_kills = 0
        self.complete = False

    @property
    def stage(self) -> str:
        if self.complete:
            return "SEA_CONTROL"
        if self.warship_kills < self.WARSHIP_GOAL:
            return "SURFACE_ACTION_GROUP"
        return "MARITIME_AIR_DEFENSE"

    def record_destroyed(self, target_kind: str) -> bool:
        """Record a player-attributed Ocean kill. Returns True on first completion."""
        if self.complete:
            return False
        kind = str(target_kind).upper()
        if kind == "WARSHIP":
            self.warship_kills = min(self.WARSHIP_GOAL, self.warship_kills + 1)
        elif kind in {"HELICOPTER", "HELI"}:
            self.helicopter_kills = min(self.HELICOPTER_GOAL, self.helicopter_kills + 1)
        else:
            return False

        was_complete = self.complete
        self.complete = (
            self.warship_kills >= self.WARSHIP_GOAL
            and self.helicopter_kills >= self.HELICOPTER_GOAL
        )
        return (not was_complete) and self.complete

    def objective_text(self) -> str:
        if self.complete:
            return "SEA CONTROL ESTABLISHED // OPERATION COMPLETE"
        if self.warship_kills < self.WARSHIP_GOAL:
            return f"BREAK SURFACE ACTION GROUP // WARSHIPS {self.warship_kills}/{self.WARSHIP_GOAL}"
        return f"DEFEAT MARITIME AIR ATTACK // HELICOPTERS {self.helicopter_kills}/{self.HELICOPTER_GOAL}"

    def diagnostic_text(self) -> str:
        return (
            f"OCEAN_OP // {self.stage} // WARSHIPS {self.warship_kills}/{self.WARSHIP_GOAL} "
            f"// HELICOPTERS {self.helicopter_kills}/{self.HELICOPTER_GOAL}"
        )
