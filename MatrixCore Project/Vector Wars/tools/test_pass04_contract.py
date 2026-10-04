#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
s = (root / 'main.py').read_text(encoding='utf-8')
checks = {
    'ground operation imported': 'from ground_operation import GroundOperation' in s,
    'ground operation instantiated': 'ground_operation = GroundOperation()' in s,
    'street kill attribution': '_record_player_kill("GROUND", "STREET")' in s,
    'giant kill attribution': '_record_player_kill("GROUND", "GIANT")' in s,
    'ground completion commits outcome': 'combat_outcomes.mark_complete("GROUND")' in s,
    'ground reward repairs hull': 'player.hp = player.hp_max' in s,
    'ground reward restores shield': 'player.shield = player.shield_max' in s,
    'ground HUD uses mission authority': 'hud_layout.mission_lines(' in s and 'ground_operation=ground_operation' in s,
    'normal TAB still developer gated': 'elif ev.key == pygame.K_TAB:' in s and 'if dev_mode and not (ground_assault and ground_recovery.redeploy_required):' in s,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
if failed:
    raise SystemExit('contract failures: ' + ', '.join(failed))
print('pass04_contract: PASS')
