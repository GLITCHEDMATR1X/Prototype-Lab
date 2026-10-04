from __future__ import annotations
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
main = (ROOT / 'main.py').read_text()
pacing = (ROOT / 'pacing_balance.py').read_text()
checks = {
    'pacing authority imported': 'from pacing_balance import player_speed_scale, ocean_cruise_target' in main,
    'ship update uses phase speed scale': 'phase_speed_scale = float(ctrl.get("phase_speed_scale", 1.0))' in main,
    'control packet gets front speed scale': '"phase_speed_scale": player_speed_scale(_front_name())' in main,
    'ocean cruise uses authority': 'cruise_target = ocean_cruise_target(' in main,
    'old ocean fighter-like cruise removed': '78.0 + max(0.0, throttle) * 58.0 + (34.0 if boost else 0.0)' not in main,
    'air scale remains full': '"AIR": 1.00' in pacing,
    'ground scale below air': '"GROUND": 0.48' in pacing,
    'ocean scale below air': '"OCEAN": 0.66' in pacing,
}
for name, ok in checks.items():
    print(('PASS ' if ok else 'FAIL ') + name)
if not all(checks.values()):
    raise SystemExit(1)
print('pass17_phase_pacing: PASS')
