"""A long automated playthrough: a scripted player lives through several in-game days using the
real game loop (every task, at a fixed 30 fps), pressing the real keys. It watches for:

  - errors             any exception from any task
  - bad positions      a character not finite, or far off the ground when it should stand on it
  - getting stuck      the player holding W but not moving for 20 s (terrain, places, bodies,
                       shell walls and doorways)
  - stuck states       Indigo knocked out > 1 day, the red one in one busy state > 4 min, a
                       gesture / E-hold / panel that never ends
  - frame time         game logic per frame (drawing is switched off; median, 95th percentile, worst)
and reports what happened: places found, fights, knock-outs, sleeps, collapses, saves.

    python tools_playthrough.py                 3 in-game days (~48 min of game time)
    python tools_playthrough.py --days 1 --seed 7
    python tools_playthrough.py --with-sound     sound on (off by default: a machine without a
                                                 real sound device stalls on every play)
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
import tempfile
import time
import traceback
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='indigo_play_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
ARGS = argparse.ArgumentParser()
ARGS.add_argument('--days', type=float, default=3.0)
ARGS.add_argument('--seed', type=int, default=11)
ARGS.add_argument('--with-sound', action='store_true',
                  help='keep the real sound device (on a machine without one its stalls pollute frame times)')
args = ARGS.parse_args()
sys.argv = sys.argv[:1]

from panda3d.core import ClockObject, Point3, loadPrcFileData   # noqa: E402
if not args.with_sound:
    loadPrcFileData('', 'audio-library-name null')     # measure the game, not the sound device

import main as game   # noqa: E402

GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
FPS = 30.0


class Player:
    """A simple scripted player that uses the real key bindings."""

    def __init__(self, a, seed):
        self.a = a
        self.rng = random.Random(seed)
        self.goal = None
        self.goal_t = 0.0
        self.held = set()
        self.e_hold = 0.0
        self.log = Counter()
        self.next_gesture = 30.0
        self.ride_until = None
        self.trip = None                 # Pass 57: walking into a shell to cool off, then out again

    def key(self, action, down=True):
        k = self.a.bindings[action]
        if down and action not in self.held:
            self.a.messenger.send(k)
            self.held.add(action)
        elif not down and action in self.held:
            self.a.messenger.send(k + '-up')
            self.held.discard(action)

    def tap(self, action):
        k = self.a.bindings[action]
        self.a.messenger.send(k)
        self.a.messenger.send(k + '-up')
        self.log['tap ' + action] += 1

    def release_all(self):
        for act in list(self.held):
            self.key(act, False)

    def face(self, p):
        a = self.a
        focus = a.human.getPos(a.render) if a.controlled_name == 'human' else a.giant.getPos(a.render)
        a.heading = math.degrees(math.atan2(p.x - focus.x, p.y - focus.y))

    # ------------------------------------------------------------ Pass 57: shelter in a shell
    def _local_point(self, s, lx, ly):
        h = math.radians(s.heading)
        return Point3(s.pos.x + lx * math.cos(h) - ly * math.sin(h), s.pos.y + lx * math.sin(h) + ly * math.cos(h), 0)

    def shell_trip(self, t):
        """Hot by day: walk to an unbroken shell, in through its mouth, cool off, walk out.
        Returns True while the trip is steering the player."""
        a = self.a
        geom = __import__('desert_geom')
        tr = self.trip
        hp = a.human.getPos(a.render)
        if tr is None and not a.carried:
            inside = a.shells.inside(hp, limit=1.0)
            if inside is not None and not a.sleeping():
                # wandered in (the doorway draws you in if you walk into its frame): walk out again
                tr = self.trip = {'s': inside, 'phase': 'leave', 'until': t + 60.0, 'wandered': True}
                self.log['wandered into a shell'] += 1
        if tr is None:
            if a.heat < 50.0 or a.carried or a.is_night() or a.giant_knocked_out:
                return False
            if a.red_state in ('pursue', 'stomp') and a._human_red_distance() < 90.0:
                return False
            s = a.shells.nearest(hp, 220.0, states=('intact',))
            if s is None or s.occupied:
                return False
            tr = self.trip = {'s': s, 'phase': 'approach', 'until': t + 240.0}
            self.log['shell trips'] += 1
        s = tr['s']
        why = ('too long' if t > tr['until'] else 'carried' if a.carried else 'shell overturned' if s.state == 'flipped'
               else 'shell lifted' if s.held else 'collapsed' if not a.human_alive else None)
        if why:
            self.trip = None
            self.log['shell trip given up: ' + why] += 1
            return False
        lx, ly = a.shells._local(s, hp)
        if tr['phase'] == 'approach':
            if ly < geom.SHELL_RY * 0.6:           # behind or beside it: go round to the front
                side = 1.0 if lx >= 0 else -1.0
                goal = self._local_point(s, side * (geom.SHELL_RX + 2.5), geom.SHELL_RY * 1.0)
                if ly > -0.5 and abs(lx) > geom.SHELL_RX + 1.5:
                    goal = s.entrance_point()
            else:
                goal = s.entrance_point()
            if (hp - s.entrance_point()).length() < 1.2 or a.hidden_shell is s:
                tr['phase'] = 'enter'
        elif tr['phase'] == 'enter':
            goal = a.shells.inner_spot(s)
            if a.hidden_shell is s and (hp - goal).length() < 0.6:
                tr.update(phase='rest', rest_until=t + 90.0)
                self.log['shell entered'] += 1
        elif tr['phase'] == 'rest':
            self.key('move_forward', False)
            self.key('jog', False)
            if a.heat < 8.0 or t > tr['rest_until'] or a.is_night():
                tr['phase'] = 'leave'
                self.log['shell rests'] += 1
            return True
        else:
            goal = self._local_point(s, 0.0, geom.SHELL_RY + 6.0)
            if a.shells._q(lx, ly) > 1.4:
                self.trip = None
                self.log['walked out'] += 1
                if tr.get('wandered'):
                    # heading somewhere behind the shell: go on out the front instead of back in
                    self.goal = self._local_point(s, self.rng.uniform(-60.0, 60.0), self.rng.uniform(150.0, 400.0))
                    self.goal_t = t + 150.0
                return False
        self.face(goal)
        self.key('move_forward', True)
        self.key('jog', tr['phase'] == 'approach' and (hp - goal).length() > 15.0 and a.stamina > 30 and not a.winded)
        return True

    # ------------------------------------------------------------ decide
    def think(self, t, dt):
        a = self.a
        if a.panel_name is not None:
            a.close_panel()
        if not a.human_alive:
            self.release_all()
            self.tap('retry')
            self.log['collapsed'] += 1
            return
        hp = a.human.getPos(a.render)
        night = a.is_night()
        # asleep / fading: let it run
        if a.sleeping():
            self.release_all()
            return
        # Indigo knocked out: go and wake it
        if a.giant_knocked_out and a.giant_getup < 0:
            self.goal = a.giant.getPos(a.render)
            if a.near_downed_indigo():
                self.release_all()
                self.tap('use')
                self.log['wake taps'] += 1
                return
        # red one knocked out and we carry poison: feed it
        if a.red_knocked_out and a.bag('human').get('bane', 0) > 0 and a.red_weakness < 3:
            if a.can_feed_red():
                self.release_all()
                self.tap('use')
                self.log['doses fed'] += 1
                return
            self.goal = a.red_giant.getPos(a.render)
        # danger: the red one close and hunting
        if a.red_state in ('pursue', 'stomp') and a._human_red_distance() < 70.0 and not a.carried:
            if self.rng.random() < 0.02:
                self.tap('whistle')
        # night: sleep beside Indigo
        if night and not a.carried and a.hidden_shell is None:
            ok, _why = a.can_sleep()
            if ok:
                self.release_all()
                self.tap('sleep')
                self.log['sleep requests'] += 1
                return
            self.goal = a.giant.getPos(a.render)
            if a.comp.get('mode') != 'follow' and self.rng.random() < 0.01:
                self.tap('come')
        # hurt: eat
        if a.human_health < 45 and self.rng.random() < 0.05:
            self.tap('eat')
        # hot: shelter in a shell for a while
        if self.shell_trip(t):
            return
        # riding for a while now and then
        if self.ride_until is not None:
            if t > self.ride_until or night:
                if a.carried:
                    self.tap('lift')
                self.ride_until = None
            else:
                self.key('move_forward', True)
                return
        if t > self.next_gesture and not night:
            self.next_gesture = t + self.rng.uniform(40, 120)
            g = self.rng.choice(['come', 'come', 'shade', 'lift', 'stay'])
            self.tap(g)
            if g == 'lift':
                self.ride_until = t + self.rng.uniform(40, 120)
            return
        # E: whatever is here (dig, search, drink, climb, smash...)
        kind, _target = a._e_target()
        if kind is not None and kind not in ('hide',) and self.e_hold < 3.2:
            self.key('move_forward', False)
            self.key('use', True)
            self.e_hold += dt
            if self.e_hold >= 3.0:
                self.log['e ' + kind] += 1
            return
        if self.e_hold > 0:
            self.key('use', False)
            self.e_hold = 0.0
        # walk / jog toward a goal
        if self.goal is None or t > self.goal_t or (hp - self.goal).length() < 8.0:
            spot = a.places.unfound_near(hp, 900.0, night) if self.rng.random() < 0.6 else None
            if spot is not None:
                self.goal = Point3(spot.pos)
            else:
                ang = self.rng.uniform(0, 2 * math.pi)
                r = self.rng.uniform(150, 600)
                self.goal = Point3(hp.x + math.cos(ang) * r, hp.y + math.sin(ang) * r, 0)
            self.goal_t = t + 150.0
        self.face(self.goal)
        self.key('move_forward', True)
        self.key('jog', a.stamina > 55 and not a.winded)


def main():
    t0 = time.time()
    clock = ClockObject.getGlobalClock()
    clock.setMode(ClockObject.MNonRealTime)
    clock.setFrameRate(FPS)
    import json
    TMP.mkdir(parents=True, exist_ok=True)
    (TMP / 'settings.json').write_text(json.dumps({'resolution': '1280x720', 'fullscreen': False, 'msaa': 0,
                                                   'vsync': False, 'hints': False}))
    # a real (hidden) window, so every game task runs exactly as in play; drawing is switched off
    a = game.StreamingTerrainWithGiant(giant_glb=GLB, new_game=True, persist=True, save_dir=TMP, show_title=False)
    a.win.setActive(False)
    p = Player(a, args.seed)
    frames = int(args.days * 16.3 * 60 * FPS)          # a day is 12 min of light + ~4 min of night
    problems = []
    frame_ms = []
    still_t = 0.0
    last_pos = a.human.getPos(a.render)
    state_t = {'red': [None, 0.0], 'ko': 0.0, 'gesture': 0.0, 'panel': 0.0}
    states = Counter()
    save_every = int(8 * 60 * FPS)
    saves = 0
    start_day = a.day
    for f in range(frames):
        t = f / FPS
        try:
            p.think(t, 1 / FPS)
            s = time.perf_counter()
            a.taskMgr.step()
            frame_ms.append((time.perf_counter() - s) * 1000.0)
        except Exception:                                            # noqa: BLE001
            problems.append(('ERROR', t, traceback.format_exc()))
            break
        # ---- watchers (4 times a second)
        if f % 8:
            continue
        dt = 8 / FPS
        for name, node in (('human', a.human), ('indigo', a.giant), ('red', a.red_giant)):
            q = node.getPos(a.render)
            if not all(math.isfinite(v) for v in (q.x, q.y, q.z)):
                problems.append(('NaN position', t, name))
            ground = a.field.height(q.x, q.y)
            riding = name == 'human' and a.carried
            jumping = a.jump_states.get('human' if name == 'human' else 'giant', {}).get('active') if name != 'red' else False
            if not riding and not jumping and abs(q.z - ground) > (2.5 if name == 'human' else 6.0):
                problems.append(('off the ground', t, f'{name} {q.z - ground:+.1f} m'))
        hp = a.human.getPos(a.render)
        moving_wanted = 'move_forward' in p.held and a.controlled_name == 'human' and not (
            a.carried or a.sleeping() or a.human_dazed > 0 or not a.human_alive or a.gesture
            or a.world_frozen() or a.human_is_smashing() or a.e_hold['t'] > 0)
        if moving_wanted and (hp - last_pos).length() < 0.05:
            still_t += dt
            if still_t > 20.0:
                near = a.shells.nearest(hp, 12.0)
                where = ''
                if near is not None:
                    lx, ly = a.shells._local(near, hp)
                    where = (f'; {near.state} shell at local ({lx:.1f}, {ly:.1f}) q {a.shells._q(lx, ly):.2f}, '
                             f'trip {p.trip["phase"] if p.trip else None}')
                problems.append(('stuck', t, f'player holding W but not moving at {hp.x:.0f},{hp.y:.0f}{where}'))
                still_t = 0.0
                p.goal = None
        else:
            still_t = 0.0
        last_pos = hp
        rs = a.red_state
        states[rs] += dt
        if rs == state_t['red'][0]:
            state_t['red'][1] += dt
            if rs in ('melee', 'stomp', 'meal', 'forage', 'watching', 'bait', 'eating') and state_t['red'][1] > 240:
                problems.append(('red stuck', t, rs))
                state_t['red'][1] = -1e9
        else:
            state_t['red'] = [rs, 0.0]
        state_t['ko'] = state_t['ko'] + dt if a.giant_knocked_out else 0.0
        if state_t['ko'] > 17 * 60:
            problems.append(('Indigo down > a day', t, ''))
            state_t['ko'] = -1e9
        state_t['gesture'] = state_t['gesture'] + dt if a.gesture else 0.0
        if state_t['gesture'] > 10:
            problems.append(('gesture never ends', t, str(a.gesture)))
            state_t['gesture'] = -1e9
        if f % save_every == 0 and f and a.human_alive:
            saves += a.save_game('playthrough') is not False
    # ---- reload what was saved into a fresh game
    tasks = sorted(((t.getName(), t.getAverageDt() * 1000.0, t.getMaxDt() * 1000.0) for t in a.taskMgr.getAllTasks()
                    if t.getMaxDt() > 0.0), key=lambda r: -r[2])[:10]
    p.release_all()
    a.persist = True
    ok_save = a.save_game('end')
    snap_day, snap_found = a.day, a.places.found_count()
    report = {
        'wall s': round(time.time() - t0),
        'game days': round(args.days, 1), 'day reached': a.day - start_day + 1,
        'frames': len(frame_ms),
        'frame ms p50/p95/max': (round(sorted(frame_ms)[len(frame_ms) // 2], 2),
                                 round(sorted(frame_ms)[int(len(frame_ms) * 0.95)], 2), round(max(frame_ms), 1)),
        'places found': a.places.found_count(), 'kinds': len(a.found_kinds), 'stats': dict(a.stats),
        'red time by state (s)': {k: round(v) for k, v in states.most_common()},
        'player': dict(p.log), 'saves': saves + bool(ok_save),
        'slowest tasks (avg ms / worst ms)': [(n, round(av, 2), round(mx, 1)) for n, av, mx in tasks],
    }
    a.destroy()
    try:
        b = game.StreamingTerrainWithGiant(giant_glb=GLB, persist=True, save_dir=TMP, show_title=False)
        report['reload'] = 'ok' if (b.day == snap_day and b.places.found_count() == snap_found) else \
            f'MISMATCH day {b.day}/{snap_day} places {b.places.found_count()}/{snap_found}'
    except Exception:                                                # noqa: BLE001
        problems.append(('ERROR on reload', 0, traceback.format_exc()))
    print('REPORT')
    for k, v in report.items():
        print(f'  {k}: {v}')
    print('PROBLEMS', len(problems))
    seen = Counter()
    for kind, t, detail in problems:
        seen[kind] += 1
        if seen[kind] <= 12:
            print(f'  [{kind}] t={t / 60:.1f} min  {detail}')
    for kind, n in seen.items():
        if n > 12:
            print(f'  ... {kind} x{n}')
    os._exit(0 if not problems else 1)


if __name__ == '__main__':
    main()
