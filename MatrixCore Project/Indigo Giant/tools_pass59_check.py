"""Pass 59 check: Indigo's night glow, and the glow you can carry.

    python tools_pass59_check.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from panda3d.core import Point3

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='indigo_save59_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import fight          # noqa: E402
import glow           # noqa: E402
import main as game   # noqa: E402
import wild           # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
DT = 1 / 30.0


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def new_app(**kw):
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, persist=True, save_dir=TMP,
                                       show_title=False, **kw)
    a.time_frozen = True
    a.comp.update({'mode': 'stay', 'moving': False})
    b = a.human_base_pos
    a.red_giant.setPos(ground(a, b.x + 900, b.y))
    a.red_state = 'idle'
    return a


def at(a, hour, steps=3):
    a.hour = hour
    a._apply_time(force=True)
    for _ in range(steps):
        a.survival_step(DT)


def shader_vec(np_, name):
    inp = np_.getShaderInput(name)          # keep the input alive while its vector is read
    v = inp.getVector()
    return tuple(float(v[i]) for i in range(4))


def shader_float(np_, name):
    return shader_vec(np_, name)[0]


def main():
    a = new_app(new_game=True)
    b = a.human_base_pos
    a.human.setPos(ground(a, b.x, b.y))
    a.giant.setPos(ground(a, b.x + 6, b.y))

    # 1. it glows at night, not by day; it comes up with the dusk
    at(a, 12.0)
    day = a._glow_level
    day_self = shader_float(a.giant, 'glow_self')
    at(a, 18.8)
    dusk = a._glow_level
    at(a, 23.0)
    night = a._glow_level
    check('Indigo glows at night (not by day), coming up with the dusk',
          day == 0.0 and day_self == 0.0 and 0.05 < dusk < 0.95 and night > 0.95
          and shader_float(a.giant, 'glow_self') > 0.8 and not a.indigo_aura.isHidden(),
          f'noon {day:.2f}, 18:48 {dusk:.2f}, 23:00 {night:.2f}')
    col = shader_vec(a.render, 'glow_color')
    check('its light falls on the world around it (the sand, you): an indigo light, ~30 m',
          col[2] > 0.8 and col[2] > col[0] * 2 and shader_vec(a.render, 'glow_pos_view')[3] == glow.GLOW_REACH
          and shader_float(a.giant, 'glow_receive') == 0.0,
          f'colour {col[0]:.2f} {col[1]:.2f} {col[2]:.2f}')
    a.knock_out_indigo_quiet()
    at(a, 23.0)
    ember = a._glow_level
    a.giant_knocked_out, a.giant_alive, a.giant_getup = False, True, -1.0
    at(a, 23.0)
    check('knocked out, its glow sinks to an ember', ember <= glow.GLOW_KO + 1e-6 and a._glow_level > 0.95,
          f'{ember:.2f}')

    # 2. it protects Indigo
    a.giant_stamina = fight.STAMINA_MAX['giant']
    s0 = a.giant_stamina
    a.resolve_hit('red', 'giant')
    night_cost = s0 - a.giant_stamina
    at(a, 12.0)
    a.giant_stamina = fight.STAMINA_MAX['giant']
    a.resolve_hit('red', 'giant')
    day_cost = fight.STAMINA_MAX['giant'] - a.giant_stamina
    at(a, 23.0)
    a.giant_energy = 1.0
    a.indigo_resting = False
    for _ in range(int(20 / DT)):
        a.survival_step(DT)
    drained = 1.0 - a.giant_energy
    check('at night the glow protects Indigo: hits cost it 40% less, the cold drains it half as fast',
          abs(night_cost / day_cost - 0.6) < 0.02 and abs(drained - wild.NIGHT_DRAIN * 20 * 0.5) < 0.005,
          f'a hit costs {night_cost:.2f} at night, {day_cost:.2f} by day; 20 s of night took {drained:.3f} '
          f'energy (was {wild.NIGHT_DRAIN * 20:.3f})')

    # 3. it warms you, inside its light (beyond the 14 m of its body warmth)
    a.giant.setPos(ground(a, b.x + 20, b.y))
    a.chill = 50.0
    for _ in range(int(10 / DT)):
        a.survival_step(DT)
    near = a.chill
    a.giant.setPos(ground(a, b.x + 60, b.y))
    a.chill = 50.0
    for _ in range(int(10 / DT)):
        a.survival_step(DT)
    far = a.chill
    check("at night Indigo's light warms you, 20 m off (its body warmth reaches 14 m); out of it you chill",
          near < 50.0 < far and a.glow_warming() is False, f'10 s at 20 m: cold 50 -> {near:.0f}; at 60 m: 50 -> {far:.0f}')

    # 4. drawing the glow (hold E beside Indigo at night)
    a.giant.setPos(ground(a, b.x + 6, b.y))
    a.chill = 0.0
    at(a, 23.0)
    kind, _t = a._e_target()
    a.keys['e'] = True
    a.e_hold['spent'] = False
    for _ in range(int(1.5 / DT)):
        a._update_e_hold(DT)
    a.keys['e'] = False
    a._update_e_hold(DT)
    first = (a.glow_charge, a.indigo_glow_reserve)
    at(a, 23.0)
    dimmer = a._glow_level
    a._complete_e('glow', None)
    second = a.glow_charge
    third_ok = a.can_draw_glow()
    check('at night beside Indigo, hold E to draw some of its glow; each draw dims Indigo a little',
          kind == 'glow' and first == (60.0, 0.7) and 0.8 < dimmer < 0.9 and second == 100.0 and not third_ok,
          f'after one draw: carry {first[0]:.0f}, Indigo {first[1]:.2f} (glow {dimmer:.2f}); two: {second:.0f}')
    at(a, 12.0)
    check('you cannot draw it by day', not a.can_draw_glow() and a._e_target()[0] != 'glow')

    # 5. the perk, by day
    a.glow_charge = 100.0
    a.human_effort = 'sprint'
    a.controlled_name = 'human'
    a.stamina, a.winded = 100.0, False
    a.heat_factor_override = 0.0
    a._update_heat(1.0)
    with_glow = 100.0 - a.stamina
    spent_glow = 100.0 - a.glow_charge
    a.glow_charge = 0.0
    a.stamina = 100.0
    a._update_heat(1.0)
    without = 100.0 - a.stamina
    a.human_effort = 'idle'
    check('strength: effort costs x0.6 breath while you carry it (and spends the glow)',
          abs(with_glow / without - 0.6) < 0.01 and spent_glow > 0.0,
          f'1 s sprint: {with_glow:.1f} breath with it, {without:.1f} without; glow spent {spent_glow:.1f}')
    a.glow_charge = 100.0
    check('strength: hold-E work in 0.7 of the time', abs(a.work_speed() * 0.7 - 1.0) < 1e-6)
    hp_before = a.human_health = 100.0
    a.glow_charge = 100.0
    scale = a.human_damage_scale()
    a.heat = 100.0
    a._update_heat(1.0)
    heat_loss = hp_before - a.human_health
    a.heat = 0.0
    a.human_health = 50.0
    for _ in range(int(10 / DT)):
        a.survival_step(DT)
    healed = a.human_health - 50.0
    check('health: heat, cold and blows hurt x0.65, and you heal slowly while you carry it',
          scale == 0.65 and abs(heat_loss - 100.0 / 180.0 * 0.65) < 0.02 and healed > 3.0,
          f'1 s at full heat cost {heat_loss:.2f} life (was {100 / 180:.2f}); healed {healed:.1f} in 10 s')

    # 6. it fades as you spend breath by day, at once when winded; not at night
    a.glow_charge = 50.0
    a.winded, a.stamina = True, 0.0                 # out of breath
    for _ in range(int(2.5 / DT)):
        a.survival_step(DT)
    winded_left = a.glow_charge
    a.winded = False
    a.stamina = 100.0
    a.glow_charge = 50.0
    at(a, 23.0)
    for _ in range(int(30 / DT)):
        a.survival_step(DT)
    night_left = a.glow_charge
    at(a, 12.0)
    for _ in range(int(60 / DT)):
        a.survival_step(DT)
    day_left = a.glow_charge
    check('it fades: at once when you run out of breath by day, slowly with the day, not at night',
          winded_left == 0.0 and night_left == 50.0 and 40.0 < day_left < 50.0,
          f'winded: 50 -> {winded_left:.0f}; 30 s of night: 50 -> {night_left:.0f}; a minute of day -> {day_left:.1f}')

    # 7. the cold creeps in slower at night while you carry it
    at(a, 23.0)
    a.giant.setPos(ground(a, b.x + 200, b.y))
    a.glow_charge, a.chill = 100.0, 0.0
    for _ in range(int(10 / DT)):
        a.survival_step(DT)
    charged_chill = a.chill
    a.glow_charge, a.chill = 0.0, 0.0
    for _ in range(int(10 / DT)):
        a.survival_step(DT)
    plain_chill = a.chill
    check('carrying it, the night cold creeps in slower (x0.6)', abs(charged_chill / plain_chill - 0.6) < 0.03,
          f'10 s away from Indigo: {charged_chill:.1f} with it, {plain_chill:.1f} without')

    # 8. Indigo's glow recovers; saves keep both
    a.indigo_glow_reserve = 0.4
    for _ in range(int(60 / DT)):
        a.survival_step(DT)
    check("Indigo's glow recovers (fully in 4 minutes)", abs(a.indigo_glow_reserve - (0.4 + 60 / 240)) < 0.01,
          f'{a.indigo_glow_reserve:.2f}')
    a.glow_charge, a.indigo_glow_reserve = 42.0, 0.55
    a.save_game('check')
    a.destroy()
    a = new_app()
    check('the glow you carry and Indigo\'s own are saved', a.glow_charge == 42.0 and a.indigo_glow_reserve == 0.55,
          f'{a.glow_charge}, {a.indigo_glow_reserve}')

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
