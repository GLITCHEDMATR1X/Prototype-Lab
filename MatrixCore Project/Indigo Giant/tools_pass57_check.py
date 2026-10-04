"""Pass 57 check: the build review.

  - shells restored by a saved journey keep their levelled sand (it was lost on every load)
  - a shell Indigo sets down gets level sand too; branches and finds there follow the ground
  - doorways: brushing the doorframe near the opening slides you in (and out); inside the
    doorway its sides are walls you slide along, not a push back outside
  - Indigo: goes round to your side of a shell, never reaches in through a roof to lift you,
    never sets you down in a shell's wall

    python tools_pass57_check.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

from panda3d.core import Point3, Vec3

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='indigo_save57_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import desert_geom as geom    # noqa: E402
import desert_world as world  # noqa: E402
import flora                  # noqa: E402
import main as game           # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
DT = 1 / 30.0


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def new_app(**kw):
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, persist=True, save_dir=TMP,
                                       show_title=False, **kw)
    a.time_frozen = True
    a.heat_factor_override = 0.0
    a.hour = 12.0
    a.comp.update({'mode': 'stay', 'moving': False})
    return a


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def floor_spread(a, s):
    zs = []
    for k in range(12):
        for r in (0.0, 1.5, geom.SHELL_RY * 0.95):
            t = 2 * math.pi * k / 12
            zs.append(a.field.height(s.pos.x + math.cos(t) * r, s.pos.y + math.sin(t) * r))
    return max(zs) - min(zs), abs(s.pos.z - a.field.height(s.pos.x, s.pos.y))


def local_to_world(s, lx, ly):
    h = math.radians(s.heading)
    return Point3(s.pos.x + lx * math.cos(h) - ly * math.sin(h), s.pos.y + lx * math.sin(h) + ly * math.cos(h), 0)


def walk(a, goal, seconds):
    t = 0.0
    while t < seconds:
        hp = a.human.getPos(a.render)
        d = Vec3(goal.x - hp.x, goal.y - hp.y, 0)
        if d.length() < 0.15:
            break
        a._apply_controlled_move(d, DT, t, gait='walk')
        t += DT
    a._apply_controlled_move(Vec3(0, 0, 0), DT, t)


def main():
    # 1. a saved journey: shells restored from the save keep their levelled sand
    a = new_app(new_game=True)
    b0 = a.human_base_pos
    far = Point3(b0.x + 1500, b0.y + 400, 0)
    a.shells.update_active(far)                   # the journey went out there: shells were laid out
    out_there = [s for s in a.shells.shells.values() if math.hypot(s.pos.x - far.x, s.pos.y - far.y) < 600]
    a.save_game('check')
    a.destroy()
    a = new_app()
    worst = 0.0
    for s0 in out_there:
        s = a.shells.shells[s0.pid]
        spread, above = floor_spread(a, s)
        worst = max(worst, spread, above)
    check('after loading a journey, shells far from the start still sit on level sand (it was lost on load)',
          out_there and worst < 0.06, f'{len(out_there)} shells, worst {worst * 100:.1f} cm')

    # 2. a shell Indigo sets down on a slope gets level sand; what stands there follows the ground
    b0 = a.human_base_pos
    best = None
    for i in range(400):
        x, y = b0.x + 40 + (i % 20) * 9.0, b0.y - 90 + (i // 20) * 9.0
        sl = world.slope_deg(a.field, x, y)
        if 6.0 < sl < 12.0 and a.shells.nearest(Point3(x, y, 0), 25.0) is None and a.field.is_clear(x, y):
            best = (x, y, sl)
            break
    x, y, sl = best
    shell = a.shells.shells[('start', 0)]
    before = [a.field.height(x + math.cos(t) * 3.0, y + math.sin(t) * 3.0) for t in (0, 1.6, 3.1, 4.7)]
    br = flora.BloodBranch(('check', 1), Point3(x + 6.5, y, a.field.height(x + 6.5, y)), 0, 0.0)
    a.flora.branches[br.pid] = br
    a.flora._spawn(br)
    a.shells.place(shell, Point3(x, y, 0), 30.0)
    a._refresh_world(force=True)
    spread, above = floor_spread(a, shell)
    check(f'a shell set down on a {sl:.0f} deg slope rests on levelled sand (it used to tilt into the dune)',
          spread < 0.06 and above < 0.06 and max(before) - min(before) > 0.3,
          f'the slope rose {max(before) - min(before):.2f} m across it; now {spread * 100:.1f} cm')
    check('a branch beside it follows the new ground (not left floating or buried)',
          abs(br.pos.z - a.field.height(br.pos.x, br.pos.y)) < 0.01 and abs(br.node.getZ() - br.pos.z) < 0.01,
          f'{br.pos.z - a.field.height(br.pos.x, br.pos.y):+.3f} m')
    a.save_game('check')
    a.destroy()
    a = new_app()
    shell = a.shells.shells[('start', 0)]
    spread, above = floor_spread(a, shell)
    check('...and still does after saving and loading', spread < 0.06 and above < 0.06,
          f'{spread * 100:.1f} cm, {above * 100:.1f} cm off the floor')
    a.shells.set_state(shell, 'intact')
    b0 = a.human_base_pos
    a.giant.setPos(ground(a, shell.pos.x + 150, shell.pos.y + 80))
    a.red_giant.setPos(ground(a, shell.pos.x + 700, shell.pos.y))
    a._refresh_world(force=True)
    sf, s = a.shells, shell

    # 3. doorways
    def q_now():
        return sf._q(*sf._local(s, a.human.getPos(a.render)))
    start = local_to_world(s, 0.0, geom.SHELL_RY + 3.0)
    for off_deg, label in ((20.0, 'a little off to one side'), (-24.0, 'well off to the other side')):
        a.human.setPos(ground(a, start.x, start.y))
        t = math.radians(90.0 + off_deg)
        aim = Point3(s.pos.x, s.pos.y, 0) + (local_to_world(s, math.cos(t) * 3.0, math.sin(t) * 3.0) - Point3(s.pos.x, s.pos.y, 0))
        walk(a, aim, 3.0)                              # to the doorframe
        walk(a, local_to_world(s, math.cos(t) * 0.5, math.sin(t) * 0.5 - 0.8), 6.0)
        a._update_shell_presence()
        check(f'walking at the doorframe {label} ({abs(off_deg):.0f} deg), you slide into the doorway and in',
              q_now() < world.ROOM_Q and a.hidden_shell is s, f'q {q_now():.2f}')
    # inside the doorway, walking diagonally: slide along its side, keep going in
    a.human.setPos(ground(a, *(lambda p: (p.x, p.y))(local_to_world(s, 0.0, geom.SHELL_RY * 0.95))))
    walk(a, local_to_world(s, -geom.SHELL_RX, -geom.SHELL_RY * 0.2), 4.0)
    check('in the doorway, walking diagonally slides you along its side and on into the room',
          q_now() <= world.ROOM_Q + 0.01, f'q {q_now():.2f}')
    # from inside, walking out a little off-line: out you go
    a.human.setPos(sf.inner_spot(s))
    walk(a, local_to_world(s, 2.2, geom.SHELL_RY + 4.0), 8.0)
    a._update_shell_presence()
    check('from inside, walking out a little off-line still takes you out through the doorway',
          q_now() > 1.0 and a.hidden_shell is None, f'q {q_now():.2f}')
    # walking along the outside of the wall is not pulled in
    a.human.setPos(ground(a, *(lambda p: (p.x, p.y))(local_to_world(s, -geom.SHELL_RX - 0.6, -1.5))))
    walk(a, local_to_world(s, -geom.SHELL_RX - 0.6, 1.2), 4.0)
    check('walking past the side of a shell does not pull you in', q_now() > 1.0 and a.hidden_shell is None,
          f'q {q_now():.2f}')

    # 4. Indigo and shells
    beside = local_to_world(s, 0.0, -geom.SHELL_RY - 0.6)             # just behind the shell
    a.giant.setPos(ground(a, *(lambda p: (p.x, p.y))(local_to_world(s, 0.0, geom.SHELL_RY + 30.0))))
    goal = sf.clear_point(beside, a.giant.getPos(a.render))
    check('Indigo walks round to your side of a shell (not to its far side)',
          math.hypot(goal.x - beside.x, goal.y - beside.y) < 2.0, f'{math.hypot(goal.x - beside.x, goal.y - beside.y):.1f} m from you')
    a.human.setPos(sf.inner_spot(s))
    a._update_shell_presence()
    a.comp.update({'mode': 'pickup', 'phase': 'approach', 'elapsed': 0.0, 'target': None})
    a._update_pickup(DT, a.human.getPos(a.render))
    check('Indigo will not reach in through the roof to lift you out of a shell',
          a.comp['mode'] == 'stay' and not a.carried)
    a.exit_shell()
    front = local_to_world(s, 0.0, geom.SHELL_RY + 2.0)
    a.giant.setPos(ground(a, front.x, front.y))
    a.giant.setH(game.heading_toward(s.pos.x - front.x, s.pos.y - front.y))
    raw = game.SurvivalMixin._setdown_point(a)
    p = a._setdown_point()
    lx, ly = sf._local(s, p)
    check('Indigo never sets you down inside a shell\'s wall', sf._q(lx, ly, world.BODY_RADIUS) >= 0.999,
          f'it would have been q {sf._q(*sf._local(s, raw)):.2f}; now {sf._q(lx, ly):.2f}')

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
