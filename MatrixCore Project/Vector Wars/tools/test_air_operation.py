from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from air_operation import AirOperation

op = AirOperation()
assert op.stage == 'FIGHTER_SWEEP'
assert '0/6' in op.objective_text()

# UFO kills can be banked early but do not skip the fighter-control stage.
op.record_destroyed('UFO')
op.record_destroyed('UFO')
assert op.ufo_kills == 2
assert op.stage == 'FIGHTER_SWEEP'

for _ in range(5):
    assert not op.record_destroyed('FIGHTER')
assert op.fighter_kills == 5
assert not op.complete
assert op.record_destroyed('FIGHTER')
assert op.complete
assert op.stage == 'SECURED'
assert 'AIR SECURED' in op.objective_text()

# Completion is sticky and unknown targets do not mutate state.
assert not op.record_destroyed('FIGHTER')
assert not op.record_destroyed('UNKNOWN')
assert op.fighter_kills == 6 and op.ufo_kills == 2
print('air_operation: PASS')
