from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from direct.showbase.DirectObject import DirectObject

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ENTRY = PROJECT_ROOT / "main.py"


def _node_key(node_path):
    try:
        node = node_path.node()
        raw = getattr(node, "this", None)
        return ("ptr", int(raw)) if raw is not None else ("node", id(node))
    except Exception:
        return ("np", id(node_path))


def _children_snapshot(root):
    try:
        return {_node_key(child) for child in root.getChildren()}
    except Exception:
        return set()


def _owned_child_keys(root, baseline):
    """Capture only children created by Anatomic during its construction phase."""
    try:
        return {_node_key(child) for child in root.getChildren() if _node_key(child) not in baseline}
    except Exception:
        return set()


def _remove_owned_children(root, owned_keys):
    """Remove Anatomic-owned children without touching host UI created later."""
    if root is None or not owned_keys:
        return
    try:
        for child in list(root.getChildren()):
            if _node_key(child) in owned_keys:
                child.removeNode()
    except Exception:
        pass


def _load_source_module():
    module_name = f"anatomic_holoverse_source_{id(SOURCE_ENTRY)}"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    previous = os.environ.get("ANATOMIC_HOLOVERSE_EMBEDDED")
    os.environ["ANATOMIC_HOLOVERSE_EMBEDDED"] = "1"
    try:
        spec = importlib.util.spec_from_file_location(module_name, SOURCE_ENTRY)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load Anatomic source: {SOURCE_ENTRY}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            os.environ.pop("ANATOMIC_HOLOVERSE_EMBEDDED", None)
        else:
            os.environ["ANATOMIC_HOLOVERSE_EMBEDDED"] = previous


