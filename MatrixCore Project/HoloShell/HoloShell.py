import colorsys
import json
import math
import os
import random
import subprocess
import sys
import time
import textwrap
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

SELF_TEST = "--self-test" in sys.argv
AUTO_SHOT = "--auto-shot" in sys.argv
AUTO_EXIT = "--auto-exit" in sys.argv

def get_cli_arg(flag: str, default=None, cast=str):
    if flag in sys.argv:
        try:
            return cast(sys.argv[sys.argv.index(flag) + 1])
        except Exception:
            return default
    return default

ARTIFACT_SHOT_ID = get_cli_arg("--artifact-shot", None, int)
ARTIFACT_SHOT_PATH = get_cli_arg("--artifact-shot-path", None, str)


def _truthy(value, default=False):
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _int_setting(value, default, low, high):
    try:
        return max(low, min(high, int(float(value))))
    except Exception:
        return default


def _float_setting(value, default, low, high):
    try:
        return max(low, min(high, float(value)))
    except Exception:
        return default


def load_holoverse_runtime_settings():
    """Read the host display/input/audio contract without requiring HoloVerse.

    Native same-window mode borrows the live ShowBase and only uses these values
    as behavioral settings. Compatibility/external mode consumes the same payload
    before opening its own window so Windows presentation matches the host.
    """
    payload = {}
    raw_path = str(os.environ.get("HOLOVERSE_SETTINGS_PATH", "") or "").strip()
    if raw_path:
        try:
            path = Path(raw_path)
            if path.exists():
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    payload = loaded
        except Exception:
            payload = {}
    native = _truthy(os.environ.get("HOLOVERSE_NATIVE_INPROCESS"), False)
    hosted = bool(raw_path or os.environ.get("HOLOVERSE_DIMENSION_ID") or native)
    return {
        "hosted_contract": hosted,
        "native_inprocess": native,
        "width": _int_setting(os.environ.get("MATRIX_GAME_WIDTH", os.environ.get("HOLOVERSE_WIDTH", payload.get("width", 1920))), 1920, 640, 7680),
        "height": _int_setting(os.environ.get("MATRIX_GAME_HEIGHT", os.environ.get("HOLOVERSE_HEIGHT", payload.get("height", 1080))), 1080, 360, 4320),
        "window_x": _int_setting(os.environ.get("MATRIX_GAME_X", os.environ.get("HOLOVERSE_WINDOW_X", payload.get("window_x", 0))), 0, -32768, 32768),
        "window_y": _int_setting(os.environ.get("MATRIX_GAME_Y", os.environ.get("HOLOVERSE_WINDOW_Y", payload.get("window_y", 0))), 0, -32768, 32768),
        "fullscreen": _truthy(os.environ.get("MATRIX_GAME_FULLSCREEN", payload.get("fullscreen", False))),
        "borderless": _truthy(os.environ.get("MATRIX_GAME_BORDERLESS", payload.get("borderless", False))),
        "bordered_fullscreen": _truthy(os.environ.get("HOLOVERSE_BORDERED_FULLSCREEN", payload.get("bordered_fullscreen", True))),
        "vsync": _truthy(os.environ.get("HOLOVERSE_VSYNC", payload.get("vsync", True)), True),
        "fps_cap": _int_setting(os.environ.get("HOLOVERSE_FPS_CAP", payload.get("fps_cap", 60)), 60, 15, 240),
        "ui_scale": _float_setting(os.environ.get("HOLOVERSE_UI_SCALE", payload.get("ui_scale", 1.0)), 1.0, 0.75, 1.5),
        "render_scale": _float_setting(os.environ.get("HOLOVERSE_RENDER_SCALE", payload.get("render_scale", 1.0)), 1.0, 0.5, 2.0),
        "hud_visible": _truthy(os.environ.get("MATRIX_GAME_HUD_VISIBLE", os.environ.get("HOLOVERSE_HUD_ENABLED", payload.get("hud_enabled", payload.get("hud_visible", True)))), True),
        "subtitles_enabled": _truthy(os.environ.get("HOLOVERSE_SUBTITLES_ENABLED", payload.get("subtitles_enabled", True)), True),
        "mouse_sensitivity": _float_setting(os.environ.get("MATRIX_GAME_MOUSE_SENSITIVITY", os.environ.get("HOLOVERSE_MOUSE_SENSITIVITY", payload.get("mouse_sensitivity", 0.22))), 0.22, 0.02, 1.0),
        "invert_y": _truthy(os.environ.get("MATRIX_GAME_INVERT_Y", os.environ.get("HOLOVERSE_INVERT_Y", payload.get("invert_y", False)))),
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

from panda3d.core import loadPrcFileData

PRC = """
window-title HoloVerse Observatory
win-size 1920 1080
show-frame-rate-meter 0
sync-video 1
framebuffer-multisample 1
multisamples 4
textures-power-2 none
texture-anisotropic-degree 8
notify-level-display warning
notify-level-glgsg warning
cursor-hidden 1
audio-library-name null
model-path ./assets
"""
if SELF_TEST:
    PRC += "\nwindow-type offscreen\n"
if not HOLOVERSE_RUNTIME_SETTINGS.get("native_inprocess", False):
    if HOLOVERSE_RUNTIME_SETTINGS.get("hosted_contract", False):
        PRC += f"\nwin-size {int(HOLOVERSE_RUNTIME_SETTINGS['width'])} {int(HOLOVERSE_RUNTIME_SETTINGS['height'])}\n"
        PRC += f"sync-video {1 if HOLOVERSE_RUNTIME_SETTINGS.get('vsync', True) else 0}\n"
    loadPrcFileData("", PRC)

from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from direct.task import Task
from panda3d.core import (
    AmbientLight,
    AntialiasAttrib,
    CardMaker,
    ClockObject,
    DirectionalLight,
    Filename,
    Fog,
    InputDevice,
    LineSegs,
    PNMImage,
    SamplerState,
    TextNode,
    Texture,
    TextureStage,
    TransparencyAttrib,
    Vec2,
    Vec3,
    WindowProperties,
    LColor,
)

VERSION = "1.2.0-holoverse-native"
GAME_NAME = "HoloVerse Observatory"

def _user_data_root() -> Path:
    """Glitched Matrix standard user-data folder (Windows %LOCALAPPDATA%\\GLITCHED MATRIX\\HoloShell).
    HOLOSHELL_USER_DATA overrides it.  The game folder itself is never written."""
    override = str(os.environ.get("HOLOSHELL_USER_DATA") or "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = str(os.environ.get("LOCALAPPDATA") or "").strip()
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "GLITCHED MATRIX" / "HoloShell"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "GLITCHED MATRIX" / "HoloShell"
    xdg = str(os.environ.get("XDG_DATA_HOME") or "").strip()
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / "glitched-matrix" / "holoshell"

ROOT = Path(__file__).resolve().parent
USER_DATA_DIR = _user_data_root()
ASSETS = ROOT / "assets"
SHIPPED_CONFIG_DIR = ASSETS / "config"
CONFIG_DIR = USER_DATA_DIR / "settings"
LOG_DIR = USER_DATA_DIR / "logs"
SCREENSHOT_DIR = LOG_DIR / "screenshots"
PATCH_DIR = LOG_DIR
CONFIG_PATH = CONFIG_DIR / "holoverse_config.json"
TEXTURE_DIR = ASSETS / "generated_hub_textures"
LATEST_LOG = LOG_DIR / "latest.log"
CRASH_LOG = LOG_DIR / "crash.log"
LATEST_PATCH = PATCH_DIR / "latest_patch_notes.txt"
LATEST_SHOT = SCREENSHOT_DIR / "latest_command_hub.png"
SELF_TEST_REPORT = LOG_DIR / "self_test_report.json"

MODE_FOLDER_NAMES = ("HoloVerse", "Holoverse")


def _candidate_roots():
    roots = []
    seen = set()

    def add(path):
        try:
            path = Path(path).resolve()
        except Exception:
            return
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            roots.append(path)

    add(ROOT)
    add(ROOT.parent)
    add(ROOT.parent / "games")
    add(ROOT.parent / "games" / "HoloVerse")
    add(ROOT.parent / "games" / "Holoverse")
    add(ROOT.parent.parent)
    add(ROOT.parent.parent / "games")
    add(ROOT.parent.parent / "games" / "HoloVerse")
    add(ROOT.parent.parent / "games" / "Holoverse")
    add(Path.cwd())
    for base in list(roots):
        for folder_name in MODE_FOLDER_NAMES:
            add(base / folder_name)
            add(base / "games" / folder_name)
    return roots


SEARCH_ROOTS = _candidate_roots()


def mode_main_candidates(mode_name: str):
    candidates = []
    seen = set()

    def add(path):
        try:
            path = Path(path).resolve()
        except Exception:
            return
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            candidates.append(path)

    for base in SEARCH_ROOTS:
        add(base / mode_name / "main.py")
        add(base / "games" / mode_name / "main.py")
        for folder_name in MODE_FOLDER_NAMES:
            add(base / folder_name / mode_name / "main.py")
            add(base / "games" / folder_name / mode_name / "main.py")

    add(ROOT / mode_name / "main.py")
    add(ROOT.parent / mode_name / "main.py")
    add(ROOT.parent / "games" / mode_name / "main.py")
    add(Path("/mnt/data/games/HoloVerse") / mode_name / "main.py")
    add(Path("/mnt/data/games/Holoverse") / mode_name / "main.py")
    add(Path("/mnt/data/patch_unzipped/games/HoloVerse") / mode_name / "main.py")
    add(Path("/mnt/data/patch_unzipped/games/Holoverse") / mode_name / "main.py")
    return candidates


VECTOR_WARS_CANDIDATES = mode_main_candidates("Vector Wars")
VECTOR_CONQUEST_CANDIDATES = mode_main_candidates("Vector Conquest")
CAMPAIGN_CANDIDATES = mode_main_candidates("Holo Campaign")


def first_existing_path(candidates):
    for c in candidates:
        try:
            cp = Path(c)
            if cp.exists():
                return cp
        except Exception:
            pass
    return None


@dataclass
class ObservatoryConfig:
    mouse_sensitivity: float = 0.11
    controller_look_sensitivity: float = 110.0
    walk_speed: float = 10.0
    sprint_speed: float = 16.0
    line_thickness: float = 1.9
    line_hue: float = 0.57
    line_saturation: float = 0.72
    line_value: float = 1.0
    background_value: float = 0.018
    fov: float = 82.0
    fog_distance: float = 620.0
    hud_visible: bool = True
    terrain_chunk_size: float = 56.0
    terrain_render_radius: int = 4
    terrain_grid_step: float = 8.0
    terrain_height: float = 15.0
    safe_flat_radius: float = 42.0
    transition_duration: float = 4.6
    world_seed: int = 10457
    hub_fill_enabled: bool = False
    hub_fill_opacity: float = 0.72
    player_eye_height: float = 2.52
    master_volume: float = 0.82
    sfx_volume: float = 0.82
    music_volume: float = 0.42
    ambience_volume: float = 0.58
    launch_width: int = 1920
    launch_height: int = 1080
    launch_fullscreen: bool = False
    launch_borderless: bool = False
    launch_game_mouse_sensitivity: float = 0.22
    launch_invert_y: bool = False
    launch_hud_visible: bool = True
    launch_graphics_quality: str = "medium"
    launch_controller_deadzone: float = 0.12


DEFAULT_CONFIG = ObservatoryConfig()


def ensure_dirs():
    for p in [ASSETS, CONFIG_DIR, TEXTURE_DIR, LOG_DIR, SCREENSHOT_DIR, PATCH_DIR]:
        p.mkdir(parents=True, exist_ok=True)


class TeeLogger:
    def __init__(self, path: Path):
        self.file = path.open("w", encoding="utf-8")

    def write(self, text: str):
        self.file.write(text)
        self.file.flush()
        sys.__stdout__.write(text)
        sys.__stdout__.flush()

    def flush(self):
        self.file.flush()
        sys.__stdout__.flush()


def install_logging():
    ensure_dirs()
    logger = TeeLogger(LATEST_LOG)
    sys.stdout = logger
    sys.stderr = logger


def install_crash_reporter():
    def _hook(exc_type, exc, tb):
        ensure_dirs()
        with CRASH_LOG.open("w", encoding="utf-8") as f:
            f.write(f"{GAME_NAME} {VERSION}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")
            traceback.print_exception(exc_type, exc, tb, file=f)
        traceback.print_exception(exc_type, exc, tb)

    sys.excepthook = _hook


def write_patch_notes():
    ensure_dirs()
    note = textwrap.dedent(
        f"""
        {GAME_NAME}
        Version: {VERSION}
        Generated: {datetime.now().isoformat()}

        Patch Notes
        - Upgraded biome dressing so world chunks build with stronger 3D geometric silhouettes instead of reading like plain line terrains.
        - Added sparse per-world creature families with rare solo spawns, size variation, and simple ambient motion for frontier, venus, space, underwater, and jungle zones.
        - Added geometric environmental set dressing such as crystal clusters, coral forms, canopy pods, and void structures to improve depth and theme identity.
        - Tuned world screenshot staging so artifact self-tests frame the upgraded worlds more clearly.
        - Preserved path discovery, settings, HUD, launch payload sharing, logging, screenshots, and built-in Campaign / Conquest transitions.
        """
    ).strip()
    LATEST_PATCH.write_text(note + "\n", encoding="utf-8")


def load_config(write_back: bool = True) -> ObservatoryConfig:
    ensure_dirs()
    source = CONFIG_PATH if CONFIG_PATH.exists() else SHIPPED_CONFIG_DIR / CONFIG_PATH.name
    if source.exists():
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
            merged = asdict(DEFAULT_CONFIG)
            merged.update({k: v for k, v in data.items() if k in merged})
            cfg = ObservatoryConfig(**merged)
        except Exception:
            cfg = DEFAULT_CONFIG
    else:
        cfg = DEFAULT_CONFIG
    if write_back:
        save_config(cfg)
        write_audio_bus(cfg)
        write_shared_launch_settings(cfg)
    return cfg


def save_config(cfg: ObservatoryConfig):
    ensure_dirs()
    CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
    write_audio_bus(cfg)
    write_shared_launch_settings(cfg)



def build_audio_bus_payload(cfg: ObservatoryConfig):
    return {
        "master_volume": round(max(0.0, min(1.0, cfg.master_volume)), 3),
        "sfx_volume": round(max(0.0, min(1.0, cfg.sfx_volume)), 3),
        "music_volume": round(max(0.0, min(1.0, cfg.music_volume)), 3),
        "ambience_volume": round(max(0.0, min(1.0, cfg.ambience_volume)), 3),
    }


def build_launch_settings_payload(cfg: ObservatoryConfig):
    quality = str(cfg.launch_graphics_quality).lower().strip()
    if quality not in {"low", "medium", "high"}:
        quality = "medium"
    return {
        "width": int(max(1280, min(3840, cfg.launch_width))),
        "height": int(max(720, min(2160, cfg.launch_height))),
        "fullscreen": bool(cfg.launch_fullscreen),
        "borderless": bool(cfg.launch_borderless),
        "mouse_sensitivity": round(max(0.02, min(1.0, cfg.launch_game_mouse_sensitivity)), 3),
        "invert_y": bool(cfg.launch_invert_y),
        "hud_visible": bool(cfg.launch_hud_visible),
        "graphics_quality": quality,
        "controller_deadzone": round(max(0.0, min(0.45, cfg.launch_controller_deadzone)), 3),
    }


def write_shared_launch_settings(cfg: ObservatoryConfig) -> Path:
    ensure_dirs()
    path = CONFIG_DIR / "holoverse_shared_settings.json"
    path.write_text(json.dumps(build_launch_settings_payload(cfg), indent=2), encoding="utf-8")
    return path


def write_audio_bus(cfg: ObservatoryConfig) -> Path:
    ensure_dirs()
    path = CONFIG_DIR / "holoverse_audio_bus.json"
    path.write_text(json.dumps(build_audio_bus_payload(cfg), indent=2), encoding="utf-8")
    return path


def hsv_color(h: float, s: float, v: float, a: float = 1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return (r, g, b, a)




WORLD_SPECS = {
    0: {"name": "Frontier Lens", "kind": "frontier", "bg": (0.018, 0.018, 0.022), "hub": (0.90, 0.97, 1.0)},
    1: {"name": "Signal Bastion", "kind": "frontier", "bg": (0.020, 0.018, 0.026), "hub": (0.96, 0.78, 0.92)},
    2: {"name": "Aether Reach", "kind": "frontier", "bg": (0.018, 0.020, 0.025), "hub": (0.80, 0.90, 1.0)},
    3: {"name": "Ruin Meridian", "kind": "frontier", "bg": (0.020, 0.018, 0.020), "hub": (0.98, 0.84, 0.76)},
    4: {"name": "Venus Lens", "kind": "venus", "bg": (0.17, 0.07, 0.03), "hub": (1.0, 0.60, 0.28)},
    5: {"name": "Void Fleet Lens", "kind": "space", "bg": (0.01, 0.015, 0.05), "hub": (0.55, 0.72, 1.0)},
    6: {"name": "Aqua Abyss Lens", "kind": "underwater", "bg": (0.01, 0.10, 0.16), "hub": (0.30, 0.96, 0.88)},
    7: {"name": "Verdant Canopy Lens", "kind": "jungle", "bg": (0.03, 0.09, 0.04), "hub": (0.56, 0.96, 0.52)},
    8: {"name": "Campaign Merge", "kind": "campaign", "bg": (0.96, 0.96, 0.96), "hub": (0.12, 0.12, 0.12)},
    9: {"name": "Conquest Merge", "kind": "conquest", "bg": (0.08, 0.05, 0.04), "hub": (1.0, 0.62, 0.36)},
}


class WorldActor:
    def __init__(self, root, kind, seed, home):
        self.root = root
        self.kind = kind
        self.seed = seed
        self.home = Vec3(home)
        self.phase = random.Random(seed).random() * math.tau
        self.follow_timer = 0.0
        self.health = 100.0
        self.team = "neutral"
        self.speed = 0.0


@dataclass
class WorldProjectile:
    node: object
    velocity: Vec3
    ttl: float
    damage: float
    team: str


@dataclass
class InternalModeState:
    mode_key: str = ""
    fire_down: bool = False
    weapon_cooldown: float = 0.0
    player_health: float = 100.0
    capture_energy: float = 0.0
    ammo: float = 100.0
    score: int = 0
    objective: str = ""
    last_hit_flash: float = 0.0
    projectiles: list = field(default_factory=list)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_rgb(a, b, t):
    return tuple(lerp(a[i], b[i], t) for i in range(3))


class CommandHubApp(ShowBase):
    def __init__(self, host_base=None, hosted: bool = False):
        ensure_dirs()
        self._holoverse_hosted = bool(hosted and host_base is not None)
        self._holoverse_host = host_base if self._holoverse_hosted else None
        self._holoverse_runtime_settings = self._host_runtime_settings(host_base) if self._holoverse_hosted else dict(HOLOVERSE_RUNTIME_SETTINGS)
        self.holoverse_runtime_contract = dict(self._holoverse_runtime_settings)
        self._hosted_elapsed = 0.0
        self._hosted_destroyed = False
        if self._holoverse_hosted:
            self._bind_host_showbase(host_base)
        else:
            super().__init__()
            self.disableMouse()
        self.clock = ClockObject.getGlobalClock()
        if not self._holoverse_hosted:
            if self._holoverse_runtime_settings.get("hosted_contract", False):
                try:
                    self.clock.setMode(ClockObject.MLimited)
                    self.clock.setFrameRate(float(self._holoverse_runtime_settings.get("fps_cap", 60)))
                except Exception:
                    self.clock.setMode(ClockObject.MNormal)
            else:
                self.clock.setMode(ClockObject.MNormal)
        self.cfg = load_config(write_back=not self._holoverse_hosted)
        self.apply_host_runtime_settings()
        self.elapsed = 0.0
        self.menu_open = False
        self.hud_visible = self.cfg.hud_visible
        self.keys = getattr(host_base, "keys", {}) if self._holoverse_hosted else {}
        self.gamepad = getattr(host_base, "gamepad", None) if self._holoverse_hosted else None
        self.player_pos = Vec3(0, -10, self.cfg.player_eye_height)
        self.player_yaw = 0.0
        self.player_pitch = -7.0
        self.move_velocity = Vec2(0, 0)
        self.room_bounds = []
        self.hub_radius = 30.0
        self.artifact_radius = 22.8
        self.active_artifact = None
        self.active_artifact_id = None
        self.world_unlocked = False
        self.transition_progress = 0.0
        self.transition_target = 0.0
        self.terrain_chunks = {}
        self.artifacts = []
        self.galaxy_nodes = []
        self.nearest_artifact = None
        self.nearest_artifact_dist = 999.0
        self.base_teleport = Vec3(0, -10, self.cfg.player_eye_height)
        self.hub_fill_nodes = []
        self.hub_fill_alpha = 1.0 if self.cfg.hub_fill_enabled else 0.0
        self.hub_fill_target = self.hub_fill_alpha
        self.hub_textures = {}
        self.world_actors = []
        self.last_world_kind = "frontier"
        self.world_theme_blend = 0.0
        self.default_hub_rgb = (0.94, 0.96, 1.0)
        self.current_hub_rgb = self.default_hub_rgb
        self.current_bg_rgb = (self.cfg.background_value, self.cfg.background_value, self.cfg.background_value)
        self.vector_wars_path = first_existing_path(VECTOR_WARS_CANDIDATES)
        self.vector_conquest_path = first_existing_path(VECTOR_CONQUEST_CANDIDATES)
        self.campaign_path = first_existing_path(CAMPAIGN_CANDIDATES)
        self.core_console_open = False
        self.external_process = None
        self.underwater_vehicle_root = None
        self.underwater_vehicle_color = (0.30, 0.96, 0.88, 0.96)
        self.internal_mode = InternalModeState()
        self.pending_internal_mode = ""
        self.mode_build_stamp = 0.0

        if not self._holoverse_hosted:
            self.setup_window()
        self.setup_scene()
        self.setup_ui()
        if not self._holoverse_hosted:
            self.setup_input()
            self.setup_gamepad()
        self.apply_host_runtime_settings()
        self.ensure_hub_textures()
        self.rebuild_station()
        self.refresh_ui()
        self.camera.setPos(self.player_pos)
        self.camera.setHpr(self.player_yaw, self.player_pitch, 0)
        if not self._holoverse_hosted:
            self.accept("window-event", self.on_window_event)
            self.taskMgr.add(self.update_task, "update-task")
        if SELF_TEST and not self._holoverse_hosted:
            self.taskMgr.doMethodLater(0.8, self.self_test_setup, "self-test-setup")
            self.taskMgr.doMethodLater(1.7, self.capture_latest_screenshot, "self-test-shot")
            self.taskMgr.doMethodLater(2.1, self.self_test_exit, "self-test-exit")
        elif not self._holoverse_hosted:
            self.recenter_mouse(force=True)
            if AUTO_SHOT:
                self.taskMgr.doMethodLater(1.5, self.capture_latest_screenshot, "auto-shot")
            if AUTO_EXIT:
                self.taskMgr.doMethodLater(2.0, self.self_test_exit, "auto-exit")

    @staticmethod
    def _host_runtime_settings(host) -> dict:
        cfg = getattr(host, "cfg", None)
        if cfg is None:
            data = dict(HOLOVERSE_RUNTIME_SETTINGS)
            data["hosted_contract"] = True
            data["native_inprocess"] = True
            return data
        data = dict(HOLOVERSE_RUNTIME_SETTINGS)
        data.update({
            "hosted_contract": True,
            "native_inprocess": True,
            "width": int(getattr(cfg, "launch_width", data.get("width", 1920))),
            "height": int(getattr(cfg, "launch_height", data.get("height", 1080))),
            "fullscreen": bool(getattr(cfg, "launch_fullscreen", False)),
            "borderless": bool(getattr(cfg, "launch_borderless", False)),
            "bordered_fullscreen": bool(getattr(cfg, "launch_bordered_fullscreen", True)),
            "vsync": bool(getattr(cfg, "launch_vsync", True)),
            "fps_cap": int(getattr(cfg, "launch_fps_cap", 60)),
            "ui_scale": float(getattr(cfg, "launch_ui_scale", 1.0)),
            "render_scale": float(getattr(cfg, "launch_render_scale", 1.0)),
            "hud_visible": bool(getattr(cfg, "launch_hud_visible", getattr(cfg, "hud_visible", True))),
            "subtitles_enabled": bool(getattr(cfg, "launch_subtitles_enabled", True)),
            "mouse_sensitivity": float(getattr(cfg, "launch_game_mouse_sensitivity", getattr(cfg, "mouse_sensitivity", 0.22))),
            "invert_y": bool(getattr(cfg, "launch_invert_y", False)),
            "controller_deadzone": float(getattr(cfg, "launch_controller_deadzone", 0.12)),
            "brightness": float(getattr(cfg, "launch_brightness", 1.0)),
            "contrast": float(getattr(cfg, "launch_contrast", 1.0)),
            "gamma": float(getattr(cfg, "launch_gamma", 1.0)),
            "graphics_quality": str(getattr(cfg, "launch_graphics_quality", "medium") or "medium").lower(),
            "master_volume": float(getattr(cfg, "master_volume", 1.0)),
            "music_volume": float(getattr(cfg, "music_volume", 1.0)),
            "sfx_volume": float(getattr(cfg, "sfx_volume", 1.0)),
            "ambience_volume": float(getattr(cfg, "ambience_volume", 1.0)),
        })
        try:
            if getattr(host, "win", None) is not None:
                props = host.win.getProperties()
                origin = props.getOrigin() if hasattr(props, "getOrigin") else None
                if origin is not None:
                    data["window_x"], data["window_y"] = int(origin.x), int(origin.y)
                data["width"], data["height"] = int(host.win.getXSize()), int(host.win.getYSize())
        except Exception:
            pass
        return data

    def _bind_host_showbase(self, host) -> None:
        required = ("render", "render2d", "aspect2d", "camera", "camLens", "loader", "taskMgr", "mouseWatcherNode", "win")
        missing = [name for name in required if not hasattr(host, name)]
        if missing:
            raise RuntimeError("HoloVerse host missing ShowBase fields: " + ", ".join(missing))
        for name in required + ("pixel2d", "cam", "graphicsEngine", "pipe", "devices"):
            if hasattr(host, name):
                setattr(self, name, getattr(host, name))

    def apply_host_runtime_settings(self) -> None:
        settings = dict(getattr(self, "_holoverse_runtime_settings", HOLOVERSE_RUNTIME_SETTINGS) or {})
        self.holoverse_runtime_contract = dict(settings)
        if not hasattr(self, "cfg"):
            return
        self.cfg.launch_width = int(settings.get("width", self.cfg.launch_width))
        self.cfg.launch_height = int(settings.get("height", self.cfg.launch_height))
        self.cfg.launch_fullscreen = bool(settings.get("fullscreen", self.cfg.launch_fullscreen))
        self.cfg.launch_borderless = bool(settings.get("borderless", self.cfg.launch_borderless))
        self.cfg.launch_game_mouse_sensitivity = float(settings.get("mouse_sensitivity", self.cfg.launch_game_mouse_sensitivity))
        self.cfg.launch_invert_y = bool(settings.get("invert_y", self.cfg.launch_invert_y))
        self.cfg.launch_graphics_quality = str(settings.get("graphics_quality", self.cfg.launch_graphics_quality))
        self.cfg.launch_controller_deadzone = float(settings.get("controller_deadzone", self.cfg.launch_controller_deadzone))
        self.cfg.mouse_sensitivity = float(settings.get("mouse_sensitivity", self.cfg.mouse_sensitivity))
        self.cfg.master_volume = float(settings.get("master_volume", self.cfg.master_volume))
        self.cfg.music_volume = float(settings.get("music_volume", self.cfg.music_volume))
        self.cfg.sfx_volume = float(settings.get("sfx_volume", self.cfg.sfx_volume))
        self.cfg.ambience_volume = float(settings.get("ambience_volume", self.cfg.ambience_volume))
        self._controller_deadzone = float(settings.get("controller_deadzone", 0.12))
        self._invert_y = bool(settings.get("invert_y", False))
        # Hosted HoloShell keeps its own HUD visibility and authored UI scale.
        # Host settings no longer rescale/hide its interactive UI.
        self._ui_scale = 1.0
        scene = getattr(self, "root_3d", None)
        if scene is not None:
            try:
                if str(settings.get("graphics_quality", "medium")).lower() == "low":
                    scene.clearAntialias()
                else:
                    scene.setAntialias(AntialiasAttrib.MLine)
            except Exception:
                pass

    def setup_window(self):
        settings = dict(getattr(self, "_holoverse_runtime_settings", HOLOVERSE_RUNTIME_SETTINGS) or {})
        props = WindowProperties()
        props.setTitle("HoloVerse // HoloShell" if settings.get("hosted_contract") else GAME_NAME)
        props.setSize(int(settings.get("width", 1920)), int(settings.get("height", 1080)))
        props.setCursorHidden(not SELF_TEST)
        if settings.get("hosted_contract"):
            borderless = bool(settings.get("borderless", False))
            bordered_fullscreen = bool(settings.get("bordered_fullscreen", False))
            props.setOrigin(int(settings.get("window_x", 0)), int(settings.get("window_y", 0)))
            props.setFullscreen(bool(settings.get("fullscreen", False)) and not borderless and not bordered_fullscreen)
            props.setUndecorated(borderless)
            props.setFixedSize(bool(borderless))
        if self.win is not None and hasattr(self.win, "requestProperties"):
            self.win.requestProperties(props)
        self.setBackgroundColor(self.cfg.background_value, self.cfg.background_value, self.cfg.background_value)

    def setup_scene(self):
        self.root_3d = self.render.attachNewNode("holoshell-root-3d")
        self.root_3d.setAntialias(AntialiasAttrib.MLine)
        self.root_3d.setTransparency(TransparencyAttrib.MAlpha)
        self.surface_root = self.root_3d.attachNewNode("surface-root")
        self.line_root = self.root_3d.attachNewNode("line-root")
        self.accent_root = self.root_3d.attachNewNode("accent-root")
        self.dome_root = self.root_3d.attachNewNode("dome-root")
        self.lens_root = self.root_3d.attachNewNode("lens-root")
        self.sky_root = self.root_3d.attachNewNode("sky-root")
        self.world_root = self.root_3d.attachNewNode("world-root")
        self.galaxy_root = self.root_3d.attachNewNode("galaxy-root")
        self.world_root.setTransparency(TransparencyAttrib.MAlpha)
        self.galaxy_root.setTransparency(TransparencyAttrib.MAlpha)
        self.camLens.setNearFar(0.05, self.cfg.fog_distance)
        self.camLens.setFov(self.cfg.fov)

        self.fog = Fog("hub-fog")
        self.fog.setColor(self.cfg.background_value, self.cfg.background_value, self.cfg.background_value)
        self.fog.setLinearRange(self.cfg.fog_distance * 0.48, self.cfg.fog_distance)
        self.root_3d.setFog(self.fog)

        ambient = AmbientLight("holoshell-ambient")
        ambient.setColor((0.58, 0.62, 0.68, 1.0))
        ambient_np = self.root_3d.attachNewNode(ambient)
        self.root_3d.setLight(ambient_np)

        dlight = DirectionalLight("holoshell-sun")
        dlight.setColor((0.34, 0.37, 0.42, 1.0))
        dnp = self.root_3d.attachNewNode(dlight)
        dnp.setHpr(-20, -48, 0)
        self.root_3d.setLight(dnp)

    def make_generated_texture(self, name: str, width: int, height: int, painter):
        path = TEXTURE_DIR / name
        if not path.exists():
            img = PNMImage(width, height, 4)
            painter(img, width, height)
            img.write(Filename.fromOsSpecific(str(path)))
        tex = self.loader.loadTexture(Filename.fromOsSpecific(str(path)))
        if tex:
            tex.setWrapU(SamplerState.WM_repeat)
            tex.setWrapV(SamplerState.WM_repeat)
            tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
            tex.setMagfilter(SamplerState.FT_linear)
        return tex

    def ensure_hub_textures(self):
        def floor_painter(img, w, h):
            for y in range(h):
                for x in range(w):
                    grid = 0.50 if x % 32 in (0, 1, 30, 31) or y % 32 in (0, 1, 30, 31) else 0.0
                    wave = 0.08 + 0.04 * math.sin((x + y) * 0.045)
                    v = wave + grid
                    img.setXelA(x, y, 0.08 + v * 0.28, 0.12 + v * 0.34, 0.16 + v * 0.42, 1.0)

        def wall_painter(img, w, h):
            for y in range(h):
                for x in range(w):
                    pillars = 0.46 if x % 56 in (0, 1, 2, 53, 54, 55) else 0.0
                    rails = 0.22 if y % 72 in (0, 1, 70, 71) else 0.0
                    wave = 0.05 + 0.03 * math.sin(x * 0.025 + y * 0.012)
                    v = wave + pillars + rails
                    img.setXelA(x, y, 0.06 + v * 0.26, 0.10 + v * 0.34, 0.14 + v * 0.44, 1.0)

        def core_painter(img, w, h):
            cx, cy = w * 0.5, h * 0.5
            for y in range(h):
                for x in range(w):
                    dx = (x - cx) / max(1.0, cx)
                    dy = (y - cy) / max(1.0, cy)
                    dist = math.sqrt(dx * dx + dy * dy)
                    rings = 0.45 if int(dist * 18) % 2 == 0 else 0.12
                    cross = 0.35 if abs(dx) < 0.04 or abs(dy) < 0.04 else 0.0
                    v = max(0.0, 1.0 - dist) * 0.24 + rings + cross
                    img.setXelA(x, y, 0.08 + v * 0.32, 0.12 + v * 0.40, 0.18 + v * 0.48, 1.0)

        def ceiling_painter(img, w, h):
            cx, cy = w * 0.5, h * 0.5
            for y in range(h):
                for x in range(w):
                    dx = (x - cx) / max(1.0, cx)
                    dy = (y - cy) / max(1.0, cy)
                    ang = (math.atan2(dy, dx) + math.pi) / (math.tau)
                    sector = 0.34 if int(ang * 8) % 2 == 0 else 0.12
                    ring = 0.18 if abs(math.sqrt(dx * dx + dy * dy) - 0.68) < 0.05 else 0.0
                    v = 0.06 + sector + ring
                    img.setXelA(x, y, 0.05 + v * 0.22, 0.09 + v * 0.30, 0.13 + v * 0.40, 1.0)

        def dome_painter(img, w, h):
            for y in range(h):
                for x in range(w):
                    diag = 0.42 if (x - y) % 72 in (0, 1, 2, 69, 70, 71) or (x + y) % 72 in (0, 1, 2, 69, 70, 71) else 0.0
                    rib = 0.24 if x % 90 in (0, 1, 88, 89) else 0.0
                    v = 0.06 + diag + rib
                    img.setXelA(x, y, 0.05 + v * 0.20, 0.09 + v * 0.28, 0.14 + v * 0.36, 1.0)

        self.hub_textures = {
            "floor": self.make_generated_texture("hub_floor.png", 512, 512, floor_painter),
            "wall": self.make_generated_texture("hub_wall.png", 512, 512, wall_painter),
            "core": self.make_generated_texture("hub_core.png", 512, 512, core_painter),
            "ceiling": self.make_generated_texture("hub_ceiling.png", 512, 512, ceiling_painter),
            "dome": self.make_generated_texture("hub_dome.png", 512, 512, dome_painter),
        }

    def add_textured_panel(self, parent, pos, hpr, sx, sy, texture_key, alpha=0.0, tex_scale=(1.0, 1.0), two_sided=True):
        cm = CardMaker(f"panel-{texture_key}")
        cm.setFrame(-sx * 0.5, sx * 0.5, -sy * 0.5, sy * 0.5)
        np = parent.attachNewNode(cm.generate())
        np.setPos(pos)
        np.setHpr(hpr)
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setColor(1, 1, 1, alpha)
        np.setDepthWrite(False)
        if two_sided:
            np.setTwoSided(True)
        tex = self.hub_textures.get(texture_key)
        if tex:
            np.setTexture(tex, 1)
            np.setTexScale(TextureStage.getDefault(), tex_scale[0], tex_scale[1])
        self.hub_fill_nodes.append(np)
        return np

    def build_hub_infill(self):
        self.hub_fill_nodes = []
        self.add_textured_panel(self.surface_root, Vec3(0, 0, 0.02), Vec3(0, -90, 0), 56.0, 56.0, "floor", tex_scale=(4.8, 4.8))

        wall_height = 9.2
        wall_width = 21.4
        wall_r = self.hub_radius - 0.98
        for i in range(8):
            ang = math.radians(22.5) + math.tau * i / 8
            n = Vec3(math.cos(ang), math.sin(ang), 0)
            pos = n * wall_r + Vec3(0, 0, wall_height * 0.5)
            self.add_textured_panel(self.surface_root, pos, Vec3(math.degrees(ang) + 90, 0, 0), wall_width, wall_height, "wall", tex_scale=(2.2, 1.6))

        for i in range(8):
            ang = math.radians(22.5) + math.tau * i / 8
            n = Vec3(math.cos(ang), math.sin(ang), 0)
            pos = n * 2.05 + Vec3(0, 0, 3.2)
            self.add_textured_panel(self.surface_root, pos, Vec3(math.degrees(ang) + 90, 0, 0), 1.55, 5.9, "core", tex_scale=(1.0, 2.0))

        self.add_textured_panel(self.surface_root, Vec3(0, 0, 10.02), Vec3(0, 90, 22.5), 31.8, 31.8, "ceiling", tex_scale=(2.0, 2.0))

        dome_bands = [(24.0, 9.8, 12.4), (20.0, 12.0, 14.7), (15.0, 14.2, 16.8)]
        for width, z0, z1 in dome_bands:
            pitch = -24.0 - (z0 - 9.8) * 1.85
            radius = self.hub_radius - 3.2 - (z0 - 9.8) * 0.7
            for i in range(8):
                ang = math.radians(22.5) + math.tau * i / 8
                n = Vec3(math.cos(ang), math.sin(ang), 0)
                pos = n * radius + Vec3(0, 0, (z0 + z1) * 0.5)
                self.add_textured_panel(self.surface_root, pos, Vec3(math.degrees(ang) + 90, pitch, 0), width, z1 - z0, "dome", tex_scale=(2.0, 1.0))
        self.update_hub_fill_visuals(force=True)

    def set_hub_fill_enabled(self, enabled: bool, instant=False):
        self.cfg.hub_fill_enabled = enabled
        self.hub_fill_target = 1.0 if enabled else 0.0
        if instant:
            self.hub_fill_alpha = self.hub_fill_target
            self.update_hub_fill_visuals(force=True)
        save_config(self.cfg)

    def update_hub_fill_visuals(self, force=False):
        alpha = self.hub_fill_alpha * self.cfg.hub_fill_opacity
        for np in getattr(self, "hub_fill_nodes", []):
            np.setColorScale(1, 1, 1, alpha)
            if alpha > 0.001:
                np.show()
            else:
                np.hide()

    def is_near_core(self):
        return math.sqrt(self.player_pos.x ** 2 + self.player_pos.y ** 2) < 6.8

    def open_core_console(self):
        self.core_console_open = True
        self.core_console_root.show()
        self.center_hint["text"] = "CORE // SELECT 1 CAMPAIGN MERGE  2 VECTOR WARS  3 CONQUEST MERGE  5 INFILL"

    def close_core_console(self):
        self.core_console_open = False
        self.core_console_root.hide()

    def launch_external_level(self, path: Path, label: str):
        if path is None or not Path(path).exists():
            self.center_hint["text"] = f"CORE // {label} MISSING"
            return
        try:
            audio_bus_path = write_audio_bus(self.cfg)
            launch_settings_path = write_shared_launch_settings(self.cfg)
            env = os.environ.copy()
            env["MATRIX_AUDIO_CONFIG"] = os.fspath(audio_bus_path)
            env["MATRIX_LAUNCH_SETTINGS"] = os.fspath(launch_settings_path)
            payload = build_audio_bus_payload(self.cfg)
            launch_payload = build_launch_settings_payload(self.cfg)
            env["MATRIX_MASTER_VOLUME"] = str(payload["master_volume"])
            env["MATRIX_SFX_VOLUME"] = str(payload["sfx_volume"])
            env["MATRIX_MUSIC_VOLUME"] = str(payload["music_volume"])
            env["MATRIX_AMBIENCE_VOLUME"] = str(payload["ambience_volume"])
            env["MATRIX_GAME_WIDTH"] = str(launch_payload["width"])
            env["MATRIX_GAME_HEIGHT"] = str(launch_payload["height"])
            env["MATRIX_GAME_FULLSCREEN"] = "1" if launch_payload["fullscreen"] else "0"
            env["MATRIX_GAME_BORDERLESS"] = "1" if launch_payload["borderless"] else "0"
            env["MATRIX_GAME_MOUSE_SENSITIVITY"] = str(launch_payload["mouse_sensitivity"])
            env["MATRIX_GAME_INVERT_Y"] = "1" if launch_payload["invert_y"] else "0"
            env["MATRIX_GAME_HUD_VISIBLE"] = "1" if launch_payload["hud_visible"] else "0"
            env["MATRIX_GAME_GRAPHICS_QUALITY"] = str(launch_payload["graphics_quality"])
            env["MATRIX_GAME_CONTROLLER_DEADZONE"] = str(launch_payload["controller_deadzone"])
            env["MATRIX_LAUNCHER_NAME"] = GAME_NAME
            self.external_process = subprocess.Popen([sys.executable, os.fspath(path)], cwd=os.fspath(Path(path).parent), env=env)
            self.center_hint["text"] = f"CORE // {label} OPENED"
        except Exception:
            self.center_hint["text"] = f"CORE // {label} FAILED"

    def interact(self):
        if self.is_near_core():
            self.open_core_console()
            return
        self.activate_nearest_artifact()

    def core_secondary_action(self):
        if self.is_near_core():
            self.open_core_console()
            return
        self.activate_nearest_artifact()

    def sync_core(self):
        try:
            save_config(self.cfg)
        except Exception:
            pass
        try:
            write_audio_bus(self.cfg)
        except Exception:
            pass
        try:
            write_shared_launch_settings(self.cfg)
        except Exception:
            pass
        self.refresh_ui()

    def activate_internal_mode(self, mode_key: str):
        if mode_key == "campaign":
            self.active_artifact = {"id": 8, "name": WORLD_SPECS[8]["name"], "yaw": 168.0, "pitch": 11.0, "radius": 0.0}
            self.active_artifact_id = 8
            self.player_pos = Vec3(0, 18, self.cfg.player_eye_height + 0.15)
            self.player_yaw = 180.0
            self.player_pitch = -7.0
            self.internal_mode = InternalModeState(mode_key="campaign", player_health=100.0, ammo=100.0, capture_energy=0.0, objective="ETCHLINE BREACH // collapse hostile pylons")
        elif mode_key == "conquest":
            self.active_artifact = {"id": 9, "name": WORLD_SPECS[9]["name"], "yaw": 156.0, "pitch": 10.0, "radius": 0.0}
            self.active_artifact_id = 9
            self.player_pos = Vec3(0, 16, self.cfg.player_eye_height + 0.15)
            self.player_yaw = 180.0
            self.player_pitch = -8.0
            self.internal_mode = InternalModeState(mode_key="conquest", player_health=140.0, ammo=160.0, capture_energy=0.0, objective="ASHFALL PUSH // clear raiders and charge relay")
        else:
            return
        self.close_core_console()
        self.sync_core()
        self.transition_target = 1.0
        self.world_unlocked = True
        self.clear_world_chunks()
        self.camera.setPos(self.player_pos)
        self.camera.setHpr(self.player_yaw, self.player_pitch, 0)
        self.set_hub_fill_enabled(True, instant=True)
        self.refresh_ui()

    def core_launch_campaign(self):
        if self.is_near_core():
            self.activate_internal_mode("campaign")

    def core_launch_vector_wars(self):
        if self.is_near_core() and self.vector_wars_path is not None:
            self.close_core_console()
            self.sync_core()
            self.launch_external_level(self.vector_wars_path, "VECTOR WARS")

    def core_launch_vector_conquest(self):
        if self.is_near_core():
            self.activate_internal_mode("conquest")

    def core_toggle_infill(self):
        if self.is_near_core():
            self.close_core_console()
            self.set_hub_fill_enabled(not self.cfg.hub_fill_enabled)
            self.center_hint["text"] = "CORE // INFILL ON" if self.cfg.hub_fill_enabled else "CORE // INFILL OFF"

    def setup_ui(self):
        self.menu_tab = "display"
        self.menu_actions = []
        self.hud_root = self.aspect2d.attachNewNode("hud-root")
        self.top_panel = DirectFrame(parent=self.hud_root, frameColor=(0.01, 0.01, 0.012, 0.78), frameSize=(-0.26, 0.20, -0.06, 0.06), pos=(-1.06, 0, 0.92))
        self.hud_label = DirectLabel(parent=self.top_panel, text="", text_align=TextNode.ALeft, text_scale=0.030, text_fg=(0.95, 0.97, 1.0, 1.0), frameColor=(0, 0, 0, 0), pos=(-0.23, 0, 0.0), textMayChange=True)
        self.center_hint = DirectLabel(parent=self.hud_root, text="", text_align=TextNode.ACenter, text_scale=0.043, text_fg=(0.96, 0.30, 0.34, 0.95), frameColor=(0, 0, 0, 0), pos=(0, 0, -0.80), textMayChange=True)
        self.coords_label = DirectLabel(parent=self.hud_root, text="", text_align=TextNode.ALeft, text_scale=0.028, text_fg=(1.0, 0.34, 0.38, 0.92), frameColor=(0, 0, 0, 0), pos=(-1.28, 0, -0.93), textMayChange=True)
        self.tip_label = None

        self.crosshair_root = self.aspect2d.attachNewNode("crosshair-root")
        self.crosshair_parts = []
        for a, b in [((-0.014, 0, 0), (-0.004, 0, 0)), ((0.014, 0, 0), (0.004, 0, 0)), ((0, 0, -0.014), (0, 0, -0.004)), ((0, 0, 0.014), (0, 0, 0.004))]:
            segs = LineSegs("cross")
            segs.setThickness(1.35)
            segs.setColor(0.92, 0.95, 1.0, 0.9)
            segs.moveTo(*a)
            segs.drawTo(*b)
            np = self.crosshair_root.attachNewNode(segs.create())
            np.setDepthTest(False)
            np.setDepthWrite(False)
            np.setBin("fixed", 100)
            self.crosshair_parts.append(np)

        self.core_console_root = self.aspect2d.attachNewNode("core-console-root")
        self.core_console_root.hide()
        DirectFrame(parent=self.core_console_root, frameColor=(0.02, 0.02, 0.025, 0.92), frameSize=(-0.78, 0.78, -0.22, 0.22), pos=(0, 0, -0.56))
        self.core_console_label = DirectLabel(parent=self.core_console_root, text="CORE ACCESS // 1 CAMPAIGN MERGE  2 VECTOR WARS  3 CONQUEST MERGE  5 INFILL  T HUB  ESC CLOSE", text_scale=0.034, text_align=TextNode.ACenter, text_fg=(0.98, 0.92, 0.94, 1.0), frameColor=(0, 0, 0, 0), pos=(0, 0, -0.56), textMayChange=True)

        self.menu_root = self.aspect2d.attachNewNode("menu-root")
        self.menu_root.hide()
        self.help_root = None
        self.menu_back = DirectFrame(parent=self.menu_root, frameColor=(0.01, 0.01, 0.012, 0.96), frameSize=(-0.98, 0.98, -0.62, 0.62))
        self.menu_header = DirectFrame(parent=self.menu_root, frameColor=(0.18, 0.01, 0.02, 0.88), frameSize=(-0.98, 0.98, 0.48, 0.62))
        self.menu_title = DirectLabel(parent=self.menu_root, text="OBSERVATORY // SYSTEM GRID", text_scale=0.050, text_fg=(1.0, 0.96, 0.96, 1.0), frameColor=(0, 0, 0, 0), pos=(0, 0, 0.56))
        self.menu_subtitle = DirectLabel(parent=self.menu_root, text="", text_scale=0.024, text_fg=(0.96, 0.40, 0.44, 1.0), frameColor=(0, 0, 0, 0), pos=(0, 0, 0.51), textMayChange=True)

        tabs = [("DISPLAY", "display"), ("PLAYER", "player"), ("WORLD", "world"), ("AUDIO", "audio"), ("LAUNCH", "launch"), ("SYSTEM", "system"), ("HELP", "help")]
        self.menu_tab_buttons = []
        start_x = -0.56
        for i, (label, key) in enumerate(tabs):
            btn = DirectButton(parent=self.menu_root, text=label, command=self.set_menu_tab, extraArgs=[key], pos=(start_x + i * 0.28, 0, 0.42), scale=0.042, frameColor=(0.08, 0.01, 0.02, 1.0), text_fg=(1.0, 0.84, 0.86, 1.0), relief=1)
            self.menu_tab_buttons.append((key, btn))

        self.menu_left = DirectFrame(parent=self.menu_root, frameColor=(0.03, 0.03, 0.035, 0.88), frameSize=(-0.70, -0.02, -0.52, 0.34), pos=(0, 0, -0.02))
        self.menu_right = DirectFrame(parent=self.menu_root, frameColor=(0.03, 0.03, 0.035, 0.88), frameSize=(0.06, 0.70, -0.52, 0.34), pos=(0, 0, -0.02))
        self.menu_info = DirectLabel(parent=self.menu_left, text="", text_align=TextNode.ALeft, text_scale=0.030, text_fg=(0.94, 0.95, 1.0, 1.0), frameColor=(0, 0, 0, 0), pos=(-0.64, 0, 0.26), textMayChange=True)
        self.menu_section = DirectLabel(parent=self.menu_left, text="", text_align=TextNode.ALeft, text_scale=0.023, text_fg=(0.98, 0.28, 0.32, 1.0), frameColor=(0, 0, 0, 0), pos=(-0.64, 0, 0.14), textMayChange=True)
        self.menu_detail = DirectLabel(parent=self.menu_left, text="", text_align=TextNode.ALeft, text_scale=0.025, text_fg=(0.82, 0.84, 0.90, 1.0), frameColor=(0, 0, 0, 0), pos=(-0.64, 0, 0.03), textMayChange=True)
        self.menu_status = DirectLabel(parent=self.menu_left, text="", text_align=TextNode.ALeft, text_scale=0.022, text_fg=(1.0, 0.40, 0.44, 1.0), frameColor=(0, 0, 0, 0), pos=(-0.64, 0, -0.44), textMayChange=True)
        self.menu_buttons = []
        for i in range(6):
            btn = DirectButton(parent=self.menu_right, text="", command=self.apply_menu_action, extraArgs=[i], pos=(0.38, 0, 0.23 - i * 0.13), scale=0.043, frameColor=(0.10, 0.01, 0.02, 1.0), text_fg=(1.0, 0.92, 0.94, 1.0), relief=1)
            self.menu_buttons.append(btn)
        self.refresh_menu_actions()

    def setup_input(self):
        for key in ["w", "a", "s", "d", "shift", "space", "control"]:
            self.accept(key, self.set_key, [key, True])
            self.accept(f"{key}-up", self.set_key, [key, False])
        self.accept("h", self.toggle_hud)
        self.accept("escape", self.toggle_menu)
        self.accept("f12", self.capture_latest_screenshot)
        self.accept("mouse1", self.set_fire_down, [True])
        self.accept("mouse1-up", self.set_fire_down, [False])
        self.accept("e", self.interact)
        self.accept("q", self.core_secondary_action)
        self.accept("1", self.core_launch_campaign)
        self.accept("2", self.core_launch_vector_wars)
        self.accept("3", self.core_launch_vector_conquest)
        self.accept("5", self.core_toggle_infill)
        self.accept("t", self.teleport_to_hub)
        self.accept("f1", self.toggle_help_overlay)

    def setup_gamepad(self):
        try:
            devices = self.devices.getDevices(InputDevice.DeviceClass.gamepad)
            if devices:
                self.attachInputDevice(devices[0], prefix="gamepad")
                self.gamepad = devices[0]
            self.accept("connect-device", self.on_device_connect)
            self.accept("disconnect-device", self.on_device_disconnect)
        except Exception:
            self.gamepad = None

    def on_device_connect(self, device):
        try:
            if device.device_class == InputDevice.DeviceClass.gamepad and self.gamepad is None:
                self.attachInputDevice(device, prefix="gamepad")
                self.gamepad = device
        except Exception:
            pass

    def on_device_disconnect(self, device):
        if self.gamepad == device:
            self.detachInputDevice(device)
            self.gamepad = None

    def set_key(self, key, value):
        self.keys[key] = value

    def set_fire_down(self, value):
        self.internal_mode.fire_down = bool(value)

    def station_line_color(self, alpha=1.0):
        return hsv_color(self.cfg.line_hue, self.cfg.line_saturation, self.cfg.line_value, alpha)

    def station_glow_color(self, alpha=1.0):
        return hsv_color((self.cfg.line_hue + 0.06) % 1.0, min(1.0, self.cfg.line_saturation * 0.76), min(1.0, self.cfg.line_value), alpha)

    def artifact_color(self, idx: int, alpha=1.0):
        return hsv_color((self.cfg.line_hue + idx / 8.0 + 0.08) % 1.0, 0.74, 1.0, alpha)

    def lens_color(self, alpha=1.0):
        return hsv_color((self.cfg.line_hue + 0.48) % 1.0, 0.46, 1.0, alpha)

    def add_surface_card(self, parent, pos, hpr, sx, sy, color, two_sided=True):
        cm = CardMaker("surface-card")
        cm.setFrame(-sx * 0.5, sx * 0.5, -sy * 0.5, sy * 0.5)
        np = parent.attachNewNode(cm.generate())
        np.setPos(pos)
        np.setHpr(hpr)
        np.setColor(*color)
        np.setTransparency(TransparencyAttrib.MAlpha)
        if two_sided:
            np.setTwoSided(True)
        return np

    def add_polyline(self, parent, points, color, thickness=None, closed=False, name="poly"):
        segs = LineSegs(name)
        segs.setThickness(thickness or self.cfg.line_thickness)
        segs.setColor(*color)
        if points:
            segs.moveTo(points[0])
            for p in points[1:]:
                segs.drawTo(p)
            if closed:
                segs.drawTo(points[0])
        np = parent.attachNewNode(segs.create())
        np.setAntialias(AntialiasAttrib.MLine)
        np.setTransparency(TransparencyAttrib.MAlpha)
        return np

    def polygon_points(self, radius, z, count=8, offset_deg=22.5):
        pts = []
        for i in range(count):
            a = math.radians(offset_deg) + math.tau * i / count
            pts.append(Vec3(math.cos(a) * radius, math.sin(a) * radius, z))
        return pts

    def add_prism(self, parent, radius, height, color, count=8, offset_deg=22.5, thickness_scale=1.0):
        bottom = self.polygon_points(radius, 0, count, offset_deg)
        top = self.polygon_points(radius, height, count, offset_deg)
        self.add_polyline(parent, bottom, color, self.cfg.line_thickness * thickness_scale, True, "prism-bottom")
        self.add_polyline(parent, top, color, self.cfg.line_thickness * thickness_scale, True, "prism-top")
        for a, b in zip(bottom, top):
            self.add_polyline(parent, [a, b], color, self.cfg.line_thickness * thickness_scale, False, "prism-side")

    def add_box(self, parent, center, size, color, thickness_scale=1.0):
        hx, hy, hz = size.x * 0.5, size.y * 0.5, size.z * 0.5
        corners = [
            Vec3(center.x - hx, center.y - hy, center.z - hz), Vec3(center.x + hx, center.y - hy, center.z - hz),
            Vec3(center.x + hx, center.y + hy, center.z - hz), Vec3(center.x - hx, center.y + hy, center.z - hz),
            Vec3(center.x - hx, center.y - hy, center.z + hz), Vec3(center.x + hx, center.y - hy, center.z + hz),
            Vec3(center.x + hx, center.y + hy, center.z + hz), Vec3(center.x - hx, center.y + hy, center.z + hz),
        ]
        edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
        for a, b in edges:
            self.add_polyline(parent, [corners[a], corners[b]], color, self.cfg.line_thickness * thickness_scale, False, "box-edge")

    def build_octagonal_floor_grid(self, parent, inner_r, outer_r, z, color):
        for r in [inner_r + i * 2.2 for i in range(int((outer_r - inner_r) / 2.2) + 1)]:
            self.add_polyline(parent, self.polygon_points(r, z, 8, 22.5), color, self.cfg.line_thickness * 0.76, True, "oct-ring")
        for i in range(8):
            a = math.radians(22.5) + math.tau * i / 8
            p0 = Vec3(math.cos(a) * inner_r, math.sin(a) * inner_r, z)
            p1 = Vec3(math.cos(a) * outer_r, math.sin(a) * outer_r, z)
            self.add_polyline(parent, [p0, p1], color, self.cfg.line_thickness * 0.72, False, "oct-spoke")

    def clear_station(self):
        for node in [self.surface_root, self.line_root, self.accent_root, self.dome_root, self.lens_root, self.sky_root, self.world_root, self.galaxy_root]:
            node.removeNode()
        self.surface_root = self.root_3d.attachNewNode("surface-root")
        self.line_root = self.root_3d.attachNewNode("line-root")
        self.accent_root = self.root_3d.attachNewNode("accent-root")
        self.dome_root = self.root_3d.attachNewNode("dome-root")
        self.lens_root = self.root_3d.attachNewNode("lens-root")
        self.sky_root = self.root_3d.attachNewNode("sky-root")
        self.world_root = self.root_3d.attachNewNode("world-root")
        self.galaxy_root = self.root_3d.attachNewNode("galaxy-root")
        self.world_root.setTransparency(TransparencyAttrib.MAlpha)
        self.galaxy_root.setTransparency(TransparencyAttrib.MAlpha)
        self.room_bounds = []
        self.terrain_chunks = {}
        self.artifacts = []
        self.galaxy_nodes = []
        self.nearest_artifact = None
        self.nearest_artifact_dist = 999.0

    def rebuild_station(self):
        self.clear_station()
        self.setBackgroundColor(self.cfg.background_value, self.cfg.background_value, self.cfg.background_value)
        self.fog.setColor(self.cfg.background_value, self.cfg.background_value, self.cfg.background_value)
        self.camLens.setFov(self.cfg.fov)
        self.camLens.setNearFar(0.05, self.cfg.fog_distance)
        self.fog.setLinearRange(self.cfg.fog_distance * 0.48, self.cfg.fog_distance)
        self.build_sky_shell()
        self.build_hub()
        self.build_hub_infill()
        self.build_observatory_dome()
        self.build_artifacts()
        self.build_lens()
        self.build_galaxy_targets()
        self.update_world_chunks(force=True)
        cr = self.station_line_color(0.95)
        for np in self.crosshair_parts:
            np.setColor(*cr)

    def build_sky_shell(self):
        bg = self.cfg.background_value
        for i, size in enumerate([340, 420, 520]):
            hue = (self.cfg.line_hue + 0.66 + i * 0.06) % 1.0
            color = hsv_color(hue, 0.44, 0.46 - i * 0.08, 0.06 if i < 2 else 0.04)
            self.add_surface_card(self.sky_root, Vec3(0, 0, 120 + i * 50), Vec3(0, 90, 0), size, size, color)
        for radius, alpha in [(90, 0.05), (120, 0.04), (160, 0.03)]:
            self.add_polyline(self.sky_root, self.polygon_points(radius, 78, 8, 0), self.station_glow_color(alpha), self.cfg.line_thickness * 0.5, True, "sky-ring")

    def build_hub(self):
        hub_color = self.station_line_color(0.90)
        core_color = hsv_color((self.cfg.line_hue + 0.24) % 1.0, 0.88, 1.0, 0.96)

        self.build_octagonal_floor_grid(self.line_root, 3.2, self.hub_radius, 0.03, self.station_line_color(0.64))
        self.add_prism(self.line_root, self.hub_radius, 10.0, hub_color, 8, 22.5, 1.0)
        self.add_prism(self.line_root, self.hub_radius - 2.3, 8.8, self.station_line_color(0.42), 8, 22.5, 0.78)
        self.room_bounds.append((-self.hub_radius + 1.0, self.hub_radius - 1.0, -self.hub_radius + 1.0, self.hub_radius - 1.0))

        for r, z in [(2.7, 1.2), (4.4, 3.0), (6.0, 5.0)]:
            self.add_polyline(self.line_root, self.polygon_points(r, z, 8, 22.5), core_color, self.cfg.line_thickness * 0.88, True, "core-ring")
        self.add_prism(self.line_root, 2.4, 6.4, core_color, 8, 22.5, 0.92)

        for i in range(8):
            ang = math.radians(22.5) + math.tau * i / 8
            n = Vec3(math.cos(ang), math.sin(ang), 0)
            t = Vec3(-n.y, n.x, 0)
            base = n * 14.2
            self.add_box(self.line_root, base + Vec3(0, 0, 1.1), Vec3(4.4, 1.8, 2.2), self.station_line_color(0.72), 0.8)
            self.add_surface_card(self.accent_root, base + n * -0.42 + Vec3(0, 0, 2.1), Vec3(math.degrees(ang) + 90, 0, 0), 3.1, 1.3, self.station_glow_color(0.14))
            rail_center = n * (self.hub_radius - 0.7)
            self.add_polyline(self.line_root, [rail_center + t * -2.0 + Vec3(0,0,0.05), rail_center + t * 2.0 + Vec3(0,0,0.05)], self.station_line_color(0.40), self.cfg.line_thickness * 0.56, False, "rail")

    def build_observatory_dome(self):
        dome_color = self.station_line_color(0.42)
        base_r = self.hub_radius - 1.8
        apex = 18.0
        ring_count = 7
        seg_count = 8
        for j in range(1, ring_count + 1):
            t = j / ring_count
            r = base_r * math.sqrt(max(0.0, 1.0 - t * t * 0.86))
            z = 6.4 + t * (apex - 6.4)
            pts = self.polygon_points(r, z, seg_count, 22.5)
            self.add_polyline(self.dome_root, pts, dome_color, self.cfg.line_thickness * (0.82 - t * 0.22), True, "dome-ring")
        for i in range(seg_count):
            a = math.radians(22.5) + math.tau * i / seg_count
            prev = Vec3(math.cos(a) * base_r, math.sin(a) * base_r, 6.4)
            for j in range(1, ring_count + 1):
                t = j / ring_count
                r = base_r * math.sqrt(max(0.0, 1.0 - t * t * 0.86))
                z = 6.4 + t * (apex - 6.4)
                cur = Vec3(math.cos(a) * r, math.sin(a) * r, z)
                self.add_polyline(self.dome_root, [prev, cur], dome_color, self.cfg.line_thickness * 0.72, False, "dome-meridian")
                prev = cur
        self.add_polyline(self.dome_root, self.polygon_points(base_r + 0.6, 6.2, 8, 22.5), self.station_line_color(0.34), self.cfg.line_thickness * 0.66, True, "dome-base")

    def artifact_shape(self, parent, center, color, shape_idx):
        if shape_idx == 0:
            pts = [center + Vec3(x, y, z) for x, y, z in [(-1.1,0,0),(0,-1.1,0),(1.1,0,0),(0,1.1,0),(-0.45,0,1.2),(0.45,0,1.2),(-0.45,0,-1.2),(0.45,0,-1.2)]]
            order = [(0,4),(1,4),(2,5),(3,5),(0,6),(1,6),(2,7),(3,7),(0,1),(1,2),(2,3),(3,0),(4,5),(6,7)]
        elif shape_idx == 1:
            pts = [center + Vec3(x, y, z) for x, y, z in [(-0.9,-0.9,-0.9),(0.9,-0.9,-0.9),(0.9,0.9,-0.9),(-0.9,0.9,-0.9),(-0.4,-0.4,0.9),(1.4,-0.4,0.9),(1.4,1.4,0.9),(-0.4,1.4,0.9)]]
            order = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
        elif shape_idx == 2:
            pts = [center + Vec3(math.cos(a) * (1.4 if i % 2 == 0 else 0.76), math.sin(a) * (1.4 if i % 2 == 0 else 0.76), (0.8 if i < 4 else -0.8)) for i, a in enumerate([0, math.pi/4, math.pi/2, 3*math.pi/4, math.pi, 5*math.pi/4, 3*math.pi/2, 7*math.pi/4])]
            order = [(i, (i+1)%8) for i in range(8)] + [(0,4),(1,5),(2,6),(3,7)]
        else:
            pts = [center + Vec3(x, y, z) for x, y, z in [(0,0,1.5),(1.2,0,0.55),(0,1.2,0.55),(-1.2,0,0.55),(0,-1.2,0.55),(0,0,-1.5)]]
            order = [(0,1),(0,2),(0,3),(0,4),(5,1),(5,2),(5,3),(5,4),(1,2),(2,3),(3,4),(4,1)]
        for a, b in order:
            self.add_polyline(parent, [pts[a], pts[b]], color, self.cfg.line_thickness * 0.82, False, "artifact")

    def build_artifacts(self):
        self.artifacts = []
        for i in range(8):
            ang = math.radians(22.5) + math.tau * i / 8
            pos = Vec3(math.cos(ang) * self.artifact_radius, math.sin(ang) * self.artifact_radius, 0)
            col = self.artifact_color(i, 0.95)
            ped_col = self.station_line_color(0.58)
            self.add_box(self.line_root, pos + Vec3(0, 0, 0.72), Vec3(1.8, 1.8, 1.44), ped_col, 0.64)
            self.add_box(self.line_root, pos + Vec3(0, 0, 2.08), Vec3(2.3, 2.3, 0.28), self.station_line_color(0.42), 0.54)
            self.add_surface_card(self.accent_root, pos + Vec3(0, 0, 1.98), Vec3(45, -90, 0), 1.9, 1.9, self.artifact_color(i, 0.12))
            self.artifact_shape(self.line_root, pos + Vec3(0, 0, 3.95), col, i % 4)
            name = WORLD_SPECS.get(i, {}).get("name", ("Frontier Lens" if i == 0 else f"Universe Lens {i+1}"))
            self.artifacts.append({"id": i, "name": name, "pos": pos + Vec3(0, 0, 3.95), "yaw": math.degrees(ang), "pitch": 56.0 + (i % 3) * 4.0, "radius": 3.6})

    def build_lens(self):
        self.lens_pivot = self.lens_root.attachNewNode("lens-pivot")
        self.lens_pivot.setPos(0, 0, 10.3)
        self.lens_barrel = self.lens_pivot.attachNewNode("lens-barrel")
        barrel_color = self.lens_color(0.96)
        for y, scale in [(0.0, 1.0), (1.6, 1.18), (3.2, 0.86), (4.5, 0.54)]:
            ring = []
            for i in range(8):
                a = math.tau * i / 8
                ring.append(Vec3(math.cos(a) * 0.95 * scale, y, math.sin(a) * 0.95 * scale))
            self.add_polyline(self.lens_barrel, ring, barrel_color, self.cfg.line_thickness * 0.88, True, "lens-ring")
        for i in range(8):
            a = math.tau * i / 8
            p0 = Vec3(math.cos(a) * 0.95, 0.0, math.sin(a) * 0.95)
            p1 = Vec3(math.cos(a) * 0.78, 4.9, math.sin(a) * 0.78)
            self.add_polyline(self.lens_barrel, [p0, p1], barrel_color, self.cfg.line_thickness * 0.74, False, "lens-rail")
        self.add_box(self.line_root, Vec3(0, 0, 10.0), Vec3(2.4, 2.4, 1.6), self.station_line_color(0.58), 0.72)
        self.add_polyline(self.line_root, [Vec3(-1.6,0,10.0), Vec3(1.6,0,10.0)], self.station_line_color(0.48), self.cfg.line_thickness * 0.62, False, "lens-base")

    def galaxy_points(self, seed: int, count: int = 140):
        rng = random.Random(seed)
        pts = []
        for _ in range(count):
            arm = rng.randint(0, 2)
            t = rng.random() * 5.7
            radius = 1.2 + t * 1.3 + rng.random() * 0.7
            twist = arm * 2.094 + t * 1.55
            x = math.cos(twist) * radius
            z = math.sin(twist) * radius
            y = (rng.random() - 0.5) * 0.7
            pts.append(Vec3(x, y, z) * 2.1)
        return pts

    def build_galaxy_targets(self):
        self.galaxy_nodes = []
        for artifact in self.artifacts:
            gnode = self.galaxy_root.attachNewNode(f"galaxy-{artifact['id']}")
            yaw = artifact["yaw"]
            pitch = artifact["pitch"]
            gnode.setPos(0, 0, 11.0)
            gnode.setHpr(yaw, -pitch, 0)
            gnode.setY(210.0)
            color = self.artifact_color(artifact["id"], 0.0)
            pts = self.galaxy_points(self.cfg.world_seed + artifact["id"] * 137)
            for p in pts:
                self.add_polyline(gnode, [p + Vec3(-0.14, 0, 0), p + Vec3(0.14, 0, 0)], color, self.cfg.line_thickness * 0.34, False, "star-x")
                self.add_polyline(gnode, [p + Vec3(0, 0, -0.14), p + Vec3(0, 0, 0.14)], color, self.cfg.line_thickness * 0.34, False, "star-z")
            halo = self.artifact_color(artifact["id"], 0.07)
            self.add_surface_card(gnode, Vec3(0, 0, 0), Vec3(0, 0, 0), 42, 42, halo)
            self.galaxy_nodes.append(gnode)

    def hashed_seed(self, x: int, y: int, salt: int = 0):
        return (x * 92837111 ^ y * 689287499 ^ self.cfg.world_seed ^ salt * 334214459) & 0xFFFFFFFF

    def terrain_height_at(self, x: float, y: float):
        r = math.sqrt(x * x + y * y)
        if r < self.cfg.safe_flat_radius:
            return 0.0
        n1 = math.sin(x * 0.028 + self.cfg.world_seed * 0.01) * math.cos(y * 0.024 - self.cfg.world_seed * 0.02)
        n2 = math.sin((x + y) * 0.012) * 0.65 + math.cos((x - y) * 0.017) * 0.45
        rim = min(1.0, max(0.0, (r - self.cfg.safe_flat_radius) / 90.0))
        base = (n1 * 0.55 + n2 * 0.45) * self.cfg.terrain_height * rim
        return base

    def current_world_spec(self):
        return WORLD_SPECS.get(self.active_artifact_id, WORLD_SPECS[0])

    def chunk_axis_positions(self):
        chunk_size = max(1.0, float(self.cfg.terrain_chunk_size))
        step = max(0.001, float(self.cfg.terrain_grid_step))
        segments = max(1, int(math.ceil(chunk_size / step)))
        coords = [chunk_size * (idx / segments) for idx in range(segments + 1)]
        coords[0] = 0.0
        coords[-1] = chunk_size
        return coords

    def clear_world_actors(self):
        for actor in self.world_actors:
            try:
                actor.root.removeNode()
            except Exception:
                pass
        self.world_actors = []

    def clear_world_chunks(self):
        for np in self.terrain_chunks.values():
            np.removeNode()
        self.terrain_chunks = {}
        self.clear_world_actors()

    def apply_world_theme(self, dt):
        spec = self.current_world_spec() if self.transition_target > 0.0 else WORLD_SPECS[0]
        target_blend = self.transition_progress if self.transition_target > 0.0 else 0.0
        self.world_theme_blend = lerp(self.world_theme_blend, target_blend, min(1.0, dt * 1.8))
        self.current_bg_rgb = lerp_rgb((self.cfg.background_value, self.cfg.background_value, self.cfg.background_value), spec["bg"], self.world_theme_blend)
        self.current_hub_rgb = lerp_rgb(self.default_hub_rgb, spec["hub"], self.world_theme_blend)
        self.setBackgroundColor(*self.current_bg_rgb, 1.0)
        self.fog.setColor(*self.current_bg_rgb)
        self.line_root.setColorScale(*self.current_hub_rgb, 0.98)
        self.dome_root.setColorScale(*self.current_hub_rgb, 0.96)
        self.accent_root.setColorScale(*self.current_hub_rgb, 0.82)
        self.surface_root.setColorScale(*self.current_hub_rgb, 1.0)

    def world_height_at(self, x: float, y: float, spec=None):
        spec = spec or self.current_world_spec()
        kind = spec["kind"]
        if kind == "venus":
            r = math.sqrt(x * x + y * y)
            if r < self.cfg.safe_flat_radius:
                return 0.0
            dunes = math.sin(x * 0.020 + self.cfg.world_seed * 0.03) * 9.0 + math.cos(y * 0.018 - self.cfg.world_seed * 0.02) * 7.0
            ridges = math.sin((x + y) * 0.009) * 14.0 + math.cos((x - y) * 0.013) * 8.0
            rim = min(1.0, max(0.0, (r - self.cfg.safe_flat_radius) / 70.0))
            return (dunes + ridges) * 0.45 * rim
        if kind == "jungle":
            r = math.sqrt(x * x + y * y)
            if r < self.cfg.safe_flat_radius:
                return 0.0
            hills = math.sin(x * 0.016) * 8.0 + math.cos(y * 0.017) * 7.0
            root_noise = math.sin((x + y) * 0.025) * 3.0
            rim = min(1.0, max(0.0, (r - self.cfg.safe_flat_radius) / 60.0))
            return (hills + root_noise) * rim
        if kind == "underwater":
            r = math.sqrt(x * x + y * y)
            base = -18.0 - min(50.0, r * 0.08)
            dunes = math.sin(x * 0.014) * 4.0 + math.cos(y * 0.016) * 4.5
            return base + dunes
        if kind == "campaign":
            r = math.sqrt(x * x + y * y)
            if r < 16.0:
                return 0.0
            ridges = math.sin(x * 0.024 + y * 0.013) * 2.5 + math.cos(y * 0.022 - x * 0.015) * 2.2
            steps = (math.sin((x + y) * 0.08) > 0.25) * 1.5
            return ridges + steps
        if kind == "conquest":
            r = math.sqrt(x * x + y * y)
            if r < 20.0:
                return 0.0
            dunes = math.sin(x * 0.018) * 5.8 + math.cos(y * 0.016) * 5.1
            scars = math.sin((x - y) * 0.033) * 1.6
            rim = min(1.0, max(0.0, (r - 20.0) / 64.0))
            return (dunes + scars) * rim
        return self.terrain_height_at(x, y)

    def add_world_actor(self, node, kind, seed, home):
        self.world_actors.append(WorldActor(node, kind, seed, home))

    def add_ship_actor(self, parent, pos: Vec3, seed: int):
        rng = random.Random(seed)
        node = parent.attachNewNode(f"ship-{seed}")
        node.setPos(pos)
        col = (0.72 + rng.random() * 0.28, 0.82 + rng.random() * 0.18, 1.0, 0.95)
        span = 2.2 + rng.random() * 3.8
        body = 4.0 + rng.random() * 8.0
        segs = LineSegs('ship')
        segs.setThickness(max(1.0, self.cfg.line_thickness * 0.72))
        segs.setColor(*col)
        pts = [Vec3(-span,0,0), Vec3(0,body,0), Vec3(span,0,0), Vec3(0,-body*0.35,0)]
        for a,b in [(0,1),(1,2),(2,3),(3,0),(0,2)]:
            segs.moveTo(pts[a]); segs.drawTo(pts[b])
        segs.moveTo(0, -body*0.1, -span*0.45); segs.drawTo(0, body*0.52, span*0.12)
        np = node.attachNewNode(segs.create())
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setAntialias(AntialiasAttrib.MLine)
        self.add_world_actor(node, 'ship', seed, pos)

    def add_underwater_actor(self, parent, pos: Vec3, seed: int, whale=False):
        rng = random.Random(seed)
        node = parent.attachNewNode(f"sea-{seed}")
        node.setPos(pos)
        col = (0.30, 0.96, 0.88, 0.82 if not whale else 0.68)
        segs = LineSegs('sea')
        segs.setThickness(max(1.0, self.cfg.line_thickness * (0.75 if whale else 0.55)))
        segs.setColor(*col)
        length = (10.0 + rng.random() * 10.0) if whale else (2.2 + rng.random() * 2.8)
        height = length * (0.22 if whale else 0.28)
        body_pts = []
        for i in range(10):
            t = i / 9.0
            x = (t - 0.5) * length
            z = math.sin(t * math.pi) * height
            body_pts.append(Vec3(x, 0, z))
        for a, b in zip(body_pts, body_pts[1:]):
            segs.moveTo(a); segs.drawTo(b)
        segs.moveTo(Vec3(length * 0.45, 0, 0)); segs.drawTo(Vec3(length * 0.62, 0, height * 0.6)); segs.moveTo(Vec3(length * 0.45, 0, 0)); segs.drawTo(Vec3(length * 0.62, 0, -height * 0.6))
        segs.moveTo(Vec3(-length * 0.1, 0, height * 0.4)); segs.drawTo(Vec3(-length * 0.22, 0, height * 0.9))
        np = node.attachNewNode(segs.create())
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setAntialias(AntialiasAttrib.MLine)
        self.add_world_actor(node, 'whale' if whale else 'fish', seed, pos)

    def add_tree_actor(self, parent, pos: Vec3, seed: int):
        rng = random.Random(seed)
        node = parent.attachNewNode(f"tree-{seed}")
        node.setPos(pos)
        trunk_h = 8.0 + rng.random() * 16.0
        crown_r = 3.2 + rng.random() * 5.5
        trunk = LineSegs('trunk')
        trunk.setThickness(max(1.0, self.cfg.line_thickness * 0.72))
        trunk.setColor(0.58, 0.42, 0.22, 0.94)
        trunk.moveTo(0,0,0); trunk.drawTo(0,0,trunk_h)
        node.attachNewNode(trunk.create()).setTransparency(TransparencyAttrib.MAlpha)
        crown = []
        for i in range(8):
            a = math.tau * i / 8.0
            crown.append(Vec3(math.cos(a) * crown_r, math.sin(a) * crown_r, trunk_h + math.sin(a * 2.0) * 1.2))
        self.add_polyline(node, crown, (0.36, 0.96, 0.46, 0.82), self.cfg.line_thickness * 0.55, True, 'crown')
        self.add_world_actor(node, 'tree', seed, pos)

    def add_crystal_cluster(self, parent, pos: Vec3, seed: int, color, height_range=(5.0, 16.0), radius_range=(1.8, 4.8), count_range=(3, 6)):
        rng = random.Random(seed)
        group = parent.attachNewNode(f"cluster-{seed}")
        group.setPos(pos)
        count = rng.randint(*count_range)
        for _ in range(count):
            local = Vec3(rng.uniform(-3.0, 3.0), rng.uniform(-3.0, 3.0), 0.0)
            height = rng.uniform(*height_range)
            radius = rng.uniform(*radius_range)
            prism = group.attachNewNode("crystal")
            prism.setPos(local)
            prism.setH(rng.uniform(0.0, 360.0))
            self.add_prism(prism, radius, height, color, count=4 if rng.random() < 0.5 else 6, offset_deg=45.0 if rng.random() < 0.5 else 22.5, thickness_scale=0.48)
            self.add_polyline(prism, [Vec3(0, 0, height), Vec3(0, 0, height + rng.uniform(0.8, 2.2))], color, self.cfg.line_thickness * 0.42, False, 'crystal-tip')

    def add_geometric_creature(self, parent, pos: Vec3, seed: int, family: str):
        rng = random.Random(seed)
        node = parent.attachNewNode(f"{family}-{seed}")
        node.setPos(pos)
        scale = 1.0
        if family == 'grazer':
            scale = rng.uniform(0.9, 1.7)
            col = (0.82, 0.92, 1.0, 0.92)
            self.add_box(node, Vec3(0, 0, 2.6 * scale), Vec3(4.6 * scale, 2.8 * scale, 2.6 * scale), col, 0.56)
            self.add_box(node, Vec3(2.9 * scale, 0, 4.1 * scale), Vec3(1.8 * scale, 1.5 * scale, 1.8 * scale), col, 0.52)
            self.add_polyline(node, [Vec3(1.8 * scale, 0, 3.2 * scale), Vec3(2.7 * scale, 0, 4.1 * scale)], col, self.cfg.line_thickness * 0.50, False, 'neck')
            for sx in (-1.4, -0.3, 0.8, 1.8):
                self.add_polyline(node, [Vec3(sx * scale, 0, 1.3 * scale), Vec3(sx * scale, 0, -1.6 * scale)], col, self.cfg.line_thickness * 0.48, False, 'leg')
            self.add_polyline(node, [Vec3(-2.6 * scale, 0, 3.0 * scale), Vec3(-3.8 * scale, 0, 4.8 * scale)], col, self.cfg.line_thickness * 0.44, False, 'tail')
        elif family == 'strider':
            scale = rng.uniform(1.0, 2.4)
            col = (1.0, 0.62, 0.26, 0.92)
            self.add_prism(node, 1.4 * scale, 5.2 * scale, col, count=6, thickness_scale=0.52)
            self.add_box(node, Vec3(0, 0, 6.4 * scale), Vec3(3.2 * scale, 2.1 * scale, 1.6 * scale), col, 0.50)
            self.add_polyline(node, [Vec3(0, 0, 6.8 * scale), Vec3(0, 0, 9.8 * scale)], col, self.cfg.line_thickness * 0.44, False, 'spire')
            for sx, sy in [(-1.2, -0.7), (1.2, -0.7), (-1.0, 0.8), (1.0, 0.8)]:
                self.add_polyline(node, [Vec3(sx * scale, sy * scale, 2.0 * scale), Vec3(sx * scale * 1.2, sy * scale * 1.2, -2.6 * scale)], col, self.cfg.line_thickness * 0.48, False, 'leg')
        elif family == 'orbiter':
            scale = rng.uniform(0.9, 2.2)
            col = (0.62, 0.78, 1.0, 0.82)
            self.add_box(node, Vec3(0, 0, 0), Vec3(2.2 * scale, 2.2 * scale, 2.2 * scale), col, 0.52)
            ring = [Vec3(math.cos(math.tau * i / 10.0) * 3.2 * scale, math.sin(math.tau * i / 10.0) * 3.2 * scale, math.sin(i * 0.7) * 0.7 * scale) for i in range(10)]
            self.add_polyline(node, ring, col, self.cfg.line_thickness * 0.40, True, 'ring')
            self.add_polyline(node, [Vec3(-4.2 * scale, 0, 0), Vec3(4.2 * scale, 0, 0)], col, self.cfg.line_thickness * 0.34, False, 'axis')
            self.add_polyline(node, [Vec3(0, -4.2 * scale, 0), Vec3(0, 4.2 * scale, 0)], col, self.cfg.line_thickness * 0.34, False, 'axis')
        elif family == 'ray':
            scale = rng.uniform(0.8, 2.1)
            col = (0.30, 0.96, 0.88, 0.78)
            wing = [Vec3(-3.6 * scale, 0, 0), Vec3(-1.0 * scale, 0, 1.3 * scale), Vec3(0, 0, 0.4 * scale), Vec3(1.0 * scale, 0, 1.3 * scale), Vec3(3.6 * scale, 0, 0), Vec3(0, 0, -1.0 * scale)]
            self.add_polyline(node, wing, col, self.cfg.line_thickness * 0.44, True, 'ray-body')
            self.add_polyline(node, [Vec3(0, 0, -0.8 * scale), Vec3(0, 0, -4.6 * scale)], col, self.cfg.line_thickness * 0.38, False, 'tail')
        elif family == 'canopy_beast':
            scale = rng.uniform(0.9, 1.9)
            col = (0.56, 0.96, 0.52, 0.86)
            self.add_prism(node, 1.7 * scale, 3.0 * scale, col, count=5, offset_deg=18.0, thickness_scale=0.46)
            self.add_box(node, Vec3(2.0 * scale, 0, 3.7 * scale), Vec3(1.8 * scale, 1.5 * scale, 1.4 * scale), col, 0.42)
            for sx in (-1.1, 0.9):
                for sy in (-0.7, 0.7):
                    self.add_polyline(node, [Vec3(sx * scale, sy * scale, 0.6 * scale), Vec3(sx * scale * 1.1, sy * scale * 1.1, -2.6 * scale)], col, self.cfg.line_thickness * 0.42, False, 'leg')
            self.add_polyline(node, [Vec3(-1.8 * scale, 0, 3.2 * scale), Vec3(-3.4 * scale, 0, 4.4 * scale)], col, self.cfg.line_thickness * 0.38, False, 'tail')
        else:
            scale = rng.uniform(0.8, 1.6)
            col = (0.90, 0.90, 1.0, 0.85)
            self.add_box(node, Vec3(0, 0, 1.2 * scale), Vec3(2.0 * scale, 2.0 * scale, 2.4 * scale), col, 0.5)
        actor = WorldActor(node, family, seed, pos)
        actor.speed = 1.0 + rng.random() * 2.2
        actor.health = 80.0
        self.world_actors.append(actor)

    def add_campaign_enemy(self, parent, pos: Vec3, seed: int):
        rng = random.Random(seed)
        node = parent.attachNewNode(f"campaign-enemy-{seed}")
        node.setPos(pos)
        col = (0.06, 0.06, 0.06, 0.95)
        self.add_box(node, Vec3(0, 0, 2.2), Vec3(2.2, 1.5, 4.4), col, 0.7)
        self.add_box(node, Vec3(0, 0.0, 5.3), Vec3(1.2, 1.0, 1.1), col, 0.7)
        self.add_polyline(node, [Vec3(-1.2, 0, 2.6), Vec3(-2.4, 0, 0.8)], col, self.cfg.line_thickness * 0.6, False, 'arm')
        self.add_polyline(node, [Vec3(1.2, 0, 2.6), Vec3(2.4, 0, 0.8)], col, self.cfg.line_thickness * 0.6, False, 'arm')
        self.add_polyline(node, [Vec3(-0.6, 0, 0.4), Vec3(-0.8, 0, -2.0)], col, self.cfg.line_thickness * 0.6, False, 'leg')
        self.add_polyline(node, [Vec3(0.6, 0, 0.4), Vec3(0.8, 0, -2.0)], col, self.cfg.line_thickness * 0.6, False, 'leg')
        self.add_polyline(node, [Vec3(-0.18, 0.76, 5.3), Vec3(0.18, 0.76, 5.3)], (1, 1, 1, 1), self.cfg.line_thickness * 0.4, False, 'visor')
        actor = WorldActor(node, 'campaign_enemy', seed, pos)
        actor.health = 42.0
        actor.team = 'enemy'
        actor.speed = 4.2 + rng.random() * 0.8
        self.world_actors.append(actor)

    def add_conquest_unit(self, parent, pos: Vec3, seed: int, team='enemy'):
        rng = random.Random(seed)
        node = parent.attachNewNode(f"conquest-{team}-{seed}")
        node.setPos(pos)
        base_col = (1.0, 0.62, 0.34, 0.96) if team == 'enemy' else (0.34, 0.88, 1.0, 0.96)
        self.add_box(node, Vec3(0, 0, 1.6), Vec3(2.4, 1.6, 2.2), base_col, 0.75)
        self.add_box(node, Vec3(0, 0.2, 3.2), Vec3(1.4, 1.0, 1.2), base_col, 0.72)
        self.add_polyline(node, [Vec3(-1.2, -0.5, 0.2), Vec3(-1.8, 0.8, -0.8)], base_col, self.cfg.line_thickness * 0.6, False, 'track')
        self.add_polyline(node, [Vec3(1.2, -0.5, 0.2), Vec3(1.8, 0.8, -0.8)], base_col, self.cfg.line_thickness * 0.6, False, 'track')
        self.add_polyline(node, [Vec3(0, 0.4, 3.2), Vec3(0, 2.4, 3.4)], base_col, self.cfg.line_thickness * 0.65, False, 'barrel')
        actor = WorldActor(node, 'conquest_unit', seed, pos)
        actor.health = 64.0 if team == 'enemy' else 76.0
        actor.team = team
        actor.speed = 2.8 + rng.random() * 0.6
        self.world_actors.append(actor)

    def spawn_world_projectile(self, pos: Vec3, velocity: Vec3, team: str, damage: float, color):
        node = self.world_root.attachNewNode(f"proj-{team}-{time.time_ns()}")
        self.add_polyline(node, [Vec3(0, 0, 0), Vec3(0, 1.4, 0)], color, self.cfg.line_thickness * 0.58, False, 'proj')
        node.setPos(pos)
        if velocity.lengthSquared() > 0.001:
            node.lookAt(pos + velocity)
        self.internal_mode.projectiles.append(WorldProjectile(node=node, velocity=Vec3(velocity), ttl=2.4, damage=damage, team=team))

    def create_world_chunk(self, cx: int, cy: int):
        node = self.world_root.attachNewNode(f"chunk-{cx}-{cy}")
        spec = self.current_world_spec()
        kind = spec["kind"]
        line_color = (*spec["hub"], 0.72)
        chunk_size = self.cfg.terrain_chunk_size
        axis_coords = self.chunk_axis_positions()
        ox = cx * chunk_size
        oy = cy * chunk_size
        rng = random.Random(self.hashed_seed(cx, cy, 71 + (self.active_artifact_id or 0)))
        if kind == "space":
            for _ in range(2 + rng.randint(0, 2)):
                pos = Vec3(ox + rng.uniform(0.0, chunk_size), oy + rng.uniform(0.0, chunk_size), rng.uniform(-80.0, 80.0))
                self.add_ship_actor(node, pos, rng.randint(1, 10**9))
            if rng.random() < 0.55:
                pos = Vec3(ox + rng.uniform(12.0, chunk_size - 12.0), oy + rng.uniform(12.0, chunk_size - 12.0), rng.uniform(-42.0, 42.0))
                self.add_geometric_creature(node, pos, rng.randint(1, 10**9), 'orbiter')
            for _ in range(18 + rng.randint(0, 12)):
                pos = Vec3(ox + rng.uniform(0.0, chunk_size), oy + rng.uniform(0.0, chunk_size), rng.uniform(-120.0, 120.0))
                self.add_polyline(node, [pos + Vec3(-0.15, 0, 0), pos + Vec3(0.15, 0, 0)], (0.72, 0.86, 1.0, 0.55), self.cfg.line_thickness * 0.28, False, 'starx')
                self.add_polyline(node, [pos + Vec3(0, 0, -0.15), pos + Vec3(0, 0, 0.15)], (0.72, 0.86, 1.0, 0.55), self.cfg.line_thickness * 0.28, False, 'starz')
            for _ in range(1 + rng.randint(0, 1)):
                pos = Vec3(ox + rng.uniform(8.0, chunk_size - 8.0), oy + rng.uniform(8.0, chunk_size - 8.0), rng.uniform(-30.0, 30.0))
                self.add_crystal_cluster(node, pos, rng.randint(1, 10**9), (0.52, 0.72, 1.0, 0.46), (6.0, 12.0), (2.8, 5.4), (2, 4))
            return node
        if kind == "campaign":
            for _ in range(4 + rng.randint(0, 2)):
                px = ox + rng.uniform(8.0, chunk_size - 8.0)
                py = oy + rng.uniform(8.0, chunk_size - 8.0)
                pz = self.world_height_at(px, py, spec)
                self.add_campaign_enemy(node, Vec3(px, py, pz + 2.2), rng.randint(1, 10**9))
            for _ in range(2):
                bx = ox + rng.uniform(10.0, chunk_size - 10.0)
                by = oy + rng.uniform(10.0, chunk_size - 10.0)
                bz = self.world_height_at(bx, by, spec)
                self.add_box(node, Vec3(bx, by, bz + 2.2), Vec3(5.0, 5.0, 4.0), (0.08, 0.08, 0.08, 0.92), 0.7)
        if kind == "conquest":
            for _ in range(3 + rng.randint(0, 2)):
                px = ox + rng.uniform(10.0, chunk_size - 10.0)
                py = oy + rng.uniform(10.0, chunk_size - 10.0)
                pz = self.world_height_at(px, py, spec)
                self.add_conquest_unit(node, Vec3(px, py, pz + 1.6), rng.randint(1, 10**9), team='enemy')
            if abs(cx) + abs(cy) <= 2:
                for _ in range(2):
                    px = ox + rng.uniform(12.0, chunk_size - 12.0)
                    py = oy + rng.uniform(12.0, chunk_size - 12.0)
                    pz = self.world_height_at(px, py, spec)
                    self.add_conquest_unit(node, Vec3(px, py, pz + 1.4), rng.randint(1, 10**9), team='ally')
            relay = Vec3(ox + chunk_size * 0.5, oy + chunk_size * 0.5, self.world_height_at(ox + chunk_size * 0.5, oy + chunk_size * 0.5, spec) + 4.0)
            self.add_box(node, relay, Vec3(3.0, 3.0, 8.0), (0.98, 0.62, 0.35, 0.82), 0.68)
        for local_x in axis_coords:
            pts = []
            x = ox + local_x
            for local_y in axis_coords:
                y = oy + local_y
                z = self.world_height_at(x, y, spec)
                pts.append(Vec3(x, y, z))
            self.add_polyline(node, pts, line_color, self.cfg.line_thickness * 0.52, False, "terrain-x")
        for local_y in axis_coords:
            pts = []
            y = oy + local_y
            for local_x in axis_coords:
                x = ox + local_x
                z = self.world_height_at(x, y, spec)
                pts.append(Vec3(x, y, z))
            self.add_polyline(node, pts, line_color, self.cfg.line_thickness * 0.52, False, "terrain-y")
        if kind in {"frontier", "venus", "jungle", "underwater"}:
            for _ in range(1 + rng.randint(0, 2)):
                px = ox + rng.uniform(8.0, chunk_size - 8.0)
                py = oy + rng.uniform(8.0, chunk_size - 8.0)
                pz = self.world_height_at(px, py, spec)
                if kind == "underwater":
                    pz += rng.uniform(4.0, 12.0)
                self.add_crystal_cluster(node, Vec3(px, py, pz), rng.randint(1, 10**9), (*spec["hub"], 0.54), (4.0, 12.0), (1.4, 3.8), (2, 5))
        if kind == "venus":
            for _ in range(3 + rng.randint(0, 3)):
                px = ox + rng.uniform(8.0, chunk_size - 8.0)
                py = oy + rng.uniform(8.0, chunk_size - 8.0)
                base = self.world_height_at(px, py, spec)
                height = 10.0 + rng.random() * 26.0
                radius = 4.0 + rng.random() * 7.0
                pts = [Vec3(px + math.cos(math.tau * i / 8.0) * radius, py + math.sin(math.tau * i / 8.0) * radius, base + math.sin(i) * 0.7) for i in range(8)]
                top = [Vec3(p.x * 0.88 + px * 0.12, p.y * 0.88 + py * 0.12, base + height) for p in pts]
                self.add_polyline(node, pts, (1.0, 0.55, 0.24, 0.76), self.cfg.line_thickness * 0.56, True, 'mesa0')
                self.add_polyline(node, top, (1.0, 0.68, 0.32, 0.82), self.cfg.line_thickness * 0.56, True, 'mesa1')
                for a, b in zip(pts, top):
                    self.add_polyline(node, [a, b], (1.0, 0.55, 0.24, 0.62), self.cfg.line_thickness * 0.48, False, 'mesa2')
            if rng.random() < 0.65:
                pos = Vec3(ox + rng.uniform(12.0, chunk_size - 12.0), oy + rng.uniform(12.0, chunk_size - 12.0), self.world_height_at(ox + chunk_size * 0.5, oy + chunk_size * 0.5, spec) + 2.0)
                self.add_geometric_creature(node, pos, rng.randint(1, 10**9), 'strider')
        elif kind == "underwater":
            if rng.random() < 0.38:
                px = ox + rng.uniform(10.0, chunk_size - 10.0)
                py = oy + rng.uniform(10.0, chunk_size - 10.0)
                pz = self.world_height_at(px, py, spec) + 18.0 + rng.uniform(0.0, 14.0)
                self.add_underwater_actor(node, Vec3(px, py, pz), rng.randint(1, 10**9), whale=True)
            ray_count = 1 + rng.randint(0, 2)
            for _ in range(ray_count):
                px = ox + rng.uniform(6.0, chunk_size - 6.0)
                py = oy + rng.uniform(6.0, chunk_size - 6.0)
                pz = self.world_height_at(px, py, spec) + 7.0 + rng.uniform(0.0, 10.0)
                self.add_geometric_creature(node, Vec3(px, py, pz), rng.randint(1, 10**9), 'ray')
            for _ in range(2 + rng.randint(0, 3)):
                px = ox + rng.uniform(0.0, chunk_size)
                py = oy + rng.uniform(0.0, chunk_size)
                pz = self.world_height_at(px, py, spec) + 4.0 + rng.uniform(0.0, 9.0)
                self.add_underwater_actor(node, Vec3(px, py, pz), rng.randint(1, 10**9), whale=False)
        elif kind == "jungle":
            for _ in range(8 + rng.randint(0, 8)):
                px = ox + rng.uniform(0.0, chunk_size)
                py = oy + rng.uniform(0.0, chunk_size)
                pz = self.world_height_at(px, py, spec)
                self.add_tree_actor(node, Vec3(px, py, pz), rng.randint(1, 10**9))
            if rng.random() < 0.55:
                pos = Vec3(ox + rng.uniform(10.0, chunk_size - 10.0), oy + rng.uniform(10.0, chunk_size - 10.0), self.world_height_at(ox + chunk_size * 0.5, oy + chunk_size * 0.5, spec))
                self.add_geometric_creature(node, pos, rng.randint(1, 10**9), 'canopy_beast')
        elif kind == "frontier":
            for _ in range(1 + rng.randint(0, 1)):
                px = ox + rng.uniform(10.0, chunk_size - 10.0)
                py = oy + rng.uniform(10.0, chunk_size - 10.0)
                base = self.world_height_at(px, py, spec)
                h = 6.0 + rng.random() * 10.0
                self.add_prism(node, 2.4 + rng.random() * 2.2, h, (0.76, 0.90, 1.0, 0.62), count=5 if rng.random() < 0.5 else 6, thickness_scale=0.42)
            if rng.random() < 0.48:
                pos = Vec3(ox + rng.uniform(10.0, chunk_size - 10.0), oy + rng.uniform(10.0, chunk_size - 10.0), self.world_height_at(ox + chunk_size * 0.5, oy + chunk_size * 0.5, spec))
                self.add_geometric_creature(node, pos, rng.randint(1, 10**9), 'grazer')
        return node

    def update_world_chunks(self, force=False):
        if not self.world_unlocked and self.transition_target <= 0.0 and not force:
            self.world_root.hide()
            return
        self.world_root.show()
        size = self.cfg.terrain_chunk_size
        pcx = int(math.floor(self.player_pos.x / size))
        pcy = int(math.floor(self.player_pos.y / size))
        needed = set()
        radius = self.cfg.terrain_render_radius
        for cx in range(pcx - radius, pcx + radius + 1):
            for cy in range(pcy - radius, pcy + radius + 1):
                needed.add((cx, cy))
                if (cx, cy) not in self.terrain_chunks:
                    self.terrain_chunks[(cx, cy)] = self.create_world_chunk(cx, cy)
        for key in list(self.terrain_chunks.keys()):
            if key not in needed:
                self.terrain_chunks[key].removeNode()
                del self.terrain_chunks[key]

    def current_zone_name(self):
        r = math.sqrt(self.player_pos.x ** 2 + self.player_pos.y ** 2)
        if r < 8.0:
            return "Central Core"
        if r < 19.0:
            return "Observatory Ring"
        if r < self.hub_radius + 1.0:
            return "Artifact Perimeter"
        return "Frontier Field"

    def find_nearest_artifact(self):
        best = None
        best_d = 999.0
        for artifact in self.artifacts:
            d = (artifact["pos"] - self.player_pos).length()
            if d < best_d:
                best_d = d
                best = artifact
        self.nearest_artifact = best
        self.nearest_artifact_dist = best_d

    def activate_artifact(self):
        if self.nearest_artifact is None:
            return
        self.active_artifact = self.nearest_artifact
        self.active_artifact_id = self.active_artifact["id"]
        self.transition_target = 1.0
        self.world_unlocked = True

    def activate_nearest_artifact(self):
        self.find_nearest_artifact()
        if self.nearest_artifact is not None and self.nearest_artifact_dist < self.nearest_artifact["radius"]:
            self.activate_artifact()

    def teleport_to_hub(self):
        self.player_pos = Vec3(self.base_teleport)
        self.camera.setPos(self.player_pos)
        self.active_artifact = None
        self.active_artifact_id = None
        self.transition_target = 0.0
        self.world_unlocked = False
        self.internal_mode = InternalModeState()
        self.clear_world_chunks()
        self.refresh_ui()

    def toggle_hud(self):
        self.hud_visible = not self.hud_visible
        self.cfg.hud_visible = self.hud_visible
        save_config(self.cfg)
        self.refresh_ui()

    def toggle_help_overlay(self):
        if not self.menu_open:
            self.menu_open = True
            self.menu_root.show()
        self.set_menu_tab("help")
        props = WindowProperties()
        props.setCursorHidden(False)
        if self.win is not None and hasattr(self.win, "requestProperties"):
            self.win.requestProperties(props)
        self.center_hint["text"] = ""
        self.refresh_ui()

    def toggle_menu(self):
        if self.core_console_open:
            self.close_core_console()
            return
        self.menu_open = not self.menu_open
        props = WindowProperties()
        props.setCursorHidden(not self.menu_open and not SELF_TEST)
        if self.win is not None and hasattr(self.win, "requestProperties"):
            self.win.requestProperties(props)
        if self.menu_open:
            self.menu_root.show()
            self.center_hint["text"] = ""
        else:
            self.menu_root.hide()
            if not SELF_TEST:
                self.recenter_mouse(force=True)
        self.refresh_ui()

    def set_menu_tab(self, tab_key):
        self.menu_tab = tab_key
        self.refresh_menu_actions()
        self.refresh_ui()

    def apply_menu_action(self, index):
        if index >= len(self.menu_actions):
            return
        action = self.menu_actions[index]
        fn = getattr(self, action[1], None)
        if callable(fn):
            fn(*action[2:])

    def adjust_walk_speed(self, delta):
        self.cfg.walk_speed = max(2.0, min(30.0, self.cfg.walk_speed + delta))
        save_config(self.cfg)
        self.refresh_ui()

    def adjust_sprint_speed(self, delta):
        self.cfg.sprint_speed = max(self.cfg.walk_speed + 1.0, min(42.0, self.cfg.sprint_speed + delta))
        save_config(self.cfg)
        self.refresh_ui()

    def adjust_mouse_sensitivity(self, delta):
        self.cfg.mouse_sensitivity = max(0.02, min(1.0, self.cfg.mouse_sensitivity + delta))
        save_config(self.cfg)
        self.refresh_ui()

    def adjust_eye_height(self, delta):
        self.cfg.player_eye_height = max(1.6, min(3.0, self.cfg.player_eye_height + delta))
        self.player_pos.z = self.cfg.player_eye_height + self.terrain_height_at(self.player_pos.x, self.player_pos.y) * 0.02
        self.base_teleport.z = self.cfg.player_eye_height
        save_config(self.cfg)
        self.refresh_ui()

    def adjust_grid_step(self, delta):
        self.cfg.terrain_grid_step = max(4.0, min(20.0, self.cfg.terrain_grid_step + delta))
        save_config(self.cfg)
        self.rebuild_station()
        self.refresh_ui()

    def adjust_terrain_height(self, delta):
        self.cfg.terrain_height = max(2.0, min(40.0, self.cfg.terrain_height + delta))
        save_config(self.cfg)
        self.rebuild_station()
        self.refresh_ui()

    def adjust_render_radius(self, delta):
        self.cfg.terrain_render_radius = max(1, min(8, self.cfg.terrain_render_radius + int(delta)))
        save_config(self.cfg)
        self.update_world_chunks(force=True)
        self.refresh_ui()

    def reset_settings(self):
        self.cfg = ObservatoryConfig()
        self.hud_visible = self.cfg.hud_visible
        self.base_teleport = Vec3(0, -10, self.cfg.player_eye_height)
        save_config(self.cfg)
        self.rebuild_station()
        self.refresh_menu_actions()
        self.refresh_ui()

    def refresh_menu_actions(self):
        zone = self.current_zone_name()
        art_name = self.active_artifact["name"] if self.active_artifact else "Hub Standby"
        self.menu_subtitle["text"] = f"{zone} // {art_name}"
        specs = {
            "display": [
                ("FOV +", "adjust_fov", 3.0), ("FOV -", "adjust_fov", -3.0),
                ("BG +", "adjust_background", 0.015), ("BG -", "adjust_background", -0.015),
                ("HUE +", "shift_line_hue", 0.08), ("HUE -", "shift_line_hue", -0.08),
            ],
            "player": [
                ("WALK +", "adjust_walk_speed", 1.0), ("WALK -", "adjust_walk_speed", -1.0),
                ("RUN +", "adjust_sprint_speed", 1.0), ("RUN -", "adjust_sprint_speed", -1.0),
                ("SENSE +", "adjust_mouse_sensitivity", 0.02), ("SENSE -", "adjust_mouse_sensitivity", -0.02),
            ],
            "world": [
                ("LINE +", "adjust_line_thickness", 0.2), ("LINE -", "adjust_line_thickness", -0.2),
                ("GRID +", "adjust_grid_step", 1.0), ("GRID -", "adjust_grid_step", -1.0),
                ("HGT +", "adjust_terrain_height", 1.0), ("HGT -", "adjust_terrain_height", -1.0),
            ],
            "audio": [
                ("MASTER +", "adjust_master_volume", 0.05), ("MASTER -", "adjust_master_volume", -0.05),
                ("SFX +", "adjust_sfx_volume", 0.05), ("SFX -", "adjust_sfx_volume", -0.05),
                ("MUSIC +", "adjust_music_volume", 0.05), ("MUSIC -", "adjust_music_volume", -0.05),
            ],
            "launch": [
                ("RES CYCLE", "cycle_launch_resolution"), ("FULLSCREEN", "toggle_launch_fullscreen"),
                ("BORDERLESS", "toggle_launch_borderless"), ("GAME HUD", "toggle_launch_hud"),
                ("LOOK +", "adjust_launch_game_mouse_sensitivity", 0.02), ("LOOK -", "adjust_launch_game_mouse_sensitivity", -0.02),
                ("INVERT Y", "toggle_launch_invert_y"), ("GFX", "cycle_launch_graphics_quality"),
                ("DEADZONE +", "adjust_launch_deadzone", 0.01), ("DEADZONE -", "adjust_launch_deadzone", -0.01),
            ],
            "system": [
                ("RESUME", "toggle_menu"), ("HUD", "toggle_hud"),
                ("SHOT", "capture_latest_screenshot"), ("HUB", "teleport_to_hub"),
                ("RESET CFG", "reset_settings"), ("HELP", "toggle_help_overlay"),
            ],
            "help": [
                ("BACK", "set_menu_tab", "display"), ("RESUME", "toggle_menu"),
            ],
        }
        self.menu_actions = specs.get(self.menu_tab, [])
        for i, btn in enumerate(self.menu_buttons):
            if i < len(self.menu_actions):
                btn.show()
                btn["text"] = self.menu_actions[i][0]
            else:
                btn.hide()
        for key, btn in self.menu_tab_buttons:
            btn["frameColor"] = (0.20, 0.01, 0.03, 1.0) if key == self.menu_tab else (0.08, 0.01, 0.02, 1.0)

    def shift_line_hue(self, delta):
        self.cfg.line_hue = (self.cfg.line_hue + delta) % 1.0
        save_config(self.cfg)
        self.rebuild_station()
        self.refresh_ui()

    def adjust_line_thickness(self, delta):
        self.cfg.line_thickness = max(0.8, min(5.0, self.cfg.line_thickness + delta))
        save_config(self.cfg)
        self.rebuild_station()
        self.refresh_ui()

    def adjust_background(self, delta):
        self.cfg.background_value = max(0.0, min(0.22, self.cfg.background_value + delta))
        save_config(self.cfg)
        self.rebuild_station()
        self.refresh_ui()

    def adjust_fov(self, delta):
        self.cfg.fov = max(60.0, min(110.0, self.cfg.fov + delta))
        save_config(self.cfg)
        self.rebuild_station()
        self.refresh_ui()


    def _adjust_audio_field(self, field_name, delta):
        value = max(0.0, min(1.0, getattr(self.cfg, field_name) + delta))
        setattr(self.cfg, field_name, value)
        save_config(self.cfg)
        self.refresh_ui()

    def adjust_master_volume(self, delta):
        self._adjust_audio_field("master_volume", delta)

    def adjust_sfx_volume(self, delta):
        self._adjust_audio_field("sfx_volume", delta)

    def adjust_music_volume(self, delta):
        self._adjust_audio_field("music_volume", delta)

    def cycle_launch_resolution(self):
        options = [(1280, 720), (1600, 900), (1920, 1080), (2560, 1440), (3840, 2160)]
        current = (int(self.cfg.launch_width), int(self.cfg.launch_height))
        try:
            idx = options.index(current)
        except ValueError:
            idx = 2
        self.cfg.launch_width, self.cfg.launch_height = options[(idx + 1) % len(options)]
        save_config(self.cfg)
        self.refresh_ui()

    def toggle_launch_fullscreen(self):
        self.cfg.launch_fullscreen = not self.cfg.launch_fullscreen
        if self.cfg.launch_fullscreen:
            self.cfg.launch_borderless = False
        save_config(self.cfg)
        self.refresh_ui()

    def toggle_launch_borderless(self):
        self.cfg.launch_borderless = not self.cfg.launch_borderless
        if self.cfg.launch_borderless:
            self.cfg.launch_fullscreen = False
        save_config(self.cfg)
        self.refresh_ui()

    def toggle_launch_hud(self):
        self.cfg.launch_hud_visible = not self.cfg.launch_hud_visible
        save_config(self.cfg)
        self.refresh_ui()

    def adjust_launch_game_mouse_sensitivity(self, delta):
        self.cfg.launch_game_mouse_sensitivity = max(0.02, min(1.0, self.cfg.launch_game_mouse_sensitivity + delta))
        save_config(self.cfg)
        self.refresh_ui()

    def toggle_launch_invert_y(self):
        self.cfg.launch_invert_y = not self.cfg.launch_invert_y
        save_config(self.cfg)
        self.refresh_ui()

    def cycle_launch_graphics_quality(self):
        order = ["low", "medium", "high"]
        current = str(self.cfg.launch_graphics_quality).lower().strip()
        if current not in order:
            current = "medium"
        self.cfg.launch_graphics_quality = order[(order.index(current) + 1) % len(order)]
        save_config(self.cfg)
        self.refresh_ui()

    def adjust_launch_deadzone(self, delta):
        self.cfg.launch_controller_deadzone = max(0.0, min(0.45, self.cfg.launch_controller_deadzone + delta))
        save_config(self.cfg)
        self.refresh_ui()

    def refresh_ui(self):
        zone = self.current_zone_name()
        art_name = self.active_artifact["name"] if self.active_artifact else "Hub Standby"
        coords = f"X {self.player_pos.x:07.2f}  Y {self.player_pos.y:07.2f}  Z {self.player_pos.z:06.2f}"
        self.hud_label["text"] = f"{zone}\n{art_name}"
        self.coords_label["text"] = coords
        if self.menu_tab == "display":
            self.menu_info["text"] = "DISPLAY"
            self.menu_section["text"] = "VIEW // optics, contrast, chroma"
            self.menu_detail["text"] = (
                f"FOV {self.cfg.fov:.0f}\n"
                f"Brightness {self.cfg.background_value:.3f}\n"
                f"Hue {self.cfg.line_hue:.2f}\n"
                f"Line {self.cfg.line_thickness:.1f}"
            )
        elif self.menu_tab == "player":
            self.menu_info["text"] = "PLAYER"
            self.menu_section["text"] = "MOVE // height, speed, look"
            self.menu_detail["text"] = (
                f"Eye Height {self.cfg.player_eye_height:.2f}\n"
                f"Walk {self.cfg.walk_speed:.1f}\n"
                f"Run {self.cfg.sprint_speed:.1f}\n"
                f"Look Sense {self.cfg.mouse_sensitivity:.2f}"
            )
        elif self.menu_tab == "world":
            self.menu_info["text"] = "WORLD"
            self.menu_section["text"] = "PROC // density, scale, draw"
            self.menu_detail["text"] = (
                f"Grid Step {self.cfg.terrain_grid_step:.1f}\n"
                f"Terrain Height {self.cfg.terrain_height:.1f}\n"
                f"Render Radius {self.cfg.terrain_render_radius}\n"
                f"Transition {self.cfg.transition_duration:.1f}"
            )
        elif self.menu_tab == "audio":
            self.menu_info["text"] = "AUDIO"
            self.menu_section["text"] = "BUS // shared launch mix"
            self.menu_detail["text"] = (
                f"Master {self.cfg.master_volume:.2f}\n"
                f"SFX {self.cfg.sfx_volume:.2f}\n"
                f"Music {self.cfg.music_volume:.2f}\n"
                f"Ambience {self.cfg.ambience_volume:.2f}"
            )
        elif self.menu_tab == "launch":
            self.menu_info["text"] = "LAUNCH"
            self.menu_section["text"] = "HANDOFF // shared game boot config"
            self.menu_detail["text"] = (
                f"{self.cfg.launch_width}x{self.cfg.launch_height}\n"
                f"Fullscreen {'ON' if self.cfg.launch_fullscreen else 'OFF'}  Borderless {'ON' if self.cfg.launch_borderless else 'OFF'}\n"
                f"Look {self.cfg.launch_game_mouse_sensitivity:.2f}  InvertY {'ON' if self.cfg.launch_invert_y else 'OFF'}\n"
                f"HUD {'ON' if self.cfg.launch_hud_visible else 'OFF'}  GFX {str(self.cfg.launch_graphics_quality).upper()}  Deadzone {self.cfg.launch_controller_deadzone:.2f}"
            )
        elif self.menu_tab == "system":
            self.menu_info["text"] = "SYSTEM"
            self.menu_section["text"] = "OPS // shell actions"
            self.menu_detail["text"] = (
                f"Build {VERSION}\n"
                f"HUD {'ON' if self.hud_visible else 'OFF'}\n"
                f"Seed {self.cfg.world_seed}\n"
                f"Shot {LATEST_SHOT.name}"
            )
        else:
            self.menu_info["text"] = "HELP"
            self.menu_section["text"] = "OPS // controls and file refs"
            self.menu_detail["text"] = (
                "WASD move   Shift sprint   Mouse look\n"
                "E interact  T hub return   H hud   Esc settings\n"
                "Space rise (underwater)   Ctrl dive (underwater)\nF1 help     F12 screenshot\n\n"
                f"Log {LATEST_LOG.name}\n"
                f"Shot {LATEST_SHOT.name}\n"
                f"Config {CONFIG_PATH.name}"
            )
        self.menu_status["text"] = f"ACTIVE TAB // {self.menu_tab.upper()}"
        self.refresh_menu_actions()
        if self.hud_visible:
            self.hud_root.show()
            if not self.menu_open:
                self.crosshair_root.show()
        else:
            self.hud_root.hide()
            self.crosshair_root.hide()
        if self.menu_open:
            self.top_panel.hide()
            self.coords_label.hide()
            self.crosshair_root.hide()
        else:
            self.top_panel.show()
            self.coords_label.show()

    def on_window_event(self, window):
        if not self.menu_open and not SELF_TEST:
            self.recenter_mouse(force=True)

    def recenter_mouse(self, force=False):
        if SELF_TEST or self.menu_open or not self.win:
            return
        if not hasattr(self.win, "getProperties") or not hasattr(self.win, "movePointer"):
            return
        props = self.win.getProperties()
        if hasattr(props, "getForeground") and not props.getForeground() and not force:
            return
        cx = self.win.getXSize() // 2
        cy = self.win.getYSize() // 2
        self.win.movePointer(0, cx, cy)

    def update_look(self, dt):
        if self.menu_open or SELF_TEST or self.win is None or self.win.getXSize() <= 0:
            return
        if not hasattr(self.win, "getPointer"):
            return
        cx = self.win.getXSize() // 2
        cy = self.win.getYSize() // 2
        md = self.win.getPointer(0)
        dx = md.getX() - cx
        dy = md.getY() - cy
        self.player_yaw -= dx * self.cfg.mouse_sensitivity
        mouse_delta = dy * self.cfg.mouse_sensitivity
        if bool(getattr(self, "_invert_y", False)):
            mouse_delta *= -1.0
        self.player_pitch = max(-82.0, min(82.0, self.player_pitch - mouse_delta))
        if self.gamepad:
            try:
                rx = self.gamepad.findAxis(InputDevice.Axis.right_x)
                ry = self.gamepad.findAxis(InputDevice.Axis.right_y)
                gx = rx.value if rx else 0.0
                gy = ry.value if ry else 0.0
                deadzone = float(getattr(self, "_controller_deadzone", 0.12))
                if abs(gx) > deadzone:
                    self.player_yaw -= gx * self.cfg.controller_look_sensitivity * dt
                if abs(gy) > deadzone:
                    look_delta = gy * self.cfg.controller_look_sensitivity * dt
                    if bool(getattr(self, "_invert_y", False)):
                        look_delta *= -1.0
                    self.player_pitch = max(-82.0, min(82.0, self.player_pitch + look_delta))
            except Exception:
                pass
        self.camera.setHpr(self.player_yaw, self.player_pitch, 0)
        self.recenter_mouse()

    def get_move_input(self):
        move = Vec2(0, 0)
        if self.keys.get("w"):
            move.y += 1
        if self.keys.get("s"):
            move.y -= 1
        if self.keys.get("a"):
            move.x -= 1
        if self.keys.get("d"):
            move.x += 1
        if self.gamepad:
            try:
                lx = self.gamepad.findAxis(InputDevice.Axis.left_x)
                ly = self.gamepad.findAxis(InputDevice.Axis.left_y)
                deadzone = float(getattr(self, "_controller_deadzone", 0.12))
                if lx and abs(lx.value) > deadzone:
                    move.x += lx.value
                if ly and abs(ly.value) > deadzone:
                    move.y += -ly.value
            except Exception:
                pass
        if move.lengthSquared() > 1.0:
            move.normalize()
        return move

    def point_allowed(self, pos: Vec3):
        spec = self.current_world_spec()
        r = math.sqrt(pos.x * pos.x + pos.y * pos.y)
        if self.world_unlocked or self.transition_target > 0.0:
            if spec["kind"] in ("underwater", "space"):
                return r < self.cfg.terrain_chunk_size * (self.cfg.terrain_render_radius + 0.8) and -120.0 < pos.z < 120.0
            return r < self.cfg.terrain_chunk_size * (self.cfg.terrain_render_radius + 0.8)
        return r <= self.hub_radius - 1.4

    def update_player(self, dt):
        self.update_look(dt)
        move = self.get_move_input()
        target_speed = self.cfg.sprint_speed if self.keys.get("shift") else self.cfg.walk_speed
        target_vel = move * target_speed
        blend = min(1.0, dt * 7.5)
        self.move_velocity = self.move_velocity * (1.0 - blend) + target_vel * blend
        quat = self.camera.getQuat(self.render)
        forward = quat.getForward(); right = quat.getRight(); up = quat.getUp()
        spec = self.current_world_spec()
        if spec["kind"] == "underwater":
            if forward.lengthSquared() > 0: forward.normalize()
            if right.lengthSquared() > 0: right.normalize()
            vertical = 0.0
            if self.keys.get("space"): vertical += 1.0
            if self.keys.get("control"): vertical -= 1.0
            step = forward * self.move_velocity.y * dt + right * self.move_velocity.x * dt + Vec3(0, 0, vertical * target_speed * 0.65 * dt)
            candidate = Vec3(self.player_pos + step)
            if self.point_allowed(candidate):
                self.player_pos = candidate
            self.update_underwater_vehicle(dt)
        else:
            self.hide_underwater_vehicle()
            forward.z = 0; right.z = 0
            if forward.lengthSquared() > 0: forward.normalize()
            if right.lengthSquared() > 0: right.normalize()
            step = forward * self.move_velocity.y * dt + right * self.move_velocity.x * dt
            base_h = self.world_height_at(self.player_pos.x + step.x, self.player_pos.y + step.y, spec) if spec["kind"] != "space" else 0.0
            z = self.cfg.player_eye_height + (base_h * 0.02 if spec["kind"] != "space" else 0.0)
            candidate = Vec3(self.player_pos.x + step.x, self.player_pos.y + step.y, z)
            if self.point_allowed(candidate):
                self.player_pos = candidate
            self.camera.setPos(self.player_pos)

    def ensure_underwater_vehicle(self):
        if self.underwater_vehicle_root is not None and not self.underwater_vehicle_root.isEmpty():
            return
        root = self.world_root.attachNewNode("underwater-vehicle")
        root.setTransparency(TransparencyAttrib.MAlpha)
        col = self.underwater_vehicle_color
        segs = LineSegs("aqua-vehicle")
        segs.setThickness(max(1.0, self.cfg.line_thickness * 0.8))
        segs.setColor(*col)
        pts = [Vec3(-2.8, -4.0, -0.8), Vec3(0.0, 5.4, 0.0), Vec3(2.8, -4.0, -0.8), Vec3(0.0, -2.0, 1.6)]
        for a, b in [(0,1),(1,2),(2,0),(0,3),(1,3),(2,3)]:
            segs.moveTo(pts[a]); segs.drawTo(pts[b])
        segs.moveTo(-2.1, -1.0, 0.0); segs.drawTo(-4.4, -3.0, -0.1)
        segs.moveTo(2.1, -1.0, 0.0); segs.drawTo(4.4, -3.0, -0.1)
        segs.moveTo(0.0, -3.6, 0.2); segs.drawTo(0.0, -6.2, -0.3)
        np = root.attachNewNode(segs.create())
        np.setAntialias(AntialiasAttrib.MLine)
        np.setTransparency(TransparencyAttrib.MAlpha)
        glow = CardMaker("aqua-canopy")
        glow.setFrame(-1.1, 1.1, -0.7, 0.7)
        canopy = root.attachNewNode(glow.generate())
        canopy.setPos(0, 0.2, 0.35)
        canopy.setHpr(0, 0, 18)
        canopy.setColor(0.22, 0.96, 0.92, 0.18)
        canopy.setTransparency(TransparencyAttrib.MAlpha)
        canopy.setDepthWrite(False)
        self.underwater_vehicle_root = root

    def hide_underwater_vehicle(self):
        if self.underwater_vehicle_root is not None and not self.underwater_vehicle_root.isEmpty():
            self.underwater_vehicle_root.hide()

    def update_underwater_vehicle(self, dt):
        self.ensure_underwater_vehicle()
        if self.underwater_vehicle_root is None or self.underwater_vehicle_root.isEmpty():
            return
        self.underwater_vehicle_root.show()
        quat = self.camera.getQuat(self.render)
        forward = quat.getForward()
        if forward.lengthSquared() > 0.001:
            forward.normalize()
        self.underwater_vehicle_root.setPos(self.player_pos)
        heading = math.degrees(math.atan2(-forward.x, forward.y))
        pitch = max(-28.0, min(28.0, math.degrees(math.asin(max(-1.0, min(1.0, forward.z))))))
        self.underwater_vehicle_root.setHpr(heading, pitch, math.sin(self.elapsed * 1.6) * 3.5)
        chase = self.player_pos - forward * 18.0 + Vec3(0, 0, 6.0)
        self.camera.setPos(chase)
        self.camera.lookAt(self.player_pos + forward * 7.5)

    def update_artifact_focus(self, dt):
        self.find_nearest_artifact()
        spec = self.current_world_spec()
        if spec["kind"] != self.last_world_kind:
            self.last_world_kind = spec["kind"]
            self.clear_world_chunks()
            self.update_world_chunks(force=True)
        if self.transition_progress < self.transition_target:
            self.transition_progress = min(self.transition_target, self.transition_progress + dt / max(0.001, self.cfg.transition_duration))
        elif self.transition_progress > self.transition_target:
            self.transition_progress = max(self.transition_target, self.transition_progress - dt / max(0.001, self.cfg.transition_duration))

        target_yaw = 0.0
        target_pitch = 58.0
        if self.active_artifact is not None:
            target_yaw = self.active_artifact["yaw"]
            target_pitch = self.active_artifact["pitch"]
        current_h = self.lens_pivot.getH()
        current_p = self.lens_pivot.getP()
        blend = min(1.0, dt * (1.3 + self.transition_progress * 0.9))
        self.lens_pivot.setH(current_h + (target_yaw - current_h) * blend)
        self.lens_pivot.setP(current_p + (-target_pitch - current_p) * blend)

        lens_alpha = 0.70 + self.transition_progress * 0.24
        self.lens_root.setColorScale(1, 1, 1, lens_alpha)
        self.world_root.setColorScale(1, 1, 1, self.transition_progress)
        self.world_root.show() if self.transition_progress > 0.01 else self.world_root.hide()
        self.apply_world_theme(dt)

        for i, node in enumerate(self.galaxy_nodes):
            alpha = 0.0
            if self.active_artifact_id == i:
                alpha = min(1.0, max(0.0, (self.transition_progress - 0.16) / 0.84))
            node.setColorScale(1, 1, 1, alpha)

    def animate_accents(self, dt):
        pulse = 0.10 + 0.05 * math.sin(self.elapsed * 1.6)
        self.accent_root.setColorScale(1, 1, 1, 0.78 + pulse)
        self.line_root.setColorScale(1, 1, 1, 0.98)
        self.dome_root.setColorScale(1, 1, 1, 0.96)
        if self.menu_open:
            self.center_hint["text"] = ""
            return
        if self.is_near_core():
            self.center_hint["text"] = "E // CORE OPTIONS"
        elif self.nearest_artifact is not None and self.nearest_artifact_dist < self.nearest_artifact["radius"]:
            self.center_hint["text"] = f"E // LINK {self.nearest_artifact['name']}"
        elif self.transition_progress > 0.0 and self.active_artifact is not None:
            spec = self.current_world_spec()
            suffix = " // VEHICLE SWIM" if spec["kind"] == "underwater" else (" // VOID" if spec["kind"] == "space" else (" // ETCHLINE" if spec["kind"] == "campaign" else (" // ASHFALL" if spec["kind"] == "conquest" else "")))
            self.center_hint["text"] = f"SYNC // {self.active_artifact['name']}{suffix}"
        else:
            self.center_hint["text"] = self.current_zone_name()

    def update_world_actors(self, dt):
        spec = self.current_world_spec()
        player = Vec3(self.player_pos)
        for actor in self.world_actors:
            if actor.root.isEmpty():
                continue
            if actor.kind == 'ship':
                drift = math.sin(self.elapsed * 0.22 + actor.phase) * 6.0
                actor.root.setPos(actor.home + Vec3(drift, math.cos(self.elapsed * 0.18 + actor.phase) * 14.0, math.sin(self.elapsed * 0.27 + actor.phase) * 9.0))
                actor.root.setHpr((self.elapsed * 12.0 + actor.seed % 360) % 360, math.sin(self.elapsed + actor.phase) * 4.0, math.cos(self.elapsed + actor.phase) * 6.0)
            elif actor.kind in ('fish', 'whale'):
                toward = player - actor.root.getPos()
                dist = toward.length()
                if actor.kind == 'fish' and 12.0 < dist < 34.0:
                    actor.follow_timer = min(4.0, actor.follow_timer + dt)
                else:
                    actor.follow_timer = max(0.0, actor.follow_timer - dt * 0.5)
                sway = Vec3(math.sin(self.elapsed * (1.4 if actor.kind == 'fish' else 0.5) + actor.phase) * (2.4 if actor.kind == 'fish' else 6.5), math.cos(self.elapsed * (1.1 if actor.kind == 'fish' else 0.4) + actor.phase) * (2.0 if actor.kind == 'fish' else 5.0), math.sin(self.elapsed * (1.7 if actor.kind == 'fish' else 0.35) + actor.phase) * (1.2 if actor.kind == 'fish' else 3.4))
                follow = Vec3(0, 0, 0)
                if actor.follow_timer > 0.01 and dist > 0.001:
                    toward.normalize()
                    follow = toward * min(6.0, actor.follow_timer * 1.6)
                actor.root.setPos(actor.home + sway + follow)
                actor.root.lookAt(actor.root.getPos() + sway + (follow if follow.lengthSquared() > 0.001 else Vec3(1, 0, 0)))
            elif actor.kind in ('grazer', 'strider', 'canopy_beast'):
                stride = Vec3(math.sin(self.elapsed * (0.42 + actor.speed * 0.08) + actor.phase) * (2.8 + actor.speed), math.cos(self.elapsed * (0.35 + actor.speed * 0.06) + actor.phase) * (2.2 + actor.speed * 0.7), 0.0)
                bob = math.sin(self.elapsed * (0.9 + actor.speed * 0.12) + actor.phase) * 0.6
                actor.root.setPos(actor.home + stride + Vec3(0, 0, bob))
                actor.root.lookAt(actor.root.getPos() + Vec3(stride.x if abs(stride.x) > 0.01 else 1.0, stride.y, 0.18))
                actor.root.setP(math.sin(self.elapsed * 0.7 + actor.phase) * 4.0)
            elif actor.kind in ('ray', 'orbiter'):
                drift = Vec3(math.sin(self.elapsed * (0.48 if actor.kind == 'ray' else 0.22) + actor.phase) * (4.0 if actor.kind == 'ray' else 7.0), math.cos(self.elapsed * (0.40 if actor.kind == 'ray' else 0.26) + actor.phase) * (3.2 if actor.kind == 'ray' else 6.0), math.sin(self.elapsed * (0.52 if actor.kind == 'ray' else 0.31) + actor.phase) * (1.8 if actor.kind == 'ray' else 5.0))
                actor.root.setPos(actor.home + drift)
                actor.root.setHpr((self.elapsed * (18.0 if actor.kind == 'orbiter' else 9.0) + actor.seed % 360) % 360, math.sin(self.elapsed + actor.phase) * 3.2, math.cos(self.elapsed * 0.7 + actor.phase) * 4.2)
            elif actor.kind == 'tree':
                actor.root.setR(math.sin(self.elapsed * 0.35 + actor.phase) * 2.2)
            elif actor.kind in ('campaign_enemy', 'conquest_unit'):
                actor.root.setR(math.sin(self.elapsed * 0.8 + actor.phase) * 1.2)

    def fire_internal_weapon(self):
        if self.internal_mode.mode_key not in {"campaign", "conquest"}:
            return
        if self.internal_mode.weapon_cooldown > 0.0 or self.internal_mode.ammo <= 0.0:
            return
        quat = self.camera.getQuat(self.render)
        forward = quat.getForward()
        if forward.lengthSquared() <= 0.001:
            return
        forward.normalize()
        start = self.player_pos + forward * 2.2
        color = (0.04, 0.04, 0.04, 1.0) if self.internal_mode.mode_key == "campaign" else (1.0, 0.72, 0.35, 1.0)
        speed = 86.0 if self.internal_mode.mode_key == "campaign" else 74.0
        damage = 16.0 if self.internal_mode.mode_key == "campaign" else 22.0
        self.spawn_world_projectile(start, forward * speed, "player", damage, color)
        self.internal_mode.weapon_cooldown = 0.16 if self.internal_mode.mode_key == "campaign" else 0.22
        self.internal_mode.ammo = max(0.0, self.internal_mode.ammo - 1.0)

    def update_internal_projectiles(self, dt):
        if self.internal_mode.weapon_cooldown > 0.0:
            self.internal_mode.weapon_cooldown = max(0.0, self.internal_mode.weapon_cooldown - dt)
        if self.internal_mode.last_hit_flash > 0.0:
            self.internal_mode.last_hit_flash = max(0.0, self.internal_mode.last_hit_flash - dt)
        if self.internal_mode.fire_down and not self.menu_open:
            self.fire_internal_weapon()
        alive = []
        for proj in self.internal_mode.projectiles:
            if proj.node.isEmpty():
                continue
            proj.ttl -= dt
            if proj.ttl <= 0.0:
                proj.node.removeNode()
                continue
            pos = proj.node.getPos() + proj.velocity * dt
            proj.node.setPos(pos)
            hit = None
            for actor in self.world_actors:
                if actor.root.isEmpty() or actor.team == proj.team or actor.team == 'neutral':
                    continue
                if (actor.root.getPos(self.render) - pos).length() < 3.1:
                    hit = actor
                    break
            if hit is not None:
                hit.health -= proj.damage
                self.internal_mode.last_hit_flash = 0.2
                if hit.health <= 0.0:
                    try:
                        hit.root.removeNode()
                    except Exception:
                        pass
                    self.internal_mode.score += 10
                proj.node.removeNode()
                continue
            alive.append(proj)
        self.internal_mode.projectiles = alive

    def update_internal_modes(self, dt):
        spec = self.current_world_spec()
        if spec["kind"] == "campaign":
            enemy_count = sum(1 for a in self.world_actors if a.team == 'enemy' and not a.root.isEmpty())
            self.internal_mode.objective = f"ETCHLINE BREACH // hostiles {enemy_count:02d}"
            if enemy_count == 0:
                self.internal_mode.objective = "ETCHLINE BREACH // area clear"
                self.internal_mode.ammo = min(100.0, self.internal_mode.ammo + dt * 8.0)
        elif spec["kind"] == "conquest":
            enemy_count = sum(1 for a in self.world_actors if a.team == 'enemy' and not a.root.isEmpty())
            nearby_allies = sum(1 for a in self.world_actors if a.team == 'ally' and not a.root.isEmpty() and (a.root.getPos(self.render) - self.player_pos).length() < 22.0)
            gain = (0.8 + nearby_allies * 0.18) * dt if enemy_count < 6 else 0.22 * dt
            self.internal_mode.capture_energy = min(100.0, self.internal_mode.capture_energy + gain)
            self.internal_mode.objective = f"ASHFALL PUSH // relay {self.internal_mode.capture_energy:05.1f}%  raiders {enemy_count:02d}"
            if self.internal_mode.capture_energy >= 100.0:
                self.internal_mode.objective = "ASHFALL PUSH // relay secured"
        self.update_internal_projectiles(dt)

    def capture_latest_screenshot(self, task=None):
        ensure_dirs()
        target = Path(ARTIFACT_SHOT_PATH) if ARTIFACT_SHOT_PATH else LATEST_SHOT
        if self.win is not None:
            self.win.saveScreenshot(Filename.fromOsSpecific(str(target)))
        if not SELF_TEST:
            self.center_hint["text"] = f"Saved {target.name}"
        return Task.done if task is not None else None

    def self_test_setup(self, task):
        shot_id = ARTIFACT_SHOT_ID if ARTIFACT_SHOT_ID is not None else 7
        shot_id = max(0, min(9, shot_id))
        self.active_artifact = self.artifacts[shot_id] if shot_id < len(self.artifacts) and self.artifacts else None
        self.active_artifact_id = shot_id
        if shot_id == 8:
            self.active_artifact = {"id": 8, "name": WORLD_SPECS[8]["name"], "yaw": 168.0, "pitch": 11.0, "radius": 0.0}
            self.internal_mode = InternalModeState(mode_key="campaign", player_health=100.0, ammo=100.0, objective="ETCHLINE BREACH // collapse hostile pylons")
        elif shot_id == 9:
            self.active_artifact = {"id": 9, "name": WORLD_SPECS[9]["name"], "yaw": 156.0, "pitch": 10.0, "radius": 0.0}
            self.internal_mode = InternalModeState(mode_key="conquest", player_health=140.0, ammo=160.0, objective="ASHFALL PUSH // clear raiders and charge relay")
        self.transition_target = 1.0
        self.transition_progress = 1.0
        self.world_unlocked = True
        self.set_hub_fill_enabled(True, instant=True)
        poses = {4:(Vec3(26, 38, self.cfg.player_eye_height + 1.2), 148.0, -12.0), 5:(Vec3(18, 12, 22.0), 132.0, -8.0), 6:(Vec3(24, 34, -8.0), 150.0, -6.0), 7:(Vec3(28, 34, self.cfg.player_eye_height + 1.0), 144.0, -12.0), 8:(Vec3(28, 40, self.cfg.player_eye_height + 0.2), 172.0, -8.0), 9:(Vec3(34, 46, self.cfg.player_eye_height + 0.25), 166.0, -9.0)}
        pos, yaw, pitch = poses.get(shot_id, (Vec3(0, 14.0, self.cfg.player_eye_height), 182.0, -8.0))
        self.player_yaw = yaw
        self.player_pitch = pitch
        self.player_pos = pos
        self.camera.setPos(self.player_pos)
        self.camera.setHpr(self.player_yaw, self.player_pitch, 0)
        self.update_world_chunks(force=True)
        self.apply_world_theme(1.0)
        self.refresh_ui()
        return Task.done

    def self_test_exit(self, task):
        report = {
            "game": GAME_NAME,
            "version": VERSION,
            "config": asdict(self.cfg),
            "active_artifact": self.active_artifact_id,
            "transition_progress": self.transition_progress,
            "screenshot_exists": LATEST_SHOT.exists(),
            "latest_log": str(LATEST_LOG),
            "crash_log_exists": CRASH_LOG.exists(),
            "campaign_path": str(self.campaign_path) if self.campaign_path else None,
            "vector_wars_path": str(self.vector_wars_path) if self.vector_wars_path else None,
        }
        SELF_TEST_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        self.userExit()
        return Task.done

    def _frame_step(self, dt):
        dt = min(0.033, max(0.0, float(dt or 0.0)))
        self.elapsed += dt
        self.update_player(dt)
        self.update_world_chunks()
        self.update_artifact_focus(dt)
        self.update_world_actors(dt)
        if abs(self.hub_fill_alpha - self.hub_fill_target) > 0.001:
            blend = min(1.0, dt * 0.72)
            self.hub_fill_alpha += (self.hub_fill_target - self.hub_fill_alpha) * blend
            if abs(self.hub_fill_alpha - self.hub_fill_target) < 0.01:
                self.hub_fill_alpha = self.hub_fill_target
            self.update_hub_fill_visuals()
        self.animate_accents(dt)
        self.refresh_ui()

    def update_task(self, task):
        self._frame_step(globalClock.getDt())
        return Task.cont

    def hosted_step(self, dt: float) -> bool:
        if self._hosted_destroyed:
            return False
        try:
            self._hosted_elapsed += max(0.0, float(dt or 0.0))
            self._frame_step(dt)
            return True
        except Exception as exc:
            print(f"holoshell_hosted_step_error:{exc.__class__.__name__}:{exc}")
            return False

    def hosted_action(self, action: str) -> bool:
        action = str(action or "").strip().lower()
        if action in {"escape", "pause", "menu", "return", "return_to_core"}:
            return False
        if action.endswith("_up") and action[:-3] in {"w", "a", "s", "d", "shift", "space", "control"}:
            self.set_key(action[:-3], False)
            return True
        if action in {"w", "a", "s", "d", "shift", "space", "control"}:
            self.set_key(action, True)
            return True
        if action == "mouse1":
            self.set_fire_down(True)
            return True
        if action == "mouse1_up":
            self.set_fire_down(False)
            return True
        if action in {"e", "e_down"}:
            self.interact()
            return True
        if action in {"q", "q_down"}:
            self.core_secondary_action()
            return True
        if action in {"toggle_dimension_ui", "dimension_ui", "h"}:
            self.toggle_hud()
            return True
        if action == "f1":
            self.toggle_help_overlay()
            return True
        if action == "f12":
            self.capture_latest_screenshot()
            return True
        if action == "t":
            self.teleport_to_hub()
            return True
        if action in {"1", "number_1"}:
            self.core_launch_campaign()
            return True
        if action in {"2", "number_2"}:
            self.core_launch_vector_wars()
            return True
        if action in {"3", "number_3"}:
            self.core_launch_vector_conquest()
            return True
        if action in {"5", "number_5"}:
            self.core_toggle_infill()
            return True
        return False

    def hosted_destroy(self) -> None:
        if self._hosted_destroyed:
            return
        self._hosted_destroyed = True
        try:
            self.ignoreAll()
        except Exception:
            pass
        try:
            self.removeAllTasks()
        except Exception:
            pass
        try:
            if self.external_process is not None and self.external_process.poll() is None:
                self.external_process.terminate()
        except Exception:
            pass
        try:
            self.clear_world_actors()
        except Exception:
            pass
        try:
            self.clear_world_chunks()
        except Exception:
            pass
        # HoloVerse 282.50: destroy the menu buttons properly first. Removing their parent node
        # alone left each button's click handler registered in HoloVerse after every visit.
        for button in [btn for _key, btn in getattr(self, "menu_tab_buttons", [])] + list(getattr(self, "menu_buttons", [])):
            try:
                button.destroy()
            except Exception:
                pass
        self.menu_tab_buttons = []
        self.menu_buttons = []
        for name in ("help_root", "menu_root", "core_console_root", "crosshair_root", "hud_root", "root_3d"):
            node = getattr(self, name, None)
            if node is not None:
                try:
                    if not node.isEmpty():
                        node.removeNode()
                except Exception:
                    try:
                        node.destroy()
                    except Exception:
                        pass
        self.world_actors = []
        self.terrain_chunks = {}



HoloShellApp = CommandHubApp


def main():
    ensure_dirs()
    install_logging()
    if CRASH_LOG.exists():
        CRASH_LOG.unlink()
    install_crash_reporter()
    write_patch_notes()
    print(f"Launching {GAME_NAME} {VERSION}")
    print(f"SELF_TEST={SELF_TEST}")
    app = CommandHubApp()
    app.run()


if __name__ == "__main__":
    main()
