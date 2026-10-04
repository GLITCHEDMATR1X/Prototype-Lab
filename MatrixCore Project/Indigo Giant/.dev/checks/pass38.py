"""Pass 38 headless check: gestures, lift/carry/set-down, blood branches, scraps, red boss cycle.

Run:  python .dev/checks/pass38.py            (offscreen)
      python .dev/checks/pass38.py --shots DIR (also saves screenshots)
Prints PASS/FAIL lines and exits non-zero on any failure.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

from panda3d.core import Point3, Vec3

import sys as _sys                                  # Pass 62: the game folder is two levels up
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from indigo_giant import app as game
from indigo_giant import flora

FAILS: list[str] = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail else ''))
    if not ok:
        FAILS.append(name)


def frame(a, dt=1 / 30.0, t=[0.0]):
    """Mirror the live task order: movement 5, defender+companion 6, red 7, survival 8, camera 9."""
    t[0] += dt
    h = math.radians(a.heading)
    fwd = Vec3(math.sin(h), math.cos(h), 0)
    right = Vec3(math.cos(h), -math.sin(h), 0)
    move = Vec3(0, 0, 0)
    if a.keys['w']: move += fwd
    if a.keys['s']: move -= fwd
    if a.keys['d']: move += right
    if a.keys['a']: move -= right
    if a.controlled_name == 'giant':
        a._apply_giant_heavy_input(move, dt, t[0])
    else:
        a._apply_controlled_move(move, dt, t[0])
    a._update_indigo_defender(dt, t[0])
    a._update_companion(dt)
    a._update_red_giant(dt, t[0])
    a.survival_step(dt)
    a._place_camera(immediate=False, dt=dt)
    a.service_stream_queue()


def run(a, seconds, dt=1 / 30.0, until=None):
    n = int(seconds / dt)
    for i in range(n):
        frame(a, dt)
        if until is not None and until():
            return (i + 1) * dt
    return None


def park_red(a, far=True):
    p = a.human.getPos() + Vec3(600, 0, 0) if far else a.red_giant_base_pos
    p.z = a.field.height(p.x, p.y)
    a.red_giant.setPos(p)
    a.red_state = 'idle'


def flat(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def shot(a, shots, name):
    if shots is None:
        return
    a.graphicsEngine.renderFrame()
    a.graphicsEngine.renderFrame()
    a.win.saveScreenshot(str(shots / name))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shots', type=Path)
    args = ap.parse_args()
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)
    glb = Path(__file__).resolve().parents[2] / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
    t0 = time.time()
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=glb)
    a.time_frozen = True          # Pass 43: hold the clock at a steady sun for these checks
    a.heat_factor_override = 1.0
    # Heat (Pass 39) would legitimately down the human during these long simulated
    # stretches; it has its own check (tools_pass39_check.py).
    from indigo_giant import desert
    desert.HEAT_SUN_RATE = 0.0
    print('startup', round(time.time() - t0, 2), 's')
    park_red(a)

    # --- blood branch near start + heal ----------------------------------------------------
    start = a.flora.nearest_intact(a.human.getPos(), 40.0)
    check('start branch exists', start is not None)
    a.human_health = 40.0
    bp = start.pos
    target = Point3(bp.x + 1.2, bp.y, a.field.height(bp.x + 1.2, bp.y))
    a.human.setPos(target)
    run(a, 3.0)
    check('human heals at blood branch', a.human_health > 55.0, round(a.human_health, 1))
    sap_after = start.sap
    check('branch sap is limited', sap_after < flora.SAP_MAX, round(sap_after, 1))

    # --- COME -------------------------------------------------------------------------------
    far = a.human.getPos() + Vec3(-45, 20, 0)
    far.z = a.field.height(far.x, far.y)
    a.human.setPos(far)
    check('gesture COME accepted', a.gesture_command('come'))
    arrived = run(a, 60.0, until=lambda: a.comp['mode'] == 'follow' and not a.comp['moving']
                  and flat(a.giant.getPos(), a.human.getPos()) < survival_follow_stop() + 2)
    d = flat(a.giant.getPos(), a.human.getPos())
    check('giant comes and stops near the human', arrived is not None and d > 3.0, f'{d:.1f} m in {arrived}s')

    # --- STAY ------------------------------------------------------------------------------
    run(a, 1.0)
    a.gesture_command('stay')
    run(a, 1.0)
    gpos = a.giant.getPos()
    walk_to = a.human.getPos() + Vec3(30, 0, 0)
    walk_to.z = a.field.height(walk_to.x, walk_to.y)
    a.human.setPos(walk_to)
    run(a, 4.0)
    check('giant stays put on STAY', flat(gpos, a.giant.getPos()) < 0.5, f'{flat(gpos, a.giant.getPos()):.2f} m')

    # --- LIFT ME ---------------------------------------------------------------------------
    a.gesture_command('lift')
    done = run(a, 60.0, until=lambda: a.comp['mode'] == 'carry')
    check('giant lifts the human onto its shoulder', done is not None and a.carried, f'{done}s')
    seat = a.human.getPos()
    gz = a.giant.getPos().z
    check('rider sits high on the giant', seat.z - gz > a.giant_height * 0.7, f'{seat.z - gz:.2f} / {a.giant_height:.2f}')
    check('rider stays within shoulder width', flat(seat, a.giant.getPos()) < 3.0, f'{flat(seat, a.giant.getPos()):.2f}')
    if args.shots:
        a.heading = a.giant.getH() + 140
        a._snap_camera_to_controlled(immediate=True)
        shot(a, args.shots, 'p38_riding_view.png')
        from panda3d.core import Vec3 as V
        a.cam_target = V(a.giant.getX(), a.giant.getY(), a.giant.getZ() + a.giant_height * 0.75)
        a.distance = 14.0
        a.pitch = -8.0
        for hd in (a.giant.getH() + 90, a.giant.getH() + 180):
            a.heading = hd
            a._place_camera(immediate=True)
            shot(a, args.shots, f'p38_shoulder_{int(hd) % 360}.png')

    # --- stomp immunity while carried -------------------------------------------------------
    hh = a.human_health
    a.red_giant.setPos(a.human.getPos())
    check('carried human cannot be stomped', a._apply_red_stomp_hit() is False and a.human_health == hh)
    park_red(a)

    # --- GO THERE while carried ------------------------------------------------------------
    dest = a.giant.getPos() + Vec3(50, 35, 0)
    dest.z = a.field.height(dest.x, dest.y)
    a.gesture_command('goto', dest)
    t = run(a, 90.0, until=lambda: a.comp['target'] is None and not a.comp['moving'])
    d = flat(a.giant.getPos(), dest)
    check('giant carries human to GO THERE point', t is not None and d < 6.0, f'{d:.1f} m in {t}s')
    check('rider still attached after travel', flat(a.human.getPos(), a.giant.getPos()) < 3.0)

    # --- hold W to ride where you look -----------------------------------------------------
    p0 = a.giant.getPos()
    a.keys['w'] = True
    run(a, 6.0)
    a.keys['w'] = False
    run(a, 3.0)
    check('W while riding walks the giant', flat(p0, a.giant.getPos()) > 5.0, f'{flat(p0, a.giant.getPos()):.1f} m')

    # --- TAB takes the reins while riding --------------------------------------------------
    a._toggle_control()
    check('TAB hands the reins to the rider', a.controlled_name == 'giant' and a.carried)
    p0 = a.giant.getPos()
    a.keys['w'] = True
    run(a, 5.0)
    a.keys['w'] = False
    run(a, 3.0)
    check('rider stays on while player drives', flat(a.human.getPos(), a.giant.getPos()) < 3.0
          and a.human_actor.current_clip == 'Sitting_Idle_Loop')
    check('player-driven giant moved', flat(p0, a.giant.getPos()) > 4.0)
    a._toggle_control()
    check('TAB back keeps riding', a.controlled_name == 'human' and a.carried and a.comp['mode'] == 'carry')

    # --- SET ME DOWN -----------------------------------------------------------------------
    a.gesture_command('lift')  # same key toggles to set me down
    t = run(a, 20.0, until=lambda: a.comp['mode'] == 'stay' and not a.carried)
    hp = a.human.getPos()
    ground = a.field.height(hp.x, hp.y)
    check('giant sets the human down', t is not None and abs(hp.z - ground) < 0.3, f'{t}s dz={hp.z - ground:.2f}')
    check('human back on foot next to the giant', 1.0 < flat(hp, a.giant.getPos()) < 8.0, f'{flat(hp, a.giant.getPos()):.1f}')
    check('kneel finished', a.kneel_state['phase'] == 'standing')

    # --- human smash (hold E) -> scraps -> collect -> transfer --------------------------------
    a.flora.update_active(a.human.getPos())
    b = start if not start.smashed else a.flora.nearest_intact(a.human.getPos(), 400)
    b.pos  # noqa
    spot = Point3(b.pos.x + 1.0, b.pos.y, a.field.height(b.pos.x + 1.0, b.pos.y))
    a.human.setPos(spot)
    a.flora.update_active(spot)
    before = a.human_scraps
    a.keys['e'] = True
    run(a, 2.0)
    a.keys['e'] = False
    check('holding E smashes the branch', b.smashed)
    for s in list(a.flora.scraps):
        a.human.setPos(Point3(s.pos.x, s.pos.y, a.field.height(s.pos.x, s.pos.y)))
        run(a, 0.2)
    check('human picks up scraps', a.human_scraps - before == flora.SCRAPS_PER_BRANCH, a.human_scraps)
    a.giant.setPos(a.human.getPos() + Vec3(6, 0, 0))
    moved = a.transfer_scraps(True)
    check('T gives scraps to the giant', moved == flora.SCRAPS_PER_BRANCH and a.giant_scraps == moved)
    back = a.transfer_scraps(False)
    check('Y takes scraps back', back == moved and a.human_scraps == moved)
    a.transfer_scraps(True)

    # --- giant F smash -------------------------------------------------------------------------
    b2 = a.flora.nearest_intact(a.giant.getPos(), 500)
    gp = Point3(b2.pos.x + 4.0, b2.pos.y, a.field.height(b2.pos.x + 4.0, b2.pos.y))
    a.giant.setPos(gp)
    a.human.setPos(gp + Vec3(-30, 0, 0))
    a._toggle_control()
    gs = a.giant_scraps
    check('giant F starts a smash', a._request_giant_melee() and a.pending_smash is b2)
    run(a, 2.0)
    check('giant smash breaks the branch', b2.smashed)
    run(a, 1.0)
    check('giant hoovers its scraps', a.giant_scraps > gs, f'{gs}->{a.giant_scraps}')
    a._toggle_control()

    # --- regrow ---------------------------------------------------------------------------------
    a.flora.update(flora.REGROW_SECONDS + 1)
    check('smashed branch regrows', not b2.smashed)

    # --- Red giant: scare, lurk, return ---------------------------------------------------------
    a.giant.setPos(a.human.getPos() + Vec3(6, 0, 0))
    rp = a.giant.getPos() + Vec3(4.5, 0, 0)
    a.red_giant.setPos(rp)
    a.red_health = 50.0
    a._set_combat_health('red', 50.0)
    # Pass 53: a sneaky (fed, calm) red one runs when nearly out of stamina
    a.red_anger, a.red_hunger, a.red_woken_t = 0, 0.1, 0.0
    a.red_stamina = 15.0
    anger0 = a.red_anger
    a._apply_melee_hit('giant')   # nearly spent: scared
    check('low health scares the red giant', a.red_fleeing and not a.red_knocked_out and a.red_anger == anger0 + 1,
          f'hp={a.red_health}')
    t = run(a, 120.0, until=lambda: a.red_lurking)
    check('red flees then lurks', t is not None, f'{t}s')
    hp_lurk = a.red_health
    delay = a.red_return_delay()
    t = run(a, delay + 5.0, until=lambda: a.red_returning)
    check('red returns after its delay', t is not None and abs(t - delay) < 1.0, f'{t}s vs {delay}s')
    check('red recovered while lurking', a.red_health > hp_lurk + 40, f'{hp_lurk:.0f}->{a.red_health:.0f}')
    t = run(a, 120.0, until=lambda: not a.red_returning)
    check('returning red closes back in', t is not None, f'{t}s')

    # KO path: chase-down hit
    a.red_giant.setPos(a.giant.getPos() + Vec3(4.5, 0, 0))
    a.red_fleeing = False
    a._set_combat_health('red', 20.0)
    a.red_stamina = 0.0            # Pass 53: a hit on an exhausted giant knocks it out
    a._apply_melee_hit('giant')
    check('red is knocked out at zero, never dies', a.red_knocked_out and a.red_alive)

    # --- Human downed -> retry keeps inventories ----------------------------------------------------
    a.human_alive = False
    a.human_health = 0
    scr = (a.human_scraps, a.giant_scraps)
    a._retry_after_human_down()
    check('retry resets companion but keeps scraps', a.comp['mode'] == 'stay' and not a.carried
          and (a.human_scraps, a.giant_scraps) == scr)

    # --- soak with the wheel & random gestures -----------------------------------------------------
    import random
    rng = random.Random(4)
    t0 = time.time()
    for i in range(900):
        if i % 90 == 0:
            a.gesture_command(rng.choice(['come', 'stay', 'lift', 'goto']))
        if i % 45 == 0:
            for k in ('w', 'a', 'd'):
                a.keys[k] = rng.random() < 0.3
        frame(a)
    for k in a.keys:
        a.keys[k] = False
    check('900-frame gesture soak without errors', True, f'{(time.time() - t0) / 900 * 1000:.1f} ms/frame (software GL, logic only)')

    print('HUD:', a._hud_cache.replace('\n', ' | '))
    a.destroy()
    print('RESULT', 'FAIL' if FAILS else 'PASS', FAILS)
    sys.exit(1 if FAILS else 0)


def survival_follow_stop():
    from indigo_giant import survival
    return survival.FOLLOW_STOP


if __name__ == '__main__':
    main()
