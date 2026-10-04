"""Pass 60 check: the red one's crimson powers (night only).

    python tools_pass60_check.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from panda3d.core import Point3

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='indigo_save60_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import crimson        # noqa: E402
import fight          # noqa: E402
import main as game   # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
DT = 1 / 30.0


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def shader_vec(np_, name):
    inp = np_.getShaderInput(name)
    v = inp.getVector()
    return tuple(float(v[i]) for i in range(4))


def main():
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, new_game=True, persist=True, save_dir=TMP,
                                       show_title=False)
    a.time_frozen = True
    a.comp.update({'mode': 'stay', 'moving': False})
    b = a.human_base_pos
    rp = ground(a, b.x + 60, b.y + 40)

    def setup(hour, human_d=20.0, resting=True, indigo_far=True):
        a.hour = hour
        a._apply_time(force=True)
        a.red_giant.setPos(rp)
        a.red_alive, a.red_knocked_out, a.red_recovering, a.red_dead = True, False, False, False
        a.red_resting, a.red_energy = resting, (0.1 if resting else 1.0)
        a.red_state = 'rest' if resting else 'idle'
        a.red_provoked_t = a.red_woken_t = 0.0
        a.crimson_phase, a.crimson_t, a.crimson_cool = 'idle', 0.0, 0.0
        a.human_alive, a.human_health, a.human_dazed = True, 100.0, 0.0
        a.carried = False
        if a.hidden_shell is not None:
            a.exit_shell()
        a.human.setPos(ground(a, rp.x - human_d, rp.y))
        a.glow_charge = 0.0
        if indigo_far:
            a.giant.setPos(ground(a, rp.x - 200, rp.y - 150))
        a.giant_stamina, a.giant_health = fight.STAMINA_MAX['giant'], 100.0

    def run(seconds, hold=False):
        t = 0.0
        while t < seconds:
            a._update_red_giant(DT, t)
            a.survival_step(DT)
            t += DT

    # 1. by day: no crimson
    setup(12.0, human_d=15.0, resting=False)
    run(2.5)
    check('by day the red one has no crimson power (no glow, no wave, no ward)',
          a._crimson_level == 0.0 and a.crimson_phase == 'idle' and a.human_health == 100.0
          and not a.crimson_ward_active() and shader_vec(a.red_giant, 'glow_self')[0] == 0.0)

    # 2. at night it burns crimson; resting, it is warded
    setup(23.0, human_d=60.0)
    run(0.5)
    tint = shader_vec(a.red_giant, 'glow_tint')
    light = shader_vec(a.render, 'glow3_color')
    check('at night it burns crimson: its body, a halo, a crimson light round it',
          a._crimson_level > 0.95 and shader_vec(a.red_giant, 'glow_self')[0] > 0.5 and tint[0] > 0.9 > tint[2] * 5
          and light[0] > light[2] * 5 and not a.red_aura.isHidden() and a.crimson_ward_active(),
          f'glow {shader_vec(a.red_giant, "glow_self")[0]:.2f}, light {light[0]:.2f} {light[1]:.2f} {light[2]:.2f}')

    # 3. come close: the wave swells (the ring shows its reach) - stay, and it hits
    setup(23.0, human_d=20.0)
    run(0.2)
    charging = a.crimson_phase == 'charge' and not a.crimson_ring.isHidden() and 'get away' in a._red_word()
    p0 = a.human.getPos()
    run(crimson.CHARGE_TIME + crimson.WAVE_TIME + 0.2)
    thrown = (a.human.getPos() - p0).length()
    check('within 24 m at night a crimson wave swells (a ring shows its reach); stay, and it throws you, hurt, dazed',
          charging and abs(a.human_health - (100.0 - crimson.HUMAN_DAMAGE)) < 0.5 and thrown > 3.5
          and a.stats.get('crimson_hits', 0) == 1,
          f'life {a.human_health:.0f}, thrown {thrown:.1f} m')

    # 4. get out of the ring while it swells: safe
    setup(23.0, human_d=20.0)
    run(0.3)
    a.human.setPos(ground(a, rp.x - 33.0, rp.y))       # jogged out (5.6 m/s x 1.5 s)
    run(crimson.CHARGE_TIME + crimson.WAVE_TIME + 0.2)
    check('get out of the ring before it bursts and it passes you by', a.human_health == 100.0)

    # 5. an unbroken shell, or riding on Indigo: the wave passes you by
    setup(23.0, human_d=20.0)
    s = min((sh for sh in a.shells.shells.values() if sh.state == 'intact'),
            key=lambda sh: (sh.pos - a.human.getPos()).length())
    a.red_giant.setPos(ground(a, s.pos.x + 20, s.pos.y))
    a.human.setPos(a.shells.inner_spot(s))
    a._update_shell_presence()
    in_shell = a.hidden_shell is s
    run(crimson.CHARGE_TIME + crimson.WAVE_TIME + 0.3)
    shell_hp = a.human_health
    a.exit_shell()
    setup(23.0, human_d=20.0)
    a.carried = True
    run(crimson.CHARGE_TIME + crimson.WAVE_TIME + 0.3)
    ride_hp = a.human_health
    a.carried = False
    check('inside an unbroken shell, or riding on Indigo, the wave passes you by',
          in_shell and shell_hp == 100.0 and ride_hp == 100.0, f'shell {shell_hp}, riding {ride_hp}')

    # 6. Indigo caught in it: winded and staggered (its own glow softens it)
    setup(23.0, human_d=60.0, indigo_far=False)
    a.giant.setPos(ground(a, rp.x + 15, rp.y))
    run(crimson.CHARGE_TIME + crimson.WAVE_TIME + 0.2)
    lost = fight.STAMINA_MAX['giant'] - a.giant_stamina
    check("Indigo caught in it is winded and staggered (its night glow softens the blow)",
          crimson.INDIGO_STAMINA * 0.5 < lost <= crimson.INDIGO_STAMINA and a.attack_states['giant']['cooldown'] > 0.5,
          f'stamina -{lost:.1f}')

    # 7. it needs time to swell again
    setup(23.0, human_d=20.0)
    run(crimson.CHARGE_TIME + crimson.WAVE_TIME + 0.4)
    after_first = a.crimson_cool
    a.human_health = 100.0
    run(3.0)
    check('it needs 6 s before the next wave', after_first > 5.0 and a.crimson_phase == 'idle' and a.human_health > 99.0,
          f'cool {after_first:.1f} s')

    # 8. the ward: resting at night, Indigo's blows glance off (and set off a wave)
    setup(23.0, human_d=60.0, indigo_far=False)
    a.crimson_cool = 99.0                      # no wave from Indigo standing there
    a.giant.setPos(ground(a, rp.x + 4.5, rp.y))
    st0 = a.red_stamina = fight.STAMINA_MAX['red']
    a.attack_states['giant'].update({'active': False, 'cooldown': 0.0})
    landed = a._apply_melee_hit('giant', 1.0)
    check("resting at night, it is warded: Indigo's blow glances off (and sets off a wave)",
          not landed and a.red_stamina == st0 and a.crimson_phase == 'charge' and a.red_resting)

    # 9. knocked out at night: no poison; by day, yes
    setup(23.0, human_d=60.0, resting=False)
    a.red_stamina = 0.0
    a._knock_out_red()
    a.bag('human')['bane'] = 1
    a.human.setPos(ground(a, a.red_giant.getX() + 5, a.red_giant.getY()))
    a.crimson_cool = 99.0
    night_feed = a.can_feed_red()
    a.hour = 12.0
    a._apply_time(force=True)
    day_feed = a.can_feed_red()
    check('knocked out at night the crimson light keeps you from feeding it poison; by day you can',
          not night_feed and day_feed)
    a.red_knocked_out = False

    # 10. awake at night, it stands and calls the wave
    setup(23.0, human_d=20.0, resting=False)
    a.red_state = 'pursue'
    run(0.6)
    check('awake, it stops and raises its arms to call the wave',
          a.red_state == 'crimson' and a.red_giant_actor.current_clip == 'Spell_Simple_Idle_Loop'
          and a.red_motion_speed < 0.5)

    # 11. the dead red one has no power
    setup(23.0, human_d=20.0)
    a.red_dead = True
    run(1.0)
    check('once it is dead, no crimson', a.crimson_phase == 'idle' and a._crimson_level == 0.0)
    a.red_dead = False

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
