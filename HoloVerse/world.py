import colorsys
import json
import math
import os
import random
import sys
import time
import textwrap
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from holoverse.world_geometry import (
    MAIN_AREA_RADIUS,
    SURFACE_OUTER_RADIUS,
    METROPOLIS_INNER_RADIUS,
    METROPOLIS_INFINITE,
    surface_rings,
    surface_ring_for_key,
    HOLOSPACE_VIEW_RADIUS,
    HOLOSPACE_FOCUS_Y,
    HOLOSPACE_BOT_Y,
    region_travel_for_number,
)

from holoverse.forest_region import (
    FOREST_DETAIL_PATCHES_PER_SECTOR,
    FOREST_DETAIL_PLANTS_PER_PATCH,
    FOREST_UNDERSTORY_BUSHES_PER_PATCH,
    FOREST_UNDERSTORY_FERNS_PER_PATCH,
    FOREST_UNDERSTORY_GRASS_PER_PATCH,
    generate_forest_detail_patches,
    generate_forest_understory_items,
)
from holoverse.hills_region import (
    HILLS_MEADOW_ITEMS_PER_SECTOR,
    HILLS_REPEAT_BANDS,
    HILLS_SOLID_TREES_PER_SECTOR,
    generate_hills_meadow_items,
    generate_hills_solid_tree_items,
    repeating_hills_relief_at,
)
from holoverse.mushroom_region import (
    MUSHROOM_STRUCTURES_PER_SECTOR,
    generate_mushroom_structures,
)
from holoverse.desert_region import (
    DESERT_DUNE_WAVES,
    DESERT_MACRO_STRUCTURES_PER_SECTOR,
    desert_dune_relief_at,
    generate_desert_macro_structures,
)
from holoverse.ice_region import (
    ICE_GLACIAL_WAVES,
    ICE_MACRO_STRUCTURES_PER_SECTOR,
    ice_glacial_relief_at,
    generate_ice_macro_structures,
)
from holoverse.urban_region import (
    URBAN_STRUCTURES_PER_SECTOR, URBAN_TOTAL_STRUCTURES, generate_urban_structures,
)
try:
    # Pass 282.51 shaded ring ground needs numpy (listed in requirements.txt).
    # Without it the accepted flat sector fills below are used unchanged.
    from holoverse import ring_ground as _ring_ground
except Exception as _ring_ground_import_error:  # pragma: no cover - depends on runtime
    _ring_ground = None
    print(f"ring_ground_unavailable: {_ring_ground_import_error.__class__.__name__}: {_ring_ground_import_error}")
from holoverse import metropolis_layout as _metro_layout
from holoverse import urban_conflict as _urban_conflict
try:
    # Pass 282.52 Metropolis city meshes (numpy); falls back to the Pass 91 city.
    from holoverse import metropolis_city as _metro_city
except Exception as _metro_city_import_error:  # pragma: no cover - depends on runtime
    _metro_city = None
    print(f"metropolis_city_unavailable: {_metro_city_import_error.__class__.__name__}: {_metro_city_import_error}")
try:
    # Pass 282.53 Urban ruins + robot war (needs the numpy mesh builder).
    from holoverse import urban_visuals as _urban_visuals
except Exception as _urban_visuals_import_error:  # pragma: no cover - depends on runtime
    _urban_visuals = None
    print(f"urban_visuals_unavailable: {_urban_visuals_import_error.__class__.__name__}: {_urban_visuals_import_error}")
from holoverse import ice_civilization as _ice_civ
from holoverse import desert_civilization as _desert_civ
from holoverse import fungal_civilization as _fungal_civ
try:
    # Pass 282.54 Ice towns, spires and life (needs the numpy mesh builder).
    from holoverse import ice_visuals as _ice_visuals
except Exception as _ice_visuals_import_error:  # pragma: no cover - depends on runtime
    _ice_visuals = None
    print(f"ice_visuals_unavailable: {_ice_visuals_import_error.__class__.__name__}: {_ice_visuals_import_error}")
try:
    # Shared numpy mesh kit for the ring civilizations (Pass 282.54/282.55).
    from holoverse import region_mesh_kit as _region_mesh_kit
except Exception as _region_mesh_kit_import_error:  # pragma: no cover - depends on runtime
    _region_mesh_kit = None
    print(f"region_mesh_kit_unavailable: {_region_mesh_kit_import_error.__class__.__name__}: {_region_mesh_kit_import_error}")
try:
    # Pass 282.55 Desert pyramids, towns and life.
    from holoverse import desert_visuals as _desert_visuals
except Exception as _desert_visuals_import_error:  # pragma: no cover - depends on runtime
    _desert_visuals = None
    print(f"desert_visuals_unavailable: {_desert_visuals_import_error.__class__.__name__}: {_desert_visuals_import_error}")
try:
    # Pass 282.56 alien fungal ring, plus Nyx (the giant) and Orbit as skinned characters.
    from holoverse import fungal_visuals as _fungal_visuals
    from holoverse import ual_actor as _ual_actor
except Exception as _fungal_visuals_import_error:  # pragma: no cover - depends on runtime
    _fungal_visuals = None
    _ual_actor = None
    print(f"fungal_visuals_unavailable: {_fungal_visuals_import_error.__class__.__name__}: {_fungal_visuals_import_error}")
try:
    # Pass 282.57: dimension gates beside IO (start) and Mirror (Metropolis).
    from holoverse import dimension_gate as _dimension_gate
except Exception as _dimension_gate_import_error:  # pragma: no cover - depends on runtime
    _dimension_gate = None
    print(f"dimension_gate_unavailable: {_dimension_gate_import_error.__class__.__name__}: {_dimension_gate_import_error}")

try:
    from PIL import Image, ImageDraw
except Exception:
    Image = None
    ImageDraw = None

SELF_TEST = "--self-test" in sys.argv
AUTO_EXIT = "--auto-exit" in sys.argv

def get_cli_arg(flag: str, default=None, cast=str):
    if flag in sys.argv:
        try:
            return cast(sys.argv[sys.argv.index(flag) + 1])
        except Exception:
            return default
    return default

SELF_TEST_VIEW = get_cli_arg("--view", "default", str)
SELF_TEST_SCREENSHOT = get_cli_arg("--screenshot", None, str)

from panda3d.core import loadPrcFileData

def build_prc_text() -> str:
    script_root = Path(__file__).resolve().parent
    asset_path = (script_root / "assets").as_posix()
    prc_lines = [
        "window-title HoloVerse Observatory",
        "win-size 1920 1080",
        "show-frame-rate-meter 0",
        "sync-video 1",
        "framebuffer-multisample 1",
        "multisamples 4",
        "texture-anisotropic-degree 16",
        "notify-level-display warning",
        "notify-level-glgsg warning",
        "cursor-hidden 1",
        "audio-library-name null",
        f"model-path {asset_path}",
    ]
    if SELF_TEST:
        prc_lines.extend([
            "window-type offscreen",
            "load-display p3tinydisplay",
            "aux-display p3tinydisplay",
        ])
    return "\n".join(prc_lines) + "\n"


PRC = build_prc_text()
loadPrcFileData("", PRC)

from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from direct.task import Task
from panda3d.core import (
    AmbientLight,
    AntialiasAttrib,
    ClockObject,
    DirectionalLight,
    Filename,
    Fog,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    InputDevice,
    LineSegs,
    LODNode,
    NodePath,
    TextNode,
    TransparencyAttrib,
    CollisionBox,
    CollisionNode,
    BitMask32,
    CardMaker,
    Vec2,
    Vec3,
    Vec4,
    WindowProperties,
)

VERSION = "1.13.18-render-budget-distance-lod"
GAME_NAME = "HoloVerse Observatory"
ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
TEXTURES_DIR = ASSETS / "textures"
MODELS_DIR = ASSETS / "models"
CONFIG_DIR = ASSETS / "config"
from holoverse_userdata import state_root as _hv_state_root, log_root as _hv_log_root
RUNTIME_STATE_DIR = _hv_state_root()        # Pass 282.68: player files outside the game folder
WORLD_RUNTIME_STATE_DIR = RUNTIME_STATE_DIR / "world"
LOG_DIR = _hv_log_root()
PATCH_DIR = ROOT / "patch_notes"
CONFIG_PATH = CONFIG_DIR / "holoverse_config.json"
RUNTIME_SETTINGS_DIR = RUNTIME_STATE_DIR / "settings"
RUNTIME_CONFIG_PATH = RUNTIME_SETTINGS_DIR / "holoverse_config.json"
RUNTIME_AUDIO_BUS_PATH = RUNTIME_SETTINGS_DIR / "holoverse_audio_bus.json"
LATEST_LOG = LOG_DIR / "latest.log"
CRASH_LOG = LOG_DIR / "crash.log"
LATEST_PATCH = PATCH_DIR / "latest_patch_notes.txt"
SELF_TEST_REPORT = LOG_DIR / "self_test_report.json"
USER_BUILD_SAVE_PATH = WORLD_RUNTIME_STATE_DIR / "holoverse_user_builds.json"
SPACE_BUILD_PROGRESS_PATH = WORLD_RUNTIME_STATE_DIR / "space_build_progress.txt"
SPACE_BUILD_PROGRESS_LEGACY_JSON_PATH = WORLD_RUNTIME_STATE_DIR / "space_build_progress.json"
SPACE_SKY_TEXTURE_PATH = TEXTURES_DIR / "hub" / "matrixcore_space.png"
MAX_INTERNAL_PROJECTILES = 96
MAX_WEAPON_PROJECTILES = 32
MAX_WORLD_ACTORS = 96
MAX_TERRAIN_RENDER_RADIUS = 3
MAX_SELF_TEST_TERRAIN_RENDER_RADIUS = 2
MAX_TERRAIN_CHUNKS = (MAX_TERRAIN_RENDER_RADIUS * 2 + 1) ** 2
NEON_RACE_WORLD_ID = 0
FLATLAND_DISC_RADIUS = float(MAIN_AREA_RADIUS)
FLATLAND_MINOR_STEP = 12.0
FLATLAND_MAJOR_STEP = 48.0
BIOME_SECTOR_COUNT = 48
BIOME_STREAM_SECTOR_RADIUS = 2
MAX_BIOME_TERRAIN_CHUNKS = 28
BIOME_RINGS = surface_rings()
BIOME_OUTER_RADIUS = float(SURFACE_OUTER_RADIUS)
BIOME_PROFILE_GUIDE_DEGREES = tuple(range(0, 360, 45))
BIOME_CORRIDOR_DEGREES = (-90.0, 0.0, 90.0, 180.0)
BIOME_ANCHOR_ANGLE_DEG = -90.0
BIOME_CONTOUR_T_VALUES = (0.18, 0.36, 0.50, 0.64, 0.82)
BIOME_HORIZON_GUIDE_T_VALUES = (0.32, 0.58, 0.78)
BIOME_FLOW_RIBBON_DEGREES = tuple(range(0, 360, 22))
BIOME_SEAM_BRAID_OFFSETS = (-64.0, -32.0, 0.0, 32.0, 64.0)
BIOME_INTERIOR_RHYTHM_T_VALUES = (0.24, 0.42, 0.60, 0.78)
ICE_TERRAIN_CELL_SIZE = 42.0
ICE_TERRAIN_STEP_HEIGHT = 1.18
ICE_TERRAIN_BLOCKS_PER_CHUNK = 6
ICE_FLOATING_CUBES_PER_CHUNK = 2
ICE_FAUNA_GROUPS_PER_CHUNK = 2
URBAN_RUIN_GROUPS_PER_CHUNK = 12
URBAN_STRUCTURED_BLOCKS_PER_CHUNK = 14
URBAN_BATTLE_GROUPS_PER_CHUNK = 5
URBAN_MECH_GROUPS_PER_CHUNK = 4
URBAN_DRONES_PER_CHUNK = 7
URBAN_SKELETON_GROUPS_PER_CHUNK = 6
URBAN_AIRSTRIKE_GROUPS_PER_CHUNK = 3
URBAN_TRENCH_LINES_PER_CHUNK = 7
URBAN_SMOKE_COLUMNS_PER_CHUNK = 7
URBAN_STREET_LANES_PER_CHUNK = 6
URBAN_VECTOR_DISTRICT_FRAMES_PER_CHUNK = 12
URBAN_FRONTLINE_ANCHORS_PER_CHUNK = 3
URBAN_BATTLE_BEAMS_PER_CHUNK = 9
METROPOLIS_INFILL_FADE_SECONDS = 0.0  # Pass 91: disabled; solid chunk structures appear fully visible

# Pass 282.46 render-budget policy.  Large/identity-bearing forms remain
# visible across the authored region; tiny floor detail is culled by Panda's
# LOD traverser once it is too distant to contribute readable pixels.
FOREST_UNDERSTORY_LOD_FAR = 560.0
HILLS_MEADOW_LOD_FAR = 620.0

METROPOLIS_INFILL_FADE_MIN_ALPHA = 1.0
FOREST_TALL_TREE_BONUS_PER_CHUNK = 8
# Pass 282.21: every streamed forest sector receives the same deterministic
# dense-canopy budget.  Geometry remains sector-batched and only nearby sectors
# exist in the scene graph, so full-ring coverage does not mean full-ring cost.
FOREST_DETAIL_PATCH_COUNT = int(FOREST_DETAIL_PATCHES_PER_SECTOR)
FOREST_DETAIL_PLANT_COUNT_PER_PATCH = int(FOREST_DETAIL_PLANTS_PER_PATCH)
FOREST_UNDERSTORY_BUSH_COUNT_PER_PATCH = int(FOREST_UNDERSTORY_BUSHES_PER_PATCH)
FOREST_UNDERSTORY_FERN_COUNT_PER_PATCH = int(FOREST_UNDERSTORY_FERNS_PER_PATCH)
FOREST_UNDERSTORY_GRASS_COUNT_PER_PATCH = int(FOREST_UNDERSTORY_GRASS_PER_PATCH)
# Full-detail rings keep all 48 authored sector chunks resident only while that
# region is active.  Panda can cull the independent sector branches normally;
# we do not flatten an entire world ring.  Pass 282.34 promotes Mushroom after
# its wire grammar is batched and its solid fungal architecture is established.
FOREST_FULL_RING_STREAMING = True
FOREST_FULL_RING_KEY = 2
FOREST_FULL_RING_HILLSIDE_RETENTION = 0.0  # Pass 282.32: retired; detailed rings are exclusive
ACTIVE_FULL_RING_KEYS = (2, 3, 4, 5, 6, 7)
ACTIVE_RING_EXCLUSIVE_STREAMING = True
MAX_BIOME_TERRAIN_CHUNKS = max(MAX_BIOME_TERRAIN_CHUNKS, BIOME_SECTOR_COUNT + BIOME_STREAM_SECTOR_RADIUS * 2 + 1)
# Pass 282.51: shaded level-of-detail ring ground (holoverse/ring_ground.py).
# The sector ground sheet replaces the flat unlit fill plus the wire contour,
# stitch-rail and seam lines on these rings.  Chunks outside the player's
# sector neighbourhood are built a few per frame instead of all at once.
RING_GROUND_ENABLED = True
RING_GROUND_KINDS = ("forest", "hills", "mushroom", "desert", "ice", "urban")
RING_GROUND_SYNC_SECTOR_RADIUS = 0   # built in the same frame the ring is entered
RING_GROUND_NEAR_SECTOR_RADIUS = 1   # always near-tier ground around the player
RING_GROUND_FRAME_BUDGET_MS = 4.0
RING_GROUND_TIER_CHECK_SECONDS = 0.20
HILLS_SOLID_PLANTS_PER_CHUNK = 18  # legacy count name; Pass 282.32 uses batched meadow shapes
HILLS_MEADOW_SHAPE_COUNT_PER_SECTOR = int(HILLS_MEADOW_ITEMS_PER_SECTOR)
DEEP_WATER_OCCLUSION_FOG_NEAR = 6.0
DEEP_WATER_OCCLUSION_FOG_FAR = 118.0
DEEP_WATER_CRAFT_EYE_OFFSET = 1.18
DEEP_WATER_CRAFT_VERTICAL_BOB = 0.025
DEEP_WATER_CRAFT_SPEED_SCALE = 1.18
CRAFT_FLIGHT_SPEED_MULTIPLIER = 10.0
CRAFT_FLIGHT_VERTICAL_SPEED_SCALE = 0.88
CRAFT_FLIGHT_MIN_CLEARANCE = 8.0
CRAFT_FLIGHT_MAX_EYE_Z = 1480.0
CRAFT_HUB_LOCK_PADDING = 4.0
SPACE_BUILD_PROGRESS_BASE = 0.0
SPACE_BUILD_PROGRESS_RATE = 0.00042
SPACE_BUILD_AUTOSAVE_INTERVAL = 5.0
SPACE_BUILD_VISUAL_FLOOR = 0.08
SPACE_BUILD_RING_COUNT = 6
SPACE_BUILD_ARCS_PER_RING = 20
SPACE_BUILD_NODE_COUNT = SPACE_BUILD_RING_COUNT * SPACE_BUILD_ARCS_PER_RING
CRAFT_STRATOSPHERE_START_Z = 180.0
CRAFT_STRATOSPHERE_END_Z = 1180.0
CRAFT_VISUAL_FORWARD_OFFSET = 4.2
CRAFT_VISUAL_VERTICAL_OFFSET = -1.65
CRAFT_VISUAL_SCALE = 1.58
SPACE_LAYER_START_Z = 420.0
SPACE_LAYER_FULL_Z = 960.0
SPACE_LAYER_STAR_COUNT = 40
SPACE_LAYER_ASTEROID_COUNT = 3
SPACE_LAYER_FIELD_RADIUS = 820.0
SPACE_LAYER_FIELD_DEPTH = 520.0
# Pass 79: HoloSpace key 8 now uses a true 3D landmark instead of the old
# bare scaffold. It reads as a distant vector black hole with a replaceable
# sphere mesh hook, dark matter ribbons, and a slow 4D octagonal surround.
SPACE_DYSON_ROOT_POS = Vec3(0.0, float(HOLOSPACE_FOCUS_Y), 1020.0)
SPACE_DYSON_FOCUS_POS = Vec3(0.0, float(HOLOSPACE_FOCUS_Y), 1185.0)
SPACE_DYSON_VIEW_POS = Vec3(0.0, -float(HOLOSPACE_VIEW_RADIUS), 1096.0)
SPACE_DYSON_BOT_ANCHOR = Vec3(258.0, float(HOLOSPACE_BOT_Y), 1112.0)
SPACE_DYSON_RADIUS = 320.0
SPACE_DYSON_OUTER_RADIUS = 432.0
SPACE_DYSON_EVENT_HORIZON_RADIUS = 122.0
SPACE_DYSON_INSPECTOR_COUNT = 3
SPACE_DYSON_PLAYER_COLLISION_PADDING = 26.0
SPACE_DYSON_BUILD_BAND_COUNT = 5
SPACE_DYSON_BUILD_SLOT_COUNT = 6
SPACE_DYSON_MESH_BASENAMES = ("dyson_sphere", "black_hole_sphere", "holospace_sphere", "dyson_core")
SPACE_WHITE_DWARF_RADIUS = 38.0
SPACE_WHITE_DWARF_HALO_RADIUS = 205.0
SPACE_GRAVITY_LENS_RING_COUNT = 2
SPACE_PHOTON_BEAM_COUNT = 2
SPACE_LENSING_CAUSTIC_COUNT = 2
MINI_BIOME_DENSITY_DIVISOR = 5
SALVAGE_POPULATION_PER_CHUNK = 6
SALVAGE_POPULATION_SIZE_SCALE = 4.8
# Pass 282.24: keep the accepted pre-full-ring animated population ceiling.
# Increasing resident static Forest sectors must not silently multiply active
# salvage actors and per-frame update work.
MAX_SALVAGE_POPULATION_NODES = 28 * SALVAGE_POPULATION_PER_CHUNK

MAX_NAMED_REGION_BOTS = 10        # Pass 282.56 adds the giant Nyx at the fungal port
NAMED_REGION_BOT_SCALE = 4.20
NAMED_REGION_BOT_HOVER_AMPLITUDE = 1.15
METROPOLIS_NAMED_BOT_CLEAR_RADIUS = 260.0
METROPOLIS_SPAWN_ANCHOR_T = 0.50
METROPOLIS_GUIDE_WANDER_RADIUS = 10.0      # Pass 282.57: Mirror keeps close to his gate
METROPOLIS_GUIDE_WANDER_SPEED = 0.090
ICE_GUIDE_WANDER_RADIUS = 98.0             # (before Pass 282.58 gave the Archivist a gate)
GATE_GUIDE_WANDER_RADIUS = 8.0             # Pass 282.58: a guide with a gate stays beside it
ICE_GUIDE_WANDER_SPEED = 0.092
GATE_GUIDE_ROAM_RADIUS = 7.0               # host roam radius for a guide standing at a gate
START_GATE_GUIDE_XY = (0.0, -28.5)         # Pass 282.62: IO waits in the hub, just behind the spawn, clear of every artifact lane
METROPOLIS_GATE_GUIDE_XY = (30.0, -5066.0) # Mirror, beside a cleared city lot off the boulevard
NAMED_REGION_BOT_HOVER_SPEED = 0.82
NAMED_REGION_BOT_ANCHOR_ANGLE_DEG = BIOME_ANCHOR_ANGLE_DEG
# Pass 282.58: every guide but Nyx stands at a dimension gate; a guide with an
# in-world activity offers it as a second option in the dialogue.
# Pass 282.57 roster:
#   IO      FLAT        in the hub behind the spawn; Afterlife of IO opens only from his dialogue (282.62)
#   Solace  GREEN HILLS Anomaly Sequence gate (Pass 282.81: the Oddities activity was removed)
#   Nyx     MUSHROOM    the giant of The Indigo Giant, at the REDACTED port with Orbit
#   Archivist ICE       The Archivist gate (Pass 282.81: Frost Circuit was removed)
#   Mirror  METROPOLIS  Mirror's Limbo gate (moved from Ice; Robot Lab unhooked)
NAMED_REGION_BOT_MAP = [
    {"name": "IO", "region": "FLAT", "activity": "AFTERLIFE OF IO", "ring_key": 1, "kind": "flat", "color": (0.78, 0.82, 0.86), "accent": (1.00, 0.92, 0.70), "anchor_t": 0.22, "scale": 1.00, "wander_radius": 1.5, "wander_speed": 0.060, "activity_flag": "", "anchor_xy": START_GATE_GUIDE_XY},  # Pass 282.62: no gate; Afterlife of IO opens only from IO's dialogue
    {"name": "Vanta", "region": "FORESTS", "activity": "GLYPHBOUND", "ring_key": 2, "kind": "forest", "color": (0.05, 0.72, 0.28), "accent": (0.48, 1.00, 0.34), "anchor_t": 0.30, "scale": 1.02, "wander_radius": GATE_GUIDE_WANDER_RADIUS, "wander_speed": 0.052, "activity_flag": "forest_growth_active", "gate": {"title": "Glyphbound", "along": 24.0, "outward": 0.0}},
    {"name": "Solace", "region": "GREEN HILLS", "activity": "ANOMALY SEQUENCE", "ring_key": 3, "kind": "hills", "color": (1.00, 0.24, 0.88), "accent": (0.15, 1.00, 1.00), "anchor_t": 0.38, "scale": 1.05, "wander_radius": GATE_GUIDE_WANDER_RADIUS, "wander_speed": 0.046, "activity_flag": "oddities_active", "gate": {"title": "Anomaly Sequence", "along": 24.0, "outward": 0.0}},
    # Pass 282.56/57: Nyx, the giant of the REDACTED archive (The Indigo Giant), stands at the port with Orbit.
    {"name": "Nyx", "region": "MUSHROOM", "activity": "THE INDIGO GIANT", "ring_key": 4, "kind": "mushroom", "color": (0.27, 0.54, 0.92), "accent": (0.55, 0.62, 1.00), "anchor_t": 0.62, "scale": 1.0, "wander_radius": 0.0, "wander_speed": 0.0, "activity_flag": "", "character": "giant", "port_offset": (16.0, 0.0)},
    {"name": "Ember", "region": "DESERT", "activity": "VECTOR WARS", "ring_key": 5, "kind": "desert", "color": (1.00, 0.42, 0.12), "accent": (1.00, 0.82, 0.30), "anchor_t": 0.54, "scale": 1.04, "wander_radius": GATE_GUIDE_WANDER_RADIUS, "wander_speed": 0.078, "activity_flag": "desert_ships_active", "gate": {"title": "Vector Wars", "along": -26.0, "outward": 0.0}},
    {"name": "Archivist", "region": "ICE", "activity": "THE ARCHIVIST", "ring_key": 6, "kind": "ice", "color": (0.30, 0.62, 1.00), "accent": (0.76, 0.88, 1.00), "anchor_t": 0.62, "scale": 1.08, "wander_radius": GATE_GUIDE_WANDER_RADIUS, "wander_speed": ICE_GUIDE_WANDER_SPEED, "activity_flag": "frost_circuit_active", "gate": {"title": "The Archivist", "along": -24.0, "outward": 0.0}},
    {"name": "Sable", "region": "URBAN", "activity": "ANATOMIC", "ring_key": 7, "kind": "urban", "color": (0.90, 0.08, 0.18), "accent": (0.34, 0.36, 0.40), "anchor_t": 0.70, "scale": 1.06, "wander_radius": GATE_GUIDE_WANDER_RADIUS, "wander_speed": 0.054, "activity_flag": "urban_warzone_active", "gate": {"title": "Anatomic", "along": 26.0, "outward": 0.0}},
    {"name": "Mirror", "region": "METROPOLIS", "activity": "MIRROR'S LIMBO", "ring_key": 8, "kind": "metropolis", "color": (0.68, 0.92, 1.00), "accent": (1.00, 1.00, 1.00), "anchor_t": METROPOLIS_SPAWN_ANCHOR_T, "scale": 1.02, "wander_radius": METROPOLIS_GUIDE_WANDER_RADIUS, "wander_speed": METROPOLIS_GUIDE_WANDER_SPEED, "activity_flag": "", "anchor_xy": METROPOLIS_GATE_GUIDE_XY, "gate": {"title": "Mirror's Limbo", "along": 14.0, "outward": 14.0, "snap": "metropolis_lot"}},
    # Orbit, Nyx's companion, stands at his feet; Orbit still opens HoloSpace flight.
    {"name": "Orbit", "region": "MUSHROOM", "activity": "HOLOSPACE FLIGHT", "ring_key": 4, "kind": "mushroom", "color": (0.77, 0.73, 0.70), "accent": (0.45, 0.82, 1.00), "anchor_t": 0.62, "scale": 1.0, "wander_radius": 0.0, "wander_speed": 0.0, "activity_flag": "holospace_active", "character": "human", "port_offset": (19.5, -3.0), "gate": {"title": "HoloMap", "along": 16.0, "outward": 4.0}},
]
NAMED_REGION_BOT_MAPPING = {item["name"]: item["region"] for item in NAMED_REGION_BOT_MAP}
DEEP_WATER_SKY_CREATURES_PER_CHUNK = 0
DEEP_WATER_ONLY_SECTOR_RADIUS = 2
DEEP_WATER_LITE_MODE = True
DEEP_WATER_ENABLE_CREATURES = False
DEEP_WATER_ENABLE_FLORA = False
DEEP_WATER_ENABLE_FEATURES = False
DEEP_WATER_ENABLE_SALVAGE = False
DEEP_WATER_SURFACE_MAX_LINES_PER_CHUNK = 0
MUSHROOM_FOREST_GROUPS_PER_CHUNK = 8
MUSHROOM_CLUSTER_CAP_STEPS = 8
MUSHROOM_HILL_LINE_COUNT = 8
METROPOLIS_CHUNK_SIZE = 320.0
METROPOLIS_STREAM_RADIUS = 2   # Pass 282.52: 5 x 5 chunks (1.6 km) so the skyline never pops inside the fog
METROPOLIS_CITY_ENABLED = True
# Pass 282.53: dystopian Urban ring (ruins, robot war, Sable's fight, smog).
URBAN_CONFLICT_ENABLED = True
URBAN_SMOG_RGB = (0.30, 0.11, 0.055)   # matches the smog dome horizon
URBAN_SMOG_BLEND_METRES = 160.0
URBAN_WAR_BAND_METRES = 350.0
URBAN_KEEP_CLEAR_RADIUS = 125.0   # no collapsed blocks; debris may come within 26 m
# Pass 282.54: peaceful Ice civilization (Frostkin towns, ice spires, aurora, frost haze).
ICE_CIVILIZATION_ENABLED = True
ICE_HAZE_BLEND_METRES = 160.0
ICE_LIFE_BAND_METRES = 300.0
# Pass 282.55: peaceful Desert civilization (obsidian pyramids, oasis towns, caravans, dusk haze).
DESERT_CIVILIZATION_ENABLED = True
DESERT_HAZE_BLEND_METRES = 160.0
DESERT_LIFE_BAND_METRES = 300.0
# Pass 282.56: alien fungal Mushroom ring (Sporekin hollows, giant fungi, Nyx and Orbit's port).
FUNGAL_CIVILIZATION_ENABLED = True
FUNGAL_HAZE_BLEND_METRES = 160.0
FUNGAL_LIFE_BAND_METRES = 300.0
CHARACTER_LOAD_RADIUS = 1400.0    # Nyx and Orbit load (a step a frame) inside this distance
CHARACTER_LOOKS = {
    # the Indigo Giant archive's own palettes for its giant and its human
    "giant": {"height": 20.0, "palette": ((0.27, 0.54, 0.92, 1.0), (0.12, 0.29, 0.63, 1.0)), "rim": (0.36, 0.30, 1.00, 0.55), "focus": 13.0},
    "human": {"height": 1.8, "palette": ((0.77, 0.73, 0.70, 1.0), (0.53, 0.48, 0.45, 1.0)), "rim": (0.0, 0.0, 0.0, 0.0), "focus": 1.5},
}
REGION_CIV_SYNC_REACH = 1       # sectors either side of the player built with their chunk
REGION_CIV_ATTACH_REACH = 3     # further sectors are attached a step per frame (layout, mesh, attach)
METROPOLIS_PRELOAD_RADIUS = METROPOLIS_STREAM_RADIUS
MAX_METROPOLIS_CHUNKS = (METROPOLIS_PRELOAD_RADIUS * 2 + 1) ** 2
METROPOLIS_LOTS_PER_AXIS = 4
METROPOLIS_INNER_CLEARANCE = 42.0
METROPOLIS_SEAM_Z_BIAS = 0.034
METROPOLIS_VEHICLES_PER_CHUNK = 3
METROPOLIS_ROBOTS_PER_CHUNK = 7
METROPOLIS_ENTRY_BLEND = 280.0
BIOME_TRANSITION_BLEND = 0.080
SPACE_SKY_RGB = (0.006, 0.010, 0.030)
SPACE_SKY_SHELL_RADIUS = 420.0
SPACE_SKY_LAT_STEPS = 20
SPACE_SKY_LON_STEPS = 40
CELESTIAL_ORBIT_RADIUS = 245.0
CELESTIAL_STAR_COUNT = 84
FOREST_TREE_VARIANTS = ("spire", "canopy", "split", "tower")
SPACE_SKY_AUTHORITY = {"rgb": SPACE_SKY_RGB, "texture": SPACE_SKY_TEXTURE_PATH.name}
BIOME_LUSH_PALETTES = {
    "flat": {
        "fill": (0.050, 0.170, 0.075), "soft": (0.160, 0.500, 0.190), "line": (0.420, 0.950, 0.300),
        "accent": (0.850, 1.000, 0.420), "trunk": (0.420, 0.290, 0.145), "canopy": (0.270, 0.900, 0.260),
    },
    "forest": {
        # Pass: deeper trunks + layered emerald canopy colors render more clearly
        # against the forest floor than the old flat neon-green tree set.
        "fill": (0.014, 0.150, 0.058), "soft": (0.060, 0.410, 0.145), "line": (0.320, 1.000, 0.390),
        "accent": (0.780, 1.000, 0.360), "trunk": (0.345, 0.185, 0.088), "canopy": (0.120, 0.780, 0.245),
    },
    "hills": {
        "fill": (0.105, 0.420, 0.055), "soft": (0.260, 0.760, 0.130), "line": (0.640, 1.000, 0.220),
        "accent": (0.840, 1.000, 0.260), "trunk": (0.250, 0.360, 0.120), "canopy": (0.520, 1.000, 0.180),
    },
    "water": {
        "fill": (0.012, 0.185, 0.235), "soft": (0.060, 0.520, 0.660), "line": (0.150, 0.900, 0.950),
        "accent": (0.560, 1.000, 0.820), "trunk": (0.120, 0.320, 0.290), "canopy": (0.190, 0.760, 0.560),
    },
    "mushroom": {
        "fill": (0.240, 0.045, 0.205), "soft": (0.760, 0.130, 0.680), "line": (1.000, 0.270, 0.920),
        "accent": (0.090, 1.000, 1.000), "trunk": (0.780, 0.520, 0.840), "canopy": (1.000, 0.180, 0.720),
    },
    "desert": {
        "fill": (0.235, 0.145, 0.092), "soft": (0.680, 0.390, 0.285), "line": (1.000, 0.720, 0.500),
        "accent": (1.000, 0.660, 0.760), "trunk": (0.600, 0.365, 0.170), "canopy": (0.760, 0.520, 0.280),
    },
    "ice": {
        "fill": (0.020, 0.148, 0.250), "soft": (0.110, 0.455, 0.740), "line": (0.400, 0.900, 1.000),
        "accent": (0.760, 0.980, 1.000), "trunk": (0.200, 0.390, 0.560), "canopy": (0.390, 0.800, 0.920),
    },
    "urban": {
        "fill": (0.075, 0.082, 0.096), "soft": (0.220, 0.235, 0.265), "line": (0.780, 0.820, 0.880),
        "accent": (1.000, 0.680, 0.420), "trunk": (0.130, 0.140, 0.158), "canopy": (0.300, 0.320, 0.355),
    },
    "metropolis": {
        "fill": (0.078, 0.050, 0.135), "soft": (0.380, 0.240, 0.640), "line": (0.760, 0.530, 1.000),
        "accent": (1.000, 0.630, 0.940), "trunk": (0.350, 0.280, 0.410), "canopy": (0.440, 0.420, 0.710),
    },
}
LUSH_NATURE_KINDS = {"flat", "forest", "hills", "mushroom", "desert", "ice"}
DUSK_WARMTH_RGB = (0.130, 0.054, 0.028)
NEON_RACE_TRACK_LENGTH = 7200.0
NEON_RACE_GATE_SPACING = 88.0
NEON_RACE_LANES = (-8.0, -4.0, 0.0, 4.0, 8.0)
MAX_NEON_TRAFFIC = 6



@dataclass
class ObservatoryConfig:
    mouse_sensitivity: float = 0.11
    controller_look_sensitivity: float = 110.0
    walk_speed: float = 10.0
    sprint_speed: float = 16.0
    line_thickness: float = 2.4
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
    world_anchor_distance: float = 72.0
    world_hub_clear_radius: float = 46.0
    world_corridor_half_width: float = 7.5
    world_ground_match_radius: float = 24.0
    world_ground_match_blend: float = 18.0
    transition_duration: float = 4.6
    world_seed: int = 10457
    world_fill_mode: str = "transparent"
    world_fill_opacity: float = 0.16
    world_fill_stride: int = 2
    player_eye_height: float = 2.52
    master_volume: float = 0.82
    sfx_volume: float = 0.82
    music_volume: float = 0.42
    ambience_volume: float = 0.58


DEFAULT_CONFIG = ObservatoryConfig()


def ensure_dirs():
    for p in [ASSETS, TEXTURES_DIR, MODELS_DIR, CONFIG_DIR, WORLD_RUNTIME_STATE_DIR, LOG_DIR, PATCH_DIR]:
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
        - v1.11.58 Pass 50: Rebuilt the DESERT and ICE rings as broader biome systems instead of single hero structures.
        - v1.11.59 Pass 51: Reworked ICE from pile/cluster props into a terrain-first stepped cubic grid.
        - v1.11.60 Pass 52: Rebuilt the final METROPOLIS ring into an infinite streaming futuristic city.
        - v1.11.61 Pass 53: Polished METROPOLIS into a neater district-based skyline with more orderly city blocks and improved aerial motion.
        - v1.11.62 Pass 54: Rebuilt the skipped URBAN ring into a grey ruined war-zone biome with active combat silhouettes.
        - v1.11.63 Pass 55: Finished the URBAN battlefield pass with trench lines, smoke columns, stronger cratered relief, more robots/airstrikes, fixed Retired Ocean swim entry from the hub shell, and raised connected terrain relief across every non-flat biome.
        - v1.11.64 Pass 56: Rebuilt Retired Ocean as a local ocean/watercraft region: no terrain floor mesh in the water ring, hard blue fog occlusion while inside it, water-only chunk streaming, hidden region signs, and surface craft movement that recovers cleanly when leaving the ring.
        - v1.11.65 Pass 57: Added Tab travel-craft mode outside the hub, reusing the Retired Ocean craft visual for 10x walk-speed flight through every biome with instant hover/stop when input is released.
        - v1.11.66 Pass 58: Added a replaceable sky PNG feature. A placeholder moon-style image is generated in assets/textures and drawn as a distant always-visible sky card above the hub.
        - v1.11.67 Pass 59: Reduced line popping and metropolis overlap by giving city chunks a preload buffer, preventing generic biome terrain from streaming under METROPOLIS, and removing duplicate shared-edge city street/boundary lines.
        - v1.11.68 Pass 60: Fixed the overly dark day sky by removing the low sky-brightness cap, brightening biome daytime palettes, adding altitude-based stratosphere darkening with visible stars, lifting the craft ceiling far above the old sky barrier, and redesigning the craft silhouette so it is brighter and easier to see.
        - v1.11.69 Pass 61: Reworked biome ground fill coloring so terrain no longer blends into the sky in normal regions. Forest and grass bands now read clearly green, while desert, urban, metropolis, and other bands use distinct theme-appropriate ground tones. ICE remains the one allowed sky-adjacent exception.
        - v1.11.70 Pass 62: Added a surface-authority audit pass. Each streamed biome sector now owns one exact non-overlapping ground slice, water/metropolis continue to suppress redundant terrain fills, and the live audit reports which surface layer is actually authoritative before future color/material work.
        - v1.11.71 Pass 63: Converted the authoritative grid fills to opaque, untextured, single-layer chunk geometry with explicit biome colors: flat white, forest green, hills yellow, water no ground/colliders, desert amber, ice blue, urban grey, metropolis purple, and space black.
        - v1.11.72 Pass 64: Salvaged the useful artifact-world ideas as embedded oasis mini-biomes instead of separate broken destinations: IO-88 now appears in Flat, jungle/canopy pockets populate green hills/forest sectors, Venus furnace pockets populate desert sectors, Retired Ocean now has denser sea life plus airborne ocean creatures, and high-altitude craft flight enters an endless procedural space layer.
        - v1.11.83 Pass 83: Converted Retired Ocean to lite mode: no above-ground water volumes, no water fauna/flora/features/salvage population by default, thinner surface ribbons, lower wave/craft height, smaller water-only streaming radius, and explicit authoritative-file notes for cleanup.
        - v1.11.84 Pass 84: Removed all above-terrain Retired Ocean rendering. Water chunks no longer build surface ribbons/ripples, refresh now purges old surface nodes, and the water volume band is forced below the terrain line while craft traversal remains available.
        - v1.11.73 Pass 65: Added a capped salvage-population layer to streamed biome chunks. Each active sector can now contain small animated life/salvage silhouettes--grazers, crawlers, crystal walkers, ocean skimmers, and urban salvage bots--with explicit per-chunk counts and runtime caps so density improves without allowing runaway entities.
        - v1.13.01 Pass 282.21: Extended the existing dense verdant-canopy forest grammar across every streamed FORESTS sector with deterministic thickets, roots, ferns, deadfall, corridor/arrival clearances, and no change to region artifacts or Forest Growth state.
        - FORESTS now carry more tall trees, including a tower-canopy variant, while all non-flat terrain remains seam-connected through the same height envelope.
        - URBAN now reads as a devastated battlefield: broken grey structures, cratered lots, trenches, smoke, battling robot squads, colored laser fire, and overhead air-strike passes.
        - METROPOLIS remains the outer infinite city ring, while URBAN now fills the separate pre-metropolis warzone band.
        - Ice now draws many single terrain blocks at varied heights, with standalone sky cubes distributed over the biome instead of stacked piles.
        - Added sparse crystalline ice fauna silhouettes so the biome reads as terrain + life, not a single cube sculpture.
        """
    ).strip()
    LATEST_PATCH.write_text(note + "\n", encoding="utf-8")


def _safe_write_json(path: Path, payload: dict) -> bool:
    target = Path(path)
    tmp = target.with_name(target.name + ".tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
        return True
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        return False


def load_config() -> ObservatoryConfig:
    ensure_dirs()
    loaded = {}
    for source in (CONFIG_PATH, RUNTIME_CONFIG_PATH):
        try:
            if source.exists():
                data = json.loads(source.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    loaded.update(data)
        except Exception:
            pass
    try:
        merged = asdict(DEFAULT_CONFIG)
        merged.update({k: v for k, v in loaded.items() if k in merged})
        cfg = ObservatoryConfig(**merged)
    except Exception:
        cfg = DEFAULT_CONFIG
    try:
        cfg.terrain_render_radius = int(max(1, min(3, int(cfg.terrain_render_radius))))
        cfg.world_fill_stride = int(max(1, min(4, int(cfg.world_fill_stride))))
        cfg.line_thickness = float(max(2.4, min(5.0, float(cfg.line_thickness))))
    except Exception:
        cfg.terrain_render_radius = DEFAULT_CONFIG.terrain_render_radius
        cfg.world_fill_stride = DEFAULT_CONFIG.world_fill_stride
        cfg.line_thickness = DEFAULT_CONFIG.line_thickness
    save_config(cfg)
    return cfg


def save_config(cfg: ObservatoryConfig):
    ensure_dirs()
    try:
        cfg.terrain_render_radius = int(max(1, min(3, int(cfg.terrain_render_radius))))
    except Exception:
        cfg.terrain_render_radius = DEFAULT_CONFIG.terrain_render_radius
    try:
        cfg.world_fill_stride = int(max(1, min(4, int(cfg.world_fill_stride))))
    except Exception:
        cfg.world_fill_stride = DEFAULT_CONFIG.world_fill_stride
    try:
        cfg.line_thickness = float(max(2.4, min(5.0, float(cfg.line_thickness))))
    except Exception:
        cfg.line_thickness = DEFAULT_CONFIG.line_thickness
    _safe_write_json(RUNTIME_CONFIG_PATH, asdict(cfg))
    write_audio_bus(cfg)



def build_audio_bus_payload(cfg: ObservatoryConfig):
    return {
        "master_volume": round(max(0.0, min(1.0, cfg.master_volume)), 3),
        "sfx_volume": round(max(0.0, min(1.0, cfg.sfx_volume)), 3),
        "music_volume": round(max(0.0, min(1.0, cfg.music_volume)), 3),
        "ambience_volume": round(max(0.0, min(1.0, cfg.ambience_volume)), 3),
    }


def write_audio_bus(cfg: ObservatoryConfig) -> Path:
    ensure_dirs()
    path = RUNTIME_AUDIO_BUS_PATH
    _safe_write_json(path, build_audio_bus_payload(cfg))
    return path


def hsv_color(h: float, s: float, v: float, a: float = 1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return (r, g, b, a)




WORLD_SPECS = {
    0: {"name": "Observatory Hub", "kind": "hub", "profile": "hub_only", "bg": (0.010, 0.014, 0.024), "hub": (0.94, 0.96, 1.0)},
}

# Hub-only prune: no artifact worlds or simulator destinations are active.
ARTIFACT_WORLD_IDS = []


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
    source: str = ""


@dataclass
class InternalModeState:
    mode_key: str = ""
    fire_down: bool = False
    weapon_cooldown: float = 0.0
    player_health: float = 100.0
    ammo: float = 100.0
    score: int = 0
    objective: str = ""
    last_hit_flash: float = 0.0
    projectiles: list = field(default_factory=list)


@dataclass
class UserBuildState:
    key: tuple
    cell_x: float
    cell_y: float
    footprint: float
    height: float
    node: object = None

    def to_payload(self):
        return {
            "key": [int(self.key[0]), int(self.key[1])],
            "cell_x": round(float(self.cell_x), 4),
            "cell_y": round(float(self.cell_y), 4),
            "footprint": round(float(self.footprint), 4),
            "height": round(float(self.height), 4),
        }


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_rgb(a, b, t):
    return tuple(lerp(a[i], b[i], t) for i in range(3))


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def rgb_to_rgba(rgb, alpha=1.0, intensity=1.0):
    intensity = max(0.0, float(intensity))
    return (
        clamp(float(rgb[0]) * intensity, 0.0, 1.0),
        clamp(float(rgb[1]) * intensity, 0.0, 1.0),
        clamp(float(rgb[2]) * intensity, 0.0, 1.0),
        clamp(float(alpha), 0.0, 1.0),
    )


def smoothstep(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def vec_normalized(v):
    out = Vec3(v)
    if out.lengthSquared() > 1e-6:
        out.normalize()
    return out


def point_segment_distance(point: Vec3, seg_a: Vec3, seg_b: Vec3) -> float:
    seg = seg_b - seg_a
    seg_len_sq = seg.lengthSquared()
    if seg_len_sq <= 1e-8:
        return (point - seg_a).length()
    t = clamp((point - seg_a).dot(seg) / seg_len_sq, 0.0, 1.0)
    closest = seg_a + seg * t
    return (point - closest).length()


def focus_hpr(from_pos: Vec3, target_pos: Vec3):
    look = target_pos - from_pos
    flat = math.sqrt(look.x * look.x + look.y * look.y)
    yaw = math.degrees(math.atan2(look.y, look.x))
    pitch = math.degrees(math.atan2(look.z, max(0.001, flat)))
    return yaw, pitch


@dataclass
class WeaponShardProjectile:
    node: object
    wire: object
    velocity: Vec3
    spin: Vec3
    life: float
    gravity: float
    damage: float
    side: str


@dataclass
class NeonRaceState:
    ready: bool = False
    active: bool = False
    progress: float = 0.0
    lateral: float = 0.0
    target_lateral: float = 0.0
    lane_index: int = 2
    speed: float = 0.0
    boost_heat: float = 0.0
    race_time: float = 0.0
    best_distance: float = 0.0
    impact_flash: float = 0.0
    traffic: list = field(default_factory=list)



class CommandHubApp(ShowBase):
    def __init__(self):
        ensure_dirs()
        super().__init__()
        self.disableMouse()
        self.clock = ClockObject.getGlobalClock()
        self.clock.setMode(ClockObject.MNormal)
        self.cfg = load_config()
        self.elapsed = 0.0
        self.frame_fps = 0.0
        self.frame_ms_smoothed = 0.0
        self.menu_open = False
        self.hud_visible = self.cfg.hud_visible
        self.keys = {}
        self.gamepad = None
        self.player_pos = Vec3(0, -10, self.cfg.player_eye_height)
        self.player_yaw = 0.0
        self.player_pitch = -7.0
        self.move_velocity = Vec2(0, 0)
        self.player_velocity = Vec3(0, 0, 0)
        self.room_bounds = []
        self.hub_radius = 30.0
        self.artifact_radius = 22.8
        self.active_artifact = None
        self.active_artifact_id = None
        self.world_unlocked = False
        self.transition_progress = 0.0
        self.transition_target = 0.0
        self.terrain_chunks = {}
        self.terrain_chunk_pruned_count = 0
        self.active_biome_name = "HUB"
        self.last_biome_travel_key = None
        self.artifacts = []
        self.galaxy_nodes = []
        self.nearest_artifact = None
        self.nearest_artifact_dist = 999.0
        self.base_teleport = Vec3(0, -10, self.cfg.player_eye_height)
        self.world_actors = []
        self.world_actor_pruned_count = 0
        self.last_world_kind = "frontier"
        self.world_theme_blend = 0.0
        self.default_hub_rgb = (0.94, 0.96, 1.0)
        self.current_hub_rgb = self.default_hub_rgb
        self.current_bg_rgb = (self.cfg.background_value, self.cfg.background_value, self.cfg.background_value)
        self.current_sky_rgb = self.current_bg_rgb
        self.current_day_factor = 0.0  # compatibility: space sky has no day cycle
        self.current_dusk_factor = 0.0
        self.current_sky_biome = "HUB"
        self.sky_ring_nodes = []
        self.surface_audit_summary = {}
        self.legacy_sky_background_removed = True
        self.forest_tree_variants = tuple(FOREST_TREE_VARIANTS)
        self.celestial_nodes = {}
        self.sky_png_root = None
        self.sky_png_card = None
        self.sky_png_path = SPACE_SKY_TEXTURE_PATH
        self.core_console_open = False
        self.underwater_vehicle_root = None
        self.underwater_vehicle_color = (0.30, 0.96, 0.88, 0.96)
        self.flight_craft_active = False
        self.flight_craft_velocity = Vec3(0, 0, 0)
        self.flight_craft_last_hint_time = -999.0
        self.deep_water_creature_nodes = []
        self.deep_water_glow_nodes = []
        self.deep_water_feature_nodes = []
        self.deep_water_sky_creature_nodes = []
        self.deep_water_surface_refresh_time = -999.0
        self.current_water_depth = 0.0
        self.water_region_occlusion_active = False
        self.metropolis_chunks = {}
        self.metropolis_preload_radius = int(METROPOLIS_PRELOAD_RADIUS)
        self.metropolis_overlap_skip_count = 0
        self.metropolis_duplicate_edge_suppression_count = 0
        self.metropolis_hover_vehicle_nodes = []
        self.metropolis_robot_nodes = []
        self.urban_battle_nodes = []
        self.urban_mech_nodes = []
        self.urban_drone_nodes = []
        self.urban_skeleton_nodes = []
        self.urban_airstrike_nodes = []
        self.space_layer_root = None
        self.space_layer_star_root = None
        self.space_layer_asteroid_nodes = []
        self.space_layer_initialized = False
        self.space_layer_active = False
        self.salvage_population_nodes = []
        self.salvage_population_pruned_count = 0
        self.named_region_bot_nodes = []
        self.named_region_bot_specs = []
        self.named_region_bot_pruned_count = 0
        self.internal_mode = InternalModeState()
        self.neon_race = NeonRaceState()
        self.neon_race_root = None
        self.neon_vehicle_root = None
        self.neon_traffic_nodes = []
        self.user_buildings = {}
        self.selected_user_build_key = None
        self.build_mouse_held = False
        self.last_build_click_time = -999.0
        self.last_build_click_key = None
        self.last_delete_click_time = -999.0
        self.last_delete_click_key = None
        self.build_hint_override_until = 0.0
        self.debug_sky_cam_enabled = False
        self.debug_sky_cam_restore = None
        self.space_build_total_seconds = 0.0
        self.space_build_session_seconds = 0.0
        self.space_build_progress = 0.0
        self.space_build_last_save_elapsed = -999.0
        self.space_build_loaded = False
        self.space_build_first_started_utc = ""
        self.space_build_last_saved_utc = ""
        self.space_build_session_count = 0

        self.render.setAntialias(AntialiasAttrib.MAuto)
        self.render.setTransparency(TransparencyAttrib.MAlpha)
        self.setup_window()
        self.setup_scene()
        self.setup_ui()
        self.setup_weapon_system()
        self.setup_input()
        self.setup_gamepad()
        self.rebuild_station()
        self.activate_default_world_shell()
        self.load_user_buildings_from_disk()
        self.load_space_build_progress()
        self.refresh_ui()
        self.camera.setPos(self.player_pos)
        self.camera.setHpr(self.player_yaw, self.player_pitch, 0)
        self.accept("window-event", self.on_window_event)
        self.taskMgr.add(self.update_task, "update-task")
        if SELF_TEST:
            self.taskMgr.doMethodLater(0.8, self.self_test_setup, "self-test-setup")
            self.taskMgr.doMethodLater(5.2, self.self_test_exit, "self-test-exit")
        else:
            self.recenter_mouse(force=True)
            if AUTO_EXIT:
                self.taskMgr.doMethodLater(2.0, self.self_test_exit, "auto-exit")

    def setup_window(self):
        props = WindowProperties()
        props.setTitle(GAME_NAME)
        props.setSize(1920, 1080)
        props.setCursorHidden(not SELF_TEST)
        if self.win is not None and hasattr(self.win, "requestProperties"):
            self.win.requestProperties(props)
        self.setBackgroundColor(self.cfg.background_value, self.cfg.background_value, self.cfg.background_value)

    def setup_scene(self):
        self.root_3d = self.render.attachNewNode("root-3d")
        self.surface_root = self.root_3d.attachNewNode("surface-root")
        self.line_root = self.root_3d.attachNewNode("line-root")
        self.accent_root = self.root_3d.attachNewNode("accent-root")
        self.dome_root = self.root_3d.attachNewNode("dome-root")
        self.lens_root = self.root_3d.attachNewNode("lens-root")
        self.sky_root = self.root_3d.attachNewNode("sky-root")
        self.atmosphere_root = self.root_3d.attachNewNode("atmosphere-root")
        self.world_root = self.root_3d.attachNewNode("world-root")
        self.user_build_root = self.world_root.attachNewNode("user-build-root")
        self.galaxy_root = self.root_3d.attachNewNode("galaxy-root")
        self.world_root.setTransparency(TransparencyAttrib.MAlpha)
        self.user_build_root.setTransparency(TransparencyAttrib.MAlpha)
        self.galaxy_root.setTransparency(TransparencyAttrib.MAlpha)
        self.atmosphere_root.setTransparency(TransparencyAttrib.MAlpha)
        self.camLens.setNearFar(0.05, self.cfg.fog_distance)
        self.camLens.setFov(self.cfg.fov)

        self.fog = Fog("hub-fog")
        self.fog.setColor(self.cfg.background_value, self.cfg.background_value, self.cfg.background_value)
        self.fog.setLinearRange(self.cfg.fog_distance * 0.48, self.cfg.fog_distance)
        self.render.setFog(self.fog)

        ambient = AmbientLight("ambient")
        ambient.setColor((0.58, 0.62, 0.68, 1.0))
        self.render.setLight(self.render.attachNewNode(ambient))

        dlight = DirectionalLight("sun")
        dlight.setColor((0.34, 0.37, 0.42, 1.0))
        dnp = self.render.attachNewNode(dlight)
        dnp.setHpr(-20, -48, 0)
        self.render.setLight(dnp)
        self.setup_sky_png_card()
        self.setup_space_layer()


    def is_near_core(self):
        return math.sqrt(self.player_pos.x ** 2 + self.player_pos.y ** 2) < 6.8

    def open_core_console(self):
        self.core_console_open = True
        self.core_console_root.show()
        self.center_hint["text"] = "CORE // HUB ONLY"

    def close_core_console(self):
        self.core_console_open = False
        self.core_console_root.hide()

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
        self.refresh_ui()

    def setup_ui(self):
        self.menu_tab = "display"
        self.menu_actions = []
        self.hud_root = self.aspect2d.attachNewNode("hud-root")
        self.top_panel = DirectFrame(parent=self.hud_root, frameColor=(0.01, 0.01, 0.012, 0.72), frameSize=(-0.26, 0.20, -0.06, 0.06), pos=(-1.06, 0, 0.92))
        self.hud_label = DirectLabel(parent=self.top_panel, text="", text_align=TextNode.ALeft, text_scale=0.030, text_fg=(0.95, 0.97, 1.0, 1.0), frameColor=(0, 0, 0, 0), pos=(-0.23, 0, 0.0), textMayChange=True)
        self.center_hint = DirectLabel(parent=self.hud_root, text="", text_align=TextNode.ACenter, text_scale=0.043, text_fg=(0.96, 0.30, 0.34, 0.95), frameColor=(0, 0, 0, 0), pos=(0, 0, -0.80), textMayChange=True)
        self.coords_label = DirectLabel(parent=self.hud_root, text="", text_align=TextNode.ALeft, text_scale=0.028, text_fg=(1.0, 0.34, 0.38, 0.92), frameColor=(0, 0, 0, 0), pos=(-1.28, 0, -0.93), textMayChange=True)
        self.safety_exit_root = self.aspect2d.attachNewNode("safety-exit-root")
        self.safety_exit_panel = DirectFrame(parent=self.safety_exit_root, frameColor=(0.08, 0.01, 0.02, 0.70), frameSize=(-0.18, 0.18, -0.070, 0.070), pos=(1.46, 0, 0.82))
        self.safety_exit_button = DirectButton(parent=self.safety_exit_root, text="CLOSE APP", command=self.quit_holoverse_app, pos=(1.46, 0, 0.838), scale=0.039, frameSize=(-2.30, 2.30, -0.34, 0.40), text_scale=0.40, text_pos=(0, -0.08), relief=1, rolloverSound=None, clickSound=None)
        self.safety_exit_hint = DirectLabel(parent=self.safety_exit_root, text="(hold esc)", text_align=TextNode.ACenter, text_scale=0.0155, text_fg=(1.0, 0.76, 0.80, 0.94), frameColor=(0, 0, 0, 0), pos=(1.46, 0, 0.786), textMayChange=True)

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
        DirectFrame(parent=self.core_console_root, frameColor=(0.02, 0.02, 0.025, 0.88), frameSize=(-0.52, 0.52, -0.12, 0.12), pos=(0, 0, -0.56))
        DirectLabel(parent=self.core_console_root, text="CORE // HUB ONLY", text_scale=0.034, text_align=TextNode.ACenter, text_fg=(0.98, 0.92, 0.94, 1.0), frameColor=(0, 0, 0, 0), pos=(0, 0, -0.53), textMayChange=True)
        DirectLabel(parent=self.core_console_root, text="Esc close   T return", text_scale=0.024, text_align=TextNode.ACenter, text_fg=(0.78, 0.82, 0.90, 1.0), frameColor=(0, 0, 0, 0), pos=(0, 0, -0.60), textMayChange=True)

        self.menu_root = self.aspect2d.attachNewNode("menu-root")
        self.menu_root.hide()
        DirectFrame(parent=self.menu_root, frameColor=(0.008, 0.008, 0.010, 0.94), frameSize=(-0.72, 0.72, -0.44, 0.46))
        DirectFrame(parent=self.menu_root, frameColor=(0.12, 0.01, 0.02, 0.86), frameSize=(-0.72, 0.72, 0.32, 0.46))
        DirectLabel(parent=self.menu_root, text="OBSERVATORY", text_scale=0.044, text_fg=(1.0, 0.95, 0.96, 1.0), frameColor=(0, 0, 0, 0), pos=(0, 0, 0.405))
        self.menu_subtitle = DirectLabel(parent=self.menu_root, text="Hub clean-room", text_scale=0.022, text_fg=(0.96, 0.43, 0.47, 1.0), frameColor=(0, 0, 0, 0), pos=(0, 0, 0.345), textMayChange=True)

        tabs = [("VIEW", "display"), ("AUDIO", "audio"), ("SYSTEM", "system")]
        self.menu_tab_buttons = []
        start_x = -0.36
        tab_step = 0.36
        for i, (label, key) in enumerate(tabs):
            btn = DirectButton(parent=self.menu_root, text=label, command=self.set_menu_tab, extraArgs=[key], pos=(start_x + i * tab_step, 0, 0.265), scale=0.041, frameColor=(0.06, 0.01, 0.02, 1.0), text_fg=(1.0, 0.86, 0.88, 1.0), relief=1)
            self.menu_tab_buttons.append((key, btn))

        self.menu_left = DirectFrame(parent=self.menu_root, frameColor=(0.025, 0.026, 0.032, 0.86), frameSize=(-0.60, -0.06, -0.32, 0.18), pos=(0, 0, -0.02))
        self.menu_right = DirectFrame(parent=self.menu_root, frameColor=(0.025, 0.026, 0.032, 0.86), frameSize=(0.08, 0.60, -0.32, 0.18), pos=(0, 0, -0.02))
        self.menu_info = DirectLabel(parent=self.menu_left, text="", text_align=TextNode.ALeft, text_scale=0.033, text_fg=(0.96, 0.98, 1.0, 1.0), frameColor=(0, 0, 0, 0), pos=(-0.54, 0, 0.115), textMayChange=True)
        self.menu_section = DirectLabel(parent=self.menu_left, text="", text_align=TextNode.ALeft, text_scale=0.025, text_fg=(0.98, 0.36, 0.40, 1.0), frameColor=(0, 0, 0, 0), pos=(-0.54, 0, 0.035), textMayChange=True)
        self.menu_detail = DirectLabel(parent=self.menu_left, text="", text_align=TextNode.ALeft, text_scale=0.026, text_fg=(0.83, 0.86, 0.92, 1.0), frameColor=(0, 0, 0, 0), pos=(-0.54, 0, -0.070), textMayChange=True)
        self.menu_status = DirectLabel(parent=self.menu_root, text="", text_align=TextNode.ACenter, text_scale=0.022, text_fg=(1.0, 0.40, 0.44, 0.95), frameColor=(0, 0, 0, 0), pos=(0, 0, -0.395), textMayChange=True)
        self.menu_buttons = []
        for i in range(4):
            btn = DirectButton(parent=self.menu_right, text="", command=self.apply_menu_action, extraArgs=[i], pos=(0.34, 0, 0.105 - i * 0.125), scale=0.044, frameColor=(0.09, 0.01, 0.02, 1.0), text_fg=(1.0, 0.92, 0.94, 1.0), relief=1)
            self.menu_buttons.append(btn)
        self.refresh_menu_actions()

    def setup_input(self):
        for key in ["w", "a", "s", "d", "shift", "space", "control"]:
            self.accept(key, self.set_key, [key, True])
            self.accept(f"{key}-up", self.set_key, [key, False])
        self.accept("v", self.toggle_flight_craft)
        self.accept("h", self.toggle_hud)
        self.accept("escape", self.toggle_menu)
        self.accept("mouse1", self.on_mouse1_down)
        self.accept("mouse1-up", self.on_mouse1_up)
        self.accept("wheel_up", self.on_mouse_wheel, [1])
        self.accept("wheel_down", self.on_mouse_wheel, [-1])
        self.accept("mouse3", self.on_mouse3_down)
        self.accept("e", self.interact)
        self.accept("q", self.core_secondary_action)
        self.accept("t", self.teleport_to_hub)
        for biome_key in range(1, 9):
            self.accept(str(biome_key), self.fast_travel_to_biome, [biome_key])
        self.accept("f1", self.toggle_help_overlay)
        self.accept("f2", self.toggle_debug_sky_cam)

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

    def show_build_hint(self, text: str, duration: float = 1.2):
        if hasattr(self, "center_hint"):
            self.center_hint["text"] = text
        self.build_hint_override_until = self.elapsed + max(0.1, duration)

    def current_view_disc_point(self):
        return None

    def flatworld_build_cell_from_point(self, point):
        return None

    def flatworld_build_cell_bounds(self, key):
        return (Vec3(0, 0, 0), Vec3(0, 0, 0))

    def can_build_in_flatworld_cell(self, key):
        return False

    def build_cell_under_reticle(self):
        self.show_build_hint("HUB-ONLY // build domain removed", 1.2)
        return False

    def save_user_buildings_to_disk(self):
        return

    def load_user_buildings_from_disk(self):
        self.user_buildings = {}
        self.selected_user_build_key = None
        return

    def compute_space_build_progress(self, total_seconds=None):
        total = float(self.space_build_total_seconds if total_seconds is None else total_seconds)
        return clamp(float(SPACE_BUILD_PROGRESS_BASE) + total * float(SPACE_BUILD_PROGRESS_RATE), 0.0, 1.0)

    def parse_space_build_progress_text(self, raw: str):
        data = {}
        raw = str(raw or "").strip()
        if not raw:
            return data
        if raw.startswith("{"):
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
        return data

    def save_space_build_progress(self, force=False):
        ensure_dirs()
        if not force and (self.elapsed - float(getattr(self, "space_build_last_save_elapsed", -999.0))) < float(SPACE_BUILD_AUTOSAVE_INTERVAL):
            return False
        utc_now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        first_started = str(getattr(self, "space_build_first_started_utc", "") or utc_now)
        payload = {
            "game": GAME_NAME,
            "version": VERSION,
            "kind": "space_build_progress",
            "first_started_utc": first_started,
            "last_saved_utc": utc_now,
            "session_count": int(max(1, int(getattr(self, "space_build_session_count", 1) or 1))),
            "total_build_seconds": round(float(getattr(self, "space_build_total_seconds", 0.0)), 4),
            "session_build_seconds": round(float(getattr(self, "space_build_session_seconds", 0.0)), 4),
            "space_build_progress": round(float(getattr(self, "space_build_progress", self.compute_space_build_progress())), 6),
            "progress_rate_per_second": float(SPACE_BUILD_PROGRESS_RATE),
            "base_progress": float(SPACE_BUILD_PROGRESS_BASE),
            "reset_hint": "Delete this TXT file to reset the Dyson sphere build progress.",
        }
        lines = [
            "# HoloVerse Dyson sphere build progress",
            "# Delete this TXT file to reset the build state.",
        ]
        order = [
            "game", "version", "kind", "first_started_utc", "last_saved_utc", "session_count",
            "total_build_seconds", "session_build_seconds", "space_build_progress",
            "progress_rate_per_second", "base_progress", "reset_hint",
        ]
        for key in order:
            lines.append(f"{key}={payload.get(key, '')}")
        try:
            tmp = SPACE_BUILD_PROGRESS_PATH.with_name(SPACE_BUILD_PROGRESS_PATH.name + ".tmp")
            SPACE_BUILD_PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with tmp.open("w", encoding="utf-8", newline="") as fh:
                fh.write("\n".join(lines) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, SPACE_BUILD_PROGRESS_PATH)
            self.space_build_last_save_elapsed = float(self.elapsed)
            self.space_build_last_saved_utc = utc_now
            self.space_build_first_started_utc = first_started
            return True
        except Exception:
            return False

    def load_space_build_progress(self):
        ensure_dirs()
        loaded = {}
        if SPACE_BUILD_PROGRESS_PATH.exists():
            try:
                loaded = self.parse_space_build_progress_text(SPACE_BUILD_PROGRESS_PATH.read_text(encoding="utf-8"))
            except Exception:
                loaded = {}
        elif SPACE_BUILD_PROGRESS_LEGACY_JSON_PATH.exists():
            try:
                loaded = json.loads(SPACE_BUILD_PROGRESS_LEGACY_JSON_PATH.read_text(encoding="utf-8"))
            except Exception:
                loaded = {}
        try:
            self.space_build_total_seconds = float(loaded.get("total_build_seconds", 0.0) or 0.0)
        except Exception:
            self.space_build_total_seconds = 0.0
        self.space_build_session_seconds = 0.0
        self.space_build_progress = self.compute_space_build_progress(self.space_build_total_seconds)
        self.space_build_last_save_elapsed = float(self.elapsed)
        self.space_build_first_started_utc = str(loaded.get("first_started_utc", "") or "")
        self.space_build_last_saved_utc = str(loaded.get("last_saved_utc", "") or "")
        try:
            previous_sessions = int(float(loaded.get("session_count", 0) or 0))
        except Exception:
            previous_sessions = 0
        self.space_build_session_count = previous_sessions + 1
        if not self.space_build_first_started_utc:
            self.space_build_first_started_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self.space_build_loaded = True
        return loaded

    def ray_box_intersection(self, origin: Vec3, direction: Vec3, min_v: Vec3, max_v: Vec3):
        tmin = -1e30
        tmax = 1e30
        for axis in ("x", "y", "z"):
            o = getattr(origin, axis)
            d = getattr(direction, axis)
            mn = getattr(min_v, axis)
            mx = getattr(max_v, axis)
            if abs(d) < 1e-6:
                if o < mn or o > mx:
                    return None
                continue
            inv = 1.0 / d
            t1 = (mn - o) * inv
            t2 = (mx - o) * inv
            if t1 > t2:
                t1, t2 = t2, t1
            tmin = max(tmin, t1)
            tmax = min(tmax, t2)
            if tmax < tmin:
                return None
        if tmax < 0.0:
            return None
        return tmin if tmin >= 0.0 else tmax

    def looked_at_user_building(self):
        return None

    def resolve_user_building_collisions(self, candidate):
        return candidate

    def rebuild_user_building_visual(self, state):
        return

    def select_user_building(self, key):
        self.selected_user_build_key = None
        return

    def create_user_building_at_cell(self, key):
        self.show_build_hint("HUB-ONLY // building removed", 1.2)
        return None

    def delete_user_building(self, key):
        return False

    def adjust_selected_user_build_height(self, direction: int):
        return

    def self_test_demo_building_specs(self):
        return []

    def is_self_test_demo_building(self, key):
        return False

    def purge_self_test_demo_buildings(self):
        self.user_buildings = {}
        return

    def ensure_self_test_demo_buildings(self):
        return

    def on_mouse1_down(self):
        self.set_fire_down(True)
        return

    def on_mouse1_up(self):
        self.set_fire_down(False)
        self.build_mouse_held = False

    def on_mouse_wheel(self, direction):
        return

    def on_mouse3_down(self):
        self.show_build_hint("HUB-ONLY // delete/build removed", 1.0)
        return


    def create_unit_box_model(self):
        """Create an internal unit-cube template so object geometry no longer depends on models/box."""
        fmt = GeomVertexFormat.getV3()
        vdata = GeomVertexData("unit-colorless-box", fmt, Geom.UHStatic)
        vwriter = GeomVertexWriter(vdata, "vertex")
        verts = [
            (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
            (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5),
        ]
        for vx, vy, vz in verts:
            vwriter.addData3f(vx, vy, vz)
        tris = GeomTriangles(Geom.UHStatic)
        for a, b, c in (
            (0, 2, 1), (0, 3, 2),
            (4, 5, 6), (4, 6, 7),
            (0, 1, 5), (0, 5, 4),
            (1, 2, 6), (1, 6, 5),
            (2, 3, 7), (2, 7, 6),
            (3, 0, 4), (3, 4, 7),
        ):
            tris.addVertices(a, b, c)
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        geom_node = GeomNode("generated-unit-box")
        geom_node.addGeom(geom)
        model = NodePath(geom_node)
        model.setTextureOff(10)
        model.setLightOff(1)
        model.setTwoSided(False)
        return model

    def setup_weapon_system(self):
        self.box_model = self.create_unit_box_model()
        # Textureless object pass: color and wireframe carry the form.
        self.hybrid_floor_tex = None
        self.hybrid_wall_tex = None
        self.hybrid_shard_tex = None
        self.hybrid_accent_tex = None
        self.weapon_root = self.camera.attachNewNode("weapon-root")
        self.weapon_root.setPos(0.0, 0.0, 0.0)
        self.weapon_root.setHpr(0.0, 0.0, 0.0)
        self.weapon_root.setBin("fixed", 50)
        self.weapon_root.setDepthWrite(False)
        self.weapon_root.setDepthTest(False)
        self.weapon_root.setFogOff(1)
        self.weapon_wire_nodes = []
        self.weapon_energy_parts = []
        self.weapon_detachable_parts = []
        self.weapon_projectiles = []
        self.weapon_rng = random.Random(27017)
        self.weapon_recoil = 0.0
        self.shield_active = False
        self.shield_charges = 0
        self.shield_time = 0.0
        self.shield_max_time = 6.0
        self.shield_radius = 3.1
        self.left_weapon = self.build_weapon("left")
        self.right_weapon = self.build_weapon("right")
        self.setup_shield_visual()
        self.weapon_root.hide()

    def wire_flash_rgb(self, base_rgb: Vec3):
        pulse = 0.5 + 0.5 * math.sin(self.elapsed * 2.8)
        return (
            clamp(base_rgb.x * (0.88 + pulse * 0.34), 0.0, 1.65),
            clamp(base_rgb.y * (0.88 + pulse * 0.34), 0.0, 1.65),
            clamp(base_rgb.z * (0.88 + pulse * 0.40), 0.0, 1.85),
        )


    def add_box_model(self, parent, pos, hpr, scale, tex, tint, tex_scale=(8.0, 8.0), wire_rgb=None, emission_boost=0.0, alpha=1.0):
        if getattr(self, "box_model", None) is None:
            return None
        part = self.box_model.copyTo(parent)
        part.setPos(pos)
        part.setHpr(hpr)
        part.setScale(scale)
        part.setTextureOff(10)
        part.setLightOff(1)
        part.setColorScale(tint[0], tint[1], tint[2], alpha)
        part.setTransparency(TransparencyAttrib.MAlpha)
        part.setTwoSided(False)

        wire = self.box_model.copyTo(part)
        wire.setScale(1.025)
        wire.setRenderModeWireframe()
        wire.setLightOff(1)
        wire.setTextureOff(10)
        wire.setTransparency(TransparencyAttrib.MAlpha)
        rgb = wire_rgb or Vec3(0.28, 0.92, 1.18)
        wire.setColorScale(rgb.x, rgb.y, rgb.z, 0.42)
        self.weapon_wire_nodes.append((wire, rgb))
        return part

    def weapon_part_wire(self, node):
        if not node or node.isEmpty() or node.getNumChildren() <= 0:
            return None
        wire = node.getChild(0)
        return None if wire.isEmpty() else wire

    def register_detachable_weapon_part(self, parent, node, side, local_pos, local_hpr, local_scale, tex, tint, tex_scale, wire_rgb, emission_boost, phase):
        self.weapon_detachable_parts.append({
            "parent": parent,
            "node": node,
            "replacement_node": None,
            "projectile": None,
            "side": side,
            "local_pos": Vec3(local_pos),
            "local_hpr": Vec3(local_hpr),
            "local_scale": Vec3(local_scale),
            "tex": tex,
            "tint": Vec4(tint),
            "tex_scale": tex_scale,
            "wire_rgb": Vec3(wire_rgb),
            "emission_boost": emission_boost,
            "phase": phase,
            "state": "attached",
            "replacement_progress": 0.0,
            "replacement_start_pos": Vec3(0.0),
            "replacement_start_hpr": Vec3(0.0),
        })

    def spawn_replacement_weapon_part(self, slot):
        sign = -1.0 if slot["side"] == "left" else 1.0
        spawn_local = Vec3(slot["local_pos"].x + sign * 1.55, slot["local_pos"].y - 1.40, slot["local_pos"].z + 0.95)
        spawn_hpr = Vec3(slot["local_hpr"].x + 32.0, slot["local_hpr"].y + 24.0 * sign, slot["local_hpr"].z + 65.0 * sign)
        node = self.add_box_model(slot["parent"], spawn_local, spawn_hpr, slot["local_scale"] * 0.12, slot["tex"], slot["tint"], tex_scale=slot["tex_scale"], wire_rgb=slot["wire_rgb"], emission_boost=slot["emission_boost"])
        if node is None:
            return
        node.setAlphaScale(0.0)
        wire = self.weapon_part_wire(node)
        if wire is not None:
            wire.setAlphaScale(0.0)
        slot["replacement_node"] = node
        slot["replacement_progress"] = 0.0
        slot["replacement_start_pos"] = spawn_local
        slot["replacement_start_hpr"] = spawn_hpr
        slot["state"] = "replacing"

    def build_weapon(self, side: str):
        sign = -1.0 if side == "left" else 1.0
        base = self.weapon_root.attachNewNode(f"{side}_weapon")
        base.setPos(0.56 * sign, 1.48, -0.47)
        base.setHpr(7.0 * sign, -7.5, -2.0 * sign)
        base.setScale(0.34)
        base.setBin("fixed", 55)
        base.setDepthWrite(False)
        base.setDepthTest(False)
        base.setFogOff(1)
        accent_rgb = Vec4(0.26, 0.98, 1.0, 1.0) if side == "left" else Vec4(1.0, 0.28, 0.86, 1.0)
        accent_wire = Vec3(0.25, 1.0, 1.15) if side == "left" else Vec3(1.15, 0.26, 0.98)
        self.add_box_model(base, Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 0.0), Vec3(0.54, 1.04, 0.34), self.hybrid_wall_tex, Vec4(0.22, 0.22, 0.27, 1.0), tex_scale=(11.0, 11.0))
        self.add_box_model(base, Vec3(0.0, -0.02, 0.23), Vec3(0.0, 4.0, 0.0), Vec3(0.34, 0.64, 0.14), self.hybrid_floor_tex, Vec4(0.40, 0.40, 0.46, 1.0), tex_scale=(13.0, 13.0))
        self.add_box_model(base, Vec3(0.0, -0.08, -0.18), Vec3(0.0, -8.0, 0.0), Vec3(0.28, 0.54, 0.12), self.hybrid_floor_tex, Vec4(0.18, 0.18, 0.22, 1.0), tex_scale=(12.0, 12.0))
        self.add_box_model(base, Vec3(0.0, 0.86, 0.02), Vec3(0.0, 0.0, 0.0), Vec3(0.24, 0.62, 0.18), self.hybrid_wall_tex, Vec4(0.18, 0.18, 0.22, 1.0), tex_scale=(12.0, 16.0))
        self.add_box_model(base, Vec3(0.0, 1.26, 0.02), Vec3(0.0, 0.0, 0.0), Vec3(0.15, 0.26, 0.15), self.hybrid_accent_tex, accent_rgb, tex_scale=(7.0, 7.0), wire_rgb=accent_wire, emission_boost=0.20)
        self.add_box_model(base, Vec3(0.0, 1.48, 0.02), Vec3(0.0, 0.0, 0.0), Vec3(0.11, 0.14, 0.11), self.hybrid_shard_tex, accent_rgb, tex_scale=(8.0, 8.0), wire_rgb=accent_wire, emission_boost=0.34)
        for idx, rib_y in enumerate((-0.18, 0.18, 0.56)):
            pos_a = Vec3(0.30 * sign, rib_y, 0.06)
            hpr_a = Vec3(0.0, 0.0, 18.0 * sign)
            scale_a = Vec3(0.08, 0.34, 0.08)
            rib_a = self.add_box_model(base, pos_a, hpr_a, scale_a, self.hybrid_accent_tex, accent_rgb, tex_scale=(10.0, 6.0), wire_rgb=accent_wire, emission_boost=0.10)
            self.register_detachable_weapon_part(base, rib_a, side, pos_a, hpr_a, scale_a, self.hybrid_accent_tex, accent_rgb, (10.0, 6.0), accent_wire, 0.10, idx * 0.7 + (0.1 if side == "left" else 1.2))
            pos_b = Vec3(-0.30 * sign, rib_y, 0.06)
            hpr_b = Vec3(0.0, 0.0, -18.0 * sign)
            scale_b = Vec3(0.08, 0.34, 0.08)
            rib_b = self.add_box_model(base, pos_b, hpr_b, scale_b, self.hybrid_accent_tex, accent_rgb, tex_scale=(10.0, 6.0), wire_rgb=accent_wire, emission_boost=0.10)
            self.register_detachable_weapon_part(base, rib_b, side, pos_b, hpr_b, scale_b, self.hybrid_accent_tex, accent_rgb, (10.0, 6.0), accent_wire, 0.10, idx * 0.7 + 0.35 + (0.2 if side == "left" else 1.4))
        self.add_box_model(base, Vec3(0.0, -0.36, -0.56), Vec3(16.0, 0.0, 0.0), Vec3(0.18, 0.26, 0.44), self.hybrid_shard_tex, Vec4(0.12, 0.12, 0.15, 1.0), tex_scale=(12.0, 9.0))
        self.add_box_model(base, Vec3(0.0, -0.10, -0.36), Vec3(-6.0, 0.0, 0.0), Vec3(0.22, 0.34, 0.18), self.hybrid_floor_tex, Vec4(0.16, 0.16, 0.20, 1.0), tex_scale=(11.0, 11.0))
        crown_offsets = [Vec3(0.16 * sign, -0.26, 0.34), Vec3(-0.14 * sign, 0.04, 0.38), Vec3(0.08 * sign, 0.42, 0.28), Vec3(-0.10 * sign, 0.70, 0.24)]
        for idx, offset in enumerate(crown_offsets):
            tex = self.hybrid_floor_tex if idx % 2 == 0 else self.hybrid_wall_tex
            tint = Vec4(0.34, 0.34, 0.40, 1.0) if idx % 2 == 0 else Vec4(0.16, 0.16, 0.20, 1.0)
            hpr = Vec3(0.0, idx * 7.0, 0.0)
            scale = Vec3(0.12, 0.18, 0.10)
            crown = self.add_box_model(base, offset, hpr, scale, tex, tint, tex_scale=(14.0, 14.0))
            self.register_detachable_weapon_part(base, crown, side, offset, hpr, scale, tex, tint, (14.0, 14.0), Vec3(0.28, 0.92, 1.18), 0.0, idx * 0.82 + (0.5 if side == "left" else 1.8))
        left_rail = self.add_box_model(base, Vec3(0.14 * sign, 0.54, -0.03), Vec3(0.0, 0.0, 0.0), Vec3(0.05, 0.78, 0.05), self.hybrid_accent_tex, accent_rgb, tex_scale=(4.0, 16.0), wire_rgb=accent_wire, emission_boost=0.18)
        right_rail = self.add_box_model(base, Vec3(-0.14 * sign, 0.54, -0.03), Vec3(0.0, 0.0, 0.0), Vec3(0.05, 0.78, 0.05), self.hybrid_accent_tex, accent_rgb, tex_scale=(4.0, 16.0), wire_rgb=accent_wire, emission_boost=0.18)
        core = self.add_box_model(base, Vec3(0.0, 0.98, 0.02), Vec3(0.0, 0.0, 0.0), Vec3(0.14, 0.18, 0.14), self.hybrid_accent_tex, accent_rgb, tex_scale=(5.0, 5.0), wire_rgb=accent_wire, emission_boost=0.42)
        self.weapon_energy_parts.extend([
            {"node": left_rail, "base_scale": Vec3(0.05, 0.78, 0.05), "phase": 0.0 if side == "left" else 1.4, "accent": accent_rgb, "side": side},
            {"node": right_rail, "base_scale": Vec3(0.05, 0.78, 0.05), "phase": 0.7 if side == "left" else 2.1, "accent": accent_rgb, "side": side},
            {"node": core, "base_scale": Vec3(0.14, 0.18, 0.14), "phase": 1.0 if side == "left" else 2.8, "accent": accent_rgb, "side": side},
        ])
        return base

    def setup_shield_visual(self):
        self.shield_root = self.render.attachNewNode("shield-root")
        self.shield_root.setPos(0.0, 0.0, -0.08)
        self.shield_root.setTransparency(TransparencyAttrib.MAlpha)
        self.shield_root.setLightOff(1)
        self.shield_root.hide()
        self.shield_shells = []
        try:
            sphere_model = self.loader.loadModel("models/misc/sphere")
        except Exception:
            sphere_model = None
        if sphere_model is None:
            return
        shell_specs = [(3.05, Vec4(0.14, 0.92, 1.0, 0.14), 1.0, 2.4, 0.0), (2.72, Vec4(0.24, 0.98, 1.0, 0.11), 0.72, 3.2, 0.8), (2.38, Vec4(0.10, 0.72, 0.92, 0.08), 0.46, 4.2, 1.7)]
        for idx, (scale, color, alpha, scroll, phase) in enumerate(shell_specs):
            shell = sphere_model.copyTo(self.shield_root)
            shell.setScale(scale)
            shell.setTextureOff(1)
            shell.setColorScale(color)
            shell.setTransparency(TransparencyAttrib.MAlpha)
            shell.setTwoSided(True)
            shell.setLightOff(1)
            shell.setShaderOff(1)
            shell.setDepthWrite(False)
            shell.setDepthTest(False)
            self.shield_shells.append({"node": shell, "base_scale": scale, "base_color": color, "alpha": alpha, "scroll": scroll, "phase": phase})

    def activate_shield(self):
        if self.menu_open or not self.world_unlocked:
            return
        if self.shield_active:
            return
        self.shield_active = True
        self.shield_charges = 3
        self.shield_time = self.shield_max_time
        self.shield_root.show()
        self.shield_root.setScale(0.62)
        self.shield_root.setAlphaScale(0.0)


    def fire_random_weapon_part(self):
        eligible = [slot for slot in self.weapon_detachable_parts if slot["state"] == "attached" and slot["node"] is not None and not slot["node"].isEmpty()]
        if not eligible or self.box_model is None:
            return False
        slot = self.weapon_rng.choice(eligible)
        node = slot["node"]
        wire = self.weapon_part_wire(node)
        world_pos = node.getPos(self.render)
        world_hpr = node.getHpr(self.render)
        world_scale = node.getScale(self.render)
        node.wrtReparentTo(self.render)
        node.setPos(world_pos)
        node.setHpr(world_hpr)
        node.setScale(world_scale)
        aim_dir = self.camera.getQuat(self.render).getForward()
        aim_dir = vec_normalized(aim_dir)
        if aim_dir.lengthSquared() <= 1e-6:
            aim_dir = Vec3(0, 1, 0)
        velocity = aim_dir * 118.0
        projectile = WeaponShardProjectile(node=node, wire=wire, velocity=velocity, spin=Vec3(self.weapon_rng.uniform(-220.0, 220.0), self.weapon_rng.uniform(-220.0, 220.0), self.weapon_rng.uniform(-260.0, 260.0)), life=5.8, gravity=3.4, damage=18.0, side=slot["side"])
        self.weapon_projectiles.append({"slot": slot, "projectile": projectile})
        slot["projectile"] = projectile
        slot["node"] = None
        slot["state"] = "projectile"
        self.spawn_replacement_weapon_part(slot)
        self.prune_weapon_projectile_overflow()
        return True

    def prune_weapon_projectile_overflow(self):
        overflow = len(self.weapon_projectiles) - MAX_WEAPON_PROJECTILES
        if overflow <= 0:
            return
        for entry in list(self.weapon_projectiles)[:overflow]:
            slot = entry.get("slot") if isinstance(entry, dict) else None
            proj = entry.get("projectile") if isinstance(entry, dict) else None
            try:
                if proj is not None and proj.node is not None and not proj.node.isEmpty():
                    proj.node.removeNode()
            except Exception:
                pass
            if slot is not None:
                slot["projectile"] = None
                if slot.get("state") == "projectile":
                    slot["state"] = "replacing"
            try:
                self.weapon_projectiles.remove(entry)
            except ValueError:
                pass

    def trigger_weapon_recoil(self):
        self.weapon_recoil = clamp(self.weapon_recoil + 0.95, 0.0, 1.4)

    def update_weapon_slot_visuals(self, dt, clock):
        for slot in self.weapon_detachable_parts:
            phase = slot["phase"]
            side_sign = -1.0 if slot["side"] == "left" else 1.0
            breath = math.sin(clock * 0.82 + phase)
            disturbance = math.sin(clock * 0.48 + phase * 1.7)
            target_pos = slot["local_pos"] + Vec3(side_sign * disturbance * 0.010, breath * 0.040, abs(breath) * 0.020)
            target_hpr = slot["local_hpr"] + Vec3(breath * 3.2, disturbance * 3.8, breath * side_sign * 5.0)
            target_scale = slot["local_scale"] * (1.0 + abs(breath) * 0.035)
            node = slot.get("node")
            if node is not None and not node.isEmpty() and slot["state"] == "attached":
                node.setPos(target_pos)
                node.setHpr(target_hpr)
                node.setScale(target_scale)
                wire = self.weapon_part_wire(node)
                if wire is not None:
                    r, g, b = self.wire_flash_rgb(slot["wire_rgb"])
                    wire.setColorScale(r, g, b, 0.26 + abs(breath) * 0.16)
            if slot["state"] == "replacing":
                slot["replacement_progress"] = min(1.0, slot["replacement_progress"] + dt * 3.8)
                t = smoothstep(slot["replacement_progress"])
                replacement = slot.get("replacement_node")
                if replacement is not None and not replacement.isEmpty():
                    replacement.setPos(slot["replacement_start_pos"] * (1.0 - t) + target_pos * t)
                    replacement.setHpr(slot["replacement_start_hpr"] * (1.0 - t) + target_hpr * t)
                    replacement.setScale(slot["local_scale"] * (0.12 + 0.88 * t))
                    replacement.setAlphaScale(t)
                    wire = self.weapon_part_wire(replacement)
                    if wire is not None:
                        r, g, b = self.wire_flash_rgb(slot["wire_rgb"])
                        wire.setAlphaScale(t)
                        wire.setColorScale(r, g, b, 0.22 + t * 0.24)
                if slot["replacement_progress"] >= 1.0:
                    slot["node"] = replacement
                    slot["replacement_node"] = None
                    slot["projectile"] = None
                    slot["state"] = "attached"

    def find_world_actor_hit(self, start, end):
        return None

    def update_weapon_projectiles(self, dt):
        for entry in list(self.weapon_projectiles):
            slot = entry["slot"]
            proj = entry["projectile"]
            if proj.node is None or proj.node.isEmpty():
                self.weapon_projectiles.remove(entry)
                continue
            start_pos = proj.node.getPos(self.render)
            proj.life -= dt
            proj.velocity.z -= proj.gravity * dt
            end_pos = start_pos + proj.velocity * dt
            proj.node.setPos(end_pos)
            proj.node.setHpr(proj.node.getH() + proj.spin.x * dt, proj.node.getP() + proj.spin.y * dt, proj.node.getR() + proj.spin.z * dt)
            if proj.wire is not None and not proj.wire.isEmpty():
                r, g, b = self.wire_flash_rgb(Vec3(0.32, 0.96, 1.18) if proj.side == "left" else Vec3(1.12, 0.28, 0.98))
                proj.wire.setColorScale(r, g, b, 1.0)
            hit = self.find_world_actor_hit(start_pos, end_pos)
            expired = proj.life <= 0.0 or end_pos.z < -32.0 or (end_pos - self.player_pos).length() > 420.0
            if hit is not None:
                actor, piece = hit
                self.internal_mode.last_hit_flash = 0.22
                actor.health -= proj.damage
                if actor.health <= 0.0:
                    try:
                        actor.root.removeNode()
                    except Exception:
                        pass
                    self.internal_mode.score += 25
                proj.node.removeNode()
                slot["projectile"] = None
                if slot["state"] == "projectile":
                    slot["state"] = "replacing"
                self.weapon_projectiles.remove(entry)
                continue
            if expired:
                proj.node.removeNode()
                slot["projectile"] = None
                if slot["state"] == "projectile":
                    slot["state"] = "replacing"
                self.weapon_projectiles.remove(entry)

    def update_weapon_viewmodels(self, dt, clock):
        weapon_active = self.world_unlocked and self.transition_progress > 0.05 and not self.menu_open and self.left_weapon is not None and self.right_weapon is not None
        if not weapon_active:
            self.weapon_root.hide()
            return
        self.weapon_root.show()
        self.weapon_recoil = max(0.0, self.weapon_recoil - dt * 4.6)
        move_factor = min(1.0, self.move_velocity.length())
        bob_x = math.sin(self.elapsed * 7.0) * 0.012 * (0.25 + move_factor)
        bob_z = abs(math.sin(self.elapsed * 14.0)) * 0.020 * (0.20 + move_factor)
        idle_x = math.sin(clock * 1.7) * 0.006
        idle_z = math.cos(clock * 1.3) * 0.004
        breath = math.sin(clock * 0.82)
        disturbance = math.sin(clock * 0.48 + 1.3)
        recoil_push = self.weapon_recoil * 0.12
        recoil_pitch = self.weapon_recoil * 10.0
        recoil_roll = self.weapon_recoil * 4.5
        magnet_push = breath * 0.022 + disturbance * 0.008
        magnet_roll = breath * 1.8 + disturbance * 1.2
        magnet_yaw = math.sin(clock * 0.39) * 0.75
        self.weapon_root.setPos(idle_x + bob_x, recoil_push + magnet_push, idle_z - bob_z + abs(breath) * 0.010)
        self.weapon_root.setHpr(magnet_yaw, recoil_pitch + breath * 1.2, -math.sin(clock * 1.1) * 0.8 + magnet_roll * 0.45)
        self.left_weapon.setPos(-0.56 + bob_x * 0.8 - self.weapon_recoil * 0.018 - disturbance * 0.014, 1.48 - recoil_push * 0.6 + breath * 0.030, -0.47 - bob_z * 0.6 + abs(breath) * 0.020)
        self.right_weapon.setPos(0.56 + bob_x * 0.8 + self.weapon_recoil * 0.018 + disturbance * 0.014, 1.48 - recoil_push * 0.6 + breath * 0.030, -0.47 - bob_z * 0.6 + abs(breath) * 0.020)
        self.left_weapon.setHpr(-7.0 + recoil_roll + magnet_roll, -7.5 - recoil_pitch * 0.7 + breath * 2.2, 2.0 + recoil_roll * 0.5 + magnet_roll * 0.45)
        self.right_weapon.setHpr(7.0 - recoil_roll - magnet_roll, -7.5 - recoil_pitch * 0.7 + breath * 2.2, -2.0 - recoil_roll * 0.5 - magnet_roll * 0.45)
        for wire, rgb in list(self.weapon_wire_nodes):
            if wire is None or wire.isEmpty():
                continue
            r, g, b = self.wire_flash_rgb(rgb)
            alpha = clamp(0.24 + abs(breath) * 0.10, 0.12, 0.72)
            wire.setColorScale(r, g, b, alpha)
        for part in self.weapon_energy_parts:
            node = part.get("node")
            if node is None or node.isEmpty():
                continue
            pulse = 0.5 + 0.5 * math.sin(clock * 5.2 + part["phase"])
            scale = part["base_scale"]
            boost = 1.0 + pulse * 0.08 + abs(breath) * 0.06
            node.setScale(scale.x * (1.0 + pulse * 0.05), scale.y * boost, scale.z * (1.0 + pulse * 0.05))
            accent = part["accent"]
            node.setColorScale(clamp(accent[0] * (0.78 + pulse * 0.40), 0.0, 1.6), clamp(accent[1] * (0.78 + pulse * 0.40), 0.0, 1.6), clamp(accent[2] * (0.78 + pulse * 0.48), 0.0, 1.8), 1.0)
        self.update_weapon_slot_visuals(dt, clock)
        self.update_weapon_projectiles(dt)
        if self.internal_mode.fire_down and not self.menu_open:
            if self.internal_mode.weapon_cooldown <= 0.0 and self.fire_random_weapon_part():
                self.trigger_weapon_recoil()
                self.internal_mode.weapon_cooldown = 0.12
        if self.internal_mode.weapon_cooldown > 0.0:
            self.internal_mode.weapon_cooldown = max(0.0, self.internal_mode.weapon_cooldown - dt)

    def update_shield(self, dt: float, clock: float):
        if self.shield_active:
            self.shield_time = max(0.0, self.shield_time - dt)
            if self.shield_time <= 0.0 or self.shield_charges <= 0:
                self.shield_active = False
        self.shield_root.setPos(self.player_pos)
        if not self.shield_active:
            self.shield_root.setScale(max(0.62, self.shield_root.getScale().x * max(0.0, 1.0 - dt * 5.5)))
            self.shield_root.setAlphaScale(max(0.0, self.shield_root.getSa() - dt * 3.0))
            if self.shield_root.getSa() <= 0.01:
                self.shield_root.hide()
            return
        self.shield_root.show()
        pulse = 0.5 + 0.5 * math.sin(clock * 2.8)
        grow = 1.0 + pulse * 0.035
        self.shield_root.setScale(grow)
        self.shield_root.setAlphaScale(0.60 + pulse * 0.10)
        self.shield_root.setHpr(0.0, 0.0, 0.0)
        charge_boost = 0.90 + 0.08 * self.shield_charges
        for shell in self.shield_shells:
            node = shell["node"]
            if node.isEmpty():
                continue
            p = 0.5 + 0.5 * math.sin(clock * shell["scroll"] + shell["phase"])
            node.setScale(shell["base_scale"] * (1.0 + p * 0.08))
            base_color = shell["base_color"]
            node.setColorScale(clamp(base_color[0] * (0.88 + p * 0.22) * charge_boost, 0.0, 1.5), clamp(base_color[1] * (0.88 + p * 0.22) * charge_boost, 0.0, 1.5), clamp(base_color[2] * (0.88 + p * 0.28) * charge_boost, 0.0, 1.7), shell["alpha"] * (0.78 + p * 0.22))

    def fracture_profile_settings(self, profile: str):
        return {"height": 0.0, "radius": 0.0, "count": 0}

    def add_fracture_piece(self, *args, **kwargs):
        return None

    def fracture_lines_for_chunk(self, *args, **kwargs):
        return []

    def build_hybrid_fracture_chunk(self, *args, **kwargs):
        return None

    def station_line_color(self, alpha=1.0):
        return hsv_color(self.cfg.line_hue, self.cfg.line_saturation, self.cfg.line_value, alpha)

    def station_glow_color(self, alpha=1.0):
        return hsv_color((self.cfg.line_hue + 0.06) % 1.0, min(1.0, self.cfg.line_saturation * 0.76), min(1.0, self.cfg.line_value), alpha)

    def artifact_color(self, idx: int, alpha=1.0):
        return hsv_color((self.cfg.line_hue + 0.08) % 1.0, 0.78, 1.0, alpha)

    def lens_color(self, alpha=1.0):
        return hsv_color((self.cfg.line_hue + 0.48) % 1.0, 0.46, 1.0, alpha)

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
    def add_line_segments(self, parent, segments, color, thickness=None, name="line-batch"):
        if not segments:
            return None
        segs = LineSegs(name)
        segs.setThickness(thickness or self.cfg.line_thickness)
        segs.setColor(*color)
        for a, b in segments:
            segs.moveTo(a)
            segs.drawTo(b)
        np = parent.attachNewNode(segs.create())
        np.setAntialias(AntialiasAttrib.MLine)
        np.setTransparency(TransparencyAttrib.MAlpha)
        return np

    def add_polyline_batch(self, parent, polylines, color, thickness=None, closed=False, name="poly-batch"):
        polylines = [pts for pts in polylines if pts and len(pts) >= 2]
        if not polylines:
            return None
        segs = LineSegs(name)
        segs.setThickness(thickness or self.cfg.line_thickness)
        segs.setColor(*color)
        for points in polylines:
            segs.moveTo(points[0])
            for p in points[1:]:
                segs.drawTo(p)
            if closed:
                segs.drawTo(points[0])
        np = parent.attachNewNode(segs.create())
        np.setAntialias(AntialiasAttrib.MLine)
        np.setTransparency(TransparencyAttrib.MAlpha)
        return np

    def effective_terrain_render_radius(self):
        return 0
    def sanitize_runtime_config(self):
        self.cfg.terrain_render_radius = self.effective_terrain_render_radius()
        try:
            self.cfg.world_fill_stride = int(max(1, min(4, int(self.cfg.world_fill_stride))))
        except Exception:
            self.cfg.world_fill_stride = DEFAULT_CONFIG.world_fill_stride
        try:
            self.cfg.world_fill_opacity = float(max(0.0, min(1.0, float(self.cfg.world_fill_opacity))))
        except Exception:
            self.cfg.world_fill_opacity = DEFAULT_CONFIG.world_fill_opacity

    def normalized_world_fill_mode(self):
        return "hub-only"

    def world_fill_base_color(self, spec, alpha):
        return (0.0, 0.0, 0.0, 0.0)

    def flatworld_surface_color_at(self, x, y, alpha=1.0):
        return (0.0, 0.0, 0.0, 0.0)

    def build_world_fill_mesh(self, parent, grid_points, spec):
        return None

    def polygon_points(self, radius, z, count=8, offset_deg=22.5):
        pts = []
        for i in range(count):
            a = math.radians(offset_deg) + math.tau * i / count
            pts.append(Vec3(math.cos(a) * radius, math.sin(a) * radius, z))
        return pts

    def ellipse_points(self, radius_x, radius_y=None, count=64, phase_deg=0.0, plane="xy", center=None):
        radius_x = max(0.001, float(radius_x))
        radius_y = radius_x if radius_y is None else max(0.001, float(radius_y))
        count = max(8, int(count))
        plane = str(plane or "xy").lower()
        phase = math.radians(float(phase_deg))
        c = Vec3(center) if center is not None else Vec3(0.0, 0.0, 0.0)
        pts = []
        for i in range(count):
            a = phase + math.tau * i / count
            ca = math.cos(a)
            sa = math.sin(a)
            if plane == "xz":
                pts.append(Vec3(c.x + ca * radius_x, c.y, c.z + sa * radius_y))
            elif plane == "yz":
                pts.append(Vec3(c.x, c.y + ca * radius_x, c.z + sa * radius_y))
            else:
                pts.append(Vec3(c.x + ca * radius_x, c.y + sa * radius_y, c.z))
        return pts

    def try_load_space_landmark_mesh(self, parent, basenames=None, desired_radius=None, node_name="space-landmark-mesh"):
        basenames = tuple(basenames or SPACE_DYSON_MESH_BASENAMES)
        desired_radius = max(8.0, float(desired_radius or SPACE_DYSON_RADIUS))
        candidates = []
        for stem in basenames:
            for ext in ("bam", "glb", "gltf", "egg", "obj"):
                p = MODELS_DIR / f"{stem}.{ext}"
                if p.exists():
                    candidates.append(p)
        for path in candidates:
            try:
                model = self.loader.loadModel(Filename.fromOsSpecific(str(path)))
            except Exception:
                continue
            if model is None or model.isEmpty():
                continue
            model.reparentTo(parent)
            model.setName(node_name)
            model.setTransparency(TransparencyAttrib.MAlpha)
            model.setLightOff(1)
            model.setFogOff(1)
            model.setTwoSided(True)
            model.clearModelNodes()
            try:
                bounds = model.getTightBounds()
                if bounds and bounds[0] is not None and bounds[1] is not None:
                    mins, maxs = bounds
                    ext = max(0.001, (maxs - mins).length() * 0.5)
                    scale = desired_radius / ext
                    model.setScale(scale)
            except Exception:
                model.setScale(desired_radius / 10.0)
            model.setColorScale(0.05, 0.06, 0.09, 0.94)
            model.setPythonTag("replacement_mesh_source", str(path))
            return model
        return None

    def build_space_inspector_drone(self, parent, idx, orbit_radius, orbit_height, color=(0.45, 0.85, 1.0), accent=(1.0, 0.82, 0.28)):
        drone = parent.attachNewNode(f"space-inspector-drone-{idx:02d}")
        drone.setTransparency(TransparencyAttrib.MAlpha)
        drone.setLightOff(1)
        drone.setFogOff(1)
        drone.setTwoSided(True)
        drone.setPythonTag("orbit_radius", float(orbit_radius))
        drone.setPythonTag("orbit_height", float(orbit_height))
        drone.setPythonTag("orbit_speed", 0.050 + idx * 0.011)
        drone.setPythonTag("orbit_phase", idx * (math.tau / max(1, int(SPACE_DYSON_INSPECTOR_COUNT))))
        body = (clamp(color[0] * 0.58 + 0.08, 0.0, 1.0), clamp(color[1] * 0.58 + 0.08, 0.0, 1.0), clamp(color[2] * 0.58 + 0.08, 0.0, 1.0), 0.90)
        dark = (clamp(color[0] * 0.20 + 0.02, 0.0, 1.0), clamp(color[1] * 0.20 + 0.02, 0.0, 1.0), clamp(color[2] * 0.20 + 0.02, 0.0, 1.0), 0.96)
        accent_rgba = (clamp(accent[0], 0.0, 1.0), clamp(accent[1], 0.0, 1.0), clamp(accent[2], 0.0, 1.0), 0.96)
        wire = Vec3(min(1.25, accent_rgba[0] * 1.08), min(1.25, accent_rgba[1] * 1.08), min(1.25, accent_rgba[2] * 1.08))
        self.add_box_model(drone, Vec3(0.0, 0.0, 0.00), Vec3(0.0, 0.0, 0.0), Vec3(5.4, 3.2, 2.2), None, dark, wire_rgb=wire, alpha=0.94)
        self.add_box_model(drone, Vec3(0.0, 1.8, 0.15), Vec3(0.0, -6.0, 0.0), Vec3(2.4, 1.0, 0.8), None, accent_rgba, wire_rgb=wire, alpha=0.96)
        self.add_box_model(drone, Vec3(-3.1, 0.0, -0.08), Vec3(0.0, 0.0, -10.0), Vec3(1.8, 2.2, 0.7), None, body, wire_rgb=wire, alpha=0.90)
        self.add_box_model(drone, Vec3(3.1, 0.0, -0.08), Vec3(0.0, 0.0, 10.0), Vec3(1.8, 2.2, 0.7), None, body, wire_rgb=wire, alpha=0.90)
        self.add_line_segments(drone, [
            (Vec3(-2.2, 0.0, 0.8), Vec3(-6.0, 1.2, 1.6)),
            (Vec3(2.2, 0.0, 0.8), Vec3(6.0, 1.2, 1.6)),
            (Vec3(0.0, -1.4, 0.0), Vec3(0.0, -5.0, -1.6)),
            (Vec3(0.0, 0.0, 0.6), Vec3(0.0, 0.0, 5.0)),
        ], accent_rgba, self.cfg.line_thickness * 0.26, f"space-inspector-trim-{idx:02d}")
        scan = self.add_polyline(drone, self.ellipse_points(2.0, 0.8, 24, idx * 18.0, "xy", Vec3(0.0, 3.9, 0.0)), (0.45, 1.0, 1.0, 0.34), self.cfg.line_thickness * 0.18, True, f"space-inspector-scan-{idx:02d}")
        if scan is not None:
            scan.setPythonTag("scan_ring", True)
        return drone

    def dyson_focus_world_pos(self):
        return Vec3(SPACE_DYSON_FOCUS_POS)

    def constrain_dyson_player_position(self, candidate: Vec3):
        center = self.dyson_focus_world_pos()
        delta = Vec3(candidate - center)
        safe_radius = float(SPACE_DYSON_OUTER_RADIUS) + float(SPACE_DYSON_PLAYER_COLLISION_PADDING)
        dist = delta.length()
        if dist >= safe_radius:
            return candidate, False
        if dist <= 1e-4:
            delta = Vec3(0.0, 1.0, 0.0)
            dist = 1.0
        else:
            delta /= dist
        corrected = Vec3(center + delta * safe_radius)
        return corrected, True

    def build_dyson_shell_segments(self, parent, radius: float):
        slot_count = max(4, int(SPACE_DYSON_BUILD_SLOT_COUNT))
        band_count = max(5, int(SPACE_DYSON_BUILD_BAND_COUNT))
        shell_root = parent.attachNewNode("dyson-shell-octaforge-root")
        shell_root.setTransparency(TransparencyAttrib.MAlpha)
        shell_root.setLightOff(1)
        shell_root.setFogOff(1)
        shell_root.setTwoSided(True)
        slot_buckets = [[] for _ in range(slot_count)]
        band_points = []
        band_ts = [(-0.92 + (1.84 * i / max(1, band_count - 1))) for i in range(band_count)]
        for band_idx, t in enumerate(band_ts):
            z = radius * t
            local_radius = max(radius * 0.16, math.sqrt(max(0.0, radius * radius - z * z)))
            pts = self.polygon_points(local_radius, z, slot_count, 22.5)
            band_points.append(pts)
            alpha = 0.24 + 0.20 * (1.0 - abs(t))
            for edge_idx in range(slot_count):
                a = pts[edge_idx]
                b = pts[(edge_idx + 1) % slot_count]
                color = (1.00, 0.18 + 0.03 * (band_idx % 4), 0.12 + 0.03 * (edge_idx % 3), alpha)
                node = self.add_polyline(shell_root, [a, b], color, self.cfg.line_thickness * (0.38 + 0.10 * (1.0 - abs(t))), False, f"dyson-band-edge-{band_idx:02d}-{edge_idx:02d}")
                if node is not None:
                    node.setPythonTag("base_alpha", float(color[3]))
                    node.setPythonTag("construction_anchor", Vec3((a.x + b.x) * 0.5, (a.y + b.y) * 0.5, (a.z + b.z) * 0.5))
                    node.setPythonTag("base_scale", 1.0)
                    slot_buckets[edge_idx % slot_count].append(node)
        for band_idx in range(len(band_points) - 1):
            low = band_points[band_idx]
            high = band_points[band_idx + 1]
            for slot in range(slot_count):
                a = low[slot]
                b = high[slot]
                color = (0.96, 0.26 + 0.03 * (band_idx % 4), 0.16, 0.22 + 0.04 * ((slot + band_idx) % 3))
                node = self.add_polyline(shell_root, [a, b], color, self.cfg.line_thickness * 0.34, False, f"dyson-vertical-strut-{band_idx:02d}-{slot:02d}")
                if node is not None:
                    node.setPythonTag("base_alpha", float(color[3]))
                    node.setPythonTag("construction_anchor", Vec3((a.x + b.x) * 0.5, (a.y + b.y) * 0.5, (a.z + b.z) * 0.5))
                    node.setPythonTag("base_scale", 1.0)
                    slot_buckets[(slot + band_idx) % slot_count].append(node)

        ordered = []
        max_bucket = max((len(bucket) for bucket in slot_buckets), default=0)
        for row in range(max_bucket):
            for slot in range(slot_count):
                if row < len(slot_buckets[slot]):
                    ordered.append(slot_buckets[slot][row])
        total = max(1, len(ordered))
        self.space_layer_build_nodes = []
        for idx, node in enumerate(ordered):
            node.setPythonTag("construction_index", int(idx))
            node.setPythonTag("construction_total", int(total))
            self.space_layer_build_nodes.append(node)
        self.dyson_shell_root = shell_root
        self.dyson_shell_total_segments = total
        return shell_root

    def add_prism(self, parent, radius, height, color, count=8, offset_deg=22.5, thickness_scale=1.0):
        bottom = self.polygon_points(radius, 0, count, offset_deg)
        top = self.polygon_points(radius, height, count, offset_deg)
        segs = LineSegs("prism-wire-batched")
        segs.setThickness(self.cfg.line_thickness * thickness_scale)
        segs.setColor(*color)
        rings = [bottom, top]
        for ring in rings:
            if ring:
                segs.moveTo(ring[0])
                for p in ring[1:]:
                    segs.drawTo(p)
                segs.drawTo(ring[0])
        for a, b in zip(bottom, top):
            segs.moveTo(a)
            segs.drawTo(b)
        np = parent.attachNewNode(segs.create())
        np.setAntialias(AntialiasAttrib.MLine)
        np.setTransparency(TransparencyAttrib.MAlpha)
        return np

    def add_box(self, parent, center, size, color, thickness_scale=1.0):
        hx, hy, hz = size.x * 0.5, size.y * 0.5, size.z * 0.5
        corners = [
            Vec3(center.x - hx, center.y - hy, center.z - hz), Vec3(center.x + hx, center.y - hy, center.z - hz),
            Vec3(center.x + hx, center.y + hy, center.z - hz), Vec3(center.x - hx, center.y + hy, center.z - hz),
            Vec3(center.x - hx, center.y - hy, center.z + hz), Vec3(center.x + hx, center.y - hy, center.z + hz),
            Vec3(center.x + hx, center.y + hy, center.z + hz), Vec3(center.x - hx, center.y + hy, center.z + hz),
        ]
        edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
        segs = LineSegs("box-wire-batched")
        segs.setThickness(self.cfg.line_thickness * thickness_scale)
        segs.setColor(*color)
        for a, b in edges:
            segs.moveTo(corners[a])
            segs.drawTo(corners[b])
        np = parent.attachNewNode(segs.create())
        np.setAntialias(AntialiasAttrib.MLine)
        np.setTransparency(TransparencyAttrib.MAlpha)
        return np

    def add_solid_box(self, parent, center, size, color, alpha=None, name="solid-box-infill", hpr=None):
        """Cheap solid box fill behind vector wireframes.

        This reuses the generated unit cube, so it avoids model/texture asset
        dependency while giving large structures readable infill faces.
        """
        if getattr(self, "box_model", None) is None:
            return None
        try:
            rgba = tuple(float(v) for v in color)
            if len(rgba) < 4:
                rgba = (rgba[0], rgba[1], rgba[2], 1.0)
        except Exception:
            rgba = (0.18, 0.10, 0.28, 1.0)
        a = float(rgba[3] if alpha is None else alpha)
        node = self.box_model.copyTo(parent)
        node.setName(str(name))
        node.setTextureOff(10)
        node.setLightOff(1)
        node.setPos(center)
        if hpr is not None:
            try:
                node.setHpr(hpr)
            except Exception:
                pass
        node.setScale(size)
        node.setColorScale(rgba[0], rgba[1], rgba[2], clamp(a, 0.0, 1.0))
        if a < 0.999:
            node.setTransparency(TransparencyAttrib.MAlpha)
        else:
            node.setTransparency(TransparencyAttrib.MNone)
            node.setDepthWrite(True)
            node.setDepthTest(True)
        node.setTwoSided(False)
        return node

    def add_rect_terrain_surface(self, parent, x0, y0, size, color, name="rect-terrain-infill", grid_steps=6, z_bias=-0.050):
        """Opaque/solid terrain-following rectangle for chunk-level ground infill."""
        steps = max(1, int(grid_steps))
        size = float(size)
        vdata = GeomVertexData(str(name), GeomVertexFormat.getV3(), Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        for iy in range(steps + 1):
            y = float(y0) + size * (iy / float(steps))
            for ix in range(steps + 1):
                x = float(x0) + size * (ix / float(steps))
                z = self.world_height_at(x, y) + float(z_bias)
                vertex.addData3(x, y, z)
        tris = GeomTriangles(Geom.UHStatic)
        row = steps + 1
        for iy in range(steps):
            for ix in range(steps):
                i0 = iy * row + ix
                i1 = i0 + 1
                i2 = (iy + 1) * row + ix
                i3 = i2 + 1
                tris.addVertices(i0, i2, i1); tris.closePrimitive()
                tris.addVertices(i1, i2, i3); tris.closePrimitive()
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gnode = GeomNode(str(name))
        gnode.addGeom(geom)
        np = parent.attachNewNode(gnode)
        try:
            rgba = tuple(float(v) for v in color)
            if len(rgba) < 4:
                rgba = (rgba[0], rgba[1], rgba[2], 1.0)
        except Exception:
            rgba = (0.18, 0.08, 0.30, 1.0)
        np.setColor(*rgba)
        if rgba[3] < 0.999:
            np.setTransparency(TransparencyAttrib.MAlpha)
        else:
            np.setTransparency(TransparencyAttrib.MNone)
            np.setDepthWrite(True)
            np.setDepthTest(True)
        np.setTwoSided(True)
        return np

    def build_octagonal_floor_grid(self, parent, inner_r, outer_r, z, color):
        for r in [inner_r + i * 2.2 for i in range(int((outer_r - inner_r) / 2.2) + 1)]:
            self.add_polyline(parent, self.polygon_points(r, z, 8, 22.5), color, self.cfg.line_thickness * 0.76, True, "oct-ring")
        for i in range(8):
            a = math.radians(22.5) + math.tau * i / 8
            p0 = Vec3(math.cos(a) * inner_r, math.sin(a) * inner_r, z)
            p1 = Vec3(math.cos(a) * outer_r, math.sin(a) * outer_r, z)
            self.add_polyline(parent, [p0, p1], color, self.cfg.line_thickness * 0.72, False, "oct-spoke")

    def clear_station(self):
        for node in [self.surface_root, self.line_root, self.accent_root, self.dome_root, self.lens_root, self.sky_root, getattr(self, "atmosphere_root", None), self.world_root, self.galaxy_root]:
            if node is not None:
                node.removeNode()
        self.surface_root = self.root_3d.attachNewNode("surface-root")
        self.line_root = self.root_3d.attachNewNode("line-root")
        self.accent_root = self.root_3d.attachNewNode("accent-root")
        self.dome_root = self.root_3d.attachNewNode("dome-root")
        self.lens_root = self.root_3d.attachNewNode("lens-root")
        self.sky_root = self.root_3d.attachNewNode("sky-root")
        self.atmosphere_root = self.root_3d.attachNewNode("atmosphere-root")
        self.world_root = self.root_3d.attachNewNode("world-root")
        self.user_build_root = self.world_root.attachNewNode("user-build-root")
        self.galaxy_root = self.root_3d.attachNewNode("galaxy-root")
        self.world_root.setTransparency(TransparencyAttrib.MAlpha)
        self.user_build_root.setTransparency(TransparencyAttrib.MAlpha)
        self.galaxy_root.setTransparency(TransparencyAttrib.MAlpha)
        self.atmosphere_root.setTransparency(TransparencyAttrib.MAlpha)
        self.room_bounds = []
        self.terrain_chunks = {}
        self.deep_water_creature_nodes = []
        self.deep_water_glow_nodes = []
        self.deep_water_feature_nodes = []
        self.deep_water_sky_creature_nodes = []
        self.deep_water_surface_refresh_time = -999.0
        self.named_region_bot_nodes = []
        self.named_region_bot_specs = []
        self.named_region_bot_pruned_count = 0
        self.io88_bot_root = None
        self.artifacts = []
        self.galaxy_nodes = []
        self.nearest_artifact = None
        self.nearest_artifact_dist = 999.0

    def rebuild_station(self):
        self.clear_station()
        self.current_bg_rgb = self.compute_target_sky_rgb()
        self.current_sky_rgb = self.current_bg_rgb
        self.setBackgroundColor(*self.current_bg_rgb)
        self.fog.setColor(*self.current_bg_rgb)
        self.camLens.setFov(self.cfg.fov)
        self.camLens.setNearFar(0.05, self.cfg.fog_distance)
        self.fog.setLinearRange(self.cfg.fog_distance * 0.48, self.cfg.fog_distance)
        self.build_dynamic_sky_guides()
        self.build_flatland_disk()
        self.build_named_region_bot_network()
        self.build_biome_ring_framework()
        self.build_hub()
        self.build_observatory_dome()
        self.build_artifacts()
        self.build_sector_gates()
        self.build_lens()
        self.build_galaxy_targets()
        self.update_world_chunks(force=True)
        cr = self.station_line_color(0.95)
        for np in self.crosshair_parts:
            np.setColor(*cr)

    def build_dynamic_sky_guides(self):
        """Build the persistent star overlay for the shared HoloVerse space sky.

        Pass 26 retires the old atmosphere rings, day/dusk guides, sun, moon,
        and orbital sky bands.  The authored star texture is the sky authority;
        this small line-star layer only adds HoloVerse's vector sparkle language.
        """
        self.sky_ring_nodes = []
        self.celestial_nodes = {}
        self.legacy_sky_background_removed = True
        self.forest_tree_variants = tuple(FOREST_TREE_VARIANTS)
        if not hasattr(self, "atmosphere_root") or self.atmosphere_root.isEmpty():
            self.atmosphere_root = self.root_3d.attachNewNode("atmosphere-root")
            self.atmosphere_root.setTransparency(TransparencyAttrib.MAlpha)
        self.build_celestial_cycle_markers()

    def build_celestial_cycle_markers(self):
        """Build fixed vector stars; there is intentionally no sun, moon, or orbit."""
        self.celestial_nodes = {}
        star_root = self.atmosphere_root.attachNewNode("persistent-star-field")
        star_segments = []
        for i in range(CELESTIAL_STAR_COUNT):
            a = (i * 137.508) % 360.0
            ring = i % 6
            radius = 82.0 + ring * 26.0 + (i % 5) * 2.2
            z = 102.0 + (i % 7) * 15.0
            x = math.cos(math.radians(a)) * radius
            y = math.sin(math.radians(a)) * radius
            size = 0.82 + (i % 4) * 0.18
            star_segments.append((Vec3(x - size, y, z), Vec3(x + size, y, z)))
            star_segments.append((Vec3(x, y - size, z), Vec3(x, y + size, z)))
        self.add_line_segments(
            star_root,
            star_segments,
            (0.82, 0.92, 1.0, 0.44),
            self.cfg.line_thickness * 0.28,
            "persistent-stars",
        )
        self.celestial_nodes = {"stars": star_root}
        self.update_celestial_cycle_markers(0.0)

    def update_celestial_cycle_markers(self, dt: float):
        if not hasattr(self, "atmosphere_root") or self.atmosphere_root.isEmpty():
            return
        self.atmosphere_root.setPos(self.player_pos.x, self.player_pos.y, 0.0)
        nodes = getattr(self, "celestial_nodes", {}) or {}
        if nodes.get("stars") and not nodes["stars"].isEmpty():
            nodes["stars"].setColorScale(0.82, 0.92, 1.0, 0.48)
        self.current_sun_alpha = 0.0
        self.current_moon_alpha = 0.0
        self.current_star_alpha = 0.48
        self.current_day_factor = 0.0
        self.current_dusk_factor = 0.0

    def cleanup_obsolete_space_layers(self):
        """Remove older space-layer roots that were parented outside the active world shell.

        Previous passes attached endless-space-layer directly to render. When the
        source bridge reloaded, those old nodes could survive and collide with
        the current HoloSpace view. This cleanup keeps one authoritative layer.
        """
        render = getattr(self, "render", None)
        if render is None:
            return
        active = getattr(self, "space_layer_root", None)
        for pattern in ("**/endless-space-layer", "**/holo-dyson-space-layer", "**/dyson-sphere-build-megastructure", "**/space-layer-asteroid-*", "**/endless-space-stars"):
            try:
                matches = list(render.findAllMatches(pattern))
            except Exception:
                matches = []
            for node in matches:
                try:
                    if active is not None and not active.isEmpty() and node == active:
                        continue
                    node.removeNode()
                except Exception:
                    pass

    def setup_space_layer(self):
        self.cleanup_obsolete_space_layers()
        if getattr(self, "space_layer_root", None) is not None and not self.space_layer_root.isEmpty():
            self.space_layer_root.removeNode()
        parent = getattr(self, "root_3d", None) or getattr(self, "render", None)
        if parent is None:
            return
        self.space_layer_root = parent.attachNewNode("holo-dyson-space-layer")
        self.space_layer_root.setPythonTag("holoverse_space_layer", "dyson_authoritative_pass77")
        self.space_layer_root.setTransparency(TransparencyAttrib.MAlpha)
        self.space_layer_root.setLightOff(1)
        self.space_layer_root.setFogOff(1)
        self.space_layer_root.hide()
        self.space_layer_asteroid_nodes = []
        self.space_layer_initialized = False
        self.space_layer_active = False
        self.space_layer_build_root = None
        self.space_layer_build_nodes = []
        self.rebuild_space_layer()

    def rebuild_space_layer(self):
        root = getattr(self, "space_layer_root", None)
        if root is None or root.isEmpty():
            return
        for child in root.getChildren():
            child.removeNode()
        star_segments = []
        rng = random.Random(88088)
        radius = float(SPACE_LAYER_FIELD_RADIUS)
        depth = float(SPACE_LAYER_FIELD_DEPTH)
        for idx in range(int(SPACE_LAYER_STAR_COUNT)):
            ang = rng.random() * math.tau
            rr = radius * math.sqrt(rng.random())
            z = rng.uniform(-depth * 0.34, depth)
            x = math.cos(ang) * rr
            y = math.sin(ang) * rr
            s = rng.uniform(1.0, 3.4)
            star_segments.append((Vec3(x - s, y, z), Vec3(x + s, y, z)))
            if idx % 3 == 0:
                star_segments.append((Vec3(x, y - s, z), Vec3(x, y + s, z)))
        self.space_layer_star_root = root.attachNewNode("endless-space-starfield-root")
        self.space_layer_star_root.setTransparency(TransparencyAttrib.MAlpha)
        self.space_layer_star_root.setLightOff(1)
        self.space_layer_star_root.setFogOff(1)
        self.add_line_segments(self.space_layer_star_root, star_segments, (0.82, 0.92, 1.0, 0.62), self.cfg.line_thickness * 0.22, "endless-space-stars")
        self.space_layer_asteroid_nodes = []
        self.space_layer_build_nodes = []
        self.space_layer_build_root = None
        for idx in range(int(SPACE_LAYER_ASTEROID_COUNT)):
            ang = rng.random() * math.tau
            rr = rng.uniform(radius * 0.20, radius * 0.92)
            z = rng.uniform(-depth * 0.12, depth * 0.88)
            node = root.attachNewNode(f"space-layer-asteroid-{idx:02d}")
            node.setPos(math.cos(ang) * rr, math.sin(ang) * rr, z)
            node.setHpr(rng.uniform(0, 360), rng.uniform(-45, 45), rng.uniform(0, 360))
            size = rng.uniform(4.0, 13.0)
            pts = []
            sides = rng.randint(5, 8)
            for i in range(sides):
                aa = math.tau * i / sides
                local_r = size * rng.uniform(0.55, 1.15)
                pts.append(Vec3(math.cos(aa) * local_r, math.sin(aa) * local_r, rng.uniform(-size * 0.28, size * 0.28)))
            self.add_polyline(node, pts, (0.54, 0.62, 0.76, 0.54), self.cfg.line_thickness * 0.26, True, "space-asteroid-wire")
            node.setPythonTag("spin", Vec3(rng.uniform(-5, 5), rng.uniform(-7, 7), rng.uniform(-11, 11)))
            self.space_layer_asteroid_nodes.append(node)
        self.build_space_layer_megastructure(root)
        self.space_layer_initialized = True

    def build_space_layer_megastructure(self, root):
        self.space_layer_build_nodes = []
        self.space_layer_dark_matter_nodes = []
        self.space_layer_octagon_nodes = []
        self.space_layer_accretion_nodes = []
        self.space_layer_inspector_nodes = []
        self.space_layer_white_dwarf_nodes = []
        self.space_layer_lensing_nodes = []
        self.space_layer_photon_beam_nodes = []
        self.space_layer_build_root = root.attachNewNode("dyson-sphere-build-megastructure")
        self.space_layer_build_root.setPythonTag("dyson_sphere_landmark", True)
        self.space_layer_build_root.setTransparency(TransparencyAttrib.MAlpha)
        self.space_layer_build_root.setLightOff(1)
        self.space_layer_build_root.setFogOff(1)
        self.space_layer_build_root.setPos(0.0, 0.0, 165.0)

        radius = float(SPACE_DYSON_RADIUS)
        outer_radius = float(SPACE_DYSON_OUTER_RADIUS)
        event_horizon = float(SPACE_DYSON_EVENT_HORIZON_RADIUS)
        self.dyson_visual_root = self.space_layer_build_root.attachNewNode("dyson-visual-root")
        self.dyson_visual_root.setTransparency(TransparencyAttrib.MAlpha)
        self.dyson_visual_root.setLightOff(1)
        self.dyson_visual_root.setFogOff(1)
        self.dyson_visual_root.setTwoSided(True)

        shadow_root = self.dyson_visual_root.attachNewNode("dyson-black-hole-shadow")
        shadow_root.setTransparency(TransparencyAttrib.MAlpha)
        shadow_root.setTwoSided(True)
        for idx, (disc_radius, alpha, hpr) in enumerate((
            (event_horizon * 1.02, 0.98, Vec3(0.0, 0.0, 0.0)),
            (event_horizon * 1.16, 0.72, Vec3(0.0, 90.0, 0.0)),
            (event_horizon * 1.16, 0.72, Vec3(90.0, 0.0, 0.0)),
            (event_horizon * 1.26, 0.42, Vec3(48.0, 42.0, 0.0)),
        )):
            disc = self.add_disc_surface(shadow_root, disc_radius, 0.0, (0.01, 0.01, 0.03, alpha), segments=88, name=f"dyson-shadow-disc-{idx:02d}")
            if disc is not None:
                disc.setHpr(hpr)
                try:
                    disc.setDepthWrite(False)
                    disc.setBin("transparent", 54)
                except Exception:
                    pass
        self.dyson_landmark_core = shadow_root

        # Pass 82: build the white dwarf as an actual 3D wireframe sphere
        # instead of billboard-like circles.  The star stays readable from a
        # distance, but every primary contour is now volumetric.
        self.dyson_white_dwarf_root = self.dyson_visual_root.attachNewNode("dyson-white-dwarf-star-core")
        self.dyson_white_dwarf_root.setTransparency(TransparencyAttrib.MAlpha)
        self.dyson_white_dwarf_root.setLightOff(1)
        self.dyson_white_dwarf_root.setFogOff(1)
        self.dyson_white_dwarf_root.setTwoSided(True)
        white_r = float(SPACE_WHITE_DWARF_RADIUS)
        halo_r = float(SPACE_WHITE_DWARF_HALO_RADIUS)
        latitudes = (-0.78, -0.48, -0.18, 0.18, 0.48, 0.78)
        for idx, lat_t in enumerate(latitudes):
            z = white_r * lat_t
            local_r = max(white_r * 0.24, math.sqrt(max(0.0, white_r * white_r - z * z)))
            alpha = 0.88 - abs(lat_t) * 0.22
            node = self.add_polyline(self.dyson_white_dwarf_root, self.ellipse_points(local_r, local_r, 52, idx * 7.5, "xy", Vec3(0.0, 0.0, z)), (0.94, 0.98, 1.0, alpha), self.cfg.line_thickness * (0.56 + (1.0 - abs(lat_t)) * 0.18), True, f"white-dwarf-latitude-{idx:02d}")
            if node is not None:
                node.setPythonTag("base_alpha", float(alpha))
                node.setPythonTag("base_scale", 1.0)
                self.space_layer_white_dwarf_nodes.append(node)
        for idx, hpr in enumerate((Vec3(0.0, 90.0, 0.0), Vec3(90.0, 90.0, 0.0), Vec3(45.0, 90.0, 0.0), Vec3(-45.0, 90.0, 0.0))):
            meridian_root = self.dyson_white_dwarf_root.attachNewNode(f"white-dwarf-meridian-root-{idx:02d}")
            meridian_root.setHpr(hpr)
            alpha = 0.76 - idx * 0.08
            node = self.add_polyline(meridian_root, self.ellipse_points(white_r, white_r, 58, idx * 9.0, "xy"), (0.92, 0.98, 1.0, alpha), self.cfg.line_thickness * 0.58, True, f"white-dwarf-meridian-{idx:02d}")
            if node is not None:
                node.setPythonTag("base_alpha", float(alpha))
                node.setPythonTag("base_scale", 1.0)
                self.space_layer_white_dwarf_nodes.append(node)
        glow_holder = self.dyson_white_dwarf_root.attachNewNode("white-dwarf-halo-holder")
        glow_holder.setHpr(Vec3(18.0, 54.0, 0.0))
        for idx, radius_scale in enumerate((1.34, 1.92)):
            alpha = 0.24 - idx * 0.08
            ring = self.add_polyline(glow_holder, self.ellipse_points(white_r * radius_scale, white_r * radius_scale * (0.76 - idx * 0.10), 68, idx * 12.0, "xy"), (0.82, 0.94, 1.0, alpha), self.cfg.line_thickness * (0.32 - idx * 0.04), True, f"white-dwarf-halo-{idx:02d}")
            if ring is not None:
                ring.setPythonTag("base_alpha", float(alpha))
                ring.setPythonTag("base_scale", 1.0)
                self.space_layer_white_dwarf_nodes.append(ring)
        self.add_line_segments(self.dyson_white_dwarf_root, [
            (Vec3(-halo_r * 0.34, 0, 0), Vec3(halo_r * 0.34, 0, 0)),
            (Vec3(0, -halo_r * 0.34, 0), Vec3(0, halo_r * 0.34, 0)),
            (Vec3(0, 0, -halo_r * 0.30), Vec3(0, 0, halo_r * 0.30)),
        ], (0.92, 0.98, 1.0, 0.62), self.cfg.line_thickness * 0.30, "white-dwarf-prismatic-axis")

        self.dyson_lensing_root = self.dyson_visual_root.attachNewNode("dyson-gravity-lensing-root")
        self.dyson_lensing_root.setTransparency(TransparencyAttrib.MAlpha)
        self.dyson_lensing_root.setLightOff(1)
        self.dyson_lensing_root.setFogOff(1)
        self.dyson_lensing_root.setTwoSided(True)
        for idx in range(int(SPACE_GRAVITY_LENS_RING_COUNT)):
            t = idx / max(1.0, float(SPACE_GRAVITY_LENS_RING_COUNT - 1))
            rx = float(SPACE_DYSON_EVENT_HORIZON_RADIUS) * (1.24 + t * 2.25)
            ry = rx * (0.25 + 0.12 * idx)
            holder = self.dyson_lensing_root.attachNewNode(f"white-dwarf-einstein-ring-holder-{idx:02d}")
            holder.setHpr(Vec3(-12.0 + idx * 7.0, 61.0 - idx * 4.0, idx * 11.0))
            color = (0.70 + 0.05 * min(idx, 3), 0.88 + 0.02 * idx, 1.0, 0.48 - t * 0.18)
            ring = self.add_polyline(holder, self.ellipse_points(rx, ry, 96, idx * 9.0, "xy"), color, self.cfg.line_thickness * (0.26 - t * 0.06), True, f"white-dwarf-einstein-ring-{idx:02d}")
            if ring is not None:
                ring.setPythonTag("base_alpha", float(color[3]))
                ring.setPythonTag("base_scale", 1.0 + t * 0.05)
                self.space_layer_lensing_nodes.append(ring)
        for idx in range(int(SPACE_LENSING_CAUSTIC_COUNT)):
            pts = []
            phase = idx * math.tau / max(1, int(SPACE_LENSING_CAUSTIC_COUNT))
            span = math.radians(128.0 + (idx % 3) * 26.0)
            base_r = float(SPACE_DYSON_EVENT_HORIZON_RADIUS) * (1.55 + 0.08 * (idx % 4))
            for step in range(34):
                u = step / 33.0
                a = phase - span * 0.5 + span * u
                pinch = math.sin(u * math.pi)
                r = base_r + pinch * (42.0 + 8.0 * (idx % 3))
                z = math.sin(a * 1.7 + idx) * 18.0 * pinch
                pts.append(Vec3(math.cos(a) * r, math.sin(a) * r * 0.62, z))
            color = (0.86, 0.96, 1.0, 0.34 + 0.04 * (idx % 3))
            node = self.add_polyline(self.dyson_lensing_root, pts, color, self.cfg.line_thickness * 0.20, False, f"white-dwarf-lensing-caustic-{idx:02d}")
            if node is not None:
                node.setPythonTag("base_alpha", float(color[3]))
                node.setPythonTag("phase", phase)
                self.space_layer_lensing_nodes.append(node)
        for idx in range(int(SPACE_PHOTON_BEAM_COUNT)):
            pts = []
            phase = idx * math.tau / max(1, int(SPACE_PHOTON_BEAM_COUNT))
            turn = -1.0 if idx % 2 else 1.0
            for step in range(46):
                u = step / 45.0
                bend = math.sin(u * math.pi) * (0.72 + 0.10 * (idx % 4)) * turn
                a = phase + bend
                r = white_r * 1.05 + u * halo_r * (1.52 + 0.05 * (idx % 3))
                y_squash = 0.52 + 0.06 * math.sin(idx)
                z = math.sin(phase * 2.0 + u * math.pi) * (18.0 + 52.0 * math.sin(u * math.pi))
                pts.append(Vec3(math.cos(a) * r, math.sin(a) * r * y_squash, z))
            color = (0.86, 0.96, 1.0, 0.20 + 0.04 * (idx % 4))
            node = self.add_polyline(self.dyson_lensing_root, pts, color, self.cfg.line_thickness * 0.16, False, f"white-dwarf-bent-light-ray-{idx:02d}")
            if node is not None:
                node.setPythonTag("base_alpha", float(color[3]))
                node.setPythonTag("phase", phase)
                node.setPythonTag("base_scale", 1.0 + 0.015 * idx)
                self.space_layer_photon_beam_nodes.append(node)

        self.dyson_replacement_mesh_root = self.dyson_visual_root.attachNewNode("dyson-replacement-mesh-root")
        self.dyson_replacement_mesh_root.setTransparency(TransparencyAttrib.MAlpha)
        self.dyson_replacement_mesh = self.try_load_space_landmark_mesh(self.dyson_replacement_mesh_root, SPACE_DYSON_MESH_BASENAMES, event_horizon * 1.12, "dyson-replacement-mesh")

        self.dyson_landmark_core_nodes = []
        ring_specs = [
            (event_horizon * 1.28, event_horizon * 0.52, Vec3(18.0, 74.0, 0.0), (1.00, 0.58, 0.16, 0.44), 0.30, "dyson-accretion-hot"),
            (event_horizon * 1.56, event_horizon * 0.74, Vec3(-24.0, 62.0, 0.0), (0.22, 0.86, 1.00, 0.38), 0.26, "dyson-accretion-cold"),
            (event_horizon * 1.84, event_horizon * 0.92, Vec3(28.0, 38.0, 0.0), (0.72, 0.28, 1.00, 0.22), 0.22, "dyson-accretion-outer"),
        ]
        for idx, (rx, ry, hpr, color, thickness, name) in enumerate(ring_specs):
            ring_parent = self.dyson_visual_root.attachNewNode(f"{name}-root")
            ring_parent.setHpr(hpr)
            node = self.add_polyline(ring_parent, self.ellipse_points(rx, ry, 72, idx * 17.0, "xy"), color, self.cfg.line_thickness * thickness, True, name)
            if node is not None:
                node.setPythonTag("ring_type", "accretion")
                node.setPythonTag("base_alpha", float(color[3]))
                node.setPythonTag("base_scale", 1.0 + idx * 0.04)
                self.dyson_landmark_core_nodes.append(node)
                self.space_layer_accretion_nodes.append(node)

        # Pass 81: the Dyson shell now grows as an actual octagonal 3D cage.
        # The construction order is interleaved across octants so the sphere
        # fills evenly over time instead of revealing in a single band.
        self.build_dyson_shell_segments(self.dyson_visual_root, radius)

        # Slow, transparent, colorful 4D octagonal field.
        self.dyson_octagon_root = self.dyson_visual_root.attachNewNode("dyson-4d-octagon-root")
        oct_specs = [
            (outer_radius * 0.98, Vec3(22.5, 90.0, 0.0), (0.32, 0.82, 1.00, 0.12), 0.24, 22.5),
        ]
        oct_roots = []
        for idx, (rad, hpr, color, thickness, offset_deg) in enumerate(oct_specs):
            oct_root = self.dyson_octagon_root.attachNewNode(f"dyson-octagon-layer-{idx:02d}")
            oct_root.setHpr(hpr)
            oct_roots.append((oct_root, rad, color))
            node = self.add_polyline(oct_root, self.polygon_points(rad, 0.0, 8, offset_deg), color, self.cfg.line_thickness * thickness, True, f"dyson-octagon-{idx:02d}")
            if node is not None:
                node.setPythonTag("base_alpha", float(color[3]))
                self.space_layer_octagon_nodes.append(node)
        if len(oct_roots) >= 2:
            a_root, a_rad, a_color = oct_roots[0]
            b_root, b_rad, _ = oct_roots[1]
            connector_parent = self.dyson_octagon_root.attachNewNode("dyson-octagon-connectors")
            segs = []
            pa = self.polygon_points(a_rad, 0.0, 8, 22.5)
            pb = self.polygon_points(b_rad, 0.0, 8, 0.0)
            for idx in range(8):
                segs.append((pa[idx], pb[idx]))
            self.add_line_segments(connector_parent, segs, (1.0, 0.30, 0.18, 0.15), self.cfg.line_thickness * 0.16, "dyson-octagon-connectors")

        # Dark matter ribbons / gravitational distortions.
        self.dyson_dark_matter_root = self.dyson_visual_root.attachNewNode("dyson-dark-matter-root")
        for idx in range(3):
            pts = []
            start_r = event_horizon * (1.10 + 0.03 * (idx % 3))
            end_r = radius * (0.82 + 0.04 * ((idx + 1) % 4))
            phase = idx * 0.54
            for step in range(52):
                t = step / 51.0
                ang = phase + t * math.tau * (1.18 + 0.08 * (idx % 4))
                r = start_r * (1.0 - t) + end_r * t
                lift = math.sin(ang * 1.8 + idx * 0.7) * radius * (0.10 + 0.09 * (1.0 - t))
                squash = 0.46 + 0.14 * math.sin(idx * 1.7)
                pts.append(Vec3(math.cos(ang) * r, math.sin(ang) * r * squash, lift))
            color = (0.16 + 0.05 * (idx % 4), 0.32 + 0.06 * ((idx + 1) % 4), 0.92 + 0.02 * (idx % 2), 0.12 + 0.012 * (idx % 5))
            node = self.add_polyline(self.dyson_dark_matter_root, pts, color, self.cfg.line_thickness * 0.14, False, f"dyson-dark-matter-{idx:02d}")
            if node is not None:
                node.setPythonTag("base_alpha", float(color[3]))
                node.setPythonTag("base_scale", 1.0 + idx * 0.01)
                node.setPythonTag("phase", phase)
                self.space_layer_dark_matter_nodes.append(node)

        # Multiple robots visibly inspecting the structure.
        self.dyson_inspector_root = self.dyson_visual_root.attachNewNode("dyson-inspector-root")
        self.dyson_construction_beam_root = self.dyson_visual_root.attachNewNode("dyson-construction-beam-root")
        self.dyson_construction_beam_root.setTransparency(TransparencyAttrib.MAlpha)
        self.dyson_construction_beam_root.setLightOff(1)
        self.dyson_construction_beam_root.setFogOff(1)
        self.space_layer_robot_beam_nodes = [None] * int(SPACE_DYSON_INSPECTOR_COUNT)
        for idx in range(int(SPACE_DYSON_INSPECTOR_COUNT)):
            orbit_radius = radius * (1.18 + 0.06 * (idx % 3))
            orbit_height = (-1.0 + idx / max(1.0, float(SPACE_DYSON_INSPECTOR_COUNT - 1))) * radius * 0.58
            drone = self.build_space_inspector_drone(self.dyson_inspector_root, idx, orbit_radius, orbit_height, color=(1.0, 0.28, 0.18), accent=(1.0, 0.66, 0.22))
            self.space_layer_inspector_nodes.append(drone)

    def visible_space_build_progress(self):

        return clamp(max(float(getattr(self, "space_build_progress", 0.0)), float(SPACE_BUILD_VISUAL_FLOOR)), 0.0, 1.0)

    def update_space_build_megastructure(self, dt: float, space_alpha: float):
        build_root = getattr(self, "space_layer_build_root", None)
        if build_root is None or build_root.isEmpty():
            return
        visual_progress = self.visible_space_build_progress()
        pulse = 0.5 + 0.5 * math.sin(self.elapsed * 0.72)
        build_root.setH(build_root.getH() + dt * 0.08)
        build_root.setScale(0.995 + pulse * 0.008)
        build_root.setColorScale(1.0, 1.0, 1.0, clamp(space_alpha * 0.98, 0.0, 1.0))

        visual_root = getattr(self, "dyson_visual_root", None)
        if visual_root is not None and not visual_root.isEmpty():
            visual_root.setH(visual_root.getH() + dt * 0.04)
            visual_root.setP(math.sin(self.elapsed * 0.05) * 1.8)

        core = getattr(self, "dyson_landmark_core", None)
        if core is not None and not core.isEmpty():
            core.show()
            core.setH(core.getH() - dt * 1.2)
            core.setScale(1.0 + pulse * 0.012)
            core.setColorScale(0.04, 0.05, 0.08, clamp(0.82 * space_alpha, 0.0, 0.94))

        replacement_mesh = getattr(self, "dyson_replacement_mesh", None)
        if replacement_mesh is not None and not replacement_mesh.isEmpty():
            glow = 0.72 + pulse * 0.08
            replacement_mesh.setH(replacement_mesh.getH() - dt * 0.22)
            replacement_mesh.setColorScale(0.04 * glow, 0.05 * glow, 0.09 * glow, clamp(0.88 * space_alpha, 0.0, 0.96))

        white_root = getattr(self, "dyson_white_dwarf_root", None)
        star_pulse = 0.5 + 0.5 * math.sin(self.elapsed * 2.8)
        slow_flare = 0.5 + 0.5 * math.sin(self.elapsed * 0.41)
        if white_root is not None and not white_root.isEmpty():
            white_root.show()
            white_root.setH(white_root.getH() - dt * 2.4)
            white_root.setP(math.sin(self.elapsed * 0.18) * 2.2)
            white_root.setScale(1.0 + star_pulse * 0.035 + slow_flare * 0.012)
            white_root.setColorScale(0.94 + star_pulse * 0.06, 0.98 + star_pulse * 0.04, 1.0, clamp(space_alpha, 0.0, 1.0))
        for idx, node in enumerate(list(getattr(self, "space_layer_white_dwarf_nodes", []) or [])):
            if node is None or node.isEmpty():
                continue
            alpha = float(node.getPythonTag("base_alpha") or 0.70)
            scale = float(node.getPythonTag("base_scale") or 1.0)
            flicker = 0.82 + 0.18 * math.sin(self.elapsed * (1.6 + idx * 0.05) + idx * 0.73)
            node.show()
            node.setScale(scale * (1.0 + star_pulse * 0.060 + 0.020 * math.sin(self.elapsed * 0.9 + idx)))
            node.setColorScale(0.92 + 0.10 * flicker, 0.97 + 0.06 * flicker, 1.0, clamp(alpha * space_alpha * flicker, 0.0, 1.0))

        lens_root = getattr(self, "dyson_lensing_root", None)
        if lens_root is not None and not lens_root.isEmpty():
            lens_root.show()
            lens_root.setH(lens_root.getH() + dt * 0.16)
            lens_root.setR(math.sin(self.elapsed * 0.13) * 3.0)
        for idx, node in enumerate(list(getattr(self, "space_layer_lensing_nodes", []) or [])):
            if node is None or node.isEmpty():
                continue
            alpha = float(node.getPythonTag("base_alpha") or 0.28)
            phase = float(node.getPythonTag("phase") or (idx * 0.31))
            scale = float(node.getPythonTag("base_scale") or 1.0)
            shimmer = 0.72 + 0.28 * math.sin(self.elapsed * 0.74 + phase + idx * 0.17)
            node.show()
            node.setScale(scale * (1.0 + 0.018 * shimmer))
            node.setColorScale(0.82 + 0.18 * shimmer, 0.92 + 0.08 * shimmer, 1.0, clamp(alpha * space_alpha * shimmer, 0.0, 0.72))
        for idx, node in enumerate(list(getattr(self, "space_layer_photon_beam_nodes", []) or [])):
            if node is None or node.isEmpty():
                continue
            alpha = float(node.getPythonTag("base_alpha") or 0.20)
            phase = float(node.getPythonTag("phase") or 0.0)
            scale = float(node.getPythonTag("base_scale") or 1.0)
            wave = 0.62 + 0.38 * math.sin(self.elapsed * 0.92 + phase * 2.0)
            node.show()
            node.setScale(scale * (1.0 + 0.020 * wave))
            node.setColorScale(0.88 + 0.10 * wave, 0.96 + 0.04 * wave, 1.0, clamp(alpha * space_alpha * (0.72 + 0.28 * wave), 0.0, 0.54))

        build_nodes = list(getattr(self, "space_layer_build_nodes", []) or [])
        total_build_nodes = max(1, len(build_nodes))
        target_build_float = clamp(visual_progress, 0.0, 1.0) * total_build_nodes
        finished_count = int(target_build_float)
        partial_amount = clamp(target_build_float - finished_count, 0.0, 1.0)
        pending_nodes = []
        for idx, node in enumerate(build_nodes):
            if node is None or node.isEmpty():
                continue
            build_index = int(node.getPythonTag("construction_index") or idx)
            base_alpha = float(node.getPythonTag("base_alpha") or 0.28)
            if build_index < finished_count:
                show_alpha = base_alpha * (0.88 + 0.12 * math.sin(self.elapsed * 0.48 + idx * 0.33))
                node.show()
            elif build_index == finished_count:
                show_alpha = base_alpha * max(0.14, partial_amount)
                node.show()
                pending_nodes.append(node)
            else:
                if build_index <= finished_count + int(SPACE_DYSON_INSPECTOR_COUNT):
                    show_alpha = base_alpha * 0.06
                    node.show()
                    pending_nodes.append(node)
                else:
                    node.hide()
                    continue
            node.setScale(float(node.getPythonTag("base_scale") or 1.0) * (1.0 + 0.008 * math.sin(self.elapsed * 0.62 + idx * 0.41)))
            node.setColorScale(1.0, 0.26 + 0.06 * pulse, 0.16 + 0.05 * pulse, clamp(show_alpha * space_alpha, 0.0, 0.82))

        inspector_nodes = list(getattr(self, "space_layer_inspector_nodes", []) or [])
        beam_root = getattr(self, "dyson_construction_beam_root", None)
        if beam_root is not None and not beam_root.isEmpty():
            beam_root.show()
        for idx, drone in enumerate(inspector_nodes):
            if drone is None or drone.isEmpty():
                continue
            orbit_radius = float(drone.getPythonTag("orbit_radius") or (SPACE_DYSON_RADIUS * 1.2))
            orbit_height = float(drone.getPythonTag("orbit_height") or 0.0)
            orbit_speed = float(drone.getPythonTag("orbit_speed") or 0.06)
            orbit_phase = float(drone.getPythonTag("orbit_phase") or 0.0)
            ang = orbit_phase + self.elapsed * orbit_speed
            bob = math.sin(self.elapsed * 0.82 + idx * 1.2) * 8.0
            pos = Vec3(math.cos(ang) * orbit_radius, math.sin(ang) * orbit_radius, orbit_height + bob)
            drone.setPos(pos)
            drone.lookAt(0.0, 0.0, 0.0)
            drone.setR(math.sin(self.elapsed * 0.62 + idx) * 14.0)
            drone.setColorScale(0.92 + pulse * 0.10, 0.94 + pulse * 0.08, 1.0, clamp(space_alpha * 0.94, 0.0, 1.0))
            for child in drone.getChildren():
                try:
                    if bool(child.getPythonTag("scan_ring")):
                        child.setScale(1.0 + 0.08 * math.sin(self.elapsed * 2.2 + idx * 0.6))
                        child.setColorScale(1.0, 0.72 + 0.20 * pulse, 0.34, clamp(0.24 + 0.18 * abs(math.sin(self.elapsed * 1.6 + idx)), 0.0, 0.52))
                except Exception:
                    pass
            beam_list = getattr(self, "space_layer_robot_beam_nodes", None)
            if beam_list is not None and idx < len(beam_list):
                old_beam = beam_list[idx]
                try:
                    if old_beam is not None and not old_beam.isEmpty():
                        old_beam.removeNode()
                except Exception:
                    pass
                target_node = None
                if pending_nodes:
                    target_node = pending_nodes[(idx * 2) % len(pending_nodes)]
                elif build_nodes:
                    target_node = build_nodes[min(len(build_nodes) - 1, max(0, finished_count - 1))]
                if target_node is not None and beam_root is not None and not beam_root.isEmpty():
                    target_anchor = target_node.getPythonTag("construction_anchor") or Vec3(0.0, 0.0, 0.0)
                    if not isinstance(target_anchor, Vec3):
                        try:
                            target_anchor = Vec3(target_anchor)
                        except Exception:
                            target_anchor = Vec3(0.0, 0.0, 0.0)
                    beam_start = Vec3(pos)
                    beam_alpha = clamp((0.36 + 0.24 * abs(math.sin(self.elapsed * 2.0 + idx))) * space_alpha, 0.0, 0.82)
                    beam = self.add_line_segments(beam_root, [(beam_start, target_anchor)], (1.0, 0.22 + 0.10 * pulse, 0.12, beam_alpha), self.cfg.line_thickness * 0.16, f"dyson-inspector-laser-{idx:02d}")
                    beam_list[idx] = beam
                else:
                    beam_list[idx] = None

    def space_layer_factor(self, pos=None):

        pos = pos if pos is not None else self.player_pos
        return smoothstep((float(pos.z) - float(SPACE_LAYER_START_Z)) / max(1.0, float(SPACE_LAYER_FULL_Z - SPACE_LAYER_START_Z)))

    def update_space_layer(self, dt: float):
        root = getattr(self, "space_layer_root", None)
        if root is None or root.isEmpty():
            return
        holospace = bool(getattr(self, "holospace_active", False))
        t = 1.0 if holospace else self.space_layer_factor()
        if t <= 0.01:
            root.hide()
            self.space_layer_active = False
            return
        root.show()
        self.space_layer_active = True
        if holospace:
            # Fixed HoloSpace landmark: key 8 and Orbit both point at this.
            root.setPos(Vec3(SPACE_DYSON_ROOT_POS))
        else:
            # Outside HoloSpace, preserve the high-altitude endless-space effect.
            root.setPos(self.player_pos.x, self.player_pos.y, self.player_pos.z + 40.0)
        space_alpha = clamp(t, 0.0, 1.0)
        # Pass 282.58 fix: in the game the shell mount never runs world.py's __init__,
        # so this counter may not exist yet; it used to crash this update every frame.
        self.space_build_total_seconds = float(getattr(self, "space_build_total_seconds", 0.0) or 0.0)
        self.space_build_progress = self.compute_space_build_progress(self.space_build_total_seconds)
        root.setColorScale(1.0, 1.0, 1.0, space_alpha)
        star_root = getattr(self, "space_layer_star_root", None)
        if star_root is not None and not star_root.isEmpty():
            if holospace:
                star_root.show()
                star_root.setColorScale(1.0, 0.34, 0.26, 0.18)
            else:
                star_root.show()
                star_root.setColorScale(1.0, 1.0, 1.0, clamp(space_alpha * 0.70, 0.0, 0.70))
        self.update_space_build_megastructure(dt, space_alpha)
        for node in list(getattr(self, "space_layer_asteroid_nodes", []) or []):
            if node is None or node.isEmpty():
                continue
            if holospace:
                # Old asteroid clutter is hidden near the Dyson viewing lane. The
                # asteroid field still exists for high-altitude free flight.
                node.hide()
                continue
            node.show()
            spin = node.getPythonTag("spin") or Vec3(0, 0, 0)
            node.setHpr(node.getH() + spin.x * dt, node.getP() + spin.y * dt, node.getR() + spin.z * dt)

    def setup_sky_png_card(self):
        """Compatibility entrypoint: build the persistent shared space sky shell."""
        self.setup_space_sky_shell()

    def setup_space_sky_shell(self):
        if getattr(self, "sky_png_root", None) is not None and not self.sky_png_root.isEmpty():
            self.sky_png_root.removeNode()
        self.sky_png_root = self.render.attachNewNode("holoverse-space-sky-root")
        self.sky_png_root.setDepthWrite(False)
        self.sky_png_root.setDepthTest(False)
        self.sky_png_root.setTwoSided(True)
        self.sky_png_root.setLightOff(1)
        self.sky_png_root.setFogOff(1)
        self.sky_png_root.setBin("background", 10)
        self.sky_png_card = None
        self.space_sky_cards = []
        tex = None
        try:
            tex = self.loader.loadTexture(Filename.fromOsSpecific(str(SPACE_SKY_TEXTURE_PATH)))
        except Exception:
            tex = None

        # One UV sphere avoids the visible corners of card/cube skies while
        # still reusing the exact MatrixCore space texture.  The texture edges
        # are authored to tile cleanly, so the longitude seam stays unobtrusive.
        radius = float(SPACE_SKY_SHELL_RADIUS)
        lat_steps = int(SPACE_SKY_LAT_STEPS)
        lon_steps = int(SPACE_SKY_LON_STEPS)
        fmt = GeomVertexFormat.getV3t2()
        vdata = GeomVertexData("holoverse-space-sky-sphere", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        texcoord = GeomVertexWriter(vdata, "texcoord")
        for iy in range(lat_steps + 1):
            v = iy / float(lat_steps)
            phi = -math.pi * 0.5 + math.pi * v
            z = math.sin(phi) * radius
            ring_r = math.cos(phi) * radius
            for ix in range(lon_steps + 1):
                u = ix / float(lon_steps)
                theta = math.tau * u
                vertex.addData3(math.cos(theta) * ring_r, math.sin(theta) * ring_r, z)
                texcoord.addData2(u, 1.0 - v)
        tris = GeomTriangles(Geom.UHStatic)
        row = lon_steps + 1
        for iy in range(lat_steps):
            for ix in range(lon_steps):
                a = iy * row + ix
                b = a + 1
                c = a + row
                d = c + 1
                tris.addVertices(a, c, b)
                tris.addVertices(b, c, d)
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("holoverse-space-sky-sphere")
        node.addGeom(geom)
        sphere = self.sky_png_root.attachNewNode(node)
        sphere.setTwoSided(True)
        sphere.setDepthWrite(False)
        sphere.setDepthTest(False)
        sphere.setLightOff(1)
        sphere.setFogOff(1)
        sphere.setBin("background", 11)
        sphere.setColorScale(0.90, 0.94, 1.0, 1.0)
        if tex is not None:
            sphere.setTexture(tex, 1)
        sphere.setPythonTag("holoverse_space_sky_surface", True)
        self.space_sky_cards = [sphere]
        self.sky_png_card = sphere
        self.update_sky_png_card(0.0)

    def update_sky_png_card(self, dt: float = 0.0):
        root = getattr(self, "sky_png_root", None)
        if root is None or root.isEmpty():
            return
        # Recenter the background shell on the player so the star texture is
        # effectively infinitely distant and never becomes a reachable wall.
        root.setPos(float(self.player_pos.x), float(self.player_pos.y), float(self.player_pos.z))

    def add_disc_surface(self, parent, radius: float, z: float, color, segments: int = 144, name: str = "disc-fill"):
        radius = max(1.0, float(radius))
        segments = max(12, int(segments))
        vdata = GeomVertexData(name, GeomVertexFormat.getV3(), Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        vertex.addData3(0.0, 0.0, z)
        for i in range(segments):
            ang = math.tau * i / segments
            vertex.addData3(math.cos(ang) * radius, math.sin(ang) * radius, z)
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segments):
            tris.addVertices(0, i + 1, ((i + 1) % segments) + 1)
            tris.closePrimitive()
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode(name)
        node.addGeom(geom)
        np = parent.attachNewNode(node)
        np.setColor(*color)
        if len(color) >= 4 and float(color[3]) < 0.999:
            np.setTransparency(TransparencyAttrib.MAlpha)
        else:
            np.setTransparency(TransparencyAttrib.MNone)
            np.setDepthWrite(True)
            np.setDepthTest(True)
        np.setTwoSided(True)
        return np

    def add_annular_sector_surface(self, parent, r0: float, r1: float, a0: float, a1: float, color, name: str = "biome-sector-fill", radial_steps: int = 7, angular_steps: int = 4):
        r0 = max(0.0, float(r0))
        r1 = max(r0 + 1.0, float(r1))
        radial_steps = max(1, int(radial_steps))
        angular_steps = max(1, int(angular_steps))
        vdata = GeomVertexData(name, GeomVertexFormat.getV3(), Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        for ri in range(radial_steps + 1):
            radius = lerp(r0, r1, ri / float(radial_steps))
            for ai in range(angular_steps + 1):
                ang = lerp(a0, a1, ai / float(angular_steps))
                x = math.cos(ang) * radius
                y = math.sin(ang) * radius
                z = self.world_height_at(x, y) - 0.018
                vertex.addData3(x, y, z)
        tris = GeomTriangles(Geom.UHStatic)
        row = angular_steps + 1
        for ri in range(radial_steps):
            for ai in range(angular_steps):
                i0 = ri * row + ai
                i1 = i0 + 1
                i2 = (ri + 1) * row + ai
                i3 = i2 + 1
                tris.addVertices(i0, i2, i1)
                tris.closePrimitive()
                tris.addVertices(i1, i2, i3)
                tris.closePrimitive()
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode(name)
        node.addGeom(geom)
        np = parent.attachNewNode(node)
        np.setColor(*color)
        if len(color) >= 4 and float(color[3]) < 0.999:
            np.setTransparency(TransparencyAttrib.MAlpha)
        else:
            np.setTransparency(TransparencyAttrib.MNone)
            np.setDepthWrite(True)
            np.setDepthTest(True)
        np.setTwoSided(True)
        return np

    def add_desert_annular_sector_surface(self, parent, ring, r0: float, r1: float, a0: float, a1: float, name: str = "desert-sector-fill", radial_steps: int = 18, angular_steps: int = 12):
        """Build a dune-aware static Desert surface with per-vertex sand shading."""
        r0=max(0.0,float(r0)); r1=max(r0+1.0,float(r1))
        radial_steps=max(1,int(radial_steps)); angular_steps=max(1,int(angular_steps))
        fmt=GeomVertexFormat.getV3c4()
        vdata=GeomVertexData(name,fmt,Geom.UHStatic)
        vertex=GeomVertexWriter(vdata,"vertex"); color=GeomVertexWriter(vdata,"color")
        trough=(0.245,0.105,0.028,1.0); mid=(0.475,0.245,0.060,1.0); crest=(0.735,0.430,0.125,1.0)
        def mix(a,b,t):
            t=clamp(float(t),0.0,1.0); return tuple(lerp(float(a[i]),float(b[i]),t) for i in range(4))
        for ri in range(radial_steps+1):
            radius=lerp(r0,r1,ri/float(radial_steps))
            for ai in range(angular_steps+1):
                ang=lerp(a0,a1,ai/float(angular_steps))
                x=math.cos(ang)*radius; y=math.sin(ang)*radius
                z=self.world_height_at(x,y)-0.018
                relief=desert_dune_relief_at(x,y,float(ring["r0"]),float(ring["r1"]))
                t=clamp((relief-0.12)/1.90,0.0,1.0)
                rgba=mix(trough,mid,min(1.0,t*1.65)) if t<0.58 else mix(mid,crest,(t-0.58)/0.42)
                vertex.addData3(x,y,z); color.addData4(*rgba)
        tris=GeomTriangles(Geom.UHStatic); row=angular_steps+1
        for ri in range(radial_steps):
            for ai in range(angular_steps):
                i0=ri*row+ai; i1=i0+1; i2=(ri+1)*row+ai; i3=i2+1
                tris.addVertices(i0,i2,i1); tris.closePrimitive(); tris.addVertices(i1,i2,i3); tris.closePrimitive()
        geom=Geom(vdata); geom.addPrimitive(tris); node=GeomNode(name); node.addGeom(geom)
        np=parent.attachNewNode(node)
        np.setLightOff(1); np.setTextureOff(10); np.setTransparency(TransparencyAttrib.MNone)
        np.setDepthWrite(True); np.setDepthTest(True); np.setTwoSided(True)
        np.setPythonTag("desert_dune_shaded_surface",1)
        return np

    def add_ice_annular_sector_surface(self, parent, ring, r0: float, r1: float, a0: float, a1: float, name: str = "ice-sector-fill", radial_steps: int = 18, angular_steps: int = 12):
        """Build a glacial-relief static Ice surface with cold depth shading."""
        r0=max(0.0,float(r0)); r1=max(r0+1.0,float(r1))
        radial_steps=max(1,int(radial_steps)); angular_steps=max(1,int(angular_steps))
        fmt=GeomVertexFormat.getV3c4()
        vdata=GeomVertexData(name,fmt,Geom.UHStatic)
        vertex=GeomVertexWriter(vdata,"vertex"); color=GeomVertexWriter(vdata,"color")
        deep=(0.055,0.19,0.39,1.0); mid=(0.14,0.46,0.78,1.0); high=(0.46,0.82,0.96,1.0); crest=(0.80,0.95,1.0,1.0)
        track_radius=(float(ring["r0"])+float(ring["r1"]))*0.5
        def mix(a,b,t):
            t=clamp(float(t),0.0,1.0); return tuple(lerp(float(a[i]),float(b[i]),t) for i in range(4))
        for ri in range(radial_steps+1):
            radius=lerp(r0,r1,ri/float(radial_steps))
            for ai in range(angular_steps+1):
                ang=lerp(a0,a1,ai/float(angular_steps))
                x=math.cos(ang)*radius; y=math.sin(ang)*radius
                z=self.world_height_at(x,y)-0.018
                relief=ice_glacial_relief_at(x,y,float(ring["r0"]),float(ring["r1"]),track_radius)
                t=clamp((relief-0.16)/1.62,0.0,1.0)
                rgba=mix(deep,mid,min(1.0,t*1.7)) if t<0.52 else (mix(mid,high,(t-0.52)/0.34) if t<0.86 else mix(high,crest,(t-0.86)/0.14))
                vertex.addData3(x,y,z); color.addData4(*rgba)
        tris=GeomTriangles(Geom.UHStatic); row=angular_steps+1
        for ri in range(radial_steps):
            for ai in range(angular_steps):
                i0=ri*row+ai; i1=i0+1; i2=(ri+1)*row+ai; i3=i2+1
                tris.addVertices(i0,i2,i1); tris.closePrimitive(); tris.addVertices(i1,i2,i3); tris.closePrimitive()
        geom=Geom(vdata); geom.addPrimitive(tris); node=GeomNode(name); node.addGeom(geom)
        np=parent.attachNewNode(node)
        np.setLightOff(1); np.setTextureOff(10); np.setTransparency(TransparencyAttrib.MNone)
        np.setDepthWrite(True); np.setDepthTest(True); np.setTwoSided(True)
        np.setPythonTag("ice_glacial_shaded_surface",1)
        return np

    def tag_surface_authority(self, np, role: str, owner_kind: str, owner_key: str, priority: int, **meta):
        if np is None or getattr(np, 'isEmpty', lambda: True)():
            return np
        np.setPythonTag('surface_role', str(role))
        np.setPythonTag('surface_owner_kind', str(owner_kind))
        np.setPythonTag('surface_owner_key', str(owner_key))
        np.setPythonTag('surface_priority', int(priority))
        for key, value in meta.items():
            np.setPythonTag(str(key), value)
        return np

    def biome_sector_angle_span(self, sector_idx: int, expanded: bool = False):
        sector_width = math.tau / float(BIOME_SECTOR_COUNT)
        owned_a0 = (int(sector_idx) % BIOME_SECTOR_COUNT) * sector_width
        owned_a1 = owned_a0 + sector_width
        if not expanded:
            return owned_a0, owned_a1
        return owned_a0 - sector_width * 0.62, owned_a0 + sector_width * 1.62

    def audit_surface_authority(self):
        summary = {
            'mode': 'surface-authority',
            'flat_surface_count': 0,
            'biome_fill_surface_count': 0,
            'biome_inner_band_surface_count': 0,
            'biome_inner_band_stream_overlap_count': 0,
            'water_fill_suppressed_count': 0,
            'metropolis_generic_overlap_removed_count': 0,
            'duplicate_surface_owner_keys': 0,
            'duplicate_surface_owner_key_names': [],
            'owner_kind_counts': {},
            'active_surface_authority_count': 0,
            'surface_owned_sector_mode': True,
            'opaque_fill_surface_count': 0,
        }
        owner_counts = {}
        try:
            for np in self.surface_root.findAllMatches('**/+GeomNode'):
                role = str(np.getPythonTag('surface_role') or '')
                if role == 'flatland_fill':
                    summary['flat_surface_count'] += 1
                    summary['opaque_fill_surface_count'] += 1
                elif role == 'biome_inner_band':
                    summary['biome_inner_band_surface_count'] += 1
                    summary['opaque_fill_surface_count'] += 1
        except Exception:
            pass
        for key, chunk in list((getattr(self, 'terrain_chunks', {}) or {}).items()):
            kind = str(chunk.getPythonTag('surface_owner_kind') or self.biome_ring_for_key(int(key[0])).get('kind', '') if self.biome_ring_for_key(int(key[0])) else '')
            owner_key = str(chunk.getPythonTag('surface_owner_key') or f'{int(key[0])}:{int(key[1])}')
            fill_enabled = int(chunk.getPythonTag('surface_fill_enabled') or 0)
            if fill_enabled:
                summary['biome_fill_surface_count'] += 1
                summary['opaque_fill_surface_count'] += 1
                owner_counts[owner_key] = owner_counts.get(owner_key, 0) + 1
                summary['owner_kind_counts'][kind] = int(summary['owner_kind_counts'].get(kind, 0)) + 1
                # Pass 282.24: 282.23 presentation bands are retired.  Sector
                # fills own their biome surface directly, so there is no
                # presentation-band/sector overlap category to test here.
            if int(chunk.getPythonTag('deep_water_ground_removed') or 0) == 1:
                summary['water_fill_suppressed_count'] += 1
        for key, chunk in list((getattr(self, 'metropolis_chunks', {}) or {}).items()):
            if int(chunk.getPythonTag('metropolis_generic_biome_overlap_removed') or 0) == 1:
                summary['metropolis_generic_overlap_removed_count'] += 1
        duplicates = sorted(k for k, v in owner_counts.items() if v > 1)
        summary['duplicate_surface_owner_keys'] = len(duplicates)
        summary['duplicate_surface_owner_key_names'] = duplicates[:12]
        summary['active_surface_authority_count'] = int(summary['flat_surface_count']) + int(summary['biome_inner_band_surface_count']) + int(summary['biome_fill_surface_count'])
        self.surface_audit_summary = summary
        return summary

    def add_world_label(self, parent, text: str, pos: Vec3, color, scale: float = 2.7):
        label = TextNode(f"world-label-{text}")
        label.setText(str(text))
        label.setAlign(TextNode.ACenter)
        label.setTextColor(*color)
        label.setShadow(0.045, 0.045)
        label.setShadowColor(0, 0, 0, min(0.80, color[3] if len(color) > 3 else 0.8))
        np = parent.attachNewNode(label)
        np.setPos(pos)
        np.setScale(scale)
        try:
            np.setBillboardPointEye()
        except Exception:
            pass
        np.setTransparency(TransparencyAttrib.MAlpha)
        return np

    def _flatland_grid_segments(self, radius: float, inner_radius: float, step: float, z: float):
        radius = max(1.0, float(radius))
        inner_radius = max(0.0, float(inner_radius))
        step = max(1.0, float(step))
        segments = []
        count = int(math.floor(radius / step))
        for idx in range(-count, count + 1):
            value = idx * step
            outer_half = math.sqrt(max(0.0, radius * radius - value * value))
            if outer_half <= 0.001:
                continue
            if abs(value) < inner_radius:
                inner_half = math.sqrt(max(0.0, inner_radius * inner_radius - value * value))
                if outer_half > inner_half + 0.001:
                    segments.append((Vec3(value, -outer_half, z), Vec3(value, -inner_half, z)))
                    segments.append((Vec3(value, inner_half, z), Vec3(value, outer_half, z)))
                    segments.append((Vec3(-outer_half, value, z), Vec3(-inner_half, value, z)))
                    segments.append((Vec3(inner_half, value, z), Vec3(outer_half, value, z)))
            else:
                segments.append((Vec3(value, -outer_half, z), Vec3(value, outer_half, z)))
                segments.append((Vec3(-outer_half, value, z), Vec3(outer_half, value, z)))
        return segments

    def build_flatland_disk(self):
        # Pass 30: restore a broad walkable flatland connected to the hub floor.
        floor_z = self.hub_ground_level()
        fill_z = floor_z - 0.022
        minor_z = floor_z + 0.010
        major_z = floor_z + 0.020
        outer_r = self.flatworld_disc_radius()
        inner_cut = max(0.0, self.hub_radius - 0.55)
        flat_palette = BIOME_LUSH_PALETTES["flat"]
        fill_color = self.biome_ground_fill_color({"kind": "flat"}, alpha=1.0, brighten=0.0)
        minor_color = rgb_to_rgba(flat_palette["soft"], 0.36, 1.08)
        major_color = rgb_to_rgba(flat_palette["line"], 0.58, 1.05)
        lane_color = rgb_to_rgba(flat_palette["accent"], 0.78, 1.0)
        boundary_color = rgb_to_rgba(flat_palette["canopy"], 0.88, 1.06)

        flat_fill = self.add_disc_surface(self.surface_root, outer_r, fill_z, fill_color, 160, "flatland-disc-fill")
        self.tag_surface_authority(flat_fill, "flatland_fill", "flat", "flatland-disc", 100, radius=float(outer_r), z=float(fill_z))
        minor_segments = self._flatland_grid_segments(outer_r, inner_cut, self.flatworld_minor_grid_step(), minor_z)
        major_segments = self._flatland_grid_segments(outer_r, inner_cut, self.flatworld_major_grid_step(), major_z)
        self.add_line_segments(self.line_root, minor_segments, minor_color, self.cfg.line_thickness * 0.46, "flatland-minor-grid")
        self.add_line_segments(self.line_root, major_segments, major_color, self.cfg.line_thickness * 0.66, "flatland-major-grid")

        ring_polys = []
        ring = self.hub_radius
        while ring < outer_r:
            ring += self.flatworld_major_grid_step()
            if ring < outer_r - 0.5:
                ring_polys.append(self.polygon_points(ring, major_z + 0.006, 96, 0.0))
        self.add_polyline_batch(self.line_root, ring_polys, major_color, self.cfg.line_thickness * 0.58, True, "flatland-range-rings")
        self.add_polyline(self.line_root, self.polygon_points(self.hub_radius + 0.25, major_z + 0.012, 96, 0.0), lane_color, self.cfg.line_thickness * 0.84, True, "flatland-hub-seam")
        self.add_polyline(self.line_root, self.polygon_points(outer_r, major_z + 0.018, 160, 0.0), boundary_color, self.cfg.line_thickness * 1.02, True, "flatland-outer-boundary")

        approach_segments = []
        lane_half = 4.8
        for sign in (-1.0, 1.0):
            approach_segments.extend([
                (Vec3(sign * lane_half, self.hub_radius, major_z + 0.025), Vec3(sign * lane_half, outer_r, major_z + 0.025)),
                (Vec3(sign * lane_half, -self.hub_radius, major_z + 0.025), Vec3(sign * lane_half, -outer_r, major_z + 0.025)),
                (Vec3(self.hub_radius, sign * lane_half, major_z + 0.025), Vec3(outer_r, sign * lane_half, major_z + 0.025)),
                (Vec3(-self.hub_radius, sign * lane_half, major_z + 0.025), Vec3(-outer_r, sign * lane_half, major_z + 0.025)),
            ])
        self.add_line_segments(self.line_root, approach_segments, lane_color, self.cfg.line_thickness * 0.82, "flatland-approach-lanes")

    def build_io88_flatland_bot(self):
        spec = next((item for item in NAMED_REGION_BOT_MAP if item.get("name") == "IO"), None)
        if spec is None:
            return None
        root = self.build_named_region_bot(spec)
        self.io88_bot_root = root
        return root

    def character_port_anchor(self, spec: dict) -> Vec3:
        """Ground position for a character standing at the Mushroom REDACTED port.
        ``port_offset`` is (along the ring, outward) in metres from the beam."""
        px, py = _fungal_civ.port_position()
        radial = math.atan2(py, px)
        ox, oy = spec.get("port_offset", (0.0, 0.0))
        tx, ty = -math.sin(radial), math.cos(radial)
        rx, ry = math.cos(radial), math.sin(radial)
        x, y = px + tx * float(ox) + rx * float(oy), py + ty * float(ox) + ry * float(oy)
        return Vec3(x, y, self.world_height_at(x, y))

    def named_region_bot_anchor(self, spec: dict) -> Vec3:
        if spec.get("character"):
            return self.character_port_anchor(spec)
        if spec.get("anchor_xy"):      # Pass 282.57: a guide placed at a fixed spot (IO at the start)
            x, y = (float(v) for v in spec["anchor_xy"])
            return Vec3(x, y, self.world_height_at(x, y) + 10.5)
        angle = math.radians(float(NAMED_REGION_BOT_ANCHOR_ANGLE_DEG))
        kind = str(spec.get("kind", "flat"))
        if kind == "space":
            # Orbit now patrols the Dyson build site instead of the older cluttered
            # outer-ring space marker, making the bot a landmark guide.
            return Vec3(SPACE_DYSON_BOT_ANCHOR)
        ring = self.biome_ring_for_key(spec.get("ring_key")) or BIOME_RINGS[0]
        span = float(ring["r1"]) - float(ring["r0"])
        if int(ring.get("key", 1)) == 1:
            radius = min(float(ring["r1"]) - 54.0, max(120.0, float(ring["r0"]) + span * 0.42))
        else:
            t = clamp(float(spec.get("anchor_t", 0.50)), 0.12, 0.88)
            radius = float(ring["r0"]) + span * t
        x = math.cos(angle) * radius
        y = math.sin(angle) * radius
        if kind == "water":
            z = self.deep_water_craft_eye_z(x, y, ring) + 9.0
        else:
            z = self.world_height_at(x, y) + 10.5
        return Vec3(x, y, z)

    def metropolis_named_bot_clearance_centers(self):
        centers = []
        # Pass 282.57 fix: in the game the shell mount owns bot anchors and skips
        # named_region_bot_anchor, so this used to find no centre and never cleared
        # the guide's lots.  Use whichever anchor function this host has.
        anchor_fn = getattr(self, "modern_region_bot_anchor", None) or self.named_region_bot_anchor
        for spec in NAMED_REGION_BOT_MAP:
            if str(spec.get("kind", "")).lower() != "metropolis":
                continue
            try:
                anchor = anchor_fn(spec)
                centers.append((float(anchor.x), float(anchor.y), str(spec.get("name", "Metropolis Bot"))))
            except Exception:
                continue
        return centers

    def metropolis_named_bot_clearance_name(self, x: float, y: float) -> str:
        radius = float(METROPOLIS_NAMED_BOT_CLEAR_RADIUS)
        radius_sq = radius * radius
        for ax, ay, name in self.metropolis_named_bot_clearance_centers():
            dx = float(x) - ax
            dy = float(y) - ay
            if (dx * dx + dy * dy) <= radius_sq:
                return name
        return ""

    def build_named_region_bot(self, spec: dict):
        name = str(spec.get("name", "Bot"))
        region = str(spec.get("region", "REGION"))
        activity = str(spec.get("activity", region) or region).strip()
        kind = str(spec.get("kind", region.lower()))
        color = tuple(float(c) for c in spec.get("color", (0.6, 0.8, 1.0)))
        accent = tuple(float(c) for c in spec.get("accent", (0.9, 1.0, 1.0)))
        root = self.world_root.attachNewNode(f"named-region-bot-{name.lower()}-{kind}")
        anchor = self.named_region_bot_anchor(spec)
        root.setPos(anchor)
        scale = float(NAMED_REGION_BOT_SCALE) * float(spec.get("scale", 1.0))
        root.setScale(scale)
        root.setTransparency(TransparencyAttrib.MAlpha)
        root.setLightOff(1)
        root.setTextureOff(10)
        root.setTwoSided(True)
        root.setPythonTag("named_region_bot_name", name)
        root.setPythonTag("named_region_bot_region", region)
        root.setPythonTag("named_region_bot_activity", activity)
        root.setPythonTag("named_region_bot_kind", kind)
        root.setPythonTag("named_region_bot_base_x", float(anchor.x))
        root.setPythonTag("named_region_bot_base_y", float(anchor.y))
        root.setPythonTag("named_region_bot_base_z", float(anchor.z))
        root.setPythonTag("named_region_bot_wander_radius", float(spec.get("wander_radius", 0.0) or 0.0))
        root.setPythonTag("named_region_bot_wander_speed", float(spec.get("wander_speed", 0.0) or 0.0))
        root.setPythonTag("named_region_bot_activity_flag", str(spec.get("activity_flag", "") or ""))
        root.setPythonTag("named_region_bot_spawn_nearby", bool(spec.get("spawn_nearby", False)))
        root.setPythonTag("named_region_bot_phase", len(getattr(self, "named_region_bot_nodes", [])) * 0.73)
        root.setPythonTag("named_region_bot_solid_color", True)
        if spec.get("character"):
            return self._build_character_bot(root, spec, name, activity, accent)
        root.setPythonTag("named_region_bot_hovering", True)
        base_rgba = (color[0], color[1], color[2], 0.94)
        mid_rgba = (color[0] * 0.72 + accent[0] * 0.28, color[1] * 0.72 + accent[1] * 0.28, color[2] * 0.72 + accent[2] * 0.28, 0.91)
        accent_rgba = (accent[0], accent[1], accent[2], 0.98)
        wire = Vec3(min(1.20, accent[0] * 1.08), min(1.20, accent[1] * 1.08), min(1.20, accent[2] * 1.08))
        shadow = (max(0.02, color[0] * 0.30), max(0.02, color[1] * 0.30), max(0.02, color[2] * 0.30), 0.38)
        self.add_disc_surface(root, 4.8, 0.05, shadow, 36, f"{name.lower()}-hover-pad")
        self.add_polyline(root, self.polygon_points(5.0, 0.35, 12, 15.0), accent_rgba, self.cfg.line_thickness * 0.58, True, f"{name.lower()}-hover-halo")

        # Pass 21: make regional activities readable from the world instead of
        # adding another HUD/objective-marker lane.  Artifact arrivals already
        # land roughly 50 world units inward from their guide; these low-cost
        # line cues occupy that physical gap and point directly at the guide.
        guide_signal = root.attachNewNode(f"{name.lower()}-guide-wayfinding")
        root.setPythonTag("named_region_bot_wayfinding", guide_signal)
        guide_signal.setTransparency(TransparencyAttrib.MAlpha)
        guide_signal.setLightOff(1)
        guide_signal.setTextureOff(10)
        guide_signal.setTwoSided(True)
        self.add_polyline(guide_signal, self.polygon_points(5.85, 0.24, 16, 11.25), (accent[0], accent[1], accent[2], 0.34), self.cfg.line_thickness * 0.38, True, f"{name.lower()}-guide-ring-inner")
        self.add_polyline(guide_signal, self.polygon_points(7.10, 0.28, 20, 0.0), (accent[0], accent[1], accent[2], 0.15), self.cfg.line_thickness * 0.30, True, f"{name.lower()}-guide-ring-outer")
        self.add_line_segments(guide_signal, [
            (Vec3(0.0, 0.0, 7.3), Vec3(0.0, 0.0, 11.0)),
            (Vec3(-0.62, 0.0, 10.15), Vec3(0.0, 0.0, 11.0)),
            (Vec3(0.62, 0.0, 10.15), Vec3(0.0, 0.0, 11.0)),
        ], (accent[0], accent[1], accent[2], 0.40), self.cfg.line_thickness * 0.40, f"{name.lower()}-guide-signal-mast")
        if kind not in {"space", "flat"}:
            chevrons = []
            for cue_y in (6.0, 9.0, 12.0):
                cue_z = 0.42
                chevrons.extend([
                    (Vec3(-1.65, cue_y + 1.20, cue_z), Vec3(0.0, cue_y, cue_z)),
                    (Vec3(1.65, cue_y + 1.20, cue_z), Vec3(0.0, cue_y, cue_z)),
                ])
            self.add_line_segments(guide_signal, chevrons, (accent[0], accent[1], accent[2], 0.34), self.cfg.line_thickness * 0.42, f"{name.lower()}-arrival-chevrons")
        if getattr(self, "box_model", None) is not None:
            self.add_box_model(root, Vec3(0.0, 0.0, 2.85), Vec3(0.0, 0.0, 0.0), Vec3(0.72, 0.44, 0.96), None, base_rgba, wire_rgb=wire, alpha=0.94)
            self.add_box_model(root, Vec3(0.0, 0.0, 5.25), Vec3(0.0, 0.0, 0.0), Vec3(0.58, 0.42, 0.46), None, accent_rgba, wire_rgb=wire, alpha=0.98)
            self.add_box_model(root, Vec3(-0.92, 0.0, 3.35), Vec3(0.0, 0.0, -8.0), Vec3(0.26, 0.30, 0.70), None, mid_rgba, wire_rgb=wire, alpha=0.91)
            self.add_box_model(root, Vec3(0.92, 0.0, 3.35), Vec3(0.0, 0.0, 8.0), Vec3(0.26, 0.30, 0.70), None, mid_rgba, wire_rgb=wire, alpha=0.91)
            self.add_box_model(root, Vec3(-0.42, 0.0, 1.10), Vec3(0.0, 0.0, -5.0), Vec3(0.18, 0.24, 0.38), None, accent_rgba, wire_rgb=wire, alpha=0.82)
            self.add_box_model(root, Vec3(0.42, 0.0, 1.10), Vec3(0.0, 0.0, 5.0), Vec3(0.18, 0.24, 0.38), None, accent_rgba, wire_rgb=wire, alpha=0.82)
        else:
            self.add_prism(root, 2.3, 5.4, base_rgba, 8, f"{name.lower()}-fallback-body")
            self.add_prism(root, 1.4, 2.1, accent_rgba, 8, f"{name.lower()}-fallback-head").setZ(5.2)
        limb_segments = []
        for sx in (-1.0, 1.0):
            limb_segments.extend([
                (Vec3(sx * 0.72, 0.0, 4.25), Vec3(sx * 2.40, 0.0, 3.45)),
                (Vec3(sx * 0.34, 0.0, 1.70), Vec3(sx * 1.10, 0.0, 0.60)),
                (Vec3(sx * 0.20, 0.0, 5.80), Vec3(sx * 0.90, 0.0, 6.55)),
            ])
        self.add_line_segments(root, limb_segments, accent_rgba, self.cfg.line_thickness * 0.62, f"{name.lower()}-hover-bot-lines")
        self.add_polyline(root, self.polygon_points(2.0, 6.75, 10, 18.0), accent_rgba, self.cfg.line_thickness * 0.62, True, f"{name.lower()}-sensor-ring")
        label_text = f"{name.upper()}\n{activity.upper()}"
        self.add_world_label(root, label_text, Vec3(0.0, 0.0, 8.35), accent_rgba, 0.74)
        if name == "IO":
            self.io88_bot_root = root
        return root

    # -- Pass 282.56: Nyx (the giant) and Orbit, characters rather than drones ------------------
    def _build_character_bot(self, root, spec, name, activity, accent):
        """A grounded character: no drone body, hover pad or wayfinding rings.
        Its skinned mannequin loads a step at a time once the player is near
        (``update_character_bots``), so building the network costs nothing."""
        look = CHARACTER_LOOKS[str(spec.get("character"))]
        root.setScale(1.0)
        root.setPythonTag("named_region_bot_hovering", False)
        root.setPythonTag("named_region_bot_character", str(spec.get("character")))
        root.setPythonTag("named_region_bot_focus_height", float(look["focus"]))
        root.setPythonTag("named_region_bot_wander_radius", 0.0)
        root.setPythonTag("named_region_bot_wander_speed", 0.0)
        root.setH(float(spec.get("heading_deg", -90.0)))
        label = f"{name.upper()}\n{activity.upper()}"
        tag = self.add_world_label(root, label, Vec3(0.0, 0.0, float(look["height"]) + (3.0 if look["height"] > 5 else 1.2)), (accent[0], accent[1], accent[2], 0.98), 0.74 if look["height"] > 5 else 0.42)
        if tag is not None:
            # the name stays readable through the fungal haze
            tag.setFogOff(100)
            tag.setLightOff(100)
            tag.setShaderOff(100)
            tag.setColorScaleOff(100)
            tag.setBin("fixed", 40)          # after the sky dome, which otherwise veils it
            tag.setDepthWrite(False)
        return root

    def _character_load_step(self):
        """Load Nyx's and Orbit's mannequins one step per call (parse the GLB,
        bake each clip, build each body), so approaching them never stalls."""
        if _ual_actor is None or not self.fungal_civilization_active():
            return None
        nodes = [n for n in self._active_named_region_bot_nodes() if n.getPythonTag("named_region_bot_character")]
        try:
            if not _ual_actor.GLB_PATH.is_file():
                return None
            key = str(_ual_actor.GLB_PATH.resolve())
            if key not in _ual_actor._SHARED:
                _ual_actor.skin_for()
                return "parse"
            for clip in ("Idle_Loop", "Idle_Talking_Loop"):
                if (key, clip) not in _ual_actor._CLIPS:
                    _ual_actor.bake_clip_step(clip, 0.008)
                    return clip
            for node in nodes:
                if node.getPythonTag("named_region_bot_actor") is None:
                    kind = str(node.getPythonTag("named_region_bot_character"))
                    look = CHARACTER_LOOKS[kind]
                    actor = _ual_actor.SkinnedCharacter(node, f"{str(node.getPythonTag('named_region_bot_name')).lower()}-character", look["height"], look["palette"],
                                                        clips=("Idle_Loop", "Idle_Talking_Loop"), rim=look["rim"], gsg=self.ring_ground_gsg(),
                                                        light={"sun": (0.78, 0.84, 0.80), "sky": (0.34, 0.44, 0.48), "bounce": (0.22, 0.34, 0.32)})
                    node.setPythonTag("named_region_bot_actor", actor)
                    return kind
        except Exception as exc:
            print(f"character_load_failed err={exc.__class__.__name__}:{exc}")
            self._character_load_failed = True
        return None

    def update_character_bots(self, dt: float):
        """Nyx and Orbit: idle (talking while in dialogue) and turn to face a nearby player."""
        nodes = [n for n in self._active_named_region_bot_nodes() if n.getPythonTag("named_region_bot_character")]
        if not nodes:
            return None
        px, py = float(self.player_pos.x), float(self.player_pos.y)
        near = min(math.hypot(n.getX() - px, n.getY() - py) for n in nodes)
        if near <= float(CHARACTER_LOAD_RADIUS) and not getattr(self, "_character_load_failed", False):
            self._character_load_step()
        elapsed = float(getattr(self, "elapsed", 0.0) or 0.0)
        for idx, node in enumerate(nodes):
            actor = node.getPythonTag("named_region_bot_actor")
            talking = bool(node.getPythonTag("named_region_bot_paused"))
            d = math.hypot(node.getX() - px, node.getY() - py)
            if d < 90.0:
                want = math.degrees(math.atan2(-(px - node.getX()), (py - node.getY())))
                cur = float(node.getH())
                delta = (want - cur + 180.0) % 360.0 - 180.0
                node.setH(cur + delta * min(1.0, float(dt) * (1.2 if node.getPythonTag("named_region_bot_character") == "giant" else 3.0)))
            if actor is not None and d < float(CHARACTER_LOAD_RADIUS):
                actor.play("Idle_Talking_Loop" if talking else "Idle_Loop", elapsed + idx * 0.7)
        return None

    def build_named_region_bot_network(self):
        for old in list(getattr(self, "named_region_bot_nodes", []) or []):
            try:
                if old is not None and not old.isEmpty():
                    old.removeNode()
            except Exception:
                pass
        self.named_region_bot_nodes = []
        self.named_region_bot_specs = []
        self.named_region_bot_pruned_count = 0
        for spec in NAMED_REGION_BOT_MAP[:int(MAX_NAMED_REGION_BOTS)]:
            bot = self.build_named_region_bot(spec)
            if bot is not None:
                self.named_region_bot_nodes.append(bot)
                self.named_region_bot_specs.append({"name": spec.get("name"), "region": spec.get("region"), "kind": spec.get("kind")})
        extras = self.named_region_bot_nodes[int(MAX_NAMED_REGION_BOTS):]
        for extra in extras:
            try:
                if extra is not None and not extra.isEmpty():
                    extra.removeNode()
                    self.named_region_bot_pruned_count += 1
            except Exception:
                pass
        self.named_region_bot_nodes = self.named_region_bot_nodes[:int(MAX_NAMED_REGION_BOTS)]
        self.build_dimension_gates()
        return self.named_region_bot_nodes

    # -- Pass 282.57: dimension gates ------------------------------------------------------
    def dimension_gate_placement(self, spec: dict):
        """(x, y, z, heading_deg) of the gate beside a guide: offset from the guide's
        anchor along the ring and outward, its opening turned towards the hub."""
        gate = dict(spec.get("gate") or {})
        # In the game the shell mount owns bot anchors (modern_region_bot_anchor);
        # world.py on its own uses named_region_bot_anchor.
        anchor_fn = getattr(self, "modern_region_bot_anchor", None) or self.named_region_bot_anchor
        anchor = self.character_port_anchor(spec) if spec.get("character") else anchor_fn(spec)
        outward = math.atan2(float(anchor.y), float(anchor.x))
        x, y = _dimension_gate.gate_position((anchor.x, anchor.y), outward, float(gate.get("along", 0.0)), float(gate.get("outward", 0.0)))
        if gate.get("snap") == "metropolis_lot" and _metro_layout is not None:
            # Stand on the middle of a city pad (cleared for the guide), never on a street.
            lx, ly = _metro_layout.lot_index_for_point(x, y)
            px0, py0, px1, py1 = _metro_layout.lot_pad_rect(lx, ly)
            x, y = (px0 + px1) * 0.5, (py0 + py1) * 0.5
            heading = math.degrees(math.atan2(x, -y))
            return x, y, float(self.world_height_at(x, y)) + float(_metro_layout.PAD_HEIGHT), heading
        heading = math.degrees(math.atan2(x, -y))          # local +y looks back at the hub
        return x, y, float(self.world_height_at(x, y)), heading

    def build_dimension_gates(self):
        for gate in list(getattr(self, "dimension_gates", []) or []):
            try:
                gate.destroy()
            except Exception:
                pass
        self.dimension_gates = []
        if _dimension_gate is None:
            return []
        for spec in NAMED_REGION_BOT_MAP[:int(MAX_NAMED_REGION_BOTS)]:
            title = str((spec.get("gate") or {}).get("title", "") or "")
            if not title:
                continue
            try:
                x, y, z, heading = self.dimension_gate_placement(spec)
                gate = _dimension_gate.DimensionGate(self.world_root, title, (x, y, z), heading, self.ring_ground_gsg())
                gate.root.setPythonTag("dimension_gate_guide", str(spec.get("name", "")))
                self.dimension_gates.append(gate)
            except Exception as exc:
                print(f"dimension_gate_build_failed title={title} err={exc.__class__.__name__}:{exc}")
        return self.dimension_gates

    def update_dimension_gates(self, dt: float):
        del dt
        gates = list(getattr(self, "dimension_gates", []) or [])
        if not gates:
            return None
        elapsed = float(getattr(self, "elapsed", 0.0) or 0.0)
        player = (float(self.player_pos.x), float(self.player_pos.y))
        for gate in gates:
            gate.update(elapsed, player)
        return len(gates)

    def update_named_region_bots(self, dt: float):
        del dt
        elapsed = float(getattr(self, "elapsed", 0.0) or 0.0)
        for idx, node in enumerate(list(getattr(self, "named_region_bot_nodes", []) or [])):
            try:
                if node is None or node.isEmpty():
                    continue
                if bool(node.getPythonTag("named_region_bot_paused")) or node.getPythonTag("named_region_bot_character"):
                    continue
                base_x = float(node.getPythonTag("named_region_bot_base_x") or node.getX())
                base_y = float(node.getPythonTag("named_region_bot_base_y") or node.getY())
                base_z = float(node.getPythonTag("named_region_bot_base_z") or node.getZ())
                phase = float(node.getPythonTag("named_region_bot_phase") or 0.0)
                amp = float(NAMED_REGION_BOT_HOVER_AMPLITUDE)
                bob = math.sin(elapsed * float(NAMED_REGION_BOT_HOVER_SPEED) + phase) * amp
                wander_radius = max(0.0, float(node.getPythonTag("named_region_bot_wander_radius") or 0.0))
                wander_speed = max(0.0, float(node.getPythonTag("named_region_bot_wander_speed") or 0.0))
                activity_flag = str(node.getPythonTag("named_region_bot_activity_flag") or "").strip()
                activity_active = bool(activity_flag and getattr(self, activity_flag, False))
                previous = Vec3(node.getPos())
                if wander_radius > 0.0 and wander_speed > 0.0 and not activity_active:
                    # Every guide gets a restrained patrol around its authored anchor.
                    # The owning activity freezes that patrol so a race, battle, forge,
                    # selector, etc. cannot have its guide drifting out from under it.
                    orbit = elapsed * wander_speed + phase
                    x = base_x + math.cos(orbit) * wander_radius * 0.74
                    y = base_y + math.sin(orbit * 0.72 + phase * 0.41) * wander_radius * 0.56
                    kind = str(node.getPythonTag("named_region_bot_kind") or "").lower()
                    if kind != "space":
                        try:
                            base_z = self.world_height_at(x, y) + 10.5
                        except Exception:
                            pass
                    node.setPos(x, y, base_z + bob)
                else:
                    node.setZ(base_z + bob)
                moved = Vec3(node.getPos() - previous)
                if moved.lengthSquared() > 0.0004 and not activity_active:
                    node.setH(math.degrees(math.atan2(-float(moved.x), float(moved.y))))
                elif not activity_active:
                    node.setH((elapsed * 2.0 + phase * 17.0 + idx * 7.0) % 360.0)
                # Keep Pass 21 arrival chevrons aligned to the world corridor even
                # while the bot itself performs its inherited idle rotation.
                try:
                    guide_signal = node.getPythonTag("named_region_bot_wayfinding")
                    if guide_signal is not None and not guide_signal.isEmpty():
                        guide_signal.setH(-float(node.getH()))
                except Exception:
                    pass
            except Exception:
                continue

    def _active_named_region_bot_nodes(self) -> list:
        out = []
        for node in list(getattr(self, "named_region_bot_nodes", []) or []):
            try:
                if node is not None and not node.isEmpty():
                    out.append(node)
            except Exception:
                pass
        return out

    def _biome_point_at(self, radius: float, angle: float, z_offset: float = 0.12) -> Vec3:
        x = math.cos(angle) * float(radius)
        y = math.sin(angle) * float(radius)
        return Vec3(x, y, self.world_height_at(x, y) + float(z_offset))

    def _angle_delta(self, a: float, b: float) -> float:
        return abs((float(a) - float(b) + math.pi) % math.tau - math.pi)

    def _smootherstep(self, value: float) -> float:
        t = clamp(float(value), 0.0, 1.0)
        return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)

    def biome_corridor_weight_at(self, angle: float, lane_half_width: float = 0.060) -> float:
        # 0 = off corridor, 1 = corridor center.  Used for both visuals and
        # height easing so the routes read as real traversable landforms.
        best = 0.0
        lane_half_width = max(0.010, float(lane_half_width))
        for deg in BIOME_CORRIDOR_DEGREES:
            d = self._angle_delta(float(angle), math.radians(float(deg)))
            if d < lane_half_width:
                best = max(best, 1.0 - self._smootherstep(d / lane_half_width))
        return clamp(best, 0.0, 1.0)

    def build_biome_traversal_corridors(self):
        # Pass 33: four long, readable routes through the ring world.  These
        # are not separate roads; they are guide-lines that sit on the actual
        # terrain profile so hills/depths still connect visually.
        floor_z = self.hub_ground_level()
        center_color = hsv_color((self.cfg.line_hue + 0.50) % 1.0, 0.82, 1.0, 0.58)
        edge_color = hsv_color((self.cfg.line_hue + 0.44) % 1.0, 0.66, 0.92, 0.32)
        node_color = hsv_color((self.cfg.line_hue + 0.58) % 1.0, 0.72, 1.0, 0.52)
        center_lines = []
        edge_lines = []
        cross_lines = []
        start_r = self.hub_radius + 3.0
        # Pass 282.52: the Metropolis street grid carries the routes inside the city.
        end_r = self.map_line_outer_radius()
        samples = 124
        for deg in BIOME_CORRIDOR_DEGREES:
            ang = math.radians(float(deg))
            for side in (-1.0, 1.0):
                edge_ang = ang + side * 0.030
                pts = []
                for idx in range(samples + 1):
                    radius = lerp(start_r, end_r, idx / float(samples))
                    pts.append(self._biome_point_at(radius, edge_ang, 0.20))
                edge_lines.append(pts)
            pts = []
            for idx in range(samples + 1):
                radius = lerp(start_r, end_r, idx / float(samples))
                pts.append(self._biome_point_at(radius, ang, 0.26))
            center_lines.append(pts)
            # Transition gates at every biome seam prove the route returns to
            # the common floor level before entering the next ring.
            for ring in BIOME_RINGS[1:]:
                for radius in (float(ring["r0"]),):
                    width = 13.0 if int(ring["key"]) < 7 else 18.0
                    tangent = Vec3(-math.sin(ang), math.cos(ang), 0.0)
                    base = Vec3(math.cos(ang) * radius, math.sin(ang) * radius, floor_z + 0.30)
                    cross_lines.append([base - tangent * width, base + tangent * width])
        self.add_polyline_batch(self.line_root, edge_lines, edge_color, self.cfg.line_thickness * 0.48, False, "biome-corridor-edge-guides")
        self.add_polyline_batch(self.accent_root, center_lines, center_color, self.cfg.line_thickness * 0.96, False, "biome-corridor-center-guides")
        self.add_polyline_batch(self.accent_root, cross_lines, node_color, self.cfg.line_thickness * 0.80, False, "biome-corridor-seam-gates")

    def build_biome_route_beacons(self):
        # Pass 34: line-only route markers.  These are terrain/navigation
        # beacons, not prop meshes. They tell the player what region they are
        # approaching while keeping the world readable from ground level.
        floor_z = self.hub_ground_level()
        beacon_color = hsv_color((self.cfg.line_hue + 0.54) % 1.0, 0.84, 1.0, 0.62)
        label_color = hsv_color((self.cfg.line_hue + 0.58) % 1.0, 0.50, 1.0, 0.92)
        ring_color = hsv_color((self.cfg.line_hue + 0.62) % 1.0, 0.70, 1.0, 0.34)
        vertical_segments = []
        cap_polys = []
        gate_polys = []
        for ring in BIOME_RINGS[1:]:
            ring_key = int(ring["key"])
            mid_r = (float(ring["r0"]) + float(ring["r1"])) * 0.5
            height = 5.8 if ring_key < 7 else 8.4
            half_gate = 10.0 if ring_key < 7 else 15.0
            for deg in BIOME_CORRIDOR_DEGREES:
                ang = math.radians(float(deg))
                tangent = Vec3(-math.sin(ang), math.cos(ang), 0.0)
                radial = Vec3(math.cos(ang), math.sin(ang), 0.0)
                base_xy = radial * mid_r
                ground = self.world_height_at(base_xy.x, base_xy.y)
                base = Vec3(base_xy.x, base_xy.y, ground + 0.28)
                top = Vec3(base_xy.x, base_xy.y, ground + height)
                vertical_segments.append((base, top))
                cap = []
                for i in range(8):
                    a = math.tau * i / 8.0
                    cap.append(Vec3(base.x + math.cos(a) * half_gate * 0.30, base.y + math.sin(a) * half_gate * 0.30, top.z))
                cap_polys.append(cap)
                # Entry gate exactly on the inner seam, held at shared floor.
                seam_r = float(ring["r0"])
                seam = radial * seam_r
                gate_center = Vec3(seam.x, seam.y, floor_z + 0.38)
                gate_polys.append([
                    gate_center - tangent * half_gate,
                    gate_center + tangent * half_gate,
                    gate_center + tangent * half_gate + Vec3(0, 0, height * 0.42),
                    gate_center - tangent * half_gate + Vec3(0, 0, height * 0.42),
                ])
            # Pass 56: route sign text removed. Navigation remains through gates/lines only.
        self.add_line_segments(self.accent_root, vertical_segments, beacon_color, self.cfg.line_thickness * 0.82, "biome-route-beacon-posts")
        self.add_polyline_batch(self.accent_root, cap_polys, beacon_color, self.cfg.line_thickness * 0.64, True, "biome-route-beacon-caps")
        self.add_polyline_batch(self.line_root, gate_polys, ring_color, self.cfg.line_thickness * 0.58, True, "biome-route-entry-gates")

    def build_biome_profile_guides(self):
        # Pass 32: continuous ribs prove that ring terrain is connected terrain,
        # not a stack of disconnected shapes.  The ribs follow actual height.
        profile_color = hsv_color((self.cfg.line_hue + 0.27) % 1.0, 0.76, 1.0, 0.42)
        seam_color = hsv_color((self.cfg.line_hue + 0.35) % 1.0, 0.70, 1.0, 0.34)
        contour_color = hsv_color((self.cfg.line_hue + 0.21) % 1.0, 0.58, 0.92, 0.24)
        anchor_color = hsv_color((self.cfg.line_hue + 0.48) % 1.0, 0.84, 1.0, 0.70)
        floor_z = self.hub_ground_level()

        # Long terrain ribs across all rings. These are always visible map-grade
        # curves, so the player can read where terrain rises, dips, then returns.
        ribs = []
        start_r = self.hub_radius + 8.0
        end_r = self.map_line_outer_radius()
        samples = 96
        for deg in BIOME_PROFILE_GUIDE_DEGREES:
            ang = math.radians(float(deg))
            pts = []
            for idx in range(samples + 1):
                radius = lerp(start_r, end_r, idx / float(samples))
                pts.append(self._biome_point_at(radius, ang, 0.18))
            ribs.append(pts)
        self.add_polyline_batch(self.line_root, ribs, profile_color, self.cfg.line_thickness * 0.72, False, "biome-continuous-profile-ribs")

        # Ring-local contours use real height but remain lightweight. They make
        # each biome look like one shaped annular terrain field.
        contour_polys = []
        seam_polys = []
        for ring in BIOME_RINGS:
            r0 = float(ring["r0"])
            r1 = float(ring["r1"])
            if int(ring["key"]) > 1:
                for radius in (r0, r1):
                    pts = []
                    for i in range(192):
                        ang = math.tau * i / 192.0
                        pts.append(Vec3(math.cos(ang) * radius, math.sin(ang) * radius, floor_z + 0.165))
                    seam_polys.append(pts)
            for t in BIOME_CONTOUR_T_VALUES:
                radius = lerp(r0, r1, float(t))
                pts = []
                for i in range(192):
                    ang = math.tau * i / 192.0
                    x = math.cos(ang) * radius
                    y = math.sin(ang) * radius
                    pts.append(Vec3(x, y, self.world_height_at(x, y) + 0.135))
                contour_polys.append(pts)
        self.add_polyline_batch(self.line_root, contour_polys, contour_color, self.cfg.line_thickness * 0.36, True, "biome-global-contour-bands")
        self.add_polyline_batch(self.line_root, seam_polys, seam_color, self.cfg.line_thickness * 0.88, True, "biome-ground-return-seams")

        # Development fast-travel pads: these are terrain markings, not props.
        # Pass 36 makes them safer/readable by giving each pad a larger landing
        # ring plus an inward/outward route mark. The outbound tick is longer so
        # a player arriving by number key knows which way continues the biome path.
        anchor_polys = []
        anchor_angle = math.radians(BIOME_ANCHOR_ANGLE_DEG)
        for ring in BIOME_RINGS:
            arrival, radius, anchor_angle = self.biome_arrival_point(ring)
            x = arrival.x
            y = arrival.y
            z = self.world_height_at(x, y) + 0.25
            ring_key = int(ring["key"])
            pad_r = 15.5 if ring_key < 7 else 21.0
            anchor_polys.append([Vec3(x + math.cos(math.tau * i / 16.0) * pad_r, y + math.sin(math.tau * i / 16.0) * pad_r, z) for i in range(16)])
            anchor_polys.append([Vec3(x + math.cos(math.tau * i / 4.0 + math.radians(45.0)) * (pad_r * 0.72), y + math.sin(math.tau * i / 4.0 + math.radians(45.0)) * (pad_r * 0.72), z + 0.02) for i in range(4)])
            # Short inward tick, longer outward tick.
            inward_r = max(float(ring["r0"]) + 4.0, radius - 34.0)
            outward_r = min(float(ring["r1"]) - 4.0, radius + max(82.0, min(180.0, (float(ring["r1"]) - float(ring["r0"])) * 0.18)))
            anchor_polys.append([self._biome_point_at(inward_r, anchor_angle, 0.27), self._biome_point_at(radius, anchor_angle, 0.27)])
            anchor_polys.append([self._biome_point_at(radius, anchor_angle, 0.31), self._biome_point_at(outward_r, anchor_angle, 0.31)])
            # Outward chevron at the forward end.
            tip = self._biome_point_at(outward_r, anchor_angle, 0.36)
            tangent = Vec3(-math.sin(anchor_angle), math.cos(anchor_angle), 0.0)
            back = self._biome_point_at(max(float(ring["r0"]) + 4.0, outward_r - 34.0), anchor_angle, 0.34)
            anchor_polys.append([back + tangent * (pad_r * 0.42), tip, back - tangent * (pad_r * 0.42)])
        self.add_polyline_batch(self.accent_root, anchor_polys, anchor_color, self.cfg.line_thickness * 1.04, True, "biome-safe-arrival-anchor-pads")

    def biome_arrival_point(self, ring):
        # Safe arrival is always on the south radial corridor, halfway through the
        # ring. The corridor easing keeps the landing area readable and low-slope.
        radius = (float(ring["r0"]) + float(ring["r1"])) * 0.5
        angle = math.radians(BIOME_ANCHOR_ANGLE_DEG)
        x = math.cos(angle) * radius
        y = math.sin(angle) * radius
        ground_z = self.world_height_at(x, y)
        if str(ring.get("kind", "")) == "water":
            # Pass 56: arrive on the ocean craft surface, not below an old terrain floor.
            craft_z = self.deep_water_craft_eye_z(x, y, ring)
            return Vec3(x, y, craft_z), radius, angle
        return Vec3(x, y, self.cfg.player_eye_height + ground_z), radius, angle

    def biome_outward_focus_point(self, ring, radius: float, angle: float):
        span = max(1.0, float(ring["r1"]) - float(ring["r0"]))
        focus_r = min(float(ring["r1"]) - 8.0, float(radius) + max(160.0, min(420.0, span * 0.22)))
        focus_r = max(float(ring["r0"]) + 8.0, focus_r)
        x = math.cos(angle) * focus_r
        y = math.sin(angle) * focus_r
        return Vec3(x, y, self.cfg.player_eye_height + self.world_height_at(x, y) + 2.2)

    def deep_water_mode_active(self, pos=None):
        spec = self.current_world_spec()
        kind = str(spec.get("kind", ""))
        if kind == "underwater":
            return True
        # The current hub-only shell still uses the flatworld biome rings as the
        # playable overworld.  Do not require a separate flatworld WORLD_SPEC;
        # otherwise the Retired Ocean ring is visible but never enters swim mode.
        if kind not in ("flatworld", "hub"):
            return False
        pos = pos if pos is not None else self.player_pos
        ring = self.biome_ring_for_radius(math.sqrt(pos.x * pos.x + pos.y * pos.y))
        return ring is not None and str(ring.get("kind", "")) == "water"

    def deep_water_surface_level(self, x=None, y=None, ring=None):
        ring = ring if ring is not None else (self.biome_ring_for_radius(math.sqrt(x * x + y * y)) if x is not None and y is not None else None)
        # Pass 84: hard remove above-terrain water.  The playable water biome
        # can still trigger craft/fog behavior, but no visible water plane,
        # slab, ribbon, or volume is allowed above the terrain line.
        del x, y, ring
        return self.hub_ground_level() - 1.85

    def deep_water_wave_height(self, radius: float, angle: float, ring=None, elapsed=None):
        # Pass 84: no surface waves above terrain.  Keep this stable below the
        # terrain line so any caller that still asks for water height cannot
        # resurrect floating water chunks.
        del radius, angle, ring, elapsed
        return self.hub_ground_level() - 1.85

    def deep_water_craft_eye_z(self, x=None, y=None, ring=None):
        ring = ring if ring is not None else (self.biome_ring_for_radius(math.sqrt(x * x + y * y)) if x is not None and y is not None else None)
        radius = math.sqrt(float(x or 0.0) * float(x or 0.0) + float(y or 0.0) * float(y or 0.0)) if x is not None and y is not None else ((float(ring["r0"]) + float(ring["r1"])) * 0.5 if ring is not None else 0.0)
        angle = math.atan2(float(y or 0.0), float(x or 0.0)) if x is not None and y is not None else math.radians(BIOME_ANCHOR_ANGLE_DEG)
        wave_z = self.deep_water_wave_height(radius, angle, ring)
        bob = math.sin(self.elapsed * 1.35 + angle * 1.8) * float(DEEP_WATER_CRAFT_VERTICAL_BOB)
        return wave_z + float(DEEP_WATER_CRAFT_EYE_OFFSET) + bob

    def deep_water_depth_factor(self, pos=None):
        # Pass 56: this is now a water-region immersion factor rather than a
        # literal player-under-surface depth. While the craft is in Retired Ocean,
        # the whole view gets full blue fog/tint and non-water regions are hidden.
        return 1.0 if self.deep_water_mode_active(pos) else 0.0

    def deep_water_bounds(self, x: float, y: float, ring=None):
        # Pass 84: force the water volume band below terrain.  Nothing that uses
        # these bounds should appear above the shared ground line anymore.
        del x, y, ring
        ground = self.hub_ground_level()
        return ground - 2.60, ground - 0.18

    def build_deep_water_surface_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        # Pass 84: absolutely no visible above-terrain water.  This function is
        # intentionally a no-op placeholder so old callers keep working while
        # water planes/ribbons/ripples stop rendering.
        del ring, a0, a1
        node = parent.attachNewNode(f"deep-water-surface-disabled-{sector_idx:02d}")
        node.hide()
        node.setPythonTag("water_surface_line_count", 0)
        node.setPythonTag("deep_water_surface_disabled", 1)
        node.setPythonTag("no_above_terrain_water", 1)
        return node

    def build_deep_water_creature_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        if bool(globals().get("DEEP_WATER_LITE_MODE", True)) and not bool(globals().get("DEEP_WATER_ENABLE_CREATURES", False)):
            return 0
        palette = [
            ((0.22, 0.98, 1.00, 0.88), (0.08, 0.56, 0.72, 0.36)),
            ((0.64, 1.00, 0.90, 0.88), (0.18, 0.48, 0.38, 0.32)),
            ((1.00, 0.54, 0.86, 0.90), (0.52, 0.18, 0.40, 0.30)),
            ((0.90, 0.82, 0.24, 0.84), (0.44, 0.36, 0.08, 0.28)),
            ((0.64, 0.78, 1.00, 0.90), (0.24, 0.30, 0.56, 0.32)),
        ]
        styles = ("jelly", "shoal", "ray")
        created = 0
        span = max(1.0, float(ring["r1"]) - float(ring["r0"]))
        for idx, t in enumerate((0.14, 0.22, 0.31, 0.40, 0.50, 0.59, 0.68, 0.77, 0.86)):
            u = ((sector_idx * 0.173) + idx * 0.19) % 1.0
            ang = lerp(a0 + 0.10, a1 - 0.10, u)
            radius = lerp(float(ring["r0"]) + span * 0.05, float(ring["r1"]) - span * 0.05, t)
            x = math.cos(ang) * radius
            y = math.sin(ang) * radius
            bottom_z, top_z = self.deep_water_bounds(x, y, ring)
            if top_z - bottom_z < 0.8:
                continue
            lane_clear = self.biome_corridor_weight_at(ang, lane_half_width=0.050)
            if lane_clear > 0.56:
                continue
            depth = lerp(0.32, 0.82, ((idx * 0.31 + sector_idx * 0.07) % 1.0))
            z = lerp(top_z - 0.2, bottom_z + 0.3, depth)
            root = parent.attachNewNode(f"deep-creature-{sector_idx:02d}-{idx:02d}")
            primary, secondary = palette[(sector_idx + idx) % len(palette)]
            style = styles[(sector_idx + idx) % len(styles)]
            size = 1.9 + ((sector_idx + idx) % 4) * 0.42
            if style == "jelly":
                dome = [Vec3(math.cos(math.radians(a)) * size * 0.86, 0.0, math.sin(math.radians(a)) * size * 0.62) for a in range(180, -1, -20)]
                tentacles = []
                for off in (-0.62, -0.22, 0.22, 0.62):
                    tentacles.append([Vec3(off * size, 0.0, -0.10 * size), Vec3(off * size * 0.82, 0.0, -0.75 * size), Vec3(off * size * 0.58, 0.0, -1.36 * size)])
                self.add_polyline(root, dome, primary, self.cfg.line_thickness * 0.54, False, "deep-jelly-dome")
                self.add_polyline_batch(root, tentacles, secondary, self.cfg.line_thickness * 0.40, False, "deep-jelly-tentacles")
                halo = self.polygon_points(size * 0.95, size * 0.08, 10, 0.0)
                self.add_polyline(root, halo, secondary, self.cfg.line_thickness * 0.28, True, "deep-jelly-halo")
            elif style == "ray":
                outline = [Vec3(-size * 1.15, 0.0, 0.0), Vec3(-size * 0.24, 0.0, size * 0.50), Vec3(size * 1.05, 0.0, 0.0), Vec3(-size * 0.24, 0.0, -size * 0.50)]
                self.add_polyline(root, outline, primary, self.cfg.line_thickness * 0.58, True, "deep-ray-outline")
                self.add_polyline(root, [Vec3(-size * 0.85, 0.0, 0.0), Vec3(size * 0.72, 0.0, 0.0)], secondary, self.cfg.line_thickness * 0.32, False, "deep-ray-spine")
                self.add_polyline(root, [Vec3(-size * 1.04, 0.0, 0.0), Vec3(-size * 1.55, 0.0, 0.28 * size), Vec3(-size * 1.95, 0.0, -0.10 * size)], secondary, self.cfg.line_thickness * 0.26, False, "deep-ray-tail")
            else:
                body = [Vec3(-size, 0.0, 0.0), Vec3(-size * 0.18, 0.0, size * 0.42), Vec3(size * 0.92, 0.0, 0.0), Vec3(-size * 0.18, 0.0, -size * 0.42)]
                self.add_polyline(root, body, primary, self.cfg.line_thickness * 0.48, True, "deep-shoal-body")
                for fin in (-0.45, 0.0, 0.45):
                    self.add_polyline(root, [Vec3(-size * 0.12, 0.0, fin * size * 0.42), Vec3(-size * 0.46, 0.0, fin * size * 0.78)], secondary, self.cfg.line_thickness * 0.26, False, "deep-shoal-fin")
                self.add_polyline(root, [Vec3(-size, 0.0, 0.0), Vec3(-size * 1.34, 0.0, size * 0.34), Vec3(-size * 1.34, 0.0, -size * 0.34), Vec3(-size, 0.0, 0.0)], secondary, self.cfg.line_thickness * 0.22, False, "deep-shoal-tail")
            root.setPos(x, y, z)
            root.setH(math.degrees(ang) + 90.0)
            root.setP(-12.0 + math.sin(idx * 1.8 + sector_idx) * 8.0)
            root.setPythonTag("base_pos", Vec3(x, y, z))
            root.setPythonTag("phase", float((sector_idx + 1) * 0.61 + idx * 1.37))
            root.setPythonTag("bob_amp", 0.12 + ((sector_idx + idx) % 3) * 0.05)
            root.setPythonTag("swim_amp", 0.40 + ((sector_idx + idx) % 4) * 0.18)
            root.setPythonTag("spin_rate", 4.0 + ((sector_idx + idx) % 5) * 1.3)
            self.deep_water_creature_nodes.append(root)
            created += 1
        return created

    def build_deep_water_flora_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        if bool(globals().get("DEEP_WATER_LITE_MODE", True)) and not bool(globals().get("DEEP_WATER_ENABLE_FLORA", False)):
            return 0
        glow_palettes = [
            ((0.30, 0.96, 1.00, 0.86), (0.10, 0.42, 0.56, 0.24)),
            ((0.72, 1.00, 0.90, 0.84), (0.20, 0.44, 0.32, 0.22)),
            ((1.00, 0.58, 0.88, 0.86), (0.36, 0.14, 0.28, 0.20)),
            ((0.96, 0.84, 0.34, 0.82), (0.36, 0.28, 0.10, 0.20)),
        ]
        created = 0
        span = max(1.0, float(ring["r1"]) - float(ring["r0"]))
        for idx, t in enumerate((0.16, 0.28, 0.40, 0.54, 0.68, 0.82)):
            u = ((sector_idx * 0.117) + idx * 0.143) % 1.0
            ang = lerp(a0 + 0.07, a1 - 0.07, u)
            radius = lerp(float(ring["r0"]) + span * 0.03, float(ring["r1"]) - span * 0.03, t)
            if self.biome_corridor_weight_at(ang, lane_half_width=0.052) > 0.55:
                continue
            x = math.cos(ang) * radius
            y = math.sin(ang) * radius
            bottom_z, top_z = self.deep_water_bounds(x, y, ring)
            floor_z = bottom_z
            root = parent.attachNewNode(f"deep-flora-{sector_idx:02d}-{idx:02d}")
            root.setPos(x, y, floor_z + 0.10)
            root.setH(math.degrees(ang) + 90.0)
            bright, dim = glow_palettes[(sector_idx + idx) % len(glow_palettes)]
            height = 1.5 + ((sector_idx + idx) % 4) * 0.45
            width = 0.36 + ((sector_idx + idx) % 3) * 0.10
            self.add_polyline(root, [Vec3(0, 0, 0), Vec3(0, 0, height * 0.55), Vec3(0, 0, height)], dim, self.cfg.line_thickness * 0.30, False, "deep-flora-stalk")
            fronds = []
            for side in (-1, 1):
                fronds.append([Vec3(0, 0, height * 0.24), Vec3(side * width * 0.7, 0, height * 0.52), Vec3(side * width * 1.2, 0, height * 0.84)])
                fronds.append([Vec3(0, 0, height * 0.42), Vec3(side * width * 0.5, 0, height * 0.72), Vec3(side * width * 0.95, 0, height * 1.05)])
            self.add_polyline_batch(root, fronds, bright, self.cfg.line_thickness * 0.26, False, "deep-flora-fronds")
            crown = self.polygon_points(width * 1.05, width * 0.72, 8, 0.0)
            crown = [Vec3(p.x, p.y, p.z + height * 1.06) for p in crown]
            self.add_polyline(root, crown, bright, self.cfg.line_thickness * 0.22, True, "deep-flora-crown")
            ring_pts = self.polygon_points(width * 0.82, width * 0.44, 10, 0.0)
            self.add_polyline(root, ring_pts, dim, self.cfg.line_thickness * 0.18, True, "deep-flora-base")
            root.setPythonTag("glow_phase", float((sector_idx + 1) * 0.53 + idx * 1.21))
            root.setPythonTag("sway_phase", float((sector_idx + 1) * 0.34 + idx * 0.77))
            root.setPythonTag("sway_amp", 3.5 + ((sector_idx + idx) % 3) * 1.2)
            self.deep_water_glow_nodes.append(root)
            created += 1
        return created

    def build_deep_water_feature_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        if bool(globals().get("DEEP_WATER_LITE_MODE", True)) and not bool(globals().get("DEEP_WATER_ENABLE_FEATURES", False)):
            return {"features": 0, "hero": 0, "coral": 0, "bubble": 0}
        counts = {"features": 0, "hero": 0, "coral": 0, "bubble": 0}
        span = max(1.0, float(ring["r1"]) - float(ring["r0"]))
        coral_palettes = [
            ((0.98, 0.56, 0.86, 0.82), (0.42, 0.16, 0.30, 0.26)),
            ((0.28, 0.96, 1.00, 0.82), (0.08, 0.40, 0.50, 0.24)),
            ((0.92, 0.86, 0.34, 0.80), (0.34, 0.26, 0.08, 0.22)),
        ]
        # Two sparse coral landmarks per sector.
        for idx, t in enumerate((0.24, 0.72)):
            u = ((sector_idx * 0.211) + idx * 0.37) % 1.0
            ang = lerp(a0 + 0.08, a1 - 0.08, u)
            if self.biome_corridor_weight_at(ang, lane_half_width=0.052) > 0.56:
                continue
            radius = lerp(float(ring["r0"]) + span * 0.06, float(ring["r1"]) - span * 0.06, t)
            x = math.cos(ang) * radius
            y = math.sin(ang) * radius
            bottom_z, top_z = self.deep_water_bounds(x, y, ring)
            floor_z = bottom_z
            root = parent.attachNewNode(f"deep-feature-coral-{sector_idx:02d}-{idx:02d}")
            root.setPos(x, y, floor_z + 0.12)
            root.setH(math.degrees(ang) + 90.0)
            bright, dim = coral_palettes[(sector_idx + idx) % len(coral_palettes)]
            height = 2.4 + ((sector_idx + idx) % 3) * 0.55
            width = 0.55 + ((sector_idx + idx) % 4) * 0.12
            stems = []
            for side in (-1, 0, 1):
                bend = side * width * 0.46
                stems.append([Vec3(0.0, 0.0, 0.0), Vec3(bend * 0.35, 0.0, height * 0.42), Vec3(bend, 0.0, height)])
            self.add_polyline_batch(root, stems, bright, self.cfg.line_thickness * 0.28, False, "deep-feature-coral-stems")
            frills = []
            for side in (-1, 1):
                frills.append([Vec3(0, 0, height * 0.44), Vec3(side * width * 0.62, 0.0, height * 0.72), Vec3(side * width * 1.08, 0.0, height * 0.90)])
                frills.append([Vec3(0, 0, height * 0.66), Vec3(side * width * 0.46, 0.0, height * 0.94), Vec3(side * width * 0.78, 0.0, height * 1.12)])
            self.add_polyline_batch(root, frills, dim, self.cfg.line_thickness * 0.20, False, "deep-feature-coral-frills")
            crown = [Vec3(math.cos(math.radians(a)) * width * 0.90, 0.0, height + math.sin(math.radians(a)) * width * 0.34) for a in range(180, -1, -24)]
            self.add_polyline(root, crown, bright, self.cfg.line_thickness * 0.18, False, "deep-feature-coral-crown")
            root.setPythonTag("feature_kind", "coral")
            root.setPythonTag("base_pos", Vec3(x, y, floor_z + 0.12))
            root.setPythonTag("glow_phase", float((sector_idx + 1) * 0.73 + idx * 1.14))
            root.setPythonTag("sway_phase", float((sector_idx + 1) * 0.31 + idx * 0.67))
            root.setPythonTag("sway_amp", 4.0 + idx * 1.4)
            self.deep_water_feature_nodes.append(root)
            counts["features"] += 1
            counts["coral"] += 1
        # One vent every other sector.
        if sector_idx % 2 == 0:
            ang = lerp(a0 + 0.14, a1 - 0.14, 0.52)
            if self.biome_corridor_weight_at(ang, lane_half_width=0.052) <= 0.58:
                radius = lerp(float(ring["r0"]) + span * 0.12, float(ring["r1"]) - span * 0.12, 0.44)
                x = math.cos(ang) * radius
                y = math.sin(ang) * radius
                bottom_z, top_z = self.deep_water_bounds(x, y, ring)
                floor_z = bottom_z
                root = parent.attachNewNode(f"deep-feature-bubble-{sector_idx:02d}")
                root.setPos(x, y, floor_z + 0.10)
                stem_color = (0.18, 0.72, 0.86, 0.28)
                bubble_color = (0.72, 0.98, 1.00, 0.72)
                vent_h = 3.3 + (sector_idx % 3) * 0.4
                self.add_polyline(root, [Vec3(0, 0, 0), Vec3(0, 0, vent_h)], stem_color, self.cfg.line_thickness * 0.14, False, "deep-feature-bubble-stem")
                for bi, bz in enumerate((0.7, 1.8, 2.9)):
                    bubble = self.polygon_points(0.18 + bi * 0.04, 0.18 + bi * 0.04, 8, 0.0)
                    bubble = [Vec3(p.x, p.y, p.z + bz) for p in bubble]
                    self.add_polyline(root, bubble, bubble_color, self.cfg.line_thickness * 0.12, True, f"deep-feature-bubble-{bi}")
                root.setPythonTag("feature_kind", "bubble")
                root.setPythonTag("base_pos", Vec3(x, y, floor_z + 0.10))
                root.setPythonTag("phase", float((sector_idx + 1) * 0.88))
                root.setPythonTag("vent_height", vent_h)
                self.deep_water_feature_nodes.append(root)
                counts["features"] += 1
                counts["bubble"] += 1
        # A single large hero creature every third sector.
        if sector_idx % 3 == 0:
            ang = lerp(a0 + 0.12, a1 - 0.12, 0.74)
            if self.biome_corridor_weight_at(ang, lane_half_width=0.052) <= 0.58:
                radius = lerp(float(ring["r0"]) + span * 0.10, float(ring["r1"]) - span * 0.10, 0.62)
                x = math.cos(ang) * radius
                y = math.sin(ang) * radius
                bottom_z, top_z = self.deep_water_bounds(x, y, ring)
                z = lerp(top_z - 0.32, bottom_z + 0.48, 0.46)
                root = parent.attachNewNode(f"deep-feature-hero-{sector_idx:02d}")
                size = 4.8 + (sector_idx % 2) * 0.7
                hero_color = (0.62, 0.92, 1.00, 0.76)
                accent = (0.18, 0.46, 0.60, 0.24)
                body = [Vec3(-size * 1.05, 0.0, 0.0), Vec3(-size * 0.38, 0.0, size * 0.36), Vec3(size * 0.82, 0.0, size * 0.18), Vec3(size * 1.22, 0.0, 0.0), Vec3(size * 0.84, 0.0, -size * 0.18), Vec3(-size * 0.42, 0.0, -size * 0.32)]
                self.add_polyline(root, body, hero_color, self.cfg.line_thickness * 0.34, True, "deep-feature-hero-body")
                self.add_polyline(root, [Vec3(-size * 1.02, 0.0, 0.0), Vec3(-size * 1.48, 0.0, size * 0.42), Vec3(-size * 1.48, 0.0, -size * 0.42), Vec3(-size * 1.02, 0.0, 0.0)], accent, self.cfg.line_thickness * 0.20, False, "deep-feature-hero-tail")
                self.add_polyline(root, [Vec3(0.0, 0.0, size * 0.12), Vec3(size * 0.22, 0.0, size * 0.52), Vec3(size * 0.58, 0.0, size * 0.26)], accent, self.cfg.line_thickness * 0.18, False, "deep-feature-hero-fin-top")
                self.add_polyline(root, [Vec3(-0.12 * size, 0.0, -size * 0.08), Vec3(size * 0.22, 0.0, -size * 0.48), Vec3(size * 0.56, 0.0, -size * 0.22)], accent, self.cfg.line_thickness * 0.18, False, "deep-feature-hero-fin-bottom")
                root.setPos(x, y, z)
                root.setH(math.degrees(ang) + 90.0)
                root.setPythonTag("feature_kind", "hero")
                root.setPythonTag("base_pos", Vec3(x, y, z))
                root.setPythonTag("phase", float((sector_idx + 1) * 0.52))
                root.setPythonTag("bob_amp", 0.18)
                root.setPythonTag("swim_amp", 0.52)
                self.deep_water_feature_nodes.append(root)
                counts["features"] += 1
                counts["hero"] += 1
        return counts

    def build_deep_water_sky_creature_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        if bool(globals().get("DEEP_WATER_LITE_MODE", True)) or int(DEEP_WATER_SKY_CREATURES_PER_CHUNK) <= 0:
            return 0
        # Airborne ocean life for the water ring: rays/jellies that hover above the open sea.
        created = 0
        span = max(1.0, float(ring["r1"]) - float(ring["r0"]))
        sky_color = (0.62, 0.98, 1.0, 0.72)
        wing_color = (0.18, 0.62, 0.88, 0.42)
        for idx in range(int(DEEP_WATER_SKY_CREATURES_PER_CHUNK)):
            u = ((sector_idx * 0.271) + idx * 0.237) % 1.0
            t = 0.18 + ((idx * 0.29 + sector_idx * 0.071) % 0.64)
            ang = lerp(a0 + 0.06, a1 - 0.06, u)
            if self.biome_corridor_weight_at(ang, lane_half_width=0.050) > 0.64:
                continue
            radius = lerp(float(ring["r0"]) + span * 0.04, float(ring["r1"]) - span * 0.04, t)
            x = math.cos(ang) * radius
            y = math.sin(ang) * radius
            surface_z = self.deep_water_wave_height(radius, ang, ring)
            z = surface_z + 20.0 + idx * 10.0 + (sector_idx % 5) * 2.2
            root = parent.attachNewNode(f"deep-water-sky-creature-{sector_idx:02d}-{idx:02d}")
            size = 5.6 + ((sector_idx + idx) % 4) * 1.25
            body = [Vec3(-size * 0.9, 0.0, 0.0), Vec3(-size * 0.1, 0.0, size * 0.35), Vec3(size * 1.0, 0.0, 0.0), Vec3(-size * 0.1, 0.0, -size * 0.35)]
            self.add_polyline(root, body, sky_color, self.cfg.line_thickness * 0.46, True, "water-sky-ray-body")
            self.add_polyline(root, [Vec3(-size * 0.80, 0, 0), Vec3(-size * 1.55, 0, size * 0.32), Vec3(-size * 1.92, 0, -size * 0.10)], wing_color, self.cfg.line_thickness * 0.30, False, "water-sky-ray-tail")
            self.add_polyline(root, [Vec3(-size * 0.18, 0, size * 0.22), Vec3(size * 0.18, 0, size * 0.62), Vec3(size * 0.48, 0, size * 0.24)], wing_color, self.cfg.line_thickness * 0.26, False, "water-sky-ray-wing-a")
            self.add_polyline(root, [Vec3(-size * 0.18, 0, -size * 0.22), Vec3(size * 0.18, 0, -size * 0.62), Vec3(size * 0.48, 0, -size * 0.24)], wing_color, self.cfg.line_thickness * 0.26, False, "water-sky-ray-wing-b")
            root.setPos(x, y, z)
            root.setH(math.degrees(ang) + 90.0)
            root.setPythonTag("base_pos", Vec3(x, y, z))
            root.setPythonTag("phase", float((sector_idx + 3) * 0.71 + idx * 1.31))
            root.setPythonTag("sky_amp", 4.0 + idx * 1.5)
            self.deep_water_sky_creature_nodes.append(root)
            created += 1
        return created

    def mini_biome_allowed(self, ring, sector_idx: int, salt: int = 0):
        kind = str((ring or {}).get("kind", ""))
        if kind in ("water", "urban", "metropolis", "ice"):
            return False
        hashed = (int(ring.get("key", 0)) * 16127 + int(sector_idx) * 31337 + int(salt) * 7919) & 0x7fffffff
        return (hashed % int(max(2, MINI_BIOME_DENSITY_DIVISOR))) in (1,)

    def build_jungle_oasis_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        kind = str(ring.get("kind", ""))
        if kind != "hills" or not self.mini_biome_allowed(ring, sector_idx, 3):
            return 0
        span = max(1.0, float(ring["r1"]) - float(ring["r0"]))
        center_u = 0.26 + ((sector_idx * 0.173) % 0.48)
        center_ang = lerp(a0 + 0.08, a1 - 0.08, center_u)
        center_r = lerp(float(ring["r0"]) + span * 0.18, float(ring["r1"]) - span * 0.18, 0.56 + 0.20 * math.sin(sector_idx * 1.9))
        cx = math.cos(center_ang) * center_r
        cy = math.sin(center_ang) * center_r
        cz = self.world_height_at(cx, cy) + 0.22
        oasis = parent.attachNewNode(f"mini-jungle-oasis-{sector_idx:02d}")
        oasis.setPythonTag("salvaged_artifact_oasis_kind", "verdant-canopy")
        vine = (0.12, 1.0, 0.42, 0.86)
        canopy = (0.38, 1.0, 0.30, 0.76)
        blossom = (1.0, 0.66, 0.94, 0.82)
        count = 0
        for idx, off in enumerate((-18.0, -8.0, 5.0, 17.0, 29.0)):
            angle = center_ang + 0.010 * off
            rr = center_r + off * 2.4
            x = math.cos(angle) * rr
            y = math.sin(angle) * rr
            z = self.world_height_at(x, y)
            h = 18.0 + (idx % 3) * 7.0
            p = Vec3(x, y, z)
            trunk = []
            for step in range(5):
                f = step / 4.0
                bend = math.sin(f * math.pi + idx) * 1.8
                trunk.append(Vec3(p.x + math.cos(angle + math.pi * 0.5) * bend, p.y + math.sin(angle + math.pi * 0.5) * bend, p.z + h * f))
            self.add_polyline(oasis, trunk, vine, self.cfg.line_thickness * 0.52, False, "jungle-oasis-vine-trunk")
            crown_z = z + h
            crown = []
            for i in range(10):
                aa = math.tau * i / 10.0
                crown.append(Vec3(x + math.cos(aa) * (5.0 + idx * 0.35), y + math.sin(aa) * (4.2 + idx * 0.25), crown_z + math.sin(aa * 2.0) * 0.9))
            self.add_polyline(oasis, crown, canopy, self.cfg.line_thickness * 0.40, True, "jungle-oasis-crown")
            if idx % 2 == 0:
                self.add_polyline(oasis, self.polygon_points(2.1 + idx * 0.2, crown_z + 1.2, 7, idx * 12.0), blossom, self.cfg.line_thickness * 0.34, True, "jungle-oasis-bloom")
            count += 1
        self.add_polyline(oasis, self.polygon_points(38.0, cz + 0.18, 18, 0.0), (0.40, 1.0, 0.58, 0.28), self.cfg.line_thickness * 0.38, True, "jungle-oasis-boundary")
        parent.setPythonTag("mini_jungle_oasis_count", count)
        return count

    def build_venus_oasis_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        if str(ring.get("kind", "")) != "desert" or not self.mini_biome_allowed(ring, sector_idx, 9):
            return 0
        span = max(1.0, float(ring["r1"]) - float(ring["r0"]))
        center_ang = lerp(a0 + 0.10, a1 - 0.10, 0.38 + ((sector_idx * 0.091) % 0.24))
        center_r = lerp(float(ring["r0"]) + span * 0.20, float(ring["r1"]) - span * 0.20, 0.62)
        center = Vec3(math.cos(center_ang) * center_r, math.sin(center_ang) * center_r, 0.0)
        center.z = self.world_height_at(center.x, center.y) + 0.26
        root = parent.attachNewNode(f"mini-venus-furnace-{sector_idx:02d}")
        root.setPythonTag("salvaged_artifact_oasis_kind", "venus-furnace")
        lava = (1.0, 0.34, 0.12, 0.88)
        hot = (1.0, 0.78, 0.24, 0.76)
        smoke = (0.72, 0.42, 0.28, 0.34)
        count = 0
        for idx, off in enumerate((-28.0, -11.0, 9.0, 25.0)):
            angle = center_ang + 0.015 * off
            rr = center_r + off * 2.0
            x = math.cos(angle) * rr
            y = math.sin(angle) * rr
            z = self.world_height_at(x, y) + 0.2
            tower_h = 10.0 + idx * 5.0
            self.add_polyline(root, [Vec3(x, y, z), Vec3(x + math.cos(angle) * 2.0, y + math.sin(angle) * 2.0, z + tower_h)], lava, self.cfg.line_thickness * 0.48, False, "venus-fumarole-spire")
            self.add_polyline(root, self.polygon_points(3.4 + idx * 0.7, z + tower_h, 9, idx * 8.0), hot, self.cfg.line_thickness * 0.34, True, "venus-fumarole-mouth")
            self.add_polyline(root, self.polygon_points(7.0 + idx * 2.1, z + 0.12, 10, idx * 11.0), smoke, self.cfg.line_thickness * 0.28, True, "venus-heat-ring")
            count += 1
        crack_lines = []
        for idx in range(9):
            aa = center_ang + (idx - 4) * 0.018
            r0 = center_r - 46.0 + idx * 5.0
            r1 = center_r + 52.0 - idx * 3.0
            p0 = Vec3(math.cos(aa) * r0, math.sin(aa) * r0, self.world_height_at(math.cos(aa) * r0, math.sin(aa) * r0) + 0.30)
            p1 = Vec3(math.cos(aa) * r1, math.sin(aa) * r1, self.world_height_at(math.cos(aa) * r1, math.sin(aa) * r1) + 0.32)
            crack_lines.append((p0, p1))
        self.add_line_segments(root, crack_lines, lava, self.cfg.line_thickness * 0.38, "venus-lava-cracks")
        parent.setPythonTag("mini_venus_oasis_count", count)
        return count

    def refresh_deep_water_surfaces(self, force=False):
        if not force and (self.elapsed - float(getattr(self, "deep_water_surface_refresh_time", -999.0))) < 0.10:
            return
        self.deep_water_surface_refresh_time = float(self.elapsed)
        for key, chunk in list((getattr(self, "terrain_chunks", {}) or {}).items()):
            if chunk is None or chunk.isEmpty():
                continue
            ring = self.biome_ring_for_key(key[0])
            if ring is None or str(ring.get("kind", "")) != "water":
                continue
            # Remove both pass83 lite ribbons and older pass56+ heavy water grids.
            for pattern in ("deep-water-surface-*", "deep-water-surface-lite-*", "deep-water-surface-disabled-*"):
                for old in list(chunk.findAllMatches(pattern)):
                    if old is not None and not old.isEmpty():
                        old.removeNode()
            if int(globals().get("DEEP_WATER_SURFACE_MAX_LINES_PER_CHUNK", 0) or 0) <= 0:
                chunk.setPythonTag("water_surface_line_count", 0)
                chunk.setPythonTag("deep_water_surface_disabled", 1)
                continue
            a0, a1 = self.biome_sector_angle_span(key[1], expanded=False)
            self.build_deep_water_surface_set(chunk, ring, key[1], a0, a1)

    def update_deep_water_life(self, dt: float):
        if self.deep_water_mode_active():
            self.current_water_depth = self.deep_water_depth_factor()
        else:
            self.current_water_depth = 0.0
        self.water_region_occlusion_active = False
        self.refresh_deep_water_surfaces(False)
        glowers = []
        for node in list(getattr(self, "deep_water_glow_nodes", []) or []):
            try:
                if node is None or node.isEmpty():
                    continue
                glow_phase = float(node.getPythonTag("glow_phase") or 0.0)
                sway_phase = float(node.getPythonTag("sway_phase") or 0.0)
                sway_amp = float(node.getPythonTag("sway_amp") or 4.0)
                node.setR(math.sin(self.elapsed * 0.62 + sway_phase) * sway_amp)
                pulse = 0.74 + 0.26 * (0.5 + 0.5 * math.sin(self.elapsed * 1.7 + glow_phase))
                node.setColorScale(pulse, pulse, pulse, 0.76 + 0.18 * pulse)
                glowers.append(node)
            except Exception:
                continue
        self.deep_water_glow_nodes = glowers
        feature_alive = []
        for node in list(getattr(self, "deep_water_feature_nodes", []) or []):
            try:
                if node is None or node.isEmpty():
                    continue
                kind = str(node.getPythonTag("feature_kind") or "")
                base = node.getPythonTag("base_pos") or Vec3(node.getPos())
                phase = float(node.getPythonTag("phase") or node.getPythonTag("glow_phase") or 0.0)
                if kind == "hero":
                    sway = math.sin(self.elapsed * 0.34 + phase) * float(node.getPythonTag("swim_amp") or 0.52)
                    drift = math.cos(self.elapsed * 0.27 + phase * 1.3) * 0.34
                    bob = math.sin(self.elapsed * 0.90 + phase) * float(node.getPythonTag("bob_amp") or 0.18)
                    node.setPos(base.x + sway, base.y + drift, base.z + bob)
                    node.setH(node.getH() + dt * 1.2)
                    glow = 0.78 + 0.18 * (0.5 + 0.5 * math.sin(self.elapsed * 0.9 + phase))
                    node.setColorScale(glow, glow, glow, 0.72 + 0.16 * glow)
                elif kind == "bubble":
                    rise = (0.5 + 0.5 * math.sin(self.elapsed * 1.15 + phase)) * 0.55
                    node.setPos(base.x, base.y, base.z + rise)
                    pulse = 0.82 + 0.18 * (0.5 + 0.5 * math.sin(self.elapsed * 1.9 + phase))
                    node.setColorScale(pulse, pulse, pulse, 0.58 + 0.18 * pulse)
                else:
                    sway_phase = float(node.getPythonTag("sway_phase") or phase)
                    sway_amp = float(node.getPythonTag("sway_amp") or 4.0)
                    node.setPos(base.x, base.y, base.z)
                    node.setR(math.sin(self.elapsed * 0.54 + sway_phase) * sway_amp)
                    pulse = 0.72 + 0.28 * (0.5 + 0.5 * math.sin(self.elapsed * 1.55 + phase))
                    node.setColorScale(pulse, pulse, pulse, 0.70 + 0.18 * pulse)
                feature_alive.append(node)
            except Exception:
                continue
        self.deep_water_feature_nodes = feature_alive
        alive = []
        for node in list(getattr(self, "deep_water_creature_nodes", []) or []):
            try:
                if node is None or node.isEmpty():
                    continue
                base = node.getPythonTag("base_pos") or Vec3(node.getPos())
                phase = float(node.getPythonTag("phase") or 0.0)
                bob_amp = float(node.getPythonTag("bob_amp") or 0.14)
                swim_amp = float(node.getPythonTag("swim_amp") or 0.40)
                spin_rate = float(node.getPythonTag("spin_rate") or 6.0)
                sway = math.sin(self.elapsed * 0.52 + phase) * swim_amp
                drift = math.cos(self.elapsed * 0.33 + phase * 1.3) * swim_amp * 0.55
                bob = math.sin(self.elapsed * 1.25 + phase * 0.9) * bob_amp
                node.setPos(base.x + sway, base.y + drift, base.z + bob)
                node.setH(node.getH() + dt * spin_rate)
                glow = 0.72 + 0.28 * (0.5 + 0.5 * math.sin(self.elapsed * 1.8 + phase * 2.1))
                node.setColorScale(glow, glow, glow, 0.72 + 0.22 * glow)
                alive.append(node)
            except Exception:
                continue
        self.deep_water_creature_nodes = alive
        sky_alive = []
        for node in list(getattr(self, "deep_water_sky_creature_nodes", []) or []):
            try:
                if node is None or node.isEmpty():
                    continue
                base = node.getPythonTag("base_pos") or Vec3(node.getPos())
                phase = float(node.getPythonTag("phase") or 0.0)
                amp = float(node.getPythonTag("sky_amp") or 4.0)
                glide = math.sin(self.elapsed * 0.35 + phase) * amp
                bob = math.sin(self.elapsed * 0.78 + phase * 1.4) * amp * 0.38
                node.setPos(base.x + glide, base.y + math.cos(self.elapsed * 0.29 + phase) * amp * 0.42, base.z + bob)
                node.setH(node.getH() + dt * (1.2 + (phase % 2.0)))
                pulse = 0.74 + 0.26 * (0.5 + 0.5 * math.sin(self.elapsed * 1.2 + phase))
                node.setColorScale(pulse, pulse, pulse, 0.66 + 0.18 * pulse)
                sky_alive.append(node)
            except Exception:
                continue
        self.deep_water_sky_creature_nodes = sky_alive

    def metropolis_district_profile(self, cx: int, cy: int):
        phase = math.sin(cx * 0.57 + cy * 0.91)
        alt_phase = math.cos(cx * 0.31 - cy * 0.47)
        selector = (phase + alt_phase) * 0.5
        if selector > 0.35:
            return {
                "name": "spire",
                "density": 0.88,
                "height_scale": 1.42,
                "hue": 0.62,
                "street_glow": 1.10,
                "accent": 0.82,
            }
        if selector > -0.05:
            return {
                "name": "commerce",
                "density": 0.78,
                "height_scale": 1.12,
                "hue": 0.70,
                "street_glow": 1.02,
                "accent": 0.74,
            }
        if selector > -0.42:
            return {
                "name": "garden-tech",
                "density": 0.64,
                "height_scale": 0.92,
                "hue": 0.54,
                "street_glow": 0.96,
                "accent": 0.66,
            }
        return {
            "name": "residential",
            "density": 0.70,
            "height_scale": 0.76,
            "hue": 0.80,
            "street_glow": 0.94,
            "accent": 0.58,
        }

    def metropolis_chunk_key_for_point(self, x: float, y: float):
        size = float(METROPOLIS_CHUNK_SIZE)
        return int(math.floor(float(x) / size)), int(math.floor(float(y) / size))

    def target_metropolis_chunk_keys(self):
        ring = self.biome_ring_for_key(8)
        if ring is None:
            return set()
        radius = math.sqrt(self.player_pos.x * self.player_pos.x + self.player_pos.y * self.player_pos.y)
        if radius < float(ring["r0"]) - 140.0:
            return set()
        cx, cy = self.metropolis_chunk_key_for_point(self.player_pos.x, self.player_pos.y)
        radius_cells = int(max(1, int(METROPOLIS_PRELOAD_RADIUS)))
        targets = set()
        for dx in range(-radius_cells, radius_cells + 1):
            for dy in range(-radius_cells, radius_cells + 1):
                candidate = (cx + dx, cy + dy)
                if self.metropolis_chunk_intersects_city_ring(candidate[0], candidate[1], ring):
                    targets.add(candidate)
        return targets

    def metropolis_chunk_intersects_city_ring(self, cx: int, cy: int, ring=None):
        ring = ring or self.biome_ring_for_key(8) or BIOME_RINGS[-1]
        size = float(METROPOLIS_CHUNK_SIZE)
        half = size * 0.5
        x0 = int(cx) * size
        y0 = int(cy) * size
        center_x = x0 + half
        center_y = y0 + half
        center_r = math.sqrt(center_x * center_x + center_y * center_y)
        half_diag = math.sqrt(2.0) * half
        # Reject chunks that are wholly inside the previous biome. Borderline
        # chunks stay because the city needs a stable entry seam.
        return (center_r + half_diag) >= (float(ring["r0"]) + float(METROPOLIS_INNER_CLEARANCE))

    def prune_metropolis_chunks_to_targets(self, targets):
        obstacles = getattr(self, "metropolis_obstacles", None)
        if isinstance(obstacles, dict):
            for key in list(obstacles.keys()):
                if key not in targets:
                    obstacles.pop(key, None)
        for key in list(self.metropolis_chunks.keys()):
            if key not in targets:
                try:
                    self.metropolis_chunks[key].removeNode()
                except Exception:
                    pass
                self.metropolis_chunks.pop(key, None)
        if len(self.metropolis_chunks) > MAX_METROPOLIS_CHUNKS:
            overflow = max(0, len(self.metropolis_chunks) - MAX_METROPOLIS_CHUNKS)
            for key in list(self.metropolis_chunks.keys())[:overflow]:
                try:
                    self.metropolis_chunks[key].removeNode()
                except Exception:
                    pass
                self.metropolis_chunks.pop(key, None)

    def metro_segment_allowed(self, p0: Vec3, p1: Vec3, min_radius: float):
        mid = (p0 + p1) * 0.5
        return math.sqrt(mid.x * mid.x + mid.y * mid.y) >= float(min_radius)

    def map_line_outer_radius(self) -> float:
        """Outer end of the hub-wide map guide lines.  Inside the Pass 282.52
        city the street grid carries the routes, so the lines stop at its edge;
        Pass 282.53 also keeps them off the war-torn Urban ring."""
        if self.urban_conflict_active():
            urban = self.biome_ring_for_key(7)
            if urban is not None:
                return float(urban["r0"])
        return float(METROPOLIS_INNER_RADIUS) if self.metropolis_city_active() else float(BIOME_OUTER_RADIUS)

    def metropolis_city_active(self) -> bool:
        if not METROPOLIS_CITY_ENABLED or _metro_city is None:
            return False
        return bool(getattr(getattr(self, "cfg", None), "metropolis_city_enabled", True))

    def build_metropolis_chunk(self, cx: int, cy: int):
        if self.metropolis_city_active():
            return self.build_metropolis_city_chunk(cx, cy)
        return self.build_metropolis_chunk_legacy(cx, cy)

    def build_metropolis_city_chunk(self, cx: int, cy: int):
        """Pass 282.52: lit, merged, collidable city chunk."""
        key = (int(cx), int(cy))
        if key in self.metropolis_chunks:
            return self.metropolis_chunks[key]
        ring = self.biome_ring_for_key(8) or BIOME_RINGS[-1]
        if not self.metropolis_chunk_intersects_city_ring(cx, cy, ring):
            self.metropolis_overlap_skip_count += 1
            return None
        r0 = float(ring["r0"])
        layout = _metro_layout.generate_chunk(int(cx), int(cy), r0, clear_fn=self.metropolis_named_bot_clearance_name)
        parent = self.world_root.attachNewNode(f"metropolis-city-{cx:+d}-{cy:+d}")
        parent.setPythonTag("metropolis_preloaded_chunk", 1)
        parent.setPythonTag("metropolis_generic_biome_overlap_removed", 1)
        parent.setPythonTag("metropolis_single_ground_surface_authority", 1)
        parent.setPythonTag("metropolis_city_pass28252", 1)
        gsg = self.ring_ground_gsg()
        ground, structures = _metro_city.build_chunk_nodes(parent, layout, r0, gsg)
        triangles = sum(int(n.getPythonTag("metro_triangles") or 0) for n in (ground, structures) if n is not None)

        district = layout.district
        facade, glass, window, accent, *_ = _metro_layout.DISTRICTS[district]
        size = float(_metro_layout.CHUNK_SIZE)
        x0 = cx * size
        y0 = cy * size
        inner_radius = r0 + float(METROPOLIS_INNER_CLEARANCE)
        lines = _metro_layout.street_lines_in_chunk(int(cx), int(cy))
        vehicle_count = 0
        for idx in range(int(METROPOLIS_VEHICLES_PER_CHUNK)):
            n = _metro_layout._hash01(cx, cy, idx, 41)
            axis, coord = lines[int(n * len(lines)) % len(lines)]
            mid = Vec3(x0 + size * 0.5, coord, 0.0) if axis == 0 else Vec3(coord, y0 + size * 0.5, 0.0)
            if math.hypot(mid.x, mid.y) < inner_radius:
                continue
            body_rgb = (0.20 + 0.50 * _metro_layout._hash01(cx, cy, idx, 43), 0.20 + 0.30 * _metro_layout._hash01(cx, cy, idx, 47), 0.26 + 0.40 * _metro_layout._hash01(cx, cy, idx, 53))
            root = parent.attachNewNode(f"metro-hover-{cx}-{cy}-{idx}")
            _metro_city.build_mover_node(root, f"metro-hover-body-{idx}", _metro_city.build_vehicle_mesh(body_rgb, accent), gsg, district)
            lane_offset = (2.6 if n < 0.5 else -2.6)
            root.setPythonTag("metro_kind", "vehicle")
            root.setPythonTag("axis", int(axis))
            root.setPythonTag("x_min", x0)
            root.setPythonTag("x_max", x0 + size)
            root.setPythonTag("y_min", y0)
            root.setPythonTag("y_max", y0 + size)
            root.setPythonTag("base_x", (x0 + size * n) if axis == 0 else coord + lane_offset)
            root.setPythonTag("base_y", (coord + lane_offset) if axis == 0 else (y0 + size * n))
            root.setPythonTag("alt", self.hub_ground_level() + 62.0 + 110.0 * _metro_layout._hash01(cx, cy, idx, 59))
            root.setPythonTag("speed", (26.0 + 30.0 * n) * (1.0 if n < 0.5 else -1.0))
            root.setPythonTag("phase", n * math.tau)
            root.setPythonTag("amp", 0.6)
            self.metropolis_hover_vehicle_nodes.append(root)
            vehicle_count += 1

        robot_count = 0
        for idx in range(int(METROPOLIS_ROBOTS_PER_CHUNK)):
            n = _metro_layout._hash01(cx, cy, idx, 61)
            # A loop around one block, flying above the street centre lines.
            lx = int(cx) * _metro_layout.LOTS_PER_CHUNK + int(n * _metro_layout.LOTS_PER_CHUNK)
            ly = int(cy) * _metro_layout.LOTS_PER_CHUNK + int(_metro_layout._hash01(cx, cy, idx, 67) * _metro_layout.LOTS_PER_CHUNK)
            bx0 = lx * _metro_layout.LOT_SIZE; by0 = ly * _metro_layout.LOT_SIZE
            bx1 = bx0 + _metro_layout.LOT_SIZE; by1 = by0 + _metro_layout.LOT_SIZE
            if math.hypot((bx0 + bx1) * 0.5, (by0 + by1) * 0.5) < inner_radius + 40.0:
                continue
            alt = self.hub_ground_level() + 7.0 + 9.0 * _metro_layout._hash01(cx, cy, idx, 71)
            route = [(bx0, by0, alt), (bx1, by0, alt + 1.0), (bx1, by1, alt), (bx0, by1, alt + 1.0)]
            if n < 0.5:
                route.reverse()
            root = parent.attachNewNode(f"metro-robot-{cx}-{cy}-{idx}")
            _metro_city.build_mover_node(root, f"metro-drone-{idx}", _metro_city.build_drone_mesh((0.70, 0.72, 0.78), accent), gsg, district)
            root.setPythonTag("metro_kind", "robot")
            root.setPythonTag("route_points", route)
            root.setPythonTag("speed", 0.10 + 0.08 * n)
            root.setPythonTag("phase", n * 4.0)
            self.metropolis_robot_nodes.append(root)
            robot_count += 1

        if not hasattr(self, "metropolis_obstacles") or not isinstance(getattr(self, "metropolis_obstacles", None), dict):
            self.metropolis_obstacles = {}
        self.metropolis_obstacles[key] = list(layout.obstacles)
        buildings = sum(1 for lot in layout.lots if lot.kind in ("tower", "spire", "slab", "residential"))
        parent.setPythonTag("metropolis_building_count", buildings)
        parent.setPythonTag("metropolis_vehicle_count", vehicle_count)
        parent.setPythonTag("metropolis_robot_count", robot_count)
        parent.setPythonTag("metropolis_skybridge_count", int(layout.bridges))
        parent.setPythonTag("metropolis_district_name", district)
        parent.setPythonTag("metropolis_obstacle_count", len(layout.obstacles))
        parent.setPythonTag("metropolis_triangles", int(triangles))
        parent.setPythonTag("metropolis_lot_kinds", ",".join(lot.kind for lot in layout.lots))
        self.metropolis_chunks[key] = parent
        return parent

    def metropolis_resolve_move(self, px: float, py: float, nx: float, ny: float, z=None, radius: float = 0.9):
        """Slide a move from (px, py) to (nx, ny) around Metropolis buildings.

        Returns (x, y, blocked).  Outside the city, or with the legacy city,
        the move is returned unchanged.
        """
        obstacles_by_chunk = getattr(self, "metropolis_obstacles", None)
        if not obstacles_by_chunk or not self.metropolis_city_active():
            return float(nx), float(ny), False
        ring = self.biome_ring_for_key(8)
        if ring is None or math.hypot(float(nx), float(ny)) < float(ring["r0"]):
            return float(nx), float(ny), False
        kx, ky = _metro_layout.chunk_key_for_point(nx, ny)
        nearby = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nearby.extend(obstacles_by_chunk.get((kx + dx, ky + dy), ()) or ())
        if not nearby:
            return float(nx), float(ny), False
        return _metro_layout.resolve_move(nearby, float(px), float(py), float(nx), float(ny), radius=radius, z=z)

    def build_metropolis_chunk_legacy(self, cx: int, cy: int):
        key = (int(cx), int(cy))
        if key in self.metropolis_chunks:
            return self.metropolis_chunks[key]
        size = float(METROPOLIS_CHUNK_SIZE)
        half = size * 0.5
        x0 = cx * size
        y0 = cy * size
        center = Vec3(x0 + half, y0 + half, 0.0)
        ring = self.biome_ring_for_key(8) or BIOME_RINGS[-1]
        if not self.metropolis_chunk_intersects_city_ring(cx, cy, ring):
            self.metropolis_overlap_skip_count += 1
            return None
        parent = self.world_root.attachNewNode(f"metropolis-city-{cx:+d}-{cy:+d}")
        parent.setPythonTag("metropolis_preloaded_chunk", 1)
        parent.setPythonTag("metropolis_generic_biome_overlap_removed", 1)
        profile = self.metropolis_district_profile(cx, cy)
        district_hue = float(profile["hue"])
        street_color = hsv_color((district_hue + 0.05) % 1.0, 0.32, profile["street_glow"], 0.48)
        line_color = hsv_color((district_hue + 0.08) % 1.0, 0.48, 1.0, 0.96)
        accent_color = hsv_color((district_hue + 0.18) % 1.0, 0.70, 1.0, 0.92)
        base_tower_color = hsv_color(district_hue % 1.0, 0.52, 1.0, 0.88)
        plaza_color = hsv_color((district_hue + 0.11) % 1.0, 0.24, 0.94, 0.34)
        lot_size = size / float(METROPOLIS_LOTS_PER_AXIS)
        # Pass 89: no duplicate solid Metropolis ground sheets here.
        # The single authoritative biome-fill sector already sits under the
        # street/grid layer. Extra rectangular sheets below it were invisible,
        # expensive, and a source of texture popping.
        parent.setPythonTag("metropolis_single_ground_surface_authority", 1)
        building_count = 0
        vehicle_count = 0
        robot_count = 0
        skybridge_count = 0
        ground_lines = []

        # Neater street lattice. Shared chunk-edge streets are suppressed so
        # adjacent city chunks do not draw identical lines on the same coords.
        inner_radius = float(ring["r0"]) + float(METROPOLIS_INNER_CLEARANCE)
        for i in range(1, METROPOLIS_LOTS_PER_AXIS):
            x = x0 + i * lot_size
            p0 = Vec3(x, y0, self.world_height_at(x, y0) + 0.12)
            p1 = Vec3(x, y0 + size, self.world_height_at(x, y0 + size) + 0.12)
            if self.metro_segment_allowed(p0, p1, inner_radius):
                ground_lines.append([p0, p1])
        for j in range(1, METROPOLIS_LOTS_PER_AXIS):
            y = y0 + j * lot_size
            p0 = Vec3(x0, y, self.world_height_at(x0, y) + 0.12)
            p1 = Vec3(x0 + size, y, self.world_height_at(x0 + size, y) + 0.12)
            if self.metro_segment_allowed(p0, p1, inner_radius):
                ground_lines.append([p0, p1])
        self.metropolis_duplicate_edge_suppression_count += 2 * (METROPOLIS_LOTS_PER_AXIS + 1)
        self.add_polyline_batch(parent, ground_lines, street_color, self.cfg.line_thickness * 0.50, False, f"metro-streets-{cx}-{cy}")

        # Pass 91: replace faded/transparent structure infill with one solid
        # child root. This keeps the city readable like the arena without a
        # chunk fade task or transparent parent layer.
        infill_parent = parent.attachNewNode("metropolis-solid-structure-root")
        infill_parent.setTransparency(TransparencyAttrib.MNone)
        infill_parent.setColorScale(1.0, 1.0, 1.0, 1.0)
        parent.setPythonTag("metropolis_solid_structure_root", 1)
        parent.setPythonTag("metropolis_infill_fade_active", 0)

        tower_entries = []
        # Structured lots with density-based occupancy.
        for ix in range(METROPOLIS_LOTS_PER_AXIS):
            for iy in range(METROPOLIS_LOTS_PER_AXIS):
                lot_cx = x0 + (ix + 0.5) * lot_size
                lot_cy = y0 + (iy + 0.5) * lot_size
                r = math.sqrt(lot_cx * lot_cx + lot_cy * lot_cy)
                if r < float(ring["r0"]) + 28.0:
                    continue
                clear_bot_name = self.metropolis_named_bot_clearance_name(lot_cx, lot_cy)
                if clear_bot_name:
                    pz = self.world_height_at(lot_cx, lot_cy) + 0.14
                    self.add_box(infill_parent, Vec3(lot_cx, lot_cy, pz + 0.06), Vec3(lot_size * 0.82, lot_size * 0.82, 0.12), plaza_color, 0.18)
                    parent.setPythonTag(f"metropolis_clear_plaza_{clear_bot_name.lower()}", 1)
                    continue
                hseed = math.sin((cx * 19 + ix * 7) * 12.9898 + (cy * 23 + iy * 11) * 78.233 + 3.91) * 43758.5453
                n = hseed - math.floor(hseed)
                if n > float(profile["density"]):
                    # Plaza/open block.
                    pz = self.world_height_at(lot_cx, lot_cy) + 0.14
                    self.add_box(infill_parent, Vec3(lot_cx, lot_cy, pz + 0.05), Vec3(lot_size * 0.76, lot_size * 0.76, 0.10), plaza_color, 0.16)
                    continue
                base_z = self.world_height_at(lot_cx, lot_cy)
                height_seed = 0.5 + 0.5 * math.sin((cx + ix * 2) * 1.7 + (cy + iy * 3) * 1.1)
                footprint_x = lot_size * (0.34 + 0.28 * ((math.sin(n * 19.0) + 1.0) * 0.5))
                footprint_y = lot_size * (0.34 + 0.28 * ((math.cos(n * 23.0) + 1.0) * 0.5))
                tower_hue = (district_hue + (ix - iy) * 0.015 + n * 0.08) % 1.0
                tower_color = hsv_color(tower_hue, 0.58, 1.0, 0.90)
                mid_height = (20.0 + 24.0 * n) * float(profile["height_scale"])
                tall_bonus = (34.0 + 110.0 * height_seed) * (0.66 + 0.42 * float(profile["height_scale"]))
                height = mid_height + (tall_bonus if n > 0.42 else 0.0)
                height += max(0.0, 22.0 * math.sin((lot_cx + lot_cy) * 0.0028))
                if profile["name"] == "spire" and (ix == 1 or iy == 2):
                    height *= 1.16
                size_vec = Vec3(footprint_x, footprint_y, height)
                center_vec = Vec3(lot_cx, lot_cy, base_z + height * 0.5)
                fill_color = hsv_color(tower_hue, 0.42 + 0.08 * n, 0.52 + 0.18 * height_seed, 1.0)
                self.add_solid_box(infill_parent, center_vec, size_vec, fill_color, name=f"metro-building-face-infill-{cx}-{cy}-{ix}-{iy}")
                self.add_box(infill_parent, center_vec, size_vec, tower_color, 0.48)
                building_count += 1
                tower_entries.append({
                    "ix": ix,
                    "iy": iy,
                    "x": lot_cx,
                    "y": lot_cy,
                    "base_z": base_z,
                    "top_z": base_z + height,
                    "height": height,
                })
                if n > 0.54:
                    upper_h = height * (0.20 + 0.16 * n)
                    upper_size = Vec3(footprint_x * 0.60, footprint_y * 0.60, upper_h)
                    upper_center = Vec3(
                        lot_cx + footprint_x * 0.05 * math.sin(n * 9.0),
                        lot_cy + footprint_y * 0.05 * math.cos(n * 11.0),
                        base_z + height + upper_h * 0.5,
                    )
                    upper_fill = hsv_color((tower_hue + 0.08) % 1.0, 0.34, 0.66, 1.0)
                    self.add_solid_box(infill_parent, upper_center, upper_size, upper_fill, name=f"metro-upper-face-infill-{cx}-{cy}-{ix}-{iy}")
                    self.add_box(infill_parent, upper_center, upper_size, accent_color, 0.42)
                if n > 0.72:
                    spire_h = height * 0.18 + 14.0
                    tip = Vec3(lot_cx, lot_cy, base_z + height + spire_h)
                    self.add_polyline(infill_parent, [Vec3(lot_cx, lot_cy, base_z + height), tip], accent_color, self.cfg.line_thickness * 0.40, False, f"metro-spire-{cx}-{cy}-{ix}-{iy}")
                    self.add_polyline(infill_parent, [tip + Vec3(-3.0, 0.0, -6.0), tip, tip + Vec3(3.0, 0.0, -6.0)], accent_color, self.cfg.line_thickness * 0.34, False, f"metro-spire-cap-{cx}-{cy}-{ix}-{iy}")

        # A few clean skybridges between neighboring tall towers.
        tower_map = {(entry["ix"], entry["iy"]): entry for entry in tower_entries}
        for entry in tower_entries:
            for dx, dy in ((1, 0), (0, 1)):
                other = tower_map.get((entry["ix"] + dx, entry["iy"] + dy))
                if not other:
                    continue
                if min(entry["height"], other["height"]) < 70.0:
                    continue
                bridge_z = min(entry["top_z"], other["top_z"]) - 12.0
                p0 = Vec3(entry["x"], entry["y"], bridge_z)
                p1 = Vec3(other["x"], other["y"], bridge_z)
                if (entry["ix"] + entry["iy"] + dx + dy + cx + cy) % 3 != 0:
                    continue
                self.add_polyline(infill_parent, [p0, p1], accent_color, self.cfg.line_thickness * 0.34, False, f"metro-skybridge-{cx}-{cy}-{entry['ix']}-{entry['iy']}-{dx}-{dy}")
                skybridge_count += 1

        # Chunk boundary and district frame. Only left/bottom ownership edges are
        # drawn; right/top would be duplicated by neighboring chunks and can flicker.
        seam_z = 0.16 + float(METROPOLIS_SEAM_Z_BIAS)
        boundary_lines = [
            [Vec3(x0, y0, self.world_height_at(x0, y0) + seam_z), Vec3(x0, y0 + size, self.world_height_at(x0, y0 + size) + seam_z)],
            [Vec3(x0, y0, self.world_height_at(x0, y0) + seam_z), Vec3(x0 + size, y0, self.world_height_at(x0 + size, y0) + seam_z)],
        ]
        self.add_polyline_batch(parent, boundary_lines, line_color, self.cfg.line_thickness * 0.56, False, f"metro-owned-boundary-{cx}-{cy}")
        self.metropolis_duplicate_edge_suppression_count += 2

        # Hover lanes high above the skyline.
        lane_alt = self.hub_ground_level() + 138.0 + 22.0 * math.sin(cx * 0.7 + cy * 0.9)
        lane_x = [Vec3(x0 + lot_size * 0.5, y0 + half, lane_alt), Vec3(x0 + size - lot_size * 0.5, y0 + half, lane_alt)]
        lane_y = [Vec3(x0 + half, y0 + lot_size * 0.5, lane_alt + 12.0), Vec3(x0 + half, y0 + size - lot_size * 0.5, lane_alt + 12.0)]
        if self.metro_segment_allowed(lane_x[0], lane_x[1], inner_radius):
            self.add_polyline(parent, lane_x, street_color, self.cfg.line_thickness * 0.26, False, f"metro-lane-x-{cx}-{cy}")
        if self.metro_segment_allowed(lane_y[0], lane_y[1], inner_radius):
            self.add_polyline(parent, lane_y, street_color, self.cfg.line_thickness * 0.22, False, f"metro-lane-y-{cx}-{cy}")

        for idx in range(int(METROPOLIS_VEHICLES_PER_CHUNK)):
            seed = math.sin((cx * 31 + cy * 17 + idx * 13) * 1.213) * 43758.5453
            n = seed - math.floor(seed)
            root = parent.attachNewNode(f"metro-hover-{cx}-{cy}-{idx}")
            trail_len = 18.0 + 26.0 * n
            craft_color = hsv_color((district_hue + 0.16 + n * 0.10) % 1.0, 0.52, 1.0, 0.92)
            trail_color = hsv_color((district_hue + 0.22 + n * 0.10) % 1.0, 0.82, 1.0, 0.56)
            self.add_polyline(root, [Vec3(-trail_len, 0.0, 0.0), Vec3(-6.0, 0.0, 0.0)], trail_color, self.cfg.line_thickness * 0.44, False, f"metro-hover-trail-{idx}")
            self.add_polyline(root, [Vec3(-4.0, -2.0, 0.0), Vec3(3.6, 0.0, 0.0), Vec3(-4.0, 2.0, 0.0)], craft_color, self.cfg.line_thickness * 0.48, False, f"metro-hover-body-{idx}")
            self.add_polyline(root, [Vec3(-1.2, -3.0, 0.0), Vec3(-3.6, 0.0, 0.0), Vec3(-1.2, 3.0, 0.0)], craft_color, self.cfg.line_thickness * 0.34, False, f"metro-hover-wing-{idx}")
            x_min = x0 - half * 0.25
            x_max = x0 + size + half * 0.25
            y_min = y0 - half * 0.25
            y_max = y0 + size + half * 0.25
            alt = self.hub_ground_level() + 116.0 + 76.0 * n
            axis = 0 if n < 0.5 else 1
            speed = 30.0 + 36.0 * (0.25 + n)
            root.setPythonTag("metro_kind", "vehicle")
            root.setPythonTag("axis", axis)
            root.setPythonTag("x_min", x_min)
            root.setPythonTag("x_max", x_max)
            root.setPythonTag("y_min", y_min)
            root.setPythonTag("y_max", y_max)
            root.setPythonTag("base_x", x0 + size * ((idx + 0.23) / max(1, METROPOLIS_VEHICLES_PER_CHUNK)))
            root.setPythonTag("base_y", y0 + size * ((idx * 0.37 + 0.19) % 1.0))
            root.setPythonTag("alt", alt)
            root.setPythonTag("speed", speed)
            root.setPythonTag("phase", n * math.tau)
            root.setPythonTag("amp", 6.0 + 12.0 * n)
            self.metropolis_hover_vehicle_nodes.append(root)
            vehicle_count += 1

        # Tiny service robots move on small waypoint loops through the city.
        for idx in range(int(METROPOLIS_ROBOTS_PER_CHUNK)):
            seed = math.sin((cx * 13 + cy * 29 + idx * 5) * 3.173) * 12741.731
            n = seed - math.floor(seed)
            root = parent.attachNewNode(f"metro-robot-{cx}-{cy}-{idx}")
            robot_color = hsv_color((district_hue + 0.24 + n * 0.22) % 1.0, 0.32, 1.0, 0.94)
            self.add_polyline(root, [Vec3(-1.1, 0.0, 0.0), Vec3(1.1, 0.0, 0.0)], robot_color, self.cfg.line_thickness * 0.30, False, f"metro-robot-h-{idx}")
            self.add_polyline(root, [Vec3(0.0, -1.1, 0.0), Vec3(0.0, 1.1, 0.0)], robot_color, self.cfg.line_thickness * 0.30, False, f"metro-robot-v-{idx}")
            self.add_polyline(root, [Vec3(0.0, 0.0, -0.6), Vec3(0.0, 0.0, 0.6)], robot_color, self.cfg.line_thickness * 0.26, False, f"metro-robot-z-{idx}")
            base_ix = idx % METROPOLIS_LOTS_PER_AXIS
            base_iy = (idx // max(1, METROPOLIS_LOTS_PER_AXIS)) % METROPOLIS_LOTS_PER_AXIS
            lane_x = x0 + (base_ix + 0.5) * lot_size
            lane_y = y0 + (base_iy + 0.5) * lot_size
            route = []
            for step in range(4):
                wx = x0 + (((base_ix + step) % METROPOLIS_LOTS_PER_AXIS) + 0.5) * lot_size
                wy = y0 + (((base_iy + (step % 2)) % METROPOLIS_LOTS_PER_AXIS) + 0.5) * lot_size
                wz = self.world_height_at(wx, wy) + 10.0 + 16.0 * n + (step % 2) * 2.0
                route.append((wx, wy, wz))
            root.setPythonTag("metro_kind", "robot")
            root.setPythonTag("route_points", route)
            root.setPythonTag("radius", 8.0 + 8.0 * n)
            root.setPythonTag("alt", self.world_height_at(lane_x, lane_y) + 12.0 + 18.0 * n)
            root.setPythonTag("speed", 0.36 + 0.54 * (0.25 + n))
            root.setPythonTag("phase", n * math.tau)
            self.metropolis_robot_nodes.append(root)
            robot_count += 1

        parent.setPythonTag("metropolis_building_count", building_count)
        parent.setPythonTag("metropolis_vehicle_count", vehicle_count)
        parent.setPythonTag("metropolis_robot_count", robot_count)
        parent.setPythonTag("metropolis_skybridge_count", skybridge_count)
        parent.setPythonTag("metropolis_district_name", profile["name"])
        self.metropolis_chunks[key] = parent
        return parent

    def prune_redundant_surface_layers(self):
        """Remove known duplicate solid surface layers; keep one authoritative fill per sector.

        Visual line grids, contour lines, mushrooms, and structure/entity infill are left alone.
        This only removes extra solid ground sheets that sit directly under another opaque
        authoritative surface and therefore cost performance without being visible.
        """
        removed = 0
        for root in (getattr(self, "world_root", None), getattr(self, "surface_root", None)):
            if root is None or root.isEmpty():
                continue
            for pattern in ("**/metro-ground-infill-*", "**/metro-ground-soft-infill-*"):
                try:
                    matches = list(root.findAllMatches(pattern))
                except Exception:
                    matches = []
                for node in matches:
                    try:
                        if node is not None and not node.isEmpty():
                            node.removeNode()
                            removed += 1
                    except Exception:
                        pass
        if removed:
            self.surface_audit_summary = dict(getattr(self, "surface_audit_summary", {}) or {})
            self.surface_audit_summary["redundant_solid_surface_layers_removed"] = int(removed)
        return removed

    def update_metropolis_infill_fade(self, dt: float):
        """Pass 91: Metropolis fade is retired.

        City structures now use solid roots/opaque fill so there is no per-frame
        fade scan, alpha ramp, or transparent parent layer.
        """
        return

    def update_metropolis_air_traffic(self, dt):
        if not self.metropolis_chunks:
            self.metropolis_hover_vehicle_nodes = []
            self.metropolis_robot_nodes = []
            return
        alive_vehicles = []
        for node in list(self.metropolis_hover_vehicle_nodes):
            if node is None or node.isEmpty():
                continue
            try:
                axis = int(node.getPythonTag("axis") or 0)
                x_min = float(node.getPythonTag("x_min"))
                x_max = float(node.getPythonTag("x_max"))
                y_min = float(node.getPythonTag("y_min"))
                y_max = float(node.getPythonTag("y_max"))
                speed = float(node.getPythonTag("speed") or 24.0)
                phase = float(node.getPythonTag("phase") or 0.0)
                amp = float(node.getPythonTag("amp") or 8.0)
                base_x = float(node.getPythonTag("base_x") or 0.0)
                base_y = float(node.getPythonTag("base_y") or 0.0)
                alt = float(node.getPythonTag("alt") or 80.0)
                if axis == 0:
                    span = max(1.0, x_max - x_min)
                    x = x_min + ((base_x - x_min + self.elapsed * speed) % span)
                    y = base_y + math.sin(self.elapsed * 0.8 + phase) * amp
                    h = 0.0 if speed >= 0.0 else 180.0
                else:
                    span = max(1.0, y_max - y_min)
                    y = y_min + ((base_y - y_min + self.elapsed * speed) % span)
                    x = base_x + math.sin(self.elapsed * 0.8 + phase) * amp
                    h = 90.0 if speed >= 0.0 else -90.0
                z = alt + math.sin(self.elapsed * 1.2 + phase * 1.7) * 4.0
                node.setPos(x, y, z)
                node.setH(h)
                alive_vehicles.append(node)
            except Exception:
                continue
        self.metropolis_hover_vehicle_nodes = alive_vehicles

        alive_robots = []
        for node in list(self.metropolis_robot_nodes):
            if node is None or node.isEmpty():
                continue
            try:
                route = node.getPythonTag("route_points") or []
                speed = float(node.getPythonTag("speed") or 1.0)
                phase = float(node.getPythonTag("phase") or 0.0)
                if len(route) >= 2:
                    cycle = self.elapsed * speed + phase
                    seg = int(math.floor(cycle)) % len(route)
                    nxt = (seg + 1) % len(route)
                    t = cycle - math.floor(cycle)
                    x = lerp(route[seg][0], route[nxt][0], t)
                    y = lerp(route[seg][1], route[nxt][1], t)
                    z = lerp(route[seg][2], route[nxt][2], t) + math.sin(self.elapsed * 2.1 + phase) * 1.4
                    heading = math.degrees(math.atan2(route[nxt][1] - route[seg][1], route[nxt][0] - route[seg][0]))
                else:
                    radius = float(node.getPythonTag("radius") or 12.0)
                    alt = float(node.getPythonTag("alt") or 8.0)
                    ang = self.elapsed * speed + phase
                    x = math.cos(ang) * radius
                    y = math.sin(ang * 1.35) * radius * 0.55
                    z = alt + math.sin(self.elapsed * 2.2 + phase) * 2.2
                    heading = math.degrees(ang) % 360.0
                node.setPos(x, y, z)
                node.setH(heading % 360.0)
                alive_robots.append(node)
            except Exception:
                continue
        self.metropolis_robot_nodes = alive_robots

    def build_biome_horizon_guides(self):
        # Pass 36: sparse long-distance terrain cues inside the large rings.
        # These are horizon/route guides, not props or city meshes. They help a
        # player read direction inside a wide biome without needing to see the
        # next biome seam immediately.
        horizon_color = hsv_color((self.cfg.line_hue + 0.40) % 1.0, 0.62, 1.0, 0.20)
        chevron_color = hsv_color((self.cfg.line_hue + 0.52) % 1.0, 0.78, 1.0, 0.36)
        arcs = []
        chevrons = []
        for ring in BIOME_RINGS[1:]:
            r0 = float(ring["r0"])
            r1 = float(ring["r1"])
            span = max(1.0, r1 - r0)
            # Three very broad range rails per biome: near, mid, far.
            for t in BIOME_HORIZON_GUIDE_T_VALUES:
                radius = lerp(r0, r1, float(t))
                pts = []
                for i in range(128):
                    ang = math.tau * i / 128.0
                    x = math.cos(ang) * radius
                    y = math.sin(ang) * radius
                    pts.append(Vec3(x, y, self.world_height_at(x, y) + 0.42))
                arcs.append(pts)
            # Outward chevrons at the four route lanes, placed well inside each
            # ring so they guide the eye across the current biome rather than at
            # the seam into the next one.
            for deg in BIOME_CORRIDOR_DEGREES:
                ang = math.radians(float(deg))
                tangent = Vec3(-math.sin(ang), math.cos(ang), 0.0)
                radius = r0 + span * 0.70
                tip = self._biome_point_at(radius + min(90.0, span * 0.10), ang, 0.55)
                back = self._biome_point_at(radius, ang, 0.50)
                width = 18.0 if int(ring["key"]) < 7 else 28.0
                chevrons.append([back + tangent * width, tip, back - tangent * width])
        self.add_polyline_batch(self.line_root, arcs, horizon_color, self.cfg.line_thickness * 0.44, True, "biome-pass36-horizon-range-rails")
        self.add_polyline_batch(self.accent_root, chevrons, chevron_color, self.cfg.line_thickness * 0.72, False, "biome-pass36-outward-chevrons")

    def build_biome_connection_ribbons(self):
        # Pass 37: beauty/continuity layer. These are still terrain lines, not
        # props. They arc across multiple rings and prove the terrain is one
        # connected field with biome-specific shapes layered onto it.
        floor_z = self.hub_ground_level()
        forest_palette = BIOME_LUSH_PALETTES["forest"]
        hills_palette = BIOME_LUSH_PALETTES["hills"]
        water_palette = BIOME_LUSH_PALETTES["water"]
        flow_color = rgb_to_rgba(forest_palette["line"], 0.38, 1.04)
        braid_color = rgb_to_rgba(hills_palette["accent"], 0.44, 1.00)
        rhythm_color = rgb_to_rgba(hills_palette["soft"], 0.30, 1.04)
        floor_return_color = rgb_to_rgba(water_palette["accent"], 0.56, 0.95)

        flow_ribbons = []
        start_r = self.hub_radius + 18.0
        end_r = self.map_line_outer_radius() - 12.0
        samples = 188
        for base_deg in BIOME_FLOW_RIBBON_DEGREES:
            base_ang = math.radians(float(base_deg))
            phase = math.radians(float(base_deg) * 1.7)
            pts = []
            for idx in range(samples + 1):
                t = idx / float(samples)
                radius = lerp(start_r, end_r, t)
                # Extremely shallow angular drift: enough to read as composed
                # organic flow, not enough to break the radial/ring structure.
                drift = 0.020 * math.sin(t * math.tau * 2.0 + phase) + 0.010 * math.sin(t * math.tau * 5.0 - phase)
                ang = base_ang + drift
                pts.append(self._biome_point_at(radius, ang, 0.245))
            flow_ribbons.append(pts)

        seam_braids = []
        floor_return_rings = []
        for ring in BIOME_RINGS[1:]:
            seam_r = float(ring["r0"])
            # A clear exact-floor seam, plus adjacent terrain-following braid
            # rings on both sides. This makes boundaries feel connected rather
            # than like stacked discs.
            seam_pts = []
            for i in range(224):
                ang = math.tau * i / 224.0
                seam_pts.append(Vec3(math.cos(ang) * seam_r, math.sin(ang) * seam_r, floor_z + 0.245))
            floor_return_rings.append(seam_pts)
            for off in BIOME_SEAM_BRAID_OFFSETS:
                radius = clamp(seam_r + float(off), self.hub_radius + 4.0, self.map_line_outer_radius() - 4.0)
                pts = []
                for i in range(224):
                    u = i / 224.0
                    ang = math.tau * u
                    # Subtle scallop makes the seam read as a soft transition
                    # field while still following actual terrain height.
                    r = radius + 6.0 * math.sin(ang * 6.0 + seam_r * 0.001)
                    x = math.cos(ang) * r
                    y = math.sin(ang) * r
                    pts.append(Vec3(x, y, self.world_height_at(x, y) + 0.205 + abs(off) * 0.0006))
                seam_braids.append(pts)

        rhythm_rings = []
        for ring in BIOME_RINGS[1:]:
            r0 = float(ring["r0"])
            r1 = float(ring["r1"])
            kind = str(ring.get("kind", ""))
            wave_amp = 5.0 if kind in ("forest", "water", "desert") else 3.0
            if kind in ("urban", "metropolis"):
                wave_amp = 1.0
            for t in BIOME_INTERIOR_RHYTHM_T_VALUES:
                radius = lerp(r0, r1, float(t))
                pts = []
                for i in range(180):
                    u = i / 180.0
                    ang = math.tau * u
                    r = radius + wave_amp * math.sin(ang * (5.0 + int(ring["key"])) + float(t) * math.tau)
                    x = math.cos(ang) * r
                    y = math.sin(ang) * r
                    pts.append(Vec3(x, y, self.world_height_at(x, y) + 0.175))
                rhythm_rings.append(pts)

        self.add_polyline_batch(self.line_root, flow_ribbons, flow_color, self.cfg.line_thickness * 0.62, False, "biome-pass37-continuous-flow-ribbons")
        self.add_polyline_batch(self.line_root, seam_braids, braid_color, self.cfg.line_thickness * 0.50, True, "biome-pass37-seam-braid-rings")
        self.add_polyline_batch(self.accent_root, floor_return_rings, floor_return_color, self.cfg.line_thickness * 0.88, True, "biome-pass37-floor-return-seams")
        self.add_polyline_batch(self.line_root, rhythm_rings, rhythm_color, self.cfg.line_thickness * 0.42, True, "biome-pass37-interior-rhythm-rails")

    def biome_inner_presentation_band_outer_radius(self, ring) -> float:
        """Compatibility helper after 282.23 presentation-strip removal.

        Pass 282.24 restores sector terrain ownership all the way to each
        biome's real inner radius.  Returning r0 keeps old callers safe while
        ensuring there is no hidden annular strip underneath the full Forest
        ring pilot.
        """
        return float((ring or {}).get("r0", 0.0))

    def build_continuous_biome_inner_bands(self):
        """Pass 282.24: retired.

        282.23 drew a lightweight full-circle floor strip, but the requested
        behavior is a full 360-degree *detailed Forest ring*.  Keeping this
        method as a no-op avoids breaking older diagnostics while ensuring no
        presentation strip overlaps the real sector terrain.
        """
        try:
            self.surface_root.setPythonTag("continuous_inner_biome_band_count", 0)
            self.surface_root.setPythonTag("continuous_inner_biome_band_pass28223", 0)
            self.surface_root.setPythonTag("forest_full_ring_streaming_pass28224", 1)
        except Exception:
            pass
        return 0

    def build_biome_ring_framework(self):
        # Pass 282.24: 282.23 presentation strips are retired; this no-op keeps
        # compatibility tags explicit before map-grade lines are built.
        self.build_continuous_biome_inner_bands()
        # Pass 31: readable concentric region map around the clean hub/flatland.
        floor_z = self.hub_ground_level()
        guide_z = floor_z + 0.055
        boundary_color = hsv_color((self.cfg.line_hue + 0.18) % 1.0, 0.72, 1.0, 0.50)
        label_color = hsv_color((self.cfg.line_hue + 0.22) % 1.0, 0.54, 1.0, 0.86)
        spoke_color = hsv_color((self.cfg.line_hue + 0.10) % 1.0, 0.64, 0.88, 0.25)

        # Always-visible map rings and spoke lanes tell the player what exists beyond the current streamed terrain.
        for ring in BIOME_RINGS:
            if ring["r0"] > self.hub_radius + 0.5:
                self.add_polyline(self.line_root, self.polygon_points(ring["r0"], guide_z, 192, 0.0), boundary_color, self.cfg.line_thickness * 0.66, True, f"biome-boundary-{ring['name']}")
            if not bool(ring.get("infinite", False)):
                self.add_polyline(self.line_root, self.polygon_points(ring["r1"], guide_z + 0.01, 192, 0.0), boundary_color, self.cfg.line_thickness * (0.82 if ring["key"] == 1 else 0.58), True, f"biome-outer-{ring['name']}")
            # Pass 56: remove region signs. The map rings remain as subtle world structure,
            # but no floating text labels are generated in or around the biome fields.

        spoke_segments = []
        for deg in range(0, 360, 30):
            ang = math.radians(deg)
            start = self.hub_radius + 2.0
            end = self.map_line_outer_radius()
            spoke_segments.append((Vec3(math.cos(ang) * start, math.sin(ang) * start, guide_z + 0.018), Vec3(math.cos(ang) * end, math.sin(ang) * end, guide_z + 0.018)))
        self.add_line_segments(self.line_root, spoke_segments, spoke_color, self.cfg.line_thickness * 0.44, "biome-map-spokes")
        self.build_biome_profile_guides()
        self.build_biome_traversal_corridors()
        self.build_biome_route_beacons()
        self.build_biome_horizon_guides()
        self.build_biome_connection_ribbons()

    def biome_ring_for_radius(self, radius: float):
        r = float(radius)
        for ring in BIOME_RINGS:
            if ring["r0"] <= r < ring["r1"]:
                return ring
        if r >= BIOME_RINGS[-1]["r1"]:
            return BIOME_RINGS[-1]
        return None

    def biome_ring_for_key(self, key: int):
        for ring in BIOME_RINGS:
            if int(ring["key"]) == int(key):
                return ring
        return None

    def biome_height_offset_at(self, x: float, y: float) -> float:
        radius = math.sqrt(x * x + y * y)
        ring = self.biome_ring_for_radius(radius)
        if not ring or ring["kind"] == "flat":
            return 0.0
        span = max(1.0, ring["r1"] - ring["r0"])
        t = clamp((radius - ring["r0"]) / span, 0.0, 1.0)
        # Critical terrain rule: offset is exactly zero at both ring seams.
        # Pass 33 uses smoother seam easing so the visual mesh and collision
        # return to the hub level without a sharp step.
        seam_blend = max(0.04, float(BIOME_TRANSITION_BLEND))
        seam_in = self._smootherstep(clamp(t / seam_blend, 0.0, 1.0))
        seam_out = self._smootherstep(clamp((1.0 - t) / seam_blend, 0.0, 1.0))
        envelope = math.sin(math.pi * t) * seam_in * seam_out
        angle = math.atan2(y, x)
        kind = ring["kind"]
        h = float(ring.get("height", 0.0))
        corridor = self.biome_corridor_weight_at(angle, lane_half_width=0.058)
        # Corridors remain shaped but calmer. They are not separate flat roads;
        # they are readable low-slope traversal lanes through the ring terrain.
        corridor_scale = lerp(1.0, 0.24, corridor)
        if kind == "metropolis" and self.metropolis_city_active():
            # Pass 282.52: flat streets and +0.30 m sidewalk pads, exactly the
            # drawn city ground (holoverse/metropolis_layout.py).
            return _metro_layout.ground_offset(x, y, float(ring["r0"]))
        if kind == "metropolis":
            # Pass 52: the last region no longer tapers out at the old outer ring.
            # It becomes a lightly terraced, effectively endless city base whose
            # visible skyline is supplied by streaming city chunks.
            entry = self._smootherstep(clamp((radius - float(ring["r0"])) / float(METROPOLIS_ENTRY_BLEND), 0.0, 1.0))
            cell = 92.0
            gx = (x + 18000.0) / cell
            gy = (y - 14000.0) / cell
            fx = abs((gx - math.floor(gx)) - 0.5)
            fy = abs((gy - math.floor(gy)) - 0.5)
            road = 1.0 if (fx < 0.17 or fy < 0.17) else 0.0
            ix = math.floor(gx)
            iy = math.floor(gy)
            block_hash = math.sin(ix * 12.9898 + iy * 78.233 + 91.77) * 43758.5453
            noise = block_hash - math.floor(block_hash)
            podium = 0.18 + 0.92 * noise
            road_scale = 0.22 if road > 0.5 else 1.0
            value = h * entry * (0.28 + podium * 0.70) * road_scale
            return value * corridor_scale
        if kind == "forest":
            # Pass 55: give the forest real connected terrain relief instead
            # of a nearly flat carpet. The seam envelope still returns exactly
            # to shared ground at both ring edges.
            und = 0.52 + 0.30 * math.sin(angle * 5.0 + radius * 0.010) + 0.18 * math.sin(angle * 11.0 - radius * 0.006)
            root_swell = 0.16 * math.cos(x * 0.006 - y * 0.004)
            value = h * (envelope ** 1.04) * clamp(und + root_swell, 0.16, 1.12)
        elif kind == "hills":
            # Pass 282.33: recognizable broad repeating hills replace the old
            # mostly-waveform relief.  The repeated mound field is deterministic
            # and continuous; the shared seam envelope and corridor authority
            # still own transitions and walkable radial routes.
            mound_relief = repeating_hills_relief_at(x, y, float(ring["r0"]), float(ring["r1"]))
            broad_roll = 0.12 + 0.08 * math.sin(angle * 2.0 - radius * 0.0031) + 0.05 * math.cos(x * 0.0022 + y * 0.0016)
            terrain_profile = clamp(broad_roll + mound_relief, 0.04, 1.92)
            # Suppress large mound mass more aggressively in the four authored
            # travel corridors while preserving slight natural terrain motion.
            hill_corridor_scale = lerp(1.0, 0.14, corridor)
            value = h * (envelope ** 1.14) * terrain_profile * hill_corridor_scale
        elif kind == "water":
            basin = 0.78 + 0.16 * math.sin(angle * 4.0 - radius * 0.006) + 0.10 * math.cos(x * 0.004 + y * 0.003)
            trough = 0.16 * math.sin(angle * 8.0 + radius * 0.0045)
            value = h * (envelope ** 0.82) * clamp(basin + trough, 0.48, 1.18)
        elif kind == "mushroom":
            # Pass 85: region 4 is now a ground-level Mushroom biome with real hills.
            # It returns exactly to the shared ground at both seams like the other land rings.
            ridge = math.sin(angle * 3.2 + radius * 0.0042)
            cross = math.sin(angle * 7.0 - radius * 0.0064)
            pocket = math.cos(x * 0.0030 + y * 0.0044)
            mound = abs(math.sin(angle * 4.5 + radius * 0.0028)) * 0.34
            rolling = 0.48 + 0.34 * ridge + 0.22 * cross + 0.18 * pocket + mound
            value = h * (envelope ** 1.10) * clamp(rolling, 0.08, 1.28)
        elif kind == "desert":
            # Pass 282.36: the Desert is terrain-first now.  Three continuous
            # wind-wave families form broad repeated dunes, while shared seam
            # and corridor authorities keep ring transitions and radial travel
            # lanes safe.  Macro mesas/rocks are a separate visual layer.
            dune_relief = desert_dune_relief_at(x, y, float(ring["r0"]), float(ring["r1"]))
            desert_corridor_scale = lerp(1.0, 0.18, corridor)
            value = h * (envelope ** 1.10) * dune_relief * desert_corridor_scale
        elif kind == "ice":
            # Pass 282.37: Ice is now broad glacial terrain rather than a flat
            # stepped grid.  Frost Circuit owns the central race band, so relief
            # is deliberately calmer near the track radius while the outer and
            # inner ice shelves receive stronger ridges.  Shared seams/corridors
            # remain the final traversal authority.
            track_radius = (float(ring["r0"]) + float(ring["r1"])) * 0.5
            glacial_relief = ice_glacial_relief_at(x, y, float(ring["r0"]), float(ring["r1"]), track_radius)
            ice_corridor_scale = lerp(1.0, 0.28, corridor)
            value = h * (envelope ** 1.08) * glacial_relief * ice_corridor_scale
        elif kind == "urban":
            block = 1.0 if int((angle % math.tau) / (math.tau / 16.0)) % 2 == 0 else 0.62
            crater_roll = 0.24 * math.sin(x * 0.0082 + y * 0.0051) + 0.18 * math.cos(x * 0.0041 - y * 0.0093)
            berms = 0.22 * abs(math.sin(angle * 10.0 + radius * 0.0044))
            value = h * envelope * clamp(0.28 + 0.42 * block + crater_roll + berms, 0.10, 1.18)
        elif kind == "metropolis":
            crown = 0.55 + 0.45 * abs(math.sin(angle * 8.0))
            value = h * envelope * crown
        else:
            value = 0.0
        return value * corridor_scale

    def theme_ground_rgb(self, ring):
        kind = str((ring or {}).get("kind", "flat"))
        # Pass 63: explicit low-cost grid-fill palette. These are the visible
        # authoritative ground fills; they are not decorative hidden underlays.
        theme = {
            "flat": (0.92, 0.94, 0.90),       # white
            "forest": (0.06, 0.46, 0.12),     # green
            "hills": (0.36, 0.78, 0.16),      # lime green, distinct from forest
            "water": (0.0, 0.0, 0.0),         # legacy; not used by region 4 anymore
            "mushroom": (0.62, 0.08, 0.50),   # pink/purple ground authority
            "desert": (0.46, 0.235, 0.060),    # warm sand / burnt amber
            "ice": (0.16, 0.42, 0.76),        # blue
            "urban": (0.115, 0.122, 0.138),    # dark asphalt; intentionally darker than the Urban sky
            "metropolis": (0.22, 0.09, 0.34), # darker purple infill authority
            "space": (0.0, 0.0, 0.0),         # black
            "hub": (0.92, 0.94, 0.90),
        }
        return theme.get(kind, theme["flat"])

    def separated_ground_rgb(self, ring, base_rgb=None):
        kind = str((ring or {}).get("kind", "flat"))
        if base_rgb is None:
            base_rgb = self.theme_ground_rgb(ring)
        base_rgb = tuple(float(v) for v in base_rgb)
        if kind == "ice":
            return base_rgb
        sky_rgb = SPACE_SKY_RGB
        diff = abs(base_rgb[0] - sky_rgb[0]) + abs(base_rgb[1] - sky_rgb[1]) + abs(base_rgb[2] - sky_rgb[2])
        if diff < 0.34:
            target = self.theme_ground_rgb(ring)
            weight = clamp((0.34 - diff) / 0.34, 0.0, 1.0)
            base_rgb = lerp_rgb(base_rgb, target, 0.82 + weight * 0.18)
        return base_rgb

    def biome_ground_fill_color(self, ring, alpha=1.0, brighten=0.0):
        kind = str((ring or {}).get("kind", "flat"))
        if kind == "water":
            return (0.0, 0.0, 0.0, 0.0)
        # Opaque color geometry is cheaper and more readable than translucent
        # layered fills; alpha is forced to 1 for land authority surfaces.
        return (*self.theme_ground_rgb(ring), 1.0)

    def biome_color(self, ring, alpha=0.16, brighten=0.34, channel="line"):
        kind = str((ring or {}).get("kind", "flat"))
        palette = BIOME_LUSH_PALETTES.get(kind)
        if palette:
            channel = str(channel or "line")
            if channel not in palette:
                channel = "line"
            if channel == "fill":
                intensity = clamp(0.78 + float(brighten) * 0.80, 0.62, 1.16)
            elif channel == "soft":
                intensity = clamp(0.78 + float(brighten) * 0.44, 0.62, 1.15)
            else:
                intensity = clamp(0.82 + float(brighten) * 0.30, 0.72, 1.18)
            return rgb_to_rgba(palette[channel], alpha, intensity)
        return hsv_color((self.cfg.line_hue + float((ring or {}).get("hue", 0.0))) % 1.0, 0.58, brighten, alpha)

    def sky_palette_for_ring(self, ring):
        # Compatibility helper for older terrain-contrast logic.  Every region
        # now shares the same persistent space sky authority.
        return {"space": SPACE_SKY_RGB}

    def compute_target_sky_rgb(self):
        self.current_day_factor = 0.0
        self.current_dusk_factor = 0.0
        radius = math.sqrt(self.player_pos.x * self.player_pos.x + self.player_pos.y * self.player_pos.y)
        ring = self.biome_ring_for_radius(radius)
        self.current_sky_biome = "SPACE"
        color = SPACE_SKY_RGB
        if ring is not None and str(ring.get("kind", "")) == "water":
            depth_t = self.deep_water_depth_factor()
            if depth_t > 0.0:
                color = lerp_rgb(SPACE_SKY_RGB, (0.002, 0.018, 0.044), 0.78 + depth_t * 0.18)
        return tuple(float(c) for c in color)

    def craft_stratosphere_factor(self, pos=None):
        pos = pos if pos is not None else self.player_pos
        radius = math.sqrt(float(pos.x) * float(pos.x) + float(pos.y) * float(pos.y))
        if radius <= self.craft_hub_lock_radius():
            return 0.0
        try:
            min_z = self.craft_minimum_eye_z(float(pos.x), float(pos.y))
        except Exception:
            min_z = float(self.cfg.player_eye_height)
        altitude = max(0.0, float(pos.z) - float(min_z))
        return smoothstep(clamp((altitude - float(CRAFT_STRATOSPHERE_START_Z)) / max(1.0, float(CRAFT_STRATOSPHERE_END_Z - CRAFT_STRATOSPHERE_START_Z)), 0.0, 1.0))

    def set_water_region_occlusion(self, active: bool):
        active = bool(active)
        if getattr(self, "water_region_occlusion_active", False) == active:
            return
        self.water_region_occlusion_active = active
        hide_when_water = [
            getattr(self, "surface_root", None),
            getattr(self, "line_root", None),
            getattr(self, "accent_root", None),
            getattr(self, "dome_root", None),
            getattr(self, "lens_root", None),
            getattr(self, "sky_root", None),
            getattr(self, "galaxy_root", None),
            getattr(self, "user_build_root", None),
            getattr(self, "atmosphere_root", None),
        ]
        for node in hide_when_water:
            try:
                if node is None or node.isEmpty():
                    continue
                node.hide() if active else node.show()
            except Exception:
                pass
        try:
            if active:
                self.world_root.setColorScale(0.58, 0.88, 1.0, 0.96)
            else:
                self.world_root.setColorScale(1.0, 1.0, 1.0, 1.0)
        except Exception:
            pass

    def update_water_region_visual_state(self):
        self.set_water_region_occlusion(self.deep_water_mode_active())

    def update_day_night_sky(self, dt: float):
        """Compatibility update hook for the Pass 26 persistent space sky.

        The old day/night cycle is intentionally retired.  HoloSpace keeps its
        long-distance fog authority; ordinary regions keep local fog depth but
        always render against the same outer-space background.
        """
        self.update_water_region_visual_state()
        target = SPACE_SKY_RGB
        self.current_bg_rgb = target
        self.current_sky_rgb = target
        self.current_day_factor = 0.0
        self.current_dusk_factor = 0.0
        self.current_sky_biome = "SPACE"
        self.setBackgroundColor(*target)
        self.fog.setColor(*target)
        if bool(getattr(self, "holospace_active", False)):
            self.fog.setLinearRange(9000.0, 18000.0)
        else:
            fog_near = self.cfg.fog_distance * 0.46
            fog_far = self.cfg.fog_distance * 1.02
            active_ring = self.biome_ring_for_radius(math.sqrt(self.player_pos.x * self.player_pos.x + self.player_pos.y * self.player_pos.y))
            if active_ring is not None and str(active_ring.get("kind", "")) == "urban":
                fog_near = self.cfg.fog_distance * 0.24
                fog_far = self.cfg.fog_distance * 0.58
            if self.urban_conflict_active():
                urban = self.biome_ring_for_key(7)
                pr = math.sqrt(self.player_pos.x * self.player_pos.x + self.player_pos.y * self.player_pos.y)
                edge = min(pr - float(urban["r0"]), float(urban["r1"]) - pr)
                smog = clamp((edge + float(URBAN_SMOG_BLEND_METRES)) / (2.0 * float(URBAN_SMOG_BLEND_METRES)), 0.0, 1.0)
                self.urban_smog_factor = float(smog)
                if smog > 0.0:
                    self.fog.setColor(*lerp_rgb(SPACE_SKY_RGB, URBAN_SMOG_RGB, smog))
            if self.ice_civilization_active():
                haze = self._ring_edge_blend(6, float(ICE_HAZE_BLEND_METRES))
                self.ice_haze_factor = float(haze)
                if haze > 0.0:
                    self.fog.setColor(*lerp_rgb(SPACE_SKY_RGB, _ice_visuals.ICE_HAZE_RGB, haze))
            if self.fungal_civilization_active():
                haze = self._ring_edge_blend(4, float(FUNGAL_HAZE_BLEND_METRES))
                self.fungal_haze_factor = float(haze)
                if haze > 0.0:
                    self.fog.setColor(*lerp_rgb(SPACE_SKY_RGB, _fungal_visuals.FUNGAL_HAZE_RGB, haze))
            if self.desert_civilization_active():
                haze = self._ring_edge_blend(5, float(DESERT_HAZE_BLEND_METRES))
                self.desert_haze_factor = float(haze)
                if haze > 0.0:
                    self.fog.setColor(*lerp_rgb(SPACE_SKY_RGB, _desert_visuals.DESERT_HAZE_RGB, haze))
            altitude_t = self.craft_stratosphere_factor()
            if altitude_t > 0.0:
                fog_near = lerp(fog_near, self.cfg.fog_distance * 0.62, altitude_t)
                fog_far = lerp(fog_far, self.cfg.fog_distance * 2.20, altitude_t)
            depth_t = self.deep_water_depth_factor()
            if depth_t > 0.0:
                fog_near = lerp(fog_near, float(DEEP_WATER_OCCLUSION_FOG_NEAR), depth_t)
                fog_far = lerp(fog_far, float(DEEP_WATER_OCCLUSION_FOG_FAR), depth_t)
                self.fog.setColor(*lerp_rgb(SPACE_SKY_RGB, (0.010, 0.082, 0.132), 0.68 + depth_t * 0.24))
            self.fog.setLinearRange(fog_near, fog_far)
        self.update_celestial_cycle_markers(dt)
        self.update_sky_png_card(dt)

    def angle_in_sector(self, angle: float, a0: float, a1: float) -> bool:
        angle = angle % math.tau
        a0 = a0 % math.tau
        a1 = a1 % math.tau
        if a0 <= a1:
            return a0 <= angle <= a1
        return angle >= a0 or angle <= a1

    def forest_tree_grid_step(self, ring) -> float:
        span = max(120.0, float(ring["r1"]) - float(ring["r0"]))
        return max(42.0, min(64.0, span / 26.0))

    def forest_tree_candidate_points(self, ring, sector_idx: int, a0: float, a1: float):
        if str(ring.get("kind", "")) != "forest":
            return []
        step = self.forest_tree_grid_step(ring)
        r0 = float(ring["r0"]) + step * 0.45
        r1 = float(ring["r1"]) - step * 0.45
        if r1 <= r0:
            return []
        sample_points = []
        for radius in (r0, (r0 + r1) * 0.5, r1):
            for ang in (a0, (a0 + a1) * 0.5, a1):
                sample_points.append((math.cos(ang) * radius, math.sin(ang) * radius))
        min_x = min(p[0] for p in sample_points) - step
        max_x = max(p[0] for p in sample_points) + step
        min_y = min(p[1] for p in sample_points) - step
        max_y = max(p[1] for p in sample_points) + step
        ix0 = int(math.floor(min_x / step))
        ix1 = int(math.ceil(max_x / step))
        iy0 = int(math.floor(min_y / step))
        iy1 = int(math.ceil(max_y / step))
        candidates = []
        center_ang = (a0 + a1) * 0.5
        sector_seed = int(ring["key"]) * 1009 + int(sector_idx) * 9173
        for ix in range(ix0, ix1 + 1):
            x = ix * step
            for iy in range(iy0, iy1 + 1):
                y = iy * step
                radius = math.sqrt(x * x + y * y)
                if radius < r0 or radius > r1:
                    continue
                ang = math.atan2(y, x) % math.tau
                if not self.angle_in_sector(ang, a0, a1):
                    continue
                if self.biome_corridor_weight_at(ang, lane_half_width=0.072) > 0.20:
                    continue
                lane_bias = 1.0 - min(1.0, abs(((ang - center_ang + math.pi) % math.tau) - math.pi) / max(0.001, (a1 - a0) * 0.7))
                hashed = (ix * 92821) ^ (iy * 68917) ^ sector_seed
                keep_score = (hashed & 1023) / 1023.0
                if keep_score > 0.34 + 0.16 * lane_bias:
                    continue
                z = self.world_height_at(x, y)
                candidates.append((keep_score, Vec3(x, y, z)))
        candidates.sort(key=lambda item: item[0])
        max_trees = 26
        if max_x - min_x > step * 5.5:
            max_trees = 34
        if max_x - min_x > step * 7.5:
            max_trees = 42
        max_trees += int(max(0, FOREST_TALL_TREE_BONUS_PER_CHUNK))
        return [pt for _score, pt in candidates[:max_trees]]

    def append_forest_tree_geometry(self, pos: Vec3, height: float, canopy_radius: float, variant: str, trunk_segments, branch_segments, canopy_polys, base_polys):
        trunk_base = Vec3(pos.x, pos.y, pos.z + 0.10)
        trunk_top = Vec3(pos.x, pos.y, pos.z + height)
        trunk_segments.append((trunk_base, trunk_top))
        base_ring = []
        for i in range(6):
            ang = math.tau * i / 6.0
            base_ring.append(Vec3(pos.x + math.cos(ang) * canopy_radius * 0.22, pos.y + math.sin(ang) * canopy_radius * 0.22, pos.z + 0.12))
        base_polys.append(base_ring)
        if variant == "spire":
            tiers = ((0.34, 1.00, 6), (0.56, 0.74, 6), (0.78, 0.48, 5))
            for frac, scale, count in tiers:
                z = pos.z + height * frac
                ring_pts = []
                for i in range(count):
                    ang = math.tau * i / float(count)
                    p = Vec3(pos.x + math.cos(ang) * canopy_radius * scale, pos.y + math.sin(ang) * canopy_radius * scale, z)
                    ring_pts.append(p)
                    branch_segments.append((Vec3(pos.x, pos.y, z + height * 0.05), p))
                canopy_polys.append(ring_pts)
            crown = pos + Vec3(0.0, 0.0, height * 1.05)
            for p in canopy_polys[-1][::2]:
                branch_segments.append((crown, p))
        elif variant == "canopy":
            z1 = pos.z + height * 0.62
            z2 = pos.z + height * 0.84
            for z, scale, count, phase in ((z1, 1.10, 8, 0.0), (z2, 0.76, 7, 0.23)):
                ring_pts = []
                for i in range(count):
                    ang = phase + math.tau * i / float(count)
                    ring_pts.append(Vec3(pos.x + math.cos(ang) * canopy_radius * scale, pos.y + math.sin(ang) * canopy_radius * scale, z))
                canopy_polys.append(ring_pts)
                for p in ring_pts[::2]:
                    branch_segments.append((Vec3(pos.x, pos.y, z - height * 0.12), p))
            crown = pos + Vec3(0.0, 0.0, height * 0.98)
            canopy_polys.append([
                Vec3(pos.x, pos.y + canopy_radius * 0.40, pos.z + height * 0.98),
                Vec3(pos.x + canopy_radius * 0.34, pos.y, pos.z + height * 1.02),
                Vec3(pos.x, pos.y - canopy_radius * 0.40, pos.z + height * 0.98),
                Vec3(pos.x - canopy_radius * 0.34, pos.y, pos.z + height * 1.02),
            ])
            branch_segments.append((trunk_top, crown))
        elif variant == "tower":
            tier_count = 5
            for tier in range(tier_count):
                frac = 0.26 + tier * 0.145
                z = pos.z + height * frac
                count = 7 if tier % 2 == 0 else 6
                scale = 1.16 - tier * 0.145
                ring_pts = []
                for i in range(count):
                    ang = math.tau * i / float(count) + tier * 0.19
                    p = Vec3(pos.x + math.cos(ang) * canopy_radius * scale, pos.y + math.sin(ang) * canopy_radius * scale, z)
                    ring_pts.append(p)
                    if i % 2 == 0:
                        branch_segments.append((Vec3(pos.x, pos.y, z - height * 0.07), p))
                canopy_polys.append(ring_pts)
            crown = pos + Vec3(0.0, 0.0, height * 1.12)
            for p in canopy_polys[-1]:
                branch_segments.append((crown, p))
        else:
            split_z = pos.z + height * 0.52
            left = Vec3(pos.x - canopy_radius * 0.85, pos.y - canopy_radius * 0.18, split_z + height * 0.18)
            right = Vec3(pos.x + canopy_radius * 0.82, pos.y + canopy_radius * 0.16, split_z + height * 0.22)
            branch_segments.append((Vec3(pos.x, pos.y, split_z), left))
            branch_segments.append((Vec3(pos.x, pos.y, split_z + height * 0.04), right))
            for center, radius_scale, z, count, phase in ((left, 0.42, left.z, 5, 0.12), (right, 0.48, right.z, 6, 0.30), (trunk_top, 0.52, trunk_top.z, 6, 0.0)):
                ring_pts = []
                for i in range(count):
                    ang = phase + math.tau * i / float(count)
                    ring_pts.append(Vec3(center.x + math.cos(ang) * canopy_radius * radius_scale, center.y + math.sin(ang) * canopy_radius * radius_scale, z))
                canopy_polys.append(ring_pts)
                for p in ring_pts[::2]:
                    branch_segments.append((center, p))

    def add_solid_tree_mass_batch(self, parent, specs, trunk_rgb, canopy_rgb, name="solid-tree-masses"):
        """Batch opaque low-poly tree mass into one sector Geom.

        Pass 282.45 reuses the accepted faceted solid-tree geometry in Green
        Hills while removing it from the full Forest preview around the Hub.
        The geometry remains visual-only and sector-batched.
        """
        specs = list(specs or [])
        if not specs:
            return None
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData(str(name), fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        color = GeomVertexWriter(vdata, "color")
        tris = GeomTriangles(Geom.UHStatic)
        next_idx = 0

        def emit(point, rgba):
            nonlocal next_idx
            vertex.addData3(float(point.x), float(point.y), float(point.z))
            color.addData4(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
            idx = next_idx
            next_idx += 1
            return idx

        def tri(a, b, c):
            tris.addVertices(int(a), int(b), int(c))
            tris.closePrimitive()

        trunk_base = tuple(max(0.0, min(1.0, float(v) * 0.52)) for v in trunk_rgb[:3]) + (1.0,)
        trunk_top = tuple(max(0.0, min(1.0, float(v) * 0.76)) for v in trunk_rgb[:3]) + (1.0,)
        canopy_shadow = tuple(max(0.0, min(1.0, float(v) * 0.24)) for v in canopy_rgb[:3]) + (1.0,)
        canopy_core = tuple(max(0.0, min(1.0, float(v) * 0.43)) for v in canopy_rgb[:3]) + (1.0,)
        canopy_high = tuple(max(0.0, min(1.0, float(v) * 0.62 + 0.015)) for v in canopy_rgb[:3]) + (1.0,)

        sides = 7
        for spec in specs:
            pos = Vec3(spec["pos"])
            height = max(4.0, float(spec.get("height", 12.0)))
            radius = max(1.4, float(spec.get("radius", 4.0)))
            variant = str(spec.get("variant", "canopy"))

            # Low-poly tapered trunk, batched into the same sector Geom.
            trunk_radius = max(0.30, min(0.95, radius * 0.095))
            trunk_top_z = pos.z + height * (0.72 if variant != "tower" else 0.78)
            bottom_ids = []
            top_ids = []
            for i in range(sides):
                a = math.tau * i / float(sides)
                ca, sa = math.cos(a), math.sin(a)
                bottom_ids.append(emit(Vec3(pos.x + ca * trunk_radius, pos.y + sa * trunk_radius, pos.z + 0.08), trunk_base))
                top_ids.append(emit(Vec3(pos.x + ca * trunk_radius * 0.58, pos.y + sa * trunk_radius * 0.58, trunk_top_z), trunk_top))
            for i in range(sides):
                j = (i + 1) % sides
                tri(bottom_ids[i], bottom_ids[j], top_ids[j])
                tri(bottom_ids[i], top_ids[j], top_ids[i])

            # Variant-aware faceted crown.  This is not new vegetation; it is a
            # low-cost volumetric backing for the existing authored crown lines.
            if variant == "spire":
                rx, ry, rz, center_frac = radius * 0.94, radius * 0.94, max(radius * 1.10, height * 0.24), 0.73
            elif variant == "tower":
                rx, ry, rz, center_frac = radius * 0.82, radius * 0.82, max(radius * 1.28, height * 0.29), 0.70
            elif variant == "split":
                rx, ry, rz, center_frac = radius * 1.08, radius * 0.94, max(radius * 0.76, height * 0.18), 0.77
            else:
                rx, ry, rz, center_frac = radius * 1.14, radius * 1.04, max(radius * 0.68, height * 0.16), 0.77
            center_z = pos.z + height * center_frac
            ring_defs = ((-0.58, 0.58, canopy_shadow), (0.0, 1.00, canopy_core), (0.56, 0.64, canopy_high))
            rings = []
            for ring_idx, (zmul, rmul, rgba) in enumerate(ring_defs):
                ids = []
                phase = 0.20 * ring_idx + (0.11 if variant in {"split", "tower"} else 0.0)
                for i in range(sides):
                    a = phase + math.tau * i / float(sides)
                    wobble = 1.0 + 0.07 * math.sin(a * 3.0 + height * 0.13)
                    ids.append(emit(Vec3(pos.x + math.cos(a) * rx * rmul * wobble, pos.y + math.sin(a) * ry * rmul / wobble, center_z + rz * zmul), rgba))
                rings.append(ids)
            bottom = emit(Vec3(pos.x, pos.y, center_z - rz * 0.96), canopy_shadow)
            top = emit(Vec3(pos.x, pos.y, center_z + rz * 0.98), canopy_high)
            for i in range(sides):
                j = (i + 1) % sides
                tri(bottom, rings[0][j], rings[0][i])
                for r in range(len(rings) - 1):
                    tri(rings[r][i], rings[r][j], rings[r + 1][j])
                    tri(rings[r][i], rings[r + 1][j], rings[r + 1][i])
                tri(rings[-1][i], rings[-1][j], top)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gnode = GeomNode(str(name))
        gnode.addGeom(geom)
        np = parent.attachNewNode(gnode)
        np.setLightOff(1)
        np.setTextureOff(10)
        np.setTransparency(TransparencyAttrib.MNone)
        np.setDepthWrite(True)
        np.setDepthTest(True)
        np.setTwoSided(True)
        np.setPythonTag("solid_tree_mass_count", len(specs))
        np.setPythonTag("solid_tree_mass_batched", 1)
        return np

    def add_forest_mass_batch(self, parent, specs, trunk_rgb, canopy_rgb, name="forest-tree-masses"):
        """Compatibility wrapper for the former Pass 282.30 Forest mass API."""
        np = self.add_solid_tree_mass_batch(parent, specs, trunk_rgb, canopy_rgb, name)
        if np is not None:
            np.setPythonTag("forest_mass_count", len(list(specs or [])))
            np.setPythonTag("forest_mass_batched", 1)
        return np

    def add_forest_understory_batch(self, parent, items, ring, name="forest-understory-masses"):
        """Build one static nature batch for a forest sector.

        Bushes, ferns, grass and deadfall share a single Geom so the denser
        floor does not become hundreds of scene-graph nodes.  Bright contour
        lines are emitted in a second pair of sector batches to preserve the
        HoloVerse hardlight language.  All objects are visual-only.
        """
        items = list(items or [])
        if not items:
            return {"bushes": 0, "ferns": 0, "grass": 0, "deadfall": 0, "geom": None}

        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData(str(name), fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        color = GeomVertexWriter(vdata, "color")
        tris = GeomTriangles(Geom.UHStatic)
        next_idx = 0
        outline_polys = []
        detail_segments = []
        counts = {"bushes": 0, "ferns": 0, "grass": 0, "deadfall": 0}

        def emit(point, rgba):
            nonlocal next_idx
            vertex.addData3(float(point.x), float(point.y), float(point.z))
            color.addData4(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
            idx = next_idx
            next_idx += 1
            return idx

        def tri(a, b, c):
            tris.addVertices(int(a), int(b), int(c))
            tris.closePrimitive()

        # Restrained natural masses under the neon contours.  The values are
        # deliberately darker than the tree outlines so added density improves
        # depth without turning the forest floor into a bright carpet.
        bush_shadow = (0.020, 0.145, 0.042, 1.0)
        bush_core = (0.035, 0.275, 0.070, 1.0)
        bush_high = (0.055, 0.410, 0.095, 1.0)
        fern_core = (0.035, 0.315, 0.085, 1.0)
        fern_high = (0.085, 0.520, 0.125, 1.0)
        grass_core = (0.045, 0.245, 0.065, 1.0)
        grass_high = (0.095, 0.430, 0.100, 1.0)
        log_dark = (0.090, 0.105, 0.055, 1.0)
        log_high = (0.155, 0.180, 0.075, 1.0)
        hardlight = self.biome_color(ring, alpha=0.68, brighten=0.92, channel="accent")
        softlight = self.biome_color(ring, alpha=0.48, brighten=0.72, channel="canopy")

        def emit_bush(center, radius, height, heading, variant):
            # Three profiles: round, split-lobe, and taller thicket.
            axis = Vec3(math.cos(heading), math.sin(heading), 0.0)
            cross = Vec3(-axis.y, axis.x, 0.0)
            # Every shrub is a small uneven thicket rather than one symmetric
            # ellipsoid, which keeps it reading as vegetation instead of rock.
            if int(variant) == 0:
                lobes = [
                    (axis * (-radius * 0.20) + cross * (radius * 0.14), radius * 0.67, height * 0.80),
                    (axis * ( radius * 0.22), radius * 0.78, height * 1.00),
                    (cross * (-radius * 0.20), radius * 0.56, height * 0.68),
                ]
            elif int(variant) == 1:
                lobes = [
                    (axis * (-radius * 0.28), radius * 0.70, height * 0.84),
                    (axis * ( radius * 0.30), radius * 0.77, height * 1.00),
                    (cross * (radius * 0.18), radius * 0.48, height * 0.64),
                ]
            else:
                lobes = [
                    (cross * (-radius * 0.18), radius * 0.60, height * 0.82),
                    (axis * (radius * 0.08), radius * 0.70, height * 1.08),
                    (cross * (radius * 0.22) - axis * (radius * 0.12), radius * 0.50, height * 0.74),
                ]
            for lobe_idx, (offset, rr, hh) in enumerate(lobes):
                c = center + offset
                sides = 7
                rings = []
                ring_defs = ((0.08, 0.72, bush_shadow), (0.45, 1.00, bush_core), (0.78, 0.70, bush_high))
                for ri, (zf, rf, rgba) in enumerate(ring_defs):
                    ids=[]
                    pts=[]
                    phase = heading + 0.18 * ri + 0.27 * lobe_idx
                    for i in range(sides):
                        a = phase + math.tau * i / sides
                        wobble = 1.0 + 0.10 * math.sin(a * 3.0 + variant)
                        p = Vec3(c.x + math.cos(a) * rr * rf * wobble, c.y + math.sin(a) * rr * rf / wobble, c.z + hh * zf)
                        ids.append(emit(p, rgba))
                        pts.append(p + Vec3(0,0,0.025))
                    rings.append(ids)
                    if ri == 1:
                        outline_polys.append(pts)
                bottom = emit(Vec3(c.x, c.y, c.z + 0.04), bush_shadow)
                top = emit(Vec3(c.x, c.y, c.z + hh), bush_high)
                for i in range(sides):
                    j=(i+1)%sides
                    tri(bottom, rings[0][j], rings[0][i])
                    for r in range(len(rings)-1):
                        tri(rings[r][i], rings[r][j], rings[r+1][j])
                        tri(rings[r][i], rings[r+1][j], rings[r+1][i])
                    tri(rings[-1][i], rings[-1][j], top)

        def emit_fern(center, radius, height, heading, variant):
            fronds = 5 + (int(variant) % 2)
            for i in range(fronds):
                a = heading + math.tau * i / fronds + 0.11 * variant
                d = Vec3(math.cos(a), math.sin(a), 0.0)
                side = Vec3(-d.y, d.x, 0.0)
                tip = center + d * radius + Vec3(0,0,height * (0.58 + 0.18 * ((i+variant)%3)))
                mid = center + d * (radius * 0.52) + Vec3(0,0,height * 0.48)
                left = mid + side * (radius * 0.20) + Vec3(0,0,-height*0.08)
                right = mid - side * (radius * 0.20) + Vec3(0,0,-height*0.08)
                b = emit(center + Vec3(0,0,0.04), fern_core)
                l = emit(left, fern_high)
                t = emit(tip, fern_high)
                r = emit(right, fern_core)
                tri(b,l,t); tri(b,t,r)
                detail_segments.append((center + Vec3(0,0,0.08), tip + Vec3(0,0,0.03)))

        def emit_grass(center, radius, height, heading, variant):
            blades = 4 + int(variant)
            for i in range(blades):
                a = heading + (i - (blades-1)*0.5) * 0.34
                d = Vec3(math.cos(a), math.sin(a), 0.0)
                side = Vec3(-d.y, d.x, 0.0)
                h = height * (0.72 + 0.10 * ((i + variant) % 4))
                root = center + d * (radius * 0.10)
                tip = root + d * (radius * (0.35 + 0.08*i)) + Vec3(0,0,h)
                width = radius * 0.12
                a0 = emit(root - side * width + Vec3(0,0,0.03), grass_core)
                a1 = emit(root + side * width + Vec3(0,0,0.03), grass_core)
                at = emit(tip, grass_high)
                tri(a0,a1,at)
                detail_segments.append((root + Vec3(0,0,0.06), tip + Vec3(0,0,0.02)))

        def emit_deadfall(center, half_len, height, heading, variant):
            axis = Vec3(math.cos(heading), math.sin(heading), 0.0)
            side = Vec3(-axis.y, axis.x, 0.0)
            ends = [center - axis * half_len, center + axis * half_len]
            rings=[]
            sides=6
            rad=max(0.22, height*0.42)
            for ei,end in enumerate(ends):
                ids=[]
                for i in range(sides):
                    a=math.tau*i/sides
                    p=end + side*(math.cos(a)*rad) + Vec3(0,0,rad + math.sin(a)*rad)
                    ids.append(emit(p, log_dark if ei==0 else log_high))
                rings.append(ids)
            for i in range(sides):
                j=(i+1)%sides
                tri(rings[0][i],rings[0][j],rings[1][j])
                tri(rings[0][i],rings[1][j],rings[1][i])
            detail_segments.append((ends[0] + Vec3(0,0,rad*2.0+0.03), ends[1] + Vec3(0,0,rad*2.0+0.03)))
            if int(variant) == 1:
                branch_dir = Vec3(math.cos(heading+0.9), math.sin(heading+0.9), 0.0)
                detail_segments.append((center + Vec3(0,0,rad*1.8), center + branch_dir*(half_len*0.45) + Vec3(0,0,rad*2.8)))

        for item in items:
            ground = self.world_height_at(float(item.x), float(item.y))
            center = Vec3(float(item.x), float(item.y), ground + 0.06)
            kind = str(item.kind)
            if kind == "bush":
                emit_bush(center, float(item.radius), float(item.height), float(item.heading), int(item.variant)); counts["bushes"] += 1
            elif kind == "fern":
                emit_fern(center, float(item.radius), float(item.height), float(item.heading), int(item.variant)); counts["ferns"] += 1
            elif kind == "grass":
                emit_grass(center, float(item.radius), float(item.height), float(item.heading), int(item.variant)); counts["grass"] += 1
            elif kind == "deadfall":
                emit_deadfall(center, float(item.radius), float(item.height), float(item.heading), int(item.variant)); counts["deadfall"] += 1

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gnode = GeomNode(str(name))
        gnode.addGeom(geom)
        np = parent.attachNewNode(gnode)
        np.setLightOff(1)
        np.setTextureOff(10)
        np.setTransparency(TransparencyAttrib.MNone)
        np.setDepthWrite(True)
        np.setDepthTest(True)
        np.setTwoSided(True)
        np.setPythonTag("forest_understory_batched", 1)
        np.setPythonTag("forest_understory_item_count", len(items))
        if outline_polys:
            self.add_polyline_batch(parent, outline_polys, hardlight, self.cfg.line_thickness * 0.30, True, f"{name}-bush-outlines")
        if detail_segments:
            self.add_line_segments(parent, detail_segments, softlight, self.cfg.line_thickness * 0.24, f"{name}-detail-lines")
        counts["geom"] = np
        return counts

    def make_sector_detail_lod_parent(self, parent, ring, sector_idx: int, a0: float, a1: float, far_distance: float, name: str):
        """Create one Panda LOD child for a whole sector detail layer.

        The geometry below the returned node is one detail level and disappears
        beyond ``far_distance``.  Keeping the LOD at sector granularity preserves
        the existing culling hierarchy instead of flattening an entire biome.
        """
        lod = LODNode(str(name))
        lod.addSwitch(float(far_distance), 0.0)
        mid_a = (float(a0) + float(a1)) * 0.5
        mid_r = (float(ring["r0"]) + float(ring["r1"])) * 0.5
        cx = math.cos(mid_a) * mid_r
        cy = math.sin(mid_a) * mid_r
        cz = self.world_height_at(cx, cy)
        lod.setCenter(Vec3(cx, cy, cz))
        lod_np = parent.attachNewNode(lod)
        detail_root = lod_np.attachNewNode(f"{name}-near")
        lod_np.setPythonTag("distance_lod_far", float(far_distance))
        lod_np.setPythonTag("distance_lod_sector", int(sector_idx))
        return detail_root

    def build_forest_understory_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        if str(ring.get("kind", "")) != "forest":
            return {"bushes": 0, "ferns": 0, "grass": 0, "deadfall": 0}
        forest_travel = region_travel_for_number(1) or {}
        items = generate_forest_understory_items(
            int(sector_idx), float(ring["r0"]), float(ring["r1"]),
            sector_count=BIOME_SECTOR_COUNT,
            corridor_degrees=BIOME_CORRIDOR_DEGREES,
            vanta_radius=float(forest_travel.get("radius", float(ring["r0"]))),
            landing_radius=float(forest_travel.get("landing_radius", float(ring["r0"]))),
            anchor_angle_deg=BIOME_ANCHOR_ANGLE_DEG,
        )
        expected = {kind: sum(1 for item in items if str(item.kind) == kind) for kind in ("bush", "fern", "grass", "deadfall")}
        counts = {"bushes": expected["bush"], "ferns": expected["fern"], "grass": expected["grass"], "deadfall": expected["deadfall"]}

        # The Hub sees Forest only as a 310+ metre horizon.  Grass, ferns and
        # low shrubs are sub-pixel there, but used to account for most Forest
        # triangles.  Keep their authored data/counts and instantiate them when
        # the player actually enters Forest.
        player_r = math.hypot(float(self.player_pos.x), float(self.player_pos.y))
        hub_preview = player_r <= float(MAIN_AREA_RADIUS)
        if hub_preview:
            parent.setPythonTag("forest_understory_geometry_enabled", 0)
            parent.setPythonTag("forest_understory_hub_preview_culled", 1)
            return counts

        detail_parent = self.make_sector_detail_lod_parent(
            parent, ring, sector_idx, a0, a1, FOREST_UNDERSTORY_LOD_FAR,
            f"forest-understory-lod-{int(sector_idx):02d}",
        )
        result = self.add_forest_understory_batch(detail_parent, items, ring, f"forest-understory-{ring['name']}-{int(sector_idx):02d}")
        parent.setPythonTag("forest_understory_geometry_enabled", 1)
        parent.setPythonTag("forest_understory_hub_preview_culled", 0)
        parent.setPythonTag("forest_understory_lod_far", float(FOREST_UNDERSTORY_LOD_FAR))
        return {k: int(result.get(k, 0)) for k in ("bushes", "ferns", "grass", "deadfall")}

    def build_forest_tree_set(self, parent, ring, sector_idx: int, a0: float, a1: float, trunk_color, canopy_color):
        points = self.forest_tree_candidate_points(ring, sector_idx, a0, a1)
        if not points:
            parent.setPythonTag("forest_tree_count", 0)
            return 0
        trunk_segments = []
        branch_segments = []
        canopy_polys = []
        base_polys = []
        seed = (int(ring["key"]) * 65537) + int(sector_idx) * 31337
        rng = random.Random(seed)
        variants = list(self.forest_tree_variants)
        tall_count = 0
        mass_specs = []
        for idx, pos in enumerate(points):
            height = rng.uniform(15.0, 31.0)
            if (idx + sector_idx) % 5 == 0:
                height *= 1.32
                tall_count += 1
            canopy_radius = rng.uniform(3.6, 8.2)
            variant = variants[(idx + rng.randint(0, len(variants) - 1)) % len(variants)]
            mass_specs.append({"pos": Vec3(pos), "height": float(height), "radius": float(canopy_radius), "variant": str(variant)})
            self.append_forest_tree_geometry(pos, height, canopy_radius, variant, trunk_segments, branch_segments, canopy_polys, base_polys)
        forest_render_pass = str(ring.get("kind", "")) == "forest"
        # Pass 282.45: retain every accepted holographic Forest tree/branch/crown
        # but remove the later opaque backing mass from the Hub's full-ring preview.
        # The solid-tree family now belongs to Green Hills instead.
        parent.setPythonTag("forest_tree_mass_count", 0)
        if trunk_segments:
            self.add_line_segments(parent, trunk_segments, trunk_color, self.cfg.line_thickness * 0.82, f"forest-tree-trunks-{ring['name']}")
        if branch_segments:
            branch_color = self.biome_color(ring, alpha=0.78 if forest_render_pass else 0.86, brighten=0.74, channel="soft") if forest_render_pass else canopy_color
            self.add_line_segments(parent, branch_segments, branch_color, self.cfg.line_thickness * 0.54, f"forest-tree-branches-{ring['name']}")
        if canopy_polys:
            if forest_render_pass:
                shadow_polys = canopy_polys[0::3]
                core_polys = canopy_polys[1::3]
                highlight_polys = canopy_polys[2::3]
                shadow_color = rgb_to_rgba((0.055, 0.370, 0.115), 0.72, 1.0)
                core_color = canopy_color
                highlight_color = self.biome_color(ring, alpha=0.86, brighten=1.08, channel="accent")
                if shadow_polys:
                    self.add_polyline_batch(parent, shadow_polys, shadow_color, self.cfg.line_thickness * 0.40, True, f"forest-tree-canopy-shadow-{ring['name']}")
                if core_polys:
                    self.add_polyline_batch(parent, core_polys, core_color, self.cfg.line_thickness * 0.48, True, f"forest-tree-canopy-core-{ring['name']}")
                if highlight_polys:
                    self.add_polyline_batch(parent, highlight_polys, highlight_color, self.cfg.line_thickness * 0.52, True, f"forest-tree-canopy-highlight-{ring['name']}")
            else:
                self.add_polyline_batch(parent, canopy_polys, canopy_color, self.cfg.line_thickness * 0.44, True, f"forest-tree-canopies-{ring['name']}")
        if base_polys:
            self.add_polyline_batch(parent, base_polys, trunk_color, self.cfg.line_thickness * 0.38, True, f"forest-tree-bases-{ring['name']}")
        parent.setPythonTag("forest_tree_count", len(points))
        parent.setPythonTag("forest_tall_tree_count", tall_count)
        return len(points)

    def build_forest_dense_detail_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        """Repeat the established verdant-canopy vegetation across FORESTS.

        Pass 282.21 deliberately reuses the live forest's richest authored
        vegetation language: five curved vine trunks with broad crowns.  The
        old implementation put one such pocket in only one out of five sectors.
        Here, five deterministic pockets are distributed through every streamed
        forest sector.  They remain visual-only and are emitted as sector-level
        batches, preserving the existing collision and streaming authorities.
        """
        if str(ring.get("kind", "")) != "forest":
            return {"patches": 0, "detail_trees": 0, "crowns": 0}
        forest_travel = region_travel_for_number(1) or {}
        patches = generate_forest_detail_patches(
            int(sector_idx),
            float(ring["r0"]),
            float(ring["r1"]),
            sector_count=BIOME_SECTOR_COUNT,
            corridor_degrees=BIOME_CORRIDOR_DEGREES,
            vanta_radius=float(forest_travel.get("radius", float(ring["r0"]) + (float(ring["r1"]) - float(ring["r0"])) * 0.30)),
            landing_radius=float(forest_travel.get("landing_radius", float(ring["r0"]) + (float(ring["r1"]) - float(ring["r0"])) * 0.30 - 48.0)),
            anchor_angle_deg=BIOME_ANCHOR_ANGLE_DEG,
        )
        if not patches:
            return {"patches": 0, "detail_trees": 0, "crowns": 0}

        vine = (0.12, 1.0, 0.42, 0.86)
        canopy = (0.38, 1.0, 0.30, 0.76)
        trunk_polys = []
        crown_polys = []
        detail_trees = 0

        # Five-plant asymmetric group derived from the old verdant-canopy oasis.
        # Its footprint is intentionally kept inside each validated patch circle.
        local_pattern = (
            (-0.50, -0.18),
            (-0.22, 0.30),
            (0.04, -0.36),
            (0.34, 0.22),
            (0.58, -0.04),
        )
        for patch in patches:
            radial = Vec3(math.cos(patch.angle), math.sin(patch.angle), 0.0)
            tangent = Vec3(-radial.y, radial.x, 0.0)
            center = Vec3(radial.x * patch.radius, radial.y * patch.radius, 0.0)
            center.z = self.world_height_at(center.x, center.y)
            plant_radius = float(patch.patch_radius) * 0.70
            for idx, (ru, tu) in enumerate(local_pattern):
                x = center.x + radial.x * (ru * plant_radius) + tangent.x * (tu * plant_radius)
                y = center.y + radial.y * (ru * plant_radius) + tangent.y * (tu * plant_radius)
                z = self.world_height_at(x, y)
                h = (18.0 + (idx % 3) * 7.0) * float(patch.scale)

                # Preserve the old curved five-step trunk construction.
                trunk = []
                for step in range(5):
                    f = step / 4.0
                    bend = math.sin(f * math.pi + idx + patch.phase) * 1.8 * float(patch.scale)
                    trunk.append(Vec3(
                        x + tangent.x * bend,
                        y + tangent.y * bend,
                        z + h * f,
                    ))
                trunk_polys.append(trunk)

                # Preserve the old broad ten-point canopy profile and height rhythm.
                crown_z = z + h
                rx = (5.0 + idx * 0.35) * float(patch.scale)
                ry = (4.2 + idx * 0.25) * float(patch.scale)
                crown = []
                for point_idx in range(10):
                    aa = patch.phase + math.tau * point_idx / 10.0
                    crown.append(Vec3(
                        x + math.cos(aa) * rx,
                        y + math.sin(aa) * ry,
                        crown_z + math.sin(aa * 2.0) * 0.9 * float(patch.scale),
                    ))
                crown_polys.append(crown)
                detail_trees += 1

        if trunk_polys:
            self.add_polyline_batch(parent, trunk_polys, vine, self.cfg.line_thickness * 0.52, False, f"forest-verdant-trunks-{ring['name']}")
        if crown_polys:
            self.add_polyline_batch(parent, crown_polys, canopy, self.cfg.line_thickness * 0.40, True, f"forest-verdant-crowns-{ring['name']}")

        return {
            "patches": len(patches),
            "detail_trees": int(detail_trees),
            "crowns": int(len(crown_polys)),
        }

    def hill_flower_grid_step(self, ring) -> float:
        span = max(160.0, float(ring["r1"]) - float(ring["r0"]))
        return max(72.0, min(108.0, span / 18.0))

    def hill_flower_candidate_points(self, ring, sector_idx: int, a0: float, a1: float):
        if str(ring.get("kind", "")) != "hills":
            return []
        step = self.hill_flower_grid_step(ring)
        r0 = float(ring["r0"]) + step * 0.55
        r1 = float(ring["r1"]) - step * 0.55
        if r1 <= r0:
            return []
        sample_points = []
        for radius in (r0, (r0 + r1) * 0.5, r1):
            for ang in (a0, (a0 + a1) * 0.5, a1):
                sample_points.append((math.cos(ang) * radius, math.sin(ang) * radius))
        min_x = min(p[0] for p in sample_points) - step
        max_x = max(p[0] for p in sample_points) + step
        min_y = min(p[1] for p in sample_points) - step
        max_y = max(p[1] for p in sample_points) + step
        ix0 = int(math.floor(min_x / step))
        ix1 = int(math.ceil(max_x / step))
        iy0 = int(math.floor(min_y / step))
        iy1 = int(math.ceil(max_y / step))
        candidates = []
        center_ang = (a0 + a1) * 0.5
        sector_seed = int(ring["key"]) * 12011 + int(sector_idx) * 48731
        for ix in range(ix0, ix1 + 1):
            x = ix * step
            for iy in range(iy0, iy1 + 1):
                y = iy * step
                radius = math.sqrt(x * x + y * y)
                if radius < r0 or radius > r1:
                    continue
                ang = math.atan2(y, x) % math.tau
                if not self.angle_in_sector(ang, a0, a1):
                    continue
                if self.biome_corridor_weight_at(ang, lane_half_width=0.076) > 0.18:
                    continue
                hashed = (ix * 193513) ^ (iy * 83492791) ^ sector_seed
                keep_score = (hashed & 2047) / 2047.0
                center_bias = 1.0 - min(1.0, abs(((ang - center_ang + math.pi) % math.tau) - math.pi) / max(0.001, (a1 - a0) * 0.68))
                threshold = 0.22 + 0.22 * center_bias
                if keep_score > threshold:
                    continue
                z = self.world_height_at(x, y)
                candidates.append((keep_score, Vec3(x, y, z)))
        candidates.sort(key=lambda item: item[0])
        max_flowers = 36
        if max_x - min_x > step * 5.5:
            max_flowers = 44
        return [pt for _score, pt in candidates[:max_flowers]]

    def build_hills_solid_tree_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        if str(ring.get("kind", "")) != "hills":
            return 0
        hills_travel = region_travel_for_number(2) or {}
        items = generate_hills_solid_tree_items(
            sector_idx, float(ring["r0"]), float(ring["r1"]),
            sector_count=BIOME_SECTOR_COUNT, corridor_degrees=BIOME_CORRIDOR_DEGREES,
            nyx_radius=float(hills_travel.get("radius", (float(ring["r0"])+float(ring["r1"]))*0.5)),
            landing_radius=float(hills_travel.get("landing_radius", float(ring["r0"])+80.0)),
            anchor_angle_deg=BIOME_ANCHOR_ANGLE_DEG,
        )
        if not items:
            parent.setPythonTag("hills_solid_tree_count", 0)
            return 0
        specs = []
        for item in items:
            specs.append({
                "pos": Vec3(float(item.x), float(item.y), self.world_height_at(float(item.x), float(item.y))),
                "height": float(item.height), "radius": float(item.radius), "variant": str(item.variant),
            })
        trunk_color = self.biome_color(ring, alpha=1.0, brighten=0.58, channel="soft")
        canopy_color = self.biome_color(ring, alpha=1.0, brighten=0.82, channel="canopy")
        node = self.add_solid_tree_mass_batch(
            parent, specs, tuple(float(v) for v in trunk_color[:3]), tuple(float(v) for v in canopy_color[:3]),
            f"hills-solid-tree-masses-{int(sector_idx):02d}",
        )
        count = len(specs) if node is not None else 0
        if node is not None:
            node.setPythonTag("hills_solid_tree_count", count)
            node.setPythonTag("hills_solid_tree_batched", 1)
        parent.setPythonTag("hills_solid_tree_count", count)
        parent.setPythonTag("hills_solid_tree_batched", 1 if count else 0)
        return count

    def build_hill_flower_set(self, parent, ring, sector_idx: int, a0: float, a1: float, stem_color, petal_color):
        points = self.hill_flower_candidate_points(ring, sector_idx, a0, a1)
        if not points:
            parent.setPythonTag("hill_flower_count", 0)
            return 0
        stem_segments = []
        leaf_segments = []
        petal_polys = []
        blossom_rings = []
        seed = (int(ring["key"]) * 91081) + int(sector_idx) * 17749
        rng = random.Random(seed)
        for idx, pos in enumerate(points):
            height = rng.uniform(2.4, 5.6)
            flower_r = rng.uniform(0.90, 1.80)
            stem_base = Vec3(pos.x, pos.y, pos.z + 0.08)
            stem_top = Vec3(pos.x, pos.y, pos.z + height)
            stem_segments.append((stem_base, stem_top))
            for frac, yaw in ((0.42, 0.0), (0.68, math.pi * 0.5)):
                leaf_z = pos.z + height * frac
                leaf_r = flower_r * (0.72 if frac < 0.5 else 0.52)
                dx = math.cos(yaw) * leaf_r
                dy = math.sin(yaw) * leaf_r
                leaf_segments.append((Vec3(pos.x - dx, pos.y - dy, leaf_z - 0.06), Vec3(pos.x + dx, pos.y + dy, leaf_z + 0.06)))
            center = Vec3(pos.x, pos.y, pos.z + height)
            phase = rng.random() * math.tau
            petal_count = 5 if idx % 3 else 6
            for petal_idx in range(petal_count):
                ang = phase + math.tau * petal_idx / float(petal_count)
                side = ang + math.pi * 0.5
                tip = Vec3(center.x + math.cos(ang) * flower_r, center.y + math.sin(ang) * flower_r, center.z + 0.08)
                left = Vec3(center.x + math.cos(ang) * flower_r * 0.38 + math.cos(side) * flower_r * 0.22, center.y + math.sin(ang) * flower_r * 0.38 + math.sin(side) * flower_r * 0.22, center.z - 0.05)
                right = Vec3(center.x + math.cos(ang) * flower_r * 0.38 - math.cos(side) * flower_r * 0.22, center.y + math.sin(ang) * flower_r * 0.38 - math.sin(side) * flower_r * 0.22, center.z - 0.05)
                petal_polys.append([center, left, tip, right])
            blossom_rings.append([
                Vec3(center.x + flower_r * 0.20, center.y, center.z),
                Vec3(center.x, center.y + flower_r * 0.20, center.z + 0.03),
                Vec3(center.x - flower_r * 0.20, center.y, center.z),
                Vec3(center.x, center.y - flower_r * 0.20, center.z + 0.03),
            ])
        detail_parent = self.make_sector_detail_lod_parent(
            parent, ring, sector_idx, a0, a1, HILLS_MEADOW_LOD_FAR,
            f"hills-meadow-lod-{int(sector_idx):02d}",
        )
        if stem_segments:
            self.add_line_segments(detail_parent, stem_segments, stem_color, self.cfg.line_thickness * 0.66, f"hill-flower-stems-{ring['name']}")
        if leaf_segments:
            self.add_line_segments(detail_parent, leaf_segments, stem_color, self.cfg.line_thickness * 0.50, f"hill-flower-leaves-{ring['name']}")
        if petal_polys:
            self.add_polyline_batch(detail_parent, petal_polys, petal_color, self.cfg.line_thickness * 0.46, True, f"hill-flower-petals-{ring['name']}")
        if blossom_rings:
            self.add_polyline_batch(detail_parent, blossom_rings, petal_color, self.cfg.line_thickness * 0.34, True, f"hill-flower-centers-{ring['name']}")
        solid_count = self.build_hill_solid_plant_set(detail_parent, ring, sector_idx, a0, a1, points)
        parent.setPythonTag("hill_flower_count", len(points) + solid_count)
        parent.setPythonTag("hill_solid_plant_count", solid_count)
        parent.setPythonTag("hill_meadow_shape_count", solid_count)
        parent.setPythonTag("hills_lime_ground_collision_authority", 1)
        parent.setPythonTag("hills_meadow_lod_far", float(HILLS_MEADOW_LOD_FAR))
        return len(points) + solid_count

    def build_hill_solid_plant_set(self, parent, ring, sector_idx: int, a0: float, a1: float, existing_points=None):
        """Build Green Hills meadow masses as one static sector batch.

        Pass 282.32 replaces hundreds of per-plant NodePaths with a single Geom
        per sector.  The visual language remains open meadow: low shrubs, grass,
        stones and tall seed heads.  These objects are visual-only; terrain height
        remains the movement/collision authority.
        """
        if str(ring.get("kind", "")) != "hills":
            return 0
        travel = region_travel_for_number(2) or {}
        items = generate_hills_meadow_items(
            int(sector_idx), float(ring["r0"]), float(ring["r1"]),
            sector_count=BIOME_SECTOR_COUNT,
            corridor_degrees=BIOME_CORRIDOR_DEGREES,
            nyx_radius=float(travel.get("radius", 1222.2)),
            landing_radius=float(travel.get("landing_radius", 1167.8)),
            anchor_angle_deg=BIOME_ANCHOR_ANGLE_DEG,
        )
        if not items:
            parent.setPythonTag("hill_meadow_shape_count", 0)
            return 0

        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData(f"hills-meadow-{int(sector_idx):02d}", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        color = GeomVertexWriter(vdata, "color")
        tris = GeomTriangles(Geom.UHStatic)
        next_idx = 0
        contour_polys = []
        detail_segments = []

        grass_dark = (0.050, 0.250, 0.045, 1.0)
        grass_mid = (0.110, 0.440, 0.070, 1.0)
        grass_high = (0.250, 0.650, 0.090, 1.0)
        shrub_dark = (0.040, 0.180, 0.035, 1.0)
        shrub_mid = (0.090, 0.330, 0.050, 1.0)
        shrub_high = (0.190, 0.520, 0.075, 1.0)
        stone_dark = (0.105, 0.125, 0.072, 1.0)
        stone_high = (0.235, 0.275, 0.120, 1.0)
        seed_dark = (0.135, 0.220, 0.050, 1.0)
        seed_high = (0.690, 0.900, 0.120, 1.0)
        hardlight = self.biome_color(ring, alpha=0.62, brighten=0.96, channel="accent")
        softlight = self.biome_color(ring, alpha=0.40, brighten=0.72, channel="line")

        def emit(point, rgba):
            nonlocal next_idx
            vertex.addData3(float(point.x), float(point.y), float(point.z))
            color.addData4(*map(float, rgba))
            idx = next_idx
            next_idx += 1
            return idx

        def tri(a, b, c):
            tris.addVertices(int(a), int(b), int(c)); tris.closePrimitive()

        def grass(center, radius, height, heading, variant):
            blades = 5 + int(variant)
            for i in range(blades):
                a = heading + (i - (blades - 1) * 0.5) * 0.26
                d = Vec3(math.cos(a), math.sin(a), 0.0)
                side = Vec3(-d.y, d.x, 0.0)
                root = center + d * radius * 0.10
                h = height * (0.72 + 0.08 * ((i + variant) % 4))
                tip = root + d * radius * (0.45 + 0.07 * i) + Vec3(0, 0, h)
                width = radius * 0.11
                i0=emit(root-side*width+Vec3(0,0,0.03),grass_dark)
                i1=emit(root+side*width+Vec3(0,0,0.03),grass_mid)
                it=emit(tip,grass_high)
                tri(i0,i1,it)
                detail_segments.append((root+Vec3(0,0,0.05),tip+Vec3(0,0,0.02)))

        def shrub(center, radius, height, heading, variant):
            axis=Vec3(math.cos(heading),math.sin(heading),0); cross=Vec3(-axis.y,axis.x,0)
            lobes=((axis*-0.22+cross*0.12,0.72,0.82),(axis*0.25,0.82,1.0),(cross*-0.20,0.58,0.68))
            for li,(off,rs,hs) in enumerate(lobes):
                c=center+off*radius; rr=radius*rs; hh=height*hs; sides=6
                low=[]; mid=[]; top=[]; outline=[]
                for i in range(sides):
                    a=heading+0.17*li+math.tau*i/sides
                    wob=1.0+0.08*math.sin(a*3.0+variant)
                    p0=Vec3(c.x+math.cos(a)*rr*0.72*wob,c.y+math.sin(a)*rr*0.72/wob,c.z+hh*0.12)
                    p1=Vec3(c.x+math.cos(a)*rr*wob,c.y+math.sin(a)*rr/wob,c.z+hh*0.48)
                    p2=Vec3(c.x+math.cos(a)*rr*0.54,c.y+math.sin(a)*rr*0.54,c.z+hh*0.80)
                    low.append(emit(p0,shrub_dark)); mid.append(emit(p1,shrub_mid)); top.append(emit(p2,shrub_high)); outline.append(p1+Vec3(0,0,0.02))
                apex=emit(Vec3(c.x,c.y,c.z+hh),shrub_high)
                for i in range(sides):
                    j=(i+1)%sides
                    tri(low[i],low[j],mid[j]); tri(low[i],mid[j],mid[i])
                    tri(mid[i],mid[j],top[j]); tri(mid[i],top[j],top[i]); tri(top[i],top[j],apex)
                contour_polys.append(outline)

        def stone(center, radius, height, heading, variant):
            sides=7; base=[]; shoulder=[]; top=[]
            phase=heading+variant*0.23
            for i in range(sides):
                a=phase+math.tau*i/sides; wob=0.82+0.16*math.sin(a*3.0+variant)
                base.append(emit(Vec3(center.x+math.cos(a)*radius*wob,center.y+math.sin(a)*radius/wob,center.z+0.03),stone_dark))
                shoulder.append(emit(Vec3(center.x+math.cos(a)*radius*0.82,center.y+math.sin(a)*radius*0.82,center.z+height*0.52),stone_high))
                top.append(Vec3(center.x+math.cos(a)*radius*0.38,center.y+math.sin(a)*radius*0.38,center.z+height*0.88))
            apex=emit(Vec3(center.x,center.y,center.z+height),stone_high)
            for i in range(sides):
                j=(i+1)%sides
                ti=emit(top[i],stone_high); tj=emit(top[j],stone_high)
                tri(base[i],base[j],shoulder[j]); tri(base[i],shoulder[j],shoulder[i])
                tri(shoulder[i],shoulder[j],tj); tri(shoulder[i],tj,ti); tri(ti,tj,apex)
            contour_polys.append([Vec3(center.x+math.cos(phase+math.tau*i/sides)*radius*0.82,center.y+math.sin(phase+math.tau*i/sides)*radius*0.82,center.z+height*0.54) for i in range(sides)])

        def seedhead(center, radius, height, heading, variant):
            d=Vec3(math.cos(heading),math.sin(heading),0); side=Vec3(-d.y,d.x,0)
            base=center+Vec3(0,0,0.03); top=center+Vec3(0,0,height)
            w=max(0.08,radius*0.12)
            i0=emit(base-side*w,seed_dark); i1=emit(base+side*w,seed_dark); i2=emit(top+side*w*0.35,seed_high); i3=emit(top-side*w*0.35,seed_high)
            tri(i0,i1,i2); tri(i0,i2,i3)
            detail_segments.append((base+Vec3(0,0,0.04),top))
            head_r=radius*(0.55+0.08*variant); sides=6; ring_ids=[]; ring_pts=[]
            for i in range(sides):
                a=heading+math.tau*i/sides
                p=top+Vec3(math.cos(a)*head_r,math.sin(a)*head_r,math.sin(a*2.0)*head_r*0.22)
                ring_ids.append(emit(p,seed_high)); ring_pts.append(p+Vec3(0,0,0.02))
            c=emit(top,seed_high)
            for i in range(sides): tri(c,ring_ids[i],ring_ids[(i+1)%sides])
            contour_polys.append(ring_pts)

        for item in items:
            center=Vec3(float(item.x),float(item.y),self.world_height_at(float(item.x),float(item.y))+0.06)
            if item.kind=="grass": grass(center,float(item.radius),float(item.height),float(item.heading),int(item.variant))
            elif item.kind=="shrub": shrub(center,float(item.radius),float(item.height),float(item.heading),int(item.variant))
            elif item.kind=="stone": stone(center,float(item.radius),float(item.height),float(item.heading),int(item.variant))
            else: seedhead(center,float(item.radius),float(item.height),float(item.heading),int(item.variant))

        geom=Geom(vdata); geom.addPrimitive(tris)
        gnode=GeomNode(f"hills-meadow-{int(sector_idx):02d}"); gnode.addGeom(geom)
        np=parent.attachNewNode(gnode)
        np.setLightOff(1); np.setTextureOff(10); np.setTransparency(TransparencyAttrib.MNone); np.setDepthWrite(True); np.setDepthTest(True); np.setTwoSided(True)
        np.setPythonTag("hills_meadow_batched",1); np.setPythonTag("hills_meadow_item_count",len(items))
        if contour_polys:
            self.add_polyline_batch(parent,contour_polys,hardlight,self.cfg.line_thickness*0.26,True,f"hills-meadow-contours-{int(sector_idx):02d}")
        if detail_segments:
            self.add_line_segments(parent,detail_segments,softlight,self.cfg.line_thickness*0.22,f"hills-meadow-details-{int(sector_idx):02d}")
        parent.setPythonTag("hill_meadow_shape_count",len(items))
        parent.setPythonTag("hills_meadow_pass28232",1)
        return len(items)

    def desert_pyramid_candidate_specs(self, ring, sector_idx: int, a0: float, a1: float):
        if str(ring.get("kind", "")) != "desert":
            return []
        # Pass 282.36: geometric pyramids remain as occasional HoloVerse ruins/
        # landmarks, not a continuous artificial skyline. Natural dunes, mesas,
        # and rocks are now the Desert's dominant grammar.
        if int(sector_idx) % 4 != 0:
            return []
        step = 156.0
        inset = step * 0.55
        r0 = float(ring["r0"]) + inset
        r1 = float(ring["r1"]) - inset
        if r1 <= r0:
            return []
        sample_points = []
        for radius in (r0, (r0 + r1) * 0.5, r1):
            for ang in (a0, (a0 + a1) * 0.5, a1):
                sample_points.append((math.cos(ang) * radius, math.sin(ang) * radius))
        min_x = min(p[0] for p in sample_points) - step
        max_x = max(p[0] for p in sample_points) + step
        min_y = min(p[1] for p in sample_points) - step
        max_y = max(p[1] for p in sample_points) + step
        ix0 = int(math.floor(min_x / step))
        ix1 = int(math.ceil(max_x / step))
        iy0 = int(math.floor(min_y / step))
        iy1 = int(math.ceil(max_y / step))
        specs = []
        seen = set()
        sector_seed = int(ring["key"]) * 15101 + int(sector_idx) * 7607

        def add_spec(x: float, y: float, base_size: float, height: float, hero: bool = False):
            key = (int(round(x / step)), int(round(y / step)))
            if key in seen:
                return
            seen.add(key)
            pos = Vec3(x, y, self.world_height_at(x, y))
            facing = Vec3(-x, -y, 0.0)
            if facing.lengthSquared() < 0.001:
                facing = Vec3(0.0, 1.0, 0.0)
            else:
                facing.normalize()
            specs.append({"pos": pos, "facing": facing, "base": base_size, "height": height, "hero": hero})

        # Seed a few larger pyramids so the biome reads as a field of pyramids,
        # not a single hero monument.
        for idx, (u, rt, base_size) in enumerate(((0.20, 0.34, 92.0), (0.48, 0.56, 104.0), (0.78, 0.74, 90.0))):
            ang = lerp(a0, a1, u)
            corridor = self.biome_corridor_weight_at(ang, lane_half_width=0.072)
            if corridor > 0.22:
                continue
            radius = lerp(r0, r1, rt)
            x = round((math.cos(ang) * radius) / step) * step
            y = round((math.sin(ang) * radius) / step) * step
            add_spec(x, y, base_size, base_size * (0.90 + 0.04 * idx), hero=(idx == 1))

        for ix in range(ix0, ix1 + 1):
            x = ix * step
            for iy in range(iy0, iy1 + 1):
                y = iy * step
                radius = math.sqrt(x * x + y * y)
                if radius < r0 or radius > r1:
                    continue
                ang = math.atan2(y, x) % math.tau
                if not self.angle_in_sector(ang, a0, a1):
                    continue
                corridor = self.biome_corridor_weight_at(ang, lane_half_width=0.068)
                if corridor > 0.20:
                    continue
                hashed = (ix * 92837111) ^ (iy * 689287499) ^ sector_seed
                keep_score = (hashed & 4095) / 4095.0
                if keep_score > 0.24:
                    continue
                radial_bias = 1.0 - abs(((radius - (r0 + r1) * 0.5) / max(1.0, (r1 - r0) * 0.5)))
                size_bias = 0.84 + radial_bias * 0.10
                base_size = (52.0 + ((hashed >> 6) & 15) * 2.3) * size_bias
                if keep_score < 0.08:
                    base_size += 12.0
                height = base_size * (0.88 + (((hashed >> 11) & 15) / 15.0) * 0.24)
                add_spec(x, y, base_size, height, hero=False)
        specs.sort(key=lambda item: (0 if item.get("hero") else 1, item["pos"].lengthSquared()))
        # Pass 282.36: pyramids are now sparse HoloVerse landmarks rather than
        # the dominant Desert silhouette. Natural landforms own the horizon.
        return specs[:2]

    def add_desert_solid_box_batch(self, parent, boxes, name="desert-solid-boxes"):
        """Build all static Desert pyramid/obelisk mass for one sector as one Geom."""
        boxes = list(boxes or [])
        if not boxes:
            return None
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData(str(name), fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        color = GeomVertexWriter(vdata, "color")
        tris = GeomTriangles(Geom.UHStatic)
        index = 0
        faces = ((0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7))
        for center, size, rgba, heading in boxes:
            hx,hy,hz=float(size.x)*0.5,float(size.y)*0.5,float(size.z)*0.5
            ca,sa=math.cos(float(heading)),math.sin(float(heading))
            pts=[]
            for lx,ly,lz in ((-hx,-hy,-hz),(hx,-hy,-hz),(hx,hy,-hz),(-hx,hy,-hz),(-hx,-hy,hz),(hx,-hy,hz),(hx,hy,hz),(-hx,hy,hz)):
                x=float(center.x)+lx*ca-ly*sa; y=float(center.y)+lx*sa+ly*ca; z=float(center.z)+lz
                vertex.addData3(x,y,z); color.addData4(*map(float,rgba)); pts.append(index); index+=1
            for a,b,c,d in faces:
                tris.addVertices(pts[a],pts[b],pts[c]); tris.closePrimitive()
                tris.addVertices(pts[a],pts[c],pts[d]); tris.closePrimitive()
        geom=Geom(vdata); geom.addPrimitive(tris)
        gnode=GeomNode(str(name)); gnode.addGeom(geom)
        np=parent.attachNewNode(gnode)
        np.setLightOff(1); np.setTextureOff(10); np.setTransparency(TransparencyAttrib.MNone)
        np.setDepthWrite(True); np.setDepthTest(True); np.setTwoSided(False)
        np.setPythonTag("desert_solid_batched",1); np.setPythonTag("desert_solid_box_count",len(boxes))
        return np

    def build_desert_pyramid_set(self, parent, ring, sector_idx: int, a0: float, a1: float, line_color, accent_color):
        specs = self.desert_pyramid_candidate_specs(ring, sector_idx, a0, a1)
        if not specs:
            parent.setPythonTag("desert_pyramid_count", 0)
            parent.setPythonTag("desert_obelisk_count", 0)
            return 0, 0
        edge_segments = []
        ridge_segments = []
        inner_segments = []
        base_rings = []
        terrace_rings = []
        window_frames = []
        apex_oculi = []
        guide_segments = []
        voxel_block_count = 0
        obelisk_count = 0
        solid_boxes = []
        for idx, spec in enumerate(specs):
            pos = spec["pos"]
            facing = Vec3(spec["facing"])
            if facing.lengthSquared() < 0.001:
                facing = Vec3(0.0, 1.0, 0.0)
            else:
                facing.normalize()
            tangent = Vec3(-facing.y, facing.x, 0.0)
            base_size = float(spec["base"])
            height = float(spec["height"])
            half = base_size * 0.5
            c1 = Vec3(pos.x + facing.x * half + tangent.x * half, pos.y + facing.y * half + tangent.y * half, self.world_height_at(pos.x + facing.x * half + tangent.x * half, pos.y + facing.y * half + tangent.y * half) + 0.16)
            c2 = Vec3(pos.x + facing.x * half - tangent.x * half, pos.y + facing.y * half - tangent.y * half, self.world_height_at(pos.x + facing.x * half - tangent.x * half, pos.y + facing.y * half - tangent.y * half) + 0.16)
            c3 = Vec3(pos.x - facing.x * half - tangent.x * half, pos.y - facing.y * half - tangent.y * half, self.world_height_at(pos.x - facing.x * half - tangent.x * half, pos.y - facing.y * half - tangent.y * half) + 0.16)
            c4 = Vec3(pos.x - facing.x * half + tangent.x * half, pos.y - facing.y * half + tangent.y * half, self.world_height_at(pos.x - facing.x * half + tangent.x * half, pos.y - facing.y * half + tangent.y * half) + 0.16)
            corners = [c1, c2, c3, c4]
            apex = Vec3(pos.x, pos.y, pos.z + height)
            # Filled voxel Desert architecture: keep the vector edges, but give
            # pyramids real 3D mass with stacked amber blocks.  This replaces
            # the old mostly-wire look without creating a second Desert route.
            heading = math.degrees(math.atan2(-facing.x, facing.y))
            fill_base = (0.82, 0.42, 0.10, 0.96)
            fill_mid = (1.00, 0.58, 0.16, 0.94)
            fill_hot = (1.00, 0.78, 0.30, 0.92)
            for layer_idx, (scale, z0, z1, rgba) in enumerate((
                (1.00, 0.00, 0.22, fill_base),
                (0.78, 0.22, 0.42, fill_mid),
                (0.56, 0.42, 0.61, fill_base),
                (0.36, 0.61, 0.79, fill_hot),
                (0.18, 0.79, 0.94, fill_mid),
            )):
                h = max(1.0, height * (z1 - z0))
                zc = pos.z + height * ((z0 + z1) * 0.5)
                solid_boxes.append((Vec3(pos.x, pos.y, zc), Vec3(base_size * scale, base_size * scale, h), rgba, math.radians(heading)))
                voxel_block_count += 1
            solid_boxes.append((Vec3(pos.x, pos.y, pos.z + height * 0.975), Vec3(base_size * 0.12, base_size * 0.12, max(1.0, height * 0.08)), fill_hot, math.radians(heading)))
            voxel_block_count += 1
            # Sparse voxel obelisks and colored solar blocks give the Desert
            # study area more readable 3D objects without overfilling the ring.
            if idx < 4:
                for side in (-1.0, 1.0):
                    ox = pos.x + facing.x * (base_size * 0.86) + tangent.x * (side * base_size * 0.46)
                    oy = pos.y + facing.y * (base_size * 0.86) + tangent.y * (side * base_size * 0.46)
                    gz = self.world_height_at(ox, oy)
                    ob_h = base_size * (0.34 + 0.05 * ((idx + 1) % 3))
                    solid_boxes.append((Vec3(ox, oy, gz + ob_h * 0.5), Vec3(base_size * 0.10, base_size * 0.10, ob_h), fill_hot if side > 0 else fill_mid, math.radians(heading)))
                    obelisk_count += 1
                    voxel_block_count += 1
            base_rings.append(corners)
            for corner in corners:
                edge_segments.append((corner, apex))
            for frac in (0.22, 0.42, 0.62):
                scale = 1.0 - frac * 0.72
                ring_pts = []
                for corner in corners:
                    ring_pts.append(Vec3(pos.x + (corner.x - pos.x) * scale, pos.y + (corner.y - pos.y) * scale, lerp(corner.z, apex.z, frac)))
                terrace_rings.append(ring_pts)
            front_mid = Vec3((c1.x + c2.x) * 0.5, (c1.y + c2.y) * 0.5, (c1.z + c2.z) * 0.5)
            back_mid = Vec3((c3.x + c4.x) * 0.5, (c3.y + c4.y) * 0.5, (c3.z + c4.z) * 0.5)
            ridge_segments.append((front_mid, apex))
            ridge_segments.append((back_mid, apex))
            chamber_half = base_size * 0.18
            chamber_base_z = pos.z + 0.20
            chamber_top_z = pos.z + height * 0.54
            chamber_corners = [
                Vec3(pos.x + facing.x * chamber_half + tangent.x * chamber_half, pos.y + facing.y * chamber_half + tangent.y * chamber_half, chamber_base_z),
                Vec3(pos.x + facing.x * chamber_half - tangent.x * chamber_half, pos.y + facing.y * chamber_half - tangent.y * chamber_half, chamber_base_z),
                Vec3(pos.x - facing.x * chamber_half - tangent.x * chamber_half, pos.y - facing.y * chamber_half - tangent.y * chamber_half, chamber_base_z),
                Vec3(pos.x - facing.x * chamber_half + tangent.x * chamber_half, pos.y - facing.y * chamber_half + tangent.y * chamber_half, chamber_base_z),
            ]
            chamber_top = [Vec3(v.x, v.y, chamber_top_z) for v in chamber_corners]
            for a, b in zip(chamber_corners, chamber_top):
                inner_segments.append((a, b))
            apex_oculi.append(chamber_top)
            front_open = [
                Vec3(lerp(c1.x, apex.x, 0.34), lerp(c1.y, apex.y, 0.34), lerp(c1.z, apex.z, 0.34)),
                Vec3(pos.x, pos.y, pos.z + height * 0.50),
                Vec3(lerp(c2.x, apex.x, 0.34), lerp(c2.y, apex.y, 0.34), lerp(c2.z, apex.z, 0.34)),
            ]
            window_frames.append(front_open)
            if idx % 2 == 0:
                rear_open = [
                    Vec3(lerp(c3.x, apex.x, 0.34), lerp(c3.y, apex.y, 0.34), lerp(c3.z, apex.z, 0.34)),
                    Vec3(pos.x, pos.y, pos.z + height * 0.46),
                    Vec3(lerp(c4.x, apex.x, 0.34), lerp(c4.y, apex.y, 0.34), lerp(c4.z, apex.z, 0.34)),
                ]
                window_frames.append(rear_open)
            for ring_pts in (chamber_corners, chamber_top):
                base_rings.append(ring_pts)
            for side in (-1.0, 1.0):
                start = Vec3(pos.x + facing.x * (base_size * 0.98) + tangent.x * (side * base_size * 0.16), pos.y + facing.y * (base_size * 0.98) + tangent.y * (side * base_size * 0.16), self.world_height_at(pos.x + facing.x * (base_size * 0.98) + tangent.x * (side * base_size * 0.16), pos.y + facing.y * (base_size * 0.98) + tangent.y * (side * base_size * 0.16)) + 0.08)
                end = Vec3(pos.x + facing.x * (base_size * 1.62) + tangent.x * (side * base_size * 0.10), pos.y + facing.y * (base_size * 1.62) + tangent.y * (side * base_size * 0.10), self.world_height_at(pos.x + facing.x * (base_size * 1.62) + tangent.x * (side * base_size * 0.10), pos.y + facing.y * (base_size * 1.62) + tangent.y * (side * base_size * 0.10)) + 0.08)
                guide_segments.append((start, end))
        if solid_boxes:
            self.add_desert_solid_box_batch(parent, solid_boxes, f"desert-solid-mass-{int(sector_idx):02d}")
        if base_rings:
            self.add_polyline_batch(parent, base_rings, line_color, self.cfg.line_thickness * 0.74, True, f"desert-pyramid-bases-{ring['name']}")
        if terrace_rings:
            self.add_polyline_batch(parent, terrace_rings, line_color, self.cfg.line_thickness * 0.54, True, f"desert-pyramid-terraces-{ring['name']}")
        if edge_segments:
            self.add_line_segments(parent, edge_segments, accent_color, self.cfg.line_thickness * 0.70, f"desert-pyramid-edges-{ring['name']}")
        if ridge_segments:
            self.add_line_segments(parent, ridge_segments, accent_color, self.cfg.line_thickness * 0.44, f"desert-pyramid-ridges-{ring['name']}")
        if inner_segments:
            self.add_line_segments(parent, inner_segments, line_color, self.cfg.line_thickness * 0.40, f"desert-pyramid-inner-{ring['name']}")
        if window_frames:
            self.add_polyline_batch(parent, window_frames, accent_color, self.cfg.line_thickness * 0.42, True, f"desert-pyramid-sky-windows-{ring['name']}")
        if apex_oculi:
            self.add_polyline_batch(parent, apex_oculi, accent_color, self.cfg.line_thickness * 0.34, True, f"desert-pyramid-oculi-{ring['name']}")
        if guide_segments:
            self.add_line_segments(parent, guide_segments, line_color, self.cfg.line_thickness * 0.24, f"desert-approach-guides-{ring['name']}")
        parent.setPythonTag("desert_pyramid_count", len(specs))
        parent.setPythonTag("desert_obelisk_count", int(obelisk_count))
        parent.setPythonTag("desert_voxel_block_count", int(voxel_block_count))
        parent.setPythonTag("desert_visual_style", "sector_batched_filled_voxel_shapes_pass28235")
        parent.setPythonTag("desert_full_ring_pass28235", 1)
        return len(specs), int(obelisk_count)

    def build_desert_macro_structure_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        """Build Pass 282.36's natural Desert silhouettes as one static sector Geom.

        These are visual macro landmarks only in this pass.  Terrain remains the
        collision authority, avoiding surprise blockers until the silhouettes
        themselves are accepted in gameplay.
        """
        if str(ring.get("kind", "")) != "desert":
            return {"total": 0, "mesas": 0, "spires": 0, "boulders": 0, "ruins": 0}
        travel = region_travel_for_number(4) or {}
        items = generate_desert_macro_structures(
            sector_idx, float(ring["r0"]), float(ring["r1"]),
            sector_count=BIOME_SECTOR_COUNT, corridor_degrees=BIOME_CORRIDOR_DEGREES,
            ember_radius=float(travel.get("radius", 2728.0)),
            landing_radius=float(travel.get("landing_radius", 2672.0)),
            anchor_angle_deg=BIOME_ANCHOR_ANGLE_DEG,
        )
        if not items:
            return {"total": 0, "mesas": 0, "spires": 0, "boulders": 0, "ruins": 0}

        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData(f"desert-natural-{int(sector_idx):02d}", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        color = GeomVertexWriter(vdata, "color")
        tris = GeomTriangles(Geom.UHStatic)
        cursor = 0
        outline_polys = []
        detail_segments = []

        sandstone_dark = (0.24, 0.105, 0.035, 1.0)
        sandstone_mid = (0.46, 0.235, 0.072, 1.0)
        sandstone_high = (0.72, 0.405, 0.115, 1.0)
        sandstone_sun = (0.88, 0.565, 0.185, 1.0)
        ruin_dark = (0.20, 0.145, 0.105, 1.0)
        ruin_high = (0.56, 0.39, 0.22, 1.0)
        hardlight = self.biome_color(ring, alpha=0.70, brighten=0.98, channel="line")
        softlight = self.biome_color(ring, alpha=0.48, brighten=0.78, channel="soft")

        def emit(p, rgba):
            nonlocal cursor
            vertex.addData3(float(p.x), float(p.y), float(p.z))
            color.addData4(*map(float, rgba))
            idx = cursor; cursor += 1
            return idx

        def face(a, b, c):
            tris.addVertices(a, b, c); tris.closePrimitive()

        def frustum(cx, cy, z0, z1, r0, r1, sides, phase, low_rgba, high_rgba, squash=1.0):
            bottom=[]; top=[]; bottom_pts=[]; top_pts=[]
            for i in range(int(sides)):
                a=float(phase)+math.tau*i/float(sides)
                # A restrained deterministic facet wobble stops perfect cylinders.
                wobble=1.0+0.07*math.sin((i+1)*2.17+phase*3.0)
                bp=Vec3(cx+math.cos(a)*r0*wobble, cy+math.sin(a)*r0*wobble*squash, z0)
                tp=Vec3(cx+math.cos(a)*r1*wobble, cy+math.sin(a)*r1*wobble*squash, z1)
                bottom.append(emit(bp, low_rgba)); top.append(emit(tp, high_rgba))
                bottom_pts.append(bp+Vec3(0,0,0.06)); top_pts.append(tp+Vec3(0,0,0.06))
            bc=emit(Vec3(cx,cy,z0),low_rgba); tc=emit(Vec3(cx,cy,z1),high_rgba)
            for i in range(int(sides)):
                j=(i+1)%int(sides)
                face(bottom[i],bottom[j],top[j]); face(bottom[i],top[j],top[i])
                face(bc,bottom[j],bottom[i]); face(tc,top[i],top[j])
            outline_polys.append(top_pts)
            return bottom_pts, top_pts

        def box(center, size, heading, rgba):
            hx,hy,hz=float(size.x)*0.5,float(size.y)*0.5,float(size.z)*0.5
            ca,sa=math.cos(float(heading)),math.sin(float(heading))
            ids=[]; pts=[]
            for lx,ly,lz in ((-hx,-hy,-hz),(hx,-hy,-hz),(hx,hy,-hz),(-hx,hy,-hz),(-hx,-hy,hz),(hx,-hy,hz),(hx,hy,hz),(-hx,hy,hz)):
                px=float(center.x)+lx*ca-ly*sa; py=float(center.y)+lx*sa+ly*ca; pz=float(center.z)+lz
                p=Vec3(px,py,pz); ids.append(emit(p,rgba)); pts.append(p)
            for a,b,c,d in ((0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7)):
                face(ids[a],ids[b],ids[c]); face(ids[a],ids[c],ids[d])
            outline_polys.append([pts[4]+Vec3(0,0,0.05),pts[5]+Vec3(0,0,0.05),pts[6]+Vec3(0,0,0.05),pts[7]+Vec3(0,0,0.05)])

        counts={"mesa":0,"rock_spire":0,"boulder_field":0,"buried_ruin":0}
        for item in items:
            counts[item.kind]=counts.get(item.kind,0)+1
            x=float(item.x); y=float(item.y); ground=self.world_height_at(x,y)
            r=float(item.radius); h=float(item.height); phase=float(item.heading)
            buried=ground-max(1.4,h*0.10)
            if item.kind=="mesa":
                # Broad buried base + narrower sunlit cap = eroded flat-topped mesa.
                frustum(x,y,buried,ground+h*0.58,r,r*0.82,8,phase,sandstone_dark,sandstone_mid,0.84)
                frustum(x,y,ground+h*0.56,ground+h,r*0.82,r*0.62,8,phase+0.06,sandstone_mid,sandstone_high,0.84)
                top_a=Vec3(x+math.cos(phase)*r*0.54,y+math.sin(phase)*r*0.45,ground+h+0.12)
                top_b=Vec3(x-math.cos(phase)*r*0.54,y-math.sin(phase)*r*0.45,ground+h+0.12)
                detail_segments.append((top_a,top_b))
            elif item.kind=="rock_spire":
                frustum(x,y,buried,ground+h*0.62,r*0.72,r*0.40,6,phase,sandstone_dark,sandstone_mid,0.78)
                _b,top=frustum(x,y,ground+h*0.60,ground+h,r*0.40,r*0.08,6,phase+0.10,sandstone_mid,sandstone_sun,0.78)
                detail_segments.append((Vec3(x,y,ground+h*0.25),Vec3(x,y,ground+h)))
            elif item.kind=="boulder_field":
                tangent=Vec3(-math.sin(phase),math.cos(phase),0)
                forward=Vec3(math.cos(phase),math.sin(phase),0)
                for j,(u,v,scale) in enumerate(((-0.42,-0.12,0.62),(0.26,0.24,0.78),(0.10,-0.46,0.48))):
                    cx=x+forward.x*(u*r)+tangent.x*(v*r); cy=y+forward.y*(u*r)+tangent.y*(v*r)
                    gz=self.world_height_at(cx,cy); bh=h*scale
                    frustum(cx,cy,gz-bh*0.18,gz+bh,r*scale,r*scale*0.70,6,phase+j*0.57,sandstone_dark,sandstone_mid if j!=1 else sandstone_high,0.78)
            else:  # buried_ruin
                # Sparse civilization echo: two half-buried uprights and a broken lintel.
                tangent=Vec3(-math.sin(phase),math.cos(phase),0); forward=Vec3(math.cos(phase),math.sin(phase),0)
                span=r*0.78; pillar_h=h*0.86
                for side in (-1.0,1.0):
                    cx=x+tangent.x*span*side; cy=y+tangent.y*span*side; gz=self.world_height_at(cx,cy)
                    box(Vec3(cx,cy,gz+pillar_h*0.36),Vec3(r*0.28,r*0.34,pillar_h),phase,ruin_dark if side<0 else ruin_high)
                box(Vec3(x+forward.x*r*0.10,y+forward.y*r*0.10,ground+h*0.78),Vec3(r*1.75,r*0.28,h*0.24),phase+0.08,ruin_high)

        geom=Geom(vdata); geom.addPrimitive(tris)
        gnode=GeomNode(f"desert-natural-{int(sector_idx):02d}"); gnode.addGeom(geom)
        np=parent.attachNewNode(gnode)
        np.setLightOff(1); np.setTextureOff(10); np.setTransparency(TransparencyAttrib.MNone)
        np.setDepthWrite(True); np.setDepthTest(True); np.setTwoSided(False)
        np.setPythonTag("desert_natural_batched",1)
        np.setPythonTag("desert_natural_structure_count",len(items))
        if outline_polys:
            self.add_polyline_batch(parent,outline_polys,hardlight,self.cfg.line_thickness*0.30,True,f"desert-natural-outlines-{int(sector_idx):02d}")
        if detail_segments:
            self.add_line_segments(parent,detail_segments,softlight,self.cfg.line_thickness*0.24,f"desert-natural-details-{int(sector_idx):02d}")
        parent.setPythonTag("desert_natural_structure_count",len(items))
        parent.setPythonTag("desert_mesa_count",counts.get("mesa",0))
        parent.setPythonTag("desert_rock_spire_count",counts.get("rock_spire",0))
        parent.setPythonTag("desert_boulder_field_count",counts.get("boulder_field",0))
        parent.setPythonTag("desert_buried_ruin_count",counts.get("buried_ruin",0))
        parent.setPythonTag("desert_visual_rebuild_pass28236",1)
        return {
            "total":len(items),"mesas":counts.get("mesa",0),"spires":counts.get("rock_spire",0),
            "boulders":counts.get("boulder_field",0),"ruins":counts.get("buried_ruin",0),
        }

    def build_ice_macro_structure_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        """Build Pass 282.37 frozen macro silhouettes as one static sector Geom."""
        if str(ring.get("kind", "")) != "ice":
            return {"total":0,"ridges":0,"spires":0,"shelves":0,"pressure":0,"crevasses":0}
        travel=region_travel_for_number(5) or {}
        track_radius=(float(ring["r0"])+float(ring["r1"]))*0.5
        items=generate_ice_macro_structures(
            sector_idx,float(ring["r0"]),float(ring["r1"]),track_radius=track_radius,
            sector_count=BIOME_SECTOR_COUNT,corridor_degrees=BIOME_CORRIDOR_DEGREES,
            mirror_radius=float(travel.get("radius",3484.0)),landing_radius=float(travel.get("landing_radius",3428.0)),
            anchor_angle_deg=BIOME_ANCHOR_ANGLE_DEG,
        )
        if not items:
            return {"total":0,"ridges":0,"spires":0,"shelves":0,"pressure":0,"crevasses":0}
        fmt=GeomVertexFormat.getV3c4(); vdata=GeomVertexData(f"ice-macro-{int(sector_idx):02d}",fmt,Geom.UHStatic)
        vertex=GeomVertexWriter(vdata,"vertex"); color=GeomVertexWriter(vdata,"color"); tris=GeomTriangles(Geom.UHStatic)
        cursor=0; outlines=[]; details=[]
        ice_dark=(0.035,0.13,0.29,1.0); ice_mid=(0.10,0.42,0.72,1.0); ice_high=(0.42,0.80,0.96,1.0); ice_white=(0.82,0.96,1.0,1.0)
        hard=self.biome_color(ring,alpha=0.72,brighten=1.02,channel="line"); soft=self.biome_color(ring,alpha=0.44,brighten=0.82,channel="soft")
        def emit(p,rgba):
            nonlocal cursor
            vertex.addData3(float(p.x),float(p.y),float(p.z)); color.addData4(*map(float,rgba)); i=cursor; cursor+=1; return i
        def face(a,b,c): tris.addVertices(a,b,c); tris.closePrimitive()
        def box(center,size,heading,rgba):
            hx,hy,hz=float(size.x)*0.5,float(size.y)*0.5,float(size.z)*0.5; ca,sa=math.cos(float(heading)),math.sin(float(heading)); ids=[]; pts=[]
            for lx,ly,lz in ((-hx,-hy,-hz),(hx,-hy,-hz),(hx,hy,-hz),(-hx,hy,-hz),(-hx,-hy,hz),(hx,-hy,hz),(hx,hy,hz),(-hx,hy,hz)):
                p=Vec3(float(center.x)+lx*ca-ly*sa,float(center.y)+lx*sa+ly*ca,float(center.z)+lz); ids.append(emit(p,rgba)); pts.append(p)
            for a,b,c,d in ((0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7)):
                face(ids[a],ids[b],ids[c]); face(ids[a],ids[c],ids[d])
            outlines.append([pts[4]+Vec3(0,0,0.05),pts[5]+Vec3(0,0,0.05),pts[6]+Vec3(0,0,0.05),pts[7]+Vec3(0,0,0.05)])
        def spire(cx,cy,gz,r,h,phase):
            sides=6; base=[]; top=[]; bpts=[]; tpts=[]
            for i in range(sides):
                a=phase+math.tau*i/sides; wob=1.0+0.06*math.sin(i*2.3+phase)
                bp=Vec3(cx+math.cos(a)*r*wob,cy+math.sin(a)*r*wob,gz-h*0.10); tp=Vec3(cx+math.cos(a)*r*0.18,cy+math.sin(a)*r*0.18,gz+h*0.78)
                base.append(emit(bp,ice_mid)); top.append(emit(tp,ice_high)); bpts.append(bp); tpts.append(tp)
            tip=emit(Vec3(cx,cy,gz+h),ice_white); bc=emit(Vec3(cx,cy,gz-h*0.10),ice_dark)
            for i in range(sides):
                j=(i+1)%sides; face(base[i],base[j],top[j]); face(base[i],top[j],top[i]); face(top[i],top[j],tip); face(bc,base[j],base[i])
            outlines.append(tpts+[Vec3(cx,cy,gz+h+0.05)])
        counts={"glacial_ridge":0,"crystal_spire":0,"ice_shelf":0,"pressure_ridge":0,"crevasse_fin":0}
        for item in items:
            counts[item.kind]=counts.get(item.kind,0)+1
            x=float(item.x); y=float(item.y); g=self.world_height_at(x,y); r=float(item.radius); h=float(item.height); a=float(item.heading)
            f=Vec3(math.cos(a),math.sin(a),0); t=Vec3(-f.y,f.x,0)
            if item.kind=="glacial_ridge":
                box(Vec3(x,y,g+h*0.30),Vec3(r*2.4,r*0.72,h*0.62),a,ice_dark)
                box(Vec3(x+t.x*r*0.12,y+t.y*r*0.12,g+h*0.62),Vec3(r*1.9,r*0.48,h*0.52),a+0.04,ice_mid)
                details.append((Vec3(x-f.x*r,y-f.y*r,g+h*0.78),Vec3(x+f.x*r,y+f.y*r,g+h*0.92)))
            elif item.kind=="crystal_spire":
                spire(x,y,g,r,h,a)
            elif item.kind=="ice_shelf":
                box(Vec3(x,y,g+h*0.28),Vec3(r*2.25,r*1.35,h*0.56),a,ice_mid)
                box(Vec3(x+f.x*r*0.18,y+f.y*r*0.18,g+h*0.66),Vec3(r*1.65,r*1.05,h*0.28),a+0.02,ice_high)
            elif item.kind=="pressure_ridge":
                for j,off in enumerate((-0.72,-0.24,0.25,0.72)):
                    cx=x+f.x*r*off; cy=y+f.y*r*off; hh=h*(0.58+0.20*((j+item.variant)%3)); spire(cx,cy,self.world_height_at(cx,cy),r*0.34,hh,a+0.22*j)
            else:
                # Thin upright fractured fin, doubled for a visible crevasse jaw.
                for side in (-1.0,1.0):
                    cx=x+t.x*r*0.36*side; cy=y+t.y*r*0.36*side
                    box(Vec3(cx,cy,g+h*0.40),Vec3(r*1.65,r*0.17,h*0.80),a+(0.06*side),ice_dark if side<0 else ice_high)
                details.append((Vec3(x-f.x*r*0.85,y-f.y*r*0.85,g+0.12),Vec3(x+f.x*r*0.85,y+f.y*r*0.85,g+0.12)))
        geom=Geom(vdata); geom.addPrimitive(tris); node=GeomNode(f"ice-macro-{int(sector_idx):02d}"); node.addGeom(geom)
        np=parent.attachNewNode(node); np.setLightOff(1); np.setTextureOff(10); np.setTransparency(TransparencyAttrib.MNone); np.setDepthWrite(True); np.setDepthTest(True); np.setTwoSided(False)
        if outlines: self.add_polyline_batch(parent,outlines,hard,self.cfg.line_thickness*0.30,True,f"ice-macro-outlines-{int(sector_idx):02d}")
        if details: self.add_line_segments(parent,details,soft,self.cfg.line_thickness*0.24,f"ice-macro-details-{int(sector_idx):02d}")
        parent.setPythonTag("ice_macro_structure_count",len(items)); parent.setPythonTag("ice_glacial_ridge_count",counts.get("glacial_ridge",0)); parent.setPythonTag("ice_crystal_spire_count",counts.get("crystal_spire",0)); parent.setPythonTag("ice_shelf_count",counts.get("ice_shelf",0)); parent.setPythonTag("ice_pressure_ridge_count",counts.get("pressure_ridge",0)); parent.setPythonTag("ice_crevasse_fin_count",counts.get("crevasse_fin",0)); parent.setPythonTag("ice_visual_rebuild_pass28237",1)
        return {"total":len(items),"ridges":counts.get("glacial_ridge",0),"spires":counts.get("crystal_spire",0),"shelves":counts.get("ice_shelf",0),"pressure":counts.get("pressure_ridge",0),"crevasses":counts.get("crevasse_fin",0)}

    def _deterministic_unit(self, *values) -> float:
        seed = 0.0
        for idx, value in enumerate(values):
            seed += (idx + 1) * 19.371 * float(value)
        raw = math.sin(seed * 12.9898 + 78.233) * 43758.5453123
        return raw - math.floor(raw)

    def ice_block_terrain_specs(self, ring, sector_idx: int, a0: float, a1: float):
        if str(ring.get("kind", "")) != "ice":
            return []
        r0 = float(ring["r0"])
        r1 = float(ring["r1"])
        span = max(1.0, r1 - r0)
        sector_width = max(0.001, a1 - a0)
        specs = []
        radial_count = 3
        angular_count = 6
        cell = float(ICE_TERRAIN_CELL_SIZE)
        for ai in range(angular_count):
            u = (ai + 0.5) / float(angular_count)
            ang = lerp(a0 + sector_width * 0.10, a1 - sector_width * 0.10, u)
            for ri in range(radial_count):
                v = (ri + 0.5) / float(radial_count)
                # Stagger each row so the field reads organic while each block
                # still sits on an exact cubic grid footprint.
                jitter_a = (self._deterministic_unit(sector_idx, ai, ri, 0.37) - 0.5) * sector_width * 0.13
                jitter_r = (self._deterministic_unit(sector_idx, ai, ri, 0.73) - 0.5) * span * 0.030
                radius = lerp(r0, r1, lerp(0.18, 0.84, v)) + jitter_r
                x = round((math.cos(ang + jitter_a) * radius) / cell) * cell
                y = round((math.sin(ang + jitter_a) * radius) / cell) * cell
                actual_radius = math.sqrt(x * x + y * y)
                if actual_radius < r0 + span * 0.10 or actual_radius > r1 - span * 0.045:
                    continue
                angle = math.atan2(y, x)
                if self.biome_corridor_weight_at(angle, lane_half_width=0.060) > 0.52:
                    continue
                ground = self.world_height_at(x, y)
                base = self.hub_ground_level() + 0.04
                height = max(0.86, ground - base + 0.42)
                footprint_seed = self._deterministic_unit(sector_idx, ai, ri, 1.19)
                footprint = lerp(cell * 0.62, cell * 0.94, footprint_seed)
                specs.append({
                    "pos": Vec3(x, y, base + height * 0.5),
                    "size": Vec3(footprint, footprint, height),
                    "top_z": base + height,
                    "seed": sector_idx * 101 + ai * 13 + ri * 7,
                })
        return specs[:int(ICE_TERRAIN_BLOCKS_PER_CHUNK)]

    def ice_floating_cube_specs(self, ring, sector_idx: int, a0: float, a1: float):
        if str(ring.get("kind", "")) != "ice":
            return []
        r0 = float(ring["r0"])
        r1 = float(ring["r1"])
        span = max(1.0, r1 - r0)
        specs = []
        for idx in range(int(ICE_FLOATING_CUBES_PER_CHUNK)):
            u = (idx + 0.5) / float(max(1, ICE_FLOATING_CUBES_PER_CHUNK))
            ang = lerp(a0, a1, u) + (self._deterministic_unit(sector_idx, idx, 2.0) - 0.5) * (a1 - a0) * 0.28
            radius = lerp(r0, r1, 0.18 + 0.70 * self._deterministic_unit(sector_idx, idx, 3.0))
            x = math.cos(ang) * radius
            y = math.sin(ang) * radius
            size = lerp(10.0, 28.0, self._deterministic_unit(sector_idx, idx, 4.0))
            z = self.world_height_at(x, y) + lerp(34.0, 126.0, self._deterministic_unit(sector_idx, idx, 5.0))
            rot = math.tau * self._deterministic_unit(sector_idx, idx, 6.0)
            specs.append({"pos": Vec3(x, y, z), "size": Vec3(size, size, size), "angle": rot})
        return specs

    def append_oriented_box_segments(self, segments: list, center: Vec3, size: Vec3, facing: Vec3 | None = None, tangent: Vec3 | None = None) -> None:
        hx, hy, hz = size.x * 0.5, size.y * 0.5, size.z * 0.5
        if facing is None or facing.lengthSquared() < 0.001:
            facing = Vec3(0.0, 1.0, 0.0)
        else:
            facing = Vec3(facing)
            facing.normalize()
        if tangent is None or tangent.lengthSquared() < 0.001:
            tangent = Vec3(-facing.y, facing.x, 0.0)
        else:
            tangent = Vec3(tangent)
            tangent.normalize()
        basis = [
            (Vec3(-hx, -hy, -hz), Vec3(hx, -hy, -hz)), (Vec3(hx, -hy, -hz), Vec3(hx, hy, -hz)),
            (Vec3(hx, hy, -hz), Vec3(-hx, hy, -hz)), (Vec3(-hx, hy, -hz), Vec3(-hx, -hy, -hz)),
            (Vec3(-hx, -hy, hz), Vec3(hx, -hy, hz)), (Vec3(hx, -hy, hz), Vec3(hx, hy, hz)),
            (Vec3(hx, hy, hz), Vec3(-hx, hy, hz)), (Vec3(-hx, hy, hz), Vec3(-hx, -hy, hz)),
            (Vec3(-hx, -hy, -hz), Vec3(-hx, -hy, hz)), (Vec3(hx, -hy, -hz), Vec3(hx, -hy, hz)),
            (Vec3(hx, hy, -hz), Vec3(hx, hy, hz)), (Vec3(-hx, hy, -hz), Vec3(-hx, hy, hz)),
        ]
        def tr(local: Vec3):
            return Vec3(
                center.x + tangent.x * local.x + facing.x * local.y,
                center.y + tangent.y * local.x + facing.y * local.y,
                center.z + local.z,
            )
        for a, b in basis:
            segments.append((tr(a), tr(b)))

    def heading_from_facing_vec(self, facing: Vec3) -> float:
        try:
            f = Vec3(facing)
            if f.lengthSquared() < 0.0001:
                return 0.0
            f.normalize()
            return math.degrees(math.atan2(f.x, f.y))
        except Exception:
            return 0.0

    def build_ice_fauna_set(self, parent, ring, sector_idx: int, a0: float, a1: float, line_color, accent_color):
        if str(ring.get("kind", "")) != "ice":
            parent.setPythonTag("ice_fauna_count", 0)
            return 0
        fauna_segments = []
        antler_lines = []
        r0 = float(ring["r0"])
        r1 = float(ring["r1"])
        for idx in range(int(ICE_FAUNA_GROUPS_PER_CHUNK)):
            ang = lerp(a0, a1, (idx + 0.5) / float(max(1, ICE_FAUNA_GROUPS_PER_CHUNK)))
            ang += (self._deterministic_unit(sector_idx, idx, 7.0) - 0.5) * (a1 - a0) * 0.20
            radius = lerp(r0, r1, lerp(0.25, 0.78, self._deterministic_unit(sector_idx, idx, 8.0)))
            x = math.cos(ang) * radius
            y = math.sin(ang) * radius
            angle = math.atan2(y, x)
            if self.biome_corridor_weight_at(angle, lane_half_width=0.058) > 0.48:
                continue
            ground = self.world_height_at(x, y)
            facing = Vec3(math.cos(ang + math.pi * 0.5), math.sin(ang + math.pi * 0.5), 0.0)
            if facing.lengthSquared() > 0.001:
                facing.normalize()
            tangent = Vec3(-facing.y, facing.x, 0.0)
            scale = lerp(0.84, 1.28, self._deterministic_unit(sector_idx, idx, 9.0))
            body_center = Vec3(x, y, ground + 5.4 * scale)
            body_len = 22.0 * scale
            body_w = 7.5 * scale
            shoulder_z = ground + 9.2 * scale
            neck = body_center + facing * (body_len * 0.43) + Vec3(0.0, 0.0, 5.0 * scale)
            head = neck + facing * (7.0 * scale) + Vec3(0.0, 0.0, 3.4 * scale)
            tail = body_center - facing * (body_len * 0.45) + Vec3(0.0, 0.0, 1.5 * scale)
            left_hip = body_center - facing * (body_len * 0.32) + tangent * body_w
            right_hip = body_center - facing * (body_len * 0.32) - tangent * body_w
            left_shoulder = body_center + facing * (body_len * 0.32) + tangent * body_w
            right_shoulder = body_center + facing * (body_len * 0.32) - tangent * body_w
            top_left = Vec3(left_shoulder.x, left_shoulder.y, shoulder_z)
            top_right = Vec3(right_shoulder.x, right_shoulder.y, shoulder_z)
            rear_left = Vec3(left_hip.x, left_hip.y, shoulder_z - 1.3 * scale)
            rear_right = Vec3(right_hip.x, right_hip.y, shoulder_z - 1.3 * scale)
            fauna_segments.extend([
                (rear_left, top_left), (top_left, top_right), (top_right, rear_right), (rear_right, rear_left),
                (top_left, neck), (top_right, neck), (neck, head), (body_center, tail),
            ])
            for foot_base in (left_hip, right_hip, left_shoulder, right_shoulder):
                knee = Vec3(foot_base.x, foot_base.y, ground + 3.2 * scale)
                hoof = Vec3(foot_base.x + tangent.x * 1.2 * scale, foot_base.y + tangent.y * 1.2 * scale, ground + 0.20)
                fauna_segments.append((Vec3(foot_base.x, foot_base.y, ground + 7.2 * scale), knee))
                fauna_segments.append((knee, hoof))
            for side in (-1.0, 1.0):
                root = head + tangent * (side * 1.8 * scale)
                tip = root + tangent * (side * 8.0 * scale) + Vec3(0.0, 0.0, 8.5 * scale)
                branch = root + tangent * (side * 5.2 * scale) + facing * (5.0 * scale) + Vec3(0.0, 0.0, 5.0 * scale)
                antler_lines.append((root, tip))
                antler_lines.append((root, branch))
        if fauna_segments:
            self.add_line_segments(parent, fauna_segments, line_color, self.cfg.line_thickness * 0.42, f"ice-crystalline-fauna-{ring['name']}")
        if antler_lines:
            self.add_line_segments(parent, antler_lines, accent_color, self.cfg.line_thickness * 0.36, f"ice-crystalline-antlers-{ring['name']}")
        count = len(fauna_segments) // 16
        parent.setPythonTag("ice_fauna_count", count)
        return count

    def build_ice_cube_set(self, parent, ring, sector_idx: int, a0: float, a1: float, line_color, accent_color):
        terrain_specs = self.ice_block_terrain_specs(ring, sector_idx, a0, a1)
        floating_specs = self.ice_floating_cube_specs(ring, sector_idx, a0, a1)
        terrain_segments = []
        top_rings = []
        floating_segments = []
        floating_shadow_rings = []

        for spec in terrain_specs:
            center = Vec3(spec["pos"])
            size = Vec3(spec["size"])
            angle = math.atan2(center.y, center.x) + math.pi * 0.5
            facing = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-facing.y, facing.x, 0.0)
            self.append_oriented_box_segments(terrain_segments, center, size, facing, tangent)
            hx = size.x * 0.5
            hy = size.y * 0.5
            z = float(spec.get("top_z", center.z + size.z * 0.5)) + 0.04
            top_rings.append([
                Vec3(center.x + tangent.x * -hx + facing.x * -hy, center.y + tangent.y * -hx + facing.y * -hy, z),
                Vec3(center.x + tangent.x *  hx + facing.x * -hy, center.y + tangent.y *  hx + facing.y * -hy, z),
                Vec3(center.x + tangent.x *  hx + facing.x *  hy, center.y + tangent.y *  hx + facing.y *  hy, z),
                Vec3(center.x + tangent.x * -hx + facing.x *  hy, center.y + tangent.y * -hx + facing.y *  hy, z),
            ])

        for spec in floating_specs:
            center = Vec3(spec["pos"])
            size = Vec3(spec["size"])
            angle = float(spec.get("angle", 0.0))
            facing = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-facing.y, facing.x, 0.0)
            self.append_oriented_box_segments(floating_segments, center, size, facing, tangent)
            shadow_z = self.world_height_at(center.x, center.y) + 0.16
            shadow_r = max(5.0, size.x * 0.55)
            floating_shadow_rings.append([
                Vec3(center.x - shadow_r, center.y - shadow_r, shadow_z),
                Vec3(center.x + shadow_r, center.y - shadow_r, shadow_z),
                Vec3(center.x + shadow_r, center.y + shadow_r, shadow_z),
                Vec3(center.x - shadow_r, center.y + shadow_r, shadow_z),
            ])

        if terrain_segments:
            self.add_line_segments(parent, terrain_segments, line_color, self.cfg.line_thickness * 0.52, f"ice-stepped-terrain-blocks-{ring['name']}")
        if top_rings:
            self.add_polyline_batch(parent, top_rings, accent_color, self.cfg.line_thickness * 0.38, True, f"ice-grid-top-plates-{ring['name']}")
        if floating_segments:
            self.add_line_segments(parent, floating_segments, accent_color, self.cfg.line_thickness * 0.56, f"ice-standalone-floating-cubes-{ring['name']}")
        if floating_shadow_rings:
            self.add_polyline_batch(parent, floating_shadow_rings, line_color, self.cfg.line_thickness * 0.28, True, f"ice-floating-cube-ground-shadows-{ring['name']}")
        parent.setPythonTag("ice_cube_count", len(terrain_specs))
        parent.setPythonTag("ice_floating_cube_count", len(floating_specs))
        return len(terrain_specs), len(floating_specs)

    # -- Pass 282.54: Ice civilization ---------------------------------------------
    # -- Pass 282.54/282.55: ring civilizations (Ice, Desert) -------------------------
    # Both rings stream the same way: a sector's layout, then its mesh arrays,
    # then the attach to its chunk, one step per frame, nearest first.  Only
    # the player's sector and its neighbours are built with their chunk; the
    # full-ring fill would otherwise build all 48 (most far outside the 620 m
    # view), so the rest wait in ``<kind>_civ_pending``.
    def _civ_spec(self, kind: str):
        if kind == "ice":
            return 6, self.ice_sector_data, self._attach_ice_civilization
        if kind == "fungal":
            return 4, self.fungal_sector_data, self._attach_fungal_civilization
        return 5, self.desert_sector_data, self._attach_desert_civilization

    def _civ_cache(self, kind: str) -> dict:
        cache = getattr(self, f"{kind}_sectors_by_index", None)
        if not isinstance(cache, dict):
            cache = {}
            setattr(self, f"{kind}_sectors_by_index", cache)
        return cache

    def _civ_pending(self, kind: str) -> dict:
        pending = getattr(self, f"{kind}_civ_pending", None)
        if not isinstance(pending, dict):
            pending = {}
            setattr(self, f"{kind}_civ_pending", pending)
        return pending

    def _civ_build_set(self, kind: str, parent, sector_idx: int):
        sector_idx = int(sector_idx) % BIOME_SECTOR_COUNT
        cached = self._civ_cache(kind).get(sector_idx)
        ready = cached is not None and cached.mesh_cache is not None
        if not ready and self.ring_sector_delta(sector_idx) > int(REGION_CIV_SYNC_REACH):
            self._civ_pending(kind)[sector_idx] = parent
            parent.setPythonTag(f"{kind}_civilization_pending", 1)
            return {}
        return self._civ_spec(kind)[2](parent, sector_idx)

    def _civ_prewarm(self, kind: str, center: int, reach: int):
        cache = self._civ_cache(kind)
        pending = self._civ_pending(kind)
        _key, data_fn, attach_fn = self._civ_spec(kind)
        for key in [k for k, node in pending.items() if node is None or node.isEmpty()]:
            pending.pop(key, None)       # the chunk was unloaded before its turn
        for delta in sorted(range(-reach, reach + 1), key=abs):
            sector = (int(center) + delta) % BIOME_SECTOR_COUNT
            data = cache.get(sector)
            if data is None:
                data_fn(sector)
                return sector
            if data.mesh_cache is None:
                _region_mesh_kit.sector_arrays_step(data, self.world_height_at, self.ring_ground_gsg())
                return sector
            if sector in pending:
                attach_fn(pending.pop(sector), sector)
                return sector
        return None

    def _civ_resolve_move(self, kind: str, px: float, py: float, nx: float, ny: float, z=None, radius: float = 0.9):
        ring = self.biome_ring_for_key(self._civ_spec(kind)[0])
        r = math.hypot(float(nx), float(ny))
        if ring is None or not (float(ring["r0"]) - 10.0 <= r <= float(ring["r1"]) + 10.0):
            return nx, ny, False
        sector = int((math.atan2(ny, nx) % math.tau) / (math.tau / BIOME_SECTOR_COUNT)) % BIOME_SECTOR_COUNT
        cache = self._civ_cache(kind)
        obstacles = []
        for delta in (-1, 0, 1):
            data = cache.get((sector + delta) % BIOME_SECTOR_COUNT)
            if data is not None:
                obstacles.extend(ob for ob in data.obstacles if abs(ob.x - nx) < 140.0 and abs(ob.y - ny) < 140.0)
        if not obstacles:
            return nx, ny, False
        return _urban_conflict.resolve_move(obstacles, float(px), float(py), float(nx), float(ny), radius=max(float(radius), 1.0), z=z)

    def _ring_band_contains(self, ring_key: int, band: float) -> bool:
        ring = self.biome_ring_for_key(ring_key)
        r = math.hypot(float(self.player_pos.x), float(self.player_pos.y))
        return ring is not None and float(ring["r0"]) - band <= r <= float(ring["r1"]) + band

    def _ring_edge_blend(self, ring_key: int, metres: float) -> float:
        ring = self.biome_ring_for_key(ring_key)
        pr = math.hypot(float(self.player_pos.x), float(self.player_pos.y))
        edge = min(pr - float(ring["r0"]), float(ring["r1"]) - pr)
        return clamp((edge + float(metres)) / (2.0 * float(metres)), 0.0, 1.0)

    # -- Ice (Pass 282.54) -------------------------------------------------------------
    def ice_civilization_active(self) -> bool:
        if not ICE_CIVILIZATION_ENABLED or _ice_visuals is None:
            return False
        return bool(getattr(getattr(self, "cfg", None), "ice_civilization_enabled", True))

    def ice_keep_clear_areas(self):
        """The Ice guide's post (the Archivist since Pass 282.57) and the Ice travel landing stay open
        (the course is kept clear separately)."""
        areas = []
        ring = self.biome_ring_for_key(6)
        for spec in NAMED_REGION_BOT_MAP:
            if int(spec.get("ring_key", 0) or 0) == 6 and not spec.get("character") and not spec.get("anchor_xy"):
                t = float(spec.get("anchor_t", 0.62))
                rad = float(ring["r0"]) + (float(ring["r1"]) - float(ring["r0"])) * t
                ang = math.radians(float(NAMED_REGION_BOT_ANCHOR_ANGLE_DEG))
                areas.append((math.cos(ang) * rad, math.sin(ang) * rad, float(_ice_civ.MIRROR_CLEARANCE) + float(spec.get("wander_radius", 0.0)) * 0.25))
        landing = region_travel_for_number(5) or {}
        if landing:
            ang = math.radians(float(landing.get("landing_angle_deg", -90.0)))
            rad = float(landing.get("landing_radius", 3428.0))
            areas.append((math.cos(ang) * rad, math.sin(ang) * rad, float(_ice_civ.LANDING_CLEARANCE)))
        return areas

    def ice_sector_data(self, sector_idx: int):
        cache = self._civ_cache("ice")
        sector_idx = int(sector_idx) % BIOME_SECTOR_COUNT
        if sector_idx not in cache:
            ring = self.biome_ring_for_key(6)
            cache[sector_idx] = _ice_civ.ice_sector(sector_idx, float(ring["r0"]), float(ring["r1"]), self.world_height_at, BIOME_SECTOR_COUNT, keep_clear=self.ice_keep_clear_areas())
        return cache[sector_idx]

    def build_ice_civilization_set(self, parent, ring, sector_idx: int):
        """Towns and spires for one Ice chunk (see the ring-civilization notes above)."""
        parent.setPythonTag("ice_visual_rebuild_pass28237", 1)
        return self._civ_build_set("ice", parent, sector_idx)

    def _attach_ice_civilization(self, parent, sector_idx: int):
        data = self.ice_sector_data(sector_idx)
        node = _ice_visuals.build_ice_node(parent, data, self.world_height_at, self.ring_ground_gsg())
        parent.setPythonTag("ice_civilization_pending", 0)
        c = data.counts
        parent.setPythonTag("ice_civilization_pass28254", 1)
        parent.setPythonTag("ice_town_count", int(c.get("towns", 0)))
        parent.setPythonTag("ice_hall_count", int(c.get("halls", 0)))
        parent.setPythonTag("ice_tower_count", int(c.get("towers", 0)))
        parent.setPythonTag("ice_spire_count", int(c.get("spires", 0)))
        parent.setPythonTag("ice_arch_count", int(c.get("arches", 0)))
        parent.setPythonTag("ice_herd_count", int(c.get("herds", 0)))
        parent.setPythonTag("ice_collision_records", len(data.obstacles))
        parent.setPythonTag("ice_civilization_triangles", int(node.getPythonTag("ice_triangles") or 0) if node is not None else 0)
        # Keep the Pass 282.37 report keys meaningful for the hub audit.
        parent.setPythonTag("ice_macro_structure_count", int(c.get("spires", 0)) + int(c.get("arches", 0)) + int(c.get("landmarks", 0)) + int(c.get("halls", 0)) + int(c.get("towers", 0)))
        parent.setPythonTag("ice_crystal_spire_count", int(c.get("spires", 0)))
        parent.setPythonTag("ice_visual_rebuild_pass28237", 1)
        return c

    def stop_ice_life(self):
        director = getattr(self, "ice_life_director", None)
        if director is not None:
            try:
                director.destroy()
            except Exception:
                pass
        self.ice_life_director = None

    def update_ice_life(self, dt: float):
        """Pass 282.54: Frostkin, skaters, mammoth herds, aurora and frost haze near the player."""
        if not self.ice_civilization_active() or bool(getattr(self, "holospace_active", False)) or not self._ring_band_contains(6, float(ICE_LIFE_BAND_METRES)):
            self.stop_ice_life()
            return None
        director = getattr(self, "ice_life_director", None)
        if director is None:
            director = _ice_visuals.IceLifeDirector(self.world_root, self.ring_ground_gsg())
            self.ice_life_director = director
        center = self.ring_center_sector()
        self.prewarm_ice_sectors(center)
        cache = self._civ_cache("ice")
        sectors = [cache[(center + d) % BIOME_SECTOR_COUNT] for d in (-2, -1, 0, 1, 2) if (center + d) % BIOME_SECTOR_COUNT in cache]
        haze = float(getattr(self, "ice_haze_factor", 0.0) or 0.0)
        if bool(getattr(self, "frost_circuit_active", False)):
            haze *= 0.6   # keep the race readable: lighter sky dome while racing
        director.update(dt, player=(float(self.player_pos.x), float(self.player_pos.y)), sectors=sectors, ground=self.world_height_at, elapsed=float(self.elapsed), sky=haze, eye_z=float(self.player_pos.z))
        return director.counts()

    def prewarm_ice_sectors(self, center: int, reach: int = REGION_CIV_ATTACH_REACH):
        return self._civ_prewarm("ice", center, reach)

    def ice_resolve_move(self, px: float, py: float, nx: float, ny: float, z=None, radius: float = 0.9):
        if not self.ice_civilization_active():
            return nx, ny, False
        return self._civ_resolve_move("ice", px, py, nx, ny, z=z, radius=radius)

    # -- Desert (Pass 282.55) -----------------------------------------------------------
    def desert_civilization_active(self) -> bool:
        if not DESERT_CIVILIZATION_ENABLED or _desert_visuals is None:
            return False
        return bool(getattr(getattr(self, "cfg", None), "desert_civilization_enabled", True))

    def desert_keep_clear_areas(self):
        """Ember's post, the Desert travel landing and the Venus-furnace oases stay open."""
        areas = []
        ring = self.biome_ring_for_key(5)
        r0, r1 = float(ring["r0"]), float(ring["r1"])
        for spec in NAMED_REGION_BOT_MAP:
            if str(spec.get("name", "")) == "Ember":
                t = float(spec.get("anchor_t", 0.54))
                rad = r0 + (r1 - r0) * t
                ang = math.radians(float(NAMED_REGION_BOT_ANCHOR_ANGLE_DEG))
                areas.append((math.cos(ang) * rad, math.sin(ang) * rad, float(_desert_civ.EMBER_CLEARANCE)))
        landing = region_travel_for_number(4) or {}
        if landing:
            ang = math.radians(float(landing.get("landing_angle_deg", -90.0)))
            rad = float(landing.get("landing_radius", 2672.0))
            areas.append((math.cos(ang) * rad, math.sin(ang) * rad, float(_desert_civ.LANDING_CLEARANCE)))
        span = max(1.0, r1 - r0)
        step = math.tau / BIOME_SECTOR_COUNT
        for sector in range(BIOME_SECTOR_COUNT):
            if not self.mini_biome_allowed(ring, sector, 9):
                continue
            a0, a1 = sector * step, (sector + 1) * step
            ang = lerp(a0 + 0.10, a1 - 0.10, 0.38 + ((sector * 0.091) % 0.24))
            rad = lerp(r0 + span * 0.20, r1 - span * 0.20, 0.62)
            areas.append((math.cos(ang) * rad, math.sin(ang) * rad, float(_desert_civ.OASIS_CLEARANCE)))
        return areas

    def desert_sector_data(self, sector_idx: int):
        cache = self._civ_cache("desert")
        sector_idx = int(sector_idx) % BIOME_SECTOR_COUNT
        if sector_idx not in cache:
            ring = self.biome_ring_for_key(5)
            keep = getattr(self, "_desert_keep_clear", None)
            if keep is None:
                keep = self._desert_keep_clear = self.desert_keep_clear_areas()
            cache[sector_idx] = _desert_civ.desert_sector(sector_idx, float(ring["r0"]), float(ring["r1"]), self.world_height_at, BIOME_SECTOR_COUNT, keep_clear=keep)
        return cache[sector_idx]

    def build_desert_civilization_set(self, parent, ring, sector_idx: int):
        """Obsidian pyramids, oasis towns and wilds for one Desert chunk (see the ring-civilization notes above)."""
        return self._civ_build_set("desert", parent, sector_idx)

    def _attach_desert_civilization(self, parent, sector_idx: int):
        data = self.desert_sector_data(sector_idx)
        node = _desert_visuals.build_desert_node(parent, data, self.world_height_at, self.ring_ground_gsg())
        parent.setPythonTag("desert_civilization_pending", 0)
        c = data.counts
        parent.setPythonTag("desert_civilization_pass28255", 1)
        for key in ("pyramids", "obelisks", "towns", "houses", "tents", "palms", "mesas", "hoodoos", "arches", "cacti", "caravans"):
            parent.setPythonTag(f"desert_{key}_count", int(c.get(key, 0)))
        parent.setPythonTag("desert_collision_records", len(data.obstacles))
        parent.setPythonTag("desert_civilization_triangles", int(node.getPythonTag("desert_triangles") or 0) if node is not None else 0)
        # Keep the Pass 282.36 report keys meaningful for the hub audit.
        parent.setPythonTag("desert_pyramid_count", int(c.get("pyramids", 0)))
        parent.setPythonTag("desert_obelisk_count", int(c.get("obelisks", 0)))
        parent.setPythonTag("desert_natural_structure_count", int(c.get("mesas", 0)) + int(c.get("hoodoos", 0)) + int(c.get("arches", 0)) + int(c.get("boulder_fields", 0)))
        return c

    def stop_desert_life(self):
        director = getattr(self, "desert_life_director", None)
        if director is not None:
            try:
                director.destroy()
            except Exception:
                pass
        self.desert_life_director = None

    def update_desert_life(self, dt: float):
        """Pass 282.55: Dunefolk, camel caravans, lantern motes, dust and the dusk sky near the player."""
        if not self.desert_civilization_active() or bool(getattr(self, "holospace_active", False)) or not self._ring_band_contains(5, float(DESERT_LIFE_BAND_METRES)):
            self.stop_desert_life()
            return None
        director = getattr(self, "desert_life_director", None)
        if director is None:
            director = _desert_visuals.DesertLifeDirector(self.world_root, self.ring_ground_gsg())
            self.desert_life_director = director
        center = self.ring_center_sector()
        self.prewarm_desert_sectors(center)
        cache = self._civ_cache("desert")
        sectors = [cache[(center + d) % BIOME_SECTOR_COUNT] for d in (-2, -1, 0, 1, 2) if (center + d) % BIOME_SECTOR_COUNT in cache]
        haze = float(getattr(self, "desert_haze_factor", 0.0) or 0.0)
        director.update(dt, player=(float(self.player_pos.x), float(self.player_pos.y)), sectors=sectors, ground=self.world_height_at, elapsed=float(self.elapsed), sky=haze, eye_z=float(self.player_pos.z))
        return director.counts()

    def prewarm_desert_sectors(self, center: int, reach: int = REGION_CIV_ATTACH_REACH):
        return self._civ_prewarm("desert", center, reach)

    def desert_resolve_move(self, px: float, py: float, nx: float, ny: float, z=None, radius: float = 0.9):
        if not self.desert_civilization_active():
            return nx, ny, False
        return self._civ_resolve_move("desert", px, py, nx, ny, z=z, radius=radius)

    # -- Mushroom (Pass 282.56) -----------------------------------------------------
    def fungal_civilization_active(self) -> bool:
        if not FUNGAL_CIVILIZATION_ENABLED or _fungal_visuals is None:
            return False
        return bool(getattr(getattr(self, "cfg", None), "fungal_civilization_enabled", True))

    def fungal_keep_clear_areas(self):
        """Any drone guide's post, Nyx and Orbit's port and the Mushroom travel landing stay open.
        (Solace kept a post here until Pass 282.57; she now lives in Green Hills.)"""
        areas = []
        ring = self.biome_ring_for_key(4)
        r0, r1 = float(ring["r0"]), float(ring["r1"])
        for spec in NAMED_REGION_BOT_MAP:
            if int(spec.get("ring_key", 0) or 0) == 4 and not spec.get("character") and not spec.get("anchor_xy"):
                t = float(spec.get("anchor_t", 0.46))
                rad = r0 + (r1 - r0) * t
                ang = math.radians(float(NAMED_REGION_BOT_ANCHOR_ANGLE_DEG))
                areas.append((math.cos(ang) * rad, math.sin(ang) * rad, float(_fungal_civ.SOLACE_CLEARANCE)))
        landing = region_travel_for_number(3) or {}
        if landing:
            ang = math.radians(float(landing.get("landing_angle_deg", -90.0)))
            rad = float(landing.get("landing_radius", 1918.0))
            areas.append((math.cos(ang) * rad, math.sin(ang) * rad, float(_fungal_civ.LANDING_CLEARANCE)))
        px, py = _fungal_civ.port_position()
        areas.append((px, py, float(_fungal_civ.PORT_CLEARANCE)))
        return areas

    def fungal_sector_data(self, sector_idx: int):
        cache = self._civ_cache("fungal")
        sector_idx = int(sector_idx) % BIOME_SECTOR_COUNT
        if sector_idx not in cache:
            ring = self.biome_ring_for_key(4)
            keep = getattr(self, "_fungal_keep_clear", None)
            if keep is None:
                keep = self._fungal_keep_clear = self.fungal_keep_clear_areas()
            cache[sector_idx] = _fungal_civ.fungal_sector(sector_idx, float(ring["r0"]), float(ring["r1"]), self.world_height_at, BIOME_SECTOR_COUNT, keep_clear=keep)
        return cache[sector_idx]

    def build_fungal_civilization_set(self, parent, ring, sector_idx: int):
        """Giant fungi, Sporekin hollows and the REDACTED port for one Mushroom chunk."""
        return self._civ_build_set("fungal", parent, sector_idx)

    def _attach_fungal_civilization(self, parent, sector_idx: int):
        data = self.fungal_sector_data(sector_idx)
        node = _fungal_visuals.build_fungal_node(parent, data, self.world_height_at, self.ring_ground_gsg())
        parent.setPythonTag("fungal_civilization_pending", 0)
        c = data.counts
        parent.setPythonTag("fungal_civilization_pass28256", 1)
        for key in ("mushrooms", "towns", "houses", "groves", "titans", "corals", "glow_fields", "vents", "drifts", "ports"):
            parent.setPythonTag(f"fungal_{key}_count", int(c.get(key, 0)))
        parent.setPythonTag("fungal_collision_records", len(data.obstacles))
        parent.setPythonTag("fungal_civilization_triangles", int(node.getPythonTag("fungal_triangles") or 0) if node is not None else 0)
        # Keep the Pass 282.34 report key meaningful for the hub audit.
        parent.setPythonTag("mushroom_solid_structure_count", int(c.get("mushrooms", 0)) + int(c.get("houses", 0)))
        return c

    def stop_fungal_life(self):
        director = getattr(self, "fungal_life_director", None)
        if director is not None:
            try:
                director.destroy()
            except Exception:
                pass
        self.fungal_life_director = None

    def update_fungal_life(self, dt: float):
        """Pass 282.56: Sporekin, spore jellies, vent spores, the port beam and the alien sky near the player."""
        self.update_character_bots(dt)
        if not self.fungal_civilization_active() or bool(getattr(self, "holospace_active", False)) or not self._ring_band_contains(4, float(FUNGAL_LIFE_BAND_METRES)):
            self.stop_fungal_life()
            return None
        director = getattr(self, "fungal_life_director", None)
        if director is None:
            director = _fungal_visuals.FungalLifeDirector(self.world_root, self.ring_ground_gsg())
            self.fungal_life_director = director
        center = self.ring_center_sector()
        self.prewarm_fungal_sectors(center)
        cache = self._civ_cache("fungal")
        sectors = [cache[(center + d) % BIOME_SECTOR_COUNT] for d in (-2, -1, 0, 1, 2) if (center + d) % BIOME_SECTOR_COUNT in cache]
        haze = float(getattr(self, "fungal_haze_factor", 0.0) or 0.0)
        director.update(dt, player=(float(self.player_pos.x), float(self.player_pos.y)), sectors=sectors, ground=self.world_height_at, elapsed=float(self.elapsed), sky=haze, eye_z=float(self.player_pos.z))
        return director.counts()

    def prewarm_fungal_sectors(self, center: int, reach: int = REGION_CIV_ATTACH_REACH):
        return self._civ_prewarm("fungal", center, reach)

    def fungal_resolve_move(self, px: float, py: float, nx: float, ny: float, z=None, radius: float = 0.9):
        if not self.fungal_civilization_active():
            return nx, ny, False
        return self._civ_resolve_move("fungal", px, py, nx, ny, z=z, radius=radius)

    def urban_conflict_active(self) -> bool:
        if not URBAN_CONFLICT_ENABLED or _urban_visuals is None:
            return False
        return bool(getattr(getattr(self, "cfg", None), "urban_conflict_enabled", True))

    def urban_keep_clear_areas(self):
        """Sable's post and the Urban travel landing stay free of debris."""
        areas = []
        for spec in NAMED_REGION_BOT_MAP:
            if str(spec.get("name", "")) == "Sable":
                ring = self.biome_ring_for_key(7)
                t = float(spec.get("anchor_t", 0.7))
                rad = float(ring["r0"]) + (float(ring["r1"]) - float(ring["r0"])) * t
                ang = math.radians(float(NAMED_REGION_BOT_ANCHOR_ANGLE_DEG))
                areas.append((math.cos(ang) * rad, math.sin(ang) * rad, float(URBAN_KEEP_CLEAR_RADIUS)))
        landing = region_travel_for_number(6) or {}
        if landing:
            ang = math.radians(float(landing.get("landing_angle_deg", -90.0)))
            rad = float(landing.get("landing_radius", 4245.0))
            areas.append((math.cos(ang) * rad, math.sin(ang) * rad, 60.0))
        return areas

    def urban_ruins_for_sector(self, sector_idx: int):
        cache = getattr(self, "urban_ruins_by_sector", None)
        if not isinstance(cache, dict):
            cache = {}
            self.urban_ruins_by_sector = cache
        sector_idx = int(sector_idx) % BIOME_SECTOR_COUNT
        if sector_idx not in cache:
            ring = self.biome_ring_for_key(7)
            cache[sector_idx] = _urban_conflict.ruin_sector(sector_idx, float(ring["r0"]), float(ring["r1"]), self.world_height_at, BIOME_SECTOR_COUNT, keep_clear=self.urban_keep_clear_areas())
        return cache[sector_idx]

    def build_urban_city_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        if self.urban_conflict_active():
            ruins = self.urban_ruins_for_sector(sector_idx)
            node = _urban_visuals.build_ruin_node(parent, ruins, self.ring_ground_gsg())
            items = ruins.structures
            parent.setPythonTag("urban_structure_count", len(items)); parent.setPythonTag("urban_structured_block_count", len(items)); parent.setPythonTag("urban_street_lane_count", 0)
            parent.setPythonTag("urban_city_collision_records", len(ruins.obstacles)); parent.setPythonTag("urban_full_ring_pass28239", 1)
            parent.setPythonTag("urban_ruins_pass28253", 1)
            parent.setPythonTag("urban_ruin_box_count", len(ruins.boxes))
            parent.setPythonTag("urban_fire_count", len(ruins.fires))
            parent.setPythonTag("urban_ruin_triangles", int(node.getPythonTag("urban_triangles") or 0) if node is not None else 0)
            return {"structures": len(items), "blocks": len(items), "streets": 0}
        return self.build_urban_city_set_legacy(parent, ring, sector_idx, a0, a1)

    def build_urban_city_set_legacy(self, parent, ring, sector_idx: int, a0: float, a1: float):
        """Permanent Pass 282.39 Urban shell: streets + solid city mass, sector-batched."""
        items = generate_urban_structures(int(sector_idx), float(ring["r0"]), float(ring["r1"]), sector_count=BIOME_SECTOR_COUNT)
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData(f"urban-city-{int(sector_idx):02d}", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex"); color = GeomVertexWriter(vdata, "color"); tris = GeomTriangles(Geom.UHStatic)
        cursor = 0
        faces=((0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7))
        palette=((0.08,0.10,0.15,1.0),(0.12,0.16,0.22,1.0),(0.16,0.12,0.22,1.0),(0.09,0.18,0.20,1.0))
        tops=[]
        for item in items:
            ground=self.world_height_at(item.x,item.y)
            center=Vec3(item.x,item.y,ground+item.sz*0.5)
            hx,hy,hz=item.sx*0.5,item.sy*0.5,item.sz*0.5; ca,sa=math.cos(item.heading),math.sin(item.heading)
            ids=[]; pts=[]; rgba=palette[int(item.tone)%len(palette)]
            # Damaged buildings lose one upper corner, but retain conservative collision footprint.
            corners=((-hx,-hy,-hz),(hx,-hy,-hz),(hx,hy,-hz),(-hx,hy,-hz),(-hx,-hy,hz),(hx,-hy,hz),(hx,hy,hz),(-hx,hy,hz))
            for ci,(lx,ly,lz) in enumerate(corners):
                if item.kind=="damaged" and ci==6: lz-=hz*0.55
                x=center.x+lx*ca-ly*sa; y=center.y+lx*sa+ly*ca; z=center.z+lz
                vertex.addData3(x,y,z); color.addData4(*rgba); ids.append(cursor); pts.append(Vec3(x,y,z)); cursor+=1
            for a,b,c,d in faces:
                tris.addVertices(ids[a],ids[b],ids[c]); tris.closePrimitive(); tris.addVertices(ids[a],ids[c],ids[d]); tris.closePrimitive()
            # roof hardlight cross gives skyline depth without translucent billboard cards
            topz=max(p.z for p in pts)+0.10
            tops.append([Vec3(item.x-item.sx*.18,item.y,topz),Vec3(item.x+item.sx*.18,item.y,topz)])
            tops.append([Vec3(item.x,item.y-item.sy*.18,topz),Vec3(item.x,item.y+item.sy*.18,topz)])
        geom=Geom(vdata); geom.addPrimitive(tris); node=GeomNode(f"urban-city-{int(sector_idx):02d}"); node.addGeom(geom)
        np=parent.attachNewNode(node); np.setLightOff(1); np.setTextureOff(10); np.setTransparency(TransparencyAttrib.MNone); np.setDepthWrite(True); np.setDepthTest(True)
        if tops: self.add_polyline_batch(parent,tops,(0.18,0.78,1.0,0.62),self.cfg.line_thickness*0.36,False,f"urban-rooftop-hardlight-{int(sector_idx):02d}")
        # City avenues: one radial centerline and three circumferential road bars per sector.
        road=(0.035,0.045,0.060,1.0); boxes=[]; amid=(float(a0)+float(a1))*0.5
        for t in (0.18,0.48,0.78):
            rr=lerp(float(ring["r0"]),float(ring["r1"]),t); x=math.cos(amid)*rr; y=math.sin(amid)*rr; g=self.world_height_at(x,y)
            boxes.append((Vec3(x,y,g+0.035),Vec3(120.0,18.0,0.10),road,amid+math.pi*0.5))
        rr=(float(ring["r0"])+float(ring["r1"]))*0.5; x=math.cos(amid)*rr; y=math.sin(amid)*rr; g=self.world_height_at(x,y)
        boxes.append((Vec3(x,y,g+0.04),Vec3(float(ring["r1"]-ring["r0"])*0.92,16.0,0.10),road,amid))
        self.add_desert_solid_box_batch(parent, boxes, name=f"urban-street-batch-{int(sector_idx):02d}")
        parent.setPythonTag("urban_structure_count",len(items)); parent.setPythonTag("urban_structured_block_count",len(items)); parent.setPythonTag("urban_street_lane_count",4)
        parent.setPythonTag("urban_city_collision_records",len(items)); parent.setPythonTag("urban_full_ring_pass28239",1)
        return {"structures":len(items),"blocks":len(items),"streets":4}

    def build_urban_warzone_set(self, parent, ring, sector_idx: int, a0: float, a1: float, line_color, accent_color):
        """Retired source-world Urban renderer.

        Urban Warzone gameplay now belongs only to Dimensions/Urban Warzone/runtime.py.
        The older world.py Urban chunk art was the duplicate main-game Urban world that
        kept masking and competing with the runtime. Keep this method as a safe no-op so
        legacy callers do not rebuild hidden ruins/mechs/drones/battle beams.
        """
        try:
            parent.setPythonTag("urban_main_world_deleted", 1)
            parent.setPythonTag("urban_runtime_owns_gameplay", 1)
            for tag in (
                "urban_infill_count", "urban_ruin_count", "urban_structure_count",
                "urban_structured_block_count", "urban_battle_count", "urban_mech_count",
                "urban_drone_count", "urban_skeleton_count", "urban_airstrike_count",
                "urban_trench_count", "urban_smoke_count", "urban_street_lane_count",
                "urban_frontline_anchor_count", "urban_battle_beam_count",
            ):
                parent.setPythonTag(tag, 0)
        except Exception:
            pass
        return {
            "ruins": 0, "structures": 0, "structured_blocks": 0, "streets": 0,
            "frontline_anchors": 0, "battle_beams": 0, "battles": 0, "mechs": 0,
            "drones": 0, "skeletons": 0, "airstrikes": 0, "trenches": 0, "smoke": 0,
            "deleted_source_world": 1,
        }

    def urban_sable_node(self):
        for node in list(getattr(self, "named_region_bot_nodes", []) or []):
            try:
                if node is not None and not node.isEmpty() and str(node.getPythonTag("named_region_bot_name") or "") == "Sable":
                    return node
            except Exception:
                continue
        return None

    def urban_war_sites(self, sable):
        sites = getattr(self, "_urban_sector_sites", None)
        ring = self.biome_ring_for_key(7)
        if sites is None:
            sites = []
            for sector in range(BIOME_SECTOR_COUNT):
                site = _urban_conflict.sector_site(sector, float(ring["r0"]), float(ring["r1"]), sector_count=BIOME_SECTOR_COUNT)
                if site is None:
                    continue
                if any(math.hypot(site.x - cx, site.y - cy) < cr + 60.0 for cx, cy, cr in self.urban_keep_clear_areas()):
                    continue
                sites.append(site)
            self._urban_sector_sites = sites
        out = list(sites)
        if sable is not None:
            bx = float(sable.getPythonTag("named_region_bot_base_x") or sable.getX())
            by = float(sable.getPythonTag("named_region_bot_base_y") or sable.getY())
            out.append(_urban_conflict.Site("sable", bx, by, math.atan2(by, bx) + math.pi * 0.5, sable=True))
        return out

    def stop_urban_conflict(self):
        director = getattr(self, "urban_war_director", None)
        if director is not None:
            try:
                director.destroy()
            except Exception:
                pass
        self.urban_war_director = None

    def update_urban_conflict(self, dt: float):
        """Pass 282.53: run the Urban robot war near the player (Sable never loses)."""
        if not self.urban_conflict_active() or bool(getattr(self, "urban_warzone_active", False)) or bool(getattr(self, "holospace_active", False)):
            self.stop_urban_conflict()
            return None
        ring = self.biome_ring_for_key(7)
        px, py = float(self.player_pos.x), float(self.player_pos.y)
        r = math.hypot(px, py)
        band = float(URBAN_WAR_BAND_METRES)
        if ring is None or not (float(ring["r0"]) - band <= r <= float(ring["r1"]) + band):
            self.stop_urban_conflict()
            return None
        director = getattr(self, "urban_war_director", None)
        if director is None:
            director = _urban_visuals.UrbanWarDirector(self.world_root, self.ring_ground_gsg())
            self.urban_war_director = director
        sable = self.urban_sable_node()
        paused = bool(sable.getPythonTag("named_region_bot_paused")) if sable is not None else False
        center = self.ring_center_sector()
        fires, towers = [], []
        for delta in (-2, -1, 0, 1, 2):
            ruins = (getattr(self, "urban_ruins_by_sector", {}) or {}).get((center + delta) % BIOME_SECTOR_COUNT)
            if ruins is not None:
                fires.extend(ruins.fires)
                towers.extend(ruins.towers)
        director.update(dt, player=(px, py), r0=float(ring["r0"]), r1=float(ring["r1"]), ground=self.world_height_at,
                        sites=self.urban_war_sites(sable), sable=sable, sable_paused=paused, fires=fires, elapsed=float(self.elapsed), towers=towers,
                        smog=float(getattr(self, "urban_smog_factor", 0.0) or 0.0), eye_z=float(self.player_pos.z))
        return director.counts()

    def world_resolve_move(self, px: float, py: float, nx: float, ny: float, z=None, radius: float = 0.9):
        """Slide a move around every solid world obstacle (Metropolis buildings,
        Ice towns and spires, Desert pyramids and towns, Mushroom fungi and
        hollows, Urban ruins/wrecks/barricades).  Returns (x, y, blocked)."""
        x, y, blocked = self.metropolis_resolve_move(px, py, nx, ny, z=z, radius=radius)
        x, y, iblocked = self.ice_resolve_move(px, py, x, y, z=z, radius=radius)
        x, y, dblocked = self.desert_resolve_move(px, py, x, y, z=z, radius=radius)
        x, y, fblocked = self.fungal_resolve_move(px, py, x, y, z=z, radius=radius)
        blocked = bool(blocked or iblocked or dblocked or fblocked)
        if not self.urban_conflict_active():
            return x, y, blocked
        ring = self.biome_ring_for_key(7)
        r = math.hypot(float(x), float(y))
        if ring is None or not (float(ring["r0"]) - 10.0 <= r <= float(ring["r1"]) + 10.0):
            return x, y, blocked
        sector = int((math.atan2(y, x) % math.tau) / (math.tau / BIOME_SECTOR_COUNT)) % BIOME_SECTOR_COUNT
        obstacles = []
        cache = getattr(self, "urban_ruins_by_sector", {}) or {}
        for delta in (-1, 0, 1):
            ruins = cache.get((sector + delta) % BIOME_SECTOR_COUNT)
            if ruins is not None:
                obstacles.extend(ruins.obstacles)
        if not obstacles:
            return x, y, blocked
        # 1.4 m keeps the slide outside the Urban Warzone runtime's own 1.35 m
        # structure check, so walls slide instead of rejecting the move.
        ux, uy, ublocked = _urban_conflict.resolve_move(obstacles, float(px), float(py), float(x), float(y), radius=max(float(radius), 1.4), z=z)
        return ux, uy, bool(blocked or ublocked)

    def update_urban_warzone(self, dt: float):
        """Retired source-world Urban animation loop.

        Runtime-owned Urban Warzone installs its own update_urban_warzone on the
        CommandHubApp host. The old world.py loop is intentionally dead so no duplicate
        Urban battlefield can animate behind or instead of the real runtime.
        """
        del dt
        for list_attr in (
            "urban_battle_nodes", "urban_airstrike_nodes", "urban_mech_nodes",
            "urban_drone_nodes", "urban_skeleton_nodes",
        ):
            stale = []
            for node in list(getattr(self, list_attr, []) or []):
                try:
                    if node is not None and not node.isEmpty():
                        node.removeNode()
                except Exception:
                    pass
            try:
                setattr(self, list_attr, stale)
            except Exception:
                pass
        self.source_world_urban_deleted = True
        return None
    def biome_lush_accent_lines(self, ring, a0: float, a1: float):
        # Pass 42: capped color accent strokes that follow terrain. These are
        # not prop systems; they are small line accents to make natural biomes
        # read lush while keeping chunk streaming bounded.
        kind = str(ring.get("kind", ""))
        if kind not in LUSH_NATURE_KINDS:
            return []
        r0 = float(ring["r0"])
        r1 = float(ring["r1"])
        lines = []
        mid = (a0 + a1) * 0.5
        span = max(0.001, a1 - a0)
        if kind in ("forest", "hills"):
            t_values = (0.28, 0.43, 0.58, 0.73)
            for idx, t in enumerate(t_values):
                pts = []
                for sample in range(12):
                    u = sample / 11.0
                    ang = lerp(a0 + span * 0.12, a1 - span * 0.12, u)
                    radius = lerp(r0, r1, t + 0.018 * math.sin(u * math.tau + idx * 1.7))
                    pts.append(self._biome_point_at(radius, ang, 0.32 + idx * 0.018))
                lines.append(pts)
            for off in (-0.22, 0.22):
                stem = []
                ang = mid + off * span
                for sample in range(9):
                    t = lerp(0.32, 0.82, sample / 8.0)
                    radius = lerp(r0, r1, t)
                    stem.append(self._biome_point_at(radius, ang + 0.012 * math.sin(t * math.tau * 2.0), 0.36))
                lines.append(stem)
        elif kind == "water":
            for t in (0.24, 0.38, 0.52, 0.66, 0.80):
                pts = []
                for sample in range(14):
                    u = sample / 13.0
                    ang = lerp(a0, a1, u)
                    radius = lerp(r0, r1, t + 0.010 * math.sin(u * math.tau * 2.0))
                    pts.append(self._biome_point_at(radius, ang, 0.24))
                lines.append(pts)
        elif kind == "desert":
            for idx, t in enumerate((0.32, 0.50, 0.68)):
                pts = []
                for sample in range(12):
                    u = sample / 11.0
                    ang = lerp(a0, a1, u)
                    radius = lerp(r0, r1, t + 0.012 * math.sin(u * math.tau * 1.25 + idx * 0.9))
                    pts.append(self._biome_point_at(radius, ang, 0.32 + idx * 0.02))
                lines.append(pts)
        elif kind == "ice":
            for off in (-0.28, -0.10, 0.12, 0.30):
                pts = []
                ang = mid + off * span
                for sample in range(10):
                    radius = lerp(r0, r1, lerp(0.24, 0.84, sample / 9.0))
                    pts.append(self._biome_point_at(radius, ang, 0.34))
                lines.append(pts)
        return lines

    def biome_feature_guide_lines(self, ring, a0: float, a1: float):
        # Terrain-first signatures: line-only landform cues, not prop clutter.
        r0 = float(ring["r0"])
        r1 = float(ring["r1"])
        kind = str(ring.get("kind", ""))
        lines = []
        def radial_line(angle: float, t0: float = 0.08, t1: float = 0.92, samples: int = 22, zoff: float = 0.16):
            pts = []
            for idx in range(samples):
                t = lerp(t0, t1, idx / float(max(1, samples - 1)))
                radius = lerp(r0, r1, t)
                pts.append(self._biome_point_at(radius, angle, zoff))
            return pts
        def arc_line(t: float, wiggle: float = 0.0, samples: int = 26, zoff: float = 0.16):
            pts = []
            for idx in range(samples):
                u = idx / float(max(1, samples - 1))
                ang = lerp(a0, a1, u)
                radius = lerp(r0, r1, t + wiggle * math.sin(u * math.tau))
                pts.append(self._biome_point_at(radius, ang, zoff))
            return pts
        mid = (a0 + a1) * 0.5
        span = max(0.001, a1 - a0)
        if kind == "forest":
            for off in (-0.30, 0.0, 0.30):
                lines.append(radial_line(mid + off * span, 0.12, 0.88, 24, 0.18))
            for t in (0.33, 0.58, 0.78):
                lines.append(arc_line(t, wiggle=0.015, samples=28, zoff=0.14))
        elif kind == "hills":
            for t in (0.42, 0.52, 0.64):
                lines.append(arc_line(t, wiggle=0.028, samples=30, zoff=0.20))
            for off in (-0.22, 0.22):
                lines.append(radial_line(mid + off * span, 0.20, 0.80, 22, 0.18))
        elif kind == "water":
            for t in (0.25, 0.40, 0.55, 0.70):
                lines.append(arc_line(t, wiggle=0.010, samples=28, zoff=0.10))
            lines.append(radial_line(mid, 0.18, 0.82, 22, 0.12))
        elif kind == "desert":
            for t in (0.26, 0.42, 0.58, 0.74):
                lines.append(arc_line(t, wiggle=0.014, samples=30, zoff=0.19))
            for off in (-0.26, 0.26):
                lines.append(radial_line(mid + off * span, 0.16, 0.86, 22, 0.18))
        elif kind == "ice":
            for off in (-0.34, -0.10, 0.15, 0.36):
                lines.append(radial_line(mid + off * span, 0.14, 0.86, 18, 0.18))
        elif kind == "urban":
            for t in (0.22, 0.38, 0.54, 0.70, 0.86):
                lines.append(arc_line(t, wiggle=0.0, samples=24, zoff=0.18))
            for off in (-0.32, 0.0, 0.32):
                lines.append(radial_line(mid + off * span, 0.10, 0.92, 18, 0.18))
        elif kind == "metropolis":
            for t in (0.20, 0.35, 0.50, 0.65, 0.80):
                lines.append(arc_line(t, wiggle=0.0, samples=24, zoff=0.22))
            for off in (-0.38, -0.18, 0.0, 0.18, 0.38):
                lines.append(radial_line(mid + off * span, 0.08, 0.94, 18, 0.22))
        return lines


    def register_salvage_population_node(self, node):
        if node is None:
            return
        nodes = [n for n in list(getattr(self, "salvage_population_nodes", []) or []) if n is not None and not n.isEmpty()]
        nodes.append(node)
        overflow = max(0, len(nodes) - int(MAX_SALVAGE_POPULATION_NODES))
        if overflow:
            for stale in nodes[:overflow]:
                try:
                    stale.removeNode()
                except Exception:
                    pass
            nodes = nodes[overflow:]
            self.salvage_population_pruned_count = int(getattr(self, "salvage_population_pruned_count", 0)) + overflow
        self.salvage_population_nodes = nodes

    def build_salvage_population_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        kind = str(ring.get("kind", ""))
        if kind in ("flat", "metropolis"):
            return 0
        if kind == "water" and (bool(globals().get("DEEP_WATER_LITE_MODE", True)) or not bool(globals().get("DEEP_WATER_ENABLE_SALVAGE", False))):
            return 0
        r0 = float(ring["r0"])
        r1 = float(ring["r1"])
        span = max(1.0, r1 - r0)
        sector_span = max(0.001, a1 - a0)
        count = 0
        primary = self.biome_color(ring, alpha=0.92, brighten=1.08, channel="accent")
        secondary = self.biome_color(ring, alpha=0.58, brighten=0.84, channel="line")
        soft = self.biome_color(ring, alpha=0.40, brighten=0.70, channel="soft")
        for idx in range(int(SALVAGE_POPULATION_PER_CHUNK)):
            u = (idx + 0.5) / float(max(1, SALVAGE_POPULATION_PER_CHUNK))
            jitter_a = (self._deterministic_unit(sector_idx, idx, int(ring["key"]), 311.0) - 0.5) * sector_span * 0.46
            ang = lerp(a0 + sector_span * 0.10, a1 - sector_span * 0.10, u) + jitter_a
            if self.biome_corridor_weight_at(ang, lane_half_width=0.052) > 0.62:
                continue
            radial_t = 0.16 + 0.68 * self._deterministic_unit(sector_idx, idx, int(ring["key"]), 319.0)
            radius = lerp(r0 + span * 0.06, r1 - span * 0.08, radial_t)
            x = math.cos(ang) * radius
            y = math.sin(ang) * radius
            if kind == "water":
                bottom_z, top_z = self.deep_water_bounds(x, y, ring)
                z = lerp(bottom_z + 0.8, top_z - 0.25, 0.24 + 0.58 * self._deterministic_unit(sector_idx, idx, 337.0))
            else:
                z = self.world_height_at(x, y) + 0.62
            root = parent.attachNewNode(f"salvage-pop-{kind}-{sector_idx:02d}-{idx:02d}")
            root.setPos(x, y, z)
            root.setHpr(math.degrees(ang), 0.0, 0.0)
            root.setPythonTag("salvage_pop_base_z", float(z))
            root.setPythonTag("salvage_pop_phase", float(self._deterministic_unit(sector_idx, idx, 347.0) * math.tau))
            root.setPythonTag("salvage_pop_amp", float(0.045 if kind not in ("water", "urban") else 0.085))
            root.setPythonTag("salvage_pop_kind", kind)
            scale = 1.0 + 0.26 * self._deterministic_unit(sector_idx, idx, 353.0)
            root.setScale(scale * float(SALVAGE_POPULATION_SIZE_SCALE))
            if kind in ("forest", "hills"):
                size = 2.2 + 0.9 * self._deterministic_unit(sector_idx, idx, 359.0)
                body = [Vec3(-size * 0.90, 0, size * 0.72), Vec3(-size * 0.28, 0, size * 1.05), Vec3(size * 0.68, 0, size * 0.74), Vec3(size * 0.20, 0, size * 0.42)]
                head = [Vec3(size * 0.70, 0, size * 0.82), Vec3(size * 1.05, 0, size * 1.08), Vec3(size * 1.23, 0, size * 0.78)]
                legs = []
                for lx in (-0.62, -0.16, 0.36, 0.70):
                    legs.append([Vec3(lx * size, 0, size * 0.48), Vec3(lx * size * 0.92, 0, 0.04)])
                horns = [[Vec3(size * 1.00, 0, size * 1.02), Vec3(size * 1.18, 0, size * 1.30)], [Vec3(size * 0.88, 0, size * 0.98), Vec3(size * 0.72, 0, size * 1.22)]]
                self.add_polyline(root, body, primary, self.cfg.line_thickness * 0.46, True, "salvage-grazer-body")
                self.add_polyline(root, head, primary, self.cfg.line_thickness * 0.42, False, "salvage-grazer-head")
                self.add_polyline_batch(root, legs + horns, secondary, self.cfg.line_thickness * 0.34, False, "salvage-grazer-detail")
            elif kind == "desert":
                size = 2.6 + 1.1 * self._deterministic_unit(sector_idx, idx, 367.0)
                shell = [Vec3(-size, 0, size * 0.28), Vec3(-size * 0.45, 0, size * 0.80), Vec3(size * 0.55, 0, size * 0.74), Vec3(size * 1.08, 0, size * 0.30), Vec3(size * 0.46, 0, size * 0.08), Vec3(-size * 0.64, 0, size * 0.10)]
                legs = []
                for lx in (-0.72, -0.36, 0.08, 0.44, 0.78):
                    legs.append([Vec3(lx * size, 0, size * 0.12), Vec3((lx + 0.10) * size, 0, -0.18 * size)])
                antenna = [[Vec3(size * 0.72, 0, size * 0.68), Vec3(size * 1.04, 0, size * 1.16)], [Vec3(size * 0.54, 0, size * 0.72), Vec3(size * 0.74, 0, size * 1.18)]]
                self.add_polyline(root, shell, primary, self.cfg.line_thickness * 0.48, True, "salvage-crawler-shell")
                self.add_polyline_batch(root, legs + antenna, secondary, self.cfg.line_thickness * 0.34, False, "salvage-crawler-detail")
                self.add_polyline(root, self.polygon_points(size * 1.26, 0.0, 12, 0.0), soft, self.cfg.line_thickness * 0.24, True, "salvage-crawler-shadow")
            elif kind == "ice":
                size = 2.0 + 0.9 * self._deterministic_unit(sector_idx, idx, 373.0)
                spire = [Vec3(0, 0, 0.0), Vec3(-size * 0.46, 0, size * 1.25), Vec3(0.0, 0, size * 2.15), Vec3(size * 0.52, 0, size * 1.10), Vec3(0, 0, 0.0)]
                legs = [[Vec3(-size * 0.22, 0, size * 0.10), Vec3(-size * 0.74, 0, -size * 0.52)], [Vec3(size * 0.20, 0, size * 0.10), Vec3(size * 0.72, 0, -size * 0.50)]]
                arms = [[Vec3(-size * 0.38, 0, size * 1.16), Vec3(-size * 1.00, 0, size * 1.46)], [Vec3(size * 0.40, 0, size * 1.14), Vec3(size * 1.04, 0, size * 1.40)]]
                self.add_polyline(root, spire, primary, self.cfg.line_thickness * 0.44, True, "salvage-crystal-walker")
                self.add_polyline_batch(root, legs + arms, secondary, self.cfg.line_thickness * 0.32, False, "salvage-crystal-limbs")
            elif kind == "urban":
                size = 2.1 + 0.8 * self._deterministic_unit(sector_idx, idx, 379.0)
                self.add_box(root, Vec3(0, 0, size * 0.92), Vec3(size * 0.90, size * 0.54, size * 1.30), primary, 0.34)
                mast = [[Vec3(0, 0, size * 1.58), Vec3(0, 0, size * 2.22)], [Vec3(0, 0, size * 2.22), Vec3(size * 0.34, 0, size * 2.44)]]
                arms = [[Vec3(-size * 0.45, 0, size * 1.16), Vec3(-size * 1.08, 0, size * 0.82)], [Vec3(size * 0.45, 0, size * 1.12), Vec3(size * 1.06, 0, size * 0.80)]]
                legs = [[Vec3(-size * 0.24, 0, size * 0.28), Vec3(-size * 0.58, 0, -size * 0.22)], [Vec3(size * 0.24, 0, size * 0.28), Vec3(size * 0.54, 0, -size * 0.22)]]
                self.add_polyline_batch(root, mast + arms + legs, secondary, self.cfg.line_thickness * 0.32, False, "salvage-urban-bot-lines")
                self.add_polyline(root, [Vec3(size * 1.06, 0, size * 0.82), Vec3(size * 2.45, 0, size * 1.02)], (1.0, 0.22, 0.18, 0.50), self.cfg.line_thickness * 0.26, False, "salvage-urban-scan")
            elif kind == "water":
                size = 2.5 + 1.2 * self._deterministic_unit(sector_idx, idx, 383.0)
                hull = [Vec3(-size * 1.10, 0, 0.0), Vec3(-size * 0.20, 0, size * 0.42), Vec3(size * 1.12, 0, 0.0), Vec3(-size * 0.20, 0, -size * 0.42)]
                fins = [[Vec3(-size * 0.18, 0, size * 0.42), Vec3(-size * 0.46, 0, size * 0.94)], [Vec3(-size * 0.18, 0, -size * 0.42), Vec3(-size * 0.44, 0, -size * 0.94)], [Vec3(-size * 1.10, 0, 0), Vec3(-size * 1.66, 0, size * 0.36), Vec3(-size * 1.66, 0, -size * 0.32)]]
                self.add_polyline(root, hull, primary, self.cfg.line_thickness * 0.46, True, "salvage-water-skimmer")
                self.add_polyline_batch(root, fins, secondary, self.cfg.line_thickness * 0.32, False, "salvage-water-skimmer-fins")
            else:
                continue
            self.register_salvage_population_node(root)
            count += 1
        parent.setPythonTag("salvage_population_count", int(count))
        return count

    def update_salvage_population(self, dt: float):
        nodes = []
        for node in list(getattr(self, "salvage_population_nodes", []) or []):
            try:
                if node is None or node.isEmpty():
                    continue
                base_z = float(node.getPythonTag("salvage_pop_base_z") or node.getZ())
                phase = float(node.getPythonTag("salvage_pop_phase") or 0.0)
                amp = float(node.getPythonTag("salvage_pop_amp") or 0.04)
                kind = str(node.getPythonTag("salvage_pop_kind") or "")
                speed = 1.65 if kind in ("water", "urban") else 0.82
                bob = math.sin(self.elapsed * speed + phase) * amp
                node.setZ(base_z + bob)
                node.setR(math.sin(self.elapsed * (speed * 0.55) + phase) * (1.6 if kind != "urban" else 2.8))
                nodes.append(node)
            except Exception:
                continue
        self.salvage_population_nodes = nodes

    def add_mushroom_solid_batch(self, parent, items, ring, name="mushroom-solid-structures"):
        """Build solid fungal architecture as one static sector batch.

        Pass 282.34 keeps these structures visual-only while their placement is
        being established.  Terrain remains the movement/collision authority.
        Dark faceted mass sits underneath a small number of hardlight contours,
        so the region reads as solid from a distance without creating hundreds
        of separate Panda3D draw nodes.
        """
        items = list(items or [])
        if not items:
            return None

        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData(str(name), fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        color = GeomVertexWriter(vdata, "color")
        tris = GeomTriangles(Geom.UHStatic)
        next_idx = 0
        contour_polys = []
        detail_segments = []

        stem_dark = (0.115, 0.030, 0.125, 1.0)
        stem_mid = (0.205, 0.055, 0.210, 1.0)
        stem_high = (0.310, 0.085, 0.300, 1.0)
        cap_shadow = (0.180, 0.018, 0.170, 1.0)
        cap_mid = (0.420, 0.035, 0.335, 1.0)
        cap_high = (0.700, 0.080, 0.515, 1.0)
        cap_tip = (0.880, 0.130, 0.665, 1.0)
        root_dark = (0.115, 0.022, 0.130, 1.0)
        root_high = (0.350, 0.050, 0.300, 1.0)
        hardlight = self.biome_color(ring, alpha=0.74, brighten=1.02, channel="accent")
        softlight = self.biome_color(ring, alpha=0.46, brighten=0.82, channel="line")

        def emit(point, rgba):
            nonlocal next_idx
            vertex.addData3(float(point.x), float(point.y), float(point.z))
            color.addData4(*map(float, rgba))
            idx = next_idx
            next_idx += 1
            return idx

        def tri(a, b, c):
            tris.addVertices(int(a), int(b), int(c))
            tris.closePrimitive()

        def prism(center, z0, z1, r0, r1, heading=0.0, sides=8,
                  lower_rgba=stem_dark, upper_rgba=stem_high, drift=None):
            drift = Vec3(drift or Vec3(0, 0, 0))
            lows = []
            highs = []
            low_pts = []
            high_pts = []
            for i in range(int(sides)):
                a = float(heading) + math.tau * i / float(sides)
                ca, sa = math.cos(a), math.sin(a)
                p0 = Vec3(center.x + ca * r0, center.y + sa * r0, z0)
                p1 = Vec3(center.x + drift.x + ca * r1, center.y + drift.y + sa * r1, z1)
                lows.append(emit(p0, lower_rgba)); highs.append(emit(p1, upper_rgba))
                low_pts.append(p0); high_pts.append(p1)
            for i in range(int(sides)):
                j = (i + 1) % int(sides)
                tri(lows[i], lows[j], highs[j]); tri(lows[i], highs[j], highs[i])
            return low_pts, high_pts

        def cap(center, z, rx, ry, thickness, heading=0.0, sides=10, offset=None,
                lower_rgba=cap_shadow, middle_rgba=cap_mid, upper_rgba=cap_high):
            offset = Vec3(offset or Vec3(0, 0, 0))
            c = Vec3(center) + offset
            # Broad low rim, full shoulder, narrower crown, then apex.  The
            # lower fan closes the underside so caps are opaque from below.
            defs = (
                (-0.42, 0.86, lower_rgba),
                (-0.06, 1.00, middle_rgba),
                (0.36, 0.68, upper_rgba),
            )
            rings = []
            ring_pts = []
            for ri, (zf, scale, rgba) in enumerate(defs):
                ids = []; pts = []
                phase = float(heading) + 0.08 * ri
                for i in range(int(sides)):
                    a = phase + math.tau * i / float(sides)
                    wob = 1.0 + 0.045 * math.sin(a * 3.0 + ri * 0.9)
                    p = Vec3(c.x + math.cos(a) * rx * scale * wob,
                             c.y + math.sin(a) * ry * scale / wob,
                             float(z) + float(thickness) * zf)
                    ids.append(emit(p, rgba)); pts.append(p)
                rings.append(ids); ring_pts.append(pts)
            bottom = emit(Vec3(c.x, c.y, float(z) - float(thickness) * 0.54), lower_rgba)
            apex = emit(Vec3(c.x, c.y, float(z) + float(thickness) * 0.72), cap_tip)
            for i in range(int(sides)):
                j = (i + 1) % int(sides)
                tri(bottom, rings[0][j], rings[0][i])
                for r in range(2):
                    tri(rings[r][i], rings[r][j], rings[r + 1][j])
                    tri(rings[r][i], rings[r + 1][j], rings[r + 1][i])
                tri(rings[2][i], rings[2][j], apex)
            contour_polys.append([p + Vec3(0, 0, 0.03) for p in ring_pts[1]])
            underside = Vec3(c.x, c.y, float(z) - float(thickness) * 0.48)
            for p in ring_pts[0][::2]:
                detail_segments.append((underside, p + Vec3(0, 0, 0.02)))
            return ring_pts

        def bulb(center, rx, ry, rz, heading=0.0, sides=7):
            rings = []
            for ri, (zf, sf, rgba) in enumerate(((-0.46, 0.58, root_dark), (0.0, 1.0, root_high), (0.48, 0.60, cap_mid))):
                ids = []
                for i in range(int(sides)):
                    a = float(heading) + 0.16 * ri + math.tau * i / float(sides)
                    ids.append(emit(Vec3(center.x + math.cos(a) * rx * sf,
                                         center.y + math.sin(a) * ry * sf,
                                         center.z + rz * zf), rgba))
                rings.append(ids)
            bottom = emit(Vec3(center.x, center.y, center.z - rz * 0.78), root_dark)
            top = emit(Vec3(center.x, center.y, center.z + rz * 0.82), cap_high)
            for i in range(int(sides)):
                j=(i+1)%int(sides)
                tri(bottom,rings[0][j],rings[0][i])
                tri(rings[0][i],rings[0][j],rings[1][j]); tri(rings[0][i],rings[1][j],rings[1][i])
                tri(rings[1][i],rings[1][j],rings[2][j]); tri(rings[1][i],rings[2][j],rings[2][i])
                tri(rings[2][i],rings[2][j],top)

        for item in items:
            x = float(item.x); y = float(item.y)
            base_z = self.world_height_at(x, y) + 0.06
            center = Vec3(x, y, base_z)
            radius = float(item.radius)
            height = float(item.height)
            heading = float(item.heading)
            variant = int(item.variant)
            axis = Vec3(math.cos(heading), math.sin(heading), 0.0)
            cross = Vec3(-axis.y, axis.x, 0.0)

            if item.kind == "cap_tower":
                stem_h = height * (0.66 + 0.025 * variant)
                drift = axis * radius * (0.08 + 0.025 * variant)
                _, top_pts = prism(center, base_z + 0.06, base_z + stem_h,
                                   radius * 0.22, radius * 0.13, heading, 8,
                                   stem_dark, stem_high, drift)
                top_center = Vec3(x + drift.x, y + drift.y, base_z + stem_h)
                cap(top_center, top_center.z + radius * 0.10,
                    radius * 1.05, radius * (0.88 + 0.035 * variant), radius * 0.62,
                    heading + variant * 0.19)
                detail_segments.append((Vec3(x, y, base_z + 0.16), top_center))

            elif item.kind == "shelf_column":
                pillar_h = height * 0.94
                drift = axis * radius * 0.06
                _, top_pts = prism(center, base_z + 0.04, base_z + pillar_h,
                                   radius * 0.24, radius * 0.14, heading, 7,
                                   stem_dark, stem_mid, drift)
                for si, frac in enumerate((0.34, 0.56, 0.78)):
                    side = -1.0 if (si + variant) % 2 else 1.0
                    shelf_axis = Vec3(math.cos(heading + side * 0.72), math.sin(heading + side * 0.72), 0.0)
                    off = shelf_axis * radius * (0.38 + 0.06 * si)
                    zz = base_z + pillar_h * frac
                    cap(Vec3(x, y, zz), zz,
                        radius * (0.56 + 0.10 * si), radius * (0.43 + 0.07 * si),
                        radius * 0.22, heading + side * 0.30, sides=8, offset=off,
                        lower_rgba=cap_shadow, middle_rgba=cap_mid, upper_rgba=cap_high)
                contour_polys.append([p + Vec3(0,0,0.03) for p in top_pts])

            elif item.kind == "spire":
                sides = 7
                ring_defs = (
                    (0.00, 0.66),
                    (0.20, 0.90),
                    (0.43, 0.62),
                    (0.66, 0.76),
                    (0.84, 0.42),
                    (1.00, 0.10),
                )
                rings = []
                pts_rings = []
                for ri, (frac, scale) in enumerate(ring_defs):
                    ids=[]; pts=[]
                    twist = heading + ri * (0.20 + variant * 0.025)
                    drift = axis * math.sin(frac * math.pi) * radius * 0.18 + cross * math.sin(frac * math.tau + variant) * radius * 0.08
                    for i in range(sides):
                        a=twist+math.tau*i/sides
                        p=Vec3(x+drift.x+math.cos(a)*radius*scale,
                               y+drift.y+math.sin(a)*radius*scale,
                               base_z+height*frac)
                        rgba=(stem_dark if ri<2 else stem_mid if ri<4 else cap_high)
                        ids.append(emit(p,rgba)); pts.append(p)
                    rings.append(ids); pts_rings.append(pts)
                for r in range(len(rings)-1):
                    for i in range(sides):
                        j=(i+1)%sides
                        tri(rings[r][i],rings[r][j],rings[r+1][j]); tri(rings[r][i],rings[r+1][j],rings[r+1][i])
                for ridx in (1,3,4): contour_polys.append([p+Vec3(0,0,0.02) for p in pts_rings[ridx]])
                # Offset shelves make the tall form unmistakably fungal instead
                # of reading as a generic obelisk/rocket silhouette.
                for si,(frac,scale,side) in enumerate(((0.46,0.62,1.0),(0.70,0.52,-1.0))):
                    shelf_axis = cross * side + axis * (0.25 if si == 1 else -0.10)
                    off = shelf_axis * radius * (0.24 + 0.06 * si)
                    zz = base_z + height * frac
                    cap(Vec3(x,y,zz), zz, radius*scale, radius*scale*0.76,
                        max(0.70,radius*(0.18+0.02*si)), heading+side*(0.30+0.08*si),
                        sides=8, offset=off, lower_rgba=cap_shadow, middle_rgba=cap_mid, upper_rgba=cap_high)
                crown_z = base_z + height * 0.93
                cap(Vec3(x,y,crown_z), crown_z, radius*0.72, radius*0.62,
                    max(0.85,radius*0.28), heading+0.14*variant, sides=9,
                    lower_rgba=cap_shadow, middle_rgba=cap_mid, upper_rgba=cap_tip)

            elif item.kind == "root_mass":
                # Five overlapping bulbs create one grounded fungal/root mass.
                offsets = (
                    (Vec3(0,0,0), 1.00, 1.00),
                    (axis * radius * 0.42, 0.70, 0.76),
                    (axis * radius * -0.34, 0.64, 0.70),
                    (cross * radius * 0.38, 0.58, 0.64),
                    (cross * radius * -0.31, 0.54, 0.60),
                )
                for bi,(off,rs,hs) in enumerate(offsets):
                    bx=x+off.x; by=y+off.y
                    bz=self.world_height_at(bx,by)+height*hs*0.46
                    bulb(Vec3(bx,by,bz), radius*rs*0.72, radius*rs*0.60, height*hs*0.58,
                         heading+bi*0.31, 7)
                contour_polys.append(self.ellipse_points(radius*0.84, radius*0.70, count=10, phase_deg=math.degrees(heading), center=Vec3(x,y,base_z+height*0.46)))

            else:  # arch-like twin stems with one broad fungal bridge cap.
                half = radius * 0.54
                left = center + cross * half
                right = center - cross * half
                pillar_h = height * 0.68
                left_drift = axis * radius * 0.10
                right_drift = axis * radius * -0.06
                prism(left, base_z+0.04, base_z+pillar_h, radius*0.18, radius*0.11,
                      heading, 7, stem_dark, stem_mid, left_drift)
                prism(right, base_z+0.04, base_z+pillar_h*0.94, radius*0.18, radius*0.11,
                      heading+0.16, 7, stem_dark, stem_mid, right_drift)
                bridge_center=Vec3(x+axis.x*radius*0.04,y+axis.y*radius*0.04,base_z+pillar_h)
                cap(bridge_center, bridge_center.z,
                    radius*1.18, radius*0.52, radius*0.34,
                    heading, sides=10)
                detail_segments.append((Vec3(left.x,left.y,base_z+pillar_h*0.70), Vec3(right.x,right.y,base_z+pillar_h*0.66)))

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gnode = GeomNode(str(name))
        gnode.addGeom(geom)
        np = parent.attachNewNode(gnode)
        np.setLightOff(1)
        np.setTextureOff(10)
        np.setTransparency(TransparencyAttrib.MNone)
        np.setDepthWrite(True)
        np.setDepthTest(True)
        np.setTwoSided(True)
        np.setPythonTag("mushroom_solid_batched", 1)
        np.setPythonTag("mushroom_solid_structure_count", len(items))
        if contour_polys:
            self.add_polyline_batch(parent, contour_polys, hardlight,
                                    self.cfg.line_thickness * 0.34, True,
                                    f"{name}-hardlight-contours")
        if detail_segments:
            self.add_line_segments(parent, detail_segments, softlight,
                                   self.cfg.line_thickness * 0.22,
                                   f"{name}-soft-details")
        return np

    def build_mushroom_solid_structure_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        if str(ring.get("kind", "")) != "mushroom":
            return 0
        travel = region_travel_for_number(3) or {}
        items = generate_mushroom_structures(
            int(sector_idx), float(ring["r0"]), float(ring["r1"]),
            sector_count=BIOME_SECTOR_COUNT,
            corridor_degrees=BIOME_CORRIDOR_DEGREES,
            solace_radius=float(travel.get("radius", 1972.0)),
            landing_radius=float(travel.get("landing_radius", 1918.0)),
            anchor_angle_deg=BIOME_ANCHOR_ANGLE_DEG,
        )
        if not items:
            parent.setPythonTag("mushroom_solid_structure_count", 0)
            return 0
        self.add_mushroom_solid_batch(parent, items, ring,
                                      f"mushroom-solids-{int(sector_idx):02d}")
        parent.setPythonTag("mushroom_solid_structure_count", len(items))
        parent.setPythonTag("mushroom_solid_pass28234", 1)
        return len(items)

    def build_mushroom_wire_forest_set(self, parent, ring, sector_idx: int, a0: float, a1: float):
        """Build the secondary pink/cyan mushroom line grammar in batches.

        Pass 282.34 preserves the established small mushroom identity but stops
        creating several NodePaths for every individual mushroom.  All stems,
        caps, gills, and dots of a sector are accumulated into a handful of
        LineSegs batches so Mushroom can safely become a full 48-sector ring.
        """
        rng = random.Random(85000 + int(sector_idx) * 977 + int(ring.get("key", 4)) * 131)
        fallback_ring = surface_ring_for_key(4) or {"r0": 1650.0, "r1": 2350.0}
        r0 = float(ring.get("r0", fallback_ring["r0"]))
        r1 = float(ring.get("r1", fallback_ring["r1"]))
        groups = int(max(4, globals().get("MUSHROOM_FOREST_GROUPS_PER_CHUNK", 8)))
        pink = self.biome_color(ring, alpha=0.92, brighten=1.05, channel="line")
        cyan = self.biome_color(ring, alpha=0.88, brighten=1.04, channel="accent")
        stem = self.biome_color(ring, alpha=0.76, brighten=0.92, channel="trunk")
        canopy = self.biome_color(ring, alpha=0.70, brighten=1.00, channel="canopy")
        soft = self.biome_color(ring, alpha=0.52, brighten=0.82, channel="soft")
        infill_segments = []
        hill_highlights = []
        stem_cores = []
        stem_ribs = []
        lower_caps = []
        upper_caps = []
        cap_struts = []
        gill_segments = []
        dot_segments = []
        built = 0

        for i in range(max(2, int(globals().get("MUSHROOM_HILL_LINE_COUNT", 8)))):
            f = (i + 0.5) / max(1, int(globals().get("MUSHROOM_HILL_LINE_COUNT", 8)))
            rr = lerp(r0 + 36.0, r1 - 36.0, f)
            pts = []
            for j in range(9):
                aa = lerp(a0, a1, j / 8.0)
                x = math.cos(aa) * rr
                y = math.sin(aa) * rr
                gz = self.world_height_at(x, y)
                pts.append(Vec3(x, y, gz + 0.18))
                if j in (1, 3, 5, 7):
                    infill_segments.append((Vec3(x, y, self.hub_ground_level() + 0.08), Vec3(x, y, gz + 0.16)))
            hill_highlights.append(pts)

        for idx in range(groups):
            cluster_t = rng.uniform(0.12, 0.88)
            cluster_a = rng.uniform(a0 + 0.018, a1 - 0.018)
            cluster_r = lerp(r0 + 50.0, r1 - 50.0, cluster_t)
            cluster_count = 2 + (idx % 4)
            for j in range(cluster_count):
                aa = cluster_a + rng.uniform(-0.022, 0.022)
                rr = cluster_r + rng.uniform(-42.0, 42.0)
                x = math.cos(aa) * rr
                y = math.sin(aa) * rr
                ground = self.world_height_at(x, y)
                height = rng.uniform(5.5, 16.0) * (1.18 if j == 0 else 0.82)
                stem_r = rng.uniform(0.55, 1.20) * (1.15 if j == 0 else 0.82)
                cap_r = rng.uniform(3.2, 8.5) * (1.25 if j == 0 else 0.86)
                cap_z = ground + height
                base = Vec3(x, y, ground + 0.12)
                top = Vec3(x, y, cap_z)
                tilt_angle = aa + math.pi * 0.5
                tilt = Vec3(math.cos(tilt_angle), math.sin(tilt_angle), 0.0) * rng.uniform(-0.65, 0.65)
                top = top + tilt
                stem_cores.append((base, top))
                for k in range(6):
                    ang = math.tau * k / 6.0 + aa
                    off = Vec3(math.cos(ang) * stem_r, math.sin(ang) * stem_r, 0.0)
                    stem_ribs.append((base + off * 0.60, top + off * 0.26))

                lower=[]; upper=[]
                cap_steps=int(max(6,globals().get("MUSHROOM_CLUSTER_CAP_STEPS",8)))
                for k in range(cap_steps):
                    ang=math.tau*k/cap_steps+math.radians(22.5)
                    radial=Vec3(math.cos(ang),math.sin(ang),0.0)
                    lower.append(top+radial*cap_r+Vec3(0,0,-0.32*cap_r))
                    upper.append(top+radial*(cap_r*0.72)+Vec3(0,0,0.30*cap_r))
                lower_caps.append(lower); upper_caps.append(upper)
                for k in range(cap_steps):
                    cap_struts.append((lower[k],upper[k]))
                    gill_segments.append((top+Vec3(0,0,-0.12*cap_r),lower[k]))
                for d in range(3):
                    spot=upper[(d*2+idx+j)%len(upper)]
                    size=0.65+0.18*d
                    dot_segments.append((spot+Vec3(-size,0,0),spot+Vec3(size,0,0)))
                    dot_segments.append((spot+Vec3(0,-size,0),spot+Vec3(0,size,0)))
                built += 1

        self.add_polyline_batch(parent,hill_highlights,cyan,self.cfg.line_thickness*0.68,False,f"mushroom-hill-contours-{sector_idx:02d}")
        self.add_line_segments(parent,infill_segments,(0.95,0.18,0.92,0.38),self.cfg.line_thickness*0.36,f"mushroom-ground-infill-ribs-{sector_idx:02d}")
        self.add_line_segments(parent,stem_cores,stem,self.cfg.line_thickness*0.74,f"mushroom-stem-cores-{sector_idx:02d}")
        self.add_line_segments(parent,stem_ribs,soft,self.cfg.line_thickness*0.38,f"mushroom-stem-ribs-{sector_idx:02d}")
        self.add_polyline_batch(parent,lower_caps,pink,self.cfg.line_thickness*0.82,True,f"mushroom-cap-lower-{sector_idx:02d}")
        self.add_polyline_batch(parent,upper_caps,canopy,self.cfg.line_thickness*0.62,True,f"mushroom-cap-upper-{sector_idx:02d}")
        self.add_line_segments(parent,cap_struts,pink,self.cfg.line_thickness*0.44,f"mushroom-cap-struts-{sector_idx:02d}")
        self.add_line_segments(parent,gill_segments,cyan,self.cfg.line_thickness*0.24,f"mushroom-gills-{sector_idx:02d}")
        self.add_line_segments(parent,dot_segments,(0.06,1.0,1.0,0.62),self.cfg.line_thickness*0.18,f"mushroom-spots-{sector_idx:02d}")
        parent.setPythonTag("mushroom_wire_count", int(built))
        parent.setPythonTag("mushroom_wire_batched_pass28234", 1)
        return built

    def build_biome_terrain_chunk(self, ring, sector_idx: int):
        key = (int(ring["key"]), int(sector_idx) % BIOME_SECTOR_COUNT)
        if key in self.terrain_chunks:
            return self.terrain_chunks[key]
        parent = self.world_root.attachNewNode(f"biome-chunk-{ring['name']}-{key[1]:02d}")
        owned_a0, owned_a1 = self.biome_sector_angle_span(key[1], expanded=False)
        stream_a0, stream_a1 = self.biome_sector_angle_span(key[1], expanded=True)
        r0 = ring["r0"]
        r1 = ring["r1"]
        kind = str(ring.get("kind", ""))
        is_water_region = kind == "water"
        fill_color = self.biome_ground_fill_color(ring, alpha=1.0 if not is_water_region else 0.0, brighten=0.0)
        line_color = self.biome_color(ring, alpha=0.70, brighten=0.96, channel="line")
        soft_line_color = self.biome_color(ring, alpha=0.42, brighten=0.80, channel="soft")
        accent_line_color = self.biome_color(ring, alpha=0.66, brighten=1.0, channel="accent")

        ring_ground_active = bool(self.ring_ground_active_for(kind))
        parent.setPythonTag("ring_ground_active", 1 if ring_ground_active else 0)
        if not is_water_region:
            fill_r0 = float(self.biome_inner_presentation_band_outer_radius(ring))
            fill_r0 = max(float(r0), min(float(r1) - 1.0, fill_r0))
            if ring_ground_active:
                ground_tier = self.ring_ground_tier_for_sector(ring, key[1])
                fill_np = _ring_ground.build_sector_ground(parent, ring, fill_r0, r1, owned_a0, owned_a1, ground_tier, name=f"biome-fill-{ring['name']}", gsg=self.ring_ground_gsg())
                parent.setPythonTag("ring_ground_tier", str(ground_tier))
            elif kind == "desert":
                fill_np = self.add_desert_annular_sector_surface(parent, ring, fill_r0, r1, owned_a0, owned_a1, f"biome-fill-{ring['name']}", radial_steps=18, angular_steps=12)
            elif kind == "ice":
                fill_np = self.add_ice_annular_sector_surface(parent, ring, fill_r0, r1, owned_a0, owned_a1, f"biome-fill-{ring['name']}", radial_steps=18, angular_steps=12)
            else:
                fill_np = self.add_annular_sector_surface(parent, fill_r0, r1, owned_a0, owned_a1, fill_color, f"biome-fill-{ring['name']}", radial_steps=14, angular_steps=8)
            self.tag_surface_authority(fill_np, "biome_fill", kind, f"{int(ring['key'])}:{key[1]}", 60, ring_key=int(ring["key"]), sector=int(key[1]), r0=float(fill_r0), r1=float(r1), a0=float(owned_a0), a1=float(owned_a1))
            parent.setPythonTag("surface_fill_r0", float(fill_r0))
            parent.setPythonTag("surface_fill_r1", float(r1))
            parent.setPythonTag("continuous_inner_band_outer_r", float(fill_r0))

        if not is_water_region and not ring_ground_active:
            radial_guides = []
            for ai in range(0, 5):
                ang = lerp(owned_a0, owned_a1, ai / 4.0)
                pts = []
                for ri in range(0, 14):
                    radius = lerp(r0, r1, ri / 13.0)
                    x = math.cos(ang) * radius
                    y = math.sin(ang) * radius
                    pts.append(Vec3(x, y, self.world_height_at(x, y) + 0.08))
                radial_guides.append(pts)
            ring_guides = []
            for ri in range(0, 6):
                radius = lerp(r0, r1, ri / 5.0)
                pts = []
                for ai in range(0, 14):
                    ang = lerp(owned_a0, owned_a1, ai / 13.0)
                    x = math.cos(ang) * radius
                    y = math.sin(ang) * radius
                    pts.append(Vec3(x, y, self.world_height_at(x, y) + 0.09))
                ring_guides.append(pts)
            self.add_polyline_batch(parent, radial_guides, soft_line_color, self.cfg.line_thickness * 0.60, False, f"biome-radial-guides-{ring['name']}")
            self.add_polyline_batch(parent, ring_guides, line_color, self.cfg.line_thickness * 0.66, False, f"biome-contours-{ring['name']}")
            feature_guides = self.biome_feature_guide_lines(ring, owned_a0, owned_a1)
            if feature_guides:
                self.add_polyline_batch(parent, feature_guides, line_color, self.cfg.line_thickness * 0.54, False, f"biome-terrain-signature-{ring['name']}")
            lush_accent_guides = self.biome_lush_accent_lines(ring, owned_a0, owned_a1)
            if lush_accent_guides:
                self.add_polyline_batch(parent, lush_accent_guides, accent_line_color, self.cfg.line_thickness * 0.50, False, f"biome-lush-accent-strokes-{ring['name']}")
                parent.setPythonTag("lush_accent_line_count", len(lush_accent_guides))
        else:
            # Pass 56: the water ring no longer draws a land/terrain fill mesh or
            # terrain-following contour grid. Water owns the visual field here.
            parent.setPythonTag("deep_water_ground_removed", 1)

        forest_tree_count = 0
        forest_detail_patch_count = 0
        forest_detail_tree_count = 0
        forest_detail_crown_count = 0
        forest_understory_bush_count = 0
        forest_understory_fern_count = 0
        forest_understory_grass_count = 0
        forest_understory_deadfall_count = 0
        hill_flower_count = 0
        hills_solid_tree_count = 0
        desert_pyramid_count = 0
        desert_obelisk_count = 0
        desert_natural_structure_count = 0
        desert_mesa_count = 0
        desert_rock_spire_count = 0
        desert_boulder_field_count = 0
        desert_buried_ruin_count = 0
        ice_cube_count = 0
        ice_floating_cube_count = 0
        ice_fauna_count = 0
        ice_macro_structure_count = 0
        ice_glacial_ridge_count = 0
        ice_crystal_spire_count = 0
        ice_shelf_count = 0
        ice_pressure_ridge_count = 0
        ice_crevasse_fin_count = 0
        deep_water_creature_count = 0
        deep_water_flora_count = 0
        deep_water_feature_count = 0
        deep_water_hero_count = 0
        deep_water_coral_count = 0
        deep_water_bubble_count = 0
        water_surface_line_count = 0
        urban_ruin_count = 0
        urban_structure_count = 0
        urban_structured_block_count = 0
        urban_battle_count = 0
        urban_mech_count = 0
        urban_drone_count = 0
        urban_skeleton_count = 0
        urban_airstrike_count = 0
        urban_trench_count = 0
        urban_smoke_count = 0
        urban_street_lane_count = 0
        urban_frontline_anchor_count = 0
        urban_battle_beam_count = 0
        mushroom_wire_count = 0
        mushroom_solid_structure_count = 0
        mini_jungle_oasis_count = 0
        mini_venus_oasis_count = 0
        deep_water_sky_creature_count = 0
        salvage_population_count = 0
        if str(ring.get("kind", "")) == "forest":
            trunk_color = self.biome_color(ring, alpha=0.68, brighten=0.82, channel="trunk")
            canopy_color = self.biome_color(ring, alpha=0.86, brighten=1.0, channel="canopy")
            forest_tree_count = self.build_forest_tree_set(parent, ring, key[1], owned_a0, owned_a1, trunk_color, canopy_color)
            forest_detail = self.build_forest_dense_detail_set(parent, ring, key[1], owned_a0, owned_a1)
            forest_detail_patch_count = int(forest_detail.get("patches", 0))
            forest_detail_tree_count = int(forest_detail.get("detail_trees", 0))
            forest_detail_crown_count = int(forest_detail.get("crowns", 0))
            forest_understory = self.build_forest_understory_set(parent, ring, key[1], owned_a0, owned_a1)
            forest_understory_bush_count = int(forest_understory.get("bushes", 0))
            forest_understory_fern_count = int(forest_understory.get("ferns", 0))
            forest_understory_grass_count = int(forest_understory.get("grass", 0))
            forest_understory_deadfall_count = int(forest_understory.get("deadfall", 0))
        elif str(ring.get("kind", "")) == "hills":
            stem_color = self.biome_color(ring, alpha=0.84, brighten=0.92, channel="canopy")
            flower_color = self.biome_color(ring, alpha=0.88, brighten=1.02, channel="accent")
            hill_flower_count = self.build_hill_flower_set(parent, ring, key[1], owned_a0, owned_a1, stem_color, flower_color)
            hills_solid_tree_count = self.build_hills_solid_tree_set(parent, ring, key[1], owned_a0, owned_a1)
        elif str(ring.get("kind", "")) == "mushroom" and self.fungal_civilization_active():
            fungal_counts = self.build_fungal_civilization_set(parent, ring, key[1])
            mushroom_solid_structure_count = int(fungal_counts.get("mushrooms", 0))
        elif str(ring.get("kind", "")) == "mushroom":
            mushroom_solid_structure_count = self.build_mushroom_solid_structure_set(parent, ring, key[1], owned_a0, owned_a1)
            mushroom_wire_count = self.build_mushroom_wire_forest_set(parent, ring, key[1], owned_a0, owned_a1)
        elif str(ring.get("kind", "")) == "desert" and self.desert_civilization_active():
            desert_counts = self.build_desert_civilization_set(parent, ring, key[1])
            desert_pyramid_count = int(desert_counts.get("pyramids", 0))
            desert_obelisk_count = int(desert_counts.get("obelisks", 0))
        elif str(ring.get("kind", "")) == "desert":
            natural_counts = self.build_desert_macro_structure_set(parent, ring, key[1], owned_a0, owned_a1)
            desert_natural_structure_count = int(natural_counts.get("total", 0))
            desert_mesa_count = int(natural_counts.get("mesas", 0))
            desert_rock_spire_count = int(natural_counts.get("spires", 0))
            desert_boulder_field_count = int(natural_counts.get("boulders", 0))
            desert_buried_ruin_count = int(natural_counts.get("ruins", 0))
            desert_line = self.biome_color(ring, alpha=0.82, brighten=0.94, channel="line")
            desert_accent = self.biome_color(ring, alpha=0.88, brighten=1.02, channel="accent")
            desert_pyramid_count, desert_obelisk_count = self.build_desert_pyramid_set(parent, ring, key[1], owned_a0, owned_a1, desert_line, desert_accent)
        elif str(ring.get("kind", "")) == "ice" and self.ice_civilization_active():
            ice_counts = self.build_ice_civilization_set(parent, ring, key[1])
            ice_macro_structure_count = int(parent.getPythonTag("ice_macro_structure_count") or 0)
            ice_crystal_spire_count = int(ice_counts.get("spires", 0))
        elif str(ring.get("kind", "")) == "ice":
            macro_counts = self.build_ice_macro_structure_set(parent, ring, key[1], owned_a0, owned_a1)
            ice_macro_structure_count = int(macro_counts.get("total", 0))
            ice_glacial_ridge_count = int(macro_counts.get("ridges", 0))
            ice_crystal_spire_count = int(macro_counts.get("spires", 0))
            ice_shelf_count = int(macro_counts.get("shelves", 0))
            ice_pressure_ridge_count = int(macro_counts.get("pressure", 0))
            ice_crevasse_fin_count = int(macro_counts.get("crevasses", 0))
            ice_line = self.biome_color(ring, alpha=0.74, brighten=0.94, channel="line")
            ice_accent = self.biome_color(ring, alpha=0.80, brighten=1.04, channel="accent")
            ice_cube_count, ice_floating_cube_count = self.build_ice_cube_set(parent, ring, key[1], owned_a0, owned_a1, ice_line, ice_accent)
            ice_fauna_count = self.build_ice_fauna_set(parent, ring, key[1], owned_a0, owned_a1, ice_line, ice_accent)
        elif str(ring.get("kind", "")) == "water":
            if int(globals().get("DEEP_WATER_SURFACE_MAX_LINES_PER_CHUNK", 0) or 0) > 0:
                surface_node = self.build_deep_water_surface_set(parent, ring, key[1], owned_a0, owned_a1)
                water_surface_line_count = int(surface_node.getPythonTag("water_surface_line_count") or 0)
            else:
                water_surface_line_count = 0
                parent.setPythonTag("deep_water_surface_disabled", 1)
                parent.setPythonTag("no_above_terrain_water", 1)
            if not bool(globals().get("DEEP_WATER_LITE_MODE", True)):
                deep_water_creature_count = self.build_deep_water_creature_set(parent, ring, key[1], owned_a0, owned_a1)
                deep_water_flora_count = self.build_deep_water_flora_set(parent, ring, key[1], owned_a0, owned_a1)
                feature_counts = self.build_deep_water_feature_set(parent, ring, key[1], owned_a0, owned_a1)
                deep_water_feature_count = int(feature_counts.get("features", 0))
                deep_water_hero_count = int(feature_counts.get("hero", 0))
                deep_water_coral_count = int(feature_counts.get("coral", 0))
                deep_water_bubble_count = int(feature_counts.get("bubble", 0))
            parent.setPythonTag("deep_water_lite_mode", 1)
        elif str(ring.get("kind", "")) == "urban":
            urban_counts = self.build_urban_city_set(parent, ring, key[1], owned_a0, owned_a1)
            urban_structure_count = int(urban_counts.get("structures", 0))
            urban_structured_block_count = int(urban_counts.get("blocks", 0))
            urban_street_lane_count = int(urban_counts.get("streets", 0))
            parent.setPythonTag("urban_permanent_city_pass28239", 1)
        # Salvaged artifact-world content is now embedded as oasis mini-biomes, never as separate broken destinations.
        if str(ring.get("kind", "")) == "hills":
            mini_jungle_oasis_count = self.build_jungle_oasis_set(parent, ring, key[1], owned_a0, owned_a1)
        if str(ring.get("kind", "")) == "desert":
            mini_venus_oasis_count = self.build_venus_oasis_set(parent, ring, key[1], owned_a0, owned_a1)
        if str(ring.get("kind", "")) == "water":
            # Pass 82: keep the water ring visually grounded.  Airborne ocean
            # life is disabled so the region no longer reads as suspended water
            # volume above the terrain.
            deep_water_sky_creature_count = 0
        salvage_population_count = 0 if (str(ring.get("kind", "")) == "mushroom" or (str(ring.get("kind", "")) == "urban" and self.urban_conflict_active()) or (str(ring.get("kind", "")) == "ice" and self.ice_civilization_active()) or (str(ring.get("kind", "")) == "desert" and self.desert_civilization_active())) else self.build_salvage_population_set(parent, ring, key[1], owned_a0, owned_a1)

        if ring_ground_active:
            # Pass 282.51: the shaded ground has no sector panels to stitch and
            # carries its own near-player holographic grid, so the wire seam,
            # stitch-rail, contour and accent-stroke layers are not built.
            parent.setPythonTag("ring_ground_wire_layers_retired", 1)
        elif not is_water_region:
            # Pass 34: stitch rails on sector edges. These make streamed terrain
            # chunks read as one continuous annular field instead of separate panels.
            stitch_guides = []
            for edge_ang in (owned_a0,):
                pts = []
                for ri in range(0, 34):
                    radius = lerp(r0, r1, ri / 33.0)
                    x = math.cos(edge_ang) * radius
                    y = math.sin(edge_ang) * radius
                    pts.append(Vec3(x, y, self.world_height_at(x, y) + 0.145))
                stitch_guides.append(pts)
                tangent = Vec3(-math.sin(edge_ang), math.cos(edge_ang), 0.0)
                for t in (0.25, 0.50, 0.75):
                    radius = lerp(r0, r1, t)
                    x = math.cos(edge_ang) * radius
                    y = math.sin(edge_ang) * radius
                    z = self.world_height_at(x, y) + 0.155
                    span = 4.2 if int(ring["key"]) < 7 else 6.0
                    stitch_guides.append([Vec3(x, y, z) - tangent * span, Vec3(x, y, z) + tangent * span])
            self.add_polyline_batch(parent, stitch_guides, soft_line_color, self.cfg.line_thickness * 0.72, False, f"biome-chunk-stitch-rails-{ring['name']}")

            # Strong seam lines show that every altitude/depth returns to the shared floor.
            seam_polys = []
            for radius in (r0, r1):
                pts = []
                for ai in range(0, 18):
                    ang = lerp(owned_a0, owned_a1, ai / 17.0)
                    pts.append(Vec3(math.cos(ang) * radius, math.sin(ang) * radius, self.hub_ground_level() + 0.12))
                seam_polys.append(pts)
            self.add_polyline_batch(parent, seam_polys, line_color, self.cfg.line_thickness * 0.82, False, f"biome-seams-{ring['name']}")
        else:
            # No sea-floor seam/stitch lines. The shore is communicated by fog,
            # wave boundaries, and the craft transition only.
            parent.setPythonTag("deep_water_terrain_stitch_removed", 1)

        parent.setPythonTag("forest_tree_count", int(parent.getPythonTag("forest_tree_count") or forest_tree_count or 0))
        parent.setPythonTag("forest_detail_patch_count", int(forest_detail_patch_count))
        parent.setPythonTag("forest_detail_tree_count", int(forest_detail_tree_count))
        parent.setPythonTag("forest_detail_crown_count", int(forest_detail_crown_count))
        parent.setPythonTag("forest_understory_bush_count", int(forest_understory_bush_count))
        parent.setPythonTag("forest_understory_fern_count", int(forest_understory_fern_count))
        parent.setPythonTag("forest_understory_grass_count", int(forest_understory_grass_count))
        parent.setPythonTag("forest_understory_deadfall_count", int(forest_understory_deadfall_count))
        parent.setPythonTag("forest_understory_pass28231", 1 if kind == "forest" else 0)
        parent.setPythonTag("forest_full_ring_density_pass28221", 1 if kind == "forest" else 0)
        parent.setPythonTag("hill_flower_count", int(parent.getPythonTag("hill_flower_count") or hill_flower_count or 0))
        parent.setPythonTag("hills_solid_tree_count", int(parent.getPythonTag("hills_solid_tree_count") or hills_solid_tree_count or 0))
        parent.setPythonTag("hills_solid_tree_pass28245", 1 if kind == "hills" else 0)
        parent.setPythonTag("desert_pyramid_count", int(parent.getPythonTag("desert_pyramid_count") or desert_pyramid_count or 0))
        parent.setPythonTag("desert_obelisk_count", int(parent.getPythonTag("desert_obelisk_count") or desert_obelisk_count or 0))
        parent.setPythonTag("desert_natural_structure_count", int(parent.getPythonTag("desert_natural_structure_count") or desert_natural_structure_count or 0))
        parent.setPythonTag("desert_mesa_count", int(parent.getPythonTag("desert_mesa_count") or desert_mesa_count or 0))
        parent.setPythonTag("desert_rock_spire_count", int(parent.getPythonTag("desert_rock_spire_count") or desert_rock_spire_count or 0))
        parent.setPythonTag("desert_boulder_field_count", int(parent.getPythonTag("desert_boulder_field_count") or desert_boulder_field_count or 0))
        parent.setPythonTag("desert_buried_ruin_count", int(parent.getPythonTag("desert_buried_ruin_count") or desert_buried_ruin_count or 0))
        parent.setPythonTag("ice_cube_count", int(parent.getPythonTag("ice_cube_count") or ice_cube_count or 0))
        parent.setPythonTag("ice_floating_cube_count", int(parent.getPythonTag("ice_floating_cube_count") or ice_floating_cube_count or 0))
        parent.setPythonTag("ice_fauna_count", int(parent.getPythonTag("ice_fauna_count") or ice_fauna_count or 0))
        parent.setPythonTag("ice_macro_structure_count", int(parent.getPythonTag("ice_macro_structure_count") or ice_macro_structure_count or 0))
        parent.setPythonTag("ice_glacial_ridge_count", int(parent.getPythonTag("ice_glacial_ridge_count") or ice_glacial_ridge_count or 0))
        parent.setPythonTag("ice_crystal_spire_count", int(parent.getPythonTag("ice_crystal_spire_count") or ice_crystal_spire_count or 0))
        parent.setPythonTag("ice_shelf_count", int(parent.getPythonTag("ice_shelf_count") or ice_shelf_count or 0))
        parent.setPythonTag("ice_pressure_ridge_count", int(parent.getPythonTag("ice_pressure_ridge_count") or ice_pressure_ridge_count or 0))
        parent.setPythonTag("ice_crevasse_fin_count", int(parent.getPythonTag("ice_crevasse_fin_count") or ice_crevasse_fin_count or 0))
        parent.setPythonTag("deep_water_creature_count", int(parent.getPythonTag("deep_water_creature_count") or deep_water_creature_count or 0))
        parent.setPythonTag("deep_water_flora_count", int(parent.getPythonTag("deep_water_flora_count") or deep_water_flora_count or 0))
        parent.setPythonTag("deep_water_feature_count", int(parent.getPythonTag("deep_water_feature_count") or deep_water_feature_count or 0))
        parent.setPythonTag("deep_water_hero_count", int(parent.getPythonTag("deep_water_hero_count") or deep_water_hero_count or 0))
        parent.setPythonTag("deep_water_coral_count", int(parent.getPythonTag("deep_water_coral_count") or deep_water_coral_count or 0))
        parent.setPythonTag("deep_water_bubble_count", int(parent.getPythonTag("deep_water_bubble_count") or deep_water_bubble_count or 0))
        parent.setPythonTag("water_surface_line_count", int(parent.getPythonTag("water_surface_line_count") or water_surface_line_count or 0))
        parent.setPythonTag("urban_ruin_count", int(parent.getPythonTag("urban_ruin_count") or urban_ruin_count or 0))
        parent.setPythonTag("urban_structure_count", int(parent.getPythonTag("urban_structure_count") or urban_structure_count or 0))
        parent.setPythonTag("urban_structured_block_count", int(parent.getPythonTag("urban_structured_block_count") or urban_structured_block_count or 0))
        parent.setPythonTag("urban_battle_count", int(parent.getPythonTag("urban_battle_count") or urban_battle_count or 0))
        parent.setPythonTag("urban_mech_count", int(parent.getPythonTag("urban_mech_count") or urban_mech_count or 0))
        parent.setPythonTag("urban_drone_count", int(parent.getPythonTag("urban_drone_count") or urban_drone_count or 0))
        parent.setPythonTag("urban_skeleton_count", int(parent.getPythonTag("urban_skeleton_count") or urban_skeleton_count or 0))
        parent.setPythonTag("urban_airstrike_count", int(parent.getPythonTag("urban_airstrike_count") or urban_airstrike_count or 0))
        parent.setPythonTag("urban_trench_count", int(parent.getPythonTag("urban_trench_count") or urban_trench_count or 0))
        parent.setPythonTag("urban_smoke_count", int(parent.getPythonTag("urban_smoke_count") or urban_smoke_count or 0))
        parent.setPythonTag("urban_street_lane_count", int(parent.getPythonTag("urban_street_lane_count") or urban_street_lane_count or 0))
        parent.setPythonTag("urban_frontline_anchor_count", int(parent.getPythonTag("urban_frontline_anchor_count") or urban_frontline_anchor_count or 0))
        parent.setPythonTag("urban_battle_beam_count", int(parent.getPythonTag("urban_battle_beam_count") or urban_battle_beam_count or 0))
        parent.setPythonTag("mushroom_wire_count", int(parent.getPythonTag("mushroom_wire_count") or mushroom_wire_count or 0))
        parent.setPythonTag("mushroom_solid_structure_count", int(parent.getPythonTag("mushroom_solid_structure_count") or mushroom_solid_structure_count or 0))
        parent.setPythonTag("mushroom_solid_pass28234", 1 if kind == "mushroom" else 0)
        parent.setPythonTag("mini_jungle_oasis_count", int(parent.getPythonTag("mini_jungle_oasis_count") or mini_jungle_oasis_count or 0))
        parent.setPythonTag("mini_venus_oasis_count", int(parent.getPythonTag("mini_venus_oasis_count") or mini_venus_oasis_count or 0))
        parent.setPythonTag("deep_water_sky_creature_count", int(parent.getPythonTag("deep_water_sky_creature_count") or deep_water_sky_creature_count or 0))
        parent.setPythonTag("salvage_population_count", int(parent.getPythonTag("salvage_population_count") or salvage_population_count or 0))
        parent.setPythonTag("surface_owner_key", f"{int(ring['key'])}:{key[1]}")
        parent.setPythonTag("surface_owner_kind", kind)
        parent.setPythonTag("surface_sector", int(key[1]))
        parent.setPythonTag("surface_fill_enabled", int(0 if is_water_region else 1))
        parent.setPythonTag("surface_owned_a0", float(owned_a0))
        parent.setPythonTag("surface_owned_a1", float(owned_a1))
        if kind == "forest":
            parent.setPythonTag("forest_full_ring_streaming_pass28224", 1)
            parent.setPythonTag("forest_full_ring_sector", int(key[1]))
        self.terrain_chunks[key] = parent
        return parent

    # ------------------------------------------------------------------
    # Pass 282.51: shaded ring ground, distance tiers and paced streaming
    # ------------------------------------------------------------------
    def ring_ground_active_for(self, kind) -> bool:
        if not RING_GROUND_ENABLED or _ring_ground is None:
            return False
        if not bool(getattr(getattr(self, "cfg", None), "ring_ground_enabled", True)):
            return False
        return str(kind or "") in RING_GROUND_KINDS

    def ring_ground_gsg(self):
        try:
            win = getattr(self, "win", None)
            return win.getGsg() if win is not None else None
        except Exception:
            return None

    def ring_center_sector(self) -> int:
        angle = math.atan2(self.player_pos.y, self.player_pos.x) % math.tau
        return int(angle / (math.tau / BIOME_SECTOR_COUNT)) % BIOME_SECTOR_COUNT

    def ring_sector_delta(self, sector_idx: int, center_sector=None) -> int:
        if center_sector is None:
            center_sector = self.ring_center_sector()
        d = abs(int(sector_idx) - int(center_sector)) % BIOME_SECTOR_COUNT
        return min(d, BIOME_SECTOR_COUNT - d)

    def ring_ground_tier_for_sector(self, ring, sector_idx: int) -> str:
        """Pick the ground detail tier for one sector from the player's position."""
        px, py = float(self.player_pos.x), float(self.player_pos.y)
        pr = math.hypot(px, py)
        if pr <= float(MAIN_AREA_RADIUS):
            # Hub preview of the Forest edge: everything is at least ~290 m away.
            return "far"
        player_ring = self.biome_ring_for_radius(pr)
        if player_ring is not None and int(player_ring.get("key", -1)) == int(ring["key"]):
            if self.ring_sector_delta(sector_idx) <= int(RING_GROUND_NEAR_SECTOR_RADIUS):
                return "near"
        a0, a1 = self.biome_sector_angle_span(sector_idx, expanded=False)
        distance = _ring_ground.sector_distance(px, py, float(ring["r0"]), float(ring["r1"]), a0, a1)
        return _ring_ground.tier_for_distance(distance)

    def ring_chunk_can_defer(self, ring, sector_idx: int, center_sector: int) -> bool:
        if not self.ring_ground_active_for(str(ring.get("kind", ""))):
            return False
        return self.ring_sector_delta(sector_idx, center_sector) > int(RING_GROUND_SYNC_SECTOR_RADIUS)

    def rebuild_ring_ground_tier(self, key, chunk, tier: str) -> bool:
        ring = self.biome_ring_for_key(int(key[0]))
        if ring is None or chunk is None or chunk.isEmpty():
            return False
        owned_a0, owned_a1 = self.biome_sector_angle_span(int(key[1]), expanded=False)
        fill_r0 = float(chunk.getPythonTag("surface_fill_r0") or ring["r0"])
        fill_r1 = float(chunk.getPythonTag("surface_fill_r1") or ring["r1"])
        old_fills = [child for child in chunk.getChildren() if str(child.getPythonTag("surface_role") or "") == "biome_fill"]
        fill_np = _ring_ground.build_sector_ground(chunk, ring, fill_r0, fill_r1, owned_a0, owned_a1, tier, name=f"biome-fill-{ring['name']}", gsg=self.ring_ground_gsg())
        self.tag_surface_authority(fill_np, "biome_fill", str(ring.get("kind", "")), f"{int(ring['key'])}:{int(key[1])}", 60, ring_key=int(ring["key"]), sector=int(key[1]), r0=float(fill_r0), r1=float(fill_r1), a0=float(owned_a0), a1=float(owned_a1))
        for old in old_fills:
            old.removeNode()
        chunk.setPythonTag("ring_ground_tier", str(tier))
        self.ring_ground_tier_rebuild_count = int(getattr(self, "ring_ground_tier_rebuild_count", 0) or 0) + 1
        return True

    def service_ring_ground(self, budget_ms=None):
        """Build deferred ring chunks and retier ground sheets within a frame budget.

        Called once per frame from update_world_chunks.  At least one queued
        chunk is built per frame so the ring always fills in; more are built
        while the frame budget allows.
        """
        budget = float(RING_GROUND_FRAME_BUDGET_MS if budget_ms is None else budget_ms) / 1000.0
        start = time.perf_counter()
        center = self.ring_center_sector()
        queue = list(getattr(self, "_ring_chunk_queue", []) or [])
        targets = getattr(self, "_ring_chunk_targets", set()) or set()
        built = 0
        if queue:
            queue.sort(key=lambda k: (self.ring_sector_delta(k[1], center), k))
            while queue:
                key = queue.pop(0)
                if key in self.terrain_chunks or key not in targets:
                    continue
                ring = self.biome_ring_for_key(key[0])
                if ring is None:
                    continue
                self.build_biome_terrain_chunk(ring, key[1])
                built += 1
                if time.perf_counter() - start >= budget:
                    break
            self._ring_chunk_queue = queue
            self.ring_chunk_deferred_built_count = int(getattr(self, "ring_chunk_deferred_built_count", 0) or 0) + built
            if not queue:
                self.audit_surface_authority()
        metro_queue = list(getattr(self, "_metro_chunk_queue", []) or [])
        if metro_queue:
            metro_targets = getattr(self, "_metro_chunk_targets", set()) or set()
            pk = _metro_layout.chunk_key_for_point(self.player_pos.x, self.player_pos.y)
            metro_queue.sort(key=lambda k: (max(abs(k[0] - pk[0]), abs(k[1] - pk[1])), k))
            while metro_queue:
                if built and time.perf_counter() - start >= budget:
                    break
                key = metro_queue.pop(0)
                if key in self.metropolis_chunks or key not in metro_targets:
                    continue
                self.build_metropolis_chunk(key[0], key[1])
                built += 1
            self._metro_chunk_queue = metro_queue
        now = time.perf_counter()
        last_center = getattr(self, "_ring_ground_last_center", None)
        due = now - float(getattr(self, "_ring_ground_last_tier_check", 0.0) or 0.0) >= float(RING_GROUND_TIER_CHECK_SECONDS)
        if due or last_center != center:
            self._ring_ground_last_tier_check = now
            self._ring_ground_last_center = center
            order = {name: idx for idx, name in enumerate(("near", "mid", "far"))}
            wanted = []
            for key, chunk in list(self.terrain_chunks.items()):
                try:
                    current = chunk.getPythonTag("ring_ground_tier")
                except Exception:
                    continue
                if not current:
                    continue
                ring = self.biome_ring_for_key(int(key[0]))
                if ring is None:
                    continue
                tier = self.ring_ground_tier_for_sector(ring, int(key[1]))
                if tier != str(current):
                    wanted.append((order.get(tier, 3), self.ring_sector_delta(key[1], center), key, tier))
            wanted.sort(key=lambda item: (item[0], item[1]))
            self._ring_tier_pending = [(key, tier) for _rank, _delta, key, tier in wanted]
        pending = list(getattr(self, "_ring_tier_pending", []) or [])
        while pending:
            if built and time.perf_counter() - start >= budget:
                break
            key, tier = pending.pop(0)
            chunk = self.terrain_chunks.get(key)
            if chunk is None or chunk.isEmpty():
                continue
            if str(chunk.getPythonTag("ring_ground_tier") or "") == tier:
                continue
            if self.rebuild_ring_ground_tier(key, chunk, tier):
                built += 1
        self._ring_tier_pending = pending
        return built

    def visible_ground_height_at(self, x: float, y: float) -> float:
        """Height of the drawn ring ground at (x, y).

        The ground sheet is a triangle grid sampled from world_height_at, so
        between vertices it differs slightly from the analytic surface.  The
        player stands on the drawn triangles (same grid, same split) so feet
        never sink into a crest or float over a dip.  Outside shaded ring
        ground this is exactly world_height_at.
        """
        x = float(x); y = float(y)
        radius = math.hypot(x, y)
        ring = self.biome_ring_for_radius(radius)
        if ring is None or not self.ring_ground_active_for(str(ring.get("kind", ""))):
            return self.world_height_at(x, y)
        sector = int((math.atan2(y, x) % math.tau) / (math.tau / BIOME_SECTOR_COUNT)) % BIOME_SECTOR_COUNT
        chunk = (getattr(self, "terrain_chunks", {}) or {}).get((int(ring["key"]), sector))
        if chunk is None or chunk.isEmpty():
            return self.world_height_at(x, y)
        tier = str(chunk.getPythonTag("ring_ground_tier") or "")
        if not tier:
            return self.world_height_at(x, y)
        r0 = float(chunk.getPythonTag("surface_fill_r0") or ring["r0"])
        r1 = float(chunk.getPythonTag("surface_fill_r1") or ring["r1"])
        a0, a1 = self.biome_sector_angle_span(sector, expanded=False)
        rs, as_ = _ring_ground.grid_steps(r0, r1, a0, a1, _ring_ground.tier_cell(tier))
        fr = clamp((radius - r0) / max(1e-6, r1 - r0), 0.0, 1.0) * rs
        fa = clamp(((math.atan2(y, x) - a0) % math.tau) / max(1e-9, a1 - a0), 0.0, 1.0) * as_
        ri = min(rs - 1, int(fr)); ai = min(as_ - 1, int(fa))
        u = fr - ri; v = fa - ai

        def corner(i, j):
            rad = r0 + (r1 - r0) * i / rs
            ang = a0 + (a1 - a0) * j / as_
            return self.world_height_at(math.cos(ang) * rad, math.sin(ang) * rad)

        if u + v <= 1.0:
            h00 = corner(ri, ai)
            return h00 + u * (corner(ri + 1, ai) - h00) + v * (corner(ri, ai + 1) - h00)
        h11 = corner(ri + 1, ai + 1)
        return h11 + (1.0 - u) * (corner(ri, ai + 1) - h11) + (1.0 - v) * (corner(ri + 1, ai) - h11)

    def ring_ground_report(self):
        tiers = {}
        triangles = 0
        for chunk in list((getattr(self, "terrain_chunks", {}) or {}).values()):
            tier = str(chunk.getPythonTag("ring_ground_tier") or "")
            if tier:
                tiers[tier] = tiers.get(tier, 0) + 1
            for child in chunk.getChildren():
                triangles += int(child.getPythonTag("ring_ground_triangles") or 0)
        return {
            "enabled": bool(RING_GROUND_ENABLED and _ring_ground is not None),
            "shader": _ring_ground.shader_status() if _ring_ground is not None else "module_unavailable",
            "tiers": tiers,
            "ground_triangles": triangles,
            "queued_chunks": len(getattr(self, "_ring_chunk_queue", []) or []),
            "deferred_built": int(getattr(self, "ring_chunk_deferred_built_count", 0) or 0),
            "tier_rebuilds": int(getattr(self, "ring_ground_tier_rebuild_count", 0) or 0),
        }

    def target_biome_chunk_keys(self):
        """Return the detailed terrain sectors owned by the player's current ring.

        Pass 282.32 changes residency from the old Forest-retention pilot to an
        exclusive ring lifecycle.  Detailed chunks from the region we left are
        pruned as soon as the new ring becomes authoritative.  Forest, Green Hills, Mushroom, Desert, Ice, and Urban are full-360 resident while active;
        Metropolis keeps its independent unbounded city streamer.
        """
        r = math.sqrt(self.player_pos.x * self.player_pos.x + self.player_pos.y * self.player_pos.y)
        angle = math.atan2(self.player_pos.y, self.player_pos.x) % math.tau
        center_sector = int(angle / (math.tau / BIOME_SECTOR_COUNT)) % BIOME_SECTOR_COUNT
        targets = set()
        active_ring = self.biome_ring_for_radius(r)
        # The central spawn/Observatory sits inside SURFACE_INNER_RADIUS (30),
        # so biome_ring_for_radius() legitimately returns None there.  Treat
        # that inner core as Hub context for the historical Forest horizon.
        hub_context = bool(r <= float(MAIN_AREA_RADIUS) and (active_ring is None or str(active_ring.get("kind", "")) == "flat"))
        if active_ring is None and not hub_context:
            return targets
        kind = str(active_ring.get("kind", "")) if active_ring is not None else "flat"
        ring_key = int(active_ring.get("key", 0) or 0) if active_ring is not None else 0
        if hub_context:
            # Pass 282.43: restore the accepted Hub -> Forest horizon continuity
            # from Pass 282.31.  Forest remains the single detailed preview ring
            # while the player is in the compact Hub; it is pruned immediately
            # when Green Hills (or any later detailed ring) becomes authoritative.
            # This restores the visible tree line from spawn without reverting the
            # reduced 310-960 Forest footprint or retaining Forest inside Hills.
            forest_ring = self.biome_ring_for_key(int(FOREST_FULL_RING_KEY))
            if FOREST_FULL_RING_STREAMING and forest_ring is not None:
                for sector in range(BIOME_SECTOR_COUNT):
                    targets.add((int(forest_ring["key"]), int(sector)))
            return targets
        if kind == "metropolis":
            return targets
        if kind == "water":
            radius = int(DEEP_WATER_ONLY_SECTOR_RADIUS)
            for delta in range(-radius, radius + 1):
                targets.add((ring_key, (center_sector + delta) % BIOME_SECTOR_COUNT))
            return targets
        if ring_key in tuple(int(v) for v in ACTIVE_FULL_RING_KEYS):
            for sector in range(BIOME_SECTOR_COUNT):
                targets.add((ring_key, sector))
            return targets
        for delta in range(-BIOME_STREAM_SECTOR_RADIUS, BIOME_STREAM_SECTOR_RADIUS + 1):
            targets.add((ring_key, (center_sector + delta) % BIOME_SECTOR_COUNT))
        return targets

    def prune_biome_chunks_to_targets(self, targets):
        for key in list(self.terrain_chunks.keys()):
            if key not in targets:
                try:
                    self.terrain_chunks[key].removeNode()
                except Exception:
                    pass
                self.terrain_chunks.pop(key, None)
                self.terrain_chunk_pruned_count += 1
        if len(self.terrain_chunks) > MAX_BIOME_TERRAIN_CHUNKS:
            for key in list(self.terrain_chunks.keys())[: max(0, len(self.terrain_chunks) - MAX_BIOME_TERRAIN_CHUNKS)]:
                try:
                    self.terrain_chunks[key].removeNode()
                except Exception:
                    pass
                self.terrain_chunks.pop(key, None)
                self.terrain_chunk_pruned_count += 1

    def fast_travel_to_biome(self, biome_key: int):
        ring = self.biome_ring_for_key(int(biome_key))
        if ring is None:
            return
        self.player_pos, radius, angle = self.biome_arrival_point(ring)
        focus = self.biome_outward_focus_point(ring, radius, angle)
        yaw, pitch = focus_hpr(self.player_pos, focus)
        self.player_yaw = yaw
        self.player_pitch = max(-32.0, min(18.0, pitch))
        self.camera.setPos(self.player_pos)
        self.camera.setHpr(self.player_yaw, self.player_pitch, 0)
        self.last_biome_travel_key = int(biome_key)
        self.update_world_chunks(force=True)
        self.show_build_hint(f"{biome_key} // {ring['name']} safe arrival // facing outward", 1.4)
        self.refresh_ui()

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

        # Pass 26: table-like console boxes and their dark panel cards removed; hub room is open floor only.

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
        return None

    def get_artifact_by_world_id(self, world_id: int):
        return None

    def build_artifacts(self):
        self.artifacts = []
        self.nearest_artifact = None
        self.nearest_artifact_dist = 999.0
        return

    def world_sector_style(self, spec, idx=0):
        return {"name": "Hub", "color": self.station_line_color(0.5)}

    def build_sector_gates(self):
        return

    def build_lens(self):
        # Pass 28: remove the off-center telescope/cylinder assembly and replace it with
        # a centered observatory beacon that rises directly from the core.
        beacon_color = self.lens_color(0.98)
        inner_color = self.station_glow_color(0.28)
        anchor_z = 6.4
        emitter_z = 8.2
        beam_top_z = 74.0

        # Aligned emitter cage above the core.
        self.add_prism(self.lens_root, 0.96, emitter_z, beacon_color, 8, 22.5, 0.84)
        self.add_prism(self.lens_root, 0.62, emitter_z + 1.2, self.station_line_color(0.72), 8, 22.5, 0.68)
        for z, r, thickness in [(anchor_z + 0.5, 1.55, 0.70), (emitter_z, 1.95, 0.82), (emitter_z + 1.25, 1.35, 0.70)]:
            self.add_polyline(self.lens_root, self.polygon_points(r, z, 8, 22.5), beacon_color, self.cfg.line_thickness * thickness, True, "beacon-ring")

        # Four centered support struts.
        for ang_deg in (22.5, 112.5, 202.5, 292.5):
            ang = math.radians(ang_deg)
            lower = Vec3(math.cos(ang) * 0.82, math.sin(ang) * 0.82, anchor_z)
            upper = Vec3(math.cos(ang) * 0.50, math.sin(ang) * 0.50, emitter_z + 1.2)
            self.add_polyline(self.lens_root, [lower, upper], beacon_color, self.cfg.line_thickness * 0.74, False, "beacon-strut")

        # Central vertical beam and a lighter inner core line.
        self.add_polyline(self.sky_root, [Vec3(0, 0, emitter_z + 0.1), Vec3(0, 0, beam_top_z)], beacon_color, self.cfg.line_thickness * 1.18, False, "beacon-beam")
        self.add_polyline(self.sky_root, [Vec3(0, 0, emitter_z + 0.1), Vec3(0, 0, beam_top_z)], inner_color, self.cfg.line_thickness * 0.54, False, "beacon-beam-inner")

        # Beam guide rings climbing into the dome/sky for a cleaner observatory silhouette.
        for z, r, alpha, tscale in [
            (14.0, 2.8, 0.16, 0.72),
            (24.0, 4.0, 0.12, 0.62),
            (38.0, 5.6, 0.10, 0.58),
            (56.0, 7.6, 0.08, 0.52),
        ]:
            ring_color = hsv_color((self.cfg.line_hue + 0.18) % 1.0, 0.62, 1.0, alpha)
            self.add_polyline(self.sky_root, self.polygon_points(r, z, 8, 22.5), ring_color, self.cfg.line_thickness * tscale, True, "beacon-guide")

    def galaxy_points(self, seed, count=90):
        return []

    def build_galaxy_targets(self):
        self.galaxy_nodes = []
        return

    def hashed_seed(self, *values):
        return abs(hash(tuple(values))) & 0x7fffffff

    def terrain_height_at(self, x, y, scale=1.0):
        return 0.0

    def current_world_spec(self):
        return WORLD_SPECS[0]

    def world_profile(self, spec=None):
        return "hub_only"

    def chunk_axis_positions(self, coord: int, chunk_size: float):
        return []

    def world_anchor_direction(self, spec=None):
        return Vec3(1.0, 0.0, 0.0)

    def world_anchor_distance_for_spec(self, spec=None):
        return self.hub_radius

    def world_anchor_point(self, spec=None):
        return Vec3(0, 0, 0)

    def world_formula_xy(self, x, y, spec=None):
        return 0.0

    def world_hub_clear_radius_for_spec(self, spec=None):
        return self.hub_radius + 2.0

    def hub_ground_level(self):
        return 0.03

    def world_ground_match_radius_for_spec(self, spec=None):
        return self.hub_radius + 2.0

    def world_ground_match_blend_for_spec(self, spec=None):
        return 1.0

    def grade_match_blend_value(self, *args, **kwargs):
        return 1.0

    def align_world_ground_height(self, *args, **kwargs):
        return 0.0

    def point_in_world_corridor(self, *args, **kwargs):
        return False

    def is_world_point_reserved(self, *args, **kwargs):
        return True

    def chunk_has_world_content(self, *args, **kwargs):
        return False

    def add_masked_polyline(self, *args, **kwargs):
        return None

    def add_world_approach_bridge(self, *args, **kwargs):
        return None

    def add_world_outer_ring_staging(self, *args, **kwargs):
        return None

    def clear_world_actors(self):
        for actor in list(getattr(self, "world_actors", [])):
            try:
                actor.root.removeNode()
            except Exception:
                pass
        self.world_actors = []
        self.world_actor_pruned_count = 0

    def prune_world_actor_overflow(self):
        self.clear_world_actors()

    def prune_terrain_chunk_overflow(self, needed=None):
        return

    def clear_world_chunks(self):
        for np in list(getattr(self, "terrain_chunks", {}).values()):
            try:
                np.removeNode()
            except Exception:
                pass
        self.terrain_chunks = {}
        self.terrain_chunk_pruned_count = 0
        self.deep_water_creature_nodes = []
        self.deep_water_glow_nodes = []
        self.deep_water_feature_nodes = []
        self.deep_water_sky_creature_nodes = []
        self.salvage_population_nodes = []
        self.salvage_population_pruned_count = 0
        self.named_region_bot_nodes = []
        self.named_region_bot_specs = []
        self.named_region_bot_pruned_count = 0
        self.deep_water_surface_refresh_time = -999.0
        self.clear_world_actors()

    def apply_world_theme(self, dt):
        self.world_theme_blend = 0.0
        self.current_hub_rgb = self.default_hub_rgb
        self.update_day_night_sky(dt)

    def world_height_at(self, x, y, spec=None):
        return self.hub_ground_level() + self.biome_height_offset_at(float(x), float(y))

    def add_world_actor(self, *args, **kwargs):
        return None

    def add_ship_actor(self, *args, **kwargs):
        return None

    def add_underwater_actor(self, *args, **kwargs):
        return None

    def add_tree_actor(self, *args, **kwargs):
        return None

    def add_bloom_floret(self, *args, **kwargs):
        return None

    def add_ribbon_gate(self, *args, **kwargs):
        return None

    def add_choir_ring(self, *args, **kwargs):
        return None

    def add_fumarole_tower(self, *args, **kwargs):
        return None

    def add_kelp_fan(self, *args, **kwargs):
        return None

    def add_reef_arch(self, *args, **kwargs):
        return None

    def add_root_arch(self, *args, **kwargs):
        return None

    def add_crystal_cluster(self, *args, **kwargs):
        return None

    def add_signal_pylon(self, *args, **kwargs):
        return None

    def add_geometric_creature(self, *args, **kwargs):
        return None

    def spawn_world_projectile(self, *args, **kwargs):
        return None

    def prune_internal_projectile_overflow(self):
        return

    def create_world_chunk(self, cx, cy):
        return None

    def add_flatworld_build_grid_chunk(self, *args, **kwargs):
        return None

    def update_world_chunks(self, force=False):
        # Pass 90: chunk streaming only needs to run when the player crosses a
        # biome sector/metropolis chunk boundary. Running the full target/prune/
        # audit path every frame was one of the largest frame-time spikes.
        # Pass 282.51: the paced ring-ground service runs every frame first.
        if not force:
            self.service_ring_ground()
        r = math.sqrt(self.player_pos.x * self.player_pos.x + self.player_pos.y * self.player_pos.y)
        angle = math.atan2(self.player_pos.y, self.player_pos.x) % math.tau
        center_sector = int(angle / (math.tau / BIOME_SECTOR_COUNT)) % BIOME_SECTOR_COUNT
        ring = self.biome_ring_for_radius(r)
        self.active_biome_name = ring["name"] if ring else "HUB"
        try:
            metro_key = self.metropolis_chunk_key_for_point(self.player_pos.x, self.player_pos.y)
        except Exception:
            metro_key = (0, 0)
        kind = str((ring or {}).get("kind", ""))
        detail_ring_key = int((ring or {}).get("key", 0) or 0) if kind not in {"", "flat", "metropolis"} else 0
        previous_detail_ring_key = int(getattr(self, "active_detail_ring_key", 0) or 0)
        if detail_ring_key != previous_detail_ring_key:
            self.last_unloaded_detail_ring_key = previous_detail_ring_key if previous_detail_ring_key else 0
            self.active_detail_ring_key = detail_ring_key
            self.ring_stream_transition_count = int(getattr(self, "ring_stream_transition_count", 0) or 0) + 1
            history = list(getattr(self, "ring_stream_history", []) or [])
            history.append({"from": previous_detail_ring_key, "to": detail_ring_key, "radius": round(float(r), 3)})
            self.ring_stream_history = history[-16:]
        full_ring_active = detail_ring_key in tuple(int(v) for v in ACTIVE_FULL_RING_KEYS)
        sig_sector = -1 if full_ring_active else int(center_sector)
        hub_forest_preview = bool(r <= float(MAIN_AREA_RADIUS) and (ring is None or kind == "flat"))
        stream_sig = (int(ring["key"]) if ring else 0, sig_sector, int(metro_key[0]), int(metro_key[1]), bool(self.deep_water_mode_active()), bool(full_ring_active), bool(hub_forest_preview))
        if not force and stream_sig == getattr(self, "_last_world_chunk_stream_sig", None):
            return
        self._last_world_chunk_stream_sig = stream_sig
        previous_preview = getattr(self, "_last_hub_forest_preview_mode", None)
        preview_transition = previous_preview is not None and bool(previous_preview) != bool(hub_forest_preview)
        self._last_hub_forest_preview_mode = bool(hub_forest_preview)
        if preview_transition:
            # Hub and active Forest intentionally share ring key 2, but they no
            # longer share the same micro-detail budget. Rebuild only Forest
            # sectors when crossing that authority boundary so understory comes
            # back in-region and is removed again on return to the Hub preview.
            for key in list(getattr(self, "terrain_chunks", {}).keys()):
                if int(key[0]) == int(FOREST_FULL_RING_KEY):
                    try:
                        self.terrain_chunks[key].removeNode()
                    except Exception:
                        pass
                    self.terrain_chunks.pop(key, None)
                    self.terrain_chunk_pruned_count += 1
        before_sig = (len(getattr(self, "terrain_chunks", {}) or {}), len(getattr(self, "metropolis_chunks", {}) or {}))
        targets = self.target_biome_chunk_keys()
        self.prune_biome_chunks_to_targets(targets)
        deferred = []
        for key in sorted(targets):
            if key in self.terrain_chunks:
                continue
            ring_for_key = self.biome_ring_for_key(key[0])
            if ring_for_key is not None:
                if not force and self.ring_chunk_can_defer(ring_for_key, key[1], center_sector):
                    deferred.append(key)
                    continue
                self.build_biome_terrain_chunk(ring_for_key, key[1])
        self._ring_chunk_targets = set(targets)
        self._ring_chunk_queue = deferred
        if self.deep_water_mode_active():
            metro_targets = set()
        else:
            metro_targets = self.target_metropolis_chunk_keys()
        self.prune_metropolis_chunks_to_targets(metro_targets)
        player_metro_key = tuple(int(v) for v in metro_key)
        metro_deferred = []
        for key in sorted(metro_targets):
            if key in self.metropolis_chunks:
                continue
            if not force and self.metropolis_city_active() and key != player_metro_key:
                metro_deferred.append(key)
                continue
            self.build_metropolis_chunk(key[0], key[1])
        self._metro_chunk_targets = set(metro_targets)
        self._metro_chunk_queue = metro_deferred
        after_sig = (len(getattr(self, "terrain_chunks", {}) or {}), len(getattr(self, "metropolis_chunks", {}) or {}))
        # Pass 282.45: duplicate-surface cleanup is a chunk lifecycle operation,
        # not a frame operation.  Running findAllMatches across the world every
        # frame cost CPU even while the streamed world was unchanged.
        if force or before_sig != after_sig:
            self.prune_redundant_surface_layers()
        if force or before_sig != after_sig or getattr(self, "_last_surface_audit_chunk_sig", None) != after_sig:
            self._last_surface_audit_chunk_sig = after_sig
            self.audit_surface_authority()
        return

    def activate_default_world_shell(self):
        self.active_artifact = None
        self.active_artifact_id = None
        self.world_unlocked = False
        self.transition_target = 0.0
        self.transition_progress = 0.0
        self.internal_mode = InternalModeState()
        self.clear_world_chunks()
        return

    def flatworld_zone_name_for_point(self, x: float, y: float):
        return "Observatory Hub"

    def is_neon_city_spec(self, spec=None):
        return False

    def is_neon_racing_active(self):
        return False

    def neon_race_frame(self, spec=None):
        return Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0)

    def neon_race_point(self, progress: float, lateral: float = 0.0, spec=None, lift: float = 0.0):
        return Vec3(0, 0, lift)

    def prepare_neon_city_racing(self):
        self.neon_race = NeonRaceState()
        return

    def start_neon_racing_mode(self):
        return

    def exit_neon_racing_mode(self, clear_visuals=False):
        if getattr(self, "neon_race_root", None) is not None:
            try:
                self.neon_race_root.removeNode()
            except Exception:
                pass
        self.neon_race_root = None
        self.neon_vehicle_root = None
        self.neon_traffic_nodes = []
        self.neon_race = NeonRaceState()

    def ensure_neon_racing_visuals(self):
        return

    def rebuild_neon_traffic(self):
        self.neon_traffic_nodes = []
        return

    def update_neon_city_state(self, dt):
        return

    def update_neon_racing_drive(self, dt):
        return

    def update_neon_traffic(self, dt):
        return

    def add_neon_race_track_chunk(self, *args, **kwargs):
        return None

    def point_in_chunk_bounds(self, x, y, cx, cy, margin=0.0):
        return False

    def flatworld_walkable_radius(self):
        return BIOME_OUTER_RADIUS - 2.0


    def flatworld_boundary_floor_z(self):
        return self.hub_ground_level()

    def flatworld_disc_radius(self):
        return FLATLAND_DISC_RADIUS

    def flatworld_build_ring_radius(self):
        return FLATLAND_DISC_RADIUS - self.flatworld_major_grid_step()

    def flatworld_minor_grid_step(self):
        return FLATLAND_MINOR_STEP

    def flatworld_major_grid_step(self):
        return FLATLAND_MAJOR_STEP

    def flatworld_surface_color(self, x, y, alpha=1.0):
        return (0.0, 0.0, 0.0, 0.0)


    def clamp_flatworld_candidate(self, candidate: Vec3, spec=None):
        candidate.z = self.cfg.player_eye_height
        return candidate

    def current_zone_name(self):
        r = math.sqrt(self.player_pos.x ** 2 + self.player_pos.y ** 2)
        if r < 8.0:
            return "Central Core"
        if r < 19.0:
            return "Observatory Ring"
        if r < self.hub_radius + 1.0:
            return "Hub Perimeter"
        ring = self.biome_ring_for_radius(r)
        if ring is not None:
            return f"{ring['key']} // {ring['name']}"
        return "Outer Boundary"

    def find_nearest_artifact(self):
        self.nearest_artifact = None
        self.nearest_artifact_dist = 999.0

    def activate_artifact(self):
        self.show_build_hint("HUB-ONLY // simulator artifacts removed", 1.2)
        return

    def activate_nearest_artifact(self):
        self.find_nearest_artifact()
        return

    def teleport_to_hub(self):
        self.exit_neon_racing_mode(clear_visuals=True)
        self.flight_craft_active = False
        self.flight_craft_velocity = Vec3(0, 0, 0)
        self.hide_underwater_vehicle()
        self.player_pos = Vec3(self.base_teleport)
        self.player_pos.z = self.cfg.player_eye_height
        self.camera.setPos(self.player_pos)
        self.active_artifact = None
        self.active_artifact_id = None
        self.transition_target = 0.0
        self.transition_progress = 0.0
        self.world_unlocked = False
        self.internal_mode = InternalModeState()
        self.clear_world_chunks()
        self.update_world_chunks(force=True)
        self.show_build_hint("T RETURN // spawn restored", 1.0)
        self.refresh_ui()

    def toggle_debug_sky_cam(self):
        target = Vec3(0.0, 0.0, 6.0)
        sky_pos = Vec3(0.0, -2.0, self.cfg.player_eye_height + 344.0)
        if not self.debug_sky_cam_enabled:
            self.debug_sky_cam_restore = (Vec3(self.player_pos), float(self.player_yaw), float(self.player_pitch))
            yaw, pitch = focus_hpr(sky_pos, target)
            self.player_pos = Vec3(sky_pos)
            self.player_yaw = yaw
            self.player_pitch = pitch
            self.camera.setPos(self.player_pos)
            self.camera.setHpr(self.player_yaw, self.player_pitch, 0)
            self.debug_sky_cam_enabled = True
        else:
            if self.debug_sky_cam_restore is not None:
                self.player_pos = Vec3(self.debug_sky_cam_restore[0])
                self.player_yaw = float(self.debug_sky_cam_restore[1])
                self.player_pitch = float(self.debug_sky_cam_restore[2])
                self.camera.setPos(self.player_pos)
                self.camera.setHpr(self.player_yaw, self.player_pitch, 0)
            self.debug_sky_cam_enabled = False
        if hasattr(self, "center_hint"):
            self.center_hint["text"] = "DEBUG SKY CAM" if self.debug_sky_cam_enabled else "F2 DEBUG CAM"

    def toggle_hud(self):
        self.hud_visible = not self.hud_visible
        self.cfg.hud_visible = self.hud_visible
        save_config(self.cfg)
        self.refresh_ui()

    def toggle_help_overlay(self):
        if not self.menu_open:
            self.menu_open = True
            self.menu_root.show()
        self.set_menu_tab("system")
        props = WindowProperties()
        props.setCursorHidden(False)
        if self.win is not None and hasattr(self.win, "requestProperties"):
            self.win.requestProperties(props)
        self.center_hint["text"] = ""
        self.refresh_ui()

    def quit_holoverse_app(self):
        try:
            if getattr(self, "center_hint", None) is not None:
                self.center_hint["text"] = "EXITING HOLOVERSE"
        except Exception:
            pass
        self.userExit()

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
        if tab_key not in {"display", "audio", "system"}:
            tab_key = "display"
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


    def reset_settings(self):
        self.cfg = ObservatoryConfig()
        self.hud_visible = self.cfg.hud_visible
        self.base_teleport = Vec3(0, -10, self.cfg.player_eye_height)
        save_config(self.cfg)
        self.rebuild_station()
        self.refresh_menu_actions()
        self.refresh_ui()

    def refresh_menu_actions(self):
        self.menu_subtitle["text"] = "Hub flatland + terrain rings // 1-8 fast travel"
        specs = {
            "display": [
                ("FOV +", "adjust_fov", 3.0),
                ("FOV -", "adjust_fov", -3.0),
                ("LINES +", "adjust_line_thickness", 0.2),
                ("LINES -", "adjust_line_thickness", -0.2),
            ],
            "audio": [
                ("MASTER +", "adjust_master_volume", 0.05),
                ("MASTER -", "adjust_master_volume", -0.05),
                ("SFX +", "adjust_sfx_volume", 0.05),
                ("SFX -", "adjust_sfx_volume", -0.05),
            ],
            "system": [
                ("RESUME", "toggle_menu"),
                ("HUD", "toggle_hud"),
                ("QUIT APP", "quit_holoverse_app"),
                ("RESET", "reset_settings"),
            ],
        }
        if self.menu_tab not in specs:
            self.menu_tab = "display"
        self.menu_actions = specs.get(self.menu_tab, [])
        for i, btn in enumerate(self.menu_buttons):
            if i < len(self.menu_actions):
                btn.show()
                btn["text"] = self.menu_actions[i][0]
            else:
                btn.hide()
        for key, btn in self.menu_tab_buttons:
            btn["frameColor"] = (0.16, 0.01, 0.03, 1.0) if key == self.menu_tab else (0.055, 0.01, 0.02, 1.0)

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
        # Background value is now configured only as the minimum sky/fog floor for
        # the biome day/night system; no static backdrop cards are generated.
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

    def runtime_debug_counts(self):
        actor_count = 0
        for actor in getattr(self, "world_actors", []):
            try:
                if actor.root is not None and not actor.root.isEmpty():
                    actor_count += 1
            except Exception:
                pass
        forest_tree_count = 0
        forest_detail_patch_count = 0
        forest_detail_tree_count = 0
        forest_detail_crown_count = 0
        forest_understory_bush_count = 0
        forest_understory_fern_count = 0
        forest_understory_grass_count = 0
        forest_understory_deadfall_count = 0
        hill_flower_count = 0
        deep_water_creature_count = 0
        deep_water_flora_count = 0
        deep_water_feature_count = 0
        deep_water_hero_count = 0
        deep_water_coral_count = 0
        deep_water_bubble_count = 0
        water_surface_line_count = 0
        urban_ruin_count = 0
        urban_structure_count = 0
        urban_structured_block_count = 0
        urban_battle_count = 0
        urban_mech_count = 0
        urban_drone_count = 0
        urban_skeleton_count = 0
        urban_airstrike_count = 0
        urban_trench_count = 0
        urban_smoke_count = 0
        for chunk in (getattr(self, "terrain_chunks", {}) or {}).values():
            try:
                forest_tree_count += int(chunk.getPythonTag("forest_tree_count") or 0)
            except Exception:
                pass
            try:
                forest_detail_patch_count += int(chunk.getPythonTag("forest_detail_patch_count") or 0)
                forest_detail_tree_count += int(chunk.getPythonTag("forest_detail_tree_count") or 0)
                forest_detail_crown_count += int(chunk.getPythonTag("forest_detail_crown_count") or 0)
                forest_understory_bush_count += int(chunk.getPythonTag("forest_understory_bush_count") or 0)
                forest_understory_fern_count += int(chunk.getPythonTag("forest_understory_fern_count") or 0)
                forest_understory_grass_count += int(chunk.getPythonTag("forest_understory_grass_count") or 0)
                forest_understory_deadfall_count += int(chunk.getPythonTag("forest_understory_deadfall_count") or 0)
            except Exception:
                pass
            try:
                hill_flower_count += int(chunk.getPythonTag("hill_flower_count") or 0)
            except Exception:
                pass
            try:
                deep_water_creature_count += int(chunk.getPythonTag("deep_water_creature_count") or 0)
            except Exception:
                pass
            try:
                deep_water_flora_count += int(chunk.getPythonTag("deep_water_flora_count") or 0)
            except Exception:
                pass
            try:
                deep_water_feature_count += int(chunk.getPythonTag("deep_water_feature_count") or 0)
            except Exception:
                pass
            try:
                deep_water_hero_count += int(chunk.getPythonTag("deep_water_hero_count") or 0)
            except Exception:
                pass
            try:
                deep_water_coral_count += int(chunk.getPythonTag("deep_water_coral_count") or 0)
            except Exception:
                pass
            try:
                deep_water_bubble_count += int(chunk.getPythonTag("deep_water_bubble_count") or 0)
            except Exception:
                pass
            try:
                water_surface_line_count += int(chunk.getPythonTag("water_surface_line_count") or 0)
            except Exception:
                pass
            try:
                urban_ruin_count += int(chunk.getPythonTag("urban_ruin_count") or 0)
            except Exception:
                pass
            try:
                urban_structure_count += int(chunk.getPythonTag("urban_structure_count") or 0)
            except Exception:
                pass
            try:
                urban_structured_block_count += int(chunk.getPythonTag("urban_structured_block_count") or 0)
            except Exception:
                pass
            try:
                urban_battle_count += int(chunk.getPythonTag("urban_battle_count") or 0)
            except Exception:
                pass
            try:
                urban_mech_count += int(chunk.getPythonTag("urban_mech_count") or 0)
            except Exception:
                pass
            try:
                urban_drone_count += int(chunk.getPythonTag("urban_drone_count") or 0)
            except Exception:
                pass
            try:
                urban_skeleton_count += int(chunk.getPythonTag("urban_skeleton_count") or 0)
            except Exception:
                pass
            try:
                urban_airstrike_count += int(chunk.getPythonTag("urban_airstrike_count") or 0)
            except Exception:
                pass
            try:
                urban_trench_count += int(chunk.getPythonTag("urban_trench_count") or 0)
            except Exception:
                pass
            try:
                urban_smoke_count += int(chunk.getPythonTag("urban_smoke_count") or 0)
            except Exception:
                pass
        return {
            "fps": float(getattr(self, "frame_fps", 0.0)),
            "frame_ms": float(getattr(self, "frame_ms_smoothed", 0.0)),
            "chunks": len(getattr(self, "terrain_chunks", {}) or {}),
            "chunk_cap": MAX_BIOME_TERRAIN_CHUNKS,
            "chunks_pruned": int(getattr(self, "terrain_chunk_pruned_count", 0)),
            "active_detail_ring_key": int(getattr(self, "active_detail_ring_key", 0) or 0),
            "last_unloaded_detail_ring_key": int(getattr(self, "last_unloaded_detail_ring_key", 0) or 0),
            "ring_stream_transition_count": int(getattr(self, "ring_stream_transition_count", 0) or 0),
            "loaded_ring_keys": sorted({int(key[0]) for key in (getattr(self, "terrain_chunks", {}) or {}).keys()}),
            "loaded_sector_counts": {str(k): sum(1 for key in (getattr(self, "terrain_chunks", {}) or {}) if int(key[0]) == int(k)) for k in sorted({int(key[0]) for key in (getattr(self, "terrain_chunks", {}) or {}).keys()})},
            "active_ring_exclusive_streaming": bool(ACTIVE_RING_EXCLUSIVE_STREAMING),
            "forest_trees": int(forest_tree_count),
            "forest_detail_patches": int(forest_detail_patch_count),
            "forest_detail_trees": int(forest_detail_tree_count),
            "forest_detail_crowns": int(forest_detail_crown_count),
            "forest_understory_bushes": int(forest_understory_bush_count),
            "forest_understory_ferns": int(forest_understory_fern_count),
            "forest_understory_grass": int(forest_understory_grass_count),
            "forest_understory_deadfall": int(forest_understory_deadfall_count),
            "hill_flowers": int(hill_flower_count),
            "hill_meadow_shapes": sum(int((chunk.getPythonTag("hill_meadow_shape_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "deep_water_creatures": int(deep_water_creature_count),
            "deep_water_flora": int(deep_water_flora_count),
            "deep_water_features": int(deep_water_feature_count),
            "deep_water_heroes": int(deep_water_hero_count),
            "deep_water_corals": int(deep_water_coral_count),
            "deep_water_bubbles": int(deep_water_bubble_count),
            "water_surface_lines": int(water_surface_line_count),
            "water_depth": float(getattr(self, "current_water_depth", 0.0)),
            "urban_ruins": int(urban_ruin_count),
            "urban_structures": int(urban_structure_count),
            "urban_structured_blocks": int(urban_structured_block_count),
            "urban_battles": int(urban_battle_count),
            "urban_mechs": int(urban_mech_count),
            "urban_drones": int(urban_drone_count),
            "urban_skeletons": int(urban_skeleton_count),
            "urban_airstrikes": int(urban_airstrike_count),
            "urban_trenches": int(urban_trench_count),
            "urban_smoke": int(urban_smoke_count),
            "actors": actor_count,
            "actor_cap": MAX_WORLD_ACTORS,
            "actors_pruned": int(getattr(self, "world_actor_pruned_count", 0)),
            "named_region_bots": len(self._active_named_region_bot_nodes()),
            "named_region_bot_cap": int(MAX_NAMED_REGION_BOTS),
            "named_region_bots_pruned": int(getattr(self, "named_region_bot_pruned_count", 0)),
            "internal_projectiles": len(getattr(getattr(self, "internal_mode", None), "projectiles", []) or []),
            "weapon_projectiles": len(getattr(self, "weapon_projectiles", []) or []),
            "user_buildings": len(getattr(self, "user_buildings", {}) or {}),
            "neon_race_active": bool(getattr(getattr(self, "neon_race", None), "active", False)),
            "neon_race_speed": float(getattr(getattr(self, "neon_race", None), "speed", 0.0)),
            "neon_race_progress": float(getattr(getattr(self, "neon_race", None), "progress", 0.0)),
        }

    def refresh_ui(self):
        zone = self.current_zone_name()
        art_name = self.active_artifact["name"] if self.active_artifact else (self.current_world_spec()["name"] if self.transition_target > 0.0 else WORLD_SPECS[0]["name"])
        coords = f"X {self.player_pos.x:07.2f}  Y {self.player_pos.y:07.2f}  Z {self.player_pos.z:06.2f}"
        if getattr(self, "space_layer_active", False) or self.space_layer_factor() > 0.08:
            progress_pct = clamp(float(getattr(self, "space_build_progress", 0.0)) * 100.0, 0.0, 100.0)
            coords += f"  SPACE BUILD {progress_pct:05.2f}%"
        if getattr(self, "flight_craft_active", False):
            coords += f"  CRAFT FLIGHT {float(CRAFT_FLIGHT_SPEED_MULTIPLIER):.0f}X"
        elif self.deep_water_mode_active():
            coords += f"  DEPTH {self.current_water_depth * 100.0:05.1f}%"
        self.hud_label["text"] = f"{zone}\n{art_name}"
        self.coords_label["text"] = coords
        counts = self.runtime_debug_counts()
        if self.menu_tab == "display":
            self.menu_info["text"] = "VIEW"
            self.menu_section["text"] = "Camera and wire clarity"
            self.menu_detail["text"] = (
                f"FOV        {self.cfg.fov:.0f}\n"
                f"Line width {self.cfg.line_thickness:.1f}\n"
                f"Sky floor {self.cfg.background_value:.3f}\n"
                "Sky        SPACE // PERSISTENT"
            )
        elif self.menu_tab == "audio":
            self.menu_info["text"] = "AUDIO"
            self.menu_section["text"] = "Local mix"
            self.menu_detail["text"] = (
                f"Master {self.cfg.master_volume:.2f}\n"
                f"SFX    {self.cfg.sfx_volume:.2f}\n"
                f"Music  {self.cfg.music_volume:.2f}"
            )
        else:
            self.menu_info["text"] = "SYSTEM"
            self.menu_section["text"] = "Hub flatland recovery shell"
            self.menu_detail["text"] = (
                f"Build {VERSION}\n"
                f"FPS   {counts['fps']:.1f}\n"
                f"HUD   {'ON' if self.hud_visible else 'OFF'}\n"
                f"Biome {getattr(self, 'active_biome_name', 'HUB')}\n"
                f"Sky   {getattr(self, 'current_sky_biome', 'SPACE')} // PERSISTENT\n"
                f"Water {counts.get('water_depth', 0.0) * 100.0:05.1f}% depth\n"
                f"Waterfx {counts.get('deep_water_features', 0):d}"
            )
        self.menu_status["text"] = "Esc resume   V craft outside hub   1-8 biome travel   Space/Ctrl vertical   T spawn"
        self.refresh_menu_actions()
        if self.hud_visible:
            self.hud_root.show()
            if not self.menu_open:
                self.crosshair_root.show()
        else:
            self.hud_root.hide()
            self.crosshair_root.hide()
        self.core_console_root.show() if self.core_console_open else self.core_console_root.hide()

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
        if self.debug_sky_cam_enabled:
            self.camera.setPos(self.player_pos)
            self.camera.setHpr(self.player_yaw, self.player_pitch, 0)
            return
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
        self.player_pitch = max(-82.0, min(82.0, self.player_pitch - dy * self.cfg.mouse_sensitivity))
        if self.gamepad:
            try:
                rx = self.gamepad.findAxis(InputDevice.Axis.right_x)
                ry = self.gamepad.findAxis(InputDevice.Axis.right_y)
                gx = rx.value if rx else 0.0
                gy = ry.value if ry else 0.0
                if abs(gx) > 0.12:
                    self.player_yaw -= gx * self.cfg.controller_look_sensitivity * dt
                if abs(gy) > 0.12:
                    self.player_pitch = max(-82.0, min(82.0, self.player_pitch + gy * self.cfg.controller_look_sensitivity * dt))
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
                if lx:
                    move.x += lx.value
                if ly:
                    move.y += -ly.value
            except Exception:
                pass
        if move.lengthSquared() > 1.0:
            move.normalize()
        return move

    def point_allowed(self, pos: Vec3):
        spec = self.current_world_spec()
        r = math.sqrt(pos.x * pos.x + pos.y * pos.y)
        if getattr(self, "flight_craft_active", False):
            return self.craft_allowed_position(pos)
        if self.deep_water_mode_active(pos):
            ring = self.biome_ring_for_radius(r)
            if ring is None:
                return False
            bottom_z, top_z = self.deep_water_bounds(pos.x, pos.y, ring)
            return (float(ring["r0"]) + 4.0) <= r <= (float(ring["r1"]) - 4.0) and (bottom_z - 0.05) <= pos.z <= (top_z + 0.05)
        if self.world_unlocked or self.transition_target > 0.0:
            if spec["kind"] == "flatworld":
                return r < min(self.cfg.terrain_chunk_size * (self.effective_terrain_render_radius() + 0.8), self.flatworld_disc_radius() - 0.2)
            if spec["kind"] in ("underwater", "space"):
                return r < self.cfg.terrain_chunk_size * (self.effective_terrain_render_radius() + 0.8) and -120.0 < pos.z < 120.0
            return r < self.cfg.terrain_chunk_size * (self.effective_terrain_render_radius() + 0.8)
        # Default hub shell now includes the surrounding flatland, so the player
        # can walk out of the observatory without activating a simulator world.
        if METROPOLIS_INFINITE and r >= float(METROPOLIS_INNER_RADIUS):
            return True
        return r <= self.flatworld_walkable_radius()

    def terrain_motion_profile(self, pos=None):
        if pos is None:
            pos = self.player_pos
        radius = math.sqrt(float(pos.x) * float(pos.x) + float(pos.y) * float(pos.y))
        ring = self.biome_ring_for_radius(radius)
        kind = str((ring or {}).get("kind", ""))
        if kind == "ice":
            return {"traction": 0.26, "glide": 1.04, "kind": kind}
        return {"traction": 1.0, "glide": 1.0, "kind": kind or "hub"}

    def craft_hub_lock_radius(self):
        return float(self.hub_radius) + float(CRAFT_HUB_LOCK_PADDING)

    def can_use_flight_craft_at(self, pos=None):
        pos = pos if pos is not None else self.player_pos
        radius = math.sqrt(float(pos.x) * float(pos.x) + float(pos.y) * float(pos.y))
        return radius > self.craft_hub_lock_radius() and radius <= self.flatworld_walkable_radius()

    def craft_surface_eye_z(self, x: float, y: float, ring=None):
        ring = ring if ring is not None else self.biome_ring_for_radius(math.sqrt(x * x + y * y))
        if ring is not None and str(ring.get("kind", "")) == "water":
            return self.deep_water_craft_eye_z(x, y, ring)
        return self.cfg.player_eye_height + self.world_height_at(x, y, self.current_world_spec())

    def craft_minimum_eye_z(self, x: float, y: float, ring=None):
        return self.craft_surface_eye_z(x, y, ring) + float(CRAFT_FLIGHT_MIN_CLEARANCE)

    def craft_allowed_position(self, pos: Vec3):
        radius = math.sqrt(float(pos.x) * float(pos.x) + float(pos.y) * float(pos.y))
        if radius <= self.craft_hub_lock_radius():
            return False
        if not (METROPOLIS_INFINITE and radius >= float(METROPOLIS_INNER_RADIUS)) and radius > self.flatworld_walkable_radius():
            return False
        ring = self.biome_ring_for_radius(radius)
        min_z = self.craft_minimum_eye_z(pos.x, pos.y, ring) - 1.0
        max_z = max(float(CRAFT_FLIGHT_MAX_EYE_Z), min_z + 24.0)
        if self.world_resolve_move(pos.x, pos.y, pos.x, pos.y, z=float(pos.z), radius=2.0)[2]:
            return False  # Pass 282.52/53: city buildings and Urban ruins block the craft below roof height
        return min_z <= float(pos.z) <= max_z

    def travel_craft_active(self):
        return bool(getattr(self, "flight_craft_active", False)) or self.deep_water_mode_active()

    def toggle_flight_craft(self):
        if self.menu_open or self.debug_sky_cam_enabled:
            return
        if getattr(self, "flight_craft_active", False):
            self.flight_craft_active = False
            self.flight_craft_velocity = Vec3(0, 0, 0)
            if self.deep_water_mode_active():
                ring = self.biome_ring_for_radius(math.sqrt(self.player_pos.x * self.player_pos.x + self.player_pos.y * self.player_pos.y))
                self.player_pos.z = self.deep_water_craft_eye_z(self.player_pos.x, self.player_pos.y, ring)
                self.show_build_hint("AIRCRAFT // surface-water mode", 1.2)
            else:
                self.hide_underwater_vehicle()
                self.player_pos.z = self.cfg.player_eye_height + self.world_height_at(self.player_pos.x, self.player_pos.y, self.current_world_spec())
                self.show_build_hint("AIRCRAFT // disengaged", 1.1)
            self.camera.setPos(self.player_pos)
            self.refresh_ui()
            return
        if not self.can_use_flight_craft_at(self.player_pos):
            self.show_build_hint("AIRCRAFT LOCKED // leave the hub first", 1.35)
            return
        self.flight_craft_active = True
        self.flight_craft_velocity = Vec3(0, 0, 0)
        ring = self.biome_ring_for_radius(math.sqrt(self.player_pos.x * self.player_pos.x + self.player_pos.y * self.player_pos.y))
        self.player_pos.z = max(self.player_pos.z, self.craft_minimum_eye_z(self.player_pos.x, self.player_pos.y, ring))
        self.camera.setPos(self.player_pos)
        self.ensure_underwater_vehicle()
        self.show_build_hint("AIRCRAFT // flight online // 10x walk speed // high-altitude unlocked", 1.65)
        self.refresh_ui()

    def update_flight_craft(self, dt, move, forward, right, up):
        if not self.can_use_flight_craft_at(self.player_pos):
            self.flight_craft_active = False
            self.flight_craft_velocity = Vec3(0, 0, 0)
            self.hide_underwater_vehicle()
            self.player_pos.z = self.cfg.player_eye_height + self.world_height_at(self.player_pos.x, self.player_pos.y, self.current_world_spec())
            self.camera.setPos(self.player_pos)
            if self.elapsed - getattr(self, "flight_craft_last_hint_time", -999.0) > 0.8:
                self.flight_craft_last_hint_time = self.elapsed
                self.show_build_hint("AIRCRAFT SAFETY // hub boundary disengaged", 1.2)
            return
        if forward.lengthSquared() > 0: forward.normalize()
        if right.lengthSquared() > 0: right.normalize()
        if up.lengthSquared() > 0: up.normalize()
        vertical = 0.0
        if self.keys.get("space"):
            vertical += 1.0
        if self.keys.get("control"):
            vertical -= 1.0
        has_input = move.lengthSquared() > 0.0001 or abs(vertical) > 0.0001
        if not has_input:
            self.flight_craft_velocity = Vec3(0, 0, 0)
            self.player_velocity = Vec3(0, 0, 0)
            hover_floor = self.craft_minimum_eye_z(self.player_pos.x, self.player_pos.y)
            if self.player_pos.z < hover_floor:
                self.player_pos.z = hover_floor
            self.camera.setPos(self.player_pos)
            self.update_underwater_vehicle(dt)
            return
        speed = float(self.cfg.walk_speed) * float(CRAFT_FLIGHT_SPEED_MULTIPLIER)
        desired = (forward * move.y + right * move.x) * speed
        desired += up * vertical * speed * float(CRAFT_FLIGHT_VERTICAL_SPEED_SCALE)
        if desired.lengthSquared() > speed * speed * 1.25:
            desired.normalize()
            desired *= speed
        self.flight_craft_velocity = desired
        step = self.flight_craft_velocity * max(0.0, dt)
        candidate = Vec3(self.player_pos + step)
        min_z = self.craft_minimum_eye_z(candidate.x, candidate.y)
        candidate.z = clamp(float(candidate.z), min_z, float(CRAFT_FLIGHT_MAX_EYE_Z))
        candidate, hit_dyson_shell = self.constrain_dyson_player_position(candidate)
        if hit_dyson_shell:
            self.flight_craft_velocity = Vec3(0, 0, 0)
            if self.elapsed - getattr(self, "dyson_collision_hint_time", -999.0) > 0.8:
                self.dyson_collision_hint_time = self.elapsed
                self.show_build_hint("DYSON SHELL LOCK // exterior access only", 0.95)
        if self.point_allowed(candidate):
            self.player_pos = candidate
        else:
            self.flight_craft_velocity = Vec3(0, 0, 0)
        self.player_velocity = Vec3(self.flight_craft_velocity)
        self.camera.setPos(self.player_pos)
        self.update_underwater_vehicle(dt)

    def update_player(self, dt):
        if getattr(self.neon_race, "active", False):
            self.update_neon_racing_drive(dt)
            return
        self.update_look(dt)
        if self.debug_sky_cam_enabled:
            return
        move = self.get_move_input()
        target_speed = self.cfg.sprint_speed if self.keys.get("shift") else self.cfg.walk_speed
        target_vel = move * target_speed
        motion_profile = self.terrain_motion_profile(self.player_pos)
        traction = clamp(float(motion_profile.get("traction", 1.0)), 0.12, 1.0)
        glide = clamp(float(motion_profile.get("glide", 1.0)), 1.0, 1.20)
        blend = min(1.0, dt * 7.5 * traction)
        if move.lengthSquared() < 0.0001 and traction < 0.999:
            damping = min(1.0, dt * (1.20 + traction * 2.6))
            self.move_velocity = self.move_velocity * (1.0 - damping)
        else:
            self.move_velocity = self.move_velocity * (1.0 - blend) + target_vel * blend
        quat = self.camera.getQuat(self.render)
        forward = quat.getForward(); right = quat.getRight(); up = quat.getUp()
        spec = self.current_world_spec()
        if getattr(self, "flight_craft_active", False):
            self.update_flight_craft(dt, move, Vec3(forward), Vec3(right), Vec3(up))
        elif spec["kind"] == "underwater" or self.deep_water_mode_active():
            if forward.lengthSquared() > 0: forward.normalize()
            if right.lengthSquared() > 0: right.normalize()
            if up.lengthSquared() > 0: up.normalize()
            if self.deep_water_mode_active() and spec["kind"] != "underwater":
                # Pass 56: Retired Ocean is a local surface-craft region, not a walkable seabed.
                # Movement stays free/dynamic on the ocean plane until the craft crosses a shore seam.
                forward.z = 0.0
                right.z = 0.0
                if forward.lengthSquared() > 0: forward.normalize()
                if right.lengthSquared() > 0: right.normalize()
                craft_speed = target_speed * float(DEEP_WATER_CRAFT_SPEED_SCALE)
                water_vel = self.move_velocity
                if move.lengthSquared() > 0.0001:
                    water_vel = target_vel * float(DEEP_WATER_CRAFT_SPEED_SCALE)
                step = (forward * water_vel.y * dt + right * water_vel.x * dt)
                self.player_velocity = step / max(dt, 1e-6)
                candidate = Vec3(self.player_pos.x + step.x, self.player_pos.y + step.y, self.player_pos.z)
                next_ring = self.biome_ring_for_radius(math.sqrt(candidate.x * candidate.x + candidate.y * candidate.y))
                if next_ring is not None and str(next_ring.get("kind", "")) == "water":
                    candidate.z = self.deep_water_craft_eye_z(candidate.x, candidate.y, next_ring)
                else:
                    candidate.z = self.cfg.player_eye_height + self.visible_ground_height_at(candidate.x, candidate.y)
                if self.point_allowed(candidate):
                    self.player_pos = candidate
            else:
                vertical = 0.0
                if self.keys.get("space"): vertical += 1.0
                if self.keys.get("control"): vertical -= 1.0
                swim_speed = target_speed
                step = forward * self.move_velocity.y * dt + right * self.move_velocity.x * dt + up * vertical * swim_speed * 0.58 * dt
                self.player_velocity = step / max(dt, 1e-6)
                candidate = Vec3(self.player_pos + step)
                if self.point_allowed(candidate):
                    self.player_pos = candidate
            self.camera.setPos(self.player_pos)
            self.update_underwater_vehicle(dt)
        else:
            self.hide_underwater_vehicle()
            forward.z = 0; right.z = 0
            if forward.lengthSquared() > 0: forward.normalize()
            if right.lengthSquared() > 0: right.normalize()
            step = (forward * self.move_velocity.y * dt + right * self.move_velocity.x * dt) * glide
            self.player_velocity = step / max(dt, 1e-6)
            nx, ny, _blocked = self.world_resolve_move(self.player_pos.x, self.player_pos.y, self.player_pos.x + step.x, self.player_pos.y + step.y)
            base_h = self.visible_ground_height_at(nx, ny) if spec["kind"] != "space" else 0.0
            z = self.cfg.player_eye_height + (base_h if spec["kind"] != "space" else 0.0)
            candidate = Vec3(nx, ny, z)
            next_r = math.sqrt(candidate.x * candidate.x + candidate.y * candidate.y)
            next_ring = self.biome_ring_for_radius(next_r)
            if next_ring is not None and str(next_ring.get("kind", "")) == "water":
                candidate.z = self.deep_water_craft_eye_z(candidate.x, candidate.y, next_ring)
            if spec["kind"] == "flatworld":
                candidate = self.clamp_flatworld_candidate(candidate, spec)
                candidate = self.resolve_user_building_collisions(self.player_pos, candidate, spec)
            if self.point_allowed(candidate):
                self.player_pos = candidate
            self.camera.setPos(self.player_pos)

    def ensure_underwater_vehicle(self):
        if getattr(self, "underwater_vehicle_root", None) is not None and not self.underwater_vehicle_root.isEmpty():
            return self.underwater_vehicle_root
        root = self.world_root.attachNewNode("deep-water-surface-craft")
        root.setTransparency(TransparencyAttrib.MAlpha)
        root.setScale(float(CRAFT_VISUAL_SCALE))
        hull = (0.42, 0.96, 1.0, 0.96)
        hull_inner = (0.10, 0.48, 0.66, 0.78)
        glow = (0.64, 1.00, 1.00, 0.54)
        engine = (1.00, 0.86, 0.36, 0.62)
        rail = (0.16, 0.52, 0.72, 0.70)
        wake = (0.62, 0.96, 1.0, 0.36)
        # Larger, clearer craft silhouette: forward canopy, winglets, engine rings, and wake trails.
        self.add_polyline(root, [Vec3(0.0, 3.8, -0.52), Vec3(-2.2, 1.4, -1.10), Vec3(-2.6, -1.8, -1.38), Vec3(0.0, -3.4, -1.22), Vec3(2.6, -1.8, -1.38), Vec3(2.2, 1.4, -1.10), Vec3(0.0, 3.8, -0.52)], hull, self.cfg.line_thickness * 0.72, True, "craft-hull")
        self.add_polyline(root, [Vec3(0.0, 2.2, -0.34), Vec3(-1.1, 0.6, -0.84), Vec3(0.0, -0.8, -0.96), Vec3(1.1, 0.6, -0.84), Vec3(0.0, 2.2, -0.34)], hull_inner, self.cfg.line_thickness * 0.48, True, "craft-canopy")
        self.add_polyline(root, [Vec3(-2.0, 0.6, -1.08), Vec3(-4.2, -0.4, -1.28), Vec3(-5.8, -1.8, -1.44)], hull, self.cfg.line_thickness * 0.42, False, "craft-left-wing")
        self.add_polyline(root, [Vec3(2.0, 0.6, -1.08), Vec3(4.2, -0.4, -1.28), Vec3(5.8, -1.8, -1.44)], hull, self.cfg.line_thickness * 0.42, False, "craft-right-wing")
        self.add_polyline(root, [Vec3(0.0, 1.0, 0.38), Vec3(0.0, -0.2, 0.92), Vec3(0.0, -1.8, 0.40)], rail, self.cfg.line_thickness * 0.38, False, "craft-fin")
        self.add_polyline(root, self.polygon_points(0.88, -2.42, 14, 0.0), engine, self.cfg.line_thickness * 0.34, True, "craft-engine-core")
        self.add_polyline(root, self.polygon_points(1.34, -2.42, 14, 0.0), glow, self.cfg.line_thickness * 0.28, True, "craft-engine-halo")
        self.add_polyline(root, [Vec3(-2.52, 1.2, -1.56), Vec3(-2.92, -2.6, -1.62), Vec3(-2.10, -3.2, -1.56)], rail, self.cfg.line_thickness * 0.34, False, "craft-left-pontoon")
        self.add_polyline(root, [Vec3(2.52, 1.2, -1.56), Vec3(2.92, -2.6, -1.62), Vec3(2.10, -3.2, -1.56)], rail, self.cfg.line_thickness * 0.34, False, "craft-right-pontoon")
        self.add_polyline(root, [Vec3(-1.3, -2.8, -1.68), Vec3(-3.6, -5.8, -1.84), Vec3(-5.6, -8.4, -1.98)], wake, self.cfg.line_thickness * 0.30, False, "craft-left-wake")
        self.add_polyline(root, [Vec3(1.3, -2.8, -1.68), Vec3(3.6, -5.8, -1.84), Vec3(5.6, -8.4, -1.98)], wake, self.cfg.line_thickness * 0.30, False, "craft-right-wake")
        self.underwater_vehicle_root = root
        return root

    def hide_underwater_vehicle(self):
        if getattr(self, "underwater_vehicle_root", None) is not None:
            try:
                self.underwater_vehicle_root.removeNode()
            except Exception:
                pass
        self.underwater_vehicle_root = None

    def update_underwater_vehicle(self, dt):
        if not self.travel_craft_active():
            self.hide_underwater_vehicle()
            return
        craft = self.ensure_underwater_vehicle()
        if craft is None:
            return
        yaw_rad = math.radians(self.player_yaw)
        forward = Vec3(math.sin(yaw_rad), math.cos(yaw_rad), 0.0)
        craft_pos = Vec3(self.player_pos) + forward * float(CRAFT_VISUAL_FORWARD_OFFSET) + Vec3(0.0, 0.0, float(CRAFT_VISUAL_VERTICAL_OFFSET))
        craft.setPos(craft_pos)
        craft.setH(self.player_yaw)
        flight_active = bool(getattr(self, "flight_craft_active", False))
        speed_vec = Vec3(getattr(self, "player_velocity", Vec3(0, 0, 0)))
        speed_norm = max(1.0, float(self.cfg.walk_speed) * float(CRAFT_FLIGHT_SPEED_MULTIPLIER)) if flight_active else max(1.0, self.cfg.sprint_speed * 1.4)
        speed = min(1.0, speed_vec.length() / speed_norm)
        if flight_active:
            craft.setP(self.player_pitch * 0.32 + math.sin(self.elapsed * 2.1) * (0.5 + speed * 1.2))
            craft.setR((-self.move_velocity.x / max(1.0, self.cfg.walk_speed)) * 7.5 + math.sin(self.elapsed * 1.45 + self.player_yaw * 0.02) * 1.6)
            craft.setColorScale(1.02 + speed * 0.26, 0.96 + speed * 0.18, 1.08, 0.96)
        else:
            bob = math.sin(self.elapsed * 2.2) * 1.5
            roll = math.sin(self.elapsed * 1.45 + self.player_yaw * 0.02) * 3.2
            craft.setP(bob)
            craft.setR(roll)
            craft.setColorScale(0.92 + speed * 0.24, 1.00 + speed * 0.10, 1.08, 0.88)

    def update_artifact_focus(self, dt):
        self.find_nearest_artifact()
        try:
            self.core_ui["text"] = "CORE // HUB ONLY"
        except Exception:
            pass

    def animate_accents(self, dt):
        pulse = 0.10 + 0.05 * math.sin(self.elapsed * 1.6)
        self.accent_root.setColorScale(1, 1, 1, 0.78 + pulse)
        self.line_root.setColorScale(1, 1, 1, 0.98)
        self.dome_root.setColorScale(1, 1, 1, 0.96)
        if self.menu_open:
            self.center_hint["text"] = ""
            return
        if self.elapsed < self.build_hint_override_until:
            return
        if self.is_near_core():
            self.center_hint["text"] = "E // CORE OPTIONS"
        elif getattr(self, "flight_craft_active", False):
            self.center_hint["text"] = f"{self.current_zone_name()}   // V exit craft   10x flight hover"
        else:
            self.center_hint["text"] = f"{self.current_zone_name()}   // V craft   1-8 travel   T spawn"

    def update_world_actors(self, dt):
        self.clear_world_actors()


    def update_internal_projectiles(self, dt):
        return

    def update_internal_modes(self, dt):
        return

    def self_test_setup(self, task):
        self.active_artifact = None
        self.active_artifact_id = None
        self.transition_target = 0.0
        self.transition_progress = 0.0
        self.world_unlocked = False
        self.clear_world_chunks()
        pos = Vec3(0.0, -18.0, self.cfg.player_eye_height + 12.0)
        focus = Vec3(0.0, 0.0, 5.0)
        view_key = str(SELF_TEST_VIEW).lower()
        skip_final_chunk_update = False
        if view_key in ("sky", "celestial"):
            # Space-sky proof angle: upward enough to show the shared star shell and persistent star overlay.
            pos = Vec3(0.0, -42.0, self.cfg.player_eye_height + 13.0)
            focus = Vec3(0.0, 34.0, 226.0)
        elif view_key in ("forest", "trees", "lush"):
            ring = self.biome_ring_for_key(2) or BIOME_RINGS[1]
            arrival, radius, angle = self.biome_arrival_point(ring)
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            pos = arrival - direction * 18.0 + tangent * 44.0 + Vec3(0.0, 0.0, 22.0)
            focus = arrival + direction * 185.0 + Vec3(0.0, 0.0, 13.5)
        elif view_key in ("understory", "forestfloor", "bushes"):
            ring = self.biome_ring_for_key(2) or BIOME_RINGS[1]
            arrival, radius, angle = self.biome_arrival_point(ring)
            sector_idx = int((angle % math.tau) / (math.tau / float(BIOME_SECTOR_COUNT))) % BIOME_SECTOR_COUNT
            forest_travel = region_travel_for_number(1) or {}
            items = generate_forest_understory_items(
                sector_idx, float(ring["r0"]), float(ring["r1"]),
                sector_count=BIOME_SECTOR_COUNT, corridor_degrees=BIOME_CORRIDOR_DEGREES,
                vanta_radius=float(forest_travel.get("radius", radius)),
                landing_radius=float(forest_travel.get("landing_radius", radius - 48.0)),
                anchor_angle_deg=BIOME_ANCHOR_ANGLE_DEG,
            )
            bushes = [item for item in items if str(item.kind) == "bush"]
            target = bushes[len(bushes)//2] if bushes else items[0]
            center = Vec3(float(target.x), float(target.y), self.world_height_at(float(target.x), float(target.y)))
            radial = Vec3(center.x, center.y, 0.0); radial.normalize()
            tangent = Vec3(-radial.y, radial.x, 0.0)
            self.player_pos = center + Vec3(0,0,self.cfg.player_eye_height)
            self.update_world_chunks(force=True)
            pos = center - radial * 17.0 + tangent * 10.0 + Vec3(0,0,5.8)
            focus = center + radial * 6.0 + Vec3(0,0,2.1)
        elif view_key in ("hillsnature", "meadow", "hillsshapes"):
            ring = self.biome_ring_for_key(3) or BIOME_RINGS[2]
            arrival, radius, angle = self.biome_arrival_point(ring)
            sector_idx = int((angle % math.tau) / (math.tau / float(BIOME_SECTOR_COUNT))) % BIOME_SECTOR_COUNT
            hills_travel = region_travel_for_number(2) or {}
            items = generate_hills_meadow_items(
                sector_idx, float(ring["r0"]), float(ring["r1"]),
                sector_count=BIOME_SECTOR_COUNT, corridor_degrees=BIOME_CORRIDOR_DEGREES,
                nyx_radius=float(hills_travel.get("radius", radius)),
                landing_radius=float(hills_travel.get("landing_radius", radius - 48.0)),
                anchor_angle_deg=BIOME_ANCHOR_ANGLE_DEG,
            )
            shrubs = [item for item in items if str(item.kind) == "shrub"]
            target = shrubs[len(shrubs)//2] if shrubs else items[0]
            center = Vec3(float(target.x), float(target.y), self.world_height_at(float(target.x), float(target.y)))
            radial = Vec3(center.x, center.y, 0.0); radial.normalize()
            tangent = Vec3(-radial.y, radial.x, 0.0)
            self.player_pos = center + Vec3(0,0,self.cfg.player_eye_height)
            self.update_world_chunks(force=True)
            pos = center - radial * 18.0 + tangent * 9.0 + Vec3(0,0,5.4)
            focus = center + radial * 5.0 + Vec3(0,0,1.8)
        elif view_key in ("ringhandoff", "ring_lifecycle", "regionstream"):
            forest_ring = self.biome_ring_for_key(2) or BIOME_RINGS[1]
            hills_ring = self.biome_ring_for_key(3) or BIOME_RINGS[2]
            mushroom_ring = self.biome_ring_for_key(4) or BIOME_RINGS[3]
            desert_ring = self.biome_ring_for_key(5) or BIOME_RINGS[4]
            ice_ring = self.biome_ring_for_key(6) or BIOME_RINGS[5]
            forest_arrival, _, _ = self.biome_arrival_point(forest_ring)
            self.player_pos = Vec3(forest_arrival)
            self.update_world_chunks(force=True)
            before_keys = sorted({int(key[0]) for key in self.terrain_chunks})
            before_counts = {str(k): sum(1 for key in self.terrain_chunks if int(key[0]) == k) for k in before_keys}

            hills_arrival, _, _ = self.biome_arrival_point(hills_ring)
            self.player_pos = Vec3(hills_arrival)
            self.update_world_chunks(force=True)
            hills_keys = sorted({int(key[0]) for key in self.terrain_chunks})
            hills_counts = {str(k): sum(1 for key in self.terrain_chunks if int(key[0]) == k) for k in hills_keys}

            mushroom_arrival, radius, angle = self.biome_arrival_point(mushroom_ring)
            self.player_pos = Vec3(mushroom_arrival)
            self.update_world_chunks(force=True)
            mushroom_keys = sorted({int(key[0]) for key in self.terrain_chunks})
            mushroom_counts = {str(k): sum(1 for key in self.terrain_chunks if int(key[0]) == k) for k in mushroom_keys}

            # Continue outward through the accepted full-ring sequence and prove
            # Desert -> Ice ownership transfer.  Then return one ring and
            # re-enter Ice so the final proof frame represents Pass 282.37.
            desert_arrival, _, _ = self.biome_arrival_point(desert_ring)
            self.player_pos = Vec3(desert_arrival)
            self.update_world_chunks(force=True)
            desert_keys = sorted({int(key[0]) for key in self.terrain_chunks})
            desert_counts = {str(k): sum(1 for key in self.terrain_chunks if int(key[0]) == k) for k in desert_keys}

            ice_arrival, radius, angle = self.biome_arrival_point(ice_ring)
            self.player_pos = Vec3(ice_arrival)
            self.update_world_chunks(force=True)
            ice_keys = sorted({int(key[0]) for key in self.terrain_chunks})
            ice_counts = {str(k): sum(1 for key in self.terrain_chunks if int(key[0]) == k) for k in ice_keys}

            self.player_pos = Vec3(desert_arrival)
            self.update_world_chunks(force=True)
            return_keys = sorted({int(key[0]) for key in self.terrain_chunks})
            return_counts = {str(k): sum(1 for key in self.terrain_chunks if int(key[0]) == k) for k in return_keys}
            self.player_pos = Vec3(ice_arrival)
            self.update_world_chunks(force=True)
            restore_keys = sorted({int(key[0]) for key in self.terrain_chunks})
            restore_counts = {str(k): sum(1 for key in self.terrain_chunks if int(key[0]) == k) for k in restore_keys}

            self.ring_lifecycle_selftest_data = {
                "forest_before_loaded_ring_keys": before_keys,
                "forest_before_sector_counts": before_counts,
                "hills_after_loaded_ring_keys": hills_keys,
                "hills_after_sector_counts": hills_counts,
                "forest_unloaded_after_hills_entry": 2 not in hills_keys,
                "hills_full_ring_loaded": hills_counts.get("3", 0) == int(BIOME_SECTOR_COUNT),
                "mushroom_after_loaded_ring_keys": mushroom_keys,
                "mushroom_after_sector_counts": mushroom_counts,
                "hills_unloaded_after_mushroom_entry": 3 not in mushroom_keys,
                "mushroom_full_ring_loaded": mushroom_counts.get("4", 0) == int(BIOME_SECTOR_COUNT),
                "desert_after_loaded_ring_keys": desert_keys,
                "desert_after_sector_counts": desert_counts,
                "mushroom_unloaded_after_desert_entry": 4 not in desert_keys,
                "desert_full_ring_loaded": desert_counts.get("5", 0) == int(BIOME_SECTOR_COUNT),
                "ice_after_loaded_ring_keys": ice_keys,
                "ice_after_sector_counts": ice_counts,
                "desert_unloaded_after_ice_entry": 5 not in ice_keys,
                "ice_full_ring_loaded": ice_counts.get("6", 0) == int(BIOME_SECTOR_COUNT),
                "desert_return_loaded_ring_keys": return_keys,
                "desert_return_sector_counts": return_counts,
                "ice_unloaded_after_desert_return": 6 not in return_keys,
                "desert_full_ring_reloaded": return_counts.get("5", 0) == int(BIOME_SECTOR_COUNT),
                "ice_restore_loaded_ring_keys": restore_keys,
                "ice_restore_sector_counts": restore_counts,
                "desert_unloaded_after_ice_restore": 5 not in restore_keys,
                "ice_full_ring_restored": restore_counts.get("6", 0) == int(BIOME_SECTOR_COUNT),
                "last_unloaded_detail_ring_key": int(getattr(self, "last_unloaded_detail_ring_key", 0) or 0),
                "active_detail_ring_key": int(getattr(self, "active_detail_ring_key", 0) or 0),
            }
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            pos = ice_arrival + tangent * 104.0 - direction * 68.0 + Vec3(0.0, 0.0, 40.0)
            focus = ice_arrival + direction * 220.0 + tangent * 18.0 + Vec3(0.0, 0.0, 20.0)
        elif view_key in ("hillsrelief", "naturalhills", "rollinghills"):
            ring = self.biome_ring_for_key(3) or BIOME_RINGS[2]
            # Pass 282.33 proof position sits deliberately between radial travel
            # corridors so the broad repeating terrain masses are visible.
            radius = lerp(float(ring["r0"]), float(ring["r1"]), 0.52)
            angle = math.radians(-62.0)
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            ground = self.world_height_at(math.cos(angle) * radius, math.sin(angle) * radius)
            self.player_pos = Vec3(math.cos(angle) * radius, math.sin(angle) * radius, ground + self.cfg.player_eye_height)
            self.update_world_chunks(force=True)
            pos = self.player_pos - direction * 86.0 + tangent * 74.0 + Vec3(0.0, 0.0, 44.0)
            focus = self.player_pos + direction * 155.0 - tangent * 12.0 + Vec3(0.0, 0.0, 12.0)
        elif view_key in ("hills", "flowers", "greenhills"):
            ring = self.biome_ring_for_key(3) or BIOME_RINGS[2]
            arrival, radius, angle = self.biome_arrival_point(ring)
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            self.player_pos = arrival
            self.update_world_chunks(force=True)
            pos = arrival + tangent * 88.0 - direction * 56.0 + Vec3(0.0, 0.0, 30.0)
            focus = arrival + direction * 210.0 + tangent * 20.0 + Vec3(0.0, 0.0, 18.0)
        elif view_key in ("mushroom", "fungal", "fungalstructures", "solace"):
            ring = self.biome_ring_for_key(4) or BIOME_RINGS[3]
            arrival, radius, angle = self.biome_arrival_point(ring)
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            self.player_pos = Vec3(arrival)
            self.update_world_chunks(force=True)
            pos = arrival + tangent * 104.0 - direction * 62.0 + Vec3(0.0, 0.0, 38.0)
            focus = arrival + direction * 225.0 + tangent * 24.0 + Vec3(0.0, 0.0, 22.0)
        elif view_key in ("mushroomclose", "fungalcloseup", "captower", "fungalclose"):
            ring = self.biome_ring_for_key(4) or BIOME_RINGS[3]
            angle = math.radians(-62.0)
            sector_idx = int((angle % math.tau) / (math.tau / float(BIOME_SECTOR_COUNT))) % BIOME_SECTOR_COUNT
            travel = region_travel_for_number(3) or {}
            items = generate_mushroom_structures(
                sector_idx, float(ring["r0"]), float(ring["r1"]),
                sector_count=BIOME_SECTOR_COUNT, corridor_degrees=BIOME_CORRIDOR_DEGREES,
                solace_radius=float(travel.get("radius", 1972.0)),
                landing_radius=float(travel.get("landing_radius", 1918.0)),
                anchor_angle_deg=BIOME_ANCHOR_ANGLE_DEG,
            )
            targets = [item for item in items if str(item.kind) == "cap_tower"] or items
            target = targets[len(targets) // 2]
            center = Vec3(float(target.x), float(target.y), self.world_height_at(float(target.x), float(target.y)))
            radial = Vec3(center.x, center.y, 0.0); radial.normalize()
            tangent = Vec3(-radial.y, radial.x, 0.0)
            self.player_pos = center + Vec3(0, 0, self.cfg.player_eye_height)
            self.update_world_chunks(force=True)
            pos = center - radial * 42.0 + tangent * 24.0 + Vec3(0, 0, 12.0)
            focus = center + radial * 4.0 + Vec3(0, 0, float(target.height) * 0.52)
        elif view_key in ("desert", "pyramid", "pyramids"):
            ring = self.biome_ring_for_key(5) or BIOME_RINGS[4]
            arrival, radius, angle = self.biome_arrival_point(ring)
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            self.player_pos = arrival + direction * 44.0
            self.update_world_chunks(force=True)
            pos = self.player_pos + tangent * 118.0 - direction * 56.0 + Vec3(0.0, 0.0, 34.0)
            focus = self.player_pos + direction * 210.0 + tangent * 42.0 + Vec3(0.0, 0.0, 34.0)
        elif view_key in ("desertclose", "desertnatural", "mesa", "desertmacro"):
            ring = self.biome_ring_for_key(5) or BIOME_RINGS[4]
            angle = math.radians(-58.0)
            sector_idx = int((angle % math.tau) / (math.tau / float(BIOME_SECTOR_COUNT))) % BIOME_SECTOR_COUNT
            travel = region_travel_for_number(4) or {}
            items = generate_desert_macro_structures(
                sector_idx, float(ring["r0"]), float(ring["r1"]),
                sector_count=BIOME_SECTOR_COUNT, corridor_degrees=BIOME_CORRIDOR_DEGREES,
                ember_radius=float(travel.get("radius", 2728.0)),
                landing_radius=float(travel.get("landing_radius", 2672.0)),
                anchor_angle_deg=BIOME_ANCHOR_ANGLE_DEG,
            )
            targets = [item for item in items if str(item.kind) == "mesa"] or items
            target = targets[len(targets) // 2]
            center = Vec3(float(target.x), float(target.y), self.world_height_at(float(target.x), float(target.y)))
            radial = Vec3(center.x, center.y, 0.0); radial.normalize()
            tangent = Vec3(-radial.y, radial.x, 0.0)
            self.player_pos = center + Vec3(0, 0, self.cfg.player_eye_height)
            self.update_world_chunks(force=True)
            cam_xy = center - radial * 92.0 + tangent * 64.0
            cam_ground = self.world_height_at(float(cam_xy.x), float(cam_xy.y))
            pos = Vec3(cam_xy.x, cam_xy.y, float(cam_ground) + self.cfg.player_eye_height)
            focus = center + radial * 6.0 + Vec3(0, 0, max(8.0, float(target.height) * 0.42))
        elif view_key in ("ice", "icecubes", "frozen"):
            ring = self.biome_ring_for_key(6) or BIOME_RINGS[5]
            arrival, radius, angle = self.biome_arrival_point(ring)
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            self.player_pos = Vec3(arrival)
            self.update_world_chunks(force=True)
            pos = arrival + tangent * 112.0 - direction * 74.0 + Vec3(0.0, 0.0, 42.0)
            focus = arrival + direction * 235.0 + tangent * 18.0 + Vec3(0.0, 0.0, 22.0)
        elif view_key in ("iceclose", "glacier", "iceforms", "icespire"):
            ring = self.biome_ring_for_key(6) or BIOME_RINGS[5]
            angle = math.radians(-58.0)
            sector_idx = int((angle % math.tau) / (math.tau / float(BIOME_SECTOR_COUNT))) % BIOME_SECTOR_COUNT
            travel = region_travel_for_number(5) or {}
            track_radius=(float(ring["r0"])+float(ring["r1"]))*0.5
            items=generate_ice_macro_structures(sector_idx,float(ring["r0"]),float(ring["r1"]),track_radius=track_radius,sector_count=BIOME_SECTOR_COUNT,corridor_degrees=BIOME_CORRIDOR_DEGREES,mirror_radius=float(travel.get("radius",3484.0)),landing_radius=float(travel.get("landing_radius",3428.0)),anchor_angle_deg=BIOME_ANCHOR_ANGLE_DEG)
            targets=[item for item in items if str(item.kind)=="crystal_spire"] or items
            target=targets[len(targets)//2]
            center=Vec3(float(target.x),float(target.y),self.world_height_at(float(target.x),float(target.y)))
            radial=Vec3(center.x,center.y,0.0); radial.normalize(); tangent=Vec3(-radial.y,radial.x,0.0)
            self.player_pos=center+Vec3(0,0,self.cfg.player_eye_height); self.update_world_chunks(force=True)
            pos=center-radial*82.0+tangent*58.0+Vec3(0,0,30.0)
            focus=center+Vec3(0,0,max(10.0,float(target.height)*0.52))
        elif view_key in ("craft", "flightcraft", "tabcraft", "aircraft"):
            ring = self.biome_ring_for_key(7) or BIOME_RINGS[6]
            angle = math.radians(-42.0)
            radius = float(ring["r0"]) + 640.0
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            ground = self.world_height_at(math.cos(angle) * radius, math.sin(angle) * radius)
            self.player_pos = Vec3(math.cos(angle) * radius, math.sin(angle) * radius, self.cfg.player_eye_height + ground + float(CRAFT_FLIGHT_MIN_CLEARANCE) + 18.0)
            self.flight_craft_active = True
            self.flight_craft_velocity = Vec3(0, 0, 0)
            self.update_world_chunks(force=True)
            self.ensure_underwater_vehicle()
            pos = self.player_pos + tangent * 72.0 - direction * 82.0 + Vec3(0.0, 0.0, 36.0)
            focus = self.player_pos + direction * 70.0 + tangent * 8.0 + Vec3(0.0, 0.0, -3.0)
        elif view_key in ("highcraft", "stratosphere", "highflight"):
            ring = self.biome_ring_for_key(8) or BIOME_RINGS[-1]
            angle = math.radians(-66.0)
            radius = float(ring["r0"]) + 540.0
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            ground = self.world_height_at(math.cos(angle) * radius, math.sin(angle) * radius)
            self.player_pos = Vec3(math.cos(angle) * radius, math.sin(angle) * radius, self.cfg.player_eye_height + ground + 720.0)
            self.flight_craft_active = True
            self.flight_craft_velocity = Vec3(0, 0, 0)
            self.elapsed = 2.0
            self.update_world_chunks(force=True)
            self.ensure_underwater_vehicle()
            pos = self.player_pos + tangent * 30.0 - direction * 38.0 + Vec3(0.0, 0.0, 10.0)
            focus = self.player_pos + direction * 120.0 + Vec3(0.0, 0.0, -20.0)
        elif view_key in ("oasis", "minibiome", "salvage", "salvaged"):
            ring = self.biome_ring_for_key(5) or BIOME_RINGS[4]
            # Pick a deterministic desert sector that receives the Venus oasis.
            sector = 0
            for candidate in range(BIOME_SECTOR_COUNT):
                if self.mini_biome_allowed(ring, candidate, 9):
                    sector = candidate
                    break
            a0, a1 = self.biome_sector_angle_span(sector, expanded=False)
            angle = (a0 + a1) * 0.5
            radius = (float(ring["r0"]) + float(ring["r1"])) * 0.5
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            ground = self.world_height_at(math.cos(angle) * radius, math.sin(angle) * radius)
            self.player_pos = Vec3(math.cos(angle) * radius, math.sin(angle) * radius, self.cfg.player_eye_height + ground)
            self.update_world_chunks(force=True)
            pos = self.player_pos + tangent * 112.0 - direction * 80.0 + Vec3(0.0, 0.0, 46.0)
            focus = self.player_pos + direction * 115.0 + tangent * 10.0 + Vec3(0.0, 0.0, 24.0)
        elif view_key in ("population", "salvagepop", "lifepop", "densepop"):
            ring = self.biome_ring_for_key(3) or BIOME_RINGS[2]
            # Close proof angle aimed at the new capped salvage-population creatures
            # in a known Green Hills sector. This avoids stale wide shots where the
            # new silhouettes are technically present but too small to judge.
            sector = 39
            idx = 2
            a0, a1 = self.biome_sector_angle_span(sector, expanded=False)
            sector_span = max(0.001, a1 - a0)
            u = (idx + 0.5) / float(max(1, SALVAGE_POPULATION_PER_CHUNK))
            angle = lerp(a0 + sector_span * 0.10, a1 - sector_span * 0.10, u) + (self._deterministic_unit(sector, idx, int(ring["key"]), 311.0) - 0.5) * sector_span * 0.46
            radius = lerp(float(ring["r0"]) + (float(ring["r1"]) - float(ring["r0"])) * 0.06, float(ring["r1"]) - (float(ring["r1"]) - float(ring["r0"])) * 0.08, 0.16 + 0.68 * self._deterministic_unit(sector, idx, int(ring["key"]), 319.0))
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            target_ground = self.world_height_at(math.cos(angle) * radius, math.sin(angle) * radius)
            target = Vec3(math.cos(angle) * radius, math.sin(angle) * radius, target_ground + 3.4)
            self.player_pos = Vec3(target.x, target.y, self.cfg.player_eye_height + target_ground)
            self.update_world_chunks(force=True)
            pos = target - direction * 34.0 + tangent * 18.0 + Vec3(0.0, 0.0, 10.0)
            focus = target + direction * 10.0 + Vec3(0.0, 0.0, 2.8)
        elif view_key in ("water", "deepwater", "underwater", "ocean", "watercraft"):
            ring = self.biome_ring_for_key(4) or BIOME_RINGS[3]
            arrival, radius, angle = self.biome_arrival_point(ring)
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            self.player_pos = arrival + direction * 66.0
            self.player_pos.z = self.deep_water_craft_eye_z(self.player_pos.x, self.player_pos.y, ring)
            self.update_world_chunks(force=True)
            pos = self.player_pos + tangent * 34.0 - direction * 24.0 + Vec3(0.0, 0.0, 7.0)
            focus = self.player_pos + direction * 128.0 + tangent * 4.0 + Vec3(0.0, 0.0, -1.2)
        elif view_key in ("urban", "warzone", "ruins"):
            ring = self.biome_ring_for_key(7) or BIOME_RINGS[6]
            angle = math.radians(-38.0)
            radius = float(ring["r0"]) + 520.0
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            ground = self.world_height_at(math.cos(angle) * radius, math.sin(angle) * radius)
            self.player_pos = Vec3(math.cos(angle) * radius, math.sin(angle) * radius, self.cfg.player_eye_height + ground)
            self.update_world_chunks(force=True)
            pos = self.player_pos + tangent * 138.0 - direction * 104.0 + Vec3(0.0, 0.0, 86.0)
            focus = self.player_pos + direction * 132.0 + tangent * 26.0 + Vec3(0.0, 0.0, 28.0)
        elif view_key in ("metropolis", "city"):
            ring = self.biome_ring_for_key(8) or BIOME_RINGS[-1]
            angle = math.radians(-72.0)
            radius = float(ring["r0"]) + 540.0
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            ground = self.world_height_at(math.cos(angle) * radius, math.sin(angle) * radius)
            self.player_pos = Vec3(math.cos(angle) * radius, math.sin(angle) * radius, self.cfg.player_eye_height + ground)
            self.update_world_chunks(force=True)
            pos = self.player_pos + tangent * 160.0 - direction * 120.0 + Vec3(0.0, 0.0, 118.0)
            focus = self.player_pos + direction * 160.0 + tangent * 32.0 + Vec3(0.0, 0.0, 54.0)
        elif view_key.startswith("bot_") or view_key.startswith("bot-") or view_key in {"botio", "botvanta", "botnyx", "botsolace", "botember", "botmirror", "botsable", "botarchivist", "botorbit"}:
            self.build_named_region_bot_network()
            self.camLens.setFov(56.0)
            self.camLens.setNearFar(0.05, 18000.0)
            self.fog.setLinearRange(9000.0, 18000.0)
            token = view_key.replace("bot_", "").replace("bot-", "").replace("bot", "").strip()
            lookup = {str(node.getPythonTag("named_region_bot_name") or "").lower(): node for node in self._active_named_region_bot_nodes()}
            target_node = lookup.get(token) or lookup.get("io") or (self._active_named_region_bot_nodes()[0] if self._active_named_region_bot_nodes() else None)
            if target_node is not None:
                anchor = Vec3(target_node.getPos(self.world_root))
                angle = math.radians(float(NAMED_REGION_BOT_ANCHOR_ANGLE_DEG))
                direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
                tangent = Vec3(-direction.y, direction.x, 0.0)
                self.player_pos = Vec3(anchor.x, anchor.y, max(anchor.z + 9.0, self.cfg.player_eye_height + 4.0))
                skip_final_chunk_update = True
                pos = anchor - direction * 64.0 + tangent * 32.0 + Vec3(0.0, 0.0, 54.0)
                focus = anchor + Vec3(0.0, 0.0, 22.0)
        elif view_key in ("regionbots", "bots", "botmap", "namedbots"):
            self.build_named_region_bot_network()
            self.camLens.setFov(78.0)
            self.camLens.setNearFar(0.05, 18000.0)
            self.fog.setLinearRange(12800.0, 18000.0)
            self.fog.setColor(0.025, 0.030, 0.040)
            self.setBackgroundColor(0.025, 0.030, 0.040)
            angle = math.radians(float(NAMED_REGION_BOT_ANCHOR_ANGLE_DEG))
            corridor_y = math.sin(angle) * (float(BIOME_OUTER_RADIUS) * 0.50)
            self.player_pos = Vec3(0.0, corridor_y, 210.0)
            self.update_world_chunks(force=True)
            pos = Vec3(6400.0, corridor_y, 4300.0)
            focus = Vec3(0.0, corridor_y, 115.0)
        elif view_key in ("surfaceaudit", "surfaces", "surface"):
            ring = self.biome_ring_for_key(7) or BIOME_RINGS[6]
            angle = math.radians(-46.0)
            radius = float(ring["r0"]) + 360.0
            direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
            tangent = Vec3(-direction.y, direction.x, 0.0)
            ground = self.world_height_at(math.cos(angle) * radius, math.sin(angle) * radius)
            self.player_pos = Vec3(math.cos(angle) * radius, math.sin(angle) * radius, self.cfg.player_eye_height + ground + 40.0)
            self.flight_craft_active = True
            self.flight_craft_velocity = Vec3(0, 0, 0)
            self.update_world_chunks(force=True)
            self.ensure_underwater_vehicle()
            pos = self.player_pos + tangent * 180.0 - direction * 220.0 + Vec3(0.0, 0.0, 120.0)
            focus = self.player_pos + direction * 240.0 + tangent * 14.0 + Vec3(0.0, 0.0, 18.0)
        elif view_key == "ground":
            pos = Vec3(22.0, -24.0, self.cfg.player_eye_height + 1.5)
            focus = Vec3(0.0, -3.0, self.cfg.player_eye_height + 3.4)
        elif view_key == "flatland":
            # Proof angle: shows the hub floor seam and the surrounding flatland in one frame.
            pos = Vec3(70.0, -92.0, self.cfg.player_eye_height + 18.0)
            focus = Vec3(0.0, -7.0, self.cfg.player_eye_height + 2.6)
        elif view_key in ("biomes", "biome"):
            # Pass 37 proof angle: above the Forests safe-arrival corridor,
            # facing outward across connected flow ribbons, range rails, and chevrons.
            ring = self.biome_ring_for_key(2) or BIOME_RINGS[1]
            arrival, radius, angle = self.biome_arrival_point(ring)
            self.player_pos = arrival
            self.update_world_chunks(force=True)
            pos = Vec3(arrival.x + 150.0, arrival.y + 72.0, arrival.z + 105.0)
            focus = self.biome_outward_focus_point(ring, radius, angle)
        yaw, pitch = focus_hpr(pos, Vec3(focus))
        self.player_pos = pos
        self.player_yaw = yaw
        self.player_pitch = pitch
        self.camera.setPos(self.player_pos)
        self.camera.setHpr(self.player_yaw, self.player_pitch, 0)
        if not skip_final_chunk_update:
            self.update_world_chunks(force=True)
        self.apply_world_theme(1.0)
        if str(SELF_TEST_VIEW).lower() == "menu":
            self.menu_open = True
            self.menu_root.show()
            self.set_menu_tab("display")
        self.refresh_ui()
        return Task.done

    def self_test_exit(self, task):
        self.save_space_build_progress(force=True)
        report = {
            "game": GAME_NAME,
            "version": VERSION,
            "config": asdict(self.cfg),
            "active_artifact": self.active_artifact_id,
            "transition_progress": self.transition_progress,
            "latest_log": str(LATEST_LOG),
            "crash_log_exists": CRASH_LOG.exists(),
            "external_process_launching": False,
            "external_launch_settings": False,
            "hub_only": True,
            "active_world_name": WORLD_SPECS[0]["name"],
            "ice_terrain_cell_size": float(ICE_TERRAIN_CELL_SIZE),
            "ice_terrain_step_height": float(ICE_TERRAIN_STEP_HEIGHT),
            "ice_visual_rule": "glacial terrain + solid macro formations + restrained legacy cubic detail",
            "flatworld_visual_fill_enabled": True,
            "flatland_walkable_radius": float(self.flatworld_walkable_radius()),
            "flatland_disc_radius": float(self.flatworld_disc_radius()),
            "flatland_floor_z": round(self.flatworld_boundary_floor_z(), 3),
            "flatland_connected_to_hub_floor": abs(self.flatworld_boundary_floor_z() - self.hub_ground_level()) < 0.001,
            "t_returns_to_spawn": True,
            "biome_terrain_rings_enabled": True,
            "biome_ring_order": [ring["name"] for ring in BIOME_RINGS],
            "biome_outer_radius": float(BIOME_OUTER_RADIUS),
            "biome_stream_sector_count": int(BIOME_SECTOR_COUNT),
            "biome_active_chunks": len(getattr(self, "terrain_chunks", {}) or {}),
            "biome_chunk_cap": int(MAX_BIOME_TERRAIN_CHUNKS),
            "biome_ground_level": round(self.hub_ground_level(), 3),
            "biome_fast_travel_keys": {str(ring["key"]): ring["name"] for ring in BIOME_RINGS},
            "biome_terrain_guides_pass32": True,
            "biome_traversal_corridors_pass33": True,
            "biome_route_beacons_pass34": True,
            "biome_chunk_stitching_pass34": True,
            "biome_expanded_rings_pass35": True,
            "biome_orientation_horizon_pass36": True,
            "biome_safe_arrival_pads_pass36": True,
            "biome_fast_travel_faces_outward_pass36": True,
            "biome_beautiful_connected_pass37": True,
            "persistent_space_sky_pass26": True,
            "day_night_cycle_retired_pass26": True,
            "sun_moon_markers_retired_pass26": True,
            "space_sky_texture_path": str(SPACE_SKY_TEXTURE_PATH),
            "space_sky_texture_exists": SPACE_SKY_TEXTURE_PATH.exists(),
            "space_sky_lat_steps": int(SPACE_SKY_LAT_STEPS),
            "space_sky_lon_steps": int(SPACE_SKY_LON_STEPS),
            "space_sky_shell_surface_count": len(getattr(self, "space_sky_cards", []) or []),
            "legacy_sky_background_cards_removed": True,
            "dynamic_sky_guides_configured": True,
            "forest_trees_pass41": True,
            "forest_tree_variants": list(getattr(self, "forest_tree_variants", FOREST_TREE_VARIANTS)),
            "forest_tree_grid_snapped": True,
            "forest_tree_active_count": sum(int((chunk.getPythonTag("forest_tree_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "forest_tall_tree_count": sum(int((chunk.getPythonTag("forest_tall_tree_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "forest_tall_tree_bonus_per_chunk_pass55": int(FOREST_TALL_TREE_BONUS_PER_CHUNK),
            "forest_full_ring_density_pass28221": True,
            "forest_detail_patches_per_sector": int(FOREST_DETAIL_PATCH_COUNT),
            "forest_detail_plants_per_patch": int(FOREST_DETAIL_PLANT_COUNT_PER_PATCH),
            "forest_detail_active_patch_count": sum(int((chunk.getPythonTag("forest_detail_patch_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "forest_detail_active_tree_count": sum(int((chunk.getPythonTag("forest_detail_tree_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "forest_detail_active_crown_count": sum(int((chunk.getPythonTag("forest_detail_crown_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "forest_understory_pass28231": True,
            "forest_understory_bushes_per_patch": int(FOREST_UNDERSTORY_BUSH_COUNT_PER_PATCH),
            "forest_understory_ferns_per_patch": int(FOREST_UNDERSTORY_FERN_COUNT_PER_PATCH),
            "forest_understory_grass_per_patch": int(FOREST_UNDERSTORY_GRASS_COUNT_PER_PATCH),
            "forest_understory_active_bush_count": sum(int((chunk.getPythonTag("forest_understory_bush_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "forest_understory_active_fern_count": sum(int((chunk.getPythonTag("forest_understory_fern_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "forest_understory_active_grass_count": sum(int((chunk.getPythonTag("forest_understory_grass_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "forest_understory_active_deadfall_count": sum(int((chunk.getPythonTag("forest_understory_deadfall_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "green_hills_gradual_roll_pass43": True,
            "green_hills_grid_snapped_flowers": True,
            "green_hills_active_flower_count": sum(int((chunk.getPythonTag("hill_flower_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "desert_pass50": True,
            "desert_pyramid_count": sum(int((chunk.getPythonTag("desert_pyramid_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "desert_obelisk_count": sum(int((chunk.getPythonTag("desert_obelisk_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "desert_visual_rebuild_pass28236": True,
            "desert_dune_wave_family_count_pass28236": len(DESERT_DUNE_WAVES),
            "desert_macro_structures_per_sector_pass28236": int(DESERT_MACRO_STRUCTURES_PER_SECTOR),
            "desert_natural_active_structure_count": sum(int((chunk.getPythonTag("desert_natural_structure_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "desert_mesa_count": sum(int((chunk.getPythonTag("desert_mesa_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "desert_rock_spire_count": sum(int((chunk.getPythonTag("desert_rock_spire_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "desert_boulder_field_count": sum(int((chunk.getPythonTag("desert_boulder_field_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "desert_buried_ruin_count": sum(int((chunk.getPythonTag("desert_buried_ruin_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "desert_macro_collision_policy": "visual_only_pass28236",
            "desert_sky_authority": "SPACE",
            "ice_pass50": True,
            "ice_pass51_terrain_grid": True,
            "ice_cube_count": sum(int((chunk.getPythonTag("ice_cube_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "ice_floating_cube_count": sum(int((chunk.getPythonTag("ice_floating_cube_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "ice_fauna_count": sum(int((chunk.getPythonTag("ice_fauna_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "ice_visual_rebuild_pass28237": True,
            "ice_glacial_wave_family_count_pass28237": len(ICE_GLACIAL_WAVES),
            "ice_macro_structures_per_sector_pass28237": int(ICE_MACRO_STRUCTURES_PER_SECTOR),
            "ice_macro_active_structure_count": sum(int((chunk.getPythonTag("ice_macro_structure_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "ice_glacial_ridge_count": sum(int((chunk.getPythonTag("ice_glacial_ridge_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "ice_crystal_spire_count": sum(int((chunk.getPythonTag("ice_crystal_spire_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "ice_shelf_count": sum(int((chunk.getPythonTag("ice_shelf_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "ice_pressure_ridge_count": sum(int((chunk.getPythonTag("ice_pressure_ridge_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "ice_crevasse_fin_count": sum(int((chunk.getPythonTag("ice_crevasse_fin_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "ice_macro_collision_policy": "visual_only_pass28237",
            "ice_sky_authority": "SPACE",
            "ice_surface_traction": 0.26,
            "deep_water_pass45": True,
            "deep_water_surface_ripples": True,
            "deep_water_swim_enabled": False,
            "deep_water_surface_craft_enabled_pass56": True,
            "deep_water_dynamic_ocean_movement_pass56": True,
            "deep_water_hub_ring_swim_fix_pass55": True,
            "deep_water_pass56_ocean_watercraft": True,
            "deep_water_ground_mesh_removed_pass56": True,
            "deep_water_region_signs_removed_pass56": True,
            "deep_water_only_streaming_pass56": True,
            "deep_water_occlusion_active": bool(getattr(self, "water_region_occlusion_active", False)),
            "deep_water_craft_visible": bool(getattr(self, "underwater_vehicle_root", None) is not None and not self.underwater_vehicle_root.isEmpty()),
            "tab_flight_craft_enabled": True,
            "tab_flight_craft_hub_locked": True,
            "tab_flight_craft_speed_multiplier": float(CRAFT_FLIGHT_SPEED_MULTIPLIER),
            "tab_flight_craft_hover_stop": True,
            "deep_water_occlusion_fog_far": float(DEEP_WATER_OCCLUSION_FOG_FAR),
            "deep_water_non_water_chunks_visible": sum(1 for key in (getattr(self, "terrain_chunks", {}) or {}).keys() if int(key[0]) != 4),
            "deep_water_ground_removed_chunk_count": sum(1 for chunk in (getattr(self, "terrain_chunks", {}) or {}).values() if int(chunk.getPythonTag("deep_water_ground_removed") or 0) == 1),
            "deep_water_terrain_stitch_removed_chunk_count": sum(1 for chunk in (getattr(self, "terrain_chunks", {}) or {}).values() if int(chunk.getPythonTag("deep_water_terrain_stitch_removed") or 0) == 1),
            "deep_water_creature_count": sum(int((chunk.getPythonTag("deep_water_creature_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "deep_water_flora_count": sum(int((chunk.getPythonTag("deep_water_flora_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "deep_water_feature_count": sum(int((chunk.getPythonTag("deep_water_feature_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "deep_water_hero_count": sum(int((chunk.getPythonTag("deep_water_hero_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "deep_water_coral_count": sum(int((chunk.getPythonTag("deep_water_coral_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "deep_water_bubble_count": sum(int((chunk.getPythonTag("deep_water_bubble_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "deep_water_surface_line_count": sum(int((chunk.getPythonTag("water_surface_line_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "deep_water_depth_factor": round(float(getattr(self, "current_water_depth", 0.0)), 4),
            "urban_pass54": True,
            "urban_pass55_finished_battlefield": True,
            "urban_pass14_vector_warzone": True,
            "urban_ruin_count": sum(int((chunk.getPythonTag("urban_ruin_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "urban_structured_block_count": sum(int((chunk.getPythonTag("urban_structured_block_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "urban_battle_count": sum(int((chunk.getPythonTag("urban_battle_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "urban_mech_count": sum(int((chunk.getPythonTag("urban_mech_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "urban_drone_count": sum(int((chunk.getPythonTag("urban_drone_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "urban_skeleton_count": sum(int((chunk.getPythonTag("urban_skeleton_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "urban_airstrike_count": sum(int((chunk.getPythonTag("urban_airstrike_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "urban_trench_count": sum(int((chunk.getPythonTag("urban_trench_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "urban_smoke_count": sum(int((chunk.getPythonTag("urban_smoke_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "lush_nature_colors_pass42": True,
            "lush_nature_palette_kinds": sorted(LUSH_NATURE_KINDS),
            "lush_nature_active_accent_lines": sum(int((chunk.getPythonTag("lush_accent_line_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "lush_nature_textureless": True,
            "celestial_star_count": int(CELESTIAL_STAR_COUNT),
            "current_sun_alpha": 0.0,
            "current_moon_alpha": 0.0,
            "current_star_alpha": round(float(getattr(self, "current_star_alpha", 0.88)), 4),
            "persistent_space_sky": True,
            "space_sky_texture": str(SPACE_SKY_TEXTURE_PATH.name),
            "space_sky_surface_count": len(getattr(self, "space_sky_cards", []) or []),
            "current_sky_biome": getattr(self, "current_sky_biome", "SPACE"),
            "stratosphere_factor": round(float(self.craft_stratosphere_factor()), 4),
            "craft_high_altitude_unlocked": float(CRAFT_FLIGHT_MAX_EYE_Z),
            "biome_ground_sky_separation_pass": True,
            "current_bg_rgb": [round(float(c), 5) for c in getattr(self, "current_bg_rgb", (0, 0, 0))],
            "sky_palette_biomes": ["SPACE"],
            "biome_continuous_flow_ribbons_pass37": True,
            "biome_seam_braid_rings_pass37": True,
            "biome_interior_rhythm_rails_pass37": True,
            "biome_horizon_guide_t_values": list(BIOME_HORIZON_GUIDE_T_VALUES),
            "biome_flow_ribbon_degrees": list(BIOME_FLOW_RIBBON_DEGREES),
            "biome_seam_braid_offsets": list(BIOME_SEAM_BRAID_OFFSETS),
            "biome_interior_rhythm_t_values": list(BIOME_INTERIOR_RHYTHM_T_VALUES),
            "biome_ring_widths": {ring["name"]: round(float(ring["r1"] - ring["r0"]), 2) for ring in BIOME_RINGS},
            "continuous_inner_ring_render_pass28223": False,
            "continuous_inner_ring_band_count": 0,
            "forest_full_ring_streaming_pass28224": True,
            "forest_full_ring_sector_count": int(BIOME_SECTOR_COUNT),
            "forest_full_ring_chunk_cap": int(MAX_BIOME_TERRAIN_CHUNKS),
            "forest_full_ring_hillside_retention": float(FOREST_FULL_RING_HILLSIDE_RETENTION),
            "forest_full_ring_active_chunks": sum(1 for key in (getattr(self, "terrain_chunks", {}) or {}) if int(key[0]) == int(FOREST_FULL_RING_KEY)),
            "active_full_ring_keys_pass28234": list(ACTIVE_FULL_RING_KEYS),
            "active_ring_exclusive_streaming_pass28235": bool(ACTIVE_RING_EXCLUSIVE_STREAMING),
            "ring_lifecycle_selftest": dict(getattr(self, "ring_lifecycle_selftest_data", {}) or {}),
            "green_hills_meadow_shapes_per_sector_pass28232": int(HILLS_MEADOW_SHAPE_COUNT_PER_SECTOR),
            "green_hills_repeating_relief_pass28233": True,
            "green_hills_repeating_relief_band_count": len(HILLS_REPEAT_BANDS),
            "green_hills_nominal_repeating_hill_count": sum(int(row[1]) for row in HILLS_REPEAT_BANDS),
            "green_hills_meadow_active_shape_count": sum(int((chunk.getPythonTag("hill_meadow_shape_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "green_hills_solid_tree_per_sector_pass28245": int(HILLS_SOLID_TREES_PER_SECTOR),
            "green_hills_active_solid_tree_count": sum(int((chunk.getPythonTag("hills_solid_tree_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "mushroom_full_ring_pass28234": 4 in tuple(int(v) for v in ACTIVE_FULL_RING_KEYS),
            "mushroom_solid_structures_per_sector_pass28234": int(MUSHROOM_STRUCTURES_PER_SECTOR),
            "mushroom_solid_active_structure_count": sum(int((chunk.getPythonTag("mushroom_solid_structure_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "mushroom_wire_batched_pass28234": True,
            "biome_min_nonflat_ring_width": round(min(float(ring["r1"] - ring["r0"]) for ring in BIOME_RINGS if ring["kind"] != "flat"), 2),
            "biome_fog_distance": round(float(self.cfg.fog_distance), 2),
            "biome_corridor_degrees": list(BIOME_CORRIDOR_DEGREES),
            "biome_height_corridor_easing_enabled": True,
            "biome_connected_hills_all_nonflat_pass55": True,
            "biome_ring_heights": {ring["name"]: float(ring.get("height", 0.0)) for ring in BIOME_RINGS},
            "biome_feature_signature_guides_enabled": True,
            "biome_profile_guide_degrees": list(BIOME_PROFILE_GUIDE_DEGREES),
            "biome_fast_travel_anchor_count": len(BIOME_RINGS),
            "biome_contour_t_values": list(BIOME_CONTOUR_T_VALUES),
            "simulator_worlds_removed": True,
            "hub_tables_removed": True,
            "hub_infill_removed": True,
            "campaign_option_removed": True,
            "ui_minimized": True,
            "hub_telescope_removed": True,
            "hub_center_beacon_enabled": True,
            "line_flicker_mitigation": True,
            "line_pop_stabilization_pass59": True,
            "metropolis_preload_radius_pass59": int(METROPOLIS_PRELOAD_RADIUS),
            "metropolis_active_chunks_pass59": len(getattr(self, "metropolis_chunks", {}) or {}),
            "metropolis_max_chunks_pass59": int(MAX_METROPOLIS_CHUNKS),
            "metropolis_generic_biome_terrain_disabled_pass59": True,
            "metropolis_duplicate_edge_suppression_count": int(getattr(self, "metropolis_duplicate_edge_suppression_count", 0)),
            "metropolis_overlap_skip_count": int(getattr(self, "metropolis_overlap_skip_count", 0)),
            "surface_authority_pass62": True,
            "surface_audit_summary": dict(getattr(self, "surface_audit_summary", {}) or {}),
            "surface_owned_sector_mode": bool((getattr(self, "surface_audit_summary", {}) or {}).get("surface_owned_sector_mode", False)),
            "surface_duplicate_owner_key_count": int((getattr(self, "surface_audit_summary", {}) or {}).get("duplicate_surface_owner_keys", 0)),
            "surface_biome_fill_surface_count": int((getattr(self, "surface_audit_summary", {}) or {}).get("biome_fill_surface_count", 0)),
            "surface_water_fill_suppressed_count": int((getattr(self, "surface_audit_summary", {}) or {}).get("water_fill_suppressed_count", 0)),
            "surface_metropolis_generic_overlap_removed_count": int((getattr(self, "surface_audit_summary", {}) or {}).get("metropolis_generic_overlap_removed_count", 0)),
            "grid_fill_palette_pass63": True,
            "grid_fill_palette": {"flat": "white", "forest": "green", "hills": "yellow", "water": "none", "desert": "amber", "ice": "blue", "urban": "grey", "metropolis": "purple", "space": "black"},
            "salvaged_oasis_pass64": True,
            "mini_jungle_oasis_count": sum(int((chunk.getPythonTag("mini_jungle_oasis_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "mini_venus_oasis_count": sum(int((chunk.getPythonTag("mini_venus_oasis_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "deep_water_sky_creature_count": sum(int((chunk.getPythonTag("deep_water_sky_creature_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "deep_water_total_creature_count": sum(int((chunk.getPythonTag("deep_water_creature_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "io88_flatworld_present": bool(getattr(self, "io88_bot_root", None) is not None and not self.io88_bot_root.isEmpty()),
            "space_layer_enabled_pass64": True,
            "space_layer_active": bool(getattr(self, "space_layer_active", False)),
            "space_layer_star_count": int(SPACE_LAYER_STAR_COUNT),
            "space_layer_asteroid_count": int(SPACE_LAYER_ASTEROID_COUNT),
            "space_layer_factor": round(float(self.space_layer_factor()), 4),
            "salvage_population_pass65": True,
            "salvage_population_per_chunk_cap": int(SALVAGE_POPULATION_PER_CHUNK),
            "salvage_population_size_scale": float(SALVAGE_POPULATION_SIZE_SCALE),
            "salvage_population_node_cap": int(MAX_SALVAGE_POPULATION_NODES),
            "salvage_population_active_node_count": len([n for n in (getattr(self, "salvage_population_nodes", []) or []) if n is not None and not n.isEmpty()]),
            "salvage_population_streamed_count": sum(int((chunk.getPythonTag("salvage_population_count") or 0)) for chunk in (getattr(self, "terrain_chunks", {}) or {}).values()),
            "salvage_population_pruned_count": int(getattr(self, "salvage_population_pruned_count", 0)),
            "named_region_bots_pass66": True,
            "named_region_bot_mapping": dict(NAMED_REGION_BOT_MAPPING),
            "named_region_bot_cap": int(MAX_NAMED_REGION_BOTS),
            "named_region_bot_active_count": len(self._active_named_region_bot_nodes()),
            "named_region_bot_labels": [str(node.getPythonTag("named_region_bot_name") or "") for node in self._active_named_region_bot_nodes()],
            "named_region_bot_regions": [str(node.getPythonTag("named_region_bot_region") or "") for node in self._active_named_region_bot_nodes()],
            "named_region_bot_solid_color_boxes": True,
            "named_region_bot_hovering": True,
            "named_region_bot_io_silver": True,
            "legacy_noop_updates_gated": True,
            "salvaged_artifact_world_policy": "mini-biome-oases; fractured/shattered excluded",
            "grid_fill_land_alpha": 1.0,
            "mushroom_replaces_deep_water_pass85": True,
            "water_has_ground_fill": False,
            "water_has_ground_colliders": False,
            "effective_line_thickness": float(self.cfg.line_thickness),
            "menu_tab_count": len(getattr(self, "menu_tab_buttons", []) or []),
            "visible_menu_tabs": [key for key, _btn in getattr(self, "menu_tab_buttons", [])],
            "world_anchor": tuple(round(v, 3) for v in self.world_anchor_point().xyz),
            "world_hub_clear_radius": float(self.world_hub_clear_radius_for_spec()),
            "hub_ground_z": round(self.hub_ground_level(), 3),
            "anchor_ground_z": round(self.world_height_at(self.world_anchor_point().x, self.world_anchor_point().y, self.current_world_spec()), 3),
            "entry_ground_z": round(self.world_height_at(self.world_anchor_point().x - self.world_anchor_direction(self.current_world_spec()).x * 12.0, self.world_anchor_point().y - self.world_anchor_direction(self.current_world_spec()).y * 12.0, self.current_world_spec()), 3),
            "grade_match_radius": float(self.world_ground_match_radius_for_spec()),
            "grade_match_blend": float(self.world_ground_match_blend_for_spec()),
            "sector_gate_count": len(self.artifacts),
            "artifact_world_ids": list(ARTIFACT_WORLD_IDS),
            "artifact_world_names": [WORLD_SPECS.get(world_id, {}).get("name", str(world_id)) for world_id in ARTIFACT_WORLD_IDS],
            "user_building_count": len(self.user_buildings),
            "selected_user_build_key": list(self.selected_user_build_key) if self.selected_user_build_key is not None else None,
            "user_build_save_exists": USER_BUILD_SAVE_PATH.exists(),
            "space_build_progress_save_exists": SPACE_BUILD_PROGRESS_PATH.exists(),
            "space_build_progress_path": str(SPACE_BUILD_PROGRESS_PATH),
            "space_build_total_seconds": round(float(getattr(self, "space_build_total_seconds", 0.0)), 4),
            "space_build_session_seconds": round(float(getattr(self, "space_build_session_seconds", 0.0)), 4),
            "space_build_progress": round(float(getattr(self, "space_build_progress", 0.0)), 6),
            "space_build_progress_percent": round(float(getattr(self, "space_build_progress", 0.0)) * 100.0, 3),
            "space_build_visual_progress": round(float(self.visible_space_build_progress()), 6),
            "space_build_visual_node_count": len(getattr(self, "space_layer_build_nodes", []) or []),
            "space_build_session_count": int(getattr(self, "space_build_session_count", 0)),
            "space_build_last_saved_utc": str(getattr(self, "space_build_last_saved_utc", "") or ""),
            "runtime_debug_counts": self.runtime_debug_counts(),
            "projectile_caps": {"internal_world": MAX_INTERNAL_PROJECTILES, "weapon_shards": MAX_WEAPON_PROJECTILES},
            "actor_caps": {"world_actors": MAX_WORLD_ACTORS, "named_region_bots": MAX_NAMED_REGION_BOTS},
            "chunk_caps": {"terrain_chunks": MAX_BIOME_TERRAIN_CHUNKS, "metropolis_chunks": MAX_METROPOLIS_CHUNKS, "max_render_radius": MAX_TERRAIN_RENDER_RADIUS},
        }
        SELF_TEST_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if SELF_TEST_SCREENSHOT:
            try:
                shot = Path(str(SELF_TEST_SCREENSHOT)).expanduser().resolve()
                shot.parent.mkdir(parents=True, exist_ok=True)
                self.win.saveScreenshot(Filename.fromOsSpecific(str(shot)))
                report["self_test_screenshot"] = str(shot)
                SELF_TEST_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            except Exception as exc:
                report["self_test_screenshot_error"] = repr(exc)
                SELF_TEST_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if SELF_TEST:
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except Exception:
                pass
            os._exit(0)
        self.userExit()
        return Task.done

    def update_task(self, task):
        dt = min(0.033, globalClock.getDt())
        self.elapsed += dt
        instant_fps = (1.0 / dt) if dt > 1e-6 else 0.0
        instant_ms = dt * 1000.0
        if self.frame_fps <= 0.0:
            self.frame_fps = instant_fps
            self.frame_ms_smoothed = instant_ms
        else:
            blend = 0.08
            self.frame_fps += (instant_fps - self.frame_fps) * blend
            self.frame_ms_smoothed += (instant_ms - self.frame_ms_smoothed) * blend
        self.sanitize_runtime_config()
        self.update_player(dt)
        self.update_neon_city_state(dt)
        self.update_world_chunks()
        # Pass 91: retired metropolis fade task; structures are solid on build.
        self.update_metropolis_air_traffic(dt)
        self.update_urban_warzone(dt)
        self.update_deep_water_life(dt)
        self.update_salvage_population(dt)
        self.update_named_region_bots(dt)
        self.update_urban_conflict(dt)
        self.update_ice_life(dt)
        self.update_desert_life(dt)
        self.update_fungal_life(dt)
        self.update_dimension_gates(dt)
        self.update_day_night_sky(dt)
        if self.space_layer_factor() > 0.01:
            self.space_build_total_seconds += float(dt)
            self.space_build_session_seconds += float(dt)
            self.space_build_progress = self.compute_space_build_progress(self.space_build_total_seconds)
            self.save_space_build_progress(force=False)
        self.update_space_layer(dt)
        # Legacy separate artifact worlds / neon mode / actor combat are salvaged as local biome content now.
        # Avoid running their no-op update paths every frame.
        if getattr(self, "legacy_runtime_enabled", False):
            self.update_artifact_focus(dt)
            self.update_world_actors(dt)
            self.update_internal_modes(dt)
            self.update_weapon_viewmodels(dt, self.elapsed)
            self.update_shield(dt, self.elapsed)
        self.animate_accents(dt)
        # Pass 282.45: Panda text regeneration is not free.  Coordinates/FPS do
        # not need 60+ geometry rebuilds per second, while explicit menu/state
        # actions still call refresh_ui() immediately through their existing paths.
        next_ui = float(getattr(self, "_next_runtime_ui_refresh_elapsed", -1.0))
        if self.elapsed >= next_ui:
            self._next_runtime_ui_refresh_elapsed = self.elapsed + 0.10
            self.refresh_ui()
        if SELF_TEST:
            if not hasattr(self, "_self_test_wall_start"):
                self._self_test_wall_start = time.monotonic()
            wall_elapsed = time.monotonic() - self._self_test_wall_start
            stage = getattr(self, "_self_test_stage", 0)
            if stage == 0 and wall_elapsed >= 0.20:
                self._self_test_stage = 1
                self.self_test_setup(None)
            elif stage == 1 and wall_elapsed >= 0.90:
                self._self_test_stage = 2
            elif stage == 2 and wall_elapsed >= 1.25:
                self._self_test_stage = 3
                return self.self_test_exit(task)
        return Task.cont


def main():
    ensure_dirs()
    install_logging()
    if CRASH_LOG.exists():
        CRASH_LOG.unlink()
    install_crash_reporter()
    if not LATEST_PATCH.exists():
        write_patch_notes()
    print(f"Launching {GAME_NAME} {VERSION}")
    print(f"SELF_TEST={SELF_TEST}")
    app = CommandHubApp()
    app.run()


if __name__ == "__main__":
    main()
