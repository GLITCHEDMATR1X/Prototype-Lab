from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class HackOutcome(str, Enum):
    CLEAN = 'clean_success'
    NOISY = 'noisy_success'
    REJECTED = 'rejected_attempt'
    GLEEBS_VIOLATION = 'gleebs_violation'

@dataclass(frozen=True)
class HackMethod:
    method_id: str
    label: str
    key: int
    description: str

METHODS = (
    HackMethod('credential_spoof', 'CREDENTIAL SPOOF', 4, 'Imitate a valid staff or service identity.'),
    HackMethod('maintenance_bypass', 'MAINTENANCE BYPASS', 5, 'Use an active diagnostic or service route.'),
    HackMethod('signal_replay', 'SIGNAL REPLAY', 6, 'Repeat a previously observed command sequence.'),
    HackMethod('power_cycle', 'POWER CYCLE', 7, 'Reset a device through its local power state.'),
    HackMethod('brute_force', 'BRUTE FORCE', 8, 'Overpower the security layer at high trace risk.'),
)
METHOD_BY_ID = {method.method_id: method for method in METHODS}
METHOD_BY_KEY = {method.key: method for method in METHODS}
