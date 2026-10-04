from __future__ import annotations


class AirOperation:
    """Deterministic Air-phase objective authority, independent of rendering.

    Phase structure is inspired by real-world air-superiority doctrine: first
    reduce hostile air interference, then neutralize the remaining higher-risk
    contacts. Exact kill counts are gameplay tuning, not real-world claims.
    """

    FIGHTER_GOAL = 6
    UFO_GOAL = 2

    def __init__(self):
        self.fighter_kills = 0
        self.ufo_kills = 0
        self.complete = False

    @property
    def stage(self) -> str:
        if self.complete:
            return "SECURED"
        if self.fighter_kills < self.FIGHTER_GOAL:
            return "FIGHTER_SWEEP"
        return "UFO_INTERCEPT"

    def record_destroyed(self, target_kind: str) -> bool:
        """Record a player-attributed Air kill. Returns True on first completion."""
        if self.complete:
            return False
        kind = str(target_kind).upper()
        if kind == "FIGHTER":
            self.fighter_kills = min(self.FIGHTER_GOAL, self.fighter_kills + 1)
        elif kind == "UFO":
            self.ufo_kills = min(self.UFO_GOAL, self.ufo_kills + 1)
        else:
            return False

        was_complete = self.complete
        self.complete = (
            self.fighter_kills >= self.FIGHTER_GOAL
            and self.ufo_kills >= self.UFO_GOAL
        )
        return (not was_complete) and self.complete

    def objective_text(self) -> str:
        if self.complete:
            return "AIR SECURED // MARITIME PHASE RELEASED"
        if self.fighter_kills < self.FIGHTER_GOAL:
            return f"ESTABLISH AIR CONTROL // HOSTILE FIGHTERS {self.fighter_kills}/{self.FIGHTER_GOAL}"
        return f"INTERCEPT UFO CONTACTS // UFOs {self.ufo_kills}/{self.UFO_GOAL}"

    def diagnostic_text(self) -> str:
        return (
            f"AIR_OP // {self.stage} // FIGHTERS {self.fighter_kills}/{self.FIGHTER_GOAL} "
            f"// UFO {self.ufo_kills}/{self.UFO_GOAL}"
        )
