"""Settings and progress shared by Mirror's Limbo, DreamCatcher and Andrew's Nightmare.

Mirror's Limbo owns the player's settings file. DreamCatcher and Andrew's Nightmare read
it at startup so mouse feel, FOV, volume and display mode stay the same in every world,
and write the shared keys back when the player changes them there.

Linked-world progress (completions and DreamCatcher's house state) lives next to the
Limbo saves in ``linked_worlds.json``. Only one game process owns the player at a time,
so plain atomic replace-writes are sufficient.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

LIMBO_DEFAULT_FOV = 70.0
LIMBO_SENSITIVITY_RANGE = (0.035, 0.120)
DISPLAY_RESOLUTIONS = ((1280, 720), (1600, 900), (1920, 1080), (2560, 1440), (3840, 2160))
DISPLAY_MODES = ('borderless', 'fullscreen', 'windowed')
DEFAULTS = {
    'master_volume': 0.82,
    'mouse_sensitivity': 0.070,
    'invert_y': False,
    'fov': LIMBO_DEFAULT_FOV,
    'display_mode': 'borderless',
    'resolution_index': 2,
    'vsync': True,
}
PROGRESS_SCHEMA = 'gx.linked_worlds.v1'


def limbo_save_dir() -> Path:
    """Same location Mirror's Limbo main.py uses for its saves (keep in sync)."""
    try:
        if sys.platform.startswith('win'):
            base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA')
            if base:
                return Path(base) / 'GLITCHED MATRIX' / 'Mirrors Limbo' / 'saves'
        if sys.platform == 'darwin':
            return Path.home() / 'Library' / 'Application Support' / 'GLITCHED MATRIX' / 'Mirrors Limbo' / 'saves'
        base = os.environ.get('XDG_DATA_HOME')
        if base:
            return Path(base) / 'glitched-matrix' / 'mirrors-limbo' / 'saves'
        return Path.home() / '.local' / 'share' / 'glitched-matrix' / 'mirrors-limbo' / 'saves'
    except Exception:
        return Path(__file__).resolve().parents[1] / 'user_data' / 'saves'


def _read_dict(path: Path) -> dict:
    for candidate in (path, path.with_name(path.name + '.previous_good')):
        try:
            raw = json.loads(candidate.read_text(encoding='utf-8'))
            if isinstance(raw, dict):
                return raw
        except (OSError, ValueError):
            continue
    return {}


def _write_dict(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            if isinstance(json.loads(path.read_text(encoding='utf-8')), dict):
                shutil.copy2(path, path.with_name(path.name + '.previous_good'))
        except (OSError, ValueError):
            pass
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)


# ---------------------------------------------------------------- settings

def settings_path() -> Path:
    return limbo_save_dir() / 'settings.json'


def load_settings() -> dict:
    """Validated shared settings. Missing file -> Limbo defaults."""
    raw = _read_dict(settings_path())
    out = dict(DEFAULTS)
    try:
        out['master_volume'] = max(0.0, min(1.0, float(raw.get('master_volume', out['master_volume']))))
    except (TypeError, ValueError):
        pass
    try:
        lo, hi = LIMBO_SENSITIVITY_RANGE
        out['mouse_sensitivity'] = max(lo, min(hi, float(raw.get('mouse_sensitivity', out['mouse_sensitivity']))))
    except (TypeError, ValueError):
        pass
    out['invert_y'] = bool(raw.get('invert_y', out['invert_y']))
    try:
        out['fov'] = max(60.0, min(90.0, float(raw.get('fov', out['fov']))))
    except (TypeError, ValueError):
        pass
    mode = str(raw.get('display_mode', out['display_mode'])).lower()
    out['display_mode'] = mode if mode in DISPLAY_MODES else 'borderless'
    try:
        out['resolution_index'] = max(0, min(len(DISPLAY_RESOLUTIONS) - 1, int(raw.get('resolution_index', 2))))
    except (TypeError, ValueError):
        pass
    out['vsync'] = bool(raw.get('vsync', out['vsync']))
    out['resolution'] = list(DISPLAY_RESOLUTIONS[out['resolution_index']])
    out['present'] = bool(raw)
    return out


