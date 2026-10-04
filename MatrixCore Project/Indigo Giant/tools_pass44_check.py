"""Pass 44 check: stability and performance.

Covers every item from the Pass 43 audit (B1-B16), the new input gate, the sky and the
lighting fix, and a soak that asserts the frame time stays flat while the world grows.

    python tools_pass44_check.py            (about 3-4 minutes)
    python tools_pass44_check.py --long     (adds a 30-minute soak, ~20+ minutes wall time)
"""
from __future__ import annotations

import glob
import json
import math
import os
import random
import sys
import tempfile
import time
from pathlib import Path

from panda3d.core import InternalName, Point3, ShaderAttrib, Vec3

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='indigo_save44_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
LONG = '--long' in sys.argv
_ARGS = list(sys.argv)
sys.argv = sys.argv[:1]

import controls   # noqa: E402
import daycycle   # noqa: E402
import flora      # noqa: E402
import main as game   # noqa: E402
import savegame   # noqa: E402

FAILS = []
CLOCK = [0.0]
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def frame(a, dt=1 / 30.0, move=None):
    """One frame of the game in the same order as the live tasks."""
    CLOCK[0] += dt
    t = CLOCK[0]
    move = move or Vec3(0, 0, 0)
    if a.controlled_name == 'giant':
        a._apply_giant_heavy_input(move, dt, t)
    elif not a.world_frozen():
        a._apply_controlled_move(move, dt, t)
    if not a.world_frozen():
        a._update_indigo_defender(dt, t)
        a._update_companion(dt)
        a._update_red_giant(dt, t)
    a.survival_step(dt)
    a._shadow_accum += dt
    a._proxy_accum = getattr(a, '_proxy_accum', 0.0) + dt
    if a._shadow_accum >= 1.0 / game.SHADOW_UPDATE_HZ:
        a._shadow_accum = 0.0
        a._fit_shadow_camera()
    if a._proxy_accum >= 1.0 / game.SHADE_QUERY_HZ:
        a._proxy_accum = 0.0
        a._update_actor_shadows()
    a.service_stream_queue()


def run(a, seconds, dt=1 / 30.0):
    for _ in range(int(round(seconds / dt))):
        frame(a, dt)


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def park_red(a, dist=900.0):
    p = a.human.getPos() + Vec3(dist, 0, 0)
    a.red_giant.setPos(ground(a, p.x, p.y))
    a.red_state = 'idle'


def new_app(**kw):
    kw.setdefault('persist', True)
    return game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, save_dir=TMP, **kw)


def near_shell(a):
    hp = a.human.getPos(a.render)
    shells = [s for s in a.shells.shells.values() if s.state == 'intact' and not s.held and not s.occupied]
    return min(shells, key=lambda s: math.hypot(s.pos.x - hp.x, s.pos.y - hp.y))


def vec_input(np, name):
    return np.getAttrib(ShaderAttrib).getShaderInputVector(InternalName.make(name))


def reload_app(old):
    old.save_game('check')
    old.destroy()
    b = new_app()
    b.time_frozen = True
    return b


