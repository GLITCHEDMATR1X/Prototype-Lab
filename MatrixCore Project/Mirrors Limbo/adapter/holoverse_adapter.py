"""Same-window HoloVerse 282.14 native adapter for Mirror's Limbo.

The real standalone ``main.py`` remains authoritative.  This adapter imports that
source without running its standalone bootstrap, then creates ``LiminalResidence``
against the already-running HoloVerse ShowBase.  It never creates a second
ShowBase, OS window, subprocess, or event loop.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any


class HoloVerseNativeMode:
    """Host lifecycle bridge for the complete Mirror's Limbo source game."""

    HOST_CONTRACT = "holoverse_dimension_v1"
    COMPATIBILITY = "native"

    def __init__(self, host: Any, mode: dict | None = None, entry_path: Path | None = None,
                 label: str = "MIRROR'S LIMBO") -> None:
        self.host = host
        self.mode = mode or {}
        self.entry_path = Path(entry_path).resolve() if entry_path else None
        self.label = label
        self.game = None
        self.source_module: ModuleType | None = None
        self.source_module_name: str | None = None
        self._destroyed = False

    def _resolve_entry(self) -> Path:
        if self.entry_path and self.entry_path.is_file():
            return self.entry_path
        return (Path(__file__).resolve().parents[1] / "main.py").resolve()

    def _load_source(self) -> ModuleType:
        entry = self._resolve_entry()
        if not entry.is_file():
            raise FileNotFoundError(f"Mirror's Limbo source entry missing: {entry}")
        module_name = f"mirrors_limbo_full_source_{int(time.time() * 1000)}"
        spec = importlib.util.spec_from_file_location(module_name, entry)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to create source spec for {entry}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        old_embedded=os.environ.get("HOLOVERSE_EMBEDDED_MODE")
        os.environ["HOLOVERSE_EMBEDDED_MODE"]="1"
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
        finally:
            if old_embedded is None:
                os.environ.pop("HOLOVERSE_EMBEDDED_MODE",None)
            else:
                os.environ["HOLOVERSE_EMBEDDED_MODE"]=old_embedded
        runtime_cls = getattr(module, "LiminalResidence", None)
        if runtime_cls is None:
            sys.modules.pop(module_name, None)
            raise RuntimeError("Mirror's Limbo runtime class LiminalResidence was not found after source import")
        self.source_module = module
        self.source_module_name = module_name
        return module

    def enter(self):
        if self.game is not None:
            return self.game
        module = self._load_source()
        runtime_cls = module.LiminalResidence
        # Reuse HoloVerse's existing render/window/camera/task manager.  The source
        # class detects this host argument and deliberately skips ShowBase.__init__().
        self.game = runtime_cls(host=self.host, embedded=True)
        print("mirrors_limbo_native_enter source=main.py shared_showbase=1 tab_owner=holoverse responder=holoverse_responder_v1")
        return self.game

    def update(self, dt: float):
        # The original game registers its own Panda tasks on the shared task manager.
        # HoloVerse may call adapter.update(); doing nothing avoids double-stepping.
        return None

    def exit(self):
        self.destroy()

    def destroy(self):
        if self._destroyed:
            return
        self._destroyed = True
        game = self.game
        self.game = None
        if game is not None:
            try:
                game.shutdown_for_holoverse()
            except Exception as exc:
                print(f"mirrors_limbo_native_exit_cleanup_error {type(exc).__name__}:{exc}")
        # HoloVerse also unloads native modules on return; removing our private source
        # name here keeps repeated visits clean even on hosts that do not.
        if self.source_module_name:
            sys.modules.pop(self.source_module_name, None)
        self.source_module = None
        self.source_module_name = None
        print("mirrors_limbo_native_exit clean=1")


def create_mode(host, mode: dict | None = None, entry_path: Path | None = None,
                label: str = "MIRROR'S LIMBO") -> HoloVerseNativeMode:
    return HoloVerseNativeMode(host, mode=mode, entry_path=entry_path, label=label)


def create_native_mode(host, mode: dict | None = None, entry_path: Path | None = None,
                       label: str = "MIRROR'S LIMBO") -> HoloVerseNativeMode:
    return create_mode(host, mode=mode, entry_path=entry_path, label=label)


# Factory aliases used by newer/older host discovery variants.
def create_native_adapter(host, mode: dict | None = None, entry_path: Path | None = None, label: str = "MIRROR'S LIMBO") -> HoloVerseNativeMode:
    return create_mode(host, mode=mode, entry_path=entry_path, label=label)

def create_adapter(host, mode: dict | None = None, entry_path: Path | None = None, label: str = "MIRROR'S LIMBO") -> HoloVerseNativeMode:
    return create_mode(host, mode=mode, entry_path=entry_path, label=label)
