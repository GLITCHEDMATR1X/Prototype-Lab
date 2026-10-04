from enum import Enum


class GroundOperationStage(Enum):
    STREET_ASSAULT = "STREET_ASSAULT"
    GIANT_HUNT = "GIANT_HUNT"
    COMPLETE = "COMPLETE"


class GroundOperation:
    """Pure gameplay authority for the first Ground operation.

    Rendering and input do not live here. The operation consumes confirmed
    player-attributed destruction events from the existing combat simulation.
    """

    STREET_GOAL = 8
    GIANT_GOAL = 1

    def __init__(self):
        self.street_destroyed = 0
        self.giants_destroyed = 0
        self.stage = GroundOperationStage.STREET_ASSAULT
        self.completed_operations = 0

    @property
    def complete(self) -> bool:
        return self.stage is GroundOperationStage.COMPLETE

    def record_destroyed(self, target_kind: str) -> bool:
        """Record one player-attributed Ground kill.

        Returns True only when this call advances the operation stage.
        Relevant kills are remembered even if completed out of the intended
        order, so normal combat freedom is not punished.
        """
        if self.complete:
            return False

        kind = str(target_kind).upper()
        if kind == "STREET":
            self.street_destroyed = min(self.STREET_GOAL, self.street_destroyed + 1)
        elif kind == "GIANT":
            self.giants_destroyed = min(self.GIANT_GOAL, self.giants_destroyed + 1)
        else:
            return False

        old_stage = self.stage
        self._advance_if_ready()
        return self.stage is not old_stage

    def _advance_if_ready(self) -> None:
        if self.stage is GroundOperationStage.STREET_ASSAULT:
            if self.street_destroyed >= self.STREET_GOAL:
                self.stage = GroundOperationStage.GIANT_HUNT

        if self.stage is GroundOperationStage.GIANT_HUNT:
            if self.giants_destroyed >= self.GIANT_GOAL:
                self.stage = GroundOperationStage.COMPLETE
                self.completed_operations += 1

    def objective_text(self) -> str:
        if self.stage is GroundOperationStage.STREET_ASSAULT:
            return f"BREAK STREET ASSAULT // {self.street_destroyed}/{self.STREET_GOAL} HOSTILES"
        if self.stage is GroundOperationStage.GIANT_HUNT:
            return f"DESTROY A GIANT // {self.giants_destroyed}/{self.GIANT_GOAL}"
        return "GROUND SECURED // AIR PHASE AWAITS"

    def diagnostic_text(self) -> str:
        return (
            f"GROUND LOOP // {self.stage.value} // STREET "
            f"{self.street_destroyed}/{self.STREET_GOAL} // GIANT "
            f"{self.giants_destroyed}/{self.GIANT_GOAL}"
        )
