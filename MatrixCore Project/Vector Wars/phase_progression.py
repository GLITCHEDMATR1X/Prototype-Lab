from enum import Enum


class WarPhase(Enum):
    GROUND = "GROUND"
    AIR = "AIR"
    OCEAN = "OCEAN"


_MODE_FOR_PHASE = {
    WarPhase.GROUND: 1,
    WarPhase.AIR: 0,
    WarPhase.OCEAN: 2,
}


class PhaseProgression:
    """Campaign-owned combat phase authority.

    Developer front switching must not mutate this authority. Normal play always
    returns to the currently unlocked campaign phase.
    """

    def __init__(self):
        self.active_phase = WarPhase.GROUND
        self.ground_transition_count = 0
        self.air_transition_count = 0
        self.campaign_complete = False
        self.campaign_completion_count = 0

    @property
    def active_mode(self) -> int:
        return _MODE_FOR_PHASE[self.active_phase]

    def advance_ground_to_air(self) -> bool:
        """Advance once from Ground to Air. Returns True only on transition."""
        if self.active_phase is not WarPhase.GROUND:
            return False
        self.active_phase = WarPhase.AIR
        self.ground_transition_count += 1
        return True

    def advance_air_to_ocean(self) -> bool:
        """Advance once from Air to Ocean. Returns True only on transition."""
        if self.active_phase is not WarPhase.AIR:
            return False
        self.active_phase = WarPhase.OCEAN
        self.air_transition_count += 1
        return True

    def complete_ocean_campaign(self) -> bool:
        """Complete the campaign once from the Ocean phase."""
        if self.active_phase is not WarPhase.OCEAN or self.campaign_complete:
            return False
        self.campaign_complete = True
        self.campaign_completion_count += 1
        return True

    def diagnostic_text(self) -> str:
        return (
            f"WAR PHASE // {self.active_phase.value} // "
            f"GROUND->AIR {self.ground_transition_count} // AIR->OCEAN {self.air_transition_count} // "
            f"CAMPAIGN {'COMPLETE' if self.campaign_complete else 'ACTIVE'}"
        )
