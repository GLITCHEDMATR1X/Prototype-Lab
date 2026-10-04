"""The Indigo Giant - startup diagnostic (refreshed in Pass 62).

    .dev\\RUN_DIAGNOSTIC.bat        (or: python .dev/diagnostic.py)

Checks that every file the game needs is there and that Python can load Panda3D, numpy and
the game package, then starts the game and records everything it prints. The log is written
to .dev/diagnostic.log - send that file back if the game will not start.
"""
from __future__ import annotations

import importlib
import os
import platform
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOG = HERE / 'diagnostic.log'
REQUIRED = (
    ('launcher', ROOT / 'main.py'),
    ('game package', ROOT / 'indigo_giant' / 'app.py'),
    ('character animations', ROOT / 'assets' / 'Universal Animation Library[Standard]' / 'Unreal-Godot' / 'UAL1_Standard.glb'),
    ('Gleebs hologram model', ROOT / 'assets' / 'gleebs' / 'Gleebs_Game.bam'),
    ('sketch vertex shader', ROOT / 'shaders' / 'sketch.vert'),
    ('sketch fragment shader', ROOT / 'shaders' / 'sketch.frag'),
    ('skinning shader', ROOT / 'shaders' / 'skin.vert'),
    ('sky shaders', ROOT / 'shaders' / 'sky.frag'),
    ('fonts', ROOT / 'ui' / 'fonts' / 'Jura-Medium.ttf'),
    ('sound list', ROOT / 'audio' / 'audio_manifest.json'),
)


def write(message: str = '') -> None:
    print(message, flush=True)
    with LOG.open('a', encoding='utf-8') as fh:
        fh.write(message + '\n')


def module_version(name: str) -> tuple[bool, str]:
    try:
        module = importlib.import_module(name)
        version = getattr(module, '__version__', None)
        if name == 'panda3d':
            from panda3d.core import PandaSystem
            version = PandaSystem.getVersionString()
        return True, str(version or 'ok')
    except Exception as exc:
        return False, f'{type(exc).__name__}: {exc}'


def main() -> int:
    LOG.write_text('', encoding='utf-8')
    write('THE INDIGO GIANT - STARTUP DIAGNOSTIC')
    write(f"TIME: {datetime.now().isoformat(timespec='seconds')}")
    write(f'OS: {platform.platform()}')
    write(f'PYTHON: {sys.executable}')
    write(f"PYTHON_VERSION: {sys.version.replace(os.linesep, ' ')}")
    write(f'GAME_FOLDER: {ROOT}')
    write()
    files_ok = True
    for label, path in REQUIRED:
        ok = path.is_file()
        size = path.stat().st_size if ok else 0
        write(f"{label}: {'OK' if ok else 'MISSING'} | {path.relative_to(ROOT)} | {size} bytes")
        files_ok &= ok and size > 0
    write()
    deps_ok = True
    for name in ('numpy', 'panda3d', 'direct.showbase.ShowBase'):
        ok, detail = module_version(name)
        write(f"IMPORT {name}: {'OK' if ok else 'FAIL'} | {detail}")
        deps_ok &= ok
    if deps_ok and files_ok:
        sys.path.insert(0, str(ROOT))
        ok, detail = module_version('indigo_giant.app')
        write(f"IMPORT indigo_giant.app: {'OK' if ok else 'FAIL'} | {detail}")
        deps_ok &= ok
    if not files_ok or not deps_ok:
        write()
        write('RESULT: PRE-LAUNCH CHECK FAILED')
        write('The game was not started. Send .dev/diagnostic.log back for repair.')
        return 2
    write()
    write('PRE-LAUNCH CHECK: PASS')
    write('Starting main.py now. Close the game normally; anything it prints is added below.')
    write('--- GAME OUTPUT START ---')
    try:
        with LOG.open('a', encoding='utf-8') as log_handle:
            proc = subprocess.run([sys.executable, str(ROOT / 'main.py')], cwd=str(ROOT), stdout=log_handle,
                                  stderr=subprocess.STDOUT, check=False)
        write('--- GAME OUTPUT END ---')
        write(f'GAME_EXIT_CODE: {proc.returncode}')
        if proc.returncode == 0:
            write('RESULT: THE GAME CLOSED CLEANLY')
            return 0
        write('RESULT: THE GAME STOPPED WITH AN ERROR')
        write('Send .dev/diagnostic.log back for repair.')
        return proc.returncode or 1
    except Exception:
        with LOG.open('a', encoding='utf-8') as fh:
            traceback.print_exc(file=fh)
        write('RESULT: THE DIAGNOSTIC COULD NOT START THE GAME')
        write('Send .dev/diagnostic.log back for repair.')
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
