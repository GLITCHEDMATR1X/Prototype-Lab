"""Pass 48 check: living giants - the Red Giant follows your tracks, gets hungry, plucks blood
branches (leaving crumbs as clues), is sneaky or aggressive by mood; the cold night drains
both giants; you keep warm against Indigo and can sleep beside it; blood scraps are food.

    python tools_pass48_check.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

from panda3d.core import Point3, Vec3

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='indigo_save48_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import main as game   # noqa: E402
import wild           # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
CLOCK = [0.0]


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def put(node, a, x, y, sink=0.0):
    node.setPos(x, y, a.field.height(x, y) - sink)


def tick(a, seconds, dt=1 / 30.0, move=None, until=None, companion=True):
    for i in range(int(seconds / dt)):
        CLOCK[0] += dt
        t = CLOCK[0]
        if move is not None and a.controlled_name == 'human':
            a._apply_controlled_move(move, dt, t)
        if companion:
            a._update_companion(dt)
        a._update_red_giant(dt, t)
        a.survival_step(dt)
        if until is not None and until():
            return (i + 1) * dt
    return None


def dist(a, n1, n2):
    p, q = n1.getPos(a.render), n2.getPos(a.render)
    return math.hypot(p.x - q.x, p.y - q.y)


def main():
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, new_game=True, persist=True, save_dir=TMP)
    a.time_frozen = True
    a.heat_factor_override = 0.0
    a.hour = 10.0
    a._apply_time(force=True)
    hp0 = a.human.getPos()

    # ------------------------------------------------------------ your trail, and the Red Giant on it
    a.red_hunger = 0.0
    put(a.red_giant, a, hp0.x - 400.0, hp0.y)
    a.red_state = 'idle'
    a.heading = 0.0                                              # walk +Y
    tick(a, 40.0, move=Vec3(0, 1, 0))
    walked = len(a.trail)
    check('walking leaves a trail (a breadcrumb every 10 m)', walked >= 4, f'{walked} breadcrumbs')
    before = dist(a, a.red_giant, a.human)
    tick(a, 30.0)
    after = dist(a, a.red_giant, a.human)
    check('with nothing to do, the Red Giant follows your tracks', a.red_state in ('track', 'pursue', 'watching')
          and after < before - 50.0, f'{before:.0f} m -> {after:.0f} m, {a.red_state}')

    # ------------------------------------------------------------ hunger: plucking a blood branch
    hp = a.human.getPos()
    b = next(br for br in a.flora.branches.values() if not br.smashed and br.grow >= 1.0)
    put(a.human, a, b.pos.x + 200.0, b.pos.y)
    put(a.red_giant, a, b.pos.x - 60.0, b.pos.y)
    a.flora.update_active(b.pos)
    a.red_hunger = 0.8
    a.red_state = 'idle'
    scraps_before = len(a.flora.scraps)

    def eaten():
        return [br for br in a.flora.branches.values() if br.eaten_at is not None]

    t = tick(a, 90.0, until=lambda: eaten() and a.red_meal is None)
    crumbs = len(a.flora.scraps) - scraps_before
    meal = eaten()[0] if eaten() else b
    check('hungry, it plucks a blood branch and eats it, leaving a few crumbs',
          t is not None and meal.smashed and 1 <= crumbs <= 3 and a.red_hunger < 0.5,
          f'{t or 0:.0f} s, {crumbs} crumbs, hunger {a.red_hunger:.2f}')
    b = meal
    put(a.red_giant, a, b.pos.x - 300.0, b.pos.y + 200.0)
    put(a.human, a, b.pos.x + 3.0, b.pos.y)
    a.say('', 0.1)
    tick(a, 0.2)
    check('the torn stump is a clue: how long ago, and which way it went',
          'ate here' in a.lore_text.getText() and 'moments ago' in a.lore_text.getText(), a.lore_text.getText()[:70])

    # ------------------------------------------------------------ moods
    a.red_hunger, a.red_anger, a.red_woken_t = 0.2, 0, 0.0
    sneaky_range = a.red_detection_range()
    mood_calm = a.red_mood()
    a.red_hunger = 0.9
    check('fed and calm it is sneaky; hungry it turns aggressive and sees farther',
          mood_calm == 'sneaky' and a.red_mood() == 'aggressive' and a.red_detection_range() > sneaky_range * 1.2,
          f'{sneaky_range:.0f} m -> {a.red_detection_range():.0f} m')
    a.red_hunger = 0.2
    hp = a.human.getPos()
    put(a.red_giant, a, hp.x, hp.y + 90.0)
    a.red_state = 'idle'
    a.heading = 0.0                                              # looking straight at it
    a.cam_target = a._controlled_focus()
    a._place_camera(immediate=True)
    p0 = a.red_giant.getPos()
    tick(a, 3.0, companion=False)
    frozen = (a.red_giant.getPos() - p0).length()
    watched_state = a.red_state
    a.heading = 180.0                                            # look away
    a._place_camera(immediate=True)
    p1 = a.red_giant.getPos()
    tick(a, 3.0, companion=False)
    crept = (a.red_giant.getPos() - p1).length()
    check('sneaky: it stands still while you watch it, and creeps closer when you look away',
          frozen < 1.0 and watched_state == 'watching' and crept > 3.0, f'moved {frozen:.1f} m watched, {crept:.1f} m unwatched')
    a.red_hunger = 0.9
    p2 = a.red_giant.getPos()
    a.heading = 0.0
    a._place_camera(immediate=True)
    put(a.red_giant, a, hp.x, hp.y + 90.0)
    p2 = a.red_giant.getPos()
    tick(a, 3.0, companion=False)
    rushed = (a.red_giant.getPos() - p2).length()
    check('aggressive: it comes at you even while you watch it', rushed > crept, f'{rushed:.1f} m in 3 s')
    a.red_hunger = 0.2
    put(a.red_giant, a, hp.x + 3000.0, hp.y)
    a.red_state = 'idle'

    # ------------------------------------------------------------ the cold night
    a.hour = 22.0
    a._apply_time(force=True)
    a.giant_energy = a.red_energy = 1.0
    day_pace = (0.55 + 0.45 * 1.0)
    tick(a, 60.0, companion=False)
    check('at night both giants lose energy and slow down',
          # Pass 59: Indigo's night glow halves its drain (a minute: 1.0 -> 0.85)
          a.giant_energy < 0.9 and a.red_energy < 0.8 and a.giant_pace() < day_pace * 0.95 and a.red_pace() < day_pace * 0.95,
          f'Indigo {a.giant_energy:.2f}, red {a.red_energy:.2f}')
    a.red_energy = 0.1
    hp = a.human.getPos()
    put(a.red_giant, a, hp.x + 120.0, hp.y)
    tick(a, 1.0, companion=False)
    resting = a.red_resting and a.red_state == 'rest'
    put(a.human, a, a.red_giant.getX() - 10.0, a.red_giant.getY())
    tick(a, 0.5, companion=False)
    check('spent, the Red Giant hunches down to rest - walk up to it and it wakes, furious',
          resting and not a.red_resting and a.red_mood() == 'aggressive')
    put(a.red_giant, a, hp.x + 3000.0, hp.y)
    a.red_woken_t = 0.0
    a.red_state = 'idle'
    a.red_energy = 1.0

    a.giant_energy = 0.1
    a.comp.update({'mode': 'follow', 'phase': '', 'moving': False})
    put(a.giant, a, a.human.getX() + 60.0, a.human.getY())
    tick(a, 2.0)
    check('Indigo, spent in the cold, hunches down and waits for dawn', a.indigo_resting
          and 'cold' in a._companion_word())
    a.bag('giant')['scraps'] = 3
    a._indigo_eat_t = 0.0
    tick(a, 0.2)
    check('Indigo eats a blood scrap from its bag when tired', a.bag('giant')['scraps'] == 2 and a.giant_energy > 0.3)

    # you: cold away from Indigo, warm beside it
    a.comp.update({'mode': 'stay', 'moving': False})           # Indigo waits where it is
    a.chill = 0.0
    put(a.giant, a, a.human.getX() + 80.0, a.human.getY())
    tick(a, 30.0, companion=False)
    alone = a.chill
    put(a.giant, a, a.human.getX() + 8.0, a.human.getY())
    tick(a, 5.0, companion=False)
    check('at night you get cold alone, and warm up close to Indigo',
          alone > 15.0 and a.chill <= alone * 0.25,
          f'{alone:.0f} -> {a.chill:.0f}')
    a.chill = wild.CHILL_MAX
    put(a.giant, a, a.human.getX() + 80.0, a.human.getY())
    life = a.human_health
    tick(a, 3.0, companion=False)
    check('frozen through, you lose life', a.human_health < life - 1.0)
    a.human_health = 100.0
    a.chill = 30.0
    a.bag('human').clear()
    a.bag('giant').clear()
    a.bag('human')['scraps'] = 2
    a.human_health = 70.0
    ate = a.eat()
    check('blood scraps are food: life back and a little warmth', ate == 'scraps' and a.human_health > 70.0
          and a.chill < 30.0 and a.bag('human')['scraps'] == 1)

    # sleep curled against Indigo
    put(a.giant, a, a.human.getX() + 8.0, a.human.getY())
    a.hidden_shell = None
    camp = a.camp_shell
    ok, why = a.can_sleep()
    day = a.day
    a.chill = 50.0
    a.giant_energy = 0.2
    if ok:
        a._do_sleep()
    check('at night you can sleep curled against Indigo (no shell), and wake warm',
          ok and a.day == day + 1 and a.chill == 0.0 and a.giant_energy == 1.0 and a.camp_shell is camp, why)
    put(a.giant, a, a.human.getX() + 80.0, a.human.getY())
    a.hour = 22.0
    ok2, why2 = a.can_sleep()
    check('...but not alone in the open', not ok2 and 'Nyx' in why2, why2)

    # ------------------------------------------------------------ blood branches: the one common plant
    cells = 400
    grown = sum(1 for cx in range(20) for cy in range(20) if a.flora._cell_plants(cx + 500, cy + 500))
    check('blood branches are common (the one plant both giants eat)', grown / cells >= 0.3, f'{grown}/{cells} cells')

    # ------------------------------------------------------------ saved
    a.hour = 12.0
    a._apply_time(force=True)
    a.red_hunger, a.red_energy, a.giant_energy, a.chill = 0.66, 0.44, 0.55, 12.0
    trail = len(a.trail)
    a.save_game('check')
    a.persist = False
    a.destroy()
    d = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, persist=True, save_dir=TMP)
    check('hunger, energy, the cold and your trail are saved',
          abs(d.red_hunger - 0.66) < 1e-3 and abs(d.red_energy - 0.44) < 1e-3 and abs(d.giant_energy - 0.55) < 1e-3
          and abs(d.chill - 12.0) < 1e-2 and len(d.trail) == min(trail, 80), f'{len(d.trail)} breadcrumbs')

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
