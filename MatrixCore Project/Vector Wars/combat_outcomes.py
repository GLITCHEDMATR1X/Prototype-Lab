from enum import Enum


class CombatPhaseStatus(Enum):
    ACTIVE = "ACTIVE"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class CombatOutcomeAuthority:
    """Deterministic combat-front outcome state, independent of rendering.

    Ground completion is now owned by GroundOperation and committed here as a
    single completed operation. Air and Ocean retain their Pass 03 destruction
    goals until their own phase loops are built.
    """

    GOALS = {"GROUND": 1, "AIR": 8, "OCEAN": 4}

    def __init__(self):
        self.progress = {name: 0 for name in self.GOALS}
        self.status = {name: CombatPhaseStatus.ACTIVE for name in self.GOALS}
        self.failures = {name: 0 for name in self.GOALS}

    def record_hostile_destroyed(self, front: str, amount: int = 1) -> None:
        front = str(front).upper()
        if front not in self.GOALS:
            raise KeyError(front)
        if self.status[front] is CombatPhaseStatus.COMPLETE:
            return
        self.progress[front] = min(self.GOALS[front], self.progress[front] + max(0, int(amount)))
        if self.progress[front] >= self.GOALS[front]:
            self.status[front] = CombatPhaseStatus.COMPLETE

    def mark_complete(self, front: str) -> None:
        front = str(front).upper()
        if front not in self.GOALS:
            raise KeyError(front)
        self.progress[front] = self.GOALS[front]
        self.status[front] = CombatPhaseStatus.COMPLETE

    def record_failure(self, front: str) -> None:
        front = str(front).upper()
        if front not in self.GOALS:
            raise KeyError(front)
        if self.status[front] is CombatPhaseStatus.COMPLETE:
            return
        self.failures[front] += 1
        self.status[front] = CombatPhaseStatus.FAILED

    def begin_attempt(self, front: str) -> None:
        front = str(front).upper()
        if front not in self.GOALS:
            raise KeyError(front)
        if self.status[front] is not CombatPhaseStatus.COMPLETE:
            self.status[front] = CombatPhaseStatus.ACTIVE

    def snapshot(self, front: str):
        front = str(front).upper()
        if front not in self.GOALS:
            raise KeyError(front)
        return self.status[front], self.progress[front], self.GOALS[front], self.failures[front]
