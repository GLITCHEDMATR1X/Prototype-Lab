"""Key bindings for The Indigo Giant (Pass 43).

Every keyboard action goes through this table, so keys can be rebound by editing
controls.json next to main.py (it is written with the defaults on first launch). Mouse
buttons are fixed: left click = go there (riding), middle = gesture wheel, right = look.

The actions are also the seam for co-op later: a second player gets their own binding
table (or a network peer sends action names) and the same handlers run for them.
Panda3D key names: letters, digits, 'space', 'enter', 'tab', 'escape', 'shift',
'control', 'alt', 'f1'..'f12', 'arrow_left' / 'arrow_right' / 'arrow_up' / 'arrow_down'.
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_BINDINGS = {
    # movement (held)
    'move_forward': 'w', 'move_left': 'a', 'move_back': 's', 'move_right': 'd',
    'jog': 'shift', 'sprint_with_jog': 'control', 'crouch': 'c',
    'camera_left': 'arrow_left', 'camera_right': 'arrow_right', 'camera_up': 'arrow_up', 'camera_down': 'arrow_down',
    'use': 'e',                       # tap: step into a shell (or just walk in);  hold: dig, study, patch, smash, plant
    # actions
    'jump': 'space', 'eat': 'g', 'give_to_giant': 't', 'take_from_giant': 'y',
    'switch_character': 'tab', 'punch': 'f', 'kneel': 'k', 'camera_reset': 'r',
    'sleep': 'z', 'poison': 'x',            # Pass 49: work a pale scrap into a blood branch
    # gestures
    'come': '1', 'stay': '2', 'lift': '3', 'go_there': '4', 'shade': '5', 'whistle': 'q',
    # menus
    'craft': 'b', 'journal': 'j', 'controls_help': 'f1', 'menu': 'escape', 'retry': 'enter',
    'music': 'm', 'fps': 'f3', 'quick_save': 'f5',
}

# held actions -> the internal flag names the movement / camera code reads (self.keys)
HELD_FLAGS = {
    'w': 'move_forward', 'a': 'move_left', 's': 'move_back', 'd': 'move_right',
    'shift': 'jog', 'control': 'sprint_with_jog', 'c': 'crouch',
    'left': 'camera_left', 'right': 'camera_right', 'up': 'camera_up', 'down': 'camera_down',
    'e': 'use',
}

LABELS = {'arrow_left': 'left', 'arrow_right': 'right', 'arrow_up': 'up', 'arrow_down': 'down',
          'space': 'space', 'escape': 'esc', 'control': 'ctrl', 'enter': 'enter', 'shift': 'shift', 'tab': 'tab'}


def load(folder: Path, user_folder: Path | None = None) -> dict:
    """Pass 50: keys changed in the game's settings live in the save folder (user_folder) and
    win over controls.json next to main.py (which stays editable by hand)."""
    path = Path(folder) / 'controls.json'
    if user_folder is not None and (Path(user_folder) / 'controls.json').is_file():
        path = Path(user_folder) / 'controls.json'
    bindings = dict(DEFAULT_BINDINGS)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError('expected {"action": "key", ...}')
            for action, key in data.items():
                if action in bindings and isinstance(key, str) and key.strip():
                    bindings[action] = key.strip().lower()
        except (OSError, ValueError) as exc:
            print(f'[controls] ignoring controls.json: {exc}')
        _resolve_clashes(bindings)
    elif path.parent == Path(folder):
        try:
            doc = {'_readme': 'Rebind keys here (Panda3D key names). Delete this file to restore defaults.'}
            doc.update(DEFAULT_BINDINGS)
            path.write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
        except OSError:
            pass            # read-only install folder: defaults still work
    return bindings


def save(bindings: dict, user_folder: Path) -> bool:
    """Write the in-game key choices to the save folder."""
    try:
        folder = Path(user_folder)
        folder.mkdir(parents=True, exist_ok=True)
        doc = {'_readme': 'Keys chosen in the game (Esc > settings > keys). Delete this file to restore defaults.'}
        doc.update({k: bindings[k] for k in DEFAULT_BINDINGS})
        (folder / 'controls.json').write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
        return True
    except OSError as exc:
        print(f'[controls] could not save: {exc}')
        return False


def _resolve_clashes(bindings: dict) -> list:
    """Pass 44 (B13): one key cannot do two things.  A rebound action that lands on a key
    already in use goes back to its default (repeat until nothing clashes)."""
    reverted = []
    for _ in range(len(bindings)):
        owner = {}
        clash = None
        for action, key in bindings.items():
            if key in owner:
                a, b = owner[key], action
                # revert whichever of the two was changed from its default
                clash = b if bindings[b] != DEFAULT_BINDINGS[b] else a
                if bindings[clash] == DEFAULT_BINDINGS[clash]:
                    clash = None            # both are defaults: nothing to fix here
                    continue
                break
            owner[key] = action
        if clash is None:
            break
        print(f'[controls] "{bindings[clash]}" is already used - {clash} goes back to "{DEFAULT_BINDINGS[clash]}"')
        bindings[clash] = DEFAULT_BINDINGS[clash]
        reverted.append(clash)
    return reverted


def label(bindings: dict, action: str) -> str:
    key = bindings.get(action, '?')
    if key in LABELS:
        return LABELS[key]
    if len(key) == 1 or (key[0] == 'f' and key[1:].isdigit()):
        return key.upper()
    return key
