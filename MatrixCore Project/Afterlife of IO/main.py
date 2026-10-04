from __future__ import annotations

"""Afterlife of IO — current authoritative runtime.

Native startup safeguards descend from the Pass 35 runtime foundation; current gameplay and presentation authority is defined by the later pass contracts in DESIGN_AUTHORITY.md.

The authored PNG stack is the world.  Number 0 is closest to the camera.
Files containing ``walk`` define complete free-roam walkable regions. Actors
render in an invisible band immediately in front of their active walk layer and
behind the next smaller-number structure layer. Every 3930×1130 art layer
uses the same camera rectangle so the Paint.NET composition cannot tear into slabs.
Paint.NET PATH marks are authoring guides only; they are not rails.
"""

import math
import os
import re
import sys
import traceback
import json
import random
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

# Pass 31 bootstrap diagnostics are intentionally standard-library only.  They
# start before pygame/SDL is imported, because an import-time or native backend
# failure happens too early for the normal in-game crash handler to observe it.
_EARLY_LOG_HANDLE = None

def _early_diagnostic_dir() -> Path:
    candidates = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "GLITCHED MATRIX" / "Afterlife of IO")
    candidates.append(Path(__file__).resolve().parent / "saves")
    try:
        import tempfile
        candidates.append(Path(tempfile.gettempdir()) / "GLITCHED_MATRIX" / "Afterlife of IO")
    except Exception:
        pass
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_probe"
            probe.write_text("ok", encoding="ascii")
            probe.unlink(missing_ok=True)
            return candidate
        except Exception:
            continue
    return Path.cwd()

def _early_log(message: str) -> None:
    global _EARLY_LOG_HANDLE
    try:
        if _EARLY_LOG_HANDLE is None:
            path = _early_diagnostic_dir() / "startup.log"
            _EARLY_LOG_HANDLE = path.open("a", encoding="utf-8", buffering=1)
        stamp = datetime.now().isoformat(timespec="seconds")
        _EARLY_LOG_HANDLE.write(f"[{stamp}] {message}\n")
        _EARLY_LOG_HANDLE.flush()
    except Exception:
        pass

_early_log(f"BOOT begin executable={sys.executable!r} python={sys.version.split()[0]} platform={sys.platform} cwd={os.getcwd()!r}")
try:
    import faulthandler
    if _EARLY_LOG_HANDLE is not None:
        faulthandler.enable(file=_EARLY_LOG_HANDLE, all_threads=True)
        _early_log("BOOT faulthandler enabled before pygame import")
except Exception as exc:
    _early_log(f"BOOT faulthandler unavailable: {type(exc).__name__}: {exc}")

from build_info import DISPLAY_TITLE
import mode_host
import holoverse_link  # HoloVerse Dimension Archive link (stdlib only)

try:
    import pygame
    _early_log(f"BOOT pygame import PASS version={getattr(getattr(pygame, 'version', None), 'ver', 'unknown')}")
except BaseException as exc:
    _early_log(f"BOOT pygame import FAIL {type(exc).__name__}: {exc}")
    print("Afterlife of IO requires pygame-ce 2.5+ (or pygame 2.5+).")
    print("Install with: pip install pygame-ce")
    print("Import error:", exc)
    raise SystemExit(2)

from battle_core import (
    FIRST_WITNESS_MAX_PRESENCE,
    FIRST_WITNESS_MAX_RESOLVE,
    ROOTED_CROWN_ID,
    ROOTED_CROWN_MAX_PRESENCE,
    ROOTED_CROWN_MAX_RESOLVE,
    VEIL_WARDEN_ID,
    VEIL_WARDEN_MAX_PRESENCE,
    VEIL_WARDEN_MAX_RESOLVE,
    first_witness_move,
    resolve_first_witness_response,
    rooted_crown_move,
    resolve_rooted_crown_response,
    veil_warden_move,
    resolve_veil_warden_response,
    echo_challenge_tier,
    echo_challenge_presence,
    echo_challenge_damage_bonus,
    ARCHIVE_CHORUS_ID,
    HOLLOW_ENGINE_ID,
    LAST_CARTOGRAPHER_ID,
    FINAL_GUARDIAN_ID,
    ARCHIVE_CHORUS_MAX_PRESENCE,
    HOLLOW_ENGINE_MAX_PRESENCE,
    LAST_CARTOGRAPHER_MAX_PRESENCE,
    FINAL_GUARDIAN_MAX_PRESENCE,
    GENERIC_GUARDIAN_MAX_RESOLVE,
    archive_chorus_move,
    hollow_engine_move,
    last_cartographer_move,
    final_guardian_move,
    resolve_archive_chorus_response,
    resolve_hollow_engine_response,
    resolve_last_cartographer_response,
    resolve_final_guardian_response,
    final_guardian_limits,
)
from progression_core import (
    CAUSAL_RESONANCE_ABILITY,
    VEIL_WARD_ABILITY,
    LANTERN_PROJECTION_ABILITY,
    REMOTE_RESONANCE_ABILITY,
    ENTROPY_ARC_ABILITY,
    PROJECTION_LANCE_ABILITY,
    LANTERN_PROJECTION_MAX_LEVEL,
    REMOTE_RESONANCE_UNLOCK_WINS,
    REMOTE_RESONANCE_DEEP_WINS,
    ENTROPY_ARC_UNLOCK_WINS,
    ENTROPY_ARC_MASTERY_WINS,
    PROJECTION_LANCE_UPGRADE_WINS,
    PROJECTION_LANCE_MASTERY_WINS,
    lantern_projection_duration,
    remote_resonance_level,
    remote_resonance_range_scale,
    entropy_arc_level,
    entropy_arc_damage,
    projection_lance_level,
    projection_lance_stats,
    FUTURE_CLUE_ID,
    causal_resonance_band,
    normalize_progression_state,
    learned_ability_ids,
    temporal_departure_state,
    temporal_return_candidate,
)
from lore_core import (
    DEBRIS_STORY_SEED,
    FIRST_WITNESS_ECHO_IDS,
    FIRST_WITNESS_STORY_ARC,
    LORE_RECORDS,
    LoreRecord,
    first_witness_story_complete,
    lore_record_available,
    normalize_lore_progression,
    resonance_cooldown as resonance_cooldown_seconds,
)
from story_core import (
    FIRST_RECONSTRUCTION_ID,
    ROOTED_RECONSTRUCTION_ID,
    VEIL_RESONANCE_ID,
    GATE_FIRST_ACK_ID,
    GATE_ROOTED_ACK_ID,
    GATE_VEIL_ACK_ID,
    ENTROPY_MISSION_ID,
    ARCHIVE_DENSITY_ID,
    HOLOVERSE_SEED_ID,
    VEIL_WARDEN_REVELATION_ID,
    normalize_story_moments,
    story_pages,
)
from machine_core import (
    DEFAULT_MACHINE_COST,
    DEFAULT_MACHINE_WORLD_HEIGHT,
    DEFAULT_MACHINE_TOUCH_RADIUS_RATIO,
    MAX_MACHINE_PLACEMENTS,
    MAX_MACHINE_STACK,
    ROLE_CORE,
    ROLE_GEAR,
    ROLE_PIVOT,
    ROLE_FAN,
    ROLE_PIPE,
    ROLE_FRAME,
    ROLE_COSMETIC,
    ROLE_HEAD,
    ROLE_ACTUATOR,
    ROLE_SENSOR,
    ROLE_TOOL,
    PIPE_ENDPOINT_OFFSET_WORLD,
    PIPE_BRACE_ATTACH_RADIUS_WORLD,
    PIPE_END_LEFT,
    PIPE_END_RIGHT,
    PIPE_BRACE_ROLES,
    normalize_pipe_end,
    opposite_pipe_end,
    pipe_endpoints,
    pipe_pose_between,
    clamp_bits,
    clamp_machine_stack,
    sanitize_machine_inventory,
    add_machine_item,
    consume_machine_item,
    victory_bits,
    defeat_bits_loss,
    migrated_legacy_bits,
    normalize_machine_role,
    autonomous_motion_requirements,
    resolve_machine_network,
    sanitize_machine_placements,
)

from controller_core import (
    ControllerContext,
    DEFAULT_DEADZONE as CONTROLLER_DEADZONE,
    CURSOR_SPEED as CONTROLLER_CURSOR_SPEED,
    button_action as controller_button_action,
    controller_help_lines,
    radial_deadzone,
)

ROOT = Path(__file__).resolve().parent
LAYERS_DIR = ROOT / "assets" / "source" / "layers"
DERIVED_DIR = ROOT / "assets" / "derived"
AUDIO_DIR = ROOT / "assets" / "audio" / "ambient_music"
SFX_DIR = ROOT / "assets" / "audio" / "sfx"
VARIANTS_DIR = ROOT / "assets" / "current" / "variants"
MENU_ASSET_DIR = ROOT / "assets" / "current" / "menu"
STORY_ASSET_DIR = ROOT / "assets" / "current" / "story"
WORLD_FX_ASSET_DIR = ROOT / "assets" / "current" / "world_fx"
MACHINE_ASSET_DIR = ROOT / "assets" / "current" / "machines"
MACHINE_VARIANTS_DIR = VARIANTS_DIR / "machines"
MACHINE_VARIANTS_CATALOG_PATH = MACHINE_VARIANTS_DIR / "catalog.json"
PERMANENT_CORE_PART_KEY = "core_housing"
PERMANENT_CORE_ID = 900001
PERMANENT_CORE_WORLD = "b"
PERMANENT_CORE_WALK_LAYER = 1
PERMANENT_CORE_POS = (2780.0, 734.0)
MACHINE_CATALOG_PATH = MACHINE_ASSET_DIR / "catalog.json"
MENU_FONT_DIR = MENU_ASSET_DIR / "fonts"
HUD_ASSET_DIR = ROOT / "assets" / "current" / "hud"
WORLD_VARIANTS_DIR = VARIANTS_DIR / "world"
BATTLE_VARIANTS_DIR = VARIANTS_DIR / "battle"
WEATHER_VARIANTS_DIR = VARIANTS_DIR / "weather"
TRANSITION_VARIANTS_DIR = VARIANTS_DIR / "transitions"
LEGACY_DEBRIS_DIR = ROOT / "assets" / "source" / "debris"
DRONE_ASSET_DIR = ROOT / "assets" / "source" / "drones"
PLAYER_DRONE_ASSET = DRONE_ASSET_DIR / "player_drone.png"
# Pass 91: drones are the active visual authority and may also serve as broken,
# dormant remains, or mechanical fragments.  A legacy debris folder remains optional for older
# packs; loaders merge/fallback without requiring duplicate artwork.
SHARED_FRAGMENT_DIRS = (DRONE_ASSET_DIR, LEGACY_DEBRIS_DIR)
# Pass 92: cache one mirrored copy per active drone image so left-facing patrols
# do not allocate a new transformed Surface every rendered frame.
_DRONE_FACING_CACHE: dict[tuple[int, bool], pygame.Surface] = {}

# Pass 130: presentation identity stays atmospheric by default, while players
# can switch to a clean text treatment and reduce non-gameplay motion/flashes.
_UI_TEXT_STYLE = "worn"
_PRESENTATION_MOTION_SCALE = 1.0
_PRESENTATION_FLASH_SCALE = 1.0
_UI_TEXT_CACHE: dict[tuple[int, str, tuple[int, int, int], str], pygame.Surface] = {}
_HUD_ASSETS: dict[str, pygame.Surface] = {}

W, H = 1280, 720
# Pass 60 promotes 1920x1080 to the default presentation target while keeping
# the proven 1280x720 gameplay coordinate/collision authority intact.
PRESENTATION_TARGET = (1920, 1080)
DEFAULT_WINDOW = PRESENTATION_TARGET
MIN_WINDOW = (1280, 720)
FPS = 60
WORLD_SIZE = (3930, 1130)

# Camera is intentionally close.  A small actor against almost-four-thousand
# pixels of authored scenery makes the environment read as monumental.
DEFAULT_ZOOM = 1.62
# Players may tighten the authored framing, but can never expose more of the
# world than the accepted default composition.
MIN_ZOOM = DEFAULT_ZOOM
MAX_ZOOM = 1.96
ZOOM_STEP = 0.06

# Image order is front -> back.  Values are easy to tune later in the editor.
PARALLAX_BY_NUMBER = {
    # Screenshot authority: the artwork is already pre-composed.  Parallax is
    # deliberately subtle so the numbered planes never tear apart visually.
    0: 1.03,
    1: 1.015,
    2: 1.00,
    3: 0.985,
    4: 0.97,
    5: 0.00,
}

WORLD_BACKDROP = {
    "a": (18, 21, 25),
    "b": (10, 12, 15),  # intentionally darker, no radial light yet
}

WORLD_BRIGHTNESS = {"a": 1.0, "b": 0.72}

# Paint.NET screenshot authority.  The red START labels and green PATH guides
# in the user screenshot establish the intended entry points for World A.
# Coordinates are mapped back onto the authored 3930x1130 canvas.
SCREENSHOT_SPAWNS = {
    ("a", 2): (180.0, 300.0),
    ("a", 4): (36.0, 768.0),
}

PLAYER_SCALE = 0.32
WALK_SPEED = 190.0
SPRINT_SPEED = 278.0
PRESENT_MOVEMENT_MULTIPLIER = 0.84
PRESENT_IO_SHADE_MULTIPLY = (205, 205, 212, 255)
MOVE_ACCEL = 1550.0
MOVE_DECEL = 1900.0
ALPHA_THRESHOLD = 70
WALKABLE_TOLERANCE = 5
# A small ground footprint prevents the sprite from clipping through the edge of
# a walk region while still allowing the whole hand-authored area to be explored.
PLAYER_FOOTPRINT = ((0, 0), (-8, 0), (8, 0), (-5, -4), (5, -4), (0, 4))
DEPTH_SWITCH_COOLDOWN = 0.16
RECOVERY_RADIUS = 28
CAMERA_LOOKAHEAD = 0.20
HOP_DURATION = 0.48
HOP_HEIGHT = 20.0
WORLD_A_START = (180.0, 286.0)
# Pass 138: New Game has its own explicit Present spawn authority.  This
# point is on the authored 4awalk plane and is intentionally separate from
# temporal-return, portal, route-transfer, and save/load coordinates.
PRESENT_NEW_GAME_START = (219.0, 294.0)
PRESENT_NEW_GAME_WALK_LAYER = 4
WORLD_A_END = (36.0, 768.0)
# Present-world restoration: keep the authored World A stack intact. 2awalk and
# 4awalk remain ordinary authored walk planes in one shared 3930x1130 scene,
# using the established walk-layer handoff instead of detached-location routing.
PRESENT_PRIMARY_WALK_LAYER = 2
END_RADIUS = 46.0
WORLD_B_ENTRY_HINT = (180.0, 760.0)
FUTURE_CLUE_POS = WORLD_A_END
FUTURE_CLUE_INTERACT_RADIUS = 88.0
# Pass 83: nudge the Future Gleebs anchor upward so the visible anchor ring
# sits higher within the tower's circular artwork instead of cutting through its midpoint.
TEMPORAL_ANCHOR_HINT = (1796.0, 420.0)
# Present arrival is intentionally separate from the portal itself.  IO returns
# below the structure on the opposite side of its foreground wall while the
# portal/interaction anchor remains exactly where it was authored.
PRESENT_TEMPORAL_ARRIVAL_HINT = (1796.0, 520.0)
# Pass 136: invisible Present-only access trigger.  Entering this small box
# teleports IO onto the already-authored lower 2awalk terrain at the far right.
# The destination is on the same authored walk layer; no layer images or masks
# are modified, and normal movement remains authoritative after arrival.
PRESENT_LOWER_ROUTE_TRIGGER_CENTER = (199.0, 531.0)
PRESENT_LOWER_ROUTE_TRIGGER_SIZE = (56.0, 56.0)
PRESENT_LOWER_ROUTE_DESTINATION_HINT = (3860.0, 1040.0)
# Pass 137: the lower-route far-left edge has a second invisible automatic
# transfer.  IO fades fully to black before the local teleport, reappears on
# the authored upper Present terrain, and faces left.  The coordinates are
# intentionally separate from every portal/temporal anchor.
PRESENT_LOWER_ROUTE_EXIT_TRIGGER_CENTER = (71.0, 972.0)
# Pass 140: this is an EXIT gate, not a point trigger.  The invisible volume
# spans the full lower-left walk corridor so IO cannot slip around it at the
# bottom or top edge while continuing left.  Its center remains exactly the
# authored developer coordinate from Pass 137.
PRESENT_LOWER_ROUTE_EXIT_TRIGGER_SIZE = (180.0, 360.0)
PRESENT_LOWER_ROUTE_EXIT_DESTINATION_HINT = (3181.0, 551.0)
PRESENT_LOCAL_ROUTE_FADE_OUT = 0.18
PRESENT_LOCAL_ROUTE_FADE_IN = 0.26
# The matching Beginning ground plane sits lower in its authored walk layer.
# This remains sanitized through the existing footprint-aware ground resolver.
PAST_TEMPORAL_ANCHOR_HINT = (1796.0, 618.0)
GLEEBS_INTERACT_RADIUS = 96.0
GLEEBS_NAME = "GLEEBS"
GLEEBS_TITLE = "ARCHIVE EXTERNAL // HOLOVERSE ENGINEER"

# Pass 100: Sable is the first stationary ghost NPC. She exists only in the
# Beginning/Past. Her authored frames face right, which is intentional because
# her inset far-left placement makes her face into the playable field by default.
SABLE_NAME = "SABLE"
SABLE_TITLE = "THE BUILDER // DEVELOPMENT ENTITY"
SABLE_ASSET_DIR = ROOT / "assets" / "custom" / "sable"
SABLE_PAST_HINT = (320.0, 820.0)
SABLE_INTERACT_RADIUS = 92.0
SABLE_HEIGHT_RATIO = 1.10
SABLE_IDLE_FPS = 2.15
SABLE_FUTURE_STATUS = "destroyed_by_guardian"
MACHINE_TELEKINESIS_KEY = pygame.K_t
MACHINE_PLACEMENT_ALPHA = 190
MACHINE_SELECTED_OUTLINE = (162, 224, 230)
MACHINE_WORLD_MARGIN = 6.0
MACHINE_HOTBAR_MAX = 6  # authoritative numbered MAIN MACHINE KIT slots
MACHINE_CAROUSEL_VISIBLE = 7
MACHINE_WORKSHOP_INTERACT_RADIUS = 108.0
MACHINE_HEAD_INTERACT_RADIUS = 88.0
MACHINE_WORKSHOP_SHAPES = ("SOURCE", "RECT", "CIRCLE", "DIAMOND", "CAPSULE")
MACHINE_WORKSHOP_FUNCTIONS = ("rotate", "tilt", "shake")
MACHINE_WORKSHOP_ROLES = (
    ROLE_FRAME, ROLE_COSMETIC, ROLE_HEAD, ROLE_ACTUATOR, ROLE_SENSOR, ROLE_TOOL,
    ROLE_GEAR, ROLE_PIVOT, ROLE_FAN, ROLE_PIPE, ROLE_CORE,
)
MACHINE_WORKSHOP_ROLE_LABELS = {
    ROLE_FRAME: "FRAME / OVERLAY",
    ROLE_COSMETIC: "PASSIVE / COSMETIC",
    ROLE_GEAR: "GEAR / LOAD",
    ROLE_PIVOT: "PIVOT / DRIVE",
    ROLE_FAN: "ROTOR / FAN",
    ROLE_PIPE: "CONDUIT / PIPE",
    ROLE_CORE: "CORE / POWER",
    ROLE_HEAD: "HEAD / CONTROL",
    ROLE_ACTUATOR: "ACTUATOR / MOTION",
    ROLE_SENSOR: "SENSOR / INPUT",
    ROLE_TOOL: "TOOL / OUTPUT",
}
MACHINE_WORKSHOP_FX_ROLES = {ROLE_FRAME, ROLE_COSMETIC, ROLE_HEAD, ROLE_ACTUATOR, ROLE_SENSOR, ROLE_TOOL}
MACHINE_RUNTIME_FX_ROLES = {ROLE_FRAME, ROLE_COSMETIC, ROLE_HEAD, ROLE_ACTUATOR, ROLE_SENSOR, ROLE_TOOL}
MACHINE_WORKSHOP_SIZES = (("COMPACT", 56.0), ("STANDARD", 82.0), ("LARGE", 112.0), ("HEAVY", 144.0))
MACHINE_ROLE_DEFAULT_SPIN = {ROLE_PIVOT: 72.0, ROLE_FAN: 216.0}
MACHINE_WORKSHOP_MAX_SNAPS = 6
MACHINE_SNAP_ASSIST_RADIUS_WORLD = 18.0
MACHINE_HOTBAR_SLOT = 48
MACHINE_HOTBAR_GAP = 4
MACHINE_HOTBAR_BOTTOM = 14
MACHINE_HOTBAR_ROLE_ORDER = (ROLE_CORE, ROLE_GEAR, ROLE_PIVOT, ROLE_HEAD, ROLE_ACTUATOR, ROLE_FAN, ROLE_PIPE, ROLE_SENSOR, ROLE_TOOL, ROLE_FRAME, ROLE_COSMETIC)
DEV_CONSOLE_KEYS = (pygame.K_BACKQUOTE, pygame.K_F10)
# Pass 135: tiny developer-only world-coordinate readout.  The toggle is
# screen-space UI only and never changes player/world/camera authority.
DEV_COORD_TOGGLE_KEY = pygame.K_F2
DEV_COORD_TOGGLE_RECT = pygame.Rect(W - 42, H - 22, 34, 14)
RESONANCE_PULSE_TIME = 0.90
VEIL_WARD_DURATION = 2.40
VEIL_WARD_COOLDOWN = 6.00
VEIL_WARD_FADE_IN = 0.24
VEIL_WARD_FADE_OUT = 0.42

# Pass 68: exploration-only controllable lantern projection. It flies freely
# through the current era while IO remains physically where he launched it.
LANTERN_PROJECTION_SPEED = 720.0
LANTERN_PROJECTION_COAST_SPEED = 420.0
REMOTE_RESONANCE_PULSE_TIME = 0.78
LANTERN_PROJECTION_LAUNCH_OFFSET = 34.0
LANTERN_PROJECTION_RECALL_BLEND = 10.0

# Pass 72: hostile hunter drones exist only in the aerial Projection layer.
# They never target or damage IO. Their bounded patrol/alert/fire FSM sleeps
# completely whenever Lantern Projection is inactive.
ENEMY_DRONE_MAX = 4
ENEMY_DRONE_ALTITUDE = (72.0, 330.0)
ENEMY_DRONE_DETECTION_RADIUS = 560.0
ENEMY_DRONE_ATTACK_RADIUS = 455.0
ENEMY_DRONE_FOV_COS = -0.18
ENEMY_DRONE_PATROL_SPEED = 92.0
ENEMY_DRONE_CHASE_SPEED = 168.0
ENEMY_DRONE_FIRE_COOLDOWN = 0.86
ENEMY_DRONE_SHOT_SPEED = 505.0
ENEMY_DRONE_SHOT_LIFE = 1.65
ENEMY_DRONE_HIT_RADIUS = 21.0
ENEMY_DRONE_PROJECTION_MAX_Y = 500.0
LANTERN_PROJECTION_INTEGRITY = 3

# Pass 73: Projection Lance is the first offensive drone upgrade. It is only
# available while Lantern Projection is active and never targets ground IO.
PROJECTION_LANCE_SPEED = 930.0
PROJECTION_LANCE_LIFE = 1.25
PROJECTION_LANCE_HIT_RADIUS = 27.0
PROJECTION_LANCE_MAX_SHOTS = 7
PROJECTION_LANCE_TRAIL_MAX = 10
ENEMY_DRONE_BASE_INTEGRITY = 2
ENEMY_DRONE_ELITE_INTEGRITY = 3
RESONANCE_COOLDOWN = 2.60
RESONANCE_NEAR_DISTANCE = 340.0
RESONANCE_MID_DISTANCE = 820.0
LORE_TRIGGER_RADIUS = 78.0
LORE_CARD_TIME = 5.40
LORE_PLACEMENT_SEPARATION = 180.0
TRANSITION_OUT_TIME = 0.42
TRANSITION_IN_TIME = 0.58
PARALLAX_ENABLED = False  # compatibility only; Pass 20 uses one shared crop
DEPTH_COMPOSITE_CACHE_MAX = 6


# Persistent screen-space atmosphere. These are presentation-only and never
# influence walk masks, actor depth, collision, or the A->B transition.
FOG_DENSITY = {"a": 0.78, "b": 1.06}
VIGNETTE_ALPHA = {"a": 242, "b": 255}
ATMOSPHERE_DARKEN = {"a": 30, "b": 42}
PRESENT_CLOUD_SHADOW_IDLE_RANGE = (7.5, 16.0)
PRESENT_CLOUD_SHADOW_DURATION_RANGE = (4.6, 7.8)
PRESENT_CLOUD_SHADOW_ALPHA_RANGE = (8, 21)
AUDIO_EXTENSIONS = {".ogg", ".mp3", ".wav", ".flac"}
MUSIC_VOLUME = 0.78
SFX_VOLUME = 0.72
SETTINGS_FILE = "settings.json"
SAVE_FILE = "manual_save.json"
SAVE_SLOT_COUNT = 3
ENTITY_DIR = ROOT / "assets" / "source" / "Entities"
ENTITY_ASSET = ENTITY_DIR / "boss1.png"  # First Witness
ROOTED_CROWN_ASSET = ENTITY_DIR / "boss2.png"
VEIL_WARDEN_ASSET = ENTITY_DIR / "boss3.png"
SHRINE_ASSET = ROOT / "assets" / "source" / "shrine_source.png"
ENTITY_INTERACT_RADIUS = 72.0
SHRINE_INTERACT_RADIUS = 82.0
ENTITY_ID = "first_witness"
ENTITY_NAME = "THE FIRST WITNESS"
ENTITY_EPITHET = "KEEPER OF THE BEGINNING"
SHRINE_NAME = "SHRINE OF THE FIRST WITNESS"
ROOTED_CROWN_NAME = "THE ROOTED CROWN"
ROOTED_CROWN_EPITHET = "KEEPER OF RETURN"
ROOTED_CROWN_SHRINE_NAME = "SHRINE OF THE ROOTED CROWN"
VEIL_WARDEN_NAME = "THE VEIL WARDEN"
VEIL_WARDEN_EPITHET = "MEMORY GUARDIAN // ARCHIVE OF SEPARATION"
VEIL_WARDEN_SHRINE_NAME = "SHRINE OF THE VEIL WARDEN"
ARCHIVE_CHORUS_NAME = "THE ASHEN CHOIR"
ARCHIVE_CHORUS_EPITHET = "MEMORY GUARDIAN // ARCHIVE OF VOICES"
HOLLOW_ENGINE_NAME = "THE HOLLOW ENGINE"
HOLLOW_ENGINE_EPITHET = "MEMORY GUARDIAN // ARCHIVE OF MACHINES"
LAST_CARTOGRAPHER_NAME = "THE LAST CARTOGRAPHER"
LAST_CARTOGRAPHER_EPITHET = "MEMORY GUARDIAN // ARCHIVE OF WORLDS"
FINAL_GUARDIAN_NAME = "THE NULL CUSTODIAN"
FINAL_GUARDIAN_EPITHET = "FINAL MEMORY GUARDIAN // COMPLETE CIVILIZATION ARCHIVE"
MEMORY_GUARDIAN_NAMES = {
    ENTITY_ID: "THE FIRST WITNESS",
    ROOTED_CROWN_ID: "THE ROOTED CROWN",
    VEIL_WARDEN_ID: VEIL_WARDEN_NAME,
    ARCHIVE_CHORUS_ID: ARCHIVE_CHORUS_NAME,
    HOLLOW_ENGINE_ID: HOLLOW_ENGINE_NAME,
    LAST_CARTOGRAPHER_ID: LAST_CARTOGRAPHER_NAME,
    FINAL_GUARDIAN_ID: FINAL_GUARDIAN_NAME,
}
MEMORY_GUARDIAN_EPITHETS = {
    ENTITY_ID: "MEMORY GUARDIAN // ARCHIVE OF ORIGIN",
    ROOTED_CROWN_ID: "MEMORY GUARDIAN // ARCHIVE OF RETURN",
    VEIL_WARDEN_ID: VEIL_WARDEN_EPITHET,
    ARCHIVE_CHORUS_ID: ARCHIVE_CHORUS_EPITHET,
    HOLLOW_ENGINE_ID: HOLLOW_ENGINE_EPITHET,
    LAST_CARTOGRAPHER_ID: LAST_CARTOGRAPHER_EPITHET,
    FINAL_GUARDIAN_ID: FINAL_GUARDIAN_EPITHET,
}
MEMORY_GUARDIAN_ORDER = (ENTITY_ID, ROOTED_CROWN_ID, VEIL_WARDEN_ID, ARCHIVE_CHORUS_ID, HOLLOW_ENGINE_ID, LAST_CARTOGRAPHER_ID, FINAL_GUARDIAN_ID)
ADDITIONAL_SHRINE_IDS = (ARCHIVE_CHORUS_ID, HOLLOW_ENGINE_ID, LAST_CARTOGRAPHER_ID, FINAL_GUARDIAN_ID)
ADDITIONAL_SHRINE_SEEDS = {
    ARCHIVE_CHORUS_ID: 0xA54E04,
    HOLLOW_ENGINE_ID: 0xA54E05,
    LAST_CARTOGRAPHER_ID: 0xA54E06,
    FINAL_GUARDIAN_ID: 0xA54E07,
}
MEMORY_GUARDIAN_ASSETS = {
    ENTITY_ID: ENTITY_DIR / "boss1.png",
    ROOTED_CROWN_ID: ENTITY_DIR / "boss2.png",
    VEIL_WARDEN_ID: ENTITY_DIR / "boss3.png",
    ARCHIVE_CHORUS_ID: ENTITY_DIR / "boss4.png",
    HOLLOW_ENGINE_ID: ENTITY_DIR / "boss5.png",
    LAST_CARTOGRAPHER_ID: ENTITY_DIR / "boss6.png",
    FINAL_GUARDIAN_ID: ENTITY_DIR / "finalboss.png",
}
MEMORY_GUARDIAN_MIN_SEPARATION = 500.0
MEMORY_GUARDIAN_HINTS = {
    ENTITY_ID: (300.0, 665.0),
    ROOTED_CROWN_ID: (850.0, 645.0),
    VEIL_WARDEN_ID: (1400.0, 670.0),
    ARCHIVE_CHORUS_ID: (1965.0, 640.0),
    HOLLOW_ENGINE_ID: (2530.0, 675.0),
    LAST_CARTOGRAPHER_ID: (3100.0, 650.0),
    FINAL_GUARDIAN_ID: (3680.0, 680.0),
}
ARCHIVE_ATTUNEMENTS = {
    ENTITY_ID: ("ORIGIN ATTUNEMENT", "Guardian battles begin with +1 Resolve."),
    ROOTED_CROWN_ID: ("RETURN ATTUNEMENT", "Guardian battles begin with 1 Focus."),
    VEIL_WARDEN_ID: ("SEPARATION ATTUNEMENT", "Guarded mistakes lose 1 less Resolve."),
    ARCHIVE_CHORUS_ID: ("VOICE ATTUNEMENT", "IO can hold up to 3 Focus."),
    HOLLOW_ENGINE_ID: ("MACHINE ATTUNEMENT", "Entropy Arc reforms after 1 turn."),
    LAST_CARTOGRAPHER_ID: ("WORLD ATTUNEMENT", "Guardian battles gain another +1 Resolve."),
    FINAL_GUARDIAN_ID: ("CIVILIZATION ATTUNEMENT", "The complete archive is ready for Gleebs."),
}
VEIL_WARDEN_ENTITY_SEED = 0x713A71
VEIL_WARDEN_SHRINE_SEED = 0x713B71
ROOTED_CROWN_FUTURE_CLUE_ID = "rooted_crown_absence"
ROOTED_CROWN_ENTITY_SEED = 0xC20A58
ROOTED_CROWN_SHRINE_SEED = 0xC20B58
ENTITY_HEIGHT_RATIO = 1.24  # Entities read just larger than IO in exploration.
ENTITY_GLOW_ALPHA = 18
ENTITY_HALO_LAYERS = ((12, 2), (8, 4), (5, 7), (2, 10))
OBELISK_BRIGHTNESS = 0.62
BATTLE_GUARDIAN_ATTACK_FX_TIME = 0.78
MIND_INTERFERENCE_BASE_CHANCE = 0.10
MIND_INTERFERENCE_LEVEL_CHANCE = 0.09
BATTLE_SIGNAL_VERIFY_COOLDOWN_TURNS = 2
BATTLE_MIND_WARD_COOLDOWN_TURNS = 3
PERFECT_READ_FOCUS_REWARD = 1
ENTITY_DISTORTION_AMPLITUDE = 3.6
ENTITY_DISTORTION_BAND = 4
ENTITY_PLACEMENT_SEED = 0xF17A51
BOSS_PORTRAIT_ROSTER = (
    (ENTITY_ID, "boss1.png"),
    (ROOTED_CROWN_ID, "boss2.png"),
    ("boss3", "boss3.png"),
    ("boss4", "boss4.png"),
    ("boss5", "boss5.png"),
    ("boss6", "boss6.png"),
    ("finalboss", "finalboss.png"),
)
BOSS_PORTRAIT_SIZE = 38
BOSS_PORTRAIT_SLOT = 48
TIME_SHIFT_OUT = 0.10  # legacy automatic transition only
TIME_SHIFT_IN = 0.22     # Pass 64: direct era swap response window
TIME_SHIFT_FLASH_ALPHA = 205

# Battle presentation reuses the established authored/derived monochrome art.
# FX surfaces are feathered at load time so their image bounds never read as
# square/rectangular cards against the chamber.
BATTLE_CURRENT_DIR = ROOT / "assets" / "current" / "battle"
BATTLE_BACKGROUND_ASSET = BATTLE_CURRENT_DIR / "background.png"
BATTLE_GLEEBS_ASSET = BATTLE_CURRENT_DIR / "gleebs.png"
BATTLE_GATE_ASSET = BATTLE_CURRENT_DIR / "the_gate.png"
BATTLE_FALLBACK_CHAMBER_ASSET = BATTLE_CURRENT_DIR / "fallback_chamber.png"
BATTLE_BACKGROUND_ROLE = ENTITY_ASSET.stem.lower()
BATTLE_ROLE_BY_ENTITY = {ENTITY_ID: "boss1", ROOTED_CROWN_ID: "boss2", VEIL_WARDEN_ID: "boss3", ARCHIVE_CHORUS_ID: "boss4", HOLLOW_ENGINE_ID: "boss5", LAST_CARTOGRAPHER_ID: "boss6", FINAL_GUARDIAN_ID: "finalboss"}

BATTLE_ASSET_FILES = {
    "spire_left": "spire_mid_a.png",
    "spire_right": "spire_mid_b.png",
    "fog": "fog_volume_mid.png",
    "wisp": "fog_wisp.png",
    "glow": "player_glow.png",
}
BATTLE_PLAYER_HEIGHT = 164
BATTLE_ENTITY_HEIGHT = 182
BATTLE_FX_TIME = 0.58

# Pass 57: the replaceable particle folder is the single particle authority.
# Every valid PNG in assets/source/particles is loaded once at startup and is
# eligible for randomized weather and boss-impact use. Users can therefore
# curate the effect set later by simply adding/removing PNGs from that folder.
BOSS_DAMAGE_PARTICLE_DIR = ROOT / "assets" / "source" / "particles"
# Pass 91: boss breakup fragments are sourced from the shared drone/legacy-fragment pool,
# so user-curated drones automatically participate without copied aliases.
# Pass 94: this pool is intentionally boss-damage / mechanical-fragment only.
# Environmental world debris and weather are strict particle-bank consumers.
BOSS_DAMAGE_FX_MAX = 44
BOSS_DEFEAT_TIME = 1.60

WEATHER_PARTICLE_MAX = 24
WEATHER_PARTICLE_RATE = {"a": 4.5, "b": 6.5}
WEATHER_WIND_SPEED = {"a": 112.0, "b": -138.0}
WEATHER_MARGIN = 96.0

# Pass 65: anchored weather overlays may provide multiple replaceable variants
# per era (overlay_01.png, overlay_02.png, ...).  The weather field stays
# fixed in place behind the walk layer while its internal colors/alpha flow
# through strip-wise distortion and slow crossfading between variants.
WEATHER_OVERLAY_FILES = {"a": "future/overlay.png", "b": "past/overlay.png"}
WEATHER_OVERLAY_ALPHA = {"a": 148, "b": 158}
WEATHER_OVERLAY_CROSSFADE = {"a": 16.0, "b": 20.0}
WEATHER_OVERLAY_FLOW_AMPLITUDE = {"a": 18.0, "b": 12.0}
WEATHER_OVERLAY_FLOW_BAND = {"a": 14, "b": 18}
WEATHER_OVERLAY_FLOW_SPEED = {"a": (0.34, 0.19), "b": (0.22, 0.14)}
WEATHER_OVERLAY_PULSE = {"a": (0.84, 0.16), "b": (0.88, 0.12)}
WEATHER_OVERLAY_RENDER_HZ = 15.0  # slow nebula motion; cache expensive full-frame rebuilds

# Pass 66: a restrained overcast grade is applied only to the rendered
# walkable layer. The alpha channel is preserved, so this never changes walk
# masks, collision, actor authority, or transparent gaps around the artwork.
# Future receives a cooler entropy cast; Past receives a softer violet cast.
WALK_OVERCAST_MULTIPLY = {"a": (206, 220, 232), "b": (224, 212, 236)}
WALK_OVERCAST_LIFT = {"a": (5, 8, 12), "b": (10, 7, 12)}
WALK_OVERCAST_STRENGTH = {"a": 0.82, "b": 0.72}

# Pass 47: replaceable battle sound-effects use stable semantic stems. The
# runtime searches common mixer formats by stem, so users may replace a WAV
# with an OGG/MP3 of the same stem without changing code. Missing/corrupt SFX
# are presentation-only failures and never block combat.
BATTLE_SFX_CUES = (
    "battle_enter",
    "lantern_shot",
    "focus",
    "guard",
    "boss_hit",
    "boss_shatter",
    "witness_strike",
    "gate_anchor",
    "deep_recall",
    "counter",
    "gate_heal",
    "io_hurt",
    "victory",
    "defeat",
    "flee",
    "shrine_bind",
)
EXPLORATION_SFX_CUES = (
    "footstep_walk_1",
    "footstep_walk_2",
    "footstep_sprint_1",
    "footstep_sprint_2",
    "lantern_resonance",
    "memory_debris",
    "shrine_restore",
    "weather_future",
    "weather_past",
    "weather_wind",
    "machine_loop",
)
SFX_EXTENSIONS = (".wav", ".ogg", ".mp3")

WORLD_VARIANT_ROLES = {
    "a": ("witness_defeated", "witness_recorded", "witness_restored"),
    "b": ("witness_defeated",),
}
WORLD_VARIANT_FOLDERS = {"a": "future", "b": "past"}
TRANSITION_VARIANT_FILES = {
    "time_shift": "time_shift.png",
    "battle_entry": "battle_entry.png",
    "shrine_bind": "shrine_bind.png",
}


def _set_windows_dpi_awareness() -> None:
    """Request Per-Monitor-V2 DPI awareness on Windows before creating a window."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def _user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        path = base / "GLITCHED MATRIX" / "Afterlife of IO"
    else:
        path = ROOT / "saves"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _old_user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "GLITCHED MATRIX" / "Exile Afterlife"
    return ROOT / "saves"


def _crash_log_path() -> Path:
    return _user_data_dir() / "crash.log"


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Write JSON through a sibling temporary file so a partial save is never authoritative."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    encoded = json.dumps(payload, indent=2, sort_keys=True)
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            # Some virtual/read-only filesystems do not expose a durable fsync.
            # Atomic replacement still prevents a partial JSON file becoming authoritative.
            pass
    os.replace(temp, path)


def _load_json(path: Path, default: dict) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else default.copy()
    except (OSError, ValueError, TypeError):
        return default.copy()


def _settings_path() -> Path:
    return _user_data_dir() / SETTINGS_FILE


def _old_settings_path() -> Path:
    return _old_user_data_dir() / SETTINGS_FILE


def _save_path(slot: int = 1) -> Path:
    slot = max(1, min(SAVE_SLOT_COUNT, int(slot)))
    return _user_data_dir() / f"manual_save_slot_{slot}.json"

def _legacy_save_path() -> Path:
    return _user_data_dir() / SAVE_FILE


def _old_save_path(slot: int = 1) -> Path:
    slot = max(1, min(SAVE_SLOT_COUNT, int(slot)))
    return _old_user_data_dir() / f"manual_save_slot_{slot}.json"


def _old_legacy_save_path() -> Path:
    return _old_user_data_dir() / SAVE_FILE


def _load_manual_slot(slot: int) -> dict:
    """Read one manual slot through the established migration chain."""
    data = _load_json(_save_path(slot), {})
    if not data:
        data = _load_json(_old_save_path(slot), {})
    if not data and slot == 1:
        data = _load_json(_legacy_save_path(), {}) or _load_json(_old_legacy_save_path(), {})
    return data


def newest_manual_save_slot() -> int | None:
    """Return the newest valid manual slot without creating or modifying save data."""
    candidates: list[tuple[float, int]] = []
    for slot in range(1, SAVE_SLOT_COUNT + 1):
        data = _load_manual_slot(slot)
        if str(data.get("world", "")).lower() not in {"a", "b"}:
            continue
        player = data.get("player") if isinstance(data.get("player"), dict) else {}
        try:
            x = float(player.get("x"))
            y = float(player.get("y"))
            int(data.get("walk_layer"))
            if not math.isfinite(x) or not math.isfinite(y):
                continue
        except (TypeError, ValueError, OverflowError):
            continue
        # Legacy saves without a parseable timestamp remain loadable but sort
        # behind timestamped saves written by this build.
        try:
            stamp = datetime.fromisoformat(str(data.get("saved_at", "")).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError, OverflowError, OSError):
            stamp = 0.0
        candidates.append((stamp, slot))
    return max(candidates)[1] if candidates else None


def mode_progress() -> "mode_host.Progress":
    """Best Memory Guardian / campaign progress across the manual save slots."""
    return mode_host.read_progress(_load_manual_slot, SAVE_SLOT_COUNT, MEMORY_GUARDIAN_ORDER)


def remembered_modes(settings: dict) -> list[str]:
    """Unlocks persist in settings so deleting a save never re-locks a mode."""
    raw = settings.get("unlocked_modes", [])
    ids = {str(v) for v in raw} if isinstance(raw, list) else set()
    if bool(settings.get("entropy_mode_unlocked", False)):  # pre-Pass 147 flag
        ids.add("entropy")
    return sorted(i for i in ids if i in mode_host.MODE_BY_ID)


def _restore_host_faulthandler() -> None:
    import faulthandler
    if _EARLY_LOG_HANDLE is not None:
        faulthandler.enable(file=_EARLY_LOG_HANDLE, all_threads=True)


def _shutdown_pygame_for_process_exit() -> None:
    """Release SDL/pygame resources explicitly before the host Python process exits.

    Entropy is intentionally run in-process, so there is no child python.exe to
    reap.  This helper makes the Windows handoff shutdown deterministic anyway:
    audio first, then the display/window, then every remaining pygame module.
    Every operation is repeat-safe so the outer bootstrap/finally may call quit
    again without changing behavior.
    """
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.stop()
            pygame.mixer.quit()
    except Exception as exc:
        _early_log(f"SHUTDOWN mixer cleanup warning {type(exc).__name__}: {exc}")
    try:
        if pygame.display.get_init():
            pygame.display.quit()
    except Exception as exc:
        _early_log(f"SHUTDOWN display cleanup warning {type(exc).__name__}: {exc}")
    try:
        pygame.quit()
    except Exception as exc:
        _early_log(f"SHUTDOWN pygame cleanup warning {type(exc).__name__}: {exc}")
    try:
        _early_log(
            "SHUTDOWN state "
            f"pygame_init={pygame.get_init()} "
            f"display_init={pygame.display.get_init()} "
            f"mixer_init={bool(pygame.mixer.get_init())}"
        )
    except Exception:
        pass


def _start_menu_item_enabled(index: int, continue_available: bool) -> bool:
    return not (index == 0 and not continue_available)


def next_start_menu_selection(current: int, direction: int, continue_available: bool) -> int:
    """Move through root items without focusing a disabled Continue."""
    item_count = 6
    candidate = int(current) % item_count
    for _ in range(item_count):
        candidate = (candidate + (1 if direction >= 0 else -1)) % item_count
        if _start_menu_item_enabled(candidate, continue_available):
            return candidate
    return 1


def _write_crash_log(exc_type, exc_value, exc_tb) -> None:
    try:
        stamp = datetime.now().isoformat(timespec="seconds")
        body = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _crash_log_path().write_text(
            f"Afterlife of IO crash report\nTime: {stamp}\nPython: {sys.version}\nPlatform: {sys.platform}\n\n{body}",
            encoding="utf-8",
        )
    except Exception:
        pass


def _has_flag(name: str) -> bool:
    return name in sys.argv[1:]


def _flag_value(name: str, default: str | None = None) -> str | None:
    try:
        idx = sys.argv.index(name)
        return sys.argv[idx + 1]
    except (ValueError, IndexError):
        return default


def _desktop_size() -> tuple[int, int]:
    """Return the active desktop size without requesting a display-mode change."""
    try:
        sizes = pygame.display.get_desktop_sizes()
        if sizes:
            return tuple(map(int, sizes[0]))
    except Exception:
        pass
    info = pygame.display.Info()
    return max(1, int(info.current_w)), max(1, int(info.current_h))


def _parse_window_size(value: str | None, fallback: tuple[int, int] = DEFAULT_WINDOW) -> tuple[int, int]:
    """Parse WIDTHxHEIGHT for deterministic 1080p/720p acceptance runs."""
    if not value:
        return fallback
    try:
        width_text, height_text = value.lower().split("x", 1)
        width, height = int(width_text), int(height_text)
    except (ValueError, TypeError):
        return fallback
    if width <= 0 or height <= 0:
        return fallback
    # Keep the supported 16:9 presentation floor. Aspect-safe letterboxing still
    # handles odd desktop sizes during manual resizing/fullscreen.
    return max(MIN_WINDOW[0], width), max(MIN_WINDOW[1], height)


def _create_window(fullscreen: bool, size: tuple[int, int] = DEFAULT_WINDOW):
    """Create one display surface.

    Fullscreen uses the current Windows desktop resolution with plain FULLSCREEN.
    The game performs its own 1280x720 gameplay-to-window presentation scaling, so SCALED must not be
    combined with the manual presentation path.
    """
    if fullscreen:
        desktop = _desktop_size()
        return pygame.display.set_mode(desktop, pygame.FULLSCREEN)
    width = max(MIN_WINDOW[0], int(size[0]))
    height = max(MIN_WINDOW[1], int(size[1]))
    return pygame.display.set_mode((width, height), pygame.RESIZABLE)


def _present_logical(window: pygame.Surface, logical: pygame.Surface) -> None:
    """Scale 16:9 gameplay to the current window without stretching or exposing edges."""
    ww, wh = window.get_size()
    if ww <= 0 or wh <= 0:
        return
    scale = min(ww / W, wh / H)
    dw = max(1, int(round(W * scale)))
    dh = max(1, int(round(H * scale)))
    if (dw, dh) == (W, H):
        frame = logical
    else:
        frame = pygame.transform.smoothscale(logical, (dw, dh))
    window.fill((0, 0, 0))
    window.blit(frame, ((ww - dw) // 2, (wh - dh) // 2))


def _window_to_logical(window: pygame.Surface, position: tuple[int, int]) -> tuple[int, int] | None:
    """Map a window mouse position through the aspect-safe letterbox transform."""
    ww, wh = window.get_size()
    if ww <= 0 or wh <= 0:
        return None
    scale = min(ww / W, wh / H)
    dw = max(1, int(round(W * scale)))
    dh = max(1, int(round(H * scale)))
    ox = (ww - dw) // 2
    oy = (wh - dh) // 2
    mx, my = int(position[0]), int(position[1])
    if mx < ox or my < oy or mx >= ox + dw or my >= oy + dh:
        return None
    logical_x = int((mx - ox) * W / dw)
    logical_y = int((my - oy) * H / dh)
    return min(W - 1, max(0, logical_x)), min(H - 1, max(0, logical_y))


def _rect_index_at(rects: list[pygame.Rect], position: tuple[int, int] | None) -> int | None:
    if position is None:
        return None
    return next((index for index, rect in enumerate(rects) if rect.collidepoint(position)), None)


def _logical_to_window(window: pygame.Surface, position: tuple[float, float]) -> tuple[int, int]:
    """Map a logical 1280x720 point through the current letterboxed presentation."""
    ww, wh = window.get_size()
    if ww <= 0 or wh <= 0:
        return int(position[0]), int(position[1])
    scale = min(ww / W, wh / H)
    dw = max(1, int(round(W * scale)))
    dh = max(1, int(round(H * scale)))
    ox = (ww - dw) // 2
    oy = (wh - dh) // 2
    x = ox + int(round(clamp(float(position[0]), 0.0, W - 1.0) * dw / W))
    y = oy + int(round(clamp(float(position[1]), 0.0, H - 1.0) * dh / H))
    return x, y


def _post_key(key: int, *, from_controller: bool = False) -> None:
    """Route alternate input through the established keyboard action path."""
    pygame.event.post(pygame.event.Event(
        pygame.KEYDOWN, key=key, mod=0, from_controller=bool(from_controller)
    ))


class ControllerBridge:
    """Optional SDL controller bridge with raw-joystick fallback.

    SDL's controller layer normalizes Xbox/PlayStation/Nintendo-style pads to
    stable button positions.  The fallback keeps generic USB pads usable when
    SDL has no controller mapping.  Gameplay remains keyboard/mouse-authoritative:
    controller buttons are translated into the existing action paths.
    """

    RAW_BUTTON_NAMES = {
        0: "a", 1: "b", 2: "x", 3: "y", 4: "leftshoulder", 5: "rightshoulder",
        6: "back", 7: "start", 8: "leftstick", 9: "rightstick",
    }

    def __init__(self) -> None:
        self.sdl = None
        self.controller = None
        self.joystick = None
        self.name = ""
        try:
            from pygame._sdl2 import controller as sdl_controller
            sdl_controller.init()
            sdl_controller.set_eventstate(True)
            self.sdl = sdl_controller
        except Exception:
            self.sdl = None
        try:
            pygame.joystick.init()
        except Exception:
            pass
        self.refresh()

    def close(self) -> None:
        for device in (self.controller, self.joystick):
            try:
                if device is not None:
                    device.quit()
            except Exception:
                pass
        self.controller = None
        self.joystick = None
        self.name = ""

    def refresh(self) -> None:
        self.close()
        if self.sdl is not None:
            try:
                for index in range(int(self.sdl.get_count())):
                    if self.sdl.is_controller(index):
                        self.controller = self.sdl.Controller(index)
                        self.name = str(self.sdl.name_forindex(index) or "Game Controller")
                        return
            except Exception:
                self.controller = None
        try:
            count = int(pygame.joystick.get_count())
            if count > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.name = str(self.joystick.get_name() or "Generic Controller")
        except Exception:
            self.joystick = None

    @property
    def connected(self) -> bool:
        if self.controller is not None:
            try:
                return bool(self.controller.attached())
            except Exception:
                return True
        return self.joystick is not None

    def device_event(self, event: pygame.event.Event) -> bool:
        event_types = {
            getattr(pygame, "CONTROLLERDEVICEADDED", -1001),
            getattr(pygame, "CONTROLLERDEVICEREMOVED", -1002),
            getattr(pygame, "JOYDEVICEADDED", -1003),
            getattr(pygame, "JOYDEVICEREMOVED", -1004),
        }
        if event.type in event_types:
            self.refresh()
            return True
        return False

    def _standard_button_name(self, button: int) -> str | None:
        if self.sdl is None:
            return None
        pairs = (
            ("a", "CONTROLLER_BUTTON_A"), ("b", "CONTROLLER_BUTTON_B"),
            ("x", "CONTROLLER_BUTTON_X"), ("y", "CONTROLLER_BUTTON_Y"),
            ("leftshoulder", "CONTROLLER_BUTTON_LEFTSHOULDER"),
            ("rightshoulder", "CONTROLLER_BUTTON_RIGHTSHOULDER"),
            ("back", "CONTROLLER_BUTTON_BACK"), ("start", "CONTROLLER_BUTTON_START"),
            ("leftstick", "CONTROLLER_BUTTON_LEFTSTICK"), ("rightstick", "CONTROLLER_BUTTON_RIGHTSTICK"),
            ("dpad_up", "CONTROLLER_BUTTON_DPAD_UP"), ("dpad_down", "CONTROLLER_BUTTON_DPAD_DOWN"),
            ("dpad_left", "CONTROLLER_BUTTON_DPAD_LEFT"), ("dpad_right", "CONTROLLER_BUTTON_DPAD_RIGHT"),
        )
        for name, attr in pairs:
            if button == getattr(self.sdl, attr, object()):
                return name
        return None

    def button_name(self, event: pygame.event.Event, *, down: bool) -> str | None:
        controller_type = getattr(pygame, "CONTROLLERBUTTONDOWN" if down else "CONTROLLERBUTTONUP", -1)
        if self.controller is not None and event.type == controller_type:
            return self._standard_button_name(int(event.button))
        joy_type = pygame.JOYBUTTONDOWN if down else pygame.JOYBUTTONUP
        if self.controller is None and self.joystick is not None and event.type == joy_type:
            return self.RAW_BUTTON_NAMES.get(int(event.button))
        return None

    def hat_actions(self, event: pygame.event.Event) -> tuple[str, ...]:
        if self.controller is not None or event.type != pygame.JOYHATMOTION:
            return ()
        try:
            x, y = event.value
        except Exception:
            return ()
        result: list[str] = []
        if y > 0: result.append("dpad_up")
        elif y < 0: result.append("dpad_down")
        if x < 0: result.append("dpad_left")
        elif x > 0: result.append("dpad_right")
        return tuple(result)

    def _axis(self, axis_name: str, raw_index: int) -> float:
        try:
            if self.controller is not None and self.sdl is not None:
                value = float(self.controller.get_axis(getattr(self.sdl, axis_name)))
                return clamp(value / 32767.0, -1.0, 1.0)
            if self.joystick is not None and raw_index < self.joystick.get_numaxes():
                return clamp(float(self.joystick.get_axis(raw_index)), -1.0, 1.0)
        except Exception:
            return 0.0
        return 0.0

    def movement(self) -> tuple[float, float]:
        x = self._axis("CONTROLLER_AXIS_LEFTX", 0)
        y = self._axis("CONTROLLER_AXIS_LEFTY", 1)
        return radial_deadzone(x, y, CONTROLLER_DEADZONE)

    def cursor_axes(self) -> tuple[float, float]:
        x = self._axis("CONTROLLER_AXIS_RIGHTX", 2)
        y = self._axis("CONTROLLER_AXIS_RIGHTY", 3)
        return radial_deadzone(x, y, CONTROLLER_DEADZONE)


@dataclass
class ArtLayer:
    number: int
    world: str
    path: Path
    walk: bool
    clamp: bool
    surface: pygame.Surface
    mask: pygame.Mask
    brightness: float = 1.0
    focus: float = 1.0

    @property
    def parallax(self) -> float:
        if self.clamp:
            return 0.0
        return PARALLAX_BY_NUMBER.get(self.number, max(0.12, 1.0 - self.number * 0.12))


@dataclass
class WorldStack:
    key: str
    layers: list[ArtLayer]

    @property
    def walk_layers(self) -> list[ArtLayer]:
        return [layer for layer in self.layers if layer.walk]

    def actor_foreground_layers(self, walk_number: int) -> list[ArtLayer]:
        # Lower numbers are closer to camera and therefore draw after the actor.
        return [layer for layer in self.layers if layer.number < walk_number]

    def actor_background_layers(self, walk_number: int) -> list[ArtLayer]:
        # Walk layer and every deeper layer draw before the actor.
        return [layer for layer in self.layers if layer.number >= walk_number]


@dataclass(frozen=True)
class LorePlacement:
    record: LoreRecord
    position: tuple[float, float]
    walk_number: int
    sprite: pygame.Surface | None


@dataclass(frozen=True)
class MachinePartDef:
    key: str
    name: str
    cost: int
    world_height: float
    role: str
    touch_radius: float
    spin_dps: float
    description: str
    surface: pygame.Surface


def effective_parallax(layer: ArtLayer, active_walk_number: int) -> float:
    """Compatibility shim: Pass 20 disables independent layer motion."""
    return 1.0


_LAYER_RE = re.compile(r"^(\d+)([ab])(?P<tags>[a-z]*)\.png$", re.I)


def parse_layer_stacks() -> dict[str, WorldStack]:
    stacks: dict[str, list[ArtLayer]] = {"a": [], "b": []}
    for path in sorted(LAYERS_DIR.glob("*.png")):
        m = _LAYER_RE.match(path.name)
        if not m:
            continue
        number = int(m.group(1))
        world = m.group(2).lower()
        tags = m.group("tags").lower()
        surf = pygame.image.load(str(path)).convert_alpha()
        # All authored layers share one coordinate canvas.  Do not resample the
        # source art; camera zoom happens only while drawing.
        mask = pygame.mask.from_surface(surf, ALPHA_THRESHOLD)
        stacks[world].append(
            ArtLayer(
                number=number,
                world=world,
                path=path,
                walk="walk" in tags,
                clamp="clamp" in tags,
                surface=surf,
                mask=mask,
                brightness=WORLD_BRIGHTNESS[world],
            )
        )
    return {
        key: WorldStack(key, sorted(value, key=lambda layer: layer.number))
        for key, value in stacks.items()
        if value
    }


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def approach(value: float, target: float, delta: float) -> float:
    if value < target:
        return min(target, value + delta)
    if value > target:
        return max(target, value - delta)
    return value


def alpha_at(mask: pygame.Mask, x: int, y: int) -> bool:
    return 0 <= x < mask.get_size()[0] and 0 <= y < mask.get_size()[1] and bool(mask.get_at((x, y)))


def nearest_spawn(mask: pygame.Mask) -> tuple[float, float]:
    # Find a generous opaque region rather than an edge pixel.
    w, h = mask.get_size()
    for x in range(160, max(161, w - 120), 10):
        for y in range(120, max(121, h - 40), 8):
            if mask.get_at((x, y)):
                return float(x), float(y)
    return 640.0, 600.0


def camera_bounds(zoom: float) -> tuple[float, float, float, float]:
    view_w = W / zoom
    view_h = H / zoom
    # A small safety margin means raw source-image edges never enter the camera.
    margin_x = 24
    margin_y = 18
    min_x = view_w * 0.5 + margin_x
    max_x = WORLD_SIZE[0] - view_w * 0.5 - margin_x
    min_y = view_h * 0.5 + margin_y
    max_y = WORLD_SIZE[1] - view_h * 0.5 - margin_y
    return min_x, max_x, min_y, max_y


def shared_camera_rect(cam_x: float, cam_y: float, zoom: float) -> pygame.Rect:
    """One source rectangle for every 3930x1130 world layer."""
    view_w = max(1, int(round(W / zoom)))
    view_h = max(1, int(round(H / zoom)))
    left = int(round(cam_x - view_w * 0.5))
    top = int(round(cam_y - view_h * 0.5))
    left = max(0, min(WORLD_SIZE[0] - view_w, left))
    top = max(0, min(WORLD_SIZE[1] - view_h, top))
    return pygame.Rect(left, top, view_w, view_h)


def world_to_screen_shared(wx: float, wy: float, source_rect: pygame.Rect) -> tuple[int, int]:
    sx = (wx - source_rect.left) * (W / source_rect.width)
    sy = (wy - source_rect.top) * (H / source_rect.height)
    return int(round(sx)), int(round(sy))


def screen_to_world_shared(sx: float, sy: float, source_rect: pygame.Rect) -> tuple[float, float]:
    """Inverse of world_to_screen_shared for mouse-driven machine telekinesis."""
    wx = source_rect.left + float(sx) * (source_rect.width / W)
    wy = source_rect.top + float(sy) * (source_rect.height / H)
    return (
        clamp(wx, MACHINE_WORLD_MARGIN, WORLD_SIZE[0] - MACHINE_WORLD_MARGIN),
        clamp(wy, MACHINE_WORLD_MARGIN, WORLD_SIZE[1] - MACHINE_WORLD_MARGIN),
    )


def _brightness_copy(surface: pygame.Surface, brightness: float) -> pygame.Surface:
    if abs(brightness - 1.0) <= 0.001:
        return surface
    shade = max(0, min(255, int(round(255 * brightness))))
    result = surface.copy()
    result.fill((shade, shade, shade, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return result


def discover_world_variant_paths() -> dict[tuple[str, str], Path]:
    """Register optional native-size replacements for each world's back layer."""
    result: dict[tuple[str, str], Path] = {}
    for world_key, roles in WORLD_VARIANT_ROLES.items():
        folder = WORLD_VARIANTS_DIR / WORLD_VARIANT_FOLDERS[world_key]
        for role in roles:
            path = folder / f"{role}.png"
            if path.is_file():
                result[(world_key, role)] = path
    return result


def active_world_variant_role(world_key: str, entity_defeated: bool, shrine_activated: bool,
                              story_complete: bool = False) -> str:
    if world_key == "a":
        if story_complete:
            return "witness_restored"
        if shrine_activated:
            return "witness_recorded"
        if entity_defeated:
            return "witness_defeated"
    elif world_key == "b" and entity_defeated:
        return "witness_defeated"
    return "base"


def _load_registered_world_variant(path: Path) -> pygame.Surface | None:
    """Load only exact 3930x1130 art; bad optional replacements fail closed."""
    try:
        surface = pygame.image.load(str(path)).convert_alpha()
        if surface.get_size() != WORLD_SIZE:
            _early_log(f"VARIANT ignored wrong-size world art path={path} size={surface.get_size()!r}")
            return None
        return surface
    except (pygame.error, OSError, ValueError, TypeError):
        _early_log(f"VARIANT ignored unreadable world art path={path}")
        return None


def build_depth_composite(stack: WorldStack, walk_number: int,
                          back_layer_variant: pygame.Surface | None = None,
                          apply_overcast: bool = True
                          ) -> tuple[pygame.Surface, pygame.Surface, pygame.Surface]:
    """Composite native-aligned depth groups with a weather insertion band.

    Returns ``deep_background, walk_band, foreground``.  The Pass 64 alpha
    weather sheet is drawn between deep_background and walk_band at runtime,
    so it can move every frame without rebuilding/caching the 3930x1130 art.
    Collision masks and authored walk authority remain completely unchanged.
    """
    deep_background = pygame.Surface(WORLD_SIZE, pygame.SRCALPHA)
    deep_background.fill((*WORLD_BACKDROP[stack.key], 255))
    walk_band = pygame.Surface(WORLD_SIZE, pygame.SRCALPHA)
    foreground = pygame.Surface(WORLD_SIZE, pygame.SRCALPHA)

    background_layers = stack.actor_background_layers(walk_number)
    back_number = max((layer.number for layer in background_layers), default=-1)
    deep_layers = [layer for layer in background_layers if layer.number > walk_number]
    walk_layers = [layer for layer in background_layers if layer.number == walk_number]

    # Deepest planes first.  Registered world-state art still replaces only the
    # deepest authored background plane exactly as before.
    for layer in reversed(deep_layers):
        source = back_layer_variant if back_layer_variant is not None and layer.number == back_number else layer.surface
        deep_background.blit(_brightness_copy(source, layer.brightness), (0, 0))

    # Robust fallback for any future stack where the walk layer is also deepest.
    for layer in reversed(walk_layers):
        source = back_layer_variant if back_layer_variant is not None and layer.number == back_number else layer.surface
        walk_band.blit(_brightness_copy(source, layer.brightness), (0, 0))

    # Static presentation grade: compute it once with the depth composite cache,
    # not once per rendered frame.
    if apply_overcast:
        walk_band = _apply_walk_overcast(walk_band, stack.key)

    for layer in reversed(stack.actor_foreground_layers(walk_number)):
        foreground.blit(_brightness_copy(layer.surface, layer.brightness), (0, 0))
    return deep_background, walk_band, foreground


def render_composite_view(surface: pygame.Surface, source_rect: pygame.Rect) -> pygame.Surface:
    crop = surface.subsurface(source_rect)
    return pygame.transform.smoothscale(crop, (W, H))


def actor_overlaps_view(view: pygame.Surface, actor_rect: pygame.Rect) -> bool:
    """Check only the actor-sized overlap region instead of masking the full frame."""
    clipped = actor_rect.clip(view.get_rect())
    if clipped.width <= 0 or clipped.height <= 0:
        return False
    try:
        return pygame.mask.from_surface(view.subsurface(clipped), ALPHA_THRESHOLD).count() > 0
    except (pygame.error, ValueError):
        return False


_OCCLUSION_CACHE: dict[int, pygame.Surface] = {}

def _soft_occlusion_multiplier(radius: int) -> pygame.Surface:
    """Return a smoothly feathered multiplier with no hard circular rings."""
    radius = max(24, int(radius))
    if radius in _OCCLUSION_CACHE:
        return _OCCLUSION_CACHE[radius]
    size = radius * 2 + 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = (size - 1) * 0.5
    inner = radius * 0.44
    outer = radius * 0.98
    # Pass 30 deliberately avoids PixelArray here.  Some SDL/Pygame builds can
    # surface-lock differently under display resets.  This mask is tiny, cached,
    # and created only once per radius, so set_at is safer and fast enough.
    for y in range(size):
        dy = y - cy
        for x in range(size):
            dx = x - cx
            d = math.hypot(dx, dy)
            if d <= inner:
                a = 72
            elif d >= outer:
                a = 255
            else:
                u = (d - inner) / max(1.0, outer - inner)
                u = u * u * u * (u * (u * 6.0 - 15.0) + 10.0)
                a = int(round(72 + (255 - 72) * u))
            surf.set_at((x, y), (255, 255, 255, a))
    _OCCLUSION_CACHE[radius] = surf
    return surf

def apply_local_occlusion_fade(view: pygame.Surface, actor_rect: pygame.Rect) -> pygame.Surface:
    """Feather foreground pixels in-place; the composite view is already frame-local."""
    if not actor_overlaps_view(view, actor_rect):
        return view
    radius = max(70, int(max(actor_rect.width, actor_rect.height) * 2.05))
    soft = _soft_occlusion_multiplier(radius)
    view.blit(soft, soft.get_rect(center=actor_rect.center), special_flags=pygame.BLEND_RGBA_MULT)
    return view


def walkable_at(layer: ArtLayer, x: float, y: float, tolerance: int = WALKABLE_TOLERANCE) -> bool:
    """Treat the opaque area of a *walk* layer as free-roam terrain.

    A tiny tolerance bridges one-pixel alpha cuts in the hand-cut artwork while
    preserving the authored outer silhouette.
    """
    xi = int(round(x)); yi = int(round(y))
    w, h = layer.mask.get_size()
    if not (0 <= xi < w and 0 <= yi < h):
        return False
    if layer.mask.get_at((xi, yi)):
        return True
    for r in range(1, tolerance + 1):
        for dx, dy in ((r,0),(-r,0),(0,r),(0,-r),(r,r),(r,-r),(-r,r),(-r,-r)):
            xx, yy = xi + dx, yi + dy
            if 0 <= xx < w and 0 <= yy < h and layer.mask.get_at((xx, yy)):
                return True
    return False


def footprint_walkable_at(layer: ArtLayer, x: float, y: float) -> bool:
    return all(walkable_at(layer, x + dx, y + dy) for dx, dy in PLAYER_FOOTPRINT)


def recover_nearby(layer: ArtLayer, x: float, y: float, radius: int = RECOVERY_RADIUS) -> tuple[float, float] | None:
    if footprint_walkable_at(layer, x, y):
        return float(x), float(y)
    for r in range(2, radius + 1, 2):
        # Prefer cardinal corrections before diagonals so recovery is visually subtle.
        for dx, dy in ((r,0),(-r,0),(0,r),(0,-r),(r,r),(r,-r),(-r,r),(-r,-r)):
            tx, ty = x + dx, y + dy
            if footprint_walkable_at(layer, tx, ty):
                return float(tx), float(ty)
    return None


def layer_by_number(stack: WorldStack, number: int) -> ArtLayer | None:
    for layer in stack.walk_layers:
        if layer.number == number:
            return layer
    return None


def nearest_walkable_point(layer: ArtLayer, hint: tuple[float,float], max_radius: int = 180) -> tuple[float,float]:
    hx, hy = map(float, hint)
    if footprint_walkable_at(layer, hx, hy):
        return hx, hy
    for r in range(4, max_radius + 1, 4):
        for dx in range(-r, r + 1, 4):
            for dy in (-r, r):
                if footprint_walkable_at(layer, hx + dx, hy + dy):
                    return hx + dx, hy + dy
        for dy in range(-r + 4, r, 4):
            for dx in (-r, r):
                if footprint_walkable_at(layer, hx + dx, hy + dy):
                    return hx + dx, hy + dy
    return nearest_spawn(layer.mask)


def nearest_walkable_across_stack(stack: WorldStack, hint: tuple[float, float], prefer_number: int | None = None) -> tuple[ArtLayer, tuple[float, float]]:
    """Choose the nearest safe ground point to a hint across authored walk layers."""
    candidates: list[tuple[float, ArtLayer, tuple[float, float]]] = []
    for layer in stack.walk_layers:
        point = nearest_walkable_point(layer, hint)
        distance = pygame.Vector2(point).distance_to(hint)
        bias = -12.0 if prefer_number is not None and layer.number == prefer_number else 0.0
        candidates.append((distance + bias, layer, point))
    if not candidates:
        raise ValueError("stack has no walk layers")
    _, layer, point = min(candidates, key=lambda item: item[0])
    return layer, point


def guardian_field_min_separation(positions: dict[str, tuple[float, float]]) -> float:
    ordered = [positions[g] for g in MEMORY_GUARDIAN_ORDER if g in positions]
    if len(ordered) < 2:
        return float("inf")
    return min(pygame.Vector2(a).distance_to(b) for i, a in enumerate(ordered) for b in ordered[i + 1:])


def choose_walk_layer_for_target(stack: WorldStack, current: ArtLayer, x: float, y: float) -> ArtLayer | None:
    # Stay in the current depth plane whenever possible. Only transition when the
    # player leaves that walkable region and the same destination belongs to a
    # different authored walk layer.
    if footprint_walkable_at(current, x, y):
        return current
    for layer in stack.walk_layers:
        if layer.number != current.number and footprint_walkable_at(layer, x, y):
            return layer
    return None

def load_player_animations() -> dict[str, list[pygame.Surface]]:
    base = ROOT / "assets" / "custom" / "player_exile"
    states = {"idle": [], "walk": [], "sprint": [], "jump": []}
    for state in states:
        files = sorted(base.glob(f"{state}_*.png"))
        for path in files:
            img = pygame.image.load(str(path)).convert_alpha()
            size = (max(1, int(img.get_width() * PLAYER_SCALE)), max(1, int(img.get_height() * PLAYER_SCALE)))
            states[state].append(pygame.transform.smoothscale(img, size))
    if not all(states.values()):
        raise RuntimeError("Incomplete Exile animation set in assets/custom/player_exile")
    return states


def load_sable_idle_frames() -> tuple[pygame.Surface, ...]:
    """Load Sable's user-authored four-frame idle loop without altering the art."""
    frames: list[pygame.Surface] = []
    for path in sorted(SABLE_ASSET_DIR.glob("idle*.png")):
        try:
            image = pygame.image.load(str(path)).convert_alpha()
            if image.get_width() > 0 and image.get_height() > 0:
                frames.append(image)
        except (pygame.error, OSError, ValueError, TypeError):
            continue
    return tuple(frames)


_MACHINE_CUSTOM_FUNCTIONS: dict[str, tuple[str, ...]] = {}
_MACHINE_CUSTOM_META: dict[str, dict] = {}
# Pass 129 separates raw source art from finished machine components. PNGs in
# variants/machines remain immediately usable in the fabrication preview.  They
# are still catalogued for legacy save/placement compatibility, but source-only
# keys are hidden from new purchases and normal inventory selection until a
# metadata entry promotes them to a finished component.
_MACHINE_SOURCE_PARTS: dict[str, MachinePartDef] = {}
_MACHINE_SOURCE_ONLY_KEYS: set[str] = set()
# Pass 127: the numbered quick slots are reserved for the authored base machine kit.
_MACHINE_PRIMARY_KEYS: set[str] = set()

def _load_machine_metadata(path: Path) -> dict[str, dict]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        parts = raw.get("parts") if isinstance(raw, dict) else None
        if isinstance(parts, dict):
            return {str(key): value for key, value in parts.items() if isinstance(value, dict)}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return {}

def _machine_trimmed_surface(texture: pygame.Surface) -> pygame.Surface:
    """Return alpha-bounded source art without changing its authored proportions."""
    try:
        bounds = texture.get_bounding_rect(min_alpha=2)
    except TypeError:
        bounds = texture.get_bounding_rect()
    if bounds.width <= 0 or bounds.height <= 0:
        return texture.copy()
    return texture.subsurface(bounds).copy()


def _machine_shape_surface(shape: str, texture: pygame.Surface, size: int = 128) -> pygame.Surface:
    """Create workshop art while preserving the source aspect ratio.

    SOURCE keeps the actual alpha-cutout silhouette. Geometric masks use a
    proportional center-cover fill: excess is cropped rather than stretched.
    This keeps the user's long, narrow, organic, and uneven replacement art
    visually honest.
    """
    size = max(48, min(256, int(size)))
    source = _machine_trimmed_surface(texture)
    sw, sh = source.get_size()
    if sw <= 0 or sh <= 0:
        return pygame.Surface((size, size), pygame.SRCALPHA)
    shape = str(shape).upper()
    if shape == "SOURCE":
        scale = min(size / sw, size / sh)
        out_size = (max(1, int(round(sw * scale))), max(1, int(round(sh * scale))))
        return source.copy() if out_size == (sw, sh) else pygame.transform.smoothscale(source, out_size)

    scale = max(size / sw, size / sh)
    fill_size = (max(1, int(round(sw * scale))), max(1, int(round(sh * scale))))
    filled = source if fill_size == (sw, sh) else pygame.transform.smoothscale(source, fill_size)
    result = pygame.Surface((size, size), pygame.SRCALPHA)
    result.blit(filled, ((size - filled.get_width()) // 2, (size - filled.get_height()) // 2))
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    inset = max(4, size // 18)
    if shape == "CIRCLE":
        pygame.draw.ellipse(mask, (255, 255, 255, 255), pygame.Rect(inset, inset, size - inset * 2, size - inset * 2))
    elif shape == "DIAMOND":
        pygame.draw.polygon(mask, (255, 255, 255, 255), [(size // 2, inset), (size - inset, size // 2), (size // 2, size - inset), (inset, size // 2)])
    elif shape == "CAPSULE":
        pygame.draw.rect(mask, (255, 255, 255, 255), pygame.Rect(inset, size // 4, size - inset * 2, size // 2), border_radius=size // 4)
    else:
        pygame.draw.rect(mask, (255, 255, 255, 255), pygame.Rect(inset, inset, size - inset * 2, size - inset * 2), border_radius=max(3, size // 14))
    result.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return result


def _sanitize_machine_snap_points(raw: object) -> list[tuple[float, float]]:
    """Normalize user-authored socket coordinates into bounded 0..1 UV space."""
    points: list[tuple[float, float]] = []
    if isinstance(raw, (list, tuple)):
        for value in raw[:MACHINE_WORKSHOP_MAX_SNAPS]:
            if not isinstance(value, (list, tuple)) or len(value) < 2:
                continue
            try:
                x = max(0.0, min(1.0, float(value[0])))
                y = max(0.0, min(1.0, float(value[1])))
            except (TypeError, ValueError, OverflowError):
                continue
            points.append((x, y))
    return points

def load_machine_catalog() -> dict[str, MachinePartDef]:
    """Load finished machine components while indexing all source artwork.

    Base machine PNGs are always finished components. Variant PNGs are source
    art unless they have an explicit metadata entry in variants/machines/catalog.json.
    Raw variants remain in the runtime catalog so older saves/placements are not
    deleted, but they are tagged source-only and hidden from new shop/inventory UI.
    """
    base_meta = _load_machine_metadata(MACHINE_CATALOG_PATH)
    variant_meta = _load_machine_metadata(MACHINE_VARIANTS_CATALOG_PATH)
    result: dict[str, MachinePartDef] = {}
    _MACHINE_CUSTOM_FUNCTIONS.clear()
    _MACHINE_CUSTOM_META.clear()
    _MACHINE_PRIMARY_KEYS.clear()
    _MACHINE_SOURCE_PARTS.clear()
    _MACHINE_SOURCE_ONLY_KEYS.clear()
    sources = ((MACHINE_ASSET_DIR, base_meta, False), (MACHINE_VARIANTS_DIR, variant_meta, True))
    for source_dir, metadata, is_variant in sources:
        if not source_dir.is_dir():
            continue
        for path in sorted(source_dir.glob("*.png")):
            key = path.stem.strip()
            if not key:
                continue
            try:
                image = pygame.image.load(str(path)).convert_alpha()
                if image.get_width() <= 0 or image.get_height() <= 0:
                    continue
                # Pass 141: user-added variant art is runtime-trimmed to its
                # alpha silhouette before the shared max-edge envelope is
                # applied. The PNG on disk is never rewritten, and the authored
                # aspect ratio is preserved without transparent padding making a
                # part appear strangely small or oversized relative to others.
                if is_variant:
                    image = _machine_trimmed_surface(image)
            except (pygame.error, OSError, ValueError, TypeError):
                continue
            meta = metadata.get(key, {})
            name = str(meta.get("name", key.replace("_", " ").upper())).strip() or key.replace("_", " ").upper()
            try:
                cost = max(1, min(999, int(meta.get("cost", DEFAULT_MACHINE_COST))))
            except (TypeError, ValueError, OverflowError):
                cost = DEFAULT_MACHINE_COST
            try:
                world_height = max(20.0, min(320.0, float(meta.get("world_height", DEFAULT_MACHINE_WORLD_HEIGHT))))
            except (TypeError, ValueError, OverflowError):
                world_height = DEFAULT_MACHINE_WORLD_HEIGHT
            role = normalize_machine_role(meta.get("role", ROLE_COSMETIC if not is_variant else ROLE_FRAME))
            try:
                touch_radius = max(4.0, min(180.0, float(meta.get("touch_radius", world_height * DEFAULT_MACHINE_TOUCH_RADIUS_RATIO))))
            except (TypeError, ValueError, OverflowError):
                touch_radius = world_height * DEFAULT_MACHINE_TOUCH_RADIUS_RATIO
            try:
                spin_dps = max(-720.0, min(720.0, float(meta.get("spin_dps", 0.0))))
            except (TypeError, ValueError, OverflowError):
                spin_dps = 0.0
            description = str(meta.get("description", "CUSTOM MACHINE COMPONENT" if is_variant and meta else "MACHINE SOURCE ART" if is_variant else "COSMETIC MACHINE COMPONENT")).strip() or "MACHINE COMPONENT"
            part = MachinePartDef(key, name, cost, world_height, role, touch_radius, spin_dps, description, image)
            _MACHINE_SOURCE_PARTS[key] = part
            # Keep raw variants in the catalog for old saves and already-placed
            # machines, but mark them source-only so new UI never treats them as
            # purchasable generic FRAME components.
            if is_variant and key not in metadata:
                _MACHINE_SOURCE_ONLY_KEYS.add(key)
            result[key] = part
            if not is_variant:
                _MACHINE_PRIMARY_KEYS.add(key)
            elif key in metadata:
                funcs_raw = meta.get("functions", [])
                if isinstance(funcs_raw, (list, tuple)):
                    funcs = tuple(fn for fn in MACHINE_WORKSHOP_FUNCTIONS if fn in {str(v).strip().lower() for v in funcs_raw})
                else:
                    funcs = ()
                _MACHINE_CUSTOM_FUNCTIONS[key] = funcs
                _MACHINE_CUSTOM_META[key] = dict(meta)
    return result


def _machine_source_parts() -> list[MachinePartDef]:
    """Stable base/raw/custom art list used only by the fabrication SOURCE row."""
    rank = {role: index for index, role in enumerate(MACHINE_HOTBAR_ROLE_ORDER)}
    return sorted(_MACHINE_SOURCE_PARTS.values(), key=lambda part: (rank.get(part.role, len(rank)), part.name, part.key))

def _ordered_machine_parts(machine_catalog: dict[str, MachinePartDef]) -> list[MachinePartDef]:
    """Stable compatibility order across every catalogued machine component."""
    rank = {role: index for index, role in enumerate(MACHINE_HOTBAR_ROLE_ORDER)}
    return sorted(machine_catalog.values(), key=lambda part: (rank.get(part.role, len(rank)), part.name, part.key))


def _finished_machine_parts(machine_catalog: dict[str, MachinePartDef]) -> list[MachinePartDef]:
    """Parts allowed to enter new shop/inventory flows."""
    return [part for part in _ordered_machine_parts(machine_catalog) if part.key not in _MACHINE_SOURCE_ONLY_KEYS]


def _inventory_machine_parts(machine_catalog: dict[str, MachinePartDef], machine_inventory: dict[str, int]) -> list[MachinePartDef]:
    """Normal parts plus legacy raw variants the current save already owns.

    This keeps old inventory data usable without advertising newly dropped source
    artwork as a finished machine component.
    """
    return [
        part for part in _ordered_machine_parts(machine_catalog)
        if part.key not in _MACHINE_SOURCE_ONLY_KEYS or clamp_machine_stack(machine_inventory.get(part.key, 0)) > 0
    ]


def _owned_machine_parts(machine_catalog: dict[str, MachinePartDef], machine_inventory: dict[str, int]) -> list[MachinePartDef]:
    """Compact build-focus list containing only parts IO can actually place.

    Sable's shop remains the full catalog.  The in-world machine focus no longer
    forces the player to scroll through zero-count variants, which keeps the HUD
    compact as the replaceable machine library grows.
    """
    return [
        part for part in _inventory_machine_parts(machine_catalog, machine_inventory)
        if clamp_machine_stack(machine_inventory.get(part.key, 0)) > 0
    ]


def _primary_machine_parts(machine_catalog: dict[str, MachinePartDef]) -> list[MachinePartDef]:
    """Return only the authored base kit used by numbered quick slots.

    Raw/custom variant art may be useful workshop material, but must never displace
    the mechanically essential Core/Gear/Pivot/Fan/Pipe/Frame kit from 1-6.
    """
    primary = {key: part for key, part in machine_catalog.items() if key in _MACHINE_PRIMARY_KEYS}
    return _ordered_machine_parts(primary)[:MACHINE_HOTBAR_MAX]


_MACHINE_HOTBAR_ICON_CACHE: dict[tuple[int, int], pygame.Surface] = {}


def _machine_hotbar_icon(part: MachinePartDef, max_side: int = 28) -> pygame.Surface:
    key = (id(part.surface), int(max_side))
    cached = _MACHINE_HOTBAR_ICON_CACHE.get(key)
    if cached is not None:
        return cached
    w, h = part.surface.get_size()
    scale = min(max_side / max(1, w), max_side / max(1, h), 1.0)
    size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
    cached = part.surface if size == (w, h) else pygame.transform.smoothscale(part.surface, size)
    _MACHINE_HOTBAR_ICON_CACHE[key] = cached
    return cached


def _permanent_core_item() -> dict[str, object]:
    """Locked world Core used as a permanent machine power source.

    Pass 121 deliberately removes the old time-travel/Stabilizer semantics.
    This is just a machine Core: touching Core + Gear + Pivot can form a
    powered drive through the normal machine network rules.
    """
    return {
        "id": PERMANENT_CORE_ID,
        "part": PERMANENT_CORE_PART_KEY,
        "world": PERMANENT_CORE_WORLD,
        "walk_layer": PERMANENT_CORE_WALK_LAYER,
        "x": round(float(PERMANENT_CORE_POS[0]), 3),
        "y": round(float(PERMANENT_CORE_POS[1]), 3),
        "locked": True,
        "flip_x": True,
        "permanent_core": True,
        "name": "PERMANENT CORE",
    }

def draw_machine_hotbar(target: pygame.Surface, small_font, machine_catalog: dict[str, MachinePartDef],
                         machine_inventory: dict[str, int], machine_bits: int,
                         flash_key: str | None = None, selected_key: str | None = None) -> pygame.Rect | None:
    # Pass 127: the quick-slot strip is a stable MAIN MACHINE KIT. Variants and
    # fabricated parts stay in the broader inventory/workshop and never reorder 1-6.
    parts = _primary_machine_parts(machine_catalog)
    if not parts:
        return None
    visible_count = len(parts)
    start_index = 0
    visible = parts
    slot = MACHINE_HOTBAR_SLOT
    gap = MACHINE_HOTBAR_GAP
    width = len(visible) * slot + max(0, len(visible) - 1) * gap
    x0 = (W - width) // 2
    y0 = H - MACHINE_HOTBAR_BOTTOM - slot
    panel = pygame.Rect(x0 - 10, y0 - 24, width + 20, slot + 34)
    shade = pygame.Surface(panel.size, pygame.SRCALPHA)
    shade.fill((5, 8, 12, 184))
    target.blit(shade, panel)
    if not _draw_hud_skin(target, "machine_hotbar_panel", panel):
        pygame.draw.rect(target, (69, 94, 99), panel, 1, border_radius=6)
    header = _ui_render(small_font, f"MAIN MACHINE KIT    BITS {clamp_bits(machine_bits)}", True, (174, 214, 219))
    target.blit(header, header.get_rect(midtop=(panel.centerx, panel.top + 4)))
    for local_index, part in enumerate(visible):
        global_index = start_index + local_index
        rect = pygame.Rect(x0 + local_index * (slot + gap), y0, slot, slot)
        count = clamp_machine_stack(machine_inventory.get(part.key, 0))
        selected = part.key == selected_key
        flashing = flash_key == part.key
        pygame.draw.rect(target, (23, 35, 39, 236) if selected else ((20, 30, 34, 230) if count else (10, 13, 16, 206)), rect, border_radius=4)
        border = (181, 230, 235) if selected else ((157, 215, 222) if flashing else (80, 105, 110))
        pygame.draw.rect(target, border, rect, 3 if selected else (2 if flashing else 1), border_radius=4)
        slot_img = _ui_render(small_font, str(global_index + 1), True, (135, 166, 170) if count else (74, 84, 86))
        target.blit(slot_img, (rect.left + 4, rect.top + 2))
        icon = _machine_hotbar_icon(part, 31 if selected else 28)
        if count <= 0:
            icon = icon.copy(); icon.set_alpha(70)
        target.blit(icon, icon.get_rect(center=(rect.centerx, rect.centery + 1)))
        count_img = _ui_render(small_font, str(count), True, (224, 232, 233) if count else (102, 112, 114))
        target.blit(count_img, count_img.get_rect(bottomright=(rect.right - 4, rect.bottom - 2)))
    return panel


MACHINE_INVENTORY_PAGE_SIZE = 12


def draw_machine_inventory(target: pygame.Surface, body_font, small_font,
                           machine_catalog: dict[str, MachinePartDef],
                           machine_inventory: dict[str, int], machine_bits: int, page: int = 0) -> int:
    """Draw IO's owned machine-component inventory as a dedicated modal.

    The six-slot hotbar remains quick access only.  This screen is the full owned
    inventory and is intentionally reachable directly with I during exploration.
    """
    owned = _owned_machine_parts(machine_catalog, machine_inventory)
    page_count = max(1, math.ceil(len(owned) / MACHINE_INVENTORY_PAGE_SIZE))
    page = max(0, min(int(page), page_count - 1))

    shade = pygame.Surface((W, H), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 172))
    target.blit(shade, (0, 0))

    panel = pygame.Rect(156, 70, W - 312, H - 140)
    veil = pygame.Surface(panel.size, pygame.SRCALPHA)
    veil.fill((4, 8, 12, 246))
    target.blit(veil, panel)
    pygame.draw.rect(target, (88, 132, 139), panel, 2, border_radius=10)
    pygame.draw.rect(target, (37, 61, 67), panel.inflate(-10, -10), 1, border_radius=8)

    target.blit(_ui_render(body_font, "IO INVENTORY", True, (208, 232, 234)),
                (panel.left + 28, panel.top + 18))
    subtitle = f"OWNED MACHINE COMPONENTS   •   BITS {clamp_bits(machine_bits)}"
    target.blit(_ui_render(small_font, subtitle, True, (131, 174, 180)),
                (panel.left + 30, panel.top + 55))

    if not owned:
        empty = _ui_render(body_font, "NO MACHINE COMPONENTS OWNED", True, (154, 173, 176))
        target.blit(empty, empty.get_rect(center=(panel.centerx, panel.centery - 8)))
        hint = _ui_render(small_font, "BUY MACHINE PIECES FROM SABLE OR FABRICATE THEM AT A POWERED CORE.", True, (112, 142, 146))
        target.blit(hint, hint.get_rect(center=(panel.centerx, panel.centery + 34)))
    else:
        start = page * MACHINE_INVENTORY_PAGE_SIZE
        visible = owned[start:start + MACHINE_INVENTORY_PAGE_SIZE]
        cols = 2
        rows = 6
        gap_x = 18
        gap_y = 8
        content_left = panel.left + 28
        content_top = panel.top + 88
        content_width = panel.width - 56
        cell_w = (content_width - gap_x) // cols
        cell_h = 61
        for local_index, part in enumerate(visible):
            col = local_index % cols
            row = local_index // cols
            rect = pygame.Rect(
                content_left + col * (cell_w + gap_x),
                content_top + row * (cell_h + gap_y),
                cell_w, cell_h,
            )
            pygame.draw.rect(target, (13, 21, 25), rect, border_radius=6)
            pygame.draw.rect(target, (54, 84, 90), rect, 1, border_radius=6)
            icon = _machine_hotbar_icon(part, 42)
            icon_rect = icon.get_rect(midleft=(rect.left + 13, rect.centery))
            target.blit(icon, icon_rect)
            text_x = rect.left + 68
            name = _ui_render(small_font, part.name.upper(), True, (209, 225, 227))
            role_name = MACHINE_WORKSHOP_ROLE_LABELS.get(part.role, part.role.upper())
            role = _ui_render(small_font, role_name, True, (118, 158, 164))
            count = clamp_machine_stack(machine_inventory.get(part.key, 0))
            qty = _ui_render(small_font, f"x{count}", True, (176, 224, 229))
            target.blit(name, (text_x, rect.top + 9))
            target.blit(role, (text_x, rect.top + 32))
            target.blit(qty, qty.get_rect(midright=(rect.right - 12, rect.centery)))

    footer = "I / ESC CLOSE"
    if page_count > 1:
        footer += f"   •   ← / → PAGE   •   {page + 1}/{page_count}"
    footer_img = _ui_render(small_font, footer, True, (151, 188, 193))
    target.blit(footer_img, footer_img.get_rect(midbottom=(panel.centerx, panel.bottom - 18)))
    return page


def _machine_workshop_layout() -> tuple[pygame.Rect, pygame.Rect]:
    panel = pygame.Rect(178, 48, 924, 624)
    preview = pygame.Rect(panel.left + 24, panel.top + 90, 354, 354)
    return panel, preview


def draw_machine_workshop(target: pygame.Surface, body_font, small_font, machine_catalog: dict[str, MachinePartDef],
                          row: int, shape_index: int, texture_index: int, role_index: int, size_index: int,
                          functions: set[str], snap_points: list[tuple[float, float]], snap_selected: int,
                          snap_edit: bool, status: str = "") -> tuple[list[pygame.Rect], pygame.Rect | None]:
    """Centered fabrication modal with editable per-part assembly sockets."""
    textures = _machine_source_parts()
    texture_part = textures[texture_index % len(textures)] if textures else None
    shape = MACHINE_WORKSHOP_SHAPES[shape_index % len(MACHINE_WORKSHOP_SHAPES)]
    role = MACHINE_WORKSHOP_ROLES[role_index % len(MACHINE_WORKSHOP_ROLES)]
    size_name, world_height = MACHINE_WORKSHOP_SIZES[size_index % len(MACHINE_WORKSHOP_SIZES)]
    fx_enabled = role in MACHINE_WORKSHOP_FX_ROLES
    points = _sanitize_machine_snap_points(snap_points)
    panel, preview = _machine_workshop_layout()
    veil = pygame.Surface(panel.size, pygame.SRCALPHA); veil.fill((4, 8, 12, 244)); target.blit(veil, panel)
    if not _draw_hud_skin(target, "machine_workshop_panel", panel):
        pygame.draw.rect(target, (83, 126, 132), panel, 2, border_radius=8)
    target.blit(_ui_render(body_font, "MACHINE WORKSHOP", True, (205, 231, 233)), (panel.left + 24, panel.top + 14))
    target.blit(_ui_render(small_font, "POWERED CORE FABRICATION // PROPERTY + SNAP POINT AUTHORING", True, (126, 166, 171)), (panel.left + 26, panel.top + 47))

    pygame.draw.rect(target, (12, 18, 22), preview, border_radius=6)
    pygame.draw.rect(target, (58, 83, 88), preview, 1, border_radius=6)
    image_rect: pygame.Rect | None = None
    if texture_part is not None:
        custom = _machine_shape_surface(shape, texture_part.surface, 246)
        image_rect = custom.get_rect(center=(preview.centerx, preview.centery - 12))
        target.blit(custom, image_rect)
        texture_name = texture_part.name if len(texture_part.name) <= 27 else texture_part.name[:24] + "..."
        label = _ui_render(small_font, f"SOURCE: {texture_name}", True, (161, 193, 197))
        target.blit(label, label.get_rect(midbottom=(preview.centerx, preview.bottom - 8)))
        if image_rect.width > 0 and image_rect.height > 0:
            for index, (u, v) in enumerate(points):
                px = int(round(image_rect.left + u * image_rect.width))
                py = int(round(image_rect.top + v * image_rect.height))
                selected = index == snap_selected
                color = (229, 232, 176) if selected else (128, 213, 222)
                pygame.draw.circle(target, (7, 13, 16), (px, py), 9 if selected else 7)
                pygame.draw.circle(target, color, (px, py), 8 if selected else 6, 2)
                pygame.draw.line(target, color, (px - 11, py), (px + 11, py), 1)
                pygame.draw.line(target, color, (px, py - 11), (px, py + 11), 1)
                num = _ui_render(small_font, str(index + 1), True, color)
                target.blit(num, (px + 8, py - 15))

    role_line = _ui_render(small_font, f"PROPERTY {MACHINE_WORKSHOP_ROLE_LABELS.get(role, role.upper())}   //   {size_name} {world_height:.0f}", True, (142, 184, 189))
    target.blit(role_line, role_line.get_rect(midtop=(preview.centerx, preview.bottom + 12)))
    snap_note = "SNAP EDIT ACTIVE" if snap_edit else f"{len(points)} ASSEMBLY SNAP POINTS // ENTER TO EDIT"
    target.blit(_ui_render(small_font, snap_note, True, (205, 213, 158) if snap_edit else (105, 137, 142)), (preview.left + 4, preview.bottom + 35))

    texture_value = texture_part.name if texture_part else "NONE"
    if len(texture_value) > 23:
        texture_value = texture_value[:20] + "..."
    def fx_value(fn: str) -> str:
        if not fx_enabled:
            return "ROLE-DRIVEN"
        return "ON" if fn in functions else "OFF"
    options = [
        ("SHAPE", f"<  {shape}  >"),
        ("SOURCE ART", f"<  {texture_value}  >"),
        ("PROPERTY", f"<  {MACHINE_WORKSHOP_ROLE_LABELS.get(role, role.upper())}  >"),
        ("SIZE", f"<  {size_name} / {world_height:.0f}  >"),
        ("SNAP POINTS", f"EDIT {len(points)}"),
        ("ROTATE FX", fx_value("rotate")),
        ("TILT FX", fx_value("tilt")),
        ("SHAKE FX", fx_value("shake")),
        ("CREATE PART", "SAVE + ADD TO INVENTORY"),
        ("CLOSE", "RETURN TO GAME"),
    ]
    hit_rects: list[pygame.Rect] = []
    x = panel.left + 402
    y = panel.top + 80
    for index, (label, value) in enumerate(options):
        rect = pygame.Rect(x, y + index * 48, 490, 40)
        selected = index == row and not snap_edit
        row_skin = "machine_workshop_row_selected" if selected else "machine_workshop_row"
        if not _draw_hud_skin(target, row_skin, rect):
            pygame.draw.rect(target, (24, 42, 46) if selected else (13, 21, 25), rect, border_radius=5)
            pygame.draw.rect(target, (157, 220, 226) if selected else (58, 80, 85), rect, 2 if selected else 1, border_radius=5)
        label_img = _ui_render(small_font, label, True, (218, 229, 230) if selected else (159, 178, 181))
        value_color = (169, 217, 221) if selected else (119, 145, 149)
        if not fx_enabled and 5 <= index <= 7:
            value_color = (82, 105, 109)
        target.blit(label_img, (rect.left + 12, rect.top + 5))
        value_img = _ui_render(small_font, value, True, value_color)
        target.blit(value_img, value_img.get_rect(bottomright=(rect.right - 12, rect.bottom - 5)))
        hit_rects.append(rect)

    footer_text = (
        "SNAP EDIT // LMB ADD/DRAG   RMB REMOVE   TAB SELECT   ARROWS NUDGE   ENTER DONE"
        if snap_edit else
        "UP/DOWN SELECT   LEFT/RIGHT CHANGE   ENTER APPLY   E / ESC CLOSE"
    )
    footer = _ui_render(small_font, footer_text, True, (144, 171, 175))
    target.blit(footer, footer.get_rect(midbottom=(panel.centerx, panel.bottom - 12)))
    if status:
        shown = status if len(status) <= 42 else status[:39] + "..."
        status_img = _ui_render(small_font, shown, True, (197, 220, 191))
        target.blit(status_img, (preview.left + 4, preview.bottom + 58))
    return hit_rects, image_rect

def draw_machine_pointer(target: pygame.Surface, point: tuple[int, int] | None, *, active: bool = False) -> None:
    if point is None:
        return
    color = (177, 231, 235) if active else (111, 174, 181)
    x, y = int(point[0]), int(point[1])
    pygame.draw.circle(target, color, (x, y), 6 if active else 4, 1)
    pygame.draw.line(target, color, (x - 10, y), (x - 4, y), 1)
    pygame.draw.line(target, color, (x + 4, y), (x + 10, y), 1)
    pygame.draw.line(target, color, (x, y - 10), (x, y - 4), 1)
    pygame.draw.line(target, color, (x, y + 4), (x, y + 10), 1)


def draw_dev_coordinates(target: pygame.Surface, coord_font, player_x: float, player_y: float, visible: bool) -> None:
    """Draw Pass 135's tiny bottom-right XY developer toggle/readout."""
    toggle = DEV_COORD_TOGGLE_RECT
    button = pygame.Surface(toggle.size, pygame.SRCALPHA)
    button.fill((6, 10, 13, 184 if visible else 132))
    pygame.draw.rect(button, (116, 178, 186, 220 if visible else 150), button.get_rect(), 1, border_radius=3)
    label = coord_font.render("XY", True, (206, 232, 235) if visible else (146, 172, 176))
    button.blit(label, label.get_rect(center=button.get_rect().center))
    target.blit(button, toggle)
    if not visible:
        return
    text = f"X {int(round(player_x))}  Y {int(round(player_y))}"
    glyph = coord_font.render(text, True, (209, 231, 232))
    pad_x, pad_y = 7, 4
    panel = pygame.Rect(0, 0, glyph.get_width() + pad_x * 2, glyph.get_height() + pad_y * 2)
    panel.bottomright = (toggle.right, toggle.top - 4)
    bg = pygame.Surface(panel.size, pygame.SRCALPHA)
    bg.fill((4, 8, 11, 176))
    pygame.draw.rect(bg, (79, 119, 124, 180), bg.get_rect(), 1, border_radius=3)
    target.blit(bg, panel)
    target.blit(glyph, (panel.left + pad_x, panel.top + pad_y))


def draw_dev_console(target: pygame.Surface, small_font, text: str, status: str) -> None:
    panel = pygame.Rect(160, 18, W - 320, 76)
    veil = pygame.Surface(panel.size, pygame.SRCALPHA); veil.fill((2, 5, 8, 226)); target.blit(veil, panel)
    if not _draw_hud_skin(target, "console_panel", panel):
        pygame.draw.rect(target, (81, 135, 143), panel, 1, border_radius=4)
    target.blit(_ui_render(small_font, "IO DEVELOPER CONSOLE  //  ` OR F10 CLOSE", True, (157, 211, 218)), (panel.left + 12, panel.top + 8))
    target.blit(_ui_render(small_font, "> " + text + "_", True, (222, 229, 229)), (panel.left + 12, panel.top + 31))
    if status:
        msg = _ui_render(small_font, status, True, (167, 188, 190)); target.blit(msg, msg.get_rect(bottomleft=(panel.left + 12, panel.bottom - 7)))


_MACHINE_ROTATION_CACHE: dict[tuple[int, int, int, int], pygame.Surface] = {}


def _machine_part_screen_surface(part: MachinePartDef, screen_scale: float, *, angle: float = 0.0, alpha: int = 255, flip_x: bool = False, width_scale: float = 1.0) -> pygame.Surface:
    """Scale every machine PNG through one shared part-size envelope.

    Pass 126 removes all pipe-specific and folder-specific sizing rules.  The
    selected/catalogued size is the maximum edge available to every machine
    component.  Source aspect ratio decides the rectangle inside that envelope;
    it never multiplies the component's gameplay scale.

    Rotation is quantized to five-degree buckets so a running machine does not
    allocate a brand-new Surface every rendered frame.
    """
    world_width, world_height = _machine_part_world_dimensions(part)
    width = max(8, int(round(world_width * screen_scale)))
    height = max(8, int(round(world_height * screen_scale)))
    # Pass 119: machine artwork never telescopes or squashes.  The width_scale
    # argument remains for backward-compatible call sites, but is intentionally
    # ignored so every part preserves its authored aspect ratio.
    scaled = _scaled_world_object_surface(part.surface, width, height)
    bucket = int(round(float(angle) / 5.0)) % 72
    if bucket:
        key = (id(part.surface), width, height, bucket)
        image = _MACHINE_ROTATION_CACHE.get(key)
        if image is None:
            image = pygame.transform.rotate(scaled, bucket * 5.0)
            if len(_MACHINE_ROTATION_CACHE) >= 1536:
                _MACHINE_ROTATION_CACHE.clear()
            _MACHINE_ROTATION_CACHE[key] = image
    else:
        image = scaled
    if flip_x:
        image = pygame.transform.flip(image, True, False)
    if alpha < 255:
        image = image.copy()
        image.set_alpha(max(0, min(255, int(alpha))))
    return image


def _rotate_world_offset(dx: float, dy: float, angle_degrees: float) -> tuple[float, float]:
    radians = math.radians(float(angle_degrees))
    c = math.cos(radians)
    s = math.sin(radians)
    return dx * c - dy * s, dx * s + dy * c


_MACHINE_PIPE_DYNAMICS: dict[int, dict[str, float]] = {}


def _machine_part_world_dimensions(part: MachinePartDef) -> tuple[float, float]:
    """Fit source art inside the common machine-part envelope without squaring.

    ``world_height`` is retained as the serialized/catalog size field for save
    compatibility, but Pass 126 treats that value uniformly as the part's
    maximum edge.  A 1:1 gear therefore occupies the full envelope while a 4:1
    pipe occupies the same envelope as a 4:1 rectangle.  No filename, role,
    folder, or connector distance is allowed to alter the scale.
    """
    sw = max(1, int(part.surface.get_width()))
    sh = max(1, int(part.surface.get_height()))
    ratio = sw / sh
    envelope = max(8.0, float(part.world_height))
    if ratio >= 1.0:
        width = envelope
        height = envelope / max(1e-6, ratio)
    else:
        height = envelope
        width = envelope * ratio
    return max(4.0, width), max(4.0, height)

def _machine_part_natural_world_width(part: MachinePartDef) -> float:
    return _machine_part_world_dimensions(part)[0]


def _machine_part_natural_world_height(part: MachinePartDef) -> float:
    return _machine_part_world_dimensions(part)[1]


def _machine_part_explicit_snap_points(part: MachinePartDef) -> list[tuple[float, float]]:
    return _sanitize_machine_snap_points(_MACHINE_CUSTOM_META.get(part.key, {}).get("snap_points", []))


def _machine_part_inferred_snap_points(part: MachinePartDef, *, as_source: bool) -> list[tuple[float, float]]:
    """Return conservative connector anchors for irregular finished parts.

    Explicit workshop sockets always win.  Pass 143 infers only the minimum
    anchors needed to make the user-added HEAD/ARM/SENSOR/TOOL/FRAME artwork
    snap in a way that agrees with its visible silhouette.  The proven base
    drive pieces never gain source-side magnetic behavior from this helper; they
    are only exposed as target anchors for accessories.
    """
    explicit = _machine_part_explicit_snap_points(part)
    if explicit:
        return explicit
    if as_source and part.key in _MACHINE_PRIMARY_KEYS:
        # Preserve the established six-piece MAIN MACHINE KIT drag behavior.
        return []
    role = part.role
    width, height = _machine_part_world_dimensions(part)
    horizontal = width >= height * 1.22
    vertical = height >= width * 1.22
    if role == ROLE_HEAD:
        return [(0.50, 0.94)] if as_source else [(0.50, 0.94), (0.08, 0.52), (0.92, 0.52)]
    if role in {ROLE_ACTUATOR, ROLE_SENSOR, ROLE_TOOL}:
        if horizontal:
            return [(0.06, 0.50), (0.94, 0.50)]
        if vertical:
            return [(0.50, 0.06), (0.50, 0.94)]
        return [(0.08, 0.50), (0.92, 0.50)]
    if role in {ROLE_FRAME, ROLE_COSMETIC}:
        return [(0.50, 0.06), (0.94, 0.50), (0.50, 0.94), (0.06, 0.50)]
    if not as_source and role in {ROLE_CORE, ROLE_GEAR, ROLE_PIVOT, ROLE_FAN}:
        return [(0.50, 0.06), (0.94, 0.50), (0.50, 0.94), (0.06, 0.50)]
    return []


def _machine_local_snap_offset(part: MachinePartDef, uv: tuple[float, float], angle: float, flip_x: bool) -> tuple[float, float]:
    """Map normalized part-space socket coordinates into y-down world space."""
    width, height = _machine_part_world_dimensions(part)
    dx = (float(uv[0]) - 0.5) * width
    dy = (float(uv[1]) - 0.5) * height
    if flip_x:
        dx = -dx
    r = math.radians(float(angle))
    c = math.cos(r); sn = math.sin(r)
    return dx * c + dy * sn, -dx * sn + dy * c


def _machine_explicit_snap_positions(item: dict, part: MachinePartDef) -> list[tuple[float, float]]:
    """World-space authored sockets used only by the Core/Gear/Pivot authority."""
    points = _machine_part_explicit_snap_points(part)
    if not points:
        return []
    x = float(item.get("x", 0.0)); y = float(item.get("y", 0.0))
    try:
        angle = float(item.get("angle", 0.0))
    except (TypeError, ValueError, OverflowError):
        angle = 0.0
    flip_x = bool(item.get("flip_x", False))
    return [(x + dx, y + dy) for dx, dy in (_machine_local_snap_offset(part, uv, angle, flip_x) for uv in points)]


def _machine_target_snap_positions(item: dict, part: MachinePartDef) -> list[tuple[float, float]]:
    """World-space connector anchors used by drag assist and accessory contact.

    Pipe endpoints remain their established rigid endpoints.  Finished irregular
    parts may expose conservative inferred perimeter anchors, but the drive
    triangle continues to receive only explicitly authored sockets through
    ``_machine_explicit_snap_positions``.
    """
    x = float(item.get("x", 0.0)); y = float(item.get("y", 0.0))
    try:
        angle = float(item.get("angle", 0.0))
    except (TypeError, ValueError, OverflowError):
        angle = 0.0
    if part.role == ROLE_PIPE:
        authored = pipe_endpoints(x, y, angle, _machine_part_natural_world_width(part))
        return [authored[PIPE_END_LEFT], authored[PIPE_END_RIGHT]]
    points = _machine_part_inferred_snap_points(part, as_source=False)
    if points:
        flip_x = bool(item.get("flip_x", False))
        return [(x + dx, y + dy) for dx, dy in (_machine_local_snap_offset(part, uv, angle, flip_x) for uv in points)]
    return [(x, y)]


def _machine_snap_assist_position(part: MachinePartDef, desired: tuple[float, float], placements: list[dict],
                                  machine_catalog: dict[str, MachinePartDef], *, moving_id: int | None = None,
                                  angle: float = 0.0, flip_x: bool = False) -> tuple[float, float]:
    """Magnetically align explicit or conservatively inferred part sockets.

    Base Core/Gear/Pivot pieces keep their established placement behavior.  New
    irregular control/actuator/sensor/tool/frame pieces can use their visible
    perimeter as a connector, while the fixed Pipe endpoint solver is untouched.
    """
    source_points = _machine_part_inferred_snap_points(part, as_source=True)
    if not source_points:
        return float(desired[0]), float(desired[1])
    sx, sy = float(desired[0]), float(desired[1])
    source_offsets = [_machine_local_snap_offset(part, uv, angle, flip_x) for uv in source_points]
    best: tuple[float, float, float] | None = None
    for item in placements:
        try:
            instance_id = int(item.get("id", -1))
        except (TypeError, ValueError, OverflowError):
            continue
        if moving_id is not None and instance_id == int(moving_id):
            continue
        target_part = machine_catalog.get(str(item.get("part", "")))
        if target_part is None:
            continue
        for tx, ty in _machine_target_snap_positions(item, target_part):
            for ox, oy in source_offsets:
                px, py = sx + ox, sy + oy
                distance = math.hypot(tx - px, ty - py)
                if distance <= MACHINE_SNAP_ASSIST_RADIUS_WORLD and (best is None or distance < best[0]):
                    best = (distance, sx + (tx - px), sy + (ty - py))
    return (best[1], best[2]) if best is not None else (sx, sy)


def _clear_pipe_constraints(item: dict) -> None:
    """Detach a pipe cleanly without altering the player's authored angle."""
    try:
        _MACHINE_PIPE_DYNAMICS.pop(int(item.get("id", -1)), None)
    except (TypeError, ValueError, OverflowError):
        pass
    for key in (
        "attach_phase",
        "attach_local_dx",
        "attach_local_dy",
        "pipe_anchor_end",
        "pipe_hinge_id",
        "pipe_orbit_dir",
        "pipe_brace_id",
        "pipe_brace_local_dx",
        "pipe_brace_local_dy",
        "pipe_brace_angle",
    ):
        item.pop(key, None)


def _clear_pipe_brace(item: dict) -> None:
    _MACHINE_PIPE_DYNAMICS.pop(int(item.get("id", -1)), None)
    for key in ("pipe_brace_id", "pipe_brace_local_dx", "pipe_brace_local_dy", "pipe_brace_angle"):
        item.pop(key, None)


def _shortest_angle_delta(target: float, current: float) -> float:
    return ((float(target) - float(current) + 180.0) % 360.0) - 180.0


def _pipe_gravity_angle(instance_id: int, anchor_end: str, initial_angle: float, phase_seconds: float) -> float:
    """Small bounded pendulum solver for a single-ended pipe hinge.

    World y points downward, so a left-anchored pipe settles at 270 degrees
    (its right/free end below the hinge) while a right-anchored pipe settles at
    90 degrees.  State is presentation-only; save files only need constraints.
    """
    target = 270.0 if normalize_pipe_end(anchor_end) == PIPE_END_LEFT else 90.0
    now = float(phase_seconds)
    state = _MACHINE_PIPE_DYNAMICS.get(instance_id)
    if state is None or now < float(state.get("t", now)) - 0.001:
        state = {"angle": float(initial_angle) % 360.0, "omega": 0.0, "t": now}
        _MACHINE_PIPE_DYNAMICS[instance_id] = state
        return float(state["angle"])

    elapsed = max(0.0, min(0.12, now - float(state.get("t", now))))
    if elapsed <= 0.0:
        return float(state.get("angle", target)) % 360.0
    steps = max(1, min(8, int(math.ceil(elapsed / (1.0 / 90.0)))))
    h = elapsed / steps
    angle = float(state.get("angle", target)) % 360.0
    omega = float(state.get("omega", 0.0))
    for _ in range(steps):
        delta = _shortest_angle_delta(target, angle)
        # Gravity-like restoring torque plus damping.  This is intentionally
        # restrained so machine links settle quickly instead of flailing.
        accel = 720.0 * math.sin(math.radians(delta)) - 7.5 * omega
        omega += accel * h
        omega = max(-420.0, min(420.0, omega))
        angle = (angle + omega * h) % 360.0
    state.update({"angle": angle, "omega": omega, "t": now})
    return angle


def _machine_runtime_transform(
    item: dict,
    part: MachinePartDef,
    network: dict[int, dict[str, object]],
    placements_by_id: dict[int, dict],
    phase_seconds: float,
    _visited: set[int] | None = None,
) -> tuple[float, float, float, float]:
    """Return presentation x, y, angle and an always-1.0 width scale.

    Pass 119 treats a Pipe as a fixed-length rigid rod.  A saved pin/hinge keeps
    one endpoint on the crank even when power changes.  With one hinge the rod
    swings under gravity; with a second saved hinge the brace is a passive
    direction reference only. Machine placements never receive force writes.
    """
    instance_id = int(item.get("id", -1))
    base_x = float(item.get("x", 0.0))
    base_y = float(item.get("y", 0.0))
    try:
        base_angle = float(item.get("angle", 0.0)) % 360.0
    except (TypeError, ValueError, OverflowError):
        base_angle = 0.0
    state = network.get(instance_id, {})
    role = part.role
    custom_functions = _MACHINE_CUSTOM_FUNCTIONS.get(part.key, ())
    # Player-authored custom parts use the existing machine motion vocabulary.
    # They are presentation-only effects driven by the normal powered state.
    if custom_functions and role in MACHINE_RUNTIME_FX_ROLES and bool(state.get("powered")):
        custom_x, custom_y, custom_angle = base_x, base_y, base_angle
        if "shake" in custom_functions:
            custom_x += math.sin(phase_seconds * math.tau * 7.0 + instance_id * 0.13) * 1.25
            custom_y += math.sin(phase_seconds * math.tau * 10.0 + instance_id * 0.29) * 0.6
        if "rotate" in custom_functions:
            custom_angle = (custom_angle + phase_seconds * 90.0) % 360.0
        if "tilt" in custom_functions:
            custom_angle = (custom_angle + math.sin(phase_seconds * math.tau * 1.35) * 7.0) % 360.0
        return custom_x, custom_y, custom_angle, 1.0
    # A Pipe hinge is mechanical, not electrical.  Once pinned, it remains a
    # constrained rigid link even if the drive loses power.  Other parts keep
    # their existing powered/unpowered presentation rules.
    if not bool(state.get("powered")) and not (role == ROLE_PIPE and item.get("pipe_hinge_id") is not None):
        return base_x, base_y, base_angle, 1.0

    visited = set(_visited or ())
    if instance_id in visited:
        return base_x, base_y, base_angle, 1.0
    visited.add(instance_id)

    if role == ROLE_PIVOT:
        gear_id = state.get("gear_id")
        try:
            gear = placements_by_id.get(int(gear_id)) if gear_id is not None else None
        except (TypeError, ValueError, OverflowError):
            gear = None
        if gear is not None:
            gear_part = _MACHINE_RUNTIME_CATALOG.get(str(gear.get("part", "")))
            if gear_part is not None:
                gear_x, gear_y, _, _ = _machine_runtime_transform(
                    gear, gear_part, network, placements_by_id, phase_seconds, visited
                )
                return gear_x, gear_y, (base_angle - phase_seconds * part.spin_dps) % 360.0, 1.0
        return base_x, base_y, (base_angle - phase_seconds * part.spin_dps) % 360.0, 1.0

    if role == ROLE_GEAR:
        shake_x = math.sin(phase_seconds * math.tau * 8.0) * 1.35
        shake_y = math.sin(phase_seconds * math.tau * 11.0 + 0.7) * 0.55
        return base_x + shake_x, base_y + shake_y, base_angle, 1.0

    if role == ROLE_PIPE:
        # Persistent first pin: once a Pipe endpoint is attached to a Pivot, the
        # joint remains mechanical even if the drive later loses power.
        hinge_raw = item.get("pipe_hinge_id", state.get("pivot_id"))
        try:
            hinge_id = int(hinge_raw) if hinge_raw is not None else None
        except (TypeError, ValueError, OverflowError):
            hinge_id = None
        pivot = placements_by_id.get(hinge_id) if hinge_id is not None else None
        if pivot is None:
            return base_x, base_y, base_angle, 1.0
        pivot_def = _MACHINE_RUNTIME_CATALOG.get(str(pivot.get("part", "")))
        if pivot_def is None or pivot_def.role != ROLE_PIVOT:
            return base_x, base_y, base_angle, 1.0

        pivot_state = network.get(hinge_id, {})
        pivot_speed = float(pivot_def.spin_dps or 72.0)
        try:
            attach_phase = float(item.get("attach_phase", 0.0)) % 360.0
        except (TypeError, ValueError, OverflowError):
            attach_phase = 0.0
        if bool(pivot_state.get("powered")):
            drive_angle = (phase_seconds * pivot_speed) % 360.0
            item["pipe_hold_drive_angle"] = round(drive_angle, 3)
        else:
            try:
                drive_angle = float(item.get("pipe_hold_drive_angle", attach_phase)) % 360.0
            except (TypeError, ValueError, OverflowError):
                drive_angle = attach_phase
        relative_drive_angle = (drive_angle - attach_phase) % 360.0

        pivot_x, pivot_y, _, _ = _machine_runtime_transform(
            pivot, pivot_def, network, placements_by_id, phase_seconds, visited
        )
        try:
            dx = float(item.get("attach_local_dx", state.get("local_dx", 0.0)))
            dy = float(item.get("attach_local_dy", state.get("local_dy", 0.0)))
        except (TypeError, ValueError, OverflowError):
            dx = dy = 0.0
        rdx, rdy = _rotate_world_offset(dx, dy, relative_drive_angle)
        anchor_x = pivot_x + rdx
        anchor_y = pivot_y + rdy
        anchor_end = normalize_pipe_end(item.get("pipe_anchor_end", state.get("anchor_end", PIPE_END_LEFT)))
        natural_length = _machine_part_natural_world_width(part)

        # Persistent second pin. The crank endpoint is kinematic, while the brace
        # is a passive anchor reference: it can guide Pipe angle but never moves
        # another player-placed machine part.
        brace_id_raw = item.get("pipe_brace_id", None)
        try:
            brace_id = int(brace_id_raw) if brace_id_raw is not None else None
        except (TypeError, ValueError, OverflowError):
            brace_id = None
        brace = placements_by_id.get(brace_id) if brace_id is not None else None
        brace_part = _MACHINE_RUNTIME_CATALOG.get(str(brace.get("part", ""))) if brace is not None else None
        if (
            brace is not None
            and brace_part is not None
            and brace_part.role in PIPE_BRACE_ROLES
            and brace_id not in visited
            and not bool(brace.get("locked"))
        ):
            brace_x, brace_y, brace_runtime_angle, _ = _machine_runtime_transform(
                brace, brace_part, network, placements_by_id, phase_seconds, visited
            )
            try:
                brace_dx = float(item.get("pipe_brace_local_dx", 0.0))
                brace_dy = float(item.get("pipe_brace_local_dy", 0.0))
                brace_angle = float(item.get("pipe_brace_angle", brace_runtime_angle)) % 360.0
            except (TypeError, ValueError, OverflowError):
                brace_dx = brace_dy = 0.0
                brace_angle = brace_runtime_angle
            brdx, brdy = _rotate_world_offset(brace_dx, brace_dy, brace_runtime_angle - brace_angle)
            target_x = brace_x + brdx
            target_y = brace_y + brdy
            vx = target_x - anchor_x
            vy = target_y - anchor_y
            distance = math.hypot(vx, vy)
            if distance <= 0.0001:
                fallback_angle = _pipe_gravity_angle(instance_id, anchor_end, base_angle, phase_seconds)
                ux = math.cos(math.radians(fallback_angle))
                uy = -math.sin(math.radians(fallback_angle))
                if anchor_end == PIPE_END_RIGHT:
                    ux, uy = -ux, -uy
            else:
                ux = vx / distance
                uy = vy / distance
            # Passive two-pin guide. Player-placed machine parts are anchors and
            # never receive position corrections from another component. The Pipe
            # keeps its authored rigid length and aims toward the saved brace, but
            # cannot back-drive/pull the brace body out of place.
            constrained_x = anchor_x + ux * natural_length
            constrained_y = anchor_y + uy * natural_length
            if anchor_end == PIPE_END_LEFT:
                cx, cy, pipe_angle, _ = pipe_pose_between(anchor_x, anchor_y, constrained_x, constrained_y)
            else:
                cx, cy, pipe_angle, _ = pipe_pose_between(constrained_x, constrained_y, anchor_x, anchor_y)
            _MACHINE_PIPE_DYNAMICS.pop(instance_id, None)
            return cx, cy, pipe_angle, 1.0

        # One-pin pendulum.  The Pipe remains a fixed-length rigid body and only
        # rotates around the saved hinge; gravity never changes its dimensions.
        gravity_angle = _pipe_gravity_angle(instance_id, anchor_end, base_angle, phase_seconds)
        direction_x = math.cos(math.radians(gravity_angle))
        direction_y = -math.sin(math.radians(gravity_angle))
        half = natural_length * 0.5
        if anchor_end == PIPE_END_LEFT:
            center_x = anchor_x + direction_x * half
            center_y = anchor_y + direction_y * half
        else:
            center_x = anchor_x - direction_x * half
            center_y = anchor_y - direction_y * half
        return center_x, center_y, gravity_angle, 1.0

    if role == ROLE_FAN:
        if state.get("attachment") == "pipe_child_spin":
            parent_id = state.get("parent_id")
            try:
                parent = placements_by_id.get(int(parent_id)) if parent_id is not None else None
            except (TypeError, ValueError, OverflowError):
                parent = None
            if parent is not None:
                parent_part = _MACHINE_RUNTIME_CATALOG.get(str(parent.get("part", "")))
                if parent_part is not None:
                    parent_x, parent_y, parent_angle, parent_width_scale = _machine_runtime_transform(
                        parent, parent_part, network, placements_by_id, phase_seconds, visited
                    )
                    parent_length = _machine_part_natural_world_width(parent_part) * parent_width_scale
                    endpoints = pipe_endpoints(parent_x, parent_y, parent_angle, parent_length)
                    pipe_end = normalize_pipe_end(state.get("pipe_end", PIPE_END_RIGHT), PIPE_END_RIGHT)
                    ex, ey = endpoints[pipe_end]
                    return ex, ey, (base_angle + phase_seconds * part.spin_dps) % 360.0, 1.0
        return base_x, base_y, (base_angle + phase_seconds * part.spin_dps) % 360.0, 1.0

    if role == ROLE_FRAME and bool(state.get("powered")):
        tick_phase = int(phase_seconds * 2.4) & 1
        return base_x, base_y, (base_angle - 4.0) if tick_phase == 0 else (base_angle + 4.0), 1.0

    return base_x, base_y, base_angle, 1.0


# Set by the main loop once the replaceable catalogue has been loaded. Keeping
# it module-local avoids changing save data merely to resolve presentation.
_MACHINE_RUNTIME_CATALOG: dict[str, MachinePartDef] = {}

def choose_player_state(hopping: bool, moving: bool, sprinting: bool) -> str:
    if hopping:
        return "jump"
    if moving and sprinting:
        return "sprint"
    if moving:
        return "walk"
    return "idle"

_PLAYER_SCALE_CACHE: dict[tuple[int, int, int, int], pygame.Surface] = {}


def _scaled_player_frame(source: pygame.Surface, width: int, height: int, facing: int) -> pygame.Surface:
    key = (id(source), int(width), int(height), -1 if facing < 0 else 1)
    cached = _PLAYER_SCALE_CACHE.get(key)
    if cached is not None:
        return cached
    frame = pygame.transform.smoothscale(source, (max(1, int(width)), max(1, int(height))))
    if facing < 0:
        frame = pygame.transform.flip(frame, True, False)
    if len(_PLAYER_SCALE_CACHE) >= 96:
        _PLAYER_SCALE_CACHE.clear()
    _PLAYER_SCALE_CACHE[key] = frame
    return frame


def _future_entropy_player_surface(source: pygame.Surface, t: float, stability: float = 0.0) -> pygame.Surface:
    """Present IO: darker, heavier, and only faintly unstable.

    Pass 84 removes the heavily broken multi-band glitch treatment. IO now keeps
    an intact silhouette in the Present, receives a slightly darker/cooler shade,
    and only shows a restrained one-pixel entropy shimmer unless Veil Ward is
    stabilizing him. Collision and logical position remain untouched.
    """
    stability = clamp(float(stability), 0.0, 1.0)
    width, height = source.get_size()
    out = source.copy()
    # Darken RGB only while preserving the authored per-pixel alpha silhouette.
    out.fill(PRESENT_IO_SHADE_MULTIPLY, special_flags=pygame.BLEND_RGBA_MULT)
    if width < 8 or height < 8 or stability >= 0.92:
        return out

    # Rare, restrained one-pixel shimmer rather than stacked horizontal tearing.
    shimmer = 0.5 + 0.5 * math.sin(t * 2.1)
    if shimmer < 0.72:
        return out
    band_h = max(1, height // 18)
    y = int(height * (0.46 + 0.035 * math.sin(t * 1.7)))
    y = max(0, min(height - band_h, y))
    direction = -1 if math.sin(t * 0.83) < 0.0 else 1
    shift = direction if stability < 0.55 else 0
    if shift:
        strip = out.subsurface(pygame.Rect(0, y, width, band_h)).copy()
        out.blit(strip, (shift, y))
    return out


def _draw_future_entropy_glow(target: pygame.Surface, glow: pygame.Surface | None,
                              actor_rect: pygame.Rect, t: float) -> None:
    """Subtle halo that contains Future IO's fading silhouette."""
    if glow is None or actor_rect.width <= 0 or actor_rect.height <= 0:
        return
    pulse = 0.5 + 0.5 * math.sin(t * 2.15)
    gw = max(8, int(actor_rect.width * (1.42 + 0.05 * pulse)))
    gh = max(8, int(actor_rect.height * (1.16 + 0.035 * pulse)))
    try:
        halo = pygame.transform.smoothscale(glow, (gw, gh)).copy()
        halo.set_alpha(int(34 + 14 * pulse))
        target.blit(halo, halo.get_rect(center=actor_rect.center))
    except Exception:
        return




class BattleSFX:
    """Small fail-soft cache for replaceable battle/UI sound effects.

    Each cue is discovered by semantic stem in ``assets/audio/sfx``.  The
    first matching WAV/OGG/MP3 is loaded once as ``pygame.mixer.Sound`` and
    reused; this avoids decoding on every attack while keeping the folder easy
    for the user to replace.
    """

    def __init__(self, volume: float = SFX_VOLUME) -> None:
        self.volume = clamp(float(volume), 0.0, 1.0)
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.enabled = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            for stem in BATTLE_SFX_CUES:
                path = next((SFX_DIR / f"{stem}{ext}" for ext in SFX_EXTENSIONS
                             if (SFX_DIR / f"{stem}{ext}").is_file()), None)
                if path is None:
                    continue
                try:
                    sound = pygame.mixer.Sound(str(path))
                    sound.set_volume(self.volume)
                    self.sounds[stem] = sound
                except (pygame.error, OSError, ValueError, TypeError):
                    continue
            self.enabled = bool(self.sounds)
        except (pygame.error, OSError, ValueError):
            self.enabled = False

    def play(self, cue: str) -> bool:
        if not self.enabled:
            return False
        sound = self.sounds.get(str(cue))
        if sound is None:
            return False
        try:
            sound.play()
            return True
        except pygame.error:
            return False

    def set_volume(self, value: float) -> None:
        self.volume = clamp(float(value), 0.0, 1.0)
        for sound in self.sounds.values():
            try:
                sound.set_volume(self.volume)
            except pygame.error:
                pass


class ExplorationSFX:
    """Fail-soft footsteps plus protected looping weather and machinery channels.

    Footsteps are distance-driven, so frame rate and animation changes cannot
    make the cadence drift. All files are replaceable by semantic stem beside
    the battle SFX and share the existing SFX volume setting.
    """

    def __init__(self, volume: float = SFX_VOLUME) -> None:
        self.volume = clamp(float(volume), 0.0, 1.0)
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.variants = {
            "walk": ("footstep_walk_1", "footstep_walk_2"),
            "sprint": ("footstep_sprint_1", "footstep_sprint_2"),
        }
        self.variant_indices = {"walk": 0, "sprint": 0}
        self.weather_channel: pygame.mixer.Channel | None = None
        self.weather_requested = False
        self.weather_role: str | None = None
        self.machine_channel: pygame.mixer.Channel | None = None
        self.machine_requested = False
        self.machine_gain = 0.0
        self.protected_channels = False
        self.enabled = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            # Pass 129: weather and powered machinery own two reserved channels.
            # Ordinary footsteps/battle cues use automatic channels and cannot steal
            # these loops. Pygame reserves channels from Sound.play() selection.
            if pygame.mixer.get_num_channels() < 16:
                pygame.mixer.set_num_channels(16)
            if pygame.mixer.set_reserved(2) >= 2:
                self.weather_channel = pygame.mixer.Channel(0)
                self.machine_channel = pygame.mixer.Channel(1)
                self.protected_channels = True
            for stem in EXPLORATION_SFX_CUES:
                path = next((SFX_DIR / f"{stem}{ext}" for ext in SFX_EXTENSIONS
                             if (SFX_DIR / f"{stem}{ext}").is_file()), None)
                if path is None:
                    continue
                try:
                    self.sounds[stem] = pygame.mixer.Sound(str(path))
                except (pygame.error, OSError, ValueError, TypeError):
                    continue
            self.enabled = bool(self.sounds)
            self.set_volume(self.volume)
        except (pygame.error, OSError, ValueError):
            self.enabled = False

    def play_footstep(self, sprinting: bool) -> bool:
        if not self.enabled:
            return False
        role = "sprint" if sprinting else "walk"
        available = tuple(stem for stem in self.variants[role] if stem in self.sounds)
        if not available:
            return False
        index = self.variant_indices[role] % len(available)
        self.variant_indices[role] += 1
        try:
            channel = self.sounds[available[index]].play()
            if channel is not None:
                channel.set_volume(clamp(self.volume * (0.78 if sprinting else 0.68), 0.0, 1.0))
            return channel is not None
        except pygame.error:
            return False

    def play_cue(self, cue: str, gain: float = 1.0) -> bool:
        """Play one optional exploration cue through the shared SFX setting."""
        if not self.enabled:
            return False
        sound = self.sounds.get(str(cue))
        if sound is None:
            return False
        try:
            channel = sound.play()
            if channel is not None:
                channel.set_volume(clamp(self.volume * float(gain), 0.0, 1.0))
            return channel is not None
        except (pygame.error, TypeError, ValueError, OverflowError):
            return False

    def update_weather(self, should_play: bool, world_key: str) -> None:
        preferred = "weather_future" if world_key == "a" else "weather_past"
        wanted_role = preferred if preferred in self.sounds else "weather_wind"
        should_play = bool(should_play and self.enabled and wanted_role in self.sounds)
        if should_play and self.weather_role != wanted_role and self.weather_channel is not None:
            try:
                self.weather_channel.fadeout(420)
            except pygame.error:
                pass
            if not self.protected_channels:
                self.weather_channel = None
        if should_play:
            try:
                if self.weather_channel is None or not self.weather_channel.get_busy():
                    if self.protected_channels and self.weather_channel is not None:
                        self.weather_channel.play(self.sounds[wanted_role], loops=-1, fade_ms=900)
                    else:
                        self.weather_channel = self.sounds[wanted_role].play(loops=-1, fade_ms=900)
                    if self.weather_channel is not None:
                        self.weather_channel.set_volume(clamp(self.volume * 0.34, 0.0, 1.0))
                        self.weather_role = wanted_role
            except pygame.error:
                # Keep ownership of the reserved channel even after a transient
                # playback error; dropping the object would fall back to automatic
                # channel selection on the next update.
                self.weather_channel = pygame.mixer.Channel(0) if self.protected_channels else None
        elif self.weather_requested and self.weather_channel is not None:
            try:
                self.weather_channel.fadeout(650)
            except pygame.error:
                pass
            if not self.protected_channels:
                self.weather_channel = None
            self.weather_role = None
        self.weather_requested = should_play

    def update_machine(self, should_play: bool, gain: float = 0.24) -> None:
        """Run one replaceable mechanical loop while Past machine power is active."""
        wanted_role = "machine_loop"
        gain = clamp(float(gain), 0.0, 1.0)
        should_play = bool(should_play and self.enabled and wanted_role in self.sounds)
        if should_play:
            try:
                if self.machine_channel is None or not self.machine_channel.get_busy():
                    if self.protected_channels and self.machine_channel is not None:
                        self.machine_channel.play(self.sounds[wanted_role], loops=-1, fade_ms=260)
                    else:
                        self.machine_channel = self.sounds[wanted_role].play(loops=-1, fade_ms=260)
                if self.machine_channel is not None:
                    self.machine_channel.set_volume(clamp(self.volume * gain, 0.0, 1.0))
                    self.machine_gain = gain
            except pygame.error:
                # Preserve the reserved machine lane after a transient mixer error.
                self.machine_channel = pygame.mixer.Channel(1) if self.protected_channels else None
        elif self.machine_requested and self.machine_channel is not None:
            try:
                self.machine_channel.fadeout(320)
            except pygame.error:
                pass
            if not self.protected_channels:
                self.machine_channel = None
            self.machine_gain = 0.0
        self.machine_requested = should_play

    def set_volume(self, value: float) -> None:
        self.volume = clamp(float(value), 0.0, 1.0)
        for sound in self.sounds.values():
            try:
                # Cue-specific balance is applied on the playback channel so
                # the persistent SFX slider is multiplied exactly once.
                sound.set_volume(self.volume)
            except pygame.error:
                pass
        if self.weather_channel is not None:
            try:
                self.weather_channel.set_volume(clamp(self.volume * 0.34, 0.0, 1.0))
            except pygame.error:
                pass
        if self.machine_channel is not None:
            try:
                self.machine_channel.set_volume(clamp(self.volume * self.machine_gain, 0.0, 1.0))
            except pygame.error:
                pass


class AmbientPlaylist:
    """Role-aware streamed music director.

    Pygame exposes a single streamed music channel, so exploration, ordinary
    interiors, and the final boss are mutually exclusive roles rather than
    overlapping tracks.  Filename prefixes are the replacement contract:

      ambient*   -> exploration
      interior*  -> ordinary Entity battles
      finalboss* -> final boss
      dead*      -> reserved death state
      saferoom*  -> reserved safe-room state

    Audio remains optional: discovery or playback failure never blocks launch.
    """
    ROLE_PREFIXES = {
        "ambient": ("ambient",),
        "interior": ("interior",),
        "finalboss": ("finalboss", "final_boss"),
        "dead": ("dead",),
        "saferoom": ("saferoom", "safe_room"),
    }

    def __init__(self) -> None:
        self.role_tracks: dict[str, list[Path]] = {role: [] for role in self.ROLE_PREFIXES}
        try:
            candidates = sorted(
                (p for p in AUDIO_DIR.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS),
                key=lambda p: p.name.lower(),
            ) if AUDIO_DIR.exists() else []
        except (OSError, ValueError):
            candidates = []
        for path in candidates:
            stem = path.stem.lower().replace("-", "_").replace(" ", "_")
            for role, prefixes in self.ROLE_PREFIXES.items():
                if any(stem.startswith(prefix) for prefix in prefixes):
                    self.role_tracks[role].append(path)
                    break

        self.role_indices = {role: -1 for role in self.ROLE_PREFIXES}
        self.current_role: str | None = None
        self.enabled = False
        self.volume = MUSIC_VOLUME
        self.event_type = pygame.USEREVENT + 23
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.set_endevent(self.event_type)
            self.enabled = any(self.role_tracks.values())
        except (pygame.error, OSError, ValueError):
            self.enabled = False

    def _load_current(self, role: str, index: int, fade_ms: int = 700) -> bool:
        tracks = self.role_tracks.get(role, [])
        if not self.enabled or not tracks:
            return False
        index %= len(tracks)
        try:
            # Disable the completion event while replacing the one global music
            # stream so an old role cannot enqueue a stale end-event.
            pygame.mixer.music.set_endevent()
            pygame.mixer.music.load(str(tracks[index]))
            # pygame resets music volume when a new file is loaded.
            pygame.mixer.music.set_volume(self.volume)
            loops = -1 if len(tracks) == 1 else 0
            pygame.mixer.music.play(loops, fade_ms=max(0, int(fade_ms)))
            pygame.mixer.music.set_endevent(self.event_type)
            self.role_indices[role] = index
            self.current_role = role
            return True
        except (pygame.error, OSError, ValueError, TypeError):
            try:
                pygame.mixer.music.set_endevent(self.event_type)
            except Exception:
                pass
            return False

    def play_role(self, role: str, *, force: bool = False, fade_ms: int = 700) -> bool:
        tracks = self.role_tracks.get(role, [])
        if not self.enabled or not tracks:
            return False
        try:
            if not force and self.current_role == role and pygame.mixer.music.get_busy():
                return True
        except pygame.error:
            pass
        previous = self.role_indices.get(role, -1)
        next_index = 0 if previous < 0 else (previous + 1) % len(tracks)
        return self._load_current(role, next_index, fade_ms)

    def start(self) -> None:
        self.play_role("ambient", force=True, fade_ms=900)

    def play_exploration(self) -> bool:
        return self.play_role("ambient")

    def play_battle(self, final_boss: bool = False) -> bool:
        return self.play_role("finalboss" if final_boss else "interior")

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.enabled or event.type != self.event_type or self.current_role is None:
            return
        tracks = self.role_tracks.get(self.current_role, [])
        if len(tracks) <= 1:
            return
        current = self.role_indices.get(self.current_role, 0)
        self._load_current(self.current_role, (current + 1) % len(tracks), 0)

    def set_volume(self, value: float) -> None:
        self.volume = clamp(float(value), 0.0, 1.0)
        try:
            pygame.mixer.music.set_volume(self.volume)
        except (pygame.error, ValueError):
            pass


def load_atmosphere_assets() -> dict[str, pygame.Surface]:
    names = {
        "far": "fog_volume_far.png",
        "mid": "fog_volume_mid.png",
        "near": "fog_volume_near.png",
        "wisp": "fog_wisp.png",
        "vignette": "vignette.png",
    }
    result: dict[str, pygame.Surface] = {}
    for key, name in names.items():
        path = DERIVED_DIR / name
        if path.exists():
            try:
                result[key] = pygame.image.load(str(path)).convert_alpha()
            except (pygame.error, OSError, ValueError):
                # Atmosphere is presentation only. A damaged optional texture must not crash gameplay.
                continue
    return result


def _load_weather_particle_paths(paths: list[Path] | tuple[Path, ...]) -> tuple[pygame.Surface, ...]:
    result: list[pygame.Surface] = []
    for path in paths:
        if not path.exists():
            continue
        try:
            image = pygame.image.load(str(path)).convert_alpha()
            if image.get_width() > 0 and image.get_height() > 0:
                result.append(_soft_edge_surface(image, 3))
        except (pygame.error, OSError, ValueError, TypeError):
            continue
    return tuple(result)


def _particle_png_paths() -> tuple[Path, ...]:
    """Return every replaceable particle PNG in stable order."""
    try:
        return tuple(sorted(
            (path for path in BOSS_DAMAGE_PARTICLE_DIR.iterdir()
             if path.is_file() and path.suffix.lower() == ".png"),
            key=lambda path: path.name.lower(),
        )) if BOSS_DAMAGE_PARTICLE_DIR.exists() else ()
    except OSError:
        return ()


def load_weather_particle_assets() -> dict[str, tuple[pygame.Surface, ...]]:
    """Load weather strictly from the replaceable particle bank.

    Pass 94 keeps active drones/mechanical fragments out of environmental weather.
    """
    shared = _load_weather_particle_paths(_particle_png_paths())
    return {world_key: shared for world_key in WORLD_VARIANT_FOLDERS}


def _weather_overlay_variant_paths(world_key: str) -> tuple[Path, ...]:
    """Return replaceable overlay variants for one era.

    Users may provide overlay_01.png, overlay_02.png, ... in the existing
    weather variant folder. If none exist, overlay.png remains the fallback.
    """
    folder = WEATHER_VARIANTS_DIR / WORLD_VARIANT_FOLDERS[world_key]
    try:
        numbered = tuple(sorted(
            (path for path in folder.iterdir()
             if path.is_file() and path.suffix.lower() == ".png" and path.stem.lower().startswith("overlay_")),
            key=lambda path: path.name.lower(),
        ))
    except OSError:
        numbered = ()
    if numbered:
        return numbered
    fallback = folder / "overlay.png"
    return (fallback,) if fallback.is_file() else ()


def _compose_weather_overlay_variant(path: Path, alpha: int) -> pygame.Surface | None:
    """Build one anchored full-screen weather field from a replaceable PNG."""
    try:
        surface = pygame.image.load(str(path)).convert_alpha()
        tw, th = surface.get_size()
        if tw <= 0 or th <= 0:
            return None
        normal = surface.copy()
        flip_x = pygame.transform.flip(surface, True, False)
        flip_y = pygame.transform.flip(surface, False, True)
        flip_xy = pygame.transform.flip(surface, True, True)
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        cols = (W // tw) + 2
        rows = (H // th) + 2
        blits = []
        for iy in range(rows):
            y = iy * th
            for ix in range(cols):
                x = ix * tw
                variant = (2 if (iy & 1) else 0) + (1 if (ix & 1) else 0)
                tile = (normal, flip_x, flip_y, flip_xy)[variant]
                blits.append((tile, (x, y)))
        if blits:
            layer.blits(blits, doreturn=False)
        layer.set_alpha(alpha)
        return layer
    except (pygame.error, OSError, ValueError, TypeError):
        return None


def load_weather_overlay_assets() -> dict[str, tuple[pygame.Surface, ...]]:
    """Load anchored weather overlay variants for each era.

    Each loaded surface already fills the logical viewport, so drawing can keep
    the field locked in place while only its internal colors and alpha flow.
    """
    result: dict[str, tuple[pygame.Surface, ...]] = {}
    for world_key in WORLD_VARIANT_FOLDERS:
        alpha = max(0, min(255, int(WEATHER_OVERLAY_ALPHA.get(world_key, 150))))
        variants = []
        for path in _weather_overlay_variant_paths(world_key):
            layer = _compose_weather_overlay_variant(path, alpha)
            if layer is not None:
                variants.append(layer)
        if variants:
            result[world_key] = tuple(variants)
    return result


def _blit_flowing_weather_variant(
    target: pygame.Surface,
    base: pygame.Surface,
    world_key: str,
    t: float,
    weight: float,
    phase: float,
) -> None:
    """Keep the weather field anchored while its internal colors drift."""
    if base.get_width() <= 0 or base.get_height() <= 0 or weight <= 0.0:
        return
    amp = float(WEATHER_OVERLAY_FLOW_AMPLITUDE.get(world_key, 14.0)) * _PRESENTATION_MOTION_SCALE
    band = max(4, int(WEATHER_OVERLAY_FLOW_BAND.get(world_key, 16)))
    speed_a, speed_b = WEATHER_OVERLAY_FLOW_SPEED.get(world_key, (0.26, 0.16))
    floor, pulse = WEATHER_OVERLAY_PULSE.get(world_key, (0.86, 0.14))
    flow = pygame.Surface((W, H), pygame.SRCALPHA)
    for y in range(0, H, band):
        strip_h = min(band, H - y)
        source = pygame.Rect(0, y, W, strip_h)
        dx = int(round(
            math.sin((t + phase) * speed_a + y * 0.024) * amp
            + math.cos((t + phase) * speed_b + y * 0.011) * (amp * 0.55)
        ))
        flow.blit(base, (dx, y), source)
        if dx > 0:
            flow.blit(base, (dx - W, y), source)
        elif dx < 0:
            flow.blit(base, (dx + W, y), source)
    alpha_weight = floor + pulse * (0.5 + 0.5 * math.sin((t + phase) * 0.37))
    flow.set_alpha(max(0, min(255, int(255 * weight * alpha_weight))))
    target.blit(flow, (0, 0))


_WEATHER_FLOW_FRAME_CACHE: dict[str, tuple[int, tuple[int, ...], pygame.Surface]] = {}


def _draw_tiled_weather_overlay(
    target: pygame.Surface,
    variants: tuple[pygame.Surface, ...] | None,
    world_key: str,
    t: float,
) -> None:
    """Render slow anchored nebula motion from a bounded 15 Hz frame cache."""
    if not variants:
        return
    tick = int(max(0.0, t) * WEATHER_OVERLAY_RENDER_HZ)
    signature = tuple(id(surface) for surface in variants)
    cached = _WEATHER_FLOW_FRAME_CACHE.get(world_key)
    if cached is not None and cached[0] == tick and cached[1] == signature:
        target.blit(cached[2], (0, 0))
        return

    sample_t = tick / max(1.0, WEATHER_OVERLAY_RENDER_HZ)
    frame = pygame.Surface((W, H), pygame.SRCALPHA)
    count = len(variants)
    if count == 1:
        _blit_flowing_weather_variant(frame, variants[0], world_key, sample_t, 1.0, 0.0)
    else:
        cycle = max(3.0, float(WEATHER_OVERLAY_CROSSFADE.get(world_key, 18.0)))
        phase = (sample_t / cycle) % count
        index_a = int(math.floor(phase)) % count
        frac = phase - math.floor(phase)
        index_b = (index_a + 1) % count
        _blit_flowing_weather_variant(frame, variants[index_a], world_key, sample_t, 1.0 - frac, index_a * 0.77)
        _blit_flowing_weather_variant(frame, variants[index_b], world_key, sample_t, frac, index_b * 0.77)
    _WEATHER_FLOW_FRAME_CACHE[world_key] = (tick, signature, frame)
    target.blit(frame, (0, 0))


def _apply_walk_overcast(surface: pygame.Surface, world_key: str) -> pygame.Surface:
    """Return a color-graded copy of the walk layer with alpha preserved.

    The grade is intentionally limited to RGB special blends. Transparent
    pixels stay transparent, so overcast can never create new visible geometry
    or alter gameplay masks.
    """
    try:
        result = surface.copy()
        mult = WALK_OVERCAST_MULTIPLY.get(world_key, (255, 255, 255))
        lift = WALK_OVERCAST_LIFT.get(world_key, (0, 0, 0))
        strength = clamp(float(WALK_OVERCAST_STRENGTH.get(world_key, 0.0)), 0.0, 1.0)
        if strength <= 0.0:
            return result
        mixed = tuple(int(round(255 + (component - 255) * strength)) for component in mult)
        result.fill((*mixed, 255), special_flags=pygame.BLEND_RGBA_MULT)
        scaled_lift = tuple(int(round(component * strength)) for component in lift)
        if any(scaled_lift):
            result.fill((*scaled_lift, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return result
    except (pygame.error, ValueError, TypeError, OverflowError, MemoryError):
        return surface


def _draw_time_shift_response(target: pygame.Surface, surface: pygame.Surface | None,
                              world_key: str, timer: float) -> None:
    """Immediate non-black time-shift response after the destination is selected."""
    if TIME_SHIFT_IN <= 0.0:
        return
    strength = clamp(timer / TIME_SHIFT_IN, 0.0, 1.0)
    # Destination stays visible under the effect from the first frame.
    _draw_fullscreen_variant(target, surface, int(TIME_SHIFT_FLASH_ALPHA * strength * _PRESENTATION_FLASH_SCALE))
    wash = pygame.Surface((W, H), pygame.SRCALPHA)
    color = (74, 176, 214) if world_key == "a" else (158, 104, 206)
    wash.fill((*color, int(72 * strength * _PRESENTATION_FLASH_SCALE)))
    target.blit(wash, (0, 0))
    # Brief horizontal discontinuities make the response read instantly without
    # obscuring control behind a full black fade.
    line_alpha = int(115 * strength * _PRESENTATION_FLASH_SCALE)
    lines = pygame.Surface((W, H), pygame.SRCALPHA)
    for y in range(10, H, 42):
        pygame.draw.line(lines, (*color, line_alpha), (0, y), (W, y), 1)
    target.blit(lines, (0, 0))


def load_transition_variant_assets() -> dict[str, pygame.Surface]:
    """Load optional screen-space transition overlays by stable semantic name."""
    result: dict[str, pygame.Surface] = {}
    for role, filename in TRANSITION_VARIANT_FILES.items():
        path = TRANSITION_VARIANTS_DIR / filename
        if not path.is_file():
            continue
        try:
            surface = pygame.image.load(str(path)).convert_alpha()
            if surface.get_width() > 0 and surface.get_height() > 0:
                result[role] = surface
        except (pygame.error, OSError, ValueError, TypeError):
            continue
    return result


def _draw_fullscreen_variant(target: pygame.Surface, surface: pygame.Surface | None, alpha: int) -> None:
    if surface is None or alpha <= 0:
        return
    try:
        overlay = surface
        if overlay.get_size() != target.get_size():
            overlay = pygame.transform.smoothscale(overlay, target.get_size())
        else:
            overlay = overlay.copy()
        overlay.set_alpha(max(0, min(255, int(alpha))))
        target.blit(overlay, (0, 0))
    except (pygame.error, ValueError, TypeError, OverflowError, MemoryError):
        return


def _spawn_weather_particle(active: list[dict], assets: tuple[pygame.Surface, ...],
                            world_key: str, rng: random.Random, warm: bool = False) -> None:
    if not assets or len(active) >= WEATHER_PARTICLE_MAX:
        return
    try:
        source = rng.choice(assets)
        wind = float(WEATHER_WIND_SPEED.get(world_key, 110.0))
        vx = wind * rng.uniform(0.72, 1.28)
        travel = W + WEATHER_MARGIN * 2.0
        life = travel / max(1.0, abs(vx))
        progress = rng.uniform(0.02, 0.90) if warm else 0.0
        x = (-WEATHER_MARGIN + travel * progress) if vx >= 0.0 else (W + WEATHER_MARGIN - travel * progress)
        y = rng.uniform(54.0, H - 70.0)
        sw, sh = source.get_size()
        scale = rng.uniform(1.1, 2.8) * (1.08 if world_key == "b" else 1.0)
        max_side = 58
        factor = min(scale, max_side / max(1.0, float(max(sw, sh))))
        size = (max(3, int(round(sw * factor))), max(3, int(round(sh * factor))))
        angle = rng.uniform(-9.0, 9.0) + (-4.0 if vx < 0.0 else 4.0)
        surface = pygame.transform.rotozoom(source, angle, size[0] / max(1.0, float(sw)))
        active.append({
            "surface": surface,
            "x": x,
            "y": y,
            "vx": vx,
            "vy": rng.uniform(-7.0, 8.0),
            "age": progress * life,
            "life": life,
            "phase": rng.uniform(0.0, math.tau),
            "flutter": rng.uniform(5.0, 14.0),
            "alpha": rng.randint(56, 116),
            "front": rng.random() < 0.30,
        })
    except (pygame.error, ValueError, TypeError, OverflowError, MemoryError):
        return


def _seed_weather_particles(active: list[dict], assets: tuple[pygame.Surface, ...],
                            world_key: str, rng: random.Random) -> None:
    for _ in range(min(12, WEATHER_PARTICLE_MAX)):
        _spawn_weather_particle(active, assets, world_key, rng, warm=True)


def _update_weather_particles(active: list[dict], assets: tuple[pygame.Surface, ...],
                              world_key: str, rng: random.Random, dt: float,
                              spawn_accumulator: float, spawn_enabled: bool) -> float:
    dt = max(0.0, min(0.05, float(dt)))
    if spawn_enabled and assets:
        spawn_accumulator += dt * float(WEATHER_PARTICLE_RATE.get(world_key, 5.0))
        while spawn_accumulator >= 1.0 and len(active) < WEATHER_PARTICLE_MAX:
            _spawn_weather_particle(active, assets, world_key, rng)
            spawn_accumulator -= 1.0
    else:
        spawn_accumulator = min(spawn_accumulator, 0.99)

    keep: list[dict] = []
    for particle in active[:WEATHER_PARTICLE_MAX]:
        try:
            particle["age"] = float(particle["age"]) + dt
            if particle["age"] >= float(particle["life"]):
                continue
            particle["phase"] = float(particle["phase"]) + dt * 2.1
            particle["x"] = float(particle["x"]) + float(particle["vx"]) * dt
            flutter = math.sin(float(particle["phase"])) * float(particle["flutter"])
            particle["y"] = float(particle["y"]) + (float(particle["vy"]) + flutter) * dt
            if (-WEATHER_MARGIN * 1.4 <= particle["x"] <= W + WEATHER_MARGIN * 1.4
                    and -80.0 <= particle["y"] <= H + 80.0):
                keep.append(particle)
        except (TypeError, ValueError, OverflowError):
            continue
    active[:] = keep
    return spawn_accumulator


def _draw_weather_particles(target: pygame.Surface, active: list[dict], front: bool) -> None:
    """Draw wind particles with a soft entrance and an earlier exit fade."""
    for particle in active[:WEATHER_PARTICLE_MAX]:
        if bool(particle.get("front", False)) != bool(front):
            continue
        try:
            surface = particle.get("surface")
            if not isinstance(surface, pygame.Surface):
                continue
            x = float(particle["x"])
            vx = float(particle["vx"])
            if vx >= 0.0:
                entrance = clamp((x + WEATHER_MARGIN) / 150.0, 0.0, 1.0)
                exit_fade = clamp((W + WEATHER_MARGIN - x) / 240.0, 0.0, 1.0)
            else:
                entrance = clamp((W + WEATHER_MARGIN - x) / 150.0, 0.0, 1.0)
                exit_fade = clamp((x + WEATHER_MARGIN) / 240.0, 0.0, 1.0)
            remaining = float(particle["life"]) - float(particle["age"])
            life_fade = clamp(remaining / 0.75, 0.0, 1.0)
            fade = min(entrance, exit_fade, life_fade)
            fade = fade * fade * (3.0 - 2.0 * fade)
            surface.set_alpha(int(float(particle["alpha"]) * fade))
            target.blit(surface, surface.get_rect(center=(int(x), int(particle["y"]))))
        except (pygame.error, TypeError, ValueError, OverflowError):
            continue

def _soft_edge_surface(source: pygame.Surface, edge_px: int = 18) -> pygame.Surface:
    """Multiply an FX surface by a rounded edge-alpha ramp.

    This deliberately avoids PixelArray/surfarray paths: the Pass 32 native probe
    already proved ordinary SRCALPHA surfaces, draws, transforms, and blits on the
    target Windows runtime.  The result preserves the artwork while making the
    texture boundary dissolve into the scene.
    """
    try:
        surface = source.copy()
        w, h = surface.get_size()
        edge = max(2, min(int(edge_px), max(2, w // 3), max(2, h // 3)))
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        mask.fill((255, 255, 255, 0))
        for inset in range(0, edge + 1):
            t = inset / max(1, edge)
            smooth = t * t * (3.0 - 2.0 * t)
            alpha = int(round(255 * smooth))
            rect = pygame.Rect(inset, inset, max(1, w - inset * 2), max(1, h - inset * 2))
            pygame.draw.rect(mask, (255, 255, 255, alpha), rect, border_radius=max(0, edge - inset))
        surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return surface
    except (pygame.error, ValueError, TypeError, OverflowError, MemoryError):
        return source.copy()


def load_battle_assets() -> dict[str, pygame.Surface]:
    result: dict[str, pygame.Surface] = {}
    # Pass 50 checks the semantic Entity slot first, then keeps the accepted
    # Pass 41 background and procedural chamber as two fail-soft fallbacks.
    # Load only the authored backgrounds for currently playable Entities.
    # This avoids pulling the entire staged boss roster into memory.
    for entity_id, role in BATTLE_ROLE_BY_ENTITY.items():
        background_path = BATTLE_VARIANTS_DIR / f"{role}.png"
        if not background_path.is_file():
            continue
        try:
            result[f"background_{entity_id}"] = pygame.image.load(str(background_path)).convert()
        except (pygame.error, OSError, ValueError, TypeError):
            continue
    if BATTLE_BACKGROUND_ASSET.is_file():
        try:
            result["background"] = pygame.image.load(str(BATTLE_BACKGROUND_ASSET)).convert()
        except (pygame.error, OSError, ValueError, TypeError):
            pass
    if BATTLE_FALLBACK_CHAMBER_ASSET.is_file():
        try:
            result["fallback_chamber"] = pygame.image.load(str(BATTLE_FALLBACK_CHAMBER_ASSET)).convert_alpha()
        except (pygame.error, OSError, ValueError, TypeError):
            pass
    # Pass 42 imports only the two user-authored support presences from the
    # returned donor build.  Their historical filenames are preserved exactly;
    # the runtime gives them semantic roles without renaming the files.
    for key, path in (("gleebs", BATTLE_GLEEBS_ASSET), ("gate", BATTLE_GATE_ASSET)):
        if not path.exists():
            continue
        try:
            image = pygame.image.load(str(path)).convert_alpha()
            result[key] = _subdued_obelisk_surface(image) if key == "gate" else image
        except (pygame.error, OSError, ValueError, TypeError):
            continue

    # Keep the established Pass 35 derived spires loaded only as fail-soft
    # fallbacks.  They are used when a replacement support image is absent.
    for key, filename in BATTLE_ASSET_FILES.items():
        path = DERIVED_DIR / filename
        if not path.exists():
            continue
        try:
            image = pygame.image.load(str(path)).convert_alpha()
            if key in {"fog", "wisp", "glow"}:
                image = _soft_edge_surface(image, 22 if key != "wisp" else 14)
            result[key] = image
        except (pygame.error, OSError, ValueError, TypeError):
            continue
    return result


def _png_paths_from_dirs(*dirs: Path) -> tuple[Path, ...]:
    """Return unique PNG paths from optional asset directories, in stable order."""
    found: dict[str, Path] = {}
    for directory in dirs:
        try:
            paths = sorted(
                (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".png"),
                key=lambda path: path.name.lower(),
            )
        except OSError:
            continue
        for path in paths:
            # Keep both differently named files, but never duplicate the exact path.
            found[str(path.resolve())] = path
    return tuple(found.values())


def _scale_surface_to_fit(source: pygame.Surface, max_size: tuple[int, int], *, allow_upscale: bool = False, min_side: int = 2) -> pygame.Surface:
    """Scale a Surface to fit a box while preserving its original aspect ratio."""
    sw, sh = source.get_size()
    if sw <= 0 or sh <= 0:
        raise ValueError("invalid source dimensions")
    max_w, max_h = max(1, int(max_size[0])), max(1, int(max_size[1]))
    factor = min(max_w / float(sw), max_h / float(sh))
    if not allow_upscale:
        factor = min(1.0, factor)
    if abs(factor - 1.0) < 1e-6:
        return source
    width = max(min_side, int(round(sw * factor)))
    height = max(min_side, int(round(sh * factor)))
    return pygame.transform.smoothscale(source, (width, height))


def _stable_memory_debris_surface(source: pygame.Surface, token: str) -> pygame.Surface:
    """Give a world-debris particle a stable orientation without stretching it.

    The source remains from assets/source/particles; rotation is deterministic so
    persistent lore placements never change appearance across reloads.
    """
    data = token.encode("utf-8", errors="ignore")
    seed = sum((i + 3) * value for i, value in enumerate(data))
    angle = (-1 if seed % 2 else 1) * (5.0 + float(seed % 11))
    rotated = pygame.transform.rotate(source, angle)
    bounds = rotated.get_bounding_rect(min_alpha=3)
    if bounds.width > 0 and bounds.height > 0:
        rotated = rotated.subsurface(bounds).copy()
    return rotated


def _drone_facing_surface(asset: pygame.Surface, heading: float) -> pygame.Surface:
    """Return a cached left/right active-drone image; never rescale or stretch here."""
    flip_x = heading < 0.0
    key = (id(asset), flip_x)
    cached = _DRONE_FACING_CACHE.get(key)
    if cached is not None:
        return cached
    cached = pygame.transform.flip(asset, True, False) if flip_x else asset
    if len(_DRONE_FACING_CACHE) >= 64:
        _DRONE_FACING_CACHE.clear()
    _DRONE_FACING_CACHE[key] = cached
    return cached


def _load_shared_fragment_surfaces(max_size: tuple[int, int] | None = None) -> tuple[pygame.Surface, ...]:
    """Load drones plus any legacy debris as one non-destructive fragment pool."""
    result: list[pygame.Surface] = []
    for path in _png_paths_from_dirs(*SHARED_FRAGMENT_DIRS):
        try:
            image = pygame.image.load(str(path)).convert_alpha()
            if image.get_width() <= 0 or image.get_height() <= 0:
                continue
            if max_size is not None:
                image = _scale_surface_to_fit(image, max_size)
            result.append(image)
        except (pygame.error, OSError, ValueError, TypeError, OverflowError):
            continue
    return tuple(result)


def load_boss_damage_fx_assets() -> dict[str, tuple[pygame.Surface, ...]]:
    """Load a small bounded selection of user-authored hit FX.

    These are optional presentation. Missing/corrupt files never block startup
    or combat. Original decoded art is retained; hit-time scaling always starts
    from the original Surface rather than repeatedly transforming a derivative.
    """
    result: dict[str, list[pygame.Surface]] = {"debris": list(_load_shared_fragment_surfaces()), "particles": []}
    for path in _particle_png_paths():
        try:
            image = pygame.image.load(str(path)).convert_alpha()
            if image.get_width() > 0 and image.get_height() > 0:
                result["particles"].append(image)
        except (pygame.error, OSError, ValueError, TypeError):
            continue
    return {key: tuple(images) for key, images in result.items()}


def _spawn_boss_damage_fx(active: list[dict], assets: dict[str, tuple[pygame.Surface, ...]],
                          damage: int, hit_serial: int) -> None:
    """Spawn one deterministic, bounded burst at the First Witness.

    Boss motion remains stationary by design; impact readability comes from
    authored fragments and particles breaking away from the fixed Entity.
    """
    if damage <= 0 or len(active) >= BOSS_DAMAGE_FX_MAX:
        return
    try:
        rng = random.Random(0x10B055 + int(hit_serial) * 131 + int(damage) * 17)
        origin_x, origin_y = 886.0, 334.0
        debris_sources = assets.get("debris", ())
        particle_sources = assets.get("particles", ())

        def add_piece(source: pygame.Surface, kind: str, scale: float, vx: float, vy: float,
                      life: float, gravity: float) -> None:
            if len(active) >= BOSS_DAMAGE_FX_MAX:
                return
            sw, sh = source.get_size()
            max_side = 54 if kind == "debris" else 34
            target_side = max(2, int(round(min(max_side, max(sw, sh) * scale))))
            surface = _scale_surface_to_fit(source, (target_side, target_side), allow_upscale=False)
            if kind == "debris":
                surface = pygame.transform.rotate(surface, rng.uniform(-36.0, 36.0))
            active.append({
                "surface": surface, "x": origin_x + rng.uniform(-20.0, 20.0),
                "y": origin_y + rng.uniform(-28.0, 24.0), "vx": vx, "vy": vy,
                "life": life, "max_life": life, "gravity": gravity, "kind": kind,
            })

        if debris_sources:
            for _ in range(min(5, 2 + max(1, int(damage)))):
                add_piece(rng.choice(debris_sources), "debris", rng.uniform(0.22, 0.48),
                          rng.uniform(-115.0, 105.0), rng.uniform(-155.0, -62.0),
                          rng.uniform(0.58, 0.82), rng.uniform(150.0, 205.0))
        if particle_sources:
            for _ in range(min(10, 4 + max(1, int(damage)) * 2)):
                add_piece(rng.choice(particle_sources), "particle", rng.uniform(0.72, 1.35),
                          rng.uniform(-145.0, 135.0), rng.uniform(-120.0, 30.0),
                          rng.uniform(0.34, 0.58), rng.uniform(25.0, 75.0))
    except (pygame.error, OSError, ValueError, TypeError, OverflowError, MemoryError):
        return


def _spawn_boss_shatter_fx(active: list[dict], assets: dict[str, tuple[pygame.Surface, ...]],
                           hit_serial: int) -> None:
    """Spawn the bounded final breakup for a defeated Entity.

    The First Witness itself never locomotes.  The final-hit readability comes
    from a larger deterministic release of the same authored fragment/particle
    language already used by normal Presence loss.
    """
    try:
        rng = random.Random(0x51A77E + int(hit_serial) * 173)
        origin_x, origin_y = 886.0, 326.0
        debris_sources = assets.get("debris", ())
        particle_sources = assets.get("particles", ())

        def add_piece(source: pygame.Surface, kind: str, scale: float, vx: float, vy: float,
                      life: float, gravity: float) -> None:
            if len(active) >= BOSS_DAMAGE_FX_MAX:
                return
            sw, sh = source.get_size()
            max_side = 68 if kind == "debris" else 42
            target_side = max(2, int(round(min(max_side, max(sw, sh) * scale))))
            surface = _scale_surface_to_fit(source, (target_side, target_side), allow_upscale=False)
            if kind == "debris":
                surface = pygame.transform.rotate(surface, rng.uniform(-36.0, 36.0))
            active.append({
                "surface": surface, "x": origin_x + rng.uniform(-28.0, 28.0),
                "y": origin_y + rng.uniform(-42.0, 30.0), "vx": vx, "vy": vy,
                "life": life, "max_life": life, "gravity": gravity, "kind": kind,
            })

        if debris_sources:
            for _ in range(12):
                add_piece(rng.choice(debris_sources), "debris", rng.uniform(0.30, 0.62),
                          rng.uniform(-205.0, 195.0), rng.uniform(-245.0, -78.0),
                          rng.uniform(0.92, 1.34), rng.uniform(155.0, 225.0))
        if particle_sources:
            for _ in range(22):
                add_piece(rng.choice(particle_sources), "particle", rng.uniform(0.78, 1.55),
                          rng.uniform(-235.0, 225.0), rng.uniform(-190.0, 58.0),
                          rng.uniform(0.62, 1.08), rng.uniform(18.0, 72.0))
    except (pygame.error, OSError, ValueError, TypeError, OverflowError, MemoryError):
        return


def _update_boss_damage_fx(active: list[dict], dt: float) -> None:
    dt = max(0.0, min(0.05, float(dt)))
    keep: list[dict] = []
    for piece in active[:BOSS_DAMAGE_FX_MAX]:
        try:
            piece["life"] = float(piece.get("life", 0.0)) - dt
            if piece["life"] <= 0.0:
                continue
            piece["vy"] = float(piece.get("vy", 0.0)) + float(piece.get("gravity", 0.0)) * dt
            piece["x"] = float(piece.get("x", 0.0)) + float(piece.get("vx", 0.0)) * dt
            piece["y"] = float(piece.get("y", 0.0)) + float(piece.get("vy", 0.0)) * dt
            keep.append(piece)
        except (TypeError, ValueError, OverflowError):
            continue
    active[:] = keep


def _draw_boss_damage_fx(target: pygame.Surface, active: list[dict]) -> None:
    """Draw fragments after the boss sprite so damage reads as material loss."""
    for piece in active[:BOSS_DAMAGE_FX_MAX]:
        try:
            surface = piece.get("surface")
            if not isinstance(surface, pygame.Surface):
                continue
            ratio = max(0.0, min(1.0, float(piece["life"]) / max(0.001, float(piece["max_life"]))))
            # Pygame 2 combines whole-Surface alpha with the PNG's pixel alpha,
            # preserving irregular authored fragment edges while the burst fades.
            surface.set_alpha(int(255 * min(1.0, ratio * 1.65)))
            target.blit(surface, surface.get_rect(center=(int(piece["x"]), int(piece["y"]))))
        except (pygame.error, TypeError, ValueError, OverflowError):
            continue


def _battle_blit_fit(target: pygame.Surface, image: pygame.Surface | None, box: pygame.Rect,
                     alpha: int = 255) -> pygame.Rect | None:
    """Fit a support sprite inside *box* without stretching its authored ratio."""
    if image is None or box.width <= 0 or box.height <= 0:
        return None
    try:
        iw, ih = image.get_size()
        if iw <= 0 or ih <= 0:
            return None
        factor = min(box.width / float(iw), box.height / float(ih))
        size = (max(1, int(round(iw * factor))), max(1, int(round(ih * factor))))
        scaled = pygame.transform.smoothscale(image, size)
        if alpha < 255:
            scaled.set_alpha(max(0, min(255, int(alpha))))
        rect = scaled.get_rect(center=box.center)
        target.blit(scaled, rect)
        return rect
    except (pygame.error, ValueError, TypeError, OverflowError):
        return None


def _battle_blit_scaled(target: pygame.Surface, image: pygame.Surface | None, rect: pygame.Rect,
                        alpha: int = 255, flip_x: bool = False) -> pygame.Rect | None:
    if image is None or rect.width <= 0 or rect.height <= 0:
        return None
    try:
        scaled = pygame.transform.smoothscale(image, rect.size)
        if flip_x:
            scaled = pygame.transform.flip(scaled, True, False)
        if alpha < 255:
            scaled.set_alpha(max(0, min(255, int(alpha))))
        target.blit(scaled, rect)
        return rect
    except (pygame.error, ValueError, TypeError, OverflowError):
        return None


def _draw_soft_beam(target: pygame.Surface, start: tuple[int, int], end: tuple[int, int], phase: float) -> None:
    """Layered lantern beam with no hard texture boundary."""
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    pulse = 0.82 + math.sin(phase * 15.0) * 0.12
    for width, alpha in ((18, 20), (10, 34), (5, 72), (2, 180)):
        pygame.draw.line(overlay, (155, 222, 238, int(alpha * pulse)), start, end, width)
    for radius, alpha in ((30, 16), (18, 34), (8, 120)):
        pygame.draw.circle(overlay, (180, 232, 242, int(alpha * pulse)), end, radius)
    target.blit(overlay, (0, 0))


def resonance_response_message(world_key: str, player_pos: tuple[float, float],
                               entity_pos: tuple[float, float], entity_defeated: bool,
                               shrine_activated: bool,
                               unread_echo_pos: tuple[float, float] | None = None,
                               story_complete: bool = False) -> str:
    """Return bounded hot/cold investigation feedback without exposing a waypoint."""
    if world_key == "b" and not entity_defeated:
        distance = pygame.Vector2(player_pos).distance_to(entity_pos)
        band = causal_resonance_band(distance, RESONANCE_NEAR_DISTANCE, RESONANCE_MID_DISTANCE)
        if band == "near":
            return "THE FIRST WITNESS ANSWERS: NEAR."
        if band == "middle":
            return "THE FIRST WITNESS ANSWERS THROUGH THE DARK."
        return "A FAINT WITNESS RECORD ANSWERS."
    if world_key == "a" and not entity_defeated:
        distance = pygame.Vector2(player_pos).distance_to(FUTURE_CLUE_POS)
        if distance <= FUTURE_CLUE_INTERACT_RADIUS * 1.6:
            return "THE ABSENCE ANSWERS BENEATH YOUR FEET."
        return "THE MISSING RECORD PULLS THROUGH THE FUTURE."
    if shrine_activated and unread_echo_pos is not None:
        distance = pygame.Vector2(player_pos).distance_to(unread_echo_pos)
        band = causal_resonance_band(distance, RESONANCE_NEAR_DISTANCE, RESONANCE_MID_DISTANCE)
        if band == "near":
            return "UNREAD MEMORY DEBRIS ANSWERS: NEAR."
        if band == "middle":
            return "UNREAD MEMORY DEBRIS ANSWERS THROUGH STATIC."
        return "A FAINT MEMORY DEBRIS RECORD ANSWERS."
    if shrine_activated and not story_complete:
        return "AN UNREAD WITNESS ECHO ANSWERS FROM ANOTHER AGE."
    if story_complete:
        return "THE RESTORED SHRINE ANSWERS CLEARLY."
    if world_key == "a" and entity_defeated:
        return "THE RECORDED SHRINE ANSWERS." if shrine_activated else "THE SHRINE WAITS TO BE BOUND."
    return "NO UNBOUND RECORD ANSWERS."


def _draw_absence_echo(target: pygame.Surface, glow: pygame.Surface | None,
                       center: tuple[int, int], phase: float, resonance_learned: bool,
                       marker_img: pygame.Surface | None = None) -> None:
    """Soft Future clue marker; its core placeholder is replaceable from assets/current/world_fx."""
    pulse = 0.82 + math.sin(phase * 2.4) * 0.12
    size = int((118 if resonance_learned else 104) * pulse)
    alpha = 92 if resonance_learned else 62
    if glow is not None:
        _battle_blit_scaled(
            target,
            glow,
            pygame.Rect(center[0] - size // 2, center[1] - size // 2, size, size),
            alpha,
        )
    x, y = center
    if marker_img is not None:
        core_size = (72 if resonance_learned else 64, 92 if resonance_learned else 82)
        core = _scaled_world_object_surface(marker_img, *core_size).copy()
        core.set_alpha(112 if resonance_learned else 82)
        target.blit(core, core.get_rect(center=(x, y)))
    else:
        trace = pygame.Surface((W, H), pygame.SRCALPHA)
        color = (145, 208, 222, 92 if resonance_learned else 62)
        pygame.draw.aaline(trace, color, (x - 22, y - 31), (x - 8, y - 12))
        pygame.draw.aaline(trace, color, (x - 5, y - 6), (x + 4, y + 5))
        pygame.draw.aaline(trace, color, (x + 7, y + 12), (x + 23, y + 31))
        target.blit(trace, (0, 0))


def _draw_gleebs_anchor(target: pygame.Surface, glow: pygame.Surface | None,
                        center: tuple[int, int], phase: float, future: bool,
                        anchor_img: pygame.Surface | None = None) -> None:
    """Temporal anchor with a replaceable core image and fail-soft procedural fallback."""
    color = (168, 222, 232) if future else (182, 162, 232)
    pulse = 0.5 + 0.5 * math.sin(phase * (1.8 if future else 1.5))
    if anchor_img is not None:
        size = 132 + int(round(10 * pulse))
        core = _scaled_world_object_surface(anchor_img, size, size).copy()
        core.set_alpha(154 + int(58 * pulse))
        target.blit(core, core.get_rect(center=center))
    else:
        for radius, width, alpha_mul in ((30, 2, 0.42), (48, 1, 0.28), (66, 1, 0.18)):
            ring = pygame.Surface((radius * 2 + 8, radius * 2 + 8), pygame.SRCALPHA)
            pygame.draw.ellipse(ring, (*color, int(255 * alpha_mul * (0.6 + 0.4 * pulse))), ring.get_rect().inflate(-6, -6), width)
            target.blit(ring, ring.get_rect(center=center))
        dot = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.circle(dot, (*color, 215), (9, 9), 4)
        target.blit(dot, dot.get_rect(center=center))
    if glow is not None:
        aura = pygame.transform.smoothscale(glow, (170, 170))
        aura.set_alpha(30 + int(28 * pulse))
        target.blit(aura, aura.get_rect(center=(center[0], center[1] - 10)))


def _draw_resonance_pulse(target: pygame.Surface, glow: pygame.Surface | None,
                          center: tuple[int, int], timer: float) -> None:
    """Organic Causal Resonance wave: rings, arcs and wisps without card-like bounds."""
    if timer <= 0.0:
        return
    progress = clamp(1.0 - timer / RESONANCE_PULSE_TIME, 0.0, 1.0)
    fade = (1.0 - progress) ** 1.25
    layer = pygame.Surface((W, H), pygame.SRCALPHA)
    cx, cy = center
    for lag, radius_scale, alpha in ((0.0, 1.0, 165), (0.11, 0.72, 110), (0.22, 0.48, 70)):
        local = clamp(progress - lag, 0.0, 1.0)
        radius = max(12, int((34.0 + local * 255.0) * radius_scale))
        strength = max(0, min(255, int(alpha * fade * (1.0 - local * 0.28))))
        color = (151, 226, 238, strength)
        pygame.draw.circle(layer, color, (cx, cy), radius, max(1, int(2 + 2 * fade)))
        arc_box = pygame.Rect(cx - radius, cy - int(radius * 0.72), radius * 2, int(radius * 1.44))
        start = progress * math.tau * 1.7 + lag * 5.0
        pygame.draw.arc(layer, (198, 239, 244, min(255, strength + 24)), arc_box, start, start + 1.55, 2)
        pygame.draw.arc(layer, (120, 188, 224, max(0, strength - 24)), arc_box, start + math.pi, start + math.pi + 1.05, 1)
    for i in range(7):
        angle = progress * 2.1 + i * (math.tau / 7.0)
        inner = 26 + progress * 34
        outer = inner + 18 + 10 * math.sin(progress * 4.0 + i)
        x1 = cx + math.cos(angle) * inner
        y1 = cy + math.sin(angle) * inner * 0.72
        x2 = cx + math.cos(angle + 0.16) * outer
        y2 = cy + math.sin(angle + 0.16) * outer * 0.72
        pygame.draw.aaline(layer, (174, 230, 242, int(105 * fade)), (x1, y1), (x2, y2))
    target.blit(layer, (0, 0))


def _veil_ward_strength(timer: float) -> float:
    if timer <= 0.0:
        return 0.0
    elapsed = VEIL_WARD_DURATION - timer
    fade_in = clamp(elapsed / max(0.01, VEIL_WARD_FADE_IN), 0.0, 1.0)
    fade_out = clamp(timer / max(0.01, VEIL_WARD_FADE_OUT), 0.0, 1.0)
    return min(fade_in, fade_out)


def _draw_veil_ward(target: pygame.Surface, center: tuple[int, int], timer: float, t: float) -> None:
    """Soft temporal shell made only from arcs, rings and wisps."""
    strength = _veil_ward_strength(timer)
    if strength <= 0.0:
        return
    layer = pygame.Surface((W, H), pygame.SRCALPHA)
    cx, cy = center
    pulse = 0.5 + 0.5 * math.sin(t * 3.1)
    for idx, (rx, ry, alpha) in enumerate(((48, 70, 90), (62, 86, 62), (78, 104, 38))):
        box = pygame.Rect(cx - rx, cy - ry, rx * 2, ry * 2)
        spin = t * (0.58 + idx * 0.13) + idx * 1.9
        a = int(alpha * strength * (0.82 + 0.18 * pulse))
        pygame.draw.arc(layer, (174, 146, 236, a), box, spin, spin + 2.0, 2)
        pygame.draw.arc(layer, (115, 216, 231, max(1, int(a * 0.78))), box, spin + math.pi, spin + math.pi + 1.4, 1)
    for i in range(8):
        angle = t * 0.42 + i * math.tau / 8.0
        radius = 56 + 10 * math.sin(t * 1.7 + i * 0.8)
        x = cx + math.cos(angle) * radius
        y = cy + math.sin(angle) * radius * 0.72
        pygame.draw.circle(layer, (198, 236, 242, int(105 * strength)), (int(x), int(y)), 2 + (i % 2))
    target.blit(layer, (0, 0))





def _load_player_projection_drone_asset() -> pygame.Surface | None:
    """Load the replaceable player-drone sprite from the shared drone asset folder.

    ``player_drone.png`` is the explicit player authority. ``drone1.png`` is kept
    as a fail-soft compatibility fallback so older asset packs never lose the
    projection entirely. Scaling remains proportional.
    """
    candidates = (PLAYER_DRONE_ASSET, DRONE_ASSET_DIR / "drone1.png")
    for path in candidates:
        if not path.is_file():
            continue
        try:
            surf = pygame.image.load(str(path)).convert_alpha()
            if surf.get_width() <= 0 or surf.get_height() <= 0:
                continue
            return _scale_surface_to_fit(surf, (56, 56), allow_upscale=False, min_side=6)
        except (pygame.error, OSError, ValueError, TypeError, OverflowError):
            continue
    return None


def _load_projection_drone_assets() -> tuple[pygame.Surface, ...]:
    """Load active drones, falling back to legacy debris only for compatibility.

    All scaling is fit-to-box and therefore preserves each source image's aspect ratio.
    """
    paths = tuple(path for path in _png_paths_from_dirs(DRONE_ASSET_DIR) if path.name.lower() != "player_drone.png")
    if not paths:
        paths = _png_paths_from_dirs(LEGACY_DEBRIS_DIR)
    result: list[pygame.Surface] = []
    for path in paths:
        try:
            surf = pygame.image.load(str(path)).convert_alpha()
            if surf.get_width() <= 0 or surf.get_height() <= 0:
                continue
            result.append(_scale_surface_to_fit(surf, (46, 46), allow_upscale=False, min_side=4))
        except (pygame.error, OSError, ValueError, TypeError, OverflowError):
            continue
    return tuple(result)


def _spawn_projection_enemy_drones(world_key: str, projection_x: float,
                                    rng: random.Random,
                                    assets: tuple[pygame.Surface, ...],
                                    lance_level: int = 0) -> list[dict]:
    """Create a small high-altitude patrol group around the projection area."""
    if not assets:
        return []
    low_y, high_y = ENEMY_DRONE_ALTITUDE
    result: list[dict] = []
    count = min(ENEMY_DRONE_MAX, 3 + (1 if world_key == "a" else 0))
    for _ in range(count):
        x = clamp(projection_x + rng.uniform(-760.0, 760.0), 60.0, WORLD_SIZE[0] - 60.0)
        y = rng.uniform(low_y, high_y)
        direction = -1.0 if rng.random() < 0.5 else 1.0
        elite = bool(lance_level >= 2 and rng.random() < min(0.50, 0.16 + 0.10 * lance_level))
        integrity = ENEMY_DRONE_ELITE_INTEGRITY if elite else ENEMY_DRONE_BASE_INTEGRITY
        result.append({
            "x": x, "y": y, "home_x": x, "home_y": y,
            "heading": direction, "state": "patrol",
            "fire_cd": rng.uniform(0.20, ENEMY_DRONE_FIRE_COOLDOWN),
            "asset": rng.randrange(len(assets)),
            "phase": rng.random() * math.tau, "alert": 0.0,
            "integrity": integrity, "max_integrity": integrity, "elite": elite,
        })
    return result


def _enemy_drone_can_see(drone: dict, projection_x: float, projection_y: float) -> bool:
    """High-air sight cone; IO is deliberately outside this authority."""
    if projection_y > ENEMY_DRONE_PROJECTION_MAX_Y:
        return False
    dx = projection_x - float(drone["x"])
    dy = projection_y - float(drone["y"])
    dist_sq = dx * dx + dy * dy
    if dist_sq > ENEMY_DRONE_DETECTION_RADIUS ** 2 or dist_sq <= 1.0:
        return False
    dist = math.sqrt(dist_sq)
    facing_x = 1.0 if float(drone.get("heading", 1.0)) >= 0.0 else -1.0
    return (dx / dist) * facing_x >= ENEMY_DRONE_FOV_COS


def _update_projection_enemy_drones(drones: list[dict], shots: list[dict],
                                     projection_x: float, projection_y: float,
                                     dt: float, t: float) -> None:
    """Bounded patrol -> alert/chase -> fire loop for projection-only enemies."""
    low_y, high_y = ENEMY_DRONE_ALTITUDE
    for drone in drones:
        drone["fire_cd"] = max(0.0, float(drone.get("fire_cd", 0.0)) - dt)
        sees = _enemy_drone_can_see(drone, projection_x, projection_y)
        if sees:
            drone["state"] = "attack"
            drone["alert"] = min(1.0, float(drone.get("alert", 0.0)) + dt * 4.5)
            dx = projection_x - float(drone["x"])
            dy = projection_y - float(drone["y"])
            dist = max(1.0, math.hypot(dx, dy))
            drone["heading"] = 1.0 if dx >= 0.0 else -1.0
            drone["x"] = clamp(float(drone["x"]) + (dx / dist) * ENEMY_DRONE_CHASE_SPEED * dt,
                               40.0, WORLD_SIZE[0] - 40.0)
            # Pursuit never descends out of the high-air band.
            desired_y = clamp(projection_y, low_y, high_y)
            drone["y"] += (desired_y - float(drone["y"])) * min(1.0, dt * 1.7)
            if dist <= ENEMY_DRONE_ATTACK_RADIUS and float(drone["fire_cd"]) <= 0.0:
                shots.append({
                    "x": float(drone["x"]), "y": float(drone["y"]),
                    "vx": (dx / dist) * ENEMY_DRONE_SHOT_SPEED,
                    "vy": (dy / dist) * ENEMY_DRONE_SHOT_SPEED,
                    "life": ENEMY_DRONE_SHOT_LIFE,
                })
                drone["fire_cd"] = ENEMY_DRONE_FIRE_COOLDOWN
        else:
            drone["state"] = "patrol"
            drone["alert"] = max(0.0, float(drone.get("alert", 0.0)) - dt * 2.0)
            direction = 1.0 if float(drone.get("heading", 1.0)) >= 0.0 else -1.0
            drone["x"] += direction * ENEMY_DRONE_PATROL_SPEED * dt
            if abs(float(drone["x"]) - float(drone["home_x"])) > 250.0 or not (42.0 < drone["x"] < WORLD_SIZE[0] - 42.0):
                drone["heading"] = -direction
            bob = math.sin(t * 0.9 + float(drone.get("phase", 0.0))) * 16.0
            drone["y"] += (float(drone["home_y"]) + bob - float(drone["y"])) * min(1.0, dt * 1.3)
            drone["y"] = clamp(float(drone["y"]), low_y, high_y)

    for shot in shots:
        shot["x"] += float(shot["vx"]) * dt
        shot["y"] += float(shot["vy"]) * dt
        shot["life"] = float(shot["life"]) - dt
    shots[:] = [shot for shot in shots if float(shot["life"]) > 0.0 and
                -80.0 <= float(shot["x"]) <= WORLD_SIZE[0] + 80.0 and
                -80.0 <= float(shot["y"]) <= WORLD_SIZE[1] + 80.0]


def _projection_drone_hit(shots: list[dict], projection_x: float, projection_y: float) -> bool:
    """Consume one hostile pulse touching the projection. IO is never tested."""
    radius_sq = ENEMY_DRONE_HIT_RADIUS ** 2
    for idx, shot in enumerate(shots):
        dx = float(shot["x"]) - projection_x
        dy = float(shot["y"]) - projection_y
        if dx * dx + dy * dy <= radius_sq:
            shots.pop(idx)
            return True
    return False


def _draw_projection_enemy_drone(target: pygame.Surface, asset: pygame.Surface,
                                 center: tuple[int, int], heading: float,
                                 alert: float, t: float, integrity: int = 2,
                                 max_integrity: int = 2, elite: bool = False) -> None:
    """Drone silhouette with organic engine rings and no square HUD marker."""
    x, y = center
    glow = pygame.Surface((104, 78), pygame.SRCALPHA)
    pulse = 0.5 + 0.5 * math.sin(t * 4.0)
    color = (232, 92, 104) if alert > 0.05 else (132, 185, 205)
    pygame.draw.ellipse(glow, (*color, int(45 + 55 * alert)), (12, 14, 80, 50), width=2)
    pygame.draw.arc(glow, (*color, int(95 + 80 * alert)), (5, 6, 94, 66), 0.25 + pulse, 2.7 + pulse, 3)
    pygame.draw.circle(glow, (*color, int(90 + 90 * alert)), (52 + int(heading * 30), 39), 4)
    target.blit(glow, (x - 52, y - 39))
    sprite = _drone_facing_surface(asset, heading)
    target.blit(sprite, sprite.get_rect(center=(x, y)))
    # Damage state is communicated through broken arcs around the silhouette, not a box/health bar.
    if max_integrity > 0 and integrity < max_integrity:
        missing = max(1, max_integrity - integrity)
        for i in range(missing):
            radius = 27 + i * 6
            pygame.draw.arc(target, (248, 162, 174, 180), (x-radius, y-radius, radius*2, radius*2),
                            0.65 + i * 0.9, 2.55 + i * 0.9, 2)
    if elite:
        pygame.draw.arc(target, (206, 170, 255, 175), (x-34, y-24, 68, 48), t*1.2, t*1.2+4.4, 2)


def _draw_projection_enemy_shot(target: pygame.Surface, center: tuple[int, int], t: float) -> None:
    """Small curved pulse projectile; intentionally avoids square FX."""
    x, y = center
    pulse = 0.5 + 0.5 * math.sin(t * 11.0)
    pygame.draw.circle(target, (255, 108, 124, 48), (x, y), int(11 + 3 * pulse))
    pygame.draw.circle(target, (255, 164, 176, 210), (x, y), 5, width=2)
    pygame.draw.arc(target, (255, 110, 140, 210), (x - 9, y - 9, 18, 18), t * 4.0, t * 4.0 + 3.8, 2)


def _spawn_projection_lance_shot(shots: list[dict], origin: tuple[float, float],
                                   direction: pygame.Vector2) -> None:
    """Emit one organic high-speed Projection Lance pulse."""
    if len(shots) >= PROJECTION_LANCE_MAX_SHOTS:
        return
    aim = pygame.Vector2(direction)
    if aim.length_squared() <= 0.001:
        aim.update(1.0, 0.0)
    else:
        aim = aim.normalize()
    shots.append({
        "x": float(origin[0]), "y": float(origin[1]),
        "prev_x": float(origin[0]), "prev_y": float(origin[1]),
        "vx": aim.x * PROJECTION_LANCE_SPEED,
        "vy": aim.y * PROJECTION_LANCE_SPEED,
        "life": PROJECTION_LANCE_LIFE,
        "trail": [],
    })


def _segment_point_distance_sq(ax: float, ay: float, bx: float, by: float, px: float, py: float) -> float:
    """Squared distance from a point to a segment for fast projectile hits."""
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom <= 1e-9:
        return (px - ax) ** 2 + (py - ay) ** 2
    u = clamp(((px - ax) * dx + (py - ay) * dy) / denom, 0.0, 1.0)
    cx, cy = ax + dx * u, ay + dy * u
    return (px - cx) ** 2 + (py - cy) ** 2


def _update_projection_lance_shots(shots: list[dict], drones: list[dict], dt: float, damage: int) -> int:
    """Advance Projection Lance pulses and return the number of drones dispersed."""
    dispersed = 0
    hit_radius_sq = PROJECTION_LANCE_HIT_RADIUS ** 2
    alive_shots: list[dict] = []
    for shot in shots:
        shot["prev_x"], shot["prev_y"] = float(shot["x"]), float(shot["y"])
        shot["x"] += float(shot["vx"]) * dt
        shot["y"] += float(shot["vy"]) * dt
        shot["life"] = float(shot["life"]) - dt
        trail = shot.setdefault("trail", [])
        trail.append((float(shot["x"]), float(shot["y"])))
        if len(trail) > PROJECTION_LANCE_TRAIL_MAX:
            del trail[:-PROJECTION_LANCE_TRAIL_MAX]
        consumed = False
        if damage > 0:
            for drone in list(drones):
                if _segment_point_distance_sq(
                    float(shot["prev_x"]), float(shot["prev_y"]),
                    float(shot["x"]), float(shot["y"]),
                    float(drone["x"]), float(drone["y"]),
                ) <= hit_radius_sq:
                    drone["integrity"] = max(0, int(drone.get("integrity", ENEMY_DRONE_BASE_INTEGRITY)) - damage)
                    consumed = True
                    if int(drone["integrity"]) <= 0:
                        drones.remove(drone)
                        dispersed += 1
                    break
        if not consumed and float(shot["life"]) > 0.0 and -80.0 <= float(shot["x"]) <= WORLD_SIZE[0] + 80.0 and -80.0 <= float(shot["y"]) <= WORLD_SIZE[1] + 80.0:
            alive_shots.append(shot)
    shots[:] = alive_shots
    return dispersed


def _draw_projection_lance_shot(target: pygame.Surface, center: tuple[int, int], t: float, mastered: bool) -> None:
    """Organic lance pulse made from rings/arcs instead of rectangular FX."""
    x, y = center
    color = (178, 240, 255) if not mastered else (224, 196, 255)
    pulse = 0.5 + 0.5 * math.sin(t * 16.0)
    pygame.draw.circle(target, (*color, 54), (x, y), int(10 + 3 * pulse))
    pygame.draw.circle(target, (*color, 220), (x, y), 4, width=2)
    pygame.draw.arc(target, (*color, 210), (x - 12, y - 8, 24, 16), t * 5.0, t * 5.0 + 3.9, 2)


def _draw_projection_lance_trail(target: pygame.Surface, points: list[tuple[int, int]], mastered: bool) -> None:
    """Draw a tapered curved-looking dotted trail with no box sprites."""
    if len(points) < 2:
        return
    color = (126, 218, 244) if not mastered else (205, 158, 244)
    total = max(1, len(points) - 1)
    for i, point in enumerate(points):
        strength = (i + 1) / (total + 1)
        pygame.draw.circle(target, (*color, int(25 + 110 * strength)), point, max(1, int(1 + 3 * strength)))


def _projection_resonance_message(
    world_key: str, origin: tuple[float, float],
    lore_placements: tuple[LorePlacement, ...], discovered_lore: set[str],
    shrine_activated: bool, causal_resonance_learned: bool, story_complete: bool,
    entity_pos: tuple[float, float], entity_defeated: bool,
    rooted_crown_pos: tuple[float, float], rooted_crown_defeated: bool,
    rooted_crown_shrine_pos: tuple[float, float], rooted_crown_shrine_activated: bool,
    range_scale: float,
) -> str:
    """Scout from the projection without collecting or activating anything."""
    near = RESONANCE_NEAR_DISTANCE * max(1.0, float(range_scale))
    middle = RESONANCE_MID_DISTANCE * max(1.0, float(range_scale))
    candidates: list[tuple[float, str]] = []
    for placement in lore_placements:
        if placement.record.world != world_key or placement.record.record_id in discovered_lore:
            continue
        if not lore_record_available(placement.record, shrine_activated, causal_resonance_learned, story_complete):
            continue
        candidates.append((pygame.Vector2(origin).distance_to(placement.position), "MEMORY RECORD"))
    if world_key == "b":
        if not entity_defeated:
            candidates.append((pygame.Vector2(origin).distance_to(entity_pos), "ENTITY RECORD"))
        elif not rooted_crown_defeated:
            candidates.append((pygame.Vector2(origin).distance_to(rooted_crown_pos), "ENTITY RECORD"))
    else:
        if entity_defeated and not shrine_activated:
            candidates.append((pygame.Vector2(origin).distance_to(FUTURE_CLUE_POS), "SHRINE RECORD"))
        if rooted_crown_defeated and not rooted_crown_shrine_activated:
            candidates.append((pygame.Vector2(origin).distance_to(rooted_crown_shrine_pos), "SHRINE RECORD"))
    if not candidates:
        return "REMOTE RESONANCE: NO UNREAD RECORD ANSWERS."
    distance, kind = min(candidates, key=lambda item: item[0])
    band = causal_resonance_band(distance, near, middle)
    if band == "near": return f"REMOTE {kind}: NEAR."
    if band == "middle": return f"REMOTE {kind}: ANSWERS THROUGH THE VEIL."
    return f"REMOTE {kind}: FAINT."


def _draw_projection_resonance(target: pygame.Surface, center: tuple[int, int], timer: float, deep: bool) -> None:
    """Organic remote-scan FX around the possessed lantern projection."""
    if timer <= 0.0: return
    progress = clamp(1.0 - timer / max(0.01, REMOTE_RESONANCE_PULSE_TIME), 0.0, 1.0)
    fade = (1.0 - progress) ** 1.15
    layer = pygame.Surface((W, H), pygame.SRCALPHA)
    cx, cy = center
    ring_count = 4 if deep else 3
    for i in range(ring_count):
        local = clamp(progress - i * 0.09, 0.0, 1.0)
        radius = int(22 + local * (300 if deep else 245) + i * 9)
        alpha = int((160 - i * 25) * fade * (1.0 - local * 0.25))
        if alpha <= 0: continue
        color = (190, 174, 248, alpha) if deep else (150, 226, 244, alpha)
        box = pygame.Rect(cx-radius, cy-int(radius*0.72), radius*2, int(radius*1.44))
        start = progress * 5.4 + i * 1.3
        pygame.draw.arc(layer, color, box, start, start + 1.55 + i*0.08, 2)
        pygame.draw.arc(layer, (112, 198, 232, max(0, alpha-35)), box, start+math.pi, start+math.pi+0.92, 1)
    count = 9 if deep else 6
    for i in range(count):
        angle = progress * 3.3 + i * math.tau / count
        r1 = 30 + progress * 70
        r2 = r1 + 16 + (i % 3) * 4
        p1=(cx+math.cos(angle)*r1, cy+math.sin(angle)*r1*0.72)
        p2=(cx+math.cos(angle+0.11)*r2, cy+math.sin(angle+0.11)*r2*0.72)
        pygame.draw.aaline(layer, (184, 232, 246, int(105*fade)), p1, p2)
    target.blit(layer,(0,0))


def _draw_lantern_projection(target: pygame.Surface, center: tuple[int, int], remaining: float, maximum: float,
                             t: float, asset: pygame.Surface | None = None, heading: float = 1.0) -> None:
    """Draw the controllable player drone with restrained projection telemetry.

    The authored ``player_drone.png`` is now the visual authority. The small
    rings/wisps communicate projection state without replacing the drone with
    a procedural orb.
    """
    if remaining <= 0.0 or maximum <= 0.0:
        return
    cx, cy = center
    strength = clamp(remaining / maximum, 0.0, 1.0)
    layer = pygame.Surface((W, H), pygame.SRCALPHA)
    pulse = 0.5 + 0.5 * math.sin(t * 5.4)
    # Quiet telemetry rings: enough to identify player control, never a white blob.
    for idx, radius in enumerate((25, 34)):
        alpha = int((88 - idx * 26) * (0.48 + 0.52 * strength))
        pygame.draw.circle(layer, (126, 222, 238, alpha), (cx, cy), radius, 1)
        box = pygame.Rect(cx-radius-3, cy-int(radius*0.72)-2, (radius+3)*2, int((radius*0.72+2)*2))
        spin = t * (1.45 + idx * 0.28) + idx * 1.7
        pygame.draw.arc(layer, (190, 168, 234, min(150, alpha+24)), box, spin, spin + 1.18, 1)
    if asset is not None:
        drone_surface = _drone_facing_surface(asset, heading)
        drone_rect = drone_surface.get_rect(center=(cx, cy))
        layer.blit(drone_surface, drone_rect)
        # Tiny cyan locator points keep the player readable among hostile machines.
        locator_alpha = int(120 + 80 * pulse)
        pygame.draw.circle(layer, (154, 235, 244, locator_alpha), (cx - 2, cy), 2)
        pygame.draw.circle(layer, (205, 178, 241, max(60, locator_alpha - 50)), (cx + 5, cy + 1), 1)
    else:
        # Emergency fallback only if both player_drone.png and drone1.png fail.
        core_r = 4 + int(2 * pulse)
        pygame.draw.circle(layer, (199, 239, 242, 185), (cx, cy), core_r)
    # A short irregular wake makes movement direction readable.
    trail_sign = -1.0 if heading >= 0.0 else 1.0
    for i in range(3):
        x = cx + trail_sign * (22 + i * 8)
        y = cy + int(math.sin(t * 2.0 + i) * (3 + i))
        pygame.draw.circle(layer, (134, 214, 232, int((66 - i * 14) * strength)), (int(x), int(y)), max(1, 2 - i // 2))
    target.blit(layer, (0, 0))

def _draw_battle_track(target: pygame.Surface, font, label: str, value: int, maximum: int, pos: tuple[int, int],
                       align_right: bool = False) -> None:
    """Compact gothic resolve track made from diamonds rather than placeholder bars."""
    x, y = pos
    text = _ui_render(font, label, True, (201, 193, 184))
    text_rect = text.get_rect(topright=(x, y)) if align_right else text.get_rect(topleft=(x, y))
    target.blit(text, text_rect)
    step = -20 if align_right else 20
    start_x = x - text_rect.width - 18 if align_right else x + text_rect.width + 18
    for i in range(maximum):
        cx = start_x + step * i
        cy = y + 10
        pts = [(cx, cy - 5), (cx + 5, cy), (cx, cy + 5), (cx - 5, cy)]
        fill = (183, 160, 121) if i < value else (47, 43, 48)
        pygame.draw.polygon(target, fill, pts)
        pygame.draw.polygon(target, (105, 91, 82), pts, 1)


_FOG_FRAME_CACHE: dict[tuple[int, int, int, int], pygame.Surface] = {}


def _blit_repeating_fog(
    target: pygame.Surface,
    image: pygame.Surface,
    y: int,
    t: float,
    speed: float,
    alpha: int,
    scale: float = 1.0,
    phase: float = 0.0,
) -> None:
    width = max(1, int(round(image.get_width() * scale)))
    height = max(1, int(round(image.get_height() * scale)))
    alpha_i = max(0, min(255, int(alpha)))
    key = (id(image), width, height, alpha_i)
    fog = _FOG_FRAME_CACHE.get(key)
    if fog is None:
        fog = pygame.transform.smoothscale(image, (width, height)) if image.get_size() != (width, height) else image.copy()
        fog.set_alpha(alpha_i)
        if len(_FOG_FRAME_CACHE) >= 32:
            _FOG_FRAME_CACHE.clear()
        _FOG_FRAME_CACHE[key] = fog
    offset = int((t * speed + phase) % width) - width
    for x in range(offset, W + width, width):
        target.blit(fog, (x, y))


def draw_persistent_atmosphere(
    target: pygame.Surface,
    assets: dict[str, pygame.Surface],
    world_key: str,
    t: float,
    stage: str,
    density_scale: float = 1.0,
) -> None:
    """Draw persistent fog at stable screen-space depths.

    The layers drift slowly enough to feel atmospheric without breaking the
    user's authored 3930x1130 world alignment.
    """
    density = FOG_DENSITY.get(world_key, 0.75) * density_scale
    if stage == "behind_actor":
        if "far" in assets:
            _blit_repeating_fog(target, assets["far"], 235, t, 4.0, int(72 * density), 1.55, 120.0)
        if "mid" in assets:
            _blit_repeating_fog(target, assets["mid"], 350, t, -6.0, int(82 * density), 1.65, 470.0)
        if "wisp" in assets:
            _blit_repeating_fog(target, assets["wisp"], 145, t, 8.5, int(52 * density), 1.45, 750.0)
    elif stage == "front":
        if "near" in assets:
            _blit_repeating_fog(target, assets["near"], 475, t, 7.0, int(72 * density), 1.75, 210.0)
        if "wisp" in assets:
            _blit_repeating_fog(target, assets["wisp"], 555, t, -10.0, int(44 * density), 1.55, 980.0)


_DARK_OVERLAY_CACHE: dict[int, pygame.Surface] = {}
_VIGNETTE_ALPHA_CACHE: dict[tuple[int, int], pygame.Surface] = {}
_PRESENT_CLOUD_SHADOW_CACHE: dict[int, pygame.Surface] = {}


def _present_cloud_shadow_surface(alpha: int) -> pygame.Surface:
    alpha = int(clamp(alpha, 0, 255))
    shadow = _PRESENT_CLOUD_SHADOW_CACHE.get(alpha)
    if shadow is None:
        shadow = pygame.Surface((W, H), pygame.SRCALPHA)
        base_alpha = int(alpha * 0.34)
        shadow.fill((8, 10, 14, base_alpha))
        cloud_specs = (
            (-0.18, -0.14, 0.58, 0.34, 0.56),
            (0.18, -0.11, 0.62, 0.30, 0.52),
            (0.48, -0.16, 0.54, 0.32, 0.48),
        )
        for fx, fy, fw, fh, weight in cloud_specs:
            rect = pygame.Rect(int(W * fx), int(H * fy), int(W * fw), int(H * fh))
            pygame.draw.ellipse(shadow, (5, 7, 10, int(alpha * weight)), rect)
        if len(_PRESENT_CLOUD_SHADOW_CACHE) >= 40:
            _PRESENT_CLOUD_SHADOW_CACHE.clear()
        _PRESENT_CLOUD_SHADOW_CACHE[alpha] = shadow
    return shadow


def draw_atmosphere_finish(
    target: pygame.Surface,
    assets: dict[str, pygame.Surface],
    world_key: str,
    vignette_scale: float = 1.0,
    darkness_scale: float = 1.0,
    present_cloud_shadow_alpha: float = 0.0,
) -> None:
    # These full-screen overlays are static for a given settings value; reuse them.
    dark_alpha = int(clamp(ATMOSPHERE_DARKEN.get(world_key, 18) * darkness_scale, 0, 255))
    dark = _DARK_OVERLAY_CACHE.get(dark_alpha)
    if dark is None:
        dark = pygame.Surface((W, H), pygame.SRCALPHA)
        dark.fill((0, 0, 0, dark_alpha))
        _DARK_OVERLAY_CACHE[dark_alpha] = dark
    target.blit(dark, (0, 0))
    if world_key == "a" and present_cloud_shadow_alpha > 0.0:
        target.blit(_present_cloud_shadow_surface(int(round(present_cloud_shadow_alpha))), (0, 0))
    vignette = assets.get("vignette")
    if vignette is not None:
        vg_alpha = int(clamp(VIGNETTE_ALPHA.get(world_key, 225) * vignette_scale, 0, 255))
        key = (id(vignette), vg_alpha)
        vg = _VIGNETTE_ALPHA_CACHE.get(key)
        if vg is None:
            vg = vignette.copy()
            vg.set_alpha(vg_alpha)
            if len(_VIGNETTE_ALPHA_CACHE) >= 16:
                _VIGNETTE_ALPHA_CACHE.clear()
            _VIGNETTE_ALPHA_CACHE[key] = vg
        target.blit(vg, (0, 0))




def _nearest_level(value: float, levels: tuple[float, ...]) -> float:
    return min(levels, key=lambda candidate: abs(float(value) - candidate))


def _step_level(value: float, levels: tuple[float, ...], direction: float) -> float:
    current = _nearest_level(value, levels)
    index = levels.index(current)
    return levels[(index + (1 if direction >= 0 else -1)) % len(levels)]


def _normalize_guidance_mode(value: object) -> str:
    mode = str(value or "context").strip().lower()
    return mode if mode in {"full", "context", "off"} else "context"


def _step_guidance_mode(value: object, direction: float) -> str:
    levels = ("off", "context", "full")
    current = _normalize_guidance_mode(value)
    index = levels.index(current)
    return levels[(index + (1 if direction >= 0 else -1)) % len(levels)]


def continuity_thread(world_key: str, defeated_boss_ids: set[str] | list[str] | tuple[str, ...]) -> tuple[str, str]:
    """Return a short, spoiler-light objective and a useful action.

    This is intentionally derived from durable campaign state rather than a
    separate quest variable so F1/load reminders cannot drift out of sync with
    saves or nonlinear Guardian order.
    """
    defeated = {str(value) for value in defeated_boss_ids}
    recovered = sum(1 for guardian_id in MEMORY_GUARDIAN_ORDER if guardian_id in defeated)
    total = len(MEMORY_GUARDIAN_ORDER)
    if recovered >= total:
        return (
            "COMPLETE CIVILIZATION INDEX RECOVERED",
            "Return to the central Gleebs anchor and press E.",
        )
    if str(world_key).lower() == "b":
        return (
            f"BEGINNING // RECOVER MEMORY ARCHIVES {recovered}/{total}",
            "Search for a stationary Memory Guardian and press E to speak.",
        )
    if recovered:
        return (
            f"PRESENT // {recovered}/{total} MEMORY ARCHIVES RECOVERED",
            "Inspect their future consequences, or return to Gleebs for context.",
        )
    return (
        "PRESENT // FIND THE CENTRAL GLEEBS ANCHOR",
        "The Present extends into detached regions. Walk beyond a location edge to continue the search.",
    )


def continuity_thread_line(world_key: str, defeated_boss_ids: set[str] | list[str] | tuple[str, ...]) -> str:
    title, action = continuity_thread(world_key, defeated_boss_ids)
    return f"THREAD: {title} // {action}"


def _apply_presentation_preferences(settings: dict) -> None:
    """Apply presentation-only accessibility preferences without touching gameplay authority."""
    global _UI_TEXT_STYLE, _PRESENTATION_MOTION_SCALE, _PRESENTATION_FLASH_SCALE
    _UI_TEXT_STYLE = "clear" if str(settings.get("text_style", "worn")).lower() == "clear" else "worn"
    _PRESENTATION_MOTION_SCALE = _nearest_level(float(settings.get("motion_fx", 1.0)), (0.35, 0.65, 1.0))
    _PRESENTATION_FLASH_SCALE = _nearest_level(float(settings.get("flash_fx", 1.0)), (0.0, 0.5, 1.0))
    _UI_TEXT_CACHE.clear()
    cache = globals().get("_WEATHER_FLOW_FRAME_CACHE")
    if isinstance(cache, dict):
        cache.clear()
    cache = globals().get("_ENTITY_PRESENCE_FRAME_CACHE")
    if isinstance(cache, dict):
        cache.clear()


def _ui_render(font: pygame.font.Font, text: str, antialias: bool, color) -> pygame.Surface:
    """Render readable text with a restrained deterministic worn edge by default.

    CLEAR mode returns the untouched glyph surface. WORN mode removes only a
    handful of tiny interior pixels, producing a weathered print texture without
    compromising letter recognition. Cached output keeps the effect cheap.
    """
    rgb = tuple(int(c) for c in color[:3])
    key = (id(font), str(text), rgb, _UI_TEXT_STYLE)
    cached = _UI_TEXT_CACHE.get(key)
    if cached is not None:
        return cached.copy()
    image = font.render(str(text), bool(antialias), rgb)
    if _UI_TEXT_STYLE == "worn" and image.get_width() >= 18 and image.get_height() >= 12:
        image = image.convert_alpha()
        # Stable integer seed: Python's hash is process-randomized, so derive one
        # from characters and dimensions instead.
        seed = image.get_width() * 131 + image.get_height() * 17
        for index, ch in enumerate(str(text)):
            seed = (seed * 33 + ord(ch) + index * 7) & 0xFFFFFFFF
        count = max(1, min(8, image.get_width() // 48))
        state = seed or 1
        for _ in range(count):
            # Small LCG, then retry until we land on an actual glyph pixel.
            for _attempt in range(14):
                state = (1664525 * state + 1013904223) & 0xFFFFFFFF
                x = 1 + state % max(1, image.get_width() - 2)
                state = (1664525 * state + 1013904223) & 0xFFFFFFFF
                y = 1 + state % max(1, image.get_height() - 2)
                if image.get_at((int(x), int(y))).a > 96:
                    pygame.draw.rect(image, (0, 0, 0, 0), (int(x), int(y), 1 + (state & 1), 1))
                    break
    if len(_UI_TEXT_CACHE) >= 512:
        _UI_TEXT_CACHE.clear()
    _UI_TEXT_CACHE[key] = image.copy()
    return image


def _draw_hud_skin(target: pygame.Surface, name: str, rect: pygame.Rect, fallback=None) -> bool:
    """Draw an optional replaceable HUD PNG, preserving procedural/menu fallbacks."""
    skin = _scaled_menu_asset(_HUD_ASSETS.get(name), rect.size)
    if skin is not None:
        target.blit(skin, rect)
        return True
    if callable(fallback):
        fallback()
    return False


def _gothic_text(surface: pygame.Surface, font: pygame.font.Font, text: str, pos, color=(224, 220, 211), center=False):
    shadow = _ui_render(font, text, True, (5, 5, 7))
    image = _ui_render(font, text, True, color)
    rect = image.get_rect(center=pos) if center else image.get_rect(topleft=pos)
    surface.blit(shadow, rect.move(2, 2))
    surface.blit(image, rect)
    return rect


def _gothic_text_fit(surface: pygame.Surface, font: pygame.font.Font, text: str, pos, max_width: int,
                     color=(224, 220, 211), center=False):
    """Draw text at its authored size, shrinking only when a custom font would overflow."""
    shadow = _ui_render(font, text, True, (5, 5, 7))
    image = _ui_render(font, text, True, color)
    if max_width > 0 and image.get_width() > max_width:
        scale = max_width / max(1, image.get_width())
        fitted = (max(1, int(round(image.get_width() * scale))), max(1, int(round(image.get_height() * scale))))
        image = pygame.transform.smoothscale(image, fitted)
        shadow = pygame.transform.smoothscale(shadow, fitted)
    rect = image.get_rect(center=pos) if center else image.get_rect(topleft=pos)
    surface.blit(shadow, rect.move(2, 2))
    surface.blit(image, rect)
    return rect


def _draw_gothic_frame(surface: pygame.Surface, rect: pygame.Rect) -> None:
    veil = pygame.Surface(rect.size, pygame.SRCALPHA)
    veil.fill((8, 8, 11, 232))
    surface.blit(veil, rect)
    pygame.draw.rect(surface, (38, 34, 39), rect, 2)
    inner = rect.inflate(-10, -10)
    pygame.draw.rect(surface, (105, 92, 82), inner, 1)
    # restrained corner ornaments: readable gothic framing without covering gameplay
    d = 18
    for x, y, sx, sy in ((inner.left, inner.top, 1, 1), (inner.right, inner.top, -1, 1),
                          (inner.left, inner.bottom, 1, -1), (inner.right, inner.bottom, -1, -1)):
        pygame.draw.line(surface, (132, 116, 101), (x, y), (x + sx*d, y), 1)
        pygame.draw.line(surface, (132, 116, 101), (x, y), (x, y + sy*d), 1)


def _load_menu_image(name: str, *, exact_size: tuple[int, int] | None = None,
                     max_size: tuple[int, int] | None = None) -> pygame.Surface | None:
    """Load a replaceable title-screen image; invalid art falls back procedurally."""
    try:
        image = pygame.image.load(str(MENU_ASSET_DIR / name)).convert_alpha()
        if exact_size is not None and image.get_size() != exact_size:
            image = pygame.transform.smoothscale(image, exact_size)
        elif max_size is not None:
            scale = min(max_size[0] / max(1, image.get_width()), max_size[1] / max(1, image.get_height()), 1.0)
            if scale < 1.0:
                image = pygame.transform.smoothscale(
                    image,
                    (max(1, int(round(image.get_width() * scale))), max(1, int(round(image.get_height() * scale)))),
                )
        return image
    except Exception:
        return None


_MENU_SCALE_CACHE: dict[tuple[int, int, int], pygame.Surface] = {}


def _scaled_menu_asset(image: pygame.Surface | None, size: tuple[int, int]) -> pygame.Surface | None:
    """Scale a shared menu skin once per target size, then reuse the cached surface."""
    if image is None:
        return None
    key = (id(image), int(size[0]), int(size[1]))
    cached = _MENU_SCALE_CACHE.get(key)
    if cached is None:
        cached = image if image.get_size() == size else pygame.transform.smoothscale(image, size)
        _MENU_SCALE_CACHE[key] = cached
    return cached


def _draw_menu_panel_skin(target: pygame.Surface, assets: dict[str, pygame.Surface], rect: pygame.Rect) -> None:
    skin = _scaled_menu_asset(assets.get("panel"), rect.size)
    if skin is not None:
        target.blit(skin, rect)
    else:
        _draw_gothic_frame(target, rect)


def _draw_menu_item_skin(target: pygame.Surface, assets: dict[str, pygame.Surface], rect: pygame.Rect, selected: bool) -> None:
    key = "item_selected" if selected else "item"
    skin = _scaled_menu_asset(assets.get(key), rect.size)
    if skin is not None:
        target.blit(skin, rect)
    elif selected:
        highlight = pygame.Surface(rect.size, pygame.SRCALPHA)
        highlight.fill((67, 55, 55, 148))
        target.blit(highlight, rect)
        pygame.draw.rect(target, (151, 126, 106), rect, 1)


def _draw_menu_control_skin(target: pygame.Surface, assets: dict[str, pygame.Surface], rect: pygame.Rect) -> None:
    skin = _scaled_menu_asset(assets.get("control"), rect.size)
    if skin is not None:
        target.blit(skin, rect)
    else:
        pygame.draw.rect(target, (43, 38, 41), rect)
        pygame.draw.rect(target, (122, 103, 90), rect, 1)


def _load_replaceable_alpha_asset(path: Path) -> pygame.Surface | None:
    """Load one presentation-only replacement PNG without making gameplay depend on it."""
    try:
        if not path.is_file():
            return None
        image = pygame.image.load(str(path)).convert_alpha()
        if image.get_width() <= 0 or image.get_height() <= 0:
            return None
        return image
    except (pygame.error, OSError, ValueError, TypeError):
        return None


def load_hud_assets() -> dict[str, pygame.Surface]:
    """Load optional user HUD skins. Missing files intentionally preserve the existing UI."""
    names = {
        "machine_hotbar_panel": "machine_hotbar_panel.png",
        "machine_slot": "machine_slot.png",
        "machine_slot_selected": "machine_slot_selected.png",
        "machine_workshop_panel": "machine_workshop_panel.png",
        "machine_workshop_row": "machine_workshop_row.png",
        "machine_workshop_row_selected": "machine_workshop_row_selected.png",
        "help_panel": "help_panel.png",
        "guidance_panel": "guidance_panel.png",
        "console_panel": "console_panel.png",
        "battle_tray": "battle_tray.png",
    }
    result: dict[str, pygame.Surface] = {}
    for key, filename in names.items():
        image = _load_replaceable_alpha_asset(HUD_ASSET_DIR / filename)
        if image is not None:
            result[key] = image
    return result


def load_story_assets() -> dict[str, pygame.Surface]:
    """Load user-replaceable story/reconstruction placeholders from assets/current/story."""
    names = {
        "reconstruction_left": "reconstruction_left.png",
        "reconstruction_right": "reconstruction_right.png",
    }
    result: dict[str, pygame.Surface] = {}
    for key, name in names.items():
        image = _load_replaceable_alpha_asset(STORY_ASSET_DIR / name)
        if image is not None:
            result[key] = image
    return result


def load_world_fx_assets() -> dict[str, pygame.Surface]:
    """Load replaceable world markers that used to exist only as procedural placeholders."""
    names = {
        "absence_echo": "absence_echo.png",
        "anchor_future": "temporal_anchor_future.png",
        "anchor_past": "temporal_anchor_past.png",
    }
    result: dict[str, pygame.Surface] = {}
    for key, name in names.items():
        image = _load_replaceable_alpha_asset(WORLD_FX_ASSET_DIR / name)
        if image is not None:
            result[key] = image
    return result


def load_start_menu_assets() -> dict[str, pygame.Surface]:
    """Load all user-replaceable menu artwork through a fail-soft contract."""
    assets = {
        "background": _load_menu_image("background.png", exact_size=(W, H)),
        "frame": _load_menu_image("frame.png", exact_size=(W, H)),
        "logo": _load_menu_image("logo.png", max_size=(850, 190)),
        "selector": _load_menu_image("selector.png", max_size=(46, 46)),
        "panel": _load_menu_image("panel.png"),
        "item": _load_menu_image("item.png"),
        "item_selected": _load_menu_image("item_selected.png"),
        "control": _load_menu_image("control.png"),
        "dialogue_panel": _load_menu_image("dialogue_panel.png"),
        "dialogue_selector": _load_menu_image("dialogue_selector.png", max_size=(36, 36)),
    }
    return {name: image for name, image in assets.items() if image is not None}


def _load_menu_font(filename: str, size: int, *, sys_name: str | None = None, bold: bool = False, italic: bool = False) -> pygame.font.Font:
    """Load a replaceable UI font from assets/current/menu/fonts, falling back safely."""
    path = MENU_FONT_DIR / filename
    try:
        if path.is_file():
            return pygame.font.Font(str(path), size)
    except Exception:
        pass
    try:
        if sys_name:
            return pygame.font.SysFont(sys_name, size, bold=bold, italic=italic)
    except Exception:
        pass
    return pygame.font.Font(None, size)


def load_gleebs_option_font(clear_text: bool = False) -> pygame.font.Font:
    """A slightly smaller dedicated font for Gleebs' seven-item topic list."""
    if clear_text:
        return _load_menu_font("body_font.ttf", 24, sys_name="Liberation Sans", bold=True)
    return _load_menu_font("menu_font.ttf", 24, sys_name="Liberation Sans", bold=True)


def load_menu_fonts(clear_text: bool = False) -> tuple[pygame.font.Font, pygame.font.Font, pygame.font.Font, pygame.font.Font]:
    """Return the authored font set or a deterministic clear-text alternative."""
    if clear_text:
        # Use the body font at every hierarchy size so CLEAR stays user-replaceable
        # and deterministic rather than depending on whatever fonts Windows has.
        body = _load_menu_font("body_font.ttf", 22, sys_name="Liberation Sans")
        small = _load_menu_font("body_font.ttf", 18, sys_name="Liberation Sans")
        menu = _load_menu_font("body_font.ttf", 28, sys_name="Liberation Sans", bold=True)
        title = _load_menu_font("body_font.ttf", 40, sys_name="Liberation Sans", bold=True)
        return body, small, menu, title
    body = _load_menu_font("body_font.ttf", 22, sys_name="Liberation Sans")
    small = _load_menu_font("small_font.ttf", 18, sys_name="Liberation Sans")
    menu = _load_menu_font("menu_font.ttf", 28, sys_name="Liberation Sans", bold=True)
    title = _load_menu_font("title_font.ttf", 40, sys_name="Liberation Serif", bold=True)
    return body, small, menu, title


def _draw_dialogue_panel_skin(target: pygame.Surface, assets: dict[str, pygame.Surface], rect: pygame.Rect) -> None:
    skin = _scaled_menu_asset(assets.get("dialogue_panel") or assets.get("panel"), rect.size)
    if skin is not None:
        target.blit(skin, rect)
    else:
        _draw_gothic_frame(target, rect)


def _draw_selection_ornament(target: pygame.Surface, assets: dict[str, pygame.Surface], rect: pygame.Rect, *, color=(151, 211, 221)) -> None:
    selector = assets.get("dialogue_selector") or assets.get("selector")
    if selector is not None:
        ornament = _scaled_menu_asset(selector, (min(rect.width, 28), min(rect.height, 28)))
        if ornament is not None:
            orect = ornament.get_rect(center=rect.center)
            target.blit(ornament, orect)
            return
    pygame.draw.line(target, color, (rect.left + 1, rect.centery), (rect.right - 4, rect.centery), 2)
    pygame.draw.circle(target, color, (rect.centerx - 3, rect.centery), 5, 1)


def draw_start_menu_backdrop(target: pygame.Surface, assets: dict[str, pygame.Surface],
                             title_font, t: float) -> None:
    """Draw asset-backed title art with a complete fallback if files are replaced badly."""
    background = assets.get("background")
    if background is not None:
        target.blit(background, (0, 0))
    else:
        target.fill((8, 9, 12))
        for y in range(0, H, 24):
            shade = 19 - int(13 * y / H)
            pygame.draw.rect(target, (shade, shade, shade + 3), (0, y, W, 24))
        pulse = 9 + int(3 * math.sin(t * 0.45))
        pygame.draw.circle(target, (pulse + 5, pulse + 3, pulse), (245, H // 2), 270, 2)
        pygame.draw.circle(target, (pulse + 2, pulse + 1, pulse), (245, H // 2), 190, 1)

    veil = pygame.Surface((W, H), pygame.SRCALPHA)
    veil.fill((2, 3, 5, 72))
    pygame.draw.rect(veil, (0, 0, 0, 126), (W // 2, 0, W // 2, H))
    target.blit(veil, (0, 0))

    logo = assets.get("logo")
    if logo is not None:
        target.blit(logo, logo.get_rect(center=(W // 2, 118)))
    else:
        _gothic_text(target, title_font, "AFTERLIFE OF IO", (W // 2, 110), (229, 221, 205), True)
    frame = assets.get("frame")
    if frame is not None:
        target.blit(frame, (0, 0))
    else:
        pygame.draw.rect(target, (91, 78, 69), (24, 24, W - 48, H - 48), 1)
        pygame.draw.rect(target, (38, 35, 38), (31, 31, W - 62, H - 62), 1)


def draw_start_menu(target: pygame.Surface, assets: dict[str, pygame.Surface], title_font,
                    menu_font, small_font, selected: int, continue_slot: int | None,
                    modes_unlocked: int, status: str, t: float) -> list[pygame.Rect]:
    """Draw the normal-launch title menu while keeping gameplay state untouched."""
    draw_start_menu_backdrop(target, assets, title_font, t)
    panel = pygame.Rect(W // 2 - 235, 166, 470, 480)
    _draw_menu_panel_skin(target, assets, panel)
    _gothic_text(target, small_font, "BETWEEN THE BEGINNING AND THE PRESENT", (W // 2, panel.top + 35), (143, 132, 122), True)
    _gothic_text(target, small_font, "MISSION: ESCAPE YOUR OWN ENTROPY", (W // 2, panel.top + 52), (165, 145, 130), True)

    items = ["CONTINUE", "NEW GAME", "LOAD GAME", f"MODES  {modes_unlocked}/{len(mode_host.MODES)}", "SETTINGS",
             holoverse_link.quit_label("QUIT")]
    rects: list[pygame.Rect] = []
    y = panel.top + 76
    selector = assets.get("selector")
    for i, item in enumerate(items):
        rect = pygame.Rect(panel.left + 52, y, 366, 50)
        rects.append(rect)
        enabled = _start_menu_item_enabled(i, continue_slot is not None)
        _draw_menu_item_skin(target, assets, rect, i == selected)
        if i == selected and enabled:
            if selector is not None:
                target.blit(selector, selector.get_rect(midright=(rect.left - 8, rect.centery)))
        color = (101, 98, 96) if not enabled else (244, 232, 213) if i == selected else (180, 173, 163)
        _gothic_text(target, menu_font, item, rect.center, color, True)
        y += 54

    if continue_slot is not None:
        primary, secondary = _save_slot_summary(continue_slot)
        footer = f"CONTINUE: SLOT {continue_slot}  •  {primary}  •  {secondary}"
    elif modes_unlocked:
        footer = f"{modes_unlocked} MODE{'S' if modes_unlocked != 1 else ''} UNLOCKED"
    else:
        footer = "DEFEAT MEMORY GUARDIANS TO UNLOCK MODES"
    _gothic_text(target, small_font, status or footer, (W // 2, panel.bottom - 23), (154, 142, 130), True)
    _gothic_text(target, small_font, "ARROWS / WASD   •   ENTER / CLICK",
                 (W // 2, H - 48), (122, 118, 116), True)
    return rects


def draw_modes_menu(target: pygame.Surface, assets: dict[str, pygame.Surface], title_font, menu_font, small_font,
                    selected: int, progress: "mode_host.Progress", unlocked: list[str], status: str) -> list[pygame.Rect]:
    """MODES hub: every hosted mode with its unlock state and requirement."""
    dim = pygame.Surface((W, H), pygame.SRCALPHA); dim.fill((0, 0, 0, 196)); target.blit(dim, (0, 0))
    panel = pygame.Rect(W // 2 - 320, H // 2 - 262, 640, 524)
    _draw_menu_panel_skin(target, assets, panel)
    _gothic_text(target, title_font, "MODES", (W // 2, panel.top + 48), (224, 217, 202), True)
    _gothic_text(target, small_font, f"MEMORY GUARDIANS DEFEATED  {progress.guardians}/{len(MEMORY_GUARDIAN_ORDER)}",
                 (W // 2, panel.top + 84), (139, 127, 118), True)
    rects: list[pygame.Rect] = []
    y = panel.top + 118
    for i, spec in enumerate(mode_host.MODES):
        r = pygame.Rect(panel.left + 44, y, 552, 98)
        rects.append(r)
        is_open = spec.mode_id in unlocked
        _draw_menu_item_skin(target, assets, r, i == selected)
        title_color = ((242, 232, 216) if i == selected else (190, 182, 170)) if is_open else (110, 105, 101)
        _gothic_text(target, menu_font, spec.title, (r.left + 18, r.top + 12), title_color)
        state = "UNLOCKED  •  ENTER TO PLAY" if is_open else "LOCKED  •  " + mode_host.progress_text(spec, progress)
        _gothic_text_fit(target, small_font, state, (r.left + 18, r.top + 46), r.width - 36,
                         (150, 190, 170) if is_open else (150, 120, 108))
        _gothic_text_fit(target, small_font, spec.tagline, (r.left + 18, r.top + 70), r.width - 36, (124, 118, 114))
        y += 106
    back = pygame.Rect(panel.left + 44, panel.bottom - 70, 552, 42)
    rects.append(back)
    _draw_menu_item_skin(target, assets, back, selected == len(mode_host.MODES))
    _gothic_text(target, menu_font, "BACK", back.center,
                 (242, 232, 216) if selected == len(mode_host.MODES) else (177, 171, 163), True)
    _gothic_text(target, small_font, status or "QUITTING A MODE RETURNS HERE", (W // 2, panel.bottom - 12), (160, 145, 130), True)
    return rects


def draw_pause_menu(target: pygame.Surface, assets: dict[str, pygame.Surface], title_font, menu_font, small_font, selected: int, status: str) -> list[pygame.Rect]:
    dim = pygame.Surface((W, H), pygame.SRCALPHA); dim.fill((0, 0, 0, 125)); target.blit(dim, (0, 0))
    panel = pygame.Rect(W//2 - 235, H//2 - 260, 470, 520)
    _draw_menu_panel_skin(target, assets, panel)
    _gothic_text(target, title_font, 'AFTERLIFE OF IO', (W//2, panel.top + 54), (224, 217, 202), True)
    _gothic_text(target, small_font, 'PAUSED', (W//2, panel.top + 96), (139, 127, 118), True)
    _gothic_text(target, small_font, 'MISSION: ESCAPE YOUR OWN ENTROPY', (W//2, panel.top + 119), (162, 143, 130), True)
    items = ['RESUME', 'SAVE GAME', 'LOAD GAME', 'SETTINGS', holoverse_link.quit_label('QUIT TO DESKTOP')]
    rects=[]
    y=panel.top+164
    for i,item in enumerate(items):
        r=pygame.Rect(panel.left+55,y,360,52); rects.append(r)
        _draw_menu_item_skin(target, assets, r, i == selected)
        if i == selected:
            color=(242,232,216)
        else: color=(177,171,163)
        _gothic_text(target, menu_font, item, r.center, color, True)
        y += 61
    if status:
        _gothic_text(target, small_font, status, (W//2, panel.bottom-33), (160,145,130), True)
    return rects


SETTINGS_FULLSCREEN_INDEX = 9
SETTINGS_CONTROLS_INDEX = 10
SETTINGS_BACK_INDEX = 11
SETTINGS_ROW_COUNT = 12


def draw_settings_menu(target: pygame.Surface, assets: dict[str, pygame.Surface], title_font, menu_font, small_font, selected: int,
                       settings: dict, fullscreen: bool) -> list[tuple[pygame.Rect, pygame.Rect | None, pygame.Rect | None]]:
    dim = pygame.Surface((W, H), pygame.SRCALPHA); dim.fill((0,0,0,132)); target.blit(dim,(0,0))
    panel=pygame.Rect(W//2-300,18,600,H-36); _draw_menu_panel_skin(target,assets,panel)
    _gothic_text(target,title_font,'SETTINGS',(W//2,panel.top+39),(224,217,202),True)
    motion_label = {1.0: 'FULL', 0.65: 'BALANCED', 0.35: 'REDUCED'}[_nearest_level(float(settings.get('motion_fx', 1.0)), (0.35, 0.65, 1.0))]
    flash_label = {1.0: 'FULL', 0.5: 'REDUCED', 0.0: 'OFF'}[_nearest_level(float(settings.get('flash_fx', 1.0)), (0.0, 0.5, 1.0))]
    guidance_label = {'full': 'FULL', 'context': 'CONTEXT', 'off': 'OFF'}[_normalize_guidance_mode(settings.get('guidance_mode', 'context'))]
    labels=[
        ('MUSIC', f"{int(settings['music_volume']*100):d}%"),
        ('SFX', f"{int(settings['sfx_volume']*100):d}%"),
        ('FOG', f"{int(settings['fog_level']*100):d}%"),
        ('VIGNETTE', f"{int(settings['vignette_level']*100):d}%"),
        ('DARKNESS', f"{int(settings['darkness_level']*100):d}%"),
        ('TEXT STYLE', 'CLEAR' if str(settings.get('text_style','worn')).lower() == 'clear' else 'WORN'),
        ('MOTION FX', motion_label),
        ('FLASH FX', flash_label),
        ('GUIDANCE', guidance_label),
        ('FULLSCREEN', 'ON' if fullscreen else 'OFF'),
        ('CONTROLS', 'VIEW'),
        ('BACK', ''),
    ]
    controls=[]; y=panel.top+76
    for i,(label,value) in enumerate(labels):
        r=pygame.Rect(panel.left+42,y,516,40)
        _draw_menu_item_skin(target, assets, r, i == selected)
        color=(242,232,216) if i==selected else (177,171,163)
        _gothic_text(target,menu_font,label,(r.left+14,r.top+8),color)
        minus = plus = None
        if i < 9:
            minus = pygame.Rect(r.right - 180, r.top + 4, 32, 32)
            plus = pygame.Rect(r.right - 42, r.top + 4, 32, 32)
            _draw_menu_control_skin(target, assets, minus)
            _draw_menu_control_skin(target, assets, plus)
            _gothic_text(target, menu_font, '−', minus.center, color, True)
            _gothic_text(target, menu_font, '+', plus.center, color, True)
            image=_ui_render(menu_font, value,True,color)
            shadow=_ui_render(menu_font, value,True,(5,5,7))
            sr=image.get_rect(center=(r.right-94,r.centery))
            target.blit(shadow,sr.move(2,2)); target.blit(image,sr)
        elif value:
            image=_ui_render(menu_font, value,True,color)
            shadow=_ui_render(menu_font, value,True,(5,5,7))
            sr=image.get_rect(midright=(r.right-18,r.centery))
            target.blit(shadow,sr.move(2,2)); target.blit(image,sr)
        controls.append((r, minus, plus))
        y += 45
    _gothic_text(target,small_font,'ARROWS / WASD NAVIGATE   •   ENTER SELECTS   •   ESC BACK',(W//2,panel.bottom-18),(130,124,120),True)
    return controls


def _draw_control_rows(target: pygame.Surface, small_font, x: int, y: int, width: int,
                       heading: str, rows: tuple[tuple[str, str], ...]) -> int:
    _gothic_text(target, small_font, heading, (x, y), (206, 190, 169))
    y += 24
    for key, action in rows:
        _gothic_text_fit(target, small_font, key, (x, y), 170, (228, 219, 202))
        _gothic_text_fit(target, small_font, action, (x + 176, y), max(80, width - 176), (159, 153, 145))
        y += 22
    return y + 8


def draw_controls_menu(target: pygame.Surface, assets: dict[str, pygame.Surface], title_font, small_font,
                       controller_connected: bool) -> list[pygame.Rect]:
    """Player-facing control reference reachable through Settings.

    Keep this reference compact, contextual, and inside the 1280x720 logical safe
    area.  It intentionally documents current bindings rather than old pass history.
    """
    dim = pygame.Surface((W, H), pygame.SRCALPHA); dim.fill((0,0,0,142)); target.blit(dim,(0,0))
    panel = pygame.Rect(92, 28, W - 184, H - 56)
    _draw_menu_panel_skin(target, assets, panel)
    _gothic_text(target, title_font, 'CONTROLS', (W//2, panel.top+40), (224,217,202), True)
    status = 'CONTROLLER CONNECTED' if controller_connected else 'KEYBOARD / MOUSE + OPTIONAL CONTROLLER'
    _gothic_text(target, small_font, status, (W//2, panel.top+74), (139,127,118), True)

    left = panel.left + 42
    right = panel.centerx + 18
    col_w = panel.width // 2 - 72
    y1 = panel.top + 105
    y1 = _draw_control_rows(target, small_font, left, y1, col_w, 'MOVEMENT / EXPLORATION', (
        ('WASD / ARROWS', 'Move'), ('SHIFT', 'Sprint'), ('SPACE', 'Hop'),
        ('E', 'Interact / talk / use'), ('I', 'Open IO Inventory'), ('L', 'Archive'),
        ('MOUSE WHEEL / +/-', 'Zoom'), ('F1', 'Continuity Thread + help'), ('ESC', 'Pause / back'),
    ))
    y1 = _draw_control_rows(target, small_font, left, y1, col_w, 'LANTERN', (
        ('TAB', 'Launch / recall Projection'), ('R', 'Causal Resonance'), ('Q', 'Veil Ward'),
    ))
    _draw_control_rows(target, small_font, left, y1, col_w, 'MACHINES', (
        ('1–6', 'Place main kit part'), ('T', 'Machine Focus'), ('[ / ]', 'Cycle owned parts'),
        ('LMB DRAG', 'Move placed part'), ('CTRL + LMB', 'Flip placed part'), ('RMB', 'Reclaim placed part'),
    ))

    y2 = panel.top + 105
    y2 = _draw_control_rows(target, small_font, right, y2, col_w, 'CONTROLLER — EXPLORATION', (
        ('LEFT STICK', 'Move'), ('LS CLICK', 'Sprint toggle'), ('X', 'Hop'), ('A', 'Interact'),
        ('VIEW / BACK', 'Archive'), ('RS CLICK', 'Inventory'), ('D-PAD UP', 'Help'), ('MENU / START', 'Pause'),
    ))
    y2 = _draw_control_rows(target, small_font, right, y2, col_w, 'CONTROLLER — POWERS', (
        ('Y', 'Projection'), ('LB', 'Veil Ward'), ('RB', 'Causal Resonance'),
    ))
    _draw_control_rows(target, small_font, right, y2, col_w, 'CONTROLLER — MACHINE FOCUS', (
        ('D-PAD DOWN', 'Enter Machine Focus'), ('D-PAD LEFT / RIGHT', 'Cycle owned parts'),
        ('A', 'Place selected part'), ('X HOLD / RELEASE', 'Drag / anchor'),
        ('RS CLICK', 'Flip focused part'), ('Y', 'Reclaim focused part'),
    ))

    back = pygame.Rect(W//2 - 120, panel.bottom - 56, 240, 38)
    _draw_menu_item_skin(target, assets, back, True)
    _gothic_text(target, small_font, 'BACK', back.center, (242,232,216), True)
    return [back]


def draw_quit_confirmation(target: pygame.Surface, assets: dict[str, pygame.Surface], title_font, menu_font,
                           small_font, selected: int) -> list[pygame.Rect]:
    dim = pygame.Surface((W, H), pygame.SRCALPHA); dim.fill((0,0,0,165)); target.blit(dim,(0,0))
    panel = pygame.Rect(W//2-285, H//2-165, 570, 330)
    _draw_menu_panel_skin(target, assets, panel)
    _gothic_text(target, title_font, holoverse_link.quit_label('QUIT TO DESKTOP') + '?', (W//2, panel.top+54), (224,217,202), True)
    _gothic_text(target, small_font, 'ANY UNSAVED PROGRESS SINCE YOUR LAST MANUAL SAVE WILL BE LOST.',
                 (W//2, panel.top+106), (176,150,137), True)
    _gothic_text(target, small_font, 'SAVE GAME IS AVAILABLE DIRECTLY ABOVE SETTINGS IN THE PAUSE MENU.',
                 (W//2, panel.top+134), (133,128,123), True)
    items = ('CANCEL', holoverse_link.quit_label('QUIT TO DESKTOP'))
    rects=[]
    y=panel.top+184
    for i,item in enumerate(items):
        r=pygame.Rect(panel.left+90,y,390,48); rects.append(r)
        _draw_menu_item_skin(target, assets, r, i == selected)
        _gothic_text(target, menu_font, item, r.center, (242,232,216) if i==selected else (177,171,163), True)
        y += 58
    return rects


def _save_slot_summary(slot: int) -> tuple[str, str]:
    data = _load_manual_slot(slot)
    if not data:
        return "EMPTY", "No manual save"
    world = str(data.get("world", "?")).upper()
    stamp = str(data.get("saved_at", "Unknown time")).replace("T", " ")
    player = data.get("player", {}) if isinstance(data.get("player"), dict) else {}
    try:
        x, y = int(float(player.get("x", 0))), int(float(player.get("y", 0)))
        era = "FUTURE" if world == "A" else "PAST" if world == "B" else f"WORLD {world}"
        location = f"{era}  •  {x}, {y}"
    except (TypeError, ValueError):
        location = f"WORLD {world}"
    return location, stamp


def draw_save_slots_menu(target: pygame.Surface, assets: dict[str, pygame.Surface], title_font, menu_font, small_font,
                         selected: int, mode: str, status: str) -> list[pygame.Rect]:
    dim = pygame.Surface((W, H), pygame.SRCALPHA); dim.fill((0,0,0,136)); target.blit(dim,(0,0))
    panel=pygame.Rect(W//2-300,H//2-255,600,510); _draw_menu_panel_skin(target,assets,panel)
    title = 'SAVE GAME' if mode == 'save' else 'LOAD GAME'
    _gothic_text(target,title_font,title,(W//2,panel.top+50),(224,217,202),True)
    _gothic_text(target,small_font,'MANUAL SAVE SLOTS',(W//2,panel.top+86),(139,127,118),True)
    rects=[]; y=panel.top+126
    for i in range(SAVE_SLOT_COUNT):
        r=pygame.Rect(panel.left+44,y,512,82); rects.append(r)
        _draw_menu_item_skin(target, assets, r, i == selected)
        color=(242,232,216) if i==selected else (177,171,163)
        primary, secondary = _save_slot_summary(i+1)
        _gothic_text(target,menu_font,f'SLOT {i+1}',(r.left+16,r.top+13),color)
        _gothic_text(target,small_font,primary,(r.left+142,r.top+15),(166,157,149))
        _gothic_text(target,small_font,secondary,(r.left+142,r.top+43),(124,118,114))
        y += 91
    back=pygame.Rect(panel.left+44,panel.bottom-74,512,42); rects.append(back)
    _draw_menu_item_skin(target, assets, back, selected == SAVE_SLOT_COUNT)
    _gothic_text(target,menu_font,'BACK',back.center,(242,232,216) if selected==SAVE_SLOT_COUNT else (177,171,163),True)
    if status:
        _gothic_text(target,small_font,status,(W//2,panel.bottom-12),(160,145,130),True)
    return rects


def _load_optional_sprite(path: Path, max_size: tuple[int, int]) -> pygame.Surface | None:
    try:
        image = pygame.image.load(str(path)).convert_alpha()
        scale = min(max_size[0] / max(1, image.get_width()), max_size[1] / max(1, image.get_height()), 1.0)
        if scale < 1.0:
            image = pygame.transform.smoothscale(
                image,
                (max(1, int(image.get_width() * scale)), max(1, int(image.get_height() * scale))),
            )
        return image
    except Exception:
        return None


def normalize_defeated_boss_ids(raw: object, first_witness_defeated: bool = False) -> set[str]:
    """Normalize the optional schema-v4 portrait list while preserving legacy saves."""
    valid = {boss_id for boss_id, _ in BOSS_PORTRAIT_ROSTER}
    values = raw if isinstance(raw, (list, tuple, set)) else ()
    result = {str(value) for value in values if str(value) in valid}
    if first_witness_defeated:
        result.add(ENTITY_ID)
    return result


def load_boss_portraits() -> dict[str, pygame.Surface]:
    """Load tightly cropped, small portraits directly from the authored boss PNGs."""
    portraits: dict[str, pygame.Surface] = {}
    for boss_id, filename in BOSS_PORTRAIT_ROSTER:
        try:
            image = pygame.image.load(str(ENTITY_DIR / filename)).convert_alpha()
            bounds = image.get_bounding_rect(min_alpha=3)
            if bounds.width <= 0 or bounds.height <= 0:
                continue
            image = image.subsurface(bounds).copy()
            scale = min(BOSS_PORTRAIT_SIZE / image.get_width(), BOSS_PORTRAIT_SIZE / image.get_height(), 1.0)
            if scale < 1.0:
                image = pygame.transform.smoothscale(
                    image,
                    (max(1, int(round(image.get_width() * scale))), max(1, int(round(image.get_height() * scale)))),
                )
            portraits[boss_id] = image
        except Exception:
            continue
    return portraits


def draw_defeated_boss_strip(target: pygame.Surface, portraits: dict[str, pygame.Surface],
                             defeated_ids: set[str]) -> list[pygame.Rect]:
    """Line up compact defeated-boss sprites from left to right at the top-left."""
    rects: list[pygame.Rect] = []
    visible_ids = [boss_id for boss_id, _ in BOSS_PORTRAIT_ROSTER if boss_id in defeated_ids and boss_id in portraits]
    for index, boss_id in enumerate(visible_ids):
        slot = pygame.Rect(12 + index * BOSS_PORTRAIT_SLOT, 12, 44, 44)
        veil = pygame.Surface(slot.size, pygame.SRCALPHA)
        veil.fill((7, 7, 10, 184))
        target.blit(veil, slot)
        pygame.draw.rect(target, (115, 97, 85), slot, 1)
        portrait = portraits[boss_id]
        target.blit(portrait, portrait.get_rect(center=slot.center))
        rects.append(slot)
    return rects


def load_lore_debris_assets() -> dict[str, pygame.Surface]:
    """Load persistent world memory debris strictly from the particle bank.

    Lore records retain their semantic historical asset names for save compatibility,
    but removed names now map deterministically onto assets/source/particles rather
    than onto active drone artwork.  Drones remain gameplay/mechanical entities.
    """
    result: dict[str, pygame.Surface] = {}
    particle_paths = _particle_png_paths()
    fallback_paths = particle_paths
    by_name = {path.name: path for path in particle_paths}
    records = tuple(dict.fromkeys(record.asset_name for record in LORE_RECORDS))
    for name in records:
        path = by_name.get(name)
        if path is None and fallback_paths:
            # Stable assignment is derived from the semantic filename, not list order,
            # so inserting a new lore record later does not reshuffle older visuals.
            token = name.encode("utf-8", errors="ignore")
            stable_index = sum((offset + 1) * value for offset, value in enumerate(token)) % len(fallback_paths)
            path = fallback_paths[stable_index]
        if path is None:
            continue
        try:
            image = pygame.image.load(str(path)).convert_alpha()
            bounds = image.get_bounding_rect(min_alpha=3)
            if bounds.width <= 0 or bounds.height <= 0:
                continue
            image = image.subsurface(bounds).copy()
            image = _scale_surface_to_fit(image, (48, 48), allow_upscale=True, min_side=5)
            image = _stable_memory_debris_surface(image, name)
            result[name] = _soft_edge_surface(image, 4)
        except (pygame.error, OSError, ValueError, TypeError, OverflowError):
            continue
    return result


_ENTITY_PRESENCE_STATIC_CACHE: dict[tuple[int, int], tuple[pygame.Surface, pygame.Surface]] = {}
_ENTITY_PRESENCE_FRAME_CACHE: dict[tuple[int, int], tuple[int, pygame.Surface]] = {}
ENTITY_PRESENCE_ANIMATION_HZ = 12.0
_WORLD_OBJECT_SCALE_CACHE: dict[tuple[int, int, int], pygame.Surface] = {}


def _scaled_world_object_surface(source: pygame.Surface, width: int, height: int) -> pygame.Surface:
    """Cache stable world-object resizes while preserving the requested aspect-safe size."""
    width = max(1, int(width))
    height = max(1, int(height))
    key = (id(source), width, height)
    cached = _WORLD_OBJECT_SCALE_CACHE.get(key)
    if cached is not None:
        return cached
    cached = source if source.get_size() == (width, height) else pygame.transform.smoothscale(source, (width, height))
    if len(_WORLD_OBJECT_SCALE_CACHE) >= 96:
        _WORLD_OBJECT_SCALE_CACHE.clear()
    _WORLD_OBJECT_SCALE_CACHE[key] = cached
    return cached


_OBELISK_TONE_CACHE: dict[int, pygame.Surface] = {}

def _subdued_obelisk_surface(source: pygame.Surface) -> pygame.Surface:
    """Reduce the shrine/obelisk white lift while retaining authored detail."""
    key = id(source)
    cached = _OBELISK_TONE_CACHE.get(key)
    if cached is not None:
        return cached
    toned = source.copy()
    shade = max(0, min(255, int(round(255 * OBELISK_BRIGHTNESS))))
    toned.fill((shade, shade, shade, 255), special_flags=pygame.BLEND_RGBA_MULT)
    if len(_OBELISK_TONE_CACHE) >= 96:
        _OBELISK_TONE_CACHE.clear()
    _OBELISK_TONE_CACHE[key] = toned
    return toned


def _entity_presence_static_components(source: pygame.Surface, target_height: int) -> tuple[pygame.Surface, pygame.Surface]:
    """Build the expensive phase-independent Guardian scale/halo once per asset size."""
    key = (id(source), int(target_height))
    cached = _ENTITY_PRESENCE_STATIC_CACHE.get(key)
    if cached is not None:
        return cached
    sw, sh = source.get_size()
    if sw <= 0 or sh <= 0:
        raise ValueError("invalid entity surface size")
    aspect = sw / sh
    target_width = max(6, min(256, int(round(target_height * aspect))))
    base = pygame.transform.smoothscale(source, (target_width, target_height))
    pad = 24
    glow = pygame.Surface((target_width + pad * 2, target_height + pad * 2), pygame.SRCALPHA)
    soft_source = base.copy()
    soft_source.fill((38, 82, 98, 0), special_flags=pygame.BLEND_RGBA_ADD)
    softened = pygame.transform.smoothscale(
        pygame.transform.smoothscale(
            soft_source,
            (max(2, target_width // 5), max(2, target_height // 5)),
        ),
        (target_width, target_height),
    )
    for grow, alpha in ENTITY_HALO_LAYERS:
        gw = max(1, target_width + grow * 2)
        gh = max(1, target_height + grow * 2)
        halo = pygame.transform.smoothscale(softened, (gw, gh)).copy()
        halo.set_alpha(alpha)
        glow.blit(halo, halo.get_rect(center=glow.get_rect().center), special_flags=pygame.BLEND_RGBA_ADD)
    if len(_ENTITY_PRESENCE_STATIC_CACHE) >= 32:
        _ENTITY_PRESENCE_STATIC_CACHE.clear()
        _ENTITY_PRESENCE_FRAME_CACHE.clear()
    _ENTITY_PRESENCE_STATIC_CACHE[key] = (base, glow)
    return base, glow


def _entity_presence_surface(source: pygame.Surface, target_height: int, phase: float) -> pygame.Surface:
    """Render a bounded animated Guardian presence without rebuilding static transforms every frame.

    Seven Guardians may be visible in the open Past field at once.  Static scaling
    and halo construction are cached, while the subtle refraction is sampled at
    12 Hz and reused between samples.  This preserves the visual language while
    avoiding dozens of smoothscale operations per rendered frame.
    """
    target_height = max(8, min(256, int(target_height)))
    cache_key = (id(source), target_height)
    phase_bucket = int(max(0.0, float(phase)) * ENTITY_PRESENCE_ANIMATION_HZ)
    frame_cached = _ENTITY_PRESENCE_FRAME_CACHE.get(cache_key)
    if frame_cached is not None and frame_cached[0] == phase_bucket:
        return frame_cached[1]
    try:
        base, static_glow = _entity_presence_static_components(source, target_height)
        target_width, target_height = base.get_size()
    except (pygame.error, OSError, ValueError, TypeError, OverflowError):
        fallback = pygame.Surface((20, max(20, min(96, target_height))), pygame.SRCALPHA)
        pygame.draw.rect(fallback, (160, 210, 225, 190), fallback.get_rect(), border_radius=4)
        return fallback

    try:
        pad = 24
        distorted = pygame.Surface((target_width + pad * 2, target_height + pad * 2), pygame.SRCALPHA)
        band_h = max(2, int(ENTITY_DISTORTION_BAND))
        amplitude = max(0.0, min(6.0, float(ENTITY_DISTORTION_AMPLITUDE) * _PRESENTATION_MOTION_SCALE))
        sampled_phase = phase_bucket / ENTITY_PRESENCE_ANIMATION_HZ
        for y in range(0, target_height, band_h):
            h = min(band_h, target_height - y)
            dx = int(round(
                math.sin(sampled_phase * 2.2 + y * 0.105) * amplitude
                + math.sin(sampled_phase * 1.13 + y * 0.037) * (amplitude * 0.42)
            ))
            strip = base.subsurface(pygame.Rect(0, y, target_width, h))
            distorted.blit(strip, (pad + dx, pad + y))

        result = static_glow.copy()
        echo = distorted.copy()
        echo.fill((92, 150, 210, 44), special_flags=pygame.BLEND_RGBA_MULT)
        result.blit(echo, (2, -1), special_flags=pygame.BLEND_RGBA_ADD)
        result.blit(distorted, (0, 0))
        tint = distorted.copy()
        tint.fill((35, 62, 78, 0), special_flags=pygame.BLEND_RGBA_ADD)
        tint.set_alpha(ENTITY_GLOW_ALPHA)
        result.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        result = _soft_edge_surface(result, 12)
        _ENTITY_PRESENCE_FRAME_CACHE[cache_key] = (phase_bucket, result)
        return result
    except (pygame.error, OSError, ValueError, TypeError, OverflowError, MemoryError):
        return base


def _random_walkable_location(layer, rng: random.Random, avoid: tuple[float, float] | None = None,
                              min_distance: float = 450.0) -> tuple[float, float]:
    mask = layer.mask
    w, h = mask.get_size()
    reachable = mask
    if avoid is not None:
        seed = nearest_walkable_point(layer, avoid)
        try:
            reachable = mask.connected_component((int(seed[0]), int(seed[1])))
        except Exception:
            reachable = mask
    for _ in range(5000):
        x = rng.randrange(40, max(41, w - 40))
        y = rng.randrange(40, max(41, h - 40))
        if not reachable.get_at((x, y)) or not footprint_walkable_at(layer, x, y):
            continue
        if avoid and pygame.Vector2(x, y).distance_to(avoid) < min_distance:
            continue
        return float(x), float(y)
    return nearest_spawn(reachable)


def _random_walkable_location_away(layer: ArtLayer, rng: random.Random,
                                   component_hint: tuple[float, float],
                                   avoid: list[tuple[float, float]],
                                   min_distance: float = LORE_PLACEMENT_SEPARATION) -> tuple[float, float]:
    """Choose a stable random-looking point on the hint's reachable component."""
    mask = layer.mask
    width, height = mask.get_size()
    seed = nearest_walkable_point(layer, component_hint)
    try:
        reachable = mask.connected_component((int(seed[0]), int(seed[1])))
    except Exception:
        reachable = mask
    for separation in (min_distance, min_distance * 0.72, min_distance * 0.48):
        for _ in range(2600):
            x = rng.randrange(40, max(41, width - 40))
            y = rng.randrange(40, max(41, height - 40))
            if not reachable.get_at((x, y)) or not footprint_walkable_at(layer, x, y):
                continue
            if any(pygame.Vector2(x, y).distance_to(point) < separation for point in avoid):
                continue
            return float(x), float(y)
    return nearest_walkable_point(layer, seed)


def build_lore_placements(stacks: dict[str, WorldStack], sprites: dict[str, pygame.Surface],
                          entity_pos: tuple[float, float]) -> tuple[LorePlacement, ...]:
    """Register deterministic memory-debris encounters without writing positions into saves."""
    rng = random.Random(DEBRIS_STORY_SEED)
    placements: list[LorePlacement] = []
    used = {
        "a": [WORLD_A_START, FUTURE_CLUE_POS],
        "b": [WORLD_B_ENTRY_HINT, entity_pos],
    }
    for record in LORE_RECORDS:
        stack = stacks.get(record.world)
        if stack is None or not stack.walk_layers:
            continue
        # World A's accepted player-connected region is walk layer 4; raw mask
        # area is not a safe proxy because decorative alpha islands can be larger.
        layer = (layer_by_number(stack, 4) if record.world == "a" else stack.walk_layers[0])
        if layer is None:
            layer = stack.walk_layers[0]
        hint = WORLD_A_START if record.world == "a" else WORLD_B_ENTRY_HINT
        point = _random_walkable_location_away(layer, rng, hint, used[record.world])
        used[record.world].append(point)
        placements.append(LorePlacement(record, point, layer.number, sprites.get(record.asset_name)))
    return tuple(placements)


def nearest_unread_echo_position(placements: tuple[LorePlacement, ...], world_key: str,
                                 discovered: set[str], shrine_activated: bool,
                                 player_pos: tuple[float, float], resonance_learned: bool = False,
                                 story_complete: bool = False) -> tuple[float, float] | None:
    candidates = [
        placement for placement in placements
        if placement.record.world == world_key
        and (story_complete or placement.record.shrine_echo)
        and placement.record.record_id not in discovered
        and lore_record_available(placement.record, shrine_activated, resonance_learned, story_complete)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda placement: pygame.Vector2(player_pos).distance_to(placement.position)).position


def nearby_unread_lore(placements: tuple[LorePlacement, ...], world_key: str, walk_number: int,
                       player_pos: tuple[float, float], discovered: set[str],
                       shrine_activated: bool, resonance_learned: bool = False,
                       story_complete: bool = False) -> LorePlacement | None:
    candidates = [
        placement for placement in placements
        if placement.record.world == world_key and placement.walk_number == walk_number
        and placement.record.record_id not in discovered
        and lore_record_available(placement.record, shrine_activated, resonance_learned, story_complete)
        and pygame.Vector2(player_pos).distance_to(placement.position) <= LORE_TRIGGER_RADIUS
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda placement: pygame.Vector2(player_pos).distance_to(placement.position))


def _draw_lore_debris(target: pygame.Surface, placements: tuple[LorePlacement, ...], world_key: str,
                      walk_number: int, source_rect: pygame.Rect, discovered: set[str],
                      shrine_activated: bool, resonance_learned: bool, story_complete: bool,
                      glow: pygame.Surface | None, phase: float) -> None:
    screen_scale = W / source_rect.width
    for placement in placements:
        record = placement.record
        if record.world != world_key or placement.walk_number != walk_number:
            continue
        if not lore_record_available(record, shrine_activated, resonance_learned, story_complete):
            continue
        sx, sy = world_to_screen_shared(placement.position[0], placement.position[1], source_rect)
        if sx < -100 or sx > W + 100 or sy < -100 or sy > H + 100:
            continue
        read = record.record_id in discovered
        if not read and glow is not None:
            pulse = 0.88 + math.sin(phase * 2.7 + len(record.record_id)) * 0.12
            diameter = max(34, int((64 if record.shrine_echo else 48) * pulse * screen_scale))
            _battle_blit_scaled(
                target, glow,
                pygame.Rect(sx - diameter // 2, sy - diameter + 6, diameter, diameter),
                74 if record.shrine_echo else 48,
            )
        sprite = placement.sprite
        if sprite is None:
            fallback = pygame.Surface((18, 18), pygame.SRCALPHA)
            pygame.draw.polygon(fallback, (160, 184, 190, 190), ((9, 0), (17, 9), (9, 17), (0, 9)))
            sprite = fallback
        width = max(4, int(round(sprite.get_width() * screen_scale)))
        height = max(4, int(round(sprite.get_height() * screen_scale)))
        try:
            # Both dimensions derive from the same camera scale, so aspect is preserved.
            image = _scale_surface_to_fit(sprite, (width, height), allow_upscale=True, min_side=4)
            image.set_alpha(92 if read else 226)
            target.blit(image, image.get_rect(midbottom=(sx, sy)))
        except (pygame.error, ValueError, TypeError, OverflowError):
            continue


def draw_lore_card(target: pygame.Surface, title_font, small_font, title: str,
                   lines: tuple[str, str], timer: float) -> None:
    if timer <= 0.0:
        return
    fade = min(1.0, (LORE_CARD_TIME - timer) / 0.28, timer / 0.52)
    alpha = max(0, min(255, int(232 * fade)))
    panel = pygame.Rect(W // 2 - 350, 45, 700, 128)
    veil = pygame.Surface(panel.size, pygame.SRCALPHA)
    veil.fill((7, 9, 12, alpha))
    target.blit(veil, panel)
    border = (104, 128, 132, int(190 * fade))
    frame = pygame.Surface(panel.size, pygame.SRCALPHA)
    pygame.draw.rect(frame, border, frame.get_rect(), 1)
    pygame.draw.line(frame, border, (22, 38), (panel.width - 22, 38), 1)
    target.blit(frame, panel)
    title_surface = _ui_render(title_font, title, True, (220, 216, 202))
    line1 = _ui_render(small_font, lines[0], True, (190, 194, 190))
    line2 = _ui_render(small_font, lines[1], True, (172, 181, 181))
    for surface in (title_surface, line1, line2):
        surface.set_alpha(int(255 * fade))
    target.blit(title_surface, title_surface.get_rect(midtop=(panel.centerx, panel.top + 12)))
    target.blit(line1, line1.get_rect(midtop=(panel.centerx, panel.top + 58)))
    target.blit(line2, line2.get_rect(midtop=(panel.centerx, panel.top + 84)))


def draw_lore_archive(target: pygame.Surface, title_font, menu_font, small_font,
                      discovered: set[str], selected: int) -> None:
    """Temporary rereadable archive; unknown records remain unnamed."""
    records = [record for record in LORE_RECORDS if record.record_id in discovered]
    dim = pygame.Surface((W, H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 188))
    target.blit(dim, (0, 0))
    panel = pygame.Rect(74, 48, W - 148, H - 96)
    _draw_gothic_frame(target, panel)
    _gothic_text(target, title_font, "ARCHIVE FRAGMENTS", (panel.left + 34, panel.top + 28), (224, 217, 202))
    counter = _ui_render(small_font, f"RECOVERED {len(records)} / {len(LORE_RECORDS)}", True, (139, 150, 151))
    target.blit(counter, counter.get_rect(topright=(panel.right - 34, panel.top + 32)))
    pygame.draw.line(target, (88, 77, 73), (panel.left + 28, panel.top + 76), (panel.right - 28, panel.top + 76), 1)
    if not records:
        _gothic_text(target, menu_font, "NO FRAGMENTS RECOVERED", panel.center, (166, 157, 149), True)
        return
    selected = max(0, min(int(selected), len(records) - 1))
    list_rect = pygame.Rect(panel.left + 28, panel.top + 96, 355, panel.height - 146)
    detail_rect = pygame.Rect(list_rect.right + 26, list_rect.top, panel.right - list_rect.right - 54, list_rect.height)
    pygame.draw.line(target, (76, 68, 66), (list_rect.right + 12, list_rect.top), (list_rect.right + 12, list_rect.bottom), 1)
    visible = 10
    start = max(0, min(selected - visible // 2, max(0, len(records) - visible)))
    for row, record in enumerate(records[start:start + visible]):
        index = start + row
        rect = pygame.Rect(list_rect.left, list_rect.top + row * 40, list_rect.width, 34)
        if index == selected:
            hi = pygame.Surface(rect.size, pygame.SRCALPHA)
            hi.fill((68, 64, 67, 168))
            target.blit(hi, rect)
            pygame.draw.rect(target, (123, 111, 101), rect, 1)
        _gothic_text(
            target, small_font, record.title, (rect.left + 12, rect.top + 9),
            (232, 224, 210) if index == selected else (161, 158, 153),
        )
    record = records[selected]
    era = "THE PRESENT / FUTURE" if record.world == "a" else "THE BEGINNING / PAST"
    tier = "WITNESS ECHO" if record.shrine_echo else "DEEP ARCHIVE" if record.unlock == "reconstructed" else "RESONANT ARCHIVE" if record.unlock == "resonance" else "ENVIRONMENTAL RECORD"
    _gothic_text_fit(target, title_font, record.title, (detail_rect.left + 24, detail_rect.top + 28), detail_rect.width - 48, (220, 216, 202))
    _gothic_text(target, small_font, era, (detail_rect.left + 26, detail_rect.top + 76), (126, 145, 148))
    _gothic_text(target, small_font, tier, (detail_rect.left + 26, detail_rect.top + 102), (126, 117, 113))
    pygame.draw.line(target, (82, 73, 70), (detail_rect.left + 24, detail_rect.top + 136), (detail_rect.right - 24, detail_rect.top + 136), 1)
    _gothic_text(target, menu_font, record.lines[0], (detail_rect.left + 26, detail_rect.top + 184), (198, 195, 188))
    _gothic_text(target, menu_font, record.lines[1], (detail_rect.left + 26, detail_rect.top + 230), (183, 185, 181))
    _gothic_text(
        target, small_font, "UP / DOWN BROWSE   •   ESC CLOSE",
        (panel.centerx, panel.bottom - 28), (147, 140, 134), True,
    )


def _entity_dialogue_pages(first_visit: bool, declined_count: int) -> tuple[tuple[str, str], ...]:
    if declined_count > 0:
        return (("The Archive of Origin remains sealed.", "You may challenge this Guardian whenever you choose."),)
    return (
        ("I preserve the civilization before its memories became ruins.", "Gleebs requires this Archive of Origin, not my destruction."),
        ("I am the lock around what survived.", "Defeat the Guardian function and the archive becomes retrievable."),
    )


def _rooted_crown_dialogue_pages(first_visit: bool, declined_count: int) -> tuple[tuple[str, str], ...]:
    if declined_count > 0:
        return (("The Archive of Return remains rooted here.", "No order binds these Guardians. Return when you are ready."),)
    return (
        ("I preserve how your civilization understood return, inheritance and continuity.", "Gleebs needs the relationships stored beneath the Crown."),
        ("I am a Memory Guardian, not a ruler.", "Break the seal and take the Archive of Return."),
    )


def _rooted_crown_shrine_dialogue_pages(activated: bool) -> tuple[tuple[str, str], ...]:
    if activated:
        return (
            ("The Crown is recorded without its roots.", "A second causal monument now answers the lantern."),
            ("Two histories have been changed deliberately.", "The afterlife is beginning to remember your interference."),
        )
    return (
        ("This monument grew where the future was empty.", "Its crown no longer bends with the water-motion."),
        ("The Beginning lost a rooted keeper.", "Bind the result so the change becomes part of your escape record."),
    )


def _rooted_crown_clue_pages() -> tuple[tuple[str, str], ...]:
    return (
        ("A second absence has appeared since the Witness was restored.", "It is shaped like something rooted beneath a crown."),
        ("Causal Resonance already knows how to listen backward.", "Return to the Beginning and follow the new answer."),
    )


def _veil_warden_dialogue_pages(first_visit: bool, declined_count: int) -> tuple[tuple[str, str], ...]:
    if first_visit:
        return (
            ("Three records now touch the same impossible future.", "You have mistaken the Veil for distance."),
            ("I am the mechanism that made separation feel sacred.", "Break me, and the Archive will have to remember why you were contained."),
        )
    if declined_count > 0:
        return (
            ("You found the boundary and chose not to test it.", "That is what the Architects expected of every condemned mind."),
            ("The Veil still recognizes your sentence.", "Will you make it recognize your refusal?"),
        )
    return (
        ("The Veil is not a horizon.", "It is an instruction repeated until you believed it was the world."),
        ("I keep that instruction closed.", "Choose whether it remains true."),
    )




def _memory_guardian_dialogue_pages(entity_id: str, first_visit: bool, declined_count: int) -> tuple[tuple[str, str], ...]:
    if entity_id == VEIL_WARDEN_ID:
        return _veil_warden_dialogue_pages(first_visit, declined_count)
    if entity_id == ROOTED_CROWN_ID:
        return _rooted_crown_dialogue_pages(first_visit, declined_count)
    if entity_id == ENTITY_ID:
        return _entity_dialogue_pages(first_visit, declined_count)
    archive_lines = {
        ARCHIVE_CHORUS_ID: ("I hold the voices your civilization lost.", "Break my seal and Gleebs can recover how the dead once spoke to one another."),
        HOLLOW_ENGINE_ID: ("I hold the machines that remembered their makers.", "Break my seal and Gleebs can recover how your civilization built continuity into matter."),
        LAST_CARTOGRAPHER_ID: ("I hold the world as it was understood, not merely where it was.", "Break my seal and Gleebs can recover the relationships between places your people inhabited."),
        FINAL_GUARDIAN_ID: ("I contain the final index of the lost civilization.", "Every recovered archive makes you more capable of surviving me. None are required to try."),
    }
    line1, line2 = archive_lines.get(entity_id, ("A sealed memory archive waits.", "Gleebs needs what it preserves."))
    if declined_count > 0:
        return (("The archive remains sealed.", "You may challenge this Guardian whenever you choose."), (line1, line2))
    return ((line1, line2), ("I am not your enemy. I am the lock around a memory.", "Defeat the Guardian function and the archive becomes retrievable."))

def _shrine_name_for(entity_id: str) -> str:
    if entity_id == ENTITY_ID:
        return SHRINE_NAME
    if entity_id == ROOTED_CROWN_ID:
        return ROOTED_CROWN_SHRINE_NAME
    if entity_id == VEIL_WARDEN_ID:
        return VEIL_WARDEN_SHRINE_NAME
    guardian_name = MEMORY_GUARDIAN_NAMES.get(entity_id, "MEMORY GUARDIAN")
    if guardian_name.startswith("THE "):
        guardian_name = guardian_name[4:]
    return f"SHRINE OF THE {guardian_name}"


def _generic_guardian_shrine_dialogue_pages(entity_id: str, activated: bool) -> tuple[tuple[str, str], ...]:
    guardian_name = MEMORY_GUARDIAN_NAMES.get(entity_id, "THE MEMORY GUARDIAN")
    archive_label = {
        ARCHIVE_CHORUS_ID: "voices",
        HOLLOW_ENGINE_ID: "machines",
        LAST_CARTOGRAPHER_ID: "worlds",
        FINAL_GUARDIAN_ID: "civilization index",
    }.get(entity_id, "memory")
    if activated:
        return (
            (f"{guardian_name} is recorded here without its Past authority.", f"The Future now preserves the recovered archive of {archive_label}."),
            ("The causal monument remains stable.", "Challenge its Echo if you want the record to resist again."),
        )
    return (
        (f"A monument to {guardian_name} now exists in the Future.", "It was absent before IO changed the Beginning."),
        (f"Bind the archive of {archive_label} into the Present.", "The Shrine will remain as evidence that this history was changed deliberately."),
    )


def _guardian_shrine_dialogue_pages(entity_id: str, activated: bool, story_complete: bool = False) -> tuple[tuple[str, str], ...]:
    if entity_id == VEIL_WARDEN_ID:
        return _veil_warden_shrine_dialogue_pages(activated)
    if entity_id == ROOTED_CROWN_ID:
        return _rooted_crown_shrine_dialogue_pages(activated)
    if entity_id == ENTITY_ID:
        return _shrine_dialogue_pages(activated, story_complete)
    return _generic_guardian_shrine_dialogue_pages(entity_id, activated)


def _veil_warden_shrine_dialogue_pages(activated: bool) -> tuple[tuple[str, str], ...]:
    if activated:
        return (
            ("The Warden is recorded without its boundary authority.", "The Shrine now preserves a separation rule IO has already broken."),
            ("Challenge the echo if you want the rule to resist harder.", "The original Veil cannot forget that IO defeated its keeper."),
        )
    return (
        ("A third monument occupies a Future that once contained only the Veil.", "Its shape resembles a latch more than a grave."),
        ("Bind the record.", "Make the Archive disclose what the Warden was built to keep apart."),
    )


def _shrine_dialogue_pages(activated: bool, story_complete: bool = False) -> tuple[tuple[str, str], ...]:
    if activated and story_complete:
        return (
            ("The three memories have returned.", "The First Witness is no longer a fractured record."),
            ("Your lantern holds the reconstructed cadence.", "Causal Resonance now recovers faster."),
        )
    if activated:
        return (
            ("The Shrine is bound, but incomplete.", "Three broken memories escaped into both ages."),
            ("Approach the scattered memory debris to read each echo.", "Resonance can hear them without revealing a waypoint."),
        )
    return (
        ("The shape is familiar.", "The water-motion is gone, but the presence remains."),
        ("This monument was absent before the Beginning changed.", "Something inside it remembers being defeated."),
    )


def _future_clue_dialogue_pages(resonance_learned: bool) -> tuple[tuple[str, str], ...]:
    if resonance_learned:
        return (
            ("The absence still bends the ruin.", "Your lantern remembers the direction of its missing record."),
            ("Causal Resonance is already attuned.", "In the Beginning, press R and listen for distance."),
        )
    return (
        ("An absence has weight here.", "The ruin bends around a monument that never existed."),
        ("A dead signal points backward into the Beginning.", "The lantern can be taught to hear what history omitted."),
    )


def _gleebs_topic_entries(world_key: str) -> tuple[tuple[str, str], ...]:
    """Return Gleebs menu actions in presentation order.

    Temporal return is intentionally first so the most immediate navigation
    action is available as soon as the anchor opens.  The label uses the
    player's plain-language era names while the underlying destination keys
    remain unchanged.
    """
    travel = "RETURN TO THE PAST" if world_key == "a" else "RETURN TO THE PRESENT"
    return (
        ("travel", travel),
        ("mission", "CURRENT MISSION"),
        ("powers", "LANTERN POWERS"),
        ("why_io", "WHY IO"),
        ("holoverse", "THE HOLOVERSE"),
        ("mind", "THE MIND"),
        ("leave", "LEAVE"),
    )


def _gleebs_topic_labels(world_key: str) -> tuple[str, ...]:
    return tuple(label for _topic, label in _gleebs_topic_entries(world_key))


def _gleebs_mission_pages(entity_defeated: bool, shrine_activated: bool,
                          first_witness_echoes_complete: bool, rooted_crown_clue_discovered: bool,
                          rooted_crown_defeated: bool, rooted_crown_shrine_activated: bool,
                          veil_warden_defeated: bool, veil_warden_shrine_activated: bool,
                          guardian_retrieved_count: int = 0) -> tuple[tuple[str, str], ...]:
    total = len(MEMORY_GUARDIAN_ORDER)
    if guardian_retrieved_count >= total:
        return (
            ("GLEEBS: I have every surviving civilization archive.", "Origin. Return. Separation. Voices. Machines. Worlds. The final index. Nothing else is required from this prison."),
            ("You gave me the memory structures I needed for the Holoverse.", "I will honor the exchange: IO will not remain a record. I will grant you life outside the afterlife."),
        )
    if guardian_retrieved_count > 0:
        return (
            (f"GLEEBS: {guardian_retrieved_count} of {total} civilization archives recovered.", "The Guardians are independent. Challenge whichever archive you can survive next."),
            ("The Null Custodian can be challenged at any time.", "Do not mistake availability for fairness. Every lantern upgrade improves your odds against the final archive."),
        )
    return (
        ("GLEEBS: Seven Memory Guardians remain in the Beginning.", "They are not rulers or enemies. They are sealed archives of the civilization that condemned you here."),
        ("Challenge them in any order. Bring me what each obelisk protects.", "I need those memory structures for the Holoverse, and when all seven are retrieved I will grant you life."),
        ("The Null Custodian is already accessible.", "It is intentionally close to impossible without the upgrades hidden in your other recovered records and Echo Challenges."),
    )


def _gleebs_why_io_pages(archive_density_known: bool, holoverse_known: bool) -> tuple[tuple[str, str], ...]:
    if holoverse_known:
        return (
            ("GLEEBS: I did not find you because you were important to your civilization.", "I found you because your memory archive remained structurally useful after everything else failed."),
            ("Your memories preserve relationships between places, people, errors and revisions.", "That continuity is more valuable to me than a clean historical record."),
            ("The Holoverse needed a seed that could remember a world after the world was gone.", "You were already doing that inside the afterlife."),
        )
    if archive_density_known:
        return (
            ("GLEEBS: Your retention density is abnormal.", "The afterlife compressed you, but it did not erase the internal relationships between your memories."),
            ("I need those relationships, not a biography.", "Keep surviving and more of the archive will become readable from outside the system."),
        )
    return (
        ("GLEEBS: I am interested in the shape of your archive.", "Something in you retained continuity that this system was designed to reduce to a record."),
        ("Do not confuse my interest with rescue.", "Escape first. Then you can decide what part of yourself I am allowed to study."),
    )


def _gleebs_holoverse_pages(holoverse_known: bool, veil_known: bool) -> tuple[tuple[str, str], ...]:
    if holoverse_known:
        return (
            ("GLEEBS: The Holoverse is not this afterlife.", "It is a later construction that needs memories to remain relational instead of becoming static scenery."),
            ("Your archive contains damaged but coherent models of lived space.", "Those models can seed places that remember how they were used, changed and understood."),
            ("I need data from you. I do not need your imprisonment.", "The distinction matters, IO. Especially once you reach the outside."),
        )
    if veil_known:
        return (
            ("GLEEBS: You have learned what the Veil does. That is enough for now.", "The Holoverse is external to this prison and much later than the civilization that condemned you."),
            ("I require a kind of continuity your captors accidentally preserved.", "The archive will explain the rest when it can survive being opened."),
        )
    return (
        ("GLEEBS: The Holoverse is a later problem.", "For you, it is only proof that something exists beyond the chronology of this afterlife."),
        ("Do not chase my project yet.", "First prove that your continuity can cross the Veil without becoming only data."),
    )


def _gleebs_power_pages(*, entity_defeated: bool, shrine_activated: bool,
                         rooted_crown_shrine_activated: bool, veil_warden_shrine_activated: bool,
                         rematch_wins: dict[str, int], defeated_boss_ids: set[str] | None = None) -> tuple[tuple[str, str], ...]:
    total_echo_wins = sum(max(0, int(value)) for value in rematch_wins.values())
    defeated_boss_ids = defeated_boss_ids or set()
    learned: list[str] = []
    if shrine_activated:
        learned.append("R: Causal Resonance listens for missing records.")
    if rooted_crown_shrine_activated:
        learned.append("Q: Veil Ward briefly stabilizes Future IO.")
    if entity_defeated:
        learned.append("TAB: Lantern Projection leaves IO in place while you scout.")
    if total_echo_wins >= REMOTE_RESONANCE_UNLOCK_WINS:
        learned.append("R while projecting: Remote Resonance scans from the drone.")
    if total_echo_wins >= ENTROPY_ARC_UNLOCK_WINS:
        learned.append("Entropy Arc: a battle command that cuts Presence directly.")
    if veil_warden_shrine_activated:
        learned.append("SPACE while projecting: Projection Lance attacks hunter drones.")
    if not learned:
        return (("GLEEBS: Your lantern is still mostly dormant.", "Bind causal records and survive their Echo Challenges to teach it new behaviors."),)

    pages: list[tuple[str, str]] = []
    for index in range(0, len(learned), 2):
        line_a = learned[index]
        line_b = learned[index + 1] if index + 1 < len(learned) else "These powers are stored in IO's continuity, not in a separate inventory."
        pages.append((line_a, line_b))

    archive_lines = [
        f"{ARCHIVE_ATTUNEMENTS[g][0]}: {ARCHIVE_ATTUNEMENTS[g][1]}"
        for g in MEMORY_GUARDIAN_ORDER[:-1] if g in defeated_boss_ids
    ]
    for index in range(0, len(archive_lines), 2):
        line_a = archive_lines[index]
        line_b = archive_lines[index + 1] if index + 1 < len(archive_lines) else "Recovered archives permanently attune IO; no equipment slot is required."
        pages.append((line_a, line_b))

    next_unlock = "All known Echo mastery thresholds are complete."
    if total_echo_wins < REMOTE_RESONANCE_UNLOCK_WINS:
        next_unlock = f"Next Echo mastery: Remote Resonance at {REMOTE_RESONANCE_UNLOCK_WINS} total Echo wins."
    elif total_echo_wins < ENTROPY_ARC_UNLOCK_WINS:
        next_unlock = f"Next Echo mastery: Entropy Arc at {ENTROPY_ARC_UNLOCK_WINS} total Echo wins."
    elif total_echo_wins < REMOTE_RESONANCE_DEEP_WINS:
        next_unlock = f"Next Echo mastery: deeper Remote Resonance at {REMOTE_RESONANCE_DEEP_WINS} wins."
    elif total_echo_wins < ENTROPY_ARC_MASTERY_WINS:
        next_unlock = f"Next Echo mastery: Entropy Arc+ at {ENTROPY_ARC_MASTERY_WINS} wins."
    elif veil_warden_shrine_activated and total_echo_wins < PROJECTION_LANCE_UPGRADE_WINS:
        next_unlock = f"Next Echo mastery: faster Projection Lance at {PROJECTION_LANCE_UPGRADE_WINS} wins."
    elif veil_warden_shrine_activated and total_echo_wins < PROJECTION_LANCE_MASTERY_WINS:
        next_unlock = f"Next Echo mastery: mastered Projection Lance at {PROJECTION_LANCE_MASTERY_WINS} wins."
    pages.append((f"Echo Challenges cleared: {total_echo_wins}.", next_unlock))
    return tuple(pages)


def _gleebs_mind_pages(guardian_retrieved_count: int) -> tuple[tuple[str, str], ...]:
    level = min(5, 1 + max(0, int(guardian_retrieved_count)) // 2)
    return (
        ("GLEEBS: The Mind is the supervisory intelligence of this afterlife simulation.", "It holds the archive index and was programmed to reject anything attempting to enter or interfere from outside."),
        ("I am exactly the kind of process it was built to stop.", "When I interpret a Guardian for you, The Mind can overwrite labels, corrupt my guidance, and insert false instructions."),
        ("Do not trust the interface merely because it speaks with my name.", "Watch the Guardian itself. Its physical preparation is still part of the preserved record and The Mind cannot rewrite it cleanly in real time."),
        (f"Current interference pressure: {level} / 5.", "Every recovered civilization archive gives us more data, but it also gives The Mind more reason to notice the extraction."),
    )


def _gleebs_topic_pages(topic: str, *, entity_defeated: bool, shrine_activated: bool,
                        first_witness_echoes_complete: bool, rooted_crown_clue_discovered: bool,
                        rooted_crown_defeated: bool, rooted_crown_shrine_activated: bool,
                        veil_warden_defeated: bool, veil_warden_shrine_activated: bool,
                        witnessed_story_moments: set[str], rematch_wins: dict[str, int],
                        guardian_retrieved_count: int = 0,
                        defeated_boss_ids: set[str] | None = None) -> tuple[tuple[str, str], ...]:
    if topic == "mission":
        return _gleebs_mission_pages(entity_defeated, shrine_activated, first_witness_echoes_complete,
                                     rooted_crown_clue_discovered, rooted_crown_defeated,
                                     rooted_crown_shrine_activated, veil_warden_defeated,
                                     veil_warden_shrine_activated, guardian_retrieved_count)
    if topic == "powers":
        return _gleebs_power_pages(
            entity_defeated=entity_defeated, shrine_activated=shrine_activated,
            rooted_crown_shrine_activated=rooted_crown_shrine_activated,
            veil_warden_shrine_activated=veil_warden_shrine_activated, rematch_wins=rematch_wins,
            defeated_boss_ids=defeated_boss_ids,
        )
    if topic == "why_io":
        return _gleebs_why_io_pages(ARCHIVE_DENSITY_ID in witnessed_story_moments,
                                    HOLOVERSE_SEED_ID in witnessed_story_moments)
    if topic == "holoverse":
        return _gleebs_holoverse_pages(HOLOVERSE_SEED_ID in witnessed_story_moments,
                                       VEIL_RESONANCE_ID in witnessed_story_moments)
    if topic == "mind":
        return _gleebs_mind_pages(guardian_retrieved_count)
    return (("The anchor is stable.", "Use it when you are ready to cross."),)


def _draw_gleebs_wrapped(target: pygame.Surface, font: pygame.font.Font, text: str,
                          x: int, y: int, color: tuple[int, int, int], max_width: int,
                          max_lines: int = 3) -> int:
    words = str(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if font.size(candidate)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines - 1:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    used_words = sum(len(line.split()) for line in lines)
    if used_words < len(words) and lines:
        tail = lines[-1]
        while tail and font.size(tail + "...")[0] > max_width:
            tail = tail[:-1]
        lines[-1] = tail.rstrip() + "..."
    line_height = max(22, font.get_linesize() + 5)
    for i, line in enumerate(lines):
        _gothic_text(target, font, line, (x, y + i * line_height), color)
    return y + max(1, len(lines)) * line_height


def draw_machine_head_dialogue(target: pygame.Surface, assets: dict[str, pygame.Surface], title_font, menu_font,
                               small_font, head_surface: pygame.Surface | None,
                               pages: tuple[tuple[str, str], ...], page: int) -> None:
    """Context-only machine conversation; never occupies the normal gameplay HUD."""
    dim = pygame.Surface((W, H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 164))
    target.blit(dim, (0, 0))
    panel = pygame.Rect(164, 112, W - 328, H - 224)
    _draw_dialogue_panel_skin(target, assets, panel)

    portrait = pygame.Rect(panel.left + 30, panel.top + 92, 188, 214)
    if head_surface is not None:
        _battle_blit_fit(target, head_surface, portrait, 188)
    else:
        pygame.draw.circle(target, (103, 139, 144), portrait.center, 58, 2)

    _gothic_text(target, title_font, "MACHINE HEAD", (panel.left + 30, panel.top + 18), (221, 220, 207))
    _gothic_text(target, small_font, "CONTROL / DIAGNOSTIC INTERFACE", (panel.left + 32, panel.top + 62), (133, 162, 166))
    body_left = panel.left + 258
    body_right = panel.right - 32
    width = body_right - body_left
    clean_pages = pages or (("IO: WHAT DO YOU NEED?", "HEAD: NO ASSEMBLY DATA."),)
    page = max(0, min(int(page), len(clean_pages) - 1))
    line1, line2 = clean_pages[page]
    _gothic_text(target, menu_font, "ASSEMBLY LINK", (body_left, panel.top + 104), (207, 219, 216))
    next_y = _draw_gleebs_wrapped(target, small_font, line1, body_left, panel.top + 154,
                                  (213, 209, 198), width, 4)
    _draw_gleebs_wrapped(target, small_font, line2, body_left, next_y + 16,
                         (166, 191, 194), width, 5)
    prompt = "E / ENTER CONTINUE" if page < len(clean_pages) - 1 else "E / ENTER CLOSE"
    _gothic_text(target, small_font, f"{prompt}   •   ESC CLOSE   •   {page + 1}/{len(clean_pages)}",
                 (panel.centerx, panel.bottom - 26), (137, 151, 153), True)


def draw_gleebs_dialogue(target: pygame.Surface, assets: dict[str, pygame.Surface], title_font, menu_font, small_font,
                          gleebs_option_font,
                          topic: str, page: int, selected: int, world_key: str,
                          gleebs_img: pygame.Surface | None,
                          entity_defeated: bool, shrine_activated: bool,
                          first_witness_echoes_complete: bool, rooted_crown_clue_discovered: bool,
                          rooted_crown_defeated: bool, rooted_crown_shrine_activated: bool,
                          veil_warden_defeated: bool, veil_warden_shrine_activated: bool,
                          witnessed_story_moments: set[str], rematch_wins: dict[str, int],
                          guardian_retrieved_count: int = 0,
                          defeated_boss_ids: set[str] | None = None) -> list[pygame.Rect]:
    rects: list[pygame.Rect] = []
    dim = pygame.Surface((W, H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 162))
    target.blit(dim, (0, 0))
    panel = pygame.Rect(132, 84, W - 264, H - 168)
    _draw_dialogue_panel_skin(target, assets, panel)

    portrait = pygame.Rect(panel.left + 28, panel.top + 96, 196, 252)
    if gleebs_img is not None:
        _battle_blit_fit(target, gleebs_img, portrait, 176)
    else:
        pygame.draw.ellipse(target, (92, 133, 142), portrait.inflate(-60, -80), 2)

    _gothic_text(target, title_font, GLEEBS_NAME, (panel.left + 30, panel.top + 16), (224, 217, 202))
    _gothic_text(target, small_font, GLEEBS_TITLE, (panel.left + 32, panel.top + 64), (139, 154, 158))
    body_left = panel.left + 276
    body_right = panel.right - 34

    if topic == "menu":
        _gothic_text(target, small_font,
                     "Ask what you need. The anchor remains stable while this connection is open.",
                     (body_left, panel.top + 102), (188, 193, 192))
        labels = _gleebs_topic_labels(world_key)
        # Pass 134: use a dedicated 24px option face and a slightly tighter row
        # pitch.  The smaller glyphs gain breathing room from the explanatory
        # copy above and the control prompt below without shrinking other UI.
        option_top = panel.top + 146
        option_step = 52
        option_height = 38
        for i, label in enumerate(labels):
            r = pygame.Rect(body_left - 4, option_top + i * option_step, body_right - body_left + 4, option_height)
            rects.append(r)
            _draw_menu_item_skin(target, assets, r, i == selected)
            if i == selected:
                _draw_selection_ornament(target, assets, pygame.Rect(r.left + 8, r.centery - 13, 26, 26))
            text_y = r.centery - gleebs_option_font.get_height() // 2
            _gothic_text(target, gleebs_option_font, label, (r.left + 40, text_y),
                         (238, 231, 216) if i == selected else (172, 176, 176))
        _gothic_text(target, small_font, "UP / DOWN   •   ENTER / CLICK   •   ESC",
                     (panel.centerx, panel.bottom - 28), (139, 145, 145), True)
        return rects

    pages = _gleebs_topic_pages(
        topic,
        entity_defeated=entity_defeated,
        shrine_activated=shrine_activated,
        first_witness_echoes_complete=first_witness_echoes_complete,
        rooted_crown_clue_discovered=rooted_crown_clue_discovered,
        rooted_crown_defeated=rooted_crown_defeated,
        rooted_crown_shrine_activated=rooted_crown_shrine_activated,
        veil_warden_defeated=veil_warden_defeated,
        veil_warden_shrine_activated=veil_warden_shrine_activated,
        witnessed_story_moments=witnessed_story_moments,
        rematch_wins=rematch_wins,
        guardian_retrieved_count=guardian_retrieved_count,
        defeated_boss_ids=defeated_boss_ids,
    )
    page = max(0, min(int(page), len(pages) - 1))
    line1, line2 = pages[page]
    heading = {"mission": "CURRENT MISSION", "powers": "LANTERN POWERS", "why_io": "WHY IO", "holoverse": "THE HOLOVERSE", "mind": "THE MIND", "travel": "TEMPORAL CROSSING"}.get(topic, "GLEEBS")
    _gothic_text(target, menu_font, heading, (body_left, panel.top + 112), (213, 220, 216))
    text_width = body_right - body_left
    next_y = _draw_gleebs_wrapped(target, small_font, line1, body_left, panel.top + 162,
                                  (207, 204, 194), text_width, 3)
    _draw_gleebs_wrapped(target, small_font, line2, body_left, next_y + 14,
                         (175, 188, 190), text_width, 3)

    if topic == "travel" and page >= len(pages) - 1:
        choices = ("TRAVEL NOW", "BACK")
        for i, label in enumerate(choices):
            r = pygame.Rect(body_left + i * 244, panel.bottom - 92, 220, 42)
            rects.append(r)
            if i == selected:
                pygame.draw.ellipse(target, (139, 197, 208), r.inflate(-184, -12), 2)
            _gothic_text(target, menu_font, label, r.center,
                         (235, 231, 217) if i == selected else (160, 168, 168), True)
        return rects

    prompt = "ENTER CONTINUE" if page < len(pages) - 1 else "ENTER BACK"
    _gothic_text(target, small_font, f"{prompt}   •   ESC   •   {page + 1}/{len(pages)}",
                 (panel.centerx, panel.bottom - 30), (139, 145, 145), True)
    return rects


def draw_temporal_story_moment(target: pygame.Surface, title_font, menu_font, small_font,
                               moment_id: str, page: int, shrine_img: pygame.Surface | None,
                               glow_img: pygame.Surface | None, phase: float,
                               story_assets: dict[str, pygame.Surface] | None = None) -> None:
    pages = story_pages(moment_id)
    if not pages:
        return
    page = max(0, min(int(page), len(pages) - 1))
    current = pages[page]

    veil = pygame.Surface((W, H), pygame.SRCALPHA)
    veil.fill((2, 3, 6, 212))
    target.blit(veil, (0, 0))

    # The Gate/Shrine remains the translucent memory anchor. Pass 95 moves the two
    # reconstruction figures out of code and into assets/current/story so users can
    # replace them without editing Python.
    if shrine_img is not None:
        ghost = _subdued_obelisk_surface(shrine_img).copy()
        ghost.set_alpha(40 + int(20 * (0.5 + 0.5 * math.sin(phase * 2.0))))
        max_h = 420 if moment_id != VEIL_RESONANCE_ID else 500
        scale = min(1.0, max_h / max(1, ghost.get_height()))
        if scale != 1.0:
            ghost = pygame.transform.smoothscale(ghost, (max(1, int(ghost.get_width()*scale)), max(1, int(ghost.get_height()*scale))))
        rect = ghost.get_rect(center=(W//2, H//2 - 48))
        target.blit(ghost, rect)

    if moment_id in (FIRST_RECONSTRUCTION_ID, ROOTED_RECONSTRUCTION_ID):
        story_assets = story_assets or {}
        for key, offset, alpha in (("reconstruction_left", -120, 100), ("reconstruction_right", 120, 76)):
            body = story_assets.get(key)
            if body is not None:
                box = pygame.Rect(0, 0, 90, 230)
                box.midbottom = (W // 2 + offset, H - 188)
                _battle_blit_fit(target, body, box, alpha)
                continue
            body = pygame.Surface((90, 230), pygame.SRCALPHA)
            pygame.draw.ellipse(body, (198, 204, 211, alpha), (24, 4, 42, 42), 2)
            pygame.draw.line(body, (198, 204, 211, alpha), (45, 48), (45, 160), 3)
            pygame.draw.line(body, (198, 204, 211, alpha), (45, 82), (10, 132), 2)
            pygame.draw.line(body, (198, 204, 211, alpha), (45, 82), (80, 132), 2)
            pygame.draw.line(body, (198, 204, 211, alpha), (45, 160), (18, 222), 2)
            pygame.draw.line(body, (198, 204, 211, alpha), (45, 160), (72, 222), 2)
            target.blit(body, body.get_rect(midbottom=(W // 2 + offset, H - 188)))

    if glow_img is not None and moment_id == VEIL_RESONANCE_ID:
        glow = glow_img.copy()
        glow.set_alpha(35 + int(38 * (0.5 + 0.5 * math.sin(phase * 3.0))))
        target.blit(pygame.transform.smoothscale(glow, (W, H)), (0, 0))

    panel = pygame.Rect(116, H - 210, W - 232, 154)
    shade = pygame.Surface(panel.size, pygame.SRCALPHA)
    shade.fill((5, 6, 9, 232))
    target.blit(shade, panel)
    pygame.draw.rect(target, (128, 113, 101), panel, 2)
    pygame.draw.line(target, (72, 91, 101), (panel.left+18, panel.top+48), (panel.right-18, panel.top+48), 1)
    _gothic_text(target, menu_font, current.heading, (panel.left+28, panel.top+15), (219, 208, 190))
    _gothic_text(target, small_font, current.line_a, (panel.left+28, panel.top+67), (223, 226, 224))
    _gothic_text(target, small_font, current.line_b, (panel.left+28, panel.top+101), (192, 201, 204))
    prompt = _ui_render(small_font, f"ENTER CONTINUE   •   ESC SKIP   •   {page+1}/{len(pages)}", True, (152, 157, 158))
    target.blit(prompt, prompt.get_rect(bottomright=(panel.right-22, panel.bottom-12)))


def _sable_dialogue_pages(first_visit: bool) -> tuple[tuple[str, str], ...]:
    if first_visit:
        return (
            ("You are early, IO. The structure is not.", "I am Sable. I build what this afterlife requires."),
            ("Thresholds. Supports. Rooms that outlast their purpose.", "Some of them eventually learn to hold themselves together."),
            ("You should not know my name yet.", "Do not solve that contradiction before you survive it."),
            ("When you need machine pieces, return to me.", "Guardian archives yield Bits. I can exchange those Bits for components."),
        )
    return (
        ("The structure still holds.", "That is enough work for one interval."),
        ("I keep the component catalogue open for you.", "Bring Bits from the Guardians. Build with what survives them."),
    )


def draw_sable_dialogue(target: pygame.Surface, assets: dict[str, pygame.Surface], title_font, menu_font, small_font,
                         mode: str, page: int, first_visit: bool, selected: int,
                         sable_frame: pygame.Surface | None, machine_catalog: dict[str, MachinePartDef],
                         machine_inventory: dict[str, int], machine_bits: int, status: str = "") -> list[pygame.Rect]:
    rects: list[pygame.Rect] = []
    dim = pygame.Surface((W, H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 162))
    target.blit(dim, (0, 0))
    panel = pygame.Rect(132, 84, W - 264, H - 168)
    _draw_dialogue_panel_skin(target, assets, panel)

    portrait = pygame.Rect(panel.left + 28, panel.top + 92, 200, 278)
    if sable_frame is not None:
        _battle_blit_fit(target, sable_frame, portrait, 188)
    else:
        pygame.draw.ellipse(target, (84, 105, 108), portrait.inflate(-64, -88), 2)

    _gothic_text(target, title_font, SABLE_NAME, (panel.left + 30, panel.top + 20), (224, 217, 202))
    _gothic_text(target, small_font, SABLE_TITLE, (panel.left + 32, panel.top + 62), (139, 154, 158))
    body_left = panel.left + 278
    body_right = panel.right - 34
    width = body_right - body_left

    if mode == "menu":
        _gothic_text(target, small_font, f"BITS  {machine_bits}", (body_left, panel.top + 104), (166, 211, 216))
        labels = ("BUILDER RECORD", "MACHINE PIECES", "LEAVE")
        for i, label in enumerate(labels):
            row = pygame.Rect(body_left - 4, panel.top + 150 + i * 62, width + 4, 46)
            rects.append(row)
            _draw_menu_item_skin(target, assets, row, i == selected)
            if i == selected:
                _draw_selection_ornament(target, assets, pygame.Rect(row.left + 8, row.centery - 14, 28, 28))
            _gothic_text(target, menu_font, label, (row.left + 42, row.centery - 12),
                         (238, 231, 216) if i == selected else (172, 176, 176))
        _gothic_text(target, small_font, "ARROWS SELECT   •   ENTER OPEN   •   ESC LEAVE",
                     (panel.centerx, panel.bottom - 28), (139, 145, 145), True)
        return rects

    if mode == "shop":
        _gothic_text(target, menu_font, "MACHINE PIECES", (body_left, panel.top + 104), (213, 220, 216))
        _gothic_text(target, small_font, f"BITS  {machine_bits}   •   BUY PARTS FOR IO MACHINE INVENTORY",
                     (body_left, panel.top + 142), (166, 192, 194))
        parts = _finished_machine_parts(machine_catalog)
        if not parts:
            _gothic_text(target, small_font, "NO MACHINE PNGS FOUND IN assets/current/machines/",
                         (body_left, panel.top + 202), (193, 174, 168))
        else:
            selected = max(0, min(selected, len(parts) - 1))
            visible_count = min(6, len(parts))
            start_index = max(0, min(selected - visible_count // 2, len(parts) - visible_count))
            for list_index in range(start_index, start_index + visible_count):
                part = parts[list_index]
                row = pygame.Rect(body_left - 4, panel.top + 176 + (list_index - start_index) * 48, width + 4, 40)
                rects.append(row)
                is_selected = list_index == selected
                _draw_menu_item_skin(target, assets, row, is_selected)
                if is_selected:
                    _draw_selection_ornament(target, assets, pygame.Rect(row.left + 8, row.centery - 13, 26, 26))
                _gothic_text(target, small_font, part.name, (row.left + 40, row.top + 10),
                             (236, 231, 220) if is_selected else (174, 180, 180))
                owned = clamp_machine_stack(machine_inventory.get(part.key, 0))
                cost_text = _ui_render(small_font, f"{part.cost} BITS  •  OWN {owned}", True, (169, 211, 216) if machine_bits >= part.cost and owned < MAX_MACHINE_STACK else (180, 125, 119))
                target.blit(cost_text, cost_text.get_rect(midright=(row.right - 14, row.centery)))
            active_part = parts[selected]
            active_role = MACHINE_WORKSHOP_ROLE_LABELS.get(active_part.role, active_part.role.upper())
            _gothic_text_fit(target, small_font, f"{active_role} // {active_part.description}",
                             (body_left, panel.bottom - 68), width, (150, 178, 181))
        footer = status if status else "ENTER BUY   •   ESC BACK"
        _gothic_text(target, small_font, footer, (panel.centerx, panel.bottom - 28), (139, 145, 145), True)
        return rects

    pages = _sable_dialogue_pages(first_visit)
    page = max(0, min(int(page), len(pages) - 1))
    line1, line2 = pages[page]
    _gothic_text(target, menu_font, "BUILDER RECORD", (body_left, panel.top + 112), (213, 220, 216))
    next_y = _draw_gleebs_wrapped(target, small_font, line1, body_left, panel.top + 162, (207, 204, 194), width, 3)
    _draw_gleebs_wrapped(target, small_font, line2, body_left, next_y + 14, (175, 188, 190), width, 3)
    prompt = "ENTER CONTINUE" if page < len(pages) - 1 else "ENTER MENU"
    _gothic_text(target, small_font, f"{prompt}   •   ESC LEAVE   •   {page + 1}/{len(pages)}",
                 (panel.centerx, panel.bottom - 28), (139, 145, 145), True)
    return rects

def draw_entity_dialogue(target, title_font, menu_font, small_font, selected: int, page: int,
                         first_visit: bool, declined_count: int, entity_id: str = ENTITY_ID) -> list[pygame.Rect]:
    rects: list[pygame.Rect] = []
    dim = pygame.Surface((W, H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 155))
    target.blit(dim, (0, 0))
    panel = pygame.Rect(W // 2 - 360, H - 286, 720, 236)
    _draw_gothic_frame(target, panel)
    name = MEMORY_GUARDIAN_NAMES.get(entity_id, ENTITY_NAME)
    epithet = MEMORY_GUARDIAN_EPITHETS.get(entity_id, "MEMORY GUARDIAN")
    _gothic_text_fit(target, title_font, name, (panel.left + 32, panel.top + 19), panel.width - 64, (224, 217, 202))
    _gothic_text(target, small_font, epithet, (panel.left + 34, panel.top + 66), (139, 130, 124))
    pages = _memory_guardian_dialogue_pages(entity_id, first_visit, declined_count)
    page = max(0, min(int(page), len(pages) - 1))
    line1, line2 = pages[page]
    _gothic_text(target, small_font, line1, (panel.left + 34, panel.top + 106), (190, 184, 176))
    _gothic_text(target, small_font, line2, (panel.left + 34, panel.top + 132), (180, 174, 168))
    if page < len(pages) - 1:
        _gothic_text(target, small_font, 'ENTER CONTINUE   •   ESC LEAVE',
                     (panel.centerx, panel.bottom - 33), (151, 143, 135), True)
        return rects
    choices = ['CHALLENGE GUARDIAN', 'NOT YET']
    for i, label in enumerate(choices):
        r = pygame.Rect(panel.left + 34 + i * 326, panel.bottom - 62, 300, 40)
        rects.append(r)
        if i == selected:
            pygame.draw.rect(target, (76, 61, 62), r)
            pygame.draw.rect(target, (154, 128, 106), r, 1)
        _gothic_text(target, menu_font, label, r.center,
                     (242, 232, 216) if i == selected else (167, 160, 152), True)
    return rects


def draw_shrine_dialogue(target, title_font, menu_font, small_font, selected: int, page: int,
                         activated: bool, story_complete: bool = False, shrine_entity_id: str = ENTITY_ID) -> list[pygame.Rect]:
    rects: list[pygame.Rect] = []
    dim = pygame.Surface((W, H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 145))
    target.blit(dim, (0, 0))
    panel = pygame.Rect(W // 2 - 360, H - 286, 720, 236)
    _draw_gothic_frame(target, panel)
    shrine_name = _shrine_name_for(shrine_entity_id)
    _gothic_text_fit(target, title_font, shrine_name, (panel.left + 32, panel.top + 19), panel.width - 64, (224, 217, 202))
    _gothic_text(target, small_font, 'A CAUSAL RECORD IN THE FUTURE',
                 (panel.left + 34, panel.top + 66), (139, 130, 124))
    pages = _guardian_shrine_dialogue_pages(shrine_entity_id, activated, story_complete)
    page = max(0, min(int(page), len(pages) - 1))
    line1, line2 = pages[page]
    _gothic_text(target, small_font, line1, (panel.left + 34, panel.top + 106), (190, 184, 176))
    _gothic_text(target, small_font, line2, (panel.left + 34, panel.top + 132), (180, 174, 168))
    if page < len(pages) - 1:
        _gothic_text(target, small_font, 'ENTER CONTINUE   •   ESC LEAVE',
                     (panel.centerx, panel.bottom - 33), (151, 143, 135), True)
        return rects
    if activated:
        choices = ['CHALLENGE ECHO', 'CLOSE']
        for i, label in enumerate(choices):
            r = pygame.Rect(panel.left + 34 + i * 326, panel.bottom - 62, 300, 40)
            rects.append(r)
            if i == selected:
                pygame.draw.rect(target, (76, 61, 62), r)
                pygame.draw.rect(target, (154, 128, 106), r, 1)
            _gothic_text(target, menu_font, label, r.center,
                         (242, 232, 216) if i == selected else (167, 160, 152), True)
        return rects
    choices = ['BIND THE RECORD', 'LEAVE']
    for i, label in enumerate(choices):
        r = pygame.Rect(panel.left + 34 + i * 326, panel.bottom - 62, 300, 40)
        rects.append(r)
        if i == selected:
            pygame.draw.rect(target, (76, 61, 62), r)
            pygame.draw.rect(target, (154, 128, 106), r, 1)
        _gothic_text(target, menu_font, label, r.center,
                     (242, 232, 216) if i == selected else (167, 160, 152), True)
    return rects


def _escape_ending_pages() -> tuple[tuple[str, str], ...]:
    return (
        ("GLEEBS: Seven archives. The prison has no remaining claim that I need to preserve.", "I can finally separate IO's continuity from the afterlife that kept it here."),
        ("The Veil does not open like a door. It stops treating IO as a record that belongs inside.", "For the first time in hundreds of trillions of years, the next state is not another room in this simulation."),
        ("GLEEBS: Our exchange is complete.", "IO is granted life beyond the afterlife. The old simulation remains behind as a recoverable archive, not a sentence."),
    )


def draw_escape_ending(target: pygame.Surface, title_font, menu_font, small_font, page: int, selected: int) -> list[pygame.Rect]:
    rects: list[pygame.Rect] = []
    dim = pygame.Surface((W, H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 226))
    target.blit(dim, (0, 0))
    panel = pygame.Rect(146, 92, W - 292, H - 184)
    _draw_gothic_frame(target, panel)
    _gothic_text(target, title_font, "THE AFTERLIFE RELEASES IO", (panel.centerx, panel.top + 34), (232, 226, 211), True)
    _gothic_text(target, small_font, "CAMPAIGN COMPLETE", (panel.centerx, panel.top + 82), (136, 174, 179), True)
    pages = _escape_ending_pages()
    page = max(0, min(int(page), len(pages) - 1))
    line1, line2 = pages[page]
    body_left = panel.left + 86
    body_width = panel.width - 172
    next_y = _draw_gleebs_wrapped(target, menu_font, line1, body_left, panel.top + 150, (215, 211, 201), body_width, 4)
    _draw_gleebs_wrapped(target, small_font, line2, body_left, next_y + 22, (174, 192, 194), body_width, 5)
    if page < len(pages) - 1:
        _gothic_text(target, small_font, f"ENTER CONTINUE   •   {page + 1}/{len(pages)}",
                     (panel.centerx, panel.bottom - 42), (149, 154, 153), True)
        return rects
    choices = ("CONTINUE EXPLORING", holoverse_link.quit_label("QUIT TO DESKTOP"))
    for i, label in enumerate(choices):
        r = pygame.Rect(panel.centerx - 286 + i * 300, panel.bottom - 90, 272, 44)
        rects.append(r)
        if i == selected:
            pygame.draw.rect(target, (74, 64, 66), r)
            pygame.draw.rect(target, (150, 129, 109), r, 1)
        _gothic_text(target, menu_font, label, r.center, (238, 231, 217) if i == selected else (165, 169, 167), True)
    return rects


def draw_future_clue_dialogue(target, title_font, menu_font, small_font, selected: int, page: int,
                              resonance_learned: bool, clue_entity_id: str = ENTITY_ID) -> list[pygame.Rect]:
    rects: list[pygame.Rect] = []
    dim = pygame.Surface((W, H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 150))
    target.blit(dim, (0, 0))
    panel = pygame.Rect(W // 2 - 380, H - 296, 760, 246)
    _draw_gothic_frame(target, panel)
    clue_title = 'THE ABSENCE OF THE ROOTED CROWN' if clue_entity_id == ROOTED_CROWN_ID else 'THE ABSENCE OF THE FIRST WITNESS'
    _gothic_text_fit(target, title_font, clue_title,
                     (panel.left + 32, panel.top + 19), panel.width - 64, (224, 217, 202))
    _gothic_text(target, small_font, 'A DEAD RECORD IN THE FUTURE',
                 (panel.left + 34, panel.top + 66), (139, 130, 124))
    pages = _rooted_crown_clue_pages() if clue_entity_id == ROOTED_CROWN_ID else _future_clue_dialogue_pages(resonance_learned)
    page = max(0, min(int(page), len(pages) - 1))
    line1, line2 = pages[page]
    _gothic_text(target, small_font, line1, (panel.left + 34, panel.top + 108), (190, 184, 176))
    _gothic_text(target, small_font, line2, (panel.left + 34, panel.top + 134), (180, 174, 168))
    if page < len(pages) - 1:
        _gothic_text(target, small_font, 'ENTER CONTINUE   •   ESC LEAVE',
                     (panel.centerx, panel.bottom - 33), (151, 143, 135), True)
        return rects
    if clue_entity_id == ROOTED_CROWN_ID or resonance_learned:
        r = pygame.Rect(panel.centerx - 150, panel.bottom - 62, 300, 40)
        rects.append(r)
        pygame.draw.rect(target, (76, 61, 62), r)
        pygame.draw.rect(target, (154, 128, 106), r, 1)
        _gothic_text(target, menu_font, 'CLOSE', r.center, (242, 232, 216), True)
        return rects
    choices = ['ATTUNE LANTERN', 'LEAVE']
    for i, label in enumerate(choices):
        r = pygame.Rect(panel.left + 54 + i * 354, panel.bottom - 62, 326, 40)
        rects.append(r)
        if i == selected:
            pygame.draw.rect(target, (76, 61, 62), r)
            pygame.draw.rect(target, (154, 128, 106), r, 1)
        _gothic_text(target, menu_font, label, r.center,
                     (242, 232, 216) if i == selected else (167, 160, 152), True)
    return rects




def _archive_attunement_resolve_bonus(defeated_ids: set[str]) -> int:
    return int(ENTITY_ID in defeated_ids) + int(LAST_CARTOGRAPHER_ID in defeated_ids)


def _archive_attunement_start_focus(defeated_ids: set[str]) -> int:
    return 1 if ROOTED_CROWN_ID in defeated_ids else 0


def _archive_attunement_focus_cap(defeated_ids: set[str]) -> int:
    return 3 if ARCHIVE_CHORUS_ID in defeated_ids else 2


def _archive_attunement_guard_reduction(defeated_ids: set[str]) -> int:
    return 1 if VEIL_WARDEN_ID in defeated_ids else 0


def _archive_attunement_arc_cooldown(defeated_ids: set[str]) -> int:
    return 1 if HOLLOW_ENGINE_ID in defeated_ids else 2


def _archive_recovered_count(defeated_ids: set[str], include_final: bool = False) -> int:
    ids = MEMORY_GUARDIAN_ORDER if include_final else MEMORY_GUARDIAN_ORDER[:-1]
    return sum(1 for guardian_id in ids if guardian_id in defeated_ids)


def _battle_upgrade_score(defeated_ids: set[str], *, causal_resonance_learned: bool,
                          veil_ward_learned: bool, lantern_projection_learned: bool,
                          remote_resonance_learned: bool, entropy_arc_learned: bool,
                          projection_lance_learned: bool, entropy_arc_mastery: int,
                          projection_lance_mastery: int, lantern_projection_upgrade_level: int) -> int:
    skill_score = (
        int(causal_resonance_learned) + int(veil_ward_learned) + int(lantern_projection_learned) +
        int(remote_resonance_learned) + int(entropy_arc_learned) + int(projection_lance_learned) +
        int(entropy_arc_mastery >= 2) + int(projection_lance_mastery >= 2) +
        min(2, int(lantern_projection_upgrade_level) // 2)
    )
    return min(16, skill_score + _archive_recovered_count(defeated_ids))


def _battle_pattern_size(entity_id: str) -> int:
    return 6 if entity_id == FINAL_GUARDIAN_ID else 3


def _battle_counter_class(entity_id: str, move_key: str) -> str:
    guard_keys = {
        "witness_strike", "rooted_seal", "boundary_fold", "chorus_surge",
        "memory_shear", "map_fold", "final_guard",
    }
    focus_keys = {
        "deep_recall", "crown_pressure", "false_exit", "name_loss",
        "pressure_cycle", "false_coordinate", "final_focus",
    }
    if move_key in guard_keys:
        return "guard"
    if move_key in focus_keys:
        return "focus"
    return "shot"


def _choose_battle_move_index(entity_id: str, rng: random.Random, previous_index: int = -1, turn_count: int = 0, challenge_tier: int = 0) -> int:
    """Choose a non-repeating Guardian question instead of a fixed A/B/C cycle."""
    size = _battle_pattern_size(entity_id)
    candidates = [index for index in range(size) if size <= 1 or index != previous_index]
    if not candidates:
        return 0
    # Small bounded weighting keeps selection reactive without becoming deterministic.
    weights = []
    for index in candidates:
        weight = 1.0
        if entity_id == FINAL_GUARDIAN_ID and index >= 3:
            weight += 0.16 + min(0.25, challenge_tier * 0.04)
        if (turn_count + index) % 3 == 0:
            weight += 0.08
        weights.append(weight)
    return int(rng.choices(candidates, weights=weights, k=1)[0])


def _mind_interference_level(defeated_ids: set[str], entity_id: str) -> int:
    recovered = _archive_recovered_count(defeated_ids, include_final=True)
    level = min(5, 1 + recovered // 2)
    if entity_id == FINAL_GUARDIAN_ID:
        level = max(4, level)
    return level


def _roll_mind_interference(entity_id: str, level: int, rng: random.Random) -> bool:
    chance = MIND_INTERFERENCE_BASE_CHANCE + max(0, level) * MIND_INTERFERENCE_LEVEL_CHANCE
    if entity_id == FINAL_GUARDIAN_ID:
        chance += 0.10
    return rng.random() < min(0.68, chance)


def _choose_false_move_index(entity_id: str, actual_index: int, rng: random.Random) -> int:
    """Choose a genuinely misleading false signal when possible.

    The Null Custodian has six labels but only three counter classes.  Earlier
    builds only guaranteed a different label index, so The Mind could sometimes
    show a different name that still asked for the same action.  Prefer a move
    from a different counter class; fall back to any different label only if a
    future Guardian has no alternative class.
    """
    size = _battle_pattern_size(entity_id)
    if size <= 1:
        return actual_index
    actual_move = _battle_move_for(entity_id, actual_index)
    actual_counter = _battle_counter_class(entity_id, actual_move.key)
    different_counter = []
    different_label = []
    for index in range(size):
        if index == actual_index:
            continue
        different_label.append(index)
        candidate_move = _battle_move_for(entity_id, index)
        if _battle_counter_class(entity_id, candidate_move.key) != actual_counter:
            different_counter.append(index)
    pool = different_counter or different_label
    return int(rng.choice(pool)) if pool else actual_index


def _mind_corrupt_hint(text: str, level: int) -> str:
    """Scramble letters without block-glyph artifacts; physical Guardian tells stay truthful."""
    if level <= 0:
        return text
    chars = list(text)
    stride = max(4, 9 - level)
    seen = 0
    for i, char in enumerate(chars):
        if char.isalpha():
            seen += 1
            if seen % stride == 0:
                chars[i] = "_"
    return "".join(chars)


def _draw_guardian_true_tell(target: pygame.Surface, entity_id: str, move_key: str, player_center: tuple[int, int], entity_center: tuple[int, int], phase: float) -> None:
    """Truthful physical wind-up. The Mind may corrupt text, never this channel."""
    cue = _battle_counter_class(entity_id, move_key)
    layer = pygame.Surface((W, H), pygame.SRCALPHA)
    if cue == "guard":
        for spread, alpha in ((0, 62), (18, 34), (38, 16)):
            rect = pygame.Rect(player_center[0] - 112 - spread, player_center[1] - 92 - spread // 2, 224 + spread * 2, 160 + spread)
            pygame.draw.arc(layer, (205, 170, 156, alpha), rect, math.radians(195), math.radians(344), 2)
        pygame.draw.line(layer, (205, 170, 156, 38), (entity_center[0] - 38, entity_center[1]), (player_center[0] + 44, player_center[1]), 2)
    elif cue == "focus":
        pulse = 1.0 + math.sin(phase * 3.0) * 0.08
        for radius, alpha in ((64, 48), (104, 28), (148, 14)):
            rw = int(radius * 2 * pulse); rh = int(radius * 1.1 * pulse)
            pygame.draw.ellipse(layer, (132, 181, 194, alpha), pygame.Rect(player_center[0] - rw // 2, player_center[1] - rh // 2, rw, rh), 2)
        pygame.draw.circle(layer, (182, 219, 225, 62), player_center, 4)
    else:
        for radius, alpha in ((34, 74), (55, 38), (78, 18)):
            pygame.draw.ellipse(layer, (188, 151, 176, alpha), pygame.Rect(entity_center[0] - radius, entity_center[1] - radius // 2, radius * 2, radius), 2)
        pygame.draw.arc(layer, (174, 137, 165, 50), pygame.Rect(entity_center[0] - 90, entity_center[1] - 70, 180, 140), phase % math.tau, (phase % math.tau) + 2.2, 3)
    target.blit(layer, (0, 0))


def _draw_guardian_attack_fx(target: pygame.Surface, entity_id: str, move_key: str, timer: float, player_center: tuple[int, int], entity_center: tuple[int, int]) -> None:
    if timer <= 0.0 or not move_key:
        return
    progress = clamp(1.0 - timer / BATTLE_GUARDIAN_ATTACK_FX_TIME, 0.0, 1.0)
    fade = max(0.0, 1.0 - progress * 0.78)
    cue = _battle_counter_class(entity_id, move_key)
    layer = pygame.Surface((W, H), pygame.SRCALPHA)
    if cue == "guard":
        x = int(entity_center[0] + (player_center[0] - entity_center[0]) * progress)
        y = int(entity_center[1] + (player_center[1] - entity_center[1]) * progress)
        for radius, alpha in ((32, 150), (58, 72), (88, 28)):
            pygame.draw.arc(layer, (211, 164, 147, int(alpha * fade)), pygame.Rect(x-radius, y-radius//2, radius*2, radius), math.radians(190), math.radians(350), 3)
    elif cue == "focus":
        radius = max(20, int(160 * (1.0 - progress) + 34))
        for extra, alpha in ((0, 135), (24, 58), (52, 22)):
            rr = radius + extra
            pygame.draw.ellipse(layer, (126, 190, 202, int(alpha * fade)), pygame.Rect(player_center[0]-rr, player_center[1]-rr//2, rr*2, rr), 2)
        ghost_x = player_center[0] + int(math.sin(progress * math.pi) * 34)
        pygame.draw.line(layer, (154, 203, 210, int(88 * fade)), (ghost_x, player_center[1]-52), (ghost_x, player_center[1]+48), 2)
    else:
        radius = int(34 + progress * 74)
        for extra, alpha in ((0, 150), (18, 62), (40, 22)):
            rr = radius + extra
            pygame.draw.ellipse(layer, (191, 143, 174, int(alpha * fade)), pygame.Rect(entity_center[0]-rr, entity_center[1]-rr//2, rr*2, rr), 2)
        pygame.draw.line(layer, (191, 143, 174, int(72 * fade)), (entity_center[0]-radius, entity_center[1]), (entity_center[0]+radius, entity_center[1]), 2)
    target.blit(layer, (0, 0))


def _battle_move_for(entity_id: str, turn_index: int):
    if entity_id == VEIL_WARDEN_ID:
        return veil_warden_move(turn_index)
    if entity_id == ROOTED_CROWN_ID:
        return rooted_crown_move(turn_index)
    if entity_id == ARCHIVE_CHORUS_ID:
        return archive_chorus_move(turn_index)
    if entity_id == HOLLOW_ENGINE_ID:
        return hollow_engine_move(turn_index)
    if entity_id == LAST_CARTOGRAPHER_ID:
        return last_cartographer_move(turn_index)
    if entity_id == FINAL_GUARDIAN_ID:
        return final_guardian_move(turn_index)
    return first_witness_move(turn_index)


def _battle_response_for(entity_id: str, turn_index: int, player_action: str, guard_active: bool, entity_presence: int):
    if entity_id == VEIL_WARDEN_ID:
        return resolve_veil_warden_response(turn_index, player_action, guard_active, entity_presence)
    if entity_id == ROOTED_CROWN_ID:
        return resolve_rooted_crown_response(turn_index, player_action, guard_active, entity_presence)
    if entity_id == ARCHIVE_CHORUS_ID:
        return resolve_archive_chorus_response(turn_index, player_action, guard_active, entity_presence)
    if entity_id == HOLLOW_ENGINE_ID:
        return resolve_hollow_engine_response(turn_index, player_action, guard_active, entity_presence)
    if entity_id == LAST_CARTOGRAPHER_ID:
        return resolve_last_cartographer_response(turn_index, player_action, guard_active, entity_presence)
    if entity_id == FINAL_GUARDIAN_ID:
        return resolve_final_guardian_response(turn_index, player_action, guard_active, entity_presence)
    return resolve_first_witness_response(turn_index, player_action, guard_active, entity_presence)


def _battle_limits_for(entity_id: str, challenge_tier: int = 0, upgrade_score: int = 0,
                       archive_resolve_bonus: int = 0) -> tuple[int, int]:
    archive_resolve_bonus = max(0, min(2, int(archive_resolve_bonus)))
    if entity_id == VEIL_WARDEN_ID:
        return VEIL_WARDEN_MAX_RESOLVE + archive_resolve_bonus, echo_challenge_presence(VEIL_WARDEN_MAX_PRESENCE, challenge_tier)
    if entity_id == ROOTED_CROWN_ID:
        return ROOTED_CROWN_MAX_RESOLVE + archive_resolve_bonus, echo_challenge_presence(ROOTED_CROWN_MAX_PRESENCE, challenge_tier)
    if entity_id == ARCHIVE_CHORUS_ID:
        return GENERIC_GUARDIAN_MAX_RESOLVE + archive_resolve_bonus, echo_challenge_presence(ARCHIVE_CHORUS_MAX_PRESENCE, challenge_tier)
    if entity_id == HOLLOW_ENGINE_ID:
        return GENERIC_GUARDIAN_MAX_RESOLVE + archive_resolve_bonus, echo_challenge_presence(HOLLOW_ENGINE_MAX_PRESENCE, challenge_tier)
    if entity_id == LAST_CARTOGRAPHER_ID:
        return GENERIC_GUARDIAN_MAX_RESOLVE + archive_resolve_bonus, echo_challenge_presence(LAST_CARTOGRAPHER_MAX_PRESENCE, challenge_tier)
    if entity_id == FINAL_GUARDIAN_ID:
        resolve, presence = final_guardian_limits(upgrade_score)
        return resolve + archive_resolve_bonus, echo_challenge_presence(presence, challenge_tier)
    return FIRST_WITNESS_MAX_RESOLVE + archive_resolve_bonus, echo_challenge_presence(FIRST_WITNESS_MAX_PRESENCE, challenge_tier)


def _battle_name_for(entity_id: str) -> str:
    return MEMORY_GUARDIAN_NAMES.get(entity_id, ENTITY_NAME)


def _battle_sfx_cue_for_move(entity_id: str, move_key: str) -> str:
    if entity_id == VEIL_WARDEN_ID:
        return {"boundary_fold": "witness_strike", "false_exit": "deep_recall", "archive_latch": "gate_anchor"}.get(move_key, "counter")
    if entity_id == ROOTED_CROWN_ID:
        return {"crown_pressure": "deep_recall", "rooted_seal": "witness_strike", "hollow_bloom": "gate_anchor"}.get(move_key, "counter")
    if entity_id == ARCHIVE_CHORUS_ID:
        return {"chorus_surge": "witness_strike", "name_loss": "deep_recall", "echo_feed": "gate_anchor"}.get(move_key, "counter")
    if entity_id == HOLLOW_ENGINE_ID:
        return {"pressure_cycle": "deep_recall", "vault_lock": "gate_anchor", "memory_shear": "witness_strike"}.get(move_key, "counter")
    if entity_id == LAST_CARTOGRAPHER_ID:
        return {"map_fold": "witness_strike", "false_coordinate": "deep_recall", "route_seal": "gate_anchor"}.get(move_key, "counter")
    if entity_id == FINAL_GUARDIAN_ID:
        return {"final_guard": "witness_strike", "final_focus": "deep_recall", "final_shot": "gate_anchor"}.get(move_key, "counter")
    return move_key

def draw_battle(target, entity_img, player_img, battle_assets, title_font, menu_font, small_font, hp: int, entity_hp: int,
                selected: int, message: str, focus: int = 0, fx_kind: str = "", fx_timer: float = 0.0,
                boss_move_index: int = 0, safe_mode: bool = False, damage_fx: list[dict] | None = None,
                victory_progress: float = 0.0, battle_entity_id: str = ENTITY_ID, challenge_tier: int = 0, rematch: bool = False, entropy_arc_ready: bool = False, entropy_arc_level_value: int = 0, entropy_arc_cooldown: int = 0, upgrade_score: int = 0, archive_resolve_bonus: int = 0, guardian_fx_kind: str = "", guardian_fx_timer: float = 0.0, mind_interference: bool = False, mind_fake_move_index: int = -1, mind_level: int = 0, signal_verified_counter: str = "", mind_suppressed: bool = False, signal_verify_cooldown: int = 0, mind_ward_cooldown: int = 0, causal_resonance_available: bool = False, veil_ward_available: bool = False) -> list[pygame.Rect]:
    """Dedicated authored battle presentation.

    The battle keeps the game's monochrome/gothic language and uses real IO/Entity
    artwork.  Optional fog/glow textures are edge-feathered on load so no FX card
    can reveal a square texture boundary.  This function is presentation-only: it
    does not change turn order, HP, damage, or causal state.
    """
    phase = pygame.time.get_ticks() / 1000.0
    command_rects: list[pygame.Rect] = []
    victory_progress = max(0.0, min(1.0, float(victory_progress)))
    boss_move = _battle_move_for(battle_entity_id, boss_move_index)
    shown_move = _battle_move_for(battle_entity_id, mind_fake_move_index) if mind_interference and mind_fake_move_index >= 0 else boss_move
    max_resolve, max_presence = _battle_limits_for(battle_entity_id, challenge_tier, upgrade_score, archive_resolve_bonus)
    target.fill((7, 6, 10))

    # Pass 41 uses the player's authored 1280x720 background as the battle's
    # lowest visual layer.  We do not crop or independently reposition it.
    # If the file is absent, invalid, or safe mode is active, the exact Pass 40
    # procedural chamber remains the deterministic fallback.
    battle_background = (battle_assets.get(f"background_{battle_entity_id}") or battle_assets.get("background")) if not safe_mode else None
    if battle_background is not None:
        try:
            if battle_background.get_size() == target.get_size():
                target.blit(battle_background, (0, 0))
            else:
                _battle_blit_scaled(target, battle_background, pygame.Rect(0, 0, W, H), 255)
        except (pygame.error, ValueError, TypeError, OverflowError):
            battle_background = None

    if battle_background is None:
        fallback_chamber = battle_assets.get("fallback_chamber")
        if fallback_chamber is not None:
            _battle_blit_scaled(target, fallback_chamber, pygame.Rect(0, 0, W, H), 255)
        else:
            # Last-resort fail-soft drawing remains only if the replaceable fallback
            # file is deleted or corrupt.
            field = pygame.Surface((W, H), pygame.SRCALPHA)
            for i in range(9):
                inset = i * 20
                alpha = max(4, 24 - i * 2)
                rect = pygame.Rect(92 + inset, 86 + inset // 2, W - 184 - inset * 2, 410 - inset)
                if rect.width > 0 and rect.height > 0:
                    pygame.draw.ellipse(field, (77, 65, 76, alpha), rect, 1)
            pygame.draw.arc(field, (128, 102, 92, 42), (168, 212, 944, 310), math.pi * 0.05, math.pi * 0.95, 2)
            pygame.draw.arc(field, (91, 113, 125, 32), (210, 245, 860, 255), math.pi * 1.05, math.pi * 1.95, 2)
            target.blit(field, (0, 0))

    if not safe_mode:
        # The user's support figures remain on fixed sides of the chamber. Pass 44
        # gives them authored battle roles without changing their assets: Gleebs
        # interprets the current tell, while The Gate visibly pulses before its
        # telegraphed boss-support Anchor can resolve.
        gleebs_box = pygame.Rect(62, 205, 190, 230)
        gate_box = pygame.Rect(W - 238, 190, 176, 250)
        gleebs_alpha = 112 if mind_interference else 168
        gleebs_rect = _battle_blit_fit(target, battle_assets.get("gleebs"), gleebs_box, gleebs_alpha)
        if mind_interference and gleebs_rect is not None:
            ghost = battle_assets.get("gleebs")
            if ghost is not None:
                _battle_blit_fit(target, ghost, gleebs_box.move(4, -2), 46)
        if gleebs_rect is None:
            _battle_blit_scaled(target, battle_assets.get("spire_left"), pygame.Rect(78, 92, 150, 338), 98)
        gate_alpha = 178
        if victory_progress > 0.0:
            gate_alpha = max(42, int(178 * (1.0 - victory_progress * 0.76)))
        elif boss_move.key in {"gate_anchor", "hollow_bloom"}:
            gate_alpha = max(178, min(238, 208 + int(math.sin(phase * 5.2) * 24)))
        if _battle_blit_fit(target, battle_assets.get("gate"), gate_box, gate_alpha) is None:
            _battle_blit_scaled(target, battle_assets.get("spire_right"), pygame.Rect(W - 246, 86, 158, 348), 98, True)

        fog = battle_assets.get("fog")
        if fog is not None:
            fog_rect = pygame.Rect(80, 318, W - 160, 180)
            _battle_blit_scaled(target, fog, fog_rect, 82)
        wisp = battle_assets.get("wisp")
        if wisp is not None:
            drift = int(math.sin(phase * 0.7) * 24)
            _battle_blit_scaled(target, wisp, pygame.Rect(260 + drift, 150, 470, 112), 62)
            _battle_blit_scaled(target, wisp, pygame.Rect(625 - drift, 330, 420, 100), 48, True)

    _gothic_text(target, small_font, 'THE BEGINNING  /  SEALED MEMORY CHAMBER',
                 (W // 2, 34), (135, 126, 122), True)
    _gothic_text(target, title_font, _battle_name_for(battle_entity_id), (W // 2, 70), (220, 210, 197), True)
    if rematch and challenge_tier > 0:
        _gothic_text(target, small_font, f'MEMORY ECHO CHALLENGE // TIER {challenge_tier}', (W // 2, 104), (156, 206, 219), True)

    # Pass 44: every boss response is announced before the player commits an
    # action. During Pass 48's final breakup the tell tray yields the screen to
    # the defeat beat instead of advertising an attack that can no longer occur.
    if victory_progress <= 0.0:
        tell = pygame.Rect(284, 102, 712, 74)
        tell_surface = pygame.Surface(tell.size, pygame.SRCALPHA)
        tell_surface.fill((18, 14, 20, 174))
        target.blit(tell_surface, tell)
        pygame.draw.rect(target, (109, 88, 86), tell, 1)
        tell_label = f'SIGNAL CORRUPTED  //  {shown_move.label}' if mind_interference else f'NEXT ANSWER  //  {shown_move.label}'
        tell_color = (207, 126, 137) if mind_interference else (181, 157, 143)
        _gothic_text(target, small_font, tell_label,
                     (tell.centerx, tell.top + 16), tell_color, True)
        _gothic_text(target, small_font, shown_move.telegraph,
                     (tell.centerx, tell.top + 37), (218, 207, 193), True)
        hint_line = _mind_corrupt_hint(shown_move.gleebs_hint, mind_level) if mind_interference else shown_move.gleebs_hint
        _gothic_text(target, small_font, hint_line,
                     (tell.centerx, tell.top + 58), (187, 121, 145) if mind_interference else (137, 180, 184), True)
        if signal_verified_counter:
            verified = f"CAUSAL RESONANCE // VERIFIED COUNTER: {signal_verified_counter.upper()}"
            _gothic_text(target, small_font, verified,
                         (tell.centerx, tell.bottom + 12), (146, 215, 220), True)
        elif mind_suppressed:
            _gothic_text(target, small_font, "VEIL WARD // MIND INJECTION SUPPRESSED",
                         (tell.centerx, tell.bottom + 12), (176, 156, 218), True)
    else:
        _gothic_text(target, small_font, f'{_battle_name_for(battle_entity_id)} // RECORD FRACTURING',
                     (W // 2, 132), (205, 188, 174), True)

    player_center = (360, 345)
    entity_center = (900, 320)

    # Player lantern glow sits behind IO and is intentionally feathered.
    glow = battle_assets.get("glow") if not safe_mode else None
    glow_strength = 92 + min(2, max(0, int(focus))) * 38
    if fx_kind == "focus" and fx_timer > 0:
        glow_strength = 205
    if glow is not None:
        pulse = 1.0 + math.sin(phase * 4.2) * 0.06
        gw, gh = int(166 * pulse), int(176 * pulse)
        _battle_blit_scaled(target, glow, pygame.Rect(player_center[0] - gw // 2 + 28, player_center[1] - gh // 2 + 14, gw, gh), glow_strength)

    player_rect = None
    if player_img is not None:
        try:
            ratio = player_img.get_width() / max(1, player_img.get_height())
            pw = max(30, int(BATTLE_PLAYER_HEIGHT * ratio))
            player_rect = pygame.Rect(0, 0, pw, BATTLE_PLAYER_HEIGHT)
            player_rect.midbottom = (player_center[0], 438)
            _battle_blit_scaled(target, player_img, player_rect, 255)
        except Exception:
            player_rect = None

    battle_entity = None
    if entity_img is not None:
        if safe_mode:
            try:
                ratio = entity_img.get_width() / max(1, entity_img.get_height())
                battle_entity = pygame.transform.scale(entity_img, (max(8, int(BATTLE_ENTITY_HEIGHT * ratio)), BATTLE_ENTITY_HEIGHT))
            except Exception:
                battle_entity = entity_img
        else:
            battle_entity = _entity_presence_surface(entity_img, BATTLE_ENTITY_HEIGHT, phase)
        if battle_entity is not None:
            entity_rect = battle_entity.get_rect(midbottom=(entity_center[0], 426))
            if victory_progress > 0.0:
                # The boss remains fixed in place while its record loses coherence.
                # Alpha falls away behind the authored fragment burst rather than
                # moving/shaking the Entity itself.
                battle_entity = battle_entity.copy()
                battle_entity.set_alpha(max(0, int(255 * (1.0 - victory_progress))))
                if victory_progress < 0.78:
                    ghost = battle_entity.copy()
                    ghost.set_alpha(max(0, int(72 * (1.0 - victory_progress))))
                    target.blit(ghost, entity_rect.move(int(math.sin(phase * 13.0) * 4), 0))
            target.blit(battle_entity, entity_rect)
        else:
            entity_rect = pygame.Rect(entity_center[0] - 40, 250, 80, 176)
    else:
        entity_rect = pygame.Rect(entity_center[0] - 40, 250, 80, 176)

    if damage_fx and not safe_mode:
        _draw_boss_damage_fx(target, damage_fx)

    # Pass 89: The Mind can lie through text, but the Guardian's physical wind-up
    # remains a truthful channel the player can learn to read.
    if victory_progress <= 0.0:
        _draw_guardian_true_tell(target, battle_entity_id, boss_move.key, player_center, entity_center, phase)
    if guardian_fx_timer > 0.0:
        _draw_guardian_attack_fx(target, battle_entity_id, guardian_fx_kind, guardian_fx_timer, player_center, entity_center)

    # Short-lived action feedback uses soft procedural/feathered treatment rather
    # than opaque image cards.
    lantern_start = (player_center[0] + 40, 354)
    entity_target = (entity_center[0] - 18, 330)
    if fx_timer > 0:
        if fx_kind == "lantern_shot":
            _draw_soft_beam(target, lantern_start, entity_target, phase)
        elif fx_kind == "guard":
            ward = pygame.Surface((W, H), pygame.SRCALPHA)
            for expand, alpha in ((0, 80), (10, 42), (22, 18)):
                r = pygame.Rect(player_center[0] - 76 - expand, 248 - expand, 152 + expand * 2, 210 + expand * 2)
                pygame.draw.ellipse(ward, (149, 211, 226, alpha), r, 2)
            target.blit(ward, (0, 0))
        elif fx_kind == "entropy_arc":
            arc = pygame.Surface((W, H), pygame.SRCALPHA)
            progress = clamp(1.0 - fx_timer / max(0.01, BATTLE_FX_TIME), 0.0, 1.0)
            start_x, start_y = lantern_start
            end_x, end_y = entity_target
            for layer, alpha in ((0, 154), (8, 88), (18, 38)):
                box = pygame.Rect(start_x - 30 - layer, start_y - 90 - layer, (end_x - start_x) + 80 + layer * 2, 180 + layer * 2)
                start_ang = math.radians(205 + progress * 18)
                stop_ang = math.radians(338 + progress * 22)
                pygame.draw.arc(arc, (132, 224, 235, alpha), box, start_ang, stop_ang, max(1, 4 - layer // 8))
            ring_radius = 32 + int(progress * 56)
            for extra, alpha in ((0, 138), (14, 66), (30, 24)):
                rr = ring_radius + extra
                pygame.draw.ellipse(arc, (174, 238, 240, alpha), pygame.Rect(end_x - rr, end_y - rr // 2, rr * 2, rr), 2)
            for i in range(7):
                angle = phase * 2.4 + i * (math.tau / 7.0)
                radius = 20 + i * 3
                px = end_x + math.cos(angle) * radius
                py = end_y + math.sin(angle) * radius * 0.55
                pygame.draw.circle(arc, (194, 245, 240, max(26, 118 - i * 11)), (int(px), int(py)), 2 + (i % 2))
            target.blit(arc, (0, 0))
        elif fx_kind == "arrival":
            veil = battle_assets.get("wisp") if not safe_mode else None
            if veil is not None:
                _battle_blit_scaled(target, veil, pygame.Rect(344, 176, 580, 180), 86)
            if not safe_mode:
                _draw_fullscreen_variant(
                    target,
                    battle_assets.get("transition_entry"),
                    int(210 * clamp(fx_timer / 0.85, 0.0, 1.0) * _PRESENTATION_FLASH_SCALE),
                )

    _gothic_text(target, small_font, 'IO', (player_center[0], 464), (198, 190, 181), True)
    _gothic_text(target, small_font, MEMORY_GUARDIAN_EPITHETS.get(battle_entity_id, "MEMORY GUARDIAN"), (entity_center[0], 464), (154, 146, 140), True)
    _draw_battle_track(target, small_font, 'RESOLVE', hp, max_resolve, (96, 485), False)
    _draw_battle_track(target, small_font, 'PRESENCE', entity_hp, max_presence, (W - 96, 485), True)

    # Battle-only command tray; no permanent gameplay HUD is introduced.
    tray = pygame.Rect(72, 520, W - 144, 164)
    if not _draw_hud_skin(target, "battle_tray", tray):
        _draw_gothic_frame(target, tray)
    _gothic_text(target, small_font, message, (tray.centerx, tray.top + 30), (190, 180, 168), True)
    if victory_progress <= 0.0:
        options = ['LANTERN SHOT', 'FOCUS', 'GUARD']
        if entropy_arc_ready:
            arc_name = 'ENTROPY ARC+' if entropy_arc_level_value >= 2 else 'ENTROPY ARC'
            arc_label = arc_name if entropy_arc_cooldown <= 0 else f'{arc_name} // {entropy_arc_cooldown}'
            options.append(arc_label)
        options.append('FLEE')
        count = len(options)
        gap = 12
        available = tray.width - 68
        button_w = max(158, min(238, (available - gap * (count - 1)) // count))
        total_w = button_w * count + gap * (count - 1)
        start_x = tray.centerx - total_w // 2
        for i, label in enumerate(options):
            r = pygame.Rect(start_x + i * (button_w + gap), tray.top + 70, button_w, 54)
            command_rects.append(r)
            if i == selected:
                select = pygame.Surface(r.size, pygame.SRCALPHA)
                select.fill((72, 57, 62, 148))
                target.blit(select, r)
                pygame.draw.rect(target, (152, 126, 105), r, 1)
            disabled = entropy_arc_ready and i == 3 and entropy_arc_cooldown > 0
            _gothic_text(target, small_font, label, r.center,
                         (108, 108, 114) if disabled else ((240, 230, 212) if i == selected else (155, 149, 144)), True)
        counterplay = []
        if causal_resonance_available:
            verify_label = 'R VERIFY' if signal_verify_cooldown <= 0 else f'R VERIFY // {signal_verify_cooldown}'
            counterplay.append(verify_label)
        if veil_ward_available:
            ward_label = 'Q PURGE' if mind_ward_cooldown <= 0 else f'Q PURGE // {mind_ward_cooldown}'
            counterplay.append(ward_label)
        footer = 'A / D OR ARROWS   •   ENTER'
        if counterplay:
            footer += '   •   ' + '   •   '.join(counterplay)
        _gothic_text(target, small_font, footer,
                     (tray.centerx, tray.bottom - 20), (118, 112, 111), True)
    else:
        _gothic_text(target, menu_font, 'THE RECORD BREAKS', (tray.centerx, tray.top + 92),
                     (211, 199, 184), True)
    return command_rects


def _sanitize_era_state(raw: object, stack: "WorldStack", fallback: tuple[float, float], fallback_facing: int = 1) -> dict:
    """Return a safe temporal anchor even when a save contains damaged values."""
    state = raw if isinstance(raw, dict) else {}
    default_layer = stack.walk_layers[0]
    try:
        wanted_number = int(state.get("walk_layer", default_layer.number))
    except (TypeError, ValueError):
        wanted_number = default_layer.number
    layer = layer_by_number(stack, wanted_number)
    if layer is None or not layer.walk:
        layer = default_layer
    try:
        x = float(state.get("x", fallback[0]))
        y = float(state.get("y", fallback[1]))
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("non-finite temporal anchor")
    except (TypeError, ValueError, OverflowError):
        x, y = fallback
    x = clamp(x, 1.0, WORLD_SIZE[0] - 2.0)
    y = clamp(y, 1.0, WORLD_SIZE[1] - 2.0)
    x, y = nearest_walkable_point(layer, (x, y))
    try:
        facing = -1 if int(state.get("facing", fallback_facing)) < 0 else 1
    except (TypeError, ValueError):
        facing = -1 if fallback_facing < 0 else 1
    return {"x": x, "y": y, "walk_layer": layer.number, "facing": facing}


def _run_session() -> int:
    _early_log(f"MAIN enter argv={sys.argv!r}")
    _set_windows_dpi_awareness()
    _early_log("MAIN dpi awareness complete")
    pygame.init()
    _early_log(f"MAIN pygame.init complete display={pygame.display.get_init()} font={pygame.font.get_init()} mixer={pygame.mixer.get_init()!r}")
    settings_defaults = {
        "music_volume": MUSIC_VOLUME,
        "sfx_volume": SFX_VOLUME,
        "fog_level": 1.0,
        "vignette_level": 1.0,
        "darkness_level": 1.0,
        "text_style": "worn",
        "motion_fx": 1.0,
        "flash_fx": 1.0,
        "guidance_mode": "context",
        "fullscreen": False,
    }
    settings = _load_json(_settings_path(), {})
    if not settings:
        settings = _load_json(_old_settings_path(), settings_defaults)
    for key in ("music_volume", "sfx_volume", "fog_level", "vignette_level", "darkness_level"):
        default = settings_defaults[key]
        try:
            settings[key] = clamp(float(settings.get(key, default)), 0.0, 1.0 if key in {"music_volume", "sfx_volume"} else 1.5)
        except (TypeError, ValueError):
            settings[key] = default
    settings["text_style"] = "clear" if str(settings.get("text_style", "worn")).lower() == "clear" else "worn"
    try:
        settings["motion_fx"] = _nearest_level(float(settings.get("motion_fx", 1.0)), (0.35, 0.65, 1.0))
    except (TypeError, ValueError):
        settings["motion_fx"] = 1.0
    try:
        settings["flash_fx"] = _nearest_level(float(settings.get("flash_fx", 1.0)), (0.0, 0.5, 1.0))
    except (TypeError, ValueError):
        settings["flash_fx"] = 1.0
    settings["guidance_mode"] = _normalize_guidance_mode(settings.get("guidance_mode", "context"))
    settings["fullscreen"] = bool(settings.get("fullscreen", False))
    _apply_presentation_preferences(settings)
    if _has_flag("--fullscreen"):
        fullscreen = True
    elif _has_flag("--windowed"):
        fullscreen = False
    else:
        fullscreen = settings["fullscreen"]
    windowed_size = _parse_window_size(_flag_value("--window-size"), DEFAULT_WINDOW)
    existing = pygame.display.get_surface()
    if existing is not None and not fullscreen and not (existing.get_flags() & (pygame.FULLSCREEN | pygame.NOFRAME)):
        # Returning from a hosted mode: keep the player's current window size.
        windowed_size = _parse_window_size(f"{existing.get_width()}x{existing.get_height()}", windowed_size)
    _early_log(f"MAIN creating display fullscreen={fullscreen} size={windowed_size}")
    window = _create_window(fullscreen, windowed_size)
    _early_log(f"MAIN display created driver={pygame.display.get_driver()!r} surface={window.get_size()!r}")
    logical = pygame.Surface((W, H)).convert()
    pygame.display.set_caption(DISPLAY_TITLE)
    clock = pygame.time.Clock()
    font, small, menu_font, title_font = load_menu_fonts(settings["text_style"] == "clear")
    gleebs_option_font = load_gleebs_option_font(settings["text_style"] == "clear")
    dev_coord_font = _load_menu_font("small_font.ttf", 11, sys_name="Liberation Mono")
    smoke_test = _has_flag("--smoke-test")
    test_shot = _flag_value("--test-shot")
    test_causal_resonance = _has_flag("--test-causal-resonance")
    test_lore_debris = _has_flag("--test-lore-debris")
    test_shrine_echo = _has_flag("--test-shrine-echo")
    test_final_shrine_echo = _has_flag("--test-final-shrine-echo")
    test_deep_lore = _has_flag("--test-deep-lore")
    test_lore_archive = _has_flag("--test-lore-archive")
    test_start_menu = _has_flag("--test-start-menu")
    test_boss_strip = _has_flag("--test-boss-strip")
    test_projection_drone = _has_flag("--test-projection-drone")
    safe_mode = _has_flag("--safe-mode")
    smoke_frames = 0

    _early_log("MAIN parsing authored layer stacks")
    stacks = parse_layer_stacks()
    _early_log(f"MAIN layer stacks loaded keys={sorted(stacks)}")
    world_variant_paths = discover_world_variant_paths()
    world_variant_surfaces: dict[tuple[str, str], pygame.Surface | None] = {}
    _early_log(f"MAIN world variants registered roles={sorted(world_variant_paths)}")
    depth_composites: dict[tuple[str, int, str], tuple[pygame.Surface, pygame.Surface, pygame.Surface]] = {}

    def depth_composite_for(active_stack: WorldStack, active_walk_number: int):
        requested_role = active_world_variant_role(
            active_stack.key, entity_defeated, shrine_activated, first_witness_echoes_complete
        )
        candidate_roles = [requested_role]
        if requested_role == "witness_restored":
            candidate_roles.append("witness_recorded")
        elif requested_role == "witness_recorded":
            candidate_roles.append("witness_defeated")
        selected_role = next(
            (role for role in candidate_roles if (active_stack.key, role) in world_variant_paths),
            "base",
        )
        variant_path = world_variant_paths.get((active_stack.key, selected_role))
        cache_role = selected_role
        key = (active_stack.key, active_walk_number, cache_role)
        if key not in depth_composites:
            variant_surface = None
            variant_key = (active_stack.key, selected_role)
            if variant_path is not None:
                if variant_key not in world_variant_surfaces:
                    world_variant_surfaces[variant_key] = _load_registered_world_variant(variant_path)
                variant_surface = world_variant_surfaces[variant_key]
            if len(depth_composites) >= DEPTH_COMPOSITE_CACHE_MAX:
                depth_composites.pop(next(iter(depth_composites)))
            depth_composites[key] = build_depth_composite(active_stack, active_walk_number, variant_surface, not safe_mode)
        return depth_composites[key]
    if not stacks:
        raise RuntimeError("No numbered A/B layers found in assets/source/layers")

    world_key = "a" if "a" in stacks else next(iter(stacks))
    stack = stacks[world_key]
    # Pass 138: a clean New Game begins at the exact requested Present point
    # on 4awalk.  The complete World A layer stack remains active; only IO
    # start position/walk-plane authority changes here.
    if world_key == "a":
        walk_layer = layer_by_number(stack, PRESENT_NEW_GAME_WALK_LAYER) or stack.walk_layers[0]
        px, py = nearest_walkable_point(walk_layer, PRESENT_NEW_GAME_START)
    else:
        walk_layer = stack.walk_layers[0]
        px, py = nearest_spawn(walk_layer.mask)
    if test_causal_resonance and world_key == "a":
        for candidate in stack.walk_layers:
            if footprint_walkable_at(candidate, FUTURE_CLUE_POS[0], FUTURE_CLUE_POS[1]):
                walk_layer = candidate
                break
        px, py = nearest_walkable_point(walk_layer, FUTURE_CLUE_POS)
    _early_log("MAIN loading player animations")
    player_anims = load_player_animations()
    _early_log("MAIN player animations loaded")
    atmosphere_assets = load_atmosphere_assets()
    _early_log("MAIN optional atmosphere assets loaded")
    weather_particle_assets = load_weather_particle_assets()
    _early_log(
        "MAIN weather particle banks loaded "
        f"future={len(weather_particle_assets.get('a', ()))} past={len(weather_particle_assets.get('b', ()))}"
    )
    weather_overlay_assets = load_weather_overlay_assets()
    _early_log(f"MAIN weather alpha overlays loaded keys={sorted(weather_overlay_assets)}")
    player_projection_drone_asset = _load_player_projection_drone_asset()
    projection_drone_assets = _load_projection_drone_assets()
    _early_log(f"MAIN player projection drone loaded={player_projection_drone_asset is not None}")
    _early_log(f"MAIN projection enemy drone assets loaded count={len(projection_drone_assets)}")
    transition_assets = load_transition_variant_assets()
    _early_log(f"MAIN transition variants loaded keys={sorted(transition_assets)}")
    battle_assets = load_battle_assets()
    if "battle_entry" in transition_assets:
        battle_assets["transition_entry"] = transition_assets["battle_entry"]
    _early_log(f"MAIN battle presentation assets loaded keys={sorted(battle_assets)}")
    boss_damage_fx_assets = load_boss_damage_fx_assets()
    _early_log(
        "MAIN boss damage FX assets loaded "
        f"debris={len(boss_damage_fx_assets.get('debris', ()))} "
        f"particles={len(boss_damage_fx_assets.get('particles', ()))}"
    )
    lore_debris_assets = load_lore_debris_assets()
    _early_log(f"MAIN lore memory-debris particle assets loaded roles={len(lore_debris_assets)}")
    start_menu_assets = load_start_menu_assets()
    _early_log(f"MAIN start menu assets loaded keys={sorted(start_menu_assets)}")
    global _HUD_ASSETS
    _HUD_ASSETS = load_hud_assets()
    _early_log(f"MAIN optional HUD skins loaded keys={sorted(_HUD_ASSETS)}")
    story_assets = load_story_assets()
    _early_log(f"MAIN replaceable story placeholders loaded keys={sorted(story_assets)}")
    world_fx_assets = load_world_fx_assets()
    _early_log(f"MAIN replaceable world FX placeholders loaded keys={sorted(world_fx_assets)}")
    sable_idle_frames = load_sable_idle_frames()
    _early_log(f"MAIN Sable idle frames loaded count={len(sable_idle_frames)} from={SABLE_ASSET_DIR}")
    machine_catalog = load_machine_catalog()
    _MACHINE_RUNTIME_CATALOG.clear()
    _MACHINE_RUNTIME_CATALOG.update(machine_catalog)
    _early_log(f"MAIN machine catalogue finished={len(_finished_machine_parts(machine_catalog))} compatible_total={len(machine_catalog)} source_art={len(_machine_source_parts())} base={MACHINE_ASSET_DIR} variants={MACHINE_VARIANTS_DIR}")
    boss_portraits = load_boss_portraits()
    _early_log(f"MAIN boss portraits loaded keys={sorted(boss_portraits)}")
    ambient_playlist = AmbientPlaylist()
    ambient_playlist.set_volume(settings["music_volume"])
    battle_sfx = BattleSFX(settings["sfx_volume"])
    _early_log(f"MAIN battle SFX loaded cues={len(battle_sfx.sounds)}")
    exploration_sfx = ExplorationSFX(settings["sfx_volume"])
    _early_log(f"MAIN exploration SFX loaded cues={len(exploration_sfx.sounds)}")
    if not safe_mode:
        ambient_playlist.start()
    guardian_imgs = {guardian_id: _load_optional_sprite(path, (250, 300)) for guardian_id, path in MEMORY_GUARDIAN_ASSETS.items()}
    entity_img = guardian_imgs[ENTITY_ID]
    rooted_crown_img = guardian_imgs[ROOTED_CROWN_ID]
    veil_warden_img = guardian_imgs[VEIL_WARDEN_ID]
    _early_log(f"MAIN memory guardian sprites ready count={len(guardian_imgs)} ids={list(guardian_imgs)}")
    shrine_img = _load_optional_sprite(SHRINE_ASSET, (240, 300))
    _early_log(f"MAIN shrine sprite ready size={shrine_img.get_size()!r}")
    player_img = player_anims["idle"][0]
    player_x = px
    player_y = py
    facing = 1
    anim_state = "idle"
    anim_index = 0.0
    vel_x = 0.0
    vel_y = 0.0
    hop_timer = 0.0
    end_reached = False
    end_message_timer = 0.0
    depth_switch_timer = 0.0
    transition_phase = "none"
    transition_timer = 0.0

    zoom = DEFAULT_ZOOM
    cam_x = px
    cam_y = clamp(py - 40, *camera_bounds(zoom)[2:])
    show_help = False
    dev_coords_visible = False
    guidance_notice = ""
    guidance_notice_timer = 0.0
    guidance_idle_timer = 0.0
    guidance_idle_cooldown = 0.0
    guidance_pending_after_transition = False
    atmosphere_time = 0.0
    weather_rng = random.Random(0xA10F49)
    present_cloud_shadow_rng = random.Random(0xC10D5)
    present_cloud_shadow_wait = present_cloud_shadow_rng.uniform(*PRESENT_CLOUD_SHADOW_IDLE_RANGE)
    present_cloud_shadow_timer = 0.0
    present_cloud_shadow_duration = 0.0
    present_cloud_shadow_peak_alpha = 0.0
    present_cloud_shadow_alpha = 0.0
    weather_particles: list[dict] = []
    weather_spawn_accumulator = 0.0
    _seed_weather_particles(weather_particles, weather_particle_assets.get(world_key, ()), world_key, weather_rng)
    footstep_distance = 0.0
    paused = False
    machine_inventory_open = False
    machine_inventory_page = 0
    pause_screen = "main"
    pause_selected = 0
    settings_selected = 0
    save_slot_selected = 0
    current_save_slot: int | None = None
    quit_selected = 0
    pause_status = ""
    pause_status_timer = 0.0
    automated_gameplay_test = any((
        test_causal_resonance,
        test_lore_debris,
        test_shrine_echo,
        test_final_shrine_echo,
        test_deep_lore,
        test_lore_archive,
        test_boss_strip,
        test_projection_drone,
    ))
    start_menu_open = (test_start_menu or not automated_gameplay_test) and not _has_flag("--skip-start-menu")
    start_menu_screen = "main"
    continue_slot = newest_manual_save_slot()
    modes_progress = mode_progress()
    modes_unlocked = mode_host.unlocked_ids(modes_progress, remembered_modes(settings))
    settings["unlocked_modes"] = list(modes_unlocked)
    settings.pop("entropy_mode_unlocked", None)
    modes_selected = 0
    modes_hit_rects: list[pygame.Rect] = []
    mode_launch: "mode_host.ModeSpec | None" = None
    start_menu_selected = 0 if continue_slot is not None else 1
    start_menu_status = ""
    start_menu_status_timer = 0.0
    if _PENDING_TITLE_NOTICE:
        start_menu_status = _PENDING_TITLE_NOTICE.pop()
        start_menu_status_timer = 4.0
    start_menu_hit_rects: list[pygame.Rect] = []
    pause_menu_hit_rects: list[pygame.Rect] = []
    slot_hit_rects: list[pygame.Rect] = []
    settings_hit_controls: list[tuple[pygame.Rect, pygame.Rect | None, pygame.Rect | None]] = []
    controls_hit_rects: list[pygame.Rect] = []
    quit_hit_rects: list[pygame.Rect] = []
    dialogue_hit_rects: list[pygame.Rect] = []
    sable_hit_rects: list[pygame.Rect] = []
    battle_hit_rects: list[pygame.Rect] = []
    machine_screen_rects: list[tuple[int, pygame.Rect]] = []
    machine_hotbar_rect: pygame.Rect | None = None
    cursor_visible = True
    try:
        pygame.mouse.set_visible(True)
    except pygame.error:
        pass

    # Pass 131: optional controller input layers onto the existing keyboard/mouse
    # authority.  SDL's controller API normalizes mainstream pad layouts; a raw
    # joystick fallback keeps generic devices usable.  No controller is required.
    controller_bridge = ControllerBridge()
    controller_cursor = pygame.Vector2(W * 0.5, H * 0.5)
    controller_sprint_toggled = False
    controller_hint_timer = 0.0
    controller_input_mode = False
    controller_drag_active = False
    if controller_bridge.connected:
        _early_log(f"MAIN controller connected name={controller_bridge.name!r}")

    # Two independently persistent temporal anchors.  World A is the far-future
    # present; World B is the Beginning.  Shifting never teleports the other era.
    era_states = {
        "a": {"x": player_x, "y": player_y, "walk_layer": walk_layer.number, "facing": facing},
        "b": None,
    }
    # Pass 98: terminal-return snapshots are separate from ordinary era save state.
    # A snapshot exists only after the player actually LEAVES that era through
    # its terminal, so first-time arrivals still use the authored anchor.
    temporal_return_states: dict[str, dict | None] = {"a": None, "b": None}
    if "b" in stacks and stacks["b"].walk_layers:
        b_layer = stacks["b"].walk_layers[0]
        bx, by = nearest_walkable_point(b_layer, WORLD_B_ENTRY_HINT)
        era_states["b"] = {"x": bx, "y": by, "walk_layer": b_layer.number, "facing": 1}
    entity_rng = random.Random(ENTITY_PLACEMENT_SEED)
    if "b" in stacks and stacks["b"].walk_layers:
        entity_layer = stacks["b"].walk_layers[0]
        entity_pos = _random_walkable_location(entity_layer, entity_rng, WORLD_B_ENTRY_HINT)
        entity_walk_number = entity_layer.number
    else:
        entity_pos = (0.0, 0.0)
        entity_walk_number = 0
    lore_placements = build_lore_placements(stacks, lore_debris_assets, entity_pos)
    _early_log(f"MAIN deterministic lore memory-debris placements={len(lore_placements)} seed={DEBRIS_STORY_SEED}")
    rooted_crown_pos = (0.0, 0.0)
    rooted_crown_walk_number = 0
    if "b" in stacks and stacks["b"].walk_layers:
        rooted_layer = stacks["b"].walk_layers[0]
        rooted_avoid = [WORLD_B_ENTRY_HINT, entity_pos] + [p.position for p in lore_placements if p.record.world == "b"]
        rooted_crown_pos = _random_walkable_location_away(
            rooted_layer, random.Random(ROOTED_CROWN_ENTITY_SEED), WORLD_B_ENTRY_HINT, rooted_avoid, 240.0
        )
        rooted_crown_walk_number = rooted_layer.number
    rooted_crown_shrine_pos = WORLD_A_START
    rooted_crown_shrine_walk_number = 4
    if "a" in stacks and stacks["a"].walk_layers:
        shrine_layer = layer_by_number(stacks["a"], 4) or stacks["a"].walk_layers[0]
        shrine_avoid = [WORLD_A_START, WORLD_A_END] + [p.position for p in lore_placements if p.record.world == "a"]
        rooted_crown_shrine_pos = _random_walkable_location_away(
            shrine_layer, random.Random(ROOTED_CROWN_SHRINE_SEED), WORLD_A_START, shrine_avoid, 260.0
        )
        rooted_crown_shrine_walk_number = shrine_layer.number
    veil_warden_pos = (0.0, 0.0)
    veil_warden_walk_number = 0
    if "b" in stacks and stacks["b"].walk_layers:
        veil_layer = stacks["b"].walk_layers[0]
        veil_avoid = [WORLD_B_ENTRY_HINT, entity_pos, rooted_crown_pos] + [p.position for p in lore_placements if p.record.world == "b"]
        veil_warden_pos = _random_walkable_location_away(
            veil_layer, random.Random(VEIL_WARDEN_ENTITY_SEED), WORLD_B_ENTRY_HINT, veil_avoid, 260.0
        )
        veil_warden_walk_number = veil_layer.number

    # Pass 85: all seven Memory Guardians are present in the Beginning/Past at
    # once.  Placement uses authored walkable ground near broad horizontal hints
    # so the player can challenge archives in any order without progression gates.
    guardian_positions: dict[str, tuple[float, float]] = {}
    guardian_walk_numbers: dict[str, int] = {}
    if "b" in stacks and stacks["b"].walk_layers:
        for guardian_id in MEMORY_GUARDIAN_ORDER:
            hint = MEMORY_GUARDIAN_HINTS[guardian_id]
            g_layer, g_pos = nearest_walkable_across_stack(stacks["b"], hint, None)
            guardian_positions[guardian_id] = g_pos
            guardian_walk_numbers[guardian_id] = g_layer.number
        # Pass 87 placement contract: broad hints are intentionally spaced so
        # authored-ground snapping cannot bunch the archive obelisks together.
        # If custom layer art ever violates the contract, keep the resolved
        # positions but emit a diagnostic instead of silently relocating them
        # onto non-authored ground.
        guardian_spacing = guardian_field_min_separation(guardian_positions)
        _early_log(f"MAIN Memory Guardian minimum separation={guardian_spacing:.1f} target={MEMORY_GUARDIAN_MIN_SEPARATION:.1f}")
        if guardian_spacing < MEMORY_GUARDIAN_MIN_SEPARATION:
            _early_log("WARN Memory Guardian field spacing below target after authored-ground snap")
        entity_pos = guardian_positions[ENTITY_ID]
        entity_walk_number = guardian_walk_numbers[ENTITY_ID]
        rooted_crown_pos = guardian_positions[ROOTED_CROWN_ID]
        rooted_crown_walk_number = guardian_walk_numbers[ROOTED_CROWN_ID]
        veil_warden_pos = guardian_positions[VEIL_WARDEN_ID]
        veil_warden_walk_number = guardian_walk_numbers[VEIL_WARDEN_ID]

    veil_warden_shrine_pos = WORLD_A_START
    veil_warden_shrine_walk_number = 4
    if "a" in stacks and stacks["a"].walk_layers:
        veil_shrine_layer = layer_by_number(stacks["a"], 4) or stacks["a"].walk_layers[0]
        veil_shrine_avoid = [WORLD_A_START, WORLD_A_END, rooted_crown_shrine_pos] + [p.position for p in lore_placements if p.record.world == "a"]
        veil_warden_shrine_pos = _random_walkable_location_away(
            veil_shrine_layer, random.Random(VEIL_WARDEN_SHRINE_SEED), WORLD_A_START, veil_shrine_avoid, 280.0
        )
        veil_warden_shrine_walk_number = veil_shrine_layer.number
    additional_shrine_positions: dict[str, tuple[float, float]] = {}
    additional_shrine_walk_numbers: dict[str, int] = {}
    if "a" in stacks and stacks["a"].walk_layers:
        additional_shrine_layer = layer_by_number(stacks["a"], 4) or stacks["a"].walk_layers[0]
        additional_avoid = [WORLD_A_START, WORLD_A_END, rooted_crown_shrine_pos, veil_warden_shrine_pos] + [p.position for p in lore_placements if p.record.world == "a"]
        for guardian_id in ADDITIONAL_SHRINE_IDS:
            shrine_origin = MEMORY_GUARDIAN_HINTS.get(guardian_id, WORLD_A_START)
            shrine_pos = _random_walkable_location_away(
                additional_shrine_layer, random.Random(ADDITIONAL_SHRINE_SEEDS[guardian_id]), shrine_origin, additional_avoid, 260.0
            )
            additional_shrine_positions[guardian_id] = shrine_pos
            additional_shrine_walk_numbers[guardian_id] = additional_shrine_layer.number
            additional_avoid.append(shrine_pos)
    future_anchor_pos = TEMPORAL_ANCHOR_HINT
    future_anchor_walk_number = 0
    if "a" in stacks and stacks["a"].walk_layers:
        future_anchor_layer, future_anchor_pos = nearest_walkable_across_stack(stacks["a"], TEMPORAL_ANCHOR_HINT, 4)
        future_anchor_walk_number = future_anchor_layer.number
    past_anchor_pos = PAST_TEMPORAL_ANCHOR_HINT
    past_anchor_walk_number = 0
    if "b" in stacks and stacks["b"].walk_layers:
        past_anchor_layer, past_anchor_pos = nearest_walkable_across_stack(stacks["b"], PAST_TEMPORAL_ANCHOR_HINT, None)
        past_anchor_walk_number = past_anchor_layer.number

    # Sable is intentionally resolved against authored Past walkable ground near
    # the inset far-left side, clear of the heavy vignette edge. She never receives a Future render position: lore
    # authority records that a Guardian destroys her before the Present.
    sable_pos = SABLE_PAST_HINT
    sable_walk_number = 0
    if "b" in stacks and stacks["b"].walk_layers:
        sable_layer, sable_pos = nearest_walkable_across_stack(stacks["b"], SABLE_PAST_HINT, None)
        sable_walk_number = sable_layer.number
    _early_log(f"MAIN Sable resolved Past position={sable_pos!r} walk={sable_walk_number} future={SABLE_FUTURE_STATUS}")
    entity_defeated = False
    defeated_boss_ids: set[str] = set()
    entity_met = False
    entity_declined_count = 0
    entity_dialogue = False
    entity_dialogue_page = 0
    entity_dialogue_first_visit = False
    entity_choice = 0
    sable_met = False
    sable_dialogue = False
    sable_dialogue_mode = "lore"
    sable_dialogue_page = 0
    sable_dialogue_first_visit = False
    sable_dialogue_selected = 0
    sable_shop_selected = 0
    sable_shop_status = ""
    machine_bits = 0
    machine_inventory = sanitize_machine_inventory(None, valid_part_keys=set(machine_catalog))
    machine_placements: list[dict] = []
    machine_next_id = 1
    machine_build_mode = False
    machine_pending_part: str | None = None
    machine_pending_pos = (player_x + 80.0, player_y)
    machine_drag_id: int | None = None
    machine_drag_origin: tuple[float, float] | None = None
    machine_hotbar_flash_key: str | None = None
    machine_hotbar_flash_timer = 0.0
    machine_inventory_selected = 0
    machine_workshop_open = False
    machine_workshop_row = 0
    machine_workshop_shape = 0
    machine_workshop_texture = 0
    machine_workshop_role = 0
    machine_workshop_size = 1
    machine_workshop_functions: set[str] = set()
    machine_workshop_snap_points: list[tuple[float, float]] = [(0.14, 0.5), (0.86, 0.5)]
    machine_workshop_snap_selected = 0
    machine_workshop_snap_edit = False
    machine_workshop_snap_drag: int | None = None
    machine_workshop_status = ""
    machine_workshop_hit_rects: list[pygame.Rect] = []
    machine_workshop_preview_rect: pygame.Rect | None = None
    machine_head_dialogue = False
    machine_head_dialogue_page = 0
    machine_head_dialogue_pages: tuple[tuple[str, str], ...] = ()
    machine_head_dialogue_part_key = ""
    machine_network_signature: tuple | None = None
    machine_network: dict[int, dict[str, object]] = {}
    dev_console_open = False
    dev_console_text = ""
    dev_console_status = ""
    dev_console_status_timer = 0.0
    shrine_activated = False
    rooted_crown_defeated = False
    rooted_crown_met = False
    rooted_crown_declined_count = 0
    rooted_crown_shrine_activated = False
    rooted_crown_clue_discovered = False
    veil_warden_defeated = False
    veil_warden_met = False
    veil_warden_declined_count = 0
    veil_warden_shrine_activated = False
    guardian_dialogue_states: dict[str, dict[str, int | bool]] = {
        guardian_id: {"met": False, "declined_count": 0} for guardian_id in MEMORY_GUARDIAN_ORDER
    }
    additional_shrine_activated: dict[str, bool] = {guardian_id: False for guardian_id in ADDITIONAL_SHRINE_IDS}
    game_completed = False
    ending_open = False
    ending_page = 0
    ending_selected = 0
    ending_hit_rects: list[pygame.Rect] = []
    entity_dialogue_kind = ENTITY_ID
    shrine_dialogue_kind = ENTITY_ID
    battle_entity_id = ENTITY_ID
    shrine_dialogue = False
    shrine_dialogue_page = 0
    shrine_choice = 0
    future_clue_discovered = False
    causal_resonance_learned = False
    veil_ward_learned = False
    veil_ward_timer = 0.0
    veil_ward_cooldown = 0.0
    lantern_projection_learned = False
    lantern_projection_upgrade_level = 0
    lantern_projection_active = False
    lantern_projection_timer = 0.0
    lantern_projection_x = player_x
    lantern_projection_y = player_y
    lantern_projection_dir = pygame.Vector2(float(facing), 0.0)
    lantern_projection_integrity = LANTERN_PROJECTION_INTEGRITY
    projection_enemy_drones: list[dict] = []
    projection_enemy_shots: list[dict] = []
    projection_lance_shots: list[dict] = []
    projection_lance_cooldown = 0.0
    projection_lance_learned = False
    projection_lance_mastery = 0
    projection_enemy_rng = random.Random(0xD30A72)
    remote_resonance_learned = False
    remote_resonance_timer = 0.0
    entropy_arc_learned = False
    entropy_arc_mastery = 0
    battle_entropy_arc_cooldown = 0
    rematch_wins = {guardian_id: 0 for guardian_id in MEMORY_GUARDIAN_ORDER}
    future_clue_dialogue = False
    future_clue_dialogue_kind = ENTITY_ID
    future_clue_dialogue_page = 0
    future_clue_choice = 0
    gleebs_dialogue = False
    gleebs_dialogue_topic = "menu"
    gleebs_dialogue_page = 0
    gleebs_dialogue_selected = 0
    resonance_pulse_timer = 0.0
    resonance_cooldown = 0.0
    resonance_notice = ""
    resonance_notice_timer = 0.0
    causal_notice = ""
    causal_notice_timer = 0.0
    bits_notice = ""
    bits_notice_timer = 0.0
    discovered_lore: set[str] = set()
    first_witness_echoes_complete = False
    lore_card_title = ""
    lore_card_lines = ("", "")
    lore_card_timer = 0.0
    lore_archive_open = False
    lore_archive_index = 0
    witnessed_story_moments: set[str] = set()
    story_moment_id = ""
    story_moment_page = 0
    pending_story_moment = ""
    battle_active = False
    battle_selected = 0
    battle_player_hp = FIRST_WITNESS_MAX_RESOLVE
    battle_entity_hp = FIRST_WITNESS_MAX_PRESENCE
    battle_guard = False
    battle_boss_turn = 0
    battle_focus = 0
    battle_message = "Choose an action."
    battle_return_state = None
    battle_fx_kind = ""
    battle_fx_timer = 0.0
    boss_damage_fx: list[dict] = []
    boss_hit_serial = 0
    battle_victory_timer = 0.0
    battle_rematch = False
    battle_challenge_tier = 0
    battle_upgrade_score = 0
    battle_rng = random.Random()
    battle_move_index = 0
    battle_guardian_fx_kind = ""
    battle_guardian_fx_timer = 0.0
    battle_mind_interference_level = 1
    battle_mind_interference_active = False
    battle_mind_fake_move_index = -1
    battle_signal_was_corrupted = False
    battle_signal_verified_counter = ""
    battle_mind_ward_suppressed = False
    battle_signal_verify_cooldown = 0
    battle_mind_ward_cooldown = 0

    def roll_next_battle_signal(previous_index: int = -1) -> None:
        nonlocal battle_move_index, battle_mind_interference_level, battle_mind_interference_active, battle_mind_fake_move_index
        nonlocal battle_signal_was_corrupted, battle_signal_verified_counter, battle_mind_ward_suppressed
        battle_move_index = _choose_battle_move_index(
            battle_entity_id, battle_rng, previous_index, battle_boss_turn, battle_challenge_tier
        )
        battle_mind_interference_level = _mind_interference_level(defeated_boss_ids, battle_entity_id)
        battle_mind_interference_active = _roll_mind_interference(
            battle_entity_id, battle_mind_interference_level, battle_rng
        )
        battle_mind_fake_move_index = (
            _choose_false_move_index(battle_entity_id, battle_move_index, battle_rng)
            if battle_mind_interference_active else -1
        )
        battle_signal_was_corrupted = battle_mind_interference_active
        battle_signal_verified_counter = ""
        battle_mind_ward_suppressed = False

    if test_boss_strip:
        entity_defeated = True
        defeated_boss_ids.add(ENTITY_ID)
    if test_projection_drone:
        lantern_projection_learned = True
        # Seed only the isolated test state so Tab launch also exercises one real
        # Projection Lance path without modifying ordinary saves/progression.
        rematch_wins[ENTITY_ID] = max(int(rematch_wins.get(ENTITY_ID, 0)), PROJECTION_LANCE_UPGRADE_WINS)
        projection_lance_mastery = projection_lance_level(sum(int(value) for value in rematch_wins.values()), veil_warden_shrine_activated)
        projection_lance_learned = projection_lance_mastery >= 1
    if test_lore_debris or test_shrine_echo or test_final_shrine_echo or test_deep_lore or test_lore_archive:
        if test_shrine_echo or test_final_shrine_echo or test_deep_lore:
            entity_defeated = True
            defeated_boss_ids.add(ENTITY_ID)
            shrine_activated = True
            future_clue_discovered = True
            causal_resonance_learned = True
        if test_deep_lore:
            discovered_lore.update(FIRST_WITNESS_ECHO_IDS)
            first_witness_echoes_complete = True
            wanted = next((placement for placement in lore_placements if placement.record.unlock == "reconstructed"), None)
        elif test_final_shrine_echo:
            ordered_echo_ids = sorted(FIRST_WITNESS_ECHO_IDS)
            discovered_lore.update(ordered_echo_ids[:-1])
            wanted_id = ordered_echo_ids[-1]
            wanted = next((placement for placement in lore_placements if placement.record.record_id == wanted_id), None)
        elif test_shrine_echo:
            wanted = next((placement for placement in lore_placements if placement.record.shrine_echo), None)
        elif test_lore_debris:
            wanted = next((placement for placement in lore_placements if placement.record.unlock == "always" and not placement.record.shrine_echo), None)
        else:
            discovered_lore.update(record.record_id for record in LORE_RECORDS[:8])
            lore_archive_open = True
            wanted = None
        if wanted is not None and wanted.record.world in stacks:
            world_key = wanted.record.world
            stack = stacks[world_key]
            walk_layer = layer_by_number(stack, wanted.walk_number) or stack.walk_layers[0]
            player_x, player_y = wanted.position
            cam_x, cam_y = player_x, player_y - 40
            era_states[world_key] = {
                "x": player_x, "y": player_y, "walk_layer": walk_layer.number, "facing": facing,
            }

    def reset_weather_for_world() -> None:
        nonlocal weather_spawn_accumulator
        weather_particles.clear()
        weather_spawn_accumulator = 0.0
        _seed_weather_particles(
            weather_particles,
            weather_particle_assets.get(world_key, ()),
            world_key,
            weather_rng,
        )

    def store_era_state() -> None:
        era_states[world_key] = {"x": player_x, "y": player_y, "walk_layer": walk_layer.number, "facing": facing}

    def select_world(key: str, restore_temporal: bool = True) -> None:
        nonlocal world_key, stack, walk_layer, player_x, player_y, facing, vel_x, vel_y, cam_x, cam_y, hop_timer, end_reached, depth_switch_timer
        if key not in stacks:
            return
        if restore_temporal:
            store_era_state()
        world_key = key
        stack = stacks[key]
        state = era_states.get(key) if restore_temporal else None
        if state:
            fallback = WORLD_A_START if key == "a" else WORLD_B_ENTRY_HINT
            safe = _sanitize_era_state(state, stack, fallback, facing)
            candidate = layer_by_number(stack, safe["walk_layer"]) or stack.walk_layers[0]
            sx, sy = safe["x"], safe["y"]
            walk_layer = candidate
            facing = safe["facing"]
            era_states[key] = safe
        elif world_key == "a":
            walk_layer = layer_by_number(stack, PRESENT_PRIMARY_WALK_LAYER) or stack.walk_layers[0]
            sx, sy = nearest_walkable_point(walk_layer, WORLD_A_START)
        else:
            walk_layer = stack.walk_layers[0]
            sx, sy = nearest_walkable_point(walk_layer, WORLD_B_ENTRY_HINT)
        player_x, player_y = sx, sy
        vel_x = vel_y = 0.0
        hop_timer = 0.0
        end_reached = False
        depth_switch_timer = 0.0
        cam_x, cam_y = sx, sy - 40
        reset_weather_for_world()

    def travel_to_anchor(destination_world: str) -> None:
        nonlocal world_key, stack, walk_layer, player_x, player_y, facing, vel_x, vel_y, cam_x, cam_y, hop_timer, end_reached, depth_switch_timer, transition_phase, transition_timer, guidance_pending_after_transition
        if destination_world not in stacks:
            return

        # Capture the exact terminal-use position in the era being left.  This
        # snapshot is the authoritative return point until that era is left
        # through its terminal again.
        store_era_state()
        temporal_return_states[world_key] = temporal_departure_state(
            player_x, player_y, walk_layer.number, facing
        )

        world_key = destination_world
        stack = stacks[destination_world]
        saved_return = temporal_return_candidate(temporal_return_states, destination_world)
        if destination_world == "a":
            # Player-position-only adjustment: Present crossings always place IO
            # just below the portal on the open side of the foreground wall.
            # Keep the portal anchor itself, world art, camera rules, and saved
            # facing authority untouched.
            if saved_return is not None:
                safe = _sanitize_era_state(saved_return, stack, PRESENT_TEMPORAL_ARRIVAL_HINT, facing)
                facing = safe["facing"]
            else:
                facing = 1
            target_layer, (sx, sy) = nearest_walkable_across_stack(
                stack, PRESENT_TEMPORAL_ARRIVAL_HINT, PRESENT_PRIMARY_WALK_LAYER
            )
        elif saved_return is not None:
            safe = _sanitize_era_state(saved_return, stack, past_anchor_pos, facing)
            target_layer = layer_by_number(stack, safe["walk_layer"]) or stack.walk_layers[0]
            sx, sy = safe["x"], safe["y"]
            facing = safe["facing"]
        else:
            target_layer, (sx, sy) = nearest_walkable_across_stack(
                stack, past_anchor_pos, past_anchor_walk_number or None
            )
            facing = 1

        walk_layer = target_layer
        player_x, player_y = sx, sy
        vel_x = vel_y = 0.0
        hop_timer = 0.0
        end_reached = False
        depth_switch_timer = 0.0
        cam_x, cam_y = sx, sy - 40
        era_states[destination_world] = {
            "x": sx, "y": sy, "walk_layer": walk_layer.number, "facing": facing
        }
        transition_phase = "time_shift"
        transition_timer = TIME_SHIFT_IN
        guidance_pending_after_transition = _normalize_guidance_mode(settings.get("guidance_mode", "context")) != "off"
        reset_weather_for_world()
        if not safe_mode:
            exploration_sfx.play_cue("lantern_resonance", 0.78)

    def save_game(slot: int = 1) -> bool:
        nonlocal current_save_slot
        store_era_state()
        payload = {
            "version": 5,
            "world": world_key,
            "walk_layer": walk_layer.number,
            "player": {"x": round(player_x, 3), "y": round(player_y, 3), "facing": facing},
            "eras": era_states,
            "temporal_returns": temporal_return_states,
            "entity": {
                "id": ENTITY_ID,
                "x": round(entity_pos[0], 3),
                "y": round(entity_pos[1], 3),
                "walk_layer": entity_walk_number,
                "met": bool(guardian_dialogue_states[ENTITY_ID]["met"]),
                "declined_count": int(guardian_dialogue_states[ENTITY_ID]["declined_count"]),
                "defeated": entity_defeated,
            },
            "entity_states": {
                guardian_id: {
                    "x": round(float(guardian_positions.get(guardian_id, (0.0, 0.0))[0]), 3),
                    "y": round(float(guardian_positions.get(guardian_id, (0.0, 0.0))[1]), 3),
                    "walk_layer": int(guardian_walk_numbers.get(guardian_id, 0)),
                    "met": bool(guardian_dialogue_states.get(guardian_id, {}).get("met", False)),
                    "declined_count": int(guardian_dialogue_states.get(guardian_id, {}).get("declined_count", 0)),
                    "defeated": guardian_id in defeated_boss_ids,
                }
                for guardian_id in MEMORY_GUARDIAN_ORDER
            },
            "ghosts": {
                "sable": {
                    "met": bool(sable_met),
                    "world": "b",
                    "future_status": SABLE_FUTURE_STATUS,
                },
            },
            "machines": {
                "bits": int(clamp_bits(machine_bits)),
                "inventory": {key: clamp_machine_stack(machine_inventory.get(key, 0)) for key in machine_catalog},
                "next_id": int(max(1, machine_next_id)),
                "placed": [
                    {
                        "id": int(item["id"]),
                        "part": str(item["part"]),
                        "world": str(item["world"]),
                        "walk_layer": int(item["walk_layer"]),
                        "x": round(float(item["x"]), 3),
                        "y": round(float(item["y"]), 3),
                        "angle": round(float(item.get("angle", 0.0)) % 360.0, 3),
                        "flip_x": bool(item.get("flip_x", False)),
                        **({"attach_phase": round(float(item.get("attach_phase", 0.0)) % 360.0, 3)} if "attach_phase" in item else {}),
                        **({"attach_local_dx": round(float(item.get("attach_local_dx", 0.0)), 3), "attach_local_dy": round(float(item.get("attach_local_dy", 0.0)), 3)} if "attach_local_dx" in item and "attach_local_dy" in item else {}),
                        **({"pipe_anchor_end": normalize_pipe_end(item.get("pipe_anchor_end"))} if "pipe_anchor_end" in item else {}),
                        **({"pipe_hinge_id": int(item.get("pipe_hinge_id"))} if item.get("pipe_hinge_id") is not None else {}),
                        **({"pipe_orbit_dir": int(item.get("pipe_orbit_dir", 1))} if "pipe_orbit_dir" in item else {}),
                        **({"pipe_brace_id": int(item.get("pipe_brace_id"))} if item.get("pipe_brace_id") is not None else {}),
                        **({"pipe_brace_local_dx": round(float(item.get("pipe_brace_local_dx", 0.0)), 3), "pipe_brace_local_dy": round(float(item.get("pipe_brace_local_dy", 0.0)), 3)} if "pipe_brace_local_dx" in item and "pipe_brace_local_dy" in item else {}),
                        **({"pipe_brace_angle": round(float(item.get("pipe_brace_angle", 0.0)) % 360.0, 3)} if "pipe_brace_angle" in item else {}),
                    }
                    for item in machine_placements[:MAX_MACHINE_PLACEMENTS]
                ],
            },
            "causality": {
                "shrine_manifested": entity_defeated,
                "shrine_activated": shrine_activated,
                "rooted_crown_shrine": {
                    "x": round(rooted_crown_shrine_pos[0], 3),
                    "y": round(rooted_crown_shrine_pos[1], 3),
                    "walk_layer": rooted_crown_shrine_walk_number,
                    "activated": rooted_crown_shrine_activated,
                },
                "veil_warden_shrine": {
                    "x": round(veil_warden_shrine_pos[0], 3),
                    "y": round(veil_warden_shrine_pos[1], 3),
                    "walk_layer": veil_warden_shrine_walk_number,
                    "activated": veil_warden_shrine_activated,
                },
                "guardian_shrines": {
                    guardian_id: {
                        "x": round(float(additional_shrine_positions.get(guardian_id, WORLD_A_START)[0]), 3),
                        "y": round(float(additional_shrine_positions.get(guardian_id, WORLD_A_START)[1]), 3),
                        "walk_layer": int(additional_shrine_walk_numbers.get(guardian_id, 4)),
                        "activated": bool(additional_shrine_activated.get(guardian_id, False)),
                    }
                    for guardian_id in ADDITIONAL_SHRINE_IDS
                },
            },
            "progression": {
                "discovered_clues": ([FUTURE_CLUE_ID] if future_clue_discovered else []) + ([ROOTED_CROWN_FUTURE_CLUE_ID] if rooted_crown_clue_discovered else []),
                "learned_abilities": ([CAUSAL_RESONANCE_ABILITY] if causal_resonance_learned else []) + ([VEIL_WARD_ABILITY] if veil_ward_learned else []) + ([LANTERN_PROJECTION_ABILITY] if lantern_projection_learned else []) + ([REMOTE_RESONANCE_ABILITY] if remote_resonance_learned else []) + ([ENTROPY_ARC_ABILITY] if entropy_arc_learned else []) + ([PROJECTION_LANCE_ABILITY] if projection_lance_learned else []),
                "challenge_wins": {guardian_id: int(rematch_wins.get(guardian_id, 0)) for guardian_id in MEMORY_GUARDIAN_ORDER},
                "lantern_projection_level": int(lantern_projection_upgrade_level),
                "shrine_unlocks": ([ENTITY_ID] if shrine_activated else []) + ([ROOTED_CROWN_ID] if rooted_crown_shrine_activated else []) + ([VEIL_WARDEN_ID] if veil_warden_shrine_activated else []) + [guardian_id for guardian_id in ADDITIONAL_SHRINE_IDS if additional_shrine_activated.get(guardian_id, False)],
                "campaign_complete": bool(game_completed),
                "defeated_entities": sorted(defeated_boss_ids),
                "discovered_lore": sorted(discovered_lore),
                "completed_story_arcs": [FIRST_WITNESS_STORY_ARC] if first_witness_echoes_complete else [],
                "witnessed_story_moments": sorted(witnessed_story_moments),
            },
            "camera": {"zoom": round(zoom, 3)},
            "saved_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            _atomic_write_json(_save_path(slot), payload)
            current_save_slot = max(1, min(SAVE_SLOT_COUNT, int(slot)))
            return True
        except OSError:
            return False

    def load_game(slot: int = 1) -> bool:
        nonlocal world_key, stack, walk_layer, player_x, player_y, facing, zoom, vel_x, vel_y, cam_x, cam_y, hop_timer, end_reached, depth_switch_timer, transition_phase, transition_timer, entity_pos, entity_walk_number, entity_defeated, entity_met, entity_declined_count, defeated_boss_ids, shrine_activated, future_clue_discovered, causal_resonance_learned, veil_ward_learned, veil_ward_timer, veil_ward_cooldown, lantern_projection_learned, lantern_projection_upgrade_level, lantern_projection_active, lantern_projection_timer, lantern_projection_x, lantern_projection_y, lantern_projection_dir, lantern_projection_integrity, remote_resonance_learned, remote_resonance_timer, entropy_arc_learned, entropy_arc_mastery, battle_entropy_arc_cooldown, projection_lance_learned, projection_lance_mastery, projection_lance_cooldown, rematch_wins, discovered_lore, first_witness_echoes_complete, lore_card_timer, lore_archive_open, era_states, temporal_return_states, rooted_crown_pos, rooted_crown_walk_number, rooted_crown_defeated, rooted_crown_met, rooted_crown_declined_count, rooted_crown_shrine_pos, rooted_crown_shrine_walk_number, rooted_crown_shrine_activated, rooted_crown_clue_discovered, veil_warden_pos, veil_warden_walk_number, veil_warden_defeated, veil_warden_met, veil_warden_declined_count, veil_warden_shrine_pos, veil_warden_shrine_walk_number, veil_warden_shrine_activated, witnessed_story_moments, story_moment_id, story_moment_page, pending_story_moment, sable_met, machine_bits, machine_inventory, machine_placements, machine_next_id, machine_build_mode, machine_pending_part, machine_drag_id, machine_drag_origin, machine_hotbar_flash_key, machine_hotbar_flash_timer, bits_notice, bits_notice_timer, guardian_dialogue_states, additional_shrine_activated, game_completed, ending_open, ending_page, ending_selected, current_save_slot
        data = _load_manual_slot(slot)
        key = str(data.get("world", ""))
        if key not in stacks:
            return False
        loaded_eras = data.get("eras") if isinstance(data.get("eras"), dict) else None
        if loaded_eras:
            for era_key in ("a", "b"):
                if era_key not in stacks or not stacks[era_key].walk_layers:
                    continue
                state = loaded_eras.get(era_key)
                if isinstance(state, dict):
                    fallback = WORLD_A_START if era_key == "a" else WORLD_B_ENTRY_HINT
                    era_states[era_key] = _sanitize_era_state(state, stacks[era_key], fallback)
        # Terminal return points originated in save schema v4. Older saves simply
        # have no snapshots and therefore use the authored anchor on first crossing.
        temporal_return_states = {"a": None, "b": None}
        loaded_returns = data.get("temporal_returns") if isinstance(data.get("temporal_returns"), dict) else {}
        for era_key in ("a", "b"):
            if era_key not in stacks or not stacks[era_key].walk_layers:
                continue
            state = temporal_return_candidate(loaded_returns, era_key)
            if state is None:
                continue
            fallback = future_anchor_pos if era_key == "a" else past_anchor_pos
            temporal_return_states[era_key] = _sanitize_era_state(
                state, stacks[era_key], fallback
            )

        ghosts = data.get("ghosts") if isinstance(data.get("ghosts"), dict) else {}
        sable_state = ghosts.get("sable") if isinstance(ghosts.get("sable"), dict) else {}
        sable_met = bool(sable_state.get("met", sable_met))

        ent = data.get("entity") if isinstance(data.get("entity"), dict) else {}
        try:
            entity_pos = (float(ent.get("x", entity_pos[0])), float(ent.get("y", entity_pos[1])))
            entity_walk_number = int(ent.get("walk_layer", entity_walk_number))
            entity_defeated = bool(ent.get("defeated", False))
            entity_met = bool(ent.get("met", entity_met))
            entity_declined_count = max(0, min(999, int(ent.get("declined_count", entity_declined_count))))
        except (TypeError, ValueError, OverflowError):
            pass
        progression = data.get("progression") if isinstance(data.get("progression"), dict) else {}
        defeated_boss_ids = normalize_defeated_boss_ids(
            progression.get("defeated_entities"), entity_defeated
        )
        entity_defeated = entity_defeated or ENTITY_ID in defeated_boss_ids
        entity_states = data.get("entity_states") if isinstance(data.get("entity_states"), dict) else {}
        rooted_state = entity_states.get(ROOTED_CROWN_ID) if isinstance(entity_states.get(ROOTED_CROWN_ID), dict) else {}
        try:
            rooted_crown_pos = (float(rooted_state.get("x", rooted_crown_pos[0])), float(rooted_state.get("y", rooted_crown_pos[1])))
            rooted_crown_walk_number = int(rooted_state.get("walk_layer", rooted_crown_walk_number))
            rooted_crown_met = bool(rooted_state.get("met", rooted_crown_met))
            rooted_crown_declined_count = max(0, min(999, int(rooted_state.get("declined_count", rooted_crown_declined_count))))
            rooted_crown_defeated = bool(rooted_state.get("defeated", False)) or ROOTED_CROWN_ID in defeated_boss_ids
        except (TypeError, ValueError, OverflowError):
            rooted_crown_defeated = ROOTED_CROWN_ID in defeated_boss_ids
        veil_state = entity_states.get(VEIL_WARDEN_ID) if isinstance(entity_states.get(VEIL_WARDEN_ID), dict) else {}
        try:
            veil_warden_pos = (float(veil_state.get("x", veil_warden_pos[0])), float(veil_state.get("y", veil_warden_pos[1])))
            veil_warden_walk_number = int(veil_state.get("walk_layer", veil_warden_walk_number))
            veil_warden_met = bool(veil_state.get("met", veil_warden_met))
            veil_warden_declined_count = max(0, min(999, int(veil_state.get("declined_count", veil_warden_declined_count))))
            veil_warden_defeated = bool(veil_state.get("defeated", False)) or VEIL_WARDEN_ID in defeated_boss_ids
        except (TypeError, ValueError, OverflowError):
            veil_warden_defeated = VEIL_WARDEN_ID in defeated_boss_ids
        guardian_dialogue_states = {guardian_id: {"met": False, "declined_count": 0} for guardian_id in MEMORY_GUARDIAN_ORDER}
        guardian_dialogue_states[ENTITY_ID] = {"met": bool(entity_met), "declined_count": int(entity_declined_count)}
        guardian_dialogue_states[ROOTED_CROWN_ID] = {"met": bool(rooted_crown_met), "declined_count": int(rooted_crown_declined_count)}
        guardian_dialogue_states[VEIL_WARDEN_ID] = {"met": bool(veil_warden_met), "declined_count": int(veil_warden_declined_count)}
        for guardian_id in ADDITIONAL_SHRINE_IDS:
            raw_state = entity_states.get(guardian_id) if isinstance(entity_states.get(guardian_id), dict) else {}
            try:
                guardian_dialogue_states[guardian_id] = {
                    "met": bool(raw_state.get("met", False)),
                    "declined_count": max(0, min(999, int(raw_state.get("declined_count", 0)))),
                }
            except (TypeError, ValueError, OverflowError):
                guardian_dialogue_states[guardian_id] = {"met": False, "declined_count": 0}
        causality = data.get("causality") if isinstance(data.get("causality"), dict) else {}
        shrine_activated = bool(causality.get("shrine_activated", False)) if entity_defeated else False
        rooted_shrine = causality.get("rooted_crown_shrine") if isinstance(causality.get("rooted_crown_shrine"), dict) else {}
        try:
            rooted_crown_shrine_pos = (float(rooted_shrine.get("x", rooted_crown_shrine_pos[0])), float(rooted_shrine.get("y", rooted_crown_shrine_pos[1])))
            rooted_crown_shrine_walk_number = int(rooted_shrine.get("walk_layer", rooted_crown_shrine_walk_number))
        except (TypeError, ValueError, OverflowError):
            pass
        rooted_crown_shrine_activated = bool(rooted_shrine.get("activated", False)) if rooted_crown_defeated else False
        veil_shrine = causality.get("veil_warden_shrine") if isinstance(causality.get("veil_warden_shrine"), dict) else {}
        try:
            veil_warden_shrine_pos = (float(veil_shrine.get("x", veil_warden_shrine_pos[0])), float(veil_shrine.get("y", veil_warden_shrine_pos[1])))
            veil_warden_shrine_walk_number = int(veil_shrine.get("walk_layer", veil_warden_shrine_walk_number))
        except (TypeError, ValueError, OverflowError):
            pass
        veil_warden_shrine_activated = bool(veil_shrine.get("activated", False)) if veil_warden_defeated else False
        loaded_guardian_shrines = causality.get("guardian_shrines") if isinstance(causality.get("guardian_shrines"), dict) else {}
        additional_shrine_activated = {guardian_id: False for guardian_id in ADDITIONAL_SHRINE_IDS}
        for guardian_id in ADDITIONAL_SHRINE_IDS:
            raw_shrine = loaded_guardian_shrines.get(guardian_id) if isinstance(loaded_guardian_shrines.get(guardian_id), dict) else {}
            if raw_shrine:
                try:
                    additional_shrine_positions[guardian_id] = (
                        float(raw_shrine.get("x", additional_shrine_positions.get(guardian_id, WORLD_A_START)[0])),
                        float(raw_shrine.get("y", additional_shrine_positions.get(guardian_id, WORLD_A_START)[1])),
                    )
                    additional_shrine_walk_numbers[guardian_id] = int(raw_shrine.get("walk_layer", additional_shrine_walk_numbers.get(guardian_id, 4)))
                except (TypeError, ValueError, OverflowError):
                    pass
            additional_shrine_activated[guardian_id] = bool(raw_shrine.get("activated", False)) if guardian_id in defeated_boss_ids else False
        game_completed = bool(progression.get("campaign_complete", False))
        ending_open = False
        ending_page = 0
        ending_selected = 0
        # Pass 85 migration: Guardian obelisks use the new fixed nonlinear Past
        # field even when loading older saves that stored sequential encounter positions.
        if guardian_positions:
            entity_pos = guardian_positions.get(ENTITY_ID, entity_pos)
            entity_walk_number = guardian_walk_numbers.get(ENTITY_ID, entity_walk_number)
            rooted_crown_pos = guardian_positions.get(ROOTED_CROWN_ID, rooted_crown_pos)
            rooted_crown_walk_number = guardian_walk_numbers.get(ROOTED_CROWN_ID, rooted_crown_walk_number)
            veil_warden_pos = guardian_positions.get(VEIL_WARDEN_ID, veil_warden_pos)
            veil_warden_walk_number = guardian_walk_numbers.get(VEIL_WARDEN_ID, veil_warden_walk_number)
        discovered_clue_ids = {str(v) for v in progression.get("discovered_clues", [])} if isinstance(progression.get("discovered_clues"), list) else set()
        rooted_crown_clue_discovered = ROOTED_CROWN_FUTURE_CLUE_ID in discovered_clue_ids
        future_clue_discovered, causal_resonance_learned = normalize_progression_state(
            progression,
            shrine_activated,
        )
        learned_ids = learned_ability_ids(progression, shrine_activated, rooted_crown_shrine_activated, entity_defeated, veil_warden_shrine_activated)
        veil_ward_learned = VEIL_WARD_ABILITY in learned_ids
        lantern_projection_learned = LANTERN_PROJECTION_ABILITY in learned_ids
        try:
            lantern_projection_upgrade_level = max(0, min(LANTERN_PROJECTION_MAX_LEVEL, int(progression.get("lantern_projection_level", 0))))
        except (TypeError, ValueError, OverflowError):
            lantern_projection_upgrade_level = 0
        raw_wins = progression.get("challenge_wins") if isinstance(progression.get("challenge_wins"), dict) else {}
        rematch_wins = {}
        for rematch_id in MEMORY_GUARDIAN_ORDER:
            try:
                rematch_wins[rematch_id] = max(0, int(raw_wins.get(rematch_id, 0)))
            except (TypeError, ValueError, OverflowError):
                rematch_wins[rematch_id] = 0
        machine_state = data.get("machines") if isinstance(data.get("machines"), dict) else None
        if machine_state is None:
            machine_bits = migrated_legacy_bits(
                defeated_boss_ids, raw_wins, final_guardian_id=FINAL_GUARDIAN_ID
            )
            machine_inventory = sanitize_machine_inventory(None, valid_part_keys=set(machine_catalog))
            machine_placements = []
            machine_next_id = 1
        else:
            machine_bits = clamp_bits(machine_state.get("bits", 0))
            machine_inventory = sanitize_machine_inventory(machine_state.get("inventory"), valid_part_keys=set(machine_catalog))
            machine_placements = sanitize_machine_placements(
                machine_state.get("placed"),
                valid_part_keys=set(machine_catalog),
                world_width=WORLD_SIZE[0],
                world_height=WORLD_SIZE[1],
            )
            try:
                stored_next = int(machine_state.get("next_id", 1))
            except (TypeError, ValueError, OverflowError):
                stored_next = 1
            max_existing = max((int(item["id"]) for item in machine_placements), default=0)
            machine_next_id = max(1, stored_next, max_existing + 1)
        machine_build_mode = False
        machine_pending_part = None
        machine_drag_id = None
        machine_drag_origin = None
        machine_hotbar_flash_key = None
        machine_hotbar_flash_timer = 0.0
        bits_notice = ""
        bits_notice_timer = 0.0
        total_echo_wins = sum(rematch_wins.values())
        remote_resonance_learned = (REMOTE_RESONANCE_ABILITY in learned_ids) or remote_resonance_level(total_echo_wins) >= 1
        entropy_arc_mastery = entropy_arc_level(total_echo_wins)
        if ENTROPY_ARC_ABILITY in learned_ids and entropy_arc_mastery < 1:
            entropy_arc_mastery = 1
        entropy_arc_learned = entropy_arc_mastery >= 1
        projection_lance_mastery = projection_lance_level(total_echo_wins, veil_warden_shrine_activated)
        if PROJECTION_LANCE_ABILITY in learned_ids and projection_lance_mastery < 1:
            projection_lance_mastery = 1
        projection_lance_learned = projection_lance_mastery >= 1
        projection_lance_cooldown = 0.0
        battle_entropy_arc_cooldown = 0
        remote_resonance_timer = 0.0
        lantern_projection_active = False
        lantern_projection_timer = 0.0
        lantern_projection_x, lantern_projection_y = player_x, player_y
        lantern_projection_dir = pygame.Vector2(float(facing), 0.0)
        lantern_projection_integrity = LANTERN_PROJECTION_INTEGRITY
        projection_enemy_drones.clear()
        projection_enemy_shots.clear()
        projection_lance_shots.clear()
        veil_ward_timer = 0.0
        veil_ward_cooldown = 0.0
        discovered_lore, first_witness_echoes_complete = normalize_lore_progression(progression)
        first_witness_echoes_complete = bool(first_witness_echoes_complete and shrine_activated)
        witnessed_story_moments = normalize_story_moments(progression.get("witnessed_story_moments"))
        story_moment_id = ""
        story_moment_page = 0
        pending_story_moment = ""
        lore_card_timer = 0.0
        lore_archive_open = False
        if "b" in stacks and stacks["b"].walk_layers:
            entity_layer = layer_by_number(stacks["b"], entity_walk_number)
            if entity_layer is None or not entity_layer.walk:
                entity_layer = stacks["b"].walk_layers[0]
                entity_walk_number = entity_layer.number
            try:
                ex, ey = entity_pos
                if not math.isfinite(ex) or not math.isfinite(ey):
                    raise ValueError("non-finite entity position")
                entity_pos = nearest_walkable_point(entity_layer, (ex, ey))
            except (TypeError, ValueError, OverflowError):
                entity_pos = nearest_walkable_point(entity_layer, WORLD_B_ENTRY_HINT)
        player = data.get("player", {}) if isinstance(data.get("player"), dict) else {}
        try:
            wx = float(player.get("x"))
            wy = float(player.get("y"))
            wanted_number = int(data.get("walk_layer"))
        except (TypeError, ValueError):
            return False
        candidate = layer_by_number(stacks[key], wanted_number)
        if candidate is None or not candidate.walk:
            candidate = stacks[key].walk_layers[0]
        sx, sy = nearest_walkable_point(candidate, (wx, wy))
        world_key = key
        stack = stacks[key]
        walk_layer = candidate
        player_x, player_y = sx, sy
        facing = -1 if int(player.get("facing", 1)) < 0 else 1
        era_states[key] = {"x": player_x, "y": player_y, "walk_layer": walk_layer.number, "facing": facing}
        try:
            zoom = clamp(float(data.get("camera", {}).get("zoom", DEFAULT_ZOOM)), MIN_ZOOM, MAX_ZOOM)
        except (TypeError, ValueError, AttributeError):
            zoom = DEFAULT_ZOOM
        vel_x = vel_y = 0.0
        hop_timer = 0.0
        end_reached = False
        depth_switch_timer = 0.0
        transition_phase = "none"
        transition_timer = 0.0
        cam_x, cam_y = player_x, player_y - 40
        reset_weather_for_world()
        current_save_slot = max(1, min(SAVE_SLOT_COUNT, int(slot)))
        return True

    def save_settings() -> None:
        settings["fullscreen"] = bool(fullscreen)
        settings["guidance_mode"] = _normalize_guidance_mode(settings.get("guidance_mode", "context"))
        try:
            _atomic_write_json(_settings_path(), settings)
        except OSError:
            pass

    def set_guidance_notice(*, duration: float = 7.0) -> None:
        nonlocal guidance_notice, guidance_notice_timer, guidance_idle_timer, guidance_idle_cooldown
        if _normalize_guidance_mode(settings.get("guidance_mode", "context")) == "off":
            return
        guidance_notice = continuity_thread_line(world_key, defeated_boss_ids)
        guidance_notice_timer = max(guidance_notice_timer, float(duration))
        guidance_idle_timer = 0.0
        guidance_idle_cooldown = max(guidance_idle_cooldown, 45.0)

    def refresh_presentation_preferences() -> None:
        nonlocal font, small, menu_font, title_font, gleebs_option_font, dev_coord_font
        _apply_presentation_preferences(settings)
        font, small, menu_font, title_font = load_menu_fonts(settings["text_style"] == "clear")
        gleebs_option_font = load_gleebs_option_font(settings["text_style"] == "clear")
        dev_coord_font = _load_menu_font("small_font.ttf", 11, sys_name="Liberation Mono")

    def place_machine_hotbar_slot(slot_index: int) -> bool:
        nonlocal machine_inventory, machine_next_id, machine_hotbar_flash_key, machine_hotbar_flash_timer
        nonlocal causal_notice, causal_notice_timer
        parts = _primary_machine_parts(machine_catalog)
        if slot_index < 0 or slot_index >= len(parts):
            return False
        part = parts[slot_index]
        count = clamp_machine_stack(machine_inventory.get(part.key, 0))
        machine_hotbar_flash_key = part.key
        machine_hotbar_flash_timer = 0.85
        if count <= 0:
            causal_notice = f"NO {part.name} // BUY ONE FROM SABLE"; causal_notice_timer = 1.8; return False
        if len(machine_placements) >= MAX_MACHINE_PLACEMENTS:
            causal_notice = "MACHINE PLACEMENT LIMIT REACHED."; causal_notice_timer = 2.0; return False
        spawn_x = clamp(player_x + (74.0 if facing >= 0 else -74.0), MACHINE_WORLD_MARGIN, WORLD_SIZE[0] - MACHINE_WORLD_MARGIN)
        spawn_y = clamp(player_y - 18.0, MACHINE_WORLD_MARGIN, WORLD_SIZE[1] - MACHINE_WORLD_MARGIN)
        machine_placements.append({"id": machine_next_id, "part": part.key, "world": world_key, "walk_layer": walk_layer.number, "x": round(spawn_x, 3), "y": round(spawn_y, 3), "angle": 0.0, "flip_x": False})
        machine_next_id += 1
        machine_inventory, consumed = consume_machine_item(machine_inventory, part.key, 1)
        if not consumed:
            machine_placements.pop(); machine_next_id = max(1, machine_next_id - 1); return False
        causal_notice = f"{part.name} PLACED // HOLD LMB TO MOVE"; causal_notice_timer = 1.8
        return True

    def place_machine_part_key(part_key: str) -> bool:
        nonlocal machine_inventory, machine_next_id, machine_hotbar_flash_key, machine_hotbar_flash_timer
        nonlocal causal_notice, causal_notice_timer
        part = machine_catalog.get(str(part_key))
        if part is None:
            return False
        count = clamp_machine_stack(machine_inventory.get(part.key, 0))
        machine_hotbar_flash_key = part.key
        machine_hotbar_flash_timer = 0.85
        if count <= 0:
            causal_notice = f"NO {part.name} IN INVENTORY"; causal_notice_timer = 1.6; return False
        if len(machine_placements) >= MAX_MACHINE_PLACEMENTS:
            causal_notice = "MACHINE PLACEMENT LIMIT REACHED."; causal_notice_timer = 2.0; return False
        spawn_x = clamp(player_x + (74.0 if facing >= 0 else -74.0), MACHINE_WORLD_MARGIN, WORLD_SIZE[0] - MACHINE_WORLD_MARGIN)
        spawn_y = clamp(player_y - 18.0, MACHINE_WORLD_MARGIN, WORLD_SIZE[1] - MACHINE_WORLD_MARGIN)
        machine_placements.append({"id": machine_next_id, "part": part.key, "world": world_key, "walk_layer": walk_layer.number, "x": round(spawn_x, 3), "y": round(spawn_y, 3), "angle": 0.0, "flip_x": False})
        machine_next_id += 1
        machine_inventory, consumed = consume_machine_item(machine_inventory, part.key, 1)
        if not consumed:
            machine_placements.pop(); machine_next_id = max(1, machine_next_id - 1); return False
        causal_notice = f"{part.name} PLACED // HOLD LMB TO MOVE"; causal_notice_timer = 1.5
        return True

    def cycle_machine_inventory(direction: int) -> None:
        nonlocal machine_inventory_selected
        parts = _owned_machine_parts(machine_catalog, machine_inventory)
        if not parts:
            machine_inventory_selected = 0
            return
        machine_inventory_selected = (machine_inventory_selected + (1 if direction > 0 else -1)) % len(parts)

    def selected_machine_part() -> MachinePartDef | None:
        parts = _owned_machine_parts(machine_catalog, machine_inventory)
        if not parts:
            return None
        index = max(0, min(len(parts) - 1, machine_inventory_selected))
        return parts[index]

    def machine_hit_id_at(point: tuple[int, int] | None) -> int | None:
        if point is None:
            return None
        return next((instance_id for instance_id, rect in reversed(machine_screen_rects) if rect.collidepoint(point)), None)

    def flip_machine_at(point: tuple[int, int] | None) -> bool:
        nonlocal causal_notice, causal_notice_timer
        hit_id = machine_hit_id_at(point)
        if hit_id is None:
            causal_notice = "MACHINE FOCUS // AIM AT A PLACED PART"
            causal_notice_timer = 1.2
            return False
        for item in machine_placements:
            if int(item.get("id", -1)) != int(hit_id):
                continue
            item["flip_x"] = not bool(item.get("flip_x", False))
            causal_notice = "TELEKINESIS // HORIZONTAL FLIP"
            causal_notice_timer = 1.2
            return True
        # The permanent Core is intentionally not part of machine_placements.
        causal_notice = "PERMANENT CORE // TRANSFORM LOCKED"
        causal_notice_timer = 1.2
        return False

    def reclaim_machine_at(point: tuple[int, int] | None) -> bool:
        nonlocal machine_inventory, machine_drag_id, machine_drag_origin
        nonlocal machine_hotbar_flash_key, machine_hotbar_flash_timer, causal_notice, causal_notice_timer
        hit_id = machine_hit_id_at(point)
        if hit_id is None:
            causal_notice = "MACHINE FOCUS // AIM AT A PLACED PART"
            causal_notice_timer = 1.2
            return False
        for index, item in enumerate(machine_placements):
            if int(item.get("id", -1)) != int(hit_id):
                continue
            part_key = str(item.get("part", ""))
            if clamp_machine_stack(machine_inventory.get(part_key, 0)) >= MAX_MACHINE_STACK:
                causal_notice = "INVENTORY STACK FULL // PIECE LEFT IN WORLD"
                causal_notice_timer = 1.8
                return False
            machine_inventory = add_machine_item(machine_inventory, part_key, 1)
            machine_placements.pop(index)
            if machine_drag_id == hit_id:
                machine_drag_id = None
                machine_drag_origin = None
            machine_hotbar_flash_key = part_key
            machine_hotbar_flash_timer = 0.9
            causal_notice = "MACHINE PIECE RETURNED TO IO INVENTORY"
            causal_notice_timer = 1.8
            return True
        causal_notice = "PERMANENT CORE // RECLAIM LOCKED"
        causal_notice_timer = 1.2
        return False

    def _machine_items_for_interaction() -> list[dict]:
        """Machine instances that may consume the in-world E interaction.

        This intentionally includes the permanent Core Housing.  Machine interaction
        is resolved before Gleebs/Sable/Guardian dialogue so pressing E on machinery
        can never fall through into an unrelated menu.
        """
        static_items = [_permanent_core_item()] if PERMANENT_CORE_PART_KEY in machine_catalog else []
        return machine_placements + static_items

    def nearest_machine_for_interaction() -> tuple[dict, MachinePartDef, float] | None:
        candidates: list[tuple[float, dict, MachinePartDef]] = []
        for item in _machine_items_for_interaction():
            part = machine_catalog.get(str(item.get("part", "")))
            if part is None:
                continue
            if str(item.get("world", "")) != world_key or int(item.get("walk_layer", -999)) != walk_layer.number:
                continue
            try:
                distance = pygame.Vector2(player_x, player_y).distance_to((float(item.get("x", 0.0)), float(item.get("y", 0.0))))
            except (TypeError, ValueError, OverflowError):
                continue
            if distance <= MACHINE_WORKSHOP_INTERACT_RADIUS:
                candidates.append((distance, item, part))
        if not candidates:
            return None
        distance, item, part = min(candidates, key=lambda entry: entry[0])
        return item, part, distance

    def nearest_machine_head_for_interaction() -> tuple[dict, MachinePartDef, float] | None:
        candidates: list[tuple[float, dict, MachinePartDef]] = []
        for item in _machine_items_for_interaction():
            part = machine_catalog.get(str(item.get("part", "")))
            if part is None or part.role != ROLE_HEAD:
                continue
            if str(item.get("world", "")) != world_key or int(item.get("walk_layer", -999)) != walk_layer.number:
                continue
            try:
                distance = pygame.Vector2(player_x, player_y).distance_to((float(item.get("x", 0.0)), float(item.get("y", 0.0))))
            except (TypeError, ValueError, OverflowError):
                continue
            if distance <= MACHINE_HEAD_INTERACT_RADIUS:
                candidates.append((distance, item, part))
        if not candidates:
            return None
        distance, item, part = min(candidates, key=lambda entry: entry[0])
        return item, part, distance

    def _machine_diagnostic_assembly(head_item: dict) -> tuple[list[dict], dict[int, dict[str, object]]]:
        """Return the physically connected assembly rooted at a HEAD part.

        Diagnostic grouping is deliberately read-only. It never rewrites machine
        placements or the established drive graph; it only follows parts that
        physically overlap/touch in the same era and walk layer.
        """
        items = _machine_items_for_interaction()
        if not items:
            return [], {}
        network = resolve_machine_network(
            items,
            part_roles={key: part.role for key, part in machine_catalog.items()},
            part_touch_radii={key: part.touch_radius for key, part in machine_catalog.items()},
            contact_points_by_id={
                int(item.get("id", -1)): _machine_explicit_snap_positions(item, machine_catalog[str(item.get("part", ""))])
                for item in items
                if str(item.get("part", "")) in machine_catalog
                and _machine_part_explicit_snap_points(machine_catalog[str(item.get("part", ""))])
            },
            accessory_contact_points_by_id={
                int(item.get("id", -1)): _machine_target_snap_positions(item, machine_catalog[str(item.get("part", ""))])
                for item in items
                if str(item.get("part", "")) in machine_catalog
            },
            exclude_ids=({machine_drag_id} if machine_drag_id is not None else set()),
        )
        by_id: dict[int, dict] = {}
        for item in items:
            try:
                by_id[int(item.get("id", -1))] = item
            except (TypeError, ValueError, OverflowError):
                continue
        try:
            root_id = int(head_item.get("id", -1))
        except (TypeError, ValueError, OverflowError):
            return [], network
        if root_id not in by_id:
            return [], network

        def touching(left: dict, right: dict) -> bool:
            if str(left.get("world", "")) != str(right.get("world", "")):
                return False
            if int(left.get("walk_layer", -999)) != int(right.get("walk_layer", -998)):
                return False
            left_part = machine_catalog.get(str(left.get("part", "")))
            right_part = machine_catalog.get(str(right.get("part", "")))
            if left_part is None or right_part is None:
                return False
            try:
                lx, ly = float(left.get("x", 0.0)), float(left.get("y", 0.0))
                rx, ry = float(right.get("x", 0.0)), float(right.get("y", 0.0))
            except (TypeError, ValueError, OverflowError):
                return False
            drive_roles = {ROLE_CORE, ROLE_GEAR, ROLE_PIVOT}
            if left_part.role in drive_roles and right_part.role in drive_roles:
                return math.hypot(lx - rx, ly - ry) <= float(left_part.touch_radius) + float(right_part.touch_radius)
            left_uses_connectors = bool(_machine_part_inferred_snap_points(left_part, as_source=False)) or left_part.role == ROLE_PIPE
            right_uses_connectors = bool(_machine_part_inferred_snap_points(right_part, as_source=False)) or right_part.role == ROLE_PIPE
            if left_uses_connectors or right_uses_connectors:
                left_points = _machine_target_snap_positions(left, left_part)
                right_points = _machine_target_snap_positions(right, right_part)
                if left_points and right_points:
                    best = min(math.hypot(lpx - rpx, lpy - rpy) for lpx, lpy in left_points for rpx, rpy in right_points)
                    return best <= MACHINE_SNAP_ASSIST_RADIUS_WORLD
            return math.hypot(lx - rx, ly - ry) <= float(left_part.touch_radius) + float(right_part.touch_radius)

        visited = {root_id}
        frontier = [root_id]
        while frontier:
            current_id = frontier.pop()
            current = by_id[current_id]
            for other_id, other in by_id.items():
                if other_id in visited or other_id == current_id:
                    continue
                if touching(current, other):
                    visited.add(other_id)
                    frontier.append(other_id)
        return [by_id[instance_id] for instance_id in sorted(visited)], network

    def machine_head_dialogue_for(head_item: dict) -> tuple[tuple[str, str], ...]:
        assembly, network = _machine_diagnostic_assembly(head_item)
        roles: list[str] = []
        powered_drive = False
        present_labels: list[str] = []
        role_label = {
            ROLE_HEAD: "HEAD",
            ROLE_CORE: "CORE",
            ROLE_GEAR: "GEAR",
            ROLE_PIVOT: "PIVOT",
            ROLE_ACTUATOR: "ACTUATOR",
            ROLE_SENSOR: "SENSOR",
            ROLE_TOOL: "TOOL",
            ROLE_FAN: "FAN",
            ROLE_PIPE: "PIPE",
            ROLE_FRAME: "FRAME",
            ROLE_COSMETIC: "COSMETIC",
        }
        for item in assembly:
            part = machine_catalog.get(str(item.get("part", "")))
            if part is None:
                continue
            roles.append(part.role)
            label = role_label.get(part.role, part.role.upper())
            if label not in present_labels:
                present_labels.append(label)
            try:
                instance_id = int(item.get("id", -1))
            except (TypeError, ValueError, OverflowError):
                instance_id = -1
            state = network.get(instance_id, {})
            if part.role in {ROLE_CORE, ROLE_GEAR, ROLE_PIVOT} and bool(state.get("powered")):
                powered_drive = True
        report = autonomous_motion_requirements(roles, powered_drive=powered_drive)
        missing = [role_label.get(role, str(role).upper()) for role in report.get("missing_roles", ())]
        present_text = " // ".join(present_labels) if present_labels else "HEAD ONLY"
        if missing:
            status = "MISSING: " + " // ".join(missing)
            outcome = "HEAD: I CANNOT MOVE THIS ASSEMBLY INDEPENDENTLY YET. " + status + "."
        elif not bool(report.get("powered_drive")):
            outcome = "HEAD: ALL MOTION PARTS ARE PRESENT, BUT THE DRIVE IS OFFLINE. CORE, GEAR, AND PIVOT MUST FORM ONE POWERED CONTACT TRIANGLE."
        else:
            outcome = "HEAD: MOTION HARDWARE IS COMPLETE AND POWERED. AUTONOMOUS LOCOMOTION CONTROL IS THE NEXT SYSTEM; I WILL NOT MOVE THE ASSEMBLY UNTIL THAT CONTROL LAYER EXISTS."
        return (
            ("IO: WHAT PARTS DO YOU NEED IN ORDER TO MOVE INDEPENDENTLY?", "HEAD: CONTROL LINK ACCEPTED. I WILL AUDIT THE PARTS PHYSICALLY CONNECTED TO ME."),
            ("HEAD: REQUIRED HARDWARE: CORE // GEAR // PIVOT // ACTUATOR.", f"HEAD: CURRENT ASSEMBLY: {present_text}."),
            ("HEAD: MOBILITY DIAGNOSTIC COMPLETE.", outcome),
        )

    def nearest_powered_core_for_workshop() -> dict | None:
        items = _machine_items_for_interaction()
        if not items:
            return None
        network = resolve_machine_network(
            items,
            part_roles={key: part.role for key, part in machine_catalog.items()},
            part_touch_radii={key: part.touch_radius for key, part in machine_catalog.items()},
            contact_points_by_id={
                int(item.get("id", -1)): _machine_explicit_snap_positions(item, machine_catalog[str(item.get("part", ""))])
                for item in items
                if str(item.get("part", "")) in machine_catalog
                and _machine_part_explicit_snap_points(machine_catalog[str(item.get("part", ""))])
            },
            accessory_contact_points_by_id={
                int(item.get("id", -1)): _machine_target_snap_positions(item, machine_catalog[str(item.get("part", ""))])
                for item in items
                if str(item.get("part", "")) in machine_catalog
            },
            exclude_ids=({machine_drag_id} if machine_drag_id is not None else set()),
        )
        candidates = []
        for item in items:
            part = machine_catalog.get(str(item.get("part", "")))
            if part is None or part.role != ROLE_CORE:
                continue
            if str(item.get("world", "")) != world_key or int(item.get("walk_layer", -999)) != walk_layer.number:
                continue
            try:
                instance_id = int(item.get("id", -1))
                distance = pygame.Vector2(player_x, player_y).distance_to((float(item.get("x", 0.0)), float(item.get("y", 0.0))))
            except (TypeError, ValueError, OverflowError):
                continue
            if bool(network.get(instance_id, {}).get("powered")) and distance <= MACHINE_WORKSHOP_INTERACT_RADIUS:
                candidates.append((distance, item))
        return min(candidates, key=lambda pair: pair[0])[1] if candidates else None

    def create_custom_machine_part() -> str:
        nonlocal machine_catalog, machine_inventory, machine_inventory_selected, machine_workshop_texture
        textures = _machine_source_parts()
        if not textures:
            return "NO SOURCE ART AVAILABLE"
        texture_part = textures[machine_workshop_texture % len(textures)]
        shape = MACHINE_WORKSHOP_SHAPES[machine_workshop_shape % len(MACHINE_WORKSHOP_SHAPES)]
        role = MACHINE_WORKSHOP_ROLES[machine_workshop_role % len(MACHINE_WORKSHOP_ROLES)]
        size_name, world_height = MACHINE_WORKSHOP_SIZES[machine_workshop_size % len(MACHINE_WORKSHOP_SIZES)]
        existing = _load_machine_metadata(MACHINE_VARIANTS_CATALOG_PATH)
        used = set(existing) | set(machine_catalog)
        serial = 1
        while f"custom_part_{serial:03d}" in used:
            serial += 1
        key = f"custom_part_{serial:03d}"
        name = f"CUSTOM PART {serial:03d}"
        functions = [fn for fn in MACHINE_WORKSHOP_FUNCTIONS if fn in machine_workshop_functions] if role in MACHINE_WORKSHOP_FX_ROLES else []
        snaps = [[round(x, 4), round(y, 4)] for x, y in _sanitize_machine_snap_points(machine_workshop_snap_points)]
        touch_radius = max(12.0, min(180.0, float(world_height) * DEFAULT_MACHINE_TOUCH_RADIUS_RATIO))
        spin_dps = float(MACHINE_ROLE_DEFAULT_SPIN.get(role, 0.0))
        try:
            MACHINE_VARIANTS_DIR.mkdir(parents=True, exist_ok=True)
            surface = _machine_shape_surface(shape, texture_part.surface, 128)
            png_path = MACHINE_VARIANTS_DIR / f"{key}.png"
            pygame.image.save(surface, str(png_path))
            existing[key] = {
                "name": name,
                "cost": 1,
                "world_height": float(world_height),
                "role": role,
                "touch_radius": round(touch_radius, 3),
                "spin_dps": spin_dps,
                "description": f"CUSTOM {shape} // {MACHINE_WORKSHOP_ROLE_LABELS.get(role, role.upper())} // {size_name}",
                "shape": shape,
                "texture_source": texture_part.key,
                "functions": functions,
                "snap_points": snaps,
                "snap_schema": "normalized_uv_v1",
                "custom": True,
            }
            _atomic_write_json(MACHINE_VARIANTS_CATALOG_PATH, {"version": 2, "parts": existing})
        except (OSError, pygame.error, ValueError, TypeError) as exc:
            try:
                (MACHINE_VARIANTS_DIR / f"{key}.png").unlink(missing_ok=True)
            except OSError:
                pass
            return f"CREATE FAILED // {type(exc).__name__.upper()}"
        machine_catalog = load_machine_catalog()
        _MACHINE_RUNTIME_CATALOG.clear(); _MACHINE_RUNTIME_CATALOG.update(machine_catalog)
        machine_inventory = sanitize_machine_inventory(machine_inventory, valid_part_keys=set(machine_catalog))
        machine_inventory = add_machine_item(machine_inventory, key, 1)
        parts = _owned_machine_parts(machine_catalog, machine_inventory)
        machine_inventory_selected = next((i for i, part in enumerate(parts) if part.key == key), max(0, len(parts) - 1))
        machine_workshop_texture %= max(1, len(_machine_source_parts()))
        return f"{name} CREATED // {len(snaps)} SNAP POINTS // +1 INVENTORY"

    def execute_dev_console(command: str) -> str:
        nonlocal machine_inventory, machine_bits, machine_inventory_selected
        cleaned = " ".join(str(command).strip().split()); lowered = cleaned.lower()
        if not cleaned:
            return "TYPE help FOR COMMANDS"
        if lowered in {"help", "?"}:
            return "give all   |   give bits <amount>"
        if lowered in {"give all", "give machines", "give all machines"}:
            primary = _primary_machine_parts(machine_catalog)
            if not primary:
                return "MAIN MACHINE KIT UNAVAILABLE // CHECK assets/current/machines/catalog.json"
            # Preserve any legitimately fabricated/custom inventory, but only refill
            # the authored main kit. Raw variants are not injected into quick slots.
            machine_inventory = sanitize_machine_inventory(machine_inventory, valid_part_keys=set(machine_catalog))
            for part in primary:
                machine_inventory[part.key] = MAX_MACHINE_STACK
            all_parts = _owned_machine_parts(machine_catalog, machine_inventory)
            first_key = primary[0].key
            machine_inventory_selected = next((i for i, part in enumerate(all_parts) if part.key == first_key), 0)
            return f"MAIN MACHINE KIT LOADED // SLOTS 1-{len(primary)} // {MAX_MACHINE_STACK} EACH // VARIANTS UNCHANGED"
        if lowered.startswith("give bits"):
            pieces = lowered.split(); amount = 999
            if len(pieces) >= 3:
                try:
                    amount = max(0, int(pieces[2]))
                except (TypeError, ValueError, OverflowError):
                    return "USAGE: give bits <amount>"
            machine_bits = clamp_bits(machine_bits + amount)
            return f"IO RECEIVED {amount} BITS // TOTAL {machine_bits}"
        return "UNKNOWN COMMAND // TYPE help"

    def _controller_context() -> ControllerContext:
        modal = bool(
            start_menu_open or paused or lore_archive_open or sable_dialogue or entity_dialogue
            or shrine_dialogue or future_clue_dialogue or gleebs_dialogue or battle_active or ending_open
            or story_moment_id or dev_console_open or machine_workshop_open or machine_head_dialogue or machine_inventory_open
        )
        return ControllerContext(
            modal=modal,
            machine_focus=bool(machine_build_mode),
            projection_active=bool(lantern_projection_active),
            snap_edit=bool(machine_workshop_open and machine_workshop_snap_edit),
        )

    def _controller_mouse_event(button: int, down: bool) -> None:
        pos = _logical_to_window(window, (controller_cursor.x, controller_cursor.y))
        event_type = pygame.MOUSEBUTTONDOWN if down else pygame.MOUSEBUTTONUP
        pygame.event.post(pygame.event.Event(
            event_type, button=int(button), pos=pos, from_controller=True
        ))

    def handle_controller_action(action: str | None, *, pressed: bool = True) -> None:
        nonlocal controller_sprint_toggled, controller_hint_timer, controller_input_mode, controller_drag_active
        nonlocal causal_notice, causal_notice_timer
        if action is None:
            return
        controller_hint_timer = 2.0
        controller_input_mode = True
        if not pressed:
            if action == "machine_grab" and controller_drag_active:
                _controller_mouse_event(1, False)
                controller_drag_active = False
            return
        key_map = {
            "confirm": pygame.K_RETURN,
            "interact": pygame.K_e,
            "back": pygame.K_ESCAPE,
            "pause": pygame.K_ESCAPE,
            "hop": pygame.K_SPACE,
            "projection": pygame.K_TAB,
            "veil_ward": pygame.K_q,
            "causal_resonance": pygame.K_r,
            "archive": pygame.K_l,
            "inventory": pygame.K_i,
            "help": pygame.K_F1,
            "machine_focus": pygame.K_t,
            "ui_up": pygame.K_UP,
            "ui_down": pygame.K_DOWN,
            "ui_left": pygame.K_LEFT,
            "ui_right": pygame.K_RIGHT,
        }
        if action in key_map:
            _post_key(key_map[action], from_controller=True)
            return
        if action == "machine_prev":
            if machine_build_mode:
                _post_key(pygame.K_LEFT, from_controller=True)
            return
        if action == "machine_next":
            if machine_build_mode:
                _post_key(pygame.K_RIGHT, from_controller=True)
            return
        if action == "sprint_toggle":
            controller_sprint_toggled = not controller_sprint_toggled
            causal_notice = f"SPRINT TOGGLE {'ON' if controller_sprint_toggled else 'OFF'}"
            causal_notice_timer = 1.0
            return
        if action == "machine_grab":
            if machine_build_mode:
                _controller_mouse_event(1, True)
                controller_drag_active = True
            return
        if action == "machine_flip":
            if machine_build_mode:
                flip_machine_at((int(controller_cursor.x), int(controller_cursor.y)))
            return
        if action == "machine_reclaim":
            if machine_build_mode:
                reclaim_machine_at((int(controller_cursor.x), int(controller_cursor.y)))
            return

    running = True
    _early_log("MAIN entering frame loop")
    first_frame_logged = False
    while running:
        dt = min(1 / 20, clock.tick(FPS) / 1000.0)
        atmosphere_time += dt
        if not paused and transition_phase == "none" and world_key == "a":
            if present_cloud_shadow_timer > 0.0 and present_cloud_shadow_duration > 0.0:
                present_cloud_shadow_timer = max(0.0, present_cloud_shadow_timer - dt)
                progress = 1.0 - (present_cloud_shadow_timer / max(0.001, present_cloud_shadow_duration))
                pulse = math.sin(progress * math.pi)
                present_cloud_shadow_alpha = present_cloud_shadow_peak_alpha * max(0.0, pulse)
            else:
                present_cloud_shadow_alpha = 0.0
                present_cloud_shadow_wait -= dt
                if present_cloud_shadow_wait <= 0.0:
                    present_cloud_shadow_duration = present_cloud_shadow_rng.uniform(*PRESENT_CLOUD_SHADOW_DURATION_RANGE)
                    present_cloud_shadow_timer = present_cloud_shadow_duration
                    present_cloud_shadow_peak_alpha = present_cloud_shadow_rng.uniform(*PRESENT_CLOUD_SHADOW_ALPHA_RANGE)
                    present_cloud_shadow_wait = present_cloud_shadow_rng.uniform(*PRESENT_CLOUD_SHADOW_IDLE_RANGE)
        elif world_key != "a":
            present_cloud_shadow_alpha = 0.0
        if battle_fx_timer > 0.0:
            battle_fx_timer = max(0.0, battle_fx_timer - dt)
            if battle_fx_timer <= 0.0:
                battle_fx_kind = ""
        if battle_guardian_fx_timer > 0.0:
            battle_guardian_fx_timer = max(0.0, battle_guardian_fx_timer - dt)
            if battle_guardian_fx_timer <= 0.0:
                battle_guardian_fx_kind = ""
        if boss_damage_fx:
            _update_boss_damage_fx(boss_damage_fx, dt)
        if battle_victory_timer > 0.0:
            battle_victory_timer = max(0.0, battle_victory_timer - dt)
            if battle_victory_timer <= 0.0 and battle_active:
                if battle_rematch:
                    rematch_wins[battle_entity_id] = int(rematch_wins.get(battle_entity_id, 0)) + 1
                    total_echo_wins = sum(int(value) for value in rematch_wins.values())
                    newly_remote = (not remote_resonance_learned and remote_resonance_level(total_echo_wins) >= 1)
                    remote_deepened = (remote_resonance_level(total_echo_wins) >= 2 and remote_resonance_level(total_echo_wins - 1) < 2)
                    previous_arc_mastery = entropy_arc_mastery
                    entropy_arc_mastery = entropy_arc_level(total_echo_wins)
                    old_lance_level = projection_lance_mastery
                    projection_lance_mastery = projection_lance_level(total_echo_wins, veil_warden_shrine_activated)
                    projection_lance_learned = projection_lance_mastery >= 1
                    newly_entropy_arc = (not entropy_arc_learned and entropy_arc_mastery >= 1)
                    entropy_arc_mastered = (entropy_arc_mastery >= 2 and previous_arc_mastery < 2)
                    if newly_remote:
                        remote_resonance_learned = True
                    if newly_entropy_arc:
                        entropy_arc_learned = True
                    previous_level = lantern_projection_upgrade_level
                    lantern_projection_upgrade_level = min(LANTERN_PROJECTION_MAX_LEVEL, lantern_projection_upgrade_level + 1)
                    duration = lantern_projection_duration(lantern_projection_upgrade_level)
                    if newly_entropy_arc:
                        causal_notice = "ENTROPY ARC LEARNED // BATTLE POWER // ORGANIC LIGHT CUTS THE ECHO."
                    elif entropy_arc_mastered:
                        causal_notice = "ENTROPY ARC MASTERED // FOCUS CAN STRENGTHEN THE ARC."
                    elif newly_remote:
                        causal_notice = f"REMOTE RESONANCE LEARNED // R WHILE PROJECTING // {duration:.0f} SECOND WINDOW."
                    elif remote_deepened:
                        causal_notice = f"REMOTE RESONANCE DEEPENED // LONGER REACH // {duration:.0f} SECOND WINDOW."
                    elif lantern_projection_upgrade_level > previous_level:
                        causal_notice = f"LANTERN PROJECTION EXTENDED // {duration:.0f} SECONDS."
                    else:
                        causal_notice = f"ECHO CHALLENGE CLEARED // PROJECTION MASTERED AT {duration:.0f} SECONDS."
                    causal_notice_timer = 3.5
                    battle_message = f"{_battle_name_for(battle_entity_id)} yields to the stronger echo challenge."
                else:
                    if battle_entity_id == VEIL_WARDEN_ID:
                        veil_warden_defeated = True
                        defeated_boss_ids.add(VEIL_WARDEN_ID)
                        battle_message = "The Veil Warden releases its Archive of Separation."
                        causal_notice = "MEMORY ARCHIVE RETRIEVED // SEPARATION."
                    elif battle_entity_id == ROOTED_CROWN_ID:
                        rooted_crown_defeated = True
                        defeated_boss_ids.add(ROOTED_CROWN_ID)
                        battle_message = "The Rooted Crown releases its Archive of Return."
                        causal_notice = "MEMORY ARCHIVE RETRIEVED // RETURN."
                    elif battle_entity_id == ENTITY_ID:
                        entity_defeated = True
                        defeated_boss_ids.add(ENTITY_ID)
                        lantern_projection_learned = True
                        battle_message = "The First Witness releases its Archive of Origin."
                        causal_notice = "MEMORY ARCHIVE RETRIEVED // ORIGIN. LANTERN PROJECTION LEARNED."
                    else:
                        defeated_boss_ids.add(battle_entity_id)
                        battle_message = f"{_battle_name_for(battle_entity_id)} releases its sealed civilization memory."
                        if battle_entity_id == FINAL_GUARDIAN_ID:
                            causal_notice = "THE FINAL CIVILIZATION ARCHIVE IS OPEN."
                        else:
                            causal_notice = f"MEMORY ARCHIVE RETRIEVED // {_battle_name_for(battle_entity_id)}."
                    if battle_entity_id in ARCHIVE_ATTUNEMENTS and not battle_rematch:
                        attune_name, attune_effect = ARCHIVE_ATTUNEMENTS[battle_entity_id]
                        causal_notice = f"{causal_notice}  {attune_name}: {attune_effect}"
                    if set(MEMORY_GUARDIAN_ORDER).issubset(defeated_boss_ids):
                        causal_notice = "ALL LOST CIVILIZATION ARCHIVES RETRIEVED. RETURN TO GLEEBS FOR LIFE."
                    live_progress = mode_host.Progress(
                        guardians=len(defeated_boss_ids & set(MEMORY_GUARDIAN_ORDER)), campaign_complete=game_completed
                    )
                    holoverse_link.note_progress(live_progress.guardians, live_progress.campaign_complete)
                    newly_open = [
                        spec for spec in mode_host.MODES
                        if spec.mode_id not in modes_unlocked and mode_host.is_unlocked(spec, live_progress)
                    ]
                    if newly_open:
                        modes_unlocked = sorted(set(modes_unlocked) | {spec.mode_id for spec in newly_open})
                        settings["unlocked_modes"] = list(modes_unlocked)
                        save_settings()
                        names = " + ".join(spec.title for spec in newly_open)
                        causal_notice = f"{causal_notice}  //  MODE UNLOCKED: {names} (TITLE > MODES)"
                    causal_notice_timer = 4.2
                bits_gained = victory_bits(
                    rematch=battle_rematch, final_guardian=(battle_entity_id == FINAL_GUARDIAN_ID)
                )
                machine_bits = clamp_bits(machine_bits + bits_gained)
                bits_notice = f"+{bits_gained} BITS   •   TOTAL {machine_bits}"
                bits_notice_timer = 3.2
                battle_active = False
                entity_dialogue = False
                battle_return_state = None
                battle_fx_kind = ""
                battle_fx_timer = 0.0
                boss_damage_fx.clear()
                store_era_state()
                battle_rematch = False
                battle_challenge_tier = 0
                battle_entropy_arc_cooldown = 0
                if not safe_mode:
                    battle_sfx.play("victory")
                    ambient_playlist.play_exploration()
        hop_pressed = False
        hop_timer = max(0.0, hop_timer - dt)
        end_message_timer = max(0.0, end_message_timer - dt)
        depth_switch_timer = max(0.0, depth_switch_timer - dt)
        pause_status_timer = max(0.0, pause_status_timer - dt)
        start_menu_status_timer = max(0.0, start_menu_status_timer - dt)
        causal_notice_timer = max(0.0, causal_notice_timer - dt)
        bits_notice_timer = max(0.0, bits_notice_timer - dt)
        machine_hotbar_flash_timer = max(0.0, machine_hotbar_flash_timer - dt)
        dev_console_status_timer = max(0.0, dev_console_status_timer - dt)
        resonance_pulse_timer = max(0.0, resonance_pulse_timer - dt)
        remote_resonance_timer = max(0.0, remote_resonance_timer - dt)
        resonance_cooldown = max(0.0, resonance_cooldown - dt)
        veil_ward_timer = max(0.0, veil_ward_timer - dt)
        veil_ward_cooldown = max(0.0, veil_ward_cooldown - dt)
        if lantern_projection_active:
            lantern_projection_timer = max(0.0, lantern_projection_timer - dt)
            if lantern_projection_timer <= 0.0:
                lantern_projection_active = False
                projection_enemy_drones.clear()
                projection_enemy_shots.clear()
                projection_lance_shots.clear()
                causal_notice = "LANTERN PROJECTION RECALLED."
                causal_notice_timer = 0.9
        resonance_notice_timer = max(0.0, resonance_notice_timer - dt)
        lore_card_timer = max(0.0, lore_card_timer - dt)
        if pause_status_timer <= 0.0:
            pause_status = ""
        if start_menu_status_timer <= 0.0:
            start_menu_status = ""
        if causal_notice_timer <= 0.0:
            causal_notice = ""
        if bits_notice_timer <= 0.0:
            bits_notice = ""
        if machine_hotbar_flash_timer <= 0.0:
            machine_hotbar_flash_key = None
        if dev_console_status_timer <= 0.0:
            dev_console_status = ""
        if resonance_notice_timer <= 0.0:
            resonance_notice = ""
        if transition_phase != "none" and not paused and not start_menu_open:
            transition_timer = max(0.0, transition_timer - dt)

        controller_hint_timer = max(0.0, controller_hint_timer - dt)
        guidance_notice_timer = max(0.0, guidance_notice_timer - dt)
        guidance_idle_cooldown = max(0.0, guidance_idle_cooldown - dt)
        if not controller_bridge.connected:
            controller_sprint_toggled = False
        cursor_axis_x, cursor_axis_y = controller_bridge.cursor_axes() if controller_bridge.connected else (0.0, 0.0)
        if abs(cursor_axis_x) > 0.001 or abs(cursor_axis_y) > 0.001:
            controller_hint_timer = 2.0
            controller_input_mode = True
            controller_cursor.x = clamp(controller_cursor.x + cursor_axis_x * CONTROLLER_CURSOR_SPEED * dt, 0.0, W - 1.0)
            controller_cursor.y = clamp(controller_cursor.y + cursor_axis_y * CONTROLLER_CURSOR_SPEED * dt, 0.0, H - 1.0)
            pointer_context = bool(
                machine_build_mode or machine_workshop_open or machine_head_dialogue or start_menu_open or paused or lore_archive_open
                or sable_dialogue or entity_dialogue or shrine_dialogue or future_clue_dialogue
                or gleebs_dialogue or battle_active or ending_open or story_moment_id
            )
            if pointer_context:
                try:
                    pygame.mouse.set_pos(_logical_to_window(window, (controller_cursor.x, controller_cursor.y)))
                except pygame.error:
                    pass

        for event in pygame.event.get():
            ambient_playlist.handle_event(event)
            if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEWHEEL):
                guidance_idle_timer = 0.0
            if controller_bridge.device_event(event):
                if controller_drag_active:
                    _controller_mouse_event(1, False)
                    controller_drag_active = False
                controller_hint_timer = 2.0 if controller_bridge.connected else 0.0
                if not controller_bridge.connected:
                    controller_input_mode = False
                controller_sprint_toggled = False
                continue
            controller_down_name = controller_bridge.button_name(event, down=True)
            if controller_down_name is not None:
                handle_controller_action(controller_button_action(controller_down_name, _controller_context()), pressed=True)
                continue
            controller_up_name = controller_bridge.button_name(event, down=False)
            if controller_up_name is not None:
                if controller_up_name == "x" and controller_drag_active:
                    handle_controller_action("machine_grab", pressed=False)
                else:
                    handle_controller_action(controller_button_action(controller_up_name, _controller_context()), pressed=False)
                continue
            controller_hat_names = controller_bridge.hat_actions(event)
            if controller_hat_names:
                for controller_hat_name in controller_hat_names:
                    handle_controller_action(controller_button_action(controller_hat_name, _controller_context()), pressed=True)
                continue
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE and not fullscreen:
                # Pygame 2 automatically resizes a RESIZABLE display surface.
                # Re-calling set_mode() here can corrupt/recreate the Windows
                # presentation path, so only remember the new window size.
                windowed_size = (max(MIN_WINDOW[0], int(event.w)), max(MIN_WINDOW[1], int(event.h)))
                current = pygame.display.get_surface()
                if current is not None:
                    window = current
            elif event.type == pygame.TEXTINPUT and dev_console_open:
                if event.text not in {"`", "~"} and len(dev_console_text) < 72:
                    dev_console_text += event.text
            elif event.type == pygame.MOUSEMOTION:
                point = _window_to_logical(window, event.pos)
                if point is not None and not sable_dialogue:
                    source_for_mouse = shared_camera_rect(cam_x, cam_y, zoom)
                    world_point = screen_to_world_shared(point[0], point[1], source_for_mouse)
                    if machine_drag_id is not None:
                        for item in machine_placements:
                            if int(item.get("id", -1)) == machine_drag_id:
                                part_def = machine_catalog.get(str(item.get("part", "")))
                                if part_def is not None:
                                    snapped = _machine_snap_assist_position(
                                        part_def, world_point, machine_placements + ([_permanent_core_item()] if PERMANENT_CORE_PART_KEY in machine_catalog else []),
                                        machine_catalog, moving_id=machine_drag_id, angle=float(item.get("angle", 0.0)), flip_x=bool(item.get("flip_x", False))
                                    )
                                    item["x"], item["y"] = snapped
                                    if part_def.role == ROLE_PIPE:
                                        _clear_pipe_constraints(item)
                                else:
                                    item["x"], item["y"] = world_point
                                break
                    elif machine_build_mode and machine_pending_part is not None:
                        part_def = machine_catalog.get(machine_pending_part)
                        machine_pending_pos = _machine_snap_assist_position(
                            part_def, world_point, machine_placements + ([_permanent_core_item()] if PERMANENT_CORE_PART_KEY in machine_catalog else []), machine_catalog
                        ) if part_def is not None else world_point
                if machine_workshop_open:
                    if machine_workshop_snap_edit and machine_workshop_snap_drag is not None and point is not None and machine_workshop_preview_rect is not None:
                        rect = machine_workshop_preview_rect
                        if rect.width > 0 and rect.height > 0:
                            u = max(0.0, min(1.0, (point[0] - rect.left) / rect.width))
                            v = max(0.0, min(1.0, (point[1] - rect.top) / rect.height))
                            if 0 <= machine_workshop_snap_drag < len(machine_workshop_snap_points):
                                machine_workshop_snap_points[machine_workshop_snap_drag] = (u, v)
                                machine_workshop_snap_selected = machine_workshop_snap_drag
                    else:
                        index = _rect_index_at(machine_workshop_hit_rects, point)
                        if index is not None:
                            machine_workshop_row = index
                elif start_menu_open:
                    if start_menu_screen == "main":
                        index = _rect_index_at(start_menu_hit_rects, point)
                        if index is not None and _start_menu_item_enabled(index, continue_slot is not None):
                            start_menu_selected = index
                    elif start_menu_screen == "modes":
                        index = _rect_index_at(modes_hit_rects, point)
                        if index is not None:
                            modes_selected = index
                    elif start_menu_screen == "load":
                        index = _rect_index_at(slot_hit_rects, point)
                        if index is not None:
                            save_slot_selected = index
                    elif start_menu_screen == "settings":
                        for index, (row, _, _) in enumerate(settings_hit_controls):
                            if point is not None and row.collidepoint(point):
                                settings_selected = index
                                break
                elif ending_open:
                    index = _rect_index_at(ending_hit_rects, point)
                    if index is not None:
                        ending_selected = index
                elif sable_dialogue:
                    index = _rect_index_at(sable_hit_rects, point)
                    if index is not None:
                        if sable_dialogue_mode == "menu":
                            sable_dialogue_selected = index
                        elif sable_dialogue_mode == "shop":
                            parts = _finished_machine_parts(machine_catalog)
                            if parts:
                                visible_count = min(6, len(parts))
                                start_index = max(0, min(sable_shop_selected - visible_count // 2, len(parts) - visible_count))
                                sable_shop_selected = min(len(parts) - 1, start_index + index)
                elif battle_active:
                    index = _rect_index_at(battle_hit_rects, point)
                    if index is not None:
                        battle_selected = index
                elif entity_dialogue:
                    index = _rect_index_at(dialogue_hit_rects, point)
                    if index is not None:
                        entity_choice = index
                elif shrine_dialogue:
                    index = _rect_index_at(dialogue_hit_rects, point)
                    if index is not None:
                        shrine_choice = index
                elif gleebs_dialogue:
                    index = _rect_index_at(dialogue_hit_rects, point)
                    if index is not None:
                        gleebs_dialogue_selected = index
                elif future_clue_dialogue:
                    index = _rect_index_at(dialogue_hit_rects, point)
                    if index is not None:
                        future_clue_choice = index
                elif paused:
                    if pause_screen == "main":
                        index = _rect_index_at(pause_menu_hit_rects, point)
                        if index is not None:
                            pause_selected = index
                    elif pause_screen in ("save", "load"):
                        index = _rect_index_at(slot_hit_rects, point)
                        if index is not None:
                            save_slot_selected = index
                    elif pause_screen == "settings":
                        for index, (row, _, _) in enumerate(settings_hit_controls):
                            if point is not None and row.collidepoint(point):
                                settings_selected = index
                                break
                    elif pause_screen == "quit":
                        index = _rect_index_at(quit_hit_rects, point)
                        if index is not None:
                            quit_selected = index
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not bool(getattr(event, "from_controller", False)):
                    controller_input_mode = False
                point = _window_to_logical(window, event.pos)
                dev_coord_toggle_active = bool(
                    point is not None and DEV_COORD_TOGGLE_RECT.collidepoint(point)
                    and transition_phase == "none" and not (
                        start_menu_open or paused or lore_archive_open or sable_dialogue or entity_dialogue
                        or shrine_dialogue or future_clue_dialogue or gleebs_dialogue or battle_active or ending_open
                        or story_moment_id or lantern_projection_active or dev_console_open or machine_workshop_open or machine_head_dialogue or machine_inventory_open
                    )
                )
                if dev_coord_toggle_active:
                    dev_coords_visible = not dev_coords_visible
                    continue
                if machine_workshop_open:
                    if machine_workshop_snap_edit and point is not None and machine_workshop_preview_rect is not None and machine_workshop_preview_rect.collidepoint(point):
                        rect = machine_workshop_preview_rect
                        nearest = None
                        for i, (u, v) in enumerate(machine_workshop_snap_points):
                            px = rect.left + u * rect.width; py = rect.top + v * rect.height
                            d = math.hypot(point[0] - px, point[1] - py)
                            if nearest is None or d < nearest[0]: nearest = (d, i)
                        if nearest is not None and nearest[0] <= 18.0:
                            machine_workshop_snap_selected = nearest[1]
                            machine_workshop_snap_drag = nearest[1]
                        elif len(machine_workshop_snap_points) < MACHINE_WORKSHOP_MAX_SNAPS:
                            u = max(0.0, min(1.0, (point[0] - rect.left) / max(1, rect.width)))
                            v = max(0.0, min(1.0, (point[1] - rect.top) / max(1, rect.height)))
                            machine_workshop_snap_points.append((u, v))
                            machine_workshop_snap_selected = len(machine_workshop_snap_points) - 1
                            machine_workshop_snap_drag = machine_workshop_snap_selected
                            machine_workshop_status = f"SNAP {machine_workshop_snap_selected + 1} ADDED"
                        else:
                            machine_workshop_status = f"MAX {MACHINE_WORKSHOP_MAX_SNAPS} SNAP POINTS"
                        continue
                    index = _rect_index_at(machine_workshop_hit_rects, point)
                    if index is not None:
                        machine_workshop_row = index
                        _post_key(pygame.K_RETURN)
                    continue
                machine_mouse_active = bool(point is not None and not (start_menu_open or paused or lore_archive_open or sable_dialogue or entity_dialogue or shrine_dialogue or future_clue_dialogue or gleebs_dialogue or battle_active or ending_open or story_moment_id or lantern_projection_active or dev_console_open or machine_workshop_open or machine_head_dialogue or machine_inventory_open) and not (machine_hotbar_rect is not None and machine_hotbar_rect.collidepoint(point)))
                if machine_mouse_active:
                    hit_id = next((instance_id for instance_id, rect in reversed(machine_screen_rects) if rect.collidepoint(point)), None)
                    if hit_id is not None:
                        if pygame.key.get_mods() & pygame.KMOD_CTRL:
                            for item in machine_placements:
                                if int(item.get("id", -1)) == int(hit_id):
                                    item["flip_x"] = not bool(item.get("flip_x", False))
                                    break
                            causal_notice = "TELEKINESIS // HORIZONTAL FLIP"; causal_notice_timer = 1.2
                        else:
                            machine_drag_id = int(hit_id)
                            for item in machine_placements:
                                if int(item.get("id", -1)) == machine_drag_id:
                                    machine_drag_origin = (float(item["x"]), float(item["y"])); break
                            causal_notice = "TELEKINESIS // HOLD LMB TO MOVE"; causal_notice_timer = 1.2
                        continue
                if ending_open:
                    index = _rect_index_at(ending_hit_rects, point)
                    if index is not None:
                        ending_selected = index
                    _post_key(pygame.K_RETURN)
                elif start_menu_open:
                    if start_menu_screen == "main":
                        index = _rect_index_at(start_menu_hit_rects, point)
                        if index is not None and _start_menu_item_enabled(index, continue_slot is not None):
                            start_menu_selected = index
                            _post_key(pygame.K_RETURN)
                    elif start_menu_screen == "modes":
                        index = _rect_index_at(modes_hit_rects, point)
                        if index is not None:
                            modes_selected = index
                            _post_key(pygame.K_RETURN)
                    elif start_menu_screen == "load":
                        index = _rect_index_at(slot_hit_rects, point)
                        if index is not None:
                            save_slot_selected = index
                            _post_key(pygame.K_RETURN)
                    elif start_menu_screen == "settings":
                        for index, (row, minus, plus) in enumerate(settings_hit_controls):
                            if point is None or not row.collidepoint(point):
                                continue
                            settings_selected = index
                            if minus is not None and minus.collidepoint(point):
                                _post_key(pygame.K_LEFT)
                            elif plus is not None and plus.collidepoint(point):
                                _post_key(pygame.K_RIGHT)
                            elif index >= SETTINGS_FULLSCREEN_INDEX:
                                _post_key(pygame.K_RETURN)
                            break
                    else:
                        if point is not None and _rect_index_at(controls_hit_rects, point) is not None:
                            _post_key(pygame.K_RETURN)
                elif story_moment_id:
                    _post_key(pygame.K_RETURN)
                elif battle_active:
                    index = _rect_index_at(battle_hit_rects, point)
                    if index is not None:
                        battle_selected = index
                        _post_key(pygame.K_RETURN)
                elif machine_head_dialogue:
                    _post_key(pygame.K_RETURN)
                elif sable_dialogue:
                    index = _rect_index_at(sable_hit_rects, point)
                    if sable_dialogue_mode in ("menu", "shop") and index is None:
                        pass
                    else:
                        if index is not None:
                            if sable_dialogue_mode == "menu":
                                sable_dialogue_selected = index
                            elif sable_dialogue_mode == "shop":
                                parts = _finished_machine_parts(machine_catalog)
                                if parts:
                                    visible_count = min(6, len(parts))
                                    start_index = max(0, min(sable_shop_selected - visible_count // 2, len(parts) - visible_count))
                                    sable_shop_selected = min(len(parts) - 1, start_index + index)
                        _post_key(pygame.K_RETURN)
                elif entity_dialogue:
                    index = _rect_index_at(dialogue_hit_rects, point)
                    if index is not None:
                        entity_choice = index
                        _post_key(pygame.K_RETURN)
                elif shrine_dialogue:
                    index = _rect_index_at(dialogue_hit_rects, point)
                    if index is not None:
                        shrine_choice = index
                        _post_key(pygame.K_RETURN)
                elif gleebs_dialogue:
                    index = _rect_index_at(dialogue_hit_rects, point)
                    if index is not None:
                        gleebs_dialogue_selected = index
                    _post_key(pygame.K_RETURN)
                elif future_clue_dialogue:
                    index = _rect_index_at(dialogue_hit_rects, point)
                    if index is not None:
                        future_clue_choice = index
                        _post_key(pygame.K_RETURN)
                elif paused:
                    if pause_screen == "main":
                        index = _rect_index_at(pause_menu_hit_rects, point)
                        if index is not None:
                            pause_selected = index
                            _post_key(pygame.K_RETURN)
                    elif pause_screen in ("save", "load"):
                        index = _rect_index_at(slot_hit_rects, point)
                        if index is not None:
                            save_slot_selected = index
                            _post_key(pygame.K_RETURN)
                    elif pause_screen == "settings":
                        for index, (row, minus, plus) in enumerate(settings_hit_controls):
                            if point is None or not row.collidepoint(point):
                                continue
                            settings_selected = index
                            if minus is not None and minus.collidepoint(point):
                                _post_key(pygame.K_LEFT)
                            elif plus is not None and plus.collidepoint(point):
                                _post_key(pygame.K_RIGHT)
                            elif index >= SETTINGS_FULLSCREEN_INDEX:
                                _post_key(pygame.K_RETURN)
                            break
                    elif pause_screen == "controls":
                        if point is not None and _rect_index_at(controls_hit_rects, point) is not None:
                            _post_key(pygame.K_RETURN)
                    else:
                        index = _rect_index_at(quit_hit_rects, point)
                        if index is not None:
                            quit_selected = index
                            _post_key(pygame.K_RETURN)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if machine_workshop_snap_drag is not None:
                    machine_workshop_snap_drag = None
                    continue
                if machine_drag_id is not None:
                    machine_drag_id = None
                    machine_drag_origin = None
                    causal_notice = "MACHINE PIECE ANCHORED."
                    causal_notice_timer = 1.8
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if not bool(getattr(event, "from_controller", False)):
                    controller_input_mode = False
                point = _window_to_logical(window, event.pos)
                if machine_head_dialogue:
                    machine_head_dialogue = False
                    machine_head_dialogue_page = 0
                    continue
                if machine_workshop_open:
                    if machine_workshop_snap_edit:
                        if point is not None and machine_workshop_preview_rect is not None and machine_workshop_preview_rect.collidepoint(point) and machine_workshop_snap_points:
                            rect = machine_workshop_preview_rect
                            nearest = min(
                                ((math.hypot(point[0] - (rect.left + u * rect.width), point[1] - (rect.top + v * rect.height)), i) for i, (u, v) in enumerate(machine_workshop_snap_points)),
                                default=None
                            )
                            if nearest is not None and nearest[0] <= 22.0:
                                machine_workshop_snap_points.pop(nearest[1])
                                machine_workshop_snap_selected = max(0, min(machine_workshop_snap_selected, len(machine_workshop_snap_points) - 1))
                                machine_workshop_status = "SNAP POINT REMOVED"
                                continue
                        machine_workshop_snap_edit = False
                        machine_workshop_snap_drag = None
                        machine_workshop_status = "SNAP EDIT CLOSED"
                    else:
                        machine_workshop_open = False
                        machine_workshop_status = ""
                    continue
                machine_mouse_active = bool(point is not None and not (start_menu_open or paused or lore_archive_open or sable_dialogue or entity_dialogue or shrine_dialogue or future_clue_dialogue or gleebs_dialogue or battle_active or ending_open or story_moment_id or lantern_projection_active or dev_console_open or machine_workshop_open or machine_head_dialogue or machine_inventory_open) and not (machine_hotbar_rect is not None and machine_hotbar_rect.collidepoint(point)))
                reclaimed = False
                if machine_mouse_active:
                    hit_id = next((instance_id for instance_id, rect in reversed(machine_screen_rects) if rect.collidepoint(point)), None)
                    if hit_id is not None:
                        for index, item in enumerate(machine_placements):
                            if int(item.get("id", -1)) != int(hit_id):
                                continue
                            part_key = str(item.get("part", ""))
                            if clamp_machine_stack(machine_inventory.get(part_key, 0)) >= MAX_MACHINE_STACK:
                                causal_notice = "INVENTORY STACK FULL // PIECE LEFT IN WORLD"
                                causal_notice_timer = 1.8
                                reclaimed = True
                                break
                            machine_inventory = add_machine_item(machine_inventory, part_key, 1)
                            machine_placements.pop(index)
                            if machine_drag_id == hit_id:
                                machine_drag_id = None; machine_drag_origin = None
                            machine_hotbar_flash_key = part_key; machine_hotbar_flash_timer = 0.9
                            causal_notice = "MACHINE PIECE RETURNED TO IO INVENTORY"
                            causal_notice_timer = 1.8
                            reclaimed = True
                            break
                if reclaimed:
                    continue
                if machine_build_mode and machine_pending_part is not None:
                    machine_pending_part = None
                    causal_notice = "MACHINE PLACEMENT CANCELED // NO BITS SPENT"
                    causal_notice_timer = 2.1
            elif event.type == pygame.MOUSEWHEEL:
                controller_input_mode = False
                if machine_inventory_open and event.y:
                    owned_count = len(_owned_machine_parts(machine_catalog, machine_inventory))
                    page_count = max(1, math.ceil(owned_count / MACHINE_INVENTORY_PAGE_SIZE))
                    if page_count > 1:
                        machine_inventory_page = (machine_inventory_page - int(event.y)) % page_count
                    continue
                if machine_workshop_open and event.y:
                    textures = _machine_source_parts()
                    if textures:
                        machine_workshop_texture = (machine_workshop_texture - int(event.y)) % len(textures)
                    continue
                point = _window_to_logical(window, pygame.mouse.get_pos())
                if event.y and machine_hotbar_rect is not None and point is not None and machine_hotbar_rect.collidepoint(point):
                    cycle_machine_inventory(-int(event.y))
                    continue
                exploration_zoom_active = (
                    transition_phase == "none" and not start_menu_open and not paused
                    and not lore_archive_open and not sable_dialogue and not entity_dialogue and not shrine_dialogue
                    and not future_clue_dialogue and not gleebs_dialogue and not battle_active and not ending_open and not machine_head_dialogue
                )
                if exploration_zoom_active and event.y:
                    zoom = clamp(zoom + float(event.y) * ZOOM_STEP, DEFAULT_ZOOM, MAX_ZOOM)
            elif event.type == pygame.KEYDOWN:
                if not bool(getattr(event, "from_controller", False)):
                    controller_hint_timer = 0.0
                    controller_input_mode = False
                # F11 / Alt+Enter stay globally available, including while paused.
                if event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and (event.mod & pygame.KMOD_ALT)):
                    if fullscreen:
                        fullscreen = False
                        window = _create_window(False, windowed_size)
                    else:
                        try:
                            windowed_size = pygame.display.get_window_size()
                        except Exception:
                            windowed_size = window.get_size()
                        fullscreen = True
                        window = _create_window(True, windowed_size)
                    save_settings()
                    continue

                if event.key == DEV_COORD_TOGGLE_KEY and not start_menu_open and not ending_open:
                    dev_coords_visible = not dev_coords_visible
                    continue

                if event.key in DEV_CONSOLE_KEYS and not start_menu_open and not ending_open:
                    dev_console_open = not dev_console_open
                    dev_console_text = ""
                    dev_console_status = "TYPE help FOR COMMANDS" if dev_console_open else ""
                    dev_console_status_timer = 999.0 if dev_console_open else 0.0
                    try:
                        pygame.key.start_text_input() if dev_console_open else pygame.key.stop_text_input()
                    except pygame.error:
                        pass
                    vel_x = vel_y = 0.0
                    continue

                if dev_console_open:
                    if event.key == pygame.K_ESCAPE:
                        dev_console_open = False; dev_console_text = ""; dev_console_status = ""; dev_console_status_timer = 0.0
                        try:
                            pygame.key.stop_text_input()
                        except pygame.error:
                            pass
                    elif event.key == pygame.K_BACKSPACE:
                        dev_console_text = dev_console_text[:-1]
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        dev_console_status = execute_dev_console(dev_console_text); dev_console_status_timer = 999.0; dev_console_text = ""
                    continue

                if ending_open:
                    ending_pages = _escape_ending_pages()
                    final_ending_page = ending_page >= len(ending_pages) - 1
                    if final_ending_page and event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                        ending_selected = 1 - ending_selected
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if not final_ending_page:
                            ending_page += 1
                        else:
                            game_completed = True
                            holoverse_link.note_progress(len(MEMORY_GUARDIAN_ORDER), True)
                            modes_unlocked = [spec.mode_id for spec in mode_host.MODES]
                            settings["unlocked_modes"] = list(modes_unlocked)
                            save_settings()
                            if current_save_slot is not None:
                                save_game(current_save_slot)
                            ending_open = False
                            if ending_selected == 1:
                                running = False
                            else:
                                causal_notice = "CAMPAIGN COMPLETE // IO'S CONTINUITY HAS CROSSED THE VEIL."
                                causal_notice_timer = 4.0
                    continue

                if machine_workshop_open:
                    textures = _machine_source_parts()
                    if machine_workshop_snap_edit:
                        if event.key in (pygame.K_ESCAPE, pygame.K_e, pygame.K_RETURN, pygame.K_KP_ENTER):
                            machine_workshop_snap_edit = False
                            machine_workshop_snap_drag = None
                            machine_workshop_status = "SNAP EDIT SAVED IN WORKSHOP"
                        elif event.key == pygame.K_TAB and machine_workshop_snap_points:
                            machine_workshop_snap_selected = (machine_workshop_snap_selected + 1) % len(machine_workshop_snap_points)
                        elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE) and machine_workshop_snap_points:
                            machine_workshop_snap_points.pop(machine_workshop_snap_selected)
                            machine_workshop_snap_selected = max(0, min(machine_workshop_snap_selected, len(machine_workshop_snap_points) - 1))
                            machine_workshop_status = "SNAP POINT REMOVED"
                        elif event.key in (pygame.K_SPACE, pygame.K_INSERT) and len(machine_workshop_snap_points) < MACHINE_WORKSHOP_MAX_SNAPS:
                            machine_workshop_snap_points.append((0.5, 0.5))
                            machine_workshop_snap_selected = len(machine_workshop_snap_points) - 1
                            machine_workshop_status = f"SNAP {machine_workshop_snap_selected + 1} ADDED"
                        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d, pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s) and machine_workshop_snap_points:
                            u, v = machine_workshop_snap_points[machine_workshop_snap_selected]
                            step = 0.0125
                            if event.key in (pygame.K_LEFT, pygame.K_a): u -= step
                            elif event.key in (pygame.K_RIGHT, pygame.K_d): u += step
                            elif event.key in (pygame.K_UP, pygame.K_w): v -= step
                            else: v += step
                            machine_workshop_snap_points[machine_workshop_snap_selected] = (max(0.0, min(1.0, u)), max(0.0, min(1.0, v)))
                        vel_x = vel_y = 0.0
                        continue
                    if event.key in (pygame.K_ESCAPE, pygame.K_e):
                        machine_workshop_open = False
                        machine_workshop_status = ""
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        machine_workshop_row = (machine_workshop_row - 1) % 10
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        machine_workshop_row = (machine_workshop_row + 1) % 10
                    elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                        direction = -1 if event.key in (pygame.K_LEFT, pygame.K_a) else 1
                        if machine_workshop_row == 0:
                            machine_workshop_shape = (machine_workshop_shape + direction) % len(MACHINE_WORKSHOP_SHAPES)
                        elif machine_workshop_row == 1 and textures:
                            machine_workshop_texture = (machine_workshop_texture + direction) % len(textures)
                        elif machine_workshop_row == 2:
                            machine_workshop_role = (machine_workshop_role + direction) % len(MACHINE_WORKSHOP_ROLES)
                        elif machine_workshop_row == 3:
                            machine_workshop_size = (machine_workshop_size + direction) % len(MACHINE_WORKSHOP_SIZES)
                        elif machine_workshop_row == 4 and machine_workshop_snap_points:
                            machine_workshop_snap_selected = (machine_workshop_snap_selected + direction) % len(machine_workshop_snap_points)
                        elif 5 <= machine_workshop_row <= 7:
                            role = MACHINE_WORKSHOP_ROLES[machine_workshop_role % len(MACHINE_WORKSHOP_ROLES)]
                            if role in MACHINE_WORKSHOP_FX_ROLES:
                                fn = MACHINE_WORKSHOP_FUNCTIONS[machine_workshop_row - 5]
                                if fn in machine_workshop_functions: machine_workshop_functions.remove(fn)
                                else: machine_workshop_functions.add(fn)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        if machine_workshop_row == 4:
                            machine_workshop_snap_edit = True
                            machine_workshop_snap_drag = None
                            machine_workshop_status = "SNAP EDIT // CLICK ART TO ADD OR DRAG"
                        elif 5 <= machine_workshop_row <= 7:
                            role = MACHINE_WORKSHOP_ROLES[machine_workshop_role % len(MACHINE_WORKSHOP_ROLES)]
                            if role in MACHINE_WORKSHOP_FX_ROLES:
                                fn = MACHINE_WORKSHOP_FUNCTIONS[machine_workshop_row - 5]
                                if fn in machine_workshop_functions: machine_workshop_functions.remove(fn)
                                else: machine_workshop_functions.add(fn)
                            else:
                                machine_workshop_status = "MECHANICAL PROPERTY OWNS ITS MOTION"
                        elif machine_workshop_row == 8:
                            machine_workshop_status = create_custom_machine_part()
                        elif machine_workshop_row == 9:
                            machine_workshop_open = False
                            machine_workshop_status = ""
                    vel_x = vel_y = 0.0
                    continue

                if machine_head_dialogue:
                    if event.key == pygame.K_ESCAPE:
                        machine_head_dialogue = False
                        machine_head_dialogue_page = 0
                    elif event.key in (pygame.K_e, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        if machine_head_dialogue_page >= max(0, len(machine_head_dialogue_pages) - 1):
                            machine_head_dialogue = False
                            machine_head_dialogue_page = 0
                        else:
                            machine_head_dialogue_page += 1
                    vel_x = vel_y = 0.0
                    continue

                if machine_inventory_open:
                    owned_count = len(_owned_machine_parts(machine_catalog, machine_inventory))
                    page_count = max(1, math.ceil(owned_count / MACHINE_INVENTORY_PAGE_SIZE))
                    if event.key in (pygame.K_i, pygame.K_ESCAPE):
                        machine_inventory_open = False
                    elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_PAGEUP):
                        machine_inventory_page = (machine_inventory_page - 1) % page_count
                    elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_PAGEDOWN):
                        machine_inventory_page = (machine_inventory_page + 1) % page_count
                    vel_x = vel_y = 0.0
                    continue

                if start_menu_open:
                    if start_menu_screen == "main":
                        if event.key in (pygame.K_UP, pygame.K_w):
                            start_menu_selected = next_start_menu_selection(
                                start_menu_selected, -1, continue_slot is not None
                            )
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            start_menu_selected = next_start_menu_selection(
                                start_menu_selected, 1, continue_slot is not None
                            )
                        elif event.key == pygame.K_ESCAPE:
                            start_menu_selected = 5
                            start_menu_status = "PRESS ENTER TO " + holoverse_link.quit_label("QUIT")
                            start_menu_status_timer = 2.0
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if start_menu_selected == 0:
                                continue_slot = newest_manual_save_slot()
                                if continue_slot is not None and load_game(continue_slot):
                                    start_menu_open = False
                                    paused = False
                                    set_guidance_notice(duration=7.5)
                                else:
                                    continue_slot = None
                                    start_menu_status = "NO VALID MANUAL SAVE"
                                    start_menu_status_timer = 2.0
                            elif start_menu_selected == 1:
                                start_menu_open = False
                                paused = False
                                set_guidance_notice(duration=8.0)
                            elif start_menu_selected == 2:
                                start_menu_screen = "load"
                                save_slot_selected = 0
                                start_menu_status = ""
                            elif start_menu_selected == 3:
                                start_menu_screen = "modes"
                                modes_selected = 0
                                start_menu_status = ""
                            elif start_menu_selected == 4:
                                start_menu_screen = "settings"
                                settings_selected = 0
                                start_menu_status = ""
                            elif start_menu_selected == 5:
                                running = False
                    elif start_menu_screen == "modes":
                        back_index = len(mode_host.MODES)
                        if event.key == pygame.K_ESCAPE:
                            start_menu_screen = "main"
                            start_menu_status = ""
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            modes_selected = (modes_selected - 1) % (back_index + 1)
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            modes_selected = (modes_selected + 1) % (back_index + 1)
                        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                            if modes_selected >= back_index:
                                start_menu_screen = "main"
                                start_menu_status = ""
                            else:
                                spec = mode_host.MODES[modes_selected]
                                if spec.mode_id not in modes_unlocked:
                                    start_menu_status = f"LOCKED — {mode_host.progress_text(spec, modes_progress)}"
                                    start_menu_status_timer = 2.8
                                elif mode_host.find_mode_dir(spec) is None:
                                    start_menu_status = f"{spec.title} IS NOT INSTALLED IN MODES/{spec.folder.upper()}"
                                    start_menu_status_timer = 3.0
                                else:
                                    save_settings()
                                    mode_launch = spec
                                    running = False
                    elif start_menu_screen == "load":
                        if event.key == pygame.K_ESCAPE:
                            start_menu_screen = "main"
                            start_menu_status = ""
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            save_slot_selected = (save_slot_selected - 1) % (SAVE_SLOT_COUNT + 1)
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            save_slot_selected = (save_slot_selected + 1) % (SAVE_SLOT_COUNT + 1)
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if save_slot_selected == SAVE_SLOT_COUNT:
                                start_menu_screen = "main"
                                start_menu_status = ""
                            else:
                                slot = save_slot_selected + 1
                                if load_game(slot):
                                    continue_slot = slot
                                    start_menu_open = False
                                    paused = False
                                    set_guidance_notice(duration=7.5)
                                else:
                                    start_menu_status = f"SLOT {slot} IS EMPTY"
                                    start_menu_status_timer = 2.0
                    elif start_menu_screen == "settings":
                        if event.key == pygame.K_ESCAPE:
                            start_menu_screen = "main"
                            save_settings()
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            settings_selected = (settings_selected - 1) % SETTINGS_ROW_COUNT
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            settings_selected = (settings_selected + 1) % SETTINGS_ROW_COUNT
                        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                            direction = -1.0 if event.key in (pygame.K_LEFT, pygame.K_a) else 1.0
                            if settings_selected == 0:
                                settings["music_volume"] = clamp(settings["music_volume"] + direction * 0.05, 0.0, 1.0)
                                ambient_playlist.set_volume(settings["music_volume"])
                            elif settings_selected == 1:
                                settings["sfx_volume"] = clamp(settings["sfx_volume"] + direction * 0.05, 0.0, 1.0)
                                battle_sfx.set_volume(settings["sfx_volume"])
                                exploration_sfx.set_volume(settings["sfx_volume"])
                            elif settings_selected == 2:
                                settings["fog_level"] = clamp(settings["fog_level"] + direction * 0.10, 0.0, 1.5)
                            elif settings_selected == 3:
                                settings["vignette_level"] = clamp(settings["vignette_level"] + direction * 0.10, 0.0, 1.5)
                            elif settings_selected == 4:
                                settings["darkness_level"] = clamp(settings["darkness_level"] + direction * 0.10, 0.0, 1.5)
                            elif settings_selected == 5:
                                settings["text_style"] = "clear" if settings.get("text_style") != "clear" else "worn"
                                refresh_presentation_preferences()
                            elif settings_selected == 6:
                                settings["motion_fx"] = _step_level(float(settings.get("motion_fx", 1.0)), (0.35, 0.65, 1.0), direction)
                                refresh_presentation_preferences()
                            elif settings_selected == 7:
                                settings["flash_fx"] = _step_level(float(settings.get("flash_fx", 1.0)), (0.0, 0.5, 1.0), direction)
                                refresh_presentation_preferences()
                            elif settings_selected == 8:
                                settings["guidance_mode"] = _step_guidance_mode(settings.get("guidance_mode", "context"), direction)
                                if settings["guidance_mode"] == "off":
                                    guidance_notice = ""
                                    guidance_notice_timer = 0.0
                                else:
                                    set_guidance_notice(duration=6.0)
                            save_settings()
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if settings_selected == SETTINGS_FULLSCREEN_INDEX:
                                if fullscreen:
                                    fullscreen = False
                                    window = _create_window(False, windowed_size)
                                else:
                                    try:
                                        windowed_size = pygame.display.get_window_size()
                                    except Exception:
                                        windowed_size = window.get_size()
                                    fullscreen = True
                                    window = _create_window(True, windowed_size)
                                save_settings()
                            elif settings_selected == SETTINGS_CONTROLS_INDEX:
                                start_menu_screen = "controls"
                            elif settings_selected == SETTINGS_BACK_INDEX:
                                start_menu_screen = "main"
                                save_settings()
                    else:  # controls
                        if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                            start_menu_screen = "settings"
                    continue

                if story_moment_id:
                    pages = story_pages(story_moment_id)
                    if event.key == pygame.K_ESCAPE:
                        witnessed_story_moments.add(story_moment_id)
                        story_moment_id = ""
                        story_moment_page = 0
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if story_moment_page < len(pages) - 1:
                            story_moment_page += 1
                        else:
                            witnessed_story_moments.add(story_moment_id)
                            story_moment_id = ""
                            story_moment_page = 0
                    continue

                if battle_active:
                    if battle_victory_timer > 0.0:
                        # Final-hit sequence owns the chamber briefly; additional
                        # menu input cannot skip or double-commit the victory.
                        continue
                    battle_command_count = 5 if entropy_arc_learned else 4
                    battle_flee_index = battle_command_count - 1
                    battle_arc_index = 3 if entropy_arc_learned else -1
                    if event.key == pygame.K_r and causal_resonance_learned:
                        if battle_signal_verify_cooldown > 0:
                            battle_message = f"Causal Resonance is reforming // {battle_signal_verify_cooldown} turn{'s' if battle_signal_verify_cooldown != 1 else ''}."
                        elif battle_signal_verified_counter:
                            battle_message = f"Signal already verified // {battle_signal_verified_counter.upper()}."
                        else:
                            move = _battle_move_for(battle_entity_id, battle_move_index)
                            battle_signal_verified_counter = _battle_counter_class(battle_entity_id, move.key)
                            battle_signal_verify_cooldown = BATTLE_SIGNAL_VERIFY_COOLDOWN_TURNS
                            if battle_signal_was_corrupted:
                                battle_message = f"CAUSAL RESONANCE: THE MIND injection detected. True counter // {battle_signal_verified_counter.upper()}."
                            else:
                                battle_message = f"CAUSAL RESONANCE: signal authentic. Counter // {battle_signal_verified_counter.upper()}."
                            if not safe_mode:
                                battle_sfx.play("counter")
                    elif event.key == pygame.K_q and veil_ward_learned:
                        if battle_mind_ward_cooldown > 0:
                            battle_message = f"Veil Ward is reforming // {battle_mind_ward_cooldown} turn{'s' if battle_mind_ward_cooldown != 1 else ''}."
                        elif not battle_mind_interference_active:
                            battle_message = "Veil Ward finds no active Mind injection to purge."
                        else:
                            battle_mind_interference_active = False
                            battle_mind_fake_move_index = -1
                            battle_mind_ward_suppressed = True
                            battle_mind_ward_cooldown = BATTLE_MIND_WARD_COOLDOWN_TURNS
                            battle_message = "VEIL WARD: THE MIND injection collapses. Gleebs' channel clears."
                            if not safe_mode:
                                battle_sfx.play("counter")
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        battle_selected = (battle_selected - 1) % battle_command_count
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        battle_selected = (battle_selected + 1) % battle_command_count
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if battle_selected == battle_flee_index:
                            battle_active = False; battle_return_state = None; battle_message = "You withdraw from the chamber."
                            battle_rematch = False; battle_challenge_tier = 0
                            battle_entropy_arc_cooldown = 0
                            battle_fx_kind = ""; battle_fx_timer = 0.0
                            battle_guardian_fx_kind = ""; battle_guardian_fx_timer = 0.0
                            boss_damage_fx.clear()
                            if not safe_mode:
                                battle_sfx.play("flee")
                                ambient_playlist.play_exploration()
                        elif battle_selected == battle_arc_index and battle_entropy_arc_cooldown > 0:
                            battle_message = f"Entropy Arc is reforming // {battle_entropy_arc_cooldown} turn{'s' if battle_entropy_arc_cooldown != 1 else ''}."
                        else:
                            damage = 0
                            used_entropy_arc = battle_selected == battle_arc_index and entropy_arc_learned
                            player_action = "entropy_arc" if used_entropy_arc else "shot" if battle_selected == 0 else "focus" if battle_selected == 1 else "guard"
                            if battle_selected == 0:
                                damage = 1 + (1 if battle_focus > 0 else 0); battle_focus = max(0, battle_focus-1)
                                battle_message = f"Lantern light tears through the Guardian record for {damage}."
                                battle_fx_kind = "lantern_shot"; battle_fx_timer = BATTLE_FX_TIME
                                if not safe_mode: battle_sfx.play("lantern_shot")
                            elif battle_selected == 1:
                                battle_focus = min(_archive_attunement_focus_cap(defeated_boss_ids), battle_focus + 1); battle_message = "The lantern gathers a colder, brighter charge."
                                battle_fx_kind = "focus"; battle_fx_timer = BATTLE_FX_TIME
                                if not safe_mode: battle_sfx.play("focus")
                            elif battle_selected == 2:
                                battle_guard = True; battle_message = "IO braces behind the lantern's veil."
                                battle_fx_kind = "guard"; battle_fx_timer = BATTLE_FX_TIME
                                if not safe_mode: battle_sfx.play("guard")
                            elif used_entropy_arc:
                                total_echo_wins = sum(int(value) for value in rematch_wins.values())
                                arc_rule_wins = max(total_echo_wins, 5 if entropy_arc_mastery >= 2 else 3)
                                damage, focus_cost = entropy_arc_damage(arc_rule_wins, battle_focus)
                                battle_focus = max(0, battle_focus - focus_cost)
                                battle_entropy_arc_cooldown = _archive_attunement_arc_cooldown(defeated_boss_ids)
                                battle_message = f"IO bends his own entropy into an arc: {damage} Presence."
                                if focus_cost:
                                    battle_message += " Focus collapses into the cut."
                                battle_fx_kind = "entropy_arc"; battle_fx_timer = BATTLE_FX_TIME
                                if not safe_mode:
                                    battle_sfx.play("lantern_shot")
                                    battle_sfx.play("counter")
                            if not used_entropy_arc and battle_entropy_arc_cooldown > 0:
                                battle_entropy_arc_cooldown = max(0, battle_entropy_arc_cooldown - 1)
                            if damage > 0 and not safe_mode:
                                boss_hit_serial += 1
                                _spawn_boss_damage_fx(boss_damage_fx, boss_damage_fx_assets, damage, boss_hit_serial)
                                battle_sfx.play("boss_hit")
                            battle_entity_hp -= damage
                            if battle_entity_hp <= 0:
                                battle_entity_hp = 0
                                battle_victory_timer = BOSS_DEFEAT_TIME
                                battle_message = f"The final lantern strike fractures {_battle_name_for(battle_entity_id)}."
                                battle_fx_kind = ""
                                battle_fx_timer = 0.0
                                if not safe_mode:
                                    boss_hit_serial += 1
                                    _spawn_boss_shatter_fx(boss_damage_fx, boss_damage_fx_assets, boss_hit_serial)
                                    battle_sfx.play("boss_shatter")
                            else:
                                move = _battle_move_for(battle_entity_id, battle_move_index)
                                if not safe_mode:
                                    battle_sfx.play(_battle_sfx_cue_for_move(battle_entity_id, move.key))
                                response = _battle_response_for(
                                    battle_entity_id, battle_move_index, player_action, battle_guard, battle_entity_hp
                                )
                                guard_was_active = battle_guard
                                battle_guard = False
                                challenge_damage = echo_challenge_damage_bonus(battle_challenge_tier) if battle_rematch else 0
                                actual_player_damage = response.player_damage + (challenge_damage if response.player_damage > 0 else 0)
                                if guard_was_active and actual_player_damage > 0:
                                    actual_player_damage = max(0, actual_player_damage - _archive_attunement_guard_reduction(defeated_boss_ids))
                                battle_player_hp -= actual_player_damage
                                _max_resolve, _max_presence = _battle_limits_for(battle_entity_id, battle_challenge_tier, battle_upgrade_score, _archive_attunement_resolve_bonus(defeated_boss_ids))
                                battle_entity_hp = max(0, min(
                                    _max_presence, battle_entity_hp + response.entity_heal
                                ))
                                battle_guardian_fx_kind = move.key
                                battle_guardian_fx_timer = BATTLE_GUARDIAN_ATTACK_FX_TIME
                                if battle_mind_interference_active:
                                    battle_message += "  THE MIND corrupts Gleebs' signal."
                                if response.message:
                                    battle_message += "  " + response.message
                                if battle_rematch and challenge_damage > 0 and response.player_damage > 0:
                                    battle_message += f"  ECHO PRESSURE +{challenge_damage}."
                                perfect_read = (
                                    battle_signal_was_corrupted and response.countered
                                    and not battle_signal_verified_counter and not battle_mind_ward_suppressed
                                )
                                if perfect_read:
                                    focus_cap = _archive_attunement_focus_cap(defeated_boss_ids)
                                    old_focus = battle_focus
                                    battle_focus = min(focus_cap, battle_focus + PERFECT_READ_FOCUS_REWARD)
                                    if battle_focus > old_focus:
                                        battle_message += "  PERFECT READ // +1 FOCUS."
                                    else:
                                        battle_message += "  PERFECT READ // SIGNAL MASTERED."
                                if not safe_mode:
                                    if response.entity_heal > 0:
                                        battle_sfx.play("gate_heal")
                                    if response.player_damage > 0:
                                        battle_sfx.play("io_hurt")
                                    elif response.countered:
                                        battle_sfx.play("counter")
                                battle_signal_verify_cooldown = max(0, battle_signal_verify_cooldown - 1)
                                battle_mind_ward_cooldown = max(0, battle_mind_ward_cooldown - 1)
                                previous_move_index = battle_move_index
                                battle_boss_turn += 1
                                roll_next_battle_signal(previous_move_index)
                                if battle_player_hp <= 0:
                                    battle_active = False; entity_dialogue = False
                                    battle_player_hp, battle_entity_hp = _battle_limits_for(battle_entity_id, battle_challenge_tier, battle_upgrade_score, _archive_attunement_resolve_bonus(defeated_boss_ids))
                                    battle_focus = _archive_attunement_start_focus(defeated_boss_ids); battle_boss_turn = 0; battle_entropy_arc_cooldown = 0
                                    battle_signal_verify_cooldown = 0; battle_mind_ward_cooldown = 0
                                    battle_fx_kind = ""; battle_fx_timer = 0.0
                                    battle_guardian_fx_kind = ""; battle_guardian_fx_timer = 0.0
                                    battle_victory_timer = 0.0
                                    boss_damage_fx.clear()
                                    bits_lost = defeat_bits_loss(machine_bits)
                                    machine_bits = clamp_bits(machine_bits - bits_lost)
                                    if bits_lost > 0:
                                        bits_notice = f"-{bits_lost} BITS   •   TOTAL {machine_bits}"
                                        bits_notice_timer = 2.6
                                    # Story defeat returns to the Beginning; Shrine rematches return to the
                                    # Future Shrine that launched the challenge. Neither mode alters the other era.
                                    return_world = str(battle_return_state.get("world", "b")) if isinstance(battle_return_state, dict) else "b"
                                    if battle_return_state and return_world in stacks:
                                        fallback = WORLD_A_START if return_world == "a" else WORLD_B_ENTRY_HINT
                                        safe = _sanitize_era_state(battle_return_state, stacks[return_world], fallback)
                                        era_states[return_world] = safe
                                        world_key = return_world
                                        stack = stacks[return_world]
                                        walk_layer = layer_by_number(stack, safe["walk_layer"]) or stack.walk_layers[0]
                                        player_x, player_y = safe["x"], safe["y"]
                                        facing = safe["facing"]
                                        vel_x = vel_y = 0.0
                                        hop_timer = 0.0
                                        cam_x, cam_y = player_x, player_y - 40
                                    battle_return_state = None
                                    battle_message = "The Shrine echo releases IO." if battle_rematch else "The Beginning resets. The Future remains untouched."
                                    battle_rematch = False
                                    battle_challenge_tier = 0
                                    if not safe_mode:
                                        battle_sfx.play("defeat")
                                        ambient_playlist.play_exploration()
                    continue

                if sable_dialogue:
                    if event.key == pygame.K_ESCAPE:
                        if sable_dialogue_mode == "shop":
                            sable_dialogue_mode = "menu"
                            sable_shop_status = ""
                        else:
                            sable_dialogue = False
                    elif sable_dialogue_mode == "menu":
                        if event.key in (pygame.K_UP, pygame.K_w):
                            sable_dialogue_selected = (sable_dialogue_selected - 1) % 3
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            sable_dialogue_selected = (sable_dialogue_selected + 1) % 3
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if sable_dialogue_selected == 0:
                                sable_dialogue_mode = "lore"
                                sable_dialogue_first_visit = False
                                sable_dialogue_page = 0
                            elif sable_dialogue_selected == 1:
                                sable_dialogue_mode = "shop"
                                sable_shop_selected = min(sable_shop_selected, max(0, len(_finished_machine_parts(machine_catalog)) - 1))
                                sable_shop_status = ""
                            else:
                                sable_dialogue = False
                    elif sable_dialogue_mode == "shop":
                        part_count = len(_finished_machine_parts(machine_catalog))
                        if event.key in (pygame.K_UP, pygame.K_w) and part_count:
                            sable_shop_selected = (sable_shop_selected - 1) % part_count
                            sable_shop_status = ""
                        elif event.key in (pygame.K_DOWN, pygame.K_s) and part_count:
                            sable_shop_selected = (sable_shop_selected + 1) % part_count
                            sable_shop_status = ""
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and part_count:
                            part = _finished_machine_parts(machine_catalog)[sable_shop_selected]
                            owned = clamp_machine_stack(machine_inventory.get(part.key, 0))
                            if machine_bits < part.cost:
                                sable_shop_status = f"NEED {part.cost} BITS   •   YOU HAVE {machine_bits}"
                            elif owned >= MAX_MACHINE_STACK:
                                sable_shop_status = f"{part.name} STACK FULL // {MAX_MACHINE_STACK}"
                            else:
                                machine_bits = clamp_bits(machine_bits - part.cost)
                                machine_inventory = add_machine_item(machine_inventory, part.key, 1)
                                owned = clamp_machine_stack(machine_inventory.get(part.key, 0))
                                sable_shop_status = f"{part.name} ADDED TO INVENTORY   •   OWN {owned}"
                                bits_notice = f"-{part.cost} BITS   •   TOTAL {machine_bits}"; bits_notice_timer = 2.2
                                machine_hotbar_flash_key = part.key; machine_hotbar_flash_timer = 1.0
                    else:
                        pages = _sable_dialogue_pages(sable_dialogue_first_visit)
                        final_page = sable_dialogue_page >= len(pages) - 1
                        if not final_page and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            sable_dialogue_page += 1
                        elif final_page and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            sable_dialogue_mode = "menu"
                            sable_dialogue_first_visit = False
                            sable_dialogue_selected = 0
                    continue

                if entity_dialogue:
                    active_declines = int(guardian_dialogue_states.get(entity_dialogue_kind, {}).get("declined_count", 0))
                    pages = _memory_guardian_dialogue_pages(entity_dialogue_kind, entity_dialogue_first_visit, active_declines)
                    final_page = entity_dialogue_page >= len(pages) - 1
                    if event.key == pygame.K_ESCAPE:
                        entity_dialogue = False
                    elif not final_page and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        entity_dialogue_page += 1
                    elif final_page and event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                        entity_choice = 1 - entity_choice
                    elif final_page and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if entity_choice == 0:
                            entity_dialogue = False; battle_active = True; battle_selected = 0
                            battle_entity_id = entity_dialogue_kind
                            battle_rematch = battle_entity_id in defeated_boss_ids
                            battle_challenge_tier = echo_challenge_tier(rematch_wins.get(battle_entity_id, 0)) if battle_rematch else 0
                            battle_upgrade_score = _battle_upgrade_score(
                                defeated_boss_ids,
                                causal_resonance_learned=causal_resonance_learned,
                                veil_ward_learned=veil_ward_learned,
                                lantern_projection_learned=lantern_projection_learned,
                                remote_resonance_learned=remote_resonance_learned,
                                entropy_arc_learned=entropy_arc_learned,
                                projection_lance_learned=projection_lance_learned,
                                entropy_arc_mastery=entropy_arc_mastery,
                                projection_lance_mastery=projection_lance_mastery,
                                lantern_projection_upgrade_level=lantern_projection_upgrade_level,
                            )
                            battle_player_hp, battle_entity_hp = _battle_limits_for(battle_entity_id, battle_challenge_tier, battle_upgrade_score, _archive_attunement_resolve_bonus(defeated_boss_ids))
                            battle_focus = _archive_attunement_start_focus(defeated_boss_ids); battle_guard = False; battle_boss_turn = 0; battle_entropy_arc_cooldown = 0
                            battle_signal_verify_cooldown = 0; battle_mind_ward_cooldown = 0
                            battle_guardian_fx_kind = ""; battle_guardian_fx_timer = 0.0
                            roll_next_battle_signal(-1)
                            battle_victory_timer = 0.0
                            battle_return_state = {"world": world_key, "x": player_x, "y": player_y, "walk_layer": walk_layer.number, "facing": facing}
                            battle_message = (f"{_battle_name_for(battle_entity_id)} Echo Challenge tier {battle_challenge_tier}." if battle_rematch
                                              else f"{_battle_name_for(battle_entity_id)} seals the archive chamber. Choose an action.")
                            battle_fx_kind = "arrival"; battle_fx_timer = 0.85
                            boss_damage_fx.clear()
                            boss_hit_serial = 0
                            if not safe_mode:
                                battle_sfx.play("battle_enter")
                                ambient_playlist.play_battle(final_boss=(battle_entity_id == FINAL_GUARDIAN_ID))
                        else:
                            guardian_state = guardian_dialogue_states.setdefault(entity_dialogue_kind, {"met": True, "declined_count": 0})
                            guardian_state["declined_count"] = min(999, int(guardian_state.get("declined_count", 0)) + 1)
                            entity_dialogue = False
                    continue

                if shrine_dialogue:
                    active_shrine_activated = (
                        veil_warden_shrine_activated if shrine_dialogue_kind == VEIL_WARDEN_ID
                        else rooted_crown_shrine_activated if shrine_dialogue_kind == ROOTED_CROWN_ID
                        else shrine_activated if shrine_dialogue_kind == ENTITY_ID
                        else bool(additional_shrine_activated.get(shrine_dialogue_kind, False))
                    )
                    pages = _guardian_shrine_dialogue_pages(shrine_dialogue_kind, active_shrine_activated, first_witness_echoes_complete)
                    final_page = shrine_dialogue_page >= len(pages) - 1
                    if event.key == pygame.K_ESCAPE:
                        shrine_dialogue = False
                    elif not final_page and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        shrine_dialogue_page += 1
                    elif final_page and active_shrine_activated and event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                        shrine_choice = 1 - shrine_choice
                    elif final_page and active_shrine_activated and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if shrine_choice == 0:
                            battle_entity_id = shrine_dialogue_kind
                            battle_rematch = True
                            battle_challenge_tier = echo_challenge_tier(rematch_wins.get(battle_entity_id, 0))
                            battle_upgrade_score = _battle_upgrade_score(
                                defeated_boss_ids,
                                causal_resonance_learned=causal_resonance_learned,
                                veil_ward_learned=veil_ward_learned,
                                lantern_projection_learned=lantern_projection_learned,
                                remote_resonance_learned=remote_resonance_learned,
                                entropy_arc_learned=entropy_arc_learned,
                                projection_lance_learned=projection_lance_learned,
                                entropy_arc_mastery=entropy_arc_mastery,
                                projection_lance_mastery=projection_lance_mastery,
                                lantern_projection_upgrade_level=lantern_projection_upgrade_level,
                            )
                            battle_player_hp, battle_entity_hp = _battle_limits_for(battle_entity_id, battle_challenge_tier, battle_upgrade_score, _archive_attunement_resolve_bonus(defeated_boss_ids))
                            battle_focus = _archive_attunement_start_focus(defeated_boss_ids)
                            battle_guard = False
                            battle_entropy_arc_cooldown = 0
                            battle_boss_turn = 0
                            battle_signal_verify_cooldown = 0
                            battle_mind_ward_cooldown = 0
                            battle_guardian_fx_kind = ""; battle_guardian_fx_timer = 0.0
                            roll_next_battle_signal(-1)
                            battle_victory_timer = 0.0
                            battle_return_state = {"world": world_key, "x": player_x, "y": player_y, "walk_layer": walk_layer.number, "facing": facing}
                            battle_message = f"Memory Echo Challenge tier {battle_challenge_tier}. The record has learned from IO."
                            battle_fx_kind = ""
                            battle_fx_timer = 0.0
                            boss_damage_fx.clear()
                            boss_hit_serial = 0
                            shrine_dialogue = False
                            battle_active = True
                            if not safe_mode:
                                battle_sfx.play("battle_enter")
                                ambient_playlist.play_battle(final_boss=(battle_entity_id == FINAL_GUARDIAN_ID))
                        else:
                            shrine_dialogue = False
                    elif final_page and not active_shrine_activated and event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                        shrine_choice = 1 - shrine_choice
                    elif final_page and not active_shrine_activated and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if shrine_choice == 0:
                            if shrine_dialogue_kind == VEIL_WARDEN_ID:
                                veil_warden_shrine_activated = True
                                projection_lance_learned = True
                                total_echo_wins = sum(int(value) for value in rematch_wins.values())
                                projection_lance_mastery = max(1, projection_lance_level(total_echo_wins, True))
                                causal_notice = "PROJECTION LANCE LEARNED. THE VEIL'S ORIGINAL FUNCTION HAS BEEN RECOVERED."
                                if VEIL_WARDEN_REVELATION_ID not in witnessed_story_moments:
                                    pending_story_moment = VEIL_WARDEN_REVELATION_ID
                            elif shrine_dialogue_kind == ROOTED_CROWN_ID:
                                rooted_crown_shrine_activated = True
                                veil_ward_learned = True
                                veil_ward_timer = VEIL_WARD_DURATION
                                veil_ward_cooldown = VEIL_WARD_COOLDOWN
                                causal_notice = "VEIL WARD LEARNED. A THIRD RECORD ANSWERS IN THE BEGINNING."
                                if ROOTED_RECONSTRUCTION_ID not in witnessed_story_moments:
                                    pending_story_moment = ROOTED_RECONSTRUCTION_ID
                            elif shrine_dialogue_kind == ENTITY_ID:
                                shrine_activated = True
                                future_clue_discovered = True
                                causal_resonance_learned = True
                                causal_notice = "THE FIRST WITNESS IS RECORDED. THREE MEMORY ECHOES BREAK FREE."
                            else:
                                additional_shrine_activated[shrine_dialogue_kind] = True
                                guardian_name = _battle_name_for(shrine_dialogue_kind)
                                causal_notice = f"{guardian_name} IS RECORDED IN THE FUTURE. THE CAUSAL MONUMENT IS BOUND."
                            causal_notice_timer = 4.2
                            if not safe_mode: battle_sfx.play("shrine_bind")
                        shrine_dialogue = False
                    continue

                if gleebs_dialogue:
                    if gleebs_dialogue_topic == "menu":
                        labels = _gleebs_topic_labels(world_key)
                        if event.key == pygame.K_ESCAPE:
                            gleebs_dialogue = False
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            gleebs_dialogue_selected = (gleebs_dialogue_selected - 1) % len(labels)
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            gleebs_dialogue_selected = (gleebs_dialogue_selected + 1) % len(labels)
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            index = max(0, min(gleebs_dialogue_selected, len(labels) - 1))
                            topic_key = _gleebs_topic_entries(world_key)[index][0]
                            if topic_key == "leave":
                                gleebs_dialogue = False
                            else:
                                gleebs_dialogue_topic = topic_key
                            gleebs_dialogue_page = 0
                            gleebs_dialogue_selected = 0
                    else:
                        pages = _gleebs_topic_pages(
                            gleebs_dialogue_topic,
                            entity_defeated=entity_defeated,
                            shrine_activated=shrine_activated,
                            first_witness_echoes_complete=first_witness_echoes_complete,
                            rooted_crown_clue_discovered=rooted_crown_clue_discovered,
                            rooted_crown_defeated=rooted_crown_defeated,
                            rooted_crown_shrine_activated=rooted_crown_shrine_activated,
                            veil_warden_defeated=veil_warden_defeated,
                            veil_warden_shrine_activated=veil_warden_shrine_activated,
                            witnessed_story_moments=witnessed_story_moments,
                            rematch_wins=rematch_wins,
                            guardian_retrieved_count=sum(1 for guardian_id in MEMORY_GUARDIAN_ORDER if guardian_id in defeated_boss_ids),
                            defeated_boss_ids=defeated_boss_ids,
                        )
                        final_page = gleebs_dialogue_page >= len(pages) - 1
                        if event.key == pygame.K_ESCAPE:
                            gleebs_dialogue_topic = "menu"
                            gleebs_dialogue_page = 0
                            gleebs_dialogue_selected = 0
                        elif gleebs_dialogue_topic == "travel" and final_page and event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                            gleebs_dialogue_selected = 1 - gleebs_dialogue_selected
                        elif gleebs_dialogue_topic == "travel" and final_page and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if gleebs_dialogue_selected == 0:
                                destination = "b" if world_key == "a" else "a"
                                gleebs_dialogue = False
                                travel_to_anchor(destination)
                                causal_notice = "GLEEBS STABILIZES THE TEMPORAL CROSSING."
                                causal_notice_timer = 1.8
                            else:
                                gleebs_dialogue_topic = "menu"
                                gleebs_dialogue_page = 0
                                gleebs_dialogue_selected = 0
                        elif not final_page and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            gleebs_dialogue_page += 1
                        elif final_page and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            all_archives_recovered = set(MEMORY_GUARDIAN_ORDER).issubset(defeated_boss_ids)
                            if gleebs_dialogue_topic == "mission" and all_archives_recovered and not game_completed:
                                gleebs_dialogue = False
                                ending_open = True
                                ending_page = 0
                                ending_selected = 0
                                vel_x = vel_y = 0.0
                            else:
                                gleebs_dialogue_topic = "menu"
                                gleebs_dialogue_page = 0
                                gleebs_dialogue_selected = 0
                    continue
                if future_clue_dialogue:
                    pages = _rooted_crown_clue_pages() if future_clue_dialogue_kind == ROOTED_CROWN_ID else _future_clue_dialogue_pages(causal_resonance_learned)
                    final_page = future_clue_dialogue_page >= len(pages) - 1
                    if event.key == pygame.K_ESCAPE:
                        future_clue_dialogue = False
                    elif not final_page and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        future_clue_dialogue_page += 1
                    elif final_page and future_clue_dialogue_kind == ROOTED_CROWN_ID and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        rooted_crown_clue_discovered = True
                        future_clue_dialogue = False
                        causal_notice = "A NEW RECORD ANSWERS IN THE BEGINNING."
                        causal_notice_timer = 2.8
                    elif final_page and causal_resonance_learned and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        future_clue_dialogue = False
                    elif final_page and not causal_resonance_learned and event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                        future_clue_choice = 1 - future_clue_choice
                    elif final_page and not causal_resonance_learned and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if future_clue_choice == 0:
                            future_clue_discovered = True
                            causal_resonance_learned = True
                            resonance_pulse_timer = RESONANCE_PULSE_TIME
                            resonance_cooldown = resonance_cooldown_seconds(False)
                            causal_notice = "CAUSAL RESONANCE LEARNED. PRESS R TO LISTEN."
                            causal_notice_timer = 2.35
                            if not safe_mode:
                                exploration_sfx.play_cue("lantern_resonance", 0.78)
                        future_clue_dialogue = False
                    continue

                if lore_archive_open:
                    archive_count = sum(record.record_id in discovered_lore for record in LORE_RECORDS)
                    if event.key in (pygame.K_ESCAPE, pygame.K_l):
                        lore_archive_open = False
                    elif archive_count and event.key in (pygame.K_UP, pygame.K_w, pygame.K_LEFT, pygame.K_a):
                        lore_archive_index = (lore_archive_index - 1) % archive_count
                    elif archive_count and event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT, pygame.K_d):
                        lore_archive_index = (lore_archive_index + 1) % archive_count
                    continue

                if paused:
                    if pause_screen == "main":
                        if event.key == pygame.K_ESCAPE:
                            paused = False
                            pause_status = ""
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            pause_selected = (pause_selected - 1) % 5
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            pause_selected = (pause_selected + 1) % 5
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if pause_selected == 0:
                                paused = False
                            elif pause_selected == 1:
                                pause_screen = "save"
                                save_slot_selected = 0
                                pause_status = ""
                            elif pause_selected == 2:
                                pause_screen = "load"
                                save_slot_selected = 0
                                pause_status = ""
                            elif pause_selected == 3:
                                pause_screen = "settings"
                                settings_selected = 0
                            elif pause_selected == 4:
                                pause_screen = "quit"
                                quit_selected = 0
                    elif pause_screen in ("save", "load"):
                        if event.key == pygame.K_ESCAPE:
                            pause_screen = "main"
                            pause_status = ""
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            save_slot_selected = (save_slot_selected - 1) % (SAVE_SLOT_COUNT + 1)
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            save_slot_selected = (save_slot_selected + 1) % (SAVE_SLOT_COUNT + 1)
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if save_slot_selected == SAVE_SLOT_COUNT:
                                pause_screen = "main"
                                pause_status = ""
                            else:
                                slot = save_slot_selected + 1
                                if pause_screen == "save":
                                    pause_status = f"SLOT {slot} SAVED" if save_game(slot) else "SAVE FAILED"
                                else:
                                    pause_status = f"SLOT {slot} LOADED" if load_game(slot) else "EMPTY SLOT"
                                pause_status_timer = 2.0
                    elif pause_screen == "settings":
                        if event.key == pygame.K_ESCAPE:
                            pause_screen = "main"
                            save_settings()
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            settings_selected = (settings_selected - 1) % SETTINGS_ROW_COUNT
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            settings_selected = (settings_selected + 1) % SETTINGS_ROW_COUNT
                        elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                            direction = -1.0 if event.key in (pygame.K_LEFT, pygame.K_a) else 1.0
                            if settings_selected == 0:
                                settings["music_volume"] = clamp(settings["music_volume"] + direction * 0.05, 0.0, 1.0)
                                ambient_playlist.set_volume(settings["music_volume"])
                            elif settings_selected == 1:
                                settings["sfx_volume"] = clamp(settings["sfx_volume"] + direction * 0.05, 0.0, 1.0)
                                battle_sfx.set_volume(settings["sfx_volume"])
                                exploration_sfx.set_volume(settings["sfx_volume"])
                            elif settings_selected == 2:
                                settings["fog_level"] = clamp(settings["fog_level"] + direction * 0.10, 0.0, 1.5)
                            elif settings_selected == 3:
                                settings["vignette_level"] = clamp(settings["vignette_level"] + direction * 0.10, 0.0, 1.5)
                            elif settings_selected == 4:
                                settings["darkness_level"] = clamp(settings["darkness_level"] + direction * 0.10, 0.0, 1.5)
                            elif settings_selected == 5:
                                settings["text_style"] = "clear" if settings.get("text_style") != "clear" else "worn"
                                refresh_presentation_preferences()
                            elif settings_selected == 6:
                                settings["motion_fx"] = _step_level(float(settings.get("motion_fx", 1.0)), (0.35, 0.65, 1.0), direction)
                                refresh_presentation_preferences()
                            elif settings_selected == 7:
                                settings["flash_fx"] = _step_level(float(settings.get("flash_fx", 1.0)), (0.0, 0.5, 1.0), direction)
                                refresh_presentation_preferences()
                            elif settings_selected == 8:
                                settings["guidance_mode"] = _step_guidance_mode(settings.get("guidance_mode", "context"), direction)
                                if settings["guidance_mode"] == "off":
                                    guidance_notice = ""
                                    guidance_notice_timer = 0.0
                                else:
                                    set_guidance_notice(duration=6.0)
                            save_settings()
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if settings_selected == SETTINGS_FULLSCREEN_INDEX:
                                if fullscreen:
                                    fullscreen = False
                                    window = _create_window(False, windowed_size)
                                else:
                                    try:
                                        windowed_size = pygame.display.get_window_size()
                                    except Exception:
                                        windowed_size = window.get_size()
                                    fullscreen = True
                                    window = _create_window(True, windowed_size)
                                save_settings()
                            elif settings_selected == SETTINGS_CONTROLS_INDEX:
                                pause_screen = "controls"
                            elif settings_selected == SETTINGS_BACK_INDEX:
                                pause_screen = "main"
                                save_settings()
                    elif pause_screen == "controls":
                        if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                            pause_screen = "settings"
                    else:  # quit confirmation
                        if event.key == pygame.K_ESCAPE:
                            pause_screen = "main"
                            quit_selected = 0
                        elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_LEFT, pygame.K_a):
                            quit_selected = (quit_selected - 1) % 2
                        elif event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT, pygame.K_d):
                            quit_selected = (quit_selected + 1) % 2
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if quit_selected == 0:
                                pause_screen = "main"
                            else:
                                running = False
                    continue

                if lantern_projection_active:
                    if event.key == pygame.K_F1:
                        show_help = not show_help
                    elif event.key in (pygame.K_TAB, pygame.K_ESCAPE):
                        lantern_projection_active = False
                        lantern_projection_timer = 0.0
                        projection_enemy_drones.clear()
                        projection_enemy_shots.clear()
                        projection_lance_shots.clear()
                        causal_notice = "LANTERN PROJECTION RECALLED."
                        causal_notice_timer = 0.9
                    elif event.key == pygame.K_r and remote_resonance_learned:
                        if resonance_cooldown <= 0.0:
                            total_echo_wins = sum(int(value) for value in rematch_wins.values())
                            remote_resonance_timer = REMOTE_RESONANCE_PULSE_TIME
                            resonance_cooldown = resonance_cooldown_seconds(first_witness_echoes_complete)
                            resonance_notice = _projection_resonance_message(
                                world_key, (lantern_projection_x, lantern_projection_y), lore_placements,
                                discovered_lore, shrine_activated, causal_resonance_learned, first_witness_echoes_complete,
                                entity_pos, entity_defeated, rooted_crown_pos, rooted_crown_defeated,
                                rooted_crown_shrine_pos, rooted_crown_shrine_activated,
                                remote_resonance_range_scale(total_echo_wins),
                            )
                            resonance_notice_timer = 2.0
                            if not safe_mode:
                                exploration_sfx.play_cue("lantern_resonance", 0.76)
                        else:
                            resonance_notice = "REMOTE RESONANCE IS REFORMING."
                            resonance_notice_timer = 0.9
                    elif event.key == pygame.K_SPACE and projection_lance_learned and projection_lance_cooldown <= 0.0:
                        total_echo_wins = sum(int(value) for value in rematch_wins.values())
                        lance_damage, lance_cd = projection_lance_stats(total_echo_wins, veil_warden_shrine_activated)
                        if lance_damage > 0:
                            _spawn_projection_lance_shot(
                                projection_lance_shots,
                                (lantern_projection_x, lantern_projection_y),
                                lantern_projection_dir,
                            )
                            projection_lance_cooldown = lance_cd
                            if not safe_mode:
                                exploration_sfx.play_cue("lantern_resonance", 0.44)
                    continue

                if event.key == pygame.K_TAB and transition_phase == "none" and lantern_projection_learned:
                    lantern_projection_active = True
                    lantern_projection_timer = lantern_projection_duration(lantern_projection_upgrade_level)
                    lantern_projection_x = player_x + float(facing) * LANTERN_PROJECTION_LAUNCH_OFFSET
                    lantern_projection_y = player_y - 12.0
                    lantern_projection_dir = pygame.Vector2(float(facing), 0.0)
                    lantern_projection_integrity = LANTERN_PROJECTION_INTEGRITY
                    projection_enemy_shots.clear()
                    projection_lance_shots.clear()
                    projection_lance_cooldown = 0.0
                    total_echo_wins = sum(int(value) for value in rematch_wins.values())
                    projection_lance_mastery = projection_lance_level(total_echo_wins, veil_warden_shrine_activated)
                    projection_lance_learned = projection_lance_mastery >= 1
                    projection_enemy_drones[:] = _spawn_projection_enemy_drones(
                        world_key, lantern_projection_x, projection_enemy_rng, projection_drone_assets, projection_lance_mastery
                    )
                    vel_x = vel_y = 0.0
                    causal_notice = f"LANTERN PROJECTION // {lantern_projection_timer:.0f} SECOND WINDOW."
                    causal_notice_timer = 1.0
                    if not safe_mode:
                        exploration_sfx.play_cue("lantern_resonance", 0.66)
                    continue

                if event.key == pygame.K_TAB and transition_phase == "none" and not lantern_projection_learned:
                    causal_notice = "PLAYER DRONE LINK HAS NOT BEEN RECOVERED YET."
                    causal_notice_timer = 1.25
                    continue

                hotbar_keys = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6)
                if event.key in hotbar_keys and transition_phase == "none" and not lantern_projection_active:
                    place_machine_hotbar_slot(hotbar_keys.index(event.key))
                    continue

                if transition_phase == "none" and not lantern_projection_active:
                    if event.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
                        cycle_machine_inventory(-1 if event.key == pygame.K_LEFTBRACKET else 1)
                        continue
                    if machine_build_mode and event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        cycle_machine_inventory(-1 if event.key == pygame.K_LEFT else 1)
                        continue
                    if machine_build_mode and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        part = selected_machine_part()
                        if part is not None:
                            place_machine_part_key(part.key)
                        continue

                if event.key == pygame.K_i and transition_phase == "none" and not lantern_projection_active:
                    machine_inventory_open = True
                    machine_inventory_page = 0
                    machine_build_mode = False
                    machine_pending_part = None
                    machine_drag_id = None
                    machine_drag_origin = None
                    vel_x = vel_y = 0.0
                    continue

                if event.key == pygame.K_ESCAPE:
                    paused = True
                    pause_screen = "main"
                    pause_selected = 0
                    vel_x = vel_y = 0.0
                elif event.key == pygame.K_SPACE:
                    hop_pressed = True
                elif event.key == pygame.K_F1:
                    show_help = not show_help
                elif event.key == pygame.K_l and transition_phase == "none" and discovered_lore:
                    lore_archive_open = True
                    lore_archive_index = min(
                        lore_archive_index,
                        max(0, sum(record.record_id in discovered_lore for record in LORE_RECORDS) - 1),
                    )
                    vel_x = vel_y = 0.0
                elif event.key == pygame.K_r and transition_phase == "none" and causal_resonance_learned:
                    if resonance_cooldown <= 0.0:
                        resonance_pulse_timer = RESONANCE_PULSE_TIME
                        resonance_cooldown = resonance_cooldown_seconds(first_witness_echoes_complete)
                        unread_echo_pos = nearest_unread_echo_position(
                            lore_placements,
                            world_key,
                            discovered_lore,
                            shrine_activated,
                            (player_x, player_y),
                            causal_resonance_learned,
                            first_witness_echoes_complete,
                        )
                        if first_witness_echoes_complete and rooted_crown_clue_discovered and not rooted_crown_defeated and world_key == "b":
                            distance = pygame.Vector2(player_x, player_y).distance_to(rooted_crown_pos)
                            band = causal_resonance_band(distance, RESONANCE_NEAR_DISTANCE, RESONANCE_MID_DISTANCE)
                            resonance_notice = (
                                "THE ROOTED CROWN ANSWERS: NEAR." if band == "near" else
                                "THE ROOTED CROWN ANSWERS THROUGH THE DARK." if band == "middle" else
                                "A FAINT CROWNED RECORD ANSWERS."
                            )
                        elif first_witness_echoes_complete and not rooted_crown_defeated and world_key == "a":
                            distance = pygame.Vector2(player_x, player_y).distance_to(rooted_crown_shrine_pos)
                            resonance_notice = "THE SECOND ABSENCE ANSWERS: NEAR." if distance <= FUTURE_CLUE_INTERACT_RADIUS * 1.6 else "ANOTHER MISSING RECORD PULLS THROUGH THE FUTURE."
                        else:
                            resonance_notice = resonance_response_message(
                                world_key,
                                (player_x, player_y),
                                entity_pos,
                                entity_defeated,
                                shrine_activated,
                                unread_echo_pos,
                                first_witness_echoes_complete,
                            )
                        resonance_notice_timer = 2.15
                        # One optional story trace is hidden behind deliberate Resonance use
                        # near the authored Veil Thread memory debris.  It never gains a waypoint.
                        if VEIL_RESONANCE_ID not in witnessed_story_moments:
                            veil_placement = next((p for p in lore_placements if p.record.record_id == "future_veil_thread"), None)
                            if veil_placement is not None and world_key == "a":
                                veil_distance = pygame.Vector2(player_x, player_y).distance_to(veil_placement.position)
                                if veil_distance <= RESONANCE_NEAR_DISTANCE:
                                    pending_story_moment = VEIL_RESONANCE_ID
                                    resonance_notice = "THE VEIL ANSWERS WITH A THIRD IMAGE."
                                    resonance_notice_timer = 1.2
                        # Pass 63: after IO's archive abnormality is known, deliberate
                        # Resonance near the already-existing FOREIGN CORE can reveal a
                        # much later access trace from Gleebs.  No new prop or waypoint.
                        if (ARCHIVE_DENSITY_ID in witnessed_story_moments
                                and HOLOVERSE_SEED_ID not in witnessed_story_moments):
                            foreign_core = next((p for p in lore_placements if p.record.record_id == "future_foreign_core"), None)
                            if foreign_core is not None and world_key == "a":
                                core_distance = pygame.Vector2(player_x, player_y).distance_to(foreign_core.position)
                                if core_distance <= RESONANCE_NEAR_DISTANCE:
                                    pending_story_moment = HOLOVERSE_SEED_ID
                                    resonance_notice = "A LATER INTELLIGENCE OPENS IO'S MEMORY ARCHIVE."
                                    resonance_notice_timer = 1.35
                        if not safe_mode:
                            exploration_sfx.play_cue("lantern_resonance", 0.72)
                elif event.key == pygame.K_q and transition_phase == "none" and veil_ward_learned:
                    if veil_ward_cooldown <= 0.0:
                        veil_ward_timer = VEIL_WARD_DURATION
                        veil_ward_cooldown = VEIL_WARD_COOLDOWN
                        causal_notice = "VEIL WARD: IO HOLDS TOGETHER."
                        causal_notice_timer = 1.7
                        if not safe_mode:
                            exploration_sfx.play_cue("lantern_resonance", 0.62)
                    else:
                        causal_notice = "VEIL WARD IS REFORMING."
                        causal_notice_timer = 1.1
                elif event.key == MACHINE_TELEKINESIS_KEY:
                    machine_build_mode = not machine_build_mode
                    if not machine_build_mode:
                        machine_pending_part = None
                        if machine_drag_id is not None and machine_drag_origin is not None:
                            for item in machine_placements:
                                if int(item.get("id", -1)) == machine_drag_id:
                                    item["x"], item["y"] = machine_drag_origin
                                    break
                        machine_drag_id = None
                        machine_drag_origin = None
                        causal_notice = "TELEKINESIS RELEASED."
                    else:
                        causal_notice = "MACHINE FOCUS // POWER CONTACTS HIGHLIGHTED // T EXIT"
                    causal_notice_timer = 2.2
                elif event.key == pygame.K_e:
                    # Pass 141: a nearby HEAD is a contextual conversation target.
                    # The powered Core Workshop remains the other machine-owned E path;
                    # neither path adds a persistent HUD element or falls through into
                    # unrelated world dialogue.
                    machine_head_target = nearest_machine_head_for_interaction()
                    if machine_head_target is not None:
                        head_item, head_part, _ = machine_head_target
                        machine_head_dialogue = True
                        machine_head_dialogue_page = 0
                        machine_head_dialogue_pages = machine_head_dialogue_for(head_item)
                        machine_head_dialogue_part_key = head_part.key
                        causal_notice = "MACHINE HEAD // CONTROL LINK OPEN"
                        causal_notice_timer = 1.2
                        vel_x = vel_y = 0.0
                        continue

                    powered_core = nearest_powered_core_for_workshop()
                    if powered_core is not None:
                        machine_workshop_open = True
                        machine_workshop_row = 0
                        machine_workshop_snap_edit = False
                        machine_workshop_snap_drag = None
                        machine_workshop_status = ""
                        machine_workshop_texture %= max(1, len(_machine_source_parts()))
                        causal_notice = "POWERED CORE HOUSING // MACHINE WORKSHOP"
                        causal_notice_timer = 1.5
                        vel_x = vel_y = 0.0
                        continue

                    machine_target = nearest_machine_for_interaction()
                    if machine_target is not None:
                        _, machine_part, _ = machine_target
                        if machine_part.role == ROLE_CORE:
                            causal_notice = "CORE HOUSING OFFLINE // TOUCH CORE + GEAR + PIVOT"
                        else:
                            causal_notice = "MACHINE INTERFACE // USE E AT A POWERED CORE HOUSING"
                        causal_notice_timer = 2.0
                        vel_x = vel_y = 0.0
                        continue

                    if world_key == "a" and pygame.Vector2(player_x, player_y).distance_to(future_anchor_pos) <= GLEEBS_INTERACT_RADIUS:
                        gleebs_dialogue = True
                        gleebs_dialogue_topic = "menu"
                        gleebs_dialogue_page = 0
                        gleebs_dialogue_selected = 0
                        vel_x = vel_y = 0.0
                    elif world_key == "b" and pygame.Vector2(player_x, player_y).distance_to(past_anchor_pos) <= GLEEBS_INTERACT_RADIUS:
                        gleebs_dialogue = True
                        gleebs_dialogue_topic = "menu"
                        gleebs_dialogue_page = 0
                        gleebs_dialogue_selected = 0
                        vel_x = vel_y = 0.0
                    elif (world_key == "b" and sable_idle_frames
                          and walk_layer.number == sable_walk_number
                          and pygame.Vector2(player_x, player_y).distance_to(sable_pos) <= SABLE_INTERACT_RADIUS):
                        sable_dialogue_first_visit = not sable_met
                        sable_met = True
                        sable_dialogue = True
                        sable_dialogue_mode = "lore" if sable_dialogue_first_visit else "menu"
                        sable_dialogue_page = 0
                        sable_dialogue_selected = 0
                        sable_shop_selected = 0
                        sable_shop_status = ""
                        vel_x = vel_y = 0.0
                    elif world_key == "b":
                        nearest_guardian = None
                        nearest_distance = 10**9
                        for guardian_id in MEMORY_GUARDIAN_ORDER:
                            gpos = guardian_positions.get(guardian_id)
                            if gpos is None:
                                continue
                            distance = pygame.Vector2(player_x, player_y).distance_to(gpos)
                            if distance < nearest_distance:
                                nearest_distance = distance
                                nearest_guardian = guardian_id
                        if nearest_guardian is not None and nearest_distance <= ENTITY_INTERACT_RADIUS:
                            entity_dialogue_kind = nearest_guardian
                            guardian_state = guardian_dialogue_states.setdefault(nearest_guardian, {"met": False, "declined_count": 0})
                            entity_dialogue_first_visit = not bool(guardian_state.get("met", False))
                            guardian_state["met"] = True
                            entity_dialogue = True
                            entity_dialogue_page = 0
                            entity_choice = 0
                            vel_x = vel_y = 0.0
                    elif world_key == "a" and not entity_defeated:
                        if pygame.Vector2(player_x, player_y).distance_to(FUTURE_CLUE_POS) <= FUTURE_CLUE_INTERACT_RADIUS:
                            future_clue_dialogue_kind = ENTITY_ID
                            future_clue_dialogue = True
                            future_clue_dialogue_page = 0
                            future_clue_choice = 0
                            vel_x = vel_y = 0.0
                    elif world_key == "a" and first_witness_echoes_complete and not rooted_crown_defeated:
                        if pygame.Vector2(player_x, player_y).distance_to(rooted_crown_shrine_pos) <= FUTURE_CLUE_INTERACT_RADIUS:
                            future_clue_dialogue_kind = ROOTED_CROWN_ID
                            future_clue_dialogue = True
                            future_clue_dialogue_page = 0
                            future_clue_choice = 0
                            vel_x = vel_y = 0.0
                    if world_key == "a" and entity_defeated and pygame.Vector2(player_x, player_y).distance_to(WORLD_A_END) <= SHRINE_INTERACT_RADIUS:
                        # Pass 62: the Gate only speaks after IO has earned the relevant
                        # story knowledge, and only when the player deliberately returns
                        # to the recorded Shrine.  No automatic radio chatter or HUD.
                        gate_moment = ""
                        if (VEIL_RESONANCE_ID in witnessed_story_moments
                                and GATE_FIRST_ACK_ID in witnessed_story_moments
                                and GATE_VEIL_ACK_ID not in witnessed_story_moments):
                            gate_moment = GATE_VEIL_ACK_ID
                        elif (FIRST_RECONSTRUCTION_ID in witnessed_story_moments
                                and GATE_FIRST_ACK_ID not in witnessed_story_moments):
                            gate_moment = GATE_FIRST_ACK_ID
                        if gate_moment:
                            story_moment_id = gate_moment
                            story_moment_page = 0
                            vel_x = vel_y = 0.0
                            if not safe_mode:
                                exploration_sfx.play_cue("gate_anchor", 0.68)
                        else:
                            shrine_dialogue_kind = ENTITY_ID
                            shrine_dialogue = True
                            shrine_dialogue_page = 0
                            shrine_choice = 0
                            vel_x = vel_y = 0.0
                    elif world_key == "a" and rooted_crown_defeated and pygame.Vector2(player_x, player_y).distance_to(rooted_crown_shrine_pos) <= SHRINE_INTERACT_RADIUS:
                        if (ROOTED_RECONSTRUCTION_ID in witnessed_story_moments
                                and GATE_ROOTED_ACK_ID not in witnessed_story_moments):
                            story_moment_id = GATE_ROOTED_ACK_ID
                            story_moment_page = 0
                            vel_x = vel_y = 0.0
                            if not safe_mode:
                                exploration_sfx.play_cue("gate_anchor", 0.72)
                        else:
                            shrine_dialogue_kind = ROOTED_CROWN_ID
                            shrine_dialogue = True
                            shrine_dialogue_page = 0
                            shrine_choice = 0
                            vel_x = vel_y = 0.0
                    elif world_key == "a" and veil_warden_defeated and pygame.Vector2(player_x, player_y).distance_to(veil_warden_shrine_pos) <= SHRINE_INTERACT_RADIUS:
                        shrine_dialogue_kind = VEIL_WARDEN_ID
                        shrine_dialogue = True
                        shrine_dialogue_page = 0
                        shrine_choice = 0
                        vel_x = vel_y = 0.0
                    elif world_key == "a":
                        nearest_shrine_id = None
                        nearest_shrine_distance = 10**9
                        for guardian_id in ADDITIONAL_SHRINE_IDS:
                            if guardian_id not in defeated_boss_ids:
                                continue
                            shrine_pos = additional_shrine_positions.get(guardian_id)
                            if shrine_pos is None:
                                continue
                            distance = pygame.Vector2(player_x, player_y).distance_to(shrine_pos)
                            if distance < nearest_shrine_distance:
                                nearest_shrine_distance = distance
                                nearest_shrine_id = guardian_id
                        if nearest_shrine_id is not None and nearest_shrine_distance <= SHRINE_INTERACT_RADIUS:
                            shrine_dialogue_kind = nearest_shrine_id
                            shrine_dialogue = True
                            shrine_dialogue_page = 0
                            shrine_choice = 0
                            vel_x = vel_y = 0.0
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS):
                    zoom = clamp(zoom + ZOOM_STEP, DEFAULT_ZOOM, MAX_ZOOM)
                elif event.key == pygame.K_MINUS:
                    zoom = clamp(zoom - ZOOM_STEP, DEFAULT_ZOOM, MAX_ZOOM)

        cursor_should_be_visible = bool(
            start_menu_open or paused or lore_archive_open or battle_active
            or sable_dialogue or entity_dialogue or shrine_dialogue or future_clue_dialogue or gleebs_dialogue or ending_open or story_moment_id
            or machine_build_mode or machine_workshop_open or machine_head_dialogue or machine_inventory_open
        )
        if cursor_should_be_visible != cursor_visible:
            try:
                pygame.mouse.set_visible(cursor_should_be_visible)
                cursor_visible = cursor_should_be_visible
            except pygame.error:
                pass

        keys = pygame.key.get_pressed()
        controller_move_x, controller_move_y = controller_bridge.movement() if controller_bridge.connected else (0.0, 0.0)
        if abs(controller_move_x) > 0.001 or abs(controller_move_y) > 0.001:
            controller_hint_timer = 2.0
            controller_input_mode = True
        if transition_phase == "none" and not start_menu_open and not paused and not lore_archive_open and not sable_dialogue and not entity_dialogue and not shrine_dialogue and not future_clue_dialogue and not gleebs_dialogue and not battle_active and not ending_open and not story_moment_id and not dev_console_open and not machine_workshop_open and not machine_head_dialogue and not machine_inventory_open:
            keyboard_x = float(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - float(keys[pygame.K_a] or keys[pygame.K_LEFT])
            keyboard_y = float(keys[pygame.K_s] or keys[pygame.K_DOWN]) - float(keys[pygame.K_w] or keys[pygame.K_UP])
            # Keyboard keeps immediate authority whenever it is actively held; otherwise
            # the normalized controller stick drives the same movement vector.
            input_x = keyboard_x if keyboard_x else controller_move_x
            input_y = keyboard_y if keyboard_y else controller_move_y
        else:
            input_x = 0.0
            input_y = 0.0
            hop_pressed = False
        move_vec = pygame.Vector2(input_x, input_y)
        if move_vec.length_squared() > 1.0:
            move_vec = move_vec.normalize()
        sprinting = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or controller_sprint_toggled)
        if lantern_projection_active:
            if move_vec.length_squared() > 0.0:
                lantern_projection_dir = move_vec.normalize()
                drone_speed = LANTERN_PROJECTION_SPEED
            else:
                drone_speed = LANTERN_PROJECTION_COAST_SPEED
            lantern_projection_x = clamp(lantern_projection_x + lantern_projection_dir.x * drone_speed * dt, 1.0, WORLD_SIZE[0] - 2.0)
            lantern_projection_y = clamp(lantern_projection_y + lantern_projection_dir.y * drone_speed * dt, 1.0, WORLD_SIZE[1] - 2.0)
            projection_lance_cooldown = max(0.0, projection_lance_cooldown - dt)
            _update_projection_enemy_drones(
                projection_enemy_drones, projection_enemy_shots,
                lantern_projection_x, lantern_projection_y, dt, atmosphere_time,
            )
            total_echo_wins = sum(int(value) for value in rematch_wins.values())
            lance_damage, _lance_cd = projection_lance_stats(total_echo_wins, veil_warden_shrine_activated)
            dispersed_drones = _update_projection_lance_shots(projection_lance_shots, projection_enemy_drones, dt, lance_damage)
            if dispersed_drones:
                causal_notice = "HUNTER DRONE DISPERSED." if dispersed_drones == 1 else f"{dispersed_drones} HUNTER DRONES DISPERSED."
                causal_notice_timer = 0.75
            if _projection_drone_hit(projection_enemy_shots, lantern_projection_x, lantern_projection_y):
                lantern_projection_integrity = max(0, lantern_projection_integrity - 1)
                lantern_projection_timer = max(0.0, lantern_projection_timer - 0.12)
                causal_notice = f"HOSTILE DRONE HIT // PROJECTION INTEGRITY {lantern_projection_integrity}/{LANTERN_PROJECTION_INTEGRITY}."
                causal_notice_timer = 0.8
                if lantern_projection_integrity <= 0:
                    lantern_projection_active = False
                    lantern_projection_timer = 0.0
                    projection_enemy_drones.clear()
                    projection_enemy_shots.clear()
                    projection_lance_shots.clear()
                    causal_notice = "LANTERN PROJECTION DISRUPTED. IO UNHARMED."
                    causal_notice_timer = 1.1
            move_vec.update(0.0, 0.0)
            input_x = input_y = 0.0
            sprinting = False
        if input_x:
            facing = 1 if input_x > 0 else -1
        target_speed = SPRINT_SPEED if sprinting else WALK_SPEED
        if world_key == "a":
            target_speed *= PRESENT_MOVEMENT_MULTIPLIER
        target_x = move_vec.x * target_speed
        target_y = move_vec.y * target_speed
        if move_vec.length_squared() > 0:
            vel_x = approach(vel_x, target_x, MOVE_ACCEL * dt)
            vel_y = approach(vel_y, target_y, MOVE_ACCEL * dt)
        else:
            vel_x = approach(vel_x, 0.0, MOVE_DECEL * dt)
            vel_y = approach(vel_y, 0.0, MOVE_DECEL * dt)

        if hop_pressed and hop_timer <= 0.0:
            hop_timer = HOP_DURATION

        # Walk layers are free-roam regions, not rails and not solid platform tops.
        # The Exile's foot point may move anywhere inside the current walk mask.
        previous_player_x, previous_player_y = player_x, player_y
        dx = vel_x * dt
        dy = vel_y * dt
        trial_x = clamp(player_x + dx, 1, WORLD_SIZE[0] - 2)
        trial_y = clamp(player_y + dy, 1, WORLD_SIZE[1] - 2)

        # Legacy authored-plane authority: remain on the current walk plane while
        # possible, and hand off only when the same destination belongs to another
        # authored walk mask. No landmass-edge routing or detached-location cut.
        target_layer = choose_walk_layer_for_target(stack, walk_layer, trial_x, trial_y)
        if target_layer is not None:
            if target_layer.number != walk_layer.number and depth_switch_timer <= 0.0:
                walk_layer = target_layer
                depth_switch_timer = DEPTH_SWITCH_COOLDOWN
            player_x, player_y = trial_x, trial_y
        else:
            x_layer = choose_walk_layer_for_target(stack, walk_layer, trial_x, player_y)
            if x_layer is not None:
                player_x = trial_x
                if x_layer.number != walk_layer.number and depth_switch_timer <= 0.0:
                    walk_layer = x_layer
                    depth_switch_timer = DEPTH_SWITCH_COOLDOWN
            else:
                vel_x = 0.0
            y_layer = choose_walk_layer_for_target(stack, walk_layer, player_x, trial_y)
            if y_layer is not None:
                player_y = trial_y
                if y_layer.number != walk_layer.number and depth_switch_timer <= 0.0:
                    walk_layer = y_layer
                    depth_switch_timer = DEPTH_SWITCH_COOLDOWN
            else:
                vel_y = 0.0

            recovered = recover_nearby(walk_layer, player_x, player_y)
            if recovered is not None:
                player_x, player_y = recovered

        # Pass 136: hidden lower-Present route access.  The trigger uses IO's
        # world-space foot point and is intentionally invisible.  It only acts
        # in Present exploration and resolves the destination against the
        # existing 2awalk mask, then hands control straight back to normal
        # movement.
        if (world_key == "a" and transition_phase == "none"
                and not start_menu_open and not paused and not lore_archive_open
                and not sable_dialogue and not entity_dialogue and not shrine_dialogue
                and not future_clue_dialogue and not gleebs_dialogue and not battle_active
                and not story_moment_id and not dev_console_open and not machine_workshop_open and not machine_head_dialogue and not machine_inventory_open
                and not lantern_projection_active):
            trigger_w, trigger_h = PRESENT_LOWER_ROUTE_TRIGGER_SIZE
            trigger_left = PRESENT_LOWER_ROUTE_TRIGGER_CENTER[0] - trigger_w * 0.5
            trigger_top = PRESENT_LOWER_ROUTE_TRIGGER_CENTER[1] - trigger_h * 0.5
            inside_lower_route_trigger = (
                trigger_left <= player_x <= trigger_left + trigger_w
                and trigger_top <= player_y <= trigger_top + trigger_h
            )
            if inside_lower_route_trigger:
                # Pass 140: the first local route now uses the same protected
                # fade lifecycle as the return exit.  IO freezes here, fades
                # fully to black, relocates while hidden, then fades back in.
                transition_phase = "present_lower_route_out"
                transition_timer = PRESENT_LOCAL_ROUTE_FADE_OUT
                vel_x = vel_y = 0.0
                hop_timer = 0.0
                footstep_distance = 0.0
            else:
                exit_w, exit_h = PRESENT_LOWER_ROUTE_EXIT_TRIGGER_SIZE
                exit_left = PRESENT_LOWER_ROUTE_EXIT_TRIGGER_CENTER[0] - exit_w * 0.5
                exit_top = PRESENT_LOWER_ROUTE_EXIT_TRIGGER_CENTER[1] - exit_h * 0.5
                inside_lower_route_exit = (
                    exit_left <= player_x <= exit_left + exit_w
                    and exit_top <= player_y <= exit_top + exit_h
                )
                if inside_lower_route_exit:
                    # Freeze IO immediately; relocation happens only after the
                    # fade has reached full black in the transition update.
                    transition_phase = "present_route_out"
                    transition_timer = PRESENT_LOCAL_ROUTE_FADE_OUT
                    vel_x = vel_y = 0.0
                    hop_timer = 0.0
                    footstep_distance = 0.0

        world_exploration_active = (
            transition_phase == "none" and not start_menu_open and not paused and not sable_dialogue and not entity_dialogue
            and not shrine_dialogue and not future_clue_dialogue and not gleebs_dialogue and not lore_archive_open and not battle_active
            and not story_moment_id and not machine_head_dialogue
        )
        exploration_active = world_exploration_active and not lantern_projection_active
        if exploration_active and lore_card_timer <= 0.0:
            encounter = nearby_unread_lore(
                lore_placements,
                world_key,
                walk_layer.number,
                (player_x, player_y),
                discovered_lore,
                shrine_activated,
                causal_resonance_learned,
                first_witness_echoes_complete,
            )
            if encounter is not None:
                record = encounter.record
                discovered_lore.add(record.record_id)
                lore_card_title = record.title
                lore_card_lines = record.lines
                lore_card_timer = LORE_CARD_TIME
                completed_now = first_witness_story_complete(discovered_lore)
                if completed_now and not first_witness_echoes_complete:
                    first_witness_echoes_complete = True
                    causal_notice = "THE SHRINE RECONSTRUCTS ITS WITNESS. RESONANCE RECOVERS FASTER."
                    if FIRST_RECONSTRUCTION_ID not in witnessed_story_moments:
                        pending_story_moment = FIRST_RECONSTRUCTION_ID
                    causal_notice_timer = 4.6
                    if not safe_mode:
                        exploration_sfx.play_cue("shrine_restore", 0.88)
                elif not safe_mode:
                    exploration_sfx.play_cue("memory_debris", 0.64 if record.shrine_echo else 0.48)

        # Story moments wait until ordinary lore cards/dialogues finish, then take
        # over briefly without moving IO or creating a new persistent HUD.
        # Pass 63 story pacing: first make IO's personal entropy explicit, then
        # reveal why his unusually dense memory archive will matter much later.
        if (world_key == "a" and GATE_ROOTED_ACK_ID in witnessed_story_moments
                and ENTROPY_MISSION_ID not in witnessed_story_moments
                and not story_moment_id and not pending_story_moment):
            pending_story_moment = ENTROPY_MISSION_ID
        elif (world_key == "a" and GATE_VEIL_ACK_ID in witnessed_story_moments
                and ENTROPY_MISSION_ID in witnessed_story_moments
                and ARCHIVE_DENSITY_ID not in witnessed_story_moments
                and not story_moment_id and not pending_story_moment):
            pending_story_moment = ARCHIVE_DENSITY_ID

        if (pending_story_moment and pending_story_moment not in witnessed_story_moments
                and not story_moment_id and lore_card_timer <= 0.0 and exploration_active):
            story_moment_id = pending_story_moment
            story_moment_page = 0
            pending_story_moment = ""
            vel_x = vel_y = 0.0
            if not safe_mode:
                exploration_sfx.play_cue("memory_debris", 0.72)

        actual_step_distance = math.hypot(player_x - previous_player_x, player_y - previous_player_y)
        if exploration_active and hop_timer <= 0.0 and actual_step_distance > 0.05:
            footstep_distance += actual_step_distance
            step_spacing = 43.0 if sprinting else 57.0
            if footstep_distance >= step_spacing:
                if not safe_mode:
                    exploration_sfx.play_footstep(sprinting)
                footstep_distance %= step_spacing
        elif not exploration_active or hop_timer > 0.0:
            footstep_distance = min(footstep_distance, 10.0)

        if not safe_mode:
            exploration_sfx.update_weather(world_exploration_active, world_key)
        weather_spawn_accumulator = _update_weather_particles(
            weather_particles,
            weather_particle_assets.get(world_key, ()),
            world_key,
            weather_rng,
            dt,
            weather_spawn_accumulator,
            world_exploration_active and not safe_mode,
        )

        if not paused and transition_phase == "present_lower_route_out" and transition_timer <= 0.0:
            # Pass 140: first local-route relocation occurs only at full black.
            route_layer = layer_by_number(stack, PRESENT_PRIMARY_WALK_LAYER) or walk_layer
            route_x, route_y = nearest_walkable_point(
                route_layer, PRESENT_LOWER_ROUTE_DESTINATION_HINT
            )
            player_x, player_y = route_x, route_y
            previous_player_x, previous_player_y = player_x, player_y
            walk_layer = route_layer
            facing = -1
            vel_x = vel_y = 0.0
            hop_timer = 0.0
            depth_switch_timer = 0.0
            footstep_distance = 0.0
            cam_x, cam_y = player_x, player_y - 40.0
            era_states["a"] = {
                "x": player_x, "y": player_y,
                "walk_layer": walk_layer.number, "facing": facing,
            }
            transition_phase = "present_lower_route_in"
            transition_timer = PRESENT_LOCAL_ROUTE_FADE_IN
        elif not paused and transition_phase == "present_lower_route_in" and transition_timer <= 0.0:
            transition_phase = "none"
        elif not paused and transition_phase == "present_route_out" and transition_timer <= 0.0:
            # Pass 137/140: return relocation occurs only at full black.
            route_layer = layer_by_number(stack, PRESENT_PRIMARY_WALK_LAYER) or walk_layer
            route_x, route_y = nearest_walkable_point(
                route_layer, PRESENT_LOWER_ROUTE_EXIT_DESTINATION_HINT
            )
            player_x, player_y = route_x, route_y
            walk_layer = route_layer
            facing = -1
            vel_x = vel_y = 0.0
            hop_timer = 0.0
            depth_switch_timer = 0.0
            footstep_distance = 0.0
            cam_x, cam_y = player_x, player_y - 40.0
            era_states["a"] = {
                "x": player_x, "y": player_y,
                "walk_layer": walk_layer.number, "facing": facing,
            }
            transition_phase = "present_route_in"
            transition_timer = PRESENT_LOCAL_ROUTE_FADE_IN
        elif not paused and transition_phase == "present_route_in" and transition_timer <= 0.0:
            transition_phase = "none"
        elif not paused and transition_phase == "out" and transition_timer <= 0.0:
            select_world("b", restore_temporal=False)
            transition_phase = "in"
            transition_timer = TRANSITION_IN_TIME
        elif not paused and transition_phase == "in" and transition_timer <= 0.0:
            transition_phase = "none"
        elif not paused and transition_phase == "time_shift" and transition_timer <= 0.0:
            transition_phase = "none"
            if guidance_pending_after_transition:
                guidance_pending_after_transition = False
                set_guidance_notice(duration=7.0)

        world_guidance_idle = bool(
            not start_menu_open and not paused and transition_phase == "none" and not lantern_projection_active
            and not lore_archive_open and not sable_dialogue and not entity_dialogue and not shrine_dialogue
            and not future_clue_dialogue and not gleebs_dialogue and not battle_active and not story_moment_id
            and not dev_console_open and not machine_workshop_open and not machine_head_dialogue and pygame.Vector2(vel_x, vel_y).length_squared() < 25.0
        )
        if world_guidance_idle:
            guidance_idle_timer += dt
        else:
            guidance_idle_timer = 0.0
        if (
            _normalize_guidance_mode(settings.get("guidance_mode", "context")) == "full"
            and guidance_idle_timer >= 40.0 and guidance_idle_cooldown <= 0.0
            and not causal_notice and not resonance_notice and lore_card_timer <= 0.0
        ):
            set_guidance_notice(duration=8.0)

        # Camera follows slowly and is hard-clamped so source edges can never appear.
        if lantern_projection_active:
            target_cam_x = lantern_projection_x
            target_cam_y = lantern_projection_y
            cam_x += (target_cam_x - cam_x) * min(1.0, dt * 8.5)
            cam_y += (target_cam_y - cam_y) * min(1.0, dt * 8.5)
        else:
            target_cam_x = player_x + vel_x * CAMERA_LOOKAHEAD
            # Free-roam framing follows the authored ground plane in both axes while
            # remaining slower vertically so the monumental composition stays stable.
            target_cam_y = player_y - 40
            cam_x += (target_cam_x - cam_x) * min(1.0, dt * 3.7)
            cam_y += (target_cam_y - cam_y) * min(1.0, dt * 2.1)
        bx0, bx1, by0, by1 = camera_bounds(zoom)
        cam_x = clamp(cam_x, bx0, bx1)
        cam_y = clamp(cam_y, by0, by1)

        # Stable authored Exile animation.  Frames are normalized to one foot baseline,
        # preventing the generated poses from wobbling inside their original tiles.
        moving = pygame.Vector2(vel_x, vel_y).length_squared() > 144.0
        hopping = hop_timer > 0.0
        desired_state = choose_player_state(hopping, moving, sprinting)
        if desired_state != anim_state:
            anim_state = desired_state
            anim_index = 0.0
        frame_rates = {"idle": 4.5, "walk": 8.0, "sprint": 11.0, "jump": 7.0}
        anim_index = (anim_index + dt * frame_rates[anim_state]) % len(player_anims[anim_state])
        player_img = player_anims[anim_state][int(anim_index)]

        logical.fill(WORLD_BACKDROP[world_key])

        # Artwork and actor use the exact same source crop.
        source_rect = shared_camera_rect(cam_x, cam_y, zoom)
        psx, psy = world_to_screen_shared(player_x, player_y, source_rect)
        screen_scale = W / source_rect.width
        hop_phase = 0.0 if hop_timer <= 0.0 else 1.0 - hop_timer / HOP_DURATION
        hop_offset = math.sin(hop_phase * math.pi) * HOP_HEIGHT * screen_scale
        actor_w = max(1, int(round(player_img.get_width() * screen_scale)))
        actor_h = max(1, int(round(player_img.get_height() * screen_scale)))
        actor_rect = pygame.Rect(0, 0, actor_w, actor_h)
        actor_rect.midbottom = (psx, int(round(psy - hop_offset)))

        # Pass 66 keeps the anchored flowing weather behind the walk layer,
        # then applies a restrained RGB overcast only to that walkable art:
        # deep scenery -> nebula weather -> overcast walk layer -> actors.
        deep_world, walk_world, foreground_world = depth_composite_for(stack, walk_layer.number)
        logical.blit(render_composite_view(deep_world, source_rect), (0, 0))
        if not safe_mode:
            _draw_tiled_weather_overlay(logical, weather_overlay_assets.get(world_key), world_key, atmosphere_time)
        walk_view = render_composite_view(walk_world, source_rect)
        logical.blit(walk_view, (0, 0))
        if not safe_mode:
            draw_persistent_atmosphere(logical, atmosphere_assets, world_key, atmosphere_time, "behind_actor", settings["fog_level"])
            _draw_weather_particles(logical, weather_particles, False)
        _draw_lore_debris(
            logical,
            lore_placements,
            world_key,
            walk_layer.number,
            source_rect,
            discovered_lore,
            shrine_activated,
            causal_resonance_learned,
            first_witness_echoes_complete,
            None if safe_mode else battle_assets.get("glow"),
            atmosphere_time,
        )

        if world_key == "a" and not entity_defeated:
            clue_x, clue_y = world_to_screen_shared(FUTURE_CLUE_POS[0], FUTURE_CLUE_POS[1], source_rect)
            clue_center = (clue_x, clue_y - max(34, int(actor_h * 0.72)))
            if not safe_mode:
                _draw_absence_echo(logical, battle_assets.get("glow"), clue_center, atmosphere_time, causal_resonance_learned, world_fx_assets.get("absence_echo"))
            if pygame.Vector2(player_x, player_y).distance_to(FUTURE_CLUE_POS) <= FUTURE_CLUE_INTERACT_RADIUS:
                prompt = _ui_render(small, "E  LISTEN TO THE ABSENCE", True, (220, 224, 220))
                logical.blit(prompt, prompt.get_rect(midbottom=(clue_x, clue_center[1] - 55)))

        # Pass 58: once the First Witness is fully reconstructed, a second
        # causal absence appears in the Future. Pass 95 routes its core through the
        # shared replaceable absence_echo.png slot while retaining the old lines as fallback.
        if world_key == "a" and first_witness_echoes_complete and not rooted_crown_defeated:
            clue_x, clue_y = world_to_screen_shared(rooted_crown_shrine_pos[0], rooted_crown_shrine_pos[1], source_rect)
            clue_center = (clue_x, clue_y - max(34, int(actor_h * 0.72)))
            if not safe_mode:
                _draw_absence_echo(logical, battle_assets.get("glow"), clue_center, atmosphere_time, True, world_fx_assets.get("absence_echo"))
            if pygame.Vector2(player_x, player_y).distance_to(rooted_crown_shrine_pos) <= FUTURE_CLUE_INTERACT_RADIUS:
                prompt = _ui_render(small, "E  LISTEN TO THE SECOND ABSENCE", True, (220, 224, 220))
                logical.blit(prompt, prompt.get_rect(midbottom=(clue_x, clue_center[1] - 55)))

        if world_key == "a":
            anchor_x, anchor_y = world_to_screen_shared(future_anchor_pos[0], future_anchor_pos[1], source_rect)
            anchor_center = (anchor_x, anchor_y - max(18, int(actor_h * 0.28)))
            if not safe_mode:
                _draw_gleebs_anchor(logical, battle_assets.get("glow"), anchor_center, atmosphere_time, True, world_fx_assets.get("anchor_future"))
            if pygame.Vector2(player_x, player_y).distance_to(future_anchor_pos) <= GLEEBS_INTERACT_RADIUS:
                prompt = _ui_render(small, "E  SPEAK TO GLEEBS / TIME TRAVEL", True, (226, 232, 232))
                logical.blit(prompt, prompt.get_rect(midbottom=(anchor_x, anchor_center[1] - 58)))
        elif world_key == "b":
            anchor_x, anchor_y = world_to_screen_shared(past_anchor_pos[0], past_anchor_pos[1], source_rect)
            anchor_center = (anchor_x, anchor_y - max(18, int(actor_h * 0.28)))
            if not safe_mode:
                _draw_gleebs_anchor(logical, battle_assets.get("glow"), anchor_center, atmosphere_time, False, world_fx_assets.get("anchor_past"))
            if pygame.Vector2(player_x, player_y).distance_to(past_anchor_pos) <= GLEEBS_INTERACT_RADIUS:
                prompt = _ui_render(small, "E  RETURN THROUGH THE TEMPORAL ANCHOR", True, (226, 232, 232))
                logical.blit(prompt, prompt.get_rect(midbottom=(anchor_x, anchor_center[1] - 58)))

        sable_screen_rect: pygame.Rect | None = None
        sable_current_frame: pygame.Surface | None = None
        if (world_key == "b" and sable_idle_frames and walk_layer.number == sable_walk_number):
            sable_index = int(atmosphere_time * SABLE_IDLE_FPS) % len(sable_idle_frames)
            sable_current_frame = sable_idle_frames[sable_index]
            sx, sy = world_to_screen_shared(sable_pos[0], sable_pos[1], source_rect)
            sable_h = max(8, int(round(actor_h * SABLE_HEIGHT_RATIO)))
            ratio = sable_current_frame.get_width() / max(1, sable_current_frame.get_height())
            sable_w = max(6, int(round(sable_h * ratio)))
            sable_render = _scaled_world_object_surface(sable_current_frame, sable_w, sable_h)
            sable_screen_rect = sable_render.get_rect(midbottom=(sx, sy))
            logical.blit(sable_render, sable_screen_rect)
            if pygame.Vector2(player_x, player_y).distance_to(sable_pos) <= SABLE_INTERACT_RADIUS:
                prompt = _ui_render(small, "E  SPEAK TO SABLE", True, (214, 226, 226))
                logical.blit(prompt, prompt.get_rect(midbottom=(sx, sable_screen_rect.top - 8)))

        # The permanent Core is part of the actual runtime machine collection.
        # Keep it runtime-static rather than saving it with movable player parts.
        # It follows the same Core/Gear/Pivot power rules as every other Core.
        static_machine_items = [_permanent_core_item()] if PERMANENT_CORE_PART_KEY in machine_catalog else []
        all_machine_items = machine_placements + static_machine_items
        current_machine_signature = (
            tuple(
                sorted(
                    (
                        int(item.get("id", 0)),
                        str(item.get("part", "")),
                        str(item.get("world", "")),
                        int(item.get("walk_layer", 0)),
                        round(float(item.get("x", 0.0)), 2),
                        round(float(item.get("y", 0.0)), 2),
                        round(float(item.get("angle", 0.0)) % 360.0, 1),
                        int(bool(item.get("flip_x", False))),
                        int(bool(item.get("locked"))),
                        int(bool(item.get("permanent_core"))),
                    )
                    for item in all_machine_items
                )
            ),
            int(machine_drag_id) if machine_drag_id is not None else None,
        )
        if current_machine_signature != machine_network_signature:
            machine_network_signature = current_machine_signature
            machine_network = resolve_machine_network(
                all_machine_items,
                part_roles={key: part.role for key, part in machine_catalog.items()},
                part_touch_radii={key: part.touch_radius for key, part in machine_catalog.items()},
                contact_points_by_id={
                    int(item.get("id", -1)): _machine_explicit_snap_positions(item, machine_catalog[str(item.get("part", ""))])
                    for item in all_machine_items
                    if str(item.get("part", "")) in machine_catalog
                    and _machine_part_explicit_snap_points(machine_catalog[str(item.get("part", ""))])
                },
                accessory_contact_points_by_id={
                    int(item.get("id", -1)): _machine_target_snap_positions(item, machine_catalog[str(item.get("part", ""))])
                    for item in all_machine_items
                    if str(item.get("part", "")) in machine_catalog
                },
                exclude_ids=(() if machine_drag_id is None else (machine_drag_id,)),
            )

        machine_screen_rects = []
        permanent_core_screen_rect: pygame.Rect | None = None
        placements_by_id = {int(item.get("id", -1)): item for item in all_machine_items}

        # Pass 119: the first Pipe endpoint is a persistent revolute/pin joint.
        # Contact with a powered drive is required only to CREATE the joint. Once
        # created, the saved Pivot id and local anchor keep the Pipe mechanically
        # attached; losing power stops the motor but does not disconnect the pin.
        for placed_item in machine_placements:
            placed_part = machine_catalog.get(str(placed_item.get("part", "")))
            if placed_part is None or placed_part.role != ROLE_PIPE:
                continue
            placed_id = int(placed_item.get("id", -1))
            pipe_state = machine_network.get(placed_id, {})

            saved_hinge_raw = placed_item.get("pipe_hinge_id", None)
            try:
                saved_hinge_id = int(saved_hinge_raw) if saved_hinge_raw is not None else None
            except (TypeError, ValueError, OverflowError):
                saved_hinge_id = None

            # Migrate a valid pre-119 powered hinge by recording its Pivot id.
            if saved_hinge_id is None and all(
                key in placed_item for key in ("attach_phase", "attach_local_dx", "attach_local_dy", "pipe_anchor_end")
            ):
                try:
                    legacy_pivot_id = int(pipe_state.get("pivot_id"))
                except (TypeError, ValueError, OverflowError):
                    legacy_pivot_id = -1
                if legacy_pivot_id in placements_by_id:
                    placed_item["pipe_hinge_id"] = legacy_pivot_id
                    saved_hinge_id = legacy_pivot_id

            if saved_hinge_id is not None:
                pivot_item = placements_by_id.get(saved_hinge_id)
                pivot_def = machine_catalog.get(str(pivot_item.get("part", ""))) if pivot_item is not None else None
                valid_scope = bool(
                    pivot_item is not None
                    and pivot_def is not None
                    and pivot_def.role == ROLE_PIVOT
                    and str(pivot_item.get("world")) == str(placed_item.get("world"))
                    and int(pivot_item.get("walk_layer", -999)) == int(placed_item.get("walk_layer", -998))
                )
                if not valid_scope:
                    _clear_pipe_constraints(placed_item)
                    continue
                pipe_state["pivot_id"] = saved_hinge_id
                pipe_state["parent_id"] = saved_hinge_id
                pipe_state["local_dx"] = float(placed_item.get("attach_local_dx", 0.0))
                pipe_state["local_dy"] = float(placed_item.get("attach_local_dy", 0.0))
                pipe_state["anchor_end"] = normalize_pipe_end(placed_item.get("pipe_anchor_end"))
                pipe_state["attachment"] = "pivot_hinge"
                continue

            # No mechanical hinge yet: the network's endpoint-contact test is the
            # sole authority for creating one.  A distant/rotated Pipe stays still.
            if not bool(pipe_state.get("powered")):
                continue
            pivot_id_raw = pipe_state.get("pivot_id")
            try:
                pivot_id = int(pivot_id_raw) if pivot_id_raw is not None else None
            except (TypeError, ValueError, OverflowError):
                pivot_id = None
            pivot_item = placements_by_id.get(pivot_id) if pivot_id is not None else None
            pivot_def = machine_catalog.get(str(pivot_item.get("part", ""))) if pivot_item is not None else None
            if pivot_item is None or pivot_def is None or pivot_def.role != ROLE_PIVOT:
                continue

            pivot_speed = float(pivot_def.spin_dps or 72.0)
            attach_phase = (atmosphere_time * pivot_speed) % 360.0
            pivot_runtime_x, pivot_runtime_y, _, _ = _machine_runtime_transform(
                pivot_item, pivot_def, machine_network, placements_by_id, atmosphere_time
            )
            natural_length = _machine_part_natural_world_width(placed_part)
            try:
                authored_angle = float(placed_item.get("angle", 0.0)) % 360.0
            except (TypeError, ValueError, OverflowError):
                authored_angle = 0.0
            authored_endpoints = pipe_endpoints(
                float(placed_item.get("x", 0.0)),
                float(placed_item.get("y", 0.0)),
                authored_angle,
                natural_length,
            )
            contact_end = normalize_pipe_end(pipe_state.get("anchor_end", PIPE_END_LEFT))
            anchor_point = authored_endpoints[contact_end]
            placed_item["pipe_hinge_id"] = pivot_id
            placed_item["pipe_anchor_end"] = contact_end
            placed_item["pipe_orbit_dir"] = 1
            placed_item["attach_phase"] = round(attach_phase, 3)
            placed_item["attach_local_dx"] = round(anchor_point[0] - pivot_runtime_x, 3)
            placed_item["attach_local_dy"] = round(anchor_point[1] - pivot_runtime_y, 3)
            _clear_pipe_brace(placed_item)
            pipe_state["local_dx"] = float(placed_item["attach_local_dx"])
            pipe_state["local_dy"] = float(placed_item["attach_local_dy"])
            pipe_state["anchor_end"] = contact_end
            pipe_state["pivot_id"] = pivot_id
            pipe_state["parent_id"] = pivot_id
            pipe_state["attachment"] = "pivot_hinge"

        # The free Pipe endpoint may brace against a separate component.  The
        # contact point is preserved in that target's local orientation, so
        # translating or rotating the supporting part stabilizes/carries the
        # attached end instead of forcing a center snap.
        for placed_item in machine_placements:
            placed_part = machine_catalog.get(str(placed_item.get("part", "")))
            if placed_part is None or placed_part.role != ROLE_PIPE:
                continue
            placed_id = int(placed_item.get("id", -1))
            pipe_state = machine_network.get(placed_id, {})
            if "pipe_hinge_id" not in placed_item or "pipe_anchor_end" not in placed_item:
                continue

            pivot_id_raw = pipe_state.get("pivot_id")
            blocked_ids = {placed_id}
            for blocked_raw in (pivot_id_raw, pipe_state.get("gear_id"), pipe_state.get("core_id")):
                try:
                    if blocked_raw is not None:
                        blocked_ids.add(int(blocked_raw))
                except (TypeError, ValueError, OverflowError):
                    pass

            # Clean a stale brace first.  Pipe-to-pipe and Pipe-to-Fan braces are
            # intentionally excluded in this pass to prevent recursive cycles.
            brace_id_raw = placed_item.get("pipe_brace_id", None)
            try:
                brace_id = int(brace_id_raw) if brace_id_raw is not None else None
            except (TypeError, ValueError, OverflowError):
                brace_id = None
            if brace_id is not None:
                brace_item = placements_by_id.get(brace_id)
                brace_part = machine_catalog.get(str(brace_item.get("part", ""))) if brace_item is not None else None
                valid_scope = bool(
                    brace_item is not None
                    and str(brace_item.get("world")) == str(placed_item.get("world"))
                    and int(brace_item.get("walk_layer", -999)) == int(placed_item.get("walk_layer", -998))
                )
                if (
                    brace_id in blocked_ids
                    or brace_part is None
                    or brace_part.role not in PIPE_BRACE_ROLES
                    or not valid_scope
                    or bool(brace_item.get("locked"))
                ):
                    _clear_pipe_brace(placed_item)
                    brace_id = None

            if brace_id is not None:
                # Persistent hinge: distance never auto-breaks this joint. The
                # rigid-link solver transfers the error into the attached body.
                continue

            pipe_x, pipe_y, pipe_angle, _ = _machine_runtime_transform(
                placed_item, placed_part, machine_network, placements_by_id, atmosphere_time
            )
            pipe_length = _machine_part_natural_world_width(placed_part)
            endpoints = pipe_endpoints(pipe_x, pipe_y, pipe_angle, pipe_length)
            free_end = opposite_pipe_end(placed_item.get("pipe_anchor_end"))
            free_x, free_y = endpoints[free_end]

            candidates: list[tuple[float, int, float, float, float]] = []
            for target_id, target_item in placements_by_id.items():
                if target_id in blocked_ids:
                    continue
                if str(target_item.get("world")) != str(placed_item.get("world")) or int(target_item.get("walk_layer", -999)) != int(placed_item.get("walk_layer", -998)):
                    continue
                target_part = machine_catalog.get(str(target_item.get("part", "")))
                if target_part is None or target_part.role not in PIPE_BRACE_ROLES or bool(target_item.get("locked")):
                    continue
                target_x, target_y, target_angle, _ = _machine_runtime_transform(
                    target_item, target_part, machine_network, placements_by_id, atmosphere_time
                )
                distance = math.hypot(free_x - target_x, free_y - target_y)
                contact_limit = max(8.0, float(target_part.touch_radius)) + PIPE_BRACE_ATTACH_RADIUS_WORLD
                if distance <= contact_limit:
                    candidates.append((distance, int(target_id), target_x, target_y, target_angle))
            if candidates:
                _, brace_id, brace_x, brace_y, brace_angle = min(candidates, key=lambda value: (value[0], value[1]))
                placed_item["pipe_brace_id"] = brace_id
                placed_item["pipe_brace_local_dx"] = round(free_x - brace_x, 3)
                placed_item["pipe_brace_local_dy"] = round(free_y - brace_y, 3)
                placed_item["pipe_brace_angle"] = round(brace_angle % 360.0, 3)
                _MACHINE_PIPE_DYNAMICS.pop(placed_id, None)

        # Pass 121: there is no special generator completion circuit.
        # The normal Core + Gear + Pivot contact graph is the sole power authority.

        # Pass 117: machine audio is a strict powered-state loop, not a proximity
        # effect.  Any complete powered drive in the Beginning/Past turns the
        # replaceable loop on while IO is exploring the Past.  Entering the Future
        # or losing power shuts the channel off immediately through update_machine.
        past_machine_powered = False
        if world_key == "b" and world_exploration_active and not safe_mode:
            for instance_id, state in machine_network.items():
                if not bool(state.get("powered")) or str(state.get("role")) not in {ROLE_CORE, ROLE_GEAR, ROLE_PIVOT}:
                    continue
                item = placements_by_id.get(int(instance_id))
                if item is not None and str(item.get("world")) == "b":
                    past_machine_powered = True
                    break
        exploration_sfx.update_machine(past_machine_powered, 0.24 if past_machine_powered else 0.0)

        visible_machine_items: list[tuple[dict, MachinePartDef]] = []
        for item in all_machine_items:
            if str(item.get("world")) != world_key or int(item.get("walk_layer", -999)) != walk_layer.number:
                continue
            part = machine_catalog.get(str(item.get("part", "")))
            if part is not None:
                visible_machine_items.append((item, part))

        # Deterministic machine layer order. The stationary Gear Cluster is the
        # lower drive housing; the rotating Pivot Ring is drawn above it. Pipes
        # follow next, fans sit over their pipe endpoint, and Frame Plates remain
        # the final cosmetic overlay.
        machine_role_layer = {
            ROLE_CORE: 0,
            ROLE_GEAR: 1,
            ROLE_PIVOT: 2,
            ROLE_PIPE: 3,
            ROLE_FRAME: 4,
            ROLE_ACTUATOR: 5,
            ROLE_FAN: 6,
            ROLE_TOOL: 7,
            ROLE_SENSOR: 8,
            ROLE_HEAD: 9,
            ROLE_COSMETIC: 10,
        }
        visible_machine_items.sort(key=lambda entry: (machine_role_layer.get(entry[1].role, 3), int(entry[0].get("id", 0))))
        for item, part in visible_machine_items:
            instance_id = int(item.get("id", -1))
            if machine_drag_id is not None and instance_id == machine_drag_id:
                mx_world = float(item["x"])
                my_world = float(item["y"])
                machine_angle = float(item.get("angle", 0.0)) % 360.0
                machine_width_scale = 1.0
            else:
                mx_world, my_world, machine_angle, machine_width_scale = _machine_runtime_transform(
                    item, part, machine_network, placements_by_id, atmosphere_time
                )
            mx, my = world_to_screen_shared(mx_world, my_world, source_rect)
            mimg = _machine_part_screen_surface(
                part, screen_scale, angle=machine_angle, flip_x=bool(item.get("flip_x")), width_scale=machine_width_scale
            )
            mrect = mimg.get_rect(center=(mx, my))
            logical.blit(mimg, mrect)
            if part.role == ROLE_PIPE and (machine_build_mode or instance_id == machine_drag_id):
                pipe_length = _machine_part_natural_world_width(part) * machine_width_scale
                endpoint_world = pipe_endpoints(mx_world, my_world, machine_angle, pipe_length)
                for endpoint_name, endpoint_label in ((PIPE_END_LEFT, "L"), (PIPE_END_RIGHT, "R")):
                    ewx, ewy = endpoint_world[endpoint_name]
                    esx, esy = world_to_screen_shared(ewx, ewy, source_rect)
                    pygame.draw.circle(logical, (111, 190, 198), (int(esx), int(esy)), 5, 1)
                    endpoint_text = _ui_render(small, endpoint_label, True, (174, 224, 228))
                    logical.blit(endpoint_text, endpoint_text.get_rect(midbottom=(int(esx), int(esy) - 7)))
            if bool(item.get("permanent_core")):
                # Keep only the established local foreground readability treatment.
                # No floating machine-status label is added.
                permanent_core_screen_rect = mrect.copy()
            if not bool(item.get("locked")):
                machine_screen_rects.append((instance_id, mrect))

            if machine_build_mode:
                state = machine_network.get(instance_id, {})
                if instance_id == machine_drag_id:
                    outline = MACHINE_SELECTED_OUTLINE
                elif part.role in {ROLE_CORE, ROLE_GEAR, ROLE_PIVOT, ROLE_FAN, ROLE_PIPE, ROLE_HEAD, ROLE_ACTUATOR, ROLE_SENSOR, ROLE_TOOL}:
                    outline = (128, 205, 213) if bool(state.get("powered")) else (96, 88, 91)
                else:
                    outline = None
                if outline is not None:
                    pygame.draw.rect(logical, outline, mrect.inflate(8, 8), 1)

        # Active Past Entity plus all manifested Future Shrines. Existing boss
        # art is activated in sequence; every Shrine still reuses the single
        # replaceable shrine_source.png slot.
        objects: list[tuple[pygame.Surface | None, tuple[float, float], str, str]] = []
        if world_key == "b":
            # Pass 85: the Past is an open Memory Guardian field. Every archive
            # can be challenged in any order; defeated Guardians simply stop
            # rendering while their recovered archive remains in progression.
            for guardian_id in MEMORY_GUARDIAN_ORDER:
                gpos = guardian_positions.get(guardian_id)
                gimg = guardian_imgs.get(guardian_id)
                if gpos is not None and gimg is not None:
                    objects.append((gimg, gpos, "entity", guardian_id))
        else:
            if entity_defeated:
                objects.append((shrine_img, WORLD_A_END, "shrine", ENTITY_ID))
            if rooted_crown_defeated:
                objects.append((shrine_img, rooted_crown_shrine_pos, "shrine", ROOTED_CROWN_ID))
            if veil_warden_defeated:
                objects.append((shrine_img, veil_warden_shrine_pos, "shrine", VEIL_WARDEN_ID))
            for guardian_id in ADDITIONAL_SHRINE_IDS:
                if guardian_id in defeated_boss_ids and guardian_id in additional_shrine_positions:
                    objects.append((shrine_img, additional_shrine_positions[guardian_id], "shrine", guardian_id))

        for object_img, object_pos, object_kind, object_id in objects:
            if object_img is None:
                continue
            ox, oy = world_to_screen_shared(object_pos[0], object_pos[1], source_rect)
            if object_kind == "entity":
                entity_h = max(8, int(round(actor_h * ENTITY_HEIGHT_RATIO)))
                if safe_mode:
                    try:
                        ratio = object_img.get_width() / max(1, object_img.get_height())
                        oimg = pygame.transform.scale(object_img, (max(6, int(entity_h * ratio)), entity_h))
                    except Exception:
                        oimg = object_img
                else:
                    oimg = _entity_presence_surface(object_img, entity_h, atmosphere_time)
            else:
                ow = max(1, int(object_img.get_width() * screen_scale * 0.65))
                oh = max(1, int(object_img.get_height() * screen_scale * 0.65))
                oimg = _scaled_world_object_surface(object_img, ow, oh)
                if object_kind == "shrine":
                    oimg = _subdued_obelisk_surface(oimg)
            if object_kind == "entity" and object_id in defeated_boss_ids:
                oimg = oimg.copy()
                oimg.set_alpha(150)
            orect = oimg.get_rect(midbottom=(ox, oy))
            logical.blit(oimg, orect)
            distance = pygame.Vector2(player_x, player_y).distance_to(object_pos)
            if object_kind == "entity" and distance <= ENTITY_INTERACT_RADIUS:
                label = (f"E  CHALLENGE {_battle_name_for(object_id)} ECHO" if object_id in defeated_boss_ids
                         else f"E  READ {_battle_name_for(object_id)} ARCHIVE")
                prompt = _ui_render(small, label, True, (232, 222, 204))
                logical.blit(prompt, prompt.get_rect(midbottom=(ox, orect.top - 8)))
            elif object_kind == "shrine" and distance <= SHRINE_INTERACT_RADIUS:
                label = f"E  READ {_shrine_name_for(object_id)}"
                prompt = _ui_render(small, label, True, (232, 222, 204))
                logical.blit(prompt, prompt.get_rect(midbottom=(ox, orect.top - 8)))

        if lantern_projection_active:
            for hostile in projection_enemy_drones:
                hsx, hsy = world_to_screen_shared(float(hostile["x"]), float(hostile["y"]), source_rect)
                if -100 <= hsx <= W + 100 and -100 <= hsy <= H + 100 and projection_drone_assets:
                    asset = projection_drone_assets[int(hostile["asset"]) % len(projection_drone_assets)]
                    _draw_projection_enemy_drone(
                        logical, asset, (hsx, hsy), float(hostile.get("heading", 1.0)),
                        float(hostile.get("alert", 0.0)), atmosphere_time,
                        int(hostile.get("integrity", ENEMY_DRONE_BASE_INTEGRITY)),
                        int(hostile.get("max_integrity", ENEMY_DRONE_BASE_INTEGRITY)),
                        bool(hostile.get("elite", False)),
                    )
            for hostile_shot in projection_enemy_shots:
                ssx, ssy = world_to_screen_shared(float(hostile_shot["x"]), float(hostile_shot["y"]), source_rect)
                if -40 <= ssx <= W + 40 and -40 <= ssy <= H + 40:
                    _draw_projection_enemy_shot(logical, (ssx, ssy), atmosphere_time)
            for lance_shot in projection_lance_shots:
                trail_screen = [world_to_screen_shared(px, py, source_rect) for px, py in lance_shot.get("trail", [])]
                _draw_projection_lance_trail(logical, trail_screen, projection_lance_mastery >= 3)
                lsx, lsy = world_to_screen_shared(float(lance_shot["x"]), float(lance_shot["y"]), source_rect)
                if -40 <= lsx <= W + 40 and -40 <= lsy <= H + 40:
                    _draw_projection_lance_shot(logical, (lsx, lsy), atmosphere_time, projection_lance_mastery >= 3)
            drone_sx, drone_sy = world_to_screen_shared(lantern_projection_x, lantern_projection_y, source_rect)
            _draw_lantern_projection(
                logical,
                (drone_sx, drone_sy),
                lantern_projection_timer,
                lantern_projection_duration(lantern_projection_upgrade_level),
                atmosphere_time,
                player_projection_drone_asset,
                lantern_projection_dir.x if abs(lantern_projection_dir.x) > 0.01 else float(facing),
            )
            if not safe_mode and remote_resonance_timer > 0.0:
                total_echo_wins = sum(int(value) for value in rematch_wins.values())
                _draw_projection_resonance(logical, (drone_sx, drone_sy), remote_resonance_timer, remote_resonance_level(total_echo_wins) >= 2)

        scaled_player = _scaled_player_frame(player_img, actor_w, actor_h, facing)
        ward_strength = _veil_ward_strength(veil_ward_timer) if veil_ward_learned else 0.0
        if world_key == "a" and not safe_mode:
            _draw_future_entropy_glow(logical, battle_assets.get("glow"), actor_rect, atmosphere_time)
            scaled_player = _future_entropy_player_surface(scaled_player, atmosphere_time, ward_strength)
        logical.blit(scaled_player, actor_rect)
        if not safe_mode and veil_ward_timer > 0.0:
            _draw_veil_ward(logical, actor_rect.center, veil_ward_timer, atmosphere_time)

        foreground_view = render_composite_view(foreground_world, source_rect)
        if not safe_mode:
            foreground_view = apply_local_occlusion_fade(foreground_view, pygame.Rect(drone_sx-16, drone_sy-16, 32, 32) if lantern_projection_active else actor_rect)
            if sable_screen_rect is not None:
                foreground_view = apply_local_occlusion_fade(foreground_view, sable_screen_rect)
            if permanent_core_screen_rect is not None:
                foreground_view = apply_local_occlusion_fade(foreground_view, permanent_core_screen_rect.inflate(12, 12))
        logical.blit(foreground_view, (0, 0))
        if not safe_mode:
            draw_persistent_atmosphere(logical, atmosphere_assets, world_key, atmosphere_time, "front", settings["fog_level"])
            _draw_weather_particles(logical, weather_particles, True)
        draw_atmosphere_finish(logical, atmosphere_assets, world_key, settings["vignette_level"], settings["darkness_level"], present_cloud_shadow_alpha)
        if machine_build_mode and machine_pending_part in machine_catalog:
            part = machine_catalog[machine_pending_part]
            pmx, pmy = world_to_screen_shared(machine_pending_pos[0], machine_pending_pos[1], source_rect)
            preview = _machine_part_screen_surface(part, screen_scale, alpha=MACHINE_PLACEMENT_ALPHA)
            preview_rect = preview.get_rect(center=(pmx, pmy))
            logical.blit(preview, preview_rect)
            pygame.draw.rect(logical, MACHINE_SELECTED_OUTLINE, preview_rect.inflate(8, 8), 1)
        if not safe_mode and resonance_pulse_timer > 0.0:
            _draw_resonance_pulse(
                logical,
                battle_assets.get("glow"),
                (actor_rect.centerx, actor_rect.centery),
                resonance_pulse_timer,
            )

        machine_workshop_hit_rects = []
        machine_workshop_preview_rect = None
        if machine_workshop_open:
            machine_workshop_hit_rects, machine_workshop_preview_rect = draw_machine_workshop(
                logical, font, small, machine_catalog, machine_workshop_row, machine_workshop_shape, machine_workshop_texture,
                machine_workshop_role, machine_workshop_size, machine_workshop_functions, machine_workshop_snap_points,
                machine_workshop_snap_selected, machine_workshop_snap_edit, machine_workshop_status
            )

        machine_hotbar_visible = bool(machine_catalog and transition_phase == "none" and not (start_menu_open or paused or lore_archive_open or sable_dialogue or entity_dialogue or shrine_dialogue or future_clue_dialogue or gleebs_dialogue or battle_active or ending_open or story_moment_id or lantern_projection_active or dev_console_open or machine_workshop_open or machine_head_dialogue or machine_inventory_open))
        machine_hotbar_rect = None
        if machine_hotbar_visible:
            selected_part = selected_machine_part()
            selected_key = selected_part.key if selected_part is not None else None
            machine_hotbar_rect = draw_machine_hotbar(logical, small, machine_catalog, machine_inventory, machine_bits, machine_hotbar_flash_key, selected_key)
            pointer = _window_to_logical(window, pygame.mouse.get_pos())
            pointer_active = bool(pointer is not None and (machine_drag_id is not None or any(rect.collidepoint(pointer) for _, rect in machine_screen_rects)))
            if not machine_build_mode:
                draw_machine_pointer(logical, pointer, active=pointer_active)

        if machine_build_mode and not (sable_dialogue or battle_active or paused or start_menu_open or machine_head_dialogue):
            focus_part = selected_machine_part()
            if focus_part is not None:
                focus_owned = clamp_machine_stack(machine_inventory.get(focus_part.key, 0))
                focus_role = MACHINE_WORKSHOP_ROLE_LABELS.get(focus_part.role, focus_part.role.upper())
                build_text = f"MACHINE FOCUS   •   {focus_role}   •   {focus_part.name} [{focus_owned}]   •   ←/→ PART   •   ENTER PLACE   •   T EXIT"
            else:
                build_text = "MACHINE FOCUS   •   ←/→ PART   •   ENTER PLACE   •   T EXIT"
            if machine_pending_part in machine_catalog:
                part = machine_catalog[machine_pending_part]
                owned = clamp_machine_stack(machine_inventory.get(part.key, 0))
                build_text = f"PLACE {part.name}   •   OWNED {owned}   •   CLICK PLACE   •   RMB CANCEL"
            build_surface = _ui_render(small, build_text, True, (204, 226, 228))
            bg = pygame.Surface((build_surface.get_width() + 24, build_surface.get_height() + 12), pygame.SRCALPHA)
            bg.fill((5, 8, 12, 178))
            brect = bg.get_rect(midbottom=(W // 2, H - 86))
            logical.blit(bg, brect)
            logical.blit(build_surface, build_surface.get_rect(center=brect.center))

        dev_coords_ui_active = bool(
            transition_phase == "none" and not (
                start_menu_open or paused or lore_archive_open or sable_dialogue or entity_dialogue
                or shrine_dialogue or future_clue_dialogue or gleebs_dialogue or battle_active or ending_open
                or story_moment_id or lantern_projection_active or dev_console_open or machine_workshop_open or machine_head_dialogue or machine_inventory_open
            )
        )
        if dev_coords_ui_active:
            draw_dev_coordinates(logical, dev_coord_font, player_x, player_y, dev_coords_visible)

        # F1 exposes the compact control strip; Pass 135 adds only the tiny optional XY developer readout.
        if show_help:
            resonance_help = "   R causal resonance" if causal_resonance_learned else ""
            ward_help = "   Q veil ward" if veil_ward_learned else ""
            projection_help = f"   TAB player drone {lantern_projection_duration(lantern_projection_upgrade_level):.0f}s" if lantern_projection_learned else ""
            machine_help = "   I inventory   T machine focus / ←→ part" if machine_catalog else ""
            controller_help_active = bool(controller_bridge.connected and controller_input_mode)
            if lantern_projection_active:
                projection_help += f"   integrity {lantern_projection_integrity}/{LANTERN_PROJECTION_INTEGRITY}"
                if projection_lance_learned:
                    projection_help += "   SPACE projection lance"
                if remote_resonance_learned:
                    projection_help += "   R remote resonance"
            if lantern_projection_active and controller_help_active:
                drone_actions = "LS steer   •   Y/B recall"
                if remote_resonance_learned:
                    drone_actions += "   RB remote resonance"
                if projection_lance_learned:
                    drone_actions += "   X projection lance"
                lines = [
                    drone_actions,
                    f"PROJECTION {lantern_projection_timer:.1f}s   •   integrity {lantern_projection_integrity}/{LANTERN_PROJECTION_INTEGRITY}   •   D↑/RS help",
                ]
            elif lantern_projection_active:
                drone_actions = "WASD steer   •   TAB recall"
                if remote_resonance_learned:
                    drone_actions += "   R remote resonance"
                if projection_lance_learned:
                    drone_actions += "   SPACE projection lance"
                lines = [
                    drone_actions,
                    f"PROJECTION {lantern_projection_timer:.1f}s   •   integrity {lantern_projection_integrity}/{LANTERN_PROJECTION_INTEGRITY}   •   F1 hide",
                ]
            elif controller_help_active:
                lines = list(controller_help_lines(
                    bool(machine_catalog),
                    (bool(causal_resonance_learned), bool(veil_ward_learned)),
                    bool(lantern_projection_learned),
                ))
                if machine_build_mode:
                    lines = [
                        "MACHINE FOCUS   •   D←/→ kit   •   A place   •   RS aim cursor   •   X hold move",
                        "RS click flip   •   Y reclaim   •   D↓ exit focus   •   MENU pause   •   D↑ help",
                    ]
            else:
                lines = [
                    f"WASD move   •   SHIFT sprint   •   SPACE hop   •   E interact   •   L archive{resonance_help}{ward_help}{projection_help}{machine_help}",
                    "LMB move part   •   CTRL+LMB flip   •   RMB reclaim   •   wheel zoom   •   ESC pause   •   F1 hide",
                ]
            lines = [continuity_thread_line(world_key, defeated_boss_ids)] + list(lines)
            help_y = H - (148 if machine_hotbar_visible else 75)
            help_rect = pygame.Rect(12, help_y, W - 24, 63)
            if not _draw_hud_skin(logical, "help_panel", help_rect):
                panel = pygame.Surface(help_rect.size, pygame.SRCALPHA); panel.fill((0,0,0,145)); logical.blit(panel,help_rect)
            for i,line in enumerate(lines[:3]):
                color = (180, 220, 224) if i == 0 else (215,220,224)
                logical.blit(_ui_render(small, line, True, color), (20,help_y+5+i*19))

        if defeated_boss_ids and not battle_active:
            draw_defeated_boss_strip(logical, boss_portraits, defeated_boss_ids)

        if transition_phase == "time_shift":
            _draw_time_shift_response(
                logical,
                transition_assets.get("time_shift"),
                world_key,
                transition_timer,
            )
        elif transition_phase in {
            "present_lower_route_out", "present_lower_route_in",
            "present_route_out", "present_route_in",
        }:
            # Both local Present exits use the same clean black fade with no
            # time-shift art.  Position/camera changes happen only at alpha=255.
            if transition_phase in {"present_lower_route_out", "present_route_out"}:
                route_progress = 1.0 - (
                    transition_timer / PRESENT_LOCAL_ROUTE_FADE_OUT
                    if PRESENT_LOCAL_ROUTE_FADE_OUT else 0.0
                )
            else:
                route_progress = (
                    transition_timer / PRESENT_LOCAL_ROUTE_FADE_IN
                    if PRESENT_LOCAL_ROUTE_FADE_IN else 0.0
                )
            route_progress = clamp(route_progress, 0.0, 1.0)
            # Smoothstep keeps the short transition soft without lingering.
            route_progress = route_progress * route_progress * (3.0 - 2.0 * route_progress)
            fade = pygame.Surface((W, H), pygame.SRCALPHA)
            fade.fill((0, 0, 0, int(route_progress * 255)))
            logical.blit(fade, (0, 0))
        elif transition_phase != "none":
            # Legacy automatic transition path remains available, although the
            # anchor travel keeps the responsive non-black time-shift response.
            if transition_phase == "out":
                progress = 1.0 - (transition_timer / TRANSITION_OUT_TIME if TRANSITION_OUT_TIME else 0.0)
            else:
                progress = transition_timer / TRANSITION_IN_TIME if TRANSITION_IN_TIME else 0.0
            _draw_fullscreen_variant(
                logical,
                transition_assets.get("time_shift"),
                int(210 * math.sin(math.pi * clamp(progress, 0.0, 1.0))),
            )
            alpha = int(clamp(progress, 0.0, 1.0) * 255)
            fade = pygame.Surface((W, H), pygame.SRCALPHA)
            fade.fill((0, 0, 0, alpha))
            logical.blit(fade, (0, 0))

        battle_hit_rects = []
        dialogue_hit_rects = []
        ending_hit_rects = []
        if ending_open:
            ending_hit_rects = draw_escape_ending(logical, title_font, menu_font, small, ending_page, ending_selected)
        elif story_moment_id:
            draw_temporal_story_moment(
                logical, title_font, menu_font, small, story_moment_id, story_moment_page,
                shrine_img, None if safe_mode else battle_assets.get("glow"), atmosphere_time, story_assets,
            )
        elif battle_active:
            battle_player_frame = player_anims["idle"][int(atmosphere_time * 4.5) % len(player_anims["idle"])]
            victory_progress = 0.0
            if battle_victory_timer > 0.0:
                victory_progress = 1.0 - min(1.0, battle_victory_timer / max(0.001, BOSS_DEFEAT_TIME))
            active_battle_img = guardian_imgs.get(battle_entity_id, entity_img)
            battle_hit_rects = draw_battle(
                logical, active_battle_img, battle_player_frame, battle_assets, title_font, menu_font, small,
                battle_player_hp, battle_entity_hp, battle_selected, battle_message, battle_focus,
                battle_fx_kind, battle_fx_timer, battle_move_index, safe_mode, boss_damage_fx, victory_progress, battle_entity_id,
                battle_challenge_tier, battle_rematch, entropy_arc_learned, entropy_arc_mastery, battle_entropy_arc_cooldown, battle_upgrade_score,
                _archive_attunement_resolve_bonus(defeated_boss_ids), battle_guardian_fx_kind, battle_guardian_fx_timer,
                battle_mind_interference_active, battle_mind_fake_move_index, battle_mind_interference_level,
                battle_signal_verified_counter, battle_mind_ward_suppressed,
                battle_signal_verify_cooldown, battle_mind_ward_cooldown,
                causal_resonance_learned, veil_ward_learned,
            )
        elif machine_head_dialogue:
            head_part = machine_catalog.get(machine_head_dialogue_part_key)
            draw_machine_head_dialogue(
                logical,
                start_menu_assets,
                title_font,
                menu_font,
                small,
                head_part.surface if head_part is not None else None,
                machine_head_dialogue_pages,
                machine_head_dialogue_page,
            )
        elif sable_dialogue:
            sable_frame = sable_idle_frames[int(atmosphere_time * SABLE_IDLE_FPS) % len(sable_idle_frames)] if sable_idle_frames else None
            sable_hit_rects = draw_sable_dialogue(
                logical, start_menu_assets, title_font, menu_font, small,
                sable_dialogue_mode, sable_dialogue_page, sable_dialogue_first_visit,
                sable_dialogue_selected if sable_dialogue_mode == "menu" else sable_shop_selected,
                sable_frame, machine_catalog, machine_inventory, machine_bits, sable_shop_status,
            )
            dialogue_hit_rects = []
        elif entity_dialogue:
            dialogue_hit_rects = draw_entity_dialogue(
                logical, title_font, menu_font, small, entity_choice, entity_dialogue_page,
                entity_dialogue_first_visit,
                int(guardian_dialogue_states.get(entity_dialogue_kind, {}).get("declined_count", 0)),
                entity_dialogue_kind,
            )
        elif shrine_dialogue:
            rendered_shrine_activated = (
                veil_warden_shrine_activated if shrine_dialogue_kind == VEIL_WARDEN_ID
                else rooted_crown_shrine_activated if shrine_dialogue_kind == ROOTED_CROWN_ID
                else shrine_activated if shrine_dialogue_kind == ENTITY_ID
                else bool(additional_shrine_activated.get(shrine_dialogue_kind, False))
            )
            dialogue_hit_rects = draw_shrine_dialogue(
                logical, title_font, menu_font, small, shrine_choice, shrine_dialogue_page,
                rendered_shrine_activated, first_witness_echoes_complete, shrine_dialogue_kind,
            )
        elif gleebs_dialogue:
            dialogue_hit_rects = draw_gleebs_dialogue(
                logical, start_menu_assets, title_font, menu_font, small, gleebs_option_font,
                gleebs_dialogue_topic,
                gleebs_dialogue_page,
                gleebs_dialogue_selected,
                world_key,
                battle_assets.get("gleebs"),
                entity_defeated,
                shrine_activated,
                first_witness_echoes_complete,
                rooted_crown_clue_discovered,
                rooted_crown_defeated,
                rooted_crown_shrine_activated,
                veil_warden_defeated,
                veil_warden_shrine_activated,
                witnessed_story_moments,
                rematch_wins,
                sum(1 for guardian_id in MEMORY_GUARDIAN_ORDER if guardian_id in defeated_boss_ids),
                defeated_boss_ids,
            )
        elif future_clue_dialogue:
            dialogue_hit_rects = draw_future_clue_dialogue(
                logical,
                title_font,
                menu_font,
                small,
                future_clue_choice,
                future_clue_dialogue_page,
                causal_resonance_learned,
                future_clue_dialogue_kind,
            )
        elif lore_archive_open:
            draw_lore_archive(logical, title_font, menu_font, small, discovered_lore, lore_archive_index)
        elif machine_inventory_open:
            machine_inventory_page = draw_machine_inventory(
                logical, menu_font, small, machine_catalog, machine_inventory, machine_bits, machine_inventory_page
            )

        if causal_notice.startswith("THE FIRST WITNESS IS RECORDED.") and not safe_mode:
            bind_strength = clamp((causal_notice_timer - 2.45) / 1.05, 0.0, 1.0)
            _draw_fullscreen_variant(logical, transition_assets.get("shrine_bind"), int(205 * bind_strength * _PRESENTATION_FLASH_SCALE))

        guidance_can_draw = bool(
            guidance_notice_timer > 0.0 and guidance_notice and not show_help and not causal_notice and not resonance_notice
            and lore_card_timer <= 0.0 and not paused and not start_menu_open and not lore_archive_open and not battle_active
            and not sable_dialogue and not entity_dialogue and not shrine_dialogue and not future_clue_dialogue
            and not gleebs_dialogue and not story_moment_id and not machine_workshop_open and not machine_head_dialogue and not machine_inventory_open
        )
        if guidance_can_draw:
            # Keep the continuity thread inside the logical 1280x720 safe area.
            # Long objective/action strings wrap at the final // separator rather
            # than allowing the presentation strip to extend beyond the screen.
            max_panel_width = W - 28
            max_text_width = max_panel_width - 34
            raw_guidance = str(guidance_notice)
            raw_line = _ui_render(small, raw_guidance, True, (182, 219, 223))
            guidance_lines = [raw_guidance]
            if raw_line.get_width() > max_text_width and " // " in raw_guidance:
                lead, action = raw_guidance.rsplit(" // ", 1)
                guidance_lines = [lead, action]

            rendered_guidance: list[pygame.Surface] = []
            for text_line in guidance_lines:
                rendered = _ui_render(small, text_line, True, (182, 219, 223))
                if rendered.get_width() > max_text_width:
                    scale = max_text_width / max(1, rendered.get_width())
                    fitted_size = (
                        max(1, int(round(rendered.get_width() * scale))),
                        max(1, int(round(rendered.get_height() * scale))),
                    )
                    rendered = pygame.transform.smoothscale(rendered, fitted_size)
                rendered_guidance.append(rendered)

            line_gap = 2
            content_width = max(line.get_width() for line in rendered_guidance)
            content_height = sum(line.get_height() for line in rendered_guidance) + line_gap * (len(rendered_guidance) - 1)
            box_width = min(max_panel_width, content_width + 34)
            box_height = content_height + 18
            box_center_y = 78 if len(rendered_guidance) > 1 else 74
            box = pygame.Rect(0, 0, box_width, box_height)
            box.center = (W // 2, box_center_y)
            if not _draw_hud_skin(logical, "guidance_panel", box):
                veil = pygame.Surface(box.size, pygame.SRCALPHA); veil.fill((5, 12, 16, 210)); logical.blit(veil, box)
                pygame.draw.rect(logical, (70, 119, 126), box, 1)

            text_y = box.centery - content_height // 2
            for rendered in rendered_guidance:
                rect = rendered.get_rect(midtop=(box.centerx, text_y))
                logical.blit(rendered, rect)
                text_y += rendered.get_height() + line_gap

        if causal_notice and not paused and not lore_archive_open and not battle_active and not sable_dialogue and not entity_dialogue and not shrine_dialogue and not future_clue_dialogue and not gleebs_dialogue and not story_moment_id and not machine_head_dialogue and not machine_inventory_open:
            notice = _ui_render(small, causal_notice, True, (220, 206, 181))
            notice_y = H - 190 if (machine_hotbar_visible and show_help) else (H - 102 if machine_hotbar_visible else H - 92)
            box = notice.get_rect(center=(W // 2, notice_y)).inflate(30, 16)
            veil = pygame.Surface(box.size, pygame.SRCALPHA); veil.fill((7, 7, 10, 205)); logical.blit(veil, box)
            pygame.draw.rect(logical, (111, 94, 82), box, 1)
            logical.blit(notice, notice.get_rect(center=box.center))

        if bits_notice and not paused and not start_menu_open and not battle_active and not sable_dialogue and not entity_dialogue and not shrine_dialogue and not future_clue_dialogue and not gleebs_dialogue and not story_moment_id and not machine_head_dialogue and not machine_inventory_open:
            notice = _ui_render(small, bits_notice, True, (172, 221, 225))
            box = notice.get_rect(topright=(W - 18, 62)).inflate(24, 12)
            veil = pygame.Surface(box.size, pygame.SRCALPHA); veil.fill((7, 12, 15, 205)); logical.blit(veil, box)
            pygame.draw.rect(logical, (78, 120, 130), box, 1)
            logical.blit(notice, notice.get_rect(center=box.center))

        if resonance_notice and not paused and not lore_archive_open and not battle_active and not sable_dialogue and not entity_dialogue and not shrine_dialogue and not future_clue_dialogue and not gleebs_dialogue and not story_moment_id and not machine_head_dialogue and not machine_inventory_open:
            notice = _ui_render(small, resonance_notice, True, (181, 219, 226))
            resonance_y = H - 228 if (machine_hotbar_visible and show_help) else (H - 140 if machine_hotbar_visible else H - 126)
            box = notice.get_rect(center=(W // 2, resonance_y)).inflate(30, 16)
            veil = pygame.Surface(box.size, pygame.SRCALPHA); veil.fill((7, 12, 15, 205)); logical.blit(veil, box)
            pygame.draw.rect(logical, (78, 120, 130), box, 1)
            logical.blit(notice, notice.get_rect(center=box.center))

        if lore_card_timer > 0.0 and not paused and not lore_archive_open and not battle_active and not sable_dialogue and not entity_dialogue and not shrine_dialogue and not future_clue_dialogue and not gleebs_dialogue and not story_moment_id and not machine_head_dialogue and not machine_inventory_open:
            draw_lore_card(logical, title_font, small, lore_card_title, lore_card_lines, lore_card_timer)

        if dev_console_open and not start_menu_open:
            draw_dev_console(logical, small, dev_console_text, dev_console_status)

        pause_menu_hit_rects = []
        slot_hit_rects = []
        settings_hit_controls = []
        controls_hit_rects = []
        quit_hit_rects = []
        if paused and not lore_archive_open and not battle_active and not sable_dialogue and not entity_dialogue and not shrine_dialogue and not future_clue_dialogue and not gleebs_dialogue and not story_moment_id and not machine_head_dialogue and not machine_inventory_open:
            if pause_screen == "settings":
                settings_hit_controls = draw_settings_menu(
                    logical, start_menu_assets, title_font, menu_font, small, settings_selected, settings, fullscreen,
                )
            elif pause_screen in ("save", "load"):
                slot_hit_rects = draw_save_slots_menu(
                    logical, start_menu_assets, title_font, menu_font, small, save_slot_selected, pause_screen, pause_status,
                )
            elif pause_screen == "controls":
                controls_hit_rects = draw_controls_menu(
                    logical, start_menu_assets, title_font, small, controller_bridge.connected,
                )
            elif pause_screen == "quit":
                quit_hit_rects = draw_quit_confirmation(
                    logical, start_menu_assets, title_font, menu_font, small, quit_selected,
                )
            else:
                pause_menu_hit_rects = draw_pause_menu(
                    logical, start_menu_assets, title_font, menu_font, small, pause_selected, pause_status,
                )

        start_menu_hit_rects = []
        if start_menu_open:
            if start_menu_screen == "main":
                start_menu_hit_rects = draw_start_menu(
                    logical,
                    start_menu_assets,
                    title_font,
                    menu_font,
                    small,
                    start_menu_selected,
                    continue_slot,
                    len(modes_unlocked),
                    start_menu_status,
                    atmosphere_time,
                )
            else:
                draw_start_menu_backdrop(logical, start_menu_assets, title_font, atmosphere_time)
                if start_menu_screen == "modes":
                    modes_hit_rects = draw_modes_menu(
                        logical, start_menu_assets, title_font, menu_font, small,
                        modes_selected, modes_progress, modes_unlocked, start_menu_status,
                    )
                elif start_menu_screen == "load":
                    slot_hit_rects = draw_save_slots_menu(
                        logical, start_menu_assets, title_font, menu_font, small,
                        save_slot_selected, "load", start_menu_status,
                    )
                elif start_menu_screen == "settings":
                    settings_hit_controls = draw_settings_menu(
                        logical, start_menu_assets, title_font, menu_font, small, settings_selected, settings, fullscreen,
                    )
                else:
                    controls_hit_rects = draw_controls_menu(
                        logical, start_menu_assets, title_font, small, controller_bridge.connected,
                    )

        _present_logical(window, logical)
        pygame.display.flip()
        if not first_frame_logged:
            _early_log("MAIN first frame presented successfully")
            first_frame_logged = True

        smoke_frames += 1
        if test_shot and smoke_frames == 4:
            shot_path = Path(test_shot).expanduser().resolve()
            shot_path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(window, str(shot_path))
        if smoke_test and smoke_frames >= 8:
            running = False

    try:
        pygame.mouse.set_visible(True)
    except pygame.error:
        pass
    controller_bridge.close()
    if mode_launch is not None:
        # Keep pygame alive: the mode adopts this exact SDL window, then
        # main() rebuilds the title here when it returns.
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.stop()
            pygame.event.clear()
        except pygame.error:
            pass
        _PENDING_MODE.append(mode_launch)
        return 0
    return 0


# Hand-off between one title session and the next (same process, same window).
_PENDING_MODE: list = []
_PENDING_TITLE_NOTICE: list[str] = []


def _draw_mode_transition(title: str) -> None:
    """One black frame with the mode name so the handoff never shows stale art."""
    window = pygame.display.get_surface()
    if window is None:
        return
    try:
        window.fill((0, 0, 0))
        font = pygame.font.SysFont("georgia", max(24, window.get_height() // 24))
        text = font.render(title, True, (220, 212, 198))
        window.blit(text, text.get_rect(center=window.get_rect().center))
        pygame.display.flip()
    except pygame.error:
        pass


def _report_to_holoverse() -> None:
    """When HoloVerse launched this process, leave it the archive's progress (saved + this session)."""
    if not holoverse_link.hosted():
        return
    try:
        saved = mode_progress()
        ok = holoverse_link.report_to_holoverse(saved.guardians, saved.campaign_complete)
    except Exception as exc:
        ok = holoverse_link.report_to_holoverse()
        _early_log(f"HOLOVERSE progress read failed {type(exc).__name__}: {exc}")
    _early_log(f"HOLOVERSE result written={int(ok)}")


def main() -> int:
    """Afterlife hub loop: title session -> optional hosted mode -> title again."""
    while True:
        _PENDING_MODE.clear()
        rc = _run_session()
        if not _PENDING_MODE:
            _report_to_holoverse()
            _shutdown_pygame_for_process_exit()
            _early_log("MAIN clean shutdown")
            return rc
        spec = _PENDING_MODE.pop()
        folder = mode_host.find_mode_dir(spec)
        if folder is None:
            _PENDING_TITLE_NOTICE.append(f"{spec.title} IS NOT INSTALLED")
            continue
        _draw_mode_transition(spec.title)
        _early_log(f"MAIN handing active display to {spec.title} at {folder}")
        code, notice = mode_host.run_mode(spec, folder, log=_early_log, restore_fault_handler=_restore_host_faulthandler)
        _early_log(f"MAIN {spec.title} returned rc={code}; rebuilding the Afterlife title in the same window")
        if notice:
            _PENDING_TITLE_NOTICE.append(notice)


if __name__ == "__main__":
    sys.excepthook = _write_crash_log
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        exc_type, exc_value, exc_tb = sys.exc_info()
        _early_log(f"MAIN unhandled exception {exc_type.__name__}: {exc_value}")
        _write_crash_log(exc_type, exc_value, exc_tb)
        # One automatic recovery attempt.  It intentionally preserves gameplay,
        # saves, temporal state and authored composition while disabling only
        # optional FX/audio paths.  Never recurse if safe mode itself fails.
        if "--safe-mode" not in sys.argv:
            try:
                pygame.quit()
            except Exception:
                pass
            sys.argv.append("--safe-mode")
            try:
                raise SystemExit(main())
            except SystemExit:
                raise
            except Exception:
                exc_type, exc_value, exc_tb = sys.exc_info()
                _write_crash_log(exc_type, exc_value, exc_tb)
                raise
        raise
    finally:
        try:
            pygame.quit()
        except Exception:
            pass
