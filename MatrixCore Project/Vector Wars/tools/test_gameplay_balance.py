#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gameplay_balance import STANDARD_COMBAT_COUNTS, standard_count, validate_campaign_capacity
from ground_operation import GroundOperation
from air_operation import AirOperation
from ocean_operation import OceanOperation

expected = {
    "traffic": 30,
    "fighters": 10,
    "ufos": 3,
    "warships": 5,
    "helicopters": 2,
}
assert STANDARD_COMBAT_COUNTS == expected, STANDARD_COMBAT_COUNTS
for key, value in expected.items():
    assert standard_count(key) == value

issues = validate_campaign_capacity(
    ground_street_goal=GroundOperation.STREET_GOAL,
    air_fighter_goal=AirOperation.FIGHTER_GOAL,
    air_ufo_goal=AirOperation.UFO_GOAL,
    ocean_warship_goal=OceanOperation.WARSHIP_GOAL,
    ocean_helicopter_goal=OceanOperation.HELICOPTER_GOAL,
)
assert issues == [], issues
print('gameplay_balance: PASS')
