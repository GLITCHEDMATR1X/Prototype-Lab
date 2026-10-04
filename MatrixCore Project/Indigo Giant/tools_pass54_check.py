"""Pass 54 check: the fixes from the full code review.

    python tools_pass54_check.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from panda3d.core import Point3

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='indigo_save54_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import fight          # noqa: E402
import main as game   # noqa: E402
import settings as S  # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
DT = 1 / 30.0


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def main():
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, new_game=True, persist=True, save_dir=TMP,
                                       show_title=False)
    a.time_frozen = True
    a.heat_factor_override = 0.0
    a.hour = 12.0
    b = a.human_base_pos

    # 1. choosing a key does not also do the key's old job
    a.toggle_panel('menu')
    a.toggle_panel('settings')
    a.toggle_panel('keys')
    a.start_key_capture('jog')
    a.messenger.send('j')                    # would open the journal
    during = a.panel_name == 'keys'
    a._captured_key('j')
    a.messenger.send('j')                    # the same frame the key was chosen
    same_frame = a.panel_name == 'keys'
    a.start_key_capture('crouch')
    a._captured_key('lshift')
    check('choosing a new key does not also press it (J did not open the journal); left Shift counts as Shift',
          during and same_frame and a.bindings['jog'] == 'j' and a.bindings['crouch'] == 'shift',
          f'panel {a.panel_name}, jog={a.bindings["jog"]}, crouch={a.bindings["crouch"]}')
    a.reset_keys()
    a._panel_stack.clear()
    a.close_panel()

    # 2. an Indigo left at 0 life by an older save is knocked out (and can be woken), not lost
    a.giant_health, a.giant_alive = 0.0, False
    a.giant_knocked_out = False
    a.apply_fight({})
    check('an older save with Indigo at 0 life loads it knocked out - and wakeable',
          a.giant_knocked_out and not a.giant_alive)
    a.giant_knocked_out, a.giant_alive, a.giant_health = False, True, 100.0

    # 3. knocked out while you control it, mid-lift: you are yourself again, the shell drops
    a.giant.setPos(ground(a, b.x + 6, b.y))
    shell = min(a.shells.shells.values(), key=lambda s: (s.pos - a.giant.getPos()).length())
    a.giant.setPos(ground(a, shell.pos.x + 5, shell.pos.y))
    a._toggle_control()
    lifting = a.giant_shell_action()
    a.pending_smash = object()
    a.knock_out_indigo()
    check('knocked out while you are Indigo and lifting a shell: control comes back, the shell drops, '
          'no smash left pending',
          lifting and a.controlled_name == 'human' and a.giant_action is None and a.giant_held_shell is None
          and not shell.held and a.pending_smash is None, f'lifting={lifting}, control={a.controlled_name}')

    # 4. it wakes at the NEXT dawn, not at once when knocked out just after dawn
    a.hour = 6.2
    a.knock_out_indigo_quiet()
    for _ in range(5):
        a._update_giant_ko(DT)
    early = a.giant_getup >= 0.0
    a.day += 1
    a.hour = 6.05
    a._update_giant_ko(DT)
    check('knocked out at 06:12, Indigo waits for the next dawn to get up', not early and a.giant_getup >= 0.0)
    a.giant_knocked_out, a.giant_alive, a.giant_getup = False, True, -1.0
    a.hour = 12.0

    # 5. a dazed red one does not stop you sleeping
    a.red_giant.setPos(ground(a, b.x + 60, b.y))
    a.begin_red_calm()
    a.red_state = 'dazed'
    check('the dazed red one does not keep you awake', not a.red_blocks_sleep())
    a.red_calm_until = None

    # 6. saved while it was getting up: it gets its day of calm after loading
    a.red_recovering, a.red_fleeing = True, False
    snap = a.fight_snapshot()
    a.red_recovering = False
    a.red_fleeing = True                       # what the save's old 'fleeing' flag restores
    a.apply_fight(snap)
    check('saved while the red one was getting up: after loading it is dazed for its day',
          a.red_is_calm() and not a.red_fleeing, a.red_state)
    a.red_calm_until = None

    # 7. feeding poison uses Indigo's bag too when it is beside you
    a.red_giant.setPos(ground(a, b.x + 40, b.y))
    a.red_stamina = 0.0
    a._knock_out_red()
    a.human.setPos(ground(a, a.red_giant.getX() + 5, a.red_giant.getY()))
    a.giant.setPos(ground(a, a.red_giant.getX() + 12, a.red_giant.getY()))
    a.bag('human')['bane'] = 0
    a.bag('giant')['bane'] = 2
    kind, _t = a._e_target()
    a._on_e_press()
    a.keys['e'] = False
    check('you can feed it a pale scrap you gave to Indigo (Indigo beside you)',
          kind == 'feed' and a.red_weakness == 1 and a.bag('giant')['bane'] == 1)

    # 8. the HUD hides a lurking red one even when it is weakened
    a.red_knocked_out = False
    a.red_begin_lurk()
    for _ in range(12):
        a._update_hud(0.5)
    check('a weakened red one that is lurking stays off the HUD',
          'weakened' in a._red_word() and a.hud_red.fg[3] < 0.05, f'{a._red_word()!r} alpha {a.hud_red.fg[3]:.2f}')
    a.red_lurking = False
    a.red_weakness = 0

    # 9. save gaps: places Indigo sensed, tower sightings, the red one's fall, retry
    pf = a.places
    a._refresh_world(force=True)
    some = next(iter(pf.places.values()), None)
    if some is None:
        pf.update(Point3(b.x + 2000, b.y, 0))
        some = next(iter(pf.places.values()))
    some.sensed, some.found = True, False
    a.tower_sightings['(1, 2)'] = (10.0, 20.0)
    snap = a.places_snapshot()
    some.sensed = False
    a.tower_sightings.clear()
    a.apply_places(snap)
    check('places Indigo already sensed and tower sightings are saved',
          some.sensed and a.tower_sightings.get('(1, 2)') == (10.0, 20.0))
    a.red_stamina, a.red_calm_until = 3.0, a.game_hours() + 10
    a.human_alive = False
    a._retry_after_human_down()
    check('a retry gives the red one back its stamina and ends any calm',
          a.red_stamina == a.stamina_max('red') and a.red_calm_until is None)

    # 10. the desktop size is asked once
    S._NATIVE.clear()
    S.native_size()
    first = list(S._NATIVE)
    S.native_size()
    check('the desktop resolution is looked up once, not on every settings redraw', len(S._NATIVE) == 1 and first == S._NATIVE)

    # 11. Pass 53 numbers unchanged
    check('fight tuning unchanged', fight.PUNCH_COST == 2.0 and fight.HIT_STAMINA == 4.5)

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
