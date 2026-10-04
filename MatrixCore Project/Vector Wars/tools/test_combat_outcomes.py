#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from combat_outcomes import CombatOutcomeAuthority, CombatPhaseStatus


def main():
    c = CombatOutcomeAuthority()
    for front, goal in c.GOALS.items():
        status, progress, got_goal, failures = c.snapshot(front)
        assert status is CombatPhaseStatus.ACTIVE
        assert progress == 0 and got_goal == goal and failures == 0

        c.record_failure(front)
        status, progress, _, failures = c.snapshot(front)
        assert status is CombatPhaseStatus.FAILED and failures == 1 and progress == 0

        c.begin_attempt(front)
        assert c.snapshot(front)[0] is CombatPhaseStatus.ACTIVE

        c.record_hostile_destroyed(front, goal - 1)
        assert c.snapshot(front)[0] is CombatPhaseStatus.ACTIVE
        c.record_hostile_destroyed(front, 1)
        assert c.snapshot(front)[0] is CombatPhaseStatus.COMPLETE
        assert c.snapshot(front)[1] == goal

        # Accepted completion is sticky: failures/retries/progress cannot regress it.
        c.record_failure(front)
        c.begin_attempt(front)
        c.record_hostile_destroyed(front, 99)
        assert c.snapshot(front)[0] is CombatPhaseStatus.COMPLETE
        assert c.snapshot(front)[1] == goal
        assert c.snapshot(front)[3] == 1

    print("combat_outcomes: PASS")


if __name__ == "__main__":
    main()
