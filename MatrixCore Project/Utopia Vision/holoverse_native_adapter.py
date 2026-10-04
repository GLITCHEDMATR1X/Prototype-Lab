"""Utopia Vision (Lens Tour) inside HoloVerse's own window.  Pass 282.73.

HoloVerse loads this file instead of starting main.py as a second program, so the tour draws
into the same window (one window for OBS, no second python).  TAB returns to the hub.
main.py is untouched and still runs on its own.

The game's UtopiaApp is a ShowBase subclass.  A small subclass binds it to HoloVerse instead:
ShowBase.__init__ is skipped while it is built, and ShowBase-owned state (render, camera, loader,
taskMgr, win, audio managers, ...) resolves to HoloVerse's, whose camera/lens HoloVerse has
already isolated for the dimension.  On exit the game's events, tasks and scene nodes are
released and HoloVerse's background/clear colour is restored.
"""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

MODE_TITLE = "UTOPIA // LENS TOUR"
FOLDER = Path(__file__).resolve().parent


def _load_game_module():
    if str(FOLDER) not in sys.path:
        sys.path.insert(0, str(FOLDER))
    name = f"utopia_vision_hosted_{int(time.time() * 1000)}"
    spec = importlib.util.spec_from_file_location(name, FOLDER / "main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module, name


class HoloVerseNativeMode:
    def __init__(self, host, mode=None, entry_path=None, label=MODE_TITLE):
        self.host = host
        self.label = label
        self.world = None
        self._module_name = ""
        self._background = None
        self._clear_color = None
        self._baseline_nodes = {}

    def _roots(self) -> dict:
        host = self.host
        return {n: getattr(host, n) for n in ("render", "render2d", "aspect2d") if getattr(host, n, None) is not None}

    def enter(self):
        host = self.host
        module, self._module_name = _load_game_module()
        self._baseline_nodes = {k: {c.getKey() for c in r.getChildren()} for k, r in self._roots().items()}
        try:
            self._background = host.getBackgroundColor()
            self._clear_color = host.win.getClearColor() if host.win is not None else None
        except Exception:
            pass
        saved_argv = sys.argv
        sys.argv = [str(FOLDER / "main.py")]
        try:
            args = module.parse_args()                    # the tour's own defaults, not HoloVerse's argv
        finally:
            sys.argv = saved_argv
        from direct.showbase.ShowBase import ShowBase

        class HostedUtopiaApp(module.UtopiaApp):
            def __getattr__(self, name):                 # ShowBase-owned state -> HoloVerse's
                if name.startswith("__"):
                    raise AttributeError(name)
                return getattr(host, name)

            def userExit(self):                          # never closes HoloVerse
                host.return_from_native_mode(reason="utopia_vision_exit")

        original_init = ShowBase.__init__
        ShowBase.__init__ = lambda self, *a, **k: None
        try:
            self.world = HostedUtopiaApp(args)
        finally:
            ShowBase.__init__ = original_init
        print(f"native_mode_enter label={self.label} source=utopia_vision")

    def update(self, dt: float):
        pass                                             # the tour's tasks run on HoloVerse's task manager

    def get_holoverse_result(self) -> dict:
        return {"completed": False, "signal": "utopia_lens_tour_visit",
                "gleebs_response": "Utopia, the way it looked before it fell. I still know every street."}

    def exit(self):
        world = self.world
        self.world = None
        host = self.host
        if world is not None:
            for name in ("_stop_district_music", "_stop_dynamic_ambience", "_stop_gleebs_audio"):
                try:
                    getattr(world, name)()
                except Exception:
                    pass
            for attr in ("gleebs_actor", "gleebs_ar_actor"):
                actor = world.__dict__.get(attr)
                try:
                    if actor is not None:
                        actor.cleanup()
                except Exception:
                    pass
            try:
                world.ignoreAll()
            except Exception:
                pass
        # Tasks the tour added are removed by HoloVerse's own residue purge (it compares stable
        # Panda task ids; Python wrapper ids change between calls and must not be used here).
        for key, root in self._roots().items():
            keep = self._baseline_nodes.get(key, set())
            try:
                for child in list(root.getChildren()):
                    if child.getKey() not in keep:
                        child.removeNode()
            except Exception:
                pass
        try:
            if self._background is not None:
                host.setBackgroundColor(self._background)
            if self._clear_color is not None and host.win is not None:
                host.win.setClearColor(self._clear_color)
        except Exception:
            pass
        sys.modules.pop(self._module_name, None)

    def destroy(self):
        self.exit()


def create_mode(host, mode=None, entry_path=None, label=MODE_TITLE):
    return HoloVerseNativeMode(host, mode=mode, entry_path=entry_path, label=label)
