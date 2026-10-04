#!/usr/bin/env python3
from pathlib import Path
root = Path(__file__).resolve().parents[1]
s = (root / 'main.py').read_text(encoding='utf-8')
checks = {
    'ground recovery imported': 'from ground_recovery import GroundRecoveryAuthority' in s,
    'ground recovery instantiated': 'ground_recovery = GroundRecoveryAuthority()' in s,
    'ground loss enters recovery': 'ground_recovery.record_loss()' in s,
    'ground death records failure': 'combat_outcomes.record_failure("GROUND")' in s,
    'enter redeploy input': 'pygame.K_RETURN, pygame.K_KP_ENTER' in s and '_redeploy_ground_player()' in s,
    'checkpoint redeploy': 'ground_checkpoint_xy' in s and 'new_player.pos = Vector3(gx, gy, 3.0)' in s,
    'progress-preserved prompt': 'OPERATION PROGRESS PRESERVED' in s,
    'ground no immediate respawn': "if ground_assault:\n                if ground_recovery.record_loss():" in s,
    'air ocean legacy respawn retained': 'else:\n                combat_outcomes.record_failure(failed_front)' in s,
    'dev tab blocked during ground loss': 'dev_mode and not (ground_assault and ground_recovery.redeploy_required)' in s,
}
failed = [k for k,v in checks.items() if not v]
for k,v in checks.items(): print(('PASS' if v else 'FAIL'), k)
if failed: raise SystemExit('contract failures: ' + ', '.join(failed))
print('pass05_contract: PASS')
