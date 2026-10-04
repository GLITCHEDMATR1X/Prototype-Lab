"""Pass 47 check: a wider, emptier world with more kinds of places, and the only ending -
the pale bloom, a poisoned blood branch, and the Red Giant's last meal.

    python .dev/checks/pass47.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

from panda3d.core import Point3

HERE = Path(__file__).resolve().parents[2]          # Pass 62: the game folder
TMP = Path(tempfile.mkdtemp(prefix='indigo_save47_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import sys as _sys                                  # Pass 62: the game folder is two levels up
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from indigo_giant import endgame        # noqa: E402
from indigo_giant import flora          # noqa: E402
from indigo_giant import app as game   # noqa: E402
from indigo_giant import places         # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
CLOCK = [0.0]


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def go(a, x, y, red_far=True):
    a.human.setPos(ground(a, x, y))
    a.giant.setPos(ground(a, x + 25, y - 20))
    if red_far:
        a.red_giant.setPos(ground(a, x + 3000, y))
        a.red_state = 'idle'
    a.cam_target = a._controlled_focus()
    a._refresh_world(force=True)
    a._update_stream(force=True)
    a.drain_stream_queue()
    a._refresh_world(force=True)


def tick(a, seconds, dt=1 / 30.0, until=None):
    for i in range(int(seconds / dt)):
        CLOCK[0] += dt
        a._update_red_giant(dt, CLOCK[0])
        a.survival_step(dt)
        if until is not None and until():
            return (i + 1) * dt
    return None


def main():
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, new_game=True, persist=True, save_dir=TMP)
    a.time_frozen = True
    a.heat_factor_override = 0.0
    pf = a.places
    start = Point3(a.human_base_pos)

    # ------------------------------------------------------------ a wider world
    for R in range(0, 9001, 900):
        for ang in range(0, 360, 20):
            pf.update(Point3(start.x + R * math.cos(math.radians(ang)), start.y + R * math.sin(math.radians(ang)), 0))
    kinds = {p.kind for p in pf.places.values()}
    new = {'tree', 'nest', 'tower', 'saltflat', 'totems', 'bones'}
    check('six new kinds of place stand in the world', new <= kinds, f'{len(kinds)} kinds, {len(pf.places)} places')
    pts = [p.pos for p in pf.places.values()]
    gaps = sorted(min(math.hypot(p.x - q.x, p.y - q.y) for q in pts if q is not p) for p in pts)
    median = gaps[len(gaps) // 2]
    check('places lie far apart (exploring between them)', median >= 480.0, f'median gap {median:.0f} m')
    fx, fy, fcell = pf._first_bloom()
    first = pf.places.get(fcell)
    d0 = math.hypot(fx - start.x, fy - start.y)
    blooms = [p for p in pf.places.values() if p.kind == 'bloom']
    check('one pale bloom always grows far out (6.5 km); a few more, very rarely, farther',
          first is not None and first.kind == 'bloom' and abs(d0 - places.FIRST_BLOOM_DIST) < 1.0
          and 1 <= len(blooms) <= 12, f'{len(blooms)} blooms within 9 km, first {d0:.0f} m out')

    # ------------------------------------------------------------ the desert points the way
    camp = min((p for p in pf.places.values() if p.kind == 'camp'            # Pass 51: only far camps know
                and math.hypot(p.pos.x - start.x, p.pos.y - start.y) >= places.RUMOUR_COMMON_MIN),
               key=lambda p: math.hypot(p.pos.x - start.x, p.pos.y - start.y))
    go(a, camp.pos.x + camp.radius + 10, camp.pos.y)
    hint = getattr(a, 'bloom_hint', None)
    near_bloom = pf.bloom_near(camp.pos)
    check('a camp scratches a pale flower and points toward the nearest bloom',
          camp.found and hint is not None and near_bloom is not None
          and math.hypot(hint[0] - near_bloom[0], hint[1] - near_bloom[1])            # Pass 51: roughly right
          <= places.RUMOUR_VAGUE * math.hypot(near_bloom[0] - camp.pos.x, near_bloom[1] - camp.pos.y) + 1.0
          and 'pale flower' in a.lore_log[-1] and a.notice is not None, a.bloom_words())

    # ------------------------------------------------------------ tear up the bloom
    go(a, first.pos.x + first.radius + 60.0, first.pos.y)
    sensed = first.sensed
    a.human.setPos(ground(a, first.pos.x + first.radius + 1.0, first.pos.y))
    a._refresh_world(force=True)
    a.bag('human').clear()
    kind, target = a._e_target()
    ok = kind == 'uproot' and target is first
    a._complete_e(kind, target)
    kind2, _ = a._e_target()
    check('the pale bloom can be torn up once: 3 pale scraps', ok and a.pooled_count('bane') == places.BLOOM_SCRAPS
          and first.searched and kind2 != 'uproot', f'bane {a.pooled_count("bane")}, Indigo sensed it first: {sensed}')
    a._refresh_world(force=True)
    check('where it grew, only a torn stub remains', first.node is not None and a.bloom_words().startswith('you carry'))

    # ------------------------------------------------------------ poison a blood branch
    b = next(br for br in a.flora.active.values() if not br.smashed and br.grow >= 1.0 and br.node is not None)
    go(a, b.pos.x + 1.0, b.pos.y)
    a.human.setPos(ground(a, b.pos.x + 1.0, b.pos.y))
    kind, target = a._e_target()
    offered = a.poison_prompt() is not None and a.poison_target() is b
    a._on_poison_press()                                     # Pass 49: X - its own key
    tick(a, endgame.POISON_TIME + 0.2)
    check('with pale scraps, X at a blood branch poisons it (E still smashes)',
          offered and kind == 'smash' and b.poisoned, kind)
    a.human_health = 50.0
    healed = a.flora.heal_amount(a.human.getPos(), flora.SMASH_RANGE_HUMAN + 2.0, 10.0, 1.0, 50.0)
    check('the branch turns pale and no longer heals', b.poisoned and a.pooled_count('bane') == places.BLOOM_SCRAPS - 1
          and healed == 0.0)

    # ------------------------------------------------------------ save while it waits: the poison is kept
    snap = a.snapshot()
    rec = next((r for r in snap['world']['branches'] if r['pid'] == repr(b.pid)), None)
    check('a poisoned branch, the pale scraps and the uprooted bloom are saved',
          rec is not None and rec['poisoned'] and (snap['players'][0]['bag'].get('bane', 0)
                                                   + snap['giant']['bag'].get('bane', 0)) == places.BLOOM_SCRAPS - 1
          and repr(first.pid) in snap['world']['places']['searched'])

    # ------------------------------------------------------------ the Red Giant's last meal
    a.human.setPos(ground(a, b.pos.x + 25.0, b.pos.y + 25.0))
    a.giant.setPos(ground(a, b.pos.x + 40.0, b.pos.y + 10.0))
    a.red_giant.setPos(ground(a, b.pos.x - 2600.0, b.pos.y))
    a.red_lurking = True                                     # even lurking far off, it smells it
    a.red_state = 'lurk'
    tick(a, 0.2)
    rd = math.hypot(a.red_giant.getX() - b.pos.x, a.red_giant.getY() - b.pos.y)
    check('from far away it smells the branch and comes (it stops hunting you)',
          a.red_state == 'bait' and not a.red_lurking and rd <= endgame.RED_BAIT_FAR + 10.0, f'{rd:.0f} m from the branch')
    t = tick(a, 180.0, until=lambda: a.red_eating is not None)
    check('it walks to the branch and kneels to eat', t is not None and not a.indigo_defending, f'{t or 0:.0f} s')
    tick(a, 2.0)
    check('it tears the branch up and eats it', b.smashed and not b.poisoned)
    tick(a, 12.0, until=lambda: a.red_dead)
    check('...and does not get up again', a.red_dead and not a.red_alive and a.red_state == 'dead')
    tick(a, 5.0)
    check('the ending begins: Gleebs comes (Pass 61 - no card yet; the world goes on)',
          a.ending_shown and a.gleebs_state == 'arriving' and not a.paused)
    check('keep walking: the game goes on', not a.paused and a.panel_name is None)
    tick(a, 20.0)
    check('it never gets up (no knock-out timer, no hunting)', a.red_dead and a.red_state == 'dead')
    a._down_human()
    a._retry_after_human_down()
    check('waking after a collapse does not bring it back', a.red_dead and not a.red_alive)
    check('the journal says so', 'sleeps' in a.bloom_words())

    # ------------------------------------------------------------ saved for good
    pos = a.red_giant.getPos()
    a.save_game('check')
    a.persist = False
    a.destroy()
    d = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, persist=True, save_dir=TMP)
    d.time_frozen = True
    tick(d, 6.0)
    check('the ending is saved: it lies where it fell, and the card does not show again',
          d.red_dead and (d.red_giant.getPos() - pos).length() < 1.0 and d.ending_shown and d.panel_name != 'ending')

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
