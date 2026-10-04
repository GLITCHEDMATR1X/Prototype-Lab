"""Runs a linked game launched from HoloVerse so it behaves like part of HoloVerse.  Pass 282.69.

    python holoverse_child_bootstrap.py <path to the game's main.py> [game args...]

What it adds, without editing the game:

* Same display as HoloVerse.  HoloVerse passes its window size, position and mode in
  MATRIX_GAME_WIDTH / _HEIGHT / _X / _Y / _FULLSCREEN / _BORDERLESS.  Window-geometry lines a
  Panda3D game sets with loadPrcFileData (win-size, win-origin, fullscreen, undecorated) are
  replaced by HoloVerse's, and once the window is open the same geometry is applied again so
  start-up resizes in the game cannot pull it back to another size.
* Fully closes.  Closing the game window always ends the game (even when the game replaced
  Panda3D's own window-close handling), and once the game asks to quit the process is
  force-ended after a short grace period, so no python is left running in the background.

Standalone runs (python main.py) never use this file.  Standard library only at import time.
"""
from __future__ import annotations

import os
import runpy
import sys
import threading
import time
from pathlib import Path

GEOMETRY_KEYS = ("win-size", "win-origin", "fullscreen", "undecorated", "win-fixed-size")
EXIT_GRACE_SECONDS = 3.0


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(os.environ.get(name, default)))
    except Exception:
        return default


