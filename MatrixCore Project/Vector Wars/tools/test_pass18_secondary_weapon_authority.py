#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
s = (ROOT / 'main.py').read_text(encoding='utf-8')
checks = [
    ('weapon pacing imported', 'from weapon_pacing import secondary_cooldown, generic_missile_allowed' in s),
    ('ocean generic missile gated', '"missile": (mouse3 and generic_missile_allowed(_front_name()))' in s),
    ('ocean torpedo uses ocean cooldown', 'if mouse3 and (t_now - player.last_missile) >= secondary_cooldown("OCEAN"):' in s),
    ('HUD uses phase cooldown', 'secondary_cooldown(_front_name()) - (t_now - player.last_missile)' in s),
    ('AI retains own missile cooldown', 'if self.is_player else self.missile_cd' in s),
]
for name, ok in checks:
    print(('PASS' if ok else 'FAIL'), name)
    if not ok:
        raise SystemExit(1)
print('pass18_secondary_weapon_authority: PASS')
