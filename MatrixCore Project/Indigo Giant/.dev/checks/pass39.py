"""Pass 39 headless check: heat & shade, stamina, finds & sensing, eating, landmark trail,
shells (patch, hide, Red overturn, whistle rescue, giant lifts a shell).

Run:  python .dev/checks/pass39.py            (offscreen)
      python .dev/checks/pass39.py --shots DIR (also saves screenshots)
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
from indigo_giant import desert

FAILS: list[str] = []
CLOCK = [0.0]


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def frame(a, dt=1 / 30.0):
    """Same order as the live tasks: movement, defender+companion, red, survival, camera, shadows."""
    CLOCK[0] += dt
    t = CLOCK[0]
    h = math.radians(a.heading)
    fwd, right = Vec3(math.sin(h), math.cos(h), 0), Vec3(math.cos(h), -math.sin(h), 0)
    move = Vec3(0, 0, 0)
    if a.keys['w']: move += fwd
    if a.keys['s']: move -= fwd
    if a.keys['d']: move += right
    if a.keys['a']: move -= right
    if a.controlled_name == 'giant':
        a._apply_giant_heavy_input(move, dt, t)
    else:
        a._apply_controlled_move(move, dt, t)
    a._update_indigo_defender(dt, t)
    a._update_companion(dt)
    a._update_red_giant(dt, t)
    a.survival_step(dt)
    a._place_camera(immediate=False, dt=dt)
    a._update_actor_shadows()
    a.service_stream_queue()


def run(a, seconds, dt=1 / 30.0, until=None):
    for i in range(int(round(seconds / dt))):
        frame(a, dt)
        if until is not None and until():
            return (i + 1) * dt
    return None


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def flat(p, q):
    return math.hypot(p.x - q.x, p.y - q.y)


def park(a, node, where):
    node.setPos(ground(a, where.x, where.y))


def park_red_far(a):
    park(a, a.red_giant, a.human.getPos() + Vec3(700, 0, 0))
    a.red_state = 'idle'
    a.red_saw_hide = False


def sunny_spot(a, origin):
    """A spot near origin that is in full sun (no shells/landmarks/giants within reach)."""
    for r in range(0, 400, 12):
        for k in range(12):
            p = ground(a, origin.x + math.cos(k * 0.52) * r, origin.y + math.sin(k * 0.52) * r)
            a.human.setPos(p)
            a._refresh_world()
            if not a.point_in_shade(p) and all(flat(s.pos, p) > 25 for s in a.shells.shells.values()) \
                    and all(flat(lm.pos, p) > 60 for lm in a.landmarks.items):
                return p
    raise RuntimeError('no sunny spot')


def reset_human(a):
    a.human_alive = True
    a.human_health = 100.0
    a.heat = 0.0
    a.stamina = 100.0
    a.winded = False
    a.human_dazed = 0.0
    a.human.show()
    a.human_actor.apply_clip('Idle_Loop', 0.0, force=True)
    a._update_control_text()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shots', type=Path)
    args = ap.parse_args()
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)

    def shot(name):
        if args.shots:
            for _ in range(2):
                a.graphicsEngine.renderFrame()
            a.win.saveScreenshot(str(args.shots / name))

    glb = Path(__file__).resolve().parents[2] / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
    t0 = time.time()
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=glb)
    a.time_frozen = True          # Pass 43: hold the clock at a steady sun for these checks
    a.heat_factor_override = 1.0
    print('startup', round(time.time() - t0, 2), 's')
    park_red_far(a)
    start = Point3(a.human.getPos())

    # ---------------------------------------------------------------- sensing & digging
    run(a, 2.0)
    f0 = a.finds.finds[('start', 0)]
    check('giant senses the find near the start', f0.sensed)
    check('giant notices (turns toward) it', a.notice is not None or a._lore_alpha > 0)
    a.human.setPos(ground(a, f0.pos.x + 0.8, f0.pos.y))
    a.keys['e'] = True
    a._on_e_press()
    run(a, 1.5)
    a.keys['e'] = False
    run(a, 0.1)
    check('hold E digs the find up', f0.dug and a.bag('human')['gourd'] == 1, dict(a.bag('human')))

    # ---------------------------------------------------------------- landmark trail
    revealed0 = [lm.idx for lm in a.landmarks.items if lm.revealed]
    check('two landmarks are known from the start', len(revealed0) == 2, revealed0)
    lm = a.landmarks.items[revealed0[0]]
    shot_pos = ground(a, lm.pos.x + 7.5, lm.pos.y + 7.5)
    a.human.setPos(shot_pos)
    a._refresh_world()
    a.keys['e'] = True
    a._on_e_press()
    run(a, 2.2)
    a.keys['e'] = False
    run(a, 0.1)
    revealed1 = [x.idx for x in a.landmarks.items if x.revealed]
    check('studying a landmark marks it visited', lm.visited and a.landmarks.visited_count() == 1)
    check('its links become visible', all(a.landmarks.items[i].revealed for i in lm.links), f'{revealed0}->{revealed1}')
    check('landmark cache goes into the bag', a.bag('human')['pod'] >= 2, dict(a.bag('human')))
    if args.shots:
        a.heading = 30.0
        a._snap_camera_to_controlled(immediate=True)
        shot('p39_landmark.png')

    # ---------------------------------------------------------------- heat: 5 minutes
    reset_human(a)
    spot = sunny_spot(a, start + Vec3(-150, -120, 0))
    park(a, a.giant, spot + Vec3(160, 0, 0))
    a.comp.update({'mode': 'stay', 'moving': False})
    park_red_far(a)
    for item in ('pod', 'gourd'):
        a.bag('human')[item] = 0
    a.human.setPos(spot)
    t_full = run(a, 200, dt=1 / 15.0, until=lambda: a.heat >= 100.0)
    check('full heat after ~2 minutes of sun', t_full is not None and 115 <= t_full <= 125, t_full)
    check('heat drains stamina', a.stamina < 100.0, round(a.stamina, 1))
    check('heat slows the human', abs(a.heat_speed_factor() - 0.7) < 1e-6)
    t_down = run(a, 240, dt=1 / 15.0, until=lambda: not a.human_alive)
    total = (t_full or 0) + (t_down or 0)
    check('~5 minutes of exposure kills', t_down is not None and 290 <= total <= 310, round(total, 1))
    a._retry_after_human_down()
    check('retry resets heat and stamina', a.heat == 0.0 and a.stamina == 100.0 and a.human_alive)
    park_red_far(a)

    # ---------------------------------------------------------------- shade gesture
    spot = sunny_spot(a, start + Vec3(-150, -120, 0))
    a.human.setPos(spot)
    park(a, a.giant, spot + Vec3(30, 20, 0))
    a.heat = 60.0
    check('SHADE ME accepted', a.gesture_command('shade'))
    t = run(a, 40, until=lambda: a.comp['mode'] == 'shade' and not a.comp['moving'])
    run(a, 1.0)
    in_shade = a.point_in_shade(a.human.getPos())
    check('giant plants its shadow over the human', t is not None and in_shade, f'{t}s shade={in_shade}')
    h0 = a.heat
    run(a, 5.0)
    check('shade cools the human', a.heat < h0 - 8.0, f'{h0:.1f}->{a.heat:.1f}')
    if args.shots:
        a.heading = a.giant.getH() + 60
        a.distance = 30.0
        a.pitch = -35.0
        a.cam_target = Vec3(a.human.getPos())
        a._place_camera(immediate=True)
        shot('p39_shade.png')

    # ---------------------------------------------------------------- riding exposure
    a.heat = 20.0
    a.gesture_command('lift')
    run(a, 40, until=lambda: a.comp['mode'] == 'carry')
    h0 = a.heat
    run(a, 10.0)
    rate = (a.heat - h0) / 10.0
    check('riding is full sun, x1.25', a.shelter_word == 'riding'
          and abs(rate - desert.HEAT_SUN_RATE * desert.HEAT_RIDE_MULT) < 0.02, round(rate, 3))
    a.gesture_command('lift')
    run(a, 20, until=lambda: not a.carried and a.comp['mode'] == 'stay')

    # ---------------------------------------------------------------- eating
    a.bag('human')['gourd'] = 1
    a.bag('human')['pod'] = 1
    a.heat = 70.0
    a.stamina = 30.0
    check('G eats a gourd when hot', a.eat() == 'gourd' and abs(a.heat - 35.0) < 1e-6)
    a.heat = 10.0
    check('G eats pods otherwise', a.eat() == 'pod' and a.stamina >= 75.0)

    # ---------------------------------------------------------------- stamina
    reset_human(a)
    a.keys['shift'] = a.keys['control'] = a.keys['w'] = True
    t = run(a, 20, until=lambda: a.winded)
    a.keys['shift'] = a.keys['control'] = a.keys['w'] = False
    check('sprinting runs out of stamina', t is not None and 7 <= t <= 10, t)
    check('winded forces a walk', a._locomotion_profile('sprint')[0] == 'walk')
    run(a, 4.0)
    check('winded recovers', not a.winded, round(a.stamina, 1))
    st = a.stamina
    check('jumping costs stamina', a._request_jump() and a.stamina == st - 10.0)
    run(a, 1.5)

    # ---------------------------------------------------------------- shells
    reset_human(a)
    shell = a.shells.shells[('start', 0)]
    a._refresh_world()
    check('a cracked shell lies near the start', shell.state == 'cracked' and shell.node is not None)
    a.human.setPos(ground(a, shell.pos.x + 4.2, shell.pos.y))      # Pass 55: beside the (bigger) shell, outside it
    a.bag('human')['scraps'] = 3
    a.bag('human')['resin'] = 1
    a.keys['e'] = True
    a._on_e_press()
    run(a, 2.0)
    a.keys['e'] = False
    run(a, 0.1)
    check('hold E patches it (3 scraps + 1 resin)', shell.state == 'intact'
          and a.bag('human')['scraps'] == 0 and a.bag('human')['resin'] == 0)
    if args.shots:
        a.heading = shell.heading + 150
        a.distance = 9.0
        a.pitch = -18.0
        a.cam_target = Vec3(shell.pos.x, shell.pos.y, shell.pos.z + 0.8)
        a._place_camera(immediate=True)
        shot('p39_shell.png')
    park(a, a.giant, shell.pos + Vec3(150, 60, 0))
    a.comp.update({'mode': 'stay', 'moving': False})
    a.human.setPos(ground(a, shell.entrance_point().x, shell.entrance_point().y))
    a.heat = 80.0
    a.human_health = 60.0
    a._on_e_press()
    a.keys['e'] = False
    check('E steps into the shell (Pass 55: you stay visible, inside it)', a.hidden_shell is shell and not a.human.isHidden())
    run(a, 10.0)
    check('shell cools and heals', a.heat <= 41.0 and a.human_health >= 65.0, f'heat={a.heat:.1f} hp={a.human_health:.1f}')
    check('from inside Indigo cannot lift you (Pass 55: other signs work)', not a.gesture_command('lift'))

    # Red saw you hide -> it overturns the shell
    a.exit_shell()
    park(a, a.red_giant, shell.pos + Vec3(-60, 10, 0))
    a.red_state = 'pursue'
    if hasattr(a, 'red_hunger'):
        a.red_hunger = 0.0           # Pass 48+: a fed Red Giant, so this tests the shell, not its appetite
    a.human.setPos(ground(a, shell.entrance_point().x, shell.entrance_point().y))
    a.enter_shell(shell)
    check('red saw the hiding place', a.red_saw_hide)
    t = run(a, 40, until=lambda: shell.state == 'flipped')
    check('red heaves the shell over', t is not None, f'{t}s')
    check('human thrown out and dazed', a.hidden_shell is None and a.human_dazed > 0 and not a.human.isHidden())
    run(a, 1.0)
    check('flipped shell cannot be entered', a._e_target()[0] != 'hide')
    # Get clear, and let the giant right the shell.
    park_red_far(a)
    run(a, 2.0)
    park(a, a.giant, shell.pos + Vec3(6, 0, 0))
    a._toggle_control()
    check('giant can lift the flipped shell', a.giant_shell_action())
    run(a, 1.2)
    check('shell is in the giant\'s hand', a.giant_held_shell is shell)
    a.keys['w'] = True
    run(a, 3.0)
    a.keys['w'] = False
    run(a, 3.0)
    moved_from = Point3(shell.pos)
    check('giant sets it down upright', a.giant_shell_action() and shell.state == 'intact' and not shell.held)
    check('shell was carried', flat(moved_from, a.giant.getPos()) < 12.0)
    a._toggle_control()

    # Whistle rescue: hide in sight of red, giant far off, whistle.
    park(a, a.giant, shell.pos + Vec3(70, -40, 0))
    a.comp.update({'mode': 'stay', 'moving': False})
    park(a, a.red_giant, shell.pos + Vec3(-50, 0, 0))
    a.red_state = 'pursue'
    a.red_health = 100.0
    a.human.setPos(ground(a, shell.entrance_point().x, shell.entrance_point().y))
    a.enter_shell(shell)
    hits0 = a.combat_hits['giant']
    check('whistle works from the shell', a.gesture_command('whistle') and a.whistle_alert > 0)
    run(a, 25.0)
    check('Indigo answers the whistle and fights', a.combat_hits['giant'] > hits0, a.combat_hits)
    check('shell is not overturned', shell.state == 'intact' and a.hidden_shell is shell, shell.state)
    if args.shots:
        a.heading = 100
        a.distance = 60
        a.pitch = -14
        a.cam_target = Vec3(shell.pos.x, shell.pos.y, shell.pos.z + 8)
        a._place_camera(immediate=True)
        shot('p39_whistle_fight.png')
    a.exit_shell()

    # Not aware: giant far, no whistle -> it does not defend
    park(a, a.giant, a.human.getPos() + Vec3(150, 0, 0))
    park(a, a.red_giant, a.human.getPos() + Vec3(-30, 0, 0))
    a.red_state = 'pursue'
    a.whistle_alert = 0.0
    a.red_fleeing = a.red_lurking = a.red_knocked_out = a.red_recovering = False
    run(a, 0.5)
    check('a far giant does not notice danger on its own', not a.indigo_defending)

    # ---------------------------------------------------------------- soak
    park_red_far(a)
    reset_human(a)
    import random
    rng = random.Random(9)
    t0 = time.time()
    for i in range(1200):
        if i % 80 == 0:
            a.gesture_command(rng.choice(['come', 'stay', 'lift', 'goto', 'shade', 'whistle']))
        if i % 40 == 0:
            for k in ('w', 'a', 'd', 'shift'):
                a.keys[k] = rng.random() < 0.3
            if rng.random() < 0.2:
                a._on_e_press()
                a.keys['e'] = False
            if rng.random() < 0.1:
                a.eat()
        frame(a)
    for k in a.keys:
        a.keys[k] = False
    check('1200-frame soak without errors', True, f'{(time.time() - t0) / 1200 * 1000:.1f} ms/frame (headless)')
    print('HUD:', a._hud_cache.replace('\n', ' | '))
    a.destroy()
    print('RESULT', 'FAIL' if FAILS else 'PASS', FAILS)
    sys.exit(1 if FAILS else 0)


if __name__ == '__main__':
    main()
