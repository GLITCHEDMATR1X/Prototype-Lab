"""Pass 43 check: main.py entry, key bindings, day/night, sleep and camp, making gear,
seeds, the endless landmark trail, save / load, pause, HUD panels.

    python .dev/checks/pass43.py
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

from panda3d.core import Point3, Vec3

HERE = Path(__file__).resolve().parents[2]          # Pass 62: the game folder
TMP = Path(tempfile.mkdtemp(prefix='indigo_save_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)

import sys as _sys                                  # Pass 62: the game folder is two levels up
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from indigo_giant import controls   # noqa: E402
from indigo_giant import daycycle   # noqa: E402
from indigo_giant import desert     # noqa: E402
from indigo_giant import flora      # noqa: E402
from indigo_giant import app as game   # noqa: E402

FAILS = []
CLOCK = [0.0]


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def frame(a, dt=1 / 30.0):
    CLOCK[0] += dt
    t = CLOCK[0]
    move = Vec3(0, 0, 0)
    if a.controlled_name == 'giant':
        a._apply_giant_heavy_input(move, dt, t)
    elif not a.world_frozen():
        a._apply_controlled_move(move, dt, t)
    if not a.world_frozen():
        a._update_indigo_defender(dt, t)
        a._update_companion(dt)
        a._update_red_giant(dt, t)
    a.survival_step(dt)
    a._update_actor_shadows()
    a.service_stream_queue()


def run(a, seconds, until=None, dt=1 / 30.0):
    for i in range(int(round(seconds / dt))):
        frame(a, dt)
        if until is not None and until():
            return (i + 1) * dt
    return None


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def park_red(a):
    p = a.human.getPos() + Vec3(900, 0, 0)
    a.red_giant.setPos(ground(a, p.x, p.y))
    a.red_state = 'idle'


GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'


def new_app(**kw):
    return game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, persist=True, save_dir=TMP, **kw)


def main():
    check('the game is main.py (lab launchers run it directly)', (HERE / 'main.py').is_file()
          and 'main.py' in (HERE / 'RUN_INDIGO_GIANT.bat').read_text())

    # ------------------------------------------------------------ bindings
    b = controls.load(TMP)
    check('controls.json is written with the defaults', (TMP / 'controls.json').is_file() and b['jump'] == 'space')
    data = json.loads((TMP / 'controls.json').read_text())
    data['jump'] = 'v'
    (TMP / 'controls.json').write_text(json.dumps(data))
    check('a rebound key is picked up', controls.load(TMP)['jump'] == 'v')
    check('arrow keys bound by their real Panda names', controls.DEFAULT_BINDINGS['camera_left'] == 'arrow_left')

    a = new_app(new_game=True)
    park_red(a)
    run(a, 0.5)

    # ------------------------------------------------------------ day / night
    check('a journey starts on day 1 in the morning', a.day == 1 and 6.5 < a.hour < 8.0, f'{a.hour:.2f}')
    check('noon sun is harsh, dawn gentle, night cools',
          daycycle.sun_heat_factor(12.0) > 1.1 and daycycle.sun_heat_factor(6.2) < 0.5 and daycycle.sun_heat_factor(23.0) < 0)
    az0, el0 = daycycle.sun_angles(7.0)
    az1, el1 = daycycle.sun_angles(12.0)
    check('the sun moves across the sky', az1 != az0 and el1 > el0 + 30, f'{el0:.0f} -> {el1:.0f} deg')
    a.hour = 17.9
    t = run(a, 60.0, until=lambda: a.is_night())
    check('dusk turns to night', t is not None)
    ra = a.red_detection_range()
    check('the Red Giant sees less far at night', abs(ra - game.RED_DETECTION_RANGE * 0.6) < 1e-6)
    a.hour = 5.95
    d0 = a.day
    run(a, 1.0)
    check('a new day begins at dawn', a.day == d0 + 1, a.day)

    # ------------------------------------------------------------ making gear
    a.hour = 12.0
    a.time_frozen = True
    a.bag('human').update({'fibre': 12, 'resin': 4, 'shard': 5, 'scraps': 2})
    for rid in ('cloak', 'wraps', 'waterskin', 'canopy'):
        check(f'make the {rid}', a.craft(rid) and a.has_upgrade(rid))
    check('materials are used up', sum(a.bag('human').values()) == 0,
          dict(a.bag('human')))
    check('cannot make the same thing twice', not a.craft('cloak'))
    a.heat = 0.0
    a.heat_factor_override = 1.0
    hp = a.human.getPos()
    spot = ground(a, hp.x - 200, hp.y - 150)
    a.human.setPos(spot)
    a.giant.setPos(ground(a, spot.x + 300, spot.y))
    a._refresh_world()
    run(a, 10.0)
    rate = a.heat / 10.0
    check('sun cloak: sun heats 25% slower', a.shelter_word == 'sun' and abs(rate - desert.HEAT_SUN_RATE * 0.75) < 0.02,
          f'{rate:.3f}/s')
    check('water skin starts with 3 sips', a.water_sips == 3)
    a.heat = 70.0
    check('G sips from the skin when hot with no gourd', a.eat() == 'sip' and a.water_sips == 2 and a.heat < 50)

    # ------------------------------------------------------------ seeds
    a.heat = 0.0
    branch = a.flora.nearest_intact(a.human.getPos(), 3000)
    a.flora.update_active(branch.pos)
    a.human.setPos(ground(a, branch.pos.x + 1, branch.pos.y))
    a._journey_rng.seed(1)       # deterministic seed roll
    got = False
    for _ in range(12):
        branch.smashed = False
        if a.on_branch_smashed(branch, 'human'):
            got = True
            break
    check('smashing branches sometimes leaves a seed', got and a.pooled_count('seed') >= 1)
    a.bag('human')['seed'] = max(1, a.bag('human')['seed'])
    open_spot = None
    for k in range(40):
        p = ground(a, spot.x + 12 * math.cos(k), spot.y + 12 * math.sin(k))
        a.human.setPos(p)
        if a._plant_spot() is not None and a._e_target()[0] == 'plant':
            open_spot = p
            break
    check('hold E on open ground offers planting', open_spot is not None)
    n0 = len(a.flora.planted)
    a._on_e_press()
    run(a, 1.6)
    a.keys['e'] = False
    run(a, 0.1)
    check('the seed is planted', len(a.flora.planted) == n0 + 1)
    sprout = a.flora.planted[-1]
    check('a seedling cannot heal yet', sprout.grow < 1.0 and a.flora.nearest_intact(sprout.pos, 3.0) is not sprout)
    a.flora.update(flora.PLANT_GROW_SECONDS + 1)
    check('it grows into a full blood branch', sprout.grow >= 1.0 and sprout.sap > 0
          and a.flora.nearest_intact(sprout.pos, 3.0) is sprout)

    # ------------------------------------------------------------ sleep and camp
    shell = a.shells.shells[('start', 0)]
    a.shells.set_state(shell, 'intact')
    a.human.setPos(ground(a, shell.entrance_point().x, shell.entrance_point().y))
    a._refresh_world()
    a.hour = 12.0
    a.enter_shell(shell)
    ok, why = a.can_sleep()
    check('no sleeping at noon', not ok and 'early' in why)
    a.hour = 20.0
    a.human_health = 40.0
    a.water_sips = 0
    day0 = a.day
    check('sleep in a shell at night', a.request_sleep())
    run(a, 3.0)
    check('you wake at dawn the next day, rested', a.day == day0 + 1 and abs(a.hour - 6.0) < 0.1
          and a.human_health == 100.0 and not a.sleeping(), f'day {a.day} {a.hour:.2f}')
    check('the shell became camp, the skin filled with dew', a.camp_shell is shell and a.water_sips == 3)
    check('sleeping saved the journey', (TMP / 'journey.json').is_file())
    a.exit_shell()

    # ------------------------------------------------------------ waking at camp after collapsing
    a.human.setPos(spot)
    a._down_human()
    a._retry_after_human_down()
    check('after collapsing you wake at camp', a.human_alive and
          math.hypot(a.human.getX() - shell.entrance_point().x, a.human.getY() - shell.entrance_point().y) < 1.0)

    # ------------------------------------------------------------ the trail never ends
    n = len(a.landmarks.items)
    for lm in a.landmarks.items[:-1]:
        lm.visited = True
    last = a.landmarks.items[-1]
    reach = __import__('indigo_giant.desert_geom', fromlist=['LANDMARK_SHAPES']).LANDMARK_SHAPES[last.kind][0] + 3.0
    a.human.setPos(ground(a, last.pos.x + reach, last.pos.y))
    a._refresh_world()
    a._on_e_press()
    run(a, 2.2)
    a.keys['e'] = False
    run(a, 0.1)
    new = a.landmarks.items[n:]
    check('studying the last marker opens a wider ring', a.landmarks.chapter == 2 and len(new) == 5
          and sum(1 for lm in new if lm.revealed) == 2)
    far = min(math.hypot(lm.pos.x - a.landmarks.start.x, lm.pos.y - a.landmarks.start.y) for lm in new)
    check('the new ring lies beyond the old one', far > 1150, f'{far:.0f} m')
    worst = 0.0
    for lm in new:
        r = __import__('indigo_giant.desert_geom', fromlist=['LANDMARK_SHAPES']).LANDMARK_SHAPES[lm.kind][0]
        for k in range(8):
            worst = max(worst, abs(a.field.height(lm.pos.x + math.cos(k) * r, lm.pos.y + math.sin(k) * r) - lm.pos.z))
    check('new landmarks stand on levelled ground', worst < 0.3, f'{worst:.2f} m')
    check('their lore is written into the journal', len(a.lore_log) >= 1 and a.stats['landmarks'] >= 1)
    lines, lore = a.journal_lines()
    check('journal shows the trail', any('ring 2' in line for line in lines))

    # ------------------------------------------------------------ pause
    a.toggle_panel('menu')
    h0 = a.hour
    a.time_frozen = False
    run(a, 2.0)
    check('Esc menu pauses the world', a.paused and a.hour == h0)
    a.close_panel()
    check('closing the menu resumes', not a.paused)
    for name in ('craft', 'journal', 'help'):
        a.toggle_panel(name)
        check(f'{name} panel opens and closes', a.panel is not None)
        a.close_panel()

    # ------------------------------------------------------------ save and load
    a.time_frozen = True
    a.hour = 9.5
    a.bag('human').clear()
    a.bag('human').update({'fibre': 2, 'pod': 1})
    f0 = a.finds.finds[('start', 0)]
    f0.dug = True
    here = a.human.getPos()
    check('save the journey', a.save_game('test'))
    snap = json.loads((TMP / 'journey.json').read_text())
    check('players are stored as a list (ready for co-op)', isinstance(snap['players'], list) and snap['players'][0]['id'] == 'p1')
    a.destroy()

    b = new_app()
    run(b, 0.2)
    check('load: day, hour and trail ring', b.day == a.day and abs(b.hour - 9.5) < 0.05 and b.landmarks.chapter == 2,
          f'day {b.day} ring {b.landmarks.chapter}')
    check('load: where you stood', math.hypot(b.human.getX() - here.x, b.human.getY() - here.y) < 0.05)
    check('load: bag and gear', b.bag('human')['fibre'] == 2 and b.bag('human')['pod'] == 1
          and b.upgrades == {'cloak', 'wraps', 'waterskin', 'canopy'})
    check('load: visited markers', sum(1 for lm in b.landmarks.items if lm.visited) == len(a.landmarks.items) - 5)
    check('load: dug finds stay dug', b.finds.finds[('start', 0)].dug)
    check('load: camp and planted branch', b.camp_shell is not None and b.camp_shell.pid == ('start', 0)
          and len(b.flora.planted) == 1)
    check('load: patched shell stays patched', b.shells.shells[('start', 0)].state == 'intact')
    b.destroy()

    c = new_app(new_game=True)
    check('--new starts fresh', c.day == 1 and c.landmarks.chapter == 1 and not c.upgrades)
    c.destroy()

    shutil.rmtree(TMP, ignore_errors=True)
    print('RESULT', 'FAIL' if FAILS else 'PASS', FAILS)
    sys.exit(1 if FAILS else 0)


if __name__ == '__main__':
    main()
