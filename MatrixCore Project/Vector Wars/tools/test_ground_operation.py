#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ground_operation import GroundOperation, GroundOperationStage
from combat_outcomes import CombatOutcomeAuthority, CombatPhaseStatus


def main():
    g = GroundOperation()
    assert g.stage is GroundOperationStage.STREET_ASSAULT
    assert "0/8" in g.objective_text()

    # An early Giant kill is remembered but does not skip the street objective.
    assert not g.record_destroyed("GIANT")
    assert g.stage is GroundOperationStage.STREET_ASSAULT
    assert g.giants_destroyed == 1

    for _ in range(7):
        assert not g.record_destroyed("STREET")
    assert g.street_destroyed == 7
    assert g.stage is GroundOperationStage.STREET_ASSAULT

    # The eighth street kill advances and immediately recognizes the already-killed Giant.
    assert g.record_destroyed("STREET")
    assert g.stage is GroundOperationStage.COMPLETE
    assert g.complete
    assert g.completed_operations == 1
    assert "GROUND SECURED" in g.objective_text()

    # Completion is sticky and irrelevant target classes cannot alter it.
    assert not g.record_destroyed("STREET")
    assert not g.record_destroyed("GIANT")
    assert not g.record_destroyed("UFO")
    assert g.completed_operations == 1

    c = CombatOutcomeAuthority()
    c.mark_complete("GROUND")
    status, progress, goal, _ = c.snapshot("GROUND")
    assert status is CombatPhaseStatus.COMPLETE
    assert progress == goal == 1
    c.record_failure("GROUND")
    assert c.snapshot("GROUND")[0] is CombatPhaseStatus.COMPLETE

    print("ground_operation: PASS")


if __name__ == "__main__":
    main()
