from pathlib import Path
root = Path(__file__).resolve().parents[1]
s = (root / 'main.py').read_text()
checks = {
    'ocean operation imported': 'from ocean_operation import OceanOperation' in s,
    'ocean operation instantiated': 'ocean_operation = OceanOperation()' in s,
    'warship bullet attribution': '_record_player_kill("OCEAN", "WARSHIP")' in s,
    'helicopter bullet attribution': '_record_player_kill("OCEAN", "HELICOPTER")' in s,
    'ocean completion commits outcome': 'combat_outcomes.mark_complete("OCEAN")' in s,
    'ocean reward repairs hull': 'if ocean_reward_pending and ocean_mode:' in s and 'player.hp = float(player.hp_max)' in s,
    'ocean reward restores shield': 'if ocean_reward_pending and ocean_mode:' in s and 'player.shield = float(player.shield_max)' in s,
    'ocean HUD uses mission authority': 'hud_layout.mission_lines(' in s and 'ocean_operation=ocean_operation' in s,
    'ocean diagnostic present': 'ocean_operation.diagnostic_text()' in s,
    'no generic ocean kill hook': '_record_player_kill("OCEAN")' not in s,
}
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
if not all(checks.values()):
    raise SystemExit(1)
print('pass11_ocean_loop: PASS')
