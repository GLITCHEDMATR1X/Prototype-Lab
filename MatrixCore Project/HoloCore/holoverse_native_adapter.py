"""HoloCore native dimension adapter for HoloVerse.

HoloCore is an external project under ``Prototype Lab/MatrixCore Project``.
It owns its own scene, input bindings, local world modules and teardown.  The
HoloVerse host supplies only the already-running Panda3D window, disposable
native camera and TAB return lifecycle through ``holoverse_dimension_v1``.

This intentionally contains no dependency on a HoloCore scene class inside
HoloVerse.  Standalone development continues to run ``main.py`` directly.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

from panda3d.core import AntialiasAttrib, TextNode, Vec3, WindowProperties
from direct.gui.DirectGui import DirectLabel

ADAPTER_ID = "holocore_external_native_dimension_v7"
MODE_ID = "holocore"
MODE_TITLE = "HoloCore"
HOST_CONTRACT = "holoverse_dimension_v1"
REQUIRED_FILES = (
    "main.py",
    "hub_world.py",
    "world_grid.py",
    "holo_vessel.py",
    "dimensions/outer_flat_world.py",
    "dimensions/dimension_manager.py",
)
LOCAL_MODULES = (
    "hub_world",
    "world_grid",
    "holo_mermaid",
    "holo_jellyfish",
    "holo_octopus",
    "holo_vessel",
    "holocore_line_kit",
    "dimensions",
    "dimensions.dimension_manager",
    "dimensions.surface_placement",
    "dimensions.outer_flat_world",
    "dimensions.performance_smoother",
    "dimensions.bubble_dome_lensing",
    "dimensions.holocore_strata",
)


def adapter_manifest() -> dict[str, Any]:
    return {
        "id": ADAPTER_ID,
        "mode_id": MODE_ID,
        "route": "native_panda",
        "host_contract": HOST_CONTRACT,
        "same_window_only": True,
        "forbid_child_process": True,
        "return_target": "gleebs_dimension_archive",
        "required_files": list(REQUIRED_FILES),
    }


def _root_for(entry_path: Path | None = None) -> Path:
    if entry_path is not None:
        try:
            return Path(entry_path).resolve().parent
        except Exception:
            pass
    return Path(__file__).resolve().parent


def _validate_root(root: Path) -> None:
    missing = [rel for rel in REQUIRED_FILES if not (root / rel).is_file()]
    if missing:
        raise FileNotFoundError("HoloCore native dimension missing: " + ", ".join(missing))


class HoloVerseNativeMode:
    """Self-owned HoloCore scene mounted into HoloVerse's native camera slot."""

    def __init__(self, host, *, mode: dict | None = None, entry_path: Path | None = None, label: str = MODE_TITLE) -> None:
        self.host = host
        self.mode = dict(mode or {})
        self.label = str(label or MODE_TITLE)
        self.entry_path = Path(entry_path or (_root_for() / "main.py")).resolve()
        self.root_dir = self.entry_path.parent
        _validate_root(self.root_dir)

        self._entered = False
        self._destroyed = False
        self._inserted_path = False
        self._owned_events: set[str] = set()
        self._imported_modules: set[str] = set()
        self._displaced_modules: dict[str, object] = {}
        self._render_baseline = set()
        self._old_player_attr = getattr(host, "player", None)
        self._saved_background = None
        self._saved_render_state = None
        self._keys: dict[str, bool] = {}

        self.elapsed = 0.0
        self.heading = 0.0
        self.pitch = 0.0
        self.eye_height = 13.0
        self.mouse_sensitivity = 0.105
        self.walk_speed = 24.0
        self.sprint_speed = 46.0
        # HC-1: on-foot rise/sink through the open column, matching standalone
        # HoloCore (main.py vertical_fly_speed, x1.35 with Shift).
        self.vertical_fly_speed = 42.0

        self.hub = None
        self.outer_world = None
        self.player = None
        self.holo_vessel = None
        self.holo_vessel_boarded = False
        self.holo_vessel_piloting = False
        self.return_prompt = None
        self.help_prompt = None
        self.help_visible = False
        self.holo_vessel_prompt = None
        self._holo_vessel_prompt_visible = None
        self._holo_vessel_prompt_text = ""

    # ------------------------------------------------------------------
    # Native lifecycle
    # ------------------------------------------------------------------
    def enter(self) -> None:
        if self._entered or self._destroyed:
            return
        self._entered = True
        self._snapshot_host_state()
        try:
            HubWorldAdapter, FlatOuterWorldAdapter, HoloVessel = self._load_local_runtime()
            self.host.setBackgroundColor(0.0, 0.0, 0.0025, 1.0)
            try:
                self.host.render.setAntialias(AntialiasAttrib.MAuto)
            except Exception:
                pass
            self.hub = HubWorldAdapter().build(self.host)
            self.outer_world = FlatOuterWorldAdapter(floor_z=self.hub.floor_z, stream_radius=3).build(self.host, self.hub)
            self.player = self.host.render.attachNewNode("holocore_external_dimension_player")
            setattr(self.host, "player", self.player)
            self.host.camera.reparentTo(self.player)
            self.host.camera.setPos(0, 0, self.eye_height)
            self.host.camera.setHpr(0, 0, 0)
            try:
                self.host.camLens.setFov(72)
                self.host.camLens.setNearFar(0.18, 2400)
            except Exception:
                pass
            self._build_prompts()
            self._build_holo_vessel(HoloVessel)
            self._reset_player()
            self._bind_input()
            self._lock_mouse()
        except Exception:
            self.destroy()
            raise

    def _snapshot_host_state(self) -> None:
        try:
            self._render_baseline = {self._node_key(child) for child in self.host.render.getChildren()}
        except Exception:
            self._render_baseline = set()
        try:
            self._saved_render_state = self.host.render.getState()
        except Exception:
            self._saved_render_state = None
        try:
            self._saved_background = self.host.win.getClearColor() if self.host.win is not None else None
        except Exception:
            self._saved_background = None

    @staticmethod
    def _node_key(node_path):
        try:
            return int(node_path.node().this)
        except Exception:
            return id(node_path)

    def _load_local_runtime(self):
        root_text = os.fspath(self.root_dir)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
            self._inserted_path = True

        # HoloCore historically uses top-level local imports.  Remove only
        # conflicting modules with these exact local names, then remember what
        # this dimension imports so teardown can release them again.
        for name in LOCAL_MODULES:
            old = sys.modules.get(name)
            old_file = str(getattr(old, "__file__", "") or "") if old else ""
            if old is None:
                continue
            belongs_here = False
            if old_file:
                try:
                    belongs_here = Path(old_file).resolve().is_relative_to(self.root_dir)
                except Exception:
                    belongs_here = False
            if not belongs_here:
                self._displaced_modules[name] = old
            sys.modules.pop(name, None)
        importlib.invalidate_caches()
        hub_mod = importlib.import_module("hub_world")
        outer_mod = importlib.import_module("dimensions.outer_flat_world")
        vessel_mod = importlib.import_module("holo_vessel")
        # Capture every module HoloCore actually loaded from its own project, not
        # only a brittle handwritten list. This keeps repeated dimension visits
        # from leaving source modules behind in the shared HoloVerse process.
        for name, module in list(sys.modules.items()):
            file_name = str(getattr(module, "__file__", "") or "") if module else ""
            if not file_name:
                continue
            try:
                if Path(file_name).resolve().is_relative_to(self.root_dir):
                    self._imported_modules.add(name)
            except Exception:
                pass
        return hub_mod.HubWorldAdapter, outer_mod.FlatOuterWorldAdapter, vessel_mod.HoloVessel

    # ------------------------------------------------------------------
    # Input ownership: HoloCore owns everything except TAB.
    # ------------------------------------------------------------------
    def _bind(self, event: str, fn, args=None) -> None:
        self.host.accept(event, fn, args or [])
        self._owned_events.add(event)

    def _set_key(self, key: str, down: bool) -> None:
        self._keys[str(key)] = bool(down)

    def _bind_input(self) -> None:
        held = ("w", "a", "s", "d", "arrow_up", "arrow_down", "arrow_left", "arrow_right", "shift", "lshift", "rshift", "space", "c", "page_up", "page_down")
        for key in held:
            self._bind(key, self._set_key, [key, True])
            self._bind(key + "-up", self._set_key, [key, False])
        self._bind("e", self._interact)
        self._bind("h", self._toggle_help_prompt)
        # TAB is deliberately never registered here. HoloVerse owns it.

    def _unbind_input(self) -> None:
        for event in sorted(self._owned_events):
            try:
                self.host.ignore(event)
            except Exception:
                pass
        self._owned_events.clear()
        self._keys.clear()

    def _key_down(self, *names: str) -> bool:
        return any(bool(self._keys.get(name, False)) for name in names)

    # ------------------------------------------------------------------
    # Presentation and first-person control
    # ------------------------------------------------------------------
    def _build_prompts(self) -> None:
        try:
            self.return_prompt = DirectLabel(
                parent=self.host.aspect2d,
                text="HOLOCORE  //  H HELP  //  TAB DIMENSION ARCHIVE",
                pos=(0.0, 0.0, -0.90), scale=0.042,
                frameColor=(0, 0, 0, 0), text_fg=(0.82, 1.0, 1.0, 0.90),
                text_shadow=(0, 0, 0, 0.75), text_align=TextNode.ACenter,
            )
            self.help_prompt = DirectLabel(
                parent=self.host.aspect2d,
                text=("HOLOCORE\n\nWASD MOVE   SHIFT SPRINT   MOUSE LOOK\n"
                      "SPACE / PAGE UP RISE   C / PAGE DOWN SINK\n"
                      "E BOARD / PILOT VESSEL\n"
                      "PILOT: W/S THRUST   A/D YAW   SPACE/C VERTICAL   SHIFT BOOST\n"
                      "TAB RETURN TO HOLOVERSE   H CLOSE HELP"),
                pos=(0.0, 0.0, -0.64), scale=0.034,
                frameColor=(0.0, 0.008, 0.014, 0.86), text_fg=(0.76, 1.0, 1.0, 0.96),
                text_shadow=(0, 0, 0, 0.78), text_align=TextNode.ACenter,
            )
            self.help_prompt.hide()
            self.holo_vessel_prompt = DirectLabel(
                parent=self.host.aspect2d, text="", pos=(0.0, 0.0, -0.82), scale=0.034,
                frameColor=(0, 0, 0, 0), text_fg=(0.72, 1.0, 0.94, 0.94),
                text_shadow=(0, 0, 0, 0.78), text_align=TextNode.ACenter,
            )
            self.holo_vessel_prompt.hide()
        except Exception:
            pass

    def _toggle_help_prompt(self) -> bool:
        self.help_visible = not self.help_visible
        try:
            (self.help_prompt.show if self.help_visible else self.help_prompt.hide)()
        except Exception:
            pass
        return True

    def _lock_mouse(self) -> None:
        try:
            if self.host.win is not None:
                props = WindowProperties(); props.setCursorHidden(True); props.setForeground(True)
                self.host.win.requestProperties(props)
                self._center_mouse_pointer()
        except Exception:
            pass

    def _center_mouse_pointer(self) -> None:
        try:
            props = self.host.win.getProperties(); cx = props.getXSize() // 2; cy = props.getYSize() // 2
            if cx > 0 and cy > 0:
                self.host.win.movePointer(0, cx, cy)
        except Exception:
            pass

    def _look_player_at(self, target: Vec3) -> None:
        world_pos = self.player.getPos(self.host.render) + Vec3(0, 0, self.eye_height)
        self.host.camera.reparentTo(self.host.render); self.host.camera.setPos(world_pos); self.host.camera.lookAt(target)
        h, p, _ = self.host.camera.getHpr(self.host.render)
        self.heading = h; self.pitch = max(-78.0, min(78.0, p)); self.player.setH(self.heading)
        self.host.camera.reparentTo(self.player); self.host.camera.setPos(0, 0, self.eye_height); self.host.camera.setHpr(0, self.pitch, 0)

    def _reset_player(self) -> None:
        try:
            self.player.setPos(self.hub.get_spawn_position()); self._look_player_at(self.hub.get_spawn_target())
        except Exception:
            self.player.setPos(0, -58, 0); self.heading = 0.0; self.pitch = 0.0

    # ------------------------------------------------------------------
    # Vessel
    # ------------------------------------------------------------------
    def _build_holo_vessel(self, vessel_cls) -> None:
        try:
            ground = self._ground_z(0.0, -212.0)
            self.holo_vessel = vessel_cls().build(self.host, Vec3(0.0, -212.0, ground), heading=180.0)
        except Exception as exc:
            self.holo_vessel = None
            print(f"holocore_vessel_build_error:{exc.__class__.__name__}:{exc}")

    def _ground_z(self, x: float, y: float) -> float:
        try:
            if self.outer_world is not None and hasattr(self.outer_world, "collision_ground_z_at"):
                return float(self.outer_world.collision_ground_z_at(float(x), float(y)))
        except Exception:
            pass
        try:
            world_grid = importlib.import_module("world_grid")
            return float(world_grid.sonar_height_at(float(x), float(y)))
        except Exception:
            return float(getattr(self.hub, "floor_z", 0.0) or 0.0)

    @staticmethod
    def _keepout_allows(x: float, y: float) -> bool:
        return (float(x) * float(x) + float(y) * float(y)) >= (92.0 * 92.0)

    def _set_vessel_prompt(self, text: str | None) -> None:
        p = self.holo_vessel_prompt
        if p is None:
            return
        try:
            if not text:
                if self._holo_vessel_prompt_visible is not False:
                    p.hide(); self._holo_vessel_prompt_visible = False
                return
            if self._holo_vessel_prompt_text != text:
                p["text"] = text; self._holo_vessel_prompt_text = text
            if self._holo_vessel_prompt_visible is not True:
                p.show(); self._holo_vessel_prompt_visible = True
        except Exception:
            pass

    def _update_vessel_prompt(self) -> None:
        vessel = self.holo_vessel
        if vessel is None or self.player is None:
            self._set_vessel_prompt(None); return
        pos = self.player.getPos(self.host.render)
        if self.holo_vessel_piloting:
            text = "HOLO VESSEL // PILOTING // W/S THRUST // A/D YAW // SPACE UP // C DOWN // SHIFT BOOST // E LEAVE SEAT"
        elif self.holo_vessel_boarded:
            if vessel.is_near_pilot(pos): text = "HOLO VESSEL // E PILOT SEAT"
            elif vessel.is_near_exit(pos): text = "HOLO VESSEL // E EXIT TO TERRAIN"
            else: text = "HOLO VESSEL // WALKABLE CABIN // FIND SEAT OR REAR EXIT"
        elif vessel.is_near_entry(pos): text = "HOLO VESSEL // E BOARD CRESCENT RUNNER"
        else: text = None
        self._set_vessel_prompt(text)

    def _interact(self) -> bool:
        vessel = self.holo_vessel
        if vessel is None or self.player is None:
            return False
        pos = self.player.getPos(self.host.render)
        if self.holo_vessel_piloting:
            self.holo_vessel_piloting = False; self.holo_vessel_boarded = True
            self.player.setPos(vessel.pilot_seat_world_position())
            self.heading = float(vessel.root.getH(self.host.render)) if vessel.root is not None else self.heading
            self.player.setH(self.heading); self.host.camera.reparentTo(self.player); self.host.camera.setPos(0, 0, self.eye_height); self.host.camera.setHpr(0, self.pitch, 0)
            return True
        if self.holo_vessel_boarded:
            if vessel.is_near_pilot(pos):
                self.holo_vessel_piloting = True; self.player.setPos(vessel.pilot_seat_world_position())
                self.host.camera.reparentTo(self.host.render); self.host.camera.setPos(vessel.pilot_camera_world_position()); self.host.camera.lookAt(vessel.pilot_look_world_position())
                return True
            if vessel.is_near_exit(pos):
                self.holo_vessel_boarded = False
                entry = vessel.entry_world_position(); self.player.setPos(vessel.exit_world_position(self._ground_z(float(entry.x), float(entry.y))))
                self.host.camera.reparentTo(self.player); self.host.camera.setPos(0, 0, self.eye_height); self.host.camera.setHpr(0, self.pitch, 0)
                return True
            return False
        if vessel.is_near_entry(pos):
            self.holo_vessel_boarded = True; self.player.setPos(vessel.board_spawn_world_position())
            self.heading = float(vessel.root.getH(self.host.render)) if vessel.root is not None else self.heading
            self.player.setH(self.heading); self.host.camera.reparentTo(self.player); self.host.camera.setPos(0, 0, self.eye_height); self.host.camera.setHpr(0, self.pitch, 0)
            return True
        return False

    def _update_vessel_pilot(self, dt: float) -> None:
        vessel = self.holo_vessel
        if vessel is None or not self.holo_vessel_piloting:
            return
        forward = float(self._key_down("w", "arrow_up")) - float(self._key_down("s", "arrow_down"))
        turn = float(self._key_down("a", "arrow_left")) - float(self._key_down("d", "arrow_right"))
        vertical = float(self._key_down("space", "page_up")) - float(self._key_down("c", "page_down"))
        vessel.move_piloted(dt, forward_axis=forward, turn_axis=turn, vertical_axis=vertical,
                           terrain_height_func=self._ground_z, keepout_func=self._keepout_allows,
                           boost=self._key_down("shift", "lshift", "rshift"))
        self.player.setPos(vessel.pilot_seat_world_position())
        self.host.camera.reparentTo(self.host.render); self.host.camera.setPos(vessel.pilot_camera_world_position()); self.host.camera.lookAt(vessel.pilot_look_world_position())

    def _clamp_with_vessel(self, old_pos: Vec3, new_pos: Vec3) -> Vec3:
        vessel = self.holo_vessel
        if vessel is None:
            return Vec3(new_pos)
        if self.holo_vessel_boarded:
            return Vec3(vessel.clamp_interior_position(new_pos))
        try:
            # HC-1: new_pos already carries the on-foot altitude; keep it.
            return Vec3(vessel.push_outside_around_hull(old_pos, Vec3(new_pos)))
        except Exception:
            return Vec3(new_pos)

    # ------------------------------------------------------------------
    # Per-frame native update
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        if not self._entered or self._destroyed:
            return
        dt = min(0.05, max(0.0, float(dt or 0.0)))
        self.elapsed += dt
        task_stub = type("HoloCoreTask", (), {"time": self.elapsed, "dt": dt})()
        try:
            if self.hub is not None: self.hub.update(task_stub)
            if self.outer_world is not None: self.outer_world.update(task_stub)
        except Exception as exc:
            print(f"holocore_world_update_error:{exc.__class__.__name__}:{exc}")
        if self.holo_vessel_piloting:
            self._update_vessel_pilot(dt)
        else:
            self._update_first_person(dt)
        self._update_vessel_prompt()

    def _update_first_person(self, dt: float) -> None:
        if self.player is None or self.player.isEmpty():
            return
        try:
            props = self.host.win.getProperties(); cx = props.getXSize() // 2; cy = props.getYSize() // 2
            pointer = self.host.win.getPointer(0); dx = pointer.getX() - cx; dy = pointer.getY() - cy
            if dx or dy:
                self.heading -= dx * self.mouse_sensitivity; self.pitch -= dy * self.mouse_sensitivity
                self.pitch = max(-78.0, min(78.0, self.pitch)); self._center_mouse_pointer()
        except Exception:
            pass
        self.player.setH(self.heading); self.host.camera.setHpr(0, self.pitch, 0)
        move = Vec3(0, 0, 0); quat = self.player.getQuat(self.host.render); forward = quat.getForward(); right = quat.getRight()
        forward.setZ(0); right.setZ(0)
        if forward.lengthSquared() > 0: forward.normalize()
        if right.lengthSquared() > 0: right.normalize()
        if self._key_down("w", "arrow_up"): move += forward
        if self._key_down("s", "arrow_down"): move -= forward
        if self._key_down("d", "arrow_right"): move += right
        if self._key_down("a", "arrow_left"): move -= right
        vertical = float(self._key_down("space", "page_up")) - float(self._key_down("c", "page_down"))
        if self.holo_vessel_boarded:
            vertical = 0.0  # the cabin floor owns height while aboard
        if move.lengthSquared() <= 0 and abs(vertical) < 0.01:
            return
        sprint = self._key_down("shift", "lshift", "rshift")
        speed = self.sprint_speed if sprint else self.walk_speed
        old_pos = Vec3(self.player.getPos(self.host.render)); new_pos = Vec3(old_pos)
        if move.lengthSquared() > 0:
            move.normalize(); new_pos = Vec3(old_pos + move * speed * dt)
        if not self.holo_vessel_boarded:
            # HC-1: height is kept as an offset above the seabed, so walking
            # over hills keeps the same clearance and Space/C climb or sink
            # through the open column without a ceiling.
            offset = float(old_pos.z) - self._ground_z(float(old_pos.x), float(old_pos.y))
            if abs(offset) <= 0.08:
                offset = 0.0
            offset += vertical * self.vertical_fly_speed * (1.35 if sprint else 1.0) * dt
            new_pos.z = self._ground_z(float(new_pos.x), float(new_pos.y)) + offset
        self.player.setPos(self._clamp_with_vessel(old_pos, new_pos))

    def on_host_action(self, action: str) -> bool:
        action = str(action or "").lower()
        if action in {"e", "e_down", "interact"}:
            return self._interact()
        if action in {"toggle_dimension_ui", "dimension_ui", "h"}:
            return self._toggle_help_prompt()
        return False

    def get_holoverse_result(self) -> dict[str, Any]:
        return {"dimension": MODE_ID, "completed": False}

    def exit(self) -> None:
        self.destroy()

    def destroy(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        self._unbind_input()
        try:
            strata = getattr(self.outer_world, "strata", None)
            if strata is not None:
                strata.destroy()  # HC-1: also removes the band title from aspect2d
        except Exception:
            pass
        for widget in (self.return_prompt, self.help_prompt, self.holo_vessel_prompt):
            try:
                if widget is not None: widget.destroy()
            except Exception:
                pass
        try:
            self.host.camera.reparentTo(self.host.render)
        except Exception:
            pass
        # Remove every render child created after native entry. HoloVerse also
        # performs a baseline purge after this; this local cleanup keeps HoloCore
        # independently well-behaved with any compatible host.
        try:
            for child in list(self.host.render.getChildren()):
                if self._node_key(child) not in self._render_baseline:
                    child.removeNode()
        except Exception:
            pass
        try:
            if self._saved_render_state is not None: self.host.render.setState(self._saved_render_state)
        except Exception:
            pass
        try:
            if self._old_player_attr is None and hasattr(self.host, "player"): delattr(self.host, "player")
            elif self._old_player_attr is not None: setattr(self.host, "player", self._old_player_attr)
        except Exception:
            pass
        try:
            if self._saved_background is not None and self.host.win is not None: self.host.win.setClearColor(self._saved_background)
        except Exception:
            pass
        for name in sorted(self._imported_modules, key=lambda n: (n.count("."), n), reverse=True):
            sys.modules.pop(name, None)
        self._imported_modules.clear()
        for name, module in self._displaced_modules.items():
            if name not in sys.modules:
                sys.modules[name] = module
        self._displaced_modules.clear()
        if self._inserted_path:
            root_text = os.fspath(self.root_dir)
            try:
                while root_text in sys.path: sys.path.remove(root_text)
            except Exception:
                pass
            self._inserted_path = False


def create_mode(host_app, *, mode: dict | None = None, entry_path: Path | None = None, label: str = MODE_TITLE):
    return HoloVerseNativeMode(host_app, mode=mode, entry_path=entry_path, label=label)


create_adapter = create_mode
create_native_adapter = create_mode