def main():
    a = new_app(new_game=True)
    a.time_frozen = True
    a.heat_factor_override = 0.0
    park_red(a)
    run(a, 0.5)

    # ------------------------------------------------------------ input gate (B3)
    a.bag('human')['pod'] = 2
    a.human_health = 50.0
    a.toggle_panel('menu')
    before = (a.bag('human')['pod'], a.controlled_name)
    a.eat()
    a._toggle_control()
    ok_gesture = a.gesture_command('come')
    ok_sleep = a.request_sleep()
    a._on_e_press()
    check('B3 Esc menu blocks eat, TAB, gestures, sleep and E',
          (a.bag('human')['pod'], a.controlled_name) == before and not ok_gesture and not ok_sleep
          and not a.keys.get('e'), f'pods {a.bag("human")["pod"]}, control {a.controlled_name}')
    a.keys['e'] = False

    # ------------------------------------------------------------ menu -> controls (B4)
    a.toggle_panel('help')
    in_help = (a.panel_name, a.paused)
    a.close_panel()
    back = (a.panel_name, a.paused)
    a.close_panel()
    check('B4 controls opened from the menu keep the game paused, then return to the menu',
          in_help == ('help', True) and back == ('menu', True) and a.panel_name is None and not a.paused,
          f'help {in_help}, back {back}')
    a.toggle_panel('help')
    check('    F1 on its own does not pause', a.panel_name == 'help' and not a.paused)
    a.close_panel()

    # ------------------------------------------------------------ panel rebuilds (B10)
    a.toggle_panel('craft')
    first = a.panel
    run(a, 2.0)
    same = a.panel is first
    a.bag('human')['fibre'] += 1
    run(a, 1.0)
    check('B10 the make panel is not rebuilt while nothing changes (clicks are not eaten)',
          same and a.panel is not first, f'kept {same}, rebuilt after change {a.panel is not first}')
    a.close_panel()

    # ------------------------------------------------------------ hide during pickup (B1)
    s = near_shell(a)
    a.comp.update({'mode': 'pickup', 'phase': 'approach'})
    refused = not a.enter_shell(s)
    a.comp.update({'mode': 'stay', 'phase': ''})
    check('B1 you cannot hide in a shell while Indigo is picking you up', refused and a.hidden_shell is None)

    # ------------------------------------------------------------ sleep (B2 / B9)
    camp = near_shell(a)
    a.camp_shell = camp
    a.hour, a.day = 21.0, 2
    a._do_sleep()
    check('B2 sleeping without a shell keeps the old camp', a.camp_shell is camp)
    a.hour, a.day = 2.5, 5
    a._do_sleep()
    check('B9 sleeping after midnight still starts a new day', a.day == 6, f'day {a.day}')

    # ------------------------------------------------------------ jump (B11)
    a.jump_states['human']['active'] = True
    no_gesture = not a.gesture_command('stay')
    a.keys['e'] = True
    a.e_hold.update({'spent': False, 't': 0.3, 'kind': 'dig', 'target': None})
    a._update_e_hold(1 / 30)
    held = a.e_hold['t']
    a.keys['e'] = False
    a.jump_states['human']['active'] = False
    check('B11 no gestures or E-holds in mid-air', no_gesture and held == 0.0, f'hold t {held}')

    # ------------------------------------------------------------ downed while riding (B6)
    a.carried = True
    a.comp.update({'mode': 'carry', 'phase': ''})
    a._down_human()
    run(a, 0.3)
    check('B6 a downed rider falls off and Indigo waits', not a.carried and a.comp['mode'] == 'stay')
    a._retry_after_human_down()
    a.comp.update({'mode': 'pickup', 'phase': 'approach', 'elapsed': 0.0})
    a.human_alive = False
    run(a, 0.2)
    aborted = a.comp['mode'] == 'stay' and not a.carried
    a.human_alive = True
    a.human_health = 100.0
    check('    a pickup already under way is dropped when the human is down', aborted)
    park_red(a)

    # ------------------------------------------------------------ scraps (B12)
    br = next((b for b in a.flora.active.values() if not b.smashed and b.grow >= 1.0), None)
    if br is not None:
        a.flora.smash(br)
    n = len(a.flora.scraps)
    a.flora.update(flora.SCRAP_LIFETIME + 1.0)
    check('B12 unpicked scraps sink back into the sand', n > 0 and not a.flora.scraps,
          f'{n} -> {len(a.flora.scraps)}')

    # ------------------------------------------------------------ duplicate keys (B13)
    folder = Path(tempfile.mkdtemp(prefix='indigo_keys_'))
    (folder / 'controls.json').write_text(json.dumps({'eat': 'w', 'jump': 'q'}), encoding='utf-8')
    b = controls.load(folder)
    keys = [k for k in b.values()]
    check('B13 a key bound twice goes back to its default',
          b['eat'] == 'g' and b['jump'] == 'space' and len(keys) == len(set(keys)), f'eat {b["eat"]}, jump {b["jump"]}')

    # ------------------------------------------------------------ night sight in shells (B16)
    a.hour = 23.0
    a._apply_time(force=True)
    s = near_shell(a)
    e = s.entrance_point()                     # Pass 55: measured from the shell you hide in
    a.human.setPos(ground(a, e.x, e.y))
    hp = a.shells.inner_spot(s)
    d = game.RED_DETECTION_RANGE * 0.8
    a.red_giant.setPos(ground(a, hp.x + d, hp.y))
    a.red_state = 'idle'
    a.enter_shell(s)
    saw = a.red_saw_hide
    a.exit_shell()
    check('B16 at night the Red Giant needs to be closer to see you hide', not saw,
          f'{d:.0f} m, night range {a.red_detection_range():.0f} m')
    park_red(a)
    a.hour = 12.0
    a._apply_time(force=True)

    # ------------------------------------------------------------ sky and lighting
    sky = a.sky
    check('sky dome exists, is hidden from the shadow camera and draws first',
          sky is not None and sky.np.isHidden(game.SHADOW_CAMERA_MASK) and sky.np.getBinName() == 'background')
    fog = daycycle.palette_at(a.hour)[1]
    hz = vec_input(sky.np, 'sky_horizon')
    check('sky horizon equals the fog colour (no seam with distant terrain)',
          all(abs(hz[i] - fog[i]) < 1e-4 for i in range(3)))
    a.pitch = -5.0
    a._place_camera(immediate=True)
    lv = vec_input(a.render, 'sketch_light_dir_view')
    check('noon light is "up" in shader view space (ground seen at low pitch is lit, not inked)',
          lv[1] > 0.85, f'view-space light {lv[0]:.2f}, {lv[1]:.2f}, {lv[2]:.2f}')
    chunk = next(iter(a.loaded.values()))
    ink = chunk.getAttrib(ShaderAttrib).getShaderInput(InternalName.make('edge_ink')).getVector()[0] \
        if chunk.hasAttrib(ShaderAttrib) else None
    check('terrain uses a faint ink edge', ink is not None and abs(ink - game.TERRAIN_EDGE_INK) < 1e-6, f'{ink}')

    # ------------------------------------------------------------ save robustness (B5)
    savegame.backup_unreadable(TMP)          # clear any earlier journey
    for f in glob.glob(str(TMP / 'journey.unreadable-*.json')):
        os.remove(f)
    (TMP / savegame.SAVE_NAME).write_text('{ this is not json', encoding='utf-8')
    data = savegame.read_save(TMP)
    backups = glob.glob(str(TMP / 'journey.unreadable-*.json'))
    check('B5 an unreadable save is kept aside, never overwritten',
          data is None and len(backups) == 1 and not (TMP / savegame.SAVE_NAME).exists(), f'{len(backups)} backup(s)')

    # ------------------------------------------------------------ save / load state (B7 B8 B14 B15)
    a.persist = True
    s = near_shell(a)
    flip = next(x for x in a.shells.shells.values() if x.state == 'intact' and x is not s and not x.held)
    a.shells.start_flip(flip)
    flip_pid = flip.pid
    a.enter_shell(s)
    hidden_pid = s.pid
    a.red_giant.setPos(ground(a, a.human.getPos().x + 400, a.human.getPos().y))
    a._knock_out_red()
    a.red_knockout_remaining = 17.0
    a.comp['mode'] = 'follow'
    snap = a.snapshot()
    check('B14 a shell caught mid-overturn is saved overturned',
          next(r for r in snap['world']['shells'] if r['pid'] == repr(flip_pid))['state'] == 'flipped')
    b = reload_app(a)
    check('B7 hidden in a shell is restored (Pass 55: standing inside it, visible)',
          b.hidden_shell is not None and b.hidden_shell.pid == hidden_pid and not b.human.isHidden())
    check('B8 a knocked-out Red Giant stays knocked out after a load',
          b.red_knocked_out and abs(b.red_knockout_remaining - 17.0) < 0.2 and b.red_health <= 0.0,
          f'ko {b.red_knocked_out}, {b.red_knockout_remaining:.1f} s left')
    check('B16 companion mode is restored', b.comp['mode'] == 'follow', b.comp['mode'])
    check('B16 the landmark stinger does not replay on load',
          b._snd['visited'] == b.landmarks.visited_count())
    hp = b.human.getPos(b.render)
    check('B15 terrain streams around you right after a load',
          math.hypot(b.cam_target.x - hp.x, b.cam_target.y - hp.y) < 30.0
          and (game.world_to_chunk(hp.x), game.world_to_chunk(hp.y)) in b.loaded)

    # carried + held shell
    b.exit_shell()
    park_red(b)
    b.red_knocked_out = False
    b.red_health = 100.0
    b.red_state = 'idle'
    held = near_shell(b)
    held.held = True
    b.giant_held_shell = held
    b.carried = True
    b.comp.update({'mode': 'carry', 'phase': ''})
    c = reload_app(b)
    check('B7 riding on Indigo and the shell it holds are restored',
          c.carried and c.comp['mode'] == 'carry' and c.giant_held_shell is not None
          and c.giant_held_shell.pid == held.pid)
    c.carried = False
    c.comp.update({'mode': 'stay'})
    c.persist = False

    # red fleeing
    c.red_fleeing = True
    c.red_health = 20.0
    c.persist = True
    d = reload_app(c)
    check('B8 a fleeing Red Giant is still fleeing after a load', d.red_fleeing and d.red_state == 'flee')
    d.persist = False
    d.destroy()

    # ------------------------------------------------------------ performance
    soak(minutes=3.0, label='3-minute')
    if LONG:
        soak(minutes=30.0, label='30-minute')

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


