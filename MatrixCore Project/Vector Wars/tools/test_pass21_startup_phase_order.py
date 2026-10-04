#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'main.py').read_text(encoding='utf-8')

clock_idx = source.find('    t_now = 0.0\n\n    restored_campaign = restore_campaign_save(')
restore_apply_idx = source.find('    if restored_campaign:\n        _apply_combat_mode(phase_progression.active_mode)')
ocean_wave_idx = source.find('player.pos.z = ocean_wave_height(player.pos.x, player.pos.y, t_now) + OCEAN_PLAYER_RIDE')

checks = {
    'startup clock exists before restore load': clock_idx >= 0,
    'restored phase application exists': restore_apply_idx >= 0,
    'ocean mode samples startup clock': ocean_wave_idx >= 0,
    'clock initialized before restored phase apply': clock_idx >= 0 and restore_apply_idx >= 0 and clock_idx < restore_apply_idx,
    'startup phase-order repair remains present': clock_idx >= 0 and restore_apply_idx >= 0 and clock_idx < restore_apply_idx,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"{'PASS' if ok else 'FAIL'}: {name}")
if failed:
    raise SystemExit('Pass21 startup phase-order contract failed: ' + ', '.join(failed))
print('PASS21_STARTUP_PHASE_ORDER: PASS')
