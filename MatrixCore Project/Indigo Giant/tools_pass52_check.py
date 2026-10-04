"""Pass 52 check: feet that match the ground, for every body.

The key measurement is FOOT SLIP. While a foot is planted it should not slide across the
ground. Slip = how far the planted foot slides / how far the body travels in the same frames.
  0.0   perfect
  1.3   the old human jog (the feet swept 5.9 m/s under a body moving 2.5 m/s: running in place)

    python tools_pass52_check.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

from panda3d.core import Point3, Vec3

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='indigo_save52_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import desert         # noqa: E402
import locomotion     # noqa: E402
import main as game   # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
MARGIN = 0.06               # the game may add at most 6% slip to what is built into the animation itself


def slip_ok(clip, slip):
    return slip <= locomotion.CLIP_BUILT_IN_SLIP[clip] + MARGIN


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


class SlipMeter:
    """Watches both forefeet of one actor; measures sliding while each is planted.
    'Planted' is judged from the animation itself (the ball joint within 1.2 cm of its lowest
    in the clip), not from the terrain - on a slope a giant's body rises and falls."""

    def __init__(self, a, actor, node):
        self.a, self.actor, self.node = a, actor, node
        self.frames = []
        self.idx = [actor.skin.node_index['ball_l'], actor.skin.node_index['ball_r']]

    def sample(self, clip_time):
        local = self.actor.joint_local_points(clip_time)
        pts = []
        for joint, i in zip(('ball_l', 'ball_r'), self.idx):
            p = self.actor.joint_world_point(joint, clip_time, self.a.render)
            pts.append((p.x, p.y, float(local[i][2])))
        body = self.node.getPos(self.a.render)
        self.frames.append((body.x, body.y, pts, self.actor.current_clip))

    def slip(self):
        slid = travelled = 0.0
        for f in (0, 1):
            floor = {}
            for fr in self.frames:
                floor[fr[3]] = min(floor.get(fr[3], 9e9), fr[2][f][2])
            for (bx0, by0, p0, c0), (bx1, by1, p1, c1) in zip(self.frames, self.frames[1:]):
                if c0 != c1:
                    continue
                if not (p0[f][2] <= floor[c0] + 0.012 and p1[f][2] <= floor[c1] + 0.012):
                    continue
                slid += math.hypot(p1[f][0] - p0[f][0], p1[f][1] - p0[f][1])
                travelled += math.hypot(bx1 - bx0, by1 - by0)
        return slid / travelled if travelled > 1e-6 else float('nan'), \
            sum(math.hypot(b[0] - a_[0], b[1] - a_[1]) for a_, b in zip(self.frames, self.frames[1:]))


def reset(a):
    a.human.setPos(ground(a, a.human_base_pos.x, a.human_base_pos.y))
    a.giant.setPos(ground(a, a.human_base_pos.x + 40, a.human_base_pos.y))
    a.red_giant.setPos(ground(a, a.human_base_pos.x + 3000, a.human_base_pos.y))
    a.red_state = 'idle'
    a.heat = 0.0
    a.stamina = 100.0
    a.winded = False