def _env_flag(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def host_geometry() -> dict | None:
    if not os.environ.get("MATRIX_GAME_WIDTH"):
        return None
    return {
        "w": max(640, _env_int("MATRIX_GAME_WIDTH", 1920)),
        "h": max(360, _env_int("MATRIX_GAME_HEIGHT", 1080)),
        "x": _env_int("MATRIX_GAME_X", 0),
        "y": _env_int("MATRIX_GAME_Y", 0),
        "fullscreen": _env_flag("MATRIX_GAME_FULLSCREEN"),
        "borderless": _env_flag("MATRIX_GAME_BORDERLESS"),
    }


def _geometry_prc(geo: dict) -> str:
    return "\n".join([
        f"win-size {geo['w']} {geo['h']}",
        f"win-origin {geo['x']} {geo['y']}",
        f"fullscreen {'#t' if geo['fullscreen'] else '#f'}",
        f"undecorated {'#t' if geo['borderless'] else '#f'}",
    ])


def _hard_exit_later(seconds: float = EXIT_GRACE_SECONDS) -> None:
    def _run():
        time.sleep(seconds)
        os._exit(0)
    try:
        threading.Thread(target=_run, name="HoloVerseChildExit", daemon=True).start()
    except Exception:
        os._exit(0)


def _install_panda_hooks(geo: dict | None) -> None:
    try:
        import panda3d.core as core
    except Exception:
        return
    original = core.loadPrcFileData

    def load_prc_file_data(name, data, *args, **kwargs):
        if geo is not None and isinstance(data, str):
            kept = [line for line in data.splitlines() if line.strip().split(" ", 1)[0].lower() not in GEOMETRY_KEYS]
            data = "\n".join(kept)
        return original(name, data, *args, **kwargs)

    core.loadPrcFileData = load_prc_file_data
    if geo is not None:
        original("holoverse-host-geometry", _geometry_prc(geo))
    extra = str(os.environ.get("HOLOVERSE_CHILD_EXTRA_PRC", "") or "").replace("\\n", "\n").strip()
    if extra:                                    # test/diagnostic hook (e.g. offscreen runs)
        original("holoverse-child-extra", extra)

    try:
        from direct.showbase import ShowBase as showbase_module
    except Exception:
        return
    ShowBase = showbase_module.ShowBase
    base_init = ShowBase.__init__
    base_user_exit = ShowBase.userExit

    def user_exit(self, *args, **kwargs):
        _hard_exit_later()
        return base_user_exit(self, *args, **kwargs)

    def init(self, *args, **kwargs):
        base_init(self, *args, **kwargs)
        try:
            self._holoverse_closing = False

            def apply_geometry(task=None):
                if geo is None or self.win is None or not hasattr(self.win, "requestProperties"):
                    return None
                from panda3d.core import WindowProperties
                props = WindowProperties()
                props.setSize(geo["w"], geo["h"])
                if not geo["fullscreen"]:
                    props.setOrigin(geo["x"], geo["y"])
                props.setFullscreen(bool(geo["fullscreen"]))
                props.setUndecorated(bool(geo["borderless"]))
                self.win.requestProperties(props)
                return None

            def watch_close(task):
                try:
                    win = self.win
                    if win is not None and hasattr(win, "getProperties") and not win.getProperties().getOpen():
                        if not self._holoverse_closing:
                            self._holoverse_closing = True
                            self.userExit()
                        return task.done
                except Exception:
                    pass
                return task.cont

            # Re-apply after the game's own start-up window changes have run.
            self.taskMgr.doMethodLater(0.35, apply_geometry, "holoverse-child-geometry-a")
            self.taskMgr.doMethodLater(2.0, apply_geometry, "holoverse-child-geometry-b")
            self.taskMgr.add(watch_close, "holoverse-child-close-watch", sort=-60)
        except Exception as exc:
            print(f"holoverse_child_bootstrap_hook_failed: {exc.__class__.__name__}: {exc}")

    ShowBase.__init__ = init
    ShowBase.userExit = user_exit


def _install_pygame_hooks(geo: dict | None = None) -> None:
    """pygame games always get the guaranteed full close.

    Pass 282.75: a game whose first window is RESIZABLE (it lays itself out for any size, as
    Afterlife of IO and Vector Wars do) opens that first window at HoloVerse's size and position,
    the same display standard Panda3D games get.  They used their own 1920x1080 default centred on
    the screen.  Later set_mode calls (the player resizing, the game's own fullscreen setting) are
    left alone, and fixed-size games keep their own resolution because their layouts depend on it.
    """
    try:
        import pygame
    except Exception:
        return
    original_quit = pygame.quit

    def quit_and_end(*args, **kwargs):
        _hard_exit_later()
        return original_quit(*args, **kwargs)

    pygame.quit = quit_and_end
    if geo is None or geo.get("fullscreen"):
        return
    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{geo['x']},{geo['y']}"
    os.environ.pop("SDL_VIDEO_CENTERED", None)
    display = pygame.display
    original_set_mode = display.set_mode
    state = {"first": True}

    def set_mode(size=(0, 0), flags=0, *args, **kwargs):
        try:
            flags_int = int(flags or 0)
        except Exception:
            flags_int = 0
        if state["first"]:
            state["first"] = False
            resizable = bool(flags_int & getattr(pygame, "RESIZABLE", 0))
            fullscreen = bool(flags_int & getattr(pygame, "FULLSCREEN", 0))
            if resizable and not fullscreen:
                size = (geo["w"], geo["h"])
                print(f"holoverse_child_pygame_window size={geo['w']}x{geo['h']} pos={geo['x']},{geo['y']}")
        return original_set_mode(size, flags, *args, **kwargs)

    display.set_mode = set_mode


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: holoverse_child_bootstrap.py <game main.py> [args...]")
        return 2
    entry = Path(sys.argv[1]).resolve()
    sys.argv = [str(entry)] + sys.argv[2:]
    sys.path.insert(0, str(entry.parent))
    sys.dont_write_bytecode = True
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    geo = host_geometry()
    _install_panda_hooks(geo)
    if "pygame" in entry.read_text(encoding="utf-8", errors="ignore")[:20000]:
        _install_pygame_hooks(geo)
    code = 0
    try:
        runpy.run_path(str(entry), run_name="__main__")
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 0
    except BaseException:
        import traceback
        traceback.print_exc()
        code = 1
    # The game's main loop has ended: make sure nothing (audio threads, stray timers) keeps
    # the process alive after its window is gone.
    # os._exit skips atexit, so run the game's own exit handlers first (saves, the HoloVerse
    # result report), guarded by the hard-exit timer in case one of them hangs.
    _hard_exit_later(EXIT_GRACE_SECONDS + 2.0)
    try:
        import atexit
        atexit._run_exitfuncs()
    except Exception:
        pass
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(int(code or 0))


if __name__ == "__main__":
    main()
