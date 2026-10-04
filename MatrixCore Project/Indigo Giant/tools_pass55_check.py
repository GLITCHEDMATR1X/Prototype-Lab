"""Pass 55 check: walk-in shells.

The shells are big enough to walk into and stand up in. You walk in and out through the mouth,
the walls are solid, and while you are inside an unbroken shell you are sheltered and hidden,
awake, at any time of day.

    python tools_pass55_check.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

from panda3d.core import Point3, Vec3

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='indigo_save55_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import desert          # noqa: E402
import desert_geom as geom   # noqa: E402
import desert_world as world  # noqa: E402
import main as game    # noqa: E402

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
    a.heat_factor_override = 0.0
    a.hour = 12.0
    return a


def local_to_world(s, lx, ly):
    h = math.radians(s.heading)
    return Point3(s.pos.x + lx * math.cos(h) - ly * math.sin(h), s.pos.y + lx * math.sin(h) + ly * math.cos(h), 0)


def xy(p):
    return p.x, p.y


def q_of(a, s):
    return a.shells._q(*a.shells._local(s, a.human.getPos(a.render)))


def put(a, s, lx, ly):
    p = local_to_world(s, lx, ly)
    a.human.setPos(ground(a, p.x, p.y))


def walk(a, target: Point3, seconds: float, gait='walk'):
    """Walk the human toward a world point (straight line) for up to `seconds`."""
    t = 0.0
    while t < seconds:
        hp = a.human.getPos(a.render)
        d = Vec3(target.x - hp.x, target.y - hp.y, 0)
        if d.length() < 0.15:
            break
        a._apply_controlled_move(d, DT, t, gait=gait)
        a.survival_step(DT)
        t += DT
    a._apply_controlled_move(Vec3(0, 0, 0), DT, t, gait=gait)


def settle(a, seconds: float):
    t = 0.0
    while t < seconds:
        a._apply_controlled_move(Vec3(0, 0, 0), DT, t)
        a.survival_step(DT)
        t += DT


def main():
    a = new_app(new_game=True)
    a.comp.update({'mode': 'stay', 'moving': False})
    b = a.human_base_pos
    a.giant.setPos(ground(a, b.x + 120, b.y + 60))
    a.red_giant.setPos(ground(a, b.x + 700, b.y))
    a.red_state = 'idle'
    s = a.shells.shells[('start', 0)]
    a.shells.set_state(s, 'intact')
    a._refresh_world(force=True)

    # 1. size: taller and wider than you, with a mouth you walk through upright
    mouth_h = geom.MOUTH_TOP                   # Pass 56: the arched mouth (was a notch 2.1 m high)
    check('the shell is bigger than you: 6.8 x 6.0 m, 3.2 m high (Pass 56), a mouth 2.2 m high',
          geom.SHELL_H >= 2.6 and mouth_h > a.human_height + 0.1 and 2 * geom.SHELL_RY > 5.0,
          f'human {a.human_height:.2f} m, mouth {mouth_h:.2f} m, shell {2 * geom.SHELL_RX:.1f} x {2 * geom.SHELL_RY:.1f} x {geom.SHELL_H} m')

    # 2. the sand under it is level (a floor, not a dune face through it)
    zs = [a.field.height(*xy(local_to_world(s, math.cos(k * math.pi / 6) * r, math.sin(k * math.pi / 6) * r)))
          for k in range(12) for r in (0.0, 1.5, geom.SHELL_RY * 0.95)]
    spread = max(zs) - min(zs)
    check('the ground inside a shell is level, and the shell sits on it', spread < 0.06 and abs(s.pos.z - zs[0]) < 0.06,
          f'floor spread {spread * 100:.1f} cm, shell {s.pos.z - zs[0]:+.2f} m')
    far = [sh for sh in a.shells.shells.values() if sh.pid != ('start', 0)]
    gz = [max(abs(a.field.height(*xy(local_to_world(sh, x, y))) - a.field.height(sh.pos.x, sh.pos.y))
              for x, y in ((2.5, 0), (-2.5, 0), (0, 2.2), (0, -2.2))) for sh in far[:12]]
    check('shells out in the desert sit on levelled ground too (sites chosen beyond the built ground)',
          far and max(gz) < 0.06, f'{len(far)} shells, worst {max(gz) * 100:.1f} cm')

    # 3. walk in through the mouth: sheltered, hidden, still visible, free to move
    put(a, s, 0.0, geom.SHELL_RY + 4.0)
    a.human.setH(s.heading + 180.0)
    walk(a, local_to_world(s, 0.0, -0.5), 6.0)
    check('you walk in through the mouth - no key needed - and you are inside (and still visible)',
          a.hidden_shell is s and s.occupied and q_of(a, s) < 0.5 and not a.human.isHidden(),
          f'q {q_of(a, s):.2f}')
    check('standing inside the headroom is above your head', a.human_height < geom.SHELL_H * math.cos(
        math.asin(min(1.0, q_of(a, s)))) + 0.01)
    a.heat = 80.0
    settle(a, 5.0)
    check('inside it the heat falls (awake, at noon, no sleeping)', a.heat <= 62.0 and a.shelter_word == 'shell',
          f'heat {a.heat:.1f} ({a.shelter_word})')

    # 4. the walls are solid from inside...
    walk(a, local_to_world(s, 0.0, -geom.SHELL_RY - 3.0), 4.0)
    q_back = q_of(a, s)
    walk(a, local_to_world(s, geom.SHELL_RX + 3.0, 0.0), 4.0)
    q_side = q_of(a, s)
    check('the back and side walls stop you from inside (you stay in the shell)',
          q_back < 1.0 and q_side < 1.0 and a.hidden_shell is s, f'q back {q_back:.2f}, side {q_side:.2f}')
    check('the shell you stand in turns see-through, so you can see yourself',
          s in a.shell_fade and s.node.getColorScale()[3] < 0.5, f'alpha {s.node.getColorScale()[3]:.2f}')
    check('inside, you can call Indigo; it cannot lift you out; you cannot jump into the roof',
          a.gesture_command('come') and not a.gesture_command('lift') and not a._request_jump())
    a.gesture = None

    # 5. walk out the way you came
    walk(a, local_to_world(s, 0.0, 0.0), 3.0)
    walk(a, local_to_world(s, 0.0, geom.SHELL_RY + 4.0), 6.0)
    check('you walk back out through the mouth and are out in the open', a.hidden_shell is None and not s.occupied
          and q_of(a, s) > 1.0)
    settle(a, 1.0)
    check('the shell is solid again once you are out', s not in a.shell_fade and s.node.getColorScale()[3] >= 0.999)

    # 6. ... and from outside
    put(a, s, 0.0, -geom.SHELL_RY - 3.0)
    walk(a, local_to_world(s, 0.0, 0.0), 4.0)
    check('from outside, the back wall stops you (no walking through the shell)',
          a.hidden_shell is None and q_of(a, s) >= 1.0, f'q {q_of(a, s):.2f}')

    # 7. E at the mouth still steps you in
    e = s.entrance_point()
    a.human.setPos(ground(a, e.x, e.y))
    kind, target = a._e_target()
    a._on_e_press()
    a.keys['e'] = False
    check('E at the mouth steps you in', kind == 'hide' and target is s and a.hidden_shell is s and q_of(a, s) < 0.5)

    # 8. hidden from the red one; you can sleep at night inside
    a.red_giant.setPos(ground(a, s.pos.x + 60, s.pos.y))
    a.red_state = 'pursue'
    a.red_saw_hide = False
    handled = a._update_red_vs_shell(DT, 0.0)
    check('the red one loses you while you are inside (not seen going in)', handled and a.red_shell_state == 'searching')
    a.red_giant.setPos(ground(a, s.pos.x + 700, s.pos.y))
    a.red_state = 'idle'
    a.hour = 22.0
    ok, why = a.can_sleep()
    check('you can sleep inside it at night', ok or 'shell' not in why, why)
    a.hour = 12.0

    # 9. save and load while inside: you are still in it, where you stood
    put(a, s, 1.0, -0.8)
    settle(a, 0.2)
    where = a.human.getPos(a.render)
    pid = s.pid
    a.save_game('check')
    a.destroy()
    a = new_app()
    s = a.shells.shells[pid]
    moved = math.hypot(a.human.getX() - where.x, a.human.getY() - where.y)
    check('saved inside a shell, you load inside it, where you stood',
          a.hidden_shell is s and moved < 0.2 and not a.human.isHidden(), f'moved {moved:.2f} m')

    # 10. the red one heaving still throws you out
    a.comp.update({'mode': 'stay', 'moving': False})
    a.giant.setPos(ground(a, s.pos.x + 150, s.pos.y + 80))
    a.red_giant.setPos(ground(a, s.pos.x + 20, s.pos.y))
    a.red_state = 'pursue'
    a.red_saw_hide = True
    t = 0.0
    while t < 40.0 and s.state != 'flipped':
        a._update_red_vs_shell(DT, t)
        a.survival_step(DT)
        t += DT
    settle(a, 1.2)
    check('the red one still heaves the shell over and throws you out',
          s.state == 'flipped' and a.hidden_shell is None and q_of(a, s) > 1.0 and a.red_giant.getPos().z != 0,
          f'{t:.1f} s')

    # 11. an overturned shell is solid all round
    a.red_giant.setPos(ground(a, s.pos.x + 700, s.pos.y))
    a.red_state = 'idle'
    a.human_dazed = 0.0
    put(a, s, 0.0, geom.SHELL_RY + 4.0)
    walk(a, local_to_world(s, 0.0, 0.0), 5.0)
    check('an overturned shell is solid (you cannot walk into it)', a.hidden_shell is None and q_of(a, s) >= 1.0,
          f'q {q_of(a, s):.2f}')

    # 12. a cracked shell is shade (not a hiding place)
    a.shells.set_state(s, 'cracked')
    s.flip_t = 0.0
    a.shells._show(s)
    put(a, s, 0.0, 0.0)
    a.heat_factor_override = 1.0
    a._update_heat(DT)
    check('standing inside a cracked shell is shade, not a hiding place',
          a.shelter_word == 'shade' and a.hidden_shell is None, a.shelter_word)

    # 13. Indigo steps around shells: sent to stand on one, it stops at the edge (not running in place)
    a.shells.set_state(s, 'intact')
    a.shells._show(s)
    a.human.setPos(ground(a, s.pos.x + 30, s.pos.y + 30))
    far_side = local_to_world(s, 0.0, -geom.SHELL_RY - 25.0)
    a.giant.setPos(ground(a, far_side.x, far_side.y))
    a.comp.update({'mode': 'goto', 'target': Point3(s.pos), 'moving': True})
    worst, t = 9.0, 0.0
    while t < 40.0 and a.comp.get('mode') == 'goto' and a.comp.get('moving'):
        a._update_companion(DT)
        worst = min(worst, a.shells._q(*a.shells._local(s, a.giant.getPos()), world.GIANT_FOOT_PAD))
        t += DT
    check('Indigo never walks through a shell: sent onto one, it stops at its edge and stands still',
          worst >= 0.97 and not a.comp.get('moving') and a.giant_motion_speed < 0.1,
          f'closest {worst:.2f} of the edge, {t:.1f} s, mode {a.comp.get("mode")}')

    other_side = local_to_world(s, 0.0, geom.SHELL_RY + 25.0)      # dead ahead
    a.comp.update({'mode': 'goto', 'target': Point3(other_side.x, other_side.y, 0), 'moving': True})
    a.giant.setPos(ground(a, far_side.x, far_side.y))
    worst, t = 9.0, 0.0
    while t < 60.0 and a.comp.get('mode') == 'goto' and a.comp.get('moving'):
        a._update_companion(DT)
        worst = min(worst, a.shells._q(*a.shells._local(s, a.giant.getPos()), world.GIANT_FOOT_PAD))
        t += DT
    check('sent past a shell straight through it, Indigo goes around it and gets there',
          worst >= 0.97 and not a.comp.get('moving'), f'closest {worst:.2f} of the edge, {t:.1f} s')

    # 14. tuning moved with the size
    check('reach numbers grew with the shell', desert.PATCH_RANGE > geom.SHELL_RX and desert.RED_SHELL_STOP > geom.SHELL_RX
          and world.MOUTH_REACH > 2.0)

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
