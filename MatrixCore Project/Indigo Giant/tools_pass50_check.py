"""Pass 50 check: first launch - display settings (4K / 1080p / fullscreen), the title
screen, the settings menu, key rebinding in game, mouse settings, and the first-dawn hints.

    python tools_pass50_check.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from panda3d.core import Point3

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='indigo_save50_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import controls       # noqa: E402
import frontend       # noqa: E402
import main as game   # noqa: E402
import settings as S  # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
CLOCK = [0.0]


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def tick(a, seconds, dt=1 / 30.0):
    for _ in range(int(seconds / dt)):
        CLOCK[0] += dt
        a.survival_step(dt)


def panel_words(a):
    words = [n.node().getText() for n in a.panel.findAllMatches('**/+TextNode')]
    for n in a.panel.findAllMatches('**/+PGButton'):
        if n.hasPythonTag('label'):
            words.append(n.getPythonTag('label'))
    return words


def visible_hud(a):
    return [np_ for np_ in a.aspect2d.getChildren() if not np_.isHidden() and np_ != a.panel]


def main():
    # ------------------------------------------------------------ display settings
    d = dict(S.DEFAULTS)
    four_k = S.prc_lines(d, native=(3840, 2160))
    hd = S.prc_lines(dict(d, resolution='1920x1080'), native=(3840, 2160))
    too_big = S.window_size(dict(d, resolution='3840x2160', fullscreen=False), native=(1920, 1080))
    check('default: fullscreen at the monitor\'s own resolution (4K on a 4K screen)',
          'win-size 3840 2160' in four_k and 'fullscreen #t' in four_k, four_k[0])
    check('1080p is one choice away; a 4K window on a 1080p screen shrinks to fit',
          'win-size 1920 1080' in hd and too_big[0] <= 1920 * 0.92 and too_big[1] <= 1080 * 0.88, str(too_big))
    check('anti-aliasing and vsync go into the window settings', 'multisamples 4' in four_k and 'sync-video true' in four_k)
    (TMP / 'settings.json').write_text(json.dumps({'resolution': 'bogus', 'master': 7, 'msaa': 3, 'invert_y': 'yes'}))
    s = S.load(TMP)
    check('a damaged settings file is made safe', s['resolution'] == 'native' and s['master'] == 1.0 and s['msaa'] == 4
          and s['invert_y'] is False)
    (TMP / 'settings.json').unlink()

    # ------------------------------------------------------------ the title
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, persist=True, save_dir=TMP, show_title=True)
    check('launching shows the title, the world paused and the HUD hidden',
          a.panel_name == 'title' and a.paused and not visible_hud(a), f'{len(visible_hud(a))} HUD nodes showing')
    check('nothing can be done in the world behind the title', not a.gesture_command('come'))
    a._on_menu_key()
    check('Esc does not dismiss the title', a.panel_name == 'title')
    texts = panel_words(a)
    check('a new journey offers "begin"', any(t == 'begin' for t in texts) and not any('continue' in t for t in texts))

    # settings from the title, and back
    a.toggle_panel('settings')
    a.change_setting('music', -1)
    a.change_setting('mouse_sensitivity', 1)
    a.change_setting('resolution', 1)
    saved = S.load(TMP)
    check('settings open over the title and save as you change them',
          a.panel_name == 'settings' and abs(saved['music'] - 0.6) < 1e-6 and saved['mouse_sensitivity'] == 1.25
          and saved['resolution'] == '3840x2160' and abs(a.audio.settings['music'] - 0.6) < 1e-6)
    a.close_panel()
    check('back returns to the title', a.panel_name == 'title' and a.paused)
    a.leave_title()
    check('begin: the title goes, the HUD returns, the world moves', a.panel_name is None and not a.paused
          and visible_hud(a))

    # ------------------------------------------------------------ keys in game
    fired = []
    a.bind_action('jump', lambda: fired.append('jump'))
    a.toggle_panel('menu')
    a.toggle_panel('settings')
    a.toggle_panel('keys')
    a.start_key_capture('jump')
    a._on_menu_key()
    still = a.panel_name == 'keys'
    a._captured_key('mouse1')                        # mouse buttons are not keys
    waiting = a._capturing_key == 'jump'
    a._captured_key('v')
    a.taskMgr.step()                                  # Pass 54: the press that chose the key is swallowed
    a.messenger.send('v')
    a.messenger.send('space')
    check('rebind in game: click an action, press a key - it works at once, the old key is free',
          still and waiting and a.bindings['jump'] == 'v' and fired == ['jump'], str(fired))
    a.assign_key('jump', 'e')                        # E is "use": they swap
    check('a key already in use swaps places', a.bindings['jump'] == 'e' and a.bindings['use'] == 'v')
    saved_keys = json.loads((TMP / 'controls.json').read_text())
    check('your keys are saved in the save folder', saved_keys['jump'] == 'e' and saved_keys['use'] == 'v')
    a.reset_keys()
    check('"defaults" puts every key back', all(a.bindings[k] == v for k, v in controls.DEFAULT_BINDINGS.items()))
    a.assign_key('jump', 'v')
    a._panel_stack.clear()
    a.close_panel()

    # ------------------------------------------------------------ mouse settings
    a.settings['mouse_sensitivity'] = 2.0
    a.settings['invert_y'] = True
    pts = iter([(100, 100), (110, 104)])
    a._pointer_xy = lambda: next(pts)
    a._begin_orbit()
    a.heading, a.pitch = 0.0, -20.0
    p0 = a.pitch
    a._update_mouse_orbit()
    check('mouse sensitivity and invert-Y are used', abs(a.heading - 10 * game.MOUSE_ORBIT_SENSITIVITY * 2.0) < 1e-6
          and a.pitch > p0, f'heading {a.heading:.2f}, pitch {a.pitch:.2f}')
    a._end_orbit()

    # ------------------------------------------------------------ new journey relaunches
    launched = []
    frontend.subprocess.Popen = lambda args, cwd=None: launched.append(args)
    a.finalizeExit = lambda: launched.append('exit')
    a.restart_new_journey()
    check('"new journey" starts a fresh launch with --new', launched and '--new' in launched[0] and launched[-1] == 'exit')
    a.persist = True
    a.save_game('check')
    a.destroy()

    # ------------------------------------------------------------ a saved journey: continue, keys kept
    b = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, persist=True, save_dir=TMP, show_title=True)
    texts = panel_words(b)
    check('with a journey saved the title offers "continue" and "new journey"',
          any(t.startswith('continue') for t in texts) and any(t == 'new journey' for t in texts))
    check('keys chosen in game are there next launch', b.bindings['jump'] == 'v')
    b.persist = False
    b.destroy()

    # ------------------------------------------------------------ the first dawn
    game.StreamingTerrainWithGiant.teach_headless = True
    c = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, new_game=True, persist=False)
    c.time_frozen = True
    c.heat_factor_override = 0.0
    seen = []

    def step_text():
        tick(c, 0.6)
        seen.append(c.hud_teach.getText())
        return seen[-1]

    t0 = step_text()
    hp = c.human.getPos()
    c.human.setPos(hp + Point3(9, 0, 0))
    step_text()
    c.gesture_command('come')
    t_dig = step_text()
    gaze = c.notice is not None
    c.stats['finds_dug'] += 1
    step_text()
    c.comp['mode'] = 'shade'
    step_text()
    c.carried = True
    step_text()
    c.carried = False
    c.comp['mode'] = 'stay'
    c.hidden_shell = object()
    step_text()
    c.hidden_shell = None
    tick(c, 13.0)
    check('first dawn: one hint at a time, each gone once done (walk, come, dig, shade, lift, shell, keys)',
          'walk' in t0 and 'buried' in t_dig and len(set(seen)) >= 6 and c.teach_step == len(c.teach_steps()),
          f'step {c.teach_step}/{len(c.teach_steps())}')
    check('Indigo looks toward the buried find when that hint comes up', gaze)
    c.settings['hints'] = False
    c.teach_step = 0
    tick(c, 1.0)
    check('hints can be turned off in settings', c._teach_alpha < 0.1)

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
