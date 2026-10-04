"""Pass 53 check: giant stamina, knock-outs only when exhausted, waking Indigo with E, the red
one's day of calm after a knock-out, and feeding it poison.

    python tools_pass53_check.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from panda3d.core import Point3

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='indigo_save53_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

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


def fresh(a):
    """Both giants up, rested; the red one aggressive and awake; the human by Indigo."""
    b = a.human_base_pos
    a.human.setPos(ground(a, b.x, b.y))
    a.giant.setPos(ground(a, b.x + 6, b.y))
    a.red_giant.setPos(ground(a, b.x + 11, b.y))
    a.human_alive, a.human_health = True, 100.0
    a.giant_alive, a.giant_health, a.giant_stamina = True, 100.0, fight.STAMINA_MAX['giant']
    a.giant_knocked_out, a.giant_getup = False, -1.0
    a.red_alive, a.red_health, a.red_stamina = True, 100.0, fight.STAMINA_MAX['red']
    a.red_knocked_out = a.red_recovering = a.red_fleeing = a.red_lurking = False
    a.red_calm_until = None
    a.red_weakness = 0
    a.red_state = 'pursue'
    a.red_hunger, a.red_anger = 0.9, 3                      # aggressive: fights to the end
    a.red_resting, a.red_meal = False, None
    a.whistle_alert = 5.0
    for s in a.attack_states.values():
        s.update({'active': False, 'elapsed': 0.0, 'hit_done': False, 'cooldown': 0.0})
    a._since_blow = {'giant': 99.0, 'red': 99.0}


def step(a, n=1):
    for _ in range(n):
        a._update_indigo_defender(DT, 0.0)
        a._update_red_giant(DT, 0.0)
        a.survival_step(DT)


def main():
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, new_game=True, persist=True, save_dir=TMP)
    a.time_frozen = True
    a.heat_factor_override = 0.0
    a.hour = 12.0

    # ------------------------------------------------------------ a straight fight
    fresh(a)
    t = 0.0
    hits0 = dict(a.combat_hits)
    while t < 120.0 and not (a.giant_knocked_out or a.red_knocked_out):
        step(a)
        t += DT
    hits = {k: a.combat_hits[k] - hits0.get(k, 0) for k in a.combat_hits}
    who = 'Indigo' if a.giant_knocked_out else 'the red one' if a.red_knocked_out else 'nobody'
    check('a straight fight between the giants lasts about half a minute (was ~5 s: four hits)',
          18.0 <= t <= 90.0 and (a.giant_knocked_out or a.red_knocked_out),
          f'{t:.0f} s, {who} went down, blows landed {hits}')

    # ------------------------------------------------------------ only an exhausted giant is knocked down
    fresh(a)
    a.giant_stamina, a.giant_health = 30.0, 6.0
    r1 = a.resolve_hit('red', 'giant')
    a.giant_stamina = 0.0
    a.giant_health = 90.0
    r2 = a.resolve_hit('red', 'giant')
    check('a hit on a giant with breath left only hurts it; a hit on an exhausted one knocks it out',
          r1 == 'hurt' and r2 == 'ko', f'{r1}, {r2}')
    fresh(a)
    a.giant_stamina = fight.PUNCH_COST - 1
    no_punch = not a._start_melee('giant')
    check('an out-of-breath giant cannot throw a punch until it recovers', no_punch)

    fresh(a)
    a.giant_stamina = 20.0
    a._since_blow['giant'] = 0.0
    a.survival_step(1.0)
    fighting_regen = a.giant_stamina - 20.0
    a.giant_stamina = 20.0
    a._since_blow['giant'] = 10.0
    a.survival_step(1.0)
    calm_regen = a.giant_stamina - 20.0
    check('stamina comes back slowly between blows, quickly once the fight stops',
          0 < fighting_regen < calm_regen, f'{fighting_regen:.1f}/s vs {calm_regen:.1f}/s')

    # ------------------------------------------------------------ Indigo knocked out: wake it with E
    fresh(a)
    a.red_giant.setPos(ground(a, a.human_base_pos.x + 900, a.human_base_pos.y))
    a.giant_stamina = 0.0
    a.resolve_hit('red', 'giant')
    a.knock_out_indigo()
    step(a, 30)
    down = a.giant_knocked_out and not a.giant_alive and 'knocked out' in a._companion_word()
    a.human.setPos(ground(a, a.giant.getX() + 5, a.giant.getY()))
    kind, _t = a._e_target()
    a._on_e_press()
    a.keys['e'] = False
    step(a, 10)
    a._on_e_press()
    a.keys['e'] = False
    step(a, 10)
    still = a.giant_knocked_out and a.giant_getup < 0.0
    a._on_e_press()
    a.keys['e'] = False
    getting_up = a.giant_getup >= 0.0
    step(a, int((fight.GETUP_TIME + 0.3) / DT))
    check('Indigo knocked out stays down; three taps of E beside it wake it, and it gets up',
          down and kind == 'wake' and still and getting_up and a.giant_alive and not a.giant_knocked_out
          and a.giant_health >= fight.WAKE_HEALTH and a.giant_stamina >= fight.STAMINA_MAX['giant'] * 0.39,
          f'e={kind}, health {a.giant_health:.0f}, stamina {a.giant_stamina:.0f}')
    # taps too far apart start over
    a.knock_out_indigo_quiet()
    a._on_e_press()
    a.keys['e'] = False
    step(a, int(4.0 / DT))
    a._on_e_press()
    a.keys['e'] = False
    check('taps too far apart start the shaking over', a._wake_taps == 1)
    # left alone, it wakes with the next dawn
    a.day += 1
    a.hour = 6.1
    step(a, int((fight.GETUP_TIME + 0.5) / DT))
    a.hour = 12.0
    check('left alone, Indigo gets up by itself at dawn', a.giant_alive and not a.giant_knocked_out)
    # knocked out while you control it: you are yourself again
    fresh(a)
    a._toggle_control()
    ctrl = a.controlled_name
    a.knock_out_indigo()
    check('knocked out while you are Indigo: control comes back to you', ctrl == 'giant' and a.controlled_name == 'human')
    a.giant_knocked_out, a.giant_alive = False, True

    # ------------------------------------------------------------ the red one down: poison, then a day's calm
    fresh(a)
    a.red_stamina = 0.0
    assert a.resolve_hit('giant', 'red') == 'ko'
    a._knock_out_red()
    base_pace, base_sight = a.red_pace(), a.red_detection_range()
    a.human.setPos(ground(a, a.red_giant.getX() + 6, a.red_giant.getY()))
    a.bag('human')['bane'] = 4
    kind, _t = a._e_target()
    remaining0 = a.red_knockout_remaining
    a._on_e_press()
    a.keys['e'] = False
    one = (a.red_weakness == 1 and a.bag('human')['bane'] == 3
           and abs(a.red_knockout_remaining - remaining0 - fight.POISON_KO_EXTRA) < 1.0)
    for _ in range(4):
        a._on_e_press()
        a.keys['e'] = False
    check('with pale scraps on you, tap E beside the knocked-out red one to feed it poison (up to 3 doses)',
          kind == 'feed' and one and a.red_weakness == 3 and a.bag('human')['bane'] == 1,
          f'weakness {a.red_weakness}, scraps left {a.bag("human")["bane"]}')
    stomp = game.RED_STOMP_DAMAGE * a.blow_scale('red')
    check('poison weakens it: less stamina, softer blows, slower, and it sees you from less far',
          abs(a.stamina_max('red') - 40.0) < 0.1 and abs(stomp - game.RED_STOMP_DAMAGE * 0.55) < 0.5
          and a.red_pace() < base_pace * 0.8 and a.red_detection_range() < base_sight * 0.75,
          f'stamina max {a.stamina_max("red"):.0f}, stomp {stomp:.1f}, pace x{a.red_pace() / base_pace:.2f}, '
          f'sight x{a.red_detection_range() / base_sight:.2f}')
    a.human_health = 100.0
    a.red_weakness = 0

    # it gets up dazed and leaves you alone for a day
    a.red_knockout_remaining = 0.01
    step(a, int((game.RED_RECOVERY_STAND_TIME + 0.5) / DT))
    calm = a.red_is_calm()
    a.human.setPos(ground(a, a.red_giant.getX() + 30, a.red_giant.getY()))
    a._record_trail() if hasattr(a, '_record_trail') else None
    states = set()
    for _ in range(int(30.0 / DT)):
        step(a)
        states.add(a.red_state)
    hunted = states & {'pursue', 'stomp', 'melee', 'track', 'watching'}
    check('it gets up dazed and has lost you for a day: no hunting, no tracking, even 30 m away',
          calm and not hunted and a.human_health == 100.0 and 'dazed' in a._red_word(), f'states {sorted(states)}')
    a.day += 1
    a.hour += 0.5
    step(a, 2)
    check('after a day it picks up your trail again', not a.red_is_calm() and a.red_calm_until is None
          and a.red_state != 'dazed', a.red_state)
    # hit it while dazed: the calm is over
    a.begin_red_calm()
    a.resolve_hit('giant', 'red')
    check('hit it while it is dazed and the calm is over', not a.red_is_calm())

    # a sneaky red one runs when nearly spent; an aggressive one fights on
    fresh(a)
    a.red_hunger, a.red_anger, a.red_woken_t = 0.1, 0, 0.0
    a.red_stamina = fight.STAMINA_MAX['red'] * 0.1
    a.red_scare_check()
    sneaky_ran = a.red_fleeing
    fresh(a)
    a.red_stamina = fight.STAMINA_MAX['red'] * 0.1
    a.red_scare_check()
    check('a sneaky red one runs off when nearly spent; an aggressive one fights until it drops',
          sneaky_ran and not a.red_fleeing)

    # ------------------------------------------------------------ saves
    fresh(a)
    a.knock_out_indigo_quiet()
    a.begin_red_calm()
    a.red_weakness = 2
    a.giant_stamina, a.red_stamina = 33.0, 21.0
    snap = a.fight_snapshot()
    fresh(a)
    a.apply_fight(snap)
    check('saved: Indigo down, the red one\'s calm, its poisoning and both staminas',
          a.giant_knocked_out and not a.giant_alive and a.red_is_calm() and a.red_weakness == 2
          and a.giant_stamina == 33.0 and a.red_stamina == 21.0, str(snap))

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
