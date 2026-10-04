from __future__ import annotations

import argparse
import json
import math
import os
import sys
import traceback
import platform
import struct
import random
from datetime import datetime
from pathlib import Path

# Support QA tools that import main.py by file path rather than normal module launch.
_BOOT_ROOT = Path(__file__).resolve().parent
if str(_BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOT_ROOT))

from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    Filename,
    PNMImage,
    Texture,
    TextNode,
    CardMaker,
    TransparencyAttrib,
    Fog,
    Vec3,
    Vec4,
    WindowProperties,
    PandaSystem,
    Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter,
    loadPrcFileData,
)
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from direct.showbase.ShowBase import ShowBase
from direct.showbase import Audio3DManager
from direct.task import Task

def _mount_limbo_common() -> Path:
    """DreamCatcher lives inside Mirror's Limbo; mount Limbo's shared gx_common package."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "gx_common" / "__init__.py").is_file():
            if str(parent) not in sys.path:
                sys.path.append(str(parent))
            return parent
    raise SystemExit("DreamCatcher must stay inside the Mirror's Limbo folder (gx_common not found).")


LIMBO_ROOT = _mount_limbo_common()
from gx_common import shared  # noqa: E402
from gx_common.travel import WorldTravel  # noqa: E402

ROOT = Path(__file__).resolve().parent


def panda_filename(path) -> Filename:
    """Convert an OS-native filesystem path to Panda3D's internal Filename form."""
    return Filename.fromOsSpecific(str(Path(path).resolve()))


def _user_data_dir() -> Path:
    """Return a writable per-user runtime directory without touching the game install."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / "GLITCHED_MATRIX" / "DreamCatcherAlternate"
    state = os.environ.get("XDG_STATE_HOME")
    root = Path(state) if state else Path.home() / ".local" / "state"
    return root / "glitched-matrix" / "dreamcatcher-alternate"


USER_DATA_DIR = _user_data_dir()
LOG_DIR = USER_DATA_DIR / "logs"
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    # Read-only or heavily restricted environments should still be able to launch.
    LOG_DIR = ROOT


def _append_runtime_log(message: str) -> None:
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    log_path = LOG_DIR / "runtime.log"
    try:
        if log_path.exists() and log_path.stat().st_size > 512 * 1024:
            old_path = LOG_DIR / "runtime.previous.log"
            try:
                if old_path.exists():
                    old_path.unlink()
                log_path.replace(old_path)
            except OSError:
                pass
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {message}\n")
    except OSError:
        pass


def _write_crash_log(exc: BaseException) -> None:
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    body = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        (LOG_DIR / f"crash_{stamp}.log").write_text(body, encoding="utf-8")
    except OSError:
        pass


REQUIRED_JSON = [
    "data/house_layout.json", "data/master_bedroom_composition.json",
    "data/architectural_identity.json", "data/floor2_furnishings.json",
    "data/analog_tv_system.json", "data/tv_channel_visuals.json",
    "data/crt_signal_profile.json", "data/window_audio.json",
    "data/footstep_audio.json", "data/tv_channel_audio.json",
    "data/alternate_voice_lines.json", "data/dreamcatcher_lore.json",
]

REQUIRED_MEDIA = [
    "assets/textures/water_stain_ceiling_a.png",
    "assets/textures/water_stain_ceiling_b.png",
    "assets/textures/water_stain_corner.png",
    "assets/textures/water_puddle.png",
    "assets/textures/wall_scuffs.png",
    "assets/audio/window_exterior.wav",
    "assets/audio/footstep_carpet.wav",
    "assets/audio/footstep_wood.wav",
    "assets/audio/footstep_attic_wood.wav",
    "assets/audio/footstep_cement.wav",
    "assets/audio/forest_entity/belief_question.wav",
    "assets/audio/forest_entity/belief_yes.wav",
    "assets/audio/forest_entity/belief_no.wav",
    "assets/audio/window_events/wind_gust_01.wav",
    "assets/audio/window_events/wind_gust_02.wav",
    "assets/audio/window_events/branch_scrape_01.wav",
    "assets/audio/window_events/window_frame_creak_01.wav",
]

# Recovered media contracts are required runtime assets too. If a later pass drops
# one of these files, compat-check must fail before the branch advances.
_TV_CHANNEL_IDS = (
    "security", "news", "cartoon", "archive", "combat", "dance", "dream", "emergency",
    "kaiju", "league", "mix", "noisefight", "pirate", "racing", "ritual", "shop",
    "sportcast", "sports", "static", "surveil", "teletext", "tunnel", "weather",
    "wilderness", "wrestling",
)
_ALT_VOICE_IDS = (
    "attention_01", "approach_01", "sleep_check_01", "door_command_01", "tv_watch_01",
    "downstairs_01", "retreat_01", "fear_01", "memory_01", "memory_02", "protection_01",
    "tv_disobedience_01", "tv_disobedience_02", "broadcast_search_01",
)
REQUIRED_MEDIA += [f"assets/audio/tv_channels/{cid}.wav" for cid in _TV_CHANNEL_IDS]
REQUIRED_MEDIA += [f"assets/audio/alternate_voice/{vid}.wav" for vid in _ALT_VOICE_IDS]


def _preflight_runtime_assets() -> list[str]:
    required = list(REQUIRED_JSON) + list(REQUIRED_MEDIA)
    return [rel for rel in required if not (ROOT / rel).is_file()]


def _preflight_panda_paths() -> list[str]:
    """Verify Panda3D can resolve the OS-native path after conversion."""
    bad = []
    for rel in REQUIRED_JSON + REQUIRED_MEDIA:
        path = ROOT / rel
        if path.is_file() and not panda_filename(path).exists():
            bad.append(rel)
    return bad


def _preflight_json_errors() -> list[str]:
    errors = []
    for rel in REQUIRED_JSON:
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{rel}: {type(exc).__name__}: {exc}")
    return errors


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DreamCatcher Alternate")
    p.add_argument("--test-shot", type=str, default=os.environ.get("GXTOOL_BRIDGE_SCREENSHOT_PATH", ""), help="capture one deterministic runtime screenshot and exit")
    p.add_argument("--arm-test-shot", type=str, default="", help="capture Pass 82 note-interception arm proof and exit")
    p.add_argument("--broadcast-test-shot", type=str, default="", help="capture Pass 83 random task-broadcast proof and exit")
    p.add_argument("--forest-test-shot", type=str, default="", help="capture Pass 90 forest encounter proof and exit")
    p.add_argument("--manifest-test-shot", type=str, default="", help="capture Pass 96 chair manifestation proof and exit")
    p.add_argument("--finale-test-shot", type=str, default="", help="capture Pass 98 dramatic attic finale proof and exit")
    p.add_argument("--lore-test-shot", type=str, default="", help="capture Pass 100 DreamCatcher archive lore proof and exit")
    p.add_argument("--bridge-channel-test-shot", type=str, default="", help="capture Pass 102 colored DREAM bridge-channel proof and exit")
    p.add_argument("--bridge-prepare-test-shot", type=str, default="", help="capture Pass 103 prepared DREAM bridge proof and exit")
    p.add_argument("--headless", action="store_true", help="use p3headlessgl offscreen rendering")
    p.add_argument("--no-audio", action="store_true")
    p.add_argument("--compat-check", action="store_true", help="print runtime/asset compatibility diagnostics and exit")
    return p.parse_args()


ARGS = parse_args()
if ARGS.compat_check:
    missing = _preflight_runtime_assets()
    json_errors = _preflight_json_errors()
    panda_path_errors = _preflight_panda_paths()
    panda_version = PandaSystem.getVersionString()
    python_bits = struct.calcsize("P") * 8
    version_ok = panda_version == "1.10.16"
    bits_ok = python_bits == 64
    print(f"Python: {sys.version.split()[0]} ({python_bits}-bit, {platform.system()} {platform.machine()})")
    print(f"Panda3D: {panda_version} ({'PASS' if version_ok else 'UNTESTED'})")
    print(f"Game root: {ROOT}")
    print(f"User data: {USER_DATA_DIR}")
    print(f"Required files: {'PASS' if not missing else 'FAIL'}")
    print(f"JSON parse: {'PASS' if not json_errors else 'FAIL'}")
    print(f"Panda file paths: {'PASS' if not panda_path_errors else 'FAIL'}")
    print(f"64-bit runtime: {'PASS' if bits_ok else 'FAIL'}")
    for rel in missing:
        print(f"MISSING: {rel}")
    for item in json_errors:
        print(f"INVALID_JSON: {item}")
    for rel in panda_path_errors:
        print(f"PANDA_PATH_FAIL: {rel}")
    ok = (not missing) and (not json_errors) and (not panda_path_errors) and version_ok and bits_ok
    raise SystemExit(0 if ok else 2)

# Pass 99 — DreamCatcher Alternate display authority.  Standalone launches default
# to borderless desktop; settings are loaded before ShowBase creates the visible window.
DISPLAY_SETTINGS_FILE = USER_DATA_DIR / "display_settings.json"
DISPLAY_RESOLUTIONS = [(1280, 720), (1600, 900), (1920, 1080), (2560, 1440), (3840, 2160)]
DISPLAY_DEFAULTS = {
    "mode": "borderless",
    "resolution": [1920, 1080],
    "vsync": True,
    "fov": 74,
    "fps_meter": False,
}

def _load_display_settings() -> dict:
    cfg = dict(DISPLAY_DEFAULTS)
    try:
        if DISPLAY_SETTINGS_FILE.is_file():
            raw = json.loads(DISPLAY_SETTINGS_FILE.read_text(encoding="utf-8"))
            if str(raw.get("mode", "")) in ("borderless", "fullscreen", "windowed"):
                cfg["mode"] = str(raw["mode"])
            res = raw.get("resolution")
            if isinstance(res, list) and len(res) == 2 and tuple(map(int, res)) in DISPLAY_RESOLUTIONS:
                cfg["resolution"] = [int(res[0]), int(res[1])]
            cfg["vsync"] = bool(raw.get("vsync", cfg["vsync"]))
            fov = int(raw.get("fov", cfg["fov"]))
            cfg["fov"] = max(60, min(95, fov))
            cfg["fps_meter"] = bool(raw.get("fps_meter", cfg["fps_meter"]))
    except Exception as exc:
        _append_runtime_log(f"DISPLAY settings_load_failed {type(exc).__name__}: {exc}")
    return cfg

def _desktop_size() -> tuple[int, int]:
    # Windows is the shipping standalone target.  Query it before ShowBase opens
    # the first visible window so borderless mode does not flash a small 1280x720 window.
    if os.name == "nt":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass
            w = int(user32.GetSystemMetrics(0)); h = int(user32.GetSystemMetrics(1))
            if w >= 640 and h >= 480:
                return w, h
        except Exception:
            pass
    return (1920, 1080)

def _apply_shared_settings(cfg: dict) -> dict:
    """Mirror's Limbo owns display mode, resolution, v-sync, FOV preference and mouse feel."""
    shared_cfg = shared.load_settings()
    if shared_cfg["present"]:
        cfg["mode"] = shared_cfg["display_mode"]
        if tuple(shared_cfg["resolution"]) in DISPLAY_RESOLUTIONS:
            cfg["resolution"] = list(shared_cfg["resolution"])
        cfg["vsync"] = bool(shared_cfg["vsync"])
        cfg["fov"] = int(round(shared.world_fov(DISPLAY_DEFAULTS["fov"], shared_cfg["fov"], 60, 95)))
    return cfg


SHARED_SETTINGS = shared.load_settings()
DISPLAY_SETTINGS = _apply_shared_settings(_load_display_settings())
DESKTOP_SIZE = _desktop_size()
_CAPTURE_MODE = bool(ARGS.headless or ARGS.test_shot or ARGS.arm_test_shot or ARGS.broadcast_test_shot or ARGS.forest_test_shot or ARGS.manifest_test_shot or ARGS.finale_test_shot or ARGS.lore_test_shot or ARGS.bridge_channel_test_shot or ARGS.bridge_prepare_test_shot)
if _CAPTURE_MODE:
    loadPrcFileData("", "win-size 1280 720")
    loadPrcFileData("", "load-display p3headlessgl")
    loadPrcFileData("", "window-type offscreen")
    loadPrcFileData("", "audio-library-name null")
    loadPrcFileData("", "notify-level-device fatal")
else:
    mode = DISPLAY_SETTINGS["mode"]
    rw, rh = map(int, DISPLAY_SETTINGS["resolution"])
    loadPrcFileData("", "window-title DreamCatcher Alternate")
    if mode == "borderless":
        dw, dh = DESKTOP_SIZE
        loadPrcFileData("", f"win-size {dw} {dh}")
        loadPrcFileData("", "win-origin 0 0")
        loadPrcFileData("", "fullscreen #f")
        loadPrcFileData("", "undecorated #t")
    elif mode == "fullscreen":
        loadPrcFileData("", f"win-size {rw} {rh}")
        loadPrcFileData("", "fullscreen #t")
        loadPrcFileData("", "undecorated #t")
    else:
        loadPrcFileData("", f"win-size {rw} {rh}")
        loadPrcFileData("", "fullscreen #f")
        loadPrcFileData("", "undecorated #f")
    loadPrcFileData("", "sync-video #t" if DISPLAY_SETTINGS["vsync"] else "sync-video #f")
if ARGS.no_audio:
    loadPrcFileData("", "audio-library-name null")
loadPrcFileData("", "show-frame-rate-meter #t" if DISPLAY_SETTINGS["fps_meter"] else "show-frame-rate-meter #f")


class DreamCatcherAlternateGame(ShowBase):
    PLAYER_RADIUS = 0.23
    WALK_SPEED = 2.35
    SPRINT_SPEED = 3.75
    MOUSE_SENS = 0.12
    MOVE_COLLISION_STEP = 0.06  # Pass 89: substep movement prevents threshold corner snagging.
    INTERACTION_RADIUS_SCALE = 1.18
    INTERACTION_FACING_DOT = 0.42
    INTERACTION_STICKY_DOT = 0.26

    def __init__(self):
        super().__init__()
        missing = _preflight_runtime_assets()
        if missing:
            raise RuntimeError("Missing required runtime files: " + ", ".join(missing))
        _append_runtime_log(f"START build=ML-P151-DC106-AN21 python={sys.version.split()[0]} platform={platform.platform()} root={ROOT}")
        self.disableMouse()
        self._window_was_foreground = True
        self._focus_auto_paused = False
        self._last_window_size = (0, 0)
        self._runtime_cleanup_done = False
        # ShowBase calls exitFunc when the user closes the main window. Keep all
        # exit paths on the same idempotent cleanup routine.
        self.exitFunc = self._runtime_cleanup
        self.setBackgroundColor(0.006, 0.006, 0.008, 1)
        self.display_settings = dict(DISPLAY_SETTINGS)
        # Mirror's Limbo mouse feel (degrees per pixel in all three worlds).
        self.mouse_sens = float(SHARED_SETTINGS["mouse_sensitivity"]) if SHARED_SETTINGS["present"] else self.MOUSE_SENS
        self.mouse_invert = -1.0 if SHARED_SETTINGS["invert_y"] else 1.0
        self.desktop_size = tuple(DESKTOP_SIZE)
        self.camLens.setFov(float(self.display_settings.get("fov", 74)))
        self.camLens.setNearFar(0.05, 80)
        self.setFrameRateMeter(bool(self.display_settings.get("fps_meter", False)))

        self.layout = json.loads((ROOT / "data" / "house_layout.json").read_text())
        self.master = json.loads((ROOT / "data" / "master_bedroom_composition.json").read_text())
        self.arch = json.loads((ROOT / "data" / "architectural_identity.json").read_text())
        self.window_audio_config = json.loads((ROOT / "data" / "window_audio.json").read_text())
        self.footstep_audio_config = json.loads((ROOT / "data" / "footstep_audio.json").read_text())
        self.room = next(r for r in self.layout["rooms"] if r["id"] == "f2_master")
        self.hall = next(r for r in self.layout["rooms"] if r["id"] == "f2_hall")
        self.bath = next(r for r in self.layout["rooms"] if r["id"] == "f2_bath")
        self.stair = next(r for r in self.layout["rooms"] if r["id"] == "f2_stair")
        self.bed2 = next(r for r in self.layout["rooms"] if r["id"] == "f2_bed2")
        self.bed3 = next(r for r in self.layout["rooms"] if r["id"] == "f2_bed3")
        self.bed4 = next(r for r in self.layout["rooms"] if r["id"] == "f2_bed4")
        self.room_rect = self.room["rect"]
        self.hall_rect = self.hall["rect"]
        self.bath_rect = self.bath["rect"]
        self.stair_rect = self.stair["rect"]
        self.bed2_rect = self.bed2["rect"]
        self.bed3_rect = self.bed3["rect"]
        self.bed4_rect = self.bed4["rect"]
        self.master_portal = next(p for p in self.layout["portals"] if p["id"] == "p_master_hall")
        self.bath_portal = next(p for p in self.layout["portals"] if p["id"] == "p_bath_hall")
        self.stair_portal = next(p for p in self.layout["portals"] if p["id"] == "p_stair_hall")
        self.bed2_portal = next(p for p in self.layout["portals"] if p["id"] == "p_bed2_hall")
        self.bed3_portal = next(p for p in self.layout["portals"] if p["id"] == "p_bed3_hall")
        self.bed4_portal = next(p for p in self.layout["portals"] if p["id"] == "p_bed4_hall")
        self.floor2_furnishings = json.loads((ROOT / "data" / "floor2_furnishings.json").read_text())
        self.tv_authority = json.loads((ROOT / "data" / "analog_tv_system.json").read_text())
        self.tv_visuals = json.loads((ROOT / "data" / "tv_channel_visuals.json").read_text())
        self.tv_audio_config = json.loads((ROOT / "data" / "tv_channel_audio.json").read_text())
        self.alternate_voice_config = json.loads((ROOT / "data" / "alternate_voice_lines.json").read_text())
        self.dreamcatcher_lore = json.loads((ROOT / "data" / "dreamcatcher_lore.json").read_text())
        self.floor_z = self.layout["levels"]["floor2"]["z"]
        self.ceiling_h = self.layout["levels"]["floor2"]["ceiling_height"]

        self.heading = -float(self.master["player_start"]["heading_deg"])
        self.pitch = float(self.master["player_start"]["pitch_deg"])
        sx, sy, sz = self.master["player_start"]["floor_pos"]
        self.eye_h = float(self.master["player_start"]["eye_height"])
        self.player = Vec3(sx, sy, sz)
        self.paused = False
        self.prompt_target = None
        self.keys = {k: False for k in ("w", "a", "s", "d", "shift")}
        self.message_timer = 0.0
        self.test_shot_frame = 0
        self.tv_power = self.tv_authority["initial_state"]["power"] == "on"
        self.tv_channel = int(self.tv_authority["initial_state"]["channel_index"])
        self.tv_focused = False
        self.tv_focus_from_chair = False
        # The bundled mode owns its process; the live house remains in memory.
        self.dream_link_prepare_state = "idle"  # idle -> running -> idle / error
        self.world_travel = None
        self.dream_link_last_handoff = None
        self.tv_refresh_accum = 0.0
        self.tv_frame_counter = 0
        self.crt_profile = json.loads((ROOT / "data" / "crt_signal_profile.json").read_text())
        self._focus_restore = None
        self.tv_shutdown_count = 0
        # Pass 30 entity-memory authority. This state survives in-game resets,
        # but is intentionally not written to disk yet. Every retained field is
        # a directly observed player action or completed reset count; there are
        # no inferred motives, identities, names, or hidden-world facts.
        self.entity_memory = {
            "observed_tv_shutdowns_total": 0,
            "completed_reset_cycles": 0,
            "facts": {
                "first_tv_shutdown_observed": False,
                "second_tv_shutdown_observed": False,
                "third_tv_shutdown_observed": False,
            },
        }
        self.first_warning_armed = False
        self.first_warning_revealed = False
        self.second_warning_armed = False
        self.second_warning_revealed = False
        self.second_voice = None
        self.alternate_voice_sounds = {}
        # Pass 80 Alternate voice intelligence authority. Selection is deterministic
        # and derives only from directly observed player/game state.
        self.alternate_voice_rules_fired = set()
        self.alternate_voice_history = []
        self.tv_channel_sounds = {}
        self.tv_channel_sound_active = None
        self.datamosh_active = False
        self.datamosh_elapsed = 0.0
        self.datamosh_duration = 0.82
        self.datamosh_tick = 0

        # Pass 32/33 TV-issued task loop. Task 01 proves pickup/return; Task 02
        # proves a different room target and object-state change without expanding
        # the house. Both are run-scoped and reset with the house.
        self.tv_task = {
            "id": "bathroom_note_01",
            "state": "unissued",  # unissued -> active -> collected -> completed
            "destination": "f2_bath",
            "action": "take_note",
            "note_collected": False,
            "completion_count": 0,
        }
        self.tv_task_02 = {
            "id": "hall_frame_02",
            "state": "locked",  # locked -> unissued -> active -> changed -> completed
            "destination": "f2_hall",
            "action": "straighten_frame",
            "frame_straightened": False,
            "completion_count": 0,
        }
        self.tv_task_03 = {
            "id": "master_window_cover_03",
            "state": "locked",  # locked -> unissued -> active -> changed -> completed
            "destination": "f2_master",
            "action": "cover_south_window",
            "window_covered": False,
            "completion_count": 0,
        }
        self.tv_task_04 = {
            "id": "bathroom_mirror_cover_04",
            "state": "locked",  # locked -> unissued -> active -> changed -> completed
            "destination": "f2_bath",
            "action": "cover_mirror",
            "mirror_covered": False,
            "completion_count": 0,
        }
        self.tv_task_05 = {
            "id": "hall_phone_disconnect_05",
            "state": "locked",
            "destination": "f2_hall",
            "action": "disconnect_phone",
            "phone_disconnected": False,
            "completion_count": 0,
        }
        self.tv_task_06 = {
            "id": "master_bedroom_door_close_06",
            "state": "locked",
            "destination": "f2_master",
            "action": "close_bedroom_door",
            "bedroom_door_closed": False,
            "completion_count": 0,
        }
        # Floor 1 is part of the actual task sequence. Pass 85 retires the sink
        # task, leaving distinct downstairs actions and room variety before the basement.
        self.tv_task_07 = {
            "id": "living_lamp_off_07", "state": "locked",
            "destination": "f1_living", "action": "turn_off_lamp",
            "lamp_off": False, "completion_count": 0,
        }
        # Pass 85: sink task removed from the active sequence.  The compatibility
        # slot remains completed so old reset/progression code cannot accidentally
        # resurrect it or strand a save between Tasks 07 and 09.
        self.tv_task_08 = {
            "id": "kitchen_tap_off_08_REMOVED", "state": "completed",
            "destination": "f1_kitchen", "action": "removed",
            "tap_off": True, "completion_count": 1,
        }
        self.tv_task_09 = {
            "id": "dining_chair_in_09", "state": "locked",
            "destination": "f1_dining", "action": "push_in_chair",
            "chair_in": False, "completion_count": 0,
        }
        # Pass 86: use the previously empty rear hall before escalating below ground.
        # The rear door stays shut; the task only removes its interior latch.
        self.tv_task_10 = {
            "id": "rear_door_unlatch_10", "state": "locked",
            "destination": "f1_rearhall", "action": "unlatch_rear_door",
            "unlatched": False, "completion_count": 0,
        }
        # Pass 90: one contained outdoor faith encounter.  The rear-door task now
        # has a narrative payoff before the existing basement/attic chain resumes.
        self.forest_task = {
            "id": "forest_faith_11", "state": "locked",
            "destination": "forest", "action": "answer_entity",
            "choice": None, "completion_count": 0,
        }
        self.forest_active = False
        self.forest_dialogue_stage = None
        self.forest_dialogue_elapsed = 0.0
        self.forest_punish_elapsed = 0.0
        self.forest_no_line_played = False
        self.forest_return_ready = False
        self.basement_task = {
            "id": "basement_clue_12", "state": "locked",
            "destination": "basement", "action": "find_clue",
            "completion_count": 0,
        }
        self.task_broadcast_mode = None  # active task takeover identity
        self.task_broadcast_channel = None  # fixed random channel for the active task
        self.task_completion_broadcast_mode = None  # just-finished task notice remains visible while next task is already live
        self.task_completion_broadcast_channel = None
        self.task_broadcast_history = []    # recent task channels; avoids repetitive assignments
        self.task_broadcast_rng = random.SystemRandom()

        self.window_audio_sources = {}
        self.window_boarded = set()
        self.window_event_timer = 0.0
        self.window_event_last_id = None
        self.window_event_play_count = 0
        self.audio3d = None
        self.footstep_sounds = {}
        self.footstep_distance_accum = 0.0
        self.footstep_variant = 0
        self.grain_frame = 0
        self.grain_accum = 0.0
        # Pass 75: keep control/mouse/camera work at frame rate, but throttle purely
        # cosmetic scene work. Panda tasks execute every frame on the main thread, so
        # repeating dozens of unchanged NodePath state writes at 60+ Hz only creates
        # avoidable frame-time pressure.
        self.veil_update_accum = 0.0
        self.motion_update_accum = 0.0
        self.leak_update_accum = 0.0
        self.prompt_update_accum = 0.0
        self.distance_veils = []
        self.environment_motion_time = 0.0
        self.water_leaks = []
        self.age_decals = []
        self.window_glass_nodes = {}

        self.floor1_active = False
        self.floor1_z = float(self.layout["levels"]["floor1"]["z"])
        self.floor1_entry_pos = Vec3(10.10, 1.85, self.floor1_z)
        self.floor1_return_pos = Vec3(10.10, 1.02, self.floor1_z + 1.0)
        self.floor1_basement_pos = Vec3(10.10, 4.25, self.floor1_z + 1.0)
        self.basement_active = False
        self.basement_clue_found = False
        self.basement_loop_count = 0
        self.basement_z = float(self.layout["levels"]["basement"]["z"])
        self.basement_ceiling_h = float(self.layout["levels"]["basement"]["ceiling_height"])
        # Pass 73: expanded basement navigation authority.  The route is deliberately
        # wider than the old four overlapping strips so corners read as corridors,
        # not stacked room meshes.  One far-end threshold rebases the player to make
        # the route feel spatially impossible without using fake black doors.
        self.basement_entry_pos = Vec3(11.20, 2.20, self.basement_z)
        self.basement_exit_pos = Vec3(11.20, 1.72, self.basement_z + 1.0)
        self.basement_clue_pos = Vec3(3.55, 11.15, self.basement_z + 1.10)
        self.basement_walk_rects = [
            (10.20, 1.30, 12.20, 4.80),   # lit entry / stair landing
            (3.00, 3.20, 12.20, 4.80),    # south corridor
            (3.00, 3.20, 4.80, 12.20),    # west corridor
            (3.00, 10.40, 14.20, 12.20),  # north corridor / clue
            (12.40, 7.00, 14.20, 12.20),  # east return leg
            (7.00, 6.20, 14.20, 8.00),    # middle connector
            (7.00, 3.80, 8.80, 8.00),     # inner turn; widened south overlap prevents a 0.14 m pinch point
        ]
        self.attic_active = False
        self.attic_z = float(self.layout["levels"]["attic"]["z"])
        self.attic_ceiling_h = float(self.layout["levels"]["attic"]["ceiling_height"])
        self.attic_rooms = [r for r in self.layout["rooms"] if r["level"] == "attic"]
        # Pass 74: keep the attic navigation authority intentionally simple and open.
        # The old eave-room rectangles and narrow portal bridges created trapping pockets.
        self.attic_walk_rects = [
            (0.65, 0.65, 8.55, 9.35),   # open main attic
            (8.55, 3.00, 11.30, 5.40),  # landing begins at the real connector plane
        ]
        self.attic_entry_pos = Vec3(10.10, 4.20, self.attic_z)
        self.attic_pylon_pos = Vec3(4.45, 5.05, self.attic_z + 1.05)
        self.attic_task = {
            "id": "attic_pylon_final_13",
            "state": "locked",  # locked -> unissued -> active -> loosened
            "pylon_loosened": False,
        }
        self.finale_active = False
        self.finale_finished = False
        self.finale_elapsed = 0.0
        self.finale_player_anchor = Vec3(0, 0, 0)
        self.finale_camera_base_heading = 0.0
        self.finale_camera_base_pitch = 0.0
        self.finale_forward = Vec3(0, 1, 0)
        self.finale_voice_played = False
        self.attic_tear_nodes = []
        self.attic_tear_initial = []
        self.giant_hand_root = None

        # Pass 82 — note interception authority. The Alternate body never enters
        # playable bounds; only this procedural arm crosses the first exterior wall.
        self.note_intercept_active = False
        self.note_intercept_elapsed = 0.0
        self.note_intercept_duration = 8.2
        self.note_intercept_arm_progress = 0.0
        self.note_intercept_samples = []
        self.note_intercept_route_valid = False

        self.scene_root = self.render.attachNewNode("floor2-start-zone")
        self.baked_shadow_texture = self._make_baked_shadow_texture()
        self.unit_box = self._make_unit_box()
        self._build_scene()
        self._build_top_floor_age()
        self._build_shadow_fog()
        self._build_floor1_shell()
        self._build_floor1_task_props()
        self._build_basement_liminal()
        self._build_attic_foundation()
        self._build_attic_finale_geometry()
        self._build_distance_veils()
        self._build_first_task_object()
        self._build_note_interception_arm()
        self._build_second_task_object()
        self._build_third_task_object()
        self._build_fourth_task_object()
        self._build_fifth_task_object()
        self._build_sixth_task_object()
        self._build_window_audio()
        self._build_footstep_audio()
        self.alternate_visual = self._build_alternate_visual()
        self.alternate_visual.hide()
        self.alternate_blur_shells = []
        self.alternate_eye_nodes = []
        self.alternate_lightning_card = None
        self.alternate_anchors = []
        self.alternate_visit_order = []
        self.current_room_id = None
        self.alt_manifest_counter = 0
        self.alt_state = "hidden"  # hidden | active | retreat
        self.alt_anchor = None
        self.alt_hidden_timer = 12.0
        self.tv_focus_from_chair = False
        self.tv_sit_count = 0
        self.alt_visibility_mode = "full"
        self.alt_forced_visibility_mode = None
        self.alternate_head_variant = 0
        self.alt_local_time = 0.0
        self.alt_seen_accum = 0.0
        self.alt_origin = Vec3(0, 0, self.floor_z)
        self.alt_retreat_dir = Vec3(0, -1, 0)
        self.alt_lightning_alpha = 0.0
        self._prepare_alternate_visual_effects()
        self._build_alternate_anchors()
        self._note_room_visit(self._locate_room_id(self.player.x, self.player.y))
        self._build_wall_warning()
        self._build_second_wall_warning()
        self._build_post_reset_memory_reaction()
        self._load_alternate_voice_placeholders()
        self._load_second_warning_voice()
        self._load_tv_channel_audio()
        self._build_ui()
        self._build_forest_encounter()
        self._build_finale_ui()
        self._build_film_grain()
        self._build_datamosh_overlay()
        self._bind_controls()
        self.accept("window-event", self._on_window_event)
        self.accept("window-close", self._quit_game)
        if self.win is not None and hasattr(self.win, "setCloseRequestEvent"):
            self.win.setCloseRequestEvent("window-close")
        self._set_mouse_capture(not bool(ARGS.test_shot or ARGS.arm_test_shot or ARGS.broadcast_test_shot or ARGS.forest_test_shot or ARGS.manifest_test_shot or ARGS.finale_test_shot or ARGS.lore_test_shot or ARGS.bridge_channel_test_shot or ARGS.bridge_prepare_test_shot))
        self._apply_camera()

        self.taskMgr.add(self._update, "game-update")
        tv_hz = max(1, int(self._tv_visual_data()["motion_contract"]["update_hz"]))
        self.taskMgr.doMethodLater(1.0 / tv_hz, self._tv_runtime, "tv-runtime")
        if ARGS.test_shot or ARGS.arm_test_shot or ARGS.broadcast_test_shot or ARGS.forest_test_shot or ARGS.manifest_test_shot or ARGS.finale_test_shot or ARGS.lore_test_shot or ARGS.bridge_channel_test_shot or ARGS.bridge_prepare_test_shot:
            # Offscreen GraphicsBuffer has no pointer API; capture proofs drive their
            # state directly, so normal player-input polling is intentionally idle.
            self.taskMgr.remove("game-update")
        if ARGS.test_shot:
            self.taskMgr.add(self._capture_test_shot, "capture-test-shot", sort=100)
        if ARGS.arm_test_shot:
            self.taskMgr.add(self._capture_arm_test_shot, "capture-arm-test-shot", sort=100)
        if ARGS.broadcast_test_shot:
            self.taskMgr.add(self._capture_broadcast_test_shot, "capture-broadcast-test-shot", sort=100)
        if ARGS.forest_test_shot:
            self.taskMgr.add(self._capture_forest_test_shot, "capture-forest-test-shot", sort=100)
        if ARGS.manifest_test_shot:
            self.taskMgr.add(self._capture_manifest_test_shot, "capture-manifest-test-shot", sort=100)
        if ARGS.finale_test_shot:
            self.taskMgr.add(self._capture_finale_test_shot, "capture-finale-test-shot", sort=100)
        if ARGS.lore_test_shot:
            self.taskMgr.add(self._capture_lore_test_shot, "capture-lore-test-shot", sort=100)
        if ARGS.bridge_channel_test_shot:
            self.taskMgr.add(self._capture_bridge_channel_test_shot, "capture-bridge-channel-test-shot", sort=100)
        if ARGS.bridge_prepare_test_shot:
            self.taskMgr.add(self._capture_bridge_prepare_test_shot, "capture-bridge-prepare-test-shot", sort=100)

        self.world_travel = WorldTravel(self, ROOT, 'dreamcatcher_alternate',
            before_leave=self._travel_before_leave, on_error=self._travel_failed,
            activate=self._travel_activate)
        if not _CAPTURE_MODE:
            self.travel_back_button.show()
            if not ARGS.no_audio:
                shared.apply_master_volume(self, SHARED_SETTINGS["master_volume"])
            house = shared.load_house()
            if house is not None:
                self._restore_house_state(house)
        self.world_travel.start_receiving()

    def _travel_before_leave(self):
        self._save_display_settings()
        if not _CAPTURE_MODE:
            # The house survives trips into Andrew's Nightmare and back to Limbo.
            shared.save_house(None if self.finale_finished else self._house_snapshot())
        self._clear_input_state()

    def return_to_limbo(self):
        """DreamCatcher is part of Mirror's Limbo: every exit path leads back there."""
        if self.world_travel is None or self.world_travel.busy:
            return False
        if self.world_travel.return_target == 'mirrors_limbo':
            return self.world_travel.back()
        return self.world_travel.go('mirrors_limbo')

    # ---------- Mirror's Limbo linked house state ----------
    HOUSE_TASK_KEYS = ("tv_task", "tv_task_02", "tv_task_03", "tv_task_04", "tv_task_05",
                       "tv_task_06", "tv_task_07", "tv_task_08", "tv_task_09", "tv_task_10",
                       "forest_task", "basement_task", "attic_task")

    def _house_snapshot(self) -> dict:
        """Run-scoped house progress. Transient scenes (finale, forest, datamosh) are not saved."""
        on_floor2 = not (self.floor1_active or self.basement_active or self.attic_active or self.forest_active)
        if self.tv_focused and self._focus_restore is not None:
            pos, heading, pitch, eye_h, _hfov = self._focus_restore
        else:
            pos, heading, pitch, eye_h = self.player, self.heading, self.pitch, self.eye_h

        def plain(value):
            try:
                return json.loads(json.dumps(value))
            except (TypeError, ValueError):
                return None

        return {
            "schema": 1,
            "tasks": {key: plain(getattr(self, key)) for key in self.HOUSE_TASK_KEYS},
            "basement_clue_found": bool(self.basement_clue_found),
            "broadcast": {
                "mode": self.task_broadcast_mode, "channel": self.task_broadcast_channel,
                "completion_mode": self.task_completion_broadcast_mode,
                "completion_channel": self.task_completion_broadcast_channel,
                "history": plain(list(self.task_broadcast_history)) or [],
            },
            "tv": {"power": bool(self.tv_power), "channel": int(self.tv_channel),
                   "shutdowns": int(self.tv_shutdown_count), "sit_count": int(self.tv_sit_count)},
            "warnings": [bool(self.first_warning_armed), bool(self.first_warning_revealed),
                         bool(self.second_warning_armed), bool(self.second_warning_revealed)],
            "entity_memory": plain(self.entity_memory),
            "voice_rules_fired": sorted(str(x) for x in self.alternate_voice_rules_fired),
            "voice_history": plain(list(self.alternate_voice_history)[-32:]) or [],
            "player": [float(pos.x), float(pos.y), float(pos.z), float(heading), float(pitch), float(eye_h)] if on_floor2 else None,
        }

    def _restore_house_state(self, snap: dict) -> bool:
        if not isinstance(snap, dict) or snap.get("schema") != 1:
            return False
        try:
            tasks = snap.get("tasks") or {}
            for key in self.HOUSE_TASK_KEYS:
                if isinstance(tasks.get(key), dict):
                    getattr(self, key).update(tasks[key])
            # Mid-sequence moments that cannot resume: settle them to their next stable state.
            if self.tv_task["state"] == "intercepting":
                self.tv_task["state"] = "collected"
            if self.attic_task["state"] == "loosened":
                self.attic_task.update({"state": "active", "pylon_loosened": False})
            # Physical task props follow their saved task flags.
            if self.tv_task.get("note_collected"):
                self.task_note_root.hide()
            else:
                self.task_note_root.show()
            self._set_task_frame_crooked(not self.tv_task_02.get("frame_straightened"))
            self._set_task_window_covered(bool(self.tv_task_03.get("window_covered")))
            self._set_task_mirror_covered(bool(self.tv_task_04.get("mirror_covered")))
            self._set_task_phone_disconnected(bool(self.tv_task_05.get("phone_disconnected")))
            self._set_master_bedroom_door_closed(bool(self.tv_task_06.get("bedroom_door_closed")))
            if self.tv_task_07.get("lamp_off"):
                self.floor1_lamp_glow.setColor(0.12, 0.12, 0.12, 1)
            if self.tv_task_09.get("chair_in"):
                self.floor1_chair_root.setY(7.02)
            if self.tv_task_10.get("unlatched") and hasattr(self, "floor1_rear_latch"):
                self.floor1_rear_latch.setX(9.82)
            self.basement_clue_found = bool(snap.get("basement_clue_found"))
            if self.basement_clue_found and hasattr(self, "basement_clue_root"):
                self.basement_clue_root.hide()
            b = snap.get("broadcast") or {}
            self.task_broadcast_mode = b.get("mode")
            self.task_broadcast_channel = b.get("channel")
            self.task_completion_broadcast_mode = b.get("completion_mode")
            self.task_completion_broadcast_channel = b.get("completion_channel")
            self.task_broadcast_history[:] = list(b.get("history") or [])
            tv = snap.get("tv") or {}
            self.tv_power = bool(tv.get("power", self.tv_power))
            self.tv_channel = int(tv.get("channel", self.tv_channel))
            self.tv_shutdown_count = int(tv.get("shutdowns", 0))
            self.tv_sit_count = int(tv.get("sit_count", 0))
            if isinstance(snap.get("entity_memory"), dict):
                self.entity_memory.update(snap["entity_memory"])
            self.alternate_voice_rules_fired = set(snap.get("voice_rules_fired") or [])
            self.alternate_voice_history = list(snap.get("voice_history") or [])
            first_armed, first_seen, second_armed, second_seen = (list(snap.get("warnings") or []) + [False] * 4)[:4]
            self.first_warning_revealed = bool(first_seen)
            self.second_warning_revealed = bool(second_seen)
            if self.first_warning_revealed:
                self.first_warning_root.show()
            if self.second_warning_revealed:
                self.second_warning_root.show()
            if first_armed and not first_seen:
                self._arm_first_tv_off_warning()
            if second_armed and not second_seen:
                self._arm_second_tv_off_warning()
            self._sync_post_reset_memory_reaction()
            player = snap.get("player")
            if isinstance(player, list) and len(player) == 6:
                x, y, z, heading, pitch, eye_h = map(float, player)
                self.player = Vec3(x, y, z)
                self.heading, self.pitch, self.eye_h = heading, pitch, eye_h
            self.tv_frame_counter = 0
            self.tv_refresh_accum = 999.0
            self._render_tv_frame(force=True)
            self._apply_camera()
            self._update_prompt()
            _append_runtime_log("HOUSE_STATE restored")
            print("HOUSE_STATE RESTORED", self.tv_task["state"], self.tv_task_02["state"], flush=True)
            return True
        except Exception as exc:
            _append_runtime_log(f"HOUSE_STATE restore_failed {type(exc).__name__}: {exc}")
            return False

    def _travel_failed(self, message):
        self.dream_link_prepare_state = 'error'
        _append_runtime_log('GX_TRAVEL ' + message)
        self.paused = True
        self.pause_main.show(); self.display_panel.hide(); self.pause.show()
        self.tv_focus_ui.hide(); self.prompt.hide(); self.crosshair.hide()
        self.mode_return_notice['text'] = 'DESTINATION UNAVAILABLE — DREAMCATCHER RESTORED'
        self.mode_return_notice.show()
        self._set_mouse_capture(False)

    def _travel_activate(self):
        self.paused = False
        self._focus_auto_paused = False
        self._clear_input_state()
        self.pause.hide()
        self._set_mouse_capture(True)
        self._update_prompt()


    # ---------- scene ----------
    def _make_unit_box(self):
        return None

    def _make_baked_shadow_texture(self):
        """Procedural edge-darkening map used as baked ambient shadow on architecture."""
        size = 96
        image = PNMImage(size, size, 3)
        for y in range(size):
            v = y / float(size - 1)
            for x in range(size):
                u = x / float(size - 1)
                edge = min(u, 1.0-u, v, 1.0-v)
                t = max(0.0, min(1.0, edge / 0.20))
                t = t*t*(3.0-2.0*t)
                # Dark corners/contact edges, gentle vertical falloff, tiny deterministic age ripple.
                vertical = 0.94 + 0.06*v
                ripple = 0.985 + 0.015*math.sin((u*7.0 + v*3.0) * math.pi)
                value = max(0.42, min(1.0, (0.54 + 0.46*t) * vertical * ripple))
                image.setXel(x, y, value, value, value)
        tex = Texture("baked-architecture-shadow")
        tex.load(image)
        tex.setMinfilter(Texture.FTLinear)
        tex.setMagfilter(Texture.FTLinear)
        tex.setWrapU(Texture.WMClamp)
        tex.setWrapV(Texture.WMClamp)
        return tex

    def _architecture_uses_baked_shadow(self, name: str) -> bool:
        lowered = name.lower()
        if any(skip in lowered for skip in ("warning", "alternate", "crt", "glass", "screen", "grain")):
            return False
        return any(token in lowered for token in (
            "wall", "floor", "ceiling", "carpet", "tile", "door", "lintel",
            "base", "crown", "casing", "trim", "wainscot", "subfloor", "sill"
        ))

    def _build_shadow_fog(self):
        """Near-black camera-relative fog: close geometry stays readable, distant rooms disappear."""
        self.shadow_fog = Fog("house-shadow-fog")
        self.shadow_fog.setColor(0.006, 0.006, 0.008)
        self.shadow_fog.setExpDensity(0.165)
        self.scene_root.setFog(self.shadow_fog)

    def _build_distance_veils(self):
        """Soft dark doorway veils: distant spaces lose contrast, near spaces resolve clearly."""
        portals = [
            self.master_portal, self.bath_portal, self.stair_portal,
            self.bed2_portal, self.bed3_portal, self.bed4_portal,
        ]
        for portal in portals:
            px, py, _ = portal["center"]
            pw = float(portal["width"])
            ph = float(portal["height"])
            # A pair of very thin translucent layers gives a soft atmospheric boundary
            # without changing collision or requiring a post-processing shader.
            layers=[]
            for i, off in enumerate((-0.045, -0.018, 0.018, 0.045)):
                node = self.loader.loadModel("models/box")
                node.setName(f"distance-soft-{portal['id']}-{i}")
                node.reparentTo(self.scene_root)
                node.clearTexture(); node.setTextureOff(1); node.setLightOff(1)
                node.setPos(px - 0.004 + off, py - pw*0.46, self.floor_z + 0.08)
                node.setScale(0.008, pw*0.92, max(0.2, ph-0.16))
                node.setColor(0.006,0.006,0.009,0.0)
                node.setTransparency(TransparencyAttrib.MAlpha)
                node.setDepthWrite(False)
                node.setBin("transparent", 25+i)
                layers.append(node)
            self.distance_veils.append((Vec3(px,py,self.floor_z+ph*0.5), layers))

    def _update_distance_veils(self):
        player=Vec3(self.player.x,self.player.y,self.floor_z)
        for center,layers in self.distance_veils:
            d=(player-Vec3(center.x,center.y,self.floor_z)).length()
            # Nothing close to the player; gradual low-contrast softening farther away.
            t=max(0.0,min(1.0,(d-0.85)/2.75))
            t=t*t*(3.0-2.0*t)
            for i,node in enumerate(layers):
                a=t*((0.24, 0.19, 0.15, 0.11)[i])
                node.setColor(0.006,0.006,0.009,a)

    def _update_environment_motion(self, dt: float):
        """Rare micro-motion on visual-only props; room geometry and collision never move."""
        self.environment_motion_time += dt
        phase=self.environment_motion_time % 17.0
        pulse=0.0
        if 11.0 <= phase <= 13.0:
            pulse=math.sin((phase-11.0)*math.pi/2.0)
        player_xy=Vec3(self.player.x,self.player.y,self.floor_z)
        frame_dist=(player_xy-Vec3(self.task_frame_pos.x,self.task_frame_pos.y,self.floor_z)).length()
        phone_dist=(player_xy-Vec3(self.task_phone_pos.x,self.task_phone_pos.y,self.floor_z)).length()

        base_frame_r=0.0 if self.tv_task_02.get("frame_straightened") else 6.0
        if self.tv_task_02.get("state") != "active" and frame_dist > 3.0:
            self.task_frame_root.setR(base_frame_r + 1.15*pulse)
        else:
            self.task_frame_root.setR(base_frame_r)

        if self.tv_task_05.get("phone_disconnected"):
            base_pos=Vec3(-0.13,-0.018,-0.20); base_r=22.0
        else:
            base_pos=Vec3(0,0,0); base_r=0.0
        if (not self.tv_task_05.get("phone_disconnected")) and self.tv_task_05.get("state") != "active" and phone_dist > 3.0:
            self.task_phone_handset_root.setPos(base_pos + Vec3(0,0,0.006*pulse))
            self.task_phone_handset_root.setR(base_r + 1.7*pulse)
        else:
            self.task_phone_handset_root.setPos(base_pos)
            self.task_phone_handset_root.setR(base_r)

    def _box(self, name: str, center, size, shade: float, parent=None):
        parent = parent or self.scene_root
        model = self.loader.loadModel("models/box")
        model.setName(name)
        model.reparentTo(parent)
        model.clearTexture()
        model.setTextureOff(1)
        if hasattr(self, "baked_shadow_texture") and self._architecture_uses_baked_shadow(name):
            # Architecture receives a procedural baked-shading map.  This is intentionally
            # texture-based rather than a real-time shadow system to keep the prototype light.
            model.setTextureOff(0)
            model.setTexture(self.baked_shadow_texture, 2)
        # Panda3D's bundled box spans local (0,0,0) to (1,1,1), so anchor it by center.
        model.setPos(center[0] - size[0] / 2.0, center[1] - size[1] / 2.0, center[2] - size[2] / 2.0)
        model.setScale(size[0], size[1], size[2])
        shown = min(0.92, shade * 1.55 + 0.12)
        model.setColor(shown, shown, shown, 1)
        model.setTwoSided(True)
        return model

    def _black_window_glass(self, name: str, center, size, parent=None):
        """Render sealed window glazing as exterior night, not as an opaque cover."""
        pane = self._box(name, center, size, 0.0, parent=parent)
        pane.setColor(0.002, 0.002, 0.002, 1.0)
        pane.setLightOff(1)
        self.window_glass_nodes[name] = pane
        return pane

    def _age_decal(self, name: str, texture_name: str, center, width: float, height: float, surface: str = "wall_y", heading: float = 0.0):
        """Transparent finished decal for stains, scuffs, and wet floor patches."""
        tex_path = ROOT / "assets" / "textures" / texture_name
        if not tex_path.exists():
            return None
        cm = CardMaker(name + "-card")
        cm.setFrame(-width / 2.0, width / 2.0, -height / 2.0, height / 2.0)
        node = self.scene_root.attachNewNode(cm.generate())
        node.setName(name)
        node.setPos(*center)
        if surface == "wall_x":
            node.setH(90.0 + heading)
        elif surface in ("ceiling", "floor"):
            node.setP(-90.0)
            node.setH(heading)
        else:
            node.setH(heading)
        try:
            texture = self.loader.loadTexture(panda_filename(tex_path))
        except Exception as exc:
            try:
                node.removeNode()
            except Exception:
                pass
            self._write_runtime_log(f"Optional age decal skipped: {tex_path.name}: {exc}")
            return None
        node.setTexture(texture, 1)
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.setLightOff(1)
        node.setTwoSided(True)
        node.setDepthWrite(False)
        node.setBin("transparent", 18)
        self.age_decals.append(node)
        return node

    def _small_old_prop(self, name: str, center, size, shade=0.18, tilt=0.0):
        node = self._box(name, center, size, shade)
        if tilt:
            node.setR(tilt)
        return node

    def _build_top_floor_age(self):
        """Finished top-floor water damage, active leaks, scuffs, and lived-in wear."""
        z0 = self.floor_z
        top = z0 + self.ceiling_h

        ceiling_marks = [
            ("age-master-ceiling", "water_stain_ceiling_a.png", (2.95, 3.72, top - 0.016), 1.55, 1.02, 11),
            ("age-hall-ceiling", "water_stain_ceiling_b.png", (7.18, 7.66, top - 0.016), 1.15, 0.78, -17),
            ("age-bed2-ceiling", "water_stain_ceiling_b.png", (4.45, 6.20, top - 0.016), 0.94, 0.72, 22),
            ("age-bed3-ceiling", "water_stain_ceiling_a.png", (2.95, 9.55, top - 0.016), 1.12, 0.76, -31),
            ("age-bed4-ceiling", "water_stain_ceiling_b.png", (10.15, 7.45, top - 0.016), 1.06, 0.70, 15),
            ("age-bath-ceiling", "water_stain_ceiling_a.png", (10.25, 2.65, top - 0.016), 1.45, 0.92, -8),
        ]
        for name, tex, center, w, h, hdg in ceiling_marks:
            self._age_decal(name, tex, center, w, h, "ceiling", hdg)

        wall_marks = [
            ("age-master-south-corner", "water_stain_corner.png", (4.78, self.room_rect[1] + 0.018, z0 + 2.05), 0.72, 0.96, "wall_y", 0),
            ("age-master-west-corner", "water_stain_corner.png", (self.room_rect[0] + 0.018, 4.18, z0 + 2.02), 0.70, 1.02, "wall_x", 0),
            ("age-hall-east-corner", "water_stain_corner.png", (self.hall_rect[2] - 0.018, 7.72, z0 + 2.08), 0.62, 1.10, "wall_x", 0),
            ("age-bed2-north-corner", "water_stain_corner.png", (4.72, self.bed2_rect[3] - 0.018, z0 + 2.02), 0.68, 0.94, "wall_y", 180),
            ("age-bed3-south-corner", "water_stain_corner.png", (1.15, self.bed3_rect[1] + 0.018, z0 + 2.00), 0.72, 1.04, "wall_y", 0),
            ("age-bed4-east-corner", "water_stain_corner.png", (self.bed4_rect[2] - 0.018, 9.38, z0 + 2.03), 0.68, 1.00, "wall_x", 180),
            ("age-bath-east-corner", "water_stain_corner.png", (self.bath_rect[2] - 0.018, 2.72, z0 + 1.95), 0.82, 1.12, "wall_x", 180),
        ]
        for args in wall_marks:
            self._age_decal(*args)

        scuffs = [
            ("scuff-master-north", (3.95, self.room_rect[3] - 0.019, z0 + 0.78), 1.08, 0.78, "wall_y", 180),
            ("scuff-hall-south", (7.10, self.hall_rect[1] + 0.019, z0 + 0.73), 0.90, 0.68, "wall_y", 0),
            ("scuff-bed2-north", (3.45, self.bed2_rect[3] - 0.019, z0 + 0.72), 0.82, 0.64, "wall_y", 180),
            ("scuff-bed3-north", (4.20, self.bed3_rect[3] - 0.019, z0 + 0.74), 0.84, 0.66, "wall_y", 180),
            ("scuff-bed4-north", (10.25, self.bed4_rect[3] - 0.019, z0 + 0.70), 0.90, 0.64, "wall_y", 180),
        ]
        for name, center, w, h, surface, hdg in scuffs:
            self._age_decal(name, "wall_scuffs.png", center, w, h, surface, hdg)

        leak_specs = [
            ("master", Vec3(3.58, 3.66, z0), 0.22),
            ("hall", Vec3(7.22, 7.62, z0), 0.57),
            ("bath", Vec3(10.22, 2.62, z0), 0.86),
        ]
        for leak_name, pos, phase in leak_specs:
            self._age_decal(f"wet-{leak_name}", "water_puddle.png", (pos.x, pos.y, z0 + 0.026), 0.72, 0.50, "floor", 0)
            drops = []
            for i in range(3):
                drop = self.loader.loadModel("models/misc/sphere")
                drop.setName(f"leak-{leak_name}-drop-{i}")
                drop.reparentTo(self.scene_root)
                drop.clearTexture(); drop.setTextureOff(1); drop.setLightOff(1)
                drop.setScale(0.012, 0.012, 0.032)
                drop.setColor(0.36, 0.39, 0.42, 0.72)
                drop.setTransparency(TransparencyAttrib.MAlpha)
                drop.setBin("transparent", 23)
                drops.append(drop)
            self.water_leaks.append({"name": leak_name, "pos": pos, "phase": phase, "drops": drops})

        # Small completed household details to keep the space from reading as an empty set.
        self._small_old_prop("bed2-old-book-1", (4.17, 5.30, z0 + 0.79), (0.25, 0.17, 0.035), 0.14, -4)
        self._small_old_prop("bed2-old-book-2", (4.20, 5.31, z0 + 0.825), (0.21, 0.15, 0.028), 0.24, 5)
        self._small_old_prop("bed2-loose-paper", (4.01, 5.16, z0 + 0.777), (0.22, 0.16, 0.008), 0.58, 11)
        for idx, (px, py, r) in enumerate(((2.95, 3.78, -12), (3.12, 3.66, 9))):
            shoe = self.loader.loadModel("models/misc/sphere")
            shoe.setName(f"master-worn-shoe-{idx}")
            shoe.reparentTo(self.scene_root)
            shoe.clearTexture(); shoe.setTextureOff(1)
            shoe.setPos(px, py, z0 + 0.075); shoe.setScale(0.16, 0.085, 0.065); shoe.setR(r)
            shoe.setColor(0.12, 0.12, 0.13, 1)
        self._small_old_prop("hall-old-box", (6.35, 9.55, z0 + 0.16), (0.46, 0.34, 0.30), 0.14, -3)
        self._small_old_prop("hall-old-box-lid", (6.35, 9.55, z0 + 0.325), (0.49, 0.37, 0.035), 0.20, -3)

    def _update_water_leaks(self, dt: float):
        if not self.water_leaks:
            return
        now = globalClock.getFrameTime()
        top = self.floor_z + self.ceiling_h - 0.08
        for leak in self.water_leaks:
            for i, drop in enumerate(leak["drops"]):
                cycle = (now * (0.72 + 0.08 * i) + leak["phase"] + i * 0.37) % 1.0
                if cycle < 0.43:
                    drop.hide()
                    continue
                drop.show()
                t = (cycle - 0.43) / 0.57
                eased = t * t
                z = top - eased * (top - (self.floor_z + 0.07))
                wobble = math.sin((t + i) * 8.0) * 0.006
                drop.setPos(leak["pos"].x + wobble, leak["pos"].y, z)
                drop.setScale(0.012, 0.012, 0.020 + 0.030 * t)

    def _wallpaper_vertical(self, prefix: str, axis: str, fixed: float, start: float, end: float, z0: float, height: float, pattern: str = "stripe"):
        """Add restrained vertical wallpaper bands just inside an existing wall face.

        The bands are visual only: extremely shallow boxes that do not participate in
        manual movement collision. Patterns intentionally vary by room so the house
        does not read like one repeated material.
        """
        root = self.scene_root.attachNewNode(prefix + "-wallpaper")
        inset = 0.010
        if pattern == "stripe":
            repeat, widths, shades = 0.34, (0.055,), (0.215,)
        elif pattern == "pinstripe":
            repeat, widths, shades = 0.29, (0.020, 0.020), (0.18, 0.24)
        elif pattern == "double":
            repeat, widths, shades = 0.42, (0.030, 0.060), (0.19, 0.235)
        elif pattern == "sparse":
            repeat, widths, shades = 0.52, (0.035,), (0.20,)
        elif pattern == "triple":
            repeat, widths, shades = 0.46, (0.018, 0.050, 0.018), (0.17, 0.235, 0.17)
        elif pattern == "broad_narrow":
            repeat, widths, shades = 0.56, (0.085, 0.022), (0.205, 0.255)
        elif pattern == "quiet_pair":
            repeat, widths, shades = 0.62, (0.024, 0.024), (0.19, 0.19)
        else:
            return root

        pos = start + repeat * 0.5
        idx = 0
        while pos < end - 0.02:
            for j, width in enumerate(widths):
                offset = (j - (len(widths)-1)/2.0) * 0.055
                if axis == "x":
                    band = self._box(f"{prefix}-band-{idx}-{j}", (pos + offset, fixed, z0 + height/2), (width, 0.012, height), shades[j], parent=root)
                else:
                    band = self._box(f"{prefix}-band-{idx}-{j}", (fixed, pos + offset, z0 + height/2), (0.012, width, height), shades[j], parent=root)
                band.setTwoSided(True)
            idx += 1
            pos += repeat
        return root


    def _wallpaper_border(self, prefix: str, axis: str, fixed: float, start: float, end: float, z: float, shade: float = 0.23, thickness: float = 0.035):
        """Add a shallow horizontal wallpaper border without affecting collision."""
        if end <= start + 0.04:
            return None
        if axis == "x":
            node = self._box(prefix + "-border", ((start+end)/2, fixed, z), (end-start, 0.013, thickness), shade)
        else:
            node = self._box(prefix + "-border", (fixed, (start+end)/2, z), (0.013, end-start, thickness), shade)
        node.setTwoSided(True)
        return node

    def _wallpaper_fade_patch(self, prefix: str, axis: str, fixed: float, start: float, end: float, z: float, height: float, shade: float = 0.145):
        """Add one broad, low-contrast faded wallpaper area; visual only."""
        if end <= start + 0.04 or height <= 0.04:
            return None
        if axis == "x":
            node = self._box(prefix + "-fade", ((start+end)/2, fixed, z + height/2), (end-start, 0.011, height), shade)
        else:
            node = self._box(prefix + "-fade", (fixed, (start+end)/2, z + height/2), (0.011, end-start, height), shade)
        node.setTwoSided(True)
        return node

    def _alt_ellipsoid(self, name: str, center, scale, color, parent):
        """Create one smooth low-cost ellipsoid for the alternate visual authority."""
        model = self.loader.loadModel("models/misc/sphere")
        model.setName(name)
        model.reparentTo(parent)
        model.clearTexture()
        model.setTextureOff(1)
        model.setPos(*center)
        model.setScale(*scale)
        model.setColor(*color)
        model.setTwoSided(True)
        return model

    def _alt_ring_mesh(self, name: str, rings, color, parent, sides: int = 14):
        """Build one connected asymmetrical surface from authored elliptical rings."""
        fmt = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData(name, fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        nw = GeomVertexWriter(vdata, "normal")
        cw = GeomVertexWriter(vdata, "color")
        rows = []
        for z, rx, ry, ox, oy in rings:
            row = []
            for k in range(sides):
                a = math.tau * k / sides
                ca, sa = math.cos(a), math.sin(a)
                vw.addData3(ox + rx * ca, oy + ry * sa, z)
                n = Vec3(ca / max(rx, 1e-4), sa / max(ry, 1e-4), 0.0)
                if n.lengthSquared() > 1e-8:
                    n.normalize()
                nw.addData3(n)
                cw.addData4(*color)
                row.append(vdata.getNumRows() - 1)
            rows.append(row)
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(len(rows) - 1):
            arow, brow = rows[i], rows[i + 1]
            for k in range(sides):
                q = (k + 1) % sides
                tris.addVertices(arow[k], brow[k], brow[q])
                tris.addVertices(arow[k], brow[q], arow[q])
        # cap both ends
        for ring_i, flip in ((0, True), (len(rows)-1, False)):
            z, _rx, _ry, ox, oy = rings[ring_i]
            ci = vdata.getNumRows()
            vw.addData3(ox, oy, z)
            nw.addData3(0, 0, -1 if flip else 1)
            cw.addData4(*color)
            row = rows[ring_i]
            for k in range(sides):
                q=(k+1)%sides
                if flip: tris.addVertices(ci, row[q], row[k])
                else: tris.addVertices(ci, row[k], row[q])
        tris.closePrimitive()
        geom=Geom(vdata); geom.addPrimitive(tris)
        gn=GeomNode(name); gn.addGeom(geom)
        np=parent.attachNewNode(gn); np.setName(name); np.setTwoSided(True)
        return np

    def _alt_tube(self, name: str, points, radii, color, parent, sides: int = 12):
        """Continuous tapered limb tube following an authored curved centerline."""
        fmt = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData(name, fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        nw = GeomVertexWriter(vdata, "normal")
        cw = GeomVertexWriter(vdata, "color")
        pts=[Vec3(*p) for p in points]
        rows=[]
        for i,p in enumerate(pts):
            if i==0: tangent=pts[1]-p
            elif i==len(pts)-1: tangent=p-pts[i-1]
            else: tangent=pts[i+1]-pts[i-1]
            if tangent.lengthSquared()<1e-8: tangent=Vec3(0,0,1)
            tangent.normalize()
            ref=Vec3(0,0,1)
            side=tangent.cross(ref)
            if side.lengthSquared()<1e-6:
                ref=Vec3(0,1,0); side=tangent.cross(ref)
            side.normalize(); bino=side.cross(tangent); bino.normalize()
            r=float(radii[i]); row=[]
            for k in range(sides):
                a=math.tau*k/sides
                radial=side*math.cos(a)+bino*math.sin(a)
                vw.addData3(p+radial*r); nw.addData3(radial); cw.addData4(*color)
                row.append(vdata.getNumRows()-1)
            rows.append(row)
        tris=GeomTriangles(Geom.UHStatic)
        for i in range(len(rows)-1):
            arow,brow=rows[i],rows[i+1]
            for k in range(sides):
                q=(k+1)%sides
                tris.addVertices(arow[k],brow[k],brow[q]); tris.addVertices(arow[k],brow[q],arow[q])
        tris.closePrimitive(); geom=Geom(vdata); geom.addPrimitive(tris)
        gn=GeomNode(name); gn.addGeom(geom)
        np=parent.attachNewNode(gn); np.setName(name); np.setTwoSided(True)
        return np

    def _build_alternate_visual(self):
        """Pass 95 silhouette redesign built from Pass 92 authority.

        The creature is intentionally human-adjacent rather than anatomically normal:
        a pinched lower trunk under an over-wide uneven shoulder shelf, a too-thin neck,
        bowed long legs, forearms that hang almost to the floor, and an asymmetrical
        vertically distorted skull.  The body is continuous geometry rather than a
        stack of primitive spheres/boxes.
        """
        root=self.scene_root.attachNewNode("alternate-visual-authority")
        root.setPos(0,0,self.floor_z)
        body=(0.020,0.022,0.025,1.0)
        body_mid=(0.028,0.030,0.034,1.0)
        body_high=(0.037,0.039,0.044,1.0)
        eye=(0.94,0.96,0.92,1.0)

        # One continuous trunk.  The lower body is unnaturally narrow while the
        # upper chest spreads abruptly into an asymmetric shoulder shelf.
        torso_rings=[
            (1.02,.205,.125, .000,.000),
            (1.15,.180,.118,-.008,.004),
            (1.29,.145,.108,-.015,.006),
            (1.43,.160,.112,-.010,.004),
            (1.58,.225,.128, .000,.000),
            (1.72,.315,.145, .008,-.004),
            (1.84,.405,.157, .018,-.010),
            (1.91,.485,.165, .028,-.012),
            (1.98,.405,.150,-.006,-.010),
            (2.04,.235,.122,-.012,-.006),
        ]
        self._alt_ring_mesh("alternate-torso",torso_rings,body_mid,root,20)

        # Thin neck with a subtle forward kink so the head does not sit like a doll.
        self._alt_tube("alternate-neck",
            [(-.010,-.006,1.99),(-.018,-.018,2.10),(-.010,-.040,2.20),(0,-.055,2.27)],
            [.105,.087,.074,.068],body,root,12)

        # Irregular skull: narrow jaw, long face, offset crown, flattened depth.
        # Low-ish side count keeps the outline deliberately uneasy instead of egg-smooth.
        head=root.attachNewNode("alternate-head")
        head_rings=[
            (-.31,.082,.100, .015,-.015),
            (-.23,.112,.120, .010,-.028),
            (-.13,.145,.140, .003,-.040),
            (-.02,.182,.155,-.006,-.038),
            ( .10,.208,.165,-.016,-.026),
            ( .21,.196,.158,-.028,-.006),
            ( .31,.158,.138,-.018, .012),
            ( .39,.092,.108, .012, .022),
            ( .44,.045,.078, .028, .018),
        ]
        self._alt_ring_mesh("alternate-head-surface",head_rings,body_high,head,14)
        head.setPos(0,0,2.47)
        head.setHpr(0,-5,-3)

        # Eyes sit low on the stretched face, not centered in the cranium.
        for side,ex in (("left",-.074),("right",.082)):
            self._alt_ellipsoid(f"alternate-{side}-eye",(ex,-.176,2.39),(.050,.015,.024),eye,root).setLightOff(1)
            self._alt_ellipsoid(f"alternate-{side}-pupil",(ex,-.188,2.39),(.027,.007,.018),(.012,.012,.014,1),root).setLightOff(1)

        # Bowed legs.  The uneven stance prevents a mannequin/T-pose read.
        leg_specs={
            "left":[(-.118,-.004,1.08),(-.148,-.018,.82),(-.122,-.006,.52),(-.142,-.032,.18)],
            "right":[(.126,.006,1.08),(.151,.018,.78),(.108,.016,.47),(.132,.036,.16)],
        }
        for side,pts in leg_specs.items():
            self._alt_tube(f"alternate-{side}-leg",pts,[.090,.074,.059,.046],body,root,12)
            x,y,z=pts[-1]
            # Feet are tapered continuations, not shoes/blocks.
            forward=-1 if side=="left" else -1
            self._alt_tube(f"alternate-{side}-foot",
                [(x,y,z),(x+( -.012 if side=="left" else .012),y-.12,.095),(x+( -.020 if side=="left" else .020),y-.27,.052)],
                [.047,.052,.026],body,root,10)

        # The arms are intentionally disproportionate: slightly unequal shoulders,
        # elbows well below the waist, and narrow forearms reaching near the ankles.
        arm_specs={
            "left":[(-.438,-.008,1.91),(-.485,-.018,1.59),(-.505,-.038,1.20),(-.465,-.058,.78),(-.392,-.078,.48)],
            "right":[(.462,.004,1.86),(.510,.018,1.50),(.532,.004,1.08),(.505,.040,.65),(.448,.064,.44)],
        }
        for side,pts in arm_specs.items():
            sign=-1 if side=="left" else 1
            self._alt_tube(f"alternate-{side}-arm",pts,[.082,.068,.057,.045,.035],body,root,12)
            wx,wy,wz=pts[-1]
            # Small narrow palm that dissolves into long uneven fingers.
            palm_end=(wx+sign*.010,wy-.018,wz-.105)
            self._alt_tube(f"alternate-{side}-palm",[(wx,wy,wz),palm_end],[.039,.032],body_mid,root,10)
            lengths=(.205,.265,.245,.190)
            spreads=(-.038,-.012,.014,.038)
            for i,(spread,L) in enumerate(zip(spreads,lengths)):
                bx=palm_end[0]+sign*spread
                by=palm_end[1]-.006
                bz=palm_end[2]-.015
                # slightly curled, splayed tips; left/right are not perfect mirrors
                tip=(bx+sign*(i-1.5)*.010,by-.035,bz-L)
                mid=((bx+tip[0])*.5,by-.018,bz-L*.48)
                self._alt_tube(f"alternate-{side}-finger-{i}",[ (bx,by,bz),mid,tip ],[.0105,.008,.0045],body,root,8)
            self._alt_tube(f"alternate-{side}-thumb",
                [(palm_end[0]+sign*.026,palm_end[1],palm_end[2]+.035),
                 (palm_end[0]+sign*.075,palm_end[1]-.025,palm_end[2]-.085)],
                [.013,.006],body,root,8)

        # Variant code scales this unified head root; the old cranium/face nodes are
        # intentionally absent so they cannot reintroduce primitive anatomy.
        self.alternate_head_parts=("alternate-head",)
        return root


    def _prepare_alternate_visual_effects(self):
        """Present the alternate as a blurry shadow with readable eyes."""
        self.alternate_visual.setTransparency(TransparencyAttrib.MAlpha)
        self.alternate_visual.setDepthWrite(False)
        self.alternate_visual.setBin("transparent", 40)
        self.alternate_visual.setColorScale(0.095, 0.095, 0.11, 0.72)

        # Keep the body eyes hidden inside the dark silhouette. A separate overlay
        # root carries the whites/pupils so body color-scale and fog cannot erase
        # the one feature the player is meant to read clearly.
        for pattern in ("**/alternate-left-eye", "**/alternate-right-eye", "**/alternate-left-pupil", "**/alternate-right-pupil"):
            node = self.alternate_visual.find(pattern)
            if not node.isEmpty():
                node.hide()
        self.alternate_eye_overlay_root = self.scene_root.attachNewNode("alternate-eye-overlay")
        self.alternate_eye_overlay_root.setTransparency(TransparencyAttrib.MAlpha)
        self.alternate_eye_overlay_root.setDepthWrite(False)
        self.alternate_eye_overlay_root.setBin("transparent", 60)
        self.alternate_eye_overlay_root.setLightOff(1)
        self.alternate_eye_overlay_root.setFogOff(1)
        self.alternate_eye_nodes = []
        eye_white = (0.92, 0.94, 0.91, 1.0)
        pupil_dark = (0.005, 0.005, 0.006, 1.0)
        for side, ex in (("left", -0.086), ("right", 0.086)):
            white = self._alt_ellipsoid(f"alternate-overlay-{side}-eye", (ex, -0.205, 2.40), (0.052, 0.017, 0.026), eye_white, self.alternate_eye_overlay_root)
            pupil = self._alt_ellipsoid(f"alternate-overlay-{side}-pupil", (ex, -0.219, 2.40), (0.028, 0.009, 0.019), pupil_dark, self.alternate_eye_overlay_root)
            white.setLightOff(1); pupil.setLightOff(1)
            self.alternate_eye_nodes.extend((white, pupil))
        self.alternate_eye_overlay_root.hide()

        self.alternate_blur_shells = []
        for idx, (scale_mul, alpha) in enumerate(((1.035, 0.18), (1.075, 0.10))):
            clone = self.alternate_visual.copyTo(self.scene_root)
            clone.setName(f"alternate-blur-shell-{idx}")
            clone.setTransparency(TransparencyAttrib.MAlpha)
            clone.setDepthWrite(False)
            clone.setBin("transparent", 34 - idx)
            clone.setColorScale(0.040, 0.040, 0.048, alpha)
            for pattern in ("**/alternate-left-eye", "**/alternate-right-eye", "**/alternate-left-pupil", "**/alternate-right-pupil"):
                node = clone.find(pattern)
                if not node.isEmpty():
                    node.hide()
            clone.hide()
            self.alternate_blur_shells.append((clone, scale_mul))

        self._apply_alternate_head_variant(0)

        # Lightning is applied to the actual black window pane instead of using
        # a floating flash card, which previously read as a giant translucent slab.
        self.alternate_lightning_card = None

    def _apply_alternate_head_variant(self, variant_index: int | None = None):
        variants=(
            {"head_scale":(1.00,.94,1.00),"head_pos":(0.0,0.0,2.47),"head_hpr":(0.0,-5.0,-3.0),"eye_x":.078,"eye_z":2.39,"eye_scale":(.052,.016,.025),"pupil_scale":(.028,.008,.019)},
            {"head_scale":(.88,.90,1.14),"head_pos":(-.012,.006,2.48),"head_hpr":(0.0,-10.0,-7.0),"eye_x":.070,"eye_z":2.39,"eye_scale":(.049,.015,.026),"pupil_scale":(.026,.008,.020)},
            {"head_scale":(1.12,.84,.91),"head_pos":(.012,-.006,2.44),"head_hpr":(0.0,-2.0,8.0),"eye_x":.086,"eye_z":2.37,"eye_scale":(.055,.014,.024),"pupil_scale":(.030,.007,.018)},
            {"head_scale":(.94,1.02,1.08),"head_pos":(-.020,.004,2.46),"head_hpr":(0.0,-7.0,12.0),"eye_x":.073,"eye_z":2.40,"eye_scale":(.050,.017,.026),"pupil_scale":(.027,.009,.020)},
        )
        if variant_index is None:
            variant_index=(self.alt_manifest_counter+1)%len(variants)
        self.alternate_head_variant=variant_index%len(variants)
        v=variants[self.alternate_head_variant]
        roots=[self.alternate_visual]+[clone for clone,_scale in getattr(self,"alternate_blur_shells",[])]
        for r in roots:
            h=r.find("**/alternate-head")
            if not h.isEmpty():
                h.setPos(*v["head_pos"]); h.setScale(*v["head_scale"]); h.setHpr(*v["head_hpr"])
        if hasattr(self,"alternate_eye_overlay_root"):
            for side,sign in (("left",-1.0),("right",1.0)):
                white=self.alternate_eye_overlay_root.find(f"**/alternate-overlay-{side}-eye")
                pupil=self.alternate_eye_overlay_root.find(f"**/alternate-overlay-{side}-pupil")
                zoff = 0.006 if side == "left" else -0.004
                xmul = 0.96 if side == "left" else 1.04
                if not white.isEmpty():
                    white.setPos(sign*v["eye_x"]*xmul,-.210,v["eye_z"]+zoff)
                    sx,sy,sz=v["eye_scale"]
                    white.setScale(sx*(0.94 if side=="left" else 1.03),sy,sz*(1.04 if side=="left" else .93))
                    white.setR(7.0 if side=="left" else -4.0)
                if not pupil.isEmpty():
                    pupil.setPos(sign*v["eye_x"]*xmul,-.223,v["eye_z"]+zoff)
                    px,py,pz=v["pupil_scale"]
                    pupil.setScale(px*(0.92 if side=="left" else 1.02),py,pz*(1.05 if side=="left" else .92))
                    pupil.setR(7.0 if side=="left" else -4.0)

    def _chair_spy_anchor(self):
        h = math.radians(self.heading)
        fwd = Vec3(-math.sin(h), math.cos(h), 0)
        if fwd.lengthSquared() <= 0.0001:
            fwd = Vec3(1, 0, 0)
        fwd.normalize()
        right = Vec3(fwd.y, -fwd.x, 0)
        base = self.camera.getPos(self.render) - fwd * 0.90 + right * 0.88
        base.z = self.floor_z
        return {
            "id": "chair_spy_anchor",
            "room": self._locate_room_id(self.player.x, self.player.y),
            "kind": "shadow",
            "pos": base,
            "look": Vec3(self.camera.getPos(self.render)),
            "retreat": (-right - fwd * 0.4).normalized(),
            "back_offset": Vec3(0.0, 0.0, 0.0),
            "glass": None,
        }

    def _build_alternate_anchors(self):
        """Author limited spy points so the alternate appears only in shadows or windows."""
        wins = {w["id"]: self._window_world_position(w) for w in self.arch.get("windows", [])}

        glass_names = {
            "w_f2_master_s": "south-window-glass",
            "w_f2_master_w": "west-window-glass",
            "w_f2_bed2_w": "bed2-window-glass",
            "w_f2_bed3_w": "bed3-window-glass",
            "w_f2_bed4_e": "bed4-window-glass",
            "w_f2_bath_e": "bath-window-glass",
        }

        def add_window_anchor(anchor_id: str, room_id: str, win_id: str):
            pos = wins.get(win_id)
            if pos is None:
                return
            room = next((r for r in self.layout["rooms"] if r["id"] == room_id), None)
            if room is None:
                return
            wall = next(w["wall"] for w in self.arch.get("windows", []) if w["id"] == win_id)
            inward = {
                "south": Vec3(0, 1, 0),
                "north": Vec3(0, -1, 0),
                "west": Vec3(1, 0, 0),
                "east": Vec3(-1, 0, 0),
            }[wall]
            room_center = self._room_center(room["rect"])
            anchor_pos = Vec3(pos.x + inward.x * 0.30, pos.y + inward.y * 0.30, self.floor_z)
            self.alternate_anchors.append({
                "id": anchor_id,
                "room": room_id,
                "kind": "window",
                "pos": anchor_pos,
                "look": Vec3(room_center.x, room_center.y, self.floor_z + 1.55),
                "retreat": Vec3(-inward.x, -inward.y, 0),
                "back_offset": Vec3(-inward.x * 0.14, -inward.y * 0.14, 0.0),
                "glass": self.window_glass_nodes.get(glass_names.get(win_id, "")),
            })

        def add_shadow_anchor(anchor_id: str, room_id: str, pos: Vec3, retreat: Vec3):
            room = next((r for r in self.layout["rooms"] if r["id"] == room_id), None)
            if room is None:
                return
            room_center = self._room_center(room["rect"])
            self.alternate_anchors.append({
                "id": anchor_id,
                "room": room_id,
                "kind": "shadow",
                "pos": Vec3(pos.x, pos.y, self.floor_z),
                "look": Vec3(room_center.x, room_center.y, self.floor_z + 1.55),
                "retreat": retreat.normalized() if retreat.lengthSquared() > 0 else Vec3(0, -1, 0),
                "back_offset": retreat.normalized() * 0.08 if retreat.lengthSquared() > 0 else Vec3(0, -0.08, 0),
            })

        add_window_anchor("master_south_window", "f2_master", "w_f2_master_s")
        add_window_anchor("master_west_window", "f2_master", "w_f2_master_w")
        add_window_anchor("bed2_window", "f2_bed2", "w_f2_bed2_w")
        add_window_anchor("bed3_window", "f2_bed3", "w_f2_bed3_w")
        add_window_anchor("bed4_window", "f2_bed4", "w_f2_bed4_e")
        add_window_anchor("bath_window", "f2_bath", "w_f2_bath_e")

        x0, y0, x1, y1 = map(float, self.room_rect)
        add_shadow_anchor("master_corner_shadow", "f2_master", Vec3(x0 + 0.58, y1 - 0.62, self.floor_z), Vec3(-1, 1, 0))
        x0, y0, x1, y1 = map(float, self.hall_rect)
        add_shadow_anchor("hall_shadow", "f2_hall", Vec3(x1 - 0.55, y1 - 0.48, self.floor_z), Vec3(1, 1, 0))
        x0, y0, x1, y1 = map(float, self.bath_rect)
        add_shadow_anchor("bath_shadow", "f2_bath", Vec3(x1 - 0.40, y0 + 0.42, self.floor_z), Vec3(1, -1, 0))
        x0, y0, x1, y1 = map(float, self.stair_rect)
        add_shadow_anchor("stair_shadow", "f2_stair", Vec3(x0 + 0.45, y1 - 0.55, self.floor_z), Vec3(-1, 1, 0))
        x0, y0, x1, y1 = map(float, self.bed2_rect)
        add_shadow_anchor("bed2_shadow", "f2_bed2", Vec3(x1 - 0.45, y1 - 0.45, self.floor_z), Vec3(1, 1, 0))
        x0, y0, x1, y1 = map(float, self.bed3_rect)
        add_shadow_anchor("bed3_shadow", "f2_bed3", Vec3(x1 - 0.45, y1 - 0.45, self.floor_z), Vec3(1, 1, 0))
        x0, y0, x1, y1 = map(float, self.bed4_rect)
        add_shadow_anchor("bed4_shadow", "f2_bed4", Vec3(x0 + 0.45, y0 + 0.52, self.floor_z), Vec3(-1, -1, 0))

    def _room_center(self, rect):
        x0, y0, x1, y1 = map(float, rect)
        return Vec3((x0 + x1) * 0.5, (y0 + y1) * 0.5, self.floor_z)

    def _locate_room_id(self, x: float, y: float):
        if self._in_rect(x, y, self.room_rect): return "f2_master"
        if self._in_rect(x, y, self.hall_rect): return "f2_hall"
        if self._in_rect(x, y, self.bath_rect): return "f2_bath"
        if self._in_rect(x, y, self.stair_rect): return "f2_stair"
        if self._in_rect(x, y, self.bed2_rect): return "f2_bed2"
        if self._in_rect(x, y, self.bed3_rect): return "f2_bed3"
        if self._in_rect(x, y, self.bed4_rect): return "f2_bed4"
        return None

    def _note_room_visit(self, room_id: str | None):
        if not room_id:
            return
        self.current_room_id = room_id
        if self.alternate_visit_order and self.alternate_visit_order[-1] == room_id:
            return
        self.alternate_visit_order.append(room_id)
        if len(self.alternate_visit_order) > 8:
            self.alternate_visit_order = self.alternate_visit_order[-8:]

    def _hide_alternate(self, hard: bool = False):
        self.alt_state = "hidden"
        self.alt_anchor = None
        self.alt_local_time = 0.0
        self.alt_seen_accum = 0.0
        self.alternate_visual.hide()
        if hasattr(self, "alternate_eye_overlay_root"):
            self.alternate_eye_overlay_root.hide()
        for clone, _scale in self.alternate_blur_shells:
            clone.hide()
        if self.alt_anchor is not None and self.alt_anchor.get("glass") is not None:
            self.alt_anchor["glass"].setColor(0.002, 0.002, 0.002, 1.0)
        if hard:
            self.alt_hidden_timer = 9999.0

    def _set_alternate_visibility_mode(self, mode: str = "full"):
        """Switch between the full silhouette and a disembodied-head occurrence.

        This manipulates only presentation nodes; the manifestation state/anchor
        remains unchanged.  Panda3D NodePath hide/show keeps the geometry in the
        scene graph while controlling visibility.
        """
        mode = "head_only" if mode == "head_only" else "full"
        self.alt_visibility_mode = mode
        roots = [self.alternate_visual] + [clone for clone, _scale in getattr(self, "alternate_blur_shells", [])]
        for root in roots:
            for child in root.getChildren():
                name = child.getName()
                if "-eye" in name or "-pupil" in name:
                    child.hide()
                elif mode == "head_only":
                    if name == "alternate-head": child.show()
                    else: child.hide()
                else:
                    child.show()

    def _candidate_alternate_anchors(self):
        rooms = []
        if self.current_room_id:
            rooms.append(self.current_room_id)
        for rid in reversed(self.alternate_visit_order):
            if rid not in rooms:
                rooms.append(rid)
        scoped = [a for a in self.alternate_anchors if not rooms or a["room"] in rooms[:3]]
        scoped = scoped or list(self.alternate_anchors)

        # Ordinary manifestations prefer a point behind the player's current view.
        # If the current rooms do not contain a suitable anchor, fall back rather
        # than inventing a new position or clipping through architecture.
        if not self.tv_focused and scoped:
            cam = self.camera.getPos(self.render)
            h = math.radians(self.heading)
            fwd = Vec3(-math.sin(h), math.cos(h), 0)
            behind = []
            for anchor in scoped:
                delta = Vec3(anchor["pos"]) - cam
                delta.z = 0
                if delta.lengthSquared() <= 0.0001:
                    continue
                delta.normalize()
                if fwd.dot(delta) < -0.12:
                    behind.append(anchor)
            if behind:
                scoped = behind
        return scoped

    def _manifest_alternate(self, anchor_id: str | None = None):
        chair_spy = self.tv_focused and getattr(self, "tv_focus_from_chair", False) and anchor_id is None
        candidates = self._candidate_alternate_anchors()
        if not candidates and not chair_spy:
            return
        if chair_spy:
            anchor = self._chair_spy_anchor()
        elif anchor_id is not None:
            anchor = next((a for a in self.alternate_anchors if a["id"] == anchor_id), None)
            if anchor is None:
                anchor = candidates[0]
        else:
            if self.alt_anchor is not None and len(candidates) > 1:
                candidates = [a for a in candidates if a["id"] != self.alt_anchor["id"]] or candidates
            anchor = candidates[self.alt_manifest_counter % len(candidates)]
        self.alt_manifest_counter += 1
        self.alt_anchor = anchor
        self.alt_state = "active"
        self.alt_local_time = 0.0
        self.alt_seen_accum = 0.0
        self._apply_alternate_head_variant()
        if self.alt_forced_visibility_mode is not None:
            visibility_mode = self.alt_forced_visibility_mode
            self.alt_forced_visibility_mode = None
        elif chair_spy:
            visibility_mode = "head_only" if (self.tv_sit_count % 3 == 0) else "full"
        else:
            visibility_mode = "head_only" if (self.alt_manifest_counter % 5 == 0) else "full"
        self._set_alternate_visibility_mode(visibility_mode)
        self.alternate_visual.show()
        self.alternate_eye_overlay_root.setAlphaScale(1.0)
        self.alternate_eye_overlay_root.show()
        for clone, _scale in self.alternate_blur_shells:
            clone.show()

    def _start_alternate_retreat(self):
        if self.alt_state != "active" or self.alt_anchor is None:
            return
        self.alt_state = "retreat"
        self.alt_local_time = 0.0
        self.alt_origin = Vec3(self.alt_anchor["pos"])
        retreat = Vec3(self.alt_anchor.get("retreat", Vec3(0, -1, 0)))
        if retreat.lengthSquared() <= 0.0001:
            retreat = Vec3(0, -1, 0)
        retreat.normalize()
        self.alt_retreat_dir = retreat

    def _update_alternate(self, dt: float):
        if self.basement_active or self.attic_active:
            if self.alt_state != "hidden": self._hide_alternate()
            return
        room_id = self._locate_room_id(self.player.x, self.player.y)
        if room_id != self.current_room_id:
            self._note_room_visit(room_id)

        if self.alt_state == "hidden":
            self.alt_hidden_timer -= dt
            if self.alt_hidden_timer <= 0.0:
                self._manifest_alternate()
            return

        cam = self.camera.getPos(self.render)
        h = math.radians(self.heading)
        cam_fwd = Vec3(-math.sin(h), math.cos(h), 0)
        eye_target = Vec3(0, 0, 2.36)

        if self.alt_state == "active" and self.alt_anchor is not None:
            self.alt_local_time += dt
            local_t = self.alt_local_time
            anchor = self.alt_anchor
            base = Vec3(anchor["pos"])
            wobble = Vec3(
                math.sin(local_t * 4.3) * 0.020,
                math.sin(local_t * 2.7 + 1.2) * 0.015,
                math.sin(local_t * 5.6 + 0.4) * 0.035,
            )
            pos = base + wobble
            self.alternate_visual.setPos(pos)
            look = Vec3(cam.x, cam.y, cam.z)
            self.alternate_visual.lookAt(look)
            self.alternate_visual.setH(self.alternate_visual.getH() + 180.0)
            self.alternate_visual.setP(math.sin(local_t * 6.0) * 0.9)
            self.alternate_visual.setR(math.sin(local_t * 9.0 + 0.6) * 1.4)
            self.alternate_visual.setScale(1.0 + 0.018 * math.sin(local_t * 3.1))
            self.alternate_eye_overlay_root.setPos(pos)
            self.alternate_eye_overlay_root.setHpr(self.alternate_visual.getH(), self.alternate_visual.getP(), self.alternate_visual.getR())
            self.alternate_eye_overlay_root.setScale(self.alternate_visual.getScale())

            to_alt = (pos + eye_target) - cam
            dist = max(0.001, to_alt.length())
            to_alt_dir = to_alt / dist
            focus = cam_fwd.dot(Vec3(to_alt_dir.x, to_alt_dir.y, 0).normalized()) if abs(to_alt_dir.x) + abs(to_alt_dir.y) > 1e-4 else 0.0
            focus_limit = 0.80 if self.alt_anchor.get("id") == "chair_spy_anchor" else 0.90
            if dist < 8.0 and focus > focus_limit:
                self.alt_seen_accum += dt * (1.5 if self.alt_anchor.get("id") == "chair_spy_anchor" else 1.0)
            else:
                self.alt_seen_accum = max(0.0, self.alt_seen_accum - dt * 1.5)
            if self.alt_seen_accum > 0.040 or dist < 1.10:
                self._start_alternate_retreat()
                return

            flash = 0.0
            if anchor["kind"] == "window":
                for center, width in ((0.55, 0.08), (1.22, 0.05)):
                    pulse = max(0.0, 1.0 - abs(local_t - center) / width)
                    flash = max(flash, pulse * pulse)
            self.alt_lightning_alpha = flash * 0.65
            shade = 0.075 + 0.16 * flash
            alpha = 0.54 + 0.14 * flash
            self.alternate_visual.setColorScale(shade, shade, shade + 0.015, alpha)
            for node in self.alternate_eye_nodes:
                if "pupil" in node.getName():
                    node.setColorScale(0.010, 0.010, 0.012, 1.0)
                else:
                    eye_lift = 1.02 + flash * 0.22
                    node.setColorScale(eye_lift, eye_lift, eye_lift, 1.0)
            for idx, (clone, scale_mul) in enumerate(self.alternate_blur_shells):
                clone.setPos(pos + Vec3(0.038 * (idx + 1) * math.sin(local_t * (7.0 + idx)), 0.030 * (idx + 1) * math.cos(local_t * (5.4 + idx)), 0.012 * (idx + 1) * math.sin(local_t * (4.1 + idx))))
                clone.setHpr(self.alternate_visual.getH(), self.alternate_visual.getP(), self.alternate_visual.getR())
                clone.setScale(self.alternate_visual.getScale().x * scale_mul)
                clone.setColorScale(0.035 + flash * 0.08, 0.035 + flash * 0.08, 0.043 + flash * 0.08, (0.13, 0.08)[idx] + flash * 0.03)

            glass = anchor.get("glass")
            if glass is not None:
                if flash > 0.001:
                    lift = 0.04 + 0.24 * flash
                    glass.setColor(lift, lift, min(0.34, lift + 0.035), 1.0)
                else:
                    glass.setColor(0.002, 0.002, 0.002, 1.0)

            if self.alt_anchor.get("id") == "chair_spy_anchor":
                duration = 9999.0 if self.tv_focused else 2.10
            else:
                duration = 2.10
            if local_t >= duration:
                self._start_alternate_retreat()
                return

        elif self.alt_state == "retreat" and self.alt_anchor is not None:
            self.alt_local_time += dt
            t = min(1.0, self.alt_local_time / 0.18)
            eased = 1.0 - (1.0 - t) * (1.0 - t)
            pos = self.alt_origin + self.alt_retreat_dir * (0.38 * eased)
            self.alternate_visual.setPos(pos)
            self.alternate_visual.setScale(1.0 - 0.10 * eased)
            self.alternate_eye_overlay_root.setPos(pos)
            self.alternate_eye_overlay_root.setHpr(self.alternate_visual.getH(), self.alternate_visual.getP(), self.alternate_visual.getR())
            self.alternate_eye_overlay_root.setScale(self.alternate_visual.getScale())
            alpha = max(0.0, 0.60 * (1.0 - eased))
            self.alternate_visual.setColorScale(0.05, 0.05, 0.06, alpha)
            self.alternate_eye_overlay_root.setAlphaScale(max(0.0, 1.0 - eased))
            for idx, (clone, scale_mul) in enumerate(self.alternate_blur_shells):
                clone.setPos(pos + Vec3(0.02 * (idx + 1), -0.018 * idx, 0.0))
                clone.setHpr(self.alternate_visual.getH(), self.alternate_visual.getP(), self.alternate_visual.getR())
                clone.setScale(max(0.01, self.alternate_visual.getScale().x * scale_mul))
                clone.setColorScale(0.032, 0.032, 0.04, max(0.0, (0.15, 0.09)[idx] * (1.0 - eased)))
            glass = self.alt_anchor.get("glass")
            if glass is not None:
                glass.setColor(0.002, 0.002, 0.002, 1.0)
            if t >= 1.0:
                self._hide_alternate()
                self.alt_hidden_timer = 11.0 + 2.5 * (self.alt_manifest_counter % 4)

    def _window_world_position(self, win):
        """Return the wall-center position for one authored window."""
        room = next((r for r in self.layout["rooms"] if r["id"] == win["room"]), None)
        if room is None:
            return None
        level_id = room["level"]
        level = self.layout["levels"].get(level_id)
        if level is None:
            return None
        x0, y0, x1, y1 = map(float, room["rect"])
        wall = win["wall"]
        offset = float(win.get("center_offset", 0.5))
        z = float(level["z"]) + float(win["sill"]) + float(win["height"]) / 2.0
        if wall in ("north", "south"):
            x = x0 + (x1 - x0) * offset
            y = y1 if wall == "north" else y0
        else:
            y = y0 + (y1 - y0) * offset
            x = x1 if wall == "east" else x0
        return Vec3(x, y, z)

    def _build_window_audio(self):
        """Create positional exterior wind plus sparse one-shot window events.

        Pass 97 keeps the existing low exterior bed but avoids making every window
        behave like an identical synchronized speaker.  Each built Floor 1/2 window
        owns a positional node; a single random window occasionally emits a gust,
        branch scrape, or frame creak from that exact point.
        """
        built_levels = {"floor1", "floor2"}
        cfg = self.window_audio_config
        default_asset = str(cfg.get("default_asset", "assets/audio/window_exterior.wav"))
        per_window = cfg.get("per_window", {})
        volume = max(0.0, min(1.0, float(cfg.get("volume", 0.20))))
        min_distance = max(0.05, float(cfg.get("min_distance", 0.65)))
        dropoff = max(0.0, float(cfg.get("dropoff_factor", 1.35)))

        if not ARGS.no_audio and self.sfxManagerList:
            try:
                self.audio3d = Audio3DManager.Audio3DManager(self.sfxManagerList[0], self.camera)
                self.audio3d.setDistanceFactor(1.0)
                self.audio3d.setDropOffFactor(dropoff)
            except Exception:
                self.audio3d = None
        self.footstep_sounds = {}
        self.footstep_distance_accum = 0.0
        self.footstep_variant = 0
        self.grain_frame = 0
        self.grain_accum = 0.0

        for win in self.arch.get("windows", []):
            room = next((r for r in self.layout["rooms"] if r["id"] == win["room"]), None)
            if room is None or room.get("level") not in built_levels:
                continue
            pos = self._window_world_position(win)
            if pos is None:
                continue
            node = self.scene_root.attachNewNode(f"window-audio-{win['id']}")
            node.setPos(pos)
            entry = {"node": node, "sound": None, "asset": None, "playing": False, "events": []}
            asset_rel = str(per_window.get(win["id"], default_asset))
            asset_path = ROOT / asset_rel
            entry["asset"] = asset_rel
            if self.audio3d is not None and asset_path.exists():
                try:
                    sound = self.audio3d.loadSfx(panda_filename(asset_path))
                    sound.setLoop(True)
                    sound.setVolume(volume)
                    self.audio3d.attachSoundToObject(sound, node)
                    self.audio3d.setSoundMinDistance(sound, min_distance)
                    # Desynchronize the continuous beds where the backend permits it.
                    # This prevents all windows from sounding like one phase-locked loop.
                    try:
                        length = float(sound.length())
                        if length > 0.25:
                            sound.setTime(random.random() * min(length - 0.05, 4.0))
                    except Exception:
                        pass
                    sound.play()
                    entry["sound"] = sound
                    entry["playing"] = True
                except Exception:
                    entry["sound"] = None
            # Load sparse one-shot exterior events onto the same positional node.
            events_cfg = cfg.get("events", {})
            event_volume = max(0.0, min(1.0, float(events_cfg.get("volume", 0.34))))
            event_min_distance = max(0.05, float(events_cfg.get("min_distance", 0.70)))
            if self.audio3d is not None:
                for event_rel in events_cfg.get("assets", []):
                    event_path = ROOT / str(event_rel)
                    if not event_path.exists():
                        continue
                    try:
                        event_sound = self.audio3d.loadSfx(panda_filename(event_path))
                        event_sound.setLoop(False)
                        event_sound.setVolume(event_volume)
                        self.audio3d.attachSoundToObject(event_sound, node)
                        self.audio3d.setSoundMinDistance(event_sound, event_min_distance)
                        entry["events"].append(event_sound)
                    except Exception:
                        pass
            self.window_audio_sources[win["id"]] = entry

        events_cfg = cfg.get("events", {})
        lo = max(1.0, float(events_cfg.get("min_interval", 8.0)))
        hi = max(lo, float(events_cfg.get("max_interval", 22.0)))
        self.window_event_timer = random.uniform(lo, hi)

    def _update_window_audio_events(self, dt: float):
        """Emit occasional positional exterior sounds from individual windows."""
        if ARGS.no_audio or self.audio3d is None or self.forest_active or self.basement_active or self.attic_active:
            return
        cfg = self.window_audio_config.get("events", {})
        if not bool(cfg.get("enabled", True)):
            return
        self.window_event_timer -= max(0.0, dt)
        if self.window_event_timer > 0.0:
            return

        candidates = []
        for wid, entry in self.window_audio_sources.items():
            if wid in self.window_boarded or not entry.get("events"):
                continue
            if wid == self.window_event_last_id and len(self.window_audio_sources) > 1:
                continue
            candidates.append((wid, entry))
        if candidates:
            wid, entry = random.choice(candidates)
            snd = random.choice(entry["events"])
            try:
                snd.stop()
                snd.play()
                self.window_event_last_id = wid
                self.window_event_play_count += 1
            except Exception:
                pass

        lo = max(1.0, float(cfg.get("min_interval", 8.0)))
        hi = max(lo, float(cfg.get("max_interval", 22.0)))
        self.window_event_timer = random.uniform(lo, hi)

    def _set_window_boarded(self, window_id: str, boarded: bool):
        """Board state owns whether that window's exterior ambience is audible."""
        if boarded:
            self.window_boarded.add(window_id)
        else:
            self.window_boarded.discard(window_id)
        entry = self.window_audio_sources.get(window_id)
        if not entry or entry.get("sound") is None:
            return
        sound = entry["sound"]
        if boarded:
            sound.stop()
            entry["playing"] = False
        elif not entry.get("playing"):
            sound.play()
            entry["playing"] = True

    def _build_footstep_audio(self):
        """Load replaceable one-shot footsteps for the house surface map."""
        cfg = self.footstep_audio_config
        volume = max(0.0, min(1.0, float(cfg.get("volume", 0.38))))
        if ARGS.no_audio:
            return
        for surface, rel in cfg.get("surfaces", {}).items():
            path = ROOT / str(rel)
            if not path.exists():
                continue
            try:
                snd = self.loader.loadSfx(panda_filename(path))
                snd.setLoop(False)
                snd.setVolume(volume)
                self.footstep_sounds[surface] = snd
            except Exception:
                pass

    def _surface_under_player(self):
        """Resolve current footstep material from level height and local override zones."""
        z = float(self.player.z)
        levels = self.layout.get("levels", {})
        if not levels:
            return "carpet"
        level_id = min(levels.keys(), key=lambda lid: abs(z - float(levels[lid]["z"])))
        if level_id == "floor1":
            for zone in self.footstep_audio_config.get("floor1_carpet_zones", []):
                x0, y0, x1, y1 = map(float, zone["rect"])
                if x0 <= self.player.x <= x1 and y0 <= self.player.y <= y1:
                    return str(zone.get("surface", "carpet"))
        return str(self.footstep_audio_config.get("level_defaults", {}).get(level_id, "carpet"))

    def _play_footstep(self):
        surface = self._surface_under_player()
        snd = self.footstep_sounds.get(surface)
        if snd is None:
            return
        try:
            # Tiny alternating pitch variation keeps repeated placeholder samples from sounding mechanical.
            snd.setPlayRate(0.97 if (self.footstep_variant % 2 == 0) else 1.03)
            self.footstep_variant += 1
            snd.play()
        except Exception:
            pass

    def _build_film_grain(self):
        """Build a subtle camera-space grain layer over the complete rendered view."""
        cm = CardMaker("camera-film-grain-card")
        cm.setFrameFullscreenQuad()
        self.grain_card = self.render2d.attachNewNode(cm.generate())
        self.grain_card.setTransparency(TransparencyAttrib.MAlpha)
        self.grain_card.setBin("fixed", 200)
        self.grain_card.setDepthWrite(False)
        self.grain_card.setDepthTest(False)

        # Prebuild a tiny bank of textures once. Runtime only swaps texture handles,
        # avoiding per-frame pixel generation that could contribute to stutter.
        self.grain_textures = []
        w, h = 256, 144
        for frame_index in range(4):
            tex = Texture(f"camera-film-grain-{frame_index}")
            image = PNMImage(w, h, 4)
            seed = ((frame_index + 1) * 1103515245 + 12345) & 0x7fffffff
            for y in range(h):
                for x in range(w):
                    seed = (1103515245 * seed + 12345 + x * 17 + y * 31) & 0x7fffffff
                    n = ((seed >> 16) & 255) / 255.0
                    shade = 0.34 + n * 0.40
                    alpha = 0.010 + abs(n - 0.5) * 0.045
                    image.setXelA(x, y, shade, shade, shade, alpha)
            tex.load(image)
            tex.setMinfilter(Texture.FTLinear)
            tex.setMagfilter(Texture.FTLinear)
            self.grain_textures.append(tex)
        self.grain_card.setTexture(self.grain_textures[0])

    def _update_film_grain(self, force=False):
        if not force and self.grain_accum < 0.075:
            return
        self.grain_accum = 0.0
        self.grain_frame += 1
        if self.grain_textures:
            self.grain_card.setTexture(self.grain_textures[self.grain_frame % len(self.grain_textures)], 1)

    def _build_attic_foundation(self):
        """Build Pass 74's simplified, trap-free attic shell and final-task pylon."""
        z0 = self.attic_z
        h = self.attic_ceiling_h
        self.attic_root = self.scene_root.attachNewNode("attic-final-task-root")
        self.attic_root.setFogOff(1)

        wall_t = 0.10
        main = (0.65, 0.65, 8.55, 9.35)
        landing = (8.55, 3.00, 11.30, 5.40)

        # Two clean floor/ceiling slabs replace the old four-room/eave stack.
        # They meet at the connector plane without coplanar overlap; the authored portal
        # bridge owns movement across that seam.
        for name, rect in (("main", main), ("landing", landing)):
            x0, y0, x1, y1 = rect
            cx, cy = (x0+x1)/2.0, (y0+y1)/2.0
            w, d = x1-x0, y1-y0
            self._box(f"attic-{name}-floor", (cx,cy,z0-0.035), (w,d,0.07), 0.12, parent=self.attic_root)
            self._box(f"attic-{name}-ceiling", (cx,cy,z0+h+0.035), (w,d,0.07), 0.10, parent=self.attic_root)
            yy = y0 + 0.28
            idx = 0
            while yy < y1 - 0.12:
                seam = self._box(f"attic-{name}-board-{idx}", (cx,yy,z0+0.014),
                                 (max(0.2,w-0.12),0.012,0.004), 0.055, parent=self.attic_root)
                seam.setLightOff(1)
                yy += 0.34
                idx += 1

        # Main attic perimeter with one deliberately wide opening into the landing.
        x0,y0,x1,y1 = main
        opening_y = 4.20
        opening_w = 1.70
        opening_h = min(2.15, h-0.08)
        lo, hi = opening_y-opening_w/2.0, opening_y+opening_w/2.0
        self._box("attic-main-west-wall", (x0-wall_t/2,(y0+y1)/2,z0+h/2), (wall_t,y1-y0,h), 0.17, parent=self.attic_root)
        self._box("attic-main-south-wall", ((x0+x1)/2,y0-wall_t/2,z0+h/2), (x1-x0,wall_t,h), 0.17, parent=self.attic_root)
        self._box("attic-main-north-wall", ((x0+x1)/2,y1+wall_t/2,z0+h/2), (x1-x0,wall_t,h), 0.17, parent=self.attic_root)
        self._box("attic-main-east-wall-s", (x1+wall_t/2,(y0+lo)/2,z0+h/2), (wall_t,lo-y0,h), 0.17, parent=self.attic_root)
        self._box("attic-main-east-wall-n", (x1+wall_t/2,(hi+y1)/2,z0+h/2), (wall_t,y1-hi,h), 0.17, parent=self.attic_root)
        lint = max(0.01, h-opening_h)
        self._box("attic-main-east-lintel", (x1+wall_t/2,opening_y,z0+opening_h+lint/2),
                  (wall_t,opening_w,lint), 0.17, parent=self.attic_root)

        # Landing is a single readable room. No side eave rooms, doors, or low thresholds remain.
        lx0,ly0,lx1,ly1 = landing
        self._box("attic-landing-east-wall", (lx1+wall_t/2,(ly0+ly1)/2,z0+h/2), (wall_t,ly1-ly0,h), 0.16, parent=self.attic_root)
        self._box("attic-landing-south-wall", ((lx0+lx1)/2,ly0-wall_t/2,z0+h/2), (lx1-lx0,wall_t,h), 0.16, parent=self.attic_root)
        self._box("attic-landing-north-wall", ((lx0+lx1)/2,ly1+wall_t/2,z0+h/2), (lx1-lx0,wall_t,h), 0.16, parent=self.attic_root)

        # A simple hatch frame marks the way back down without obstructing the walk lane.
        hatch_x, hatch_y = 10.35, 4.20
        self._box("attic-return-hatch-left", (hatch_x-0.54,hatch_y,z0+0.035), (0.08,0.95,0.07), 0.24, parent=self.attic_root)
        self._box("attic-return-hatch-right", (hatch_x+0.54,hatch_y,z0+0.035), (0.08,0.95,0.07), 0.24, parent=self.attic_root)
        self._box("attic-return-hatch-front", (hatch_x,hatch_y-0.48,z0+0.035), (1.16,0.08,0.07), 0.24, parent=self.attic_root)
        self._box("attic-return-hatch-rear", (hatch_x,hatch_y+0.48,z0+0.035), (1.16,0.08,0.07), 0.24, parent=self.attic_root)

        # Overhead rafters retain the attic identity and still participate in the finale tear-away.
        # The old floor-to-ceiling cross-braces are gone; they were the main navigation snag.
        for i,x in enumerate((1.25,2.25,3.25,4.25,5.25,6.25,7.25)):
            self._box(f"attic-rafter-{i}", (x,5.0,z0+h-0.20), (0.11,8.30,0.15), 0.22, parent=self.attic_root)
            if i in (1,3,5):
                self._box(f"attic-crossbrace-{i}", (x,5.0,z0+h-0.48), (0.12,1.40,0.12), 0.19, parent=self.attic_root)

        # Storage is pushed to the perimeter, leaving a broad path from entry to pylon.
        for i,(x,y,sx,sy,sz) in enumerate((
            (1.20,1.35,0.62,0.46,0.44),
            (1.35,8.55,0.74,0.52,0.50),
            (7.55,8.55,0.58,0.55,0.54),
        )):
            self._box(f"attic-storage-{i}", (x,y,z0+sz/2), (sx,sy,sz), 0.16, parent=self.attic_root)
            self._box(f"attic-storage-lid-{i}", (x,y,z0+sz+0.018), (sx+0.03,sy+0.03,0.035), 0.22, parent=self.attic_root)

        # Final pylon/support remains in the open center with a full circulation ring around it.
        self.attic_pylon_root = self.attic_root.attachNewNode("attic-final-pylon")
        self._box("attic-pylon-post", (0,0,0), (0.30,0.30,2.08), 0.24, parent=self.attic_pylon_root)
        self._box("attic-pylon-cap", (0,0,1.00), (1.35,0.24,0.20), 0.20, parent=self.attic_pylon_root)
        self._box("attic-pylon-brace-left", (-0.34,0,0.42), (0.12,0.16,1.22), 0.18, parent=self.attic_pylon_root).setR(-22)
        self._box("attic-pylon-brace-right", (0.34,0,0.42), (0.12,0.16,1.22), 0.18, parent=self.attic_pylon_root).setR(22)
        self.attic_pylon_root.setPos(self.attic_pylon_pos)

    def _build_attic_finale_geometry(self):
        """Prepare finished finale geometry but keep it hidden until the pylon gives."""
        # The existing attic ceiling and rafters are the actual pieces that tear away.
        self.attic_tear_nodes = []
        self.attic_tear_initial = []
        for pattern in ("**/attic-*-ceiling", "**/attic-rafter-*", "**/attic-crossbrace-*"):
            for node in self.attic_root.findAllMatches(pattern):
                self.attic_tear_nodes.append(node)
                self.attic_tear_initial.append((Vec3(node.getPos()), node.getHpr()))

        # Black void just outside the roof.  It is not a placeholder: it is the final-space backdrop.
        self.attic_void = self._box(
            "attic-final-black-void", (4.5, 5.0, self.attic_z + self.attic_ceiling_h + 0.42),
            (9.8, 10.0, 0.70), 0.0, parent=self.attic_root
        )
        self.attic_void.setColor(0.0005, 0.0005, 0.0007, 1.0)
        self.attic_void.setLightOff(1)
        self.attic_void.hide()

        # Giant hand/forearm built from smooth forms: broad palm and five elongated fingers.
        self.giant_hand_root = self.scene_root.attachNewNode("finale-giant-hand")
        skin=(0.135,0.140,0.150,1.0)
        self.giant_hand_root.setFogOff(1)
        self.giant_hand_root.setLightOff(1)
        self._alt_ellipsoid("finale-forearm", (0,0,1.58), (0.42,0.38,1.48), skin, self.giant_hand_root)
        self._alt_ellipsoid("finale-palm", (0,0,0.14), (0.74,0.55,0.48), skin, self.giant_hand_root)
        finger_x=(-0.62,-0.32,0.0,0.32,0.62)
        finger_y=(-0.18,-0.09,0.0,0.09,0.18)
        finger_len=(1.02,1.27,1.42,1.25,0.96)
        for i,(fx,fy,flen) in enumerate(zip(finger_x,finger_y,finger_len)):
            finger=self._alt_ellipsoid(f"finale-finger-{i}",(fx,fy,-0.78),(0.105,0.125,flen),skin,self.giant_hand_root)
            finger.setR((i-2)*8.0)
            finger.setP(-8.0 + i*4.0)
        thumb=self._alt_ellipsoid("finale-thumb",(-0.86,0.05,-0.18),(0.14,0.16,0.76),skin,self.giant_hand_root)
        thumb.setR(-34); thumb.setP(20)
        self.giant_hand_root.setTransparency(TransparencyAttrib.MAlpha)
        self.giant_hand_root.hide()

    def _build_finale_ui(self):
        self.finale_blackout = DirectFrame(
            frameColor=(0,0,0,0), frameSize=(-1.7,1.7,-1.05,1.05), sortOrder=80
        )
        self.finale_blackout.setTransparency(TransparencyAttrib.MAlpha)
        self.finale_message = DirectLabel(
            parent=self.finale_blackout, text="", scale=0.070,
            text_fg=(0.88,0.88,0.88,0.0), frameColor=(0,0,0,0), pos=(0,0,0.04),
            text_align=TextNode.ACenter
        )
        self.finale_subtitle = DirectLabel(
            parent=self.finale_blackout, text="", scale=0.034,
            text_fg=(0.52,0.52,0.54,0.0), frameColor=(0,0,0,0), pos=(0,0,-0.13),
            text_align=TextNode.ACenter
        )
        self.finale_blackout.hide()

    def _start_attic_finale(self):
        if self.finale_active or self.finale_finished:
            return
        self.finale_active=True
        self.finale_elapsed=0.0
        self.finale_player_anchor=Vec3(self.player)
        self.finale_camera_base_heading=float(self.heading)
        self.finale_camera_base_pitch=float(self.pitch)
        # Use Panda3D's actual camera transform instead of reconstructing heading math.
        self._apply_camera()
        self.finale_forward=Vec3(self.render.getRelativeVector(self.camera, Vec3(0,-1,0)))
        self.finale_forward.z=0
        if self.finale_forward.lengthSquared() <= 0.0001:
            self.finale_forward=Vec3(0,1,0)
        else:
            self.finale_forward.normalize()
        self._hide_alternate(hard=True)
        self.attic_void.show()
        self.giant_hand_root.hide()
        self.finale_voice_played=False
        self.finale_blackout.show()
        self.finale_blackout["frameColor"]=(0,0,0,0)
        self.finale_message["text"]=""
        self.finale_message["text_fg"]=(0.88,0.88,0.88,0.0)
        self.finale_subtitle["text"]=""
        self.finale_subtitle["text_fg"]=(0.52,0.52,0.54,0.0)
        self.crosshair.hide(); self.prompt.hide(); self.tv_focus_ui.hide()
        self.status["text"]=""
        # Capture exact transforms so a reset can fully restore the attic.
        self.attic_tear_initial=[]
        for node in self.attic_tear_nodes:
            self.attic_tear_initial.append((Vec3(node.getPos()), node.getHpr()))
        self.taskMgr.remove("attic-finale")
        self.taskMgr.add(self._attic_finale_runtime,"attic-finale",sort=18)

    def _attic_finale_runtime(self, task):
        if self.paused:
            return Task.cont
        dt=min(globalClock.getDt(),0.05)
        self.finale_elapsed += dt
        t=self.finale_elapsed

        # Pass 98 finale pacing: dread first, destruction second.  The opening
        # seconds are deliberately restrained so the roof does not immediately
        # become a noisy effect dump.
        shake=max(0.0,min(1.0,t/1.9))
        if t < 3.15:
            amp=0.006 + 0.026*shake
            for i,node in enumerate(self.attic_tear_nodes):
                base_pos,base_hpr=self.attic_tear_initial[i]
                jx=math.sin(t*(10.0+i*0.23))*amp
                jy=math.sin(t*(12.0+i*0.29)+1.3)*amp*0.65
                jz=math.sin(t*(14.0+i*0.19)+0.6)*amp*0.30
                node.setPos(base_pos+Vec3(jx,jy,jz))
                node.setHpr(base_hpr.x+math.sin(t*8+i)*0.42*shake, base_hpr.y, base_hpr.z)

        # The loosened pylon visibly gives way before the roof follows it.
        if hasattr(self,"attic_pylon_root"):
            p=min(1.0,max(0.0,(t-0.55)/2.45))
            p=p*p*(3.0-2.0*p)
            self.attic_pylon_root.setR(-14.0*p)
            self.attic_pylon_root.setP(3.0*p)

        # Camera motion is small and slow; the scene itself supplies the violence.
        if t < 5.0:
            cam_amp=min(1.0,t/1.8) * (1.0 if t < 4.25 else max(0.0,(5.0-t)/0.75))
            self.heading=self.finale_camera_base_heading + math.sin(t*8.4)*0.62*cam_amp
            self.pitch=self.finale_camera_base_pitch + math.sin(t*6.6+0.8)*0.38*cam_amp

        # Roof and rafters separate into the black space above.
        if t >= 2.25:
            tear_t=max(0.0,min(1.0,(t-2.25)/2.45))
            tear_ease=tear_t*tear_t*(3.0-2.0*tear_t)
            for i,node in enumerate(self.attic_tear_nodes):
                base_pos,base_hpr=self.attic_tear_initial[i]
                angle=(i*2.399963229728653)
                outward=Vec3(math.cos(angle),math.sin(angle),1.05+0.08*(i%4))
                displacement=outward*(tear_ease*(2.0+0.11*(i%5)))
                node.setPos(base_pos+displacement)
                node.setHpr(base_hpr.x+tear_ease*(15+6*(i%3)),base_hpr.y+tear_ease*(9*((i%2)*2-1)),base_hpr.z+tear_ease*(20+4*(i%4)))

        # The existing giant hand becomes the final intrusion, entering only after
        # the void has had time to establish itself.
        if t >= 4.65:
            hand_t=max(0.0,min(1.0,(t-4.65)/2.35))
            hand_ease=hand_t*hand_t*(3.0-2.0*hand_t)
            start=self.finale_player_anchor + self.finale_forward*2.50 + Vec3(0,0,5.55)
            end=self.finale_player_anchor + self.finale_forward*0.92 + Vec3(0,0,2.18)
            hand_pos=start+(end-start)*hand_ease
            self.giant_hand_root.show()
            self.giant_hand_root.setPos(hand_pos)
            self.giant_hand_root.setHpr(self.finale_camera_base_heading+180.0,-8.0,9.0*math.sin(hand_t*math.pi))
            self.giant_hand_root.setScale(0.62+0.62*hand_ease)
            self.camera.setPos(self.player.x,self.player.y,self.player.z+self.eye_h)
            self.camera.lookAt(self.giant_hand_root)
            self.camera.setR(math.sin(t*8.0)*0.48*hand_ease)

        # One final remembered sentence appears before contact.  The audio slot is
        # already part of the recovered Alternate authority; no new dialogue is invented.
        if t >= 5.65 and not self.finale_voice_played:
            self.finale_voice_played=True
            self.finale_subtitle["text"]="You know why you are here."
            self.finale_subtitle["text_fg"]=(0.60,0.60,0.62,1.0)
            snd=getattr(self,"alternate_voice_sounds",{}).get("memory_01") if hasattr(self,"alternate_voice_sounds") else None
            if snd is not None:
                try: snd.play()
                except Exception: pass

        # Contact is allowed to linger before the image disappears.
        if t >= 6.75:
            fade=max(0.0,min(1.0,(t-6.75)/1.35))
            fade=fade*fade*(3.0-2.0*fade)
            self.finale_blackout["frameColor"]=(0,0,0,fade)

        if t >= 7.45:
            self.finale_subtitle["text_fg"]=(0.60,0.60,0.62,max(0.0,1.0-(t-7.45)/0.55))

        # End cleanly; the old contradictory "YOUR NEXT TASK IS READY" is gone.
        if t >= 8.20:
            text_a=max(0.0,min(1.0,(t-8.20)/0.55))
            self.finale_message["text"]="END"
            self.finale_message["text_fg"]=(0.72,0.72,0.74,text_a)
            self.finale_subtitle["text"]=""
        if t >= 9.25:
            self.finale_active=False
            self.finale_finished=True
            self.attic_task["state"]="completed"
            self.heading=self.finale_camera_base_heading
            self.pitch=self.finale_camera_base_pitch
            self._on_house_complete()
            return Task.done
        return Task.cont

    def _on_house_complete(self):
        """The attic finale ends DreamCatcher: record it for Limbo and wake the player there."""
        if ARGS.finale_test_shot or _CAPTURE_MODE:
            return
        shared.record_completion("dreamcatcher")
        shared.save_house(None)  # the next visit is a fresh house
        self.finale_subtitle["text"] = "ESC  //  WAKE IN MIRROR'S LIMBO"
        self.finale_subtitle["text_fg"] = (0.60, 0.66, 0.64, 1.0)
        self.taskMgr.doMethodLater(10.0, self._finale_auto_return, "finale-return-limbo")

    def _finale_auto_return(self, task):
        if self.finale_finished and not self.paused:
            self.return_to_limbo()
        return Task.done

    def _reset_attic_finale(self):
        self.taskMgr.remove("attic-finale")
        self.finale_active=False; self.finale_finished=False; self.finale_elapsed=0.0
        if hasattr(self,"attic_void"): self.attic_void.hide()
        if self.giant_hand_root is not None: self.giant_hand_root.hide()
        if hasattr(self,"attic_pylon_root"):
            self.attic_pylon_root.setHpr(0,0,0)
        if hasattr(self,"finale_blackout"):
            self.finale_blackout.hide()
            self.finale_blackout["frameColor"]=(0,0,0,0)
        for i,node in enumerate(self.attic_tear_nodes):
            if i < len(self.attic_tear_initial):
                pos,hpr=self.attic_tear_initial[i]
                node.setPos(pos); node.setHpr(hpr)

    def _enter_attic(self):
        if self.attic_task["state"] not in ("active","loosened"):
            return
        self.attic_active=True; self.basement_active=False
        self.player=Vec3(self.attic_entry_pos); self.heading=90.0; self.pitch=-3.0; self.eye_h=1.62
        self.footstep_distance_accum=0.0
        self._hide_alternate(); self.alt_hidden_timer=9999.0
        self.status["text"]="The attic is waiting."; self.message_timer=2.2
        self._apply_camera()

    def _leave_attic(self):
        if self.finale_active or self.finale_finished:
            return
        self.attic_active=False
        self.floor1_active=False
        self.basement_active=False
        # The preserved Master Bedroom doorway is the floor-transition anchor.
        # Return inside the bedroom instead of the obsolete stair-room hotspot.
        self.player=Vec3(5.30,2.55,self.floor_z); self.heading=90.0; self.pitch=-2.0; self.eye_h=1.62
        self.footstep_distance_accum=0.0; self.alt_hidden_timer=2.5
        self.status["text"]="You step back into the bedroom."; self.message_timer=1.8
        self._apply_camera(); self._update_prompt()

    def _issue_attic_final_task(self):
        if self.attic_task["state"] != "unissued": return
        self.attic_task["state"]="active"
        self._set_task_broadcast("issue13")
        self.tv_frame_counter=0; self.tv_refresh_accum=999.0; self._render_tv_frame(force=True)
        self.status["text"]="The television issues the final instruction."; self.message_timer=2.0

    def _loosen_attic_pylon(self):
        if self.attic_task["state"] != "active" or self.attic_task["pylon_loosened"]: return
        self.attic_task["pylon_loosened"]=True; self.attic_task["state"]="loosened"
        self.attic_pylon_root.setR(2.5)
        self.status["text"]="The pylon gives. Something above you answers."; self.message_timer=1.2
        self._start_attic_finale()

    def _build_basement_liminal(self):
        """Build Pass 73's expanded, readable liminal basement corridor network."""
        z0 = self.basement_z
        h = self.basement_ceiling_h
        self.basement_root = self.scene_root.attachNewNode("basement-liminal-root")
        self.basement_root.setFogOff(1)

        # One continuous slab avoids the coplanar floor/ceiling overlaps that made
        # the previous corridor rectangles flicker and visually mash together.
        self._box("basement-floor-slab", (8.60, 6.75, z0-0.045), (12.40, 11.90, 0.09), 0.15, parent=self.basement_root)
        self._box("basement-ceiling-slab", (8.60, 6.75, z0+h+0.045), (12.40, 11.90, 0.09), 0.14, parent=self.basement_root)

        wall_t = 0.14
        wall_h = h
        wall = 0.18
        # Outer shell.  South wall has a broad, unmistakable stair opening.
        for i,(cx,w) in enumerate(((6.20,7.60),(13.60,2.40))):
            self._box(f"basement-outer-south-{i}", (cx,0.80,z0+wall_h/2), (w,wall_t,wall_h), wall, parent=self.basement_root)
        self._box("basement-outer-west", (2.40,6.75,z0+wall_h/2), (wall_t,11.90,wall_h), wall, parent=self.basement_root)
        self._box("basement-outer-north", (8.60,12.70,z0+wall_h/2), (12.40,wall_t,wall_h), wall, parent=self.basement_root)
        self._box("basement-outer-east", (14.80,6.75,z0+wall_h/2), (wall_t,11.90,wall_h), wall, parent=self.basement_root)

        # Internal concrete walls.  Each segment terminates before a turn so the
        # threshold is visibly open; no black slabs or door meshes are used.
        self.basement_wall_segments = [
            (6.30,3.05,6.50,wall_t), (10.50,4.95,2.80,wall_t),
            (2.85,7.70,wall_t,5.50), (4.95,7.90,wall_t,5.00),
            (8.20,10.20,6.50,wall_t), (9.50,12.40,7.00,wall_t),
            (12.20,9.15,wall_t,2.30), (14.40,8.75,wall_t,3.10),
            (11.25,6.00,4.50,wall_t), (9.95,8.20,4.50,wall_t),
            (6.80,6.05,wall_t,2.00), (9.00,5.50,wall_t,0.90),
        ]
        for i,(cx,cy,w,d) in enumerate(self.basement_wall_segments):
            self._box(f"basement-wall-{i}", (cx,cy,z0+wall_h/2), (w,d,wall_h), wall, parent=self.basement_root)

        # Readable stair/exit alcove: warm concrete steps, side rails and a lit EXIT
        # marker.  This replaces the old near-invisible threshold hotspot.
        for i in range(4):
            # Rise toward the south wall/landing as the player walks out.
            y = 2.02 - i*0.30
            z = z0 + 0.10 + i*0.13
            self._box(f"basement-entry-step-{i}", (11.20,y,z), (1.36,0.30,0.20), 0.28, parent=self.basement_root)
        self._box("basement-entry-rail-left", (10.43,1.62,z0+0.86), (0.08,1.65,0.08), 0.34, parent=self.basement_root)
        self._box("basement-entry-rail-right", (11.97,1.62,z0+0.86), (0.08,1.65,0.08), 0.34, parent=self.basement_root)
        # Pass 92 placement repair: give the horizontal rails visible structural
        # support so they no longer read as floating bars beside the staircase.
        for side_x, side_name in ((10.43, "left"), (11.97, "right")):
            for j,(py,ph) in enumerate(((2.14,0.78),(1.58,0.91),(1.05,1.02))):
                self._box(f"basement-entry-rail-{side_name}-post-{j}",
                          (side_x,py,z0+ph/2.0), (0.08,0.08,ph), 0.32, parent=self.basement_root)
        # Lit concrete stairwell beyond the opening: no black doorway plane.
        self._box("basement-stair-landing", (11.20,0.52,z0+0.58), (1.60,0.62,0.10), 0.30, parent=self.basement_root)
        self._box("basement-stair-back-wall", (11.20,0.18,z0+1.52), (1.80,0.12,1.95), 0.26, parent=self.basement_root)
        self._box("basement-stair-side-left", (10.28,0.55,z0+1.42), (0.12,0.86,1.72), 0.24, parent=self.basement_root)
        self._box("basement-stair-side-right", (12.12,0.55,z0+1.42), (0.12,0.86,1.72), 0.24, parent=self.basement_root)
        exit_sign = self._box("basement-exit-sign", (11.20,0.33,z0+1.73), (0.92,0.06,0.28), 0.72, parent=self.basement_root)
        exit_sign.setLightOff(1)
        stair_light = self._box("basement-stair-light", (11.20,0.58,z0+2.22), (0.55,0.20,0.06), 0.78, parent=self.basement_root)
        stair_light.setLightOff(1)

        # Repeated beams/lights retain the monotonous liminal rhythm without
        # obstructing headroom or corridor width.
        light_points = [
            (10.9,3.95),(8.5,3.95),(6.1,3.95),(3.9,4.6),
            (3.9,7.0),(3.9,9.4),(4.7,11.3),(7.2,11.3),(9.7,11.3),
            (12.9,11.0),(13.3,8.7),(11.8,7.1),(9.4,7.1),(7.9,6.2),
        ]
        for i,(x,y) in enumerate(light_points):
            self._box(f"basement-beam-{i}", (x,y,z0+h-0.15), (0.75,0.10,0.12), 0.24, parent=self.basement_root)
            light = self._box(f"basement-light-{i}", (x,y,z0+h-0.24), (0.42,0.12,0.05), 0.54, parent=self.basement_root)
            light.setLightOff(1)

        # Sparse pipes and utility boxes are kept against walls, never inside the
        # player's navigation lane.
        for i,y in enumerate((5.8,7.8,9.8)):
            self._box(f"basement-pipe-{i}", (2.68,y,z0+1.65), (0.07,0.07,1.20), 0.27, parent=self.basement_root)
            self._box(f"basement-junction-{i}", (2.76,y,z0+1.18), (0.06,0.28,0.30), 0.22, parent=self.basement_root)

        self.basement_clue_root = self.basement_root.attachNewNode("basement-clue")
        # Pass 92 placement repair: mount the clue to the north wall instead of
        # leaving a paper-sized box floating unsupported in the corridor.
        self._box("basement-clue-paper", (0,0,0), (0.34,0.018,0.24), 0.82, parent=self.basement_clue_root)
        self._box("basement-clue-mark", (0,-0.014,0.012), (0.20,0.010,0.030), 0.05, parent=self.basement_clue_root)
        self._box("basement-clue-tape-left", (-0.12,-0.016,0.105), (0.045,0.010,0.060), 0.48, parent=self.basement_clue_root)
        self._box("basement-clue-tape-right", (0.12,-0.016,0.105), (0.045,0.010,0.060), 0.48, parent=self.basement_clue_root)
        self.basement_clue_pos = Vec3(3.55, 12.62, z0 + 1.30)
        self.basement_clue_root.setPos(self.basement_clue_pos)

    def _enter_basement(self):
        self.floor1_active=False
        self.basement_active=True
        self.player=Vec3(self.basement_entry_pos)
        self.heading=90.0; self.pitch=-2.0; self.footstep_distance_accum=0.0
        if hasattr(self,"_hide_alternate"):
            self._hide_alternate(); self.alt_hidden_timer=9999.0
        self.status["text"]="The stairs do not end where they should."; self.message_timer=2.4
        self._apply_camera()

    def _leave_basement(self):
        self.basement_active=False
        self.floor1_active=True
        self.player=Vec3(10.10,4.05,self.floor1_z)
        self.heading=180.0; self.pitch=-2.0
        if hasattr(self,"alt_hidden_timer"): self.alt_hidden_timer=2.5
        self.status["text"]="You are back on the first floor."; self.message_timer=1.6
        self._apply_camera()

    def _collect_basement_clue(self):
        if self.basement_clue_found: return
        self.basement_clue_found=True; self.basement_clue_root.hide()
        if self.basement_task["state"] == "active":
            self.basement_task["state"]="completed"; self.basement_task["completion_count"] += 1
        if self.attic_task["state"] == "locked": self.attic_task["state"] = "unissued"
        self.player=Vec3(self.basement_entry_pos); self.heading=180.0; self.pitch=-2.0; self.footstep_distance_accum=0.0
        self.status["text"]="The corridor folds. You are back at the basement entrance. The TV signal changes upstairs."; self.message_timer=3.4
        self._apply_camera()

    def _update_basement_loop(self):
        # The far east leg quietly folds back into the west corridor.  The player
        # never crosses a fake door or black plane; the corridor itself repeats.
        if self.basement_active and self.player.x > 13.92 and 7.10 <= self.player.y <= 7.92:
            self.player = Vec3(4.18, 7.55, self.basement_z)
            self.basement_loop_count += 1
            self.footstep_distance_accum = 0.0
            self._apply_camera()
            self.status["text"]="The hall continues."; self.message_timer=1.1

    def _build_floor1_shell(self):
        """Pass 55: build the complete downstairs wall shell from project authority.

        The six Floor 1 room rectangles, six accepted portals, and sealed-window
        schedule are the only layout authority.  No furniture or gameplay logic is
        introduced here.  A simple floor/ceiling slab is included only so the wall
        shell can be judged in context.
        """
        level = self.layout["levels"]["floor1"]
        z0 = float(level["z"])
        h = float(level["ceiling_height"])
        t_int = float(self.arch["assemblies"]["interior_partition"]["finished_thickness"])
        t_ext = float(self.arch["assemblies"]["exterior_shell"]["finished_thickness"])
        trim = float(self.arch["assemblies"]["door_casing_width"])
        rooms = [r for r in self.layout["rooms"] if r.get("level") == "floor1"]
        portals = [p for p in self.layout["portals"] if p.get("level") == "floor1"]
        windows = [w for w in self.arch.get("windows", []) if str(w.get("room", "")).startswith("f1_")]
        self.floor1_rooms = {r["id"]: r for r in rooms}

        # Minimal support surfaces only; this pass is about the wall shell.
        self._box("floor1-support-floor", (6.0, 5.0, z0 - 0.06), (11.0, 9.0, 0.12), 0.10)
        self._box("floor1-support-ceiling", (6.0, 5.0, z0 + h + 0.06), (11.0, 9.0, 0.12), 0.31)

        global_x0 = min(r["rect"][0] for r in rooms)
        global_y0 = min(r["rect"][1] for r in rooms)
        global_x1 = max(r["rect"][2] for r in rooms)
        global_y1 = max(r["rect"][3] for r in rooms)

        def side_openings(room, side):
            x0, y0, x1, y1 = map(float, room["rect"])
            horizontal = side in ("north", "south")
            out = []
            for portal in portals:
                if room["id"] not in portal.get("rooms", []):
                    continue
                px, py, _ = map(float, portal["center"])
                # Slightly widen the rendered aperture so paired room walls cannot
                # visually pinch the same doorway from opposite sides.
                width = float(portal["width"]) + 0.18; ph = float(portal["height"])
                if horizontal and portal["axis"] == "y":
                    edge = y1 if side == "north" else y0
                    if abs(py - edge) <= 0.22:
                        out.append((px - width/2, px + width/2, 0.0, ph, "portal", portal["id"]))
                elif (not horizontal) and portal["axis"] == "x":
                    edge = x1 if side == "east" else x0
                    if abs(px - edge) <= 0.22:
                        out.append((py - width/2, py + width/2, 0.0, ph, "portal", portal["id"]))
            for win in windows:
                if win["room"] != room["id"] or win["wall"] != side:
                    continue
                span0, span1 = (x0, x1) if horizontal else (y0, y1)
                center = span0 + (span1 - span0) * float(win.get("center_offset", 0.5))
                ww = float(win["width"]); sill = float(win["sill"]); wh = float(win["height"])
                out.append((center - ww/2, center + ww/2, sill, sill + wh, "window", win["id"]))
            # Pass 85: the downstairs return is now an actual visible stairwell
            # opening, not an invisible interaction point on a blank south wall.
            if room["id"] == "f1_stair" and side == "south":
                cx = 10.10
                width = 1.30
                out.append((cx-width/2, cx+width/2, 0.0, min(2.30, h), "return_stair", "f1_return_stair"))
            out.sort(key=lambda a: a[0])
            return out

        def build_wall(room, side):
            x0, y0, x1, y1 = map(float, room["rect"])
            horizontal = side in ("north", "south")
            span0, span1 = (x0, x1) if horizontal else (y0, y1)
            fixed = y1 if side == "north" else y0 if side == "south" else x1 if side == "east" else x0
            exterior = ((side == "west" and abs(x0-global_x0)<0.01) or
                        (side == "east" and abs(x1-global_x1)<0.01) or
                        (side == "south" and abs(y0-global_y0)<0.01) or
                        (side == "north" and abs(y1-global_y1)<0.01))
            thick = t_ext if exterior else t_int
            openings = side_openings(room, side)
            cursor = span0
            for i, (a,b,low,high,kind,oid) in enumerate(openings):
                a=max(span0,a); b=min(span1,b)
                if a > cursor + 0.01:
                    mid=(cursor+a)/2; length=a-cursor
                    center=(mid,fixed,z0+h/2) if horizontal else (fixed,mid,z0+h/2)
                    size=(length,thick,h) if horizontal else (thick,length,h)
                    self._box(f"f1-{room['id']}-{side}-solid-{i}",center,size,0.28)
                if b > a:
                    if low > 0.01:
                        mid=(a+b)/2
                        center=(mid,fixed,z0+low/2) if horizontal else (fixed,mid,z0+low/2)
                        size=(b-a,thick,low) if horizontal else (thick,b-a,low)
                        self._box(f"f1-{room['id']}-{side}-{oid}-below",center,size,0.28)
                    if high < h - 0.01:
                        top_h=h-high; mid=(a+b)/2
                        center=(mid,fixed,z0+high+top_h/2) if horizontal else (fixed,mid,z0+high+top_h/2)
                        size=(b-a,thick,top_h) if horizontal else (thick,b-a,top_h)
                        self._box(f"f1-{room['id']}-{side}-{oid}-above",center,size,0.28)
                    if kind == "window":
                        # Black exterior-night glazing plus simple frame/casing.
                        mid=(a+b)/2; ww=b-a; wh=high-low; glass_depth=0.018
                        if horizontal:
                            glass_center=(mid, fixed + (0.012 if side=="south" else -0.012), z0+(low+high)/2)
                            self._black_window_glass(f"f1-{oid}-glass", glass_center, (ww-0.08,glass_depth,wh-0.08))
                            for xx in (a+0.035,b-0.035):
                                self._box(f"f1-{oid}-jamb-{xx:.2f}",(xx,fixed,z0+(low+high)/2),(0.07,thick+0.03,wh+0.12),0.50)
                            for zz in (z0+low+0.035,z0+high-0.035):
                                self._box(f"f1-{oid}-rail-{zz:.2f}",(mid,fixed,zz),(ww+0.12,thick+0.03,0.07),0.50)
                        else:
                            glass_center=(fixed + (0.012 if side=="west" else -0.012), mid, z0+(low+high)/2)
                            self._black_window_glass(f"f1-{oid}-glass", glass_center, (glass_depth,ww-0.08,wh-0.08))
                            for yy in (a+0.035,b-0.035):
                                self._box(f"f1-{oid}-jamb-{yy:.2f}",(fixed,yy,z0+(low+high)/2),(thick+0.03,0.07,wh+0.12),0.50)
                            for zz in (z0+low+0.035,z0+high-0.035):
                                self._box(f"f1-{oid}-rail-{zz:.2f}",(fixed,mid,zz),(thick+0.03,ww+0.12,0.07),0.50)
                    elif kind == "portal":
                        # Pass 85: leave ordinary Floor-1 room connections visually
                        # clean.  Building casing independently from both rooms made
                        # the paired apertures read like overlapping mesh.
                        pass
                    elif kind == "return_stair":
                        # One deliberate frame marks the real route upstairs.
                        mid=(a+b)/2
                        if horizontal:
                            for xx in (a-trim/2,b+trim/2):
                                self._box(f"f1-{oid}-case-{xx:.2f}",(xx,fixed,z0+high/2),(trim,thick+0.045,high),0.54)
                            self._box(f"f1-{oid}-case-top",(mid,fixed,z0+high-trim/2),(b-a+trim*2,thick+0.045,trim),0.54)
                        else:
                            for yy in (a-trim/2,b+trim/2):
                                self._box(f"f1-{oid}-case-{yy:.2f}",(fixed,yy,z0+high/2),(thick+0.045,trim,high),0.54)
                            self._box(f"f1-{oid}-case-top",(fixed,mid,z0+high-trim/2),(thick+0.045,b-a+trim*2,trim),0.54)
                cursor=max(cursor,b)
            if cursor < span1 - 0.01:
                mid=(cursor+span1)/2; length=span1-cursor
                center=(mid,fixed,z0+h/2) if horizontal else (fixed,mid,z0+h/2)
                size=(length,thick,h) if horizontal else (thick,length,h)
                self._box(f"f1-{room['id']}-{side}-solid-tail",center,size,0.28)

        for room in rooms:
            for side in ("south","north","west","east"):
                build_wall(room, side)

    def _build_floor1_task_props(self):
        """Readable downstairs task props for living, dining and rear-hall progression."""
        z = self.floor1_z
        # Living-room side table and lamp. The lamp cap is hidden when switched off.
        self._box("f1-living-side-table", (1.55, 2.00, z+0.36), (0.62,0.50,0.72), 0.17)
        self._box("f1-living-lamp-stem", (1.55,2.00,z+0.92), (0.07,0.07,0.55), 0.36)
        self.floor1_lamp_glow = self._box("f1-living-lamp-shade", (1.55,2.00,z+1.23), (0.44,0.44,0.34), 0.72)
        self.floor1_lamp_pos = Vec3(1.55,2.00,z+1.15)
        # Kitchen counter/sink/tap.
        self._box("f1-kitchen-counter", (1.45,8.48,z+0.46), (1.45,0.56,0.92), 0.22)
        self._box("f1-kitchen-sink", (1.45,8.42,z+0.93), (0.62,0.38,0.07), 0.40)
        self.floor1_tap = self._box("f1-kitchen-tap", (1.45,8.28,z+1.12), (0.07,0.07,0.37), 0.50)
        self.floor1_tap_pos = Vec3(1.45,8.12,z+1.05)
        # Dining table plus one deliberately pulled-out chair.
        # Pass 92 placement repair: the old tabletop had no legs and sat at the
        # same height as the chair seat, so it read as a floating slab and the
        # pushed-in chair intersected it.  Use a grounded ~0.76 m table instead.
        table_x, table_y = 7.15, 7.55
        table_h = 0.76
        top_t = 0.10
        self._box("f1-dining-table-top", (table_x,table_y,z+table_h), (1.25,0.86,top_t), 0.23)
        leg_h = table_h - top_t/2.0
        for dx in (-0.49,0.49):
            for dy in (-0.30,0.30):
                self._box(f"f1-dining-table-leg-{dx}-{dy}",
                          (table_x+dx,table_y+dy,z+leg_h/2.0),
                          (0.09,0.09,leg_h), 0.18)
        self.floor1_chair_root = self.scene_root.attachNewNode("f1-dining-task-chair")
        self._box("f1-dining-chair-seat", (0,0,0.47), (0.48,0.48,0.09), 0.19, parent=self.floor1_chair_root)
        self._box("f1-dining-chair-back", (0,0.20,0.88), (0.48,0.08,0.78), 0.19, parent=self.floor1_chair_root)
        for dx in (-0.18,0.18):
            for dy in (-0.18,0.18):
                self._box(f"f1-dining-chair-leg-{dx}-{dy}", (dx,dy,0.23), (0.06,0.06,0.46), 0.16, parent=self.floor1_chair_root)
        self.floor1_chair_root.setPos(7.15,6.55,z)
        self.floor1_chair_pos = Vec3(7.15,6.55,z+0.72)

        # Pass 86: sealed rear door/latch.  It is a readable object in the rear hall,
        # but it never becomes an exit in this pass.  The unsettling instruction is
        # simply to leave the house less secure than the player found it.
        self.floor1_rear_door_root = self.scene_root.attachNewNode("f1-rear-task-door")
        self._box("f1-rear-door-slab", (0,0,1.03), (1.18,0.10,2.06), 0.135, parent=self.floor1_rear_door_root)
        self._box("f1-rear-door-inner-panel", (0,-0.061,1.05), (0.82,0.018,1.30), 0.19, parent=self.floor1_rear_door_root)
        self._box("f1-rear-door-knob", (0.41,-0.105,1.02), (0.08,0.08,0.08), 0.46, parent=self.floor1_rear_door_root)
        self.floor1_rear_latch = self.scene_root.attachNewNode("f1-rear-door-latch-root")
        self._box("f1-rear-door-latch-plate", (0,0,0), (0.33,0.045,0.085), 0.52, parent=self.floor1_rear_latch)
        self._box("f1-rear-door-latch-bolt", (0.18,0,0), (0.28,0.035,0.055), 0.66, parent=self.floor1_rear_latch)
        self.floor1_rear_door_root.setPos(10.10,9.42,z)
        self.floor1_rear_latch.setPos(10.10,9.30,z+1.48)
        self.floor1_rear_latch_pos = Vec3(10.10,9.12,z+1.48)

        # Pass 85: physical/readable return stair.  It is intentionally compact
        # and static; E at the foot performs the existing floor transition.
        stair_x = 10.10
        stair_y0 = 1.30
        for i in range(7):
            sy = stair_y0 - i*0.145
            sz = z + 0.07 + i*0.105
            self._box(f"f1-return-step-{i}", (stair_x,sy,sz), (1.10,0.28,0.13), 0.30)
        self._box("f1-return-rail-left", (9.50,0.83,z+0.62), (0.07,1.05,0.07), 0.44)
        self._box("f1-return-rail-right", (10.70,0.83,z+0.62), (0.07,1.05,0.07), 0.44)
        # A restrained bright lintel is an environmental landmark, not a HUD arrow.
        self._box("f1-return-stair-marker", (stair_x,0.47,z+2.20), (0.58,0.08,0.08), 0.68)
        self.floor1_return_pos = Vec3(stair_x, 1.48, z + 0.72)

    def _enter_floor1(self):
        self.floor1_active=True; self.basement_active=False; self.attic_active=False
        if hasattr(self,"_hide_alternate"):
            self._hide_alternate(); self.alt_hidden_timer=9999.0
        self.player=Vec3(self.floor1_entry_pos); self.heading=180.0; self.pitch=-2.0
        self.footstep_distance_accum=0.0
        self.status["text"]="You step out onto the first floor."; self.message_timer=1.8
        self._apply_camera(); self._update_prompt()

    def _leave_floor1(self):
        self.floor1_active=False
        if hasattr(self,"alt_hidden_timer"): self.alt_hidden_timer=2.5
        # Return to the preserved bedroom, inside the only real door.
        self.player=Vec3(5.30,2.55,self.floor_z); self.heading=90.0; self.pitch=-2.0
        self.footstep_distance_accum=0.0
        self.status["text"]="You return to the bedroom."; self.message_timer=1.6
        self._apply_camera(); self._update_prompt()

    def _floor1_lamp_off(self):
        if self.tv_task_07["state"] != "active" or self.tv_task_07["lamp_off"]: return
        self.tv_task_07["lamp_off"]=True; self.tv_task_07["state"]="changed"
        self.floor1_lamp_glow.setColor(0.12,0.12,0.12,1)
        self.status["text"]="The living-room lamp clicks off. Return to the television."; self.message_timer=2.4

    def _floor1_tap_off(self):
        if self.tv_task_08["state"] != "active" or self.tv_task_08["tap_off"]: return
        self.tv_task_08["tap_off"]=True; self.tv_task_08["state"]="changed"
        self.floor1_tap.setHpr(0,0,35)
        self.status["text"]="The kitchen tap stops. Return to the television."; self.message_timer=2.4

    def _floor1_chair_in(self):
        if self.tv_task_09["state"] != "active" or self.tv_task_09["chair_in"]: return
        self.tv_task_09["chair_in"]=True; self.tv_task_09["state"]="changed"
        self.floor1_chair_root.setY(7.02)
        self.status["text"]="The dining chair is pushed in. Return to the television."; self.message_timer=2.4

    def _floor1_rear_door_unlatch(self):
        if self.tv_task_10["state"] != "active" or self.tv_task_10["unlatched"]: return
        self.tv_task_10["unlatched"] = True
        self.tv_task_10["state"] = "changed"
        # Slide the bolt inward, leaving the door itself visibly closed.
        self.floor1_rear_latch.setX(9.82)
        self.status["text"] = "The rear-door bolt slides free. The door stays closed. Return to the television."
        self.message_timer = 2.8

    def _issue_floor1_task(self, taskno):
        obj={7:self.tv_task_07,8:self.tv_task_08,9:self.tv_task_09,10:self.tv_task_10}[taskno]
        if obj["state"] != "unissued": return
        obj["state"]="active"; self._set_task_broadcast(f"issue{taskno}")
        self.tv_frame_counter=0; self.tv_refresh_accum=999.0; self._render_tv_frame(force=True)
        self.status["text"]="The television sends you downstairs."; self.message_timer=1.8

    def _ack_floor1_task(self, taskno):
        obj={7:self.tv_task_07,8:self.tv_task_08,9:self.tv_task_09,10:self.tv_task_10}[taskno]
        if obj["state"] != "changed": return
        obj["state"]="completed"; obj["completion_count"]+=1
        self._preserve_completion_and_issue_next(f"complete{taskno}", lambda: self._issue_next_after_completion(taskno))
        self.status["text"]=f"The television accepts task {taskno:02d}."; self.message_timer=1.8

    def _issue_basement_task(self):
        if self.basement_task["state"] != "unissued": return
        self.basement_task["state"]="active"; self._set_task_broadcast("issue12")
        self.tv_frame_counter=0; self.tv_refresh_accum=999.0; self._render_tv_frame(force=True)
        self.status["text"]="The television finally directs you to the basement."; self.message_timer=2.0

    def _build_forest_encounter(self):
        """Pass 90: one self-contained snowy-black forest pocket and faith encounter."""
        self.forest_root = self.render.attachNewNode("faith-forest-pocket")
        self.forest_root.hide()
        self.forest_root.setLightOff(1)
        self.forest_fog = Fog("faith-forest-fog")
        self.forest_fog.setColor(0.001, 0.001, 0.002)
        self.forest_fog.setExpDensity(0.055)
        self.forest_root.setFog(self.forest_fog)
        self.forest_tree_blockers=[]
        # Near-black ground with broken snow fields rather than a clean white plane.
        ground=self._box("forest-black-ground",(0,8,-0.09),(20.0,20.5,0.18),0.0,parent=self.forest_root)
        ground.setColor(0.004,0.0045,0.005,1); ground.setLightOff(1)
        snow_patches=[
            (-5.8,2.8,3.2,1.1,0.12),(-1.8,4.0,2.5,0.8,0.17),(3.2,2.5,3.7,0.9,0.10),
            (5.7,6.4,2.7,1.4,0.15),(-5.4,8.0,3.6,1.2,0.13),(-0.7,9.0,4.0,1.5,0.18),
            (3.9,11.0,2.8,1.0,0.12),(-4.1,13.1,3.5,1.3,0.15),(1.4,15.0,4.2,1.0,0.11),
        ]
        for i,(x,y,w,d,shade) in enumerate(snow_patches):
            # Overlapping flattened lobes avoid obvious rectangular decals while
            # retaining the abstract, low-detail house shading language.
            for lobe,(ox,oy,sx,sy) in enumerate(((0,0,0.54,0.50),(w*0.15,-d*0.08,0.38,0.36),(-w*0.17,d*0.09,0.31,0.32))):
                patch=self._alt_ellipsoid(f"forest-snow-patch-{i}-{lobe}",(x+ox,y+oy,0.012),(w*sx,d*sy,0.012),(shade*1.20,shade*1.23,shade*1.28,1),self.forest_root)
                patch.setLightOff(1); patch.setH(((i*31+lobe*17)%19)-9)
        # Deterministic dead forest silhouettes.  Crooked trunks and sparse branches
        # keep the geometry abstract and noisy without turning it into clutter.
        trees=[(-7.4,2.3,.30,4.2,-7),(-5.3,5.0,.25,5.4,5),(-7.6,9.0,.34,6.0,-4),
               (-5.8,14.0,.30,5.0,8),(7.4,2.8,.32,5.2,6),(5.7,5.8,.27,4.5,-6),
               (7.7,9.2,.34,6.4,3),(5.9,14.4,.30,5.5,-8),(-2.9,16.6,.22,4.1,5),(3.3,16.8,.24,4.7,-5)]
        for i,(x,y,r,h,lean) in enumerate(trees):
            root=self.forest_root.attachNewNode(f"forest-tree-{i}"); root.setPos(x,y,0); root.setR(lean)
            trunk=self._box(f"forest-tree-{i}-trunk",(0,0,h/2),(r,r,h),0.008,parent=root)
            trunk.setColor(0.038,0.038,0.043,1); trunk.setLightOff(1)
            for j,(z,side,ang,length) in enumerate(((h*.55,-1,-33,1.6),(h*.70,1,42,1.35),(h*.83,-1,-48,1.0))):
                br=self._box(f"forest-tree-{i}-branch-{j}",(side*length*.34,0,z),(length,.10,.11),0.010,parent=root)
                br.setColor(0.032,0.032,0.037,1); br.setLightOff(1); br.setR(ang)
            self.forest_tree_blockers.append((x,y,max(.20,r*.65)))
        # Fine snow/noise flecks suspended low in the clearing.
        for i in range(62):
            x=((i*37)%181)/10.0-9.0; y=((i*61)%183)/10.0-0.2; z=.05+((i*29)%25)/100.0
            flake=self._box(f"forest-ground-noise-{i}",(x,y,z),(0.018+(i%3)*.008,0.018,0.012),0.10+(i%5)*.012,parent=self.forest_root)
            flake.setLightOff(1)
        # There is no house here: just a door standing in black space.
        self.forest_door_pos=Vec3(0,0,0)
        self.forest_door_frame=self.forest_root.attachNewNode("forest-return-door-frame")
        for x in (-.72,.72):
            n=self._box("forest-door-jamb",(x,0,1.12),(.12,.16,2.24),0.015,parent=self.forest_door_frame); n.setLightOff(1)
        n=self._box("forest-door-lintel",(0,0,2.23),(1.56,.16,.12),0.015,parent=self.forest_door_frame); n.setLightOff(1)
        self.forest_door_hinge=self.forest_root.attachNewNode("forest-black-door-hinge"); self.forest_door_hinge.setPos(-.66,0,0)
        self.forest_door_leaf=self._box("forest-black-door",(.66,0,1.08),(1.32,.10,2.16),0.0,parent=self.forest_door_hinge)
        self.forest_door_leaf.setColor(0.0003,0.0003,0.0004,1); self.forest_door_leaf.setLightOff(1)
        self.forest_door_hinge.setH(62.0)
        # A separate copy keeps ordinary house manifestations frozen while this scene owns the entity.
        self.forest_entity_root=self.alternate_visual.copyTo(self.forest_root)
        self.forest_entity_root.setName("forest-faith-entity")
        self.forest_entity_pos=Vec3(0,12.8,0)
        self.forest_entity_root.setPos(self.forest_entity_pos); self.forest_entity_root.setScale(1.12)
        self.forest_entity_root.setColorScale(0.46,0.46,0.52,0.82)
        self.forest_entity_root.setTransparency(TransparencyAttrib.MAlpha); self.forest_entity_root.setLightOff(1)
        self.forest_entity_root.lookAt(Vec3(0,2,1.4)); self.forest_entity_root.setH(self.forest_entity_root.getH()+180)
        # Eyes are deliberately more legible than the body.  The pupils begin
        # unnervingly small and expand toward the established Alternate pupil ratio
        # as the conversation gains authority.  Keep them as separate nodes so the
        # growth is smooth and does not distort the eye whites.
        self.forest_eye_root=self.forest_root.attachNewNode("forest-entity-eyes")
        self.forest_pupil_nodes=[]
        for side,ex in (("left",-.096),("right",.096)):
            eye=self._alt_ellipsoid(f"forest-faith-{side}-eye",(ex,-.208,2.42),(.055,.018,.034),(.58,.58,.60,1),self.forest_eye_root)
            pupil=self._alt_ellipsoid(f"forest-faith-{side}-pupil",(ex,-.224,2.42),(.010,.007,.009),(.002,.002,.003,1),self.forest_eye_root)
            eye.setLightOff(1); pupil.setLightOff(1); pupil.setFogOff(1)
            pupil.setColor(.002,.002,.003,1.0)
            self.forest_pupil_nodes.append(pupil)
        self.forest_pupil_growth=0.0
        self.forest_eye_root.setPos(self.forest_entity_pos); self.forest_eye_root.setScale(1.12)
        self.forest_eye_root.setHpr(self.forest_entity_root.getHpr())
        self.forest_punish_arms=self.forest_root.attachNewNode("forest-punishment-arms")
        self.forest_punish_arms.hide()
        self.forest_subtitle=DirectLabel(parent=self.aspect2d,text="",scale=.060,pos=(0,0,-.62),text_align=TextNode.ACenter,
                                         text_fg=(.78,.78,.80,1),frameColor=(0,0,0,.58),frameSize=(-.86,.86,-.11,.11),pad=(.04,.025))
        self.forest_choice=DirectLabel(parent=self.aspect2d,text="1  YES        2  NO",scale=.052,pos=(0,0,-.78),text_align=TextNode.ACenter,
                                       text_fg=(.70,.70,.72,1),frameColor=(0,0,0,.48),frameSize=(-.52,.52,-.09,.09),pad=(.03,.02))
        self.forest_blackout=DirectFrame(parent=self.aspect2d,frameColor=(0,0,0,0),frameSize=(-2,2,-1.2,1.2),sortOrder=90)
        self.forest_blackout.setTransparency(True)
        self.forest_subtitle.hide(); self.forest_choice.hide(); self.forest_blackout.hide()
        self.forest_voice={}
        if not ARGS.no_audio:
            for key in ("belief_question","belief_yes","belief_no"):
                try:
                    snd=self.loader.loadSfx(panda_filename(ROOT/f"assets/audio/forest_entity/{key}.wav")); snd.setVolume(.54); self.forest_voice[key]=snd
                except Exception:
                    self.forest_voice[key]=None

    def _forest_play_voice(self,key):
        snd=self.forest_voice.get(key) if hasattr(self,"forest_voice") else None
        if snd is not None:
            try: snd.stop(); snd.play()
            except Exception: pass

    def _set_forest_pupil_growth(self, amount: float):
        """Grow the faith-entity pupils from bead-sized points to Alternate-sized pupils."""
        amount=max(0.0,min(1.0,float(amount)))
        eased=amount*amount*(3.0-2.0*amount)
        self.forest_pupil_growth=eased
        small=Vec3(.010,.007,.009)
        large=Vec3(.036,.010,.028)
        scale=small+(large-small)*eased
        for pupil in getattr(self,"forest_pupil_nodes",[]):
            if pupil is not None and not pupil.isEmpty():
                pupil.setScale(scale)

    def _issue_forest_task(self):
        if self.forest_task["state"] != "unissued": return
        self.forest_task["state"]="active"; self._set_task_broadcast("issue11")
        self.tv_frame_counter=0; self.tv_refresh_accum=999.0; self._render_tv_frame(force=True)
        self.status["text"]="The television tells you to go outside."; self.message_timer=2.2

    def _ack_forest_task(self):
        if self.forest_task["state"] != "changed": return
        self.forest_task["state"]="completed"; self.forest_task["completion_count"] += 1
        self._preserve_completion_and_issue_next("complete11", lambda: self._issue_next_after_completion(11))
        self.status["text"]="The television accepts your answer."; self.message_timer=1.8

    def _enter_forest(self):
        if self.forest_task["state"] != "active": return
        self.floor1_active=False; self.basement_active=False; self.attic_active=False; self.forest_active=True
        self._hide_alternate(hard=True); self.scene_root.hide(); self.forest_root.show()
        self.forest_door_hinge.setH(62.0); self.forest_punish_arms.hide()
        self.player=Vec3(0,2.0,0); self.heading=0.0; self.pitch=-2.0; self.eye_h=1.62
        self.forest_dialogue_stage=None; self.forest_dialogue_elapsed=0.0; self.forest_punish_elapsed=0.0; self.forest_return_ready=False
        self._set_forest_pupil_growth(0.0)
        self.forest_subtitle.hide(); self.forest_choice.hide(); self.forest_blackout.hide(); self.forest_blackout["frameColor"]=(0,0,0,0)
        self.status["text"]="Snow absorbs the sound behind you."; self.message_timer=2.2
        self._apply_camera(); self._update_prompt()

    def _leave_forest(self):
        if not self.forest_active or self.forest_dialogue_stage in ("question","yes_response","punish"): return
        # Leaving before answering is allowed but does not complete the task.
        answered=(self.forest_task.get("choice") is True and self.forest_task["state"]=="changed")
        self.forest_active=False; self.forest_root.hide(); self.scene_root.show(); self.floor1_active=False
        self.player=Vec3(5.30,2.55,self.floor_z); self.heading=90.0; self.pitch=-2.0; self.eye_h=1.62
        self.forest_subtitle.hide(); self.forest_choice.hide(); self.forest_punish_arms.hide(); self._set_mouse_capture(True)
        if hasattr(self, "crosshair"): self.crosshair.show()
        if answered:
            self.status["text"]="The black door opens into your bedroom. Return to the television."; self.message_timer=2.8
        else:
            self.status["text"]="The door returns you to your room. The task remains unfinished."; self.message_timer=2.4
        self._apply_camera(); self._update_prompt()

    def _forest_start_question(self):
        if not self.forest_active or self.forest_task["state"] != "active" or self.forest_dialogue_stage is not None: return
        self.forest_dialogue_stage="question"; self.forest_dialogue_elapsed=0.0
        self.status["text"]=""; self.message_timer=0.0
        if hasattr(self, "crosshair"): self.crosshair.hide()
        self.forest_subtitle["text"]="Do you believe in me?"; self.forest_subtitle.show(); self.forest_choice.show()
        self._forest_play_voice("belief_question")

    def _forest_choose(self, yes: bool):
        if not self.forest_active or self.forest_dialogue_stage != "question": return
        self.forest_choice.hide(); self.forest_dialogue_elapsed=0.0
        if yes:
            self.forest_task["choice"]=True; self.forest_dialogue_stage="yes_response"
            self.forest_subtitle["text"]="Good, now go to your room my child..."; self._forest_play_voice("belief_yes")
        else:
            self.forest_task["choice"]=False; self.forest_dialogue_stage="punish"; self.forest_punish_elapsed=0.0; self.forest_no_line_played=False
            self.forest_subtitle["text"]=""; self.forest_punish_arms.show()

    def _forest_build_arm_tube(self,name,points,radius=.085):
        old=self.forest_punish_arms.find("**/"+name)
        if not old.isEmpty(): old.removeNode()
        if len(points)<2: return
        fmt=GeomVertexFormat.getV3n3c4(); vdata=GeomVertexData(name,fmt,Geom.UHDynamic)
        vw=GeomVertexWriter(vdata,"vertex"); nw=GeomVertexWriter(vdata,"normal"); cw=GeomVertexWriter(vdata,"color")
        sides=12; up=Vec3(0,0,1); rings=[]
        for i,p in enumerate(points):
            tangent=(points[min(i+1,len(points)-1)]-points[max(0,i-1)])
            if tangent.lengthSquared()<1e-8: tangent=Vec3(0,1,0)
            tangent.normalize(); side=tangent.cross(up)
            if side.lengthSquared()<1e-6: side=Vec3(1,0,0)
            else: side.normalize()
            bino=side.cross(tangent); bino.normalize(); ring=[]
            for k in range(sides):
                ang=math.tau*k/sides; radial=side*math.cos(ang)+bino*math.sin(ang)
                rr=radius*(1.0-0.28*(i/max(1,len(points)-1)))
                vw.addData3(p+radial*rr); nw.addData3(radial); cw.addData4(.055,.052,.060,.98); ring.append(i*sides+k)
            rings.append(ring)
        tris=GeomTriangles(Geom.UHDynamic)
        for i in range(len(rings)-1):
            a,b=rings[i],rings[i+1]
            for k in range(sides):
                n=(k+1)%sides; tris.addVertices(a[k],b[k],b[n]); tris.addVertices(a[k],b[n],a[n])
        tris.closePrimitive(); geom=Geom(vdata); geom.addPrimitive(tris); node=GeomNode(name); node.addGeom(geom)
        np=self.forest_punish_arms.attachNewNode(node); np.setTwoSided(True); np.setLightOff(1)

    def _update_forest_encounter(self,dt: float):
        if not self.forest_active: return
        # Nearly imperceptible body drift keeps the silhouette alive without turning it into a chase actor.
        if self.forest_dialogue_stage != "punish":
            t=globalClock.getFrameTime(); self.forest_entity_root.setR(math.sin(t*.43)*.45)
        if self.forest_dialogue_stage == "question":
            self.forest_dialogue_elapsed += dt
            # The change is intentionally slow enough to be doubted at first.
            self._set_forest_pupil_growth(min(.78, self.forest_dialogue_elapsed/3.6*.78))
        elif self.forest_dialogue_stage == "yes_response":
            self.forest_dialogue_elapsed += dt
            self._set_forest_pupil_growth(.78 + min(.22, self.forest_dialogue_elapsed/3.2*.22))
            if self.forest_dialogue_elapsed >= 3.8:
                self.forest_dialogue_stage=None; self.forest_task["state"]="changed"; self.forest_return_ready=True
                self.forest_subtitle.hide(); self.status["text"]="The door behind you is still open."; self.message_timer=1.8
                if hasattr(self, "crosshair"): self.crosshair.show()
        elif self.forest_dialogue_stage == "punish":
            self.forest_punish_elapsed += dt; t=self.forest_punish_elapsed
            grow=max(0.0,min(1.0,t/5.2)); eased=grow*grow*(3-2*grow)
            shake=(0.02+0.18*eased)*math.sin(t*(10+18*eased))
            scale=1.12*(1.0+1.18*eased)
            self.forest_entity_root.setScale(scale); self.forest_entity_root.setPos(self.forest_entity_pos+Vec3(shake,-abs(shake)*.25,0))
            # The silhouette becomes only slightly more legible as the calm disguise drops.
            fury_luma=0.46+0.20*eased
            self.forest_entity_root.setColorScale(fury_luma,fury_luma,min(.72,fury_luma+.06),.88)
            self.forest_eye_root.setScale(scale); self.forest_eye_root.setPos(self.forest_entity_root.getPos()); self.forest_eye_root.setHpr(self.forest_entity_root.getHpr())
            # The pupils finish opening as the calm disguise drops.  Their local
            # proportions match the established Alternate rather than becoming
            # glowing discs or oversized cartoon eyes.
            self._set_forest_pupil_growth(.78 + .22*min(1.0,t/2.4))
            # The sinking player is gradually compelled to keep eye contact as the figure grows.
            # This is slow camera coercion, not a shake/jumpscare.
            eye_z=float(self.forest_entity_root.getZ()) + 2.42*scale
            cam_z=float(self.player.z + self.eye_h)
            dx=float(self.forest_entity_root.getX()-self.player.x); dy=float(self.forest_entity_root.getY()-self.player.y)
            horiz=max(.001, math.hypot(dx,dy))
            target_heading=-math.degrees(math.atan2(dx,dy))
            target_pitch=math.degrees(math.atan2(eye_z-cam_z,horiz))
            lock=min(1.0,dt*(.55+1.55*eased))
            self.heading += (target_heading-self.heading)*lock
            self.pitch += (target_pitch-self.pitch)*lock
            # Two arms grow through empty air toward the freestanding door.
            armprog=max(0.0,min(1.0,(t-.75)/3.7)); armprog=armprog*armprog*(3-2*armprog)
            for side,name in ((-1,"forest-left-arm"),(1,"forest-right-arm")):
                start=Vec3(self.forest_entity_pos.x+side*.52*scale/1.12,self.forest_entity_pos.y-.05,2.0*scale/1.12)
                mid=Vec3(side*(2.2+1.2*armprog),7.0,1.85); end=Vec3(side*.63,.12,1.48)
                pts=[start]
                for i in range(1,18):
                    u=(i/17.0)*armprog; om=1-u
                    q=start*(om*om)+mid*(2*om*u)+end*(u*u); q.z+=.06*math.sin(u*8+t*.8); pts.append(q)
                self._forest_build_arm_tube(name,pts,.075+.055*eased)
            if t > 3.7:
                close=min(1.0,(t-3.7)/1.6); self.forest_door_hinge.setH(62.0*(1.0-close))
            if t > 4.1 and not self.forest_no_line_played:
                self.forest_no_line_played=True; self.forest_subtitle["text"]="Then you shall meet your maker..."; self.forest_subtitle.show(); self._forest_play_voice("belief_no")
            if t > 4.8:
                sink=min(1.0,(t-4.8)/2.4); self.player.z=-1.55*(sink*sink*(3-2*sink))
            if t > 6.0:
                fade=min(1.0,(t-6.0)/2.2); self.forest_blackout.show(); self.forest_blackout["frameColor"]=(0,0,0,fade)
            if t >= 8.35:
                self._complete_datamosh_reset()

    def _reset_forest_encounter(self):
        self.forest_active=False; self.forest_dialogue_stage=None; self.forest_dialogue_elapsed=0.0; self.forest_punish_elapsed=0.0
        self.forest_return_ready=False; self.forest_no_line_played=False
        if hasattr(self,"forest_root"): self.forest_root.hide()
        if hasattr(self,"scene_root"): self.scene_root.show()
        if hasattr(self,"forest_entity_root"):
            self.forest_entity_root.setPos(self.forest_entity_pos); self.forest_entity_root.setScale(1.12); self.forest_entity_root.setR(0)
            self.forest_entity_root.setColorScale(0.46,0.46,0.52,0.82)
        if hasattr(self,"forest_eye_root"):
            self.forest_eye_root.setPos(self.forest_entity_pos); self.forest_eye_root.setScale(1.12)
            self._set_forest_pupil_growth(0.0)
        if hasattr(self,"forest_door_hinge"): self.forest_door_hinge.setH(62.0)
        if hasattr(self,"forest_punish_arms"): self.forest_punish_arms.hide()
        if hasattr(self,"forest_subtitle"): self.forest_subtitle.hide()
        if hasattr(self,"forest_choice"): self.forest_choice.hide()
        if hasattr(self,"forest_blackout"):
            self.forest_blackout.hide(); self.forest_blackout["frameColor"]=(0,0,0,0)
        if hasattr(self, "crosshair") and not getattr(self, "paused", False) and not getattr(self, "tv_focus", False):
            self.crosshair.show()

    def _build_scene(self):
        x0, y0, x1, y1 = self.room_rect
        hx0, hy0, hx1, hy1 = self.hall_rect
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        hcx, hcy = (hx0 + hx1) / 2.0, (hy0 + hy1) / 2.0
        w, d = x1 - x0, y1 - y0
        hw, hd = hx1 - hx0, hy1 - hy0
        t = float(self.arch["assemblies"]["interior_partition"]["finished_thickness"])
        z0 = self.floor_z
        zc = z0 + self.ceiling_h / 2.0

        # Master bedroom reconstruction: the room now uses actual framed window openings,
        # architectural trim, layered flooring and household-scale detailing instead of
        # wall-sized slabs with window cards stuck onto them.
        self._box("master-floor-subfloor", (cx, cy, z0 - 0.06), (w, d, 0.12), 0.11)
        self._box("master-carpet", (cx, cy, z0 + 0.008), (w - 0.08, d - 0.08, 0.016), 0.19)
        self._box("master-ceiling", (cx, cy, z0 + self.ceiling_h + 0.06), (w, d, 0.12), 0.34)
        self._box("master-north-wall", (cx, y1 + t / 2, zc), (w, t, self.ceiling_h), 0.31)
        # Master bedroom: restrained paired pinstripes on the north wall; other walls stay plain.
        self._wallpaper_vertical("master-north", "x", y1 - 0.010, x0 + 0.10, x1 - 0.10, z0 + 0.10, self.ceiling_h - 0.17, "pinstripe")
        self._wallpaper_border("master-north-top", "x", y1 - 0.016, x0 + 0.12, x1 - 0.12, z0 + self.ceiling_h - 0.19, 0.25, 0.045)
        self._wallpaper_border("master-north-low", "x", y1 - 0.016, x0 + 0.12, x1 - 0.12, z0 + 0.33, 0.20, 0.028)

        # South wall split around the accepted sealed bedroom window.
        sw_cx, sw_w, sw_sill, sw_h = 2.25, 1.35, 0.85, 1.15
        sw_l = sw_cx - sw_w/2; sw_r = sw_cx + sw_w/2
        if sw_l > x0:
            self._box("master-south-wall-left", ((x0+sw_l)/2, y0-t/2, zc), (sw_l-x0, t, self.ceiling_h), 0.31)
        if sw_r < x1:
            self._box("master-south-wall-right", ((sw_r+x1)/2, y0-t/2, zc), (x1-sw_r, t, self.ceiling_h), 0.31)
        self._box("master-south-wall-below-window", (sw_cx, y0-t/2, z0+sw_sill/2), (sw_w, t, sw_sill), 0.31)
        above_h = self.ceiling_h - (sw_sill + sw_h)
        self._box("master-south-wall-above-window", (sw_cx, y0-t/2, z0+sw_sill+sw_h+above_h/2), (sw_w, t, above_h), 0.31)
        # Complementary south-wall pattern stops at the window instead of painting through it.
        if sw_l - x0 > 0.22:
            self._wallpaper_vertical("master-south-left", "x", y0 + 0.010, x0 + 0.10, sw_l - 0.08, z0 + 0.10, self.ceiling_h - 0.17, "quiet_pair")
        if x1 - sw_r > 0.22:
            self._wallpaper_vertical("master-south-right", "x", y0 + 0.010, sw_r + 0.08, x1 - 0.10, z0 + 0.10, self.ceiling_h - 0.17, "quiet_pair")

        # West wall split around the accepted sealed bedroom window.
        ww_cy, ww_w, ww_sill, ww_h = 2.75, 1.0, 0.85, 1.15
        ww_lo = ww_cy - ww_w/2; ww_hi = ww_cy + ww_w/2
        if ww_lo > y0:
            self._box("master-west-wall-south", (x0-t/2, (y0+ww_lo)/2, zc), (t, ww_lo-y0, self.ceiling_h), 0.32)
        if ww_hi < y1:
            self._box("master-west-wall-north", (x0-t/2, (ww_hi+y1)/2, zc), (t, y1-ww_hi, self.ceiling_h), 0.32)
        self._box("master-west-wall-below-window", (x0-t/2, ww_cy, z0+ww_sill/2), (t, ww_w, ww_sill), 0.32)
        above_h_w = self.ceiling_h - (ww_sill + ww_h)
        self._box("master-west-wall-above-window", (x0-t/2, ww_cy, z0+ww_sill+ww_h+above_h_w/2), (t, ww_w, above_h_w), 0.32)

        py = float(self.master_portal["center"][1])
        pw = float(self.master_portal["width"])
        ph = float(self.master_portal["height"])
        low_len = (py - pw / 2) - y0
        high_start = py + pw / 2
        high_len = y1 - high_start
        if low_len > 0:
            self._box("master-east-wall-south", (x1 + t / 2, y0 + low_len / 2, zc), (t, low_len, self.ceiling_h), 0.24)
        if high_len > 0:
            self._box("master-east-wall-north", (x1 + t / 2, high_start + high_len / 2, zc), (t, high_len, self.ceiling_h), 0.24)
        lintel_h = max(0.01, self.ceiling_h - ph)
        self._box("master-door-lintel", (x1 + t / 2, py, z0 + ph + lintel_h / 2), (t, pw, lintel_h), 0.24)

        # Pass 41 Upper Hall reconstruction: retain the accepted circulation geometry,
        # but give the hall the same domestic construction language as the rebuilt bedroom.
        self._box("hall-subfloor", (hcx, hcy, z0 - 0.06), (hw, hd, 0.12), 0.11)
        self._box("hall-carpet", (hcx, hcy, z0 + 0.008), (hw - 0.08, hd - 0.08, 0.016), 0.16)
        self._box("hall-ceiling", (hcx, hcy, z0 + self.ceiling_h + 0.06), (hw, hd, 0.12), 0.34)
        self._box("hall-south-wall", (hcx, hy0 - t / 2, zc), (hw, t, self.ceiling_h), 0.30)
        self._box("hall-north-wall", (hcx, hy1 + t / 2, zc), (hw, t, self.ceiling_h), 0.30)
        # Upper Hall: wider double vertical bands on both end walls to distinguish circulation.
        self._wallpaper_vertical("hall-south", "x", hy0 + 0.010, hx0 + 0.08, hx1 - 0.08, z0 + 0.10, self.ceiling_h - 0.17, "double")
        self._wallpaper_vertical("hall-north", "x", hy1 - 0.010, hx0 + 0.08, hx1 - 0.08, z0 + 0.10, self.ceiling_h - 0.17, "double")
        self._wallpaper_border("hall-south-top", "x", hy0 + 0.016, hx0 + 0.10, hx1 - 0.10, z0 + self.ceiling_h - 0.18, 0.27, 0.040)
        self._wallpaper_border("hall-north-top", "x", hy1 - 0.016, hx0 + 0.10, hx1 - 0.10, z0 + self.ceiling_h - 0.18, 0.27, 0.040)
        self._wallpaper_fade_patch("hall-south-age", "x", hy0 + 0.017, hx0 + 0.34, hx0 + 1.05, z0 + 0.52, 0.92, 0.135)

        # East hall wall: use the accepted Floor 2 portal data as the only opening authority.
        # Bathroom, stair passage and Bedroom 4 are all open reconstructed routes.
        east_portals = sorted([p for p in self.layout["portals"] if p["level"] == "floor2" and p["axis"] == "x" and abs(float(p["center"][0]) - 8.55) < 0.05], key=lambda p: p["center"][1])
        cursor_e = hy0
        open_east = {"p_bath_hall", "p_stair_hall", "p_bed4_hall"}
        for portal in east_portals:
            pcy = float(portal["center"][1]); half = float(portal["width"]) / 2
            seg_end = pcy - half
            if seg_end > cursor_e:
                self._box(f"hall-east-wall-{portal['id']}", (hx1 + t / 2, (cursor_e + seg_end) / 2, zc), (t, seg_end - cursor_e, self.ceiling_h), 0.30)
                if seg_end - cursor_e > 0.30:
                    self._wallpaper_vertical(f"hall-east-{portal['id']}", "y", hx1 - 0.010, cursor_e + 0.08, seg_end - 0.08, z0 + 0.10, self.ceiling_h - 0.17, "quiet_pair")
            if portal["id"] not in open_east:
                self._box(f"closed-{portal['id']}", (hx1 + 0.015, pcy, z0 + float(portal["height"]) / 2), (0.07, float(portal["width"]), float(portal["height"])), 0.035)
            else:
                lint = max(0.01, self.ceiling_h - float(portal["height"]))
                self._box(f"hall-east-lintel-{portal['id']}", (hx1 + t / 2, pcy, z0 + float(portal["height"]) + lint / 2), (t, float(portal["width"]), lint), 0.30)
            cursor_e = pcy + half
        if cursor_e < hy1:
            self._box("hall-east-wall-tail", (hx1 + t / 2, (cursor_e + hy1) / 2, zc), (t, hy1 - cursor_e, self.ceiling_h), 0.30)
            if hy1 - cursor_e > 0.30:
                self._wallpaper_vertical("hall-east-tail", "y", hx1 - 0.010, cursor_e + 0.08, hy1 - 0.08, z0 + 0.10, self.ceiling_h - 0.17, "quiet_pair")

        # West hall wall is segmented around every accepted Floor 2 portal.
        # Master Bedroom, Bedroom 2 and Bedroom 3 are all open reconstructed routes.
        west_portals = sorted([p for p in self.layout["portals"] if p["level"] == "floor2" and p["axis"] == "x" and abs(float(p["center"][0]) - 5.95) < 0.05], key=lambda p: p["center"][1])
        open_west = {"p_master_hall", "p_bed2_hall", "p_bed3_hall"}
        cursor = hy0
        for portal in west_portals:
            pcy = float(portal["center"][1]); half = float(portal["width"]) / 2
            seg_end = pcy - half
            if seg_end > cursor:
                self._box(f"hall-west-wall-{portal['id']}", (hx0 - t / 2, (cursor + seg_end) / 2, zc), (t, seg_end - cursor, self.ceiling_h), 0.30)
                if seg_end - cursor > 0.30:
                    self._wallpaper_vertical(f"hall-west-{portal['id']}", "y", hx0 + 0.010, cursor + 0.08, seg_end - 0.08, z0 + 0.10, self.ceiling_h - 0.17, "triple")
            if portal["id"] not in open_west:
                self._box(f"closed-{portal['id']}", (hx0 - 0.015, pcy, z0 + float(portal["height"]) / 2), (0.07, float(portal["width"]), float(portal["height"])), 0.035)
            else:
                lint = max(0.01, self.ceiling_h - float(portal["height"]))
                self._box(f"hall-west-lintel-{portal['id']}", (hx0 - t / 2, pcy, z0 + float(portal["height"]) + lint / 2), (t, float(portal["width"]), lint), 0.30)
            cursor = pcy + half
        if cursor < hy1:
            self._box("hall-west-wall-tail", (hx0 - t / 2, (cursor + hy1) / 2, zc), (t, hy1 - cursor, self.ceiling_h), 0.30)
            if hy1 - cursor > 0.30:
                self._wallpaper_vertical("hall-west-tail", "y", hx0 + 0.010, cursor + 0.08, hy1 - 0.08, z0 + 0.10, self.ceiling_h - 0.17, "triple")

        # Domestic trim and door treatment. Dimensions come from architectural_identity.json:
        # 0.10 m baseboard, 0.075 m casing, 0.018 m casing depth. Door leaves remain
        # at the exact accepted portal centers/heights; this is presentation, not layout drift.
        base_h = float(self.arch["assemblies"]["baseboard_height"])
        case_w = float(self.arch["assemblies"]["door_casing_width"])
        case_d = float(self.arch["assemblies"]["door_casing_depth"])
        crown_h = 0.07
        # Continuous end-wall trim. Long-wall trim is segmented around door openings below.
        self._box("hall-base-south", (hcx, hy0 + 0.018, z0 + base_h/2), (hw, 0.035, base_h), 0.48)
        self._box("hall-base-north", (hcx, hy1 - 0.018, z0 + base_h/2), (hw, 0.035, base_h), 0.48)
        self._box("hall-crown-south", (hcx, hy0 + 0.018, z0 + self.ceiling_h - crown_h/2), (hw, 0.035, crown_h), 0.45)
        self._box("hall-crown-north", (hcx, hy1 - 0.018, z0 + self.ceiling_h - crown_h/2), (hw, 0.035, crown_h), 0.45)

        def hall_wall_trim(axis_x, portals, side_name, face_sign):
            cursor_t = hy0
            for portal in portals:
                pcy = float(portal["center"][1]); pw = float(portal["width"]); ph = float(portal["height"]); half = pw/2
                seg_end = pcy-half
                if seg_end > cursor_t:
                    self._box(f"hall-{side_name}-base-seg", (axis_x, (cursor_t+seg_end)/2, z0+base_h/2), (0.035, seg_end-cursor_t, base_h), 0.48)
                    self._box(f"hall-{side_name}-crown-seg", (axis_x, (cursor_t+seg_end)/2, z0+self.ceiling_h-crown_h/2), (0.035, seg_end-cursor_t, crown_h), 0.45)
                # Hall-side casing around every accepted portal, including closed bedrooms.
                face_x = axis_x + face_sign*case_d/2
                self._box(f"hall-{side_name}-casing-a", (face_x, pcy-half-case_w/2, z0+ph/2), (case_d, case_w, ph), 0.56)
                self._box(f"hall-{side_name}-casing-b", (face_x, pcy+half+case_w/2, z0+ph/2), (case_d, case_w, ph), 0.56)
                self._box(f"hall-{side_name}-casing-top", (face_x, pcy, z0+ph+case_w/2), (case_d, pw+2*case_w, case_w), 0.56)
                cursor_t = pcy+half
            if cursor_t < hy1:
                self._box(f"hall-{side_name}-base-tail", (axis_x, (cursor_t+hy1)/2, z0+base_h/2), (0.035, hy1-cursor_t, base_h), 0.48)
                self._box(f"hall-{side_name}-crown-tail", (axis_x, (cursor_t+hy1)/2, z0+self.ceiling_h-crown_h/2), (0.035, hy1-cursor_t, crown_h), 0.45)

        hall_wall_trim(hx0 + 0.018, west_portals, "west", +1)
        hall_wall_trim(hx1 - 0.018, east_portals, "east", -1)

        # Give closed bedroom doors readable domestic faces instead of flat blocker boards.
        def panel_closed_door(portal, hall_face_x, face_sign, prefix):
            pcy=float(portal["center"][1]); pw=float(portal["width"]); ph=float(portal["height"])
            door_x = hall_face_x + face_sign*0.020
            panel_h = 0.46
            for yy in (-0.22, 0.22):
                for zz in (z0+0.52, z0+1.34):
                    self._box(f"{prefix}-panel", (door_x, pcy+yy, zz), (0.022, 0.27, panel_h), 0.20)
            self._box(f"{prefix}-handle", (door_x + face_sign*0.020, pcy-0.30, z0+0.98), (0.035, 0.075, 0.055), 0.63)

        for portal in west_portals:
            if portal["id"] not in open_west:
                panel_closed_door(portal, hx0+0.035, +1, f"hall-west-{portal['id']}")
        for portal in east_portals:
            if portal["id"] not in open_east:
                panel_closed_door(portal, hx1-0.035, -1, f"hall-east-{portal['id']}")

        # Two restrained flush-mount ceiling fixtures create household rhythm without
        # turning the corridor into a bright gameplay guide.
        for idx, yy in enumerate((3.15, 7.05), 1):
            self._box(f"hall-ceiling-light-{idx}", (hcx, yy, z0+self.ceiling_h-0.035), (0.34, 0.34, 0.07), 0.58)
            self._box(f"hall-ceiling-light-center-{idx}", (hcx, yy, z0+self.ceiling_h-0.075), (0.22, 0.22, 0.035), 0.74)

        # Pass 44 Bedroom 2 reconstruction. The accepted room is a compact study bedroom.
        # It becomes a real playable room without changing the authoritative footprint,
        # doorway, window schedule or furnishing footprints.
        d2x0, d2y0, d2x1, d2y1 = self.bed2_rect
        d2cx, d2cy = (d2x0 + d2x1) / 2.0, (d2y0 + d2y1) / 2.0
        d2w, d2d = d2x1 - d2x0, d2y1 - d2y0
        self._box("bed2-subfloor", (d2cx, d2cy, z0 - 0.06), (d2w, d2d, 0.12), 0.11)
        self._box("bed2-carpet", (d2cx, d2cy, z0 + 0.008), (d2w - 0.08, d2d - 0.08, 0.016), 0.18)
        self._box("bed2-ceiling", (d2cx, d2cy, z0 + self.ceiling_h + 0.06), (d2w, d2d, 0.12), 0.35)
        self._box("bed2-south-wall", (d2cx, d2y0 - t / 2, zc), (d2w, t, self.ceiling_h), 0.30)
        self._box("bed2-north-wall", (d2cx, d2y1 + t / 2, zc), (d2w, t, self.ceiling_h), 0.30)
        # Bedroom 2: classic regular vertical stripe on one wall only.
        self._wallpaper_vertical("bed2-north", "x", d2y1 - 0.010, d2x0 + 0.10, d2x1 - 0.10, z0 + 0.10, self.ceiling_h - 0.17, "stripe")
        self._wallpaper_vertical("bed2-south", "x", d2y0 + 0.010, d2x0 + 0.10, d2x1 - 0.10, z0 + 0.10, self.ceiling_h - 0.17, "broad_narrow")
        self._wallpaper_border("bed2-north-top", "x", d2y1 - 0.016, d2x0 + 0.12, d2x1 - 0.12, z0 + self.ceiling_h - 0.20, 0.24, 0.034)
        self._wallpaper_fade_patch("bed2-south-fade", "x", d2y0 + 0.017, d2x0 + 0.30, d2x0 + 1.10, z0 + 0.44, 0.70, 0.150)

        # West exterior wall: use the accepted sealed Bedroom 2 window schedule.
        bed2_window = next(wi for wi in self.arch["windows"] if wi["id"] == "w_f2_bed2_w")
        d2wc_y = d2cy
        d2ww = float(bed2_window["width"]); d2wh = float(bed2_window["height"]); d2sill = float(bed2_window["sill"])
        d2wlo, d2whi = d2wc_y - d2ww/2.0, d2wc_y + d2ww/2.0
        if d2wlo > d2y0:
            self._box("bed2-west-wall-south", (d2x0 - t/2, (d2y0+d2wlo)/2, zc), (t, d2wlo-d2y0, self.ceiling_h), 0.31)
        if d2whi < d2y1:
            self._box("bed2-west-wall-north", (d2x0 - t/2, (d2whi+d2y1)/2, zc), (t, d2y1-d2whi, self.ceiling_h), 0.31)
        self._box("bed2-west-wall-below-window", (d2x0-t/2, d2wc_y, z0+d2sill/2), (t, d2ww, d2sill), 0.31)
        d2above = self.ceiling_h - (d2sill+d2wh)
        self._box("bed2-west-wall-above-window", (d2x0-t/2, d2wc_y, z0+d2sill+d2wh+d2above/2), (t, d2ww, d2above), 0.31)

        # East wall is segmented around the accepted hall doorway.
        d2py = float(self.bed2_portal["center"][1]); d2pw = float(self.bed2_portal["width"]); d2ph = float(self.bed2_portal["height"])
        d2plo, d2phi = d2py-d2pw/2.0, d2py+d2pw/2.0
        if d2plo > d2y0:
            self._box("bed2-east-wall-south", (d2x1+t/2, (d2y0+d2plo)/2, zc), (t, d2plo-d2y0, self.ceiling_h), 0.30)
        if d2phi < d2y1:
            self._box("bed2-east-wall-north", (d2x1+t/2, (d2phi+d2y1)/2, zc), (t, d2y1-d2phi, self.ceiling_h), 0.30)
        d2lint = max(0.01, self.ceiling_h-d2ph)
        self._box("bed2-east-door-lintel", (d2x1+t/2, d2py, z0+d2ph+d2lint/2), (t, d2pw, d2lint), 0.30)

        # Window recess, dark sealed glazing, sill, frame and muntins.
        glass_x = d2x0 - 0.020
        self._box("bed2-window-recess", (glass_x+0.025, d2wc_y, z0+d2sill+d2wh/2), (0.05, d2ww+0.12, d2wh+0.12), 0.12)
        self._black_window_glass("bed2-window-glass", (glass_x, d2wc_y, z0+d2sill+d2wh/2), (0.025, d2ww-0.08, d2wh-0.08))
        frame_d = 0.045; frame_w = 0.075
        self._box("bed2-window-frame-bottom", (d2x0+0.015, d2wc_y, z0+d2sill), (frame_d, d2ww+0.10, frame_w), 0.52)
        self._box("bed2-window-frame-top", (d2x0+0.015, d2wc_y, z0+d2sill+d2wh), (frame_d, d2ww+0.10, frame_w), 0.52)
        self._box("bed2-window-frame-a", (d2x0+0.015, d2wlo, z0+d2sill+d2wh/2), (frame_d, frame_w, d2wh), 0.52)
        self._box("bed2-window-frame-b", (d2x0+0.015, d2whi, z0+d2sill+d2wh/2), (frame_d, frame_w, d2wh), 0.52)
        self._box("bed2-window-muntin-v", (d2x0+0.010, d2wc_y, z0+d2sill+d2wh/2), (0.035, 0.035, d2wh-0.08), 0.46)
        self._box("bed2-window-muntin-h", (d2x0+0.010, d2wc_y, z0+d2sill+d2wh/2), (0.035, d2ww-0.08, 0.035), 0.46)
        self._box("bed2-window-sill", (d2x0+0.08, d2wc_y, z0+d2sill-0.055), (0.18, d2ww+0.18, 0.055), 0.48)

        # Room-side baseboard/crown. Avoid drawing baseboard through the open doorway.
        self._box("bed2-base-south", (d2cx, d2y0+0.018, z0+base_h/2), (d2w, 0.035, base_h), 0.48)
        self._box("bed2-base-north", (d2cx, d2y1-0.018, z0+base_h/2), (d2w, 0.035, base_h), 0.48)
        self._box("bed2-base-west", (d2x0+0.018, d2cy, z0+base_h/2), (0.035, d2d, base_h), 0.48)
        self._box("bed2-crown-south", (d2cx, d2y0+0.018, z0+self.ceiling_h-0.035), (d2w, 0.035, 0.07), 0.45)
        self._box("bed2-crown-north", (d2cx, d2y1-0.018, z0+self.ceiling_h-0.035), (d2w, 0.035, 0.07), 0.45)
        self._box("bed2-crown-west", (d2x0+0.018, d2cy, z0+self.ceiling_h-0.035), (0.035, d2d, 0.07), 0.45)
        if d2plo > d2y0:
            self._box("bed2-base-east-south", (d2x1-0.018, (d2y0+d2plo)/2, z0+base_h/2), (0.035, d2plo-d2y0, base_h), 0.48)
        if d2phi < d2y1:
            self._box("bed2-base-east-north", (d2x1-0.018, (d2phi+d2y1)/2, z0+base_h/2), (0.035, d2y1-d2phi, base_h), 0.48)

        # Room-side doorway casing only. Bedroom 2 has no door leaf.
        room_face_x = d2x1 - case_d/2
        self._box("bed2-casing-south", (room_face_x, d2plo-case_w/2, z0+d2ph/2), (case_d, case_w, d2ph), 0.56)
        self._box("bed2-casing-north", (room_face_x, d2phi+case_w/2, z0+d2ph/2), (case_d, case_w, d2ph), 0.56)
        self._box("bed2-casing-top", (room_face_x, d2py, z0+d2ph+case_w/2), (case_d, d2pw+2*case_w, case_w), 0.56)
        # Accepted furnishings: twin bed and compact desk, rebuilt as household objects.
        f2objs = {o["id"]: o for o in self.floor2_furnishings["rooms"]["f2_bed2"]["objects"]}
        bed2 = f2objs["bed2_twin"]; bc = bed2["center"]; bs = bed2["size"]
        # Low bed frame + mattress + pillow + west headboard.
        self._box("bed2-bed-frame", (bc[0], bc[1], z0+0.15), (bs[0], bs[1], 0.20), 0.13)
        self._box("bed2-mattress", (bc[0], bc[1], z0+0.32), (bs[0]-0.10, bs[1]-0.10, 0.20), 0.52)
        self._box("bed2-blanket", (bc[0]+0.28, bc[1], z0+0.435), (bs[0]*0.55, bs[1]-0.15, 0.035), 0.27)
        self._box("bed2-pillow", (bc[0]-0.62, bc[1], z0+0.47), (0.42, 0.72, 0.12), 0.67)
        self._box("bed2-headboard", (bc[0]-bs[0]/2+0.045, bc[1], z0+0.54), (0.09, bs[1]+0.08, 0.82), 0.18)
        # Compact desk with top, modesty panel, legs and a small task lamp.
        desk = f2objs["bed2_desk"]; dc = desk["center"]; ds = desk["size"]
        self._box("bed2-desk-top", (dc[0], dc[1], z0+0.73), (ds[0], ds[1], 0.06), 0.24)
        for dx in (-ds[0]/2+0.045, ds[0]/2-0.045):
            for dy in (-ds[1]/2+0.045, ds[1]/2-0.045):
                self._box("bed2-desk-leg", (dc[0]+dx, dc[1]+dy, z0+0.36), (0.07, 0.07, 0.72), 0.19)
        self._box("bed2-desk-back", (dc[0], dc[1]+ds[1]/2-0.035, z0+0.39), (ds[0]-0.10, 0.045, 0.50), 0.17)
        self._box("bed2-desk-lamp-base", (dc[0]+0.20, dc[1], z0+0.79), (0.16, 0.16, 0.05), 0.35)
        self._box("bed2-desk-lamp-stem", (dc[0]+0.20, dc[1], z0+0.98), (0.035, 0.035, 0.36), 0.30)
        self._box("bed2-desk-lamp-shade", (dc[0]+0.20, dc[1]-0.02, z0+1.16), (0.25, 0.20, 0.14), 0.48)

        # One flush ceiling fixture, outlet and small vent give the room mundane domestic detail.
        self._box("bed2-ceiling-light", (d2cx, d2cy, z0+self.ceiling_h-0.04), (0.34, 0.34, 0.08), 0.60)
        self._box("bed2-ceiling-light-center", (d2cx, d2cy, z0+self.ceiling_h-0.085), (0.22, 0.22, 0.035), 0.76)
        self._box("bed2-outlet", (3.20, d2y0+0.018, z0+0.28), (0.16, 0.025, 0.23), 0.50)
        self._box("bed2-vent", (4.55, d2y1-0.020, z0+2.08), (0.62, 0.025, 0.22), 0.43)

        # Pass 46 Bedroom 3 reconstruction. Accepted authority: plain guest bedroom,
        # west sealed window, twin bed, compact dresser, and p_bed3_hall doorway.
        d3x0, d3y0, d3x1, d3y1 = self.bed3_rect
        d3cx, d3cy = (d3x0 + d3x1) / 2.0, (d3y0 + d3y1) / 2.0
        d3w, d3d = d3x1 - d3x0, d3y1 - d3y0
        self._box("bed3-subfloor", (d3cx, d3cy, z0 - 0.06), (d3w, d3d, 0.12), 0.11)
        self._box("bed3-carpet", (d3cx, d3cy, z0 + 0.008), (d3w - 0.08, d3d - 0.08, 0.016), 0.17)
        self._box("bed3-ceiling", (d3cx, d3cy, z0 + self.ceiling_h + 0.06), (d3w, d3d, 0.12), 0.35)
        self._box("bed3-south-wall", (d3cx, d3y0 - t/2, zc), (d3w, t, self.ceiling_h), 0.30)
        self._box("bed3-north-wall", (d3cx, d3y1 + t/2, zc), (d3w, t, self.ceiling_h), 0.30)
        # Bedroom 3: finer pinstripe, visually distinct from Bedroom 2.
        self._wallpaper_vertical("bed3-north", "x", d3y1 - 0.010, d3x0 + 0.10, d3x1 - 0.10, z0 + 0.10, self.ceiling_h - 0.17, "pinstripe")
        self._wallpaper_vertical("bed3-south", "x", d3y0 + 0.010, d3x0 + 0.10, d3x1 - 0.10, z0 + 0.10, self.ceiling_h - 0.17, "triple")
        self._wallpaper_border("bed3-south-mid", "x", d3y0 + 0.016, d3x0 + 0.12, d3x1 - 0.12, z0 + 1.08, 0.215, 0.026)

        bed3_window = next(wi for wi in self.arch["windows"] if wi["id"] == "w_f2_bed3_w")
        d3wc_y = d3cy
        d3ww = float(bed3_window["width"]); d3wh = float(bed3_window["height"]); d3sill = float(bed3_window["sill"])
        d3wlo, d3whi = d3wc_y-d3ww/2, d3wc_y+d3ww/2
        if d3wlo > d3y0:
            self._box("bed3-west-wall-south", (d3x0-t/2, (d3y0+d3wlo)/2, zc), (t, d3wlo-d3y0, self.ceiling_h), 0.31)
        if d3whi < d3y1:
            self._box("bed3-west-wall-north", (d3x0-t/2, (d3whi+d3y1)/2, zc), (t, d3y1-d3whi, self.ceiling_h), 0.31)
        self._box("bed3-west-wall-below-window", (d3x0-t/2, d3wc_y, z0+d3sill/2), (t, d3ww, d3sill), 0.31)
        d3above = self.ceiling_h-(d3sill+d3wh)
        self._box("bed3-west-wall-above-window", (d3x0-t/2, d3wc_y, z0+d3sill+d3wh+d3above/2), (t, d3ww, d3above), 0.31)

        d3py = float(self.bed3_portal["center"][1]); d3pw=float(self.bed3_portal["width"]); d3ph=float(self.bed3_portal["height"])
        d3plo, d3phi = d3py-d3pw/2, d3py+d3pw/2
        if d3plo > d3y0:
            self._box("bed3-east-wall-south", (d3x1+t/2, (d3y0+d3plo)/2, zc), (t, d3plo-d3y0, self.ceiling_h), 0.30)
        if d3phi < d3y1:
            self._box("bed3-east-wall-north", (d3x1+t/2, (d3phi+d3y1)/2, zc), (t, d3y1-d3phi, self.ceiling_h), 0.30)
        d3lint=max(0.01,self.ceiling_h-d3ph)
        self._box("bed3-east-door-lintel", (d3x1+t/2, d3py, z0+d3ph+d3lint/2), (t,d3pw,d3lint), 0.30)

        glass_x=d3x0-0.020
        self._box("bed3-window-recess", (glass_x+0.025,d3wc_y,z0+d3sill+d3wh/2), (0.05,d3ww+0.12,d3wh+0.12), 0.12)
        self._black_window_glass("bed3-window-glass", (glass_x,d3wc_y,z0+d3sill+d3wh/2), (0.025,d3ww-0.08,d3wh-0.08))
        frame_d=0.045; frame_w=0.075
        self._box("bed3-window-frame-bottom", (d3x0+0.015,d3wc_y,z0+d3sill), (frame_d,d3ww+0.10,frame_w), 0.52)
        self._box("bed3-window-frame-top", (d3x0+0.015,d3wc_y,z0+d3sill+d3wh), (frame_d,d3ww+0.10,frame_w), 0.52)
        self._box("bed3-window-frame-a", (d3x0+0.015,d3wlo,z0+d3sill+d3wh/2), (frame_d,frame_w,d3wh), 0.52)
        self._box("bed3-window-frame-b", (d3x0+0.015,d3whi,z0+d3sill+d3wh/2), (frame_d,frame_w,d3wh), 0.52)
        self._box("bed3-window-muntin-v", (d3x0+0.010,d3wc_y,z0+d3sill+d3wh/2), (0.035,0.035,d3wh-0.08), 0.46)
        self._box("bed3-window-muntin-h", (d3x0+0.010,d3wc_y,z0+d3sill+d3wh/2), (0.035,d3ww-0.08,0.035), 0.46)
        self._box("bed3-window-sill", (d3x0+0.08,d3wc_y,z0+d3sill-0.055), (0.18,d3ww+0.18,0.055), 0.48)

        self._box("bed3-base-south", (d3cx,d3y0+0.018,z0+base_h/2), (d3w,0.035,base_h), 0.48)
        self._box("bed3-base-north", (d3cx,d3y1-0.018,z0+base_h/2), (d3w,0.035,base_h), 0.48)
        self._box("bed3-base-west", (d3x0+0.018,d3cy,z0+base_h/2), (0.035,d3d,base_h), 0.48)
        self._box("bed3-crown-south", (d3cx,d3y0+0.018,z0+self.ceiling_h-0.035), (d3w,0.035,0.07), 0.45)
        self._box("bed3-crown-north", (d3cx,d3y1-0.018,z0+self.ceiling_h-0.035), (d3w,0.035,0.07), 0.45)
        self._box("bed3-crown-west", (d3x0+0.018,d3cy,z0+self.ceiling_h-0.035), (0.035,d3d,0.07), 0.45)
        if d3plo>d3y0:
            self._box("bed3-base-east-south", (d3x1-0.018,(d3y0+d3plo)/2,z0+base_h/2), (0.035,d3plo-d3y0,base_h), 0.48)
        if d3phi<d3y1:
            self._box("bed3-base-east-north", (d3x1-0.018,(d3phi+d3y1)/2,z0+base_h/2), (0.035,d3y1-d3phi,base_h), 0.48)

        room_face_x=d3x1-case_d/2
        self._box("bed3-casing-south", (room_face_x,d3plo-case_w/2,z0+d3ph/2), (case_d,case_w,d3ph), 0.56)
        self._box("bed3-casing-north", (room_face_x,d3phi+case_w/2,z0+d3ph/2), (case_d,case_w,d3ph), 0.56)
        self._box("bed3-casing-top", (room_face_x,d3py,z0+d3ph+case_w/2), (case_d,d3pw+2*case_w,case_w), 0.56)
        f3objs={o["id"]:o for o in self.floor2_furnishings["rooms"]["f2_bed3"]["objects"]}
        bed3=f3objs["bed3_twin"]; bc=bed3["center"]; bs=bed3["size"]
        self._box("bed3-bed-frame", (bc[0],bc[1],z0+0.15), (bs[0],bs[1],0.20), 0.13)
        self._box("bed3-mattress", (bc[0],bc[1],z0+0.32), (bs[0]-0.10,bs[1]-0.10,0.20), 0.52)
        self._box("bed3-blanket", (bc[0]+0.28,bc[1],z0+0.435), (bs[0]*0.55,bs[1]-0.15,0.035), 0.25)
        self._box("bed3-pillow", (bc[0]-0.62,bc[1],z0+0.47), (0.42,0.72,0.12), 0.67)
        self._box("bed3-headboard", (bc[0]-bs[0]/2+0.045,bc[1],z0+0.54), (0.09,bs[1]+0.08,0.82), 0.18)
        dr=f3objs["bed3_dresser"]; dc=dr["center"]; ds=dr["size"]
        self._box("bed3-dresser-body", (dc[0],dc[1],z0+ds[2]/2), (ds[0],ds[1],ds[2]), 0.20)
        for dz in (0.18,0.36,0.54):
            self._box("bed3-dresser-drawer", (dc[0],dc[1]-ds[1]/2-0.012,z0+dz), (ds[0]-0.08,0.024,0.12), 0.30)
            self._box("bed3-dresser-pull", (dc[0],dc[1]-ds[1]/2-0.030,z0+dz), (0.12,0.025,0.025), 0.62)
        self._box("bed3-ceiling-light", (d3cx,d3cy,z0+self.ceiling_h-0.04), (0.34,0.34,0.08), 0.60)
        self._box("bed3-ceiling-light-center", (d3cx,d3cy,z0+self.ceiling_h-0.085), (0.22,0.22,0.035), 0.76)
        self._box("bed3-outlet", (3.30,d3y0+0.018,z0+0.28), (0.16,0.025,0.23), 0.50)
        self._box("bed3-vent", (4.65,d3y1-0.020,z0+2.08), (0.62,0.025,0.22), 0.43)

        # Pass 47 Bedroom 4 reconstruction. Accepted authority: narrow spare bedroom,
        # east sealed window, twin bed, compact dresser, and p_bed4_hall doorway.
        d4x0, d4y0, d4x1, d4y1 = self.bed4_rect
        d4cx, d4cy = (d4x0+d4x1)/2.0, (d4y0+d4y1)/2.0
        d4w, d4d = d4x1-d4x0, d4y1-d4y0
        self._box("bed4-subfloor", (d4cx,d4cy,z0-0.06), (d4w,d4d,0.12), 0.11)
        self._box("bed4-carpet", (d4cx,d4cy,z0+0.008), (d4w-0.08,d4d-0.08,0.016), 0.17)
        self._box("bed4-ceiling", (d4cx,d4cy,z0+self.ceiling_h+0.06), (d4w,d4d,0.12), 0.35)
        self._box("bed4-south-wall", (d4cx,d4y0-t/2,zc), (d4w,t,self.ceiling_h), 0.30)
        # Bedroom 4: sparse vertical bands; the north/east/west walls remain blank.
        self._wallpaper_vertical("bed4-south", "x", d4y0 + 0.010, d4x0 + 0.10, d4x1 - 0.10, z0 + 0.10, self.ceiling_h - 0.17, "sparse")
        self._wallpaper_vertical("bed4-north", "x", d4y1 - 0.010, d4x0 + 0.10, d4x1 - 0.10, z0 + 0.10, self.ceiling_h - 0.17, "broad_narrow")
        self._wallpaper_border("bed4-north-top", "x", d4y1 - 0.016, d4x0 + 0.12, d4x1 - 0.12, z0 + self.ceiling_h - 0.20, 0.245, 0.036)
        self._wallpaper_fade_patch("bed4-north-fade", "x", d4y1 - 0.017, d4x1 - 1.20, d4x1 - 0.38, z0 + 0.55, 0.86, 0.145)
        self._box("bed4-north-wall", (d4cx,d4y1+t/2,zc), (d4w,t,self.ceiling_h), 0.30)

        bed4_window=next(wi for wi in self.arch["windows"] if wi["id"]=="w_f2_bed4_e")
        d4wc_y=d4cy; d4ww=float(bed4_window["width"]); d4wh=float(bed4_window["height"]); d4sill=float(bed4_window["sill"])
        d4wlo,d4whi=d4wc_y-d4ww/2,d4wc_y+d4ww/2
        if d4wlo>d4y0:
            self._box("bed4-east-wall-south", (d4x1+t/2,(d4y0+d4wlo)/2,zc), (t,d4wlo-d4y0,self.ceiling_h), 0.31)
        if d4whi<d4y1:
            self._box("bed4-east-wall-north", (d4x1+t/2,(d4whi+d4y1)/2,zc), (t,d4y1-d4whi,self.ceiling_h), 0.31)
        self._box("bed4-east-wall-below-window", (d4x1+t/2,d4wc_y,z0+d4sill/2), (t,d4ww,d4sill), 0.31)
        d4above=self.ceiling_h-(d4sill+d4wh)
        self._box("bed4-east-wall-above-window", (d4x1+t/2,d4wc_y,z0+d4sill+d4wh+d4above/2), (t,d4ww,d4above), 0.31)

        d4py=float(self.bed4_portal["center"][1]); d4pw=float(self.bed4_portal["width"]); d4ph=float(self.bed4_portal["height"])
        d4plo,d4phi=d4py-d4pw/2,d4py+d4pw/2
        if d4plo>d4y0:
            self._box("bed4-west-wall-south", (d4x0-t/2,(d4y0+d4plo)/2,zc), (t,d4plo-d4y0,self.ceiling_h), 0.30)
        if d4phi<d4y1:
            self._box("bed4-west-wall-north", (d4x0-t/2,(d4phi+d4y1)/2,zc), (t,d4y1-d4phi,self.ceiling_h), 0.30)
        d4lint=max(0.01,self.ceiling_h-d4ph)
        self._box("bed4-west-door-lintel", (d4x0-t/2,d4py,z0+d4ph+d4lint/2), (t,d4pw,d4lint), 0.30)

        glass_x=d4x1+0.020
        self._box("bed4-window-recess", (glass_x-0.025,d4wc_y,z0+d4sill+d4wh/2), (0.05,d4ww+0.12,d4wh+0.12), 0.12)
        self._black_window_glass("bed4-window-glass", (glass_x,d4wc_y,z0+d4sill+d4wh/2), (0.025,d4ww-0.08,d4wh-0.08))
        frame_d=0.045; frame_w=0.075
        self._box("bed4-window-frame-bottom", (d4x1-0.015,d4wc_y,z0+d4sill), (frame_d,d4ww+0.10,frame_w), 0.52)
        self._box("bed4-window-frame-top", (d4x1-0.015,d4wc_y,z0+d4sill+d4wh), (frame_d,d4ww+0.10,frame_w), 0.52)
        self._box("bed4-window-frame-a", (d4x1-0.015,d4wlo,z0+d4sill+d4wh/2), (frame_d,frame_w,d4wh), 0.52)
        self._box("bed4-window-frame-b", (d4x1-0.015,d4whi,z0+d4sill+d4wh/2), (frame_d,frame_w,d4wh), 0.52)
        self._box("bed4-window-muntin-v", (d4x1-0.010,d4wc_y,z0+d4sill+d4wh/2), (0.035,0.035,d4wh-0.08), 0.46)
        self._box("bed4-window-muntin-h", (d4x1-0.010,d4wc_y,z0+d4sill+d4wh/2), (0.035,d4ww-0.08,0.035), 0.46)
        self._box("bed4-window-sill", (d4x1-0.08,d4wc_y,z0+d4sill-0.055), (0.18,d4ww+0.18,0.055), 0.48)

        self._box("bed4-base-south", (d4cx,d4y0+0.018,z0+base_h/2), (d4w,0.035,base_h), 0.48)
        self._box("bed4-base-north", (d4cx,d4y1-0.018,z0+base_h/2), (d4w,0.035,base_h), 0.48)
        self._box("bed4-base-east", (d4x1-0.018,d4cy,z0+base_h/2), (0.035,d4d,base_h), 0.48)
        self._box("bed4-crown-south", (d4cx,d4y0+0.018,z0+self.ceiling_h-0.035), (d4w,0.035,0.07), 0.45)
        self._box("bed4-crown-north", (d4cx,d4y1-0.018,z0+self.ceiling_h-0.035), (d4w,0.035,0.07), 0.45)
        self._box("bed4-crown-east", (d4x1-0.018,d4cy,z0+self.ceiling_h-0.035), (0.035,d4d,0.07), 0.45)
        if d4plo>d4y0:
            self._box("bed4-base-west-south", (d4x0+0.018,(d4y0+d4plo)/2,z0+base_h/2), (0.035,d4plo-d4y0,base_h), 0.48)
        if d4phi<d4y1:
            self._box("bed4-base-west-north", (d4x0+0.018,(d4phi+d4y1)/2,z0+base_h/2), (0.035,d4y1-d4phi,base_h), 0.48)

        room_face_x=d4x0+case_d/2
        self._box("bed4-casing-south", (room_face_x,d4plo-case_w/2,z0+d4ph/2), (case_d,case_w,d4ph), 0.56)
        self._box("bed4-casing-north", (room_face_x,d4phi+case_w/2,z0+d4ph/2), (case_d,case_w,d4ph), 0.56)
        self._box("bed4-casing-top", (room_face_x,d4py,z0+d4ph+case_w/2), (case_d,d4pw+2*case_w,case_w), 0.56)
        f4objs={o["id"]:o for o in self.floor2_furnishings["rooms"]["f2_bed4"]["objects"]}
        bed4=f4objs["bed4_twin"]; bc=bed4["center"]; bs=bed4["size"]
        self._box("bed4-bed-frame", (bc[0],bc[1],z0+0.15), (bs[0],bs[1],0.20), 0.13)
        self._box("bed4-mattress", (bc[0],bc[1],z0+0.32), (bs[0]-0.10,bs[1]-0.10,0.20), 0.52)
        self._box("bed4-blanket", (bc[0],bc[1]-0.28,z0+0.435), (bs[0]-0.15,bs[1]*0.55,0.035), 0.25)
        self._box("bed4-pillow", (bc[0],bc[1]+0.62,z0+0.47), (0.72,0.42,0.12), 0.67)
        self._box("bed4-headboard", (bc[0],bc[1]+bs[1]/2-0.045,z0+0.54), (bs[0]+0.08,0.09,0.82), 0.18)
        dr=f4objs["bed4_dresser"]; dc=dr["center"]; ds=dr["size"]
        self._box("bed4-dresser-body", (dc[0],dc[1],z0+ds[2]/2), (ds[0],ds[1],ds[2]), 0.20)
        for dz in (0.18,0.36,0.54):
            self._box("bed4-dresser-drawer", (dc[0],dc[1]-ds[1]/2-0.012,z0+dz), (ds[0]-0.08,0.024,0.12), 0.30)
            self._box("bed4-dresser-pull", (dc[0],dc[1]-ds[1]/2-0.030,z0+dz), (0.12,0.025,0.025), 0.62)
        self._box("bed4-ceiling-light", (d4cx,d4cy,z0+self.ceiling_h-0.04), (0.34,0.34,0.08), 0.60)
        self._box("bed4-ceiling-light-center", (d4cx,d4cy,z0+self.ceiling_h-0.085), (0.22,0.22,0.035), 0.76)
        self._box("bed4-outlet", (d4x0+0.018,6.40,z0+0.28), (0.025,0.16,0.23), 0.50)
        self._box("bed4-vent", (d4x1-0.020,8.85,z0+2.08), (0.025,0.62,0.22), 0.43)

        # Pass 42 Bathroom reconstruction.  Keep the accepted 2.8 x 2.4 m room and
        # fixture coordinates, but replace the open gray shell with a readable domestic bathroom.
        bx0, by0, bx1, by1 = self.bath_rect
        bcx, bcy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
        bw, bd = bx1 - bx0, by1 - by0
        self._box("bath-subfloor", (bcx, bcy, z0 - 0.06), (bw, bd, 0.12), 0.11)
        self._box("bath-tile-floor", (bcx, bcy, z0 + 0.010), (bw - 0.06, bd - 0.06, 0.020), 0.31)
        # A few recessed grout lines are enough to make the floor read as tile without
        # filling the room with hundreds of tiny primitives.
        for gx in (9.40, 10.10, 10.80):
            self._box(f"bath-floor-grout-x-{gx:.2f}", (gx, bcy, z0 + 0.022), (0.014, bd - 0.10, 0.005), 0.10)
        for gy in (1.10, 1.70, 2.30):
            self._box(f"bath-floor-grout-y-{gy:.2f}", (bcx, gy, z0 + 0.022), (bw - 0.10, 0.014, 0.005), 0.10)
        self._box("bath-ceiling", (bcx, bcy, z0 + self.ceiling_h + 0.06), (bw, bd, 0.12), 0.36)
        self._box("bath-south-wall", (bcx, by0 - t / 2, zc), (bw, t, self.ceiling_h), 0.33)
        self._box("bath-north-wall", (bcx, by1 + t / 2, zc), (bw, t, self.ceiling_h), 0.33)

        # West wall is real wall now, segmented around the accepted bathroom doorway.
        bpy = float(self.bath_portal["center"][1]); bpw = float(self.bath_portal["width"]); bph = float(self.bath_portal["height"])
        bplo, bphi = bpy - bpw/2.0, bpy + bpw/2.0
        if bplo > by0:
            self._box("bath-west-wall-south", (bx0 - t/2, (by0+bplo)/2, zc), (t, bplo-by0, self.ceiling_h), 0.32)
        if bphi < by1:
            self._box("bath-west-wall-north", (bx0 - t/2, (bphi+by1)/2, zc), (t, by1-bphi, self.ceiling_h), 0.32)
        blintel = max(0.01, self.ceiling_h - bph)
        self._box("bath-west-door-lintel", (bx0 - t/2, bpy, z0+bph+blintel/2), (t, bpw, blintel), 0.32)

        # East wall is split around the accepted sealed high bathroom window rather than
        # placing a bright rectangle on top of an unbroken wall.
        bw_cy, bw_w, bw_sill, bw_h = bcy, 0.70, 1.25, 0.75
        bw_lo, bw_hi = bw_cy-bw_w/2, bw_cy+bw_w/2
        if bw_lo > by0:
            self._box("bath-east-wall-south", (bx1+t/2, (by0+bw_lo)/2, zc), (t, bw_lo-by0, self.ceiling_h), 0.32)
        if bw_hi < by1:
            self._box("bath-east-wall-north", (bx1+t/2, (bw_hi+by1)/2, zc), (t, by1-bw_hi, self.ceiling_h), 0.32)
        self._box("bath-east-wall-below-window", (bx1+t/2, bw_cy, z0+bw_sill/2), (t, bw_w, bw_sill), 0.32)
        bath_above = self.ceiling_h - (bw_sill+bw_h)
        self._box("bath-east-wall-above-window", (bx1+t/2, bw_cy, z0+bw_sill+bw_h+bath_above/2), (t, bw_w, bath_above), 0.32)

        # Lower wall tile/wainscot gives the room a bathroom material break.
        tile_h = 1.12
        self._box("bath-tile-south", (bcx, by0+0.024, z0+tile_h/2), (bw-0.10, 0.025, tile_h), 0.39)
        self._box("bath-tile-north", (bcx, by1-0.024, z0+tile_h/2), (bw-0.10, 0.025, tile_h), 0.39)
        # Tile only on the solid portions of the east wall around the window.
        if bw_lo > by0:
            self._box("bath-tile-east-south", (bx1-0.024, (by0+bw_lo)/2, z0+tile_h/2), (0.025, bw_lo-by0-0.04, tile_h), 0.39)
        if bw_hi < by1:
            self._box("bath-tile-east-north", (bx1-0.024, (bw_hi+by1)/2, z0+tile_h/2), (0.025, by1-bw_hi-0.04, tile_h), 0.39)

        # Proper framed sealed window: recess, dark glass, frame, sill and muntins.
        glass_x = bx1 - 0.028
        self._box("bath-window-recess", (glass_x+0.022, bw_cy, z0+bw_sill+bw_h/2), (0.045, bw_w+0.10, bw_h+0.10), 0.08)
        self._black_window_glass("bath-window-glass", (glass_x, bw_cy, z0+bw_sill+bw_h/2), (0.018, bw_w-0.08, bw_h-0.08))
        wf=0.055
        self._box("bath-window-frame-s", (glass_x-0.014, bw_lo+wf/2, z0+bw_sill+bw_h/2), (0.026, wf, bw_h+0.10), 0.58)
        self._box("bath-window-frame-n", (glass_x-0.014, bw_hi-wf/2, z0+bw_sill+bw_h/2), (0.026, wf, bw_h+0.10), 0.58)
        self._box("bath-window-frame-bottom", (glass_x-0.014, bw_cy, z0+bw_sill+wf/2), (0.026, bw_w+0.10, wf), 0.58)
        self._box("bath-window-frame-top", (glass_x-0.014, bw_cy, z0+bw_sill+bw_h-wf/2), (0.026, bw_w+0.10, wf), 0.58)
        self._box("bath-window-muntin-v", (glass_x-0.024, bw_cy, z0+bw_sill+bw_h/2), (0.020, 0.030, bw_h-0.10), 0.52)
        self._box("bath-window-muntin-h", (glass_x-0.024, bw_cy, z0+bw_sill+bw_h/2), (0.020, bw_w-0.10, 0.030), 0.52)
        self._box("bath-window-sill", (bx1-0.10, bw_cy, z0+bw_sill-0.035), (0.20, bw_w+0.16, 0.055), 0.52)

        # Pass 43 Stair Landing reconstruction.  This remains the accepted flat landing only;
        # the actual vertical stair flight is deliberately not invented until traversal is built.
        sx0, sy0, sx1, sy1 = self.stair_rect
        scx, scy = (sx0 + sx1) / 2.0, (sy0 + sy1) / 2.0
        sw, sd = sx1 - sx0, sy1 - sy0
        self._box("stair-landing-subfloor", (scx, scy, z0-0.06), (sw,sd,0.12), 0.11)
        self._box("stair-landing-hardwood", (scx, scy, z0+0.010), (sw-0.06,sd-0.06,0.020), 0.23)
        # Broad board seams give a household floor rhythm without pretending to be a full texture pass.
        for yy in (3.65,4.10,4.55,5.00):
            if sy0 < yy < sy1:
                self._box(f"stair-floor-board-{yy:.2f}", (scx,yy,z0+0.022), (sw-0.10,0.010,0.004), 0.08)
        self._box("stair-landing-ceiling", (scx,scy,z0+self.ceiling_h+0.06), (sw,sd,0.12), 0.34)
        self._box("stair-landing-east-wall", (sx1+t/2,scy,zc), (t,sd,self.ceiling_h), 0.30)
        self._box("stair-landing-south-wall", (scx,sy0-t/2,zc), (sw,t,self.ceiling_h), 0.30)
        self._box("stair-landing-north-wall", (scx,sy1+t/2,zc), (sw,t,self.ceiling_h), 0.30)

        # Room-side casing around the accepted hall opening. The top is derived from the
        # 2.15 m portal height, so it cannot pass through the 2.55 m ceiling.
        spw=float(self.stair_portal["width"]); sph=float(self.stair_portal["height"]); spy=float(self.stair_portal["center"][1])
        scw=float(self.arch["assemblies"]["door_casing_width"]); scd=float(self.arch["assemblies"]["door_casing_depth"])
        self._box("stair-room-casing-s", (sx0+0.018,spy-spw/2-scw/2,z0+sph/2), (scd,scw,sph), 0.55)
        self._box("stair-room-casing-n", (sx0+0.018,spy+spw/2+scw/2,z0+sph/2), (scd,scw,sph), 0.55)
        self._box("stair-room-casing-top", (sx0+0.018,spy,z0+sph+scw/2), (scd,spw+2*scw,scw), 0.55)

        # Baseboards and crown establish the same domestic scale as the bedroom/hall.
        sbh=float(self.arch["assemblies"]["baseboard_height"]); sch=0.07
        self._box("stair-base-east", (sx1-0.025,scy,z0+sbh/2), (0.035,sd,sbh), 0.48)
        self._box("stair-base-south", (scx,sy0+0.025,z0+sbh/2), (sw,0.035,sbh), 0.48)
        self._box("stair-base-north", (scx,sy1-0.025,z0+sbh/2), (sw,0.035,sbh), 0.48)
        self._box("stair-crown-east", (sx1-0.028,scy,z0+self.ceiling_h-sch/2), (0.045,sd,sch), 0.45)
        self._box("stair-crown-south", (scx,sy0+0.028,z0+self.ceiling_h-sch/2), (sw,0.045,sch), 0.45)
        self._box("stair-crown-north", (scx,sy1-0.028,z0+self.ceiling_h-sch/2), (sw,0.045,sch), 0.45)

        # A wall-mounted handrail and brackets make the space read as vertical circulation
        # without faking a traversable stair flight before that system exists.
        rail_z=z0+0.90
        self._box("stair-wall-handrail", (sx1-0.075,scy,rail_z), (0.045,sd-0.36,0.045), 0.53)
        for yy in (sy0+0.35, scy, sy1-0.35):
            self._box("stair-handrail-bracket", (sx1-0.045,yy,rail_z-0.11), (0.060,0.035,0.20), 0.42)
        self._box("stair-ceiling-light", (scx,scy,z0+self.ceiling_h-0.045), (0.34,0.34,0.08), 0.64)
        self._box("stair-wall-frame-outer", (sx1-0.045,4.66,z0+1.58), (0.045,0.56,0.48), 0.22)
        self._box("stair-wall-frame-inner", (sx1-0.070,4.66,z0+1.58), (0.025,0.44,0.36), 0.08)

        # Rebuild the accepted fixtures into recognizable household forms while preserving
        # every accepted footprint/center from floor2_furnishings.json.
        bath_objs = {o["id"]: o for o in self.floor2_furnishings["rooms"]["f2_bath"]["objects"]}

        # Fixture repair: keep the vanity/task side intact, but place the tub and
        # toilet against the room perimeter so the bathroom reads as a believable
        # lived-in room instead of two center-floating placeholders.
        tub = bath_objs["bath_tub"]; _tcx,_tcy,_ = tub["center"]; tsx,tsy,tsz = tub["size"]
        tub_len = max(tsx, 1.46)
        tub_depth = min(tsy, 0.84)
        # Pass 89: move the tub away from the doorway approach.  Its old west edge,
        # once expanded by PLAYER_RADIUS, intruded into the north half of the bathroom
        # threshold and caught diagonal entries even though the portal center was clear.
        tub_x = bx0 + tub_len * 0.50 + 0.75
        tub_y = by1 - tub_depth * 0.50 - 0.12
        self.bath_tub_blocker = (
            tub_x - tub_len * 0.50, tub_y - tub_depth * 0.50,
            tub_x + tub_len * 0.50, tub_y + tub_depth * 0.50,
        )
        self._box("bath-tub-apron", (tub_x, tub_y, z0 + tsz*0.46), (tub_len, tub_depth, tsz*0.92), 0.47)
        self._box("bath-tub-basin", (tub_x-0.020, tub_y, z0 + tsz*0.78), (tub_len*0.76, tub_depth*0.76, 0.08), 0.18)
        self._box("bath-tub-rim-west", (tub_x-tub_len*0.43, tub_y, z0+tsz*0.96), (0.08, tub_depth, 0.055), 0.63)
        self._box("bath-tub-rim-east", (tub_x+tub_len*0.43, tub_y, z0+tsz*0.96), (0.08, tub_depth, 0.055), 0.63)
        self._box("bath-tub-rim-south", (tub_x, tub_y-tub_depth*0.46, z0+tsz*0.96), (tub_len*0.82, 0.07, 0.055), 0.63)
        self._box("bath-tub-rim-north", (tub_x, tub_y+tub_depth*0.46, z0+tsz*0.96), (tub_len*0.82, 0.07, 0.055), 0.63)
        self._box("bath-tub-spout", (tub_x+tub_len*0.30, tub_y-tub_depth*0.43, z0+0.70), (0.10, 0.08, 0.05), 0.57)
        self._box("bath-tub-control", (tub_x+tub_len*0.18, tub_y-tub_depth*0.41, z0+0.82), (0.045, 0.10, 0.10), 0.55)
        self._box("bath-tub-curtain-rod", (tub_x, tub_y-tub_depth*0.52, z0+2.02), (tub_len+0.10, 0.035, 0.035), 0.52)

        toilet = bath_objs["bath_toilet"]; _qx,_qy,_ = toilet["center"]; qsx,qsy,qsz = toilet["size"]
        toilet_depth = max(qsx, 0.70)
        toilet_width = max(qsy, 0.58)
        qx = bx1 - toilet_depth * 0.50 - 0.14
        qy = by0 + toilet_width * 0.60 + 0.22
        self.bath_toilet_blocker = (
            qx - toilet_depth * 0.50, qy - toilet_width * 0.50,
            qx + toilet_depth * 0.50, qy + toilet_width * 0.50,
        )
        self._box("bath-toilet-pedestal", (qx-0.02, qy, z0+0.19), (0.38, toilet_width*0.62, 0.38), 0.53)
        self._box("bath-toilet-bowl", (qx-0.10, qy, z0+0.42), (0.24, toilet_width, 0.24), 0.61)
        self._box("bath-toilet-seat", (qx-0.16, qy, z0+0.55), (0.045, toilet_width*0.92, 0.20), 0.30)
        self._box("bath-toilet-tank", (qx+0.12, qy, z0+0.58), (0.24, toilet_width*0.90, 0.55), 0.57)
        self._box("bath-toilet-tank-lid", (qx+0.12, qy, z0+0.875), (0.28, toilet_width*0.96, 0.045), 0.65)
        self._box("bath-toilet-flush", (qx+0.21, qy+toilet_width*0.18, z0+0.73), (0.045, 0.045, 0.045), 0.62)

        vanity = bath_objs["bath_vanity"]; vx,vy,_ = vanity["center"]; vsx,vsy,vsz = vanity["size"]
        self.bath_vanity_blocker = (vx-vsx*0.50, vy-vsy*0.50, vx+vsx*0.50, vy+vsy*0.50)
        self._box("bath-vanity-cabinet", (vx, vy, z0+vsz*0.45), (vsx, vsy, vsz*0.90), 0.24)
        self._box("bath-vanity-door-left", (vx-vsx*0.24, vy+vsy*0.505, z0+vsz*0.42), (vsx*0.43, 0.025, vsz*0.68), 0.33)
        self._box("bath-vanity-door-right", (vx+vsx*0.24, vy+vsy*0.505, z0+vsz*0.42), (vsx*0.43, 0.025, vsz*0.68), 0.33)
        self._box("bath-vanity-counter", (vx, vy, z0+vsz+0.035), (vsx+0.08, vsy+0.05, 0.07), 0.61)
        self._box("bath-sink-basin", (vx, vy+0.035, z0+vsz+0.065), (vsx*0.58, vsy*0.56, 0.035), 0.20)
        self._box("bath-faucet-neck", (vx, vy-0.08, z0+vsz+0.18), (0.045, 0.045, 0.20), 0.60)
        self._box("bath-faucet-spout", (vx, vy-0.01, z0+vsz+0.25), (0.045, 0.15, 0.045), 0.60)
        self._box("bath-faucet-handle-l", (vx-0.10, vy-0.08, z0+vsz+0.13), (0.055,0.055,0.075), 0.58)
        self._box("bath-faucet-handle-r", (vx+0.10, vy-0.08, z0+vsz+0.13), (0.055,0.055,0.075), 0.58)

        # Ceiling fixture and small towel bar give household scale without adding UI clutter.
        self._box("bath-ceiling-light", (bcx, bcy, z0+self.ceiling_h-0.045), (0.34,0.34,0.08), 0.68)
        self._box("bath-towel-bar", (10.20, by1-0.035, z0+1.12), (0.58,0.035,0.035), 0.56)
        self._box("bath-towel", (10.20, by1-0.055, z0+0.88), (0.48,0.035,0.48), 0.42)

        # Pass 89: no extra threshold trim here.  The hall-side and room-side casing
        # already define these openings; a third decorative layer visibly stacked at
        # the same threshold and made the doorway read as overlapping geometry.

        # Bathroom doorway intentionally has no door leaf; casing remains for architectural finish.
        # Room-side casing from the same accepted architectural dimensions as the hall.
        bcw=float(self.arch["assemblies"]["door_casing_width"]); bcd=float(self.arch["assemblies"]["door_casing_depth"])
        self._box("bath-room-casing-s", (bx0+0.018, bpy-bpw/2-bcw/2, z0+bph/2), (bcd,bcw,bph), 0.56)
        self._box("bath-room-casing-n", (bx0+0.018, bpy+bpw/2+bcw/2, z0+bph/2), (bcd,bcw,bph), 0.56)
        self._box("bath-room-casing-top", (bx0+0.018, bpy, z0+bph+bcw/2), (bcd,bpw+2*bcw,bcw), 0.56)

        # Architectural trim uses the accepted casing/baseboard dimensions.
        trim = float(self.arch["assemblies"]["door_casing_width"])
        trim_depth = max(0.035, float(self.arch["assemblies"]["door_casing_depth"]) * 2.0)
        self._box("master-portal-trim-south", (x1 - trim_depth/2, py - pw/2 - trim/2, z0 + ph/2), (trim_depth, trim, ph), 0.50)
        self._box("master-portal-trim-north", (x1 - trim_depth/2, py + pw/2 + trim/2, z0 + ph/2), (trim_depth, trim, ph), 0.50)
        self._box("master-portal-trim-top", (x1 - trim_depth/2, py, z0 + ph + trim/2), (trim_depth, pw + 2*trim, trim), 0.50)

        # Baseboards make the room read as an interior rather than a gray collision shell.
        bb = float(self.arch["assemblies"]["baseboard_height"])
        bd = 0.035
        self._box("baseboard-north", (cx, y1-0.025, z0+bb/2), (w, bd, bb), 0.48)
        self._box("baseboard-south-left", ((x0+sw_l)/2, y0+0.025, z0+bb/2), (sw_l-x0, bd, bb), 0.48)
        self._box("baseboard-south-right", ((sw_r+x1)/2, y0+0.025, z0+bb/2), (x1-sw_r, bd, bb), 0.48)
        self._box("baseboard-west-south", (x0+0.025, (y0+ww_lo)/2, z0+bb/2), (bd, ww_lo-y0, bb), 0.48)
        self._box("baseboard-west-north", (x0+0.025, (ww_hi+y1)/2, z0+bb/2), (bd, y1-ww_hi, bb), 0.48)
        self._box("baseboard-east-south", (x1-0.025, (y0+(py-pw/2))/2, z0+bb/2), (bd, (py-pw/2)-y0, bb), 0.48)
        self._box("baseboard-east-north", (x1-0.025, ((py+pw/2)+y1)/2, z0+bb/2), (bd, y1-(py+pw/2), bb), 0.48)

        # Simple crown molding and wall details establish household scale without adding HUD clutter.
        crown_h = 0.075
        crown_d = 0.055
        self._box("crown-north", (cx, y1-0.030, z0+self.ceiling_h-crown_h/2), (w, crown_d, crown_h), 0.45)
        self._box("crown-south", (cx, y0+0.030, z0+self.ceiling_h-crown_h/2), (w, crown_d, crown_h), 0.45)
        self._box("crown-west", (x0+0.030, cy, z0+self.ceiling_h-crown_h/2), (crown_d, d, crown_h), 0.45)
        self._box("crown-east-south", (x1-0.030, (y0+(py-pw/2))/2, z0+self.ceiling_h-crown_h/2), (crown_d, (py-pw/2)-y0, crown_h), 0.45)
        self._box("crown-east-north", (x1-0.030, ((py+pw/2)+y1)/2, z0+self.ceiling_h-crown_h/2), (crown_d, y1-(py+pw/2), crown_h), 0.45)
        # Two restrained wall frames and an electrical switch make the room read as occupied.
        self._box("wall-frame-north-outer", (3.55, y1-0.045, z0+1.55), (0.62, 0.045, 0.48), 0.24)
        self._box("wall-frame-north-inner", (3.55, y1-0.070, z0+1.55), (0.50, 0.025, 0.36), 0.08)
        self._box("wall-switch", (x1-0.045, py-0.64, z0+1.18), (0.035, 0.10, 0.16), 0.56)
        self._box("ceiling-fixture-base", (cx, cy, z0+self.ceiling_h-0.055), (0.34, 0.34, 0.08), 0.42)
        self._box("ceiling-fixture-globe", (cx, cy, z0+self.ceiling_h-0.15), (0.24, 0.24, 0.14), 0.56)

        # Recessed south window: dark glass, four frame rails, sill and center muntin.
        gy = y0 + 0.030
        self._black_window_glass("south-window-glass", (sw_cx, gy, z0+sw_sill+sw_h/2), (sw_w-0.10, 0.022, sw_h-0.10))
        for xx in (sw_l+0.035, sw_r-0.035):
            self._box("south-window-frame-v", (xx, y0+0.055, z0+sw_sill+sw_h/2), (0.07, 0.07, sw_h+0.10), 0.55)
        for zz in (z0+sw_sill+0.035, z0+sw_sill+sw_h-0.035):
            self._box("south-window-frame-h", (sw_cx, y0+0.055, zz), (sw_w+0.10, 0.07, 0.07), 0.55)
        self._box("south-window-muntin-v", (sw_cx, y0+0.060, z0+sw_sill+sw_h/2), (0.035, 0.055, sw_h-0.05), 0.44)
        self._box("south-window-muntin-h", (sw_cx, y0+0.060, z0+sw_sill+sw_h/2), (sw_w-0.05, 0.055, 0.035), 0.44)
        self._box("south-window-sill", (sw_cx, y0+0.10, z0+sw_sill-0.025), (sw_w+0.18, 0.18, 0.055), 0.50)

        # Recessed west window, matching the same household construction.
        gx = x0 + 0.030
        self._black_window_glass("west-window-glass", (gx, ww_cy, z0+ww_sill+ww_h/2), (0.022, ww_w-0.10, ww_h-0.10))
        for yy in (ww_lo+0.035, ww_hi-0.035):
            self._box("west-window-frame-v", (x0+0.055, yy, z0+ww_sill+ww_h/2), (0.07, 0.07, ww_h+0.10), 0.55)
        for zz in (z0+ww_sill+0.035, z0+ww_sill+ww_h-0.035):
            self._box("west-window-frame-h", (x0+0.055, ww_cy, zz), (0.07, ww_w+0.10, 0.07), 0.55)
        self._box("west-window-muntin-v", (x0+0.060, ww_cy, z0+ww_sill+ww_h/2), (0.055, 0.035, ww_h-0.05), 0.44)
        self._box("west-window-muntin-h", (x0+0.060, ww_cy, z0+ww_sill+ww_h/2), (0.055, ww_w-0.05, 0.035), 0.44)
        self._box("west-window-sill", (x0+0.10, ww_cy, z0+ww_sill-0.025), (0.18, ww_w+0.18, 0.055), 0.50)

        # The Master Bedroom door is now the only physical interior door.
        # It is grouped under one pivot so Task 06 can close it cleanly without moving unrelated geometry.
        self.master_door_root = self.scene_root.attachNewNode("master-bedroom-door")
        self.master_door_hinge = Vec3(x1 + 0.02, py - pw/2.0, z0 + 1.025)
        self.master_door_root.setPos(self.master_door_hinge)
        self.door = self._box("master-door-leaf", (0.0, pw/2.0, 0.0), (0.08, pw, 2.05), 0.24, parent=self.master_door_root)
        for yy in (pw*0.27, pw*0.73):
            for zz in (-0.50, 0.50):
                self._box("master-door-panel", (-0.052, yy, zz), (0.022, pw*0.30, 0.40), 0.18, parent=self.master_door_root)
        self._box("master-door-rail", (-0.054, pw/2.0, 0.0), (0.026, 0.055, 1.84), 0.34, parent=self.master_door_root)
        self._box("door-handle", (-0.074, pw*0.78, 0.005), (0.045, 0.095, 0.055), 0.62, parent=self.master_door_root)
        self._set_master_bedroom_door_closed(False)

        # Furniture from accepted Pass 09 world-space composition.
        by_id = {o["id"]: o for o in self.master["objects"]}
        bed = by_id["bed"]
        bx, by = bed["center"][0], bed["center"][1]
        self._box("bed-frame", (bx, by, z0 + 0.18), (1.63, 2.09, 0.28), 0.18)
        for lx in (-0.72, 0.72):
            for ly in (-0.93, 0.93):
                self._box("bed-leg", (bx+lx, by+ly, z0+0.11), (0.09, 0.09, 0.22), 0.14)
        self._box("mattress", (bx, by, z0 + 0.43), (1.54, 2.00, 0.24), 0.48)
        self._box("blanket", (bx, by+0.25, z0 + 0.575), (1.48, 1.40, 0.07), 0.30)
        self._box("pillow-left", (bx-0.38, by+0.74, z0+0.60), (0.60, 0.34, 0.13), 0.58)
        self._box("pillow-right", (bx+0.38, by+0.74, z0+0.60), (0.60, 0.34, 0.13), 0.58)
        self._box("headboard", (bx, 4.47, z0 + 0.69), (1.63, 0.10, 1.18), 0.22)
        self._box("headboard-inset", (bx, 4.405, z0+0.78), (1.30, 0.025, 0.62), 0.16)

        chair = by_id["chair"]
        c = chair["center"]
        self._box("chair-seat", (c[0], c[1], z0 + 0.39), (0.70, 0.58, 0.16), 0.28)
        self._box("chair-cushion", (c[0], c[1]-0.02, z0+0.50), (0.62, 0.50, 0.10), 0.38)
        self._box("chair-back", (c[0] - 0.29, c[1], z0 + 0.74), (0.13, 0.62, 0.72), 0.29)
        for yy in (-0.25, 0.25):
            self._box("chair-arm", (c[0], c[1]+yy, z0+0.61), (0.58, 0.09, 0.12), 0.23)
        for xx in (-0.27, 0.27):
            for yy in (-0.22, 0.22):
                self._box("chair-leg", (c[0]+xx, c[1]+yy, z0+0.20), (0.07, 0.07, 0.32), 0.15)
        self.chair_pos = Vec3(c[0], c[1], z0 + 0.48)

        cab = by_id["tv_cabinet"]
        cc = cab["center"]
        self._box("tv-cabinet", (cc[0], cc[1], z0 + 0.33), (0.55, 0.82, 0.66), 0.18)
        self._box("tv-cabinet-top", (cc[0]-0.01, cc[1], z0+0.68), (0.60, 0.86, 0.06), 0.28)
        self._box("tv-cabinet-front-upper", (cc[0]-0.285, cc[1], z0+0.47), (0.025, 0.66, 0.18), 0.27)
        self._box("tv-cabinet-front-lower", (cc[0]-0.285, cc[1], z0+0.22), (0.025, 0.66, 0.18), 0.24)
        self._box("tv-cabinet-knob-upper", (cc[0]-0.31, cc[1]-0.22, z0+0.47), (0.035, 0.045, 0.045), 0.56)
        self._box("tv-cabinet-knob-lower", (cc[0]-0.31, cc[1]-0.22, z0+0.22), (0.035, 0.045, 0.045), 0.56)
        tv = by_id["analog_tv"]
        tc = tv["center"]
        self._box("tv-body", (tc[0], tc[1], z0 + 0.89), (0.50, 0.51, 0.46), 0.14)
        self._box("tv-bezel", (tc[0]-0.258, tc[1], z0+0.90), (0.035, 0.43, 0.36), 0.25)
        self.tv_screen = self._box("tv-screen", (tc[0] - 0.280, tc[1]-0.025, z0 + 0.90), (0.020, 0.34, 0.27), 0.48)
        self._box("tv-control-strip", (tc[0]-0.282, tc[1]+0.195, z0+0.90), (0.022, 0.055, 0.28), 0.20)
        self._box("tv-knob-top", (tc[0]-0.298, tc[1]+0.195, z0+1.00), (0.025, 0.035, 0.055), 0.62)
        self._box("tv-knob-bottom", (tc[0]-0.298, tc[1]+0.195, z0+0.84), (0.025, 0.035, 0.055), 0.62)
        self._box("tv-antenna-left", (tc[0]+0.00, tc[1]-0.11, z0+1.22), (0.025, 0.025, 0.34), 0.42)
        self._box("tv-antenna-right", (tc[0]+0.00, tc[1]+0.11, z0+1.22), (0.025, 0.025, 0.34), 0.42)
        self.tv_pos = Vec3(tc[0], tc[1], z0 + 0.90)
        self.tv_texture = Texture("crt-signal")
        self.tv_texture.setKeepRamImage(True)
        self.tv_screen.setTexture(self.tv_texture, 1)
        self.tv_screen.setColor(1, 1, 1, 1)
        self.tv_screen.setLightOff(1)
        self._render_tv_frame(force=True)

        # Readable grayscale only. Hall is deliberately darker than the starting room.
        amb = AmbientLight("room-ambient")
        amb.setColor(Vec4(0.32, 0.32, 0.35, 1))
        self.render.setLight(self.render.attachNewNode(amb))
        key = DirectionalLight("room-key")
        key.setColor(Vec4(0.50, 0.50, 0.54, 1))
        key_np = self.render.attachNewNode(key)
        key_np.setHpr(-35, -58, 0)
        self.render.setLight(key_np)


    def _build_first_task_object(self):
        """Place the first mundane task object on the accepted bathroom vanity."""
        self.task_note_root = self.scene_root.attachNewNode("task-bathroom-note")
        self.task_note_pos = Vec3(9.25, 0.73, self.floor_z + 0.665)
        # Thin paper sheet with a slightly brighter edge. It remains physical world
        # geometry instead of an objective marker or floating HUD icon.
        self._box("task-note-paper", self.task_note_pos, (0.22, 0.15, 0.012), 0.58, parent=self.task_note_root)
        self._box("task-note-fold", (self.task_note_pos.x + 0.055, self.task_note_pos.y, self.task_note_pos.z + 0.008), (0.045, 0.15, 0.008), 0.38, parent=self.task_note_root)

    def _build_note_interception_arm(self):
        """Build Pass 84's continuous hose-like note interception arm.

        The unseen body stays outside Floor 2.  Only the initial exterior-wall
        penetration may cross solid architecture.  From that entry onward the
        centreline is validated against the same authored rooms/portals used by
        player movement.  The visible arm is one procedural tube mesh, not a chain
        of ellipsoids, so bends read as a single growing limb.
        """
        self.note_intercept_arm_root = self.scene_root.attachNewNode("note-interception-arm")
        self.note_intercept_arm_root.setLightOff(1)
        self.note_intercept_arm_root.setFogOff(1)
        self.note_intercept_arm_root.setTransparency(TransparencyAttrib.MAlpha)
        self.note_intercept_arm_root.setDepthWrite(True)
        self.note_intercept_arm_root.hide()

        z = self.floor_z
        self.note_intercept_body_origin = Vec3(12.95, 6.55, z + 1.48)
        self.note_intercept_entry = Vec3(11.28, 6.55, z + 1.46)
        self.note_intercept_route = [
            self.note_intercept_body_origin,
            self.note_intercept_entry,
            Vec3(9.28, 6.55, z + 1.43),
            Vec3(9.10, 7.18, z + 1.40),
            Vec3(8.58, 7.50, z + 1.37),
            Vec3(7.55, 7.50, z + 1.34),
            Vec3(7.42, 5.25, z + 1.42),
            Vec3(7.45, 2.25, z + 1.36),
            Vec3(8.58, 1.70, z + 1.31),
            Vec3(9.02, 1.50, z + 1.28),
            Vec3(9.00, 0.94, z + 1.34),
        ]

        # Build a rounded centreline.  Each interior corner is trimmed and bridged
        # with a quadratic curve, producing hose-like bends without overshooting the
        # narrow corridor/doorway footprint.  Any rounded sample that leaves valid
        # space is rejected locally and the authored corner point is retained.
        route=self.note_intercept_route
        samples=[Vec3(route[0])]
        def append_linear(a,b,step=0.12):
            dist=max(0.001,(b-a).length()); count=max(1,int(math.ceil(dist/step)))
            for j in range(1,count+1): samples.append(Vec3(a+(b-a)*(j/count)))
        append_linear(route[0],route[1])  # only intentional wall penetration
        cursor=Vec3(route[1])
        for i in range(2,len(route)-1):
            corner=Vec3(route[i]); prev=Vec3(route[i-1]); nxt=Vec3(route[i+1])
            vin=corner-prev; vout=nxt-corner
            lin=max(0.001,vin.length()); lout=max(0.001,vout.length())
            din=vin/lin; dout=vout/lout
            trim=min(0.34,lin*0.28,lout*0.28)
            approach=corner-din*trim; depart=corner+dout*trim
            append_linear(cursor,approach)
            curve=[]; valid_curve=True
            for j in range(1,9):
                t=j/8.0; omt=1.0-t
                q=approach*(omt*omt)+corner*(2.0*omt*t)+depart*(t*t)
                if not self._note_arm_xy_clear(q.x,q.y,q.z): valid_curve=False; break
                curve.append(Vec3(q))
            if valid_curve:
                samples.extend(curve); cursor=Vec3(depart)
            else:
                append_linear(approach,corner); cursor=Vec3(corner)
        append_linear(cursor,route[-1])
        # Gentle Z-only organic drift; XY remains collision-authoritative.
        for i,q in enumerate(samples[1:],1):
            if q.x < self.note_intercept_entry.x - 0.03:
                q.z += 0.020*math.sin(i*0.23)
        self.note_intercept_samples=samples

        self.note_intercept_tube_np=self.note_intercept_arm_root.attachNewNode("note-arm-continuous-tube")
        self.note_intercept_tube_np.setTwoSided(True)
        self.note_intercept_tube_sides=12
        self.note_intercept_skin=(0.018,0.019,0.020,0.985)

        self.note_intercept_hand_root=self.note_intercept_arm_root.attachNewNode("note-arm-hand")
        skin=self.note_intercept_skin
        self._alt_ellipsoid("note-arm-palm",(0,0,0),(0.13,0.17,0.10),skin,self.note_intercept_hand_root)
        for i,x in enumerate((-0.105,-0.052,0.0,0.052,0.105)):
            finger=self._alt_ellipsoid(f"note-arm-finger-{i}",(x,0.17,-0.005),(0.022,0.16+0.018*(2-abs(i-2)),0.024),skin,self.note_intercept_hand_root)
            finger.setP(-8.0 + i*3.5)
        self.note_intercept_hand_root.hide()

        self.note_read_overlay=DirectFrame(parent=self.aspect2d,frameColor=(0.57,0.56,0.52,0.98),frameSize=(-0.48,0.48,-0.24,0.24),pos=(0,0,-0.28))
        DirectLabel(parent=self.note_read_overlay,text="IT CANNOT COME INSIDE.\nTHAT DOES NOT MEAN\nYOU ARE SAFE.",scale=0.052,pos=(0,0,0.025),text_align=TextNode.ACenter,text_fg=(0.035,0.035,0.035,1),frameColor=(0,0,0,0))
        self.note_read_overlay.hide()
        self.note_cover_fingers=[]
        for i in range(5):
            f=DirectFrame(parent=self.note_read_overlay,frameColor=(0.015,0.015,0.016,0.97),frameSize=(-0.045,0.045,-0.28,0.28),pos=(0.78+i*0.085,0,-0.01+(i-2)*0.012))
            f.setR((-8,-4,1,5,9)[i]); self.note_cover_fingers.append(f)

        self.note_intercept_route_valid=True
        for q in self.note_intercept_samples:
            if q.x >= self.note_intercept_entry.x - 0.02 and abs(q.y-self.note_intercept_entry.y) < 0.12:
                continue
            if not self._note_arm_xy_clear(q.x,q.y,q.z):
                self.note_intercept_route_valid=False; break

    def _note_arm_xy_clear(self, x: float, y: float, z: float) -> bool:
        r=0.055
        rooms=(self.room_rect,self.hall_rect,self.bath_rect,self.stair_rect,self.bed2_rect,self.bed3_rect,self.bed4_rect)
        if any(self._in_rect(x,y,rect,r) for rect in rooms):
            in_space=True
        else:
            in_space=False
            for portal in (self.master_portal,self.bath_portal,self.stair_portal,self.bed2_portal,self.bed3_portal,self.bed4_portal):
                px,py,_=portal["center"]; half=float(portal["width"])/2.0
                if portal["axis"]=="x":
                    if px-0.22 <= x <= px+0.22 and py-half+r <= y <= py+half-r: in_space=True; break
                else:
                    if py-0.22 <= y <= py+0.22 and px-half+r <= x <= px+half-r: in_space=True; break
        if not in_space: return False
        if z >= self.floor_z + 1.10: return True
        blockers=[self.bath_tub_blocker,self.bath_toilet_blocker,self.bath_vanity_blocker]
        for bx0,by0,bx1,by1 in blockers:
            if bx0-r <= x <= bx1+r and by0-r <= y <= by1+r: return False
        return True

    def _rebuild_note_interception_tube(self, progress: float):
        """Rebuild one connected tube for the visible prefix of the arm centreline."""
        if hasattr(self,"note_intercept_tube_np") and not self.note_intercept_tube_np.isEmpty():
            self.note_intercept_tube_np.removeNode()
        self.note_intercept_tube_np=self.note_intercept_arm_root.attachNewNode("note-arm-continuous-tube")
        self.note_intercept_tube_np.setTwoSided(True)
        progress=max(0.0,min(1.0,float(progress)))
        pts=self.note_intercept_samples
        if progress <= 0.0 or len(pts)<2: return
        exact=progress*(len(pts)-1)
        full=min(len(pts)-2,int(exact)); frac=exact-full
        visible=[Vec3(q) for q in pts[:full+1]]
        visible.append(pts[full] + (pts[full+1]-pts[full])*frac)
        if len(visible)<2: return

        fmt=GeomVertexFormat.getV3n3c4()
        vdata=GeomVertexData("note-arm-tube",fmt,Geom.UHDynamic)
        vw=GeomVertexWriter(vdata,"vertex"); nw=GeomVertexWriter(vdata,"normal"); cw=GeomVertexWriter(vdata,"color")
        sides=self.note_intercept_tube_sides
        skin=self.note_intercept_skin
        rings=[]
        up=Vec3(0,0,1)
        for i,p in enumerate(visible):
            if i==0: tangent=visible[1]-p
            elif i==len(visible)-1: tangent=p-visible[i-1]
            else: tangent=visible[i+1]-visible[i-1]
            if tangent.lengthSquared()<1e-8: tangent=Vec3(0,1,0)
            tangent.normalize()
            side=tangent.cross(up)
            if side.lengthSquared()<1e-6: side=Vec3(1,0,0)
            else: side.normalize()
            bino=side.cross(tangent); bino.normalize()
            along=i/max(1,len(pts)-1)
            taper=1.0-0.34*along
            base_radius=0.056*taper
            twist=0.20*math.sin(along*8.5 + self.note_intercept_elapsed*0.18)
            ring=[]
            for k in range(sides):
                ang=(math.tau*k/sides)+twist
                radial=side*math.cos(ang)+bino*math.sin(ang)
                radius=base_radius*(1.0+0.035*math.sin(along*11.0+k*0.45))
                pos=p+radial*radius
                vw.addData3(pos); nw.addData3(radial); cw.addData4(*skin)
                ring.append(i*sides+k)
            rings.append(ring)
        tris=GeomTriangles(Geom.UHDynamic)
        for r in range(len(rings)-1):
            a=rings[r]; b=rings[r+1]
            for k in range(sides):
                kn=(k+1)%sides
                tris.addVertices(a[k],b[k],b[kn]); tris.addVertices(a[k],b[kn],a[kn])
        # Cap the growing tip so it reads as one solid hose before the hand appears.
        tip_index=vdata.getNumRows(); tip=visible[-1]
        tangent=visible[-1]-visible[-2]; tangent.normalize()
        vw.addData3(tip); nw.addData3(tangent); cw.addData4(*skin)
        last=rings[-1]
        for k in range(sides): tris.addVertices(last[k],tip_index,last[(k+1)%sides])
        tris.closePrimitive()
        geom=Geom(vdata); geom.addPrimitive(tris)
        node=GeomNode("note-arm-tube-geom"); node.addGeom(geom)
        self.note_intercept_tube_np=self.note_intercept_arm_root.attachNewNode(node)
        self.note_intercept_tube_np.setTwoSided(True)

    def _pose_note_interception_arm(self, progress: float):
        progress=max(0.0,min(1.0,float(progress)))
        self.note_intercept_arm_progress=progress
        if progress <= 0.0:
            self.note_intercept_arm_root.hide()
            self.note_intercept_hand_root.hide()
            self._rebuild_note_interception_tube(0.0)
            return
        self.note_intercept_arm_root.show()
        self._rebuild_note_interception_tube(progress)
        if progress > 0.92:
            exact=progress*(len(self.note_intercept_samples)-1)
            full=min(len(self.note_intercept_samples)-2,int(exact)); frac=exact-full
            tip=self.note_intercept_samples[full]+(self.note_intercept_samples[full+1]-self.note_intercept_samples[full])*frac
            self.note_intercept_hand_root.show(); self.note_intercept_hand_root.setPos(tip)
            self.note_intercept_hand_root.lookAt(self.camera.getPos(self.render))
            self.note_intercept_hand_root.setR(7.0*math.sin(self.note_intercept_elapsed*0.45))
        else:
            self.note_intercept_hand_root.hide()

    def _start_note_interception(self):
        if self.note_intercept_active:
            return
        self.note_intercept_active=True
        self.note_intercept_elapsed=0.0
        self.note_intercept_arm_progress=0.0
        self.note_read_overlay.show()
        for i,f in enumerate(self.note_cover_fingers):
            f.setX(0.78+i*0.085)
        self._pose_note_interception_arm(0.0)
        # Hide all ordinary Alternate manifestations during this event. The body is
        # not teleported into the house; the arm's origin remains outside bounds.
        self._hide_alternate(hard=True)
        self.alt_hidden_timer=max(self.alt_hidden_timer,10.0)
        self.status["text"]=""
        self.message_timer=0.0

    def _update_note_interception(self, dt: float):
        if not self.note_intercept_active:
            return
        self.note_intercept_elapsed += dt
        t=self.note_intercept_elapsed
        # Arm begins after the player has had a quiet moment to read.
        grow=max(0.0,min(1.0,(t-1.35)/5.25))
        grow=grow*grow*(3.0-2.0*grow)
        self._pose_note_interception_arm(grow)

        # After ~2.8 seconds the hand's shadow slowly crosses the note. The player
        # still sees the room around the small card while the real arm keeps growing.
        cover=max(0.0,min(1.0,(t-2.80)/1.55))
        cover=cover*cover*(3.0-2.0*cover)
        for i,f in enumerate(self.note_cover_fingers):
            f.setX((0.78+i*0.085)*(1.0-cover)+(0.15+(i-2)*0.078)*cover)
        if t >= 4.55:
            self.note_read_overlay.hide()

        if t >= self.note_intercept_duration:
            self.note_intercept_active=False
            self.note_read_overlay.hide()
            self._pose_note_interception_arm(0.0)
            self.tv_task["state"]="collected"
            self._emit_alternate_voice_event(
                "note_interception_complete",
                reset_cycles=int(self.entity_memory.get("completed_reset_cycles", 0)),
            )
            self.status["text"]="The note is gone. Find the broadcast."
            self.message_timer=2.6
            self._update_prompt()

    def _reset_note_interception(self):
        self.note_intercept_active=False
        self.note_intercept_elapsed=0.0
        if hasattr(self,"note_read_overlay"): self.note_read_overlay.hide()
        if hasattr(self,"note_intercept_arm_root"): self._pose_note_interception_arm(0.0)

    def _build_second_task_object(self):
        """Place a mundane crooked frame on the Upper Hall south wall."""
        self.task_frame_pos = Vec3(7.25, 0.57, self.floor_z + 1.48)
        self.task_frame_root = self.scene_root.attachNewNode("task-upper-hall-frame")
        self.task_frame_root.setPos(self.task_frame_pos)
        self.task_frame_outer = self._box("task-frame-outer", (0.0, 0.0, 0.0), (0.56, 0.035, 0.44), 0.20, parent=self.task_frame_root)
        self.task_frame_inner = self._box("task-frame-inner", (0.0, 0.022, 0.0), (0.42, 0.018, 0.30), 0.46, parent=self.task_frame_root)
        self._set_task_frame_crooked(True)

    def _set_task_frame_crooked(self, crooked: bool):
        self.task_frame_root.setR(6.0 if crooked else 0.0)

    def _build_third_task_object(self):
        """Prepare the first isolation task on the existing south bedroom window."""
        x0, y0, x1, y1 = self.room_rect
        self.task_window_pos = Vec3(2.25, y0 + 0.18, self.floor_z + 1.42)
        self.task_window_cover_root = self.scene_root.attachNewNode("task-master-south-window-cover")
        # The uncovered pane remains black exterior glass. Task 03 adds actual
        # rough boards across it so "dark outside" and "covered window" are
        # visually distinct states.
        board_y = y0 + 0.060
        for i, zoff in enumerate((-0.38, -0.12, 0.14, 0.40)):
            board = self._box(
                f"task-window-board-{i+1}",
                (2.25, board_y, self.floor_z + 1.42 + zoff),
                (1.36, 0.050, 0.18),
                0.22 + i * 0.015,
                parent=self.task_window_cover_root,
            )
            board.setR((-2.0, 1.0, -1.5, 2.5)[i])
        self.task_window_cover_root.hide()

    def _set_task_window_covered(self, covered: bool):
        if covered:
            self.task_window_cover_root.show()
        else:
            self.task_window_cover_root.hide()
        self._set_window_boarded("w_f2_master_s", covered)


    def _build_fourth_task_object(self):
        """Add an ordinary bathroom mirror and a hidden cloth for Task 04."""
        # The vanity sits at 9.25, 0.73. Put the mirror on the north-facing wall
        # above it so it reads as normal bathroom furnishing before the task.
        self.task_mirror_pos = Vec3(9.25, 0.535, self.floor_z + 1.55)
        self.task_mirror_root = self.scene_root.attachNewNode("task-bathroom-mirror")
        self._box("task-mirror-frame", self.task_mirror_pos, (0.82, 0.035, 0.72), 0.15, parent=self.task_mirror_root)
        self._box("task-mirror-glass", (self.task_mirror_pos.x, self.task_mirror_pos.y + 0.022, self.task_mirror_pos.z), (0.68, 0.018, 0.58), 0.52, parent=self.task_mirror_root)
        self.task_mirror_cover_root = self.scene_root.attachNewNode("task-bathroom-mirror-cover")
        self._box("task-mirror-cloth", (self.task_mirror_pos.x, self.task_mirror_pos.y + 0.048, self.task_mirror_pos.z), (0.76, 0.018, 0.66), 0.055, parent=self.task_mirror_cover_root)
        self.task_mirror_cover_root.hide()

    def _set_task_mirror_covered(self, covered: bool):
        if covered:
            self.task_mirror_cover_root.show()
        else:
            self.task_mirror_cover_root.hide()


    def _build_fifth_task_object(self):
        """Add a restrained old wall telephone in the Upper Hall for Task 05."""
        # Pass 41: mount the phone to the west hall wall instead of floating at corridor center.
        self.task_phone_pos = Vec3(self.hall_rect[0] + 0.075, 4.58, self.floor_z + 1.36)
        self.task_phone_root = self.scene_root.attachNewNode("task-upper-hall-wall-phone")
        self.task_phone_root.setPos(self.task_phone_pos)
        self.task_phone_root.setH(90)
        self._box("task-phone-backplate", (0.0, 0.0, 0.0), (0.22, 0.035, 0.32), 0.14, parent=self.task_phone_root)
        self._box("task-phone-dial", (0.0, -0.023, -0.035), (0.11, 0.022, 0.11), 0.28, parent=self.task_phone_root)
        self.task_phone_handset_root = self.task_phone_root.attachNewNode("task-phone-handset-root")
        self.task_phone_handset = self._box("task-phone-handset", (0.0, -0.040, 0.105), (0.14, 0.050, 0.045), 0.30, parent=self.task_phone_handset_root)
        self._box("task-phone-handset-left", (-0.092, -0.040, 0.105), (0.055, 0.060, 0.085), 0.32, parent=self.task_phone_handset_root)
        self._box("task-phone-handset-right", (0.092, -0.040, 0.105), (0.055, 0.060, 0.085), 0.32, parent=self.task_phone_handset_root)
        self.task_phone_cord = self._box("task-phone-cord", (0.0, -0.030, -0.205), (0.012, 0.012, 0.17), 0.06, parent=self.task_phone_root)
        self._set_task_phone_disconnected(False)

    def _set_task_phone_disconnected(self, disconnected: bool):
        if disconnected:
            self.task_phone_handset_root.setPos(-0.13, -0.018, -0.20)
            self.task_phone_handset_root.setR(22)
            self.task_phone_cord.hide()
        else:
            self.task_phone_handset_root.setPos(0, 0, 0)
            self.task_phone_handset_root.setR(0)
            self.task_phone_cord.show()


    def _build_sixth_task_object(self):
        """Task 06 now closes the Master Bedroom door; no stair-door prop exists."""
        py = float(self.master_portal["center"][1])
        x1 = float(self.room_rect[2])
        self.task_bedroom_door_pos = Vec3(x1 - 0.30, py, self.floor_z + 1.02)
        self.basement_active=False
        self.basement_clue_found=False
        self.basement_loop_count=0
        if hasattr(self,"basement_clue_root"): self.basement_clue_root.show()
        self.attic_active=False
        self.attic_task.update({"state":"locked","pylon_loosened":False})
        if hasattr(self,"attic_pylon_root"):
            self.attic_pylon_root.setR(0)
        self._reset_attic_finale()

    def _set_master_bedroom_door_closed(self, closed: bool):
        if not hasattr(self, "master_door_root"):
            return
        # Door leaf is authored along local +Y when closed. Rotate 90 degrees into the bedroom when open.
        self.master_door_root.setH(0 if closed else 90)

    def _unlock_sixth_tv_task(self):
        if self.tv_task_06["state"] == "locked":
            self.tv_task_06["state"] = "unissued"

    def _issue_sixth_tv_task(self):
        if self.tv_task_06["state"] != "unissued": return
        self.tv_task_06["state"] = "active"
        self._set_task_broadcast("issue6")
        self.tv_frame_counter = 0; self.tv_refresh_accum = 999.0
        self._render_tv_frame(force=True)
        self.status["text"] = "The television issues another instruction."
        self.message_timer = 1.8

    def _close_sixth_task_bedroom_door(self):
        if self.tv_task_06["state"] != "active" or self.tv_task_06["bedroom_door_closed"]: return
        self.tv_task_06["bedroom_door_closed"] = True
        self.tv_task_06["state"] = "changed"
        self._set_master_bedroom_door_closed(True)
        self.status["text"] = "You close the bedroom door. Return to the television."
        self.message_timer = 2.4
        self._update_prompt()

    def _acknowledge_sixth_tv_task(self):
        if self.tv_task_06["state"] != "changed": return
        self.tv_task_06["state"] = "completed"
        self.tv_task_06["completion_count"] += 1
        self._preserve_completion_and_issue_next("complete6", lambda: self._issue_next_after_completion(6))
        self.status["text"] = "The television accepts the sixth task."
        self.message_timer = 1.8
        self._emit_alternate_voice_event(
            "floor1_unlocked",
            prior_shutdowns=int(self.entity_memory.get("observed_tv_shutdowns_total", 0)),
            reset_cycles=int(self.entity_memory.get("completed_reset_cycles", 0)),
        )

    def _unlock_fifth_tv_task(self):
        if self.tv_task_05["state"] == "locked":
            self.tv_task_05["state"] = "unissued"

    def _issue_fifth_tv_task(self):
        if self.tv_task_05["state"] != "unissued": return
        self.tv_task_05["state"] = "active"
        self._set_task_broadcast("issue5")
        self.tv_frame_counter = 0; self.tv_refresh_accum = 999.0
        self._render_tv_frame(force=True)
        self.status["text"] = "The television issues another instruction."
        self.message_timer = 1.8

    def _disconnect_fifth_task_phone(self):
        if self.tv_task_05["state"] != "active" or self.tv_task_05["phone_disconnected"]: return
        self.tv_task_05["phone_disconnected"] = True
        self.tv_task_05["state"] = "changed"
        self._set_task_phone_disconnected(True)
        self.status["text"] = "You disconnect the hall telephone. Return to the television."
        self.message_timer = 2.4
        self._update_prompt()

    def _acknowledge_fifth_tv_task(self):
        if self.tv_task_05["state"] != "changed": return
        self.tv_task_05["state"] = "completed"
        self.tv_task_05["completion_count"] += 1
        self._set_task_broadcast("complete5")
        self.tv_frame_counter = 0; self.tv_refresh_accum = 999.0
        self._render_tv_frame(force=True)
        self.status["text"] = "The television accepts the fifth task."
        self.message_timer = 1.8

    def _unlock_second_tv_task(self):
        if self.tv_task_02["state"] == "locked":
            self.tv_task_02["state"] = "unissued"

    def _issue_second_tv_task(self):
        if self.tv_task_02["state"] != "unissued":
            return
        self.tv_task_02["state"] = "active"
        self._set_task_broadcast("issue2")
        self.tv_frame_counter = 0
        self.tv_refresh_accum = 999.0
        self._render_tv_frame(force=True)
        self.status["text"] = "The television issues another instruction."
        self.message_timer = 1.8

    def _straighten_second_task_frame(self):
        if self.tv_task_02["state"] != "active" or self.tv_task_02["frame_straightened"]:
            return
        self.tv_task_02["frame_straightened"] = True
        self.tv_task_02["state"] = "changed"
        self._set_task_frame_crooked(False)
        self.status["text"] = "You straighten the frame. Return to the television."
        self.message_timer = 2.4
        self._update_prompt()

    def _acknowledge_second_tv_task(self):
        if self.tv_task_02["state"] != "changed":
            return
        self.tv_task_02["state"] = "completed"
        self.tv_task_02["completion_count"] += 1
        self._preserve_completion_and_issue_next("complete2", lambda: self._issue_next_after_completion(2))
        self.status["text"] = "The television accepts the second task."
        self.message_timer = 1.8

    def _unlock_third_tv_task(self):
        if self.tv_task_03["state"] == "locked":
            self.tv_task_03["state"] = "unissued"

    def _issue_third_tv_task(self):
        if self.tv_task_03["state"] != "unissued":
            return
        self.tv_task_03["state"] = "active"
        self._set_task_broadcast("issue3")
        self.tv_frame_counter = 0
        self.tv_refresh_accum = 999.0
        self._render_tv_frame(force=True)
        self.status["text"] = "The television issues another instruction."
        self.message_timer = 1.8

    def _cover_third_task_window(self):
        if self.tv_task_03["state"] != "active" or self.tv_task_03["window_covered"]:
            return
        self.tv_task_03["window_covered"] = True
        self.tv_task_03["state"] = "changed"
        self._set_task_window_covered(True)
        self.status["text"] = "You cover the south window. Return to the television."
        self.message_timer = 2.4
        self._update_prompt()

    def _acknowledge_third_tv_task(self):
        if self.tv_task_03["state"] != "changed":
            return
        self.tv_task_03["state"] = "completed"
        self.tv_task_03["completion_count"] += 1
        self._preserve_completion_and_issue_next("complete3", lambda: self._issue_next_after_completion(3))
        self.status["text"] = "The television accepts the third task."
        self.message_timer = 1.8


    def _unlock_fourth_tv_task(self):
        if self.tv_task_04["state"] == "locked":
            self.tv_task_04["state"] = "unissued"

    def _issue_fourth_tv_task(self):
        if self.tv_task_04["state"] != "unissued":
            return
        self.tv_task_04["state"] = "active"
        self._set_task_broadcast("issue4")
        self.tv_frame_counter = 0
        self.tv_refresh_accum = 999.0
        self._render_tv_frame(force=True)
        self.status["text"] = "The television issues another instruction."
        self.message_timer = 1.8

    def _cover_fourth_task_mirror(self):
        if self.tv_task_04["state"] != "active" or self.tv_task_04["mirror_covered"]:
            return
        self.tv_task_04["mirror_covered"] = True
        self.tv_task_04["state"] = "changed"
        self._set_task_mirror_covered(True)
        self.status["text"] = "You cover the bathroom mirror. Return to the television."
        self.message_timer = 2.4
        self._update_prompt()

    def _acknowledge_fourth_tv_task(self):
        if self.tv_task_04["state"] != "changed":
            return
        self.tv_task_04["state"] = "completed"
        self.tv_task_04["completion_count"] += 1
        self._preserve_completion_and_issue_next("complete4", lambda: self._issue_next_after_completion(4))
        self.status["text"] = "The television accepts the fourth task."
        self.message_timer = 1.8

    def _issue_first_tv_task(self):
        if self.tv_task["state"] != "unissued":
            return
        self.tv_task["state"] = "active"
        self._set_task_broadcast("issue")
        self.tv_frame_counter = 0
        self.tv_refresh_accum = 999.0
        self._render_tv_frame(force=True)
        self.status["text"] = "The television issues an instruction."
        self.message_timer = 1.8

    def _acknowledge_first_tv_task(self):
        if self.tv_task["state"] != "collected":
            return
        self.tv_task["state"] = "completed"
        self.tv_task["completion_count"] += 1
        self._preserve_completion_and_issue_next("complete", lambda: self._issue_next_after_completion(1))
        self.status["text"] = "The television accepts the task."
        self.message_timer = 1.8

    def _collect_first_task_note(self):
        if self.tv_task["state"] != "active" or self.tv_task["note_collected"] or self.note_intercept_active:
            return
        self.tv_task["note_collected"] = True
        self.tv_task["state"] = "intercepting"
        self.task_note_root.hide()
        self._start_note_interception()
        self._update_prompt()

    def tv_task_snapshot(self):
        return json.loads(json.dumps(self.tv_task))

    def tv_task_02_snapshot(self):
        return json.loads(json.dumps(self.tv_task_02))

    def tv_task_03_snapshot(self):
        return json.loads(json.dumps(self.tv_task_03))

    def tv_task_04_snapshot(self):
        return json.loads(json.dumps(self.tv_task_04))

    def tv_task_05_snapshot(self):
        return json.loads(json.dumps(self.tv_task_05))

    def tv_task_06_snapshot(self):
        return json.loads(json.dumps(self.tv_task_06))

    def _draw_task_glyph(self, image, glyph, ox, oy, scale=2, value=0.82):
        font = {
            "A":["01110","10001","10001","11111","10001","10001","10001"],
            "B":["11110","10001","10001","11110","10001","10001","11110"],
            "C":["01111","10000","10000","10000","10000","10000","01111"],
            "D":["11110","10001","10001","10001","10001","10001","11110"],
            "E":["11111","10000","10000","11110","10000","10000","11111"],
            "F":["11111","10000","10000","11110","10000","10000","10000"],
            "H":["10001","10001","10001","11111","10001","10001","10001"],
            "I":["11111","00100","00100","00100","00100","00100","11111"],
            "K":["10001","10010","10100","11000","10100","10010","10001"],
            "L":["10000","10000","10000","10000","10000","10000","11111"],
            "M":["10001","11011","10101","10101","10001","10001","10001"],
            "N":["10001","11001","10101","10011","10001","10001","10001"],
            "O":["01110","10001","10001","10001","10001","10001","01110"],
            "P":["11110","10001","10001","11110","10000","10000","10000"],
            "G":["01111","10000","10000","10111","10001","10001","01111"],
            "R":["11110","10001","10001","11110","10100","10010","10001"],
            "S":["01111","10000","10000","01110","00001","00001","11110"],
            "T":["11111","00100","00100","00100","00100","00100","00100"],
            "U":["10001","10001","10001","10001","10001","10001","01110"],
            "V":["10001","10001","10001","10001","01010","01010","00100"],
            "0":["01110","10001","10011","10101","11001","10001","01110"],
            "1":["00100","01100","00100","00100","00100","00100","01110"],
            "2":["01110","10001","00001","00010","00100","01000","11111"],
            "3":["11110","00001","00001","01110","00001","00001","11110"],
            "4":["10010","10010","10010","11111","00010","00010","00010"],
            "5":["11111","10000","10000","11110","00001","00001","11110"],
            "6":["01111","10000","10000","11110","10001","10001","01110"],
            "7":["11111","00001","00010","00100","01000","01000","01000"],
            "8":["01110","10001","10001","01110","10001","10001","01110"],
            "9":["01110","10001","10001","01111","00001","00001","11110"],
            "W":["10001","10001","10001","10101","10101","11011","10001"],
            "X":["10001","10001","01010","00100","01010","10001","10001"],
            ".":["00000","00000","00000","00000","00000","00110","00110"],
        }
        rows = font.get(glyph)
        if not rows:
            return 6 * scale
        w,h=image.getXSize(),image.getYSize()
        for ry,row in enumerate(rows):
            for rx,on in enumerate(row):
                if on == "1":
                    for yy in range(scale):
                        for xx in range(scale):
                            x,y=ox+rx*scale+xx,oy+ry*scale+yy
                            if 0 <= x < w and 0 <= y < h:
                                # The visible CRT face is the reverse side of the box
                                # texture orientation, so mirror authored glyph pixels here.
                                image.setGray(w - 1 - x,y,value)
        return 6 * scale

    def _draw_task_line(self, image, text, y, scale=2, value=0.82):
        width=sum(6*scale if ch!=' ' else 4*scale for ch in text)
        x=max(2,(image.getXSize()-width)//2)
        for ch in text:
            if ch==' ':
                x += 4*scale
            else:
                x += self._draw_task_glyph(image,ch,x,y,scale,value)

    def _render_task_broadcast(self, image):
        w,h=image.getXSize(),image.getYSize()
        image.fill(0.025)
        # restrained analog command frame; no fullscreen HUD or modern panel art.
        for x in range(8,w-8):
            image.setGray(x,8,0.34); image.setGray(x,h-9,0.34)
        for y in range(8,h-8):
            image.setGray(8,y,0.34); image.setGray(w-9,y,0.34)
        if self.task_broadcast_mode == "complete":
            lines=["TASK 01 COMPLETE.","FIND NEXT BROADCAST."]
        elif self.task_broadcast_mode == "issue2":
            lines=["TASK 02.","HALL.","SET THE FRAME.","RETURN TO TV."]
        elif self.task_broadcast_mode == "complete2":
            lines=["TASK 02 COMPLETE.","FIND NEXT BROADCAST."]
        elif self.task_broadcast_mode == "issue3":
            lines=["TASK 03.","BEDROOM.","COVER WINDOW.","RETURN TO TV."]
        elif self.task_broadcast_mode == "complete3":
            lines=["TASK 03 COMPLETE.","FIND NEXT BROADCAST."]
        elif self.task_broadcast_mode == "issue4":
            lines=["TASK 04.","BATHROOM.","COVER MIRROR.","RETURN TO TV."]
        elif self.task_broadcast_mode == "complete4":
            lines=["TASK 04 COMPLETE.","FIND NEXT BROADCAST."]
        elif self.task_broadcast_mode == "issue5":
            lines=["TASK 05.","HALL.","UNPLUG PHONE.","RETURN TO TV."]
        elif self.task_broadcast_mode == "complete5":
            lines=["TASK 05 COMPLETE.","FIND NEXT BROADCAST."]
        elif self.task_broadcast_mode == "issue6":
            lines=["TASK 06.","BEDROOM.","CLOSE BEDROOM DOOR.","RETURN TO TV."]
        elif self.task_broadcast_mode == "complete6":
            lines=["TASK 06 COMPLETE.","FIND NEXT BROADCAST."]
        elif self.task_broadcast_mode == "issue7":
            lines=["TASK 07.","LIVING ROOM.","TURN OFF LAMP.","RETURN TO TV."]
        elif self.task_broadcast_mode == "complete7":
            lines=["TASK 07 COMPLETE.","FIND NEXT BROADCAST."]
        elif self.task_broadcast_mode == "issue8":
            lines=["TASK 08.","KITCHEN.","TURN OFF TAP.","RETURN TO TV."]
        elif self.task_broadcast_mode == "complete8":
            lines=["TASK 08 COMPLETE.","FIND NEXT BROADCAST."]
        elif self.task_broadcast_mode == "issue9":
            lines=["TASK 09.","DINING ROOM.","PUSH IN CHAIR.","RETURN TO TV."]
        elif self.task_broadcast_mode == "complete9":
            lines=["TASK 09 COMPLETE.","FIND NEXT BROADCAST."]
        elif self.task_broadcast_mode == "issue10":
            lines=["TASK 10.","REAR HALL.","UNLATCH REAR DOOR.","RETURN TO TV."]
        elif self.task_broadcast_mode == "complete10":
            lines=["TASK 10 COMPLETE.","FIND NEXT BROADCAST."]
        elif self.task_broadcast_mode == "issue11":
            lines=["TASK 11.","GO OUTSIDE.","FIND HIM.","RETURN TO TV."]
        elif self.task_broadcast_mode == "complete11":
            lines=["TASK 11 COMPLETE.","FIND NEXT BROADCAST."]
        elif self.task_broadcast_mode == "issue12":
            lines=["TASK 12.","BASEMENT.","FIND THE NOTE.","RETURN UPSTAIRS."]
        elif self.task_broadcast_mode == "issue13":
            lines=["FINAL TASK.","ATTIC.","LOOSEN PYLON.","DO NOT LEAVE."]
        else:
            lines=["TASK 01.","BATHROOM.","TAKE THE NOTE.","RETURN TO TV."]
        y0=22 if len(lines)==4 else 38
        for i,line in enumerate(lines):
            self._draw_task_line(image,line,y0+i*21,scale=1,value=0.84)
        # cheap deterministic raster noise keeps the task inside the same CRT language.
        for y in range(h):
            if y % 4 == 0:
                for x in range(w):
                    v=image.getGray(x,y)*0.78
                    image.setGray(x,y,v)
            for x in range(w):
                if ((x*47+y*83+self.tv_frame_counter*31)%997) < 5:
                    image.setGray(x,y,min(1.0,image.getGray(x,y)+0.26))

    def _build_wall_warning(self):
        """Build the first shutdown warning directly on the east wall."""
        self.first_warning_root = self.scene_root.attachNewNode("first-tv-off-wall-warning")
        patterns = {
            "K": ["1001","1010","1100","1100","1010","1001","1001"],
            "E": ["1111","1000","1000","1110","1000","1000","1111"],
            "P": ["1110","1001","1001","1110","1000","1000","1000"],
            "I": ["111","010","010","010","010","010","111"],
            "T": ["11111","00100","00100","00100","00100","00100","00100"],
            "O": ["0110","1001","1001","1001","1001","1001","0110"],
            "N": ["1001","1101","1101","1011","1011","1001","1001"],
            ".": ["0","0","0","0","0","1","1"],
            " ": ["0","0","0","0","0","0","0"],
        }
        # Two compact lines sit to the player's screen-right of the CRT from the chair.
        # This keeps the warning spatial while ensuring the first reveal is actually readable.
        cell_y = 0.022
        cell_z = 0.031
        gap = 0.014
        x = self.room_rect[2] - 0.020
        lines = [("KEEP IT", 0.88, self.floor_z + 1.13), ("ON.", 0.88, self.floor_z + 0.86)]
        for line_i, (phrase, center_y, base_z) in enumerate(lines):
            widths = [len(patterns[ch][0]) if ch != " " else 2 for ch in phrase]
            total = sum(w*cell_y for w in widths) + gap*(len(phrase)-1)
            cursor = center_y - total/2.0
            for ci, ch in enumerate(phrase):
                pat = patterns[ch]
                w = widths[ci]
                for row, bits in enumerate(pat):
                    for col, bit in enumerate(bits):
                        if bit != "1":
                            continue
                        y = cursor + (col + 0.5) * cell_y
                        z = base_z + (6 - row + 0.5) * cell_z
                        self._box(
                            f"warning-{line_i}-{ci}-{row}-{col}",
                            (x, y, z),
                            (0.022, cell_y*0.76, cell_z*0.76),
                            0.30,
                            parent=self.first_warning_root,
                        )
                cursor += w*cell_y + gap
        self.first_warning_root.hide()

    def _arm_first_tv_off_warning(self):
        if self.first_warning_armed or self.first_warning_revealed:
            return
        self.first_warning_armed = True
        self.taskMgr.remove("first-tv-off-warning")
        self.taskMgr.doMethodLater(1.65, self._reveal_first_tv_off_warning, "first-tv-off-warning")

    def _reveal_first_tv_off_warning(self, task):
        if self.paused:
            task.delayTime = 0.25
            return Task.again
        if self.first_warning_revealed:
            return Task.done
        self.first_warning_armed = False
        self.first_warning_revealed = True
        self.first_warning_root.show()
        self._emit_alternate_voice_event(
            "tv_shutdown",
            cycle_index=1,
            prior_shutdowns=max(0, int(self.entity_memory.get("observed_tv_shutdowns_total", 0)) - 1),
            reset_cycles=int(self.entity_memory.get("completed_reset_cycles", 0)),
        )
        return Task.done


    def _build_second_wall_warning(self):
        """Build the second warning on the hall wall just outside the bedroom."""
        self.second_warning_root = self.scene_root.attachNewNode("second-tv-off-hall-warning")
        patterns = {
            "I":["111","010","010","010","010","010","111"],
            "H":["1001","1001","1001","1111","1001","1001","1001"],
            "E":["1111","1000","1000","1110","1000","1000","1111"],
            "A":["0110","1001","1001","1111","1001","1001","1001"],
            "R":["1110","1001","1001","1110","1010","1001","1001"],
            "D":["1110","1001","1001","1001","1001","1001","1110"],
            "T":["11111","00100","00100","00100","00100","00100","00100"],
            ".":["0","0","0","0","0","1","1"],
            " ":["0","0","0","0","0","0","0"],
        }
        phrase="I HEARD THAT."
        cell_x=0.0175; cell_z=0.024; gap=0.009
        y=self.hall_rect[1] + 0.022
        widths=[len(patterns[ch][0]) if ch != " " else 2 for ch in phrase]
        total=sum(w*cell_x for w in widths)+gap*(len(phrase)-1)
        cursor=(self.hall_rect[0]+self.hall_rect[2])/2.0-total/2.0
        base_z=self.floor_z+1.12
        for ci,ch in enumerate(phrase):
            pat=patterns[ch]; w=widths[ci]
            for row,bits in enumerate(pat):
                for col,bit in enumerate(bits):
                    if bit != "1": continue
                    x=cursor+(col+0.5)*cell_x
                    z=base_z+(6-row+0.5)*cell_z
                    self._box(f"warning2-{ci}-{row}-{col}",(x,y,z),(cell_x*0.78,0.022,cell_z*0.78),0.24,parent=self.second_warning_root)
            cursor += w*cell_x+gap
        self.second_warning_root.hide()

    def _build_post_reset_memory_reaction(self):
        """Build one subtle post-reset sign driven only by approved entity memory."""
        self.memory_reaction_root = self.scene_root.attachNewNode("post-reset-memory-reaction")
        patterns = {
            "A":["0110","1001","1001","1111","1001","1001","1001"],
            "G":["0111","1000","1000","1011","1001","1001","0111"],
            "I":["111","010","010","010","010","010","111"],
            "N":["1001","1101","1101","1011","1011","1001","1001"],
            ".":["0","0","0","0","0","1","1"],
        }
        phrase = "AGAIN."
        # Small wall writing above and slightly left of the CRT. It is visible from
        # the accepted reset spawn but reads as environmental evidence, not HUD.
        cell_y = 0.014
        cell_z = 0.020
        gap = 0.009
        x = self.room_rect[2] - 0.019
        center_y = 1.48
        base_z = self.floor_z + 2.03
        widths = [len(patterns[ch][0]) for ch in phrase]
        total = sum(w * cell_y for w in widths) + gap * (len(phrase) - 1)
        cursor = center_y - total / 2.0
        for ci, ch in enumerate(phrase):
            pat = patterns[ch]
            w = widths[ci]
            for row, bits in enumerate(pat):
                for col, bit in enumerate(bits):
                    if bit != "1":
                        continue
                    y = cursor + (col + 0.5) * cell_y
                    z = base_z + (6 - row + 0.5) * cell_z
                    self._box(
                        f"memory-reaction-{ci}-{row}-{col}",
                        (x, y, z),
                        (0.019, cell_y * 0.72, cell_z * 0.72),
                        0.20,
                        parent=self.memory_reaction_root,
                    )
            cursor += w * cell_y + gap
        self.memory_reaction_root.hide()

    def _sync_post_reset_memory_reaction(self):
        """Show the sign only after a completed reset exists in approved memory."""
        if self.entity_memory["completed_reset_cycles"] > 0:
            self.memory_reaction_root.show()
        else:
            self.memory_reaction_root.hide()

    def _load_alternate_voice_placeholders(self):
        """Load preserved Alternate voice-event placeholders.

        These are deliberately neutral signal placeholders, not synthetic speech.
        The authored line text and behavior categories live in data/alternate_voice_lines.json
        so later recorded dialogue can replace audio without losing event authority.
        """
        self.alternate_voice_sounds = {}
        if ARGS.no_audio:
            return
        for entry in self.alternate_voice_config.get("lines", []):
            path = ROOT / entry.get("audio", "")
            if not path.exists():
                continue
            try:
                snd = self.loader.loadSfx(panda_filename(path))
                snd.setVolume(float(entry.get("volume", 0.34)))
                self.alternate_voice_sounds[entry["id"]] = snd
            except Exception:
                pass

    def _alternate_voice_rule_matches(self, rule: dict, context: dict) -> bool:
        when = rule.get("when", {})
        for key, expected in when.items():
            if key.endswith("_min"):
                actual = context.get(key[:-4], 0)
                if actual < expected:
                    return False
            elif key.endswith("_max"):
                actual = context.get(key[:-4], 0)
                if actual > expected:
                    return False
            elif context.get(key) != expected:
                return False
        return True

    def _select_alternate_voice_line(self, event: str, **context):
        """Choose one authored line from observed state; never choose random chatter."""
        authority = self.alternate_voice_config.get("behavior_authority", {})
        for rule in authority.get("rules", []):
            if rule.get("event") != event:
                continue
            rule_id = str(rule.get("id", rule.get("line_id", event)))
            if rule.get("once_per_run") and rule_id in self.alternate_voice_rules_fired:
                continue
            if self._alternate_voice_rule_matches(rule, context):
                return rule
        return None

    def _resume_tv_audio_after_voice(self, task):
        self._sync_tv_channel_audio()
        return Task.done

    def _play_alternate_voice_placeholder(self, line_id: str):
        snd = self.alternate_voice_sounds.get(line_id)
        if snd is not None:
            try:
                # The Alternate voice is outside the TV broadcast. Briefly stop the
                # channel bed so a future recorded line will not be buried by it.
                active = self.tv_channel_sounds.get(self.tv_channel_sound_active)
                if active is not None:
                    active.stop()
                snd.stop(); snd.play()
                self.taskMgr.remove("alternate-voice-audio-resume")
                delay = max(0.35, float(snd.length()) + 0.10)
                self.taskMgr.doMethodLater(delay, self._resume_tv_audio_after_voice, "alternate-voice-audio-resume")
            except Exception:
                pass

    def _emit_alternate_voice_event(self, event: str, **context):
        rule = self._select_alternate_voice_line(event, **context)
        if rule is None:
            return None
        line_id = str(rule["line_id"])
        rule_id = str(rule.get("id", line_id))
        if rule.get("once_per_run"):
            self.alternate_voice_rules_fired.add(rule_id)
        role = str(rule.get("role", "behavior"))
        self.alternate_voice_history.append({"event": event, "line_id": line_id, "role": role, "context": dict(context)})
        _append_runtime_log(f"ALT_VOICE event={event} role={role} line={line_id} context={context}")
        self._play_alternate_voice_placeholder(line_id)
        return line_id

    def _emit_post_reset_voice(self, task):
        self._emit_alternate_voice_event(
            "post_reset",
            reset_cycles=int(self.entity_memory.get("completed_reset_cycles", 0)),
            prior_shutdowns=int(self.entity_memory.get("observed_tv_shutdowns_total", 0)),
        )
        return Task.done

    def _load_second_warning_voice(self):
        # Preserve the old warning event while routing it through the recovered
        # Alternate voice contract instead of a vanished one-off WAV filename.
        self.second_voice = self.alternate_voice_sounds.get("tv_disobedience_02")

    def _load_tv_channel_audio(self):
        self.tv_channel_sounds = {}
        if ARGS.no_audio:
            return
        for entry in self.tv_audio_config.get("channels", []):
            path = ROOT / entry.get("asset", "")
            if not path.exists():
                continue
            try:
                snd = self.loader.loadSfx(panda_filename(path))
                snd.setLoop(True)
                snd.setVolume(float(entry.get("volume", self.tv_audio_config.get("default_volume", 0.12))))
                self.tv_channel_sounds[int(entry["index"])] = snd
            except Exception:
                pass

    def _sync_tv_channel_audio(self):
        wanted = self.tv_channel if (self.tv_focused and self.tv_power and not ARGS.no_audio) else None
        if self.tv_channel_sound_active == wanted:
            return
        for idx, snd in self.tv_channel_sounds.items():
            try:
                snd.stop()
            except Exception:
                pass
        self.tv_channel_sound_active = None
        if wanted in self.tv_channel_sounds:
            try:
                self.tv_channel_sounds[wanted].play()
                self.tv_channel_sound_active = wanted
            except Exception:
                self.tv_channel_sound_active = None

    def _arm_second_tv_off_warning(self):
        if self.second_warning_armed or self.second_warning_revealed:
            return
        self.second_warning_armed = True
        self.taskMgr.remove("second-tv-off-warning")
        self.taskMgr.doMethodLater(1.35, self._reveal_second_tv_off_warning, "second-tv-off-warning")

    def _reveal_second_tv_off_warning(self, task):
        if self.paused:
            task.delayTime = 0.25
            return Task.again
        if self.second_warning_revealed:
            return Task.done
        self.second_warning_armed = False
        self.second_warning_revealed = True
        self.second_warning_root.show()
        self._emit_alternate_voice_event(
            "tv_shutdown",
            cycle_index=2,
            prior_shutdowns=max(0, int(self.entity_memory.get("observed_tv_shutdowns_total", 0)) - 2),
            reset_cycles=int(self.entity_memory.get("completed_reset_cycles", 0)),
        )
        # Mild reaction only: one short bright CRT frame while power remains logically off.
        self._render_second_shutdown_flash()
        self.taskMgr.doMethodLater(0.16, self._end_second_shutdown_flash, "second-tv-off-flash")
        return Task.done

    def _render_second_shutdown_flash(self):
        w,h=self.tv_authority["screen"]["internal_resolution"]
        image=PNMImage(w,h,1)
        for yy in range(h):
            for xx in range(w):
                image.setGray(xx,yy,0.82 if ((xx*19+yy*37)%23)<6 else 0.16)
        self.tv_texture.load(image)

    def _end_second_shutdown_flash(self, task):
        self._render_tv_frame(force=True)
        return Task.done


    def _build_datamosh_overlay(self):
        """Brief bounded screen-space corruption for the third TV shutdown.

        This is deliberately cheap: deterministic horizontal hold/tear bands,
        camera displacement and a dark frame-history veil. It never persists
        outside the reset transition.
        """
        self.datamosh_root = self.aspect2d.attachNewNode("datamosh-reset-overlay")
        self.datamosh_blocks = []
        # Different heights keep the effect from reading like one fullscreen flash.
        bands = [(-0.94,-0.73),(-0.69,-0.51),(-0.45,-0.31),(-0.24,-0.08),(-0.02,0.12),(0.18,0.34),(0.42,0.57),(0.64,0.78),(0.82,0.95)]
        for i,(y0,y1) in enumerate(bands):
            shade = (0.78 if i % 3 == 0 else (0.16 if i % 3 == 1 else 0.42))
            frame = DirectFrame(parent=self.datamosh_root, frameColor=(shade,shade,shade,0.0), frameSize=(-1.55,1.55,y0,y1))
            frame.setTransparency(True)
            self.datamosh_blocks.append(frame)
        self.datamosh_veil = DirectFrame(parent=self.datamosh_root, frameColor=(0.0,0.0,0.0,0.0), frameSize=(-1.55,1.55,-1.0,1.0))
        self.datamosh_veil.setTransparency(True)
        self.datamosh_root.hide()

    def _arm_third_shutdown_reset(self):
        if self.datamosh_active:
            return
        self.taskMgr.remove("third-tv-off-datamosh")
        self.taskMgr.doMethodLater(0.28, self._begin_datamosh_reset, "third-tv-off-datamosh")

    def _begin_datamosh_reset(self, task):
        if self.paused:
            task.delayTime = 0.12
            return Task.again
        self.datamosh_active = True
        self.datamosh_elapsed = 0.0
        self.datamosh_tick = 0
        for k in self.keys:
            self.keys[k] = False
        self.prompt.hide()
        self.tv_focus_ui.hide()
        self.crosshair.hide()
        self.datamosh_root.show()
        self.datamosh_veil["frameColor"] = (0.0,0.0,0.0,0.18)
        self.taskMgr.add(self._datamosh_runtime, "datamosh-runtime", sort=20)
        return Task.done

    def _datamosh_runtime(self, task):
        if not self.datamosh_active:
            return Task.done
        if self.paused:
            return Task.cont
        dt = min(globalClock.getDt(), 0.05)
        self.datamosh_elapsed += dt
        phase = min(1.0, self.datamosh_elapsed / self.datamosh_duration)
        self.datamosh_tick += 1

        # Deterministic block-hold pattern: pieces of the previous view appear
        # horizontally displaced while the camera itself drifts out of register.
        for i,frame in enumerate(self.datamosh_blocks):
            bucket = (self.datamosh_tick // 2 + i * 7) % 11
            xshift = ((bucket - 5) / 5.0) * (0.18 + 0.12 * (1.0 - phase))
            frame.setX(xshift)
            alpha = 0.18 + (((i * 13 + self.datamosh_tick * 3) % 9) / 8.0) * 0.34
            shade = 0.78 if i % 3 == 0 else (0.12 if i % 3 == 1 else 0.42)
            frame["frameColor"] = (shade, shade, shade, alpha)

        # Keep motion bounded to avoid a large camera whip.
        base_h = -90.0
        base_p = -8.0
        self.heading = base_h + math.sin(self.datamosh_elapsed * 44.0) * 2.8
        self.pitch = base_p + math.sin(self.datamosh_elapsed * 31.0 + 1.2) * 1.7
        self._apply_camera()
        self.datamosh_veil["frameColor"] = (0.0,0.0,0.0,0.16 + 0.34 * phase)

        if self.datamosh_elapsed >= self.datamosh_duration:
            self._complete_datamosh_reset()
            return Task.done
        return Task.cont

    def _complete_datamosh_reset(self):
        self.datamosh_active = False
        self.datamosh_root.hide()
        for frame in self.datamosh_blocks:
            frame.setX(0)
            frame["frameColor"] = (0,0,0,0)
        self.datamosh_veil["frameColor"] = (0,0,0,0)

        # Pass 28 reset authority: return to the accepted master-bedroom start.
        sx, sy, sz = self.master["player_start"]["floor_pos"]
        self.player = Vec3(sx, sy, sz)
        self.heading = -float(self.master["player_start"]["heading_deg"])
        self.pitch = float(self.master["player_start"]["pitch_deg"])
        self.eye_h = float(self.master["player_start"]["eye_height"])
        self.camLens.setFov(float(self.display_settings.get("fov", DISPLAY_DEFAULTS["fov"])))
        self.tv_focused = False
        self._focus_restore = None
        self.tv_power = True
        self.tv_channel = int(self.tv_authority["initial_state"]["channel_index"])
        self.tv_shutdown_count = 0
        self.tv_task.update({"state":"unissued","note_collected":False})
        self._reset_note_interception()
        self.tv_task_02.update({"state":"locked","frame_straightened":False})
        self._set_task_frame_crooked(True)
        self.tv_task_03.update({"state":"locked","window_covered":False})
        self._set_task_window_covered(False)
        self.tv_task_04.update({"state":"locked","mirror_covered":False})
        self._set_task_mirror_covered(False)
        self.tv_task_05.update({"state":"locked","phone_disconnected":False})
        self._set_task_phone_disconnected(False)
        self.tv_task_06.update({"state":"locked","bedroom_door_closed":False})
        self._set_master_bedroom_door_closed(False)
        self.tv_task_07.update({"state":"locked","lamp_off":False})
        self.tv_task_08.update({"state":"completed","tap_off":True,"completion_count":1})
        self.tv_task_09.update({"state":"locked","chair_in":False})
        self.tv_task_10.update({"state":"locked","unlatched":False,"completion_count":0})
        self.forest_task.update({"state":"locked","choice":None,"completion_count":0})
        self._reset_forest_encounter()
        if hasattr(self, "floor1_rear_latch"):
            self.floor1_rear_latch.setPos(10.10,9.30,self.floor1_z+1.48)
        self.basement_task.update({"state":"locked","completion_count":0})
        self.floor1_active=False
        self.floor1_lamp_glow.setColor(0.72,0.72,0.72,1)
        self.floor1_tap.setHpr(0,0,35)
        self.floor1_chair_root.setPos(7.15,6.55,self.floor1_z)
        self.task_broadcast_mode = None
        self.task_broadcast_channel = None
        self.task_completion_broadcast_mode = None
        self.task_completion_broadcast_channel = None
        self.task_broadcast_history.clear()
        self.task_note_root.show()
        self.tv_frame_counter = 0
        self.tv_refresh_accum = 999.0

        # Pass 30 memory authority: the house/run state resets, but approved
        # observations remain. Completing this reset is itself an observed fact.
        self.entity_memory["completed_reset_cycles"] += 1
        self._sync_post_reset_memory_reaction()
        # A datamosh reset begins a new run for bounded once-per-run voice rules.
        self.alternate_voice_rules_fired.clear()
        self.taskMgr.remove("post-reset-alternate-voice")
        self.taskMgr.doMethodLater(1.10, self._emit_post_reset_voice, "post-reset-alternate-voice")
        self._hide_alternate()
        self.alt_hidden_timer = 12.0
        self.tv_focus_from_chair = False
        self.tv_sit_count = 0
        self.alt_visibility_mode = "full"
        self.alt_forced_visibility_mode = None
        self.alternate_head_variant = 0
        self.taskMgr.remove("first-tv-off-warning")
        self.taskMgr.remove("second-tv-off-warning")
        self.taskMgr.remove("second-tv-off-flash")
        self.first_warning_armed = False
        self.first_warning_revealed = False
        self.second_warning_armed = False
        self.second_warning_revealed = False
        self.first_warning_root.hide()
        self.second_warning_root.hide()
        if self.second_voice is not None:
            try:
                self.second_voice.stop()
            except Exception:
                pass

        self._render_tv_frame(force=True)
        self.pause.hide()
        self.tv_focus_ui.hide()
        self.status.show()
        self.crosshair.show()
        self._set_mouse_capture(True)
        self._apply_camera()
        self._update_prompt()

    # ---------- UI ----------
    def _build_ui(self):
        self.crosshair = DirectLabel(text="+", scale=0.035, text_fg=(0.82, 0.82, 0.82, 0.75), frameColor=(0, 0, 0, 0), pos=(0, 0, -0.01))
        self.prompt = DirectLabel(
            text="", scale=0.052, text_fg=(0.96, 0.96, 0.96, 1),
            text_shadow=(0, 0, 0, 0.95), text_shadowOffset=(0.045, 0.045),
            frameColor=(0, 0, 0, 0.72), frameSize=(-6.1, 6.1, -0.60, 0.78),
            pos=(0, 0, -0.76))
        self.status = DirectLabel(text="", scale=0.037, text_fg=(0.75, 0.75, 0.75, 1), frameColor=(0, 0, 0, 0), pos=(-1.27, 0, 0.91), text_align=TextNode.ALeft)
        # Pass 87: TV focus uses one compact, structured panel rather than a
        # debug-style sentence stretched across a giant rectangle.  Channel,
        # task state, and controls have separate visual authority.
        self.tv_focus_ui = DirectFrame(
            frameColor=(0.010, 0.010, 0.012, 0.78),
            frameSize=(-0.86, 0.86, -0.125, 0.195),
            pos=(0, 0, -0.82))
        self.tv_focus_channel_box = DirectFrame(
            parent=self.tv_focus_ui, frameColor=(0.040, 0.040, 0.044, 0.96),
            frameSize=(-0.35, 0.35, -0.052, 0.052), pos=(-0.44, 0, 0.047))
        self.tv_focus_state_box = DirectFrame(
            parent=self.tv_focus_ui, frameColor=(0.025, 0.028, 0.026, 0.96),
            frameSize=(-0.39, 0.39, -0.052, 0.052), pos=(0.40, 0, 0.047))
        self.tv_focus_controls_box = DirectFrame(
            parent=self.tv_focus_ui, frameColor=(0.020, 0.020, 0.023, 0.96),
            frameSize=(-0.76, 0.76, -0.041, 0.041), pos=(0, 0, -0.066))
        self.tv_focus_channel = DirectLabel(
            parent=self.tv_focus_channel_box, text="", scale=0.039,
            text_fg=(0.91, 0.91, 0.89, 1), frameColor=(0, 0, 0, 0),
            pos=(0, 0, -0.012), text_align=TextNode.ACenter)
        self.tv_focus_state = DirectLabel(
            parent=self.tv_focus_state_box, text="", scale=0.031,
            text_fg=(0.74, 0.78, 0.74, 1), frameColor=(0, 0, 0, 0),
            pos=(0, 0, -0.010), text_align=TextNode.ACenter)
        self.tv_focus_controls = DirectLabel(
            parent=self.tv_focus_controls_box,
            text="LEFT / RIGHT  CHANNEL     P  POWER     E  STAND", scale=0.026,
            text_fg=(0.61, 0.61, 0.63, 1), frameColor=(0, 0, 0, 0),
            pos=(0, 0, -0.010), text_align=TextNode.ACenter)
        # Entry is available only on the powered DREAM channel, outside task broadcasts.
        self.tv_focus_link = DirectLabel(
            parent=self.tv_focus_ui, text="T  ENTER ANDREW'S NIGHTMARE", scale=0.026,
            text_fg=(0.40, 0.84, 0.78, 1), frameColor=(0.025, 0.055, 0.055, 0.94),
            frameSize=(-0.32, 0.32, -0.038, 0.038),
            pos=(0.57, 0, 0.158), text_align=TextNode.ACenter)
        self.tv_focus_link.hide()
        self.tv_focus_ui.hide()

        self.pause = DirectFrame(frameColor=(0.012, 0.012, 0.015, 0.96), frameSize=(-0.72, 0.72, -0.68, 0.68))
        self.pause_main = DirectFrame(parent=self.pause, frameColor=(0,0,0,0), frameSize=(-0.70,0.70,-0.65,0.65))
        DirectLabel(parent=self.pause_main, text="DREAMCATCHER ALTERNATE", scale=0.062, pos=(0, 0, 0.49), text_fg=(0.88, 0.88, 0.88, 1), frameColor=(0, 0, 0, 0))
        DirectLabel(parent=self.pause_main, text="PAUSED", scale=0.038, pos=(0, 0, 0.37), text_fg=(0.55, 0.55, 0.58, 1), frameColor=(0, 0, 0, 0))
        DirectLabel(parent=self.pause_main, text="WASD  MOVE     MOUSE  LOOK     SHIFT  SPRINT     E  INTERACT", scale=0.027, pos=(0, 0, 0.22), text_fg=(0.62, 0.62, 0.65, 1), frameColor=(0, 0, 0, 0))
        DirectButton(parent=self.pause_main, text="RESUME", scale=0.050, pos=(0, 0, 0.03), text_fg=(0.82,0.82,0.84,1), frameColor=(0.045,0.045,0.052,0.96), command=self.toggle_pause)
        DirectButton(parent=self.pause_main, text="DISPLAY", scale=0.050, pos=(0, 0, -0.16), text_fg=(0.82,0.82,0.84,1), frameColor=(0.045,0.045,0.052,0.96), command=self._show_display_menu)
        DirectButton(parent=self.pause_main, text="QUIT", scale=0.050, pos=(0, 0, -0.38), text_fg=(0.72,0.72,0.74,1), frameColor=(0.040,0.040,0.046,0.96), command=self._quit_game)

        self.travel_back_button = DirectButton(parent=self.pause_main, text="RETURN TO MIRROR'S LIMBO",
            text_scale=.030, pos=(0,0,-.52), frameSize=(-.37,.37,-.04,.04),
            frameColor=(.04,.065,.065,1), text_fg=(.65,.82,.80,1), relief=1,
            command=self.return_to_limbo)
        self.travel_back_button.hide()
        self.mode_return_notice = DirectLabel(parent=self.pause_main, text="", scale=0.027,
            pos=(0, 0, -0.63), text_fg=(0.55, 0.79, 0.76, 1), frameColor=(0,0,0,0))
        self.mode_return_notice.hide()
        self.display_panel = DirectFrame(parent=self.pause, frameColor=(0,0,0,0), frameSize=(-0.70,0.70,-0.65,0.65))
        DirectLabel(parent=self.display_panel, text="DISPLAY", scale=0.062, pos=(0,0,0.50), text_fg=(0.88,0.88,0.88,1), frameColor=(0,0,0,0))
        self.display_mode_label = DirectLabel(parent=self.display_panel, text="", scale=0.035, pos=(0,0,0.34), text_fg=(0.72,0.72,0.75,1), frameColor=(0,0,0,0))
        DirectButton(parent=self.display_panel, text="BORDERLESS", scale=0.035, pos=(-0.43,0,0.19), text_fg=(0.80,0.80,0.82,1), frameColor=(0.045,0.045,0.052,0.96), command=self._display_set_mode, extraArgs=["borderless"])
        DirectButton(parent=self.display_panel, text="FULLSCREEN", scale=0.035, pos=(0,0,0.19), text_fg=(0.80,0.80,0.82,1), frameColor=(0.045,0.045,0.052,0.96), command=self._display_set_mode, extraArgs=["fullscreen"])
        DirectButton(parent=self.display_panel, text="WINDOWED", scale=0.035, pos=(0.43,0,0.19), text_fg=(0.80,0.80,0.82,1), frameColor=(0.045,0.045,0.052,0.96), command=self._display_set_mode, extraArgs=["windowed"])
        self.display_resolution_label = DirectLabel(parent=self.display_panel, text="", scale=0.034, pos=(0,0,0.04), text_fg=(0.72,0.72,0.75,1), frameColor=(0,0,0,0))
        DirectButton(parent=self.display_panel, text="<", scale=0.048, pos=(-0.34,0,0.04), text_fg=(0.80,0.80,0.82,1), frameColor=(0.045,0.045,0.052,0.96), command=self._display_cycle_resolution, extraArgs=[-1])
        DirectButton(parent=self.display_panel, text=">", scale=0.048, pos=(0.34,0,0.04), text_fg=(0.80,0.80,0.82,1), frameColor=(0.045,0.045,0.052,0.96), command=self._display_cycle_resolution, extraArgs=[1])
        self.display_vsync_button = DirectButton(parent=self.display_panel, text="", scale=0.035, pos=(-0.35,0,-0.11), text_fg=(0.76,0.76,0.79,1), frameColor=(0.040,0.040,0.047,0.96), command=self._display_toggle_vsync)
        self.display_fps_button = DirectButton(parent=self.display_panel, text="", scale=0.035, pos=(0.35,0,-0.11), text_fg=(0.76,0.76,0.79,1), frameColor=(0.040,0.040,0.047,0.96), command=self._display_toggle_fps)
        self.display_fov_label = DirectLabel(parent=self.display_panel, text="", scale=0.034, pos=(0,0,-0.25), text_fg=(0.72,0.72,0.75,1), frameColor=(0,0,0,0))
        DirectButton(parent=self.display_panel, text="-", scale=0.045, pos=(-0.27,0,-0.25), text_fg=(0.80,0.80,0.82,1), frameColor=(0.045,0.045,0.052,0.96), command=self._display_adjust_fov, extraArgs=[-5])
        DirectButton(parent=self.display_panel, text="+", scale=0.045, pos=(0.27,0,-0.25), text_fg=(0.80,0.80,0.82,1), frameColor=(0.045,0.045,0.052,0.96), command=self._display_adjust_fov, extraArgs=[5])
        DirectButton(parent=self.display_panel, text="BACK", scale=0.046, pos=(0,0,-0.48), text_fg=(0.82,0.82,0.84,1), frameColor=(0.045,0.045,0.052,0.96), command=self._hide_display_menu)
        DirectLabel(parent=self.display_panel, text="F11 / ALT+ENTER  TOGGLE BORDERLESS     VSYNC APPLIES NEXT LAUNCH", scale=0.023, pos=(0,0,-0.59), text_fg=(0.48,0.48,0.51,1), frameColor=(0,0,0,0))
        self.display_panel.hide()
        self._refresh_display_ui()
        self.pause.hide()

    def _bind_controls(self):
        for key in ("w", "a", "s", "d"):
            self.accept(key, self._set_key, [key, True])
            self.accept(key + "-up", self._set_key, [key, False])
        self.accept("shift", self._set_key, ["shift", True])
        self.accept("shift-up", self._set_key, ["shift", False])
        self.accept("escape", self.toggle_pause)
        self.accept("f11", self._toggle_borderless)
        self.accept("alt-enter", self._toggle_borderless)
        self.accept("e", self._interact)
        self.accept("p", self._tv_power_toggle)
        self.accept("t", self._prepare_dream_link)
        self.accept("arrow_left", self._tv_channel_step, [-1])
        self.accept("arrow_right", self._tv_channel_step, [1])
        self.accept("1", self._forest_choose, [True])
        self.accept("2", self._forest_choose, [False])

    def _save_display_settings(self):
        try:
            USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
            DISPLAY_SETTINGS_FILE.write_text(json.dumps(self.display_settings, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:
            _append_runtime_log(f"DISPLAY settings_save_failed {type(exc).__name__}: {exc}")

    def _push_shared_display_settings(self):
        """Player changed display options here: make Mirror's Limbo follow them too."""
        if _CAPTURE_MODE:
            return
        shared.update_settings(
            display_mode=str(self.display_settings.get("mode", "borderless")),
            resolution=self.display_settings.get("resolution", [1920, 1080]),
            vsync=bool(self.display_settings.get("vsync", True)),
            fov=shared.limbo_fov_from_world(self.display_settings.get("fov", DISPLAY_DEFAULTS["fov"]), DISPLAY_DEFAULTS["fov"]),
        )

    def _refresh_display_ui(self):
        if not hasattr(self, "display_mode_label"):
            return
        mode = str(self.display_settings.get("mode", "borderless")).upper()
        rw, rh = map(int, self.display_settings.get("resolution", [1920,1080]))
        if mode == "BORDERLESS":
            dw, dh = self.desktop_size
            self.display_mode_label["text"] = f"MODE  {mode}     DESKTOP  {dw} x {dh}"
        else:
            self.display_mode_label["text"] = f"MODE  {mode}"
        self.display_resolution_label["text"] = f"RESOLUTION  {rw} x {rh}"
        self.display_vsync_button["text"] = "VSYNC  " + ("ON" if self.display_settings.get("vsync", True) else "OFF")
        self.display_fps_button["text"] = "FPS METER  " + ("ON" if self.display_settings.get("fps_meter", False) else "OFF")
        self.display_fov_label["text"] = f"FOV  {int(self.display_settings.get('fov',74))}"

    def _show_display_menu(self):
        self.pause_main.hide(); self.display_panel.show(); self._refresh_display_ui()

    def _hide_display_menu(self):
        self.display_panel.hide(); self.pause_main.show()

    def _display_set_mode(self, mode: str):
        if mode not in ("borderless", "fullscreen", "windowed"):
            return
        self.display_settings["mode"] = mode
        self._apply_display_settings()
        self._push_shared_display_settings()

    def _display_cycle_resolution(self, step: int):
        current = tuple(map(int, self.display_settings.get("resolution", [1920,1080])))
        try:
            idx = DISPLAY_RESOLUTIONS.index(current)
        except ValueError:
            idx = 2
        idx = (idx + int(step)) % len(DISPLAY_RESOLUTIONS)
        self.display_settings["resolution"] = list(DISPLAY_RESOLUTIONS[idx])
        self._apply_display_settings()
        self._push_shared_display_settings()

    def _display_toggle_vsync(self):
        # Panda's sync-video config is established when the graphics window opens.
        # Persist the preference now; it takes full effect on the next launch.
        self.display_settings["vsync"] = not bool(self.display_settings.get("vsync", True))
        self._save_display_settings(); self._refresh_display_ui()
        self._push_shared_display_settings()
        self.status["text"] = "V-Sync setting saved. Applies fully on next launch."

    def _display_toggle_fps(self):
        self.display_settings["fps_meter"] = not bool(self.display_settings.get("fps_meter", False))
        self.setFrameRateMeter(bool(self.display_settings["fps_meter"]))
        self._save_display_settings(); self._refresh_display_ui()

    def _display_adjust_fov(self, delta: int):
        fov = max(60, min(95, int(self.display_settings.get("fov",74)) + int(delta)))
        self.display_settings["fov"] = fov
        self.camLens.setFov(float(fov))
        self._save_display_settings(); self._refresh_display_ui()
        self._push_shared_display_settings()

    def _toggle_borderless(self):
        if _CAPTURE_MODE or not self.win:
            return
        self.display_settings["mode"] = "windowed" if self.display_settings.get("mode") == "borderless" else "borderless"
        self._apply_display_settings()
        self._push_shared_display_settings()

    def _apply_display_settings(self):
        self._save_display_settings()
        self._refresh_display_ui()
        if _CAPTURE_MODE or not self.win or not hasattr(self.win, "requestProperties"):
            return
        props = WindowProperties()
        props.setTitle("DreamCatcher Alternate")
        mode = str(self.display_settings.get("mode", "borderless"))
        rw, rh = map(int, self.display_settings.get("resolution", [1920,1080]))
        if mode == "borderless":
            dw, dh = self.desktop_size
            props.setFullscreen(False); props.setUndecorated(True); props.setFixedSize(True)
            props.setOrigin(0, 0); props.setSize(int(dw), int(dh))
        elif mode == "fullscreen":
            props.setUndecorated(True); props.setFullscreen(True); props.setFixedSize(True)
            props.setSize(rw, rh)
        else:
            props.setFullscreen(False); props.setUndecorated(False); props.setFixedSize(False)
            props.setSize(rw, rh)
            dw, dh = self.desktop_size
            props.setOrigin(max(0,(int(dw)-rw)//2), max(0,(int(dh)-rh)//2))
        self.win.requestProperties(props)
        _append_runtime_log(f"DISPLAY apply mode={mode} resolution={rw}x{rh} desktop={self.desktop_size}")

    def _set_key(self, key, value):
        if self.paused:
            return
        if self.tv_focused and value and key in ("a", "d"):
            self._tv_channel_step(-1 if key == "a" else 1)
            return
        if not self.tv_focused:
            self.keys[key] = value

    def _set_mouse_capture(self, capture: bool):
        # Retain the requested authority even in offscreen QA where WindowProperties
        # cannot prove an OS cursor state.  This gives regression tests a stable
        # contract without changing the real window path.
        self.mouse_capture_requested = bool(capture)
        if not self.win or ARGS.test_shot or not hasattr(self.win, "requestProperties"):
            return
        props = WindowProperties()
        props.setCursorHidden(capture)
        props.setMouseMode(WindowProperties.M_confined if capture else WindowProperties.M_absolute)
        self.win.requestProperties(props)

    def _clear_input_state(self):
        for key in self.keys:
            self.keys[key] = False
        self.footstep_distance_accum = 0.0

    def _on_window_event(self, window):
        if getattr(self, "world_travel", None) and self.world_travel.busy:
            return
        """Keep Windows focus/minimize/resize changes from leaving stale input behind."""
        if not window or not hasattr(window, "getProperties"):
            return
        props = window.getProperties()
        try:
            foreground = bool(props.getForeground())
            minimized = bool(props.getMinimized())
            width, height = int(props.getXSize()), int(props.getYSize())
        except Exception:
            return
        size = (width, height)
        if size != self._last_window_size and width > 0 and height > 0:
            self._last_window_size = size
            _append_runtime_log(f"WINDOW size={width}x{height}")
        active = foreground and not minimized
        if not active:
            self._clear_input_state()
            self._set_mouse_capture(False)
            if not self.paused and not self.finale_finished:
                self._focus_auto_paused = True
                self.paused = True
                self.pause.show()
                self.prompt.hide(); self.crosshair.hide(); self.tv_focus_ui.hide()
                _append_runtime_log("AUTO_PAUSE focus_lost")
        elif not self._window_was_foreground:
            # Stay paused after returning; the player explicitly resumes.
            self._set_mouse_capture(False if self.paused else True)
        self._window_was_foreground = active

    def _runtime_cleanup(self):
        """Idempotent cleanup shared by Quit, window-X, and crash recovery."""
        if getattr(self, "_runtime_cleanup_done", False):
            return
        self._runtime_cleanup_done = True
        travel = getattr(self, "world_travel", None)
        if not _CAPTURE_MODE and travel is not None and not travel.committed and travel.incoming is None:
            # Quitting from the house keeps its progress for the next visit.
            try:
                shared.save_house(None if self.finale_finished else self._house_snapshot())
            except Exception as exc:
                _append_runtime_log(f"HOUSE_STATE save_failed {type(exc).__name__}: {exc}")
        if getattr(self, "world_travel", None):
            self.world_travel.close()
        try:
            self._clear_input_state()
        except Exception:
            pass
        try:
            self._set_mouse_capture(False)
        except Exception:
            pass
        for entry in getattr(self, "window_audio_sources", {}).values():
            sound = entry.get("sound") if isinstance(entry, dict) else None
            if sound is not None:
                try:
                    sound.stop()
                except Exception:
                    pass
        for entry in getattr(self, "window_audio_sources", {}).values():
            if isinstance(entry, dict):
                for sound in entry.get("events", []):
                    if sound is not None:
                        try:
                            sound.stop()
                        except Exception:
                            pass
        for sound in getattr(self, "footstep_sounds", {}).values():
            if sound is not None:
                try:
                    sound.stop()
                except Exception:
                    pass
        voice = getattr(self, "second_voice", None)
        if voice is not None:
            try:
                voice.stop()
            except Exception:
                pass
        for sound in getattr(self, "tv_channel_sounds", {}).values():
            try:
                sound.stop()
            except Exception:
                pass
        self.taskMgr.remove("alternate-voice-audio-resume")
        self.taskMgr.remove("post-reset-alternate-voice")
        for sound in getattr(self, "alternate_voice_sounds", {}).values():
            try:
                sound.stop()
            except Exception:
                pass
        _append_runtime_log("EXIT cleanup")

    def _quit_game(self):
        self._runtime_cleanup()
        self.userExit()

    def toggle_pause(self):
        if self.world_travel and self.world_travel.busy:
            return
        # Ignore stale keyboard events while the OS window is not active.
        if not self._window_was_foreground:
            return
        # Do not layer the pause menu over the completed ending. Escape wakes the player in Limbo.
        if self.finale_finished and not self.paused:
            self.return_to_limbo()
            return
        # A focus-loss auto-pause may only be resumed once the OS window is active again.
        if self.paused and self._focus_auto_paused and not self._window_was_foreground:
            return
        self.paused = not self.paused
        self._clear_input_state()
        if not self.paused:
            self.mode_return_notice.hide()
            self._focus_auto_paused = False
        if self.paused:
            self.pause_main.show(); self.display_panel.hide()
            self.pause.show()
            self.prompt.hide()
            self.crosshair.hide()
            self.tv_focus_ui.hide()
            self._set_mouse_capture(False)
        else:
            self.pause.hide()
            if self.tv_focused:
                self.prompt.hide()
                self.crosshair.hide()
                self.tv_focus_ui.show()
                self.status.hide()
                self._set_mouse_capture(True)
            else:
                self.prompt.show()
                self.crosshair.show()
                self.tv_focus_ui.hide()
                self._set_mouse_capture(True)

    # ---------- gameplay ----------
    def _apply_camera(self):
        self.camera.setPos(self.player.x, self.player.y, self.player.z + self.eye_h)
        self.camera.setHpr(self.heading, self.pitch, 0)

    def _in_rect(self, x, y, rect, margin=0.0):
        x0, y0, x1, y1 = rect
        return x0 + margin <= x <= x1 - margin and y0 + margin <= y <= y1 - margin

    def _blocked(self, x: float, y: float) -> bool:
        r = self.PLAYER_RADIUS
        if self.forest_active:
            # Compact dream pocket: broad open clearing bounded by darkness.  Tree
            # trunks are physical only where they are actually visible.
            if not (-9.4 + r <= x <= 9.4 - r and -1.2 + r <= y <= 18.2 - r):
                return True
            for tx,ty,tr in self.forest_tree_blockers:
                if (x-tx)*(x-tx)+(y-ty)*(y-ty) <= (tr+r)*(tr+r):
                    return True
            return False
        if self.floor1_active:
            # Pass 85: room interiors and portal corridors share one continuous
            # navigation authority.  The old center +/- radius bridge left a 0.15 m
            # blocked strip on BOTH sides of every doorway because Floor-1 rooms are
            # separated by a 0.30 m partition gap.
            for room in self.floor1_rooms.values():
                x0,y0,x1,y1=map(float,room["rect"])
                if x0+r <= x <= x1-r and y0+r <= y <= y1-r:
                    return False
            clearance = 0.07
            for po in [q for q in self.layout["portals"] if q.get("level")=="floor1"]:
                px,py,_=map(float,po["center"]); half=float(po["width"])/2.0
                ra=self.floor1_rooms[po["rooms"][0]]["rect"]
                rb=self.floor1_rooms[po["rooms"][1]]["rect"]
                if po["axis"]=="x":
                    left,right=(ra,rb) if (ra[0]+ra[2]) < (rb[0]+rb[2]) else (rb,ra)
                    xlo=float(left[2])-r; xhi=float(right[0])+r
                    if xlo <= x <= xhi and py-half+clearance <= y <= py+half-clearance:
                        return False
                else:
                    south,north=(ra,rb) if (ra[1]+ra[3]) < (rb[1]+rb[3]) else (rb,ra)
                    ylo=float(south[3])-r; yhi=float(north[1])+r
                    if ylo <= y <= yhi and px-half+clearance <= x <= px+half-clearance:
                        return False
            return True
        if self.basement_active:
            for rect in self.basement_walk_rects:
                x0,y0,x1,y1=rect
                if x0+r <= x <= x1-r and y0+r <= y <= y1-r:
                    return False
            return True
        if self.attic_active:
            # Room rectangles plus three authored portal bridges form the entire attic navigation authority.
            for rect in self.attic_walk_rects:
                x0,y0,x1,y1=rect
                if x0+r <= x <= x1-r and y0+r <= y <= y1-r:
                    # pylon remains a physical support while the player works around it
                    if abs(x-self.attic_pylon_pos.x) <= 0.26+r and abs(y-self.attic_pylon_pos.y) <= 0.26+r:
                        return True
                    return False
            for po in [q for q in self.layout["portals"] if q["level"]=="attic"]:
                px,py,_=map(float,po["center"]); half=float(po["width"])/2.0
                if po["axis"]=="x":
                    if px-r <= x <= px+r and py-half+r*0.25 <= y <= py+half-r*0.25: return False
                else:
                    if py-r <= y <= py+r and px-half+r*0.25 <= x <= px+half-r*0.25: return False
            return True
        in_master = self._in_rect(x, y, self.room_rect, r)
        in_hall = self._in_rect(x, y, self.hall_rect, r)
        in_bath = self._in_rect(x, y, self.bath_rect, r)
        in_stair = self._in_rect(x, y, self.stair_rect, r)
        in_bed2 = self._in_rect(x, y, self.bed2_rect, r)
        in_bed3 = self._in_rect(x, y, self.bed3_rect, r)
        in_bed4 = self._in_rect(x, y, self.bed4_rect, r)

        def portal_bridge(portal, left_rect, right_rect):
            _, py, _ = portal["center"]
            half = float(portal["width"]) / 2.0
            return (left_rect[2] - r <= x <= right_rect[0] + r and py - half + r * 0.35 <= y <= py + half - r * 0.35)

        # Every reconstructed Floor 2 room connection is traversable by default.
        # Door leaves are presentation/state objects; they do not silently remove room access.
        in_master_portal = portal_bridge(self.master_portal, self.room_rect, self.hall_rect)
        in_bath_portal = portal_bridge(self.bath_portal, self.hall_rect, self.bath_rect)
        in_stair_portal = portal_bridge(self.stair_portal, self.hall_rect, self.stair_rect)
        in_bed2_portal = portal_bridge(self.bed2_portal, self.bed2_rect, self.hall_rect)
        in_bed3_portal = portal_bridge(self.bed3_portal, self.bed3_rect, self.hall_rect)
        in_bed4_portal = portal_bridge(self.bed4_portal, self.hall_rect, self.bed4_rect)
        # The only physical door is the Master Bedroom door. Once Task 06 closes it,
        # the doorway itself becomes solid instead of allowing the player to phase through the leaf.
        if self.tv_task_06.get("bedroom_door_closed") and in_master_portal:
            return True
        if not (in_master or in_hall or in_bath or in_stair or in_bed2 or in_bed3 or in_bed4 or in_master_portal or in_bath_portal or in_stair_portal or in_bed2_portal or in_bed3_portal or in_bed4_portal):
            return True

        # Accepted master-bedroom and bathroom fixture blockers.
        blockers = [
            (1.18, 2.42, 2.82, 4.58),
            (3.02, 0.98, 3.88, 1.72),
            (5.00, 0.90, 5.62, 1.82),
            self.bath_tub_blocker,
            self.bath_toilet_blocker,
            self.bath_vanity_blocker,
            # Bedroom 2 accepted twin-bed and desk footprints.
            (2.0 - 1.97/2, 6.22 - 1.02/2, 2.0 + 1.97/2, 6.22 + 1.02/2),
            (4.2 - 0.73/2, 5.3 - 0.50/2, 4.2 + 0.73/2, 5.3 + 0.50/2),
            # Bedroom 3 accepted twin-bed and dresser footprints.
            (2.0 - 1.97/2, 8.82 - 1.02/2, 2.0 + 1.97/2, 8.82 + 1.02/2),
            (4.95 - 0.55/2, 7.56 - 0.36/2, 4.95 + 0.55/2, 7.56 + 0.36/2),
            # Bedroom 4 accepted twin-bed and dresser footprints.
            (10.45 - 1.02/2, 8.17 - 1.97/2, 10.45 + 1.02/2, 8.17 + 1.97/2),
            (10.78 - 0.55/2, 5.78 - 0.36/2, 10.78 + 0.55/2, 5.78 + 0.36/2),
        ]
        for bx0, by0, bx1, by1 in blockers:
            if bx0 - r <= x <= bx1 + r and by0 - r <= y <= by1 + r:
                return True
        return False

    def _move_player_swept(self, delta: Vec3):
        """Move in short collision-tested slices so doorway corners cannot catch a long frame step.

        The navigation model is still the existing room/portal authority; this only prevents a
        0.1-0.2 m frame delta from jumping directly from one side of a narrow threshold shoulder
        to the other. Axis order follows the dominant component per slice so sliding remains
        symmetric for horizontal and vertical doorways.
        """
        distance = math.hypot(float(delta.x), float(delta.y))
        if distance <= 1e-8:
            return
        steps = max(1, int(math.ceil(distance / self.MOVE_COLLISION_STEP)))
        sx = float(delta.x) / steps
        sy = float(delta.y) / steps
        for _ in range(steps):
            if abs(sx) >= abs(sy):
                nx = self.player.x + sx
                if not self._blocked(nx, self.player.y):
                    self.player.x = nx
                ny = self.player.y + sy
                if not self._blocked(self.player.x, ny):
                    self.player.y = ny
            else:
                ny = self.player.y + sy
                if not self._blocked(self.player.x, ny):
                    self.player.y = ny
                nx = self.player.x + sx
                if not self._blocked(nx, self.player.y):
                    self.player.x = nx

    def _update(self, task):
        dt = min(globalClock.getDt(), 0.05)
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0:
                self.status["text"] = ""

        if not self.paused and not ARGS.test_shot and not ARGS.arm_test_shot and not self.tv_focused and not self.datamosh_active and not self.finale_active and not self.finale_finished:
            # Portable FPS mouse-look: confine the pointer, measure from window center, then recenter.
            # Panda3D 1.10 documents this as the portable replacement for M_relative.
            if hasattr(self.win, "hasPointer") and self.win.hasPointer(0):
                props = self.win.getProperties()
                cx = max(1, props.getXSize() // 2)
                cy = max(1, props.getYSize() // 2)
                md = self.win.getPointer(0)
                dx, dy = md.getX() - cx, md.getY() - cy
                if abs(dx) < 1000 and abs(dy) < 1000:
                    self.heading -= dx * self.mouse_sens
                    self.pitch = max(-82.0, min(82.0, self.pitch - dy * self.mouse_sens * self.mouse_invert))
                self.win.movePointer(0, cx, cy)

            forward = Vec3(-math.sin(math.radians(self.heading)), math.cos(math.radians(self.heading)), 0)
            right = Vec3(math.cos(math.radians(self.heading)), math.sin(math.radians(self.heading)), 0)
            move = Vec3(0, 0, 0)
            if self.keys["w"]: move += forward
            if self.keys["s"]: move -= forward
            if self.keys["d"]: move += right
            if self.keys["a"]: move -= right
            if self.note_intercept_active or (self.forest_active and self.forest_dialogue_stage in ("question", "yes_response", "punish")):
                move = Vec3(0, 0, 0)
            if move.lengthSquared() > 0:
                move.normalize()
                speed = self.SPRINT_SPEED if self.keys["shift"] else self.WALK_SPEED
                delta = move * speed * dt
                before = Vec3(self.player)
                self._move_player_swept(delta)
                moved = (self.player - before).length()
                if moved > 0.0001:
                    self.footstep_distance_accum += moved
                    step_distance = float(self.footstep_audio_config.get("sprint_step_distance" if self.keys["shift"] else "walk_step_distance", 0.68))
                    if self.footstep_distance_accum >= max(0.25, step_distance):
                        self.footstep_distance_accum %= max(0.25, step_distance)
                        self._play_footstep()
            else:
                self.footstep_distance_accum = min(self.footstep_distance_accum, 0.20)

        self._update_note_interception(dt)
        self._update_forest_encounter(dt)
        self._update_window_audio_events(dt)

        if self.basement_active:
            self._update_basement_loop()

        self.grain_accum += dt
        self._update_film_grain()

        # Cosmetic work is intentionally decoupled from render FPS. These rates are
        # above the perceptual needs of the individual effects while leaving input,
        # movement, camera and the Alternate animation at full frame rate. Upstairs-
        # only effects are skipped entirely while another floor is active.
        self.veil_update_accum += dt
        self.motion_update_accum += dt
        self.leak_update_accum += dt
        self.prompt_update_accum += dt
        upstairs_active = not self.floor1_active and not self.basement_active and not self.attic_active and not self.forest_active
        if not upstairs_active:
            # Do not accumulate seconds of cosmetic catch-up work while on another floor.
            self.veil_update_accum = min(self.veil_update_accum, 0.080)
            self.motion_update_accum = min(self.motion_update_accum, 0.067)
            self.leak_update_accum = min(self.leak_update_accum, 0.042)
        if upstairs_active and self.veil_update_accum >= 0.080:       # 12.5 Hz
            self.veil_update_accum %= 0.080
            self._update_distance_veils()
        if upstairs_active and self.motion_update_accum >= 0.067:     # ~15 Hz
            motion_dt = self.motion_update_accum
            self.motion_update_accum = 0.0
            self._update_environment_motion(motion_dt)
        if upstairs_active and self.leak_update_accum >= 0.042:       # ~24 Hz
            leak_dt = self.leak_update_accum
            self.leak_update_accum = 0.0
            self._update_water_leaks(leak_dt)
        self._update_alternate(dt)
        self._apply_camera()
        if self.prompt_update_accum >= 0.050:                         # 20 Hz
            self.prompt_update_accum %= 0.050
            self._update_prompt()
        return Task.cont

    def _nearest_target(self):
        if self.forest_active:
            targets=[]
            if self.forest_dialogue_stage is None and self.forest_task["state"] == "active":
                targets.append(("FOREST_ENTITY", self.forest_entity_pos + Vec3(0,0,1.30), 2.30))
            if self.forest_dialogue_stage is None and self.forest_task["state"] in ("active", "changed"):
                targets.append(("FOREST_DOOR", self.forest_door_pos + Vec3(0,0,1.05), 1.60))
        elif self.floor1_active:
            targets=[("FLOOR1_RETURN", self.floor1_return_pos, 1.45)]
            if self.tv_task_07["state"] == "active" and not self.tv_task_07["lamp_off"]:
                targets.append(("F1_LAMP", self.floor1_lamp_pos, 1.25))
            if self.tv_task_08["state"] == "active" and not self.tv_task_08["tap_off"]:
                targets.append(("F1_TAP", self.floor1_tap_pos, 1.25))
            if self.tv_task_09["state"] == "active" and not self.tv_task_09["chair_in"]:
                targets.append(("F1_CHAIR", self.floor1_chair_pos, 1.30))
            if self.tv_task_10["state"] == "active" and not self.tv_task_10["unlatched"]:
                targets.append(("F1_REAR_LATCH", self.floor1_rear_latch_pos, 1.35))
            if self.forest_task["state"] == "active":
                targets.append(("F1_REAR_DOOR", self.floor1_rear_latch_pos + Vec3(0,0,-0.40), 1.60))
            if self.basement_task["state"] == "active":
                targets.append(("BASEMENT_ENTRY", self.floor1_basement_pos, 1.45))
        elif self.basement_active:
            targets=[]
            if not self.basement_clue_found:
                targets.append(("BASEMENT_CLUE", self.basement_clue_pos, 1.20))
            targets.append(("BASEMENT_EXIT", self.basement_exit_pos, 1.65))
        elif self.attic_active:
            targets=[("ATTIC_EXIT", self.attic_entry_pos + Vec3(0,0,1.0), 1.40)]
            if self.attic_task["state"] == "active" and not self.attic_task["pylon_loosened"]:
                targets.append(("ATTIC_PYLON", self.attic_pylon_pos, 1.55))
        else:
            targets = [("TV", self.tv_pos, 1.55), ("CHAIR", self.chair_pos, 1.20)]
        if not self.floor1_active and not self.basement_active and not self.attic_active and self.tv_task["state"] == "active" and not self.tv_task["note_collected"]:
            targets.append(("TASK_NOTE", self.task_note_pos, 1.05))
        if not self.floor1_active and not self.basement_active and not self.attic_active and self.tv_task_02["state"] == "active" and not self.tv_task_02["frame_straightened"]:
            targets.append(("TASK_FRAME", self.task_frame_pos, 1.05))
        if not self.floor1_active and not self.basement_active and not self.attic_active and self.tv_task_03["state"] == "active" and not self.tv_task_03["window_covered"]:
            targets.append(("TASK_WINDOW", self.task_window_pos, 1.35))
        if not self.floor1_active and not self.basement_active and not self.attic_active and self.tv_task_04["state"] == "active" and not self.tv_task_04["mirror_covered"]:
            targets.append(("TASK_MIRROR", self.task_mirror_pos, 1.25))
        if not self.floor1_active and not self.basement_active and not self.attic_active and self.tv_task_05["state"] == "active" and not self.tv_task_05["phone_disconnected"]:
            targets.append(("TASK_PHONE", self.task_phone_pos, 1.20))
        if not self.floor1_active and not self.basement_active and not self.attic_active and self.tv_task_06["state"] == "active" and not self.tv_task_06["bedroom_door_closed"]:
            targets.append(("TASK_BEDROOM_DOOR", self.task_bedroom_door_pos, 1.45))
        if (not self.floor1_active and not self.basement_active and not self.attic_active and
                self.tv_task_06["state"] == "completed" and self.basement_task["state"] != "completed"):
            targets.append(("FLOOR1_ENTRY", self.task_bedroom_door_pos, 1.45))
        if (not self.floor1_active and not self.basement_active and not self.attic_active and
                self.basement_task["state"] == "completed" and
                self.attic_task["state"] in ("active", "loosened")):
            targets.append(("ATTIC_ENTRY", self.task_bedroom_door_pos, 1.45))
        cam = self.camera.getPos(self.render)
        h = math.radians(self.heading)
        fwd = Vec3(-math.sin(h), math.cos(h), 0)
        best = None
        sticky = None
        for name, pos, radius in targets:
            radius *= self.INTERACTION_RADIUS_SCALE
            flat = Vec3(pos.x - cam.x, pos.y - cam.y, 0)
            dist = flat.length()
            if dist <= radius and dist > 0.01:
                flat.normalize()
                facing = fwd.dot(flat)
                if name == self.prompt_target and facing > self.INTERACTION_STICKY_DOT:
                    sticky = (dist, name)
                if facing > self.INTERACTION_FACING_DOT:
                    if best is None or dist < best[0]:
                        best = (dist, name)
        # Mild hysteresis keeps a valid prompt from flickering off when the player
        # makes tiny mouse movements near the edge of an interaction target.
        if sticky is not None and (best is None or sticky[0] <= best[0] + 0.30):
            return sticky[1]
        return best[1] if best else None

    def _dream_link_indicator_active(self) -> bool:
        if not self.tv_focused or not self.tv_power:
            return False
        if self._tv_visual_data().get("id") != "dream":
            return False
        # A task interruption owns the channel while it is broadcasting; the bridge
        # indicator must never imply that T is available over an active task.
        if self.task_completion_broadcast_mode is not None and self.task_completion_broadcast_channel == self.tv_channel:
            return False
        if self.task_broadcast_mode is not None and self.task_broadcast_channel == self.tv_channel:
            return False
        return True

    def _prepare_dream_link(self):
        """Enter the packaged mode from the live TV DREAM channel."""
        if (self.paused or self.datamosh_active or self.finale_active or self.finale_finished
                or self.note_intercept_active or not self._dream_link_indicator_active()):
            return
        self.world_travel.go('andrews_nightmare')

    def _update_prompt(self):
        if self.paused:
            return
        if self.finale_active or self.finale_finished:
            self.prompt.hide(); self.tv_focus_ui.hide()
            return
        if self.tv_focused:
            self.prompt_target = "TV_FOCUS"
            ch = self._tv_channel_data()
            power = "ON" if self.tv_power else "OFF"
            if self.tv_task["state"] != "completed":
                task_text = {"unissued":"TASK WAITING","active":"TASK 01 ACTIVE","collected":"RETURN FOR ACK"}[self.tv_task["state"]]
            elif self.tv_task_02["state"] != "completed":
                task_text = {"locked":"TASK 01 COMPLETE","unissued":"TASK 02 READY","active":"TASK 02 ACTIVE","changed":"RETURN FOR ACK"}[self.tv_task_02["state"]]
            elif self.tv_task_03["state"] != "completed":
                task_text = {"locked":"TASK 02 COMPLETE","unissued":"TASK 03 READY","active":"TASK 03 ACTIVE","changed":"RETURN FOR ACK"}[self.tv_task_03["state"]]
            elif self.tv_task_04["state"] != "completed":
                task_text = {"locked":"TASK 03 COMPLETE","unissued":"TASK 04 READY","active":"TASK 04 ACTIVE","changed":"RETURN FOR ACK"}[self.tv_task_04["state"]]
            elif self.tv_task_05["state"] != "completed":
                task_text = {"locked":"TASK 04 COMPLETE","unissued":"TASK 05 READY","active":"TASK 05 ACTIVE","changed":"RETURN FOR ACK"}[self.tv_task_05["state"]]
            else:
                if self.tv_task_06["state"] != "completed":
                    task_text = {"locked":"TASK 05 COMPLETE","unissued":"TASK 06 READY","active":"TASK 06 ACTIVE","changed":"RETURN FOR ACK"}[self.tv_task_06["state"]]
                elif self.tv_task_07["state"] != "completed":
                    task_text = {"locked":"GO DOWNSTAIRS","unissued":"TASK 07 READY","active":"TASK 07 ACTIVE","changed":"RETURN FOR ACK"}[self.tv_task_07["state"]]
                elif self.tv_task_08["state"] != "completed":
                    task_text = {"locked":"TASK 07 COMPLETE","unissued":"TASK 08 READY","active":"TASK 08 ACTIVE","changed":"RETURN FOR ACK"}[self.tv_task_08["state"]]
                elif self.tv_task_09["state"] != "completed":
                    task_text = {"locked":"TASK 08 COMPLETE","unissued":"TASK 09 READY","active":"TASK 09 ACTIVE","changed":"RETURN FOR ACK"}[self.tv_task_09["state"]]
                elif self.tv_task_10["state"] != "completed":
                    task_text = {"locked":"TASK 09 COMPLETE","unissued":"TASK 10 READY","active":"TASK 10 ACTIVE","changed":"RETURN FOR ACK"}[self.tv_task_10["state"]]
                elif self.forest_task["state"] != "completed":
                    task_text = {"locked":"TASK 10 COMPLETE","unissued":"TASK 11 READY","active":"TASK 11 ACTIVE","changed":"RETURN FOR ACK"}[self.forest_task["state"]]
                elif self.basement_task["state"] != "completed":
                    task_text = {"locked":"TASK 11 COMPLETE","unissued":"BASEMENT READY","active":"BASEMENT TASK ACTIVE","changed":"RETURN FOR ACK"}[self.basement_task["state"]]
                else:
                    task_text = {"locked":"BASEMENT COMPLETE","unissued":"FINAL TASK READY","active":"FINAL TASK ACTIVE","loosened":"FINAL TASK IN PROGRESS","completed":"END"}[self.attic_task["state"]]
            if self.task_broadcast_mode is not None or self.task_completion_broadcast_mode is not None:
                if self.task_completion_broadcast_channel == self.tv_channel:
                    task_text = "TASK COMPLETE — SEARCH CHANNELS"
                elif self.task_broadcast_channel == self.tv_channel:
                    task_text = "BROADCAST FOUND"
                else:
                    task_text = "SEARCH CHANNELS"
            self.tv_focus_channel["text"] = f"CH {ch['index']:02d}   {ch['label']}"
            self.tv_focus_state["text"] = f"TV {power}   •   {task_text}"
            if self._dream_link_indicator_active():
                self.tv_focus_link["text"] = ("T  RETRY ANDREW'S NIGHTMARE"
                    if self.dream_link_prepare_state == "error" else "T  ENTER ANDREW'S NIGHTMARE")
                self.tv_focus_link.show()
            else:
                self.tv_focus_link.hide()
            self.tv_focus_ui.show()
            self.prompt.hide()
            self.status.hide()
            return
        self.tv_focus_link.hide()
        self.tv_focus_ui.hide()
        self.status.show()
        self.prompt_target = self._nearest_target()
        text = {
            "TV": "E  INSPECT TELEVISION",
            "CHAIR": "E  INSPECT CHAIR",
            "TASK_NOTE": "E  TAKE FOLDED NOTE",
            "TASK_FRAME": "E  STRAIGHTEN FRAME",
            "TASK_WINDOW": "E  COVER SOUTH WINDOW",
            "TASK_MIRROR": "E  COVER BATHROOM MIRROR",
            "TASK_PHONE": "E  DISCONNECT HALL PHONE",
            "TASK_BEDROOM_DOOR": "E  CLOSE BEDROOM DOOR",
            "FLOOR1_ENTRY": "E  DESCEND TO FLOOR 1",
            "FLOOR1_RETURN": "E  CLIMB STAIRS TO BEDROOM",
            "F1_LAMP": "E  TURN OFF LIVING ROOM LAMP",
            "F1_TAP": "E  TURN OFF KITCHEN TAP",
            "F1_CHAIR": "E  PUSH IN DINING CHAIR",
            "F1_REAR_LATCH": "E  UNLATCH REAR DOOR",
            "F1_REAR_DOOR": "E  OPEN REAR DOOR",
            "FOREST_ENTITY": "E  SPEAK",
            "FOREST_DOOR": "E  RETURN THROUGH DOOR",
            "BASEMENT_ENTRY": "E  DESCEND INTO BASEMENT",
            "BASEMENT_CLUE": "E  TAKE BASEMENT CLUE",
            "BASEMENT_EXIT": "E  CLIMB TO FLOOR 1",
            "ATTIC_ENTRY": "E  OPEN BEDROOM DOOR TO ATTIC",
            "ATTIC_EXIT": "E  RETURN THROUGH BEDROOM DOOR",
            "ATTIC_PYLON": "E  LOOSEN PYLON",
        }.get(self.prompt_target, "")
        self.prompt["text"] = text
        if text: self.prompt.show()
        else: self.prompt.hide()

    def _interact(self):
        if self.paused or self.datamosh_active or self.finale_active or self.finale_finished or self.note_intercept_active:
            return
        if self.tv_focused:
            self._leave_tv_focus()
            return
        target = self._nearest_target()
        if target in ("TV", "CHAIR"):
            self._enter_tv_focus(from_chair=(target == "CHAIR"))
        elif target == "TASK_NOTE":
            self._collect_first_task_note()
        elif target == "TASK_FRAME":
            self._straighten_second_task_frame()
        elif target == "TASK_WINDOW":
            self._cover_third_task_window()
        elif target == "TASK_MIRROR":
            self._cover_fourth_task_mirror()
        elif target == "TASK_PHONE":
            self._disconnect_fifth_task_phone()
        elif target == "TASK_BEDROOM_DOOR":
            self._close_sixth_task_bedroom_door()
        elif target == "FLOOR1_ENTRY":
            self._enter_floor1()
        elif target == "FLOOR1_RETURN":
            self._leave_floor1()
        elif target == "F1_LAMP":
            self._floor1_lamp_off()
        elif target == "F1_TAP":
            self._floor1_tap_off()
        elif target == "F1_CHAIR":
            self._floor1_chair_in()
        elif target == "F1_REAR_LATCH":
            self._floor1_rear_door_unlatch()
        elif target == "F1_REAR_DOOR":
            self._enter_forest()
        elif target == "FOREST_ENTITY":
            self._forest_start_question()
        elif target == "FOREST_DOOR":
            self._leave_forest()
        elif target == "BASEMENT_ENTRY":
            self._enter_basement()
        elif target == "BASEMENT_CLUE":
            self._collect_basement_clue()
        elif target == "BASEMENT_EXIT":
            self._leave_basement()
        elif target == "ATTIC_ENTRY":
            self._enter_attic()
        elif target == "ATTIC_EXIT":
            self._leave_attic()
        elif target == "ATTIC_PYLON":
            self._loosen_attic_pylon()

    def _enter_tv_focus(self, from_chair: bool = False):
        if self.tv_focused:
            return
        self._focus_restore = (Vec3(self.player), float(self.heading), float(self.pitch), float(self.eye_h), float(self.camLens.getHfov()))
        self.tv_focused = True
        for k in self.keys:
            self.keys[k] = False
        # Both interaction anchors settle into the accepted chair-facing-TV composition.
        self.player = Vec3(3.55, 1.35, self.floor_z)
        self.eye_h = 1.18
        self.heading = -90.0
        self.pitch = -8.0
        self.camLens.setFov(58)
        self._apply_camera()
        # Pass 87 input authority: TV focus is keyboard-driven, not a mouse menu.
        # Keep the cursor confined/hidden so entering TV focus does not create an
        # unexplained desktop-pointer mode change. Mouse-look remains suspended
        # because _update() already excludes tv_focused.
        self._set_mouse_capture(True)
        self.crosshair.hide()
        self.prompt.hide()
        self.status.hide()
        self.tv_focus_from_chair = bool(from_chair)
        if self.tv_focus_from_chair:
            self.tv_sit_count += 1
            # Every chair sit has a quiet presence behind it.  It waits there while
            # the player watches the TV, then remains briefly after standing so a
            # turn of the head can reveal it.  Every third sit is head-only.
            if self.alt_state != "hidden":
                self._hide_alternate()
            self.alt_forced_visibility_mode = "head_only" if (self.tv_sit_count % 3 == 0) else "full"
            self.alt_hidden_timer = 0.55
        self._sync_tv_channel_audio()
        self._emit_alternate_voice_event(
            "tv_focus",
            prior_shutdowns=int(self.entity_memory.get("observed_tv_shutdowns_total", 0)),
            reset_cycles=int(self.entity_memory.get("completed_reset_cycles", 0)),
        )
        if self.tv_task["state"] == "unissued":
            self._issue_first_tv_task()
        elif self.tv_task["state"] == "collected":
            self._acknowledge_first_tv_task()
        elif self.tv_task["state"] == "active":
            self._set_task_broadcast("issue")
            self._render_tv_frame(force=True)
        elif self.tv_task["state"] == "completed":
            if self.tv_task_02["state"] == "unissued":
                self._issue_second_tv_task()
            elif self.tv_task_02["state"] == "changed":
                self._acknowledge_second_tv_task()
            elif self.tv_task_02["state"] == "active":
                self._set_task_broadcast("issue2")
                self._render_tv_frame(force=True)
            elif self.tv_task_02["state"] == "completed":
                if self.tv_task_03["state"] == "unissued":
                    self._issue_third_tv_task()
                elif self.tv_task_03["state"] == "changed":
                    self._acknowledge_third_tv_task()
                elif self.tv_task_03["state"] == "active":
                    self._set_task_broadcast("issue3")
                    self._render_tv_frame(force=True)
                elif self.tv_task_03["state"] == "completed":
                    if self.tv_task_04["state"] == "unissued":
                        self._issue_fourth_tv_task()
                    elif self.tv_task_04["state"] == "changed":
                        self._acknowledge_fourth_tv_task()
                    elif self.tv_task_04["state"] == "active":
                        self._set_task_broadcast("issue4")
                        self._render_tv_frame(force=True)
                    elif self.tv_task_04["state"] == "completed":
                        if self.tv_task_05["state"] == "unissued":
                            self._issue_fifth_tv_task()
                        elif self.tv_task_05["state"] == "changed":
                            self._acknowledge_fifth_tv_task()
                        elif self.tv_task_05["state"] == "active":
                            self._set_task_broadcast("issue5")
                            self._render_tv_frame(force=True)
                        elif self.tv_task_05["state"] == "completed":
                            if self.tv_task_06["state"] == "unissued":
                                self._issue_sixth_tv_task()
                            elif self.tv_task_06["state"] == "changed":
                                self._acknowledge_sixth_tv_task()
                            elif self.tv_task_06["state"] == "active":
                                self._set_task_broadcast("issue6")
                                self._render_tv_frame(force=True)
                            elif self.tv_task_06["state"] == "completed":
                                if self.tv_task_07["state"] == "unissued":
                                    self._issue_floor1_task(7)
                                elif self.tv_task_07["state"] == "changed":
                                    self._ack_floor1_task(7)
                                elif self.tv_task_07["state"] == "active":
                                    self._set_task_broadcast("issue7"); self._render_tv_frame(force=True)
                                elif self.tv_task_07["state"] == "completed":
                                    if self.tv_task_08["state"] == "unissued":
                                        self._issue_floor1_task(8)
                                    elif self.tv_task_08["state"] == "changed":
                                        self._ack_floor1_task(8)
                                    elif self.tv_task_08["state"] == "active":
                                        self._set_task_broadcast("issue8"); self._render_tv_frame(force=True)
                                    elif self.tv_task_08["state"] == "completed":
                                        if self.tv_task_09["state"] == "unissued":
                                            self._issue_floor1_task(9)
                                        elif self.tv_task_09["state"] == "changed":
                                            self._ack_floor1_task(9)
                                        elif self.tv_task_09["state"] == "active":
                                            self._set_task_broadcast("issue9"); self._render_tv_frame(force=True)
                                        elif self.tv_task_09["state"] == "completed":
                                            if self.tv_task_10["state"] == "unissued":
                                                self._issue_floor1_task(10)
                                            elif self.tv_task_10["state"] == "changed":
                                                self._ack_floor1_task(10)
                                            elif self.tv_task_10["state"] == "active":
                                                self._set_task_broadcast("issue10"); self._render_tv_frame(force=True)
                                            elif self.tv_task_10["state"] == "completed":
                                                if self.forest_task["state"] == "unissued":
                                                    self._issue_forest_task()
                                                elif self.forest_task["state"] == "changed":
                                                    self._ack_forest_task()
                                                elif self.forest_task["state"] == "active":
                                                    self._set_task_broadcast("issue11"); self._render_tv_frame(force=True)
                                                elif self.forest_task["state"] == "completed":
                                                    if self.basement_task["state"] == "unissued":
                                                        self._issue_basement_task()
                                                    elif self.basement_task["state"] == "active":
                                                        self._set_task_broadcast("issue12"); self._render_tv_frame(force=True)
                                                    elif self.basement_task["state"] == "completed":
                                                        if self.attic_task["state"] == "unissued":
                                                            self._issue_attic_final_task()
                                                        elif self.attic_task["state"] in ("active","loosened"):
                                                            self._set_task_broadcast("issue13"); self._render_tv_frame(force=True)
                                                else:
                                                    self._set_task_broadcast("complete10"); self._render_tv_frame(force=True)
                                            else:
                                                self._set_task_broadcast("complete9"); self._render_tv_frame(force=True)
                                        else:
                                            self._set_task_broadcast("complete8"); self._render_tv_frame(force=True)
                                    else:
                                        self._set_task_broadcast("complete7"); self._render_tv_frame(force=True)
                                else:
                                    self._set_task_broadcast("complete6"); self._render_tv_frame(force=True)
                            else:
                                self._set_task_broadcast("complete5")
                                self._render_tv_frame(force=True)
                        else:
                            self._set_task_broadcast("complete4")
                            self._render_tv_frame(force=True)
                    else:
                        self._set_task_broadcast("complete3")
                        self._render_tv_frame(force=True)
                else:
                    self._set_task_broadcast("complete2")
                    self._render_tv_frame(force=True)
            else:
                self._set_task_broadcast("complete")
                self._render_tv_frame(force=True)
        self._update_prompt()

    def _leave_tv_focus(self):
        if not self.tv_focused:
            return
        self.tv_focused = False
        if self.alt_state == "active" and self.alt_anchor is not None and self.alt_anchor.get("id") == "chair_spy_anchor":
            self.alt_local_time = 0.0
            self.alt_seen_accum = 0.0
        self._sync_tv_channel_audio()
        if self._focus_restore is not None:
            pos, heading, pitch, eye_h, hfov = self._focus_restore
            self.player = Vec3(pos)
            self.heading = heading
            self.pitch = pitch
            self.eye_h = eye_h
            self.camLens.setFov(hfov)
        self._focus_restore = None
        if self.tv_task["state"] == "completed" and self.tv_task_02["state"] == "locked":
            self._unlock_second_tv_task()
        elif self.tv_task_02["state"] == "completed" and self.tv_task_03["state"] == "locked":
            self._unlock_third_tv_task()
        elif self.tv_task_03["state"] == "completed" and self.tv_task_04["state"] == "locked":
            self._unlock_fourth_tv_task()
        elif self.tv_task_04["state"] == "completed" and self.tv_task_05["state"] == "locked":
            self._unlock_fifth_tv_task()
        elif self.tv_task_05["state"] == "completed" and self.tv_task_06["state"] == "locked":
            self._unlock_sixth_tv_task()
        elif self.tv_task_06["state"] == "completed" and self.tv_task_07["state"] == "locked":
            self.tv_task_07["state"]="unissued"
        elif self.tv_task_07["state"] == "completed" and self.tv_task_08["state"] == "locked":
            self.tv_task_08["state"]="unissued"
        elif self.tv_task_08["state"] == "completed" and self.tv_task_09["state"] == "locked":
            self.tv_task_09["state"]="unissued"
        elif self.tv_task_09["state"] == "completed" and self.tv_task_10["state"] == "locked":
            self.tv_task_10["state"]="unissued"
        elif self.tv_task_10["state"] == "completed" and self.forest_task["state"] == "locked":
            self.forest_task["state"]="unissued"
        elif self.forest_task["state"] == "completed" and self.basement_task["state"] == "locked":
            self.basement_task["state"]="unissued"
        # Standing restores ordinary programming.  The obsolete completion notice
        # is discarded, while the already-active next task remains assigned.
        self.task_completion_broadcast_mode=None
        self.task_completion_broadcast_channel=None
        self._render_tv_frame(force=True)
        # Pass 29 continuity repair: standing up from the chair must not erase
        # the current TV-off escalation. The third shutdown/reset owns the
        # deliberate clearing of these run-scoped states.
        self.tv_focus_ui.hide()
        self.crosshair.show()
        self._set_mouse_capture(True)
        self._apply_camera()

    def _choose_task_broadcast_channel(self) -> int:
        """Choose one stable task channel while avoiding obvious repetition.

        The player must search: the current channel is excluded when possible, as
        are the last three task channels. Assignment remains fixed until the task
        mode advances, so the broadcast never moves while the player is looking.
        """
        count = len(self.tv_authority["channels"])
        # DREAM is a playable mode entry; task broadcasts must not hide it.
        all_channels = [ch for ch in range(1, count + 1)
                        if self.tv_authority['channels'][ch - 1]['id'] != 'dream']
        recent = set(self.task_broadcast_history[-3:])
        completion_ch=int(self.task_completion_broadcast_channel or 0)
        candidates = [ch for ch in all_channels if ch != int(self.tv_channel) and ch != completion_ch and ch not in recent]
        if not candidates:
            candidates = [ch for ch in all_channels if ch != int(self.tv_channel) and ch != completion_ch] or all_channels
        chosen = int(self.task_broadcast_rng.choice(candidates))
        self.task_broadcast_history.append(chosen)
        if len(self.task_broadcast_history) > 8:
            del self.task_broadcast_history[:-8]
        return chosen

    def _preserve_completion_and_issue_next(self, completion_mode: str, issue_next):
        """Keep the completion notice on its old channel while the next task goes live now.

        This removes the Pass 83 stand/sit dependency.  The player can read
        "FIND NEXT BROADCAST", start channel-surfing immediately, and discover the
        already-active next instruction without leaving TV focus.
        """
        self.task_completion_broadcast_mode=str(completion_mode)
        self.task_completion_broadcast_channel=self.task_broadcast_channel
        issue_next()
        self.tv_frame_counter=0; self.tv_refresh_accum=999.0
        self._render_tv_frame(force=True)

    def _issue_next_after_completion(self, taskno: int):
        if taskno == 1:
            self._unlock_second_tv_task(); self._issue_second_tv_task()
        elif taskno == 2:
            self._unlock_third_tv_task(); self._issue_third_tv_task()
        elif taskno == 3:
            self._unlock_fourth_tv_task(); self._issue_fourth_tv_task()
        elif taskno == 4:
            self._unlock_fifth_tv_task(); self._issue_fifth_tv_task()
        elif taskno == 5:
            self._unlock_sixth_tv_task(); self._issue_sixth_tv_task()
        elif taskno == 6:
            if self.tv_task_07["state"] == "locked": self.tv_task_07["state"]="unissued"
            self._issue_floor1_task(7)
        elif taskno == 7:
            # Pass 85: sink task is retired; go directly to the dining task.
            if self.tv_task_09["state"] == "locked": self.tv_task_09["state"]="unissued"
            self._issue_floor1_task(9)
        elif taskno == 8:
            # Compatibility only: old state that somehow reaches 08 also advances.
            if self.tv_task_09["state"] == "locked": self.tv_task_09["state"]="unissued"
            self._issue_floor1_task(9)
        elif taskno == 9:
            if self.tv_task_10["state"] == "locked": self.tv_task_10["state"]="unissued"
            self._issue_floor1_task(10)
        elif taskno == 10:
            if self.forest_task["state"] == "locked": self.forest_task["state"]="unissued"
            self._issue_forest_task()
        elif taskno == 11:
            if self.basement_task["state"] == "locked": self.basement_task["state"]="unissued"
            self._issue_basement_task()

    def _set_task_broadcast(self, mode: str):
        """Assign task interruptions to a stable random channel.

        Issue screens choose a new channel and keep it fixed until the task state
        advances. A just-finished task may keep a separate completion notice on its
        old channel while the next issue is already live elsewhere. Standing up
        restores ordinary programming; sitting back down restores only the active task.
        """
        mode = str(mode)
        previous_mode = self.task_broadcast_mode
        is_completion = mode.startswith("complete")
        same_mode = (previous_mode == mode and self.task_broadcast_channel is not None)
        if not same_mode:
            # Completion belongs to the task channel already discovered. New issue
            # modes receive a new random channel that is not the channel in view.
            if not is_completion or self.task_broadcast_channel is None:
                self.task_broadcast_channel = self._choose_task_broadcast_channel()
        self.task_broadcast_mode = mode
        self._emit_alternate_voice_event(
            "task_broadcast",
            task_mode=mode,
            tv_channel=int(self.task_broadcast_channel or self.tv_channel),
            reset_cycles=int(self.entity_memory.get("completed_reset_cycles", 0)),
        )

    def _tv_channel_data(self):
        return self.tv_authority["channels"][self.tv_channel - 1]

    def _tv_visual_data(self):
        return self.tv_visuals["channels"][self.tv_channel - 1]

    def _tv_channel_step(self, step: int):
        if self.paused or self.datamosh_active or not self.tv_focused:
            return
        count = len(self.tv_authority["channels"])
        self.tv_channel = ((self.tv_channel - 1 + int(step)) % count) + 1
        self.tv_frame_counter = 0
        self.tv_refresh_accum = 999.0
        self._sync_tv_channel_audio()
        self._render_tv_frame(force=True)
        self._update_prompt()

    def _remember_tv_shutdown(self, cycle_shutdown_index: int):
        """Record only facts the entity directly observed.

        Memory survives the house reset, while run-scoped warning geometry and
        the current shutdown counter remain resettable. This method deliberately
        stores no interpretation of why the player acted.
        """
        self.entity_memory["observed_tv_shutdowns_total"] += 1
        facts = self.entity_memory["facts"]
        if cycle_shutdown_index >= 1:
            facts["first_tv_shutdown_observed"] = True
        if cycle_shutdown_index >= 2:
            facts["second_tv_shutdown_observed"] = True
        if cycle_shutdown_index >= 3:
            facts["third_tv_shutdown_observed"] = True

    def entity_memory_snapshot(self):
        """Return a detached QA-safe snapshot of approved persistent facts."""
        return json.loads(json.dumps(self.entity_memory))

    def _tv_power_toggle(self):
        if self.paused or self.datamosh_active or not self.tv_focused:
            return
        was_on = self.tv_power
        self.tv_power = not self.tv_power
        if was_on and not self.tv_power:
            self.tv_shutdown_count += 1
            self._remember_tv_shutdown(self.tv_shutdown_count)
            if self.tv_shutdown_count == 1:
                self._arm_first_tv_off_warning()
            elif self.tv_shutdown_count == 2:
                self._arm_second_tv_off_warning()
            elif self.tv_shutdown_count == 3:
                self._arm_third_shutdown_reset()
        self.tv_frame_counter = 0
        self.tv_refresh_accum = 999.0
        self._sync_tv_channel_audio()
        self._render_tv_frame(force=True)
        self._update_prompt()

    def _build_tv_authored_base(self, visual, w, h, bg, mid, bright, frame):
        """Render every declared Pass-17 channel family instead of falling back to generic snow."""
        family = visual["visual_family"]
        seed = int(visual["render_seed"])
        p = visual.get("parameters", {})
        base = [[bg for _ in range(w)] for _ in range(h)]

        def put(x, y, value=bright):
            x, y = int(round(x)), int(round(y))
            if 0 <= x < w and 0 <= y < h:
                base[y][x] = max(base[y][x], value)
        def rect(x0,y0,x1,y1,value=mid,fill=False):
            x0,x1=sorted((int(x0),int(x1))); y0,y1=sorted((int(y0),int(y1)))
            if fill:
                for yy in range(max(0,y0),min(h,y1+1)):
                    for xx in range(max(0,x0),min(w,x1+1)): put(xx,yy,value)
            else:
                for xx in range(x0,x1+1): put(xx,y0,value); put(xx,y1,value)
                for yy in range(y0,y1+1): put(x0,yy,value); put(x1,yy,value)
        def line(x0,y0,x1,y1,value=bright):
            x0=float(x0); y0=float(y0); x1=float(x1); y1=float(y1)
            n=max(1,int(max(abs(x1-x0),abs(y1-y0))))
            for i in range(n+1):
                t=i/n; put(x0+(x1-x0)*t,y0+(y1-y0)*t,value)
        def circle(cx,cy,r,value=bright):
            for deg in range(0,360,3):
                a=math.radians(deg); put(cx+math.cos(a)*r,cy+math.sin(a)*r,value)
        def disk(cx,cy,r,value=mid):
            rr=int(r)
            for yy in range(int(cy)-rr,int(cy)+rr+1):
                dx=int(math.sqrt(max(0,r*r-(yy-cy)*(yy-cy)))) if abs(yy-cy)<=r else 0
                for xx in range(int(cx)-dx,int(cx)+dx+1): put(xx,yy,value)
        def stick(x,y,scale=1.0,phase=0.0,value=bright):
            bob=math.sin(frame*0.55+phase)*2
            y+=bob; circle(x,y-10*scale,3*scale,value); line(x,y-7*scale,x,y+8*scale,value)
            line(x,y-2*scale,x-6*scale,y+3*scale,value); line(x,y-2*scale,x+6*scale,y+3*scale,value)
            line(x,y+8*scale,x-5*scale,y+16*scale,value); line(x,y+8*scale,x+5*scale,y+16*scale,value)

        if family == "surveillance_grid":
            for x in range(0,w,40): line(x,0,x,h-1,mid)
            for y in range(0,h,30): line(0,y,w-1,y,mid)
            line(w//2-7,h//2,w//2+7,h//2,bright); line(w//2,h//2-7,w//2,h//2+7,bright)
            rect(8,8,50,31,mid); rect(91,62,151,109,mid)
        elif family == "broadcast_lower_third":
            rect(14,18,65,70,mid,True); circle(39,39,12,bright)
            rect(74,20,148,67,mid); rect(0,84,w-1,h-1,bright,True)
            for x in range((-frame*4)%32,w,32): rect(x,93,min(w-1,x+18),101,bg,True)
        elif family == "rubberhose_face":
            for i in range(8):
                a=math.radians(i*45+frame*3); line(80,58,80+55*math.cos(a),58+45*math.sin(a),mid)
            disk(80,58,34,mid); circle(80,58,34,bright)
            eye_dx=13+int(math.sin(frame*.5)*2)
            disk(80-eye_dx,50,5,bg); disk(80+eye_dx,50,5,bg)
            line(61,72,70,78,bg); line(70,78,89,78,bg); line(89,78,99,70,bg)
        elif family == "film_leader":
            circle(80,60,34,bright); circle(80,60,22,mid); circle(80,60,8,bright)
            line(80,18,80,102,mid); line(38,60,122,60,mid)
            wedge=(frame//3)%4; line(80,60,80+33*math.cos(wedge*math.pi/2),60+33*math.sin(wedge*math.pi/2),bright)
            for x in range(6,w,24): rect(x,6,x+9,12,mid,True); rect(x,107,x+9,113,mid,True)
        elif family == "versus_silhouettes":
            line(0,93,w-1,93,mid); stick(43,68,1.4,0,bright); stick(117,68,1.4,2,bright)
            rect(10,8,68,14,mid,True); rect(92,8,150,14,mid,True); line(78,12,82,28,bright)
            for i in range(6):
                a=i*math.pi/3+frame*.2; line(80,64,80+18*math.cos(a),64+18*math.sin(a),mid)
        elif family == "oscillating_figures":
            for y in range(87,h,8): line(0,y,w-1,y,mid)
            for x in range(0,w,26): line(x,87,80,58,mid)
            for i,x in enumerate((43,80,117)): stick(x,64,1.1,i*2.1,bright)
            for i in range(5): rect(15+i*27,12,27+i*27,12+int(8+10*(1+math.sin(frame*.5+i))),mid,True)
        elif family == "soft_horizon":
            rect(0,74,w-1,h-1,mid,True); disk(118,29,12,bright)
            for i in range(5):
                y=82+i*7+int(math.sin(frame*.25+i)*2); line(10,y,150,y,bright if i%2==0 else bg)
            for x in range(w):
                y=70+int(5*math.sin(x*.07+frame*.12)); put(x,y,bright)
        elif family == "alert_bands":
            for i in range(5): rect(0,i*24,w-1,i*24+9,bright if (i+frame//2)%2 else mid,True)
            rect(34,37,126,84,bg,True); rect(34,37,126,84,bright)
            for i in range(6):
                x=43+i*13; line(x,52,x+7,60,mid); line(x+7,60,x,68,mid)
        elif family == "city_scale":
            heights=[32,45,26,61,38,52,29]
            for i,hh in enumerate(heights): rect(6+i*21,92-hh,22+i*21,92,mid,True)
            # huge creature silhouette
            disk(90,37,12,bright); rect(80,46,102,91,bright,True); line(81,55,60,83,bright); line(101,55,126,77,bright)
            line(0,93,w-1,93,bright)
        elif family == "scoreboard":
            rect(11,12,149,108,mid); rect(18,18,142,36,bright,True)
            for y in (48,63,78,93): line(18,y,142,y,mid)
            for x in (58,100): line(x,42,x,101,mid)
            for i in range(4): rect(22,51+i*15,43,58+i*15,bright if i==(frame//4)%4 else mid,True)
        elif family == "split_montage":
            rect(5,5,76,56,mid); rect(84,5,154,56,bright); rect(5,64,76,114,bright); rect(84,64,154,114,mid)
            for i in range(3): line(0,25+i*34,159,5+i*41,bright)
            for i in range(8):
                x=(seed+i*31+frame*3)%150; y=(seed//3+i*17)%110; rect(x,y,min(159,x+7),min(119,y+5),bright if i%2 else mid,True)
        elif family == "signal_duel":
            for x in range(w):
                y1=42+int(14*math.sin(x*.10+frame*.35)); y2=78+int(14*math.sin(x*.13-frame*.29+1.7))
                put(x,y1,bright); put(x,y2,mid)
            line(80,18,80,103,bright)
            for i in range(9):
                a=i*.7+frame*.2; line(80,60,80+20*math.cos(a),60+20*math.sin(a),bright)
        elif family == "pirate_broadcast":
            line(0,85,w-1,85,mid); disk(80,48,20,mid); circle(80,48,20,bright)
            # skull + crossbones
            disk(73,44,4,bg); disk(87,44,4,bg); rect(74,57,86,62,bg,True)
            line(55,67,105,30,bright); line(55,30,105,67,bright)
            line(16,85,16,26,bright); line(16,26,52,38,mid); line(52,38,16,49,mid)
            for i in range(5): rect(122+i*5,76-i*7,124+i*5,85,bright,True)
        elif family == "road_perspective":
            vx,vy=p.get("vanish",[80,38]); line(18,119,vx,vy,bright); line(142,119,vx,vy,bright)
            for i in range(1,7):
                t=(i+((frame%8)/8.0))/7.0; y=int(vy+(119-vy)*(t*t)); half=int(4+32*t); line(vx-half,y,vx+half,y,mid)
            for i,x in enumerate((55,82,108)): rect(x,82+i*5,x+10,93+i*5,bright,True)
        elif family == "concentric_symbol":
            for r in (12,24,36,48): circle(80,60,r,bright if r in (24,48) else mid)
            for i in range(7):
                a=i*2*math.pi/7+frame*.03; line(80,60,80+48*math.cos(a),60+48*math.sin(a),mid)
            for i in range(5): disk(43+i*18,106,2,bright)
        elif family == "catalog_grid":
            for r in range(2):
                for c in range(3):
                    x=9+c*50; y=12+r*49; rect(x,y,x+42,y+37,mid); disk(x+21,y+16,8,bright); rect(x+7,y+29,x+35,y+34,bright if (r*3+c)==(frame//6)%6 else mid,True)
            rect(0,106,w-1,119,bright,True)
        elif family == "studio_field":
            rect(7,8,58,57,mid,True); circle(32,29,10,bright); rect(65,8,153,79,mid)
            for y in range(18,75,12): line(70,y,148,y,bright)
            rect(103,84,154,103,bright,True); rect(8,88,76,110,mid)
        elif family == "field_overhead":
            rect(14,12,146,108,mid); line(80,12,80,108,bright); circle(80,60,18,bright)
            rect(14,39,31,81,bright); rect(129,39,146,81,bright)
            for i in range(10):
                x=36+((i*23+frame*(1 if i%2 else -1))%88); y=27+((i*17)%66); disk(x,y,2,bright if i%2 else mid)
            disk(92+int(math.sin(frame*.4)*8),61,2,bright)
        elif family == "snow":
            for y in range(h):
                for x in range(w):
                    n=(x*73+y*151+seed*17+frame*199)%1000
                    if n<280: base[y][x]=bright if n<85 else mid
            for i in range(3):
                y=(seed+i*31+frame*5)%h; rect(0,y,w-1,min(h-1,y+2),bg,True)
        elif family == "single_camera":
            rect(8,8,151,110,mid); rect(64,30,111,101,bright); rect(71,39,104,94,bg,True)
            x=45+int(math.sin(frame*.28)*25); disk(x,73,3,bright); line(x-7,73,x+7,73,bright); line(x,66,x,80,bright)
            rect(10,10,43,20,bright,True)
        elif family == "teletext_grid":
            rect(0,0,w-1,14,bright,True)
            for row in range(8):
                y=20+row*11
                for col in range(20):
                    if ((row*23+col*11+seed)//7)%5 in (0,1): rect(4+col*7,y,9+col*7,y+6,mid if row%2 else bright,True)
        elif family == "tunnel_vanish":
            vx,vy=p.get("vanish",[80,55])
            for i in range(7):
                scale=(i+1)/7; hw=int(7+70*scale); hh=int(5+52*scale); rect(vx-hw,vy-hh,vx+hw,vy+hh,bright if i%2 else mid)
            line(vx,vy,14,119,mid); line(vx,vy,146,119,mid)
            for i in range(5): disk(35+i*23,18+int(math.sin(frame*.2+i)*3),2,bright)
        elif family == "weather_map":
            # map-like land masses + fronts/isobars
            pts=[(23,32),(42,21),(66,31),(58,49),(77,58),(57,75),(29,68)]
            for a,b in zip(pts,pts[1:]+pts[:1]): line(*a,*b,mid)
            for r in (14,24,34):
                for deg in range(200,345,4):
                    a=math.radians(deg+frame*.3); put(106+math.cos(a)*r,64+math.sin(a)*r,bright)
            for i in range(3): rect(9+i*48,93,43+i*48,108,bright if i==frame//6%3 else mid,True)
        elif family == "forest_horizon":
            line(0,87,w-1,87,mid)
            for i in range(11):
                x=7+i*14; hh=20+((i*19+seed)%35); line(x,87,x,87-hh,bright); line(x,87-hh,x-7,87-hh+14,mid); line(x,87-hh,x+7,87-hh+14,mid)
            line(80,119,72,87,bright); line(80,119,89,87,bright)
            for x in range(w): put(x,66+int(5*math.sin(x*.08+seed)),mid)
        elif family == "ring_camera":
            rect(25,45,135,100,bright); rect(30,50,130,95,mid)
            for y in (57,65,73): line(25,y,135,y,mid)
            for x in (25,135): line(x,42,x,105,bright)
            stick(62,72,.9,0,bright); stick(99,72,.9,2,bright)
            rect(0,101,w-1,119,mid,True)
        else:
            # Fail visibly rather than pretending an unknown family is implemented.
            for i in range(0,w,8): line(i,0,w-1-i,h-1,bright if (i//8)%2 else mid)
            rect(4,4,w-5,h-5,bright)
        return base

    def _active_archive_lore_fragment(self):
        """Return the first currently unlocked DreamCatcher archive fragment.

        Lore is deliberately tied to proven player progression rather than random
        exposition. Pass 100 exposes only fragment 01 after Task 01 is complete.
        """
        fragments = self.dreamcatcher_lore.get("fragments", [])
        for frag in fragments:
            unlock = str(frag.get("unlock", ""))
            if unlock == "after_task_01" and self.tv_task.get("state") == "completed":
                return frag
        return None

    def _render_archive_lore_overlay(self, image):
        if self._tv_visual_data().get("id") != "archive":
            return False
        frag = self._active_archive_lore_fragment()
        if not frag:
            return False
        # Keep it inside the CRT signal itself: no HUD panel and no modern UI.
        w, h = image.getXSize(), image.getYSize()
        for y in range(16, h-16):
            for x in range(12, w-12):
                current = image.getGray(x, y)
                image.setGray(x, y, current * 0.34)
        lines = list(frag.get("lines", []))[:4]
        start_y = max(20, 38 - (len(lines)-1)*3)
        for i, line in enumerate(lines):
            self._draw_task_line(image, str(line).upper(), start_y + i*18, scale=1, value=0.78 if i == 0 else 0.66)
        # Fine archival dropout so the record still belongs to the analog signal.
        seed = int(self.tv_frame_counter) + 71
        for i in range(22):
            x=(seed*17+i*29)%w; y=(seed*11+i*13)%h
            if 10 <= x < w-10 and 12 <= y < h-12:
                image.setGray(x,y,0.08 if i%3 else 0.88)
        return True

    def _colorize_dream_link_signal(self, gray_image):
        """Convert only the normal DREAM program to restrained color.

        Task broadcasts remain grayscale because they return before this stage.
        This is the sole colored TV program and therefore the visual bridge marker.
        """
        w, h = gray_image.getXSize(), gray_image.getYSize()
        out = PNMImage(w, h, 3)
        frame = int(self.tv_frame_counter)
        for y in range(h):
            for x in range(w):
                v = max(0.0, min(1.0, gray_image.getGray(x, y)))
                # Dark teal/cyan foundation with restrained violet contamination.
                phase = 0.5 + 0.5 * math.sin(x * 0.045 + y * 0.018 + frame * 0.11)
                r = min(1.0, v * (0.30 + 0.20 * phase))
                g = min(1.0, v * (0.82 + 0.10 * (1.0 - phase)))
                b = min(1.0, v * (0.88 + 0.12 * phase))
                # Bright signal points pick up a faint magenta edge, keeping the
                # channel uncanny rather than turning it into a saturated rainbow.
                if v > 0.68:
                    lift = (v - 0.68) * 0.50
                    r = min(1.0, r + lift)
                    b = min(1.0, b + lift * 0.55)
                out.setXel(x, y, r, g, b)
        return out

    def _render_tv_frame(self, force: bool = False):
        w, h = self.tv_authority["screen"]["internal_resolution"]
        image = PNMImage(w, h, 1)
        if not self.tv_power:
            off = self.tv_authority["screen"]["screen_value_off"] / 255.0
            image.fill(off)
            self.tv_texture.load(image)
            return

        if (self.tv_focused and self.task_completion_broadcast_mode is not None and
                self.task_completion_broadcast_channel == self.tv_channel):
            active_mode=self.task_broadcast_mode
            self.task_broadcast_mode=self.task_completion_broadcast_mode
            self._render_task_broadcast(image)
            self.task_broadcast_mode=active_mode
            self.tv_texture.load(image)
            return
        if (self.tv_focused and self.task_broadcast_mode is not None and
                self.task_broadcast_channel == self.tv_channel):
            self._render_task_broadcast(image)
            self.tv_texture.load(image)
            return

        visual = self._tv_visual_data()
        pal = visual["palette"]
        bg = (pal["background"] / 255.0) * 0.55
        mid = min(0.68, (pal["mid"] / 255.0) * 1.08)
        bright = max(pal["bright"] / 255.0, self.tv_authority["screen"]["screen_value_on"] / 255.0)
        seed = int(visual["render_seed"])
        frame = self.tv_frame_counter
        family = visual["visual_family"]
        profile = self.crt_profile

        # Build the declared authored channel family first; the CRT stage below
        # then applies the shared analog treatment without erasing channel identity.
        base = self._build_tv_authored_base(visual, w, h, bg, mid, bright, frame)

        # Analog CRT stage. All pseudo-randomness is integer/seed derived so the
        # same channel/frame produces the same pixels during regression tests.
        tear_center = (seed + frame * profile["tear_speed_rows_per_frame"]) % h
        tear_half = max(1, int(profile["tear_band_height_px"]) // 2)
        snow_families = set(profile["strong_snow_families"])
        strong_snow = family in snow_families or visual.get("id") in profile.get("strong_snow_channel_ids", [])
        noise_threshold = int(profile["strong_noise_per_1000"] if strong_snow else profile["base_noise_per_1000"])

        for y in range(h):
            # Slow line timing drift plus one moving sync-tear band.
            drift = int(round(math.sin((y * 0.19) + frame * 0.37 + seed * 0.001) * profile["line_drift_px"]))
            if abs(y - tear_center) <= tear_half:
                drift += profile["tear_offset_px"]
            for x in range(w):
                sx = (x + drift) % w
                v = base[y][sx]

                # Mild one-pixel ghost from the previous horizontal sample.
                if profile["ghost_mix"] > 0:
                    prev = base[y][(sx - profile["ghost_offset_px"]) % w]
                    v = v * (1.0 - profile["ghost_mix"]) + prev * profile["ghost_mix"]

                # Deterministic RF/snow noise; intentionally stronger on static-like channels.
                n = (x * 73 + y * 151 + seed * 17 + frame * 199) % 1000
                if n < noise_threshold:
                    nv = ((x * 29 + y * 47 + seed + frame * 61) % 256) / 255.0
                    v = v * (1.0 - profile["noise_mix"]) + nv * profile["noise_mix"]

                # Scanlines remain visible but bounded.
                if visual.get("scanlines") and y % self.tv_authority["screen"]["scanline_step_px"] == 0:
                    v *= profile["scanline_multiplier"]

                # Rounded CRT face approximation: darken edges/corners without hiding content.
                nx = abs((x + 0.5) / w * 2.0 - 1.0)
                ny = abs((y + 0.5) / h * 2.0 - 1.0)
                edge = max(nx ** profile["edge_power"], ny ** profile["edge_power"])
                corner = (nx * ny) ** profile["corner_power"]
                v *= 1.0 - profile["edge_darkening"] * edge - profile["corner_darkening"] * corner

                # Faint vertical retrace band gives motion even on simple still layouts.
                retrace_x = (frame * profile["retrace_speed_px_per_frame"] + seed) % w
                if abs(x - retrace_x) <= profile["retrace_half_width_px"]:
                    v = min(1.0, v + profile["retrace_lift"])

                image.setGray(x, y, max(0.0, min(1.0, v)))

        self._render_archive_lore_overlay(image)
        if visual.get("id") == "dream":
            image = self._colorize_dream_link_signal(image)
        self.tv_texture.load(image)

    def _tv_runtime(self, task):
        # CRT motion does not need an every-frame polling task. Panda3D's do-later
        # queue wakes this only at the authored signal rate, reducing main-loop work.
        self.tv_frame_counter += 1
        self._render_tv_frame()
        hz = max(1, int(self._tv_visual_data()["motion_contract"]["update_hz"]))
        task.delayTime = 1.0 / hz
        return Task.again


    def _capture_bridge_prepare_test_shot(self, task):
        self.test_shot_frame += 1
        if self.test_shot_frame < 5:
            return Task.cont
        self.tv_focused=True; self.tv_power=True; self.tv_channel=7
        self.task_broadcast_mode=None; self.task_completion_broadcast_mode=None
        self.task_broadcast_channel=None; self.task_completion_broadcast_channel=None
        self.dream_link_prepare_state="idle"; self.dream_link_last_handoff=None
        self.tv_frame_counter=11
        self._render_tv_frame(force=True); self._update_prompt()
        self.player=Vec3(3.55,1.35,self.floor_z); self.eye_h=1.18; self.heading=-90.0; self.pitch=-8.0
        self._apply_camera(); self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
        out=Path(ARGS.bridge_prepare_test_shot).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
        ok=self.win.saveScreenshot(panda_filename(out))
        h=self.dream_link_last_handoff or {}
        print(f"PASS103_BRIDGE_STATE={self.dream_link_prepare_state} DEST={h.get('destination')} REASON={h.get('reason')}")
        print(f"TEST_SHOT={'PASS' if ok else 'FAIL'} path={out}")
        self.userExit(); return Task.done

    def _capture_bridge_channel_test_shot(self, task):
        self.test_shot_frame += 1
        if self.test_shot_frame < 5:
            return Task.cont
        self.tv_focused=True; self.tv_power=True; self.tv_channel=7
        self.task_broadcast_mode=None; self.task_completion_broadcast_mode=None
        self.task_broadcast_channel=None; self.task_completion_broadcast_channel=None
        self.tv_frame_counter=11
        self._render_tv_frame(force=True); self._update_prompt()
        self.player=Vec3(3.55,1.35,self.floor_z); self.eye_h=1.18; self.heading=-90.0; self.pitch=-8.0
        self._apply_camera(); self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
        out=Path(ARGS.bridge_channel_test_shot).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
        ok=self.win.saveScreenshot(panda_filename(out))
        print(f"PASS102_DREAM_CHANNEL={self._tv_visual_data().get('id')} LINK_INDICATOR={self._dream_link_indicator_active()}")
        print(f"TEST_SHOT={'PASS' if ok else 'FAIL'} path={out}")
        self.userExit(); return Task.done

    def _capture_lore_test_shot(self, task):
        self.test_shot_frame += 1
        if self.test_shot_frame < 5:
            return Task.cont
        self.tv_focused=True; self.tv_power=True; self.tv_channel=4
        self.tv_task.update({"state":"completed","note_collected":True})
        self.task_broadcast_mode=None; self.task_completion_broadcast_mode=None
        self.tv_frame_counter=3; self._render_tv_frame(force=True)
        # Use the ordinary TV-focus QA camera so the proof is the in-world CRT,
        # not a synthetic texture dump.
        self.player=Vec3(3.55,1.35,self.floor_z); self.eye_h=1.18; self.heading=-90.0; self.pitch=-8.0
        self._apply_camera(); self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
        out=Path(ARGS.lore_test_shot).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
        ok=self.win.saveScreenshot(panda_filename(out))
        frag=self._active_archive_lore_fragment()
        print(f"PASS100_ARCHIVE_FRAGMENT={frag.get('id') if frag else None} CHANNEL={self.tv_channel}")
        print(f"TEST_SHOT={'PASS' if ok else 'FAIL'} path={out}")
        self.userExit(); return Task.done

    def _capture_finale_test_shot(self, task):
        self.test_shot_frame += 1
        if self.test_shot_frame < 5:
            return Task.cont
        self.tv_focused=False; self.floor1_active=False; self.basement_active=False; self.attic_active=True
        self.attic_root.show(); self.scene_root.show(); self.forest_root.hide()
        self.player=Vec3(self.attic_pylon_pos.x, self.attic_pylon_pos.y-1.7, self.attic_z)
        self.eye_h=1.62; self.heading=0.0; self.pitch=5.0
        self._apply_camera(); self._hide_alternate(hard=True)
        self.attic_task.update({"state":"loosened","pylon_loosened":True})
        self._start_attic_finale()
        # Pose the finale at the void/hand convergence point without waiting in real time.
        self.finale_elapsed=6.05
        self._attic_finale_runtime(task)
        self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
        out=Path(ARGS.finale_test_shot).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
        ok=self.win.saveScreenshot(panda_filename(out))
        print(f"PASS98_HAND_VISIBLE={not self.giant_hand_root.isHidden()} PYLON_R={self.attic_pylon_root.getR():.2f}")
        print(f"PASS98_FINALE_TEXT={self.finale_subtitle['text']!r}")
        print(f"TEST_SHOT={'PASS' if ok else 'FAIL'} path={out}")
        self.userExit(); return Task.done

    def _capture_manifest_test_shot(self, task):
        self.test_shot_frame += 1
        if self.test_shot_frame < 5:
            return Task.cont
        self.floor1_active=False; self.basement_active=False; self.attic_active=False
        self.player=Vec3(3.55,1.35,self.floor_z); self.eye_h=1.18; self.heading=-90.0; self.pitch=-8.0
        self._apply_camera(); self._hide_alternate()
        self.tv_focused=True; self.tv_focus_from_chair=True; self.tv_sit_count=3
        self.alt_forced_visibility_mode="head_only"
        self._manifest_alternate()
        anchor=Vec3(self.alt_anchor["pos"]); head=anchor+Vec3(0,0,2.45)
        # Pose the actual manifestation once before moving the QA camera; ordinary
        # gameplay does this from _update_alternate every frame.
        self.alternate_visual.setPos(anchor)
        self.alternate_eye_overlay_root.setPos(anchor)
        # Step forward from the chair and turn back for direct proof of the actual
        # chair-spy anchor.  This is only the QA camera; gameplay placement is unchanged.
        proof_cam=anchor + Vec3(3.25, 2.45, 1.68)
        self.camera.setPos(proof_cam)
        self.alternate_visual.lookAt(proof_cam)
        self.alternate_visual.setH(self.alternate_visual.getH()+180.0)
        self.alternate_eye_overlay_root.setHpr(self.alternate_visual.getH(),self.alternate_visual.getP(),self.alternate_visual.getR())
        self.camera.lookAt(head)
        self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
        out=Path(ARGS.manifest_test_shot).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
        ok=self.win.saveScreenshot(panda_filename(out))
        visible_body=[]
        for child in self.alternate_visual.getChildren():
            if not child.isHidden(): visible_body.append(child.getName())
        print(f"PASS96_CHAIR_ANCHOR={self.alt_anchor.get('id')} MODE={self.alt_visibility_mode} SIT_COUNT={self.tv_sit_count}")
        print(f"PASS96_VISIBLE_BODY={visible_body}")
        print(f"PASS96_BEHIND_CHAIR_DISTANCE={(anchor-self.player).length():.2f}")
        print(f"TEST_SHOT={'PASS' if ok else 'FAIL'} path={out}")
        self.userExit(); return Task.done

    def _capture_forest_test_shot(self,task):
        self.test_shot_frame += 1
        if self.test_shot_frame < 5: return Task.cont
        self.tv_focused=False; self.floor1_active=True; self.basement_active=False; self.attic_active=False
        self.tv_task_10.update({"state":"completed","unlatched":True})
        self.forest_task.update({"state":"active","choice":None,"completion_count":0})
        self._enter_forest(); self.player=Vec3(0,5.0,0); self.heading=0; self.pitch=-3
        self._apply_camera(); self._forest_start_question(); self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
        out=Path(ARGS.forest_test_shot).resolve(); out.parent.mkdir(parents=True,exist_ok=True); ok=self.win.saveScreenshot(panda_filename(out))
        print(f"PASS90_FOREST_ACTIVE={self.forest_active} TASK={self.forest_task['state']} HOUSE_HIDDEN={self.scene_root.isHidden()} QUESTION={self.forest_dialogue_stage}")
        print(f"PASS90_FOREST_ENTITY_POS={tuple(round(v,2) for v in self.forest_entity_pos)} TREES={len(self.forest_tree_blockers)} SCREENSHOT={ok}")
        self.userExit(); return Task.done

    def _capture_broadcast_test_shot(self, task):
        self.test_shot_frame += 1
        if self.test_shot_frame < 5:
            return Task.cont
        self.tv_focused=False; self.floor1_active=False; self.basement_active=False; self.attic_active=False
        self.tv_channel=1
        self.tv_task.update({"state":"unissued","note_collected":False})
        self.task_broadcast_mode=None; self.task_broadcast_channel=None
        self.task_completion_broadcast_mode=None; self.task_completion_broadcast_channel=None
        self.task_broadcast_history.clear()
        self.player=Vec3(3.55,1.35,self.floor_z); self.eye_h=1.18; self.heading=-90.0; self.pitch=-8.0
        self._apply_camera(); self._hide_alternate(hard=True)
        self._enter_tv_focus()
        tv_capture_requested=bool(getattr(self, "mouse_capture_requested", False))
        issue_channel=int(self.task_broadcast_channel or 0)
        stable_before=issue_channel
        self._set_task_broadcast("issue")
        stable_after=int(self.task_broadcast_channel or 0)
        self._set_task_broadcast("complete")
        complete_channel=int(self.task_broadcast_channel or 0)
        # Show the actual hijacked channel in the screenshot.
        self.tv_channel=complete_channel
        self._sync_tv_channel_audio(); self._render_tv_frame(force=True); self._update_prompt()
        self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
        out=Path(ARGS.broadcast_test_shot).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
        ok=self.win.saveScreenshot(panda_filename(out))
        self._leave_tv_focus()
        preserved_after_stand=(self.task_broadcast_channel==complete_channel and self.task_broadcast_mode=="complete")
        print(f"PASS83_ISSUE_CHANNEL={issue_channel} START_CHANNEL=1 SEARCH_REQUIRED={issue_channel != 1}")
        print(f"PASS83_STABLE_ASSIGNMENT={stable_before == stable_after}")
        print(f"PASS83_COMPLETION_SAME_CHANNEL={complete_channel == issue_channel}")
        print(f"PASS83_STAND_RESTORES_PROGRAM={not self.tv_focused and preserved_after_stand}")
        print(f"PASS87_TV_MOUSE_CAPTURE={tv_capture_requested}")
        print(f"TEST_SHOT={'PASS' if ok else 'FAIL'} path={out}")
        self.userExit(); return Task.done

    def _capture_arm_test_shot(self, task):
        self.test_shot_frame += 1
        if self.test_shot_frame < 5:
            return Task.cont
        # Put the camera in the bathroom and pose the real procedural arm deep into
        # the corridor route. This is presentation proof, not synthetic replacement geometry.
        self.tv_focused=False; self.floor1_active=False; self.basement_active=False; self.attic_active=False
        self.player=Vec3(7.55,3.05,self.floor_z); self.eye_h=1.62; self.camLens.setFov(72)
        self.heading=0.0; self.pitch=-2.0
        self._apply_camera(); self._hide_alternate(hard=True)
        self.tv_task.update({"state":"intercepting","note_collected":True})
        self.task_note_root.hide()
        self.note_intercept_active=True; self.note_intercept_elapsed=4.70
        self.note_read_overlay.hide()
        self._pose_note_interception_arm(0.66)
        self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
        out=Path(ARGS.arm_test_shot).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
        ok=self.win.saveScreenshot(panda_filename(out))
        print(f"PASS82_BODY_OUT_OF_BOUNDS={self.note_intercept_body_origin.x > 11.5}")
        print(f"PASS82_ROUTE_VALID={self.note_intercept_route_valid}")
        print(f"PASS84_CONTINUOUS_TUBE={not self.note_intercept_tube_np.isEmpty()} SAMPLES={len(self.note_intercept_samples)} SIDES={self.note_intercept_tube_sides}")
        print(f"TEST_SHOT={'PASS' if ok else 'FAIL'} path={out}")
        self.userExit(); return Task.done

    def _capture_test_shot(self, task):
        self.test_shot_frame += 1
        if self.test_shot_frame < 5:
            return Task.cont
        # Pass 78 proof: exercise the real TV progression handoff from a completed
        # basement task into the newly issued final attic task.
        self.tv_focused=False; self.floor1_active=False; self.basement_active=False; self.attic_active=False
        self.tv_task["state"]="completed"
        for obj in (self.tv_task_02,self.tv_task_03,self.tv_task_04,self.tv_task_05,self.tv_task_06,
                    self.tv_task_07,self.tv_task_08,self.tv_task_09,self.tv_task_10):
            obj["state"]="completed"
        self.forest_task.update({"state":"completed","choice":True,"completion_count":1})
        self.basement_task["state"]="completed"
        self.attic_task.update({"state":"unissued", "pylon_loosened":False})
        self.player=Vec3(3.55,1.35,self.floor_z); self.eye_h=1.62; self.camLens.setFov(72)
        self.heading=-90.0; self.pitch=-2.0
        self._hide_alternate(hard=True)
        self._apply_camera()
        self._enter_tv_focus()
        self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
        out=Path(ARGS.test_shot).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
        ok=self.win.saveScreenshot(panda_filename(out))
        print(f"PASS78_FINAL_TASK_STATE={self.attic_task['state']} BROADCAST={self.task_broadcast_mode}")
        print(f"TEST_SHOT={'PASS' if ok else 'FAIL'} path={out}")
        self.userExit(); return Task.done



# Internal compatibility alias for existing regression tools; not a player-facing project name.
LockedHouseGame = DreamCatcherAlternateGame

if __name__ == "__main__":
    game = None
    try:
        game = DreamCatcherAlternateGame()
        game.run()
    except SystemExit:
        if game is not None:
            try:
                game._runtime_cleanup()
            except Exception:
                pass
        raise
    except BaseException as exc:
        if game is not None:
            try:
                game._runtime_cleanup()
            except Exception:
                pass
        _write_crash_log(exc)
        _append_runtime_log(f"CRASH {type(exc).__name__}: {exc}")
        print("DreamCatcher Alternate failed to start or crashed.", file=sys.stderr)
        print(f"Crash log: {LOG_DIR}", file=sys.stderr)
        raise
