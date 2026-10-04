"""HoloVerse same-window adapter for the complete HoloShell game.

The adapter mounts the real HoloShell.py/CommandHubApp runtime into the
already-running HoloVerse ShowBase. It does not recreate the observatory,
artifacts, world simulation, HUD, or Core as a substitute scene.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

MODE_ID = "holoshell"
MODE_TITLE = "HoloShell"
ADAPTER_VERSION = "1.2.0-seamless-holoverse-native"


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
            "audio_owner": "holoverse_host",
        }

    def _load_source_module(self):
        # Link identity remains main.py, but native mode loads HoloShell.py
        # directly under a unique module name so repeated visits do not reuse
        # stale module-global runtime state from a prior dimension session.
        project_root = self.entry_path.parent
        source = project_root / "HoloShell.py"
        if not source.exists():
            raise FileNotFoundError(f"HoloShell source missing: {source}")
        module_name = f"holoshell_full_source_{int(time.time() * 1000)}"
        spec = importlib.util.spec_from_file_location(module_name, source)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load HoloShell source spec: {source}")
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
        if not hasattr(module, "HoloShellApp"):
            raise AttributeError("HoloShell main.py does not expose HoloShellApp")
        self._module = module
        return module

    def _snapshot_host_view(self):
        try:
            self._saved_camera_parent = self.host.camera.getParent()
            self._saved_camera_transform = self.host.camera.getTransform()
        except Exception:
            pass
        try:
            self._saved_fov = self.host.camLens.getFov()
            self._saved_near_far = (self.host.camLens.getNear(), self.host.camLens.getFar())
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
                self.host.camLens.setFov(self._saved_fov)
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
        module = self._load_source_module()
        self.delegate = module.HoloShellApp(host_base=self.host, hosted=True)
        self.delegate.setup_input()
        try:
            value = float(getattr(self.delegate.cfg, "background_value", 0.018))
            self.host.setBackgroundColor(value, value, value, 1.0)
        except Exception:
            pass
        self._entered = True
        self._started_at = time.monotonic()
        self._diagnostics.update({
            "source_version": str(getattr(module, "VERSION", "")),
            "runtime_settings": dict(getattr(self.delegate, "holoverse_runtime_contract", {}) or {}),
        })

    def update(self, dt: float):
        if not self._entered or self.delegate is None:
            return
        ok = self.delegate.hosted_step(float(dt or 0.0))
        if not ok:
            try:
                self.host.return_from_native_mode(reason="holoshell_runtime_error")
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
            data.update({
                "active_artifact": getattr(self.delegate, "active_artifact_id", None),
                "world_unlocked": bool(getattr(self.delegate, "world_unlocked", False)),
                "hud_visible": bool(getattr(self.delegate, "hud_visible", True)),
                "internal_mode": str(getattr(getattr(self.delegate, "internal_mode", None), "mode_key", "")),
            })
        return data

    def get_holoverse_result(self) -> dict:
        if self.delegate is None:
            return {"completed": False, "reason": "not_entered"}
        return {
            "completed": False,
            "active_artifact": getattr(self.delegate, "active_artifact_id", None),
            "world_unlocked": bool(getattr(self.delegate, "world_unlocked", False)),
            "internal_mode": str(getattr(getattr(self.delegate, "internal_mode", None), "mode_key", "")),
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
        if module_name.startswith("holoshell_full_source_"):
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
