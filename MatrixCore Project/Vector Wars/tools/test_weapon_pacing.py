#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from weapon_pacing import secondary_cooldown, generic_missile_allowed, validate_secondary_identity
assert secondary_cooldown('AIR') == 1.25
assert secondary_cooldown('GROUND') > secondary_cooldown('AIR')
assert secondary_cooldown('OCEAN') > secondary_cooldown('GROUND')
assert generic_missile_allowed('AIR')
assert generic_missile_allowed('GROUND')
assert not generic_missile_allowed('OCEAN')
assert validate_secondary_identity() == []
print('weapon_pacing: PASS')
