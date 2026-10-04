"""Pass 58 check: look up, footprints, a quicker human, fighting as Indigo.

    python .dev/checks/pass58.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

from panda3d.core import GeomVertexReader, Point3, Vec3

HERE = Path(__file__).resolve().parents[2]          # Pass 62: the game folder
TMP = Path(tempfile.mkdtemp(prefix='indigo_save58_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import sys as _sys                                  # Pass 62: the game folder is two levels up
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from indigo_giant import fight          # noqa: E402
from indigo_giant import locomotion     # noqa: E402
from indigo_giant import app as game   # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
DT = 1 / 30.0


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def print_points(fp):
    """World xy of a footprint's vertices: [heel pad, ball pad, inner ring..., outer ring...]."""
    geom = fp.geom_np.node().getGeom(0)
    r = GeomVertexReader(geom.getVertexData(), 'vertex')
    base = fp.root.getPos()
    pts = []
    while not r.isAtEnd():
        v = r.getData3()
        pts.append((base.x + v.x, base.y + v.y))
    return pts


def angle_between(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def main():
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, new_game=True, persist=True, save_dir=TMP,
                                       show_title=False)
    a.time_frozen = True
    a.heat_factor_override = 0.0
    a.hour = 12.0
    a.comp.update({'mode': 'stay', 'moving': False})
    b = a.human_base_pos
    a.red_giant.setPos(ground(a, b.x + 700, b.y))
    a.red_state = 'idle'

    # ------------------------------------------------------------ 1. the camera: look up
    a.cam_target = a._controlled_focus()
    a.pitch = game.CAMERA_PITCH_MAX
    a._place_camera(immediate=True)
    fwd = a.camera.getQuat(a.render).getForward()
    cp = a.camera.getPos(a.render)
    clear = cp.z - a.field.height(cp.x, cp.y)
    anchor = (cp - a.cam_target).length()
    check('you can look up: the view tilts well above the horizon (it stopped at level before)',
          math.degrees(math.asin(fwd.z)) > 40.0 and clear >= 0.44 and anchor <= game.HUMAN_CAMERA_DISTANCE + 0.1,
          f'view {math.degrees(math.asin(fwd.z)):+.0f} deg, camera {clear:.2f} m above the sand, {anchor:.1f} m from you')
    a.pitch = game.CAMERA_PITCH_MIN
    a._place_camera(immediate=True)
    fwd = a.camera.getQuat(a.render).getForward()
    check('and further down than before', math.degrees(math.asin(fwd.z)) < -60.0,
          f'view {math.degrees(math.asin(fwd.z)):+.0f} deg')
    a.pitch = game.HUMAN_CAMERA_PITCH
    a._orbit_drag = (500.0, 500.0)
    a._pointer_xy = lambda: (500.0, 380.0)              # drag the mouse up 120 px with the right button
    a._update_mouse_orbit()
    up_drag = a.pitch
    a._orbit_drag = None
    del a._pointer_xy
    a.pitch = 0.0
    a.keys['up'] = True
    a._camera_task(type('T', (), {'time': 0.0})())
    a.keys['up'] = False
    check('dragging the mouse up, or the up arrow, looks up', up_drag > 10.0 and a.pitch > 0.0,
          f'drag: {game.HUMAN_CAMERA_PITCH:+.0f} -> {up_drag:+.0f} deg; arrow: 0 -> {a.pitch:+.1f}')
    worst = 99.0
    for i in range(160):
        x, y = b.x + (i % 16) * 23.0 - 180.0, b.y + (i // 16) * 31.0 - 150.0
        a.human.setPos(ground(a, x, y))
        a.heading = (i * 47.0) % 360.0
        a.pitch = (-60.0, -15.0, 0.0, 20.0, 50.0)[i % 5]
        a.cam_target = a._controlled_focus()
        a._place_camera(immediate=True)
        cp = a.camera.getPos(a.render)
        worst = min(worst, cp.z - a.field.height(cp.x, cp.y))
    check('the camera never goes into the sand (dunes behind you, looking up)', worst >= 0.44,
          f'lowest {worst:.2f} m above the sand over 160 places, headings and angles')
    a.pitch = game.HUMAN_CAMERA_PITCH
    a.human.setPos(ground(a, b.x, b.y))

    # ------------------------------------------------------------ 2. footprints
    for heading in (0.0, 45.0, 135.0, -100.0):
        a.human.setH(heading)
        a.footprints.clear()
        a._stamp_controlled_footprint(a.human_actor, a.human, owner='human', side='right')
        pts = print_points(a.footprints[-1])
        heel, ball = pts[0], pts[2]
        toe_dir = math.degrees(math.atan2(-(ball[0] - heel[0]), ball[1] - heel[1]))
        if angle_between(toe_dir, heading) > 8.0:
            break
    check('a footprint lies along the way you face, toe forward (a diagonal used to lie across the path)',
          angle_between(toe_dir, heading) <= 8.0, f'at heading {heading:+.0f}: toes point {toe_dir:+.0f}')
    a.human.setH(30.0)
    a.footprints.clear()
    a._stamp_controlled_footprint(a.human_actor, a.human, owner='human', side='left')
    a._stamp_controlled_footprint(a.human_actor, a.human, owner='human', side='right')
    left, right = print_points(a.footprints[-2]), print_points(a.footprints[-1])
    h = math.radians(30.0)
    fwd2, right2 = (-math.sin(h), math.cos(h)), (math.cos(h), math.sin(h))

    def local(p, o):
        dx, dy = p[0] - o[0], p[1] - o[1]
        return dx * fwd2[0] + dy * fwd2[1], dx * right2[0] + dy * right2[1]
    lo, ro = a.footprints[-2].root.getPos(), a.footprints[-1].root.getPos()
    ll = [local(p, (lo.x, lo.y)) for p in left]
    rl = [local(p, (ro.x, ro.y)) for p in right]
    mirrored = max(abs(u1 - u2) + abs(v1 + v2) for (u1, v1), (u2, v2) in zip(ll, rl))
    us, vs = [u for u, _v in rl[3:]], [v for _u, v in rl[3:]]
    ratio = (max(us) - min(us)) / (max(vs) - min(vs))
    wide_ball = max(v for u, v in rl if u > 0.02) - min(v for u, v in rl if u > 0.02)
    narrow_arch = max(v for u, v in rl if -0.02 < u < 0.06) - min(v for u, v in rl if -0.02 < u < 0.06)
    check('footprints are foot-shaped: long and narrow, a wide ball and a narrower arch, left and right mirrored',
          mirrored < 0.005 and 2.0 < ratio < 2.9 and wide_ball > narrow_arch,
          f'length/width {ratio:.2f}, mirror error {mirrored * 1000:.1f} mm')

    # walking a diagonal: every print lies along the path
    a.footprints.clear()
    a.human.setPos(ground(a, b.x, b.y))
    t = 0.0
    d = Vec3(1, 1, 0)
    while t < 4.0:
        a._apply_controlled_move(d, DT, t, gait='walk')
        t += DT
    walk_dir = math.degrees(math.atan2(-d.x, d.y))
    offs = []
    for fp in a.footprints:
        pts = print_points(fp)
        heel, ball = pts[0], pts[2]
        offs.append(angle_between(math.degrees(math.atan2(-(ball[0] - heel[0]), ball[1] - heel[1])), walk_dir))
    check('walking a diagonal, every print points along the path', offs and max(offs) < 12.0,
          f'{len(offs)} prints, worst {max(offs) if offs else -1:.0f} deg off')

    # ------------------------------------------------------------ 3. a quicker human, giants the same
    hw, hj, hs = (locomotion.speed('human', g) for g in ('walk', 'jog', 'sprint'))
    gw, gj, gs = (locomotion.speed('giant', g) for g in ('walk', 'jog', 'sprint'))
    check('the human is quicker: walk 1.45, jog 5.6, sprint 8.4 m/s (were 1.2 / 4.4 / 6.6)',
          (hw, hj, hs) == (1.45, 5.6, 8.4), f'{hw} / {hj} / {hs}')
    check('the giants are unchanged', abs(gw - 3.67) < 0.01 and abs(gj - 6.80) < 0.01 and abs(gs - 9.52) < 0.01,
          f'{gw:.2f} / {gj:.2f} / {gs:.2f}')
    rates = [locomotion.playback_rate(c, s, 1.0) for c, s in (locomotion.gait('human', g) for g in ('jog', 'sprint'))]
    check('jog and sprint now play near their natural pace (were 0.74)', all(0.9 <= r <= 1.05 for r in rates),
          ', '.join(f'{r:.2f}' for r in rates))
    a.human.setPos(ground(a, b.x, b.y))
    a.stamina = 100.0
    a.human_motion_speed = 0.0
    p0 = a.human.getPos()
    t = 0.0
    while t < 2.0:
        a._apply_controlled_move(Vec3(0, 1, 0), DT, t, gait='sprint')
        t += DT
    moved = (a.human.getPos() - p0).length()
    check('sprinting covers the ground (2 s from standing)', moved > 14.5, f'{moved:.1f} m (was ~11.8)')

    # ------------------------------------------------------------ 4. fighting as Indigo
    def fresh(dist, off_deg=0.0):
        a.giant.setPos(ground(a, b.x + 40, b.y))
        a.giant.setH(0.0)
        a.giant_motion_heading = 0.0
        t_ = math.radians(off_deg)
        f_ = Vec3(-math.sin(t_), math.cos(t_), 0)
        a.red_giant.setPos(ground(a, b.x + 40 + f_.x * dist, b.y + f_.y * dist))
        a.red_alive, a.red_knocked_out, a.red_health = True, False, 100.0
        a.giant_stamina, a.red_stamina = fight.STAMINA_MAX['giant'], fight.STAMINA_MAX['red']
        for st in a.attack_states.values():
            st.update({'active': False, 'elapsed': 0.0, 'hit_done': False, 'cooldown': 0.0})
        a.attack_hold, a.attack_queued = None, False
        a.keys['punch'] = a.keys['attack_mouse'] = False
        a.combat_hits = {'giant': 0, 'red': 0}

    def frames(n):
        for _ in range(n):
            a._apply_giant_heavy_input(Vec3(0, 0, 0), DT, 0.0)

    a._toggle_control()
    fresh(4.5)
    a._on_left_click()                       # left mouse down
    frames(2)
    a.messenger.send('mouse1-up')            # a tap
    frames(1)
    started = a.attack_states['giant']['clip']
    frames(12)
    first_hit = a.combat_hits['giant']
    a._on_left_click()                       # pressed again mid-punch: queued
    a.messenger.send('mouse1-up')
    t_second = None
    for i in range(40):
        frames(1)
        if a.combat_hits['giant'] >= 2 and t_second is None:
            t_second = (i + 14) * DT
    second_clip = a.attack_states['giant']['clip']
    check('as Indigo, a tap of the left mouse punches; a second tap chains the next punch in',
          started in ('Punch_Jab', 'Punch_Cross') and second_clip != started and first_hit == 1 and a.combat_hits['giant'] >= 2 and t_second is not None
          and t_second < 0.87 + 0.34,
          f'second blow landed {t_second}s after the first press (a full jab alone is 0.87 s)')

    fresh(4.5)
    a.messenger.send(a.bindings['punch'])    # hold F ...
    frames(int(0.30 / DT))
    winding = a.giant_actor.current_clip == 'Sword_Attack' and a.giant_motion_speed == 0.0
    frames(int(0.25 / DT))
    red0 = a.red_giant.getPos()
    st0 = a.giant_stamina
    a.messenger.send(a.bindings['punch'] + '-up')   # ... and let go
    for _ in range(int(1.4 / DT)):
        frames(1)
        a._update_red_knock(DT)
    pushed = (a.red_giant.getPos() - red0).length()
    check('holding F (or the mouse) winds up a hammer blow; letting go strikes twice, drives the red one back '
          'and staggers it',
          winding and a.combat_hits['giant'] == 2 and pushed > 2.5 and st0 - a.giant_stamina >= fight.HEAVY_COST - 0.5
          and a.attack_states['red']['cooldown'] > 0.0,
          f'wind-up {winding}, hits {a.combat_hits["giant"]}, pushed {pushed:.1f} m, cost {st0 - a.giant_stamina:.1f}')

    fresh(8.5, off_deg=60.0)                 # to one side and a step too far
    a._on_left_click()
    a.messenger.send('mouse1-up')
    frames(30)
    d_after = a._giant_flat_distance()
    check('a blow turns Indigo to the red one and steps in when it is just out of reach',
          a.combat_hits['giant'] == 1 and d_after <= game.GIANT_MELEE_RANGE and a.giant_faces_red(),
          f'8.5 m away at 60 deg -> {d_after:.1f} m, hit {a.combat_hits["giant"]}')

    fresh(4.5, off_deg=180.0)                # right behind Indigo
    a._on_left_click()
    a.messenger.send('mouse1-up')
    frames(30)
    check('a punch thrown the wrong way does not land (it used to hit whatever the direction)',
          a.combat_hits['giant'] == 0)

    fresh(4.5)
    a.giant_stamina = 1.0
    a._on_left_click()
    a.messenger.send('mouse1-up')
    frames(10)
    check('out of breath, Indigo cannot punch (Pass 53 stamina still rules)', a.combat_hits['giant'] == 0)
    check('the red one\'s own punches are unchanged (costs and timing table)',
          fight.PUNCH_COST == 2.0 and game.MELEE_HITS['Punch_Jab'][0][1] == 1.0)

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
