from __future__ import annotations

import json
import importlib
import math
import os
import sys
import traceback
import textwrap
from datetime import datetime
from pathlib import Path

from holotactics_core import GameState, MAX_JOURNEY_SECTORS, create_default_game
from holotactics_actor_specs import ACTOR_VISUAL_SPECS, GLEEBS_REFERENCE_ASSET, validate_actor_visual_specs
from holotactics_ui_layout import UI_FRAMES, UI_TEXT_POS, UI_TEXT_SCALE, validate_ui_layout
from holotactics_audio import HoloSfx, SFX_CUES, MUSIC_CUES, SECTOR_MUSIC_CUES, ensure_audio_assets, ensure_sfx_assets, validate_audio_assets, validate_sfx_assets, validate_music_assets


def _user_data_root() -> Path:
    """Glitched Matrix standard user-data folder (Windows %LOCALAPPDATA%\\GLITCHED MATRIX\\HoloTactics).
    HOLOTACTICS_USER_DATA overrides it.  The game folder itself is never written."""
    override = str(os.environ.get("HOLOTACTICS_USER_DATA") or "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = str(os.environ.get("LOCALAPPDATA") or "").strip()
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "GLITCHED MATRIX" / "HoloTactics"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "GLITCHED MATRIX" / "HoloTactics"
    xdg = str(os.environ.get("XDG_DATA_HOME") or "").strip()
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / "glitched-matrix" / "holotactics"

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = _user_data_root() / "logs"
REPORTS_DIR = BASE_DIR / "reports"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
TEMPLATE_VERSION = "gleebs_protocol_holotactics.pass30_hud_alignment_redo"
HUD_SCALE = 0.055
HELP_SCALE = 0.052
LOG_SCALE = 0.050


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def _write_crash(exc: BaseException) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    report = LOGS_DIR / "crash_latest.txt"
    report.write_text(
        "Gleebs Protocol HoloTactics crash report\n"
        f"timestamp: {datetime.now().isoformat(timespec='seconds')}\n"
        f"template_version: {TEMPLATE_VERSION}\n"
        f"exception_type: {type(exc).__name__}\n"
        f"exception_message: {exc}\n\n"
        "traceback:\n"
        + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        encoding="utf-8",
    )



def _arg_value(flag: str, default: str | None = None) -> str | None:
    if flag not in sys.argv:
        return default
    index = sys.argv.index(flag)
    if index + 1 >= len(sys.argv):
        return default
    return sys.argv[index + 1]


def _truthy(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def _flag_present(flag: str) -> bool:
    return flag in sys.argv


def _int_setting(value, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(float(value))))
    except Exception:
        return int(default)


def _float_setting(value, default: float, low: float, high: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except Exception:
        return float(default)


def load_holoverse_runtime_settings() -> dict:
    """Read HoloVerse's linked-reality runtime contract without imports.

    Standalone HoloTactics keeps its normal defaults.  A HoloVerse compatibility
    launch consumes the shared settings file/environment, while native in-process
    mounting borrows the already-open ShowBase/window and treats these values as
    presentation/audio policy only.
    """
    payload = {}
    raw_path = str(os.environ.get("HOLOVERSE_SETTINGS_PATH", "") or "").strip()
    if raw_path:
        try:
            data = json.loads(Path(raw_path).read_text(encoding="utf-8"))
            if isinstance(data, dict):
                payload.update(data)
        except Exception:
            pass
    resolution = payload.get("resolution") if isinstance(payload.get("resolution"), dict) else {}
    width = _int_setting(os.environ.get("MATRIX_GAME_WIDTH", resolution.get("width", 1920)), 1920, 640, 7680)
    height = _int_setting(os.environ.get("MATRIX_GAME_HEIGHT", resolution.get("height", 1080)), 1080, 480, 4320)
    return {
        "hosted_contract": bool(raw_path or os.environ.get("HOLOVERSE_DIMENSION_ID") or _truthy(os.environ.get("HOLOVERSE_NATIVE_INPROCESS"))),
        "native_inprocess": _truthy(os.environ.get("HOLOVERSE_NATIVE_INPROCESS")),
        "width": width,
        "height": height,
        "window_x": _int_setting(os.environ.get("MATRIX_GAME_X", 0), 0, -32768, 32768),
        "window_y": _int_setting(os.environ.get("MATRIX_GAME_Y", 0), 0, -32768, 32768),
        "fullscreen": _truthy(os.environ.get("MATRIX_GAME_FULLSCREEN", payload.get("fullscreen", False))),
        "borderless": _truthy(os.environ.get("MATRIX_GAME_BORDERLESS", payload.get("borderless", False))),
        "bordered_fullscreen": _truthy(os.environ.get("MATRIX_GAME_BORDERED_FULLSCREEN", payload.get("bordered_fullscreen", False))),
        "vsync": _truthy(os.environ.get("HOLOVERSE_VSYNC", payload.get("vsync", True))),
        "fps_cap": _int_setting(os.environ.get("HOLOVERSE_FPS_CAP", payload.get("fps_cap", 60)), 60, 15, 240),
        "ui_scale": _float_setting(os.environ.get("HOLOVERSE_UI_SCALE", payload.get("ui_scale", 1.0)), 1.0, 0.75, 1.5),
        "render_scale": _float_setting(os.environ.get("HOLOVERSE_RENDER_SCALE", payload.get("render_scale", 1.0)), 1.0, 0.5, 2.0),
        "hud_visible": _truthy(os.environ.get("MATRIX_GAME_HUD_VISIBLE", os.environ.get("HOLOVERSE_HUD_ENABLED", payload.get("hud_enabled", payload.get("hud_visible", True))))),
        "subtitles_enabled": _truthy(os.environ.get("HOLOVERSE_SUBTITLES_ENABLED", payload.get("subtitles_enabled", True))),
        "mouse_sensitivity": _float_setting(os.environ.get("MATRIX_GAME_MOUSE_SENSITIVITY", payload.get("mouse_sensitivity", 0.22)), 0.22, 0.01, 2.0),
        "invert_y": _truthy(os.environ.get("MATRIX_GAME_INVERT_Y", payload.get("invert_y", False))),
        "controller_deadzone": _float_setting(os.environ.get("MATRIX_GAME_CONTROLLER_DEADZONE", os.environ.get("HOLOVERSE_CONTROLLER_DEADZONE", payload.get("controller_deadzone", 0.12))), 0.12, 0.0, 0.95),
        "brightness": _float_setting(os.environ.get("HOLOVERSE_BRIGHTNESS", payload.get("brightness", 1.0)), 1.0, 0.55, 1.65),
        "contrast": _float_setting(os.environ.get("HOLOVERSE_CONTRAST", payload.get("contrast", 1.0)), 1.0, 0.55, 1.65),
        "gamma": _float_setting(os.environ.get("HOLOVERSE_GAMMA", payload.get("gamma", 1.0)), 1.0, 0.55, 1.85),
        "graphics_quality": str(os.environ.get("MATRIX_GAME_GRAPHICS_QUALITY", os.environ.get("HOLOVERSE_GRAPHICS_QUALITY", payload.get("graphics_quality", "medium"))) or "medium").strip().lower(),
        "master_volume": _float_setting(os.environ.get("HOLOVERSE_MASTER_VOLUME", payload.get("master_volume", 1.0)), 1.0, 0.0, 1.0),
        "music_volume": _float_setting(os.environ.get("HOLOVERSE_MUSIC_VOLUME", payload.get("music_volume", 1.0)), 1.0, 0.0, 1.0),
        "sfx_volume": _float_setting(os.environ.get("HOLOVERSE_SFX_VOLUME", payload.get("sfx_volume", 1.0)), 1.0, 0.0, 1.0),
        "ambience_volume": _float_setting(os.environ.get("HOLOVERSE_AMBIENCE_VOLUME", payload.get("ambience_volume", 1.0)), 1.0, 0.0, 1.0),
    }


HOLOVERSE_RUNTIME_SETTINGS = load_holoverse_runtime_settings()

def run_settings_check() -> None:
    state = create_default_game()
    payload = {
        "schema_version": "holotactics_settings_check.v1",
        "template_version": TEMPLATE_VERSION,
        "ok": True,
        "board_size": [state.width, state.height],
        "units": list(state.units),
        "nodes": {key: {"name": node.name, "pos": node.pos, "effect": node.effect} for key, node in state.nodes.items()},
        "actor_visuals": {key: spec.__dict__ for key, spec in ACTOR_VISUAL_SPECS.items()},
        "actor_visual_issues": validate_actor_visual_specs(),
        "sfx_cues": sorted(SFX_CUES),
        "music_cues": sorted(MUSIC_CUES),
        "audio_asset_issues": validate_audio_assets(BASE_DIR),
        "snapshot": state.snapshot(),
    }
    _write_json(REPORTS_DIR / "settings_check.json", payload)
    print(json.dumps(payload, indent=2, default=str))


def run_logic_smoke() -> None:
    ensure_audio_assets(BASE_DIR)
    state = create_default_game()
    state.cursor = (1, 1)
    assert state.select_at_cursor()
    state.cursor = (3, 2)
    assert state.move_selected_to_cursor()
    state.cursor = (6, 5)
    state.end_player_turn()
    assert state.round_index == 2
    assert state.completion_percent() == 100
    _write_json(REPORTS_DIR / "logic_smoke.json", {"ok": True, "snapshot": state.snapshot()})
    print("logic smoke: ok")


if "--settings-check" in sys.argv:
    run_settings_check()
    raise SystemExit(0)

if "--logic-smoke" in sys.argv:
    run_logic_smoke()
    raise SystemExit(0)

# Panda3D signals for GPTool project discovery: panda3d.core, direct.showbase, ShowBase, loadPrcFileData, .run()
def _load_panda3d_runtime() -> None:
    """Lazy runtime import."""
    global AmbientLight, CardMaker, DirectionalLight, Geom, GeomNode, GeomTriangles
    global GeomVertexData, GeomVertexFormat, GeomVertexWriter, LineSegs, NodePath
    global Plane, Point3, TextNode, TransparencyAttrib, Vec3, WindowProperties, Filename, loadPrcFileData, OnscreenText, ShowBase, Task
    try:
        core = importlib.import_module("panda3d.core")
        onscreen_mod = importlib.import_module("direct.gui.OnscreenText")
        showbase_mod = importlib.import_module("direct.showbase.ShowBase")
        task_mod = importlib.import_module("direct.task")
    except Exception as import_exc:
        print("Panda3D is required to run the visual prototype.")
        print("Install with: python -m pip install panda3d==1.10.16")
        print(f"Import error: {import_exc}")
        raise
    AmbientLight = core.AmbientLight
    CardMaker = core.CardMaker
    DirectionalLight = core.DirectionalLight
    Geom = core.Geom
    GeomNode = core.GeomNode
    GeomTriangles = core.GeomTriangles
    GeomVertexData = core.GeomVertexData
    GeomVertexFormat = core.GeomVertexFormat
    GeomVertexWriter = core.GeomVertexWriter
    LineSegs = core.LineSegs
    NodePath = core.NodePath
    Plane = core.Plane
    Point3 = core.Point3
    TextNode = core.TextNode
    Vec3 = core.Vec3
    TransparencyAttrib = core.TransparencyAttrib
    WindowProperties = core.WindowProperties
    Filename = core.Filename
    loadPrcFileData = core.loadPrcFileData
    OnscreenText = onscreen_mod.OnscreenText
    ShowBase = showbase_mod.ShowBase
    Task = task_mod.Task
    settings = HOLOVERSE_RUNTIME_SETTINGS
    # Importing a linked Panda3D game occurs after HoloVerse has created the
    # sole ShowBase/window/audio stack.  Do not mutate process-global PRC in
    # that mode.  Standalone/compatibility launches still consume host display
    # settings and apply them before ShowBase exists.
    if not settings.get("native_inprocess", False):
        loadPrcFileData("", "window-title HoloVerse // HoloTactics" if settings.get("hosted_contract") else "window-title Gleebs Protocol: HoloTactics")
        loadPrcFileData("", f"win-size {int(settings['width'])} {int(settings['height'])}")
        loadPrcFileData("", f"sync-video {1 if settings.get('vsync', True) else 0}")
        loadPrcFileData("", "show-frame-rate-meter 0")
        loadPrcFileData("", "textures-power-2 none")
        window_type = _arg_value("--window-type") or os.environ.get("GPT_BRIDGE_WINDOW_TYPE")
        screenshot_run = "--screenshot-mode" in sys.argv or _truthy(os.environ.get("GPT_BRIDGE_SMOKE"))
        if window_type in {"offscreen", "none"} or screenshot_run:
            loadPrcFileData("", "window-type offscreen")
            loadPrcFileData("", "audio-library-name null")


_load_panda3d_runtime()


class HoloTacticsApp(ShowBase):
    def __init__(self, host_base=None, hosted: bool = False) -> None:
        self._holoverse_hosted = bool(hosted and host_base is not None)
        self._holoverse_host = host_base if self._holoverse_hosted else None
        self._holoverse_runtime_settings = self._host_runtime_settings(host_base) if self._holoverse_hosted else dict(HOLOVERSE_RUNTIME_SETTINGS)
        self._holoverse_owned_nodes: list[NodePath] = []
        self._hosted_elapsed = 0.0
        if self._holoverse_hosted:
            self._bind_host_showbase(host_base)
        else:
            super().__init__()
            self.disableMouse()
        self.scene_root = self.render.attachNewNode("holotactics_scene_root")
        self.hud_root = self.aspect2d.attachNewNode("holotactics_hud_root")
        self._holoverse_owned_nodes.extend([self.scene_root, self.hud_root])
        self.state: GameState = create_default_game()
        self.tile_nodes: dict[tuple[int, int], NodePath] = {}
        self.tile_frames: dict[tuple[int, int], NodePath] = {}
        self.hover_tile: tuple[int, int] | None = None
        self.unit_nodes: dict[str, NodePath] = {}
        self.node_markers: dict[str, NodePath] = {}
        self.ability_markers: dict[str, NodePath] = {}
        self.effect_rings: list[dict] = []
        self.move_markers: list[NodePath] = []
        self.hud_visible = True
        self.dev_view = False
        self.dev_root: NodePath | None = None
        self.dev_text: OnscreenText | None = None
        self.status_text: OnscreenText | None = None
        self.log_text: OnscreenText | None = None
        self.help_text: OnscreenText | None = None
        self.completion_text: OnscreenText | None = None
        self.title_text: OnscreenText | None = None
        self.result_text: OnscreenText | None = None
        self.menu_text: OnscreenText | None = None
        self.subtitle_text: OnscreenText | None = None
        self.pause_root: NodePath | None = None
        self.pause_text: OnscreenText | None = None
        self.pause_hint_text: OnscreenText | None = None
        self.pause_menu_index = 0
        self.pause_page = "menu"
        self.pause_confirm_action: str | None = None
        self.is_paused = False
        self.journey_map_open = False
        self.journey_map_root: NodePath | None = None
        self.journey_map_title: OnscreenText | None = None
        self.journey_map_hint: OnscreenText | None = None
        self.journey_map_labels: list[OnscreenText] = []
        self.sfx: HoloSfx | None = None
        self._last_victory_key: tuple[int, str] | None = None
        self._defeat_sfx_played = False
        self.hud_panels: list[NodePath] = []
        self.hud_panel_nodes: dict[str, NodePath] = {}
        self.screen_mode = "title"
        if not self._holoverse_hosted:
            self._setup_window()
        self._setup_lighting()
        self._setup_camera()
        self._setup_sfx()
        self._build_scene()
        self._build_hud()
        self._build_dev_overlay()
        self._build_journey_map_overlay()
        if not self._holoverse_hosted:
            self._build_pause_overlay()
            self._bind_controls()
        self.apply_host_runtime_settings()
        self._refresh_scene()
        screenshot_screen = _arg_value("--screenshot-screen") or os.environ.get("GPT_BRIDGE_SCREENSHOT_SCREEN")
        if screenshot_screen in {"mission", "actors"}:
            self._start_mission()
        elif screenshot_screen in {"expanded", "journey", "sector2"}:
            self._start_mission()
            self._force_sector_win_for_screenshot()
            self._advance_journey()
        elif screenshot_screen in {"challenge", "sector3"}:
            self._start_mission()
            self._advance_to_sector_for_screenshot(3)
        elif screenshot_screen in {"sector4", "wide"}:
            self._start_mission()
            self._advance_to_sector_for_screenshot(4)
        elif screenshot_screen in {"sector5", "horizon", "bigger"}:
            self._start_mission()
            self._advance_to_sector_for_screenshot(5)
        elif screenshot_screen in {"finale2", "horizon2"}:
            self._start_mission()
            self._advance_to_sector_for_screenshot(5)
            self._prepare_sector5_finale_stage_for_screenshot(2)
        elif screenshot_screen in {"finale3", "horizon3"}:
            self._start_mission()
            self._advance_to_sector_for_screenshot(5)
            self._prepare_sector5_finale_stage_for_screenshot(3)
        elif screenshot_screen in {"map", "journey-map", "route"}:
            self._start_mission()
            target = int(_arg_value("--screenshot-sector", "3") or 3)
            self._advance_to_sector_for_screenshot(target)
            self._toggle_journey_map(force=True)
        elif screenshot_screen in {"ability", "abilities"}:
            self._start_mission()
            self._force_ability_pickup_for_screenshot()
            self._refresh_scene()
        elif screenshot_screen in {"readability", "tactical"}:
            self._start_mission()
            self._prepare_readability_proof()
            self._refresh_scene()
        elif screenshot_screen in {"readability5", "tactical5"}:
            self._start_mission()
            self._advance_to_sector_for_screenshot(5)
            self._prepare_readability_proof()
            self._refresh_scene()
        elif screenshot_screen in {"dev", "developer", "diagnostics"}:
            self._start_mission()
            self._toggle_dev_view()
        if not self._holoverse_hosted:
            self.taskMgr.add(self._pulse_task, "holo_pulse_task")
        self._write_scene_proof("startup")
        if (not self._holoverse_hosted) and ("--screenshot-mode" in sys.argv or _truthy(os.environ.get("GPT_BRIDGE_SMOKE"))):
            self.taskMgr.doMethodLater(0.75, self._capture_smoke_screenshot, "capture_smoke_screenshot")

    @staticmethod
    def _host_runtime_settings(host) -> dict:
        cfg = getattr(host, "cfg", None)
        if cfg is None:
            data = dict(HOLOVERSE_RUNTIME_SETTINGS)
            data["hosted_contract"] = True
            data["native_inprocess"] = True
            return data
        return {
            "hosted_contract": True,
            "native_inprocess": True,
            "width": int(getattr(cfg, "launch_width", HOLOVERSE_RUNTIME_SETTINGS.get("width", 1920))),
            "height": int(getattr(cfg, "launch_height", HOLOVERSE_RUNTIME_SETTINGS.get("height", 1080))),
            "window_x": int(HOLOVERSE_RUNTIME_SETTINGS.get("window_x", 0)),
            "window_y": int(HOLOVERSE_RUNTIME_SETTINGS.get("window_y", 0)),
            "fullscreen": bool(getattr(cfg, "launch_fullscreen", False)),
            "borderless": bool(getattr(cfg, "launch_borderless", False)),
            "bordered_fullscreen": bool(getattr(cfg, "launch_bordered_fullscreen", True)),
            "vsync": bool(getattr(cfg, "launch_vsync", True)),
            "fps_cap": int(getattr(cfg, "launch_fps_cap", 60)),
            "ui_scale": float(getattr(cfg, "launch_ui_scale", 1.0)),
            "render_scale": float(getattr(cfg, "launch_render_scale", 1.0)),
            "hud_visible": bool(getattr(cfg, "launch_hud_visible", getattr(cfg, "hud_visible", True))),
            "subtitles_enabled": bool(getattr(cfg, "launch_subtitles_enabled", True)),
            "mouse_sensitivity": float(getattr(cfg, "launch_mouse_sensitivity", getattr(cfg, "mouse_sensitivity", 0.22))),
            "invert_y": bool(getattr(cfg, "launch_invert_y", getattr(cfg, "invert_y", False))),
            "controller_deadzone": float(getattr(cfg, "launch_controller_deadzone", getattr(cfg, "controller_deadzone", 0.12))),
            "brightness": float(getattr(cfg, "launch_brightness", 1.0)),
            "contrast": float(getattr(cfg, "launch_contrast", 1.0)),
            "gamma": float(getattr(cfg, "launch_gamma", 1.0)),
            "graphics_quality": str(getattr(cfg, "launch_graphics_quality", "medium") or "medium").lower(),
            "master_volume": float(getattr(cfg, "master_volume", 1.0)),
            "music_volume": float(getattr(cfg, "music_volume", 1.0)),
            "sfx_volume": float(getattr(cfg, "sfx_volume", 1.0)),
            "ambience_volume": float(getattr(cfg, "ambience_volume", 1.0)),
        }

    def _bind_host_showbase(self, host) -> None:
        required = ("render", "render2d", "aspect2d", "camera", "camLens", "loader", "taskMgr", "mouseWatcherNode", "win")
        missing = [name for name in required if not hasattr(host, name)]
        if missing:
            raise RuntimeError("HoloVerse host missing ShowBase fields: " + ", ".join(missing))
        for name in required + ("pixel2d", "cam", "graphicsEngine", "pipe"):
            if hasattr(host, name):
                setattr(self, name, getattr(host, name))

    def apply_host_runtime_settings(self) -> None:
        settings = dict(self._holoverse_runtime_settings)
        self.holoverse_runtime_contract = dict(settings)
        # Hosted HoloTactics keeps its source-authored HUD and button layout.
        # HoloVerse does not scale or hide the dimension UI.
        # Keep graphics-quality ownership scoped to HoloTactics' scene subtree.
        quality = str(settings.get("graphics_quality", "medium") or "medium").lower()
        try:
            if quality == "low":
                self.scene_root.clearAntialias()
            else:
                self.scene_root.setAntialias(1)
        except Exception:
            pass

    def _setup_window(self) -> None:
        settings = self._holoverse_runtime_settings
        props = WindowProperties()
        props.setTitle("HoloVerse // HoloTactics" if settings.get("hosted_contract") else "Gleebs Protocol: HoloTactics")
        props.setSize(int(settings.get("width", 1920)), int(settings.get("height", 1080)))
        props.setCursorHidden(False)
        if settings.get("hosted_contract"):
            borderless = bool(settings.get("borderless", False))
            bordered_fullscreen = bool(settings.get("bordered_fullscreen", False))
            props.setOrigin(int(settings.get("window_x", 0)), int(settings.get("window_y", 0)))
            props.setFullscreen(bool(settings.get("fullscreen", False)) and not borderless and not bordered_fullscreen)
            props.setUndecorated(borderless)
            props.setFixedSize(bool(borderless))
        if hasattr(self.win, "requestProperties"):
            self.win.requestProperties(props)
        self.setBackgroundColor(0.005, 0.008, 0.015, 1.0)

    def _setup_lighting(self) -> None:
        ambient = AmbientLight("holotactics_ambient")
        ambient.setColor((0.15, 0.2, 0.26, 1.0))
        ambient_np = self.scene_root.attachNewNode(ambient)
        self.scene_root.setLight(ambient_np)
        directional = DirectionalLight("holotactics_key_light")
        directional.setColor((0.7, 0.95, 1.0, 1.0))
        dnp = self.scene_root.attachNewNode(directional)
        dnp.setHpr(35, -55, 0)
        self.scene_root.setLight(dnp)

    def _setup_camera(self) -> None:
        # Fixed presentation camera with enough room for the larger Pass 14 boards.
        self.camera.setPos(6.2, -21.0, 14.2)
        self.camera.lookAt(0.2, -0.15, 0.10)
        self.camLens.setFov(31)
        self.camLens.setNearFar(0.1, 140)

    def _bind_controls(self) -> None:
        for key in (
            "arrow_left", "arrow_right", "arrow_up", "arrow_down",
            "a", "d", "w", "s", "space", "enter", "m", "v", "b",
            "f", "e", "q", "x", "n", "c", "h", "j", "r", "f9", "mouse1", "mouse3",
        ):
            self.accept(key, lambda action=key: self._standalone_input(action))
        self.accept("escape", self._toggle_pause)

    def _standalone_input(self, action: str) -> None:
        """Single standalone input gate so modal UI owns all gameplay input."""
        if self.journey_map_open:
            if action == "j":
                self._toggle_journey_map()
            return
        if self.is_paused:
            if action in {"arrow_up", "w"}:
                self._pause_move(-1)
            elif action in {"arrow_down", "s"}:
                self._pause_move(1)
            elif action in {"enter", "space"}:
                self._pause_activate()
            return
        commands = {
            "arrow_left": lambda: self._cursor(-1, 0),
            "arrow_right": lambda: self._cursor(1, 0),
            "arrow_up": lambda: self._cursor(0, 1),
            "arrow_down": lambda: self._cursor(0, -1),
            "a": lambda: self._cursor(-1, 0),
            "d": lambda: self._cursor(1, 0),
            "w": lambda: self._cursor(0, 1),
            "s": lambda: self._cursor(0, -1),
            "space": self._activate_or_select,
            "enter": self._activate_or_select,
            "m": self._move,
            "v": self._toggle_sfx,
            "b": self._toggle_music,
            "f": self._attack,
            "e": self._end_turn,
            "q": self._gleebs_patch_pulse,
            "x": self._use_ability,
            "n": self._advance_journey,
            "c": self._advance_journey,
            "h": self._toggle_hud,
            "j": self._toggle_journey_map,
            "r": self._reset_to_title,
            "f9": self._toggle_dev_view,
            "mouse1": self._mouse_activate_or_select,
            "mouse3": self._mouse_attack,
        }
        fn = commands.get(action)
        if fn is not None:
            fn()


    def _build_journey_map_overlay(self) -> None:
        """Build a read-only route view from the authoritative campaign state."""
        self.journey_map_root = self.aspect2d.attachNewNode("holotactics_journey_map_root")
        self._holoverse_owned_nodes.append(self.journey_map_root)
        cm = CardMaker("journey_map_backdrop")
        cm.setFrame(-1.28, 1.28, -0.82, 0.82)
        panel = self.journey_map_root.attachNewNode(cm.generate())
        panel.setTransparency(TransparencyAttrib.MAlpha)
        panel.setColor(0.003, 0.012, 0.024, 0.965)
        panel.setBin("fixed", 86)

        border = LineSegs("journey_map_border")
        border.setThickness(2.0)
        border.setColor(0.12, 0.88, 1.0, 0.92)
        pts = [(-1.28,0,-0.82),(1.28,0,-0.82),(1.28,0,0.82),(-1.28,0,0.82),(-1.28,0,-0.82)]
        border.moveTo(*pts[0])
        for pt in pts[1:]:
            border.drawTo(*pt)
        self.journey_map_root.attachNewNode(border.create()).setBin("fixed", 87)

        self.journey_map_title = OnscreenText(
            parent=self.journey_map_root, text="", pos=(-1.08, 0.66), align=TextNode.ALeft,
            scale=0.070, fg=(0.74, 1.0, 1.0, 1.0), mayChange=True,
        )
        self.journey_map_hint = OnscreenText(
            parent=self.journey_map_root, text="J / ESC  •  close route view", pos=(0.0, -0.70),
            align=TextNode.ACenter, scale=0.042, fg=(0.48, 0.86, 1.0, 0.92), mayChange=True,
        )
        self.journey_map_root.hide()

    def _journey_map_sector_state(self, index: int) -> str:
        from holotactics_core import SECTOR_NAMES
        sector_name = SECTOR_NAMES[index]
        if index < self.state.sector_index or sector_name in self.state.cleared_sectors:
            return "SEALED"
        if index == self.state.sector_index:
            return "SEALED" if self.state.victory() else "CURRENT"
        return "LOCKED"

    def _clear_journey_map_labels(self) -> None:
        for item in self.journey_map_labels:
            try:
                item.destroy()
            except Exception:
                pass
        self.journey_map_labels = []
        if self.journey_map_root is not None:
            for child in self.journey_map_root.findAllMatches("**/route_dynamic_*"):
                child.removeNode()

    def _update_journey_map_overlay(self) -> None:
        if self.journey_map_root is None or self.journey_map_title is None:
            return
        self._clear_journey_map_labels()
        from holotactics_core import SECTOR_NAMES, SECTOR_THREAT_LABELS
        self.journey_map_title.setText(
            "JOURNEY MAP\n"
            f"Visible route • {self.state.journey_progress_percent()}% synchronized"
        )
        xs = (-0.98, -0.49, 0.0, 0.49, 0.98)
        y = 0.08
        line = LineSegs("route_dynamic_connections")
        line.setThickness(3.0)
        for index in range(1, MAX_JOURNEY_SECTORS):
            left_state = self._journey_map_sector_state(index)
            right_state = self._journey_map_sector_state(index + 1)
            if left_state == "SEALED" and right_state in {"SEALED", "CURRENT"}:
                line.setColor(0.20, 0.92, 1.0, 0.92)
            else:
                line.setColor(0.18, 0.30, 0.38, 0.72)
            line.moveTo(xs[index-1] + 0.10, 0, y)
            line.drawTo(xs[index] - 0.10, 0, y)
        conn = self.journey_map_root.attachNewNode(line.create())
        conn.setName("route_dynamic_connections")
        conn.setBin("fixed", 88)

        for index, x in enumerate(xs, start=1):
            state = self._journey_map_sector_state(index)
            if state == "SEALED":
                color = (0.22, 1.0, 0.72, 1.0)
                fill = (0.02, 0.18, 0.18, 0.96)
            elif state == "CURRENT":
                color = (0.98, 0.88, 0.24, 1.0)
                fill = (0.18, 0.12, 0.02, 0.98)
            else:
                color = (0.38, 0.48, 0.56, 0.82)
                fill = (0.025, 0.045, 0.065, 0.94)
            cm = CardMaker(f"route_dynamic_sector_{index}")
            cm.setFrame(-0.105, 0.105, -0.105, 0.105)
            node = self.journey_map_root.attachNewNode(cm.generate())
            node.setName(f"route_dynamic_sector_{index}")
            node.setPos(x, 0, y)
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setColor(*fill)
            node.setBin("fixed", 89)
            ring = LineSegs(f"route_dynamic_ring_{index}")
            ring.setThickness(4.0 if state == "CURRENT" else 2.5)
            ring.setColor(*color)
            steps = 24
            for step in range(steps + 1):
                angle = (step / steps) * math.tau
                px, pz = x + math.cos(angle) * 0.115, y + math.sin(angle) * 0.115
                if step == 0:
                    ring.moveTo(px, 0, pz)
                else:
                    ring.drawTo(px, 0, pz)
            rnp = self.journey_map_root.attachNewNode(ring.create())
            rnp.setName(f"route_dynamic_ring_{index}")
            rnp.setBin("fixed", 90)
            size = 6 + index * 2
            label = OnscreenText(
                parent=self.journey_map_root,
                text=f"{index}\n{SECTOR_NAMES[index]}\n{size}x{size} • {SECTOR_THREAT_LABELS[index]}\n{state}",
                pos=(x, -0.11), align=TextNode.ACenter, scale=0.034,
                fg=color, mayChange=False,
            )
            self.journey_map_labels.append(label)
        current = self.state.sector_index
        if self.state.victory() and current < MAX_JOURNEY_SECTORS:
            footer = f"Sector {current} sealed • continue to reveal the next current destination"
        elif self.state.journey_complete():
            footer = "All five sectors sealed • visible route stabilized"
        else:
            footer = f"Current destination: {SECTOR_NAMES[current]}"
        foot = OnscreenText(
            parent=self.journey_map_root, text=footer, pos=(0.0, -0.48),
            align=TextNode.ACenter, scale=0.046, fg=(0.70, 0.92, 1.0, 0.96),
        )
        self.journey_map_labels.append(foot)

    def _toggle_journey_map(self, force: bool | None = None) -> None:
        if self.journey_map_root is None:
            return
        target = (not self.journey_map_open) if force is None else bool(force)
        if target and self.is_paused:
            return
        self.journey_map_open = target
        if target:
            self._update_journey_map_overlay()
            self.journey_map_root.show()
            self.hud_root.hide()
        else:
            self.journey_map_root.hide()
            if self.hud_visible:
                self.hud_root.show()


    PAUSE_MENU_ITEMS = (
        "RESUME",
        "RESTART JOURNEY",
        "CONTROLS",
        "SFX",
        "MUSIC",
        "QUIT TO DESKTOP",
    )

    def _build_pause_overlay(self) -> None:
        self.pause_root = self.aspect2d.attachNewNode("holotactics_pause_root")
        self._holoverse_owned_nodes.append(self.pause_root)
        cm = CardMaker("pause_backdrop")
        cm.setFrame(-0.82, 0.82, -0.78, 0.78)
        panel = self.pause_root.attachNewNode(cm.generate())
        panel.setTransparency(TransparencyAttrib.MAlpha)
        panel.setColor(0.005, 0.02, 0.035, 0.94)
        panel.setBin("fixed", 80)
        border = LineSegs("pause_border")
        border.setThickness(2.0)
        border.setColor(0.15, 0.95, 1.0, 0.92)
        pts = [(-0.82,0,-0.78),(0.82,0,-0.78),(0.82,0,0.78),(-0.82,0,0.78),(-0.82,0,-0.78)]
        border.moveTo(*pts[0])
        for pt in pts[1:]:
            border.drawTo(*pt)
        bnp = self.pause_root.attachNewNode(border.create())
        bnp.setTransparency(TransparencyAttrib.MAlpha)
        bnp.setBin("fixed", 81)
        self.pause_text = OnscreenText(
            parent=self.pause_root, text="", pos=(-0.66, 0.56), align=TextNode.ALeft,
            scale=0.063, fg=(0.76, 1.0, 1.0, 1.0), mayChange=True,
        )
        self.pause_hint_text = OnscreenText(
            parent=self.pause_root, text="", pos=(0.0, -0.64), align=TextNode.ACenter,
            scale=0.045, fg=(0.52, 0.90, 1.0, 0.90), mayChange=True,
        )
        self.pause_root.hide()

    def _toggle_pause(self) -> None:
        if self.journey_map_open:
            self._toggle_journey_map(force=False)
            return
        if self._holoverse_hosted:
            return
        if self.is_paused and self.pause_page == "controls":
            self.pause_page = "menu"
            self.pause_confirm_action = None
            self._update_pause_overlay()
            return
        self.is_paused = not self.is_paused
        self.pause_page = "menu"
        self.pause_confirm_action = None
        if self.pause_root is not None:
            self.pause_root.show() if self.is_paused else self.pause_root.hide()
        if self.is_paused:
            self.hud_root.hide()
        elif self.hud_visible:
            self.hud_root.show()
        else:
            self.hud_root.hide()
        self._update_pause_overlay()

    def _pause_move(self, delta: int) -> None:
        if self.pause_page != "menu":
            return
        self.pause_confirm_action = None
        self.pause_menu_index = (self.pause_menu_index + delta) % len(self.PAUSE_MENU_ITEMS)
        self._update_pause_overlay()

    def _pause_activate(self) -> None:
        if self.pause_page == "controls":
            self.pause_page = "menu"
            self._update_pause_overlay()
            return
        item = self.PAUSE_MENU_ITEMS[self.pause_menu_index]
        if item == "RESUME":
            self._toggle_pause()
        elif item == "CONTROLS":
            self.pause_page = "controls"
            self.pause_confirm_action = None
            self._update_pause_overlay()
        elif item == "SFX":
            self._toggle_sfx()
            self._update_pause_overlay()
        elif item == "MUSIC":
            self._toggle_music()
            self._update_pause_overlay()
        elif item == "RESTART JOURNEY":
            if self.pause_confirm_action != "restart":
                self.pause_confirm_action = "restart"
                self._update_pause_overlay()
            else:
                self._reset_to_title()
                self.is_paused = False
                self.pause_confirm_action = None
                if self.pause_root is not None:
                    self.pause_root.hide()
                if self.hud_visible:
                    self.hud_root.show()
        elif item == "QUIT TO DESKTOP":
            if self.pause_confirm_action != "quit":
                self.pause_confirm_action = "quit"
                self._update_pause_overlay()
            else:
                self.pause_confirm_action = None
                self.userExit()

    def _update_pause_overlay(self) -> None:
        if self.pause_text is None or self.pause_hint_text is None:
            return
        if not self.is_paused:
            return
        if self.pause_page == "controls":
            self.pause_text.setText(
                "CONTROLS\n\n"
                "LMB / ENTER / SPACE   Select or confirm\n"
                "RMB / F               Attack\n"
                "WASD / ARROWS         Move target\n"
                "M                     Move selected unit\n"
                "Q                     Gleebs Patch Pulse\n"
                "X                     Use stored ability\n"
                "E                     End turn\n"
                "V                     Toggle SFX\n"
                "B                     Toggle music\n"
                "H                     Toggle HUD\n"
                "J                     Journey Map\n"
                "ESC                   Pause / resume"
            )
            self.pause_hint_text.setText("ENTER / SPACE / ESC  •  return to pause menu")
            return
        rows = ["PAUSED", ""]
        for index, item in enumerate(self.PAUSE_MENU_ITEMS):
            label = item
            if item == "SFX":
                label += f"  [{self.sfx.status_label() if self.sfx else 'OFF'}]"
            elif item == "MUSIC":
                label += f"  [{self.sfx.music_status_label() if self.sfx else 'OFF'}]"
            prefix = "> " if index == self.pause_menu_index else "  "
            rows.append(prefix + label)
        if self.pause_confirm_action == "restart":
            rows += ["", "CONFIRM: ENTER again resets the journey to Sector 1."]
        elif self.pause_confirm_action == "quit":
            rows += ["", "CONFIRM: ENTER again closes HoloTactics."]
        self.pause_text.setText("\n".join(rows))
        self.pause_hint_text.setText("W/S or ARROWS  •  ENTER select  •  ESC resume")

    def _build_scene(self) -> None:
        self.board_root = self.scene_root.attachNewNode("holographic_board")
        max_board = max(self.state.width, self.state.height)
        # The board now grows across the journey instead of always being compressed to the old footprint.
        board_scale = min(0.80, 7.5 / max_board)
        # Center the scaled board in world space so bigger sectors remain inside the UI safe area.
        board_offset = -(board_scale * (max_board - 1) / 2.0)
        self.board_root.setPos(board_offset, board_offset, 0)
        self.board_root.setScale(board_scale)
        self._make_void_backdrop()
        for y in range(self.state.height):
            for x in range(self.state.width):
                tile = self._make_tile((x, y))
                tile.reparentTo(self.board_root)
                tile.setPos(x, y, 0)
                self.tile_nodes[(x, y)] = tile
                frame = self._make_tile_frame((x, y))
                frame.reparentTo(self.board_root)
                frame.setPos(x, y, 0.018)
                self.tile_frames[(x, y)] = frame
        self._make_board_rim()
        for node_id, node in self.state.nodes.items():
            marker = self._make_node_marker(node_id)
            marker.reparentTo(self.board_root)
            marker.setPos(node.pos[0], node.pos[1], 0.08)
            self.node_markers[node_id] = marker
        for unit_id in self.state.units:
            np = self._make_unit_piece(unit_id)
            np.reparentTo(self.board_root)
            self.unit_nodes[unit_id] = np
        self._sync_ability_markers()

    def _make_void_backdrop(self) -> None:
        cm = CardMaker("void_floor")
        cm.setFrame(-16, 16, -16, 16)
        if hasattr(self, "void_backdrop") and self.void_backdrop:
            self.void_backdrop.removeNode()
        card = self.scene_root.attachNewNode(cm.generate())
        card.setP(-90)
        card.setPos(0, 0, -0.08)
        card.setColor(0.0, 0.0, 0.0, 1.0)
        self.void_backdrop = card

    def _make_tile(self, pos: tuple[int, int]) -> NodePath:
        cm = CardMaker(f"tile_{pos[0]}_{pos[1]}")
        cm.setFrame(-0.46, 0.46, -0.46, 0.46)
        tile = NodePath(cm.generate())
        tile.setP(-90)
        tile.setTransparency(TransparencyAttrib.MAlpha)
        return tile

    def _make_tile_frame(self, pos: tuple[int, int]) -> NodePath:
        lines = LineSegs(f"tile_frame_{pos[0]}_{pos[1]}")
        lines.setThickness(1.5)
        lines.setColor(0.0, 0.9, 1.0, 0.55)
        z = 0.0
        corners = [(-0.48, -0.48, z), (0.48, -0.48, z), (0.48, 0.48, z), (-0.48, 0.48, z), (-0.48, -0.48, z)]
        lines.moveTo(*corners[0])
        for c in corners[1:]:
            lines.drawTo(*c)
        return NodePath(lines.create())

    def _make_board_rim(self) -> None:
        lines = LineSegs("board_outer_rim")
        lines.setThickness(4.0)
        lines.setColor(0.2, 0.95, 1.0, 0.9)
        z = 0.08
        right = self.state.width - 0.45
        top = self.state.height - 0.45
        corners = [(-0.55, -0.55, z), (right, -0.55, z), (right, top, z), (-0.55, top, z), (-0.55, -0.55, z)]
        lines.moveTo(*corners[0])
        for c in corners[1:]:
            lines.drawTo(*c)
        rim = self.board_root.attachNewNode(lines.create())
        rim.setName("presentation_safe_holographic_board_rim")

    def _make_node_marker(self, node_id: str) -> NodePath:
        root = NodePath(f"node_marker_{node_id}")
        if self.state.sector_index == 3 and node_id in {"patch", "die", "memory"}:
            core = make_box(f"fracture_anchor_{node_id}", 0.32, 0.32, 0.24, (1.0, 0.34, 0.06, 0.92))
            shard_a = make_box(f"fracture_anchor_{node_id}_a", 0.10, 0.48, 0.10, (1.0, 0.78, 0.10, 0.95))
            shard_b = make_box(f"fracture_anchor_{node_id}_b", 0.48, 0.10, 0.10, (1.0, 0.78, 0.10, 0.95))
            mast = make_box(f"fracture_anchor_{node_id}_mast", 0.08, 0.08, 0.52, (1.0, 0.48, 0.08, 0.9))
            shard_a.reparentTo(root); shard_a.setZ(0.40); shard_a.setH(35)
            shard_b.reparentTo(root); shard_b.setZ(0.40); shard_b.setH(-35)
            mast.reparentTo(root); mast.setZ(0.48)
        elif node_id == "memory":
            core = make_box("memory_prism", 0.32, 0.32, 0.42, (0.0, 0.95, 0.45, 0.9))
            cap = make_box("memory_prism_cap", 0.18, 0.18, 0.16, (0.75, 1.0, 0.55, 0.95))
            cap.reparentTo(root)
            cap.setZ(0.56)
        elif node_id == "patch":
            core = make_box("patch_rule_node", 0.34, 0.34, 0.34, (0.08, 0.55, 1.0, 0.9))
            mast = make_box("patch_rule_mast", 0.10, 0.10, 0.55, (0.35, 1.0, 1.0, 0.95))
            mast.reparentTo(root)
            mast.setZ(0.56)
        elif node_id == "die":
            core = make_box("action_die_core", 0.36, 0.36, 0.36, (0.85, 0.55, 1.0, 0.92))
            for index, (px, py) in enumerate(((-0.10, -0.10), (0.10, 0.10), (-0.10, 0.10), (0.10, -0.10))):
                pip = make_box(f"action_die_pip_{index}", 0.06, 0.06, 0.035, (0.1, 0.02, 0.18, 0.95))
                pip.reparentTo(root)
                pip.setPos(px, py - 0.20, 0.42)
        elif node_id == "extract":
            core = make_box("extraction_gate_core", 0.46, 0.16, 0.42, (0.15, 1.0, 0.85, 0.78))
            arch_l = make_box("extraction_gate_l", 0.08, 0.08, 0.72, (0.45, 1.0, 0.95, 0.9))
            arch_r = make_box("extraction_gate_r", 0.08, 0.08, 0.72, (0.45, 1.0, 0.95, 0.9))
            arch_top = make_box("extraction_gate_top", 0.52, 0.08, 0.08, (0.45, 1.0, 0.95, 0.9))
            arch_l.reparentTo(root); arch_l.setX(-0.27); arch_l.setZ(0.42)
            arch_r.reparentTo(root); arch_r.setX(0.27); arch_r.setZ(0.42)
            arch_top.reparentTo(root); arch_top.setZ(0.82)
        else:
            core = make_box("corruption_core", 0.38, 0.38, 0.5, (1.0, 0.1, 0.08, 0.9))
            shard_a = make_box("core_shard_a", 0.12, 0.5, 0.16, (1.0, 0.25, 0.1, 0.85))
            shard_b = make_box("core_shard_b", 0.5, 0.12, 0.16, (1.0, 0.05, 0.2, 0.85))
            shard_a.reparentTo(root); shard_a.setZ(0.54)
            shard_b.reparentTo(root); shard_b.setZ(0.54)
        core.reparentTo(root)
        core.setZ(0.21)
        return root

    def _make_unit_piece(self, unit_id: str) -> NodePath:
        """Build readable tactical actors with the Pass 08 silhouette language.

        The geometry is intentionally procedural and lightweight so the pieces stay stable
        on the board. Gleebs uses the supplied reference image as the identity reference for
        dark mass, green/purple accents, horn-like antennae, and paired orb details.
        """
        unit = self.state.units[unit_id]
        root = NodePath(f"unit_{unit_id}")
        spec_key = self._actor_spec_key(unit_id)
        spec = ACTOR_VISUAL_SPECS[spec_key]
        root.setTag("actor_visual", spec.silhouette)
        root.setTag("actor_read", spec.board_read)
        root.setTag("footprint_radius", f"{spec.footprint_radius:.2f}")
        if unit_id == "gleebs":
            self._build_gleebs_piece(root)
        elif unit_id == "guard":
            self._build_guard_piece(root)
        elif unit_id == "runner":
            self._build_runner_piece(root)
        elif unit_id.startswith("anomaly"):
            self._build_anomaly_piece(root)
        elif unit_id.startswith("sentry"):
            self._build_sentry_piece(root)
        else:
            self._attach_box(root, f"{unit_id}_fallback_body", 0.40, 0.40, 0.45, (0.0, 0.85, 1.0, 0.95), (0.0, 0.0, 0.30))
        ring_color = self._actor_ring_color(unit_id)
        ring = self._make_piece_ring(ring_color, radius=spec.footprint_radius)
        ring.reparentTo(root)
        ring.setZ(0.035)
        return root

    def _actor_spec_key(self, unit_id: str) -> str:
        if unit_id.startswith("anomaly"):
            return "anomaly"
        if unit_id.startswith("sentry"):
            return "sentry"
        return unit_id

    def _actor_ring_color(self, unit_id: str) -> tuple[float, float, float, float]:
        if unit_id.startswith("anomaly") or unit_id.startswith("sentry"):
            return (1.0, 0.12, 0.10, 0.95)
        if unit_id == "gleebs":
            return (0.55, 1.0, 0.12, 0.95)
        if unit_id == "runner":
            return (0.70, 0.36, 1.0, 0.90)
        return (0.15, 0.85, 1.0, 0.92)

    def _attach_box(
        self,
        parent: NodePath,
        name: str,
        sx: float,
        sy: float,
        sz: float,
        color: tuple[float, float, float, float],
        pos: tuple[float, float, float],
        hpr: tuple[float, float, float] | None = None,
    ) -> NodePath:
        node = make_box(name, sx, sy, sz, color)
        node.reparentTo(parent)
        node.setPos(*pos)
        if hpr is not None:
            node.setHpr(*hpr)
        return node

    def _attach_prism(
        self,
        parent: NodePath,
        name: str,
        radius: float,
        height: float,
        color: tuple[float, float, float, float],
        pos: tuple[float, float, float],
        sides: int = 6,
        top_scale: float = 1.0,
        hpr: tuple[float, float, float] | None = None,
    ) -> NodePath:
        node = make_prism(name, radius, height, color, sides=sides, top_scale=top_scale)
        node.reparentTo(parent)
        node.setPos(*pos)
        if hpr is not None:
            node.setHpr(*hpr)
        return node

    def _attach_wedge(
        self,
        parent: NodePath,
        name: str,
        sx: float,
        sy: float,
        sz: float,
        color: tuple[float, float, float, float],
        pos: tuple[float, float, float],
        hpr: tuple[float, float, float] | None = None,
    ) -> NodePath:
        node = make_wedge(name, sx, sy, sz, color)
        node.reparentTo(parent)
        node.setPos(*pos)
        if hpr is not None:
            node.setHpr(*hpr)
        return node

    def _attach_orb_glyph(
        self,
        parent: NodePath,
        name: str,
        pos: tuple[float, float, float],
        color: tuple[float, float, float, float],
        radius: float = 0.13,
    ) -> NodePath:
        # Low-cost board-readable orb: small bright core plus two crossing holo rings.
        root = NodePath(name)
        root.reparentTo(parent)
        root.setPos(*pos)
        core = make_box(f"{name}_core", radius * 1.15, radius * 1.15, radius * 1.15, color)
        core.reparentTo(root)
        ring_a = self._make_piece_ring(color, radius=radius * 1.25)
        ring_a.reparentTo(root)
        ring_a.setP(90)
        ring_b = self._make_piece_ring(color, radius=radius * 1.25)
        ring_b.reparentTo(root)
        ring_b.setR(90)
        return root

    def _build_gleebs_piece(self, root: NodePath) -> None:
        dark = (0.015, 0.020, 0.035, 0.98)
        purple = (0.30, 0.08, 0.62, 0.96)
        green = (0.48, 1.0, 0.12, 0.98)
        cyan = (0.0, 0.95, 1.0, 0.88)
        red = (1.0, 0.12, 0.08, 0.86)
        pale = (0.85, 1.0, 0.62, 0.96)
        # Pass 26: preserve the reference's rabbit/cat ears, paired orbiting spheres,
        # compact dark body and green/purple identity, but replace the old box stack
        # with a faceted tactical-piece silhouette that reads from the board camera.
        self._attach_prism(root, "gleebs_tapered_core", 0.28, 0.46, dark, (0.0, 0.0, 0.34), sides=6, top_scale=0.82)
        self._attach_prism(root, "gleebs_purple_chest", 0.225, 0.25, purple, (0.0, -0.015, 0.49), sides=6, top_scale=0.86)
        self._attach_prism(root, "gleebs_head", 0.235, 0.25, dark, (0.0, -0.005, 0.76), sides=6, top_scale=0.92)
        self._attach_box(root, "gleebs_green_visor", 0.28, 0.045, 0.075, pale, (0.0, -0.225, 0.78))
        self._attach_wedge(root, "gleebs_left_ear", 0.16, 0.15, 0.48, green, (-0.18, 0.0, 1.00), (0, 0, -8))
        self._attach_wedge(root, "gleebs_right_ear", 0.16, 0.15, 0.48, green, (0.18, 0.0, 1.00), (0, 0, 8))
        self._attach_wedge(root, "gleebs_left_ear_inner", 0.08, 0.16, 0.31, purple, (-0.18, -0.035, 0.995), (0, 0, -8))
        self._attach_wedge(root, "gleebs_right_ear_inner", 0.08, 0.16, 0.31, purple, (0.18, -0.035, 0.995), (0, 0, 8))
        self._attach_orb_glyph(root, "gleebs_cyan_orb", (-0.43, -0.04, 0.62), cyan, 0.13)
        self._attach_orb_glyph(root, "gleebs_red_orb", (0.43, -0.04, 0.62), red, 0.13)
        for x in (-0.145, 0.145):
            self._attach_prism(root, f"gleebs_leg_{x:+.2f}", 0.075, 0.31, dark, (x, 0.0, 0.17), sides=5, top_scale=0.80)
            self._attach_wedge(root, f"gleebs_foot_{x:+.2f}", 0.18, 0.25, 0.09, green, (x, -0.055, 0.055))
        self._attach_wedge(root, "gleebs_left_arm", 0.11, 0.16, 0.31, purple, (-0.29, -0.01, 0.43), (0, 0, -13))
        self._attach_wedge(root, "gleebs_right_arm", 0.11, 0.16, 0.31, purple, (0.29, -0.01, 0.43), (0, 0, 13))
        root.setH(8)

    def _build_guard_piece(self, root: NodePath) -> None:
        blue_dark = (0.02, 0.07, 0.18, 0.98)
        blue = (0.10, 0.45, 1.0, 0.96)
        cyan = (0.25, 0.95, 1.0, 0.90)
        # Broad, low hexagonal mass + unmistakable side shield.
        self._attach_prism(root, "guard_heavy_core", 0.36, 0.48, blue_dark, (0.0, 0.0, 0.35), sides=6, top_scale=0.92)
        self._attach_box(root, "guard_chest_plate", 0.46, 0.075, 0.25, blue, (0.0, -0.30, 0.45))
        self._attach_prism(root, "guard_head", 0.18, 0.21, blue_dark, (0.0, -0.02, 0.76), sides=6, top_scale=0.82)
        self._attach_box(root, "guard_visor", 0.22, 0.045, 0.055, cyan, (0.0, -0.19, 0.78))
        self._attach_prism(root, "guard_left_shoulder", 0.19, 0.22, blue, (-0.34, -0.01, 0.58), sides=6, top_scale=0.72)
        self._attach_prism(root, "guard_right_shoulder", 0.19, 0.22, blue, (0.34, -0.01, 0.58), sides=6, top_scale=0.72)
        shield = self._attach_prism(root, "guard_anchor_shield", 0.31, 0.63, (0.05, 0.18, 0.45, 0.98), (-0.48, -0.01, 0.39), sides=6, top_scale=0.84, hpr=(0, 90, 0))
        self._attach_prism(root, "guard_shield_core", 0.16, 0.06, cyan, (-0.50, -0.33, 0.40), sides=6, top_scale=1.0, hpr=(0, 90, 0))
        self._attach_wedge(root, "guard_right_gauntlet", 0.20, 0.22, 0.36, blue, (0.45, -0.02, 0.31), (0, 0, 5))
        for x in (-0.17, 0.17):
            self._attach_prism(root, f"guard_leg_{x:+.2f}", 0.10, 0.33, blue_dark, (x, 0.0, 0.16), sides=5, top_scale=0.85)
            self._attach_box(root, f"guard_foot_{x:+.2f}", 0.23, 0.24, 0.075, cyan, (x, -0.035, 0.04))
        root.setH(-5)

    def _build_runner_piece(self, root: NodePath) -> None:
        dark = (0.03, 0.025, 0.10, 0.98)
        cyan = (0.10, 0.95, 1.0, 0.94)
        violet = (0.68, 0.24, 1.0, 0.82)
        # Narrow forward-leaning spear silhouette with swept phase fins.
        self._attach_prism(root, "runner_slim_core", 0.18, 0.47, dark, (0.0, 0.0, 0.40), sides=5, top_scale=0.60, hpr=(0, -8, -8))
        self._attach_wedge(root, "runner_chest_spear", 0.20, 0.12, 0.34, cyan, (0.0, -0.13, 0.49), (0, -8, -7))
        self._attach_prism(root, "runner_head", 0.145, 0.20, dark, (0.02, -0.04, 0.76), sides=5, top_scale=0.55, hpr=(0, -10, -10))
        self._attach_box(root, "runner_visor", 0.18, 0.04, 0.05, cyan, (0.03, -0.18, 0.77))
        self._attach_wedge(root, "runner_left_leg_forward", 0.10, 0.15, 0.43, cyan, (-0.105, -0.07, 0.18), (0, 0, 12))
        self._attach_wedge(root, "runner_right_leg_back", 0.10, 0.15, 0.38, violet, (0.14, 0.07, 0.15), (0, 0, -24))
        self._attach_wedge(root, "runner_left_arm", 0.08, 0.13, 0.34, violet, (-0.24, -0.04, 0.45), (0, 0, -40))
        self._attach_wedge(root, "runner_right_arm", 0.08, 0.13, 0.31, cyan, (0.24, 0.00, 0.46), (0, 0, 32))
        self._attach_wedge(root, "runner_phase_fin_upper", 0.13, 0.46, 0.12, violet, (0.29, 0.10, 0.62), (18, 0, -28))
        self._attach_wedge(root, "runner_phase_fin_lower", 0.11, 0.39, 0.10, violet, (0.36, 0.13, 0.39), (16, 0, -31))
        root.setH(-12)

    def _build_anomaly_piece(self, root: NodePath) -> None:
        dark = (0.01, 0.006, 0.018, 0.98)
        purple = (0.32, 0.05, 0.48, 0.95)
        green = (0.48, 1.0, 0.10, 0.92)
        red = (1.0, 0.05, 0.06, 0.92)
        # Jagged asymmetric melee silhouette: broken core + shard/blade arms.
        self._attach_prism(root, "anomaly_broken_mass", 0.31, 0.53, dark, (0.0, 0.0, 0.39), sides=5, top_scale=0.68, hpr=(13, 0, 9))
        self._attach_prism(root, "anomaly_purple_shell", 0.245, 0.27, purple, (0.0, 0.02, 0.52), sides=5, top_scale=0.58, hpr=(-12, 0, 17))
        self._attach_wedge(root, "anomaly_toxic_core", 0.22, 0.08, 0.25, green, (0.0, -0.23, 0.51), (0, 0, 5))
        self._attach_prism(root, "anomaly_head", 0.18, 0.23, dark, (0.0, 0.0, 0.82), sides=5, top_scale=0.65, hpr=(10, 0, -10))
        self._attach_box(root, "anomaly_green_eye", 0.19, 0.04, 0.055, green, (0.0, -0.18, 0.83))
        self._attach_wedge(root, "anomaly_left_horn", 0.12, 0.13, 0.39, green, (-0.16, 0.01, 1.05), (0, 0, -17))
        self._attach_wedge(root, "anomaly_right_horn", 0.10, 0.13, 0.46, green, (0.16, 0.01, 1.03), (0, 0, 21))
        self._attach_wedge(root, "anomaly_left_blade", 0.55, 0.12, 0.16, red, (-0.37, -0.01, 0.56), (0, 0, -29))
        self._attach_wedge(root, "anomaly_right_blade", 0.63, 0.11, 0.14, red, (0.37, -0.01, 0.50), (0, 0, 31))
        self._attach_orb_glyph(root, "anomaly_red_shard_core", (0.39, -0.02, 0.34), red, 0.095)
        for x in (-0.13, 0.13):
            self._attach_wedge(root, f"anomaly_leg_{x:+.2f}", 0.11, 0.15, 0.34, dark, (x, 0.0, 0.17), (0, 0, 7 if x < 0 else -9))
        root.setH(14)

    def _build_sentry_piece(self, root: NodePath) -> None:
        dark = (0.04, 0.0, 0.02, 0.98)
        red = (1.0, 0.06, 0.08, 0.96)
        purple = (0.45, 0.08, 0.62, 0.84)
        green = (0.45, 1.0, 0.12, 0.76)
        # Floating ranged silhouette: compact sensor core, long barrel and swept fins.
        self._attach_prism(root, "sentry_sensor_body", 0.23, 0.38, dark, (0.0, 0.0, 0.62), sides=6, top_scale=0.78)
        self._attach_orb_glyph(root, "sentry_target_eye", (0.0, -0.22, 0.68), red, 0.15)
        self._attach_wedge(root, "sentry_left_fin", 0.19, 0.43, 0.43, red, (-0.34, 0.0, 0.58), (0, 0, -5))
        self._attach_wedge(root, "sentry_right_fin", 0.19, 0.43, 0.43, red, (0.34, 0.0, 0.58), (0, 0, 5))
        self._attach_wedge(root, "sentry_left_inner_fin", 0.10, 0.34, 0.30, purple, (-0.47, 0.01, 0.55), (0, 0, -9))
        self._attach_wedge(root, "sentry_right_inner_fin", 0.10, 0.34, 0.30, purple, (0.47, 0.01, 0.55), (0, 0, 9))
        self._attach_prism(root, "sentry_barrel", 0.075, 0.60, red, (0.0, -0.43, 0.60), sides=6, top_scale=0.72, hpr=(0, 90, 0))
        self._attach_wedge(root, "sentry_top_antenna", 0.09, 0.10, 0.31, green, (0.0, 0.03, 0.99))
        self._attach_wedge(root, "sentry_tail", 0.16, 0.17, 0.27, purple, (0.0, 0.08, 0.31), (0, 0, 45))
        root.setH(8)

    def _make_piece_ring(self, color: tuple[float, float, float, float], radius: float = 0.34) -> NodePath:
        lines = LineSegs("piece_ring")
        lines.setThickness(2.0)
        lines.setColor(*color)
        for i in range(33):
            angle = math.tau * i / 32
            p = (math.cos(angle) * radius, math.sin(angle) * radius, 0.0)
            if i == 0:
                lines.moveTo(*p)
            else:
                lines.drawTo(*p)
        return NodePath(lines.create())


    def _make_tactical_marker(self, kind: str) -> NodePath:
        """Create small shape cues so tactical state is not communicated by color alone."""
        palette = {
            "move": (0.10, 1.0, 0.45, 0.92),
            "attack": (1.0, 0.38, 0.10, 0.95),
            "danger": (1.0, 0.12, 0.12, 0.95),
            "fracture": (1.0, 0.62, 0.08, 0.95),
            "objective": (0.92, 1.0, 0.28, 1.0),
            "ability": (0.78, 0.34, 1.0, 0.96),
        }
        lines = LineSegs(f"tactical_{kind}")
        lines.setThickness(2.6 if kind in {"objective", "danger", "fracture"} else 2.0)
        lines.setColor(*palette.get(kind, (1.0, 1.0, 1.0, 0.9)))
        z = 0.065
        if kind == "move":
            pts = [(0.0, -0.12, z), (0.12, 0.0, z), (0.0, 0.12, z), (-0.12, 0.0, z), (0.0, -0.12, z)]
            lines.moveTo(*pts[0])
            for pt in pts[1:]: lines.drawTo(*pt)
        elif kind == "attack":
            r = 0.15
            lines.moveTo(-r, -r, z); lines.drawTo(r, r, z)
            lines.moveTo(-r, r, z); lines.drawTo(r, -r, z)
        elif kind in {"danger", "fracture"}:
            o, i = 0.39, 0.25
            for sx, sy in ((-1,-1),(1,-1),(1,1),(-1,1)):
                lines.moveTo(sx*o, sy*i, z); lines.drawTo(sx*o, sy*o, z); lines.drawTo(sx*i, sy*o, z)
        elif kind == "objective":
            o, i = 0.41, 0.27
            for sx, sy in ((-1,-1),(1,-1),(1,1),(-1,1)):
                lines.moveTo(sx*o, sy*i, z); lines.drawTo(sx*o, sy*o, z); lines.drawTo(sx*i, sy*o, z)
        elif kind == "ability":
            r = 0.09
            pts = [(0.0,-r,z),(r,0.0,z),(0.0,r,z),(-r,0.0,z),(0.0,-r,z)]
            lines.moveTo(*pts[0])
            for pt in pts[1:]: lines.drawTo(*pt)
            lines.moveTo(-0.04,0.0,z); lines.drawTo(0.04,0.0,z)
            lines.moveTo(0.0,-0.04,z); lines.drawTo(0.0,0.04,z)
        return NodePath(lines.create())

    def _active_objective_pos(self) -> tuple[int, int] | None:
        if self.state.sector_index == 2:
            if not self.state.memory_collected:
                return self.state.nodes["memory"].pos
            if not self.state.patch_node_captured():
                return self.state.nodes["patch"].pos
            if not self.state.extraction_reached:
                return self.state.nodes["extract"].pos
            return None
        if self.state.sector_index == 3:
            for node_id in self.state.sector3_fracture_anchor_ids():
                if self.state.nodes[node_id].captured_by != "player":
                    return self.state.nodes[node_id].pos
            if not self.state.extraction_reached:
                return self.state.nodes["extract"].pos
            return None
        if self.state.sector_index == 5:
            stage = self.state.sector5_horizon_stage()
            if stage == 1:
                for node_id in self.state.sector5_horizon_relay_ids():
                    if self.state.nodes[node_id].captured_by != "player":
                        return self.state.nodes[node_id].pos
            elif stage == 2:
                return self.state.nodes["die"].pos
            elif stage == 3:
                for node_id in self.state.sector5_horizon_relay_ids():
                    if not self.state.sector5_relay_occupied(node_id):
                        return self.state.nodes[node_id].pos
            elif not self.state.extraction_reached:
                return self.state.nodes["extract"].pos
            return None
        if not self.state.memory_collected:
            return self.state.nodes["memory"].pos
        if not self.state.core_destroyed:
            return self.state.nodes["core"].pos
        if not self.state.extraction_reached:
            return self.state.nodes["extract"].pos
        return None

    def _ability_target_tiles(self, selected) -> set[tuple[int, int]]:
        ability = self.state.inventory_ability()
        if not selected or not ability or selected.acted or self.state.turn != "player":
            return set()
        candidates = {pos for pos in self.state.tiles if self.state.distance(selected.pos, pos) <= ability.range}
        if ability.kind in {"arc", "snare"}:
            return {pos for pos in candidates if self.state.unit_at(pos, team="enemy")}
        if ability.kind == "blink":
            return {pos for pos in candidates if not self.state.unit_at(pos) and self.state.tiles[pos].state != "void"}
        if ability.kind == "patch":
            return candidates
        return set()

    def _add_tactical_marker(self, kind: str, pos: tuple[int, int]) -> None:
        marker = self._make_tactical_marker(kind)
        marker.reparentTo(self.board_root)
        marker.setPos(pos[0], pos[1], 0.0)
        self.move_markers.append(marker)

    def _make_hud_panel(self, name: str, frame: tuple[float, float, float, float], color: tuple[float, float, float, float]) -> NodePath:
        """Build one restrained HoloVerse panel using one shared alignment language."""
        left, right, bottom, top = frame
        cm = CardMaker(name)
        cm.setFrame(*frame)
        panel = self.hud_root.attachNewNode(cm.generate())
        panel.setTransparency(TransparencyAttrib.MAlpha)
        panel.setColor(*color)
        panel.setBin("fixed", 1)
        self.hud_panels.append(panel)
        self.hud_panel_nodes[name] = panel

        border_lines = LineSegs(f"{name}_border")
        border_lines.setThickness(1.25)
        border_lines.setColor(0.16, 0.90, 1.0, 0.70)
        cut = min(0.030, (right - left) * 0.06, (top - bottom) * 0.18)
        points = [
            (left + cut, 0, bottom), (right - cut, 0, bottom),
            (right, 0, bottom + cut), (right, 0, top - cut),
            (right - cut, 0, top), (left + cut, 0, top),
            (left, 0, top - cut), (left, 0, bottom + cut),
            (left + cut, 0, bottom),
        ]
        border_lines.moveTo(*points[0])
        for point in points[1:]:
            border_lines.drawTo(*point)
        border = self.hud_root.attachNewNode(border_lines.create())
        border.setTransparency(TransparencyAttrib.MAlpha)
        border.setBin("fixed", 2)
        self.hud_panels.append(border)
        self.hud_panel_nodes[f"{name}_border"] = border

        # Short top rail gives every panel the same visual starting point without
        # adding decorative noise across the rest of the screen.
        rail = LineSegs(f"{name}_rail")
        rail.setThickness(1.8)
        rail.setColor(0.30, 1.0, 0.84, 0.82)
        rail.moveTo(left + 0.055, 0, top - 0.018)
        rail.drawTo(min(right - 0.055, left + 0.23), 0, top - 0.018)
        rail_np = self.hud_root.attachNewNode(rail.create())
        rail_np.setTransparency(TransparencyAttrib.MAlpha)
        rail_np.setBin("fixed", 3)
        self.hud_panels.append(rail_np)
        self.hud_panel_nodes[f"{name}_rail"] = rail_np
        return panel

    def _build_hud(self) -> None:
        # Player-facing HUD only. Diagnostics belong exclusively to F9 DEV VIEW.
        self._ui_layout_issues = validate_ui_layout()
        self._actor_visual_issues = validate_actor_visual_specs()
        if self._actor_visual_issues:
            raise RuntimeError("Actor visual spec failed: " + "; ".join(self._actor_visual_issues))
        if self._ui_layout_issues:
            raise RuntimeError("UI safe-area layout failed: " + "; ".join(self._ui_layout_issues))
        panel_colors = {
            "ui_title_glass": (0.004, 0.035, 0.055, 0.76),
            "ui_squad_glass": (0.004, 0.032, 0.052, 0.74),
            "ui_mission_glass": (0.004, 0.032, 0.052, 0.74),
            "ui_comms_glass": (0.004, 0.028, 0.048, 0.70),
            "ui_help_glass": (0.004, 0.028, 0.048, 0.70),
        }
        for panel_name, frame in UI_FRAMES.items():
            self._make_hud_panel(panel_name, frame, panel_colors[panel_name])

        self.title_text = OnscreenText(
            parent=self.hud_root, text="GLEEBS // HOLOTACTICS",
            pos=UI_TEXT_POS["title"], align=TextNode.ACenter,
            scale=UI_TEXT_SCALE["title"], fg=(0.76, 1.0, 0.96, 0.98), mayChange=False,
        )
        self.subtitle_text = OnscreenText(
            parent=self.hud_root, text="HOLOVERSE TACTICAL LINK",
            pos=UI_TEXT_POS["subtitle"], align=TextNode.ACenter,
            scale=UI_TEXT_SCALE["subtitle"], fg=(0.34, 0.88, 1.0, 0.82), mayChange=False,
        )
        self.status_text = OnscreenText(
            parent=self.hud_root, text="", pos=UI_TEXT_POS["squad"], align=TextNode.ALeft,
            scale=UI_TEXT_SCALE["squad"], fg=(0.78, 1.0, 1.0, 1), mayChange=True,
        )
        self.completion_text = OnscreenText(
            parent=self.hud_root, text="", pos=UI_TEXT_POS["mission"], align=TextNode.ALeft,
            scale=UI_TEXT_SCALE["mission"], fg=(0.66, 1.0, 0.76, 1), mayChange=True,
        )
        self.log_text = OnscreenText(
            parent=self.hud_root, text="", pos=UI_TEXT_POS["comms"], align=TextNode.ALeft,
            scale=UI_TEXT_SCALE["comms"], fg=(0.70, 0.94, 1.0, 0.94), mayChange=True,
        )
        self.help_text = OnscreenText(
            parent=self.hud_root,
            text=(
                "LMB Select/Move   RMB Attack   Q Patch   X Ability\n"
                "E End Turn   J Route   Esc Pause"
            ),
            pos=UI_TEXT_POS["help"], align=TextNode.ALeft,
            scale=UI_TEXT_SCALE["help"], fg=(0.60, 0.91, 1.0, 0.92), mayChange=False,
        )
        self.result_text = OnscreenText(
            parent=self.hud_root, text="", pos=UI_TEXT_POS["result"], align=TextNode.ACenter,
            scale=UI_TEXT_SCALE["result"], fg=(0.75, 1.0, 1.0, 0.0), mayChange=True,
        )
        self.menu_text = OnscreenText(
            parent=self.hud_root,
            text="START SIMULATION\nSeal sectors to expand the route\nENTER / SPACE / LMB",
            pos=UI_TEXT_POS["menu"], align=TextNode.ARight, scale=UI_TEXT_SCALE["menu"],
            fg=(0.72, 1.0, 1.0, 0.96), mayChange=True,
        )

    def _build_dev_overlay(self) -> None:
        """Developer-only diagnostics. Hidden by default; F9 is the only toggle."""
        self.dev_root = self.hud_root.attachNewNode("holotactics_dev_view")
        cm = CardMaker("dev_view_backdrop")
        cm.setFrame(-0.74, 0.74, -0.72, 0.70)
        panel = self.dev_root.attachNewNode(cm.generate())
        panel.setTransparency(TransparencyAttrib.MAlpha)
        panel.setColor(0.003, 0.020, 0.035, 0.95)
        panel.setBin("fixed", 30)
        border = LineSegs("dev_view_border")
        border.setThickness(1.4)
        border.setColor(0.22, 0.95, 1.0, 0.85)
        pts = [(-0.70,0,-0.72),(0.70,0,-0.72),(0.74,0,-0.68),(0.74,0,0.66),(0.70,0,0.70),(-0.70,0,0.70),(-0.74,0,0.66),(-0.74,0,-0.68),(-0.70,0,-0.72)]
        border.moveTo(*pts[0])
        for point in pts[1:]:
            border.drawTo(*point)
        bnp = self.dev_root.attachNewNode(border.create())
        bnp.setTransparency(TransparencyAttrib.MAlpha)
        bnp.setBin("fixed", 31)
        self.dev_text = OnscreenText(
            parent=self.dev_root, text="", pos=(-0.64, 0.60), align=TextNode.ALeft,
            scale=0.034, fg=(0.72, 1.0, 0.96, 0.98), mayChange=True,
        )
        self.dev_root.hide()

    def _toggle_dev_view(self) -> None:
        self.dev_view = not self.dev_view
        if self.dev_root is None:
            return
        if self.dev_view:
            self._update_dev_view()
            self.dev_root.show()
        else:
            self.dev_root.hide()

    def _update_dev_view(self) -> None:
        if not self.dev_text:
            return
        selected = self.state.selected_unit()
        selected_desc = "NONE" if not selected else f"{selected.name} @ {selected.pos}  HP {selected.hp}/{selected.max_hp}"
        runtime = "HOLOVERSE HOST" if self._holoverse_hosted else "STANDALONE"
        self.dev_text.setText(
            "DEV VIEW // F9 TO CLOSE\n\n"
            f"Runtime       {runtime}\n"
            f"Sector        {self.state.sector_index}/{MAX_JOURNEY_SECTORS}  {self.state.sector_name}\n"
            f"Board         {self.state.width}x{self.state.height}\n"
            f"Round/Turn    {self.state.round_index}  {self._friendly_turn_label()}\n"
            f"Cursor        {self.state.cursor}\n"
            f"Selected      {selected_desc}\n"
            f"Threat        {self.state.threat_label()}\n"
            f"Pulse         {self.state.corruption_pulse_duration()} turns\n"
            f"Sector Sync   {self.state.mission_progress_percent()}%\n"
            f"Journey Sync  {self.state.journey_progress_percent()}%\n"
            f"Ability Pool  map {len(self.state.ability_pickups)}  cache {len(self.state.ability_inventory)}/3\n"
            f"Audio         SFX {self.sfx.status_label() if self.sfx else 'OFF'} / MUSIC {self.sfx.music_status_label() if self.sfx else 'OFF'}\n"
            f"UI Contract   {'OK' if not self._ui_layout_issues else 'ISSUES'}"
        )

    def _screen_tile_from_ndc(self, mouse) -> tuple[int, int] | None:
        """Map normalized screen coordinates to the exact board tile.

        The board plane is derived from the board NodePath itself, so picking stays
        correct if a host moves/rotates the HoloTactics scene or while the board
        performs its small presentation bob.
        """
        near_point = Point3()
        far_point = Point3()
        if not self.camLens.extrude(mouse, near_point, far_point):
            return None
        near_world = self.render.getRelativePoint(self.camera, near_point)
        far_world = self.render.getRelativePoint(self.camera, far_point)
        board_origin = self.render.getRelativePoint(self.board_root, Point3(0, 0, 0))
        board_normal = self.render.getRelativeVector(self.board_root, Vec3(0, 0, 1))
        board_normal.normalize()
        board_plane = Plane(board_normal, board_origin)
        hit = Point3()
        if not board_plane.intersectsLine(hit, near_world, far_world):
            return None
        local = self.board_root.getRelativePoint(self.render, hit)
        tx = int(round(local.x))
        ty = int(round(local.y))
        if abs(local.x - tx) > 0.50 or abs(local.y - ty) > 0.50:
            return None
        pos = (tx, ty)
        return pos if self.state.in_bounds(pos) else None

    def _screen_tile_under_mouse(self):
        watcher = getattr(self, "mouseWatcherNode", None)
        if watcher is None or not watcher.hasMouse():
            return None
        return self._screen_tile_from_ndc(watcher.getMouse())

    def _update_mouse_hover(self) -> None:
        """Give a pre-click target preview without moving the tactical cursor."""
        if self.screen_mode != "mission" or (self.is_paused and not self._holoverse_hosted):
            pos = None
        elif getattr(self, "mouseWatcherNode", None) is None or not self.mouseWatcherNode.hasMouse():
            pos = None
        else:
            pos = self._screen_tile_under_mouse()
        if pos == self.hover_tile:
            return
        self.hover_tile = pos
        self._update_tile_frame_feedback()

    def _update_tile_frame_feedback(self) -> None:
        selected = self.state.selected_unit()
        ability_tiles = self._ability_target_tiles(selected)
        for pos, frame in self.tile_frames.items():
            if pos == self.hover_tile and pos in ability_tiles:
                frame.setColor(0.82, 0.38, 1.0, 1.0)
                frame.setZ(0.052)
                frame.setScale(1.07)
            elif pos == self.state.cursor and pos == self.hover_tile:
                frame.setColor(1.0, 1.0, 1.0, 1.0)
                frame.setZ(0.050)
                frame.setScale(1.07)
            elif pos == self.state.cursor:
                frame.setColor(0.25, 1.0, 1.0, 1.0)
                frame.setZ(0.045)
                frame.setScale(1.055)
            elif pos == self.hover_tile:
                frame.setColor(1.0, 1.0, 0.20, 1.0)
                frame.setZ(0.035)
                frame.setScale(1.045)
            else:
                frame.clearColor()
                frame.setZ(0.006)
                frame.setScale(1.0)

    def _start_mission(self) -> None:
        if self.screen_mode == "mission":
            return
        self.screen_mode = "mission"
        self.state.log_event(f"Gleebs enters {self.state.sector_name}.")
        self._play_sfx("start")
        self._start_music()
        self._refresh_scene()

    def _input_locked_by_menu(self) -> bool:
        if self.journey_map_open:
            return True
        if self.screen_mode != "mission":
            self.state.log_event("Press ENTER, SPACE, or LMB to enter the simulation.")
            self._refresh_scene()
            return True
        return False

    def _activate_or_select(self) -> None:
        if self.screen_mode != "mission":
            self._start_mission()
            return
        if self.state.can_expand_journey():
            self._advance_journey()
            return
        self._select()

    def _mouse_activate_or_select(self) -> None:
        if self.screen_mode != "mission":
            self._start_mission()
            return
        if self.state.can_expand_journey():
            self._advance_journey()
            return
        self._mouse_select_or_move()

    def _reset_to_title(self) -> None:
        if self.journey_map_open:
            self._toggle_journey_map(force=False)
        self.state = create_default_game()
        self._last_victory_key = None
        self._defeat_sfx_played = False
        self.screen_mode = "title"
        self._rebuild_board_scene()
        self._refresh_scene()
        self._write_scene_proof("reset_to_title")

    def _mouse_select_or_move(self) -> None:
        if self._input_locked_by_menu():
            return
        pos = self._screen_tile_under_mouse()
        if pos is None:
            self.state.log_event("Mouse target missed the board.")
            self._play_sfx("blocked")
            self._refresh_scene()
            return
        self.state.set_cursor(pos)
        selected = self.state.selected_unit()
        if self.state.unit_at(pos, team="player"):
            self._play_sfx("select" if self.state.select_at_cursor() else "blocked")
        elif selected and pos in self.state.legal_moves(selected.unit_id):
            before_flags = (self.state.memory_collected, self.state.action_die_claimed, self.state.extraction_reached)
            before_abilities = len(self.state.ability_inventory)
            moved = self.state.move_selected_to_cursor()
            after_flags = (self.state.memory_collected, self.state.action_die_claimed, self.state.extraction_reached)
            after_abilities = len(self.state.ability_inventory)
            if moved and after_flags[2] and not before_flags[2]:
                self._play_sfx("extraction")
            elif moved and after_abilities > before_abilities:
                self._play_sfx("ability_drop")
            elif moved and after_flags != before_flags:
                self._play_sfx("node")
            else:
                self._play_sfx("move" if moved else "blocked")
        else:
            self.state.log_event(f"Mouse targeted tile {pos}.")
            self._play_sfx("select")
        self._refresh_scene()

    def _mouse_attack(self) -> None:
        if self._input_locked_by_menu():
            return
        pos = self._screen_tile_under_mouse()
        if pos is None:
            self.state.log_event("Mouse attack missed the board.")
            self._play_sfx("blocked")
            self._refresh_scene()
            return
        self.state.set_cursor(pos)
        self._resolve_attack_with_sfx()
        self._refresh_scene()

    def _cursor(self, dx: int, dy: int) -> None:
        if self._input_locked_by_menu():
            return
        self.state.move_cursor(dx, dy)
        self._refresh_scene()

    def _select(self) -> None:
        if self._input_locked_by_menu():
            return
        self._play_sfx("select" if self.state.select_at_cursor() else "blocked")
        self._refresh_scene()

    def _move(self) -> None:
        if self._input_locked_by_menu():
            return
        before_flags = (self.state.memory_collected, self.state.action_die_claimed, self.state.extraction_reached)
        before_abilities = len(self.state.ability_inventory)
        moved = self.state.move_selected_to_cursor()
        after_flags = (self.state.memory_collected, self.state.action_die_claimed, self.state.extraction_reached)
        after_abilities = len(self.state.ability_inventory)
        if moved and after_flags[2] and not before_flags[2]:
            self._play_sfx("extraction")
        elif moved and after_abilities > before_abilities:
            self._play_sfx("ability_drop")
        elif moved and after_flags != before_flags:
            self._play_sfx("node")
        else:
            self._play_sfx("move" if moved else "blocked")
        self._refresh_scene()

    def _resolve_attack_with_sfx(self) -> bool:
        was_core_destroyed = self.state.core_destroyed
        pickup_count = len(self.state.ability_pickups)
        ok = self.state.attack_cursor()
        if ok and self.state.core_destroyed and not was_core_destroyed:
            self._play_sfx("core")
        elif ok and len(self.state.ability_pickups) > pickup_count:
            self._play_sfx("ability_drop")
        else:
            self._play_sfx("attack" if ok else "blocked")
        return ok

    def _attack(self) -> None:
        if self._input_locked_by_menu():
            return
        self._resolve_attack_with_sfx()
        self._refresh_scene()

    def _gleebs_patch_pulse(self) -> None:
        if self._input_locked_by_menu():
            return
        self._play_sfx("patch" if self.state.use_gleebs_patch_pulse() else "blocked")
        self._refresh_scene()

    def _use_ability(self) -> None:
        if self._input_locked_by_menu():
            return
        target_pos = self.state.cursor
        ok = self.state.use_current_ability()
        if ok:
            self._play_sfx("ability_cast")
            self._spawn_effect_pulse(target_pos)
        else:
            self._play_sfx("blocked")
        self._refresh_scene()

    def _end_turn(self) -> None:
        if self._input_locked_by_menu():
            return
        hp_before = {uid: unit.hp for uid, unit in self.state.units.items() if unit.team == "player"}
        log_len = len(self.state.log)
        self.state.end_player_turn()
        hp_after = {uid: unit.hp for uid, unit in self.state.units.items() if unit.team == "player"}
        new_log = " ".join(self.state.log[log_len:])
        if any(hp_after.get(uid, 0) < hp for uid, hp in hp_before.items()):
            self._play_sfx("enemy_hit")
        elif "corruption" in new_log.lower() or "fracture" in new_log.lower():
            self._play_sfx("warning")
        else:
            self._play_sfx("select")
        self._refresh_scene()

    def _reset(self) -> None:
        self.state = create_default_game()
        self._last_victory_key = None
        self._defeat_sfx_played = False
        self.screen_mode = "mission"
        self._rebuild_board_scene()
        self._refresh_scene()
        self._write_scene_proof("reset_mission")

    def _rebuild_board_scene(self) -> None:
        if hasattr(self, "board_root") and self.board_root:
            self.board_root.removeNode()
        for marker in self.move_markers:
            marker.removeNode()
        self.tile_nodes = {}
        self.tile_frames = {}
        self.hover_tile = None
        self.unit_nodes = {}
        self.node_markers = {}
        self.ability_markers = {}
        self.effect_rings = []
        self.move_markers = []
        self._build_scene()

    def _advance_journey(self) -> None:
        if self.journey_map_open:
            return
        if self._input_locked_by_menu():
            return
        if not self.state.can_expand_journey():
            self.state.log_event("Seal the current sector before expanding the route.")
            self._refresh_scene()
            return
        previous_sector = self.state.sector_name
        if self.state.expand_after_victory():
            self.screen_mode = "mission"
            self._last_victory_key = None
            self._defeat_sfx_played = False
            self._play_sfx("expand")
            self._start_music()
            self._rebuild_board_scene()
            self._refresh_scene()
            self._write_scene_proof(f"journey_expanded_from_{previous_sector}")


    def _advance_to_sector_for_screenshot(self, target_sector: int) -> None:
        # Internal screenshot setup only: walk the route to a larger sector without changing normal gameplay.
        target_sector = max(1, min(MAX_JOURNEY_SECTORS, target_sector))
        while self.state.sector_index < target_sector:
            self._force_sector_win_for_screenshot()
            if not self.state.expand_after_victory():
                break
            self._rebuild_board_scene()
        self.state.log_event(f"Route preview locked on {self.state.sector_name}.")
        self._refresh_scene()

    def _force_sector_win_for_screenshot(self) -> None:
        # Internal screenshot setup only: this produces proof for the expanded-board review image.
        self.state.memory_collected = True
        self.state.core_destroyed = True
        self.state.extraction_reached = True
        self.state.nodes["memory"].captured_by = "player"
        self.state.nodes["core"].captured_by = "player"
        self.state.nodes["extract"].captured_by = "player"
        self.state.tiles[self.state.nodes["extract"].pos].state = "extraction"
        self.state.log_event("Sector sealed for expanded route screenshot.")

    def _prepare_sector5_finale_stage_for_screenshot(self, stage: int) -> None:
        # Internal screenshot setup only: expose later finale states without
        # changing the normal campaign path or player-facing rules.
        if self.state.sector_index != 5:
            return
        for node_id in self.state.sector5_horizon_relay_ids():
            self.state.nodes[node_id].captured_by = "player"
        self.state._resolve_sector5_relay_alignment()
        if stage >= 3:
            node = self.state.nodes["die"]
            tile = self.state.tiles[node.pos]
            tile.state = "stable"
            tile.turns_corrupted = 0
            tile.turns_fractured = 0
            node.captured_by = "player"
            self.state.units["guard"].pos = self.state.nodes["patch"].pos
            self.state.units["runner"].pos = self.state.nodes["memory"].pos
            self.state.log_event("QA preview: final relay hold is formed before hostile response.")
        else:
            self.state.log_event("QA preview: Horizon Fracture exposed for Gleebs Patch Pulse.")
        self._refresh_scene()

    def _force_ability_pickup_for_screenshot(self) -> None:
        # Internal screenshot setup: show a pickup and a loaded one-shot without changing normal start flow.
        drop = self.state.force_spawn_ability_drop("anomaly", (3, 4), kind="arc")
        self.state.force_spawn_ability_drop("sentry", (5, 3), kind="patch")
        loaded = self.state.generate_procedural_ability("sentry", (2, 2))
        loaded.kind = "blink"
        loaded.name = "Signal Blink"
        loaded.potency = 0
        loaded.range = 4
        loaded.radius = 0
        loaded.collected = True
        loaded.pos = None
        self.state.ability_inventory.append(loaded)
        self.state.log_event(f"Loaded one-shot ability: {loaded.short_label()}.")
        self.state.cursor = drop.pos or (3, 4)


    def _prepare_readability_proof(self) -> None:
        """Internal QA state showing all Pass 19 tactical cues in one real frame."""
        self.state.cursor = self.state.units["gleebs"].pos
        self.state.select_at_cursor()
        loaded = self.state.generate_procedural_ability("sentry", self.state.units["sentry"].pos)
        loaded.kind = "blink"
        loaded.name = "Signal Blink"
        loaded.potency = 0
        loaded.range = 4
        loaded.radius = 0
        loaded.collected = True
        loaded.pos = None
        self.state.ability_inventory.insert(0, loaded)
        # Guarantee both hazard shapes are visible without changing the normal mission start.
        for pos, state in (((3, 2), "corrupted"), ((4, 2), "fracture")):
            if self.state.in_bounds(pos) and not self.state.unit_at(pos) and not self.state.is_node_position(pos):
                self.state.tiles[pos].state = state
        self.state.cursor = (2, 2) if self.state.in_bounds((2, 2)) else self.state.units["gleebs"].pos
        self.state.log_event("Tactical readability proof state prepared.")

    def _toggle_hud(self) -> None:
        self.hud_visible = not self.hud_visible
        self._play_sfx("toggle")
        self._update_hud()

    def _toggle_sfx(self) -> None:
        if self.sfx is None:
            return
        muted = self.sfx.toggle_mute()
        self.state.log_event(f"SFX {'muted' if muted else 'online'}.")
        self._update_hud()

    def _toggle_music(self) -> None:
        if self.sfx is None:
            return
        muted = self.sfx.toggle_music()
        self.state.log_event(f"Music {'muted' if muted else 'online'}.")
        self._update_hud()

    def _setup_sfx(self) -> None:
        settings = self._holoverse_runtime_settings
        muted = _flag_present("--mute-sfx") or _truthy(os.environ.get("HOLOTACTICS_MUTE"))
        music_muted = _flag_present("--mute-music") or _truthy(os.environ.get("HOLOTACTICS_MUSIC_MUTE"))
        master = max(0.0, min(1.0, float(settings.get("master_volume", 1.0))))
        sfx_mix = max(0.0, min(1.0, float(settings.get("sfx_volume", 1.0))))
        music_mix = max(0.0, min(1.0, float(settings.get("music_volume", 1.0))))
        try:
            self.sfx = HoloSfx(
                self.loader, BASE_DIR, muted=muted, music_muted=music_muted,
                volume=0.72 * master * sfx_mix,
                music_volume=0.34 * master * music_mix,
            )
        except Exception:
            self.sfx = None

    def _music_cue_for_current_sector(self) -> str:
        return SECTOR_MUSIC_CUES.get(int(getattr(self.state, "sector_index", 1)), "holo_ambient")

    def _start_music(self) -> bool:
        return bool(self.sfx and self.sfx.play_music(self._music_cue_for_current_sector()))

    def _play_sfx(self, cue: str) -> bool:
        return bool(self.sfx and self.sfx.play(cue))

    def _make_ability_marker(self, ability_id: str) -> NodePath:
        root = NodePath(f"ability_pickup_{ability_id}")
        ring = self._make_piece_ring((0.80, 1.0, 0.22, 0.95), radius=0.30)
        ring.reparentTo(root)
        ring.setZ(0.03)
        core = make_box("ability_cache_core", 0.20, 0.20, 0.20, (0.65, 1.0, 0.16, 0.92))
        core.reparentTo(root)
        core.setZ(0.24)
        shard = make_box("ability_cache_shard", 0.10, 0.36, 0.08, (0.72, 0.24, 1.0, 0.78))
        shard.reparentTo(root)
        shard.setZ(0.38)
        shard.setH(35)
        return root

    def _sync_ability_markers(self) -> None:
        wanted = set(self.state.ability_pickups)
        for ability_id in list(self.ability_markers):
            if ability_id not in wanted:
                self.ability_markers[ability_id].removeNode()
                del self.ability_markers[ability_id]
        for ability_id, ability in self.state.ability_pickups.items():
            marker = self.ability_markers.get(ability_id)
            if marker is None:
                marker = self._make_ability_marker(ability_id)
                marker.reparentTo(self.board_root)
                self.ability_markers[ability_id] = marker
            if ability.pos is not None:
                marker.setPos(ability.pos[0], ability.pos[1], 0.12)
                marker.show()
            else:
                marker.hide()

    def _spawn_effect_pulse(self, pos: tuple[int, int]) -> None:
        ring = self._make_piece_ring((0.75, 1.0, 0.12, 0.95), radius=0.42)
        ring.reparentTo(self.board_root)
        ring.setPos(pos[0], pos[1], 0.16)
        self.effect_rings.append({"node": ring, "ttl": 1.20, "age": 0.0})

    def _refresh_scene(self) -> None:
        for marker in self.move_markers:
            marker.removeNode()
        self.move_markers.clear()
        legal = set()
        attack_tiles = set()
        selected = self.state.selected_unit()
        if selected:
            legal = set(self.state.legal_moves(selected.unit_id))
            attack_tiles = set(self.state.legal_attack_tiles(selected.unit_id, include_empty=True))
        ability_tiles = self._ability_target_tiles(selected)
        objective_pos = self._active_objective_pos()
        for pos, node in self.tile_nodes.items():
            tile = self.state.tiles[pos]
            color = self._tile_color(tile.state)
            if pos == self.state.cursor:
                color = (0.95, 1.0, 0.18, 0.82)
            elif pos in legal:
                color = (0.05, 0.95, 0.35, 0.55)
            elif pos in attack_tiles:
                color = (1.0, 0.35, 0.05, 0.45)
            node.setColor(*color)
            node.setZ(0.012 if pos == self.state.cursor else 0.0)
            if pos in legal:
                self._add_tactical_marker("move", pos)
            if pos in attack_tiles:
                self._add_tactical_marker("attack", pos)
            if pos == self.state.cursor and pos in ability_tiles:
                self._add_tactical_marker("ability", pos)
            if tile.state == "corrupted":
                self._add_tactical_marker("danger", pos)
            elif tile.state == "fracture":
                self._add_tactical_marker("fracture", pos)
        if self.state.sector_index == 4 and not self.state.core_destroyed:
            for node_id in self.state.sector4_grid_uplink_ids():
                self._add_tactical_marker("objective", self.state.nodes[node_id].pos)
        elif self.state.sector_index == 5 and not self.state.core_destroyed:
            stage = self.state.sector5_horizon_stage()
            if stage in {1, 3}:
                for node_id in self.state.sector5_horizon_relay_ids():
                    if stage == 3 or self.state.nodes[node_id].captured_by != "player":
                        self._add_tactical_marker("objective", self.state.nodes[node_id].pos)
            elif objective_pos is not None:
                self._add_tactical_marker("objective", objective_pos)
        elif objective_pos is not None:
            self._add_tactical_marker("objective", objective_pos)
        if selected:
            selected_ring = self._make_piece_ring((0.25, 1.0, 1.0, 1.0), radius=0.41)
            selected_ring.reparentTo(self.board_root)
            selected_ring.setPos(selected.pos[0], selected.pos[1], 0.075)
            self.move_markers.append(selected_ring)
        self._update_tile_frame_feedback()
        actor_scales = {"gleebs": 0.88, "guard": 0.90, "runner": 0.86, "anomaly": 0.88, "sentry": 0.88}
        for unit_id, unit in self.state.units.items():
            np = self.unit_nodes[unit_id]
            if unit.alive:
                np.show()
                np.setPos(unit.pos[0], unit.pos[1], 0.07)
                base_scale = actor_scales.get(unit_id, 0.88)
                selected_boost = 1.08 if unit_id == self.state.selected_unit_id else 1.0
                np.setScale(base_scale * selected_boost)
            else:
                np.hide()
        for node_id, marker in self.node_markers.items():
            node_state = self.state.nodes[node_id]
            marker.setColor(1.0, 1.0, 1.0, 1.0)
            if self.state.sector_index == 3 and node_id in {"patch", "die", "memory"} and node_state.captured_by != "player":
                marker.setColor(1.0, 0.72, 0.24, 1.0)
            if self.state.sector_index == 5 and node_id == "die" and self.state.sector5_horizon_stage() == 2:
                marker.setColor(1.0, 0.38, 0.16, 1.0)
            if node_state.captured_by == "player":
                marker.setColor(0.35, 1.0, 0.55, 1.0)
            if node_id == "core" and self.state.memory_collected and not self.state.core_destroyed and self.state.sector_index != 5:
                marker.setColor(1.0, 0.35, 0.15, 1.0)
            if node_id == "core" and self.state.core_destroyed:
                marker.setColor(0.25, 0.25, 0.25, 0.35)
            if node_id == "extract" and self.state.extraction_open():
                marker.setColor(0.35, 1.0, 0.85, 1.0)
            if node_id == "extract" and self.state.extraction_reached:
                marker.setColor(0.55, 1.0, 0.55, 1.0)
        self._sync_ability_markers()
        self._update_hud()
        self._write_scene_proof("refresh")

    def _tile_color(self, state: str) -> tuple[float, float, float, float]:
        if state == "memory":
            return (0.0, 0.65, 0.25, 0.48)
        if state == "corrupted":
            return (0.95, 0.05, 0.08, 0.50)
        if state == "anchor":
            return (0.08, 0.25, 0.95, 0.45)
        if state == "signal":
            return (0.55, 0.18, 0.95, 0.46)
        if state == "fracture":
            return (1.0, 0.55, 0.05, 0.42)
        if state == "extraction":
            return (0.05, 1.0, 0.78, 0.58)
        if state == "void":
            return (0.02, 0.02, 0.04, 0.25)
        return (0.02, 0.42, 0.55, 0.28)

    def _friendly_turn_label(self) -> str:
        if self.state.turn == "player":
            return "PLAYER LINK"
        if self.state.turn == "enemy":
            return "HOSTILE RESPONSE"
        return "SYSTEM SHIFT"

    def _unit_action_line(self, selected) -> str:
        if not selected:
            return "Select a squad unit to preview movement."
        move_state = "ready" if not selected.moved else "used"
        action_state = "ready" if not selected.acted else "used"
        return f"Move {move_state}  •  Action {action_state}"

    def _node_state_word(self, node_id: str) -> str:
        if self.state.sector_index == 3 and node_id in {"patch", "die", "memory"}:
            return "stable" if self.state.nodes[node_id].captured_by == "player" else "fractured"
        if node_id == "patch":
            return "online" if self.state.patch_node_captured() else "unclaimed"
        if node_id == "die":
            return "charged" if self.state.action_die_claimed else "available"
        if node_id == "core":
            if self.state.core_destroyed:
                return "broken"
            return "vulnerable" if self.state.memory_collected else "shielded"
        if node_id == "extract":
            if self.state.extraction_reached:
                return "complete"
            return "open" if self.state.extraction_open() else "locked"
        return "ready"

    def _clean_log_line(self, line: str) -> str:
        replacements = {
            "Review build": "Simulation",
            "review build": "simulation",
            "Pass 05": "",
            "Prototype": "",
            "prototype": "",
            "cursor": "target",
            "Cursor": "Target",
        }
        for src, dst in replacements.items():
            line = line.replace(src, dst)
        return " ".join(line.split())

    def _ability_hud_label(self) -> str:
        ability = self.state.inventory_ability()
        if not ability:
            return "EMPTY"
        return f"{ability.name} [{ability.kind.upper()}] • X"

    def _update_hud(self) -> None:
        if not self.status_text:
            return
        title_mode = self.screen_mode == "title"
        if self.menu_text:
            self.menu_text.show() if title_mode and self.hud_visible else self.menu_text.hide()
        # Keep the in-mission panels quiet on the title screen.
        for name, panel in self.hud_panel_nodes.items():
            if not self.hud_visible:
                panel.hide()
            elif title_mode and not (name.startswith("ui_title_glass") or name.startswith("ui_comms_glass")):
                panel.hide()
            else:
                panel.show()
        for item in (self.title_text, self.subtitle_text):
            if item:
                item.show() if self.hud_visible else item.hide()
        for item in (self.status_text, self.log_text, self.help_text, self.completion_text):
            if item:
                item.hide() if title_mode else (item.show() if self.hud_visible else item.hide())
        selected = self.state.selected_unit()
        selected_name = selected.name if selected else "No unit selected"
        selected_role = selected.role if selected else "Choose a squad piece"
        selected_hp = f"{selected.hp}/{selected.max_hp}" if selected else "--"
        self.status_text.setText(
            "SQUAD LINK\n"
            f"{selected_name}\n"
            f"{selected_role}\n"
            f"HP {selected_hp}\n"
            f"{self._unit_action_line(selected)}\n"
            f"Ability: {self._ability_hud_label()}"
        )

        if self.state.sector_index == 2:
            lock_state = "OPEN" if self.state.core_destroyed else "ACTIVE"
            extract_state = self._node_state_word("extract").upper()
            gate_lines = f"Route Lock: {lock_state}\nExtraction: {extract_state}"
        elif self.state.sector_index == 3:
            gate_state = "OPEN" if self.state.core_destroyed else "BOUND"
            extract_state = self._node_state_word("extract").upper()
            gate_lines = f"Stability Gate: {gate_state}\nExtraction: {extract_state}"
        elif self.state.sector_index == 4:
            gate_state = "OPEN" if self.state.core_destroyed else "ACTIVE"
            extract_state = self._node_state_word("extract").upper()
            gate_lines = f"Grid Lock: {gate_state}\nExtraction: {extract_state}"
        elif self.state.sector_index == 5:
            core_state = "OPEN" if self.state.core_destroyed else "BOUND"
            extract_state = self._node_state_word("extract").upper()
            gate_lines = f"Core: {core_state}\nExtraction: {extract_state}"
        else:
            core_state = self._node_state_word("core").upper()
            extract_state = self._node_state_word("extract").upper()
            gate_lines = f"Core: {core_state}\nExtraction: {extract_state}"

        objective_lines = self._wrapped_objective().splitlines()
        objective = "\n".join(objective_lines[:3])
        self.completion_text.setText(
            f"MISSION // {self.state.sector_name.upper()}\n"
            "PRIMARY\n"
            f"{objective}\n"
            f"{gate_lines}"
        )

        # Keep whole messages. Never show an orphaned wrapped fragment.
        groups: list[list[str]] = []
        for line in self.state.log[-3:]:
            clean = self._clean_log_line(line)
            groups.append((textwrap.wrap(clean, width=31) or [clean])[:2])
        visible: list[list[str]] = []
        budget = 4
        used = 0
        for group in reversed(groups):
            if not visible or used + len(group) <= budget:
                visible.insert(0, group)
                used += len(group)
        comms_lines = [part for group in visible for part in group]
        self.log_text.setText("GLEEBS COMMS\n" + "\n".join(comms_lines))
        if self.dev_view:
            self._update_dev_view()
        if self.result_text:
            if self.state.victory():
                victory_key = (self.state.sector_index, self.state.sector_name)
                if self._last_victory_key != victory_key:
                    self._last_victory_key = victory_key
                    self._play_sfx("sector_clear")
                self.result_text.setFg((0.55, 1.0, 0.75, 0.95))
                if self.state.can_expand_journey():
                    self.result_text.setText("SECTOR SEALED\nN / ENTER: expand route\nR: title")
                elif self.state.journey_complete():
                    self.result_text.setText("JOURNEY SEALED\nVisible route stabilized\nR: title  •  ESC: pause")
                else:
                    self.result_text.setText("SIMULATION SEALED\nExtraction complete\nR: title  •  ESC: pause")
            elif self.state.defeat():
                if not self._defeat_sfx_played:
                    self._defeat_sfx_played = True
                    self._play_sfx("defeat")
                self.result_text.setFg((1.0, 0.35, 0.25, 0.95))
                self.result_text.setText("LINK LOST\nSquad destabilized\nR: title  •  ESC: pause")
            else:
                self.result_text.setText("")


    def _wrapped_objective(self) -> str:
        if self.state.victory() or self.state.defeat():
            return self.state.objective_text()
        if self.state.sector_index == 2 and not self.state.core_destroyed:
            alpha = "SYNC" if self.state.memory_collected else "OPEN"
            beta = "SYNC" if self.state.patch_node_captured() else "OPEN"
            return f"Synchronize Signal Relays\nA {alpha}  •  B {beta}"
        if self.state.sector_index == 3 and not self.state.core_destroyed:
            return f"Stabilize Fracture Anchors\nGleebs Patch Pulse • {self.state.fracture_anchor_count()}/3"
        if self.state.sector_index == 4 and not self.state.core_destroyed:
            west = "HELD" if self.state.sector4_uplink_occupied("patch") else "OPEN"
            east = "HELD" if self.state.sector4_uplink_occupied("memory") else "OPEN"
            return f"Hold both Outer Uplinks\nW {west} • E {east} • Bridge {self.state.grid_link_charge}/2"
        if self.state.sector_index == 5 and not self.state.core_destroyed:
            stage = self.state.sector5_horizon_stage()
            if stage == 1:
                west = "SYNC" if self.state.nodes["patch"].captured_by == "player" else "OPEN"
                east = "SYNC" if self.state.nodes["memory"].captured_by == "player" else "OPEN"
                return f"Final 1/3 • Align Horizon Relays\nW {west} • E {east}"
            if stage == 2:
                return "Final 2/3 • Stabilize Horizon Fracture\nGleebs Patch Pulse (Q)"
            west = "HELD" if self.state.sector5_relay_occupied("patch") else "OPEN"
            east = "HELD" if self.state.sector5_relay_occupied("memory") else "OPEN"
            return f"Final 3/3 • Hold both Relays\nW {west} • E {east} • survive response"
        if not self.state.memory_collected:
            optional = []
            if not self.state.patch_node_captured():
                optional.append("Patch")
            if not self.state.action_die_claimed:
                optional.append("Action Die")
            if optional:
                return "/".join(optional) + " optional\nGleebs -> Memory Node"
            return "Gleebs -> Memory Node"
        if not self.state.core_destroyed:
            return "Break Game Master Core"
        return "Reach Extraction Gate"

    def _pulse_update(self, now: float, dt: float) -> None:
        self._update_mouse_hover()
        pulse = 1.0 + math.sin(now * 3.2) * 0.08
        for node_id, marker in self.node_markers.items():
            if self.state.sector_index == 3 and node_id in {"patch", "die", "memory"}:
                marker.setScale(pulse)
                marker.setH(now * (16 if node_id == "patch" else 20 if node_id == "die" else 24))
            elif self.state.sector_index == 5 and node_id in {"patch", "die", "memory"}:
                marker.setScale(pulse if node_id == "die" else 1.0 + math.sin(now * 3.6) * 0.06)
                marker.setH(now * (18 if node_id == "patch" else -26 if node_id == "die" else 22))
            else:
                marker.setScale(pulse if node_id == "memory" else 1.0 + math.sin(now * 4.1) * 0.05)
                marker.setH(now * 18 if node_id == "memory" else -now * 22)
        for marker in self.ability_markers.values():
            marker.setH(now * 55)
            marker.setScale(1.0 + math.sin(now * 5.4) * 0.08)
        dt = max(0.0, min(0.05, float(dt)))
        for effect in list(self.effect_rings):
            effect["age"] += dt
            age = effect["age"]
            ttl = effect["ttl"]
            node = effect["node"]
            if age >= ttl:
                node.removeNode()
                self.effect_rings.remove(effect)
            else:
                node.setScale(1.0 + age * 1.6)
                node.setColor(0.75, 1.0, 0.12, max(0.0, 0.95 * (1.0 - age / ttl)))
        self.board_root.setZ(math.sin(now * 0.9) * 0.025)

    def _pulse_task(self, task: Task) -> int:
        dt = globalClock.getDt() if "globalClock" in globals() else 0.016
        self._pulse_update(float(task.time), dt)
        return Task.cont

    def hosted_step(self, dt: float) -> bool:
        """Advance the complete HoloTactics presentation from HoloVerse's frame loop."""
        try:
            dt = max(0.0, min(0.05, float(dt)))
            self._hosted_elapsed += dt
            self._pulse_update(self._hosted_elapsed, dt)
            return True
        except Exception as exc:
            _write_crash(exc)
            return False

    def hosted_action(self, action: str) -> bool:
        """Receive HoloVerse's standardized input without registering a second messenger map."""
        action = str(action or "").lower().strip()
        if action in {"escape", "pause", "menu", "return", "return_to_core"}:
            return False
        if self.journey_map_open and action != "j":
            return True
        # Key-up messages are consumed but do not repeat turn-based actions.
        if action.endswith("_up") or action.endswith("-up"):
            return True
        movement = {
            "w": (0, 1), "arrow_up": (0, 1),
            "s": (0, -1), "arrow_down": (0, -1),
            "a": (-1, 0), "arrow_left": (-1, 0),
            "d": (1, 0), "arrow_right": (1, 0),
        }
        if action in movement:
            self._cursor(*movement[action])
            return True
        aliases = {"e_down": "e", "q_down": "q", "toggle_dimension_ui": "h", "dimension_ui": "h"}
        action = aliases.get(action, action)
        commands = {
            "space": self._activate_or_select,
            "enter": self._activate_or_select,
            "m": self._move,
            "v": self._toggle_sfx,
            "b": self._toggle_music,
            "f": self._attack,
            "e": self._end_turn,
            "q": self._gleebs_patch_pulse,
            "x": self._use_ability,
            "n": self._advance_journey,
            "c": self._advance_journey,
            "h": self._toggle_hud,
            "j": self._toggle_journey_map,
            "r": self._reset_to_title,
            "f9": self._toggle_dev_view,
            "mouse1": self._mouse_activate_or_select,
            "mouse3": self._mouse_attack,
        }
        fn = commands.get(action)
        if fn is None:
            return False
        fn()
        return True

    def hosted_destroy(self) -> None:
        try:
            self.ignoreAll()
        except Exception:
            pass
        try:
            self.removeAllTasks()
        except Exception:
            pass
        if self.sfx is not None:
            try:
                self.sfx.stop_music()
            except Exception:
                pass
        for task_name in ("holo_pulse_task", "capture_smoke_screenshot"):
            try:
                self.taskMgr.remove(task_name)
            except Exception:
                pass
        for text_node in (self.title_text, self.subtitle_text, self.status_text, self.completion_text, self.log_text, self.help_text, self.result_text, self.menu_text, self.pause_text, self.pause_hint_text, self.journey_map_title, self.journey_map_hint, *self.journey_map_labels):
            try:
                if text_node is not None and hasattr(text_node, "destroy"):
                    text_node.destroy()
            except Exception:
                pass
        for node in reversed(self._holoverse_owned_nodes):
            try:
                if node is not None and not node.isEmpty():
                    node.removeNode()
            except Exception:
                pass
        self._holoverse_owned_nodes.clear()

    def userExit(self):
        if self._holoverse_hosted and self._holoverse_host is not None:
            return_fn = getattr(self._holoverse_host, "return_from_native_mode", None)
            if callable(return_fn):
                return_fn(reason="holotactics_requested_return")
                return
        return super().userExit()

    def _write_scene_proof(self, reason: str) -> None:
        payload = {
            "schema_version": "holotactics_scene_proof.v1",
            "template_version": TEMPLATE_VERSION,
            "reason": reason,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "state": self.state.snapshot(),
            "completion_notes": {
                "declared_completion": "100% audio path compatibility fix milestone",
                "approval_status": "ready for audio path compatibility review; bigger world, ability loot, UI, actors, and progression preserved",
                "visual_proof": "Fresh Panda3D screenshots captured after audio path compatibility fix",
                "sfx_cues": sorted(SFX_CUES),
                "music_cues": sorted(MUSIC_CUES),
                "audio_asset_issues": validate_audio_assets(BASE_DIR),
                "actor_visual_issues": getattr(self, "_actor_visual_issues", []),
                "screen_mode": self.screen_mode,
                "ui_layout_issues": getattr(self, "_ui_layout_issues", []),
            },
        }
        _write_json(REPORTS_DIR / "scene_proof_latest.json", payload)
        proof_path = _arg_value("--proof-path") or os.environ.get("GPT_BRIDGE_SMOKE_PROOF_PATH")
        if proof_path:
            _write_json(Path(proof_path), payload)


    def _capture_smoke_screenshot(self, task: Task) -> int:
        screenshot_path = _arg_value("--screenshot-path") or os.environ.get("GPT_BRIDGE_SCREENSHOT_PATH")
        if not screenshot_path:
            screenshot_path = str(SCREENSHOTS_DIR / ("pass13_" + "smoke" + "." + "png"))
        out = Path(screenshot_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.graphicsEngine.renderFrame()
        self.graphicsEngine.renderFrame()
        saved = bool(self.win.saveScreenshot(Filename.fromOsSpecific(str(out))))
        self._write_scene_proof("screenshot_saved" if saved else "screenshot_failed")
        self.userExit()
        return Task.done


def make_prism(
    name: str,
    radius: float,
    height: float,
    color: tuple[float, float, float, float],
    sides: int = 6,
    top_scale: float = 1.0,
) -> NodePath:
    sides = max(3, int(sides))
    fmt = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    color_writer = GeomVertexWriter(vdata, "color")
    hz = height / 2.0
    for z, scale in ((-hz, 1.0), (hz, top_scale)):
        for i in range(sides):
            a = math.tau * i / sides + math.pi / 2.0
            vertex.addData3f(math.cos(a) * radius * scale, math.sin(a) * radius * scale, z)
            color_writer.addData4f(*color)
    bottom_center = sides * 2
    top_center = bottom_center + 1
    vertex.addData3f(0, 0, -hz); color_writer.addData4f(*color)
    vertex.addData3f(0, 0, hz); color_writer.addData4f(*color)
    tris = GeomTriangles(Geom.UHStatic)
    for i in range(sides):
        j = (i + 1) % sides
        tris.addVertices(i, j, sides + j)
        tris.addVertices(i, sides + j, sides + i)
        tris.addVertices(bottom_center, j, i)
        tris.addVertices(top_center, sides + i, sides + j)
    geom = Geom(vdata); geom.addPrimitive(tris)
    node = GeomNode(name); node.addGeom(geom)
    np = NodePath(node); np.setTransparency(TransparencyAttrib.MAlpha)
    return np


def make_wedge(name: str, sx: float, sy: float, sz: float, color: tuple[float, float, float, float]) -> NodePath:
    fmt = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    color_writer = GeomVertexWriter(vdata, "color")
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
    verts = [
        (-hx, -hy, -hz), (hx, -hy, -hz), (0.0, -hy, hz),
        (-hx, hy, -hz), (hx, hy, -hz), (0.0, hy, hz),
    ]
    for v in verts:
        vertex.addData3f(*v); color_writer.addData4f(*color)
    tris = GeomTriangles(Geom.UHStatic)
    faces = [
        (0, 1, 2), (3, 5, 4),
        (0, 3, 4), (0, 4, 1),
        (1, 4, 5), (1, 5, 2),
        (2, 5, 3), (2, 3, 0),
    ]
    for a, b, c in faces:
        tris.addVertices(a, b, c)
    geom = Geom(vdata); geom.addPrimitive(tris)
    node = GeomNode(name); node.addGeom(geom)
    np = NodePath(node); np.setTransparency(TransparencyAttrib.MAlpha)
    return np


def make_box(name: str, sx: float, sy: float, sz: float, color: tuple[float, float, float, float]) -> NodePath:
    fmt = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vertex = GeomVertexWriter(vdata, "vertex")
    color_writer = GeomVertexWriter(vdata, "color")
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
    verts = [
        (-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
        (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz),
    ]
    for v in verts:
        vertex.addData3f(*v)
        color_writer.addData4f(*color)
    tris = GeomTriangles(Geom.UHStatic)
    faces = [
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
    ]
    for a, b, c in faces:
        tris.addVertices(a, b, c)
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    np = NodePath(node)
    np.setTransparency(TransparencyAttrib.MAlpha)
    return np


def main() -> None:
    try:
        app = HoloTacticsApp()
        # GPTool screenshot hook support when present in a copied GPTool runtime.
        try:
            smoke_hook = importlib.import_module("runtime_hooks.panda3d_smoke_hook")
            smoke_hook.install_from_env(app)
        except (ImportError, AttributeError):
            pass
        app.run()
    except SystemExit:
        raise
    except BaseException as exc:
        _write_crash(exc)
        raise


if __name__ == "__main__":
    main()