class HoloVerseNativeMode:
    """Same-window Anatomic runtime using HoloVerse's existing ShowBase."""

    def __init__(self, host, mode=None, entry_path=None, label="ANATOMIC"):
        self.host = host
        self.mode = mode or {}
        self.entry_path = Path(entry_path) if entry_path else SOURCE_ENTRY
        self.label = str(label or "ANATOMIC")
        self.root = None
        self.game = None
        self.input_bridge = None
        self.active = False
        self._aspect_baseline = set()
        self._camera_baseline = set()
        self._aspect_owned = set()
        self._camera_owned = set()
        self._entry_window_size = None
        self._entry_fullscreen = None

    def enter(self):
        if self.active:
            return self
        self._aspect_baseline = _children_snapshot(getattr(self.host, "aspect2d", None))
        self._camera_baseline = _children_snapshot(getattr(self.host, "camera", None))
        try:
            props = self.host.win.getProperties()
            self._entry_window_size = (int(props.getXSize()), int(props.getYSize()))
            self._entry_fullscreen = bool(props.getFullscreen())
        except Exception:
            self._entry_window_size = None
            self._entry_fullscreen = None
        self.root = self.host.render.attachNewNode("anatomic_holoverse_dimension")
        try:
            self.host.setBackgroundColor(0.0, 0.0, 0.0, 1.0)
        except Exception:
            pass

        source = _load_source_module()
        self.game = source.ASCIIMatterLab(host=self.host, render_root=self.root)
        # Same-window invariant: constructing Anatomic must not change the host
        # framebuffer dimensions or fullscreen mode.  Treat any future regression
        # as an integration error instead of silently opening/resizing a window.
        try:
            props = self.host.win.getProperties()
            now_size = (int(props.getXSize()), int(props.getYSize()))
            now_fullscreen = bool(props.getFullscreen())
            if self._entry_window_size is not None and now_size != self._entry_window_size:
                raise RuntimeError(f"Anatomic changed HoloVerse window size {self._entry_window_size} -> {now_size}")
            if self._entry_fullscreen is not None and now_fullscreen != self._entry_fullscreen:
                raise RuntimeError("Anatomic changed HoloVerse fullscreen state during native entry")
        except RuntimeError:
            raise
        except Exception:
            pass
        # Freeze ownership immediately after construction.  HoloVerse may create
        # shared pause/menu UI later; those nodes must survive dimension teardown.
        self._aspect_owned = _owned_child_keys(getattr(self.host, "aspect2d", None), self._aspect_baseline)
        self._camera_owned = _owned_child_keys(getattr(self.host, "camera", None), self._camera_baseline)
        # Input is registered by Anatomic itself on Panda messenger. HoloVerse
        # owns only TAB; no host-action or supplemental bridge is installed.
        self.active = True
        return self

    def _install_supplemental_input(self):
        # These are keys HoloVerse deliberately does not own/forward.  They use a
        # dimension-local DirectObject so every hook is removed on return.
        bridge = DirectObject()
        bridge.accept("r-up", self._supplemental_action, ["r_up"])
        bridge.accept("f2", self._supplemental_action, ["f2"])
        bridge.accept("-", self._supplemental_action, ["minus"])
        bridge.accept("=", self._supplemental_action, ["equals"])
        bridge.accept("backspace", self._supplemental_action, ["backspace"])
        bridge.accept("delete", self._supplemental_action, ["delete"])
        bridge.accept("window-event", self._window_event)
        self.input_bridge = bridge

    def _window_event(self, win):
        game = self.game
        if game is not None:
            try:
                game._window_event(win)
            except Exception:
                pass

    def _supplemental_action(self, action):
        return self.on_host_action(action)

    def update(self, dt):
        if not self.active or self.game is None:
            return
        self.game.update_embedded(dt)

    def on_host_action(self, action):
        game = self.game
        if game is None:
            return False
        a = str(action or "").strip().lower()

        # HoloVerse owns TAB and ESC.  Never reinterpret them here.
        if a in {"tab", "escape", "esc"}:
            return False

        if a in {"w", "a", "s", "d", "shift", "control"}:
            game._key(a, True)
            return True
        if a in {"w_up", "a_up", "s_up", "d_up", "shift_up", "control_up"}:
            game._key(a[:-3], False)
            return True
        if a == "space":
            game.jump()
            return True
        if a == "space_up":
            return True
        if a == "r":
            game._key("r", True)
            return True
        if a == "r_up":
            game._key("r", False)
            return True

        if a == "mouse1":
            game._mouse_primary(True)
            return True
        if a == "mouse1_up":
            game._mouse_primary(False)
            return True
        if a == "mouse3":
            game._mouse_secondary(True)
            return True
        if a == "mouse3_up":
            game._mouse_secondary(False)
            return True

        if a == "m":
            game.toggle_combat_mode()
            return True
        if a == "f1":
            game.toggle_help()
            return True
        if a == "f2":
            game.toggle_motion_forge()
            return True
        if a == "f3":
            game.toggle_combo_composer()
            return True
        if a == "f10":
            game.toggle_mouse_capture()
            return True
        if a == "f11":
            # HoloVerse owns window/fullscreen state.  Returning False leaves the
            # host free to handle its global F11 policy without Anatomic resizing it.
            return False

        if a == "c":
            game._cycle_active_combo()
            return True
        if a == "x":
            if game.motion_forge_visible:
                game._forge_delete_slot()
            elif game.combo_composer_visible:
                game._combo_clear()
            else:
                game._play_active_combo()
            return True
        if a == "z":
            if game.motion_forge_visible:
                game._forge_reset_edits()
            return True
        if a == "b":
            if game.combo_composer_visible:
                game._combo_remove_last()
            return True

        if a.startswith("number_"):
            try:
                number = int(a.split("_", 1)[1])
            except Exception:
                return False
            if 1 <= number <= 9:
                game._number_key(number)
                return True
            return False

        if a == "arrow_left":
            game._forge_select_delta(-1)
            game._combo_select_delta(-1)
            return True
        if a == "arrow_right":
            game._forge_select_delta(1)
            game._combo_select_delta(1)
            return True
        if a in {"arrow_left_up", "arrow_right_up", "arrow_up", "arrow_up_up", "arrow_down", "arrow_down_up"}:
            return True
        if a == "enter":
            if game.motion_forge_visible:
                game._forge_preview()
            elif game.combo_composer_visible:
                game._combo_preview()
            return True
        if a == "q_down":
            game._forge_trim_start()
            return True
        if a == "e_down":
            game._forge_trim_end()
            return True
        if a in {"q_up", "e_up"}:
            return True
        if a in {"wheel_up", "equals"}:
            if game.motion_forge_visible:
                game._forge_speed_delta(+source_step(game))
            return True
        if a in {"wheel_down", "minus"}:
            if game.motion_forge_visible:
                game._forge_speed_delta(-source_step(game))
            return True
        if a == "backspace":
            if game.combo_composer_visible:
                game._combo_remove_last()
            elif game.motion_forge_visible:
                game._forge_reset_edits()
            return True
        if a == "delete":
            if game.combo_composer_visible:
                game._combo_clear()
            elif game.motion_forge_visible:
                game._forge_delete_slot()
            return True
        return False

    def exit(self):
        self.destroy()

    def cleanup(self):
        self.destroy()

    def destroy(self):
        if self.input_bridge is not None:
            try:
                self.input_bridge.ignoreAll()
            except Exception:
                pass
            self.input_bridge = None
        if self.game is not None:
            try:
                self.game.shutdown_embedded()
            except Exception:
                pass
        _remove_owned_children(getattr(self.host, "camera", None), self._camera_owned)
        _remove_owned_children(getattr(self.host, "aspect2d", None), self._aspect_owned)
        if self.root is not None:
            try:
                if not self.root.isEmpty():
                    self.root.removeNode()
            except Exception:
                pass
        source_module_name = getattr(getattr(self.game, "__class__", None), "__module__", "") if self.game is not None else ""
        self.game = None
        self.root = None
        if source_module_name.startswith("anatomic_holoverse_source_"):
            sys.modules.pop(source_module_name, None)
        self._camera_owned.clear()
        self._aspect_owned.clear()
        self.active = False


def source_step(game):
    source = sys.modules.get(getattr(game.__class__, "__module__", ""))
    return float(getattr(source, "MOTION_FORGE_SPEED_STEP", 0.10)) if source is not None else 0.10


def create_mode(host, mode=None, entry_path=None, label="ANATOMIC"):
    return HoloVerseNativeMode(host, mode=mode, entry_path=entry_path, label=label)
