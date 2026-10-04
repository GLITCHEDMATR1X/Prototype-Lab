#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ground_recovery import GroundRecoveryAuthority, GroundRecoveryStatus

r = GroundRecoveryAuthority()
assert r.status is GroundRecoveryStatus.DEPLOYED
assert not r.redeploy_required
assert r.record_loss() is True
assert r.redeploy_required
assert r.failures == 1
assert r.record_loss() is False
assert r.failures == 1
assert r.request_redeploy() is True
assert r.status is GroundRecoveryStatus.DEPLOYED
assert r.redeployments == 1
assert r.request_redeploy() is False
print('ground_recovery: PASS')
