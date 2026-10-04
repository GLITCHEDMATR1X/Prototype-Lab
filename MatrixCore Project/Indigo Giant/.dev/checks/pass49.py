"""Pass 49 check: every item from the post-Pass-48 review, plus the tracking-speed balance.

    python .dev/checks/pass49.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
import time
from pathlib import Path

from panda3d.core import Point3, TextNode

HERE = Path(__file__).resolve().parents[2]          # Pass 62: the game folder
TMP = Path(tempfile.mkdtemp(prefix='indigo_save49_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import sys as _sys                                  # Pass 62: the game folder is two levels up
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from indigo_giant import app as game   # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
CLOCK = [0.0]


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def put(node, a, x, y):
    node.setPos(x, y, a.field.height(x, y))


def tick(a, seconds, dt=1 / 30.0, move=None, until=None):
    for i in range(int(seconds / dt)):
        CLOCK[0] += dt
        if move is not None:
            a._apply_controlled_move(move, dt, CLOCK[0])
        a._update_red_giant(dt, CLOCK[0])
        a.survival_step(dt)
        if until is not None and until():
            return (i + 1) * dt
    return None


def fresh_branch(a, near):
    a.flora.update_active(near)
    return min((b for b in a.flora.active.values() if not b.smashed and b.grow >= 1.0 and not b.poisoned),
               key=lambda b: math.hypot(b.pos.x - near.x, b.pos.y - near.y))


def main():
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, new_game=True, persist=True, save_dir=TMP)
    a.time_frozen = True
    a.heat_factor_override = 0.0
    a.hour = 22.0
    a._apply_time(force=True)
    a.comp.update({'mode': 'stay', 'moving': False})
    hp = a.human.getPos()

    # 1 --------------------------------------------------------- hit while resting, it fights back
    put(a.red_giant, a, hp.x + 60.0, hp.y)
    a.red_energy = 0.1
    tick(a, 0.5)
    resting = a.red_resting
    a._set_combat_health('red', a.red_health - 10.0)
    tick(a, 0.2)
    check('1  hit while resting (or eating), the Red Giant drops it and fights back',
          resting and not a.red_resting and a.red_state not in ('rest', 'meal') and a.red_provoked_t > 0.0, a.red_state)
    a.red_provoked_t = 0.0
    a.red_woken_t = 0.0
    a.red_energy = 1.0

    # 2 --------------------------------------------------------- a meal knocked away is off
    a.hour = 12.0
    a._apply_time(force=True)
    b = fresh_branch(a, hp)
    put(a.red_giant, a, b.pos.x - 5.0, b.pos.y)
    put(a.human, a, b.pos.x + 200.0, b.pos.y)
    a.red_meal = {'t': 0.5, 'branch': b, 'taken': False}
    put(a.red_giant, a, b.pos.x - 200.0, b.pos.y)             # thrown well away from it
    tick(a, 0.2)
    check('2  a meal interrupted far from the branch is cancelled (no eating from afar)',
          a.red_meal is None and not b.smashed)
    a.flora.set_poisoned(b)
    a.red_eating = {'phase': 'eat', 't': 0.5, 'branch': b, 'taken': False}
    tick(a, 0.05)
    check('2b the same for the poisoned last meal', a.red_eating is None and not b.smashed and b.poisoned)
    a.flora.set_poisoned(b, False)

    # 3 --------------------------------------------------------- a resting Red Giant does not stop sleep
    a.hour = 22.0
    a._apply_time(force=True)
    put(a.human, a, hp.x, hp.y)
    put(a.giant, a, hp.x + 8.0, hp.y)
    put(a.red_giant, a, hp.x + 80.0, hp.y)
    a.red_energy = 0.1
    tick(a, 0.3)
    ok_rest, why_rest = a.can_sleep()
    a.red_resting = False
    a.red_energy = 1.0
    a.red_state = 'pursue'
    ok_hunt, _ = a.can_sleep()
    check('3  you can sleep with a resting Red Giant 80 m off, not with a hunting one', ok_rest and not ok_hunt, why_rest)
    put(a.red_giant, a, hp.x + 3000.0, hp.y)
    a.red_state = 'idle'

    # 4 --------------------------------------------------------- branches eaten out of sight stay out of the frame loop
    far = Point3(hp.x + 900.0, hp.y + 900.0, 0.0)
    for cx in range(int(far.x // 72) - 1, int(far.x // 72) + 2):
        for cy in range(int(far.y // 72) - 1, int(far.y // 72) + 2):
            a.flora._cell_plants(cx, cy)
    fb = next((x for x in a.flora.branches_near(far, 150.0) if not x.smashed and x.pid not in a.flora.active), None)
    n_active = len(a.flora.active)
    if fb is not None:
        a.flora.smash(fb, crumbs=2)
    check('4  a branch eaten far from you does not join the per-frame set', fb is not None and fb.smashed
          and len(a.flora.active) == n_active and fb.pid not in a.flora.active)

    # 5 --------------------------------------------------------- no per-frame scans of every branch ever grown
    for i in range(900):                                     # a long, wide journey remembered
        for j in range(5):
            a.flora._cell_plants(1000 + i, 1000 + j)
    total = len(a.flora.branches)
    rp = a.red_giant.getPos()
    a._forage_pick = None
    t0 = time.perf_counter()
    for _ in range(200):
        a._forage_look = 0.0
        a._forage_target(rp, 1 / 60)
        a.current_bait()
    per = (time.perf_counter() - t0) / 200 * 1000.0
    check('5  looking for food / bait costs the same however far you have walked', per < 0.5,
          f'{per:.3f} ms per frame with {total} branches remembered')

    # 6 --------------------------------------------------------- pale scraps no longer take over E
    b = fresh_branch(a, a.human.getPos())
    put(a.human, a, b.pos.x + 1.0, b.pos.y)
    a.bag('human')['bane'] = 2
    kind, _ = a._e_target()
    check('6  carrying pale scraps, E beside a branch still smashes; X poisons', kind == 'smash'
          and a.poison_prompt() is not None, kind)
    a.bag('human')['bane'] = 0

    # 7 --------------------------------------------------------- no false "wakes furious"
    a.hour = 22.0
    a._apply_time(force=True)
    hp = a.human.getPos()
    put(a.red_giant, a, hp.x + 12.0, hp.y)
    a.red_state = 'pursue'
    a.red_energy = 0.1
    a.red_woken_t = 0.0
    said = []
    orig = a.say
    a.say = lambda text, seconds=4.0: said.append(text)
    tick(a, 0.5)
    a.say = orig
    check('7  running out of energy mid-chase close to you is not "waking furious"',
          not any('wakes' in t for t in said) and a.red_woken_t == 0.0)
    put(a.red_giant, a, hp.x + 3000.0, hp.y)
    a.red_state = 'idle'
    a.red_energy = 1.0

    # 9 --------------------------------------------------------- journal fits its page
    a.lore_log = ['The Skull of the Quiet Brother.  Something the size of Indigo died here, long before the sand came.'] * 3 \
        + ['Scratched into a hut: the red one bent over a blood branch, eating. Beside it a pale flower, and the red one '
           'lying down. The flower is drawn far away, ahead and to the left.'] * 4
    a.toggle_panel('journal')
    bottoms = []
    for tn in a.panel.findAllMatches('**/+TextNode'):
        bounds = tn.getTightBounds(a.panel)
        if bounds:
            bottoms.append(bounds[0].z)
    a.close_panel()
    check('9  the journal never runs off its page', bottoms and min(bottoms) > -0.62, f'lowest text {min(bottoms):.2f}')

    # 10 -------------------------------------------------------- help and prompts
    a.toggle_panel('help')
    texts = [tn.node().getText() for tn in a.panel.findAllMatches('**/+TextNode') if isinstance(tn.node(), TextNode)]
    a.close_panel()
    check('10 F1 help lists sleeping by Indigo, scraps as food and the poison key',
          any('by Nyx' in t for t in texts) and any('scraps' in t for t in texts) and any('poison' in t for t in texts))
    a.bag('human').clear()
    a.bag('giant').clear()
    a.water_sips = 2
    a.heat = 0.0
    a.chill = 80.0
    prompt, _ = a._prompt_and_progress()
    check('10b cold with only water sips, G is not offered (sips only cool you)', 'eat' not in prompt, prompt)
    a.water_sips = 0
    a.chill = 0.0

    # balance ---------------------------------------------------- tracking speed
    a.hour = 12.0
    a._apply_time(force=True)
    a.red_hunger = 0.0
    hp = a.human.getPos()
    a.trail.clear()
    for k in range(40):
        a._trail_serial += 1
        a.trail.append((a._trail_serial, hp.x, hp.y - 600.0 + k * 10.0))
    a.red_trail_serial = None
    put(a.red_giant, a, hp.x, hp.y - 600.0)
    tick(a, 2.0)                       # Pass 60: up to its tracking pace first (it may start from a standstill)
    p0 = a.red_giant.getPos()
    tick(a, 10.0)
    speed = (a.red_giant.getPos() - p0).length() / 10.0
    check('balance: following tracks it is faster than your walk, slower than your jog',
          game.HUMAN_WALK_SPEED < speed < game.HUMAN_JOG_SPEED, f'{speed:.2f} m/s (energy {a.red_energy:.2f}, state {a.red_state})')

    # 8 --------------------------------------------------------- saved mid last-meal, and clues/rage survive a load
    put(a.red_giant, a, hp.x + 3000.0, hp.y)
    b = fresh_branch(a, a.human.getPos())
    a.flora.set_poisoned(b)
    a.red_eating = {'phase': 'sicken', 't': 0.5, 'branch': b, 'taken': True}
    e = fresh_branch(a, a.human.getPos())
    a.flora.smash(e, crumbs=2)
    e.eaten_at = a.flora.time - 30.0
    a.red_woken_t = 42.0
    a.save_game('check')
    a.persist = False
    a.destroy()
    d = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, persist=True, save_dir=TMP)
    ended = 'Crimson ate the pale branch and lay down, and did not get up.'
    db = d.flora.branches.get(b.pid)
    de = d.flora.branches.get(e.pid)
    check('8  saved during its last meal: it is dead, the journal says so, the branch is eaten',
          d.red_dead and ended in d.lore_log and db is not None and db.smashed and not db.poisoned)
    check('8b an eaten stump stays a clue, and its rage lasts, after a load',
          de is not None and de.eaten_at is not None and abs((d.flora.time - de.eaten_at) - 30.0) < 1.0
          and abs(d.red_woken_t - 42.0) < 0.2)

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