def soak(minutes: float, label: str):
    """Random play that keeps travelling (so the world lists grow) while the logic time
    per frame is measured.  The last window must not be much slower than the first."""
    a = new_app(new_game=True, persist=False)
    a.heat_factor_override = 0.3
    rng = random.Random(44)
    dt = 1 / 30.0
    frames = int(minutes * 60 * 30)
    window = 1800
    medians = []
    samples = []
    peak_scraps = peak_active = busy = 0
    start = Point3(a.human.getPos(a.render))
    t0 = time.perf_counter()
    errors = []
    for i in range(frames):
        if i % 150 == 0:
            a.keys['w'] = rng.random() < 0.85
            a.keys['shift'] = rng.random() < 0.5
            a.heading += rng.uniform(-35, 35)
            r = rng.random()
            try:
                if r < 0.10:
                    a.gesture_command(rng.choice(['come', 'stay', 'lift', 'shade', 'whistle']))
                elif r < 0.15:
                    a.eat()
                elif r < 0.22:
                    a._on_e_press()
                    a.keys['e'] = rng.random() < 0.5
                elif r < 0.24:
                    a._toggle_control()
                elif r < 0.26:
                    a.request_sleep()
            except Exception as exc:          # noqa: BLE001
                errors.append(repr(exc))
        if i % 1200 == 600:
            # jump ahead along the heading so the soak covers kilometres of new desert
            hp = a.human.getPos(a.render)
            h = math.radians(a.heading)
            x, y = hp.x + math.sin(h) * 180.0, hp.y + math.cos(h) * 180.0
            if not a.carried and a.hidden_shell is None:
                a.human.setPos(ground(a, x, y))
            park_red(a, 700.0)
        if not a.human_alive and i % 90 == 0:
            a._retry_after_human_down()
        h = math.radians(a.heading)
        move = Vec3(math.sin(h), math.cos(h), 0) if a.keys.get('w') else Vec3(0, 0, 0)
        s = time.perf_counter()
        try:
            frame(a, dt, move)
            a._update_visibility(dt)                # the live tasks also run these
            a._place_camera(immediate=False, dt=dt)
        except Exception:                     # noqa: BLE001
            import traceback
            errors.append(traceback.format_exc())
            break
        samples.append(time.perf_counter() - s)
        peak_scraps = max(peak_scraps, len(a.flora.scraps))
        peak_active = max(peak_active, len(a.flora.active))
        busy += 1 if (a.human_alive and a.hidden_shell is None and not a.world_frozen()) else 0
        if len(samples) == window:
            samples.sort()
            medians.append(samples[window // 2] * 1000.0)
            samples = []
    wall = time.perf_counter() - t0
    end = a.human.getPos(a.render)
    print(f'    soak: {wall:.0f} s wall, {busy / frames:.0%} of frames out and about, '
          f'{math.hypot(end.x - start.x, end.y - start.y):.0f} m from the start, {len(a.flora.branches)} branches generated')
    check(f'{label} soak ran without errors', not errors, errors[0].splitlines()[-1] if errors else f'{wall:.0f} s wall')
    first, last = medians[0], medians[-1]
    check(f'{label} soak: logic time stays flat while the world grows',
          last <= max(first * 1.5, first + 1.5),
          'per-minute medians ' + ' '.join(f'{m:.1f}' for m in medians) + ' ms')
    check(f'{label} soak: scraps and live branches stay bounded',
          peak_scraps <= flora.MAX_SCRAPS and peak_active < 400, f'scraps {peak_scraps}, active branches {peak_active}')
    a.destroy()


if __name__ == '__main__':
    if '--soak-only' in _ARGS:
        soak(30.0, '30-minute')
        print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
        os._exit(0 if not FAILS else 1)
    main()