def update_settings(**changes) -> None:
    """Write shared keys back into Limbo's settings file, preserving everything else."""
    path = settings_path()
    data = _read_dict(path)
    if not data:
        data = {'schema': 'mirrors_limbo.settings.v4'}
    for key, value in changes.items():
        if key == 'resolution':
            try:
                data['resolution_index'] = DISPLAY_RESOLUTIONS.index(tuple(int(v) for v in value))
            except ValueError:
                continue
        elif key == 'mouse_sensitivity':
            lo, hi = LIMBO_SENSITIVITY_RANGE
            data[key] = round(max(lo, min(hi, float(value))), 4)
        elif key == 'fov':
            data[key] = float(max(60.0, min(90.0, float(value))))
        elif key == 'display_mode':
            if value in DISPLAY_MODES:
                data[key] = value
        elif key in DEFAULTS:
            data[key] = value
    try:
        _write_dict(path, data)
    except OSError as exc:
        print('SHARED_SETTINGS SAVE_FAILED', repr(exc), flush=True)


def world_fov(world_default: float, shared_fov: float, lo: float = 55.0, hi: float = 110.0) -> float:
    """Keep each world's designed FOV but follow the player's Limbo FOV preference."""
    return max(lo, min(hi, float(world_default) + (float(shared_fov) - LIMBO_DEFAULT_FOV)))


def limbo_fov_from_world(world_fov_value: float, world_default: float) -> float:
    return max(60.0, min(90.0, LIMBO_DEFAULT_FOV + float(world_fov_value) - float(world_default)))


def apply_master_volume(base, volume: float) -> None:
    volume = max(0.0, min(1.0, float(volume)))
    for manager in [*(base.sfxManagerList or []), base.musicManager]:
        if manager is not None:
            try:
                manager.setVolume(volume)
            except Exception:
                pass


# ---------------------------------------------------------------- progress

def progress_path() -> Path:
    return limbo_save_dir() / 'linked_worlds.json'


def load_progress() -> dict:
    raw = _read_dict(progress_path())
    data = {
        'schema': PROGRESS_SCHEMA,
        'dreamcatcher': {'completed': False, 'completions': 0, 'first_completed_utc': None},
        'andrews_nightmare': {'completed': False, 'completions': 0, 'endings': [], 'first_completed_utc': None},
        'dreamcatcher_house': None,
    }
    if raw.get('schema') == PROGRESS_SCHEMA:
        for key in ('dreamcatcher', 'andrews_nightmare'):
            if isinstance(raw.get(key), dict):
                data[key].update(raw[key])
        if isinstance(raw.get('dreamcatcher_house'), dict):
            data['dreamcatcher_house'] = raw['dreamcatcher_house']
    return data


def save_progress(data: dict) -> None:
    data = dict(data)
    data['schema'] = PROGRESS_SCHEMA
    try:
        _write_dict(progress_path(), data)
    except OSError as exc:
        print('LINKED_PROGRESS SAVE_FAILED', repr(exc), flush=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def record_completion(world: str, ending: str | None = None) -> dict:
    """Mark 'dreamcatcher' or 'andrews_nightmare' complete. Returns the updated record."""
    data = load_progress()
    rec = data[world]
    rec['completed'] = True
    rec['completions'] = int(rec.get('completions', 0)) + 1
    rec['first_completed_utc'] = rec.get('first_completed_utc') or _now()
    if ending and world == 'andrews_nightmare':
        endings = list(rec.get('endings') or [])
        if ending not in endings:
            endings.append(ending)
        rec['endings'] = endings
    save_progress(data)
    print('LINKED_PROGRESS COMPLETE', world, ending or '', flush=True)
    return rec


def save_house(snapshot: dict | None) -> None:
    data = load_progress()
    data['dreamcatcher_house'] = snapshot
    save_progress(data)


def load_house() -> dict | None:
    house = load_progress().get('dreamcatcher_house')
    return house if isinstance(house, dict) else None
