from pathlib import Path

src = Path(__file__).resolve().parents[1] / 'main.py'
s = src.read_text(encoding='utf-8')

# Every direct Ground-car kill hook must classify as STREET.
car_bullet = '''alive = gc.take_damage(b.dmg)\n                        if was_alive and (not alive) and getattr(b.owner, "is_player", False):\n                            _record_player_kill("GROUND", "STREET")'''
assert car_bullet in s, 'bullet-destroyed ground traffic is not classified STREET'

car_missile = '''alive = gc.take_damage(dmg)\n                            if was_alive and (not alive) and getattr(m.owner, "is_player", False):\n                                _record_player_kill("GROUND", "STREET")'''
assert car_missile in s, 'missile-destroyed ground traffic is not classified STREET'

# Every Giant kill hook must classify as GIANT regardless of projectile family.
giant_bullet = '''gm.take_damage(b.dmg, t_now)\n                        if was_alive and gm.dead and getattr(b.owner, "is_player", False):\n                            _record_player_kill("GROUND", "GIANT")'''
assert giant_bullet in s, 'bullet-destroyed Giant is not classified GIANT'

giant_missile = '''gm.take_damage(dmg, t_now)\n                            if was_alive and gm.dead and getattr(m.owner, "is_player", False):\n                                _record_player_kill("GROUND", "GIANT")'''
assert giant_missile in s, 'missile-destroyed Giant is not classified GIANT'

# Exactly two STREET and two GIANT direct Ground kill hooks are expected here.
assert s.count('_record_player_kill("GROUND", "STREET")') == 2
assert s.count('_record_player_kill("GROUND", "GIANT")') == 2
print('PASS07_GROUND_KILL_ATTRIBUTION: PASS')
