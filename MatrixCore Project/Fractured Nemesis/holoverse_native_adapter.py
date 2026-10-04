"""Fractured Nemesis inside HoloVerse's own window.  Pass 282.72.

HoloVerse loads this file (create_mode) instead of starting main.py as a second program, so the
game draws into the same window: one window for OBS, no second python, TAB returns to the hub.
main.py is untouched and still runs on its own.

How: the game's FracturedWorld is a ShowBase subclass.  A small subclass binds it to the host
instead: ShowBase.__init__ is skipped while it is built, and anything the game reads that
ShowBase would normally own (render, camera, loader, taskMgr, win, ...) resolves to HoloVerse's,
whose camera/lens HoloVerse has already isolated for the dimension.  On exit every event the
game accepted is released and HoloVerse removes the nodes and tasks the visit created.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

MODE_TITLE = "Fractured Nemesis"
FOLDER = Path(__file__).resolve().parent


def _load_game_module():
    if str(FOLDER) not in sys.path:
        sys.path.insert(0, str(FOLDER))
    name = f"fractured_nemesis_hosted_{int(time.time() * 1000)}"
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
        self._result = {}
        self._baseline = {}

    # ---- lifecycle ---------------------------------------------------------
    def enter(self):
        host = self.host
        module, self._module_name = _load_game_module()
        self._baseline = self._scene_children()
        try:
            self._background = host.getBackgroundColor()
        except Exception:
            self._background = None
        from direct.showbase.ShowBase import ShowBase
        adapter = self

        class HostedFracturedWorld(module.FracturedWorld):
            def __getattr__(self, name):                 # ShowBase-owned state -> HoloVerse's
                if name.startswith("__"):
                    raise AttributeError(name)
                return getattr(host, name)

            def return_to_holoverse(self):               # ESC: back to the hub, never sys.exit
                try:
                    adapter._result = self._holoverse_result()
                except Exception:
                    pass
                host.return_from_native_mode(reason="fractured_nemesis_escape")

            def userExit(self):
                host.return_from_native_mode(reason="fractured_nemesis_exit")

        original_init = ShowBase.__init__
        ShowBase.__init__ = lambda self, *a, **k: None   # never a second ShowBase inside HoloVerse
        try:
            self.world = HostedFracturedWorld()
        finally:
            ShowBase.__init__ = original_init
        print(f"native_mode_enter label={self.label} source=fractured_nemesis")

    def update(self, dt: float):
        # The game's own "update_world" task runs on HoloVerse's task manager; nothing extra here.
        if self.world is not None:
            try:
                self._result = self.world._holoverse_result()
            except Exception:
                pass

    def get_holoverse_result(self) -> dict:
        return dict(self._result or {})

    def exit(self):
        world = self.world
        self.world = None
        if world is not None:
            try:
                world.ignoreAll()                         # release every key the game accepted
            except Exception:
                pass
            try:
                self.host.taskMgr.remove("update_world")
            except Exception:
                pass
            for attr in ("overlay", "crosshair_root"):
                node = world.__dict__.get(attr)
                try:
                    if node is not None and not node.isEmpty():
                        node.removeNode()
                except Exception:
                    pass
        # Remove every node the visit attached to HoloVerse's scene roots.
        baseline = self._baseline or {}
        for key, root in self._roots().items():
            keep = baseline.get(key, set())
            try:
                for child in list(root.getChildren()):
                    if child.getKey() not in keep:
                        child.removeNode()
            except Exception:
                pass
        if self._background is not None:
            try:
                self.host.setBackgroundColor(self._background)
            except Exception:
                pass
        sys.modules.pop(self._module_name, None)

    def _roots(self) -> dict:
        host = self.host
        return {name: getattr(host, name) for name in ("render", "render2d", "aspect2d") if getattr(host, name, None) is not None}

    def _scene_children(self) -> dict:
        out = {}
        for key, root in self._roots().items():
            try:
                out[key] = {child.getKey() for child in root.getChildren()}
            except Exception:
                out[key] = set()
        return out

    def destroy(self):
        self.exit()


def create_mode(host, mode=None, entry_path=None, label=MODE_TITLE):
    return HoloVerseNativeMode(host, mode=mode, entry_path=entry_path, label=label)
