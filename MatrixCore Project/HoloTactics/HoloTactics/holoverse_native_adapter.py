"""HoloVerse same-window adapter for the complete HoloTactics game.

The adapter mounts the real ``main.py`` HoloTacticsApp into the already-running
HoloVerse ShowBase.  It does not recreate the tactical board, actors, HUD, or
combat as a substitute scene.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

MODE_ID = "holotactics"
MODE_TITLE = "HoloTactics"
ADAPTER_VERSION = "28.0-native-input-authority"


class HoloVerseNativeMode:
    def __init__(self, host, mode=None, entry_path=None, label=MODE_TITLE):
        self.host = host
        self.mode = dict(mode or {})
        self.entry_path = Path(entry_path).resolve() if entry_path else Path(__file__).resolve().with_name("main.py")
        self.label = str(label or MODE_TITLE)
        self.delegate = None
        self._module = None
        self._entered = False
        self._started_at = 0.0
        self._saved_background = None
        self._saved_camera_parent = None
        self._saved_camera_transform = None
        self._saved_fov = None
        self._saved_near_far = None
        self._diagnostics = {
            "adapter_version": ADAPTER_VERSION,
            "full_source_game": True,
            "same_window": True,
            "second_showbase": False,
            "second_window": False,
            "second_frame_task": False,
            "placeholder_scene": False,
            "audio_owner": "dimension_source_with_holoverse_mix",
        }

    def _load_source_module(self):
        source = self.entry_path
        if not source.exists():
            raise FileNotFoundError(f"HoloTactics source missing: {source}")
        project_root = source.parent
        module_name = f"holotactics_full_source_{int(time.time() * 1000)}"
        spec = importlib.util.spec_from_file_location(module_name, source)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load HoloTactics source spec: {source}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        marker_key = "HOLOVERSE_NATIVE_INPROCESS"
        id_key = "HOLOVERSE_DIMENSION_ID"
        prior_marker = os.environ.get(marker_key)
        prior_id = os.environ.get(id_key)
        added_path = False
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
            added_path = True
        os.environ[marker_key] = "1"
        os.environ[id_key] = str((self.mode.get("manifest") or {}).get("id") or self.mode.get("id") or MODE_ID)
        try:
            spec.loader.exec_module(module)
        finally:
            if added_path:
                try:
                    sys.path.remove(str(project_root))
                except ValueError:
                    pass
            if prior_marker is None:
                os.environ.pop(marker_key, None)
            else:
                os.environ[marker_key] = prior_marker
            if prior_id is None:
                os.environ.pop(id_key, None)
            else:
                os.environ[id_key] = prior_id
        if not hasattr(module, "HoloTacticsApp"):
            raise AttributeError("HoloTactics main.py does not expose HoloTacticsApp")
        self._module = module
        return module

    def _snapshot_host_view(self):
        try:
            self._saved_camera_parent = self.host.camera.getParent()
            self._saved_camera_transform = self.host.camera.getTransform()
        except Exception:
            pass
        try:
            fov = self.host.camLens.getFov()
            self._saved_fov = (float(fov[0]), float(fov[1]))
            self._saved_near_far = (float(self.host.camLens.getNear()), float(self.host.camLens.getFar()))
        except Exception:
            pass
        try:
            self._saved_background = tuple(self.host.getBackgroundColor())
        except Exception:
            self._saved_background = None

    def _restore_host_view(self):
        try:
            if self._saved_camera_parent is not None and not self._saved_camera_parent.isEmpty():
                self.host.camera.reparentTo(self._saved_camera_parent)
                if self._saved_camera_transform is not None:
                    self.host.camera.setTransform(self._saved_camera_transform)
        except Exception:
            pass
        try:
            if self._saved_fov is not None:
                self.host.camLens.setFov(float(self._saved_fov[0]), float(self._saved_fov[1]))
            if self._saved_near_far is not None:
                self.host.camLens.setNearFar(*self._saved_near_far)
        except Exception:
            pass
        if self._saved_background is not None:
            try:
                self.host.setBackgroundColor(*self._saved_background)
            except Exception:
                pass

    def enter(self):
        if self._entered:
            return
        self._snapshot_host_view()
        # HoloTactics owns its source music while mounted, but its volume comes
        # from HoloVerse's master/music settings. Ensure no generic host native
        # track can overlap it if an older host started one before adapter entry.
        try:
            audio = getattr(self.host, "audio", None)
            if audio is not None:
                audio.stop_loop("native_dimension_music")
                audio.stop_loop("native_dimension_air")
        except Exception:
            pass
        module = self._load_source_module()
        # Hosted HoloTactics must not register its standalone key bindings on
        # HoloVerse's global Messenger.  The host owns ESC/TAB/window input and
        # forwards gameplay actions through on_host_action()/hosted_action().
        self.delegate = module.HoloTacticsApp(host_base=self.host, hosted=True)
        try:
            self.host.setBackgroundColor(0.005, 0.008, 0.015, 1.0)
        except Exception:
            pass
        self._entered = True
        self._started_at = time.monotonic()
        self._diagnostics.update({
            "source_template": str(getattr(module, "TEMPLATE_VERSION", "")),
            "runtime_settings": dict(getattr(self.delegate, "holoverse_runtime_contract", {}) or {}),
        })

    def update(self, dt: float):
        if not self._entered or self.delegate is None:
            return
        ok = self.delegate.hosted_step(float(dt or 0.0))
        if not ok:
            try:
                self.host.return_from_native_mode(reason="holotactics_runtime_error")
            except Exception:
                pass

    def on_host_action(self, action: str) -> bool:
        action = str(action or "").lower().strip()
        if action in {"escape", "pause", "menu", "return", "return_to_core"}:
            return False
        if self.delegate is None:
            return False
        return bool(self.delegate.hosted_action(action))

    def toggle_dimension_ui(self) -> bool:
        if self.delegate is None:
            return False
        return bool(self.delegate.hosted_action("h"))

    def get_diagnostics(self) -> dict:
        data = dict(self._diagnostics)
        data.update({
            "entered": self._entered,
            "elapsed": max(0.0, time.monotonic() - self._started_at) if self._started_at else 0.0,
        })
        if self.delegate is not None:
            state = getattr(self.delegate, "state", None)
            data.update({
                "screen_mode": str(getattr(self.delegate, "screen_mode", "")),
                "sector_index": int(getattr(state, "sector_index", 0) or 0) if state is not None else 0,
                "round_index": int(getattr(state, "round_index", 0) or 0) if state is not None else 0,
                "hud_visible": bool(getattr(self.delegate, "hud_visible", True)),
            })
        return data

    def get_holoverse_result(self) -> dict:
        if self.delegate is None:
            return {"completed": False, "reason": "not_entered"}
        state = getattr(self.delegate, "state", None)
        snapshot = {}
        if state is not None and hasattr(state, "snapshot"):
            try:
                snapshot = dict(state.snapshot() or {})
            except Exception:
                snapshot = {}
        return {
            "completed": bool(getattr(state, "journey_complete", lambda: False)()) if state is not None else False,
            "screen_mode": str(getattr(self.delegate, "screen_mode", "")),
            "sector_index": int(getattr(state, "sector_index", 0) or 0) if state is not None else 0,
            "snapshot": snapshot,
        }

    def exit(self):
        if self.delegate is not None:
            try:
                self.delegate.hosted_destroy()
            except Exception:
                pass
        self.delegate = None
        module_name = getattr(self._module, "__name__", "") if self._module is not None else ""
        self._module = None
        if module_name.startswith("holotactics_full_source_"):
            sys.modules.pop(module_name, None)
        self._restore_host_view()
        self._entered = False

    def destroy(self):
        self.exit()

    def cleanup(self):
        self.exit()


def create_mode(host, mode=None, entry_path=None, label=MODE_TITLE):
    return HoloVerseNativeMode(host, mode=mode, entry_path=entry_path, label=label)


def create_native_adapter(host, mode=None, entry_path=None, label=MODE_TITLE):
    return create_mode(host, mode=mode, entry_path=entry_path, label=label)
