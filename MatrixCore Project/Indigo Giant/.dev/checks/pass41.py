"""Pass 41 controls check: WASD / diagonals move exactly camera-relative, and the
character faces the way it walks; the Indigo Giant turns toward the pressed direction
(it is heavy, but it must end up going that way); actors are no longer mirrored.

    python .dev/checks/pass41.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from panda3d.core import Vec3

import sys as _sys                                  # Pass 62: the game folder is two levels up
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from indigo_giant import app as game

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def ang(v):
    return math.degrees(math.atan2(v.x, v.y))


def delta(a, b):
    return (b - a + 180.0) % 360.0 - 180.0


def body_forward(a, actor):
    """Facing measured from the skeleton itself (square to the shoulders), not from H."""
    t = actor.last_clip_time
    left = actor.joint_world_point('upperarm_l', t, a.render) - actor.joint_world_point('upperarm_r', t, a.render)
    f = Vec3(left.y, -left.x, 0)
    f.normalize()
    return f


def screen_xy(a, p):
    from panda3d.core import Point2
    q = a.cam.getRelativePoint(a.render, p)
    s = Point2()
    a.camLens.project(q, s)
    return s


KEYS = {'W': (0, 1), 'S': (0, -1), 'A': (-1, 0), 'D': (1, 0),
        'W+D': (1, 1), 'W+A': (-1, 1), 'S+D': (1, -1), 'S+A': (-1, -1)}


def main():
    glb = Path(__file__).resolve().parents[2] / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=glb)
    a.time_frozen = True          # Pass 43: hold the clock at a steady sun for these checks
    a.heat_factor_override = 1.0
    a.red_giant.setPos(a.red_giant.getPos() + Vec3(800, 0, 0))
    start = a.human.getPos() + Vec3(-40, -40, 0)

    # The idle pose stands a little twisted; measure that once so facing checks compare like with like.
    def idle_bias(actor, node):
        keep = node.getH()
        node.setH(0.0)
        actor.apply_clip('Idle_Loop', 0.0, force=True)
        b = ang(body_forward(a, actor))
        node.setH(keep)
        return b
    human_bias = idle_bias(a.human_actor, a.human)
    giant_bias = idle_bias(a.giant_actor, a.giant)
    print(f'   idle twist: human {human_bias:.1f} deg, giant {giant_bias:.1f} deg')

    # ------------------------------------------------------------- human
    worst_move = worst_face = 0.0
    screen_ok = True
    for cam_h in (0.0, 37.0, 135.0, -90.0, 210.0):
        for key, (x, y) in KEYS.items():
            a.human.setPos(start.x, start.y, a.field.height(start.x, start.y))
            a.heading = cam_h
            a.cam_target = a._controlled_focus()
            a._place_camera(immediate=True)
            h = math.radians(cam_h)
            fwd, right = Vec3(math.sin(h), math.cos(h), 0), Vec3(math.cos(h), -math.sin(h), 0)
            expected = right * x + fwd * y
            p0 = a.human.getPos()
            s0 = screen_xy(a, p0)
            a.simulate_move(x, y, 1.0, steps=30)
            p1 = a.human.getPos()
            moved = Vec3(p1.x - p0.x, p1.y - p0.y, 0)
            worst_move = max(worst_move, abs(delta(ang(expected), ang(moved))))
            a.human_actor.apply_clip('Idle_Loop', 0.0, force=True)
            worst_face = max(worst_face, abs(delta(ang(moved) + human_bias, ang(body_forward(a, a.human_actor)))))
            s1 = screen_xy(a, Vec3(p1.x, p1.y, p0.z))       # ignore dune slope
            # on screen: D goes right, A left, W up (away), S down (toward the camera)
            if (x and (s1.x - s0.x) * x <= 0) or (y and (s1.y - s0.y) * y <= 0):
                screen_ok = False
                print('   screen', cam_h, key, s0, s1)
    check('human moves exactly where WASD points (any camera angle)', worst_move < 1.0, f'worst {worst_move:.2f} deg')
    check('human faces the way it walks (measured from its shoulders)', worst_face < 3.0, f'worst {worst_face:.1f} deg')
    check('on screen: W away, S toward, A left, D right', screen_ok)

    # mirror: the model's left clavicle must be on its left side
    a.human.setH(0)
    a.human_actor.apply_clip('Idle_Loop', 0.0, force=True)
    fwd = body_forward(a, a.human_actor)
    left = Vec3(-fwd.y, fwd.x, 0)
    root = a.human.getPos()
    lc = a.human_actor.joint_world_point('clavicle_l', 0.0, a.render) - root
    uc = a.human_actor.joint_world_point('upperarm_l', 0.0, a.render) - root
    check('left arm is on the left (no mirror)', (uc.x * left.x + uc.y * left.y) > 0.05,
          f'{uc.x * left.x + uc.y * left.y:.3f} m')
    del lc

    # ------------------------------------------------------------- giant
    a._toggle_control()
    worst_g = 0.0
    for key in ('W', 'A', 'S', 'D', 'W+D'):
        x, y = KEYS[key]
        gs = a.giant.getPos()
        a.giant.setPos(gs.x, gs.y, gs.z)
        a.giant_motion_speed = 0.0
        a.heading = 0.0
        h0 = a.giant.getH()
        a.giant_motion_heading = h0
        expected = Vec3(x, y, 0)
        expected.normalize()
        a.simulate_giant_heavy_move(x, y, 6.0, steps=180, gait='walk')
        # direction of the last second of travel
        p_mid = a.giant.getPos()
        a.simulate_giant_heavy_move(x, y, 1.0, steps=30, gait='walk')
        moved = a.giant.getPos() - p_mid
        moved.z = 0
        err = abs(delta(ang(expected), ang(moved)))
        a.giant_actor.apply_clip('Idle_Loop', 0.0, force=True)
        face = abs(delta(ang(moved) + giant_bias, ang(body_forward(a, a.giant_actor))))
        worst_g = max(worst_g, err, face)
        a.simulate_giant_brake(4.0)
    check('giant turns and walks the pressed way, facing it', worst_g < 8.0, f'worst {worst_g:.1f} deg')

    # heavy: a full reversal at a jog brakes, turns and heads back within a few seconds
    a.giant_motion_speed = 0.0
    a.heading = 0.0
    a.simulate_giant_heavy_move(0, 1, 5.0, steps=150, gait='jog')
    p0 = a.giant.getPos()
    t_back = None
    for i in range(1, 9):
        before = a.giant.getPos()
        a.simulate_giant_heavy_move(0, -1, 0.5, steps=15, gait='jog')
        if (a.giant.getPos() - before).y < -0.5:
            t_back = i * 0.5
            break
    overshoot = max(0.0, max(a.giant.getPos().y, p0.y) - p0.y)
    check('reversing: the giant is heading back within ~4 s', t_back is not None and t_back <= 4.5,
          f'{t_back}s, carried on {overshoot:.1f} m')
    a._toggle_control()

    a.destroy()
    print('RESULT', 'FAIL' if FAILS else 'PASS', FAILS)
    sys.exit(1 if FAILS else 0)


if __name__ == '__main__':
    main()
