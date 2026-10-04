from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
s = (ROOT / 'main.py').read_text()
checks = {
    'air operation imported': 'from air_operation import AirOperation' in s,
    'air operation instantiated': 'air_operation = AirOperation()' in s,
    'fighter bullet attribution': '_record_player_kill("AIR", "FIGHTER")' in s,
    'ufo bullet attribution': '_record_player_kill("AIR", "UFO")' in s,
    'air completion commits outcome': 'combat_outcomes.mark_complete("AIR")' in s,
    'air reward repairs hull': 'if air_reward_pending' in s and 'player.hp = player.hp_max' in s,
    'air reward restores shield': 'if air_reward_pending' in s and 'player.shield = player.shield_max' in s,
    'air HUD uses mission authority': 'hud_layout.mission_lines(' in s and 'air_operation=air_operation' in s,
    'air diagnostic present': 'air_operation.diagnostic_text()' in s,
    'air loop does not own campaign transition': 'advance_air_to_ocean' not in (ROOT / 'air_operation.py').read_text(),
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS ' if ok else 'FAIL ') + name)
if failed:
    raise SystemExit(1)
print('pass09_air_loop: PASS')
