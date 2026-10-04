"""Pass 63 check: The Indigo Giant as a HoloVerse dimension.

    python .dev/checks/pass63.py

Checks the responder files HoloVerse reads, the native adapter, and a full hosted visit inside
a stand-in host (a plain offscreen ShowBase): the game borrows the host's window, lives under
its own node, moves TAB's action to V, answers with a result, and on leaving removes every task,
node, key binding and piece of UI it made. The real HoloVerse round trip is tested separately
(see PASS63 in docs/pass_notes).
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]          # the game folder
TMP = Path(tempfile.mkdtemp(prefix='indigo_save63_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]
sys.path.insert(0, str(HERE))

from panda3d.core import loadPrcFileData           # noqa: E402

loadPrcFileData('pass63', 'window-type offscreen\naudio-library-name null\nwin-size 1280 720')
from direct.showbase.ShowBase import ShowBase       # noqa: E402

from indigo_giant import holoverse_host              # noqa: E402

FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def step(base, n):
    for _ in range(n):
        base.taskMgr.step()


# ------------------------------------------------------------------ 1. the files HoloVerse reads
resp = json.loads((HERE / 'holoverse/holoverse_dimension.json').read_text(encoding='utf-8'))
ident = json.loads((HERE / 'holoverse/identity.json').read_text(encoding='utf-8'))
dim = json.loads((HERE / 'dimension.json').read_text(encoding='utf-8'))
check('responder protocol is holoverse_responder_v1', resp.get('protocol') == 'holoverse_responder_v1')
check('responder host contract is holoverse_dimension_v1', resp.get('host_contract') == 'holoverse_dimension_v1')
check('responder is native', resp.get('compatibility') == 'native')
check('responder adapter file exists', (HERE / str(resp.get('native_adapter', ''))).is_file(), resp.get('native_adapter'))
check('responder entry is main.py', resp.get('entry') == 'main.py' and (HERE / 'main.py').is_file())
check('responder preview exists', (HERE / str(resp.get('preview', ''))).is_file(), resp.get('preview'))
contract = resp.get('input_contract') or {}
check('TAB belongs to the host', 'tab' in contract.get('host_owned', []) and 'tab' not in contract.get('dimension_owned', []),
      contract)
check('identity has a fixed id', len(str(ident.get('dimension_id', ''))) == 36)
check('dimension.json agrees on the title', dim.get('title') == resp.get('title') == 'The Indigo Giant')

# ------------------------------------------------------------------ 2. the adapter
spec = importlib.util.spec_from_file_location('holoverse_native_ig_check', HERE / 'holoverse_native_adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
check('adapter has create_mode', callable(getattr(adapter, 'create_mode', None)))
for alias in ('create_native_mode', 'create_native_adapter', 'create_adapter'):
    check(f'adapter alias {alias}', getattr(adapter, alias, None) is adapter.create_mode)
check('mangled ShowBase names are borrowed', '_ShowBase__configAspectRatio' in holoverse_host.SHOWBASE_NAMES)
check('an unrelated name is not borrowed', 'dimension_registry' not in holoverse_host.SHOWBASE_NAMES)


# ------------------------------------------------------------------ 3. a hosted visit in a stand-in host
class StandInHost(ShowBase):
    """The parts of HoloVerse a native mode relies on: TAB home, and nothing else."""

    def __init__(self):
        super().__init__()
        self.disableMouse()
        self.returned = 0
        self.mode = None
        self.accept('tab', self.handle_tab_action)
        self.setBackgroundColor(0.02, 0.03, 0.05, 1)

    def handle_tab_action(self):
        self.returned += 1
        if self.mode is not None:
            self.mode.exit()
            self.mode = None


host = StandInHost()
step(host, 3)


def census():
    return {
        'tasks': sorted(t.getName() for t in host.taskMgr.getAllTasks()),
        'render': sorted(c.getName() for c in host.render.getChildren()),
        'aspect2d': len(host.aspect2d.getChildren()),
        'render2d': len(host.render2d.getChildren()),
        'pixel2d': len(host.pixel2d.getChildren()),
        'events': sorted(host.messenger.getEvents()),
        'clear': tuple(round(v, 4) for v in host.win.getClearColor()),
        'lens_fov': tuple(round(v, 3) for v in host.camLens.getFov()),
    }


before = census()


def visit(label, leave):
    mode = adapter.create_mode(host, None, HERE / 'main.py', 'THE INDIGO GIANT')
    host.mode = mode
    mode.enter()
    step(host, 6)
    game = mode.game
    check(f'{label}: game is hosted', game is not None and game.hosted)
    check(f'{label}: borrows the host window', game.win is host.win and game.camera is host.camera)
    check(f'{label}: world is its own node under the host scene', game.render.getParent() == host.render
          and game.render is not host.render)
    check(f'{label}: be Nyx / be Orbit moved off TAB', game.bindings.get('switch_character') == 'v',
          game.bindings.get('switch_character'))
    check(f'{label}: TAB still reaches the host', host.messenger.isAccepting('tab', host))
    check(f'{label}: the game does not listen to TAB', not host.messenger.isAccepting('tab', game))
    check(f'{label}: saved keys keep TAB (V is only lent while hosted)',
          game.bindings_to_save().get('switch_character') == 'tab')
    check(f'{label}: quit reads "return to HoloVerse"', game.quit_words() == 'return to HoloVerse')
    res = mode.get_holoverse_result()
    check(f'{label}: result shape', res.get('mode_id') == 'indigo_giant' and res.get('fragments_required') == '14'
          and res.get('completed') is False, res)
    leave(mode, game)
    step(host, 4)
    return mode, game


def leave_tab(mode, game):
    host.messenger.send('tab')


def leave_menu(mode, game):
    game.leave_title()
    step(host, 3)
    game.userExit()                                  # Esc > save and return to HoloVerse


def leave_restart(mode, game):
    old = game
    game.restart_new_journey()
    step(host, 6)
    check('restart: a fresh hosted game replaced the old one', mode.game is not old and mode.game.hosted)
    check('restart: the old world is gone', old.__dict__['render'].isEmpty())
    check('restart: one world under the host', sum(1 for c in host.render.getChildren()
                                                   if c.getName() == 'indigo_giant_world') == 1)
    host.messenger.send('tab')


for label, leave in (('tab', leave_tab), ('menu', leave_menu), ('restart', leave_restart)):
    mode, game = visit(label, leave)
    after = census()
    check(f'{label}: host returned once', host.returned >= 1)
    host.returned = 0
    for key in before:
        ok = before[key] == after[key]
        detail = ''
        if not ok and isinstance(before[key], list):
            detail = f'added {sorted(set(after[key]) - set(before[key]))[:6]} removed {sorted(set(before[key]) - set(after[key]))[:6]}'
        elif not ok:
            detail = f'{before[key]} -> {after[key]}'
        check(f'{label}: host {key} unchanged after leaving', ok, detail)

# the completed archive answers HoloVerse with the signal Nyx and Orbit listen for
mode = adapter.create_mode(host, None, HERE / 'main.py', 'THE INDIGO GIANT')
host.mode = mode
mode.enter()
step(host, 3)
mode.game.gleebs_state = 'gone'
res = mode.get_holoverse_result()
check('finished archive: completed + signal', res.get('completed') is True
      and res.get('signal') == 'indigo_giant_archive_complete', res)
mode.game.gleebs_state = None
host.messenger.send('tab')
step(host, 3)
check('finished archive: host clean after leaving', census() == before)

# ------------------------------------------------------------------ 4. standalone is untouched
from indigo_giant import app as game_app             # noqa: E402

check('standalone quit words', game_app.StreamingTerrainWithGiant.quit_words.__get__(
    type('S', (), {'hosted': False})())() == 'quit')
saved_keys = json.loads((HERE / 'controls.json').read_text(encoding='utf-8'))
check('controls.json still has be Nyx / be Orbit on TAB', saved_keys.get('switch_character') == 'tab')

print()
print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
os._exit(1 if FAILS else 0)