def main():
    # ------------------------------------------------------------ the tables match the animation file
    bad = []
    for clip, stride in locomotion.CLIP_STRIDE.items():
        if clip == 'Walk_Formal_Loop':
            continue
        m, (tl, tr), _built_in = locomotion.measure_clip(GLB, clip)
        cl, cr = locomotion.CLIP_CONTACTS[clip]
        dphase = min(abs(tl - cl), 1 - abs(tl - cl)) + min(abs(tr - cr), 1 - abs(tr - cr))
        if abs(m - stride) / stride > 0.02 or dphase > 0.06:
            bad.append((clip, round(m, 2), stride, round(tl, 3), round(tr, 3)))
    check('each clip\'s stride speed and touchdowns match the animation file', not bad, str(bad))

    rates = {}
    for body, scale in (('human', 1.0), ('giant', locomotion.GIANT_SCALE)):
        for g, (clip, spd) in locomotion.GAITS[body].items():
            rates[f'{body} {g}'] = round(locomotion.playback_rate(clip, spd, scale), 2)
    check('every gait plays near its natural cadence (rate 0.3 - 1.5)', all(0.3 <= r <= 1.5 for r in rates.values()),
          str(rates))

    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, new_game=True, persist=False)
    a.time_frozen = True
    a.heat_factor_override = 0.0

    # ------------------------------------------------------------ the human: every gait
    dt = 1 / 60.0
    slips = {}
    for g in ('walk', 'jog', 'sprint', 'crouch'):
        reset(a)
        a.human_motion_speed = locomotion.speed('human', g)          # measure at full pace
        meter = SlipMeter(a, a.human_actor, a.human)
        start = a.human.getPos()
        for i in range(int(3.0 / dt)):
            a.stamina = 100.0
            a._apply_controlled_move(Vec3(0, 1, 0), dt, i * dt, gait=g)
            meter.sample(a.move_clocks['human'])
        slip, _t = meter.slip()
        moved = (a.human.getPos() - start).length() / 3.0
        slips[g] = (round(slip, 3), round(moved, 2))
    check('the human\'s feet stay planted at every gait (within 6% of what each animation allows)',
          all(slip_ok(locomotion.gait('human', g)[0], slips[g][0]) for g in ('walk', 'jog', 'sprint', 'crouch')),
          f'slip, m/s: {slips}')
    check('the human moves at its gait speeds (Pass 58: walk 1.45, jog 5.6, sprint 8.4, crouch 0.95 m/s)',
          all(abs(v - locomotion.speed('human', g)) < 0.15 for g, (_s, v) in slips.items()))

    # heat slows you - the feet still match
    reset(a)
    a.heat = 100.0
    a.human_motion_speed = 0.0
    meter = SlipMeter(a, a.human_actor, a.human)
    for i in range(int(3.0 / dt)):
        a.heat = 100.0
        a._apply_controlled_move(Vec3(0, 1, 0), dt, i * dt, gait='walk')
        meter.sample(a.move_clocks['human'])
    check('heat-slowed walking: the cycle slows with the body (no sliding)', slip_ok('Walk_Loop', meter.slip()[0]),
          f'slip {meter.slip()[0]:.3f}')
    a.heat = 0.0

    # quick change of pace
    reset(a)
    a.human_motion_speed = 0.0
    t_jog = None
    for i in range(60):
        a._apply_controlled_move(Vec3(0, 1, 0), dt, i * dt, gait='jog')
        if t_jog is None and a.human_motion_speed >= locomotion.speed('human', 'jog') - 1e-3:
            t_jog = (i + 1) * dt
    a._apply_controlled_move(Vec3(0, 0, 0), dt, 1.0, gait='jog')
    check('from standing to a jog in about a third of a second; letting go stops at once',
          t_jog is not None and t_jog <= 0.4 and a.human_motion_speed == 0.0, f'{t_jog} s')

    # footprints fall at the real touchdowns: two per cycle, each where a foot is
    reset(a)
    a.human_motion_speed = locomotion.speed('human', 'jog')
    before = len(a.footprints)
    clip = 'Jog_Fwd_Loop'
    total_phase = 0.0
    for i in range(int(4.0 / dt)):
        p0 = a.move_phase['human']
        a._apply_controlled_move(Vec3(0, 1, 0), dt, i * dt, gait='jog')
        total_phase += (a.move_phase['human'] - p0) % 1.0
    prints = [fp for fp in a.footprints[before:] if fp.owner == 'human'] if hasattr(a.footprints[0], 'owner') else \
        a.footprints[before:]
    expected = 2 * total_phase
    gaps = [math.hypot(p.root.getX() - q.root.getX(), p.root.getY() - q.root.getY())
            for p, q in zip(prints, prints[1:])]
    step = locomotion.CLIP_STRIDE[clip] * a.human_actor.clips[clip]['duration'] / 2
    med = sorted(gaps)[len(gaps) // 2] if gaps else 0
    check('footprints: two per stride, one step length apart (where the feet land)',
          abs(len(prints) - expected) <= 1.5 and abs(med - step) < 0.25 * step,
          f'{len(prints)} prints for {expected:.1f} expected, step {med:.2f} m (clip step {step:.2f} m)')

    # ------------------------------------------------------------ Indigo: heavy, accelerating, ridden
    for g in ('walk', 'jog', 'sprint'):
        reset(a)
        if a.controlled_name != 'giant':
            a._toggle_control()
        a.giant_motion_speed = 0.0
        a.giant_motion_heading = game.heading_toward(0.0, 1.0)      # already facing the way it will walk
        a.giant.setH(a.giant_motion_heading)
        meter = SlipMeter(a, a.giant_actor, a.giant)
        for i in range(int(8.0 / dt)):                          # includes the heavy acceleration
            a._apply_giant_heavy_input(Vec3(0, 1, 0), dt, i * dt, gait=g)
            meter.sample(a.move_clocks['giant'])
        slips[f'indigo {g}'] = round(meter.slip()[0], 3)
    for i in range(int(3.0 / dt)):                              # and braking
        a._apply_giant_heavy_input(Vec3(0, 0, 0), dt, i * dt, gait='sprint')
    a._toggle_control()
    check('Indigo\'s feet stay planted walking, striding and hurrying - speeding up and slowing down too',
          all(slip_ok(locomotion.gait('giant', g)[0], slips[f'indigo {g}']) for g in ('walk', 'jog', 'sprint')),
          str({k: v for k, v in slips.items() if k.startswith('indigo')}))

    # Indigo following you (companion AI)
    reset(a)
    a.giant.setPos(ground(a, a.human_base_pos.x + 160, a.human_base_pos.y))
    a.comp.update({'mode': 'follow', 'moving': True})
    a.giant_motion_heading = game.heading_toward(-1.0, 0.0)
    a.giant.setH(a.giant_motion_heading)
    meter = SlipMeter(a, a.giant_actor, a.giant)
    for i in range(int(6.0 / dt)):
        a._update_companion(dt)
        meter.sample(a.move_clocks['giant'])
    s_follow = meter.slip()
    check('Indigo following you: feet planted', slip_ok('Walk_Loop', s_follow[0]) and s_follow[1] > 8, f'slip {s_follow[0]:.3f}, {s_follow[1]:.0f} m')

    # the Red Giant hunting (sprint) and tracking (walk)
    reset(a)
    a.red_giant.setPos(ground(a, a.human_base_pos.x + 90, a.human_base_pos.y))
    a.red_state = 'hunting'
    a.red_motion_heading = game.heading_toward(-1.0, 0.0)
    a.red_giant.setH(a.red_motion_heading)
    meter = SlipMeter(a, a.red_giant_actor, a.red_giant)
    for i in range(int(4.0 / dt)):
        a._update_red_giant(dt, i * dt)
        meter.sample(a.red_motion_clock)
        if a._human_red_distance() < 25:
            break
    s_red = meter.slip()
    reset(a)
    a.red_giant.setPos(ground(a, a.human_base_pos.x + 400, a.human_base_pos.y))
    a.red_motion_heading = game.heading_toward(1.0, 0.0)
    a.red_giant.setH(a.red_motion_heading)
    meter2 = SlipMeter(a, a.red_giant_actor, a.red_giant)
    target = ground(a, a.human_base_pos.x + 800, a.human_base_pos.y)
    for i in range(int(6.0 / dt)):
        a._red_walk_to(target, dt, 2.0, walk_only=True)
        meter2.sample(a.red_motion_clock)
    s_track = meter2.slip()
    check('the Red Giant\'s feet stay planted hunting and walking',
          slip_ok('Walk_Loop', s_red[0]) and slip_ok('Walk_Loop', s_track[0])
          and s_red[1] > 3 and s_track[1] > 3, f'hunt {s_red[0]:.3f} ({s_red[1]:.0f} m), walk {s_track[0]:.3f} ({s_track[1]:.0f} m)')

    # ------------------------------------------------------------ shade holds whatever Indigo's breathing
    reset(a)
    spot = ground(a, a.human_base_pos.x - 150, a.human_base_pos.y - 120)
    a.human.setPos(spot)
    a.giant.setPos(ground(a, spot.x + 30, spot.y + 20))
    a.heat = 60.0
    a.gesture_command('shade')
    for i in range(int(40 / (1 / 30.0))):
        a.survival_step(1 / 30.0)
        a._update_companion(1 / 30.0)
        a._update_actor_shadows()
        if a.comp['mode'] == 'shade' and not a.comp['moving']:
            break
    held = 0
    dur = a.giant_actor.clips['Idle_Loop']['duration']
    for k in range(24):
        a.giant_actor.apply_clip('Idle_Loop', dur * k / 24, force=True)
        a._update_actor_shadows()
        held += a.giant_shadow_contains(a.human.getPos(a.render))
    check('Indigo\'s shade covers you in every pose of its idle breathing (was a coin-flip at the edge)',
          held == 24, f'{held}/24 poses, Indigo stands within {desert.SHADE_STAND_PRECISION} m of its spot')

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
