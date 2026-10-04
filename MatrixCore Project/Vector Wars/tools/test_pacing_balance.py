from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pacing_balance import player_speed_scale, ocean_cruise_target, validate_phase_identity

assert player_speed_scale('AIR') == 1.0
assert 0.0 < player_speed_scale('GROUND') < 1.0
assert 0.0 < player_speed_scale('OCEAN') < 1.0
assert ocean_cruise_target(throttle=1.0, boost=True, current_forward_speed=0.0, dt=1/60) == 126.0
assert ocean_cruise_target(throttle=0.0, boost=False, current_forward_speed=0.0, dt=1/60) == 64.0
assert validate_phase_identity() == []
print('pacing_balance: PASS')
