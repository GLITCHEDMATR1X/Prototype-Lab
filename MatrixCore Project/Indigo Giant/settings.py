"""Pass 50 — player settings (display, sound, mouse, hints), saved beside the journey.

Where:  %LOCALAPPDATA%\\GLITCHED MATRIX\\INDIGO GIANT\\settings.json   (the save folder)

The display settings are applied before the window opens (Panda3D PRC settings); size,
fullscreen and vsync can also change while playing, anti-aliasing takes effect on the next
launch. "native" means the monitor's own resolution (3840x2160 on a 4K screen).
"""
from __future__ import annotations

import json
from pathlib import Path

RESOLUTIONS = ('native', '3840x2160', '2560x1440', '1920x1080', '1600x900', '1280x720')
MSAA_STEPS = (0, 2, 4, 8)
DEFAULTS = {
    'resolution': 'native',
    'fullscreen': True,
    'vsync': True,
    'msaa': 4,
    'master': 1.0,
    'music': 0.7,
    'sfx': 1.0,
    'ambience': 0.8,
    'mouse_sensitivity': 1.0,
    'invert_y': False,
    'hints': True,
}
FILE_NAME = 'settings.json'


def load(folder: Path) -> dict:
    s = dict(DEFAULTS)
    path = Path(folder) / FILE_NAME
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            for k, v in data.items():
                d = DEFAULTS.get(k)
                if isinstance(d, bool):
                    if isinstance(v, bool):
                        s[k] = v
                elif isinstance(d, (int, float)):
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        s[k] = type(d)(v)
                elif isinstance(d, str) and isinstance(v, str):
                    s[k] = v
        except (OSError, ValueError) as exc:
            print(f'[settings] ignoring {path.name}: {exc}')
    if s['resolution'] not in RESOLUTIONS:
        s['resolution'] = 'native'
    if s['msaa'] not in MSAA_STEPS:
        s['msaa'] = 4
    for k in ('master', 'music', 'sfx', 'ambience'):
        s[k] = min(1.0, max(0.0, float(s[k])))
    s['mouse_sensitivity'] = min(3.0, max(0.25, float(s['mouse_sensitivity'])))
    return s


def save(folder: Path, s: dict) -> bool:
    try:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / (FILE_NAME + '.tmp')
        tmp.write_text(json.dumps({k: s[k] for k in DEFAULTS}, indent=1), encoding='utf-8')
        tmp.replace(folder / FILE_NAME)
        return True
    except OSError as exc:
        print(f'[settings] could not save: {exc}')
        return False


_NATIVE = []


def native_size():
    """The desktop's resolution, asked of the graphics pipe once (before any window opens)."""
    if _NATIVE:
        return _NATIVE[0]
    _NATIVE.append(_ask_native())
    return _NATIVE[0]


def _ask_native():
    try:
        from panda3d.core import GraphicsPipeSelection
        pipe = GraphicsPipeSelection.getGlobalPtr().makeDefaultPipe()
        w, h = pipe.getDisplayWidth(), pipe.getDisplayHeight()
        if w > 0 and h > 0:
            return int(w), int(h)
    except Exception:              # noqa: BLE001 - no display (tests, servers)
        pass
    return 1920, 1080


def window_size(s: dict, native=None):
    """(width, height) for the settings. Windowed 'native' leaves room for the taskbar."""
    nw, nh = native or native_size()
    if s['resolution'] == 'native':
        w, h = nw, nh
    else:
        w, h = (int(v) for v in s['resolution'].split('x'))
    if not s['fullscreen']:
        # a window never larger than the desktop (a 4K preset on a 1080p screen falls back)
        scale = min(1.0, nw * 0.92 / w, nh * 0.88 / h)
        w, h = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2
    elif w > nw or h > nh:
        w, h = nw, nh                       # fullscreen above the screen's mode: use native
    return w, h


def prc_lines(s: dict, native=None):
    w, h = window_size(s, native)
    lines = [f'win-size {w} {h}', f"fullscreen {'#t' if s['fullscreen'] else '#f'}",
             f"sync-video {'true' if s['vsync'] else 'false'}"]
    if s['msaa']:
        lines += ['framebuffer-multisample 1', f"multisamples {s['msaa']}"]
    return lines
