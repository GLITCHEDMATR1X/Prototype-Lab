import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ocean_operation import OceanOperation

op = OceanOperation()
assert op.stage == "SURFACE_ACTION_GROUP"
assert "WARSHIPS 0/4" in op.objective_text()
# Bank helicopters even before surface stage completes.
assert op.record_destroyed("HELICOPTER") is False
assert op.record_destroyed("HELI") is False
assert op.helicopter_kills == 2
for _ in range(3):
    assert op.record_destroyed("WARSHIP") is False
assert op.stage == "SURFACE_ACTION_GROUP"
assert op.record_destroyed("WARSHIP") is True
assert op.complete
assert op.stage == "SEA_CONTROL"
assert op.record_destroyed("WARSHIP") is False
assert op.warship_kills == 4
print("ocean_operation: PASS")
