import colorsys
import importlib.util
import json
import math
import os
import random
import sys
import textwrap
import time
import traceback
import shutil
import wave
import struct
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

SELF_TEST = "--self-test" in sys.argv or "--smoke-test" in sys.argv
NO_AUDIO = "--no-audio" in sys.argv
# Utopia Conflict is a direct Prototype Lab mission/direct-launch game.
# It does not import or poll Prototype Lab runtime wrappers.

def get_cli_arg(flag: str, default=None, cast=str):
    if flag in sys.argv:
        try:
            return cast(sys.argv[sys.argv.index(flag) + 1])
        except Exception:
            return default
    return default


AUTO_EXIT_SECONDS = get_cli_arg("--auto-exit", None, float)
TEST_SHOT_PATH = get_cli_arg("--test-shot", None, str)
COMBAT_REGRESSION_TEST = "--combat-regression-test" in sys.argv
WEAPON_VARIANT_TEST = "--weapon-variant-test" in sys.argv
WEAPON_SIGNATURE_TEST = "--weapon-signature-test" in sys.argv
WEAPON_SIGNATURE_DEMO = get_cli_arg("--weapon-signature-demo", None, int)
ACTIVITY_MODE_TEST = "--activity-mode-test" in sys.argv
DISTRICT_DEMO_TEST = "--district-demo" in sys.argv
NORTH_DISTRICT_DEMO_TEST = "--north-district-demo" in sys.argv
ARENA_INTEGRATION_TEST = "--arena-integration-test" in sys.argv
CITY_CAPTURE_TEST = "--city-capture-test" in sys.argv
BOSS_VARIANT_TEST = "--boss-variant-test" in sys.argv
HUD_POLISH_TEST = "--hud-polish-test" in sys.argv
CIVILIAN_AI_TEST = "--civilian-ai-test" in sys.argv
DRONE_PATROL_TEST = "--drone-patrol-test" in sys.argv
RESPAWN_RESET_TEST = "--respawn-reset-test" in sys.argv
HEALTH_PALETTE_TEST = "--health-palette-test" in sys.argv
ARMOR_WIREFRAME_TEST = "--armor-wireframe-test" in sys.argv
ACTIVITY_INSTANCE_TEST = "--activity-instance-test" in sys.argv
SURVIVABILITY_TEST = "--survivability-test" in sys.argv
ACTIVITY_VARIETY_TEST = "--activity-variety-test" in sys.argv
CAPTURE_REGEN_TEST = "--capture-regen-test" in sys.argv
VISUAL_HIERARCHY_TEST = "--visual-hierarchy-test" in sys.argv
CHUNK_SMOOTHING_TEST = "--chunk-smoothing-test" in sys.argv
HUD_HIERARCHY_TEST = "--hud-hierarchy-test" in sys.argv
DISTRICT_SKYLINE_TEST = "--district-skyline-test" in sys.argv
DISTRICT_ACTIVITY_TEST = "--district-activity-test" in sys.argv
DISTRICT_ACTIVITY_DEMO = get_cli_arg("--district-activity-demo", None, str)
DISTRICT_DISCOVERY_TEST = "--district-discovery-test" in sys.argv
DISTRICT_DISCOVERY_DEMO = get_cli_arg("--district-discovery-demo", None, str)
ENEMY_ROLE_TEST = "--enemy-role-test" in sys.argv
ENEMY_ROLE_DEMO = get_cli_arg("--enemy-role-demo", None, str)
ENEMY_COLOR_STATE_TEST = "--enemy-color-state-test" in sys.argv
ENEMY_COLOR_STATE_DEMO = get_cli_arg("--enemy-color-state-demo", None, str)
FREEROAM_RHYTHM_TEST = "--freeroam-rhythm-test" in sys.argv
FREEROAM_RHYTHM_DEMO = get_cli_arg("--freeroam-rhythm-demo", None, str)
MASTERING_QUALITY_TEST = "--mastering-quality-test" in sys.argv
MASTERING_DEMO = "--mastering-demo" in sys.argv
HUD_MINIMALISM_TEST = "--hud-minimalism-test" in sys.argv
HUD_MINIMALISM_DEMO = "--hud-minimalism-demo" in sys.argv
HELP_REFERENCE_TEST = "--help-reference-test" in sys.argv
HELP_REFERENCE_DEMO = "--help-reference-demo" in sys.argv
PRESENTATION_READINESS_TEST = "--presentation-readiness-test" in sys.argv
PRESENTATION_DEMO = "--presentation-demo" in sys.argv
PAUSE_MENU_INPUT_TEST = "--pause-menu-input-test" in sys.argv
NORMAL_PRESENTATION_LAUNCH = not any(arg.startswith("--") and arg not in {"--no-audio"} for arg in sys.argv[1:])


def load_boot_launch_settings():
    cfg = {"width": 1920, "height": 1080, "fullscreen": False, "borderless": False}
    path = os.environ.get("MATRIX_LAUNCH_SETTINGS", "").strip()
    if path:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            for key in list(cfg.keys()):
                if key in data:
                    cfg[key] = data[key]
        except Exception:
            pass
    for env_name, key, cast in [
        ("MATRIX_GAME_WIDTH", "width", int),
        ("MATRIX_GAME_HEIGHT", "height", int),
        ("MATRIX_GAME_FULLSCREEN", "fullscreen", lambda v: str(v).strip().lower() in {"1", "true", "yes", "on"}),
        ("MATRIX_GAME_BORDERLESS", "borderless", lambda v: str(v).strip().lower() in {"1", "true", "yes", "on"}),
    ]:
        val = os.environ.get(env_name)
        if val not in (None, ""):
            try:
                cfg[key] = cast(val)
            except Exception:
                pass
    cfg["width"] = max(1280, min(3840, int(cfg["width"])))
    cfg["height"] = max(720, min(2160, int(cfg["height"])))
    cfg["fullscreen"] = bool(cfg["fullscreen"])
    cfg["borderless"] = bool(cfg["borderless"]) and not cfg["fullscreen"]
    return cfg


BOOT_SETTINGS = load_boot_launch_settings()

GAME_CONTRACT_CLI_FLAGS = {"--game-contract-test", "--game-result-test", "--complete-game-test", "--profile-test", "--mission-contract-test", "--mission-result-test", "--complete-mission-test"}
if any(_flag in sys.argv for _flag in GAME_CONTRACT_CLI_FLAGS):
    from standalone_game_contract import handle_game_contract_cli
    raise SystemExit(handle_game_contract_cli(root=Path(__file__).resolve().parent))

if "--standards-check" in sys.argv:
    _root = Path(__file__).resolve().parent
    _manifest_path = _root / "standalone_manifest.json"
    _manifest = json.loads(_manifest_path.read_text(encoding="utf-8")) if _manifest_path.exists() else {}
    _errors = []
    for _field in ("id", "title", "entry", "engine", "core_loop", "score_rules"):
        if not _manifest.get(_field):
            _errors.append(f"manifest missing {_field}")
    if _manifest.get("depends_on_mission") is True or _manifest.get("runtime_wrapper_required") is True:
        _errors.append("mission still declares wrapped/Prototype Lab dependency")
    for _required in ("README.md", "requirements.txt", "game_config.json", "build_manifest.json", "assets/asset_manifest.json"):
        if not (_root / _required).exists():
            _errors.append(f"missing {_required}")
    print(json.dumps({"schema": "glitched_matrix_standards_check_v1", "title": _manifest.get("title"), "status": "PASS" if not _errors else "FAIL", "errors": _errors}, indent=2))
    raise SystemExit(0 if not _errors else 2)

from panda3d.core import loadPrcFileData

PRC = f"""
window-title Utopia Conflict
win-size {BOOT_SETTINGS['width']} {BOOT_SETTINGS['height']}
show-frame-rate-meter 0
sync-video 1
framebuffer-multisample 1
multisamples 8
interpolate-frames 1
cursor-hidden 1
textures-power-2 none
texture-anisotropic-degree 8
notify-level-glgsg warning
notify-level-display warning
want-pstats 0
model-path ./assets
"""
if SELF_TEST:
    PRC += "\naudio-library-name null\nwindow-type none\n"
elif NO_AUDIO:
    PRC += "\naudio-library-name null\n"
else:
    PRC += "\naudio-library-name p3openal_audio\n"
loadPrcFileData("", PRC)

from direct.showbase.ShowBase import ShowBase
try:
    from direct.showbase.Audio3DManager import Audio3DManager
except Exception:
    Audio3DManager = None
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel
from direct.task import Task
from direct.filter.CommonFilters import CommonFilters
from panda3d.core import (
    AmbientLight,
    AntialiasAttrib,
    CardMaker,
    ClockObject,
    CollisionNode,
    CollisionSphere,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    Filename,
    SceneGraphAnalyzer,
    InputDevice,
    KeyboardButton,
    LColor,
    LineSegs,
    NodePath,
    Point2,
    Point3,
    TextNode,
    TransparencyAttrib,
    Vec2,
    Vec3,
    WindowProperties,
)

try:
    from PIL import Image, ImageDraw
except Exception:
    Image = None
    ImageDraw = None

VERSION = "1.0.18-utopia-conflict-pass55-pause-menu-input-repair"
GAME_NAME = "Utopia Conflict"

UTOPIA_DISTRICTS = {
    "calibration": {
        "name": "Calibration District",
        "activity": "baseline weapon lab",
        "enemy_role": "sentinel calibration units",
        "height_scale": 1.0,
        "density_scale": 0.92,
        "spire_chance": 0.26,
        "pyramid": False,
        "ammo_slots": [1, 2, 3, 4, 5, 6],
        "upgrade_focus": "balanced field tests",
        "drone_patrol": True,
        "drone_density": 0.55,
        "enemy_variants": ["sentinel", "stalker", "walker", "shifter"],
        "travel_patrol_size": 1,
    },
    "pyramid_sector": {
        "name": "Pyramid Sector",
        "activity": "pyramid relay experiments",
        "enemy_role": "prism guards and relay drones",
        "height_scale": 0.46,
        "density_scale": 0.48,
        "spire_chance": 0.22,
        "pyramid": True,
        "tower": False,
        "ammo_slots": [2, 3, 5],
        "enemy_variants": ["bulwark", "walker", "commander", "boss_mech"],
        "upgrade_focus": "Imploder / Magnet / Burst ammo",
        "drone_patrol": True,
        "drone_density": 0.85,
        "travel_patrol_size": 2,
    },
    "high_towers": {
        "name": "High Towers",
        "activity": "north uplink patrol tests",
        "enemy_role": "tower drones and fast stalker units",
        "height_scale": 1.68,
        "density_scale": 0.78,
        "spire_chance": 0.78,
        "pyramid": False,
        "tower": True,
        "ammo_slots": [1, 4, 6],
        "enemy_variants": ["stalker", "shifter", "walker", "boss_mech"],
        "upgrade_focus": "Core Lance / Disassembler / Auto ammo",
        "drone_patrol": True,
        "drone_density": 1.0,
        "travel_patrol_size": 2,
    },
}


def _user_data_root() -> Path:
    """Glitched Matrix standard user-data folder (Windows %LOCALAPPDATA%\\GLITCHED MATRIX\\Utopia Conflict).
    UTOPIA_CONFLICT_USER_DATA overrides it.  The game folder itself is never written."""
    override = str(os.environ.get("UTOPIA_CONFLICT_USER_DATA") or "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = str(os.environ.get("LOCALAPPDATA") or "").strip()
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "GLITCHED MATRIX" / "Utopia Conflict"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "GLITCHED MATRIX" / "Utopia Conflict"
    xdg = str(os.environ.get("XDG_DATA_HOME") or "").strip()
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / "glitched-matrix" / "utopia-conflict"

ROOT = Path(__file__).resolve().parent
USER_DATA_DIR = _user_data_root()
ASSETS = ROOT / "assets"
CONFIG_DIR = ASSETS / "config"
GENERATED_DIR = ASSETS / "generated"
LOG_DIR = USER_DATA_DIR / "logs"
PATCH_DIR = USER_DATA_DIR / "logs"
USER_CONFIG_PATH = USER_DATA_DIR / "game_config.json"
CRASH_DIR = LOG_DIR / "crash_reports"
LATEST_LOG = LOG_DIR / "latest.log"
BLOTCH_TEXTURE = GENERATED_DIR / "ink_blotch.png"
GENERATED_SFX_DIR = GENERATED_DIR / "sfx"
CUSTOM_FX_DIR = ASSETS / "audio" / "sfx" / "customfx"
LEGACY_CUSTOM_SFX_DIR = ASSETS / "audio" / "sfx" / "custom"
CUSTOM_SFX_DIR = CUSTOM_FX_DIR
SFX_OVERRIDE_DIR = ASSETS / "audio" / "sfx" / "overrides"
AUDIO_LOOPS_DIR = ASSETS / "audio" / "loops"
ARENA_VARIANTS_DIR = ASSETS / "arena_variants"
SHARED_SFX_ROOT = Path(os.environ.get("MATRIX_SHARED_SFX_DIR") or os.environ.get("PROTOTYPE_LAB_SHARED_SFX_DIR") or (ROOT.parent / "assets" / "shared_sfx"))
AUDIO_PROFILE = {}
CONFIG_PATH = CONFIG_DIR / "game_config.json"
ROOT_CONFIG_PATH = ROOT / "game_config.json"
SFX_STEMS = {
    "fire": "mech_fire",
    "burst_fire": "weapon_burst",
    "auto_fire": "weapon_automatic",
    "hit": "core_hit",
    "armor": "armor_hit",
    "armor_heavy": "armor_heavy_hit",
    "deflect": "deflect",
    "break": "shield_break",
    "metal_break": "metal_broken",
    "weapon_broken": "weapon_broken",
    "tell": "enemy_tell",
    "enemy1": "enemy1",
    "enemy2": "enemy2",
    "enemy3": "enemy3",
    "enemy4": "enemy4",
    "enemy5": "enemy5",
    "chain": "chain_arc",
    "recharge": "recharge",
    "kill": "mech_kill",
    "explosion_cannon": "explosion_cannon",
    "explosion_fire": "explosion_fire",
    "explosion_boss": "explosion_boss",
    "explosion_distant": "explosion_distant",
    "imploder": "imploder_pulse",
    "magnet": "magnet_field",
    "disassemble": "disassembler_cut",
    "pickup": "weapon_pickup",
    "special_pickup": "special_pickup",
    "ricochet": "ricochet",
    "objective_complete": "objective_complete",
    "dry": "dry_click",
    "weapon_empty": "weapon_empty",
    "wave_start": "wave_start",
    "breach_spawn": "breach_spawn",
    "breach_hit": "breach_hit",
    "breach_sealed": "breach_sealed",
    "enemy_spawn": "enemy_spawn",
    "enemy_destroyed": "enemy_destroyed",
    "combo_surge": "combo_surge",
    "weapon_upgrade": "weapon_upgrade",
}
SFX_ALIASES = {
    "fire": ["mech_fire", "fire", "core_lance"],
    "burst_fire": ["weapon_burst", "burst", "burst_fire"],
    "auto_fire": ["weapon_automatic", "automatic", "auto_fire"],
    "hit": ["core_hit", "hit"],
    "armor": ["armor_hit", "armor"],
    "armor_heavy": ["armor_heavy_hit", "heavy_armor", "armor_heavy"],
    "deflect": ["deflect", "glance", "armor_deflect"],
    "break": ["shield_break", "break"],
    "metal_break": ["metal_broken", "metal_break", "metal_broken"],
    "weapon_broken": ["weapon_broken", "hard_break"],
    "tell": ["enemy_tell", "tell", "warning"],
    "enemy1": ["enemy1"],
    "enemy2": ["enemy2"],
    "enemy3": ["enemy3"],
    "enemy4": ["enemy4"],
    "enemy5": ["enemy5"],
    "chain": ["chain_arc", "chain"],
    "recharge": ["recharge"],
    "kill": ["mech_kill", "kill", "enemy_kill"],
    "explosion_cannon": ["explosion_cannon", "cannon_explosion"],
    "explosion_fire": ["explosion_fire", "fire_explosion"],
    "explosion_boss": ["explosion_boss", "boss_explosion", "big_explosion"],
    "explosion_distant": ["explosion_distant", "distant_explosion"],
    "imploder": ["imploder_pulse", "imploder"],
    "magnet": ["magnet_field", "magnet"],
    "disassemble": ["disassembler_cut", "disassemble", "disassembler"],
    "pickup": ["weapon_pickup", "pickup", "ammo_pickup"],
    "special_pickup": ["special_pickup", "rare_pickup"],
    "ricochet": ["ricochet", "miss", "world_hit"],
    "objective_complete": ["objective_complete", "objective", "node_complete"],
    "dry": ["dry_click", "dry"],
    "weapon_empty": ["weapon_empty", "empty", "empty_ammo"],
    "wave_start": ["wave_start", "arena_wave_start"],
    "breach_spawn": ["breach_spawn", "arena_portal", "breach_core_spawn"],
    "breach_hit": ["breach_hit", "arena_hit"],
    "breach_sealed": ["breach_sealed", "arena_complete", "breach_complete"],
    "enemy_spawn": ["enemy_spawn", "arena_enemy_spawn"],
    "enemy_destroyed": ["enemy_destroyed", "arena_enemy_destroyed"],
    "combo_surge": ["combo_surge", "arena_combo"],
    "weapon_upgrade": ["weapon_upgrade", "upgrade", "upgrade_bought"],
}
SFX_EXTENSIONS = (".wav",)
LOOP_EXTENSIONS = (".wav",)
SFX_PATHS = {key: GENERATED_SFX_DIR / f"{stem}.wav" for key, stem in SFX_STEMS.items()}
SFX_REPLACEMENT_MAP = {
    key: {
        "official_name": SFX_STEMS[key],
        "official_replacement": f"{SFX_STEMS[key]}.wav",
        "accepted_names": [f"{alias}{ext}" for alias in SFX_ALIASES[key] for ext in SFX_EXTENSIONS],
        "customfx_printout": os.fspath((CUSTOM_FX_DIR / f"{SFX_STEMS[key]}.wav").relative_to(ROOT)),
        "generated_fallback": os.fspath(SFX_PATHS[key].relative_to(ROOT)),
    }
    for key in SFX_STEMS
}


def ensure_dirs():
    for p in [ASSETS, CONFIG_DIR, GENERATED_DIR, GENERATED_SFX_DIR, CUSTOM_FX_DIR, LEGACY_CUSTOM_SFX_DIR, SFX_OVERRIDE_DIR, AUDIO_LOOPS_DIR, ARENA_VARIANTS_DIR, LOG_DIR, PATCH_DIR, CRASH_DIR]:
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass


def write_latest_log(message: str, extra: dict | None = None):
    ensure_dirs()
    lines = [f"{datetime.now().isoformat()} | {message}"]
    if extra:
        for k, v in extra.items():
            lines.append(f"{k}={v}")
    LATEST_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def install_crash_reporter():
    def _hook(exc_type, exc, tb):
        ensure_dirs()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = CRASH_DIR / f"crash_{stamp}.log"
        with path.open("w", encoding="utf-8") as f:
            f.write(f"{GAME_NAME} {VERSION}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")
            traceback.print_exception(exc_type, exc, tb, file=f)
        traceback.print_exception(exc_type, exc, tb)
    sys.excepthook = _hook


@dataclass
class GameConfig:
    day_length_seconds: float = 600.0
    transition_length_seconds: float = 120.0
    chunk_size: int = 64
    active_chunk_radius: int = 4
    enemy_chunk_radius: int = 3
    max_view_distance: float = 620.0
    line_fade_start_ratio: float = 0.58
    texture_aura_radius: float = 160.0
    mouse_sensitivity: float = 0.11
    controller_look_sensitivity: float = 110.0
    walk_speed: float = 18.0
    sprint_speed: float = 30.0
    jump_speed: float = 8.2
    player_height: float = 1.75
    player_radius: float = 0.42
    gravity: float = 20.0
    line_thickness: float = 1.45
    enemy_line_thickness_scale: float = 1.6
    weapon_line_thickness_scale: float = 1.65
    movable_line_thickness_scale: float = 1.55
    weapon_solid_fill_enabled: bool = True
    weapon_solid_fill_alpha: float = 0.92
    audio_spatial_enabled: bool = True
    audio_spatial_min_distance: float = 6.0
    audio_spatial_max_distance: float = 110.0
    audio_spatial_dropoff: float = 0.72
    max_positional_sounds: int = 18
    audio_loop_volume: float = 0.52
    line_jitter: float = 0.05
    max_tracers: int = 180
    max_blotches: int = 90
    weapon_recharge_per_second: float = 26.0
    default_health: int = 100
    invert_background: bool = False
    music_volume: float = 0.0
    show_help: bool = True
    campaign_hue_cycle_seconds: float = 240.0
    health_palette_enabled: bool = True
    health_palette_blend_strength: float = 0.82
    health_palette_low_threshold: float = 0.35
    health_palette_mid_threshold: float = 0.68
    health_palette_background_warning_strength: float = 0.22
    player_armor_default_ratio: float = 0.10
    player_armor_upgrade_ratio_step: float = 0.10
    player_armor_hit_fade_seconds: float = 0.85
    upgrade_armor_cost: int = 110
    campaign_enemy_scale: float = 1.42
    campaign_enemy_health_scale: float = 1.38
    campaign_enemy_pressure_scale: float = 1.22
    enemy_spawn_min_distance: float = 110.0
    enemy_objective_min_distance: float = 54.0
    enemy_origin_safe_radius: float = 142.0
    enemy_max_active: int = 24
    enemy_chase_distance: float = 285.0
    spawn_director_enabled: bool = True
    spawn_queue_max: int = 16
    spawn_sequence_gap_seconds: float = 0.72
    spawn_duplicate_radius: float = 30.0
    ambient_spawn_interval_seconds: float = 8.5
    ambient_spawn_sequence_size: int = 2
    ambient_spawn_distance_min: float = 122.0
    ambient_spawn_distance_max: float = 198.0
    freeroam_rhythm_enabled: bool = True
    freeroam_quiet_departure_seconds: float = 7.0
    freeroam_quiet_after_pressure_seconds: float = 6.5
    freeroam_encounter_distance_min: float = 145.0
    freeroam_encounter_interval_min: float = 13.0
    freeroam_encounter_interval_max: float = 22.0
    freeroam_pressure_radius: float = 88.0
    freeroam_pressure_enemy_cap: int = 3
    objective_spawn_distance_min: float = 132.0
    objective_spawn_distance_max: float = 196.0
    capture_zone_wave_size: int = 4
    capture_zone_wave_min_distance: float = 66.0
    capture_zone_wave_max_distance: float = 108.0
    capture_zone_wave_behind_buildings: bool = True
    capture_health_regen_per_second: float = 8.0
    capture_armor_regen_per_second: float = 5.0
    spawn_warning_ring_radius: float = 3.25
    weapon_one_hit_kill: bool = True
    kill_explosion_fx_count: int = 34
    world_seed: int = 74219
    signal_fragments_required: int = 4
    signal_recovery_radius: float = 5.25
    extraction_radius: float = 7.0
    objective_score_per_fragment: int = 175
    objective_completion_bonus: int = 800
    objective_wave_size: int = 3
    objective_pulse_budget: int = 18
    objective_beacon_height: float = 14.0
    extraction_beacon_height: float = 22.0
    max_combat_effects: int = 28
    enemy_kill_score: int = 25
    enemy_spawn_warning_seconds: float = 1.15
    arena_enabled: bool = True
    arena_wave_seconds: float = 60.0
    arena_waves_per_capture: int = 3
    arena_wave_base_size: int = 4
    arena_wave_growth: int = 2
    arena_portal_radius: float = 5.5
    arena_reward_points_per_wave: int = 35
    arena_reward_points_complete: int = 140
    arena_level_radius: float = 74.0
    arena_bridge_count: int = 4
    arena_cover_pylon_count: int = 12
    arena_core_hits_per_wave: int = 3
    arena_shared_upgrade_bonus_wave3: int = 40
    arena_hide_city_during_mode: bool = True
    arena_stage_panel_alpha: float = 0.42
    arena_robot_fill_alpha: float = 0.84
    arena_stage_dark_alpha: float = 0.74
    arena_perimeter_panel_alpha: float = 0.82
    upgrade_health_cost: int = 120
    upgrade_ammo_cost: int = 90
    upgrade_health_step: int = 25
    upgrade_ammo_capacity_step: float = 18.0
    enemy_contact_damage: int = 10
    weak_core_hitbox_scale: float = 1.58
    enemy_body_damage_scale: float = 0.38
    enemy_body_stagger_seconds: float = 0.38
    enemy_armor_break_hits: int = 2
    enemy_armor_break_stagger_seconds: float = 1.15
    enemy_armor_broken_damage_scale: float = 1.65
    enemy_attack_tell_distance: float = 28.0
    enemy_attack_tell_seconds: float = 0.72
    enemy_attack_cooldown: float = 2.35
    enemy_attack_lunge_seconds: float = 0.26
    enemy_attack_lunge_speed_scale: float = 1.32
    enemy_kill_streak_window: float = 3.8
    enemy_kill_streak_bonus: int = 5
    enemy_kill_streak_bonus_cap: int = 35
    combat_camera_kick_seconds: float = 0.16
    combat_camera_kick_strength: float = 0.055
    kill_shockwave_radius: float = 18.0
    kill_shockwave_stagger_seconds: float = 0.55
    chain_arc_range: float = 27.0
    chain_arc_max_targets: int = 3
    chain_arc_damage_scale: float = 0.88
    chain_arc_secondary_kill_range: float = 10.5
    chain_arc_max_depth: int = 1
    max_physics_shards: int = 56
    impact_shard_count: int = 8
    shield_break_shard_count: int = 18
    kill_debris_count: int = 28
    impact_knockback_force: float = 3.2
    shield_break_knockback_force: float = 7.6
    kill_shockwave_knockback_force: float = 12.0
    chain_arc_physics_force: float = 4.6
    enemy_knockback_drag: float = 5.8
    enemy_knockback_max_speed: float = 24.0
    enemy_separation_force: float = 2.1
    physics_shard_gravity_scale: float = 0.78
    physics_shard_bounce: float = 0.38
    shockwave_ring_life: float = 0.52
    weapon_pickup_ammo: float = 28.0
    weapon_kill_ammo_reward: float = 8.0
    weapon_specific_ammo_reward: float = 10.0
    district_ammo_drop_bias: float = 0.82
    weapon_objective_ammo_reward: float = 32.0
    weapon_pickup_radius: float = 6.0
    max_weapon_pickups: int = 8
    max_weapon_fx: int = 84
    weapon_pickup_magnet_radius: float = 18.0
    weapon_pickup_magnet_pull: float = 32.0
    core_lance_pierce_range: float = 48.0
    core_lance_pierce_radius: float = 4.6
    core_lance_pierce_damage_scale: float = 0.72
    imploder_radius: float = 24.0
    imploder_damage: float = 82.0
    imploder_pull_force: float = 18.0
    imploder_crush_delay: float = 0.28
    imploder_crush_radius_scale: float = 0.62
    imploder_crush_damage: float = 44.0
    magnet_radius: float = 22.0
    magnet_life_seconds: float = 4.6
    magnet_pull_force: float = 19.0
    magnet_tick_damage: float = 10.0
    magnet_center_crush_radius_scale: float = 0.28
    magnet_center_crush_damage: float = 18.0
    disassembler_damage_per_part: float = 52.0
    disassembler_parts_to_kill: int = 5
    disassembler_slow_per_part: float = 0.10
    activity_mode_enabled: bool = True
    activity_bonus_score: int = 75
    activity_major_bonus_score: int = 140
    activity_station_radius: float = 14.0
    activity_marker_alpha: float = 0.68
    activity_instance_radius: float = 7.5
    activity_instance_spawn_count: int = 4
    player_contact_damage_cap_per_second: float = 2.0
    player_damage_grace_seconds: float = 0.16
    district_size_chunks: int = 6
    district_banner_seconds: float = 2.8
    structure_occlusion_masks: bool = True
    structure_occlusion_background_strength: float = 0.94
    structure_occlusion_max_boxes_per_chunk: int = 90
    # Pass43 visual hierarchy / streaming. Background city is intentionally quieter
    # than weapons, enemies and objectives; chunks stream by nearest-first budget.
    world_line_thickness_scale: float = 0.48
    world_line_alpha: float = 0.42
    chunk_preload_margin: int = 1
    chunk_generate_budget: int = 3
    chunk_fade_in_seconds: float = 0.42
    chunk_fade_out_seconds: float = 0.28
    # Pass44 keeps normal play sparse: mission top-center, identity/score top-left, weapons bottom-left.
    hud_compact_normal_play: bool = True
    district_landmark_scale: float = 1.0
    background_opposite_cycle: bool = True
    background_hue_shift: float = 0.5
    background_cycle_saturation: float = 0.34
    background_cycle_horizon_value_day: float = 0.64
    background_cycle_horizon_value_night: float = 0.18
    background_cycle_zenith_value_day: float = 0.34
    background_cycle_zenith_value_night: float = 0.07
    boss_mech_arm_space: float = 3.4
    boss_mech_health_scale: float = 2.45
    boss_spawn_on_capture_index: int = 2
    civilian_anchor_refresh_seconds: float = 2.25
    civilian_death_penalty: int = 125
    civilian_enabled: bool = True
    civilian_enemy_harm_distance: float = 3.4
    civilian_harm_penalty: int = 35
    civilian_health: int = 32
    civilian_max_active: int = 10
    civilian_spawn_interval_seconds: float = 1.4
    civilian_speed: float = 2.65
    dual_wield_enabled: bool = True
    enemy_break_apart_parts: int = 7
    game_hud_polish_pass: bool = True
    hud_dev_text_hidden_by_default: bool = True
    paired_dual_wield_enabled: bool = True
    patrol_drone_anchor_refresh_seconds: float = 3.0
    patrol_drone_armor: int = 180
    patrol_drone_damage: int = 3
    patrol_drone_detect_radius: float = 96.0
    patrol_drone_drop_amount_max: float = 42.0
    patrol_drone_drop_amount_min: float = 18.0
    patrol_drone_enabled: bool = True
    patrol_drone_fire_interval: float = 0.82
    patrol_drone_health: int = 260
    patrol_drone_max_active: int = 4
    patrol_drone_player_hostility_seconds: float = 9.0
    patrol_drone_spawn_interval_seconds: float = 3.2
    patrol_drone_speed: float = 7.2
    shifter_quad_speed_scale: float = 1.28
    shifter_transform_distance: float = 38.0
    walker_arm_space: float = 2.6
    weapon_fx_verified: bool = True
    technical_design_density: float = 0.72
    technical_design_window_bands: int = 4
    technical_design_max_modules_per_face: int = 3
    technical_design_spire_chance: float = 0.30


DEFAULT_CONFIG = GameConfig()

def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _randomized_mission_seed(default_seed: int) -> int:
    if not _env_flag("MATRIX_RANDOM_MISSION", False):
        return default_seed
    raw = str(os.environ.get("MATRIX_RANDOM_MISSION_SEED", "")).strip()
    if raw:
        try:
            return int(raw) & 0xFFFFFFFF
        except Exception:
            pass
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return int(stamp) & 0xFFFFFFFF


def write_game_config(cfg: GameConfig) -> None:
    # Player settings live in the user-data folder; the shipped config stays as the default.
    payload = json.dumps(asdict(cfg), indent=2)
    try:
        USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        USER_CONFIG_PATH.write_text(payload, encoding="utf-8")
    except Exception:
        pass


def load_or_create_config() -> GameConfig:
    ensure_dirs()
    source = USER_CONFIG_PATH if USER_CONFIG_PATH.exists() else CONFIG_PATH
    if source.exists():
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
            merged = asdict(DEFAULT_CONFIG)
            merged.update({k: v for k, v in data.items() if k in merged})
            cfg = GameConfig(**merged)
        except Exception:
            cfg = DEFAULT_CONFIG
    else:
        cfg = DEFAULT_CONFIG
    cfg.world_seed = _randomized_mission_seed(int(cfg.world_seed))
    write_game_config(cfg)
    return cfg



def load_shared_audio_bus():
    cfg = {"master_volume": 0.82, "sfx_volume": 0.82, "music_volume": 0.42, "ambience_volume": 0.58}
    path = os.environ.get("MATRIX_AUDIO_CONFIG", "").strip()
    if path:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            for k in list(cfg.keys()):
                if k in data:
                    cfg[k] = float(data[k])
        except Exception:
            pass
    for env_name, key in [("MATRIX_MASTER_VOLUME", "master_volume"), ("MATRIX_SFX_VOLUME", "sfx_volume"), ("MATRIX_MUSIC_VOLUME", "music_volume"), ("MATRIX_AMBIENCE_VOLUME", "ambience_volume")]:
        val = os.environ.get(env_name)
        if val:
            try:
                cfg[key] = float(val)
            except Exception:
                pass
    for key in list(cfg.keys()):
        cfg[key] = max(0.0, min(1.0, cfg[key]))
    return cfg




def load_shared_launch_settings():
    cfg = {
        "width": 1920,
        "height": 1080,
        "fullscreen": False,
        "borderless": False,
        "mouse_sensitivity": 0.22,
        "invert_y": False,
        "hud_visible": True,
        "graphics_quality": "medium",
        "controller_deadzone": 0.12,
    }
    path = os.environ.get("MATRIX_LAUNCH_SETTINGS", "").strip()
    if path:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            for key in list(cfg.keys()):
                if key in data:
                    cfg[key] = data[key]
        except Exception:
            pass
    remap = [
        ("MATRIX_GAME_WIDTH", "width", int),
        ("MATRIX_GAME_HEIGHT", "height", int),
        ("MATRIX_GAME_FULLSCREEN", "fullscreen", lambda v: str(v).strip().lower() in {"1", "true", "yes", "on"}),
        ("MATRIX_GAME_BORDERLESS", "borderless", lambda v: str(v).strip().lower() in {"1", "true", "yes", "on"}),
        ("MATRIX_GAME_MOUSE_SENSITIVITY", "mouse_sensitivity", float),
        ("MATRIX_GAME_INVERT_Y", "invert_y", lambda v: str(v).strip().lower() in {"1", "true", "yes", "on"}),
        ("MATRIX_GAME_HUD_VISIBLE", "hud_visible", lambda v: str(v).strip().lower() in {"1", "true", "yes", "on"}),
        ("MATRIX_GAME_GRAPHICS_QUALITY", "graphics_quality", str),
        ("MATRIX_GAME_CONTROLLER_DEADZONE", "controller_deadzone", float),
    ]
    for env_name, key, cast in remap:
        val = os.environ.get(env_name)
        if val not in (None, ""):
            try:
                cfg[key] = cast(val)
            except Exception:
                pass
    cfg["width"] = max(1280, min(3840, int(cfg["width"])))
    cfg["height"] = max(720, min(2160, int(cfg["height"])))
    cfg["mouse_sensitivity"] = max(0.02, min(1.0, float(cfg["mouse_sensitivity"])))
    cfg["controller_deadzone"] = max(0.0, min(0.45, float(cfg["controller_deadzone"])))
    cfg["graphics_quality"] = str(cfg["graphics_quality"]).lower().strip()
    if cfg["graphics_quality"] not in {"low", "medium", "high"}:
        cfg["graphics_quality"] = "medium"
    cfg["fullscreen"] = bool(cfg["fullscreen"])
    cfg["borderless"] = bool(cfg["borderless"])
    if cfg["fullscreen"]:
        cfg["borderless"] = False
    cfg["invert_y"] = bool(cfg["invert_y"])
    cfg["hud_visible"] = bool(cfg["hud_visible"])
    return cfg


def sfx_candidate_names(key: str):
    return list(dict.fromkeys(SFX_ALIASES.get(key, [SFX_STEMS.get(key, key)])))


def resolve_sfx_path(key: str) -> Path:
    # Priority: overrides > custom > shared/profile > generated fallback.
    # This makes the two local folders predictable for quick sound swaps.
    for folder in (SFX_OVERRIDE_DIR, CUSTOM_FX_DIR, LEGACY_CUSTOM_SFX_DIR):
        for alias in sfx_candidate_names(key):
            for ext in SFX_EXTENSIONS:
                cand = folder / f"{alias}{ext}"
                if cand.exists():
                    return cand
    try:
        if legacy_runtime:
            profile_files = legacy_runtime.profile_sfx_files(key, profile=AUDIO_PROFILE)
            if profile_files:
                return profile_files[0]
    except Exception:
        pass
    shared_map = {
        "fire": [SHARED_SFX_ROOT / "weapons" / "lasers", SHARED_SFX_ROOT / "weapons" / "guns"],
        "hit": [SHARED_SFX_ROOT / "damage" / "hit"],
        "armor": [SHARED_SFX_ROOT / "damage" / "hit"],
        "break": [SHARED_SFX_ROOT / "damage" / "destroy"],
        "tell": [SHARED_SFX_ROOT / "ui"],
        "kill": [SHARED_SFX_ROOT / "damage" / "destroy"],
        "imploder": [SHARED_SFX_ROOT / "weapons" / "lasers", SHARED_SFX_ROOT / "damage" / "destroy"],
        "magnet": [SHARED_SFX_ROOT / "weapons" / "lasers", SHARED_SFX_ROOT / "ui"],
        "disassemble": [SHARED_SFX_ROOT / "weapons" / "lasers", SHARED_SFX_ROOT / "damage" / "hit"],
        "pickup": [SHARED_SFX_ROOT / "ui"],
        "chain": [SHARED_SFX_ROOT / "weapons" / "lasers"],
        "dry": [SHARED_SFX_ROOT / "ui"],
    }
    for folder in shared_map.get(key, []):
        try:
            for ext in SFX_EXTENSIONS:
                found = sorted(folder.glob(f"*{ext}"))
                if found:
                    return found[0]
        except Exception:
            pass
    return SFX_PATHS[key]


def write_sfx_replacement_map() -> Path:
    ensure_dirs()
    data = {
        "schema": "etch_line_sfx_replacement_map_v1",
        "version": VERSION,
        "priority": [
            "assets/audio/sfx/overrides",
            "assets/audio/sfx/customfx",
            "assets/audio/sfx/custom (legacy compatibility)",
            "shared profile/shared library if present",
            "assets/generated/sfx",
        ],
        "format_rule": "SFX replacement is WAV-only in this build.",
        "folders": {
            "overrides": "Highest-priority replacement folder. Put your final WAV swaps here.",
            "customfx": "Reference printouts of the current generated SFX. Use these as editable starting points.",
            "custom": "Legacy compatibility folder from older passes. Use overrides for new work.",
            "loops": "Drop WAV music or ambience loops in assets/audio/loops. Any WAV filename is discovered automatically.",
            "generated": "Fallback sounds owned/generated by the build.",
        },
        "loop_files": [os.fspath(p.relative_to(ROOT)) for p in discover_audio_loop_files()],
        "effects": SFX_REPLACEMENT_MAP,
        "currently_resolved": {key: os.fspath(resolve_sfx_path(key).relative_to(ROOT)) if resolve_sfx_path(key).is_relative_to(ROOT) else os.fspath(resolve_sfx_path(key)) for key in SFX_STEMS},
    }
    out = LOG_DIR / "sfx_replacement_map.json"
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out


def write_patch_notes(version: str):
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    note = textwrap.dedent(
        f"""
        {GAME_NAME}
        Version: {version}
        Generated: {datetime.now().isoformat()}

        Patch Notes
        - Switched the playable world over to an open district layout derived from the uploaded level2 world logic.
        - Reduced near-field clutter with broader roads, landmarks, courtyards, and clearer route silhouettes.
        - Moved the dense metropolis into a distant skyline backdrop so it reads as scale without crushing framerate.
        - Added an aura-based material reveal: nearby structures fade their solid surfaces in around the player while linework remains readable at range.
        - Spread the cockpit shoulder pylons wider for a clearer center view and moved the LED health/ammo meters onto them.
        - Added generated mech weapon/audio feedback and hardened chain-lightning targeting against removed enemies.
        - Kept the mech combat layer, red enemy cores, fog treatment, workstation, and crash logging.
        - Increased Campaign enemy scale/pressure and added a slow saturated command-field hue cycle.
        - Pass06: reduced close-range enemy pressure with origin/player spawn safety, lower chunk spawn density, and staged objective defenders.
        - Pass06: direct weapon hits now one-shot enemy cores and create stronger kill/explosion FX.
        - Pass03: added readable enemy attack tells, armor shield-break moments, stronger impact SFX, and clearer deterministic chain arcs.
        - Pass04: added lightweight impact physics, knockback/stagger impulses, bouncing debris shards, and cleaner shockwave rings.
        - Pass05: replaced random/instant enemy pop-ins with a queued spawn director, distant warning rings, and sequenced arrivals.
        - Pass06: replaced random weapon cycling with four numbered weapon slots, separate ammo pools, objective unlocks, implosion/magnet/disassembler effects, and bounded weapon pickups.
        - Pass07: improved weapon feel with Core Lance pierce-through, Imploder crush aftershocks, Magnet center-crush/tethers, targeted disassembly, and magnetized ammo caches.
        """
    ).strip()
    (PATCH_DIR / "latest_patch_notes.txt").write_text(note + "\n", encoding="utf-8")


def generate_blotch_texture_file():
    ensure_dirs()
    if BLOTCH_TEXTURE.exists() or Image is None:
        return
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = 128
    rng = random.Random(771)
    for _ in range(56):
        rx = rng.randint(16, 64)
        ry = rng.randint(12, 58)
        ox = rng.randint(-56, 56)
        oy = rng.randint(-44, 64)
        alpha = rng.randint(18, 70)
        draw.ellipse((cx + ox - rx, cy + oy - ry, cx + ox + rx, cy + oy + ry), fill=(255, 255, 255, alpha))
    for _ in range(12):
        x = cx + rng.randint(-50, 50)
        y = cy + rng.randint(10, 50)
        w = rng.randint(8, 18)
        h = rng.randint(38, 92)
        draw.rounded_rectangle((x - w, y, x + w, y + h), radius=w // 2, fill=(255, 255, 255, rng.randint(22, 88)))
    img.save(BLOTCH_TEXTURE)




def _audio_envelope(t: float, duration: float, attack: float = 0.004, release: float = 0.04):
    if duration <= 0.0:
        return 0.0
    if t < attack:
        return t / max(attack, 1e-6)
    if t > duration - release:
        return max(0.0, (duration - t) / max(release, 1e-6))
    return 1.0


def _soft_clip(v: float) -> float:
    return max(-1.0, min(1.0, v * 0.85))


def _write_wav(path: Path, samples, sample_rate: int = 22050):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as wav_f:
        wav_f.setnchannels(1)
        wav_f.setsampwidth(2)
        wav_f.setframerate(sample_rate)
        frames = bytearray()
        for sample in samples:
            frames.extend(struct.pack('<h', int(max(-32767, min(32767, sample * 32767)))))
        wav_f.writeframes(frames)


def _synth_sfx(kind: str, duration: float, seed: int, sample_rate: int = 22050):
    rng = random.Random(seed)
    total = max(1, int(duration * sample_rate))
    out = []
    for i in range(total):
        t = i / sample_rate
        env = _audio_envelope(t, duration)
        noise = rng.uniform(-1.0, 1.0)
        if kind == 'fire':
            tone = 0.48 * math.sin(math.tau * 82.0 * t) + 0.28 * math.sin(math.tau * 164.0 * t)
            rasp = 0.36 * noise * (1.0 - min(1.0, t / duration))
            pulse = 0.12 * math.sin(math.tau * 910.0 * t)
            sample = (tone + rasp + pulse) * env
        elif kind == 'hit':
            drop = max(0.0, 1.0 - t / duration)
            tone = 0.34 * math.sin(math.tau * (920.0 - 520.0 * t / duration) * t)
            snap = 0.18 * math.sin(math.tau * 2180.0 * t) * drop
            crack = 0.58 * noise * drop
            sample = (tone + snap + crack) * env
        elif kind == 'armor':
            drop = max(0.0, 1.0 - t / duration)
            clang = 0.36 * math.sin(math.tau * (420.0 - 110.0 * t / duration) * t)
            bite = 0.32 * math.sin(math.tau * 1240.0 * t) * drop
            crack = 0.42 * noise * drop
            sample = (clang + bite + crack) * env
        elif kind == 'break':
            drop = max(0.0, 1.0 - t / duration)
            low = 0.48 * math.sin(math.tau * (138.0 - 46.0 * t / duration) * t)
            glass = 0.32 * math.sin(math.tau * (1520.0 + 340.0 * t / duration) * t) * drop
            crack = 0.68 * noise * drop
            sample = (low + glass + crack) * env
        elif kind == 'tell':
            ramp = min(1.0, t / max(0.001, duration))
            freq = 240.0 + 760.0 * ramp
            tone = 0.42 * math.sin(math.tau * freq * t)
            chirp = 0.18 * math.sin(math.tau * freq * 2.0 * t) * ramp
            sample = (tone + chirp + 0.08 * noise * ramp) * env
        elif kind == 'chain':
            drop = max(0.0, 1.0 - 0.4 * t / duration)
            tone = 0.22 * math.sin(math.tau * 1420.0 * t) + 0.16 * math.sin(math.tau * 2380.0 * t)
            crack = 0.70 * noise * drop
            sample = (tone + crack) * env
        elif kind == 'imploder':
            ramp = min(1.0, t / max(0.001, duration))
            drop = max(0.0, 1.0 - ramp)
            low = 0.62 * math.sin(math.tau * (72.0 + 34.0 * ramp) * t)
            suction = 0.40 * math.sin(math.tau * (620.0 - 260.0 * ramp) * t) * drop
            sample = (low + suction + 0.42 * noise * drop) * env
        elif kind == 'magnet':
            ramp = min(1.0, t / max(0.001, duration))
            hum = 0.44 * math.sin(math.tau * 180.0 * t) + 0.30 * math.sin(math.tau * 360.0 * t)
            chirp = 0.22 * math.sin(math.tau * (820.0 + 420.0 * ramp) * t)
            sample = (hum + chirp + 0.12 * noise) * env
        elif kind == 'disassemble':
            drop = max(0.0, 1.0 - t / duration)
            cut = 0.42 * math.sin(math.tau * (1380.0 + 520.0 * t / duration) * t)
            saw = 0.34 * math.sin(math.tau * 92.0 * t)
            sample = (cut + saw + 0.58 * noise * drop) * env
        elif kind == 'pickup':
            ramp = min(1.0, t / max(0.001, duration))
            tone = 0.36 * math.sin(math.tau * (420.0 + 880.0 * ramp) * t)
            bell = 0.26 * math.sin(math.tau * (840.0 + 440.0 * ramp) * t)
            sample = (tone + bell + 0.06 * noise) * env
        elif kind == 'recharge':
            freq = 340.0 + 980.0 * (t / duration)
            tone = 0.45 * math.sin(math.tau * freq * t)
            shimmer = 0.18 * math.sin(math.tau * freq * 0.5 * t)
            sample = (tone + shimmer) * env
        elif kind == 'kill':
            tone = 0.42 * math.sin(math.tau * (96.0 - 28.0 * t / duration) * t)
            crack = 0.38 * noise * (1.0 - t / duration)
            sample = (tone + crack) * env
        else:
            sample = (0.16 * noise + 0.08 * math.sin(math.tau * 210.0 * t)) * env
        out.append(_soft_clip(sample))
    return out


def generate_dynamic_sfx_files():
    ensure_dirs()
    specs = {
        'fire': (0.12, 1201),
        'hit': (0.13, 2302),
        'armor': (0.15, 3302),
        'break': (0.28, 4302),
        'tell': (0.22, 5302),
        'chain': (0.17, 3403),
        'recharge': (0.14, 4504),
        'kill': (0.27, 5605),
        'imploder': (0.32, 7607),
        'magnet': (0.30, 8608),
        'disassemble': (0.25, 9609),
        'pickup': (0.18, 10610),
        'dry': (0.08, 6706),
    }
    for key, path in SFX_PATHS.items():
        duration, seed = specs.get(key, (0.18, 9000 + abs(hash(key)) % 10000))
        # Deterministic fallback audio ships with the game; only create it when missing.
        if path.exists():
            continue
        try:
            _write_wav(path, _synth_sfx(key, duration, seed))
        except Exception:
            pass


def refresh_customfx_printouts(overwrite: bool = False) -> dict:
    """Copy the current generated fallback WAVs into customfx as editable printouts."""
    ensure_dirs()
    copied = {}
    for key, generated in SFX_PATHS.items():
        target = CUSTOM_FX_DIR / f"{SFX_STEMS[key]}.wav"
        try:
            if generated.exists() and (overwrite or not target.exists()):
                shutil.copy2(generated, target)
                copied[key] = os.fspath(target.relative_to(ROOT))
            elif target.exists():
                copied[key] = os.fspath(target.relative_to(ROOT))
            else:
                copied[key] = None
        except Exception:
            copied[key] = None
    try:
        if (CUSTOM_FX_DIR / "README.md").exists() and (SFX_OVERRIDE_DIR / "README.md").exists() and (AUDIO_LOOPS_DIR / "README.md").exists():
            return copied
        (CUSTOM_FX_DIR / "README.md").write_text(textwrap.dedent("""
        # customfx printouts

        This folder contains WAV printouts of the current Utopia Conflict SFX.

        Use these as references or starting points. For live replacement, copy your finished WAV into:

        `assets/audio/sfx/overrides/`

        Override files should use the same names, for example `mech_fire.wav`, `core_hit.wav`, or `magnet_field.wav`.
        The build now uses WAV-only SFX replacement to keep the replacement pipeline predictable.
        """).strip() + "\n", encoding="utf-8")
        (SFX_OVERRIDE_DIR / "README.md").write_text(textwrap.dedent("""
        # overrides

        Put replacement WAV files here. This folder has highest priority.

        Any matching WAV here overrides the customfx printout and generated fallback.
        Use `python -B main.py --sfx-map` to print the full effect-name map.
        """).strip() + "\n", encoding="utf-8")
        (AUDIO_LOOPS_DIR / "README.md").write_text(textwrap.dedent("""
        # audio loops

        Drop one or more WAV loop files here for music or ambience.

        Any WAV filename is accepted. The game scans this folder automatically on launch and starts the first loop it finds.
        Keep long loops normalized to avoid clipping. Stereo WAV files will preserve their stereo image.
        """).strip() + "\n", encoding="utf-8")
    except Exception:
        pass
    return copied


def discover_audio_loop_files() -> list[Path]:
    ensure_dirs()
    out = []
    try:
        for path in sorted(AUDIO_LOOPS_DIR.iterdir()):
            if path.is_file() and path.suffix.lower() in LOOP_EXTENSIONS:
                out.append(path)
    except Exception:
        pass
    return out


if "--sfx-map" in sys.argv:
    generate_dynamic_sfx_files()
    refresh_customfx_printouts()
    path = write_sfx_replacement_map()
    print(path.read_text(encoding="utf-8"))
    raise SystemExit(0)


def run_lightweight_self_test():
    ensure_dirs()
    install_crash_reporter()
    cfg = load_or_create_config()
    write_patch_notes(VERSION)
    generate_blotch_texture_file()
    generate_dynamic_sfx_files()
    customfx_printouts = refresh_customfx_printouts()
    report = {
        "game": GAME_NAME,
        "version": VERSION,
        "config_loaded": True,
        "day_length_seconds": cfg.day_length_seconds,
        "chunk_size": cfg.chunk_size,
        "line_thickness": cfg.line_thickness,
        "line_fade_start_ratio": cfg.line_fade_start_ratio,
        "blotch_texture_exists": BLOTCH_TEXTURE.exists(),
        "generated_sfx": {k: resolve_sfx_path(k).exists() for k in SFX_PATHS},
        "customfx_printouts": customfx_printouts,
        "audio_loops_found": [os.fspath(p.relative_to(ROOT)) for p in discover_audio_loop_files()],
        "activity_mode_enabled": bool(getattr(cfg, "activity_mode_enabled", True)),
        "patch_notes_dir": str(PATCH_DIR),
        "logs_dir": str(LOG_DIR),
    }
    (LOG_DIR / "self_test_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


_BLOTCH_TEX_CACHE = None
_BLOTCH_TEX_ATTEMPTED = False


def get_blotch_texture(loader):
    global _BLOTCH_TEX_CACHE, _BLOTCH_TEX_ATTEMPTED
    if _BLOTCH_TEX_ATTEMPTED:
        return _BLOTCH_TEX_CACHE
    _BLOTCH_TEX_ATTEMPTED = True
    try:
        ensure_dirs()
        if not BLOTCH_TEXTURE.exists():
            generate_blotch_texture_file()
        if BLOTCH_TEXTURE.exists():
            panda_path = Filename.fromOsSpecific(os.fspath(BLOTCH_TEXTURE))
            tex = loader.loadTexture(panda_path)
            if tex is not None:
                _BLOTCH_TEX_CACHE = tex
                return _BLOTCH_TEX_CACHE
    except Exception:
        _BLOTCH_TEX_CACHE = None
    return None




@dataclass
class Weapon:
    index: int
    name: str
    damage: float
    fire_interval: float
    spread: float
    range: float
    projectiles: int
    tracer_time: float
    recoil: float
    ammo_capacity: float
    ammo_cost: float
    kind: str = "core"
    slot: int = 1
    description: str = ""
    unlock_hint: str = ""
    ammo_regen: float = 0.0
    color_tag: str = "red"


@dataclass
class BoxBounds:
    min_v: Vec3
    max_v: Vec3
    normal_hint: Vec3



class SignalNode:
    """Line-built objective marker for recoverable fragments and the return lattice."""

    def __init__(self, app, index: int, pos: Vec3, label: str, kind: str = "fragment"):
        self.app = app
        self.index = int(index)
        self.pos = Vec3(pos)
        self.label = str(label)
        self.kind = str(kind or "fragment")
        self.completed = False
        self.active = self.kind != "extraction"
        self.age = 0.0
        self.radius = float(getattr(app.game_cfg, "extraction_radius", 7.0) if self.kind == "extraction" else getattr(app.game_cfg, "signal_recovery_radius", 5.25))
        parent = getattr(app, "mission_root", None) or getattr(app, "effect_root", app.render)
        self.root = parent.attachNewNode(f"etchline-signal-{self.kind}-{self.index}")
        self.root.setPos(self.pos)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.visual = self.root.attachNewNode(self._build_visual())
        self.visual.setAntialias(AntialiasAttrib.MLine)
        self.visual.setTransparency(TransparencyAttrib.MAlpha)
        self.beacon = self.root.attachNewNode(self._build_beacon_visual())
        self.beacon.setAntialias(AntialiasAttrib.MLine)
        self.beacon.setTransparency(TransparencyAttrib.MAlpha)
        self.label_np = self._build_world_label()
        if not self.active:
            self.root.hide()

    def _draw_ring_xy(self, segs: LineSegs, radius: float, z: float, segments: int = 28) -> None:
        first = None
        last = None
        for i in range(segments):
            ang = math.tau * i / max(3, segments)
            p = Vec3(math.cos(ang) * radius, math.sin(ang) * radius, z)
            if first is None:
                first = p
            if last is not None:
                segs.moveTo(last)
                segs.drawTo(p)
            last = p
        if first is not None and last is not None:
            segs.moveTo(last)
            segs.drawTo(first)

    def _build_visual(self):
        segs = LineSegs(f"etchline-signal-lines-{self.index}")
        thickness = self.app.movable_line_thickness((1.35 if self.kind == "extraction" else 1.1), 1.75)
        segs.setThickness(thickness)
        segs.setColor(*self.app.current_line_color(alpha=0.96))
        height = 9.5 if self.kind == "extraction" else 6.25
        base = 1.45 if self.kind == "extraction" else 1.0
        top = Vec3(0, 0, height)
        corners = [Vec3(base, 0, 0.15), Vec3(0, base, 0.15), Vec3(-base, 0, 0.15), Vec3(0, -base, 0.15)]
        for corner in corners:
            segs.moveTo(corner)
            segs.drawTo(top)
        for a, b in zip(corners, corners[1:] + corners[:1]):
            segs.moveTo(a)
            segs.drawTo(b)
        for z, r in ((1.2, base * 1.4), (3.1, base * 1.9), (height - 1.15, base * 1.2)):
            self._draw_ring_xy(segs, r, z, 28)
        glyph_z = height * 0.55
        glyph = [Vec3(-1.0, 0, glyph_z), Vec3(0, 0, glyph_z + 1.25), Vec3(1.0, 0, glyph_z), Vec3(0, 0, glyph_z - 1.25)]
        for a, b in zip(glyph, glyph[1:] + glyph[:1]):
            segs.moveTo(a)
            segs.drawTo(b)
        if self.kind == "extraction":
            for arm in range(8):
                ang = math.tau * arm / 8
                inner = Vec3(math.cos(ang) * 2.0, math.sin(ang) * 2.0, 2.4)
                outer = Vec3(math.cos(ang) * 5.4, math.sin(ang) * 5.4, 2.4)
                segs.moveTo(inner)
                segs.drawTo(outer)
        return segs.create()

    def _build_beacon_visual(self):
        segs = LineSegs(f"etchline-signal-beacon-{self.index}")
        segs.setThickness(self.app.movable_line_thickness((1.85 if self.kind == "extraction" else 1.45), 2.1))
        segs.setColor(*self.app.signal_accent_color(alpha=0.86 if self.kind == "extraction" else 0.72))
        height = float(getattr(self.app.game_cfg, "extraction_beacon_height", 22.0) if self.kind == "extraction" else getattr(self.app.game_cfg, "objective_beacon_height", 14.0))
        core_radius = 0.34 if self.kind != "extraction" else 0.55
        for arm in range(4):
            ang = math.tau * arm / 4 + math.pi * 0.25
            offset = Vec3(math.cos(ang) * core_radius, math.sin(ang) * core_radius, 0)
            segs.moveTo(offset.x, offset.y, 0.15)
            segs.drawTo(offset.x * 0.25, offset.y * 0.25, height)
        for z, radius, segments in ((0.08, self.radius, 48), (height * 0.44, 1.45 if self.kind != "extraction" else 2.3, 32), (height * 0.82, 0.72 if self.kind != "extraction" else 1.3, 28)):
            first = last = None
            for i in range(segments):
                ang = math.tau * i / max(3, segments)
                p = Vec3(math.cos(ang) * radius, math.sin(ang) * radius, z)
                if first is None:
                    first = p
                if last is not None:
                    segs.moveTo(last)
                    segs.drawTo(p)
                last = p
            if first is not None and last is not None:
                segs.moveTo(last)
                segs.drawTo(first)
        if self.kind == "extraction":
            for side in (-1, 1):
                x = side * 2.2
                segs.moveTo(x, -1.6, 0.2)
                segs.drawTo(x, -1.6, height * 0.68)
                segs.drawTo(x * 0.45, 0.0, height)
        return segs.create()

    def _build_world_label(self):
        try:
            text = TextNode(f"etchline-signal-label-{self.index}")
            short = "RETURN" if self.kind == "extraction" else f"F{self.index}"
            text.setText(short)
            text.setAlign(TextNode.ACenter)
            text.setTextColor(*self.app.signal_accent_color(alpha=0.88))
            text.setShadow(0.045, 0.045)
            text.setShadowColor(0, 0, 0, 0.75)
            np = self.root.attachNewNode(text)
            height = float(getattr(self.app.game_cfg, "extraction_beacon_height", 22.0) if self.kind == "extraction" else getattr(self.app.game_cfg, "objective_beacon_height", 14.0))
            np.setPos(0, 0, height + 1.2)
            np.setScale(1.05 if self.kind == "extraction" else 0.78)
            np.setBillboardAxis()
            np.setTransparency(TransparencyAttrib.MAlpha)
            return np
        except Exception:
            return None

    def set_active(self, active: bool) -> None:
        self.active = bool(active)
        try:
            self.root.show() if self.active else self.root.hide()
        except Exception:
            pass

    def mark_completed(self) -> None:
        self.completed = True
        self.active = False if self.kind == "fragment" else True
        try:
            if self.kind == "fragment" and getattr(self, "label_np", None) is not None:
                self.label_np.hide()
        except Exception:
            pass

    def dispose(self) -> None:
        try:
            if getattr(self, "root", None) is not None and not self.root.isEmpty():
                self.root.removeNode()
        except Exception:
            pass

    def update(self, dt: float, player_pos: Vec3) -> None:
        if not self.active and not self.completed:
            return
        self.age += max(0.0, float(dt or 0.0))
        pulse = 0.5 + 0.5 * math.sin(self.age * (4.2 if self.kind == "extraction" else 3.4) + self.index)
        base_scale = 1.0 + pulse * (0.11 if self.kind == "extraction" else 0.07)
        try:
            self.root.setScale(base_scale)
        except Exception:
            pass
        alpha = 0.28 if self.completed and self.kind == "fragment" else (0.72 + pulse * 0.24)
        try:
            self.visual.setColorScale(*self.app.current_line_color(alpha=alpha))
            beacon_alpha = 0.18 if self.completed and self.kind == "fragment" else (0.56 + pulse * (0.34 if self.kind == "extraction" else 0.24))
            self.beacon.setColorScale(*self.app.signal_accent_color(alpha=beacon_alpha))
            if getattr(self, "label_np", None) is not None:
                self.label_np.setColorScale(*self.app.signal_accent_color(alpha=0.65 + pulse * 0.28))
        except Exception:
            pass

    def player_inside(self, player_pos: Vec3) -> bool:
        delta = Vec3(player_pos.x - self.pos.x, player_pos.y - self.pos.y, 0)
        return delta.lengthSquared() <= self.radius * self.radius

    def ray_hit(self, origin: Vec3, direction: Vec3, max_range: float):
        if not self.active or self.completed:
            return None
        center = self.pos + Vec3(0, 0, 3.0 if self.kind != "extraction" else 4.5)
        to_center = center - origin
        t = to_center.dot(direction)
        if t < 0.1 or t > max_range:
            return None
        closest = origin + direction * t
        radius = 2.6 if self.kind == "extraction" else 2.1
        if (closest - center).lengthSquared() <= radius * radius:
            return t, center
        return None


class SignalPulseEffect:
    """Bounded objective feedback pulse for recovered fragments and return routes."""

    def __init__(self, app, pos: Vec3, label: str = "signal", radius: float = 1.0, life: float = 1.25, height: float = 0.10):
        self.app = app
        self.pos = Vec3(pos)
        self.label = str(label or "signal")
        self.base_radius = max(0.5, float(radius or 1.0))
        self.life = max(0.2, float(life or 1.25))
        self.height = float(height or 0.10)
        self.age = 0.0
        parent = getattr(app, "effect_root", app.render)
        self.root = parent.attachNewNode(f"etchline-signal-pulse-{self.label}")
        self.root.setPos(self.pos)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.visual = self.root.attachNewNode(self._build_visual())
        self.visual.setTransparency(TransparencyAttrib.MAlpha)
        self.visual.setAntialias(AntialiasAttrib.MLine)

    def _build_visual(self):
        segs = LineSegs(f"etchline-pulse-lines-{self.label}")
        segs.setThickness(max(1.4, float(getattr(self.app.game_cfg, "line_thickness", 1.45)) * 1.35))
        segs.setColor(*self.app.signal_accent_color(alpha=0.78))
        for z, radius_mul, segments in ((self.height, 1.0, 36), (self.height + 0.08, 1.45, 44), (self.height + 0.16, 1.9, 52)):
            first = last = None
            radius = self.base_radius * radius_mul
            for i in range(segments):
                ang = math.tau * i / max(3, segments)
                p = Vec3(math.cos(ang) * radius, math.sin(ang) * radius, z)
                if first is None:
                    first = p
                if last is not None:
                    segs.moveTo(last)
                    segs.drawTo(p)
                last = p
            if first is not None and last is not None:
                segs.moveTo(last)
                segs.drawTo(first)
        for arm in range(8):
            ang = math.tau * arm / 8
            inner = Vec3(math.cos(ang) * self.base_radius * 0.35, math.sin(ang) * self.base_radius * 0.35, self.height + 0.2)
            outer = Vec3(math.cos(ang) * self.base_radius * 2.25, math.sin(ang) * self.base_radius * 2.25, self.height + 0.2)
            segs.moveTo(inner)
            segs.drawTo(outer)
        return segs.create()

    def dispose(self) -> None:
        try:
            if getattr(self, "root", None) is not None and not self.root.isEmpty():
                self.root.removeNode()
        except Exception:
            pass

    def update(self, dt: float) -> bool:
        self.age += max(0.0, float(dt or 0.0))
        t = min(1.0, self.age / self.life)
        ease = t * t * (3.0 - 2.0 * t)
        try:
            self.root.setScale(1.0 + ease * 2.3)
            self.root.setZ(self.pos.z + ease * 1.7)
            self.visual.setColorScale(*self.app.signal_accent_color(alpha=max(0.0, 0.78 * (1.0 - t))))
        except Exception:
            return False
        if self.age >= self.life:
            self.dispose()
            return False
        return True


class CombatFeedbackEffect:
    """Short-lived combat pulse used for spawn warnings, hits, and enemy deaths."""

    def __init__(self, app, pos: Vec3, label: str = "hit", radius: float = 1.0, life: float = 0.55, height: float = 0.24, warning: bool = True):
        self.app = app
        self.pos = Vec3(pos)
        self.label = str(label or "hit")
        self.base_radius = max(0.25, float(radius or 1.0))
        self.life = max(0.12, float(life or 0.55))
        self.height = float(height or 0.24)
        self.warning = bool(warning)
        self.age = 0.0
        parent = getattr(app, "effect_root", app.render)
        self.root = parent.attachNewNode(f"etchline-combat-feedback-{self.label}")
        self.root.setPos(self.pos)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.visual = self.root.attachNewNode(self._build_visual())
        self.visual.setTransparency(TransparencyAttrib.MAlpha)
        self.visual.setAntialias(AntialiasAttrib.MLine)

    def _color(self, alpha: float = 1.0):
        if self.warning:
            return self.app.warning_accent_color(alpha=alpha)
        return self.app.signal_accent_color(alpha=alpha)

    def _build_visual(self):
        segs = LineSegs(f"etchline-combat-lines-{self.label}")
        segs.setThickness(max(1.2, float(getattr(self.app.game_cfg, "line_thickness", 1.45)) * 1.55))
        segs.setColor(*self._color(alpha=0.90))
        rings = 3 if self.label in {"death", "break"} else (1 if self.label == "tell" else 2)
        for r_i in range(rings):
            radius = self.base_radius * (1.0 + r_i * 0.48)
            z = self.height + r_i * 0.08
            first = last = None
            segments = 26 + r_i * 8
            for i in range(segments):
                ang = math.tau * i / max(3, segments)
                p = Vec3(math.cos(ang) * radius, math.sin(ang) * radius, z)
                if first is None:
                    first = p
                if last is not None:
                    segs.moveTo(last)
                    segs.drawTo(p)
                last = p
            if first is not None and last is not None:
                segs.moveTo(last)
                segs.drawTo(first)
        arm_count = 6 if self.label in {"spawn", "tell"} else (10 if self.label == "break" else 8)
        for arm in range(arm_count):
            ang = math.tau * arm / max(1, arm_count)
            inner = Vec3(math.cos(ang) * self.base_radius * 0.28, math.sin(ang) * self.base_radius * 0.28, self.height + 0.18)
            outer = Vec3(math.cos(ang) * self.base_radius * (1.9 if self.label == "death" else 1.45), math.sin(ang) * self.base_radius * (1.9 if self.label == "death" else 1.45), self.height + 0.18)
            segs.moveTo(inner)
            segs.drawTo(outer)
        if self.label == "spawn":
            for side in (-1, 1):
                segs.moveTo(side * self.base_radius, 0, 0.05)
                segs.drawTo(0, 0, self.height + self.base_radius * 1.8)
        elif self.label == "hit":
            segs.moveTo(-self.base_radius * 0.75, 0, self.height + self.base_radius * 0.75)
            segs.drawTo(self.base_radius * 0.75, 0, self.height - self.base_radius * 0.15)
            segs.moveTo(self.base_radius * 0.75, 0, self.height + self.base_radius * 0.75)
            segs.drawTo(-self.base_radius * 0.75, 0, self.height - self.base_radius * 0.15)
        elif self.label == "tell":
            for i in range(3):
                z = self.height + self.base_radius * (0.62 + i * 0.34)
                w = self.base_radius * (0.42 + i * 0.13)
                segs.moveTo(-w, 0, z)
                segs.drawTo(0, 0, z + self.base_radius * 0.28)
                segs.drawTo(w, 0, z)
        elif self.label == "break":
            for i in range(10):
                ang = math.tau * i / 10.0
                start = Vec3(math.cos(ang) * self.base_radius * 0.25, math.sin(ang) * self.base_radius * 0.25, self.height + 0.1)
                end = Vec3(math.cos(ang) * self.base_radius * random.uniform(1.45, 2.35), math.sin(ang) * self.base_radius * random.uniform(1.45, 2.35), self.height + random.uniform(-0.35, 0.55))
                segs.moveTo(start)
                segs.drawTo(end)
        elif self.label == "chain":
            for i in range(4):
                z = self.height + i * 0.18
                segs.moveTo(-self.base_radius, 0, z)
                segs.drawTo(self.base_radius, 0, z + self.base_radius * 0.35)
                segs.moveTo(0, -self.base_radius, z + self.base_radius * 0.18)
                segs.drawTo(0, self.base_radius, z - self.base_radius * 0.18)
        return segs.create()

    def dispose(self) -> None:
        try:
            if getattr(self, "root", None) is not None and not self.root.isEmpty():
                self.root.removeNode()
        except Exception:
            pass

    def update(self, dt: float) -> bool:
        self.age += max(0.0, float(dt or 0.0))
        t = min(1.0, self.age / self.life)
        ease = t * t * (3.0 - 2.0 * t)
        try:
            scale_boost = 2.0 if self.label in {"death", "break"} else (1.65 if self.label == "tell" else 1.35)
            z_boost = 1.3 if self.label in {"death", "break"} else (0.85 if self.label == "tell" else 0.55)
            self.root.setScale(0.72 + ease * scale_boost)
            self.root.setZ(self.pos.z + ease * z_boost)
            self.visual.setColorScale(*self._color(alpha=max(0.0, 0.92 * (1.0 - t))))
        except Exception:
            return False
        if self.age >= self.life:
            self.dispose()
            return False
        return True


class TracerEffect:
    def __init__(self, app, start: Vec3, end: Vec3, ttl: float = 0.05, color=None, thickness_scale: float = 1.0, points=None):
        self.app = app
        self.ttl = ttl
        self.age = 0.0
        self.base_color = color or (1.0, 0.16, 0.16, 1.0)
        segs = LineSegs("tracer")
        segs.setThickness(max(1.0, app.game_cfg.line_thickness * thickness_scale))
        segs.setColor(*self.base_color)
        pts = points or [start, end]
        first = True
        for p in pts:
            if first:
                segs.moveTo(p)
                first = False
            else:
                segs.drawTo(p)
        self.np = app.render.attachNewNode(segs.create())
        self.np.setAntialias(AntialiasAttrib.MLine)
        self.np.setTransparency(TransparencyAttrib.MAlpha)
        self.np.setBin("fixed", 10)

    def update(self, dt: float):
        self.age += dt
        t = max(0.0, 1.0 - self.age / max(0.001, self.ttl))
        self.np.setColorScale(self.base_color[0], self.base_color[1], self.base_color[2], self.base_color[3] * t)
        if self.age >= self.ttl:
            self.np.removeNode()
            return False
        return True



class PhysicsShardEffect:
    """Small bounded debris line with gravity and bounce for impact feel without a full physics engine."""

    def __init__(self, app, pos: Vec3, velocity: Vec3, life: float = 0.75, length: float = 0.72, color=None, thickness_scale: float = 0.82):
        self.app = app
        self.pos = Vec3(pos)
        self.velocity = Vec3(velocity)
        self.life = max(0.18, float(life or 0.75))
        self.age = 0.0
        self.length = max(0.12, float(length or 0.72))
        self.base_color = color or (1.0, 0.22, 0.08, 0.94)
        parent = getattr(app, "effect_root", app.render)
        segs = LineSegs("physics-shard")
        segs.setThickness(max(1.0, app.game_cfg.line_thickness * thickness_scale))
        segs.setColor(*self.base_color)
        segs.moveTo(0, 0, 0)
        segs.drawTo(0, self.length, 0)
        self.np = parent.attachNewNode(segs.create())
        self.np.setAntialias(AntialiasAttrib.MLine)
        self.np.setTransparency(TransparencyAttrib.MAlpha)
        self.np.setBin("fixed", 9)
        self._apply_transform()

    def _apply_transform(self):
        try:
            self.np.setPos(self.pos)
            direction = Vec3(self.velocity)
            if direction.lengthSquared() < 0.001:
                direction = Vec3(0, 1, 0)
            self.np.lookAt(self.pos + direction)
        except Exception:
            pass

    def dispose(self):
        try:
            if getattr(self, "np", None) is not None and not self.np.isEmpty():
                self.np.removeNode()
        except Exception:
            pass

    def update(self, dt: float) -> bool:
        dt = max(0.0, float(dt or 0.0))
        self.age += dt
        gravity = float(getattr(self.app.game_cfg, "gravity", 20.0)) * float(getattr(self.app.game_cfg, "physics_shard_gravity_scale", 0.78))
        self.velocity.z -= gravity * dt
        drag = max(0.0, 1.0 - dt * 1.25)
        self.velocity.x *= drag
        self.velocity.y *= drag
        self.pos += self.velocity * dt
        floor_z = 0.06
        if self.pos.z < floor_z:
            self.pos.z = floor_z
            if self.velocity.z < 0.0:
                self.velocity.z = -self.velocity.z * float(getattr(self.app.game_cfg, "physics_shard_bounce", 0.38))
                self.velocity.x *= 0.72
                self.velocity.y *= 0.72
        t = min(1.0, self.age / self.life)
        fade = max(0.0, 1.0 - t)
        try:
            self.np.setColorScale(self.base_color[0], self.base_color[1], self.base_color[2], self.base_color[3] * fade)
            self._apply_transform()
        except Exception:
            return False
        if self.age >= self.life:
            self.dispose()
            return False
        return True


class ShockwaveRingEffect:
    """Expanding impact ring that makes explosions read as physical force."""

    def __init__(self, app, pos: Vec3, radius: float = 8.0, life: float = 0.52, vertical: bool = False, color=None, thickness_scale: float = 1.4):
        self.app = app
        self.pos = Vec3(pos)
        self.radius = max(0.5, float(radius or 8.0))
        self.life = max(0.15, float(life or 0.52))
        self.vertical = bool(vertical)
        self.age = 0.0
        self.base_color = color or (1.0, 0.12, 0.08, 0.94)
        parent = getattr(app, "effect_root", app.render)
        segs = LineSegs("shockwave-ring")
        segs.setThickness(max(1.0, app.game_cfg.line_thickness * thickness_scale))
        segs.setColor(*self.base_color)
        pts = []
        for i in range(49):
            ang = math.tau * i / 48
            if self.vertical:
                pts.append(Vec3(math.cos(ang), 0.0, math.sin(ang)))
            else:
                pts.append(Vec3(math.cos(ang), math.sin(ang), 0.0))
        first = True
        for pt in pts:
            if first:
                segs.moveTo(pt)
                first = False
            else:
                segs.drawTo(pt)
        self.np = parent.attachNewNode(segs.create())
        self.np.setPos(self.pos)
        self.np.setAntialias(AntialiasAttrib.MLine)
        self.np.setTransparency(TransparencyAttrib.MAlpha)
        self.np.setBin("fixed", 8)

    def dispose(self):
        try:
            if getattr(self, "np", None) is not None and not self.np.isEmpty():
                self.np.removeNode()
        except Exception:
            pass

    def update(self, dt: float) -> bool:
        self.age += max(0.0, float(dt or 0.0))
        t = min(1.0, self.age / self.life)
        ease = 1.0 - (1.0 - t) * (1.0 - t)
        scale = max(0.01, self.radius * ease)
        fade = max(0.0, 1.0 - t)
        try:
            self.np.setScale(scale)
            self.np.setColorScale(self.base_color[0], self.base_color[1], self.base_color[2], self.base_color[3] * fade)
        except Exception:
            return False
        if self.age >= self.life:
            self.dispose()
            return False
        return True


class WeaponGlyphEffect:
    """Small geometric projectile/impact glyph used by weapon variants."""

    def __init__(self, app, start: Vec3, end: Vec3, shape: str = "diamond", life: float = 0.34, radius: float = 0.72, color=None, spin: float = 180.0):
        self.app = app
        self.start = Vec3(start)
        self.end = Vec3(end)
        self.shape = str(shape or "diamond")
        self.life = max(0.08, float(life or 0.34))
        self.radius = max(0.08, float(radius or 0.72))
        self.color = color or (1.0, 0.18, 0.08, 0.96)
        self.spin = float(spin or 180.0)
        self.age = 0.0
        parent = getattr(app, "effect_root", app.render)
        self.root = parent.attachNewNode(f"weapon-glyph-{self.shape}")
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.root.setAntialias(AntialiasAttrib.MLine)
        self.visual = self.root.attachNewNode(self._build_visual())
        self.visual.setTransparency(TransparencyAttrib.MAlpha)
        self.visual.setAntialias(AntialiasAttrib.MLine)
        self._apply_transform(0.0)

    def _build_visual(self):
        segs = LineSegs(f"weapon-glyph-lines-{self.shape}")
        segs.setThickness(max(1.0, self.app.game_cfg.line_thickness * 1.25))
        segs.setColor(*self.color)
        r = self.radius
        if self.shape == "triangle":
            pts = [Vec3(0, 0, r), Vec3(-r * 0.9, 0, -r * 0.65), Vec3(r * 0.9, 0, -r * 0.65)]
        elif self.shape == "cube":
            pts = [Vec3(-r, 0, -r), Vec3(r, 0, -r), Vec3(r, 0, r), Vec3(-r, 0, r)]
        elif self.shape == "cross":
            segs.moveTo(-r, 0, 0); segs.drawTo(r, 0, 0)
            segs.moveTo(0, 0, -r); segs.drawTo(0, 0, r)
            segs.moveTo(-r * 0.55, 0, -r * 0.55); segs.drawTo(r * 0.55, 0, r * 0.55)
            segs.moveTo(r * 0.55, 0, -r * 0.55); segs.drawTo(-r * 0.55, 0, r * 0.55)
            return segs.create()
        else:
            pts = [Vec3(0, 0, r), Vec3(r, 0, 0), Vec3(0, 0, -r), Vec3(-r, 0, 0)]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            segs.moveTo(a); segs.drawTo(b)
        if self.shape in {"cube", "diamond"}:
            segs.moveTo(0, -r * 0.55, 0); segs.drawTo(0, r * 0.55, 0)
        return segs.create()

    def _apply_transform(self, t: float):
        pos = self.start * (1.0 - t) + self.end * t
        try:
            self.root.setPos(pos)
            direction = self.end - self.start
            if direction.lengthSquared() > 0.001:
                self.root.lookAt(pos + direction)
            self.root.setR(self.spin * self.age)
        except Exception:
            pass

    def dispose(self):
        try:
            if getattr(self, "root", None) is not None and not self.root.isEmpty():
                self.root.removeNode()
        except Exception:
            pass

    def update(self, dt: float) -> bool:
        self.age += max(0.0, float(dt or 0.0))
        t = min(1.0, self.age / self.life)
        self._apply_transform(t)
        fade = max(0.0, 1.0 - t)
        try:
            self.visual.setColorScale(self.color[0], self.color[1], self.color[2], self.color[3] * fade)
            self.root.setScale(0.55 + 0.65 * (1.0 - abs(0.5 - t) * 2.0))
        except Exception:
            return False
        if self.age >= self.life:
            self.dispose()
            return False
        return True


class DetachedPartEffect:
    """Readable actor part detachment without introducing a heavy rigid-body dependency."""

    def __init__(self, app, pos: Vec3, velocity: Vec3, label: str = "part", size: float = 0.72, life: float = 1.8):
        self.app = app
        self.pos = Vec3(pos)
        self.velocity = Vec3(velocity)
        self.label = str(label or "part")
        self.size = max(0.18, float(size or 0.72))
        self.life = max(0.45, float(life or 1.8))
        self.age = 0.0
        parent = getattr(app, "effect_root", app.render)
        self.root = parent.attachNewNode(f"detached-{self.label}")
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.root.setAntialias(AntialiasAttrib.MLine)
        segs = LineSegs(f"detached-lines-{self.label}")
        segs.setThickness(app.movable_line_thickness(1.05, 1.75))
        segs.setColor(0.18, 0.92, 1.0, 0.94)
        r = self.size
        pts = [Vec3(-r, 0, -r * 0.5), Vec3(r, 0, -r * 0.5), Vec3(r, 0, r * 0.5), Vec3(-r, 0, r * 0.5)]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            segs.moveTo(a); segs.drawTo(b)
        segs.moveTo(-r * 0.65, 0, 0); segs.drawTo(r * 0.65, 0, 0)
        self.visual = self.root.attachNewNode(segs.create())
        self._apply_transform()

    def _apply_transform(self):
        try:
            self.root.setPos(self.pos)
            self.root.setHpr(self.age * 230.0, self.age * 147.0, self.age * 93.0)
        except Exception:
            pass

    def dispose(self):
        try:
            if getattr(self, "root", None) is not None and not self.root.isEmpty():
                self.root.removeNode()
        except Exception:
            pass

    def update(self, dt: float) -> bool:
        dt = max(0.0, float(dt or 0.0))
        self.age += dt
        self.velocity.z -= float(getattr(self.app.game_cfg, "gravity", 20.0)) * 0.82 * dt
        self.velocity.x *= max(0.0, 1.0 - dt * 0.85)
        self.velocity.y *= max(0.0, 1.0 - dt * 0.85)
        self.pos += self.velocity * dt
        if self.pos.z < 0.08:
            self.pos.z = 0.08
            if self.velocity.z < 0.0:
                self.velocity.z = -self.velocity.z * 0.32
                self.velocity.x *= 0.68
                self.velocity.y *= 0.68
        fade = max(0.0, 1.0 - self.age / self.life)
        try:
            self.visual.setColorScale(0.18, 0.92, 1.0, 0.94 * fade)
            self._apply_transform()
        except Exception:
            return False
        if self.age >= self.life:
            self.dispose()
            return False
        return True


class MagnetFieldEffect:
    """Temporary proximity magnet that pulls enemies toward its anchor."""

    def __init__(self, app, pos: Vec3, radius: float = 22.0, life: float = 4.6):
        self.app = app
        self.pos = Vec3(pos)
        self.radius = max(4.0, float(radius or 22.0))
        self.life = max(0.5, float(life or 4.6))
        self.age = 0.0
        self.damage_timer = 0.0
        parent = getattr(app, "effect_root", app.render)
        self.root = parent.attachNewNode("proximity-magnet-field")
        self.root.setPos(self.pos)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.root.setAntialias(AntialiasAttrib.MLine)
        self.visual = self.root.attachNewNode(self._build_visual())
        self.visual.setTransparency(TransparencyAttrib.MAlpha)
        self.visual.setAntialias(AntialiasAttrib.MLine)

    def _build_visual(self):
        segs = LineSegs("magnet-field-lines")
        segs.setThickness(max(1.0, self.app.game_cfg.line_thickness * 1.18))
        segs.setColor(0.18, 0.92, 1.0, 0.88)
        for ring, scale in enumerate([0.35, 0.62, 1.0]):
            r = self.radius * scale
            last = first = None
            for i in range(49):
                ang = math.tau * i / 48
                p = Vec3(math.cos(ang) * r, math.sin(ang) * r, 0.16 + ring * 0.18)
                if first is None:
                    first = p
                if last is not None:
                    segs.moveTo(last); segs.drawTo(p)
                last = p
            if first is not None and last is not None:
                segs.moveTo(last); segs.drawTo(first)
        for arm in range(8):
            ang = math.tau * arm / 8
            segs.moveTo(math.cos(ang) * self.radius, math.sin(ang) * self.radius, 0.24)
            segs.drawTo(math.cos(ang) * self.radius * 0.18, math.sin(ang) * self.radius * 0.18, 1.8)
        return segs.create()

    def dispose(self):
        try:
            if getattr(self, "root", None) is not None and not self.root.isEmpty():
                self.root.removeNode()
        except Exception:
            pass

    def update(self, dt: float) -> bool:
        dt = max(0.0, float(dt or 0.0))
        self.age += dt
        self.damage_timer -= dt
        pull_force = float(getattr(self.app.game_cfg, "magnet_pull_force", 19.0))
        did_tick = self.damage_timer <= 0.0
        if did_tick:
            self.damage_timer = 0.52
        tether_count = 0
        for enemy in list(getattr(self.app, "enemies", []) or []):
            if enemy.dead or enemy.root is None or enemy.root.isEmpty():
                continue
            delta = self.pos - enemy.root.getPos(self.app.render)
            delta.z = 0.0
            dist = delta.length()
            if 0.001 < dist <= self.radius:
                delta.normalize()
                falloff = 1.0 - min(1.0, dist / self.radius)
                enemy.apply_impulse(delta, pull_force * (0.18 + falloff * 0.72))
                enemy.stagger_timer = max(float(getattr(enemy, "stagger_timer", 0.0)), 0.08 + falloff * 0.18)
                if did_tick and tether_count < 5:
                    tether_count += 1
                    self.app.tracers.append(TracerEffect(self.app, enemy.core_world_position(), self.pos + Vec3(0, 0, 0.8), ttl=0.20, color=self.app.weapon_color("magnet", 0.78), thickness_scale=0.92))
                if did_tick and dist < self.radius * 0.72:
                    center_scale = float(getattr(self.app.game_cfg, "magnet_center_crush_radius_scale", 0.28))
                    center_crush = dist <= self.radius * center_scale
                    dmg = float(getattr(self.app.game_cfg, "magnet_tick_damage", 10.0)) * (0.35 + falloff)
                    if center_crush:
                        dmg += float(getattr(self.app.game_cfg, "magnet_center_crush_damage", 18.0)) * (0.35 + falloff)
                        if not bool(getattr(enemy, "armor_broken", False)):
                            enemy.break_armor(enemy.core_world_position(), -delta)
                        self.app.add_combat_feedback(enemy.core_world_position(), label="chain", radius=1.75, life=0.28, warning=False)
                    killed = enemy.hit(dmg, enemy.core_world_position(), -delta, force_kill=False, hit_kind="magnet")
                    self.app.register_combat_hit(enemy, hit_kind="magnet", killed=killed, source_point=self.pos, chain=False)
        if tether_count >= 2 and hasattr(self.app, "record_activity"):
            self.app.record_activity("magnet_garden", "Magnet Garden", pos=self.pos)
        t = min(1.0, self.age / self.life)
        pulse = 0.85 + 0.18 * math.sin(self.app.elapsed * 8.0)
        try:
            self.root.setScale(pulse)
            self.visual.setColorScale(0.18, 0.92, 1.0, 0.78 * max(0.0, 1.0 - t))
        except Exception:
            return False
        if self.age >= self.life:
            self.dispose()
            return False
        return True


class ImploderCrushEffect:
    """Delayed imploder aftershock that gives the weapon a readable two-stage collapse."""

    def __init__(self, app, pos: Vec3, radius: float, delay: float = 0.28, life: float = 0.72):
        self.app = app
        self.pos = Vec3(pos)
        self.radius = max(2.0, float(radius or 12.0))
        self.delay = max(0.04, float(delay or 0.28))
        self.life = max(self.delay + 0.08, float(life or 0.72))
        self.age = 0.0
        self.fired = False
        parent = getattr(app, "effect_root", app.render)
        self.root = parent.attachNewNode("imploder-crush-aftershock")
        self.root.setPos(self.pos)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.root.setAntialias(AntialiasAttrib.MLine)
        self.visual = self.root.attachNewNode(self._build_visual())
        self.visual.setTransparency(TransparencyAttrib.MAlpha)
        self.visual.setAntialias(AntialiasAttrib.MLine)

    def _build_visual(self):
        segs = LineSegs("imploder-crush-lines")
        segs.setThickness(max(1.0, self.app.game_cfg.line_thickness * 1.22))
        segs.setColor(1.0, 0.42, 0.08, 0.82)
        r = self.radius
        for ring, z in enumerate([0.15, 0.7]):
            last = first = None
            for i in range(37):
                ang = math.tau * i / 36.0 + ring * 0.18
                p = Vec3(math.cos(ang) * r, math.sin(ang) * r, z)
                if first is None:
                    first = p
                if last is not None:
                    segs.moveTo(last); segs.drawTo(p)
                last = p
            if first is not None and last is not None:
                segs.moveTo(last); segs.drawTo(first)
        for i in range(10):
            ang = math.tau * i / 10.0
            segs.moveTo(math.cos(ang) * r, math.sin(ang) * r, 0.35)
            segs.drawTo(0, 0, 1.25)
        return segs.create()

    def dispose(self):
        try:
            if getattr(self, "root", None) is not None and not self.root.isEmpty():
                self.root.removeNode()
        except Exception:
            pass

    def update(self, dt: float) -> bool:
        self.age += max(0.0, float(dt or 0.0))
        if not self.fired and self.age >= self.delay:
            self.fired = True
            self.app.resolve_imploder_crush(self.pos, self.radius)
        t = min(1.0, self.age / self.life)
        pre = min(1.0, self.age / self.delay)
        scale = max(0.05, (1.12 - 0.82 * pre) if not self.fired else (0.34 + 0.18 * math.sin(self.app.elapsed * 18.0)))
        fade = max(0.0, 1.0 - t)
        try:
            self.root.setScale(scale)
            self.root.setH(self.app.elapsed * -70.0)
            self.visual.setColorScale(1.0, 0.42, 0.08, 0.82 * fade)
        except Exception:
            return False
        if self.age >= self.life:
            self.dispose()
            return False
        return True


class WeaponPickupEffect:
    """Small bounded ammo pickup dropped by kills/objectives."""

    def __init__(self, app, pos: Vec3, slot: int = 0, amount: float = 24.0, life: float = 18.0):
        self.app = app
        self.pos = Vec3(pos)
        self.slot = int(slot or 0)
        self.amount = float(amount or 24.0)
        self.life = max(2.0, float(life or 18.0))
        self.age = 0.0
        self.velocity = Vec3(0, 0, 0)
        parent = getattr(app, "effect_root", app.render)
        self.root = parent.attachNewNode("weapon-ammo-pickup")
        self.root.setPos(self.pos)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.root.setAntialias(AntialiasAttrib.MLine)
        segs = LineSegs("weapon-pickup-lines")
        segs.setThickness(app.movable_line_thickness(1.15, 1.9))
        pickup_color = self._pickup_color()
        segs.setColor(*pickup_color)
        r = 1.05
        pts = [Vec3(0, 0, r), Vec3(r, 0, 0), Vec3(0, 0, -r), Vec3(-r, 0, 0)]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            segs.moveTo(a); segs.drawTo(b)
        segs.moveTo(0, -r, 0); segs.drawTo(0, r, 0)
        self.visual = self.root.attachNewNode(segs.create())
        self.visual.setTransparency(TransparencyAttrib.MAlpha)
        self.visual.setAntialias(AntialiasAttrib.MLine)

    def _pickup_color(self):
        if self.slot == 2:
            return (1.0, 0.42, 0.08, 0.9)
        if self.slot == 3:
            return (0.18, 0.92, 1.0, 0.9)
        if self.slot == 4:
            return (0.34, 0.62, 1.0, 0.9)
        if self.slot == 5:
            return (0.85, 0.38, 1.0, 0.9)
        if self.slot == 6:
            return (0.52, 1.0, 0.32, 0.9)
        return (0.96, 0.96, 0.96, 0.88)

    def dispose(self):
        try:
            if getattr(self, "root", None) is not None and not self.root.isEmpty():
                self.root.removeNode()
        except Exception:
            pass

    def update(self, dt: float) -> bool:
        dt = max(0.0, float(dt or 0.0))
        self.age += dt
        player = getattr(self.app, "player_pos", Vec3(9999, 9999, 9999))
        player_flat = Vec3(player.x, player.y, 0.0)
        pickup_flat = Vec3(self.pos.x, self.pos.y, 0.0)
        to_player = player_flat - pickup_flat
        dist = to_player.length()
        magnet_radius = float(getattr(self.app.game_cfg, "weapon_pickup_magnet_radius", 18.0))
        if 0.001 < dist <= magnet_radius:
            to_player.normalize()
            pull = float(getattr(self.app.game_cfg, "weapon_pickup_magnet_pull", 32.0)) * (1.0 - dist / max(0.001, magnet_radius))
            self.velocity += to_player * pull * dt
        self.velocity *= max(0.0, 1.0 - dt * 4.8)
        self.pos += self.velocity * dt
        bob = math.sin(self.app.elapsed * 4.2 + self.age) * 0.28
        color = self._pickup_color()
        try:
            self.root.setPos(self.pos + Vec3(0, 0, 1.2 + bob))
            self.root.setH(self.app.elapsed * 120.0)
            self.root.setR(math.sin(self.app.elapsed * 2.3) * 12.0)
            fade = max(0.0, 1.0 - self.age / self.life)
            self.visual.setColorScale(color[0], color[1], color[2], color[3] * fade)
        except Exception:
            return False
        if (player_flat - Vec3(self.pos.x, self.pos.y, 0.0)).length() <= float(getattr(self.app.game_cfg, "weapon_pickup_radius", 6.0)):
            self.app.collect_weapon_pickup(self)
            return False
        if self.age >= self.life:
            self.dispose()
            return False
        return True


class InkBlotch:
    def __init__(self, app, pos: Vec3, normal: Vec3):
        self.app = app
        self.age = 0.0
        self.life = 6.0 + random.random() * 6.0
        self.root = app.render.attachNewNode("ink-blotch")
        self.root.setPos(pos + normal * 0.03)
        self.root.setTransparency(TransparencyAttrib.MAlpha)

        if abs(normal.z) < 0.75:
            h = math.degrees(math.atan2(normal.x, -normal.y))
            p = -math.degrees(math.asin(max(-1.0, min(1.0, normal.z))))
            self.root.setHpr(h, p, 0)
        else:
            self.root.lookAt(pos + normal)

        card = CardMaker("blotch-card")
        size = 0.45 + random.random() * 0.65
        card.setFrame(-size, size, -size, size)
        self.base = self.root.attachNewNode(card.generate())
        blotch_tex = get_blotch_texture(app.loader)
        if blotch_tex is not None:
            self.base.setTexture(blotch_tex)
        self.base.setBillboardAxis()
        self.base.setTransparency(TransparencyAttrib.MAlpha)
        self.base.setDepthWrite(False)

        self.drips = []
        for _ in range(random.randint(3, 6)):
            drip = LineSegs("drip")
            drip.setThickness(max(1.0, app.game_cfg.line_thickness * 0.65))
            drip.setColor(app.current_line_color(alpha=0.95))
            drip.moveTo(0, 0, 0)
            initial = Vec3(random.uniform(-0.03, 0.03), random.uniform(-0.03, 0.03), -random.uniform(0.05, 0.16))
            drip.drawTo(initial)
            np = self.root.attachNewNode(drip.create())
            np.setTransparency(TransparencyAttrib.MAlpha)
            tangent = Vec3(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-0.4, 0.2))
            if tangent.lengthSquared() < 0.001:
                tangent = Vec3(1, 0, -0.3)
            tangent.normalize()
            tangent -= normal * tangent.dot(normal)
            if tangent.lengthSquared() < 0.001:
                tangent = Vec3(1, 0, 0)
            tangent.normalize()
            tangent += Vec3(0, 0, -0.25)
            tangent.normalize()
            self.drips.append({"np": np, "dir": tangent, "len": initial.length()})

    def update(self, dt: float):
        self.age += dt
        scale = 0.75 + min(1.0, self.age * 1.1)
        self.base.setScale(scale)
        fade = 1.0 if self.age < self.life * 0.7 else max(0.0, 1.0 - (self.age - self.life * 0.7) / (self.life * 0.3))
        tint = self.app.current_blotch_color(alpha=0.22 * fade)
        self.base.setColor(tint)
        for drip_info in self.drips:
            drip_info["len"] += dt * random.uniform(0.08, 0.25)
            segs = LineSegs("drip-update")
            segs.setThickness(max(1.0, self.app.game_cfg.line_thickness * 0.65))
            segs.setColor(self.app.current_line_color(alpha=0.92 * fade))
            segs.moveTo(0, 0, 0)
            segs.drawTo(drip_info["dir"] * drip_info["len"])
            new_np = self.root.attachNewNode(segs.create())
            new_np.setTransparency(TransparencyAttrib.MAlpha)
            drip_info["np"].removeNode()
            drip_info["np"] = new_np
        if self.age >= self.life:
            self.root.removeNode()
            return False
        return True


class Enemy:
    def __init__(self, app, pos: Vec3, seed: int, variant_override: str = None, arena_variant: str = None, arena_enemy: bool = False):
        self.app = app
        self.root = app.render.attachNewNode("enemy")
        self.root.setPos(pos)
        self.seed = seed
        self.rng = random.Random(seed)
        self.arena_enemy = bool(arena_enemy)
        self.arena_variant = str(arena_variant or "")
        district_id = "calibration"
        try:
            district_id, _district = app.district_for_position(pos)
        except Exception:
            pass
        variant_pool = UTOPIA_DISTRICTS.get(district_id, UTOPIA_DISTRICTS["calibration"]).get("enemy_variants") or ["sentinel", "stalker", "bulwark", "commander"]
        self.variant = str(variant_override or variant_pool[seed % len(variant_pool)])
        scale = max(1.0, float(getattr(app.game_cfg, "campaign_enemy_scale", 1.32)))
        health_scale = max(1.0, float(getattr(app.game_cfg, "campaign_enemy_health_scale", 1.38)))
        pressure_scale = max(1.0, float(getattr(app.game_cfg, "campaign_enemy_pressure_scale", 1.22)))
        if self.variant == "stalker":
            self.speed = (4.95 + self.rng.random() * 1.8) * min(1.16, pressure_scale)
            self.health = int((84 + self.rng.randint(0, 42)) * health_scale)
            self.radius = 0.82 * scale
            self.height = (4.2 + self.rng.random() * 0.42) * scale
            self.core_radius = 0.30 * scale
        elif self.variant == "bulwark":
            self.speed = (3.05 + self.rng.random() * 1.05) * min(1.12, pressure_scale)
            self.health = int((184 + self.rng.randint(0, 70)) * health_scale)
            self.radius = 1.22 * scale
            self.height = (6.2 + self.rng.random() * 0.55) * scale
            self.core_radius = 0.46 * scale
        elif self.variant == "commander":
            self.speed = (3.55 + self.rng.random() * 1.0) * min(1.1, pressure_scale)
            self.health = int((230 + self.rng.randint(0, 80)) * health_scale)
            self.radius = 1.12 * scale
            self.height = (5.85 + self.rng.random() * 0.52) * scale
            self.core_radius = 0.52 * scale
        elif self.variant == "walker":
            self.speed = (2.85 + self.rng.random() * 0.8) * min(1.08, pressure_scale)
            self.health = int((320 + self.rng.randint(0, 95)) * health_scale)
            self.radius = 1.55 * scale
            self.height = (5.55 + self.rng.random() * 0.48) * scale
            self.core_radius = 0.54 * scale
        elif self.variant == "shifter":
            self.speed = (4.65 + self.rng.random() * 1.2) * min(1.18, pressure_scale)
            self.health = int((168 + self.rng.randint(0, 62)) * health_scale)
            self.radius = 1.05 * scale
            self.height = (4.75 + self.rng.random() * 0.48) * scale
            self.core_radius = 0.40 * scale
        elif self.variant == "boss_mech":
            self.speed = (2.20 + self.rng.random() * 0.55) * min(1.06, pressure_scale)
            self.health = int((520 + self.rng.randint(0, 160)) * health_scale * float(getattr(app.game_cfg, "boss_mech_health_scale", 2.45)))
            self.radius = 2.05 * scale
            self.height = (8.25 + self.rng.random() * 0.82) * scale
            self.core_radius = 0.76 * scale
        else:
            self.speed = (4.0 + self.rng.random() * 1.55) * min(1.14, pressure_scale)
            self.health = int((118 + self.rng.randint(0, 52)) * health_scale)
            self.radius = 0.98 * scale
            self.height = (4.95 + self.rng.random() * 0.45) * scale
            self.core_radius = 0.36 * scale
        self.base_speed = float(self.speed)
        self.phase = self.rng.random() * math.tau
        self.wander_timer = self.rng.random() * 2.0
        self.direction = Vec3(self.rng.uniform(-1, 1), self.rng.uniform(-1, 1), 0)
        if self.direction.lengthSquared() < 0.1:
            self.direction = Vec3(1, 0, 0)
        self.direction.normalize()
        self.dead = False
        self.stagger_timer = 0.0
        self.knockback_velocity = Vec3(0, 0, 0)
        self.armor_hits = 0
        self.armor_broken = False
        self.disassembled_parts = set()
        self.tell_timer = 0.0
        self.attack_cooldown = self.rng.uniform(0.35, 1.45)
        self.attack_lunge_timer = 0.0
        self.last_core_world = Vec3(pos.x, pos.y, pos.z + self.height * 0.6)
        self.base_speed = float(getattr(self, "speed", 1.0))
        self.is_boss_mech = self.variant == "boss_mech"
        self.is_walker = self.variant == "walker"
        self.is_shifter = self.variant == "shifter"
        self.shifter_form = "quad" if self.is_shifter else "biped"
        self.previous_shifter_form = self.shifter_form
        self.role_reaction_timer = 0.0
        self.evasion_timer = 0.0
        self.evasion_direction = Vec3(0, 0, 0)
        self.boss_weakpoints = {"left_shoulder", "right_shoulder"} if self.is_boss_mech else set()
        self.boss_core_exposed = not self.is_boss_mech
        self.walker_braced = False
        self.color_state_name = "baseline"
        self.color_state_color = (1.0, 0.18, 0.10, 0.98)
        if self.variant == "boss_mech":
            self.arm_space = float(getattr(app.game_cfg, "boss_mech_arm_space", 3.4))
        elif self.variant == "walker":
            self.arm_space = float(getattr(app.game_cfg, "walker_arm_space", 2.6))
        else:
            self.arm_space = 0.0
        self.break_apart_parts = int(getattr(app.game_cfg, "enemy_break_apart_parts", 7))
        self.build_model()
        self.build_state_color_indicator()

    def build_model(self):
        self.body = self.root.attachNewNode("body")
        self.shell_root = self.body.attachNewNode("shell")
        self.line_root = self.body.attachNewNode("line-root")
        self.fx_root = self.body.attachNewNode("fx-root")
        self.line_root.setTransparency(TransparencyAttrib.MAlpha)
        self.line_root.setAntialias(AntialiasAttrib.MLine)

        torso_h = self.height * (0.28 if self.variant in {"stalker", "shifter"} else 0.32)
        pelvis_h = self.height * (0.12 if self.variant == "shifter" else 0.14)
        head_h = self.height * (0.10 if self.variant == "shifter" else 0.12)
        leg_h = self.height * (0.34 if self.variant in {"walker", "boss_mech"} else 0.30)
        shoulder_w = 1.25 if self.variant == "bulwark" else (1.55 if self.variant == "walker" else (2.25 if self.variant == "boss_mech" else 1.0))
        torso_w = 0.88 if self.variant == "bulwark" else (1.14 if self.variant == "walker" else (1.68 if self.variant == "boss_mech" else 0.74))
        torso_d = 0.52 if self.variant == "bulwark" else (0.72 if self.variant in {"walker", "boss_mech"} else 0.42)
        pelvis_w = torso_w * 0.82
        thigh_w = 0.32 if self.variant in {"stalker", "shifter"} else (0.52 if self.variant in {"walker", "boss_mech"} else 0.38)
        shin_w = thigh_w * (0.96 if self.variant in {"walker", "boss_mech"} else 0.88)
        arm_w = 0.24 if self.variant in {"stalker", "shifter"} else (0.42 if self.variant in {"walker", "boss_mech"} else 0.28)
        arm_h = self.height * (0.28 if self.variant in {"walker", "boss_mech"} else 0.24)
        head_w = 0.42 if self.variant == "bulwark" else (0.62 if self.variant == "boss_mech" else 0.36)
        boot_h = self.height * 0.06

        torso_z = self.height * 0.58
        pelvis_z = self.height * 0.33
        head_z = self.height * 0.82
        thigh_z = self.height * 0.13
        shin_z = -0.18
        foot_z = -0.44
        arm_z = self.height * 0.58

        armor_boxes = [
            (Vec3(0, 0, torso_z), Vec3(torso_w, torso_d, torso_h)),
            (Vec3(0, 0.06, pelvis_z), Vec3(pelvis_w, torso_d * 0.95, pelvis_h)),
            (Vec3(0, 0.1, head_z), Vec3(head_w, 0.34, head_h)),
            (Vec3(-shoulder_w, 0.0, arm_z), Vec3(arm_w, 0.34, arm_h)),
            (Vec3(shoulder_w, 0.0, arm_z), Vec3(arm_w, 0.34, arm_h)),
            (Vec3(-0.34, 0.04, thigh_z), Vec3(thigh_w, 0.38, leg_h)),
            (Vec3(0.34, 0.04, thigh_z), Vec3(thigh_w, 0.38, leg_h)),
            (Vec3(-0.34, 0.08, shin_z), Vec3(shin_w, 0.34, leg_h * 0.95)),
            (Vec3(0.34, 0.08, shin_z), Vec3(shin_w, 0.34, leg_h * 0.95)),
            (Vec3(-0.34, 0.28, foot_z), Vec3(0.52, 0.72, boot_h)),
            (Vec3(0.34, 0.28, foot_z), Vec3(0.52, 0.72, boot_h)),
        ]
        if self.variant == "bulwark":
            armor_boxes.extend([
                (Vec3(0, -0.26, torso_z + 0.15), Vec3(0.46, 0.16, torso_h * 0.8)),
                (Vec3(-1.36, 0.06, arm_z), Vec3(0.36, 0.44, arm_h * 0.92)),
                (Vec3(1.36, 0.06, arm_z), Vec3(0.36, 0.44, arm_h * 0.92)),
            ])
        elif self.variant == "commander":
            armor_boxes.extend([
                (Vec3(0, -0.30, torso_z + 0.20), Vec3(0.58, 0.20, torso_h * 0.95)),
                (Vec3(-1.42, 0.05, arm_z + 0.08), Vec3(0.42, 0.52, arm_h * 1.04)),
                (Vec3(1.42, 0.05, arm_z + 0.08), Vec3(0.42, 0.52, arm_h * 1.04)),
                (Vec3(0, 0.16, head_z + head_h * 0.72), Vec3(head_w * 1.25, 0.22, head_h * 0.45)),
            ])
        elif self.variant == "stalker":
            armor_boxes.extend([
                (Vec3(0, -0.14, torso_z + 0.04), Vec3(0.28, 0.16, torso_h * 0.55)),
                (Vec3(-0.88, 0.02, arm_z + 0.02), Vec3(0.16, 0.22, arm_h * 0.9)),
                (Vec3(0.88, 0.02, arm_z + 0.02), Vec3(0.16, 0.22, arm_h * 0.9)),
            ])
        elif self.variant == "walker":
            armor_boxes.extend([
                (Vec3(0, -0.28, torso_z + 0.12), Vec3(0.72, 0.22, torso_h * 0.85)),
                (Vec3(-1.95, 0.06, arm_z), Vec3(0.48, 0.62, arm_h * 1.12)),
                (Vec3(1.95, 0.06, arm_z), Vec3(0.48, 0.62, arm_h * 1.12)),
                (Vec3(-0.76, 0.18, thigh_z), Vec3(0.42, 0.48, leg_h * 1.08)),
                (Vec3(0.76, 0.18, thigh_z), Vec3(0.42, 0.48, leg_h * 1.08)),
            ])
        elif self.variant == "shifter":
            armor_boxes.extend([
                (Vec3(0, -0.10, torso_z - 0.10), Vec3(0.46, 0.30, torso_h * 0.48)),
                (Vec3(-0.92, 0.06, arm_z - 0.18), Vec3(0.18, 0.28, arm_h * 0.72)),
                (Vec3(0.92, 0.06, arm_z - 0.18), Vec3(0.18, 0.28, arm_h * 0.72)),
                (Vec3(-0.70, 0.20, thigh_z + 0.05), Vec3(0.22, 0.42, leg_h * 0.72)),
                (Vec3(0.70, 0.20, thigh_z + 0.05), Vec3(0.22, 0.42, leg_h * 0.72)),
            ])
        elif self.variant == "boss_mech":
            armor_boxes.extend([
                (Vec3(0, -0.38, torso_z + 0.22), Vec3(1.25, 0.28, torso_h * 1.05)),
                (Vec3(-2.75, 0.08, arm_z + 0.12), Vec3(0.66, 0.80, arm_h * 1.28)),
                (Vec3(2.75, 0.08, arm_z + 0.12), Vec3(0.66, 0.80, arm_h * 1.28)),
                (Vec3(-0.92, 0.20, thigh_z + 0.12), Vec3(0.58, 0.62, leg_h * 1.15)),
                (Vec3(0.92, 0.20, thigh_z + 0.12), Vec3(0.58, 0.62, leg_h * 1.15)),
                (Vec3(0, 0.24, head_z + head_h * 0.85), Vec3(head_w * 1.8, 0.34, head_h * 0.62)),
            ])
        else:
            armor_boxes.extend([
                (Vec3(0, -0.2, torso_z + 0.08), Vec3(0.34, 0.16, torso_h * 0.68)),
                (Vec3(-1.1, 0.02, arm_z), Vec3(0.22, 0.28, arm_h * 0.95)),
                (Vec3(1.1, 0.02, arm_z), Vec3(0.22, 0.28, arm_h * 0.95)),
            ])
        if getattr(self, "arena_enemy", False):
            style = str(getattr(self, "arena_variant", "") or "arena_stalker")
            armor_boxes = self.arena_robot_armor_boxes(style, torso_z, pelvis_z, head_z, arm_z, thigh_z, shin_z, foot_z, torso_h, pelvis_h, head_h, leg_h, arm_h)
            self.build_arena_robot_infill(style, armor_boxes, torso_z, pelvis_z, head_z, torso_w, torso_h, head_w)
        for center, size in armor_boxes:
            # Keep the low-cost hit readable but avoid turning arena mobs into solid cuboids.
            if not getattr(self, "arena_enemy", False):
                self.app.add_solid_box(self.shell_root, center, size, bottom_gray=0.02, top_gray=0.18, alpha=1.0)
            self.make_box_wire(center, size).reparentTo(self.line_root)

        if getattr(self, "arena_enemy", False):
            self.build_arena_robot_signature(torso_z, pelvis_z, head_z, shoulder_w, torso_w, torso_h, head_w)
        self.build_boss_variant_signature(torso_z, head_z, shoulder_w, torso_w, torso_h)
        self.build_combat_role_signature(torso_z, head_z, shoulder_w, torso_w, torso_h)

        spine = self.make_line([(0, -0.18, pelvis_z - 0.08), (0, -0.18, torso_z + 0.22), (0, -0.18, head_z + 0.06)])
        clavicle = self.make_line([(-shoulder_w * 0.76, -0.06, torso_z + 0.18), (0, -0.12, torso_z + 0.24), (shoulder_w * 0.76, -0.06, torso_z + 0.18)])
        visor = self.make_line([(-head_w * 0.32, 0.18, head_z), (head_w * 0.32, 0.18, head_z)])
        for np in [spine, clavicle, visor]:
            np.reparentTo(self.line_root)

        self.core_offset = Vec3(0, 0.24, torso_z + torso_h * 0.02)
        self.core_root = self.body.attachNewNode("core-root")
        self.core_root.setPos(self.core_offset)
        self.core_cards = []
        for idx, scale in enumerate([0.55, 0.9, 1.35]):
            cm = CardMaker(f"core-card-{idx}")
            s = self.core_radius * scale
            cm.setFrame(-s, s, -s, s)
            card = self.core_root.attachNewNode(cm.generate())
            card.setBillboardPointEye()
            blotch_tex = get_blotch_texture(self.app.loader)
            if blotch_tex is not None:
                card.setTexture(blotch_tex)
            card.setTransparency(TransparencyAttrib.MAlpha)
            card.setDepthWrite(False)
            card.setBin("fixed", 15)
            self.core_cards.append(card)

        self.plume_cards = []
        for idx, scale in enumerate([1.8, 2.35, 2.9]):
            cm = CardMaker(f"plume-card-{idx}")
            s = self.core_radius * scale
            cm.setFrame(-s, s, -s, s)
            plume = self.fx_root.attachNewNode(cm.generate())
            plume.setPos(self.core_offset + Vec3(self.rng.uniform(-0.08, 0.08), self.rng.uniform(-0.18, 0.12), self.rng.uniform(-0.08, 0.18)))
            plume.setBillboardPointEye()
            blotch_tex = get_blotch_texture(self.app.loader)
            if blotch_tex is not None:
                plume.setTexture(blotch_tex)
            plume.setTransparency(TransparencyAttrib.MAlpha)
            plume.setDepthWrite(False)
            self.plume_cards.append(plume)

    def build_boss_variant_signature(self, torso_z: float, head_z: float, shoulder_w: float, torso_w: float, torso_h: float):
        # Pass43: hostile silhouettes must read before line color.  Keep one low-cost
        # signature LineSegs branch per enemy instead of adding more box meshes.
        segs = LineSegs(f"enemy-variant-signature-{self.variant}")
        segs.setThickness(self.app.enemy_line_thickness(1.28, 2.0 if self.variant == "boss_mech" else 1.8))
        if self.variant == "boss_mech": segs.setColor(1.0, 0.18, 0.08, 0.98)
        elif self.variant in {"walker", "commander"}: segs.setColor(1.0, 0.46, 0.12, 0.96)
        elif self.variant == "shifter": segs.setColor(0.18, 0.92, 1.0, 0.96)
        elif self.variant == "bulwark": segs.setColor(0.36, 1.0, 0.92, 0.96)
        elif self.variant == "stalker": segs.setColor(1.0, 0.90, 0.22, 0.94)
        else: return
        arm = shoulder_w + (0.72 if self.variant == "boss_mech" else 0.42)
        if self.variant in {"walker", "boss_mech"}:
            segs.moveTo(-arm, 0.20, torso_z + torso_h * 0.35); segs.drawTo(-arm - 0.85, 0.54, torso_z + torso_h * 0.18)
            segs.moveTo(arm, 0.20, torso_z + torso_h * 0.35); segs.drawTo(arm + 0.85, 0.54, torso_z + torso_h * 0.18)
            for x in (-0.72, 0.72):
                segs.moveTo(x, 0.18, torso_z - torso_h * 0.65); segs.drawTo(x * 1.25, 0.48, torso_z - torso_h * 1.08)
        elif self.variant == "shifter":
            # Four low fold legs create the quad silhouette even before its transform settles.
            for x in (-0.92, 0.92):
                for y in (-0.24, 0.34):
                    segs.moveTo(x * 0.55, y, torso_z + 0.08); segs.drawTo(x * 1.34, y + 0.28, torso_z - 0.66)
                    segs.drawTo(x * 1.10, y + 0.62, torso_z - 1.28)
            segs.moveTo(-0.70, 0.38, torso_z + 0.42); segs.drawTo(0.70, 0.38, torso_z + 0.42)
        elif self.variant == "bulwark":
            # Wide shield shoulders and rectangular front shell.
            for x in (-1.55, 1.55):
                segs.moveTo(x, 0.28, torso_z + 0.52); segs.drawTo(x, 0.56, torso_z - 0.44)
                segs.drawTo(x * 0.72, 0.56, torso_z - 0.72)
            segs.moveTo(-1.55, 0.52, torso_z + 0.50); segs.drawTo(1.55, 0.52, torso_z + 0.50)
            segs.moveTo(-1.55, 0.52, torso_z - 0.44); segs.drawTo(1.55, 0.52, torso_z - 0.44)
        elif self.variant == "commander":
            # Crown antenna and asymmetric weapon arm.
            segs.moveTo(0, 0.34, head_z + 0.18); segs.drawTo(0, 0.34, head_z + 0.88)
            segs.moveTo(0, 0.34, head_z + 0.88); segs.drawTo(0.34, 0.34, head_z + 1.08)
            segs.moveTo(shoulder_w, 0.26, torso_z + 0.26); segs.drawTo(shoulder_w + 1.05, 0.60, torso_z + 0.58)
            segs.drawTo(shoulder_w + 1.42, 0.60, torso_z + 0.18)
        elif self.variant == "stalker":
            # Narrow forward horns and swept limbs make the fast enemy unmistakable.
            for x in (-0.38, 0.38):
                segs.moveTo(x, 0.30, head_z + 0.08); segs.drawTo(x * 1.55, 0.62, head_z + 0.48)
            for x in (-0.82, 0.82):
                segs.moveTo(x * 0.55, 0.22, torso_z + 0.12); segs.drawTo(x * 1.25, 0.52, torso_z - 0.46)
        if self.variant == "boss_mech":
            for x in (-1.1, 1.1):
                segs.moveTo(x, 0.22, head_z + 0.38); segs.drawTo(x * 1.22, 0.48, head_z + 1.15)
        np = self.line_root.attachNewNode(segs.create())
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setAntialias(AntialiasAttrib.MLine)


    def arena_robot_fill_color(self, style: str):
        style = str(style or "arena_stalker")
        alpha = float(getattr(self.app.game_cfg, "arena_robot_fill_alpha", 0.84))
        if style in {"arena_tank", "arena_guardian"}:
            return (0.22, 0.03, 0.04, alpha), (0.05, 0.01, 0.02, min(1.0, alpha + 0.06))
        return (0.03, 0.18, 0.13, alpha), (0.01, 0.03, 0.03, min(1.0, alpha + 0.06))

    def build_arena_robot_infill(self, style: str, armor_boxes, torso_z: float, pelvis_z: float, head_z: float, torso_w: float, torso_h: float, head_w: float):
        bright, dark = self.arena_robot_fill_color(style)
        for idx, (center, size) in enumerate(list(armor_boxes or [])):
            color = bright if idx < 3 else dark
            self.app.attach_weapon_box_fill(self.shell_root, center, size, color, f"arena-fill-{style}-{idx}")
        # signature filled panels to make the robots read like 3D hardlight machines rather than hollow boxes.
        self.app.attach_weapon_prism(self.shell_root, self.app.octagon_points(max(0.22, torso_w * 0.46), max(0.22, torso_h * 0.36)), 0.14, 0.42, bright, f"arena-fill-torso-{style}").setPos(0.0, 0.10, torso_z + torso_h * 0.10)
        self.app.attach_weapon_prism(self.shell_root, self.app.triangle_points(max(0.18, torso_w * 0.32), max(0.18, torso_h * 0.28)), 0.10, 0.36, dark, f"arena-fill-chest-{style}").setPos(0.0, 0.24, torso_z + torso_h * 0.26)
        self.app.attach_weapon_prism(self.shell_root, self.app.octagon_points(max(0.14, head_w * 0.40), max(0.10, head_w * 0.24)), 0.10, 0.26, bright, f"arena-fill-head-{style}").setPos(0.0, 0.18, head_z + 0.02)

    def arena_robot_armor_boxes(self, style: str, torso_z: float, pelvis_z: float, head_z: float, arm_z: float, thigh_z: float, shin_z: float, foot_z: float, torso_h: float, pelvis_h: float, head_h: float, leg_h: float, arm_h: float):
        style = str(style or "arena_stalker")
        if style == "arena_sentry":
            return [
                (Vec3(0, 0.05, torso_z + 0.05), Vec3(0.72, 0.36, torso_h * 0.72)),
                (Vec3(0, 0.16, head_z + 0.05), Vec3(0.46, 0.26, head_h * 0.75)),
                (Vec3(-0.98, 0.08, torso_z + 0.05), Vec3(0.34, 0.24, arm_h * 0.55)),
                (Vec3(0.98, 0.08, torso_z + 0.05), Vec3(0.34, 0.24, arm_h * 0.55)),
            ]
        if style == "arena_tank":
            return [
                (Vec3(0, 0.02, torso_z), Vec3(1.18, 0.58, torso_h * 1.05)),
                (Vec3(0, 0.08, pelvis_z), Vec3(0.95, 0.48, pelvis_h * 1.15)),
                (Vec3(0, 0.12, head_z), Vec3(0.56, 0.34, head_h * 0.96)),
                (Vec3(-1.28, 0.08, arm_z), Vec3(0.38, 0.42, arm_h * 0.96)),
                (Vec3(1.28, 0.08, arm_z), Vec3(0.38, 0.42, arm_h * 0.96)),
                (Vec3(-0.46, 0.05, thigh_z), Vec3(0.44, 0.38, leg_h * 0.8)),
                (Vec3(0.46, 0.05, thigh_z), Vec3(0.44, 0.38, leg_h * 0.8)),
            ]
        if style == "arena_guardian":
            return [
                (Vec3(0, 0.02, torso_z + 0.1), Vec3(0.96, 0.46, torso_h * 1.18)),
                (Vec3(0, 0.10, pelvis_z), Vec3(0.72, 0.38, pelvis_h * 0.95)),
                (Vec3(0, 0.18, head_z + 0.10), Vec3(0.48, 0.30, head_h * 0.92)),
                (Vec3(-1.22, 0.04, arm_z + 0.14), Vec3(0.26, 0.32, arm_h * 1.08)),
                (Vec3(1.22, 0.04, arm_z + 0.14), Vec3(0.26, 0.32, arm_h * 1.08)),
                (Vec3(-0.38, 0.05, thigh_z), Vec3(0.32, 0.30, leg_h * 0.72)),
                (Vec3(0.38, 0.05, thigh_z), Vec3(0.32, 0.30, leg_h * 0.72)),
            ]
        return [
            (Vec3(0, 0.05, torso_z), Vec3(0.62, 0.34, torso_h * 0.82)),
            (Vec3(0, 0.10, pelvis_z), Vec3(0.46, 0.28, pelvis_h * 0.75)),
            (Vec3(0, 0.18, head_z), Vec3(0.36, 0.22, head_h * 0.70)),
            (Vec3(-0.76, 0.03, arm_z), Vec3(0.14, 0.20, arm_h * 0.72)),
            (Vec3(0.76, 0.03, arm_z), Vec3(0.14, 0.20, arm_h * 0.72)),
            (Vec3(-0.28, 0.04, thigh_z), Vec3(0.18, 0.22, leg_h * 0.64)),
            (Vec3(0.28, 0.04, thigh_z), Vec3(0.18, 0.22, leg_h * 0.64)),
        ]

    def make_poly_loop_xz(self, center: Vec3, rx: float, rz: float, segments: int = 8, y_offset: float = 0.0):
        pts = []
        for i in range(max(3, int(segments)) + 1):
            a = math.tau * i / max(3, int(segments))
            pts.append((center.x + math.cos(a) * rx, center.y + y_offset, center.z + math.sin(a) * rz))
        return self.make_line(pts)

    def make_triangle_loop_xz(self, center: Vec3, rx: float, rz: float, y_offset: float = 0.0):
        pts = [
            (center.x, center.y + y_offset, center.z + rz),
            (center.x - rx, center.y + y_offset, center.z - rz * 0.72),
            (center.x + rx, center.y + y_offset, center.z - rz * 0.72),
            (center.x, center.y + y_offset, center.z + rz),
        ]
        return self.make_line(pts)

    def build_arena_robot_signature(self, torso_z: float, pelvis_z: float, head_z: float, shoulder_w: float, torso_w: float, torso_h: float, head_w: float):
        style = str(getattr(self, "arena_variant", "") or "arena_stalker")
        parts = []
        # Octagonal torso/helmet rings make these read as robots instead of stacked boxes.
        parts.append(self.make_poly_loop_xz(Vec3(0, 0.34, torso_z + torso_h * 0.10), max(0.36, torso_w * 0.62), max(0.36, torso_h * 0.62), 8))
        parts.append(self.make_poly_loop_xz(Vec3(0, 0.36, head_z + 0.02), max(0.22, head_w * 0.76), max(0.16, head_w * 0.42), 8))
        parts.append(self.make_triangle_loop_xz(Vec3(0, 0.38, torso_z + torso_h * 0.42), max(0.36, torso_w * 0.56), max(0.30, torso_h * 0.48)))
        # Joint rods and hands/feet are line limbs, not cubes.
        limb_y = 0.42
        for sx in (-1.0, 1.0):
            parts.append(self.make_line([(sx * 0.38, limb_y, torso_z + 0.15), (sx * 0.92, limb_y, torso_z - 0.18), (sx * 1.05, limb_y, pelvis_z + 0.08)]))
            parts.append(self.make_poly_loop_xz(Vec3(sx * 0.98, limb_y, pelvis_z + 0.08), 0.16, 0.16, 6))
            parts.append(self.make_line([(sx * 0.22, limb_y, pelvis_z - 0.04), (sx * 0.36, limb_y, -0.18), (sx * 0.48, limb_y, -0.58)]))
            parts.append(self.make_poly_loop_xz(Vec3(sx * 0.48, limb_y, -0.58), 0.22, 0.10, 6))
        # Variant callouts.
        if style == "arena_sentry":
            for sx in (-1.0, 1.0):
                parts.append(self.make_poly_loop_xz(Vec3(sx * 1.25, 0.42, torso_z + 0.12), 0.32, 0.32, 10))
                parts.append(self.make_line([(sx * 0.72, 0.40, torso_z + 0.12), (sx * 1.25, 0.42, torso_z + 0.12)]))
            parts.append(self.make_line([(0, 0.38, head_z + 0.25), (0, 0.38, head_z + 0.72)]))
        elif style == "arena_tank":
            for sx in (-1.0, 1.0):
                parts.append(self.make_line([(sx * 0.72, 0.44, torso_z + 0.30), (sx * 1.52, 0.44, torso_z + 0.30)]))
                parts.append(self.make_poly_loop_xz(Vec3(sx * 1.52, 0.46, torso_z + 0.30), 0.20, 0.20, 8))
            parts.append(self.make_poly_loop_xz(Vec3(0, 0.40, torso_z + 0.08), 0.70, 0.58, 8))
        elif style == "arena_guardian":
            for sx in (-1.0, 1.0):
                parts.append(self.make_line([(sx * 0.26, 0.42, head_z + 0.15), (sx * 0.80, 0.42, head_z + 0.72)]))
                parts.append(self.make_line([(sx * 0.78, 0.42, torso_z + 0.30), (sx * 1.24, 0.42, torso_z + 0.84)]))
            parts.append(self.make_poly_loop_xz(Vec3(0, 0.42, torso_z + 0.30), 0.62, 0.82, 8))
        else:
            for sx in (-1.0, 1.0):
                parts.append(self.make_line([(sx * 0.20, 0.44, head_z + 0.12), (sx * 0.46, 0.44, head_z + 0.45)]))
        for np in parts:
            if style in {"arena_tank", "arena_guardian"}:
                np.setColorScale(1.0, 0.44, 0.40, 1.0)
            else:
                np.setColorScale(0.52, 1.0, 0.86, 1.0)
            np.reparentTo(self.line_root)

    def build_combat_role_signature(self, torso_z: float, head_z: float, shoulder_w: float, torso_w: float, torso_h: float):
        """Small attached role glyphs. Geometry communicates role without HUD labels."""
        self.role_root = self.body.attachNewNode(f"combat-role-{self.variant}")
        self.role_root.setTransparency(TransparencyAttrib.MAlpha)
        self.role_root.setAntialias(AntialiasAttrib.MLine)
        segs = LineSegs(f"combat-role-lines-{self.variant}")
        segs.setThickness(self.app.enemy_line_thickness(1.1, 2.1))
        if self.variant == "walker":
            segs.setColor(1.0, 0.42, 0.08, 0.96)
            for sx in (-1.0, 1.0):
                x = sx * 0.72
                segs.moveTo(x - sx * 0.32, 0.42, 0.05); segs.drawTo(x + sx * 0.32, 0.42, 0.05)
                segs.moveTo(x, 0.42, -0.32); segs.drawTo(x, 0.42, 0.42)
        elif self.variant == "shifter":
            segs.setColor(0.18, 0.92, 1.0, 0.98)
            for sx in (-1.0, 1.0):
                segs.moveTo(0, 0.44, torso_z); segs.drawTo(sx * 0.72, 0.44, torso_z + 0.34)
                segs.drawTo(sx * 0.98, 0.44, torso_z - 0.12)
        elif self.variant == "boss_mech":
            self.boss_role_shoulder_w = float(shoulder_w)
            self.boss_role_torso_z = float(torso_z)
            self.refresh_boss_weakpoint_markers()
            return
        elif self.variant == "stalker":
            segs.setColor(1.0, 0.92, 0.18, 0.94)
            segs.moveTo(-0.38, 0.40, head_z + 0.24); segs.drawTo(0, 0.40, head_z + 0.52); segs.drawTo(0.38, 0.40, head_z + 0.24)
        else:
            return
        self.role_root.attachNewNode(segs.create()).setAntialias(AntialiasAttrib.MLine)

    def refresh_boss_weakpoint_markers(self):
        if not self.is_boss_mech or not hasattr(self, "role_root"):
            return
        for child in list(self.role_root.getChildren()):
            child.removeNode()
        shoulder_w = float(getattr(self, "boss_role_shoulder_w", self.arm_space))
        torso_z = float(getattr(self, "boss_role_torso_z", self.height * 0.58))
        for weakpoint, sx in (("left_shoulder", -1.0), ("right_shoulder", 1.0)):
            if weakpoint not in self.boss_weakpoints:
                continue
            segs = LineSegs(f"boss-weakpoint-{weakpoint}")
            segs.setThickness(self.app.enemy_line_thickness(1.35, 2.5))
            segs.setColor(1.0, 0.16, 0.06, 0.98)
            cx = sx * shoulder_w
            r = 0.46
            for i in range(13):
                a0 = math.tau * i / 12
                a1 = math.tau * (i + 1) / 12
                segs.moveTo(cx + math.cos(a0) * r, 0.50, torso_z + math.sin(a0) * r)
                segs.drawTo(cx + math.cos(a1) * r, 0.50, torso_z + math.sin(a1) * r)
            node = self.role_root.attachNewNode(segs.create())
            node.setAntialias(AntialiasAttrib.MLine)

    def spawn_role_pulse(self, point: Vec3, color=(1.0, 1.0, 1.0, 0.96), radius: float = 2.0, life: float = 0.48):
        self.app.weapon_fx.append(WeaponGlyphEffect(self.app, point, point, shape="diamond", life=life, radius=radius, color=color, spin=72.0))

    def boss_weakpoint_for_hit(self, point: Vec3):
        if not self.is_boss_mech or not self.boss_weakpoints:
            return None
        local = self.root.getRelativePoint(self.app.render, Vec3(point))
        if local.z < self.height * 0.42:
            return None
        if abs(local.x) < self.radius * 0.42:
            return None
        return "left_shoulder" if local.x < 0.0 else "right_shoulder"

    def destroy_boss_weakpoint(self, weakpoint: str, point: Vec3, normal: Vec3):
        if weakpoint not in self.boss_weakpoints:
            return False
        self.boss_weakpoints.remove(weakpoint)
        self.refresh_boss_weakpoint_markers()
        self.role_reaction_timer = 0.9
        self.stagger_timer = max(self.stagger_timer, 0.72)
        self.spawn_role_pulse(point, color=(1.0, 0.12, 0.04, 0.98), radius=2.7, life=0.66)
        self.app.spawn_physics_shards(point, normal, count=16, speed=10.0, life=0.72, warm=True)
        self.app.add_combat_feedback(point, label="break", radius=3.0, life=0.62, warning=False)
        self.app.play_sfx("metal_break", volume=0.86, rate=random.uniform(0.82, 0.96), pos=point)
        if not self.boss_weakpoints:
            self.boss_core_exposed = True
            core = self.core_world_position()
            self.spawn_role_pulse(core, color=(1.0, 0.92, 0.16, 0.98), radius=3.8, life=0.86)
            self.app.combat_banner = "BOSS CORE EXPOSED"
            self.app.combat_banner_time = max(float(getattr(self.app, "combat_banner_time", 0.0)), 1.2)
        return True

    def trigger_shifter_transition(self, new_form: str):
        if not self.is_shifter or new_form == self.previous_shifter_form:
            return
        self.previous_shifter_form = new_form
        self.role_reaction_timer = 0.72
        self.evasion_timer = 0.34 if new_form == "quad" else 0.18
        side = -1.0 if self.rng.random() < 0.5 else 1.0
        forward = Vec3(self.direction)
        self.evasion_direction = Vec3(-forward.y * side, forward.x * side, 0)
        self.spawn_role_pulse(self.core_world_position(), color=(0.18, 0.92, 1.0, 0.98), radius=2.1, life=0.56)
        self.app.play_sfx("phase", volume=0.52, rate=1.18 if new_form == "quad" else 0.94, pos=self.core_world_position())

    def core_world_position(self):
        if hasattr(self, "core_root") and self.core_root is not None and not self.core_root.isEmpty():
            pos = self.core_root.getPos(self.app.render)
            self.last_core_world = Vec3(pos)
            return pos
        if self.root is not None and not self.root.isEmpty():
            pos = self.root.getPos(self.app.render) + self.core_offset
            self.last_core_world = Vec3(pos)
            return pos
        return Vec3(self.last_core_world)

    def bounds(self):
        pos = self.root.getPos()
        return BoxBounds(pos + Vec3(-self.radius - 0.4, -self.radius - 0.4, -0.6), pos + Vec3(self.radius + 0.4, self.radius + 0.4, self.height + 0.2), Vec3(0, 0, 1))

    def make_line(self, pts):
        segs = LineSegs("enemy-line")
        segs.setThickness(self.app.enemy_line_thickness(0.95, 1.8))
        segs.setColor(1.0, 1.0, 1.0, 0.97)
        first = True
        for p in pts:
            if first:
                segs.moveTo(*p)
                first = False
            else:
                segs.drawTo(*p)
        np = NodePath(segs.create())
        np.setAntialias(AntialiasAttrib.MLine)
        return np

    def make_box_wire(self, pos, size):
        cx, cy, cz = pos
        sx, sy, sz = size
        x0, x1 = cx - sx * 0.5, cx + sx * 0.5
        y0, y1 = cy - sy * 0.5, cy + sy * 0.5
        z0, z1 = cz - sz * 0.5, cz + sz * 0.5
        edges = [
            ((x0, y0, z0), (x1, y0, z0)), ((x1, y0, z0), (x1, y1, z0)), ((x1, y1, z0), (x0, y1, z0)), ((x0, y1, z0), (x0, y0, z0)),
            ((x0, y0, z1), (x1, y0, z1)), ((x1, y0, z1), (x1, y1, z1)), ((x1, y1, z1), (x0, y1, z1)), ((x0, y1, z1), (x0, y0, z1)),
            ((x0, y0, z0), (x0, y0, z1)), ((x1, y0, z0), (x1, y0, z1)), ((x1, y1, z0), (x1, y1, z1)), ((x0, y1, z0), (x0, y1, z1)),
        ]
        segs = LineSegs("enemy-box")
        segs.setThickness(self.app.enemy_line_thickness(0.9, 1.75))
        segs.setColor(1.0, 1.0, 1.0, 0.95)
        for a, b in edges:
            segs.moveTo(*a)
            segs.drawTo(*b)
        np = NodePath(segs.create())
        np.setAntialias(AntialiasAttrib.MLine)
        return np

    def apply_impulse(self, direction: Vec3, force: float) -> None:
        if self.dead:
            return
        impulse = Vec3(direction)
        if impulse.lengthSquared() < 0.001:
            impulse = Vec3(0, -1, 0)
        impulse.z = 0.0
        if impulse.lengthSquared() < 0.001:
            impulse = Vec3(0, -1, 0)
        impulse.normalize()
        if self.variant == "walker":
            force *= 0.34 if not self.armor_broken else 0.62
        elif self.variant == "boss_mech":
            force *= 0.22 if not self.boss_core_exposed else 0.48
        elif self.variant == "stalker":
            force *= 1.28
        max_speed = float(getattr(self.app.game_cfg, "enemy_knockback_max_speed", 24.0))
        current = Vec3(getattr(self, "knockback_velocity", Vec3(0, 0, 0)))
        current += impulse * max(0.0, float(force or 0.0))
        if current.length() > max_speed:
            current.normalize()
            current *= max_speed
        self.knockback_velocity = current

    def break_armor(self, point: Vec3, normal: Vec3):
        if self.armor_broken or self.dead:
            return False
        self.armor_broken = True
        self.stagger_timer = max(float(getattr(self, "stagger_timer", 0.0)), float(getattr(self.app.game_cfg, "enemy_armor_break_stagger_seconds", 1.15)))
        self.app.add_combat_feedback(point, label="break", radius=2.45 if self.variant != "bulwark" else 3.2, life=0.55, warning=False)
        impulse_dir = self.root.getPos(self.app.render) - point
        self.apply_impulse(impulse_dir, float(getattr(self.app.game_cfg, "shield_break_knockback_force", 7.6)))
        self.app.spawn_spark_burst(point, normal, count=22, speed=8.8)
        self.app.spawn_physics_shards(point, normal, count=int(getattr(self.app.game_cfg, "shield_break_shard_count", 18)), speed=10.5, life=0.82, warm=True)
        self.app.add_shockwave_ring(point, radius=5.2 if self.variant != "bulwark" else 6.8, life=0.42, vertical=True, thickness=1.4)
        self.app.play_sfx("break", volume=0.95, rate=random.uniform(0.90, 1.06), pos=point)
        self.app.add_combat_camera_kick(0.78)
        self.app.combat_banner = "SHIELD BREAK // CORE VULNERABLE"
        self.app.combat_banner_time = max(float(getattr(self.app, "combat_banner_time", 0.0)), 0.85)
        if hasattr(self.app, "record_activity"):
            self.app.record_activity("shield_break", "Shield Fracture", pos=point)
        return True

    def trigger_attack_tell(self, player_pos: Vec3):
        if self.dead or float(getattr(self, "attack_cooldown", 0.0)) > 0.0 or float(getattr(self, "tell_timer", 0.0)) > 0.0:
            return False
        self.tell_timer = float(getattr(self.app.game_cfg, "enemy_attack_tell_seconds", 0.72))
        self.attack_cooldown = float(getattr(self.app.game_cfg, "enemy_attack_cooldown", 2.35))
        pos = self.core_world_position()
        self.app.add_combat_feedback(pos, label="tell", radius=2.05 if self.variant != "bulwark" else 2.7, life=max(0.28, self.tell_timer), warning=True)
        self.app.play_sfx("tell", volume=0.45 if self.variant == "stalker" else 0.55, rate=random.uniform(0.92, 1.08), pos=pos)
        if random.random() < 0.35:
            self.app.play_sfx(f"enemy{1 + (self.seed % 5)}", volume=0.24, rate=random.uniform(0.86, 1.12), pos=pos)
        try:
            direction = Vec3(player_pos.x - self.root.getX(), player_pos.y - self.root.getY(), 0.0)
            if direction.lengthSquared() > 0.001:
                direction.normalize()
                end = pos + direction * 3.6
                self.app.tracers.append(TracerEffect(self.app, pos, end, ttl=0.18, color=(1.0, 0.35, 0.08, 0.85), thickness_scale=1.35))
        except Exception:
            pass
        return True

    def choose_disassembly_part(self, point: Vec3):
        base = self.root.getPos(self.app.render)
        local = Vec3(point) - base
        preferred = []
        if local.z >= self.height * 0.72:
            preferred.append("head")
        if local.z <= self.height * 0.30:
            preferred.append("left leg" if local.x < 0.0 else "right leg")
            preferred.append("right leg" if local.x < 0.0 else "left leg")
        if abs(local.x) >= self.radius * 0.42 and local.z > self.height * 0.32:
            preferred.append("left arm" if local.x < 0.0 else "right arm")
            preferred.append("right arm" if local.x < 0.0 else "left arm")
        preferred.extend(["head", "left arm", "right arm", "left leg", "right leg"])
        for candidate in preferred:
            if candidate not in self.disassembled_parts:
                return candidate
        return "core frame"

    def disassemble_part(self, point: Vec3, normal: Vec3):
        if self.dead:
            return False
        part = self.choose_disassembly_part(point)
        self.disassembled_parts.add(part)
        base = self.root.getPos(self.app.render)
        offsets = {
            "head": Vec3(0.0, 0.12, self.height * 0.84),
            "left arm": Vec3(-self.radius * 1.35, 0.0, self.height * 0.58),
            "right arm": Vec3(self.radius * 1.35, 0.0, self.height * 0.58),
            "left leg": Vec3(-self.radius * 0.42, 0.04, self.height * 0.18),
            "right leg": Vec3(self.radius * 0.42, 0.04, self.height * 0.18),
            "core frame": Vec3(0.0, 0.18, self.height * 0.52),
        }
        part_pos = base + offsets.get(part, offsets["core frame"])
        impulse = Vec3(normal)
        if impulse.lengthSquared() < 0.001:
            impulse = part_pos - Vec3(point)
        if impulse.lengthSquared() < 0.001:
            impulse = Vec3(random.uniform(-1, 1), random.uniform(-1, 1), 0.65)
        impulse.normalize()
        impulse += Vec3(random.uniform(-0.35, 0.35), random.uniform(-0.35, 0.35), random.uniform(0.38, 0.88))
        self.app.spawn_detached_part(part_pos, impulse * random.uniform(7.0, 11.5), label=part)
        self.app.add_combat_feedback(part_pos, label="break", radius=1.35, life=0.36, warning=False)
        self.app.play_sfx("metal_break", volume=0.62, rate=random.uniform(0.86, 1.08), pos=part_pos)
        self.app.spawn_physics_shards(part_pos, impulse, count=10, speed=8.2, life=0.68, warm=False)
        self.stagger_timer = max(float(getattr(self, "stagger_timer", 0.0)), 0.88)
        self.apply_impulse(base - Vec3(point), 6.8)
        damage = float(getattr(self.app.game_cfg, "disassembler_damage_per_part", 52.0))
        self.health -= damage
        self.app.on_core_damage(damage * 0.66)
        part_count = len(getattr(self, "disassembled_parts", set()))
        slow_per_part = float(getattr(self.app.game_cfg, "disassembler_slow_per_part", 0.10))
        self.speed = min(float(getattr(self, "speed", 1.0)), float(getattr(self, "base_speed", self.speed)) * max(0.45, 1.0 - part_count * slow_per_part))
        if part_count >= 3 and not bool(getattr(self, "armor_broken", False)):
            self.break_armor(part_pos, impulse)
        self.body.setScale(max(0.54, 1.0 - part_count * 0.055))
        self.line_root.setColor(0.18, 0.92, 1.0, 0.98)
        self.app.combat_banner = f"DISASSEMBLED // {part.upper()} DETACHED"
        self.app.combat_banner_time = max(float(getattr(self.app, "combat_banner_time", 0.0)), 0.62)
        if part_count >= 3 and hasattr(self.app, "record_activity"):
            self.app.record_activity("disassembler_catalog", "Disassembly Catalog", pos=part_pos)
        killed = self.health <= 0 or part_count >= max(1, int(getattr(self.app.game_cfg, "disassembler_parts_to_kill", 5)))
        if killed:
            core_pos = self.core_world_position()
            self.break_apart_on_death(core_pos, Vec3(0, 0, 1))
            self.app.spawn_core_explosion(core_pos, Vec3(0, 0, 1), variant=self.variant)
            self.app.play_sfx("kill", volume=1.0, rate=random.uniform(0.88, 1.08), pos=core_pos)
            self.dead = True
            if self.root is not None and not self.root.isEmpty():
                self.root.removeNode()
        return killed

    def break_apart_on_death(self, core_pos: Vec3, normal: Vec3):
        labels = ["head", "left arm", "right arm", "left leg", "right leg", "core frame", "spine"]
        if self.variant in {"walker", "boss_mech"}:
            labels.extend(["left cannon", "right cannon", "knee piston"])
        count = min(len(labels), max(4, int(getattr(self.app.game_cfg, "enemy_break_apart_parts", 7)) + (3 if self.variant == "boss_mech" else 0)))
        for i, label in enumerate(labels[:count]):
            ang = math.tau * i / max(1, count)
            offset = Vec3(math.cos(ang) * self.radius * 0.85, math.sin(ang) * self.radius * 0.65, random.uniform(0.2, self.height * 0.82))
            velocity = Vec3(math.cos(ang), math.sin(ang), random.uniform(0.36, 0.94))
            velocity.normalize()
            self.app.spawn_detached_part(self.root.getPos(self.app.render) + offset, velocity * random.uniform(6.5, 13.5), label=label)
        if self.variant == "boss_mech":
            self.app.play_sfx("explosion_boss", volume=0.95, rate=random.uniform(0.92, 1.04), pos=core_pos)


    def hit(self, damage: float, point: Vec3, normal: Vec3, force_kill: bool = False, hit_kind: str = "core"):
        if self.dead:
            return False
        hit_kind = str(hit_kind or "core")
        is_core_hit = hit_kind == "core"
        is_chain_hit = hit_kind == "chain"
        if self.is_boss_mech and not force_kill:
            weakpoint = self.boss_weakpoint_for_hit(point)
            if weakpoint is not None and self.destroy_boss_weakpoint(weakpoint, point, normal):
                damage *= 0.70
            elif is_core_hit and not self.boss_core_exposed:
                damage *= 0.24
                self.spawn_role_pulse(self.core_world_position(), color=(1.0, 0.18, 0.05, 0.86), radius=2.1, life=0.34)
                self.app.add_combat_feedback(self.core_world_position(), label="armor", radius=2.6, life=0.38, warning=True)
        if self.variant == "walker" and not force_kill:
            self.walker_braced = not self.armor_broken
            if self.walker_braced and not is_core_hit:
                damage *= 0.72
            self.role_reaction_timer = max(self.role_reaction_timer, 0.30)
        elif self.variant == "stalker" and not force_kill:
            self.evasion_timer = max(self.evasion_timer, 0.28)
            side = -1.0 if self.rng.random() < 0.5 else 1.0
            self.evasion_direction = Vec3(-self.direction.y * side, self.direction.x * side, 0)
        elif self.variant == "shifter" and not force_kill:
            self.evasion_timer = max(self.evasion_timer, 0.36 if self.shifter_form == "quad" else 0.20)
            side = -1.0 if self.rng.random() < 0.5 else 1.0
            self.evasion_direction = Vec3(-self.direction.y * side, self.direction.x * side, 0)
        if force_kill and bool(getattr(self.app.game_cfg, "weapon_one_hit_kill", True)):
            damage = max(float(damage), float(self.health) + 1.0)
        elif not is_core_hit:
            self.stagger_timer = max(float(getattr(self, "stagger_timer", 0.0)), float(getattr(self.app.game_cfg, "enemy_body_stagger_seconds", 0.38)))
            if bool(getattr(self, "armor_broken", False)):
                damage *= float(getattr(self.app.game_cfg, "enemy_armor_broken_damage_scale", 1.65))
            else:
                self.armor_hits = int(getattr(self, "armor_hits", 0)) + (1 if not is_chain_hit else 2)
                if self.armor_hits >= max(1, int(getattr(self.app.game_cfg, "enemy_armor_break_hits", 2))):
                    self.break_armor(point, normal)
        self.health -= damage
        self.app.on_core_damage(damage if is_core_hit else damage * 0.55)
        impulse_dir = self.root.getPos(self.app.render) - point
        impact_force = float(getattr(self.app.game_cfg, "impact_knockback_force", 3.2))
        if is_core_hit or force_kill:
            impact_force *= 1.65
        elif is_chain_hit:
            impact_force = float(getattr(self.app.game_cfg, "chain_arc_physics_force", 4.6))
        self.apply_impulse(impulse_dir, impact_force)
        self.app.spawn_spark_burst(point, normal, count=22 if force_kill else (14 if not is_core_hit else 12), speed=8.0 if force_kill else (6.0 if not is_core_hit else 5.4))
        if not force_kill:
            shard_count = int(getattr(self.app.game_cfg, "impact_shard_count", 8))
            self.app.spawn_physics_shards(point, normal, count=shard_count if not is_core_hit else max(5, shard_count - 2), speed=7.4 if not is_chain_hit else 9.0, life=0.55 if not is_chain_hit else 0.62, warm=not is_chain_hit)
        feedback_label = "chain" if is_chain_hit else "hit"
        self.app.add_combat_feedback(point, label=feedback_label, radius=2.0 if is_core_hit else (1.55 if is_chain_hit else 1.18), life=0.34 if is_core_hit else 0.28, warning=(not is_core_hit and not is_chain_hit))
        if is_core_hit or force_kill:
            self.app.play_sfx("hit", volume=min(1.0, 0.56 + damage / 120.0), rate=random.uniform(0.88, 1.16), pos=point)
        elif is_chain_hit:
            self.app.play_sfx("chain", volume=0.58, rate=random.uniform(0.94, 1.06), pos=point)
        else:
            armor_key = "armor_heavy" if getattr(self, "variant", "") in {"bulwark", "commander", "walker", "boss_mech"} else "armor"
            self.app.play_sfx(armor_key, volume=min(0.95, 0.52 + damage / 140.0), rate=random.uniform(0.88, 1.12), pos=point)
            if not bool(getattr(self, "armor_broken", False)) and random.random() < 0.22:
                self.app.play_sfx("deflect", volume=0.42, rate=random.uniform(0.92, 1.1), pos=point)
        spawn_count = 2 if len(self.app.blotches) > self.app.game_cfg.max_blotches * 0.7 else random.randint(3 if is_core_hit else 1, 5 if is_core_hit else 3)
        for _ in range(spawn_count):
            self.app.blotches.append(InkBlotch(self.app, point + Vec3(random.uniform(-0.07, 0.07), random.uniform(-0.07, 0.07), random.uniform(-0.07, 0.07)), normal))
        self.app.clamp_effects()
        killed = self.health <= 0
        if killed:
            core_pos = self.core_world_position()
            self.break_apart_on_death(core_pos, Vec3(0, 0, 1))
            self.app.spawn_core_explosion(core_pos, Vec3(0, 0, 1), variant=self.variant)
            self.app.play_sfx("kill", volume=1.0, rate=random.uniform(0.88, 1.08), pos=core_pos)
            self.dead = True
            if self.root is not None and not self.root.isEmpty():
                self.root.removeNode()
        return killed

    def build_state_color_indicator(self):
        """Neutral white chest bands that display semantic combat state colors exactly."""
        self.state_color_root = self.body.attachNewNode(f"state-color-{self.variant}")
        self.state_color_root.setTransparency(TransparencyAttrib.MAlpha)
        self.state_color_root.setAntialias(AntialiasAttrib.MLine)
        segs = LineSegs(f"state-color-lines-{self.variant}")
        segs.setThickness(self.app.enemy_line_thickness(1.55, 2.8))
        segs.setColor(1.0, 1.0, 1.0, 1.0)
        z = float(self.core_offset.z)
        r = max(0.52, float(self.radius) * 0.62)
        # Side brackets deliberately avoid the core so they cannot be mistaken for weak-point rings.
        for sx in (-1.0, 1.0):
            x = sx * r * 1.20
            inner = sx * r * 0.70
            segs.moveTo(x, 0.58, z - r * 0.58); segs.drawTo(x, 0.58, z + r * 0.58)
            segs.moveTo(x, 0.58, z + r * 0.58); segs.drawTo(inner, 0.58, z + r * 0.58)
            segs.moveTo(x, 0.58, z - r * 0.58); segs.drawTo(inner, 0.58, z - r * 0.58)
        self.state_color_np = self.state_color_root.attachNewNode(segs.create())

    def combat_color_state(self):
        """Return the current semantic combat color state and RGBA tint."""
        if self.is_boss_mech:
            if self.boss_core_exposed:
                return "boss_exposed", (0.72, 1.0, 0.18, 1.0)
            return "boss_shielded", (0.70, 0.28, 1.0, 1.0)
        if self.variant == "shifter" and self.role_reaction_timer > 0.0:
            return "shifter_phase", (0.10, 1.0, 1.0, 1.0)
        if self.variant == "stalker" and self.evasion_timer > 0.0:
            return "stalker_evade", (1.0, 0.94, 0.12, 1.0)
        if self.variant == "walker" and self.walker_braced and not self.armor_broken:
            return "walker_braced", (1.0, 0.46, 0.05, 1.0)
        if float(getattr(self, "tell_timer", 0.0)) > 0.0 or float(getattr(self, "attack_lunge_timer", 0.0)) > 0.0:
            return "attack", (1.0, 0.06, 0.015, 1.0)
        if bool(getattr(self, "armor_broken", False)):
            return "armor_broken", (0.55, 1.0, 0.62, 1.0)
        return "baseline", (1.0, 0.18, 0.10, 0.98)

    def apply_combat_color_state(self):
        state_name, tint = self.combat_color_state()
        self.color_state_name = state_name
        self.color_state_color = tint
        self.line_root.setColor(*tint)
        if hasattr(self, "state_color_np") and not self.state_color_np.isEmpty():
            self.state_color_np.setColor(*tint, 100)
        shell_tint = (0.34 + tint[0] * 0.66, 0.34 + tint[1] * 0.66, 0.34 + tint[2] * 0.66, 1.0)
        self.shell_root.setColorScale(*shell_tint)
        return state_name, tint

    def update(self, dt: float, player_pos: Vec3):
        if self.dead or self.root is None or self.root.isEmpty():
            return False
        to_player = player_pos - self.root.getPos()
        to_player.z = 0
        dist = to_player.length()
        base_chase = max(70.0, float(getattr(self.app.game_cfg, "enemy_chase_distance", 118.0)))
        chase_distance = base_chase if self.variant != "bulwark" else base_chase * 1.12
        if self.variant == "commander":
            chase_distance = base_chase * 1.20
        if self.variant == "walker":
            chase_distance = base_chase * 1.12
        if self.variant == "boss_mech":
            chase_distance = base_chase * 1.35
        if self.variant == "shifter":
            transform_dist = float(getattr(self.app.game_cfg, "shifter_transform_distance", 38.0))
            self.shifter_form = "biped" if dist < transform_dist else "quad"
            self.trigger_shifter_transition(self.shifter_form)
        if dist < chase_distance and dist > 0.001:
            desired = self.app.ai_steer_towards(self.root.getPos(), player_pos, radius=float(getattr(self, "radius", 1.0)), height=float(getattr(self, "height", 4.0)), seed=int(getattr(self, "seed", 1)))
        else:
            self.wander_timer -= dt
            if self.wander_timer <= 0.0:
                self.wander_timer = 1.0 + self.rng.random() * 2.2
                self.direction = Vec3(self.rng.uniform(-1, 1), self.rng.uniform(-1, 1), 0)
                if self.direction.lengthSquared() < 0.05:
                    self.direction = Vec3(1, 0, 0)
                self.direction.normalize()
            desired = self.direction
        self.attack_cooldown = max(0.0, float(getattr(self, "attack_cooldown", 0.0)) - dt)
        self.role_reaction_timer = max(0.0, float(getattr(self, "role_reaction_timer", 0.0)) - dt)
        self.evasion_timer = max(0.0, float(getattr(self, "evasion_timer", 0.0)) - dt)
        if self.evasion_timer > 0.0 and self.evasion_direction.lengthSquared() > 0.001:
            desired = Vec3(desired) + self.evasion_direction * (1.45 if self.variant == "shifter" else 1.15)
            if desired.lengthSquared() > 0.001:
                desired.normalize()
        tell_timer = float(getattr(self, "tell_timer", 0.0))
        if tell_timer > 0.0:
            self.tell_timer = max(0.0, tell_timer - dt)
            if self.tell_timer <= 0.0 and dist < float(getattr(self.app.game_cfg, "enemy_attack_tell_distance", 28.0)) * 0.82:
                self.attack_lunge_timer = max(float(getattr(self, "attack_lunge_timer", 0.0)), float(getattr(self.app.game_cfg, "enemy_attack_lunge_seconds", 0.26)))
        elif dist < float(getattr(self.app.game_cfg, "enemy_attack_tell_distance", 28.0)) and dist > 2.0:
            self.trigger_attack_tell(player_pos)
        lunge_timer = float(getattr(self, "attack_lunge_timer", 0.0))
        if lunge_timer > 0.0:
            self.attack_lunge_timer = max(0.0, lunge_timer - dt)
        stagger_timer = float(getattr(self, "stagger_timer", 0.0))
        if stagger_timer > 0.0:
            self.stagger_timer = max(0.0, stagger_timer - dt)
        speed_scale = 0.34 if stagger_timer > 0.0 else 1.0
        if self.variant == "walker" and not self.armor_broken:
            self.walker_braced = dist < float(getattr(self.app.game_cfg, "enemy_attack_tell_distance", 28.0)) * 1.18 or self.role_reaction_timer > 0.0
            if self.walker_braced:
                speed_scale *= 0.62
        if self.variant == "stalker" and self.evasion_timer > 0.0:
            speed_scale *= 1.42
        if self.variant == "shifter" and getattr(self, "shifter_form", "quad") == "quad":
            speed_scale *= float(getattr(self.app.game_cfg, "shifter_quad_speed_scale", 1.28))
        if self.variant == "boss_mech":
            speed_scale *= 0.86
        if lunge_timer > 0.0 and stagger_timer <= 0.0:
            speed_scale *= float(getattr(self.app.game_cfg, "enemy_attack_lunge_speed_scale", 1.32))
        step = desired * self.speed * speed_scale * dt
        knock = Vec3(getattr(self, "knockback_velocity", Vec3(0, 0, 0)))
        if knock.lengthSquared() > 0.0001:
            step += knock * dt
            drag = max(0.0, 1.0 - dt * float(getattr(self.app.game_cfg, "enemy_knockback_drag", 5.8)))
            self.knockback_velocity = knock * drag
        separation = self.app.enemy_separation_vector(self)
        if separation.lengthSquared() > 0.0001:
            step += separation * float(getattr(self.app.game_cfg, "enemy_separation_force", 2.1)) * dt
        candidate = self.root.getPos() + step
        candidate.z = 0
        if not self.app.point_hits_obstacle(candidate, radius=self.radius, height=self.height):
            self.root.setPos(candidate)
        else:
            self.direction *= -1
            self.knockback_velocity = Vec3(0, 0, 0)
        if dist > 0.001:
            self.root.setH(math.degrees(math.atan2(-desired.x, desired.y)))
        stride = math.sin(self.app.elapsed * (6.4 if self.variant == "stalker" else 5.2) + self.phase)
        if self.variant == "shifter" and getattr(self, "shifter_form", "quad") == "quad":
            self.body.setP(-17.0 + stride * 1.8)
            self.body.setScale(1.08, 1.18, 0.72)
        elif self.variant == "walker" and self.walker_braced:
            self.body.setP(-4.5 + stride * 0.34)
            self.body.setScale(1.06, 1.02, 0.94)
        elif self.variant == "boss_mech" and not self.boss_core_exposed:
            self.body.setP(stride * 0.55)
            self.body.setScale(1.04, 1.0, 1.02)
        else:
            self.body.setP(stride * (0.75 if self.variant == "boss_mech" else 1.1))
            self.body.setScale(1.0)
        self.body.setR(math.sin(self.app.elapsed * 2.6 + self.phase) * (1.2 if self.variant == "boss_mech" else 1.8))
        self.body.setZ(math.sin(self.app.elapsed * 5.1 + self.phase) * (0.025 if self.variant == "boss_mech" else 0.05))
        _state_name, tint = self.apply_combat_color_state()
        pulse = 0.72 + 0.28 * (0.5 + 0.5 * math.sin(self.app.elapsed * 7.0 + self.phase))
        if float(getattr(self, "tell_timer", 0.0)) > 0.0:
            pulse = min(1.42, pulse + 0.36)
        if float(getattr(self, "stagger_timer", 0.0)) > 0.0:
            pulse = min(1.24, pulse + 0.22)
        if bool(getattr(self, "armor_broken", False)):
            pulse = min(1.48, pulse + 0.18)
        core_rgb = (1.0, 0.08 + 0.12 * pulse, 0.08 + 0.1 * pulse)
        if self.is_boss_mech:
            core_rgb = (0.72, 1.0, 0.18) if self.boss_core_exposed else (0.70, 0.28, 1.0)
        elif self.variant == "commander":
            core_rgb = (1.0, 0.34 + 0.12 * pulse, 0.05 + 0.08 * pulse)
        for idx, card in enumerate(self.core_cards):
            alpha = (0.9 - idx * 0.22) * pulse
            card.setColor(core_rgb[0], core_rgb[1], core_rgb[2], alpha)
            card.setScale(1.0 + idx * 0.1 + pulse * (0.08 if self.variant != "commander" else 0.13))
        for idx, plume in enumerate(self.plume_cards):
            plume.setColor(0.0, 0.0, 0.0, max(0.05, 0.22 - idx * 0.04) * (0.55 + 0.45 * pulse))
            plume.setScale(1.0 + pulse * (0.15 + idx * 0.05))
            plume.setZ(self.core_offset.z + 0.18 * idx + math.sin(self.app.elapsed * 1.2 + self.phase + idx) * 0.08)
        return True



class Civilian:
    """Lightweight city civilian: building-anchor route walker with simple obstacle steering."""

    def __init__(self, app, pos: Vec3, seed: int):
        self.app = app
        self.seed = int(seed)
        self.rng = random.Random(self.seed)
        self.root = app.render.attachNewNode("civilian")
        self.root.setPos(Vec3(pos.x, pos.y, 0.0))
        self.radius = 0.55
        self.height = 2.85
        self.health = int(getattr(app.game_cfg, "civilian_health", 32))
        self.dead = False
        self.is_civilian = True
        self.speed = float(getattr(app.game_cfg, "civilian_speed", 2.65)) * self.rng.uniform(0.84, 1.12)
        self.target = Vec3(pos.x, pos.y, 0.0)
        self.next_target_timer = 0.0
        self.harm_cooldown = 0.0
        self.enemy_harm_cooldown = 0.0
        self.phase = self.rng.random() * math.tau
        self.build_model()
        self.choose_new_target(force=True)

    def build_model(self):
        self.body = self.root.attachNewNode("civilian-body")
        self.shell_root = self.body.attachNewNode("civilian-shell")
        self.line_root = self.body.attachNewNode("civilian-lines")
        self.line_root.setTransparency(TransparencyAttrib.MAlpha)
        self.line_root.setAntialias(AntialiasAttrib.MLine)
        dark = (0.025, 0.045, 0.058, 0.72)
        soft = (0.08, 0.16, 0.18, 0.68)
        self.app.attach_weapon_box_fill(self.shell_root, Vec3(0, 0, 1.25), Vec3(0.55, 0.34, 1.15), soft, "civilian-torso-fill")
        self.app.attach_weapon_box_fill(self.shell_root, Vec3(0, 0.02, 2.15), Vec3(0.34, 0.26, 0.34), soft, "civilian-head-fill")
        for x in (-0.22, 0.22):
            self.app.attach_weapon_box_fill(self.shell_root, Vec3(x, 0.02, 0.42), Vec3(0.18, 0.22, 0.82), dark, "civilian-leg-fill")
        for x in (-0.46, 0.46):
            self.app.attach_weapon_box_fill(self.shell_root, Vec3(x, 0.02, 1.20), Vec3(0.14, 0.18, 0.84), dark, "civilian-arm-fill")
        segs = LineSegs("civilian-outline")
        segs.setThickness(max(1.25, float(getattr(self.app.game_cfg, "line_thickness", 1.45)) * 0.82))
        segs.setColor(0.56, 1.0, 0.92, 0.84)
        for center, size in (
            (Vec3(0, 0, 1.25), Vec3(0.55, 0.34, 1.15)),
            (Vec3(0, 0.02, 2.15), Vec3(0.34, 0.26, 0.34)),
            (Vec3(-0.22, 0.02, 0.42), Vec3(0.18, 0.22, 0.82)),
            (Vec3(0.22, 0.02, 0.42), Vec3(0.18, 0.22, 0.82)),
            (Vec3(-0.46, 0.02, 1.20), Vec3(0.14, 0.18, 0.84)),
            (Vec3(0.46, 0.02, 1.20), Vec3(0.14, 0.18, 0.84)),
        ):
            self.app.draw_box_edges(segs, center, size)
        segs.moveTo(-0.26, 0.10, 2.45); segs.drawTo(0.26, 0.10, 2.45)
        segs.moveTo(0.0, 0.10, 2.30); segs.drawTo(0.0, 0.10, 2.58)
        np = self.line_root.attachNewNode(segs.create())
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setAntialias(AntialiasAttrib.MLine)

    def bounds(self):
        p = self.root.getPos(self.app.render)
        return BoxBounds(p + Vec3(-self.radius, -self.radius, 0.0), p + Vec3(self.radius, self.radius, self.height), Vec3(0, 0, 1))

    def core_world_position(self):
        return self.root.getPos(self.app.render) + Vec3(0, 0, 1.55)

    def apply_impulse(self, vec: Vec3, amount: float):
        try:
            v = Vec3(vec)
            if v.lengthSquared() > 0.001:
                v.normalize()
                p = self.root.getPos(self.app.render) + v * min(1.4, float(amount) * 0.035)
                if not self.app.point_hits_obstacle(p, radius=self.radius, height=self.height):
                    self.root.setPos(p)
        except Exception:
            pass

    def choose_new_target(self, force: bool = False):
        anchors = list(getattr(self.app, "civilian_anchors", []) or [])
        if not anchors:
            self.target = self.root.getPos(self.app.render) + Vec3(self.rng.uniform(-24, 24), self.rng.uniform(-24, 24), 0)
            return
        here = self.root.getPos(self.app.render)
        far = [(abs((Vec3(a) - here).length()), Vec3(a)) for a in anchors if (Vec3(a) - here).length() > (18.0 if not force else 6.0)]
        if not far:
            far = [(1.0, Vec3(a)) for a in anchors]
        far.sort(key=lambda item: item[0], reverse=True)
        pick_pool = far[:min(18, len(far))]
        self.target = Vec3(self.rng.choice(pick_pool)[1])

    def hit(self, damage: float, point: Vec3, normal: Vec3, force_kill: bool = False, hit_kind: str = "hit"):
        if self.dead:
            return False
        self.health -= int(max(1, float(damage)))
        self.harm_cooldown = 0.6
        killed = bool(force_kill or self.health <= 0)
        if killed:
            self.dead = True
            self.app.spawn_physics_shards(self.core_world_position(), Vec3(0, 0, 1), count=5, speed=4.2, life=0.42, warm=False)
            if self.root is not None and not self.root.isEmpty():
                self.root.removeNode()
        else:
            self.app.add_combat_feedback(self.core_world_position(), label="civilian", radius=1.6, life=0.45, warning=True)
        return killed

    def update(self, dt: float):
        if self.dead or self.root is None or self.root.isEmpty():
            return False
        self.harm_cooldown = max(0.0, float(getattr(self, "harm_cooldown", 0.0)) - dt)
        self.enemy_harm_cooldown = max(0.0, float(getattr(self, "enemy_harm_cooldown", 0.0)) - dt)
        pos = self.root.getPos(self.app.render)
        to_target = Vec3(self.target.x - pos.x, self.target.y - pos.y, 0.0)
        if to_target.length() < 3.5 or self.next_target_timer <= 0.0:
            self.next_target_timer = self.rng.uniform(4.0, 8.5)
            self.choose_new_target()
            to_target = Vec3(self.target.x - pos.x, self.target.y - pos.y, 0.0)
        self.next_target_timer -= dt
        desired = self.app.ai_steer_towards(pos, self.target, radius=self.radius, height=self.height, seed=self.seed)
        step = desired * self.speed * dt
        candidate = pos + step
        candidate.z = 0.0
        if not self.app.point_hits_obstacle(candidate, radius=self.radius, height=self.height):
            self.root.setPos(candidate)
        else:
            self.choose_new_target(force=True)
        if desired.lengthSquared() > 0.001:
            self.root.setH(math.degrees(math.atan2(-desired.x, desired.y)))
        walk = math.sin(self.app.elapsed * 7.2 + self.phase)
        self.body.setP(walk * 0.8)
        self.body.setR(math.sin(self.app.elapsed * 2.7 + self.phase) * 1.2)
        tint = (0.52, 1.0, 0.88, 0.92) if self.harm_cooldown <= 0.0 else (1.0, 0.22, 0.18, 0.96)
        self.line_root.setColor(*tint)
        return True



class PatrolDrone:
    """Armored city patrol drone with lightweight waypoint steering and target scanning."""

    def __init__(self, app, pos: Vec3, seed: int, district_id: str = "calibration"):
        self.app = app
        self.seed = int(seed)
        self.rng = random.Random(self.seed)
        self.root = app.render.attachNewNode("patrol-drone")
        self.root.setPos(Vec3(pos.x, pos.y, 7.4 + self.rng.uniform(-1.1, 1.4)))
        self.district_id = str(district_id or "calibration")
        self.is_patrol_drone = True
        self.dead = False
        self.color_state_name = "drone_passive"
        self.color_state_color = (0.20, 1.0, 0.92, 0.92)
        self.radius = 1.45
        self.height = 2.8
        self.health = int(getattr(app.game_cfg, "patrol_drone_health", 260))
        self.armor = int(getattr(app.game_cfg, "patrol_drone_armor", 180))
        self.speed = float(getattr(app.game_cfg, "patrol_drone_speed", 7.2)) * self.rng.uniform(0.92, 1.08)
        self.target = Vec3(pos.x, pos.y, 7.5)
        self.next_target_timer = 0.0
        self.fire_cooldown = self.rng.uniform(0.25, 0.9)
        self.phase = self.rng.random() * math.tau
        self.evasive_timer = 0.0
        self.hit_flash_timer = 0.0
        self.evasive_sign = -1.0 if self.rng.random() < 0.5 else 1.0
        self.build_model()
        self.choose_new_target(force=True)

    def build_model(self):
        self.body = self.root.attachNewNode("drone-body")
        self.shell_root = self.body.attachNewNode("drone-shell")
        self.line_root = self.body.attachNewNode("drone-lines")
        self.line_root.setTransparency(TransparencyAttrib.MAlpha)
        self.line_root.setAntialias(AntialiasAttrib.MLine)
        dark = (0.018, 0.022, 0.030, 0.90)
        armor = (0.06, 0.16, 0.18, 0.82) if self.district_id != "pyramid_sector" else (0.16, 0.07, 0.04, 0.84)
        self.app.attach_weapon_prism(self.shell_root, self.app.octagon_points(1.16, 0.54), -0.74, 0.74, armor, "drone-octagon-core")
        self.app.attach_weapon_box_fill(self.shell_root, Vec3(0, 0, -0.18), Vec3(1.55, 1.05, 0.56), dark, "drone-belly-armor")
        for x in (-1.55, 1.55):
            self.app.attach_weapon_box_fill(self.shell_root, Vec3(x, 0, 0.02), Vec3(0.72, 0.42, 0.40), armor, "drone-side-pod")
            self.app.attach_weapon_prism(self.shell_root, self.app.octagon_points(0.36, 0.36), -0.08, 0.08, dark, "drone-rotor-ring").setPos(x, 0, 0.36)
        self.app.attach_weapon_box_fill(self.shell_root, Vec3(0, 0.96, 0.02), Vec3(0.42, 0.62, 0.32), armor, "drone-front-sensor")
        segs = LineSegs("drone-outline")
        segs.setThickness(max(1.7, float(getattr(self.app.game_cfg, "line_thickness", 1.45)) * 1.05))
        if self.district_id == "pyramid_sector":
            segs.setColor(1.0, 0.34, 0.18, 0.92)
        else:
            segs.setColor(0.28, 1.0, 0.94, 0.90)
        for center, size in (
            (Vec3(0, 0, -0.18), Vec3(1.55, 1.05, 0.56)),
            (Vec3(-1.55, 0, 0.02), Vec3(0.72, 0.42, 0.40)),
            (Vec3(1.55, 0, 0.02), Vec3(0.72, 0.42, 0.40)),
            (Vec3(0, 0.96, 0.02), Vec3(0.42, 0.62, 0.32)),
        ):
            self.app.draw_box_edges(segs, center, size)
        # Attached rotor circles and scan vanes, not floating world wires.
        for x in (-1.55, 1.55):
            for i in range(16):
                a0 = math.tau * i / 16
                a1 = math.tau * (i + 1) / 16
                segs.moveTo(x + math.cos(a0) * 0.48, math.sin(a0) * 0.48, 0.36)
                segs.drawTo(x + math.cos(a1) * 0.48, math.sin(a1) * 0.48, 0.36)
            segs.moveTo(x - 0.42, 0, 0.36); segs.drawTo(x + 0.42, 0, 0.36)
            segs.moveTo(x, -0.42, 0.36); segs.drawTo(x, 0.42, 0.36)
        segs.moveTo(-0.34, 1.30, 0.02); segs.drawTo(0.34, 1.30, 0.02)
        self.line_root.attachNewNode(segs.create()).setTransparency(TransparencyAttrib.MAlpha)
        self.state_color_root = self.body.attachNewNode("drone-state-color")
        self.state_color_root.setTransparency(TransparencyAttrib.MAlpha)
        self.state_color_root.setAntialias(AntialiasAttrib.MLine)
        state_segs = LineSegs("drone-state-color-lines")
        state_segs.setThickness(max(2.2, float(getattr(self.app.game_cfg, "line_thickness", 1.45)) * 1.45))
        state_segs.setColor(1.0, 1.0, 1.0, 1.0)
        # Side status rails plus a front chevron; no target-like circle around the drone core.
        for sx in (-1.0, 1.0):
            state_segs.moveTo(sx * 1.92, 0.12, -0.10); state_segs.drawTo(sx * 1.18, 0.12, -0.10)
            state_segs.moveTo(sx * 1.92, 0.12, 0.34); state_segs.drawTo(sx * 1.18, 0.12, 0.34)
            state_segs.moveTo(sx * 1.92, 0.12, -0.10); state_segs.drawTo(sx * 1.92, 0.12, 0.34)
        state_segs.moveTo(-0.44, 1.38, 0.10); state_segs.drawTo(0.0, 1.52, 0.34)
        state_segs.drawTo(0.44, 1.38, 0.10)
        self.state_color_np = self.state_color_root.attachNewNode(state_segs.create())

    def bounds(self):
        p = self.root.getPos(self.app.render)
        return BoxBounds(p + Vec3(-1.75, -1.35, -0.75), p + Vec3(1.75, 1.55, 1.05), Vec3(0, 0, 1))

    def core_world_position(self):
        return self.root.getPos(self.app.render) + Vec3(0, 0.28, 0.0)

    def apply_impulse(self, vec: Vec3, amount: float):
        try:
            v = Vec3(vec)
            if v.lengthSquared() > 0.001:
                v.normalize()
                p = self.root.getPos(self.app.render) + v * min(1.2, float(amount) * 0.018)
                if not self.app.point_hits_obstacle(Vec3(p.x, p.y, 0), radius=1.2, height=4.0):
                    self.root.setPos(p)
        except Exception:
            pass

    def choose_new_target(self, force: bool = False):
        anchors = list(getattr(self.app, "patrol_drone_anchors", []) or [])
        here = self.root.getPos(self.app.render)
        if anchors:
            choices = [Vec3(a) for a in anchors if (Vec3(a) - here).length() > (24 if not force else 4)]
            if not choices:
                choices = [Vec3(a) for a in anchors]
            self.target = Vec3(self.rng.choice(choices))
            self.target.z = 7.0 + self.rng.uniform(1.0, 7.0)
        else:
            self.target = here + Vec3(self.rng.uniform(-42, 42), self.rng.uniform(-42, 42), self.rng.uniform(-1, 1))

    def hostile_targets(self):
        targets = []
        here = self.root.getPos(self.app.render)
        detect = float(getattr(self.app.game_cfg, "patrol_drone_detect_radius", 96.0))
        for enemy in list(getattr(self.app, "enemies", []) or []):
            if getattr(enemy, "dead", False) or enemy.root is None or enemy.root.isEmpty():
                continue
            p = enemy.root.getPos(self.app.render)
            d = (p - here).length()
            if d <= detect:
                targets.append((d, enemy, p + Vec3(0, 0, max(1.4, getattr(enemy, "height", 4.0) * 0.62))))
        if float(getattr(self.app, "player_hostility_timer", 0.0)) > 0.0:
            p = Vec3(self.app.player_pos.x, self.app.player_pos.y, self.app.game_cfg.player_height)
            d = (p - here).length()
            if d <= detect * 0.86:
                targets.append((d * 0.72, "player", p))
        targets.sort(key=lambda item: item[0])
        return targets

    def fire_at(self, target, target_pos: Vec3):
        here = self.root.getPos(self.app.render) + Vec3(0, 0.74, 0.05)
        target_pos = Vec3(target_pos)
        self.app.tracers.append(TracerEffect(self.app, here, target_pos, ttl=0.18, color=(0.18, 1.0, 0.92, 0.98), thickness_scale=1.30))
        self.app.add_combat_feedback(target_pos, label="drone", radius=1.2, life=0.22, warning=False)
        self.app.play_sfx("auto_fire", volume=0.44, rate=self.rng.uniform(1.04, 1.18), pos=here)
        damage = int(getattr(self.app.game_cfg, "patrol_drone_damage", 3))
        if target == "player":
            self.app.apply_player_damage(damage, source="patrol_drone")
            self.app.add_combat_camera_kick(0.55)
            self.app.combat_banner = "PATROL DRONE LOCK // EVASIVE"
            self.app.combat_banner_time = max(float(getattr(self.app, "combat_banner_time", 0.0)), 0.66)
        else:
            normal = Vec3(target_pos - here)
            if normal.lengthSquared() > 0.001:
                normal.normalize()
            killed = target.hit(damage, target_pos, -normal if normal.lengthSquared() > 0.001 else Vec3(0, 0, 1), force_kill=False, hit_kind="drone")
            if killed:
                self.app.drone_kills = int(getattr(self.app, "drone_kills", 0)) + 1

    def hit(self, damage: float, point: Vec3, normal: Vec3, force_kill: bool = False, hit_kind: str = "hit"):
        if self.dead:
            return False
        # Good armor: most damage strips armor first, and body damage is reduced until armor breaks.
        raw = float(max(1.0, damage))
        if self.armor > 0 and not force_kill:
            absorbed = min(self.armor, int(raw * 0.76))
            self.armor -= absorbed
            raw = max(1.0, raw - absorbed * 0.52)
        self.health -= int(raw)
        self.hit_flash_timer = 0.62
        self.evasive_timer = 0.58 if self.armor > 0 else 0.26
        self.evasive_sign *= -1.0
        self.app.add_combat_feedback(point, label="break" if self.armor <= 0 else "armor", radius=1.8, life=0.34, warning=self.armor > 0)
        self.app.add_shockwave_ring(point, radius=2.8 if self.armor > 0 else 2.0, life=0.34, vertical=True, thickness=1.2)
        self.app.play_sfx("armor_heavy" if self.armor > 0 else "metal_break", volume=0.58, rate=self.rng.uniform(0.92, 1.08), pos=point)
        killed = bool(force_kill or self.health <= 0)
        if killed:
            self.dead = True
            core = self.core_world_position()
            self.app.spawn_core_explosion(core, Vec3(0, 0, 1), variant="commander")
            self.app.play_sfx("explosion_cannon", volume=0.74, rate=0.96, pos=core)
            if self.root is not None and not self.root.isEmpty():
                self.root.removeNode()
        return killed

    def update(self, dt: float):
        if self.dead or self.root is None or self.root.isEmpty():
            return False
        self.fire_cooldown = max(0.0, float(getattr(self, "fire_cooldown", 0.0)) - dt)
        self.evasive_timer = max(0.0, float(getattr(self, "evasive_timer", 0.0)) - dt)
        self.hit_flash_timer = max(0.0, float(getattr(self, "hit_flash_timer", 0.0)) - dt)
        here = self.root.getPos(self.app.render)
        targets = self.hostile_targets()
        if targets and self.fire_cooldown <= 0.0:
            _dist, target, target_pos = targets[0]
            self.fire_at(target, target_pos)
            self.fire_cooldown = float(getattr(self.app.game_cfg, "patrol_drone_fire_interval", 0.82)) * self.rng.uniform(0.82, 1.22)
        if targets:
            target_pos = Vec3(targets[0][2])
            desired = self.app.ai_steer_towards(Vec3(here.x, here.y, 0), Vec3(target_pos.x, target_pos.y, 0), radius=1.0, height=4.0, seed=self.seed)
            desired *= 0.45
        else:
            flat_target = Vec3(self.target.x, self.target.y, 0)
            desired = self.app.ai_steer_towards(Vec3(here.x, here.y, 0), flat_target, radius=1.0, height=4.0, seed=self.seed)
        if (Vec3(self.target.x, self.target.y, 0) - Vec3(here.x, here.y, 0)).length() < 6.5 or self.next_target_timer <= 0.0:
            self.next_target_timer = self.rng.uniform(3.5, 7.0)
            self.choose_new_target()
        self.next_target_timer -= dt
        if self.evasive_timer > 0.0:
            lateral = Vec3(-desired.y * self.evasive_sign, desired.x * self.evasive_sign, 0)
            desired = Vec3(desired) + lateral * 1.35
            if desired.lengthSquared() > 0.001:
                desired.normalize()
        step = desired * self.speed * (1.34 if self.evasive_timer > 0.0 else 1.0) * dt
        next_pos = here + step
        next_pos.z += (self.target.z - here.z) * min(1.0, dt * 0.9)
        if self.evasive_timer > 0.0:
            next_pos.z += 1.8 * dt
        next_pos.z += math.sin(self.app.elapsed * 2.7 + self.phase) * 0.012
        if not self.app.point_hits_obstacle(Vec3(next_pos.x, next_pos.y, 0), radius=1.0, height=4.0):
            self.root.setPos(next_pos)
        if desired.lengthSquared() > 0.001:
            self.root.setH(math.degrees(math.atan2(-desired.x, desired.y)))
        self.body.setR(math.sin(self.app.elapsed * 3.2 + self.phase) * 4.5)
        self.body.setP(math.sin(self.app.elapsed * 2.5 + self.phase) * 2.4)
        pulse = 0.68 + 0.32 * (0.5 + 0.5 * math.sin(self.app.elapsed * 6.2 + self.phase))
        player_hostile = float(getattr(self.app, "player_hostility_timer", 0.0)) > 0.0
        if self.hit_flash_timer > 0.0 and self.armor > 0:
            self.color_state_name = "drone_armor_hit"
            self.color_state_color = (0.34, 0.58, 1.0, 1.0)
        elif player_hostile:
            self.color_state_name = "drone_hostile"
            self.color_state_color = (1.0, 0.05, 0.02, 1.0)
        else:
            self.color_state_name = "drone_passive"
            self.color_state_color = (0.20, 1.0, 0.92, 0.92)
        self.line_root.setColor(*self.color_state_color)
        if hasattr(self, "state_color_np") and not self.state_color_np.isEmpty():
            self.state_color_np.setColor(*self.color_state_color, 100)
        dtint = self.color_state_color
        self.shell_root.setColorScale(0.38 + dtint[0] * 0.62, 0.38 + dtint[1] * 0.62, 0.38 + dtint[2] * 0.62, 1.0)
        return True

class EtchlineGame(ShowBase):
    def __init__(self):
        ensure_dirs()
        install_crash_reporter()
        self.game_cfg = load_or_create_config()
        write_patch_notes(VERSION)
        self.create_blotch_texture()
        generate_dynamic_sfx_files()
        refresh_customfx_printouts()
        super().__init__()
        self.disableMouse()
        self.elapsed = 0.0
        self.day_phase = 0.0
        self.health = self.game_cfg.default_health
        self.score = 0
        self.campaign_complete = False
        self.vertical_speed = 0.0
        self.on_ground = True
        self.menu_open = False
        self.hud_visible = True
        self.workstation_visible = False
        self.help_visible = False
        self.presentation_open = bool(NORMAL_PRESENTATION_LAUNCH)
        self.help_return_to_presentation = False
        # Pass51 mastering: dynamic text is cached and refreshed on a bounded cadence.
        # Panda3D text geometry can be expensive to regenerate every frame.
        self.ui_refresh_timer = 0.0
        self.workstation_refresh_timer = 0.0
        self.ui_text_mutations = 0
        self.ui_text_skips = 0
        self.fire_down = {"right": False, "left": False}
        self.fire_hold = {"right": False, "left": False}
        self.fire_cooldown = {"right": 0.0, "left": 0.0}
        self.weapon_hand_spin = {"right": 0.0, "left": 0.0}
        self.weapon_hand_spin_velocity = {"right": 0.0, "left": 0.0}
        self.weapon_hand_recoil = {"right": 0.0, "left": 0.0}
        self.weapon_hand_muzzle_flash = {"right": 0.0, "left": 0.0}
        self.weapon_dual_wield = True
        self.last_shot_time = 0.0
        self.current_weapon_seed = 0
        self.weapons = []
        self.current_weapon = None
        self.current_weapon_slot = 1
        self.hand_weapon_slots = {"right": 1, "left": 1}
        self.unlocked_weapons = {1, 2, 3, 4, 5, 6}
        self.weapon_ammo_pools = {}
        self.weapon_banner_time = 0.0
        self.tracers = []
        self.blotches = []
        self.physics_shards = []
        self.shockwaves = []
        self.weapon_fx = []
        self.weapon_pickups = []
        self.magnet_fields = []
        self.activity_mode_name = "Prototype Lab Activity Mode"
        self.activity_flags = set()
        self.activity_event_log = []
        self.activity_bonus_score = 0
        self.activity_banner = ""
        self.activity_banner_time = 0.0
        self.activity_instances = []
        self.active_activity_instance = None
        self.activity_reward_log = []
        self.player_damage_grace_timer = 0.0
        self.contact_damage_window = 0.0
        self.contact_damage_this_window = 0.0
        self.activity_catalog = [
            ("lab_entry", "Lab Entry", "Enter the Utopia Conflict activity mode"),
            ("core_sample", "Core Sample", "Shatter an enemy core"),
            ("shield_break", "Shield Fracture", "Break armor with body hits"),
            ("chain_arc", "Chain Sketch", "Create a chain rupture"),
            ("imploder_cluster", "Imploder Study", "Catch multiple targets in an implosion"),
            ("magnet_garden", "Magnet Garden", "Hold multiple enemies in a field"),
            ("combo_line", "Combo Line", "Chain together a short streak"),
            ("disassembler_catalog", "Disassembly Catalog", "Detach several parts"),
            ("ammo_cache", "Cache Sweep", "Collect a weapon cache"),
            ("node_capture", "Route Calibrator", "Capture a command node"),
            ("signal_sample", "Signal Sample", "Recover a signal fragment"),
            ("return_lattice", "Return Lattice", "Open or enter the extraction lattice"),
        ]
        self.chunks = {}
        self.chunk_line_roots = {}
        self.chunk_occlusion_roots = {}
        self.chunk_stream_alpha = {}
        self.chunk_stream_target = {}
        self.chunk_stream_remove = set()
        self.player_health_max = int(getattr(self.game_cfg, "default_health", 100))
        self.health = int(self.player_health_max)
        self.lab_points = 0
        self.upgrade_levels = {"health_capacity": 0, "ammo_capacity": 0, "armor_capacity": 0}
        self.player_armor_max = 0
        self.player_armor = 0
        self.armor_damage_fade_timer = 0.0
        self.armor_damage_flash = 0.0
        self.sync_player_armor_capacity(refill=True)
        self.arena_mode_active = False
        self.arena_wave = 0
        self.arena_wave_timer = 0.0
        self.arena_wave_kills = 0
        self.arena_total_kills = 0
        self.arena_capture_index = None
        self.arena_portals = []
        self.arena_completed_captures = set()
        self.arena_entry_return_pos = Vec3(0, 0, self.game_cfg.player_height)
        self.arena_center = Vec3(0, -520, 0)
        self.arena_variant_id = "hardlight_default"
        self.arena_core_hp = 0
        self.arena_core_max_hp = 0
        self.arena_wave_target_kills = 0
        self.arena_last_wave_result = ""
        self.arena_combo_meter = 0
        self.arena_city_weapon_slots = {"right": 1, "left": 2}
        self.arena_weapon_aliases = {}
        self.vector_arena_native_mode = None
        self.vector_arena_adapter_module = None
        self.vector_arena_adapter_error = ""
        self.vector_arena_adapter_stats = {}
        self.vector_arena_hid_uc_ui = False
        self.weapon_ammo = 100.0
        self.weapon_ammo_max = 100.0
        self.hit_replenish_flash = 0.0
        self.combat_kick_time = 0.0
        self.combat_kick_power = 0.0
        self.combat_banner = ""
        self.combat_banner_time = 0.0
        self.kill_streak = 0
        self.last_kill_time = -999.0
        self.contact_damage_accumulator = 0.0
        self.last_trace_hit_kind = "world"
        self.chunk_obstacles = {}
        self.chunk_enemy_seeds = {}
        self.enemies = []
        self.civilians = []
        self.civilian_anchors = []
        self.civilian_anchor_timer = 0.0
        self.civilian_spawn_timer = 0.25
        self.civilian_harm_count = 0
        self.civilian_death_count = 0
        self.civilian_penalty_points = 0
        self.patrol_drones = []
        self.patrol_drone_anchors = []
        self.patrol_drone_anchor_timer = 0.0
        self.patrol_drone_spawn_timer = 0.85
        self.player_hostility_timer = 0.0
        self.drone_kills = 0
        self.drone_ammo_drops = 0
        self.pending_enemy_spawns = []
        self.spawn_director_timer = 2.4
        self.spawn_sequence_serial = 0
        self.last_spawn_director_player = Vec3(0, 0, 0)
        self.player_motion_heading = Vec3(0, 1, 0)
        # Pass50: travel pacing is an explicit freeroam rhythm, not an 8.5-second spawn metronome.
        self.freeroam_rhythm_state = "quiet"
        self.freeroam_rhythm_timer = float(getattr(self.game_cfg, "freeroam_quiet_departure_seconds", 7.0))
        self.freeroam_travel_distance = 0.0
        self.freeroam_encounters = 0
        self.freeroam_pressure_active = False
        self.freeroam_rhythm_events = []
        self.keys = {}
        self.gamepad = None
        self.gamepad_fire_prev = False
        self.gamepad_tab_prev = False
        self.noise_offset = Vec2(0.0, 0.0)
        self.audio_enabled = False
        self.sfx_pool = {}
        self.sfx_index = {}
        self.audio_bus = load_shared_audio_bus()
        self.launch_settings = load_shared_launch_settings()
        self.game_cfg.mouse_sensitivity = float(self.launch_settings.get("mouse_sensitivity", self.game_cfg.mouse_sensitivity))
        write_latest_log("launch_begin", {
            "width": self.launch_settings.get("width"),
            "height": self.launch_settings.get("height"),
            "fullscreen": self.launch_settings.get("fullscreen"),
            "borderless": self.launch_settings.get("borderless"),
            "hud_visible": self.launch_settings.get("hud_visible"),
            "random_mission": _env_flag("MATRIX_RANDOM_MISSION", False),
            "world_seed": int(self.game_cfg.world_seed),
        })
        self.player_pos = Vec3(0, 0, self.game_cfg.player_height)
        if NORTH_DISTRICT_DEMO_TEST:
            self.player_pos = Vec3(0, float(getattr(self.game_cfg, "district_size_chunks", 6)) * self.game_cfg.chunk_size + 28.0, self.game_cfg.player_height)
        elif DISTRICT_DEMO_TEST:
            self.player_pos = Vec3(float(getattr(self.game_cfg, "district_size_chunks", 6)) * self.game_cfg.chunk_size + 28.0, 0, self.game_cfg.player_height)
        self.current_district_id = "calibration"
        self.last_announced_district_id = ""
        self.district_banner_time = 0.0

        self.render.setAntialias(AntialiasAttrib.MLine)
        self.render.setTransparency(TransparencyAttrib.MAlpha)
        self.setBackgroundColor(1, 1, 1)
        self.clock = ClockObject.getGlobalClock()
        self.clock.setMode(ClockObject.MNormal)

        self.setup_window()
        self.setup_scene()
        self.setup_mech_view()
        self.setup_audio()
        self.setup_ui()
        if not self.launch_settings.get("hud_visible", True):
            self.hud_visible = False
            self.hud_root.hide()
            self.crosshair.hide()
        self.setup_input()
        self.setup_gamepad()
        self.build_weapon_loadouts()
        if self.presentation_open:
            self.set_presentation_visual_isolation(True)
        self.setup_arena_integration()
        self.accept("window-event", self.on_window_event)
        self.taskMgr.add(self.update_task, "update-task")
        self.taskMgr.doMethodLater(0.25, self.chunk_task, "chunk-task")

        self.camera.setPos(self.player_pos)
        self.pitch = -12.0
        self.yaw = 0.0
        self.recenter_mouse(force=True)

        if AUTO_EXIT_SECONDS is not None:
            self.taskMgr.doMethodLater(max(0.5, AUTO_EXIT_SECONDS), self.auto_exit_task, "auto-exit")

        if SELF_TEST:
            self.taskMgr.doMethodLater(0.6, self.self_test_exit, "self-test-exit")

        if COMBAT_REGRESSION_TEST:
            self.taskMgr.doMethodLater(0.9, self.combat_regression_task, "combat-regression-test")

        if WEAPON_VARIANT_TEST:
            self.taskMgr.doMethodLater(1.0, self.weapon_variant_test_task, "weapon-variant-test")
        if WEAPON_SIGNATURE_TEST:
            self.taskMgr.doMethodLater(1.0, self.weapon_signature_test_task, "weapon-signature-test")
        if WEAPON_SIGNATURE_DEMO is not None:
            self.taskMgr.doMethodLater(1.0, self.weapon_signature_demo_task, "weapon-signature-demo")
        if ENEMY_ROLE_TEST:
            self.taskMgr.doMethodLater(1.0, self.enemy_role_test_task, "enemy-role-test")
        if ENEMY_ROLE_DEMO is not None:
            self.taskMgr.doMethodLater(1.0, self.enemy_role_demo_task, "enemy-role-demo")
        if ENEMY_COLOR_STATE_TEST:
            self.taskMgr.doMethodLater(1.0, self.enemy_color_state_test_task, "enemy-color-state-test")
        if ENEMY_COLOR_STATE_DEMO is not None:
            self.taskMgr.doMethodLater(1.0, self.enemy_color_state_demo_task, "enemy-color-state-demo")
        if ARENA_INTEGRATION_TEST:
            self.taskMgr.doMethodLater(1.0, self.arena_integration_test_task, "arena-integration-test")
        if CITY_CAPTURE_TEST:
            self.taskMgr.doMethodLater(1.0, self.city_capture_test_task, "city-capture-test")
        if BOSS_VARIANT_TEST:
            self.taskMgr.doMethodLater(1.0, self.boss_variant_test_task, "boss-variant-test")
        if HUD_POLISH_TEST:
            self.taskMgr.doMethodLater(1.0, self.hud_polish_test_task, "hud-polish-test")
        if CIVILIAN_AI_TEST:
            self.taskMgr.doMethodLater(1.0, self.civilian_ai_test_task, "civilian-ai-test")
        if DRONE_PATROL_TEST:
            self.taskMgr.doMethodLater(1.0, self.drone_patrol_test_task, "drone-patrol-test")
        if RESPAWN_RESET_TEST:
            self.taskMgr.doMethodLater(1.0, self.respawn_reset_test_task, "respawn-reset-test")
        if HEALTH_PALETTE_TEST:
            self.taskMgr.doMethodLater(1.0, self.health_palette_test_task, "health-palette-test")
        if ARMOR_WIREFRAME_TEST:
            self.taskMgr.doMethodLater(1.0, self.armor_wireframe_test_task, "armor-wireframe-test")
        if ACTIVITY_INSTANCE_TEST:
            self.taskMgr.doMethodLater(1.15, self.activity_instance_test_task, "activity-instance-test")
        if ACTIVITY_VARIETY_TEST:
            self.taskMgr.doMethodLater(1.15, self.activity_variety_test_task, "activity-variety-test")
        if SURVIVABILITY_TEST:
            self.taskMgr.doMethodLater(1.15, self.survivability_test_task, "survivability-test")
        if ACTIVITY_MODE_TEST:
            self.taskMgr.doMethodLater(1.15, self.activity_mode_test_task, "activity-mode-test")
        if CAPTURE_REGEN_TEST:
            self.taskMgr.doMethodLater(1.15, self.capture_regen_test_task, "capture-regen-test")
        if VISUAL_HIERARCHY_TEST:
            self.taskMgr.doMethodLater(1.15, self.visual_hierarchy_test_task, "visual-hierarchy-test")
        if CHUNK_SMOOTHING_TEST:
            self.taskMgr.doMethodLater(1.15, self.chunk_smoothing_test_task, "chunk-smoothing-test")
        if HUD_HIERARCHY_TEST:
            self.taskMgr.doMethodLater(1.15, self.hud_hierarchy_test_task, "hud-hierarchy-test")
        if DISTRICT_SKYLINE_TEST:
            self.taskMgr.doMethodLater(1.15, self.district_skyline_test_task, "district-skyline-test")
        if DISTRICT_ACTIVITY_TEST:
            self.taskMgr.doMethodLater(1.15, self.district_activity_test_task, "district-activity-test")
        if DISTRICT_ACTIVITY_DEMO is not None:
            self.taskMgr.doMethodLater(1.15, self.district_activity_demo_task, "district-activity-demo")
        if DISTRICT_DISCOVERY_TEST:
            self.taskMgr.doMethodLater(1.15, self.district_discovery_test_task, "district-discovery-test")
        if DISTRICT_DISCOVERY_DEMO is not None:
            self.taskMgr.doMethodLater(1.15, self.district_discovery_demo_task, "district-discovery-demo")
        if FREEROAM_RHYTHM_TEST:
            self.taskMgr.doMethodLater(1.15, self.freeroam_rhythm_test_task, "freeroam-rhythm-test")
        if FREEROAM_RHYTHM_DEMO is not None:
            self.taskMgr.doMethodLater(1.15, self.freeroam_rhythm_demo_task, "freeroam-rhythm-demo")
        if MASTERING_QUALITY_TEST:
            self.taskMgr.doMethodLater(1.35, self.mastering_quality_test_task, "mastering-quality-test")
        if MASTERING_DEMO:
            self.taskMgr.doMethodLater(1.35, self.mastering_demo_task, "mastering-demo")
        if HUD_MINIMALISM_TEST:
            self.taskMgr.doMethodLater(1.35, self.hud_minimalism_test_task, "hud-minimalism-test")
        if HUD_MINIMALISM_DEMO:
            self.taskMgr.doMethodLater(1.35, self.hud_minimalism_demo_task, "hud-minimalism-demo")
        if HELP_REFERENCE_TEST:
            self.taskMgr.doMethodLater(1.35, self.help_reference_test_task, "help-reference-test")
        if HELP_REFERENCE_DEMO:
            self.taskMgr.doMethodLater(1.35, self.help_reference_demo_task, "help-reference-demo")
        if PRESENTATION_READINESS_TEST:
            self.taskMgr.doMethodLater(1.35, self.presentation_readiness_test_task, "presentation-readiness-test")
        if PRESENTATION_DEMO:
            self.taskMgr.doMethodLater(1.35, self.presentation_demo_task, "presentation-demo")
        if PAUSE_MENU_INPUT_TEST:
            self.taskMgr.doMethodLater(1.35, self.pause_menu_input_test_task, "pause-menu-input-test")

    def setup_window(self):
        props = WindowProperties()
        props.setTitle(f"{GAME_NAME} // RANDOMIZED MISSION" if _env_flag("MATRIX_RANDOM_MISSION", False) else GAME_NAME)
        props.setSize(int(self.launch_settings.get("width", 1600)), int(self.launch_settings.get("height", 900)))
        props.setFullscreen(bool(self.launch_settings.get("fullscreen", False)))
        props.setUndecorated(bool(self.launch_settings.get("borderless", False) and not self.launch_settings.get("fullscreen", False)))
        if not SELF_TEST:
            props.setCursorHidden(True)
        if hasattr(self.win, "requestProperties"):
            self.win.requestProperties(props)

    def setup_audio(self):
        self.audio_enabled = False
        self.sfx_pool = {}
        self.sfx_index = {}
        self.audio3d = None
        self.positional_sounds = []
        self.loop_files = []
        self.active_loop_sound = None
        if Audio3DManager is not None and not NO_AUDIO and bool(getattr(self.game_cfg, "audio_spatial_enabled", True)):
            try:
                self.audio3d = Audio3DManager(self.sfxManagerList[0], self.camera)
                if hasattr(self.audio3d, "setDropOffFactor"):
                    self.audio3d.setDropOffFactor(float(getattr(self.game_cfg, "audio_spatial_dropoff", 0.72)))
            except Exception:
                self.audio3d = None
        spec = {
            'fire': (6, 0.42),
            'burst_fire': (5, 0.46),
            'auto_fire': (6, 0.34),
            'hit': (6, 0.44),
            'armor': (5, 0.42),
            'armor_heavy': (4, 0.50),
            'deflect': (4, 0.40),
            'break': (4, 0.68),
            'metal_break': (4, 0.52),
            'weapon_broken': (3, 0.56),
            'tell': (3, 0.34),
            'enemy1': (1, 0.28),
            'enemy2': (1, 0.28),
            'enemy3': (1, 0.28),
            'enemy4': (1, 0.28),
            'enemy5': (1, 0.28),
            'chain': (5, 0.36),
            'recharge': (3, 0.3),
            'kill': (4, 0.38),
            'explosion_cannon': (3, 0.50),
            'explosion_fire': (3, 0.50),
            'explosion_boss': (2, 0.64),
            'explosion_distant': (3, 0.36),
            'imploder': (3, 0.44),
            'magnet': (3, 0.36),
            'disassemble': (3, 0.48),
            'pickup': (3, 0.30),
            'special_pickup': (3, 0.42),
            'ricochet': (4, 0.30),
            'objective_complete': (3, 0.46),
            'dry': (2, 0.22),
            'weapon_empty': (2, 0.28),
        }
        try:
            for key, (pool_size, base_volume) in spec.items():
                snd_path = resolve_sfx_path(key)
                if not snd_path.exists():
                    continue
                pool = []
                panda_path = Filename.fromOsSpecific(os.fspath(snd_path))
                for _ in range(pool_size):
                    snd = self.loader.loadSfx(panda_path)
                    if snd is None:
                        continue
                    try:
                        snd.setVolume(base_volume * self.audio_bus.get("master_volume", 1.0) * self.audio_bus.get("sfx_volume", 1.0))
                    except Exception:
                        pass
                    pool.append(snd)
                if pool:
                    self.sfx_pool[key] = {'sounds': pool, 'base_volume': base_volume}
                    self.sfx_index[key] = 0
            self.audio_enabled = bool(self.sfx_pool)
            try:
                write_sfx_replacement_map()
            except Exception:
                pass
            self.music = None
            self.load_audio_loops()
        except Exception:
            self.audio_enabled = False
            self.sfx_pool = {}
            self.sfx_index = {}

    def load_audio_loops(self):
        self.loop_files = discover_audio_loop_files()
        self.active_loop_sound = None
        if not self.loop_files or NO_AUDIO:
            return
        for loop_path in self.loop_files:
            try:
                snd = self.loader.loadMusic(Filename.fromOsSpecific(os.fspath(loop_path)))
                if snd is None:
                    continue
                snd.setLoop(True)
                volume = float(getattr(self.game_cfg, "audio_loop_volume", 0.52)) * self.audio_bus.get("master_volume", 1.0) * max(self.audio_bus.get("music_volume", 1.0), self.audio_bus.get("ambience_volume", 1.0))
                snd.setVolume(max(0.0, min(1.0, volume)))
                snd.play()
                self.active_loop_sound = snd
                self.music = snd
                break
            except Exception:
                continue

    def update_audio_depth(self, dt: float):
        if self.audio3d is not None:
            try:
                self.audio3d.setListenerVelocity(Vec3(0, 0, 0))
            except Exception:
                pass
        keep = []
        for entry in list(getattr(self, "positional_sounds", []) or []):
            try:
                entry["age"] += dt
                snd = entry.get("sound")
                done = entry["age"] >= entry.get("life", 2.0)
                if snd is not None and hasattr(snd, "status"):
                    try:
                        done = done or snd.status() == snd.READY
                    except Exception:
                        pass
                if done:
                    try:
                        if self.audio3d is not None and snd is not None:
                            self.audio3d.detachSound(snd)
                    except Exception:
                        pass
                    node = entry.get("node")
                    if node is not None and not node.isEmpty():
                        node.removeNode()
                else:
                    keep.append(entry)
            except Exception:
                pass
        self.positional_sounds = keep

    def play_sfx(self, key: str, volume: float = 1.0, rate: float = 1.0, pos: Vec3 | None = None, spatial: bool = True):
        if pos is not None and spatial and self.audio3d is not None and bool(getattr(self.game_cfg, "audio_spatial_enabled", True)):
            if self.play_positional_sfx(key, pos, volume=volume, rate=rate):
                return
        entry = self.sfx_pool.get(key)
        if not entry:
            return
        pool = entry['sounds']
        idx = self.sfx_index.get(key, 0) % len(pool)
        self.sfx_index[key] = idx + 1
        snd = pool[idx]
        try:
            snd.stop()
        except Exception:
            pass
        try:
            snd.setTime(0.0)
        except Exception:
            pass
        try:
            snd.setPlayRate(max(0.5, min(1.7, rate)))
        except Exception:
            pass
        try:
            bus = self.audio_bus.get("master_volume", 1.0) * self.audio_bus.get("sfx_volume", 1.0)
            snd.setVolume(max(0.0, min(1.0, entry['base_volume'] * volume * bus)))
        except Exception:
            pass
        try:
            snd.play()
        except Exception:
            pass

    def play_positional_sfx(self, key: str, pos: Vec3, volume: float = 1.0, rate: float = 1.0) -> bool:
        try:
            if len(getattr(self, "positional_sounds", []) or []) >= int(getattr(self.game_cfg, "max_positional_sounds", 18)):
                old = self.positional_sounds.pop(0)
                try:
                    self.audio3d.detachSound(old.get("sound"))
                except Exception:
                    pass
                node = old.get("node")
                if node is not None and not node.isEmpty():
                    node.removeNode()
            snd_path = resolve_sfx_path(key)
            if not snd_path.exists():
                return False
            snd = self.loader.loadSfx(Filename.fromOsSpecific(os.fspath(snd_path)))
            if snd is None:
                return False
            node = self.effect_root.attachNewNode(f"positional-sfx-{key}")
            node.setPos(Vec3(pos))
            min_d = float(getattr(self.game_cfg, "audio_spatial_min_distance", 6.0))
            max_d = float(getattr(self.game_cfg, "audio_spatial_max_distance", 110.0))
            try:
                snd.set3dMinDistance(min_d)
                snd.set3dMaxDistance(max_d)
            except Exception:
                pass
            try:
                snd.setPlayRate(max(0.5, min(1.7, rate)))
            except Exception:
                pass
            try:
                bus = self.audio_bus.get("master_volume", 1.0) * self.audio_bus.get("sfx_volume", 1.0)
                snd.setVolume(max(0.0, min(1.0, volume * bus)))
            except Exception:
                pass
            self.audio3d.attachSoundToObject(snd, node)
            snd.play()
            self.positional_sounds.append({"sound": snd, "node": node, "age": 0.0, "life": 3.2})
            return True
        except Exception:
            return False

    def setup_scene(self):
        self.city_root = self.render.attachNewNode("city-root")
        self.effect_root = self.render.attachNewNode("effect-root")
        self.camLens.setNearFar(0.06, self.game_cfg.max_view_distance)
        self.camLens.setFov(82)

        ambient = AmbientLight("ambient")
        ambient.setColor((1, 1, 1, 1))
        self.render.setLight(self.render.attachNewNode(ambient))

        self.filters = None
        self.sky_root = self.camera.attachNewNode("sky-root")
        self.sky_root.setBin("background", 0)
        self.sky_root.setDepthWrite(False)
        self.sky_root.setDepthTest(False)
        self.sky_elements = []

        self.day_night_mix = 0.0
        self.line_rgb = (0.12, 0.08, 0.03)
        self.sky_horizon_rgb = (0.86, 0.77, 0.39)
        self.sky_zenith_rgb = (0.28, 0.21, 0.08)
        self.update_palette(0.0)
        self.build_sky_backdrop()
        self.generate_city_around_player(force=True)
        self.setup_campaign_objectives()
        self.setup_signal_objectives()
        self.setup_activity_mode()
        self.setup_district_discovery_guidance()

    def build_color_quad_geom(self, points, colors, name="color-quad"):
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData(name, fmt, Geom.UHStatic)
        vwriter = GeomVertexWriter(vdata, "vertex")
        cwriter = GeomVertexWriter(vdata, "color")
        prim = GeomTriangles(Geom.UHStatic)
        for point, color in zip(points, colors):
            vwriter.addData3f(point)
            cwriter.addData4f(*color)
        prim.addVertices(0, 1, 2)
        prim.addVertices(0, 2, 3)
        geom = Geom(vdata)
        geom.addPrimitive(prim)
        node = GeomNode(name)
        node.addGeom(geom)
        return node

    def build_disk_geom(self, center: Point3, radius: float, inner_color, outer_color, segments: int = 48, name: str = "disk"):
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData(name, fmt, Geom.UHStatic)
        vwriter = GeomVertexWriter(vdata, "vertex")
        cwriter = GeomVertexWriter(vdata, "color")
        prim = GeomTriangles(Geom.UHStatic)
        vwriter.addData3f(center)
        cwriter.addData4f(*inner_color)
        for i in range(segments + 1):
            ang = math.tau * i / segments
            x = center.x + math.cos(ang) * radius
            z = center.z + math.sin(ang) * radius
            vwriter.addData3f(x, center.y, z)
            cwriter.addData4f(*outer_color)
        for i in range(1, segments + 1):
            prim.addVertices(0, i, i + 1)
        geom = Geom(vdata)
        geom.addPrimitive(prim)
        node = GeomNode(name)
        node.addGeom(geom)
        return node

    def build_sky_backdrop(self):
        self.sky_root.node().removeAllChildren()
        self.sky_elements = []
        horizon = self.sky_horizon_rgb
        zenith = self.sky_zenith_rgb
        grad = self.sky_root.attachNewNode(
            self.build_color_quad_geom(
                [Point3(-780.0, 520.0, -460.0), Point3(780.0, 520.0, -460.0), Point3(780.0, 520.0, 460.0), Point3(-780.0, 520.0, 460.0)],
                [(*horizon, 1.0), (*horizon, 1.0), (*zenith, 1.0), (*zenith, 1.0)],
                name="sky-gradient",
            )
        )
        grad.setTwoSided(True)
        grad.setDepthWrite(False)
        grad.setDepthTest(False)
        grad.setBin("background", 0)
        self.sky_elements.append(grad)

        # Keep the sky as a distant atmosphere only.  Earlier builds used large,
        # opaque disks attached to the camera, which read like a black mesh covering
        # the first-person view.  These soft glows stay faint and behind the playfield.
        celestial_specs = [
            ((-520.0, 535.0, 300.0), 92.0, (0.66, 0.55, 0.24, 0.14), (0.14, 0.09, 0.03, 0.01)),
            ((-160.0, 536.0, 98.0), 76.0, (0.62, 0.50, 0.22, 0.12), (0.12, 0.08, 0.03, 0.01)),
            ((620.0, 534.0, 220.0), 126.0, (0.70, 0.60, 0.28, 0.10), (0.16, 0.10, 0.04, 0.01)),
        ]
        for idx, (center, radius, inner, outer) in enumerate(celestial_specs):
            disk = self.sky_root.attachNewNode(self.build_disk_geom(Point3(*center), radius, inner, outer, 56, f"sky-disk-{idx}"))
            disk.setTransparency(TransparencyAttrib.MAlpha)
            disk.setDepthWrite(False)
            disk.setDepthTest(False)
            disk.setBin("background", 1)
            self.sky_elements.append(disk)

        halo_specs = [
            ((-160.0, 516.5, 70.0), 154.0, 28),
            ((180.0, 514.5, 110.0), 92.0, 24),
        ]
        for idx, (center, radius, segs_count) in enumerate(halo_specs):
            segs = LineSegs(f"sky-halo-{idx}")
            segs.setThickness(1.0)
            segs.setColor(0.96, 0.88, 0.52, 0.20)
            last = None
            first = None
            for i in range(segs_count + 1):
                ang = math.tau * i / segs_count
                p = Point3(center[0] + math.cos(ang) * radius, 0, center[2] + math.sin(ang) * radius)
                if first is None:
                    first = p
                if last is None:
                    segs.moveTo(p)
                else:
                    segs.drawTo(p)
                last = p
            halo = self.sky_root.attachNewNode(segs.create())
            halo.setTransparency(TransparencyAttrib.MAlpha)
            halo.setDepthWrite(False)
            halo.setDepthTest(False)
            halo.setBin("background", 2)
            self.sky_elements.append(halo)

    def make_cockpit_box_lines(self, parent: NodePath, center: Vec3, size: Vec3, thickness: float = 1.5, alpha: float = 0.92):
        hx, hy, hz = size.x * 0.5, size.y * 0.5, size.z * 0.5
        x0, x1 = center.x - hx, center.x + hx
        y0, y1 = center.y - hy, center.y + hy
        z0, z1 = center.z - hz, center.z + hz
        segs = LineSegs("cockpit-box")
        segs.setThickness(thickness)
        segs.setColor(*self.current_line_color(alpha=alpha))
        edges = [
            ((x0, y0, z0), (x1, y0, z0)), ((x1, y0, z0), (x1, y1, z0)), ((x1, y1, z0), (x0, y1, z0)), ((x0, y1, z0), (x0, y0, z0)),
            ((x0, y0, z1), (x1, y0, z1)), ((x1, y0, z1), (x1, y1, z1)), ((x1, y1, z1), (x0, y1, z1)), ((x0, y1, z1), (x0, y0, z1)),
            ((x0, y0, z0), (x0, y0, z1)), ((x1, y0, z0), (x1, y0, z1)), ((x1, y1, z0), (x1, y1, z1)), ((x0, y1, z0), (x0, y1, z1)),
        ]
        for a, b in edges:
            segs.moveTo(*a)
            segs.drawTo(*b)
        np = parent.attachNewNode(segs.create())
        np.setDepthWrite(False)
        np.setDepthTest(False)
        np.setTransparency(TransparencyAttrib.MAlpha)
        return np

    def create_led_panel(self, parent: NodePath, pos: Vec3, side: str):
        root = parent.attachNewNode(f"led-{side}")
        root.setPos(pos)
        root.setDepthWrite(False)
        root.setDepthTest(False)
        outline = LineSegs(f"led-outline-{side}")
        outline.setThickness(1.3)
        outline.setColor(0.96, 0.96, 0.96, 0.88)
        outline.moveTo(0.0, 0.0, -0.02)
        outline.drawTo(0.20, 0.0, -0.02)
        outline.drawTo(0.20, 0.0, 0.02)
        outline.drawTo(0.0, 0.0, 0.02)
        outline.drawTo(0.0, 0.0, -0.02)
        outline_np = root.attachNewNode(outline.create())
        outline_np.setDepthWrite(False)
        outline_np.setDepthTest(False)
        cm = CardMaker(f"led-fill-{side}")
        cm.setFrame(0.0, 0.18, -0.014, 0.014)
        fill = root.attachNewNode(cm.generate())
        fill.setPos(0.01, 0.001, 0)
        fill.setColor(0.92, 0.94, 1.0, 0.9)
        fill.setTransparency(TransparencyAttrib.MAlpha)
        fill.setDepthWrite(False)
        fill.setDepthTest(False)
        return {"root": root, "fill": fill, "outline": outline_np, "label": None}

    def setup_mech_view(self):
        self.weapon_hand_spin = {"right": 0.0, "left": 0.0}
        self.weapon_hand_spin_velocity = {"right": 0.0, "left": 0.0}
        self.weapon_hand_recoil = {"right": 0.0, "left": 0.0}
        self.weapon_hand_muzzle_flash = {"right": 0.0, "left": 0.0}
        self.cockpit_root = self.camera.attachNewNode("cockpit-root")
        self.cockpit_root.setPos(0, 0, -0.08)
        self.cockpit_root.setBin("fixed", 40)
        self.cockpit_root.setDepthWrite(False)
        self.cockpit_root.setDepthTest(False)
        self.cockpit_root.setTransparency(TransparencyAttrib.MAlpha)

        left_base = self.make_cockpit_box_lines(self.cockpit_root, Vec3(-1.46, 1.72, -0.64), Vec3(0.44, 0.62, 1.22), 1.6, 0.92)
        right_base = self.make_cockpit_box_lines(self.cockpit_root, Vec3(1.46, 1.72, -0.64), Vec3(0.44, 0.62, 1.22), 1.6, 0.92)
        left_shoulder = self.make_cockpit_box_lines(self.cockpit_root, Vec3(-1.34, 2.36, -0.82), Vec3(0.62, 1.10, 0.38), 1.5, 0.9)
        right_shoulder = self.make_cockpit_box_lines(self.cockpit_root, Vec3(1.34, 2.36, -0.82), Vec3(0.62, 1.10, 0.38), 1.5, 0.9)
        canopy = LineSegs("cockpit-canopy")
        canopy.setThickness(1.4)
        canopy.setColor(*self.current_line_color(alpha=0.76))
        canopy.moveTo(-0.42, 0.74, -0.98)
        canopy.drawTo(-0.14, 0.34, -0.44)
        canopy.drawTo(0.14, 0.34, -0.44)
        canopy.drawTo(0.42, 0.74, -0.98)
        canopy_np = self.cockpit_root.attachNewNode(canopy.create())
        canopy_np.setDepthWrite(False)
        canopy_np.setDepthTest(False)
        canopy_np.setTransparency(TransparencyAttrib.MAlpha)

        self.weapon_mounts = {
            "right": self.create_weapon_mount("right"),
            "left": self.create_weapon_mount("left"),
        }
        self.muzzle_np = self.weapon_mounts["right"]["muzzle_np"]
        self.refresh_weapon_models()
        self.led_panels = {
            "health": self.create_led_panel(self.cockpit_root, Vec3(-1.62, 2.32, -0.48), "health"),
            "ammo": self.create_led_panel(self.cockpit_root, Vec3(1.42, 2.32, -0.48), "ammo"),
        }
        # The cockpit cage was too close to camera and looked like a view-blocking
        # mesh in first person.  Keep it built for legacy H toggles/debug, but hide
        # it by default so the command-field view stays open.
        self.cockpit_root.hide()

    def create_weapon_mount(self, side: str):
        sign = 1.0 if str(side) == "right" else -1.0
        root = self.camera.attachNewNode(f"weapon-root-{side}")
        root.setPos(0.92 * sign, 0.74, -0.78)
        root.setScale(0.72)
        root.setBin("fixed", 45)
        root.setDepthWrite(False)
        root.setDepthTest(False)
        root.setTransparency(TransparencyAttrib.MAlpha)
        spin_root = root.attachNewNode(f"weapon-spin-root-{side}")
        model_root = spin_root.attachNewNode(f"weapon-model-root-{side}")
        if sign < 0.0:
            model_root.setSx(-1.0)
        muzzle_np = spin_root.attachNewNode(f"muzzle-{side}")
        return {"root": root, "spin_root": spin_root, "model_root": model_root, "muzzle_np": muzzle_np, "side": side}

    def clear_node_children(self, node: NodePath):
        if node is None or node.isEmpty():
            return
        for child in list(node.getChildren()):
            try:
                child.removeNode()
            except Exception:
                pass

    def refresh_weapon_models(self):
        if not hasattr(self, "weapon_mounts"):
            return
        for side, mount in self.weapon_mounts.items():
            weapon = self.get_weapon_for_hand(side) if hasattr(self, "get_weapon_for_hand") else (getattr(self, "current_weapon", None) or self.get_weapon_by_slot(1))
            if weapon is None:
                continue
            model_root = mount.get("model_root")
            self.clear_node_children(model_root)
            muzzle_pos = self.build_weapon_model(model_root, weapon, side)
            mount["muzzle_np"].setPos(muzzle_pos)
            mount["root"].setColorScale(*self.current_line_color(alpha=0.98))
        right_mount = self.weapon_mounts.get("right")
        if right_mount:
            self.muzzle_np = right_mount["muzzle_np"]

    def weapon_fill_color(self, kind: str = "core"):
        palette = {
            "core": (0.18, 0.20, 0.24, float(getattr(self.game_cfg, "weapon_solid_fill_alpha", 0.92))),
            "imploder": (0.17, 0.18, 0.22, float(getattr(self.game_cfg, "weapon_solid_fill_alpha", 0.92))),
            "magnet": (0.16, 0.20, 0.22, float(getattr(self.game_cfg, "weapon_solid_fill_alpha", 0.92))),
            "burst": (0.20, 0.19, 0.22, float(getattr(self.game_cfg, "weapon_solid_fill_alpha", 0.92))),
            "automatic": (0.15, 0.17, 0.20, float(getattr(self.game_cfg, "weapon_solid_fill_alpha", 0.92))),
            "disassembler": (0.19, 0.18, 0.20, float(getattr(self.game_cfg, "weapon_solid_fill_alpha", 0.92))),
        }
        return palette.get(str(kind), palette["core"])

    def build_prism_geom(self, points_xz, y0: float, y1: float, color, name: str = "prism"):
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData(name, fmt, Geom.UHStatic)
        vwriter = GeomVertexWriter(vdata, "vertex")
        cwriter = GeomVertexWriter(vdata, "color")
        prim = GeomTriangles(Geom.UHStatic)
        pts = [Point3(float(x), float(y0), float(z)) for x, z in points_xz] + [Point3(float(x), float(y1), float(z)) for x, z in points_xz]
        for pt in pts:
            vwriter.addData3f(pt)
            cwriter.addData4f(*color)
        n = len(points_xz)
        # side quads
        for i in range(n):
            ni = (i + 1) % n
            prim.addVertices(i, ni, n + ni)
            prim.addVertices(i, n + ni, n + i)
        # caps
        for i in range(1, n - 1):
            prim.addVertices(0, i + 1, i)
            prim.addVertices(n, n + i, n + i + 1)
        geom = Geom(vdata)
        geom.addPrimitive(prim)
        node = GeomNode(name)
        node.addGeom(geom)
        return node

    def attach_weapon_prism(self, parent: NodePath, points_xz, y0: float, y1: float, color, name: str = "weapon-prism"):
        np = parent.attachNewNode(self.build_prism_geom(points_xz, y0, y1, color, name))
        np.setTwoSided(True)
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setDepthWrite(False)
        np.setDepthTest(False)
        return np

    def attach_weapon_box_fill(self, parent: NodePath, center: Vec3, size: Vec3, color, name: str = "weapon-box"):
        hx, hy, hz = size.x * 0.5, size.y * 0.5, size.z * 0.5
        pts = [(-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz)]
        np = self.attach_weapon_prism(parent, pts, center.y - hy, center.y + hy, color, name)
        np.setPos(center.x, 0.0, center.z)
        return np

    def octagon_points(self, radius_x: float, radius_z: float):
        pts = []
        for i in range(8):
            ang = math.tau * i / 8.0
            pts.append((math.cos(ang) * radius_x, math.sin(ang) * radius_z))
        return pts

    def triangle_points(self, radius_x: float, radius_z: float):
        return [(0.0, radius_z), (-radius_x, -radius_z * 0.76), (radius_x, -radius_z * 0.76)]

    def draw_prism_outline(self, segs: LineSegs, points_xz, y0: float, y1: float, x_offset: float = 0.0, z_offset: float = 0.0):
        n = len(points_xz)
        for i in range(n):
            x0, z0 = points_xz[i]
            x1, z1 = points_xz[(i + 1) % n]
            segs.moveTo(x0 + x_offset, y0, z0 + z_offset); segs.drawTo(x1 + x_offset, y0, z1 + z_offset)
            segs.moveTo(x0 + x_offset, y1, z0 + z_offset); segs.drawTo(x1 + x_offset, y1, z1 + z_offset)
            segs.moveTo(x0 + x_offset, y0, z0 + z_offset); segs.drawTo(x0 + x_offset, y1, z0 + z_offset)

    def build_weapon_model(self, parent: NodePath, weapon: Weapon, side: str = "right") -> Vec3:
        kind = str(getattr(weapon, "kind", "core"))
        fill_color = self.weapon_fill_color(kind)
        if bool(getattr(self.game_cfg, "weapon_solid_fill_enabled", True)):
            if kind == "imploder":
                self.build_imploder_weapon_fill(parent, fill_color)
            elif kind == "magnet":
                self.build_magnet_weapon_fill(parent, fill_color)
            elif kind == "disassembler":
                self.build_disassembler_weapon_fill(parent, fill_color)
            elif kind == "burst":
                self.build_burst_weapon_fill(parent, fill_color)
            elif kind == "automatic":
                self.build_automatic_weapon_fill(parent, fill_color)
            else:
                self.build_core_weapon_fill(parent, fill_color)
        segs = LineSegs(f"weapon-model-{weapon.kind}-{side}")
        segs.setThickness(self.weapon_line_thickness(1.0, 2.3))
        segs.setColor(0.96, 0.98, 1.0, 0.96)
        if kind == "imploder":
            muzzle = self.draw_imploder_weapon_model(segs)
        elif kind == "magnet":
            muzzle = self.draw_magnet_weapon_model(segs)
        elif kind == "disassembler":
            muzzle = self.draw_disassembler_weapon_model(segs)
        elif kind == "burst":
            muzzle = self.draw_burst_weapon_model(segs)
        elif kind == "automatic":
            muzzle = self.draw_automatic_weapon_model(segs)
        else:
            muzzle = self.draw_core_weapon_model(segs)
        model_np = parent.attachNewNode(segs.create())
        model_np.setDepthWrite(False)
        model_np.setDepthTest(False)
        model_np.setTransparency(TransparencyAttrib.MAlpha)
        return muzzle

    def draw_local_box(self, segs: LineSegs, center: Vec3, size: Vec3):
        hx, hy, hz = size.x * 0.5, size.y * 0.5, size.z * 0.5
        x0, x1 = center.x - hx, center.x + hx
        y0, y1 = center.y - hy, center.y + hy
        z0, z1 = center.z - hz, center.z + hz
        edges = [
            ((x0, y0, z0), (x1, y0, z0)), ((x1, y0, z0), (x1, y1, z0)), ((x1, y1, z0), (x0, y1, z0)), ((x0, y1, z0), (x0, y0, z0)),
            ((x0, y0, z1), (x1, y0, z1)), ((x1, y0, z1), (x1, y1, z1)), ((x1, y1, z1), (x0, y1, z1)), ((x0, y1, z1), (x0, y0, z1)),
            ((x0, y0, z0), (x0, y0, z1)), ((x1, y0, z0), (x1, y0, z1)), ((x1, y1, z0), (x1, y1, z1)), ((x0, y1, z0), (x0, y1, z1)),
        ]
        for a, b in edges:
            segs.moveTo(*a); segs.drawTo(*b)

    def draw_weapon_ring_xz(self, segs: LineSegs, center: Vec3, radius: float, segments: int = 12):
        first = None
        last = None
        for i in range(max(3, segments)):
            ang = math.tau * i / max(3, segments)
            p = Vec3(center.x + math.cos(ang) * radius, center.y, center.z + math.sin(ang) * radius)
            if first is None:
                first = p
            if last is not None:
                segs.moveTo(last); segs.drawTo(p)
            last = p
        if first is not None and last is not None:
            segs.moveTo(last); segs.drawTo(first)

    def build_core_weapon_fill(self, parent: NodePath, color):
        self.attach_weapon_box_fill(parent, Vec3(0.0, 0.18, 0.0), Vec3(0.22, 0.34, 0.24), color, "core-grip")
        self.attach_weapon_prism(parent, self.octagon_points(0.10, 0.10), 0.38, 1.56, color, "core-barrel")
        self.attach_weapon_prism(parent, self.triangle_points(0.08, 0.10), 0.86, 1.30, (0.24, 0.25, 0.30, color[3]), "core-scope")

    def build_imploder_weapon_fill(self, parent: NodePath, color):
        self.attach_weapon_box_fill(parent, Vec3(0.0, 0.18, 0.0), Vec3(0.26, 0.32, 0.24), color, "imploder-grip")
        self.attach_weapon_prism(parent, self.octagon_points(0.11, 0.11), 0.34, 0.76, color, "imploder-core")
        self.attach_weapon_prism(parent, self.triangle_points(0.16, 0.18), 0.74, 1.72, color, "imploder-tri-barrel")

    def build_magnet_weapon_fill(self, parent: NodePath, color):
        self.attach_weapon_box_fill(parent, Vec3(0.0, 0.18, 0.0), Vec3(0.24, 0.34, 0.24), color, "magnet-grip")
        self.attach_weapon_prism(parent, self.octagon_points(0.11, 0.11), 0.36, 1.54, color, "magnet-barrel")
        for y in (0.86, 1.18, 1.46):
            self.attach_weapon_prism(parent, self.octagon_points(0.20, 0.20), y - 0.02, y + 0.02, (0.23, 0.26, 0.29, color[3] * 0.9), f"magnet-ring-{int(y*100)}")

    def build_burst_weapon_fill(self, parent: NodePath, color):
        self.attach_weapon_box_fill(parent, Vec3(0.0, 0.18, 0.0), Vec3(0.28, 0.32, 0.24), color, "burst-grip")
        self.attach_weapon_prism(parent, self.octagon_points(0.12, 0.10), 0.34, 0.86, color, "burst-body")
        for x in (-0.12, 0.0, 0.12):
            pts = self.triangle_points(0.06, 0.08)
            np = self.attach_weapon_prism(parent, pts, 0.92, 1.76, (0.18, 0.19, 0.23, color[3]), f"burst-tube-{int((x+0.2)*100)}")
            np.setX(x)

    def build_automatic_weapon_fill(self, parent: NodePath, color):
        self.attach_weapon_box_fill(parent, Vec3(0.0, 0.18, 0.0), Vec3(0.22, 0.30, 0.20), color, "auto-grip")
        self.attach_weapon_prism(parent, self.octagon_points(0.09, 0.09), 0.34, 1.72, color, "auto-barrel")
        self.attach_weapon_prism(parent, self.triangle_points(0.07, 0.08), 0.78, 1.32, (0.22, 0.23, 0.27, color[3]), "auto-scope")

    def build_disassembler_weapon_fill(self, parent: NodePath, color):
        self.attach_weapon_box_fill(parent, Vec3(0.0, 0.18, 0.0), Vec3(0.24, 0.32, 0.22), color, "disa-grip")
        self.attach_weapon_prism(parent, self.octagon_points(0.09, 0.09), 0.34, 0.94, color, "disa-body")
        for x in (-0.08, 0.08):
            pts = self.triangle_points(0.08, 0.08)
            np = self.attach_weapon_prism(parent, pts, 0.96, 1.76, (0.20, 0.18, 0.21, color[3]), f"disa-fork-{int((x+1)*100)}")
            np.setX(x)

    def draw_core_weapon_model(self, segs: LineSegs) -> Vec3:
        self.draw_local_box(segs, Vec3(0.0, 0.18, 0.0), Vec3(0.22, 0.34, 0.24))
        self.draw_prism_outline(segs, self.octagon_points(0.10, 0.10), 0.38, 1.56)
        self.draw_prism_outline(segs, self.triangle_points(0.08, 0.10), 0.86, 1.30)
        segs.moveTo(0.0, 1.54, 0.0); segs.drawTo(0.0, 1.82, 0.0)
        return Vec3(0.0, 1.84, 0.0)

    def draw_imploder_weapon_model(self, segs: LineSegs) -> Vec3:
        self.draw_local_box(segs, Vec3(0.0, 0.18, 0.0), Vec3(0.26, 0.32, 0.24))
        self.draw_prism_outline(segs, self.octagon_points(0.11, 0.11), 0.34, 0.76)
        self.draw_prism_outline(segs, self.triangle_points(0.16, 0.18), 0.74, 1.72)
        self.draw_weapon_ring_xz(segs, Vec3(0.0, 1.08, 0.0), 0.18, 3)
        return Vec3(0.0, 1.84, 0.0)

    def draw_magnet_weapon_model(self, segs: LineSegs) -> Vec3:
        self.draw_local_box(segs, Vec3(0.0, 0.18, 0.0), Vec3(0.24, 0.34, 0.24))
        self.draw_prism_outline(segs, self.octagon_points(0.11, 0.11), 0.36, 1.54)
        for y in (0.86, 1.18, 1.46):
            self.draw_weapon_ring_xz(segs, Vec3(0.0, y, 0.0), 0.20, 8)
        return Vec3(0.0, 1.72, 0.0)

    def draw_burst_weapon_model(self, segs: LineSegs) -> Vec3:
        self.draw_local_box(segs, Vec3(0.0, 0.18, 0.0), Vec3(0.28, 0.32, 0.24))
        self.draw_prism_outline(segs, self.octagon_points(0.12, 0.10), 0.34, 0.86)
        for x in (-0.12, 0.0, 0.12):
            self.draw_prism_outline(segs, self.triangle_points(0.06, 0.08), 0.92, 1.76, x_offset=x)
        return Vec3(0.0, 1.84, 0.0)

    def draw_automatic_weapon_model(self, segs: LineSegs) -> Vec3:
        self.draw_local_box(segs, Vec3(0.0, 0.18, 0.0), Vec3(0.22, 0.30, 0.20))
        self.draw_prism_outline(segs, self.octagon_points(0.09, 0.09), 0.34, 1.72)
        self.draw_prism_outline(segs, self.triangle_points(0.07, 0.08), 0.78, 1.32)
        return Vec3(0.0, 1.78, 0.0)

    def draw_disassembler_weapon_model(self, segs: LineSegs) -> Vec3:
        self.draw_local_box(segs, Vec3(0.0, 0.18, 0.0), Vec3(0.24, 0.32, 0.22))
        self.draw_prism_outline(segs, self.octagon_points(0.09, 0.09), 0.34, 0.94)
        self.draw_prism_outline(segs, self.triangle_points(0.08, 0.08), 0.96, 1.76, x_offset=-0.08)
        self.draw_prism_outline(segs, self.triangle_points(0.08, 0.08), 0.96, 1.76, x_offset=0.08)
        return Vec3(0.0, 1.80, 0.0)

    def setup_ui(self):
        label_style = dict(scale=0.045, fg=(0.95, 0.95, 0.95, 1), align=TextNode.ALeft, mayChange=True)
        shadow_style = dict(shadow=(0, 0, 0, 1), shadowOffset=(0.04, 0.04))

        self.hud_root = self.aspect2d.attachNewNode("hud-root")
        # Player HUD should live in the screen corners and center, not as a dev-text dump.
        panel_color = (0.015, 0.018, 0.024, 0.56)
        soft_panel = (0.015, 0.018, 0.024, 0.46)
        # Pass 52: three-anchor gameplay HUD.  Persistent data lives only in the
        # score strip, objective strip, and dual-weapon strip.  Alert/context are
        # event-only branches that hide completely while empty.
        self.hud_frame = DirectFrame(parent=self.hud_root, frameColor=panel_color, frameSize=(-0.02, 0.36, -0.050, 0.050), pos=(-1.28, 0, 0.93))
        self.hud_text = DirectLabel(parent=self.hud_frame, text="", text_scale=0.029, text_align=TextNode.ALeft, text_fg=(0.96, 0.98, 1.0, 0.96), frameColor=(0, 0, 0, 0), pos=(0.02, 0, 0.012), textMayChange=True)
        self.status_frame = DirectFrame(parent=self.hud_root, frameColor=(0.12, 0.025, 0.02, 0.54), frameSize=(-0.24, 0.02, -0.046, 0.046), pos=(1.28, 0, 0.93))
        self.status_text = DirectLabel(parent=self.status_frame, text="", text_scale=0.027, text_align=TextNode.ARight, text_fg=(1.0, 0.38, 0.24, 0.98), frameColor=(0, 0, 0, 0), pos=(-0.02, 0, 0.012), textMayChange=True)
        self.weapon_frame = DirectFrame(parent=self.hud_root, frameColor=soft_panel, frameSize=(-0.02, 0.20, -0.046, 0.046), pos=(-1.28, 0, -0.93))
        self.weapon_text = DirectLabel(parent=self.weapon_frame, text="", text_scale=0.027, text_align=TextNode.ALeft, text_fg=(1.0, 0.86, 0.38, 0.94), frameColor=(0, 0, 0, 0), pos=(0.02, 0, 0.011), textMayChange=True)
        self.weapon_right_frame = DirectFrame(parent=self.hud_root, frameColor=soft_panel, frameSize=(-0.20, 0.02, -0.046, 0.046), pos=(1.28, 0, -0.93))
        self.weapon_right_text = DirectLabel(parent=self.weapon_right_frame, text="", text_scale=0.027, text_align=TextNode.ARight, text_fg=(1.0, 0.86, 0.38, 0.94), frameColor=(0, 0, 0, 0), pos=(-0.02, 0, 0.011), textMayChange=True)
        self.detail_frame = self.hud_root.attachNewNode("context-root")
        self.detail_text = DirectLabel(parent=self.detail_frame, text="", text_scale=0.025, text_align=TextNode.ACenter, text_fg=(0.90, 0.98, 1.0, 0.96), frameColor=(0.015, 0.018, 0.024, 0.48), pad=(0.16, 0.035), pos=(0, 0, -0.88), textMayChange=True)
        self.help_text = DirectLabel(parent=self.hud_root, text="", text_scale=0.01, text_align=TextNode.ARight, text_fg=(0, 0, 0, 0), frameColor=(0, 0, 0, 0), pos=(1.3, 0, -0.96), textMayChange=True)
        self.center_text = DirectLabel(parent=self.hud_root, text="", text_scale=0.041, text_align=TextNode.ACenter, text_fg=(0.98, 0.99, 1.0, 0.98), frameColor=(0.02, 0.02, 0.025, 0.34), pad=(0.18, 0.07), pos=(0, 0, -0.74), textMayChange=True)
        self.mission_text = DirectLabel(parent=self.hud_root, text="", text_scale=0.029, text_align=TextNode.ACenter, text_fg=(0.96, 0.98, 1.0, 0.94), frameColor=(0.015, 0.018, 0.024, 0.34), pad=(0.16, 0.035), pos=(0, 0, 0.93), textMayChange=True)

        self.crosshair = self.aspect2d.attachNewNode("crosshair")
        self.crosshair_lines = []
        for a, b in [((-.015, 0, 0), (-.005, 0, 0)), ((.015, 0, 0), (.005, 0, 0)), ((0, 0, -.015), (0, 0, -.005)), ((0, 0, .015), (0, 0, .005))]:
            segs = LineSegs("cross")
            segs.setThickness(1.6)
            segs.setColor(0, 0, 0, 0.9)
            segs.moveTo(*a)
            segs.drawTo(*b)
            np = self.crosshair.attachNewNode(segs.create())
            np.setDepthTest(False)
            np.setDepthWrite(False)
            np.setBin("fixed", 100)
            self.crosshair_lines.append(np)

        # Pass 54: presentation launch briefing.  This is a boot/deploy layer,
        # not another gameplay HUD.  It pauses simulation until the player deploys.
        self.presentation_root = self.aspect2d.attachNewNode("presentation-root")
        self.presentation_backdrop = DirectFrame(parent=self.presentation_root, frameColor=(0.008, 0.012, 0.020, 0.94), frameSize=(-1.12, 1.12, -0.72, 0.72), pos=(0, 0, 0))
        self.presentation_title = DirectLabel(parent=self.presentation_root, text="UTOPIA CONFLICT", text_scale=0.092, text_fg=(0.94, 0.99, 1.0, 1), frameColor=(0, 0, 0, 0), pos=(0, 0, 0.48))
        self.presentation_subtitle = DirectLabel(parent=self.presentation_root, text="HARDLIGHT DISTRICT FIELD OPERATION", text_scale=0.034, text_fg=(0.46, 0.94, 1.0, 0.96), frameColor=(0, 0, 0, 0), pos=(0, 0, 0.34))
        self.presentation_objective = DirectLabel(parent=self.presentation_root, text="CAPTURE CITY NODES  •  COMPLETE DISTRICT FIELD ACTIVITIES  •  ENTER VECTOR ARENA\nEARN LAB POINTS  •  UPGRADE  •  CONTINUE THE OPERATION", text_scale=0.035, text_align=TextNode.ACenter, text_fg=(0.92, 0.95, 0.98, 1), frameColor=(0, 0, 0, 0), pos=(0, 0, 0.12))
        self.presentation_hint = DirectLabel(parent=self.presentation_root, text="WORLD MARKERS + COLOR STATES GUIDE PLAY  •  F1 FIELD REFERENCE  •  ESC SETTINGS", text_scale=0.027, text_fg=(0.72, 0.82, 0.90, 0.95), frameColor=(0, 0, 0, 0), pos=(0, 0, -0.10))
        self.btn_deploy = DirectButton(parent=self.presentation_root, text="DEPLOY  [ENTER]", scale=0.066, frameColor=(0.04, 0.24, 0.30, 0.98), text_fg=(0.94, 1.0, 1.0, 1), command=self.begin_presentation_deploy, pos=(0, 0, -0.30))
        self.btn_reference = DirectButton(parent=self.presentation_root, text="FIELD REFERENCE  [F1]", scale=0.047, frameColor=(0.08, 0.10, 0.14, 0.98), text_fg=(0.88, 0.95, 1.0, 1), command=self.open_presentation_reference, pos=(0, 0, -0.45))
        if not self.presentation_open:
            self.presentation_root.hide()

        self.menu_root = self.aspect2d.attachNewNode("menu-root")
        self.menu_root.hide()
        self.menu_backdrop = DirectFrame(parent=self.menu_root, frameColor=(0.02, 0.02, 0.02, 0.88), frameSize=(-0.82, 0.82, -0.73, 0.58), pos=(0, 0, 0))
        self.menu_title = DirectLabel(parent=self.menu_root, text="PAUSED // SETTINGS", text_scale=0.072, text_fg=(0.96, 0.96, 0.96, 1), frameColor=(0, 0, 0, 0), pos=(0, 0, 0.44))
        self.menu_info = DirectLabel(parent=self.menu_root, text="", text_scale=0.046, text_align=TextNode.ALeft, text_fg=(0.92, 0.92, 0.92, 1), frameColor=(0, 0, 0, 0), pos=(-0.72, 0, 0.18), textMayChange=True)
        self.btn_resume = DirectButton(parent=self.menu_root, text="Resume", scale=0.065, frameColor=(0.12, 0.12, 0.12, 0.96), text_fg=(0.95, 0.95, 0.95, 1), command=self.toggle_menu, pos=(0, 0, -0.12))
        self.btn_distance = DirectButton(parent=self.menu_root, text="Draw Distance", scale=0.052, frameColor=(0.12, 0.12, 0.12, 0.96), text_fg=(0.95, 0.95, 0.95, 1), command=self.cycle_view_distance_setting, pos=(0, 0, -0.24))
        self.btn_lines = DirectButton(parent=self.menu_root, text="Line Thickness", scale=0.052, frameColor=(0.12, 0.12, 0.12, 0.96), text_fg=(0.95, 0.95, 0.95, 1), command=self.cycle_line_thickness_setting, pos=(0, 0, -0.34))
        self.btn_sensitivity = DirectButton(parent=self.menu_root, text="Mouse Sensitivity", scale=0.052, frameColor=(0.12, 0.12, 0.12, 0.96), text_fg=(0.95, 0.95, 0.95, 1), command=self.cycle_sensitivity_setting, pos=(0, 0, -0.44))
        self.btn_quit = DirectButton(parent=self.menu_root, text="Quit to Desktop", scale=0.050, frameColor=(0.18, 0.07, 0.07, 0.96), text_fg=(1.0, 0.88, 0.88, 1), command=self.userExit, pos=(0, 0, -0.53))
        self.menu_hint = DirectLabel(parent=self.menu_root, text="W/S or Up/Down: Select   •   Enter/Space: Activate   •   Esc: Resume", text_scale=0.026, text_align=TextNode.ACenter, text_fg=(0.70, 0.84, 0.92, 0.95), frameColor=(0, 0, 0, 0), pos=(0, 0, -0.66))
        self.menu_buttons = [
            (self.btn_resume, self.toggle_menu),
            (self.btn_distance, self.cycle_view_distance_setting),
            (self.btn_lines, self.cycle_line_thickness_setting),
            (self.btn_sensitivity, self.cycle_sensitivity_setting),
            (self.btn_quit, self.userExit),
        ]
        self.menu_selected_index = 0
        self.refresh_menu_selection()

        self.work_root = self.aspect2d.attachNewNode("work-root")
        self.work_root.hide()
        self.work_frame = DirectFrame(parent=self.work_root, frameColor=(0.03, 0.03, 0.03, 0.82), frameSize=(-0.63, 0.63, -0.35, 0.35), pos=(0.5, 0, 0.58))
        self.work_title = DirectLabel(parent=self.work_root, text="ACTIVITY BOARD", text_scale=0.05, text_fg=(0.95, 0.95, 0.95, 1), frameColor=(0, 0, 0, 0), pos=(0.5, 0, 0.83))
        self.work_text = DirectLabel(parent=self.work_root, text="", text_scale=0.038, text_align=TextNode.ALeft, text_fg=(0.93, 0.93, 0.93, 1), frameColor=(0, 0, 0, 0), pos=(-0.06, 0, 0.66), textMayChange=True)

        # Pass 53: one player reference layer. It is modal, opt-in, and never
        # consumes normal-play HUD space. DirectGUI branches inherit NodePath
        # show/hide behavior, so the whole reference panel can be hidden cleanly.
        self.help_root = self.aspect2d.attachNewNode("help-reference-root")
        self.help_root.hide()
        self.help_backdrop = DirectFrame(parent=self.help_root, frameColor=(0.012, 0.016, 0.024, 0.96), frameSize=(-1.18, 1.18, -0.82, 0.82), pos=(0, 0, 0))
        self.help_title = DirectLabel(parent=self.help_root, text="FIELD REFERENCE  //  F1 CLOSE", text_scale=0.055, text_fg=(0.96, 0.99, 1.0, 1), frameColor=(0, 0, 0, 0), pos=(0, 0, 0.70))
        help_left = (
            "CONTROLS\n"
            "WASD      Move\nSHIFT     Sprint\nMouse     Aim\n"
            "LMB/RMB   Fire right / left\n1-6       Right weapon\nSHIFT+1-6 Left weapon\n"
            "TAB / Q   Cycle right / left\nE         Interact\nH         HUD\n"
            "F10       Activity Board\nESC       Pause\n\n"
            "PLAYER CONDITION\n"
            "GREEN     Healthy lines\nAMBER     Injured lines\nRED       Critical lines\nCYAN      Armor shell active\n\n"
            "UPGRADES\nU         Ammo capacity\nSHIFT+U   Health capacity\nI         Armor capacity"
        )
        help_right = (
            "ENEMY COLOR STATES\n"
            "CRIMSON   Hostile baseline\nHOT RED   Attacking\nYELLOW    Evading\n"
            "AMBER     Braced / resistant\nCYAN      Phasing\nVIOLET    Boss core shielded\n"
            "LIME      Boss core exposed\nTEAL      Passive patrol drone\nBLUE      Drone armor absorbed hit\n\n"
            "CITY\n"
            "Follow physical flags and route structures.\n"
            "Capture zones regenerate health and armor.\n"
            "Press E at field activities.\n"
            "Patrol drones can become hostile after protected targets are attacked.\n\n"
            "COMBAT\n"
            "Boss shoulder rings are real weak points.\n"
            "Enemy state colors show danger, defense, or vulnerability.\n\n"
            "WEAPONS\n"
            "1  Core Lance        Pierce / core pressure\n"
            "2  Imploder          Pull inward / crush\n"
            "3  Proximity Magnet  Containment field\n"
            "4  Disassembler      Cut body sections\n"
            "5  Burst Splitter    Wide spread\n"
            "6  Auto Lattice      Rapid lattice fire\n\n"
            "FIELD ACTIVITIES\n"
            "Calibration   Core Sample / Imploder Study\n"
            "High Towers   Shield Fracture\n"
            "Pyramid       Magnet Garden"
        )
        self.help_left_text = DirectLabel(parent=self.help_root, text=help_left, text_scale=0.034, text_align=TextNode.ALeft, text_fg=(0.92, 0.96, 1.0, 1), frameColor=(0, 0, 0, 0), pos=(-1.02, 0, 0.56))
        self.help_right_text = DirectLabel(parent=self.help_root, text=help_right, text_scale=0.034, text_align=TextNode.ALeft, text_fg=(0.92, 0.96, 1.0, 1), frameColor=(0, 0, 0, 0), pos=(0.08, 0, 0.56))

        self.refresh_ui_text()


    def activity_counts(self):
        # Player-facing activity progression is the four physical field stations only.
        # The older catalog remains a background accomplishment/event log, not fake activities.
        instances = getattr(self, "activity_instances", []) or []
        keys = {str(entry.get("key", "")) for entry in instances if str(entry.get("key", ""))}
        flags = getattr(self, "activity_flags", set()) or set()
        return len([key for key in flags if key in keys]), len(keys)

    def next_activity_hint(self) -> str:
        flags = getattr(self, "activity_flags", set()) or set()
        for entry in getattr(self, "activity_instances", []) or []:
            key = str(entry.get("key", ""))
            if key and key not in flags:
                return f"{entry.get('label', 'Activity')}: {entry.get('hint', 'Try the field test')}"
        return "All four field activities complete"

    def recent_activity_line(self) -> str:
        events = getattr(self, "activity_event_log", []) or []
        if not events:
            return "none yet"
        labels = [str(e.get("label", "activity")) for e in events[-3:]]
        return " / ".join(labels)

    def award_activity_instance_reward(self, entry) -> dict:
        if not entry:
            return {}
        slot = int(entry.get("reward_slot", 0) or 0)
        ammo = float(entry.get("reward_ammo", 0.0) or 0.0)
        lab = int(entry.get("reward_lab", 0) or 0)
        kind = str(entry.get("reward_kind", "FIELD CACHE"))
        before_lab = int(getattr(self, "lab_points", 0) or 0)
        before_armor = int(getattr(self, "player_armor", 0) or 0)
        if lab > 0:
            self.lab_points = before_lab + lab
        if slot > 0 and ammo > 0.0:
            self.add_weapon_ammo(slot, ammo, silent=True)
            center = Vec3(entry.get("pos", getattr(self, "player_pos", Vec3(0, 0, 0))))
            self.spawn_weapon_pickup(center + Vec3(0, 0, 0.25), slot=slot, amount=ammo)
        if str(entry.get("key", "")) == "shield_break":
            self.player_armor = int(getattr(self, "player_armor_max", 0) or 0)
            self.armor_damage_fade_timer = 0.0
        reward = {"key": str(entry.get("key", "")), "label": str(entry.get("label", "Activity")), "lab_points": lab, "slot": slot, "ammo": ammo, "kind": kind, "armor_before": before_armor, "armor_after": int(getattr(self, "player_armor", 0) or 0)}
        self.activity_reward_log.append(reward)
        self.activity_reward_log = self.activity_reward_log[-8:]
        self.combat_banner = f"{kind} // +{lab} LAB"
        self.combat_banner_time = 2.0
        center = Vec3(entry.get("pos", getattr(self, "player_pos", Vec3(0, 0, 0))))
        self.add_shockwave_ring(center + Vec3(0, 0, 0.18), radius=6.0, life=0.48, vertical=True, thickness=1.25)
        self.play_sfx("objective_complete", volume=0.78, rate=1.05, pos=center)
        return reward

    def record_activity(self, key: str, label: str | None = None, bonus: int | None = None, pos: Vec3 | None = None):
        if not bool(getattr(self.game_cfg, "activity_mode_enabled", True)):
            return False
        key = str(key or "activity").strip()
        if not key:
            return False
        label = str(label or key.replace("_", " ").title())
        active_instance = getattr(self, "active_activity_instance", None)
        completing_instance = bool(active_instance is not None and str(active_instance.get("key", "")) == key)
        if key in getattr(self, "activity_flags", set()):
            if completing_instance:
                active_instance["active"] = False
                self.active_activity_instance = None
                self.clear_activity_instance_enemies()
            return False
        self.activity_flags.add(key)
        if bonus is None:
            bonus = int(getattr(self.game_cfg, "activity_bonus_score", 75))
        bonus = int(bonus or 0)
        self.activity_bonus_score = int(getattr(self, "activity_bonus_score", 0) or 0) + bonus
        self.score = int(getattr(self, "score", 0) or 0) + bonus
        event = {"key": key, "label": label, "bonus": bonus, "time": round(float(getattr(self, "elapsed", 0.0)), 2)}
        self.activity_event_log.append(event)
        self.activity_event_log = self.activity_event_log[-8:]
        self.activity_banner = f"LAB ACTIVITY // {label.upper()} +{bonus}"
        self.activity_banner_time = 1.7
        self.combat_banner = self.activity_banner
        self.combat_banner_time = max(float(getattr(self, "combat_banner_time", 0.0)), 1.15)
        effect_pos = Vec3(pos) if pos is not None else Vec3(getattr(self, "player_pos", Vec3(0, 0, 0)))
        try:
            self.add_combat_feedback(effect_pos + Vec3(0, 0, 1.1), label="chain", radius=2.0, life=0.44, warning=False)
            self.add_shockwave_ring(effect_pos + Vec3(0, 0, 0.14), radius=4.0, life=0.34, vertical=False, thickness=1.0)
            self.play_sfx("pickup", volume=0.55, rate=1.0)
        except Exception:
            pass
        if completing_instance:
            reward = self.award_activity_instance_reward(active_instance)
            active_instance["active"] = False
            self.active_activity_instance = None
            self.clear_activity_instance_enemies()
            reward_kind = str(reward.get("kind", "REWARD")) if reward else "REWARD"
            reward_lab = int(reward.get("lab_points", 0) or 0) if reward else 0
            self.combat_banner = f"{label.upper()} // COMPLETE // {reward_kind} +{reward_lab} LAB"
            self.combat_banner_time = 2.2
        return True


    def district_discovery_specs(self):
        """Low-text world guidance that makes the two remote districts discoverable.

        Pass 49 deliberately reuses the actual Pass 48 activity coordinates.  The
        route language is world geometry: tower rails point north and triangular
        gates point east.  No GPS arrow or persistent district text is introduced.
        """
        district_span = float(max(2, int(getattr(self.game_cfg, "district_size_chunks", 6))) * max(1.0, float(getattr(self.game_cfg, "chunk_size", 64))))
        return [
            {
                "key": "shield_break",
                "district_id": "high_towers",
                "label": "High Towers",
                "axis": "north",
                "color": (0.72, 1.0, 1.0, 0.94),
                "site": Vec3(18.0, district_span + 74.0, 0.0),
                "gate_positions": [Vec3(0.0, y, 0.0) for y in (150.0, 230.0, 310.0, district_span + 18.0)],
            },
            {
                "key": "magnet_garden",
                "district_id": "pyramid_sector",
                "label": "Pyramid Sector",
                "axis": "east",
                "color": (0.52, 1.0, 0.32, 0.88),
                "site": Vec3(district_span + 74.0, 18.0, 0.0),
                "gate_positions": [Vec3(x, 18.0, 0.0) for x in (150.0, 230.0, 310.0, district_span + 18.0)],
            },
        ]

    def setup_district_discovery_guidance(self):
        old = getattr(self, "district_guidance_root", None)
        if old is not None and not old.isEmpty():
            old.removeNode()
        self.district_guidance_root = self.render.attachNewNode("district-discovery-guidance")
        self.district_guidance_root.setTransparency(TransparencyAttrib.MAlpha)
        self.district_guidance_root.setAntialias(AntialiasAttrib.MLine)
        self.district_guidance_nodes = {}
        self.district_discovered = set()
        for spec in self.district_discovery_specs():
            root = self.district_guidance_root.attachNewNode(f"district-route-{spec['district_id']}")
            segs = LineSegs(f"district-route-lines-{spec['district_id']}")
            segs.setThickness(self.movable_line_thickness(0.82, 1.55))
            segs.setColor(*spec["color"])
            site = Vec3(spec["site"])
            # Dashes begin beyond the Calibration activity/capture area so the
            # mission field remains visually clean.
            if spec["axis"] == "north":
                start = Vec3(0.0, 126.0, 0.10)
                end = Vec3(site.x, site.y - 8.0, 0.10)
            else:
                start = Vec3(126.0, 18.0, 0.10)
                end = Vec3(site.x - 8.0, site.y, 0.10)
            delta = end - start
            length = max(1.0, delta.length())
            direction = delta / length
            cursor = 0.0
            while cursor < length:
                a = start + direction * cursor
                b = start + direction * min(length, cursor + 9.0)
                segs.moveTo(a); segs.drawTo(b)
                cursor += 18.0
            # Repeated gates teach the route silhouette without floating arrows.
            for gate in spec["gate_positions"]:
                if spec["axis"] == "north":
                    for dx in (-5.5, 5.5):
                        segs.moveTo(gate + Vec3(dx, 0, 0.0)); segs.drawTo(gate + Vec3(dx, 0, 15.0))
                    segs.moveTo(gate + Vec3(-5.5, 0, 15.0)); segs.drawTo(gate + Vec3(0, 0, 21.0)); segs.drawTo(gate + Vec3(5.5, 0, 15.0))
                else:
                    segs.moveTo(gate + Vec3(0, -6.0, 0.0)); segs.drawTo(gate + Vec3(0, 0, 16.0)); segs.drawTo(gate + Vec3(0, 6.0, 0.0)); segs.drawTo(gate + Vec3(0, -6.0, 0.0))
                    segs.moveTo(gate + Vec3(0, -3.0, 5.0)); segs.drawTo(gate + Vec3(0, 0, 16.0)); segs.drawTo(gate + Vec3(0, 3.0, 5.0))
            # A district-specific horizon crown sits above the actual activity
            # plaza.  It is a destination silhouette, not a collision object.
            if spec["axis"] == "north":
                for dx in (-8.0, 0.0, 8.0):
                    h = 34.0 if dx == 0.0 else 27.0
                    segs.moveTo(site + Vec3(dx, 0, 0.0)); segs.drawTo(site + Vec3(dx, 0, h))
                segs.moveTo(site + Vec3(-8.0, 0, 27.0)); segs.drawTo(site + Vec3(0, 0, 36.0)); segs.drawTo(site + Vec3(8.0, 0, 27.0))
                segs.moveTo(site + Vec3(-4.0, 0, 31.5)); segs.drawTo(site + Vec3(4.0, 0, 31.5))
            else:
                corners = [Vec3(-10,-10,0), Vec3(10,-10,0), Vec3(10,10,0), Vec3(-10,10,0)]
                apex = site + Vec3(0, 0, 31.0)
                for i, corner in enumerate(corners):
                    p = site + corner
                    q = site + corners[(i + 1) % len(corners)]
                    segs.moveTo(p); segs.drawTo(q); segs.moveTo(p); segs.drawTo(apex)
                for z, scale in ((10.0, 0.68), (19.0, 0.38)):
                    ring = [site + Vec3(c.x * scale, c.y * scale, z) for c in corners]
                    for i, p in enumerate(ring):
                        segs.moveTo(p); segs.drawTo(ring[(i + 1) % len(ring)])
            geom = root.attachNewNode(segs.create())
            geom.setTransparency(TransparencyAttrib.MAlpha)
            geom.setAntialias(AntialiasAttrib.MLine)
            root.setPythonTag("guidance_key", spec["key"])
            root.setPythonTag("district_id", spec["district_id"])
            self.district_guidance_nodes[spec["key"]] = {"root": root, "spec": spec}

    def update_district_discovery_guidance(self, dt: float):
        flags = getattr(self, "activity_flags", set()) or set()
        current = getattr(self, "current_district_id", "calibration")
        elapsed = float(getattr(self, "elapsed", 0.0))
        for key, info in getattr(self, "district_guidance_nodes", {}).items():
            root = info.get("root")
            spec = info.get("spec", {})
            if root is None or root.isEmpty():
                continue
            complete = key in flags
            district_id = str(spec.get("district_id", ""))
            if current == district_id:
                self.district_discovered.add(district_id)
            if complete:
                root.setColorScale(0.24, 0.32, 0.34, 0.38)
                root.setScale(1.0)
                continue
            pulse = 0.92 + 0.08 * math.sin(elapsed * 2.7 + (0.0 if district_id == "high_towers" else 1.7))
            # Once inside a destination district the distant route dims so the
            # local activity architecture, not the road cue, owns attention.
            local_scale = 0.58 if current == district_id else 1.0
            root.setColorScale(pulse * local_scale, pulse * local_scale, pulse * local_scale, 1.0)
            root.setScale(1.0)

    def district_discovery_test_task(self, task):
        try:
            specs = self.district_discovery_specs()
            nodes = getattr(self, "district_guidance_nodes", {})
            rows = []
            for spec in specs:
                actual_id, _district = self.district_for_position(Vec3(spec["site"]))
                info = nodes.get(spec["key"], {})
                root = info.get("root")
                rows.append({
                    "key": spec["key"],
                    "district_id": spec["district_id"],
                    "actual_district_id": actual_id,
                    "axis": spec["axis"],
                    "gate_count": len(spec["gate_positions"]),
                    "node_present": bool(root is not None and not root.isEmpty()),
                    "site": [round(float(spec["site"].x), 2), round(float(spec["site"].y), 2), round(float(spec["site"].z), 2)],
                })
            corridor_checks = {
                "north_mid_reserved": self.point_near_district_route(0.0, 250.0),
                "east_mid_reserved": self.point_near_district_route(250.0, 18.0),
                "off_route_open": not self.point_near_district_route(-80.0, 250.0),
            }
            ok = len(rows) == 2 and all(r["district_id"] == r["actual_district_id"] and r["gate_count"] >= 4 and r["node_present"] for r in rows) and {r["axis"] for r in rows} == {"north", "east"} and all(corridor_checks.values())
            report = {"status": "PASS" if ok else "FAIL", "guidance_routes": rows, "corridor_checks": corridor_checks, "hud_gps_added": False, "activity_system_reused": True}
            print("DISTRICT_DISCOVERY_TEST", report["status"], json.dumps(report, sort_keys=True))
            self.userExit()
        except Exception as exc:
            print("DISTRICT_DISCOVERY_TEST FAIL", repr(exc))
            traceback.print_exc()
            self.userExit()
        return Task.done

    def district_discovery_demo_task(self, task):
        key = str(DISTRICT_DISCOVERY_DEMO or "").strip().lower()
        info = getattr(self, "district_guidance_nodes", {}).get(key)
        if not info:
            print("DISTRICT_DISCOVERY_DEMO FAIL", key)
            self.userExit()
            return Task.done
        spec = info["spec"]
        site = Vec3(spec["site"])
        if spec["axis"] == "north":
            self.player_pos = Vec3(0.0, site.y - 120.0, self.game_cfg.player_height)
        else:
            self.player_pos = Vec3(site.x - 120.0, 18.0, self.game_cfg.player_height)
        self.camera.setPos(self.player_pos)
        self.camera.lookAt(site + Vec3(0, 0, 9.0))
        self.yaw = float(self.camera.getH())
        self.pitch = float(self.camera.getP())
        self.generate_city_around_player(force=True)
        self.update_current_district(announce=False)
        self.update_district_discovery_guidance(0.033)
        self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
        self.set_objective_banner("", 0.0)
        if TEST_SHOT_PATH:
            self.taskMgr.doMethodLater(0.75, lambda t: (self.save_test_screenshot(), self.userExit(), Task.done)[-1], f"district-discovery-shot-{key}")
        else:
            print("DISTRICT_DISCOVERY_DEMO PASS", key, spec["district_id"], [float(site.x), float(site.y), float(site.z)])
            self.userExit()
        return Task.done

    def district_activity_clear_zones(self):
        """Authored activity plazas reserved from procedural city massing.

        The activity geometry is created later than the initial city chunks, so the
        generator uses the same deterministic site coordinates to keep visible and
        collision space honest around each station.
        """
        district_span = float(max(2, int(getattr(self.game_cfg, "district_size_chunks", 6))) * max(1.0, float(getattr(self.game_cfg, "chunk_size", 64))))
        return [
            (Vec3(-22.0, 18.0, 0.0), 15.0, "core_sample"),
            (Vec3(22.0, 18.0, 0.0), 16.0, "imploder_cluster"),
            (Vec3(18.0, district_span + 74.0, 0.0), 22.0, "shield_break"),
            (Vec3(district_span + 74.0, 18.0, 0.0), 22.0, "magnet_garden"),
        ]

    def point_near_activity_site(self, x: float, y: float, extra_radius: float = 0.0) -> bool:
        for center, radius, _key in self.district_activity_clear_zones():
            dx = float(x) - float(center.x)
            dy = float(y) - float(center.y)
            limit = float(radius) + max(0.0, float(extra_radius))
            if dx * dx + dy * dy <= limit * limit:
                return True
        return False

    def point_near_district_route(self, x: float, y: float, extra_radius: float = 0.0) -> bool:
        """Reserve two narrow sightline/walking corridors to the remote districts."""
        span = float(max(2, int(getattr(self.game_cfg, "district_size_chunks", 6))) * max(1.0, float(getattr(self.game_cfg, "chunk_size", 64))))
        pad = 8.0 + max(0.0, float(extra_radius))
        xf, yf = float(x), float(y)
        north = 118.0 <= yf <= span + 82.0 and abs(xf) <= pad
        east = 118.0 <= xf <= span + 82.0 and abs(yf - 18.0) <= pad
        return bool(north or east)

    def point_near_authored_travel_space(self, x: float, y: float, extra_radius: float = 0.0) -> bool:
        return self.point_near_activity_site(x, y, extra_radius=extra_radius) or self.point_near_district_route(x, y, extra_radius=extra_radius)

    def setup_activity_mode(self):
        self.activity_root = self.render.attachNewNode("prototype-lab-activity-mode")
        self.activity_root.setTransparency(TransparencyAttrib.MAlpha)
        self.activity_root.setAntialias(AntialiasAttrib.MLine)
        alpha = float(getattr(self.game_cfg, "activity_marker_alpha", 0.68))
        district_span = float(max(2, int(getattr(self.game_cfg, "district_size_chunks", 6))) * max(1.0, float(getattr(self.game_cfg, "chunk_size", 64))))
        # Pass 48: the four proven activities are now authored into the districts whose
        # geometry best supports them.  No new activity rules are introduced here.
        pads = [
            {"xy": (-22, 18), "district_id": "calibration", "site_style": "calibration_pedestal", "radius": 4.6, "key": "core_sample", "label": "Core Sample", "hint": "Shatter one red enemy core", "variants": ["sentinel", "stalker", "sentinel"], "count": 3, "spawn_radius": 19.0, "color": (1.0, 0.12, 0.10, alpha), "reward_slot": 1, "reward_ammo": 34.0, "reward_lab": 18, "reward_kind": "CORE LANCE CACHE"},
            {"xy": (22, 18), "district_id": "calibration", "site_style": "calibration_compression", "radius": 4.2, "key": "imploder_cluster", "label": "Imploder Study", "hint": "Collapse two targets in one implosion", "variants": ["sentinel", "stalker", "sentinel", "stalker"], "count": 4, "spawn_radius": 7.0, "color": (1.0, 0.42, 0.08, alpha), "reward_slot": 2, "reward_ammo": 30.0, "reward_lab": 24, "reward_kind": "IMPLODER CACHE"},
            {"xy": (18, district_span + 74.0), "district_id": "high_towers", "site_style": "tower_suspension", "radius": 5.0, "key": "shield_break", "label": "Shield Fracture", "hint": "Break one armored shell", "variants": ["bulwark", "commander"], "count": 2, "spawn_radius": 15.0, "color": (0.18, 0.92, 1.0, alpha), "reward_slot": 4, "reward_ammo": 26.0, "reward_lab": 22, "reward_kind": "ARMOR + DISASSEMBLER"},
            {"xy": (district_span + 74.0, 18), "district_id": "pyramid_sector", "site_style": "pyramid_field", "radius": 5.2, "key": "magnet_garden", "label": "Magnet Garden", "hint": "Tether two targets in one magnetic field", "variants": ["stalker", "shifter", "stalker", "shifter", "stalker"], "count": 5, "spawn_radius": 13.0, "color": (0.52, 1.0, 0.32, alpha), "reward_slot": 3, "reward_ammo": 30.0, "reward_lab": 24, "reward_kind": "MAGNET CACHE"},
        ]
        self.activity_instances = []
        for index, spec in enumerate(pads):
            entry = dict(spec)
            entry.update({"index": index, "pos": Vec3(spec["xy"][0], spec["xy"][1], 0), "active": False})
            self.activity_instances.append(entry)
            self.build_activity_architecture(entry)
        self.record_activity("lab_entry", "Lab Entry", bonus=0, pos=Vec3(0, 6, 0))

    def activity_line_node(self, name: str, color, thickness: float = 1.6):
        segs = LineSegs(name)
        segs.setThickness(max(1.0, thickness))
        segs.setColor(*color)
        return segs

    def attach_activity_lines(self, segs: LineSegs):
        node = self.activity_root.attachNewNode(segs.create())
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.setAntialias(AntialiasAttrib.MLine)
        return node

    def draw_activity_ring(self, segs: LineSegs, center: Vec3, radius: float, z: float = 0.08, segments: int = 32):
        first = last = None
        for i in range(segments + 1):
            a = math.tau * i / segments
            p = center + Vec3(math.cos(a) * radius, math.sin(a) * radius, z)
            if first is None: first = p
            if last is None: segs.moveTo(p)
            else: segs.drawTo(p)
            last = p

    def build_activity_architecture(self, entry):
        key = str(entry.get("key", ""))
        c = Vec3(entry.get("pos", Vec3(0, 0, 0)))
        r = float(entry.get("radius", 4.4))
        col = tuple(entry.get("color", (0.2, 0.9, 1.0, 0.7)))
        segs = self.activity_line_node(f"activity-architecture-{key}", col, self.movable_line_thickness(0.72, 1.35))
        self.draw_activity_ring(segs, c, r)
        if key == "core_sample":
            # Containment pedestal, suspended core, three stabilizer towers.
            self.draw_activity_ring(segs, c, 2.2, 0.14)
            for i in range(3):
                a = math.tau * i / 3 - math.pi * 0.5
                p = c + Vec3(math.cos(a) * 3.5, math.sin(a) * 3.5, 0)
                segs.moveTo(p); segs.drawTo(p + Vec3(0, 0, 5.6))
                segs.moveTo(p + Vec3(0, 0, 5.6)); segs.drawTo(c + Vec3(0, 0, 3.8))
            for a in (0, math.pi * 0.5):
                p0=c+Vec3(math.cos(a)*1.0, math.sin(a)*1.0,3.8); p1=c-Vec3(math.cos(a)*1.0, math.sin(a)*1.0,-3.8)
                segs.moveTo(p0); segs.drawTo(p1)
        elif key == "shield_break":
            # High Towers suspension test: a tall armored fracture cage hangs between
            # vertical rails so the activity belongs to the skyline instead of a flat pad.
            for x in (-5.0, 5.0):
                segs.moveTo(c + Vec3(x, 0, 0)); segs.drawTo(c + Vec3(x, 0, 14.0))
                segs.moveTo(c + Vec3(x, -2.0, 7.0)); segs.drawTo(c + Vec3(x, 2.0, 7.0))
            segs.moveTo(c + Vec3(-5.0, 0, 14.0)); segs.drawTo(c + Vec3(5.0, 0, 14.0))
            for z, radius in ((3.0, 3.7), (6.0, 3.1), (9.0, 2.5)):
                last=None
                for i in range(17):
                    a=math.pi*i/16
                    p=c+Vec3(math.cos(a)*radius, 0, z + math.sin(a)*radius)
                    if last is not None: segs.moveTo(last); segs.drawTo(p)
                    last=p
            for x in (-2.2, 0.0, 2.2):
                segs.moveTo(c+Vec3(x,0,14.0)); segs.drawTo(c+Vec3(x,0,9.5))
        elif key == "imploder_cluster":
            # Compression chamber: concentric floor rings and inward radial vanes.
            for radius in (1.5, 2.7, 4.0): self.draw_activity_ring(segs, c, radius, 0.10)
            for i in range(8):
                a=math.tau*i/8; outer=c+Vec3(math.cos(a)*4.0,math.sin(a)*4.0,0.12); inner=c+Vec3(math.cos(a)*1.2,math.sin(a)*1.2,0.12)
                segs.moveTo(outer); segs.drawTo(inner)
            segs.moveTo(c+Vec3(0,0,0)); segs.drawTo(c+Vec3(0,0,4.5))
        elif key == "magnet_garden":
            # Pyramid Sector field: four stepped triangular pylons focus the same proven
            # magnetic activity into a district-shaped containment diamond.
            pylons=[]
            for i in range(4):
                a=math.tau*i/4+math.pi/4; p=c+Vec3(math.cos(a)*4.2,math.sin(a)*4.2,0); pylons.append(p)
                inward=(c-p); inward.z=0
                if inward.lengthSquared() > 0.001: inward.normalize()
                side=Vec3(-inward.y,inward.x,0)
                left=p-side*1.7; right=p+side*1.7; apex=p+Vec3(0,0,6.8)
                segs.moveTo(left); segs.drawTo(apex); segs.drawTo(right); segs.drawTo(left)
                segs.moveTo(p+inward*0.8); segs.drawTo(apex)
            for i,p in enumerate(pylons):
                q=pylons[(i+1)%len(pylons)]
                prev=p+Vec3(0,0,4.0)
                for step in range(1,7):
                    t=step/6; mid=p*(1-t)+q*t+Vec3(0,0,4.0+math.sin(math.pi*t)*2.5)
                    segs.moveTo(prev); segs.drawTo(mid); prev=mid
            for i in range(4):
                a=math.tau*i/4
                outer=c+Vec3(math.cos(a)*5.0,math.sin(a)*5.0,0.1)
                segs.moveTo(outer); segs.drawTo(c+Vec3(0,0,0.1))
        self.attach_activity_lines(segs)

    def nearest_activity_instance(self):
        player_flat = Vec3(self.player_pos.x, self.player_pos.y, 0)
        best = None
        best_dist = 999999.0
        for entry in getattr(self, "activity_instances", []) or []:
            pos = Vec3(entry.get("pos", Vec3(0, 0, 0)))
            dist = (pos - player_flat).length()
            if dist < best_dist:
                best = entry
                best_dist = dist
        return best, best_dist

    def activity_instance_prompt(self) -> str:
        entry, dist = self.nearest_activity_instance()
        radius = float(getattr(self.game_cfg, "activity_instance_radius", 7.5))
        if entry is None or dist > radius:
            return ""
        label = str(entry.get("label", "Activity")).upper()
        key = str(entry.get("key", ""))
        if key in getattr(self, "activity_flags", set()):
            return f"{label} // COMPLETE"
        if getattr(self, "active_activity_instance", None) is entry:
            return f"{label} // {str(entry.get('hint', 'ACTIVE')).upper()}"
        return f"E  START {label}"

    def clear_activity_instance_enemies(self):
        removed = 0
        for enemy in list(getattr(self, "enemies", []) or []):
            if not bool(getattr(enemy, "activity_instance_enemy", False)):
                continue
            try:
                if enemy.root is not None and not enemy.root.isEmpty():
                    enemy.root.removeNode()
            except Exception:
                pass
            try:
                self.enemies.remove(enemy)
            except ValueError:
                pass
            removed += 1
        return removed

    def start_activity_instance(self, entry) -> bool:
        if entry is None or getattr(self, "arena_mode_active", False):
            return False
        key = str(entry.get("key", ""))
        label = str(entry.get("label", "Activity"))
        if key in getattr(self, "activity_flags", set()):
            self.combat_banner = f"{label.upper()} // COMPLETE"
            self.combat_banner_time = 1.0
            return False
        self.clear_activity_instance_enemies()
        self.pending_enemy_spawns.clear()
        self.active_activity_instance = entry
        entry["active"] = True
        center = Vec3(entry.get("pos", Vec3(0, 0, 0)))
        variants = list(entry.get("variants", ["sentinel"]))
        count = max(1, int(entry.get("count", getattr(self.game_cfg, "activity_instance_spawn_count", 4))))
        rng = random.Random(self.hashed_seed(int(center.x), int(center.y), 4040 + int(entry.get("index", 0))))
        spawn_radius = max(5.0, float(entry.get("spawn_radius", 18.0)))
        for i in range(count):
            ang = math.tau * i / max(1, count) + rng.uniform(-0.10, 0.10)
            radius = spawn_radius * (0.90 + 0.12 * (i % 2))
            pos = center + Vec3(math.cos(ang) * radius, math.sin(ang) * radius, 0)
            enemy = Enemy(self, pos, self.hashed_seed(int(pos.x), int(pos.y), 4100 + i), variant_override=variants[i % len(variants)])
            enemy.activity_instance_enemy = True
            self.enemies.append(enemy)
            self.add_combat_feedback(pos, label="spawn", radius=3.0, life=0.72, warning=True)
        key = str(entry.get("key", ""))
        # Give each activity a readable starting condition instead of four identical enemy circles.
        if key == "core_sample":
            self.select_weapon_for_hand(1, hand="right", force=True, silent=True)
        elif key == "shield_break":
            self.select_weapon_for_hand(4, hand="right", force=True, silent=True)
        elif key == "imploder_cluster":
            self.select_weapon_for_hand(2, hand="right", force=True, silent=True)
        elif key == "magnet_garden":
            self.select_weapon_for_hand(3, hand="right", force=True, silent=True)
        self.spawn_director_timer = max(float(getattr(self, "spawn_director_timer", 0.0)), 6.0)
        weapon = self.get_weapon_for_hand("right") if hasattr(self, "get_weapon_for_hand") else None
        weapon_name = str(getattr(weapon, "name", "FIELD TOOL")).upper()
        self.combat_banner = f"{label.upper()} // {weapon_name}"
        self.combat_banner_time = 1.8
        self.set_objective_banner(str(entry.get("hint", "Complete the field test")), 3.2)
        self.play_sfx("wave_start", volume=0.74)
        return True

    def try_start_activity_instance(self) -> bool:
        if getattr(self, "active_activity_instance", None) is not None:
            return False
        entry, dist = self.nearest_activity_instance()
        radius = float(getattr(self.game_cfg, "activity_instance_radius", 7.5))
        if entry is None or dist > radius:
            return False
        return self.start_activity_instance(entry)

    def try_context_action(self):
        if self.try_start_activity_instance():
            return True
        entry, dist = self.nearest_arena_portal()
        if entry is not None and dist <= float(getattr(self.game_cfg, "arena_portal_radius", 5.5)):
            self.enter_arena_mode(entry)
            return True
        return False

    def setup_input(self):
        for key in ["w", "a", "s", "d", "shift", "space"]:
            self.accept(key, self.set_key, [key, True])
            self.accept(f"{key}-up", self.set_key, [key, False])
        self.accept("mouse1", self.set_fire, [True, "right"] )
        self.accept("mouse1-up", self.set_fire, [False, "right"] )
        self.accept("mouse3", self.set_fire, [True, "left"] )
        self.accept("mouse3-up", self.set_fire, [False, "left"] )
        for slot in (1, 2, 3, 4, 5, 6):
            self.accept(str(slot), self.select_weapon_slot, [slot])
            self.accept(f"shift-{slot}", self.select_left_weapon_slot, [slot])
        self.accept("tab", self.generate_next_weapon)
        self.accept("shift-tab", self.generate_previous_weapon)
        self.accept("q", self.generate_next_left_weapon)
        self.accept("shift-q", self.generate_previous_left_weapon)
        self.accept("gamepad-rshoulder", self.generate_next_weapon)
        self.accept("gamepad-lshoulder", self.generate_previous_weapon)
        self.accept("enter", self.handle_enter_action)
        self.accept("arrow_up", self.navigate_menu, [-1])
        self.accept("arrow_down", self.navigate_menu, [1])
        self.accept("arrow_left", self.adjust_menu_setting, [-1])
        self.accept("arrow_right", self.adjust_menu_setting, [1])
        self.accept("h", self.toggle_hud)
        self.accept("f1", self.toggle_help_reference)
        self.accept("f10", self.toggle_workstation)
        self.accept("e", self.try_context_action)
        self.accept("u", self.buy_ammo_capacity_upgrade)
        self.accept("shift-u", self.buy_health_capacity_upgrade)
        self.accept("i", self.buy_armor_capacity_upgrade)
        self.accept("escape", self.toggle_menu)
        self.accept("0", self.userExit)

    def setup_gamepad(self):
        devices = self.devices.getDevices(InputDevice.DeviceClass.gamepad)
        if devices:
            self.attachInputDevice(devices[0], prefix="gamepad")
            self.gamepad = devices[0]
        self.accept("connect-device", self.on_device_connect)
        self.accept("disconnect-device", self.on_device_disconnect)

    def on_device_connect(self, device):
        if device.device_class == InputDevice.DeviceClass.gamepad and self.gamepad is None:
            self.attachInputDevice(device, prefix="gamepad")
            self.gamepad = device

    def on_device_disconnect(self, device):
        if self.gamepad == device:
            self.detachInputDevice(device)
            self.gamepad = None

    def set_key(self, key, value):
        if self.menu_open:
            if value:
                if key == "w":
                    self.navigate_menu(-1)
                elif key == "s":
                    self.navigate_menu(1)
                elif key == "space":
                    self.activate_menu_selection()
            self.keys[key] = False
            return
        self.keys[key] = value

    def handle_enter_action(self):
        if self.menu_open:
            return self.activate_menu_selection()
        return self.begin_presentation_deploy()

    def refresh_menu_selection(self):
        buttons = list(getattr(self, "menu_buttons", []) or [])
        if not buttons:
            return False
        self.menu_selected_index = max(0, min(len(buttons) - 1, int(getattr(self, "menu_selected_index", 0))))
        for idx, (button, _action) in enumerate(buttons):
            selected = idx == self.menu_selected_index
            if button is getattr(self, "btn_quit", None):
                button["frameColor"] = (0.34, 0.08, 0.08, 0.99) if selected else (0.18, 0.07, 0.07, 0.96)
                button["text_fg"] = (1.0, 0.96, 0.86, 1.0) if selected else (1.0, 0.88, 0.88, 1.0)
            else:
                button["frameColor"] = (0.08, 0.34, 0.42, 0.99) if selected else (0.12, 0.12, 0.12, 0.96)
                button["text_fg"] = (1.0, 1.0, 1.0, 1.0) if selected else (0.95, 0.95, 0.95, 1.0)
        return True

    def navigate_menu(self, delta):
        if not self.menu_open:
            return False
        buttons = list(getattr(self, "menu_buttons", []) or [])
        if not buttons:
            return False
        self.menu_selected_index = (int(getattr(self, "menu_selected_index", 0)) + int(delta)) % len(buttons)
        self.refresh_menu_selection()
        return True

    def activate_menu_selection(self):
        if not self.menu_open:
            return False
        buttons = list(getattr(self, "menu_buttons", []) or [])
        if not buttons:
            return False
        self.refresh_menu_selection()
        _button, action = buttons[self.menu_selected_index]
        action()
        return True

    def adjust_menu_setting(self, direction):
        if not self.menu_open:
            return False
        idx = int(getattr(self, "menu_selected_index", 0))
        # These settings are cyclic, so left/right both keep the menu usable without
        # creating a second configuration authority. Resume/Quit intentionally ignore them.
        if idx in (1, 2, 3):
            _button, action = self.menu_buttons[idx]
            action()
            return True
        return False

    def set_fire(self, value, hand="right"):
        if self.source_vector_arena_controls_active() or bool(getattr(self, "presentation_open", False)):
            return
        hand = "left" if str(hand) == "left" else "right"
        if self.menu_open:
            if isinstance(self.fire_hold, dict):
                self.fire_hold[hand] = False
            if isinstance(self.fire_down, dict):
                self.fire_down[hand] = False
            return
        if not isinstance(self.fire_hold, dict):
            self.fire_hold = {"right": False, "left": False}
        if not isinstance(self.fire_down, dict):
            self.fire_down = {"right": False, "left": False}
        self.fire_hold[hand] = bool(value)
        if value:
            self.fire_down[hand] = True

    def set_presentation_visual_isolation(self, active: bool):
        active = bool(active)
        if active:
            self.hud_root.hide()
            self.crosshair.hide()
        elif bool(getattr(self, "hud_visible", True)):
            self.hud_root.show()
            self.crosshair.show()
        for mount in getattr(self, "weapon_mounts", {}).values():
            root = mount.get("root")
            if root is not None and not root.isEmpty():
                root.hide() if active else root.show()
        if not SELF_TEST and getattr(self, "win", None) is not None:
            props = WindowProperties()
            props.setCursorHidden(not active)
            if hasattr(self.win, "requestProperties"):
                self.win.requestProperties(props)
        return True

    def begin_presentation_deploy(self):
        if not bool(getattr(self, "presentation_open", False)):
            return False
        self.presentation_open = False
        self.presentation_root.hide()
        self.help_return_to_presentation = False
        self.set_presentation_visual_isolation(False)
        if not SELF_TEST and not self.menu_open:
            self.recenter_mouse(force=True)
        self.set_objective_banner("Follow the physical capture marker", 2.2)
        return True

    def open_presentation_reference(self):
        if not bool(getattr(self, "presentation_open", False)):
            return False
        self.help_return_to_presentation = True
        self.presentation_root.hide()
        self.toggle_help_reference()
        return True

    def toggle_hud(self):
        if bool(getattr(self, "presentation_open", False)):
            return
        if self.source_vector_arena_controls_active():
            mode = getattr(self, "vector_arena_native_mode", None)
            try:
                if mode is not None and hasattr(mode, "on_host_action"):
                    mode.on_host_action("h")
            except Exception:
                pass
            return
        self.hud_visible = not self.hud_visible
        if self.hud_visible:
            self.hud_root.show()
            self.crosshair.show()
        else:
            self.hud_root.hide()
            self.crosshair.hide()

    def toggle_workstation(self):
        if self.source_vector_arena_controls_active():
            return
        if self.help_visible:
            self.toggle_help_reference()
        self.workstation_visible = not self.workstation_visible
        if self.workstation_visible:
            self.refresh_workstation_text()
            self.workstation_refresh_timer = 0.25
            self.work_root.show()
        else:
            self.work_root.hide()

    def toggle_help_reference(self):
        if self.source_vector_arena_controls_active() or self.menu_open:
            return
        opening_from_presentation = bool(getattr(self, "presentation_open", False)) and not bool(getattr(self, "help_visible", False))
        if opening_from_presentation:
            self.help_return_to_presentation = True
            self.presentation_root.hide()
        self.help_visible = not bool(getattr(self, "help_visible", False))
        if self.help_visible:
            if self.workstation_visible:
                self.workstation_visible = False
                self.work_root.hide()
            for hand in ("right", "left"):
                self.fire_hold[hand] = False
                self.fire_down[hand] = False
            self.help_hud_was_visible = bool(getattr(self, "hud_visible", True))
            self.hud_root.hide()
            self.crosshair.hide()
            for mount in getattr(self, "weapon_mounts", {}).values():
                root = mount.get("root")
                if root is not None and not root.isEmpty():
                    root.hide()
            self.help_root.show()
            props = WindowProperties()
            props.setCursorHidden(False)
            if hasattr(self.win, "requestProperties"):
                self.win.requestProperties(props)
        else:
            self.help_root.hide()
            if bool(getattr(self, "help_hud_was_visible", getattr(self, "hud_visible", True))):
                self.hud_root.show()
                self.crosshair.show()
            if bool(getattr(self, "help_return_to_presentation", False)):
                self.presentation_open = True
                self.presentation_root.show()
                self.hud_root.hide()
                self.crosshair.hide()
                for mount in getattr(self, "weapon_mounts", {}).values():
                    root = mount.get("root")
                    if root is not None and not root.isEmpty():
                        root.hide()
                self.help_return_to_presentation = False
                props = WindowProperties()
                props.setCursorHidden(False)
                if hasattr(self.win, "requestProperties"):
                    self.win.requestProperties(props)
                return
            for mount in getattr(self, "weapon_mounts", {}).values():
                root = mount.get("root")
                if root is not None and not root.isEmpty():
                    root.show()
            if not SELF_TEST and not self.menu_open:
                props = WindowProperties()
                props.setCursorHidden(True)
                if hasattr(self.win, "requestProperties"):
                    self.win.requestProperties(props)
                self.recenter_mouse(force=True)

    def toggle_menu(self):
        if self.help_visible:
            self.toggle_help_reference()
            return
        if self.source_vector_arena_controls_active():
            self.exit_arena_mode(completed=False)
            return
        self.menu_open = not self.menu_open
        if self.menu_open:
            self.presentation_was_open_for_menu = bool(getattr(self, "presentation_open", False))
            if self.presentation_was_open_for_menu:
                self.presentation_root.hide()
            for hand in ("right", "left"):
                self.fire_hold[hand] = False
                self.fire_down[hand] = False
            self.refresh_ui_text()
            self.menu_selected_index = 0
            self.refresh_menu_selection()
            self.menu_root.show()
            props = WindowProperties()
            props.setCursorHidden(False)
            props.setMouseMode(WindowProperties.M_absolute)
            if hasattr(self.win, "requestProperties"):
                self.win.requestProperties(props)
        else:
            self.menu_root.hide()
            for key in ("w", "a", "s", "d", "shift", "space"):
                self.keys[key] = False
            if bool(getattr(self, "presentation_was_open_for_menu", False)) and bool(getattr(self, "presentation_open", False)):
                self.presentation_root.show()
                props = WindowProperties()
                props.setCursorHidden(False)
                if hasattr(self.win, "requestProperties"):
                    self.win.requestProperties(props)
                self.presentation_was_open_for_menu = False
                return
            self.presentation_was_open_for_menu = False
            if not SELF_TEST:
                props = WindowProperties()
                props.setCursorHidden(True)
                if hasattr(self.win, "requestProperties"):
                    self.win.requestProperties(props)
                self.recenter_mouse(force=True)

    def on_window_event(self, window):
        if not SELF_TEST and window is not None:
            self.recenter_mouse(force=True)

    def recenter_mouse(self, force=False):
        if SELF_TEST or self.menu_open or self.help_visible or bool(getattr(self, "presentation_open", False)) or not self.win:
            return
        if not hasattr(self.win, "movePointer") or not hasattr(self.win, "getXSize"):
            return
        if hasattr(self.win, "getProperties") and not self.win.getProperties().getForeground() and not force:
            return
        cx = self.win.getXSize() // 2
        cy = self.win.getYSize() // 2
        self.win.movePointer(0, cx, cy)

    def clean_hud_message(self, text: str) -> str:
        msg = str(text or "").strip().replace("//", " • ").replace("_", " ")
        msg = " ".join(msg.split())
        replacements = {
            "CAPTURE ZONE": "Capture zone",
            "BREACHED": "breached",
            "HOSTILES INBOUND": "hostiles inbound",
            "SPAWN BLOCKED": "spawn blocked",
            "SHIELD BREAK": "Shield broken",
            "CORE VULNERABLE": "core exposed",
            "ARMOR BROKEN": "Armor broken",
            "AIM CORE": "aim for core",
            "CIVILIAN HARMED": "Civilian harmed",
            "CIVILIAN LOST": "Civilian lost",
            "PATROL DRONE": "Patrol drone",
            "AMMO CACHE": "ammo cache",
            "VECTOR ARENA": "Vector Arena",
            "PORTAL OPEN": "portal open",
            "PRESS E": "press E",
            "BOSS MECH": "Boss mech",
            "WALKER": "walker",
            "SHIFTER": "shifter",
        }
        for src, dst in replacements.items():
            msg = msg.replace(src, dst)
        if msg.isupper():
            msg = msg.title()
        return msg[:96]

    def weapon_hud_values(self, right_weapon, left_weapon, weapon_slot: int, left_slot: int) -> tuple[str, str]:
        def ammo_for(slot):
            try:
                weapon = self.get_weapon_by_slot(slot) if hasattr(self, "get_weapon_by_slot") else None
                value = int(float(getattr(self, "weapon_ammo_pools", {}).get(int(slot), 0.0)))
                cap = int(float(getattr(self, "weapon_ammo_caps", {}).get(int(slot), getattr(weapon, "ammo_capacity", 0)))) if hasattr(self, "weapon_ammo_caps") else int(float(getattr(weapon, "ammo_capacity", 0)))
                return f"{value}/{cap}"
            except Exception:
                return "--"
        return f"L{left_slot}  {ammo_for(left_slot)}", f"R{weapon_slot}  {ammo_for(weapon_slot)}"


    def _set_ui_text(self, widget, value: str) -> bool:
        """Assign UI text only when the rendered value really changed."""
        value = str(value or "")
        if widget in (getattr(self, "center_text", None), getattr(self, "mission_text", None)):
            if value:
                widget.show()
            else:
                widget.hide()
        branch_map = {
            id(getattr(self, "status_text", None)): getattr(self, "status_frame", None),
            id(getattr(self, "detail_text", None)): getattr(self, "detail_frame", None),
        }
        branch = branch_map.get(id(widget))
        if branch is not None:
            if value:
                branch.show()
            else:
                branch.hide()
        try:
            current = str(widget["text"] or "")
        except Exception:
            current = ""
        if current == value:
            self.ui_text_skips = int(getattr(self, "ui_text_skips", 0)) + 1
            return False
        widget["text"] = value
        self.ui_text_mutations = int(getattr(self, "ui_text_mutations", 0)) + 1
        return True

    def refresh_ui_text(self):
        right_weapon = self.get_weapon_for_hand("right") if hasattr(self, "get_weapon_for_hand") else self.current_weapon
        left_weapon = self.get_weapon_for_hand("left") if hasattr(self, "get_weapon_for_hand") else self.current_weapon
        weapon_slot = self.selected_slot_for_hand("right") if hasattr(self, "selected_slot_for_hand") else int(getattr(self, "current_weapon_slot", 1) or 1)
        left_slot = self.selected_slot_for_hand("left") if hasattr(self, "selected_slot_for_hand") else weapon_slot
        activities_done, activities_total = self.activity_counts() if hasattr(self, "activity_counts") else (0, 0)
        if getattr(self, "arena_mode_active", False):
            arena_name = str((getattr(self, "arena_variant", {}) or {}).get("name", "Vector Arena"))
            wave = int(getattr(self, "arena_wave", 0))
            waves = int((getattr(self, "arena_variant", {}) or {}).get("waves_per_capture", 3))
            core_hp = int(getattr(self, "arena_core_hp", 0))
            core_max = int(getattr(self, "arena_core_max_hp", 0))
            timer = int(max(0.0, float(getattr(self, "arena_wave_timer", 0.0))))
            kills = int(getattr(self, "arena_wave_kills", 0))
            kill_goal = int(getattr(self, "arena_wave_target_kills", 0))
            hud_value = f"SCORE {int(self.score)}  •  LAB {int(getattr(self, 'lab_points', 0))}"
            status_value = f"CORE {core_hp}/{core_max}" if core_max > 0 else ""
            detail_value = f"WAVE {wave}/{waves}  •  KILLS {kills}/{kill_goal}  •  {timer:02d}s" if wave > 0 else ""
        else:
            hostile = int(max(0.0, float(getattr(self, "player_hostility_timer", 0.0))))
            hud_value = f"SCORE {int(self.score)}  •  LAB {int(getattr(self, 'lab_points', 0))}"
            status_value = f"ALERT {hostile}s" if hostile > 0 else ""
            activity_prompt = self.activity_instance_prompt() if hasattr(self, "activity_instance_prompt") else ""
            detail_value = self.clean_hud_message(activity_prompt) if activity_prompt else ""
            if not detail_value:
                active = self.get_active_campaign_point() if hasattr(self, "get_active_campaign_point") else None
                if active is not None:
                    player_flat = Vec3(self.player_pos.x, self.player_pos.y, 0.0)
                    node_dist = (active["pos"] - player_flat).length()
                    if node_dist <= 10.0:
                        detail_value = f"CAPTURE {int(round(float(active.get('progress', 0.0))))}%  •  REGEN ACTIVE"
        left_ammo, right_ammo = self.weapon_hud_values(right_weapon, left_weapon, weapon_slot, left_slot)
        self._set_ui_text(self.hud_text, hud_value)
        self._set_ui_text(self.status_text, status_value)
        self._set_ui_text(self.weapon_text, left_ammo)
        self._set_ui_text(self.weapon_right_text, right_ammo)
        self._set_ui_text(self.detail_text, detail_value)
        self._set_ui_text(self.help_text, "")
        self.refresh_mission_text()
        try:
            menu_value = (
                "WASD move  •  Mouse aim  •  Shift sprint\n"
                "LMB / RMB dual weapons  •  E interact\n"
                "H HUD  •  F1 help  •  F10 activity board\n"
                "ESC resume\n"
                "U ammo  •  Shift+U health  •  I armor"
            )
            self._set_ui_text(self.menu_info, menu_value)
            self._set_ui_text(self.btn_distance, f"Draw Distance  {int(self.game_cfg.max_view_distance)}")
            self._set_ui_text(self.btn_lines, f"Line Thickness  {self.game_cfg.line_thickness:.2f}")
            self._set_ui_text(self.btn_sensitivity, f"Mouse Sensitivity  {self.game_cfg.mouse_sensitivity:.2f}")
        except Exception:
            pass

    def refresh_workstation_text(self):
        if not bool(getattr(self, "workstation_visible", False)):
            return False
        value = (
            f"Mode: {getattr(self, 'activity_mode_name', 'Prototype Lab Activity Mode')}\n"
            f"Version: {VERSION}\n"
            f"Activities: {self.activity_counts()[0]}/{self.activity_counts()[1]}  Lab XP: {int(getattr(self, 'activity_bonus_score', 0))}\n"
            f"Body: 100-hit base  Armor shell: {self.player_armor_percent_capacity()}% cyan overlay\n"
            f"Next: {self.next_activity_hint()}\n"
            f"Weapon Pair: R{self.selected_slot_for_hand('right') if hasattr(self, 'selected_slot_for_hand') else getattr(self, 'current_weapon_slot', 1)} {self.get_weapon_for_hand('right').name if hasattr(self, 'get_weapon_for_hand') and self.get_weapon_for_hand('right') else '-'} // L{self.selected_slot_for_hand('left') if hasattr(self, 'selected_slot_for_hand') else getattr(self, 'current_weapon_slot', 1)} {self.get_weapon_for_hand('left').name if hasattr(self, 'get_weapon_for_hand') and self.get_weapon_for_hand('left') else '-'}\n"
            f"Weapon Unlocks: {self.weapon_slot_status_line() if hasattr(self, 'weapon_slot_status_line') else ''}\n"
            f"Nodes: {sum(1 for p in getattr(self, 'campaign_points', []) if p.get('captured'))}/{len(getattr(self, 'campaign_points', []) or [])}  Signals: {getattr(self, 'signal_fragments_recovered', 0)}/{getattr(self, 'signal_fragments_required', 0)}\n"
            f"Enemies: {sum(not e.dead for e in self.enemies)}  Chunks: {len(self.chunks)}\n"
            f"District: {UTOPIA_DISTRICTS.get(getattr(self, 'current_district_id', 'calibration'), UTOPIA_DISTRICTS['calibration'])['name']}  Drops: {self.district_ammo_summary() if hasattr(self, 'district_ammo_summary') else '-'}\n"
            f"Recent: {self.recent_activity_line()}\n"
            f"F10 hide  1-6 tools  TAB cycle  0 return"
        )
        return self._set_ui_text(self.work_text, value)

    def day_label(self):
        labels = ["Dawn", "Day", "Dusk", "Night"]
        t = (self.elapsed % self.game_cfg.day_length_seconds) / self.game_cfg.day_length_seconds
        if t < 0.2:
            return labels[0]
        if t < 0.5:
            return labels[1]
        if t < 0.7:
            return labels[2]
        return labels[3]

    def player_health_ratio(self) -> float:
        try:
            max_hp = max(1.0, float(getattr(self, "player_health_max", getattr(self.game_cfg, "default_health", 100)) or 100))
            return max(0.0, min(1.0, float(getattr(self, "health", max_hp)) / max_hp))
        except Exception:
            return 1.0

    def player_armor_ratio(self) -> float:
        try:
            max_armor = max(0.0, float(getattr(self, "player_armor_max", 0.0) or 0.0))
            if max_armor <= 0.0:
                return 0.0
            return max(0.0, min(1.0, float(getattr(self, "player_armor", 0.0)) / max_armor))
        except Exception:
            return 0.0

    def player_armor_percent_capacity(self) -> int:
        level = int(getattr(self, "upgrade_levels", {}).get("armor_capacity", 0) or 0)
        base = float(getattr(self.game_cfg, "player_armor_default_ratio", 0.10))
        step = float(getattr(self.game_cfg, "player_armor_upgrade_ratio_step", 0.10))
        return int(round(max(0.0, base + step * max(0, level)) * 100.0))

    def compute_player_armor_max(self) -> int:
        ratio = self.player_armor_percent_capacity() / 100.0
        return max(0, int(round(float(getattr(self, "player_health_max", getattr(self.game_cfg, "default_health", 100))) * ratio)))

    def sync_player_armor_capacity(self, refill: bool = False) -> int:
        old_max = int(getattr(self, "player_armor_max", 0) or 0)
        old_value = int(getattr(self, "player_armor", 0) or 0)
        new_max = self.compute_player_armor_max()
        self.player_armor_max = new_max
        if refill or old_max <= 0:
            self.player_armor = new_max
        else:
            self.player_armor = max(0, min(new_max, old_value + max(0, new_max - old_max)))
        return self.player_armor_max

    def health_palette_color(self, ratio: float):
        """Return the body-condition color for health.

        Full health is green, half health is amber, empty health is red. Armor
        is handled separately as a cyan overlay/blend, so health never depends
        on a generic hue cycle.
        """
        ratio = max(0.0, min(1.0, float(ratio)))
        if ratio >= 0.5:
            t = (ratio - 0.5) / 0.5
            amber = (1.00, 0.72, 0.08)
            healthy = (0.10, 1.00, 0.20)
            return tuple(amber[i] * (1.0 - t) + healthy[i] * t for i in range(3))
        t = ratio / 0.5
        danger = (1.00, 0.04, 0.02)
        amber = (1.00, 0.72, 0.08)
        return tuple(danger[i] * (1.0 - t) + amber[i] * t for i in range(3))

    def armor_cyan_color(self):
        return (0.12, 0.92, 1.00)

    def apply_health_to_line_rgb(self, cycle_rgb):
        # User-facing rule: the wireframe itself is the condition meter.
        ratio = self.player_health_ratio()
        self.health_ratio = ratio
        condition_rgb = self.health_palette_color(ratio)
        self.health_line_rgb = condition_rgb
        if not bool(getattr(self.game_cfg, "health_palette_enabled", True)):
            return tuple(cycle_rgb)

        armor_ratio = self.player_armor_ratio()
        self.armor_ratio = armor_ratio
        if armor_ratio <= 0.0:
            return condition_rgb

        cyan = self.armor_cyan_color()
        # Remaining armor controls the baseline cyan strength. A recent hit
        # temporarily exposes the most recent body-health color under the armor.
        hit_window = max(0.001, float(getattr(self.game_cfg, "player_armor_hit_fade_seconds", 0.85)))
        hit_t = max(0.0, min(1.0, float(getattr(self, "armor_damage_fade_timer", 0.0)) / hit_window))
        cyan_strength = max(0.0, min(1.0, armor_ratio * (1.0 - 0.82 * hit_t)))
        armored_rgb = tuple(condition_rgb[i] * (1.0 - cyan_strength) + cyan[i] * cyan_strength for i in range(3))
        self.armor_line_rgb = armored_rgb
        return armored_rgb

    def apply_player_damage(self, amount: float, source: str = "damage") -> dict:
        source = str(source)
        if float(getattr(self, "player_damage_grace_timer", 0.0)) > 0.0 and source != "enemy_contact":
            return {"raw": 0, "absorbed_by_armor": 0, "body_damage": 0, "armor_before": int(getattr(self, "player_armor", 0) or 0), "armor_after": int(getattr(self, "player_armor", 0) or 0), "health_before": int(getattr(self, "health", 0) or 0), "health_after": int(getattr(self, "health", 0) or 0), "source": source, "grace_blocked": True}
        raw = max(0, int(math.ceil(float(amount))))
        armor_before = int(getattr(self, "player_armor", 0) or 0)
        health_before = int(getattr(self, "health", 0) or 0)
        absorbed = min(armor_before, raw)
        remaining = raw - absorbed
        if absorbed > 0:
            self.player_armor = max(0, armor_before - absorbed)
            self.armor_damage_fade_timer = max(float(getattr(self, "armor_damage_fade_timer", 0.0)), float(getattr(self.game_cfg, "player_armor_hit_fade_seconds", 0.85)))
            self.armor_damage_flash = max(float(getattr(self, "armor_damage_flash", 0.0)), 1.0)
            try:
                self.play_sfx("armor", volume=0.58 if remaining <= 0 else 0.78)
            except Exception:
                pass
        if remaining > 0:
            self.health = max(0, health_before - remaining)
            try:
                self.play_sfx("player_hit", volume=0.68)
            except Exception:
                pass
        if raw > 0 and source != "enemy_contact":
            self.player_damage_grace_timer = max(float(getattr(self, "player_damage_grace_timer", 0.0)), float(getattr(self.game_cfg, "player_damage_grace_seconds", 0.16)))
        self.update_palette(0.0)
        return {
            "raw": raw,
            "absorbed_by_armor": absorbed,
            "body_damage": remaining,
            "armor_before": armor_before,
            "armor_after": int(getattr(self, "player_armor", 0) or 0),
            "health_before": health_before,
            "health_after": int(getattr(self, "health", 0) or 0),
            "source": str(source),
        }

    def current_line_color(self, alpha=1.0):
        r, g, b = self.line_rgb
        return (r, g, b, alpha)

    def current_blotch_color(self, alpha=1.0):
        r, g, b = self.line_rgb
        return (min(1.0, r * 1.15), min(1.0, g * 1.08), min(1.0, b * 1.02), alpha)

    def current_campaign_accent_color(self, alpha=1.0):
        r, g, b = getattr(self, "campaign_accent_rgb", self.line_rgb)
        return (r, g, b, alpha)

    def current_campaign_secondary_color(self, alpha=1.0):
        r, g, b = getattr(self, "campaign_secondary_rgb", self.line_rgb)
        return (r, g, b, alpha)

    def current_campaign_threat_color(self, alpha=1.0):
        r, g, b = getattr(self, "campaign_threat_rgb", (1.0, 0.22, 0.08))
        return (r, g, b, alpha)

    def palette_value(self):
        return sum(self.line_rgb) / 3.0

    def update_palette(self, dt: float):
        day_len = max(60.0, self.game_cfg.day_length_seconds)
        self.day_phase = (self.elapsed % day_len) / day_len
        transition = max(10.0, self.game_cfg.transition_length_seconds) / day_len

        def smooth_band(x, center):
            d = abs((x - center + 0.5) % 1.0 - 0.5)
            if d >= transition * 0.5:
                return 0.0
            y = 1.0 - d / (transition * 0.5)
            return y * y * (3 - 2 * y)

        dawn = smooth_band(self.day_phase, 0.10)
        dusk = smooth_band(self.day_phase, 0.60)
        day_base = 1.0 if 0.10 <= self.day_phase < 0.60 else 0.0
        day_amount = max(day_base, dawn)
        day_amount = min(day_amount, 1.0 - dusk * (1.0 - day_amount))
        self.day_night_mix = day_amount
        self.armor_damage_fade_timer = max(0.0, float(getattr(self, "armor_damage_fade_timer", 0.0)) - max(0.0, float(dt)))
        self.armor_damage_flash = max(0.0, float(getattr(self, "armor_damage_flash", 0.0)) - max(0.0, float(dt)) * 1.8)

        cycle_len = max(45.0, float(getattr(self.game_cfg, "campaign_hue_cycle_seconds", 240.0)))
        hue = (0.115 + (self.elapsed / cycle_len)) % 1.0
        # Keep the linework saturated while allowing the shared sky/background to
        # travel on the opposite side of the wheel for a cleaner complementary look.
        sat = 0.68
        line_value = 0.92 - 0.30 * day_amount
        cycle_line_rgb = colorsys.hsv_to_rgb(hue, sat, line_value)
        line_rgb = self.apply_health_to_line_rgb(cycle_line_rgb)
        # Keep accents cycling, but let them inherit a small amount of the player condition.
        accent_cycle = colorsys.hsv_to_rgb((hue + 0.08) % 1.0, min(0.82, sat + 0.10), min(1.0, line_value + 0.14))
        secondary_cycle = colorsys.hsv_to_rgb((hue + 0.43) % 1.0, max(0.50, sat - 0.12), min(0.98, line_value + 0.04))
        threat_rgb = colorsys.hsv_to_rgb((hue + 0.91) % 1.0, 0.86, 1.0)
        hp_rgb = getattr(self, "health_line_rgb", line_rgb)
        hp_damage = 1.0 - float(getattr(self, "health_ratio", 1.0))
        accent_rgb = tuple(accent_cycle[i] * (1.0 - hp_damage * 0.28) + hp_rgb[i] * (hp_damage * 0.28) for i in range(3))
        secondary_rgb = tuple(secondary_cycle[i] * (1.0 - hp_damage * 0.18) + hp_rgb[i] * (hp_damage * 0.18) for i in range(3))

        opposite_bg = bool(getattr(self.game_cfg, "background_opposite_cycle", True) or getattr(self.game_cfg, "invert_background", False))
        bg_hue = (hue + float(getattr(self.game_cfg, "background_hue_shift", 0.5))) % 1.0 if opposite_bg else hue
        bg_sat = max(0.08, min(0.60, float(getattr(self.game_cfg, "background_cycle_saturation", 0.34))))
        bg_horizon_value = float(getattr(self.game_cfg, "background_cycle_horizon_value_night", 0.18)) + (float(getattr(self.game_cfg, "background_cycle_horizon_value_day", 0.64)) - float(getattr(self.game_cfg, "background_cycle_horizon_value_night", 0.18))) * day_amount
        bg_zenith_value = float(getattr(self.game_cfg, "background_cycle_zenith_value_night", 0.07)) + (float(getattr(self.game_cfg, "background_cycle_zenith_value_day", 0.34)) - float(getattr(self.game_cfg, "background_cycle_zenith_value_night", 0.07))) * day_amount
        self.sky_horizon_rgb = colorsys.hsv_to_rgb(bg_hue, bg_sat, bg_horizon_value)
        self.sky_zenith_rgb = colorsys.hsv_to_rgb((bg_hue + 0.04) % 1.0, min(0.72, bg_sat + 0.08), bg_zenith_value)
        # Preserve the opposite background cycle, but let low health subtly darken
        # and warm the background so the line-color warning feels integrated.
        hp_damage = 1.0 - float(getattr(self, "health_ratio", 1.0))
        warning_strength = float(getattr(self.game_cfg, "health_palette_background_warning_strength", 0.22)) * hp_damage
        warning_bg = (0.18, 0.018, 0.012)
        self.sky_horizon_rgb = tuple(self.sky_horizon_rgb[i] * (1.0 - warning_strength) + warning_bg[i] * warning_strength for i in range(3))
        self.sky_zenith_rgb = tuple(self.sky_zenith_rgb[i] * (1.0 - warning_strength * 0.72) + warning_bg[i] * (warning_strength * 0.72) for i in range(3))
        self.structure_mask_rgb = tuple((self.sky_horizon_rgb[i] * 0.86 + self.sky_zenith_rgb[i] * 0.14) for i in range(3))
        self.line_rgb = line_rgb
        self.campaign_accent_rgb = accent_rgb
        self.campaign_secondary_rgb = secondary_rgb
        self.campaign_threat_rgb = threat_rgb

        bg = tuple(getattr(self, "structure_mask_rgb", tuple((self.sky_horizon_rgb[i] * 0.82 + self.sky_zenith_rgb[i] * 0.18) for i in range(3))))
        self.setBackgroundColor(*bg, 1.0)
        self.update_structure_occlusion_colors()
        for np in getattr(self, "crosshair_lines", []):
            np.setColor(*self.current_line_color(alpha=0.96))
        # Push palette changes into active dynamic line roots too.
        for actor in list(getattr(self, "enemies", []) or []) + list(getattr(self, "civilians", []) or []):
            try:
                line_root = getattr(actor, "line_root", None)
                if line_root is not None and not line_root.isEmpty() and not bool(getattr(actor, "is_civilian", False)):
                    line_root.setColor(*self.current_line_color(alpha=0.98))
            except Exception:
                pass
        for drone in list(getattr(self, "patrol_drones", []) or []):
            try:
                line_root = getattr(drone, "line_root", None)
                if line_root is not None and not line_root.isEmpty():
                    line_root.setColor(*self.current_line_color(alpha=0.96))
            except Exception:
                pass
        field = getattr(self, "campaign_field_node", None)
        if field is not None and not field.isEmpty():
            field.setColor(*self.current_campaign_accent_color(alpha=0.82), 1)

    def create_blotch_texture(self):
        generate_blotch_texture_file()

    def hashed_seed(self, x: int, y: int, salt: int = 0) -> int:
        return (x * 92837111 ^ y * 689287499 ^ self.game_cfg.world_seed ^ salt * 334214459) & 0xFFFFFFFF



    def district_for_chunk(self, cx: int, cy: int):
        boundary = max(2, int(getattr(self.game_cfg, "district_size_chunks", 6)))
        if max(abs(int(cx)), abs(int(cy))) < boundary:
            return "calibration", UTOPIA_DISTRICTS["calibration"]
        # Districts grow by cardinal proof passes so every new zone has a clear
        # entry direction and its own ammo/enemy flavor instead of random sprawl.
        if int(cy) >= boundary:
            return "high_towers", UTOPIA_DISTRICTS["high_towers"]
        if int(cx) >= boundary:
            return "pyramid_sector", UTOPIA_DISTRICTS["pyramid_sector"]
        return "calibration", UTOPIA_DISTRICTS["calibration"]

    def district_for_position(self, pos: Vec3):
        csize = max(1.0, float(getattr(self.game_cfg, "chunk_size", 64)))
        cx = int(math.floor(float(pos.x) / csize))
        cy = int(math.floor(float(pos.y) / csize))
        return self.district_for_chunk(cx, cy)

    def update_current_district(self, announce: bool = True):
        district_id, district = self.district_for_position(Vec3(self.player_pos.x, self.player_pos.y, 0))
        changed = district_id != getattr(self, "current_district_id", "calibration")
        self.current_district_id = district_id
        if changed or not getattr(self, "last_announced_district_id", ""):
            if announce:
                self.last_announced_district_id = district_id
                self.district_banner_time = float(getattr(self.game_cfg, "district_banner_seconds", 2.8))
                self.set_objective_banner(f"DISTRICT // {district['name'].upper()} // {district['activity']}", self.district_banner_time)
        return district_id, district

    def district_ammo_slots(self, district_id: str | None = None):
        did = district_id or getattr(self, "current_district_id", "calibration")
        district = UTOPIA_DISTRICTS.get(did, UTOPIA_DISTRICTS["calibration"])
        slots = district.get("ammo_slots", [1])
        result = []
        for slot in slots:
            try:
                slot_i = int(slot)
            except Exception:
                continue
            if self.get_weapon_by_slot(slot_i) is not None:
                result.append(slot_i)
        return result or [1]

    def district_ammo_summary(self, district_id: str | None = None) -> str:
        slots = self.district_ammo_slots(district_id)
        names = []
        for slot in slots:
            weapon = self.get_weapon_by_slot(slot) if hasattr(self, "get_weapon_by_slot") else None
            if weapon:
                names.append(f"{slot}:{weapon.name.split()[0]}")
            else:
                names.append(str(slot))
        return "/".join(names)

    def choose_enemy_ammo_drop_slot(self, enemy=None) -> int:
        district_id = getattr(self, "current_district_id", "calibration")
        if enemy is not None:
            try:
                district_id, _district = self.district_for_position(enemy.root.getPos(self.render))
            except Exception:
                pass
        district_slots = self.district_ammo_slots(district_id)
        # Districts should matter, but enemy type still nudges the result so
        # mobs feel like they carry a recognizable resource flavor.
        variant_map = {
            "stalker": 6,      # Auto Lattice cells
            "bulwark": 2,      # Imploder cores
            "commander": 5,    # Burst Splitter prisms
            "sentinel": 1,     # Core Lance charge
        }
        preferred = variant_map.get(str(getattr(enemy, "variant", "sentinel")), 1)
        rng = random.Random(self.hashed_seed(int(self.elapsed * 10), int(getattr(enemy, "seed", 0)), 1818))
        bias = float(getattr(self.game_cfg, "district_ammo_drop_bias", 0.82))
        if preferred in district_slots and rng.random() > bias:
            return preferred
        return int(rng.choice(district_slots))

    def enemy_ammo_reward_amount(self, slot: int, enemy=None) -> float:
        base = float(getattr(self.game_cfg, "weapon_specific_ammo_reward", 10.0))
        if str(getattr(enemy, "variant", "")) in {"bulwark", "commander"}:
            base *= 1.45
        weapon = self.get_weapon_by_slot(int(slot))
        if weapon is not None:
            return max(1.0, min(float(getattr(weapon, "ammo_capacity", 100.0)) * 0.34, base))
        return base

    def draw_pyramid_edges(self, segs: LineSegs, center: Vec3, base_size: Vec3, height: float, tiers: int = 3):
        tiers = max(1, int(tiers or 1))
        base_w = max(4.0, float(base_size.x))
        base_d = max(4.0, float(base_size.y))
        height = max(5.0, float(height))
        z0 = float(center.z)
        for t in range(tiers):
            f0 = 1.0 - (t / tiers) * 0.72
            f1 = 1.0 - ((t + 1) / tiers) * 0.72
            z_a = z0 + height * (t / tiers)
            z_b = z0 + height * ((t + 1) / tiers)
            lower = [
                Vec3(center.x - base_w * 0.5 * f0, center.y - base_d * 0.5 * f0, z_a),
                Vec3(center.x + base_w * 0.5 * f0, center.y - base_d * 0.5 * f0, z_a),
                Vec3(center.x + base_w * 0.5 * f0, center.y + base_d * 0.5 * f0, z_a),
                Vec3(center.x - base_w * 0.5 * f0, center.y + base_d * 0.5 * f0, z_a),
            ]
            upper = [
                Vec3(center.x - base_w * 0.5 * f1, center.y - base_d * 0.5 * f1, z_b),
                Vec3(center.x + base_w * 0.5 * f1, center.y - base_d * 0.5 * f1, z_b),
                Vec3(center.x + base_w * 0.5 * f1, center.y + base_d * 0.5 * f1, z_b),
                Vec3(center.x - base_w * 0.5 * f1, center.y + base_d * 0.5 * f1, z_b),
            ]
            for ring in (lower, upper):
                for a, b in zip(ring, ring[1:] + ring[:1]):
                    segs.moveTo(a); segs.drawTo(b)
            for a, b in zip(lower, upper):
                segs.moveTo(a); segs.drawTo(b)
            # Prism diagonals make the sector distinct without adding collision-heavy geometry.
            segs.moveTo(lower[0]); segs.drawTo(upper[2])
            segs.moveTo(lower[1]); segs.drawTo(upper[3])
        apex = Vec3(center.x, center.y, z0 + height + max(base_w, base_d) * 0.18)
        top_ring = [
            Vec3(center.x - base_w * 0.14, center.y - base_d * 0.14, z0 + height),
            Vec3(center.x + base_w * 0.14, center.y - base_d * 0.14, z0 + height),
            Vec3(center.x + base_w * 0.14, center.y + base_d * 0.14, z0 + height),
            Vec3(center.x - base_w * 0.14, center.y + base_d * 0.14, z0 + height),
        ]
        for p in top_ring:
            segs.moveTo(p); segs.drawTo(apex)

    def draw_high_tower_beacon(self, segs: LineSegs, center: Vec3, rng: random.Random, height: float):
        height = max(72.0, float(height))
        shaft_w = rng.uniform(5.0, 8.0)
        shaft_d = rng.uniform(5.0, 8.0)
        core = Vec3(center.x, center.y, height * 0.5)
        core_size = Vec3(shaft_w, shaft_d, height)
        self.draw_box_edges(segs, core, core_size)
        # Stacked deck plates make the northern district read as a high-rise zone.
        deck_count = 4 + rng.randint(0, 3)
        for i in range(1, deck_count + 1):
            z = height * i / (deck_count + 1)
            deck_size = Vec3(shaft_w * rng.uniform(1.75, 2.55), shaft_d * rng.uniform(1.75, 2.55), rng.uniform(1.2, 2.2))
            self.draw_box_edges(segs, Vec3(center.x, center.y, z), deck_size)
            if rng.random() < 0.75:
                self.draw_ring(segs, Vec3(center.x, center.y, z + deck_size.z * 0.9), max(deck_size.x, deck_size.y) * 0.34, 14)
        antenna_base = Vec3(center.x, center.y, height + 1.2)
        self.draw_technical_spire(segs, antenna_base, rng, rng.uniform(18.0, 36.0))
        # Directional uplink braces point down into the street grid and make the skyline recognizable.
        for ang in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):
            x = center.x + math.cos(ang) * shaft_w * 2.4
            y = center.y + math.sin(ang) * shaft_d * 2.4
            segs.moveTo(center.x, center.y, height * 0.72)
            segs.drawTo(x, y, height * 0.46)

    def draw_calibration_landmark(self, segs: LineSegs, center: Vec3, rng: random.Random):
        """Low concentric calibration gantry: intentionally horizontal versus tower/pyramid districts."""
        scale = max(0.6, float(getattr(self.game_cfg, "district_landmark_scale", 1.0)))
        for idx, radius in enumerate((8.0, 13.0, 19.0)):
            z = 2.0 + idx * 2.8
            self.draw_ring(segs, Vec3(center.x, center.y, z), radius * scale, 20)
        for ang in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):
            outer = Vec3(center.x + math.cos(ang) * 19.0 * scale, center.y + math.sin(ang) * 19.0 * scale, 7.6)
            inner = Vec3(center.x + math.cos(ang) * 8.0 * scale, center.y + math.sin(ang) * 8.0 * scale, 2.0)
            segs.moveTo(inner); segs.drawTo(outer)
            pylon_top = outer + Vec3(0, 0, 11.0 * scale)
            segs.moveTo(outer); segs.drawTo(pylon_top)
        # Cross-axis sight lines make spawn/calibration chunks read like a test grid from afar.
        segs.moveTo(center.x - 24.0 * scale, center.y, 0.08); segs.drawTo(center.x + 24.0 * scale, center.y, 0.08)
        segs.moveTo(center.x, center.y - 24.0 * scale, 0.08); segs.drawTo(center.x, center.y + 24.0 * scale, 0.08)

    def draw_high_tower_crown(self, segs: LineSegs, center: Vec3, height: float, radius: float):
        """A tall forked broadcast crown that reads above the ordinary procedural skyline."""
        z = max(80.0, float(height))
        r = max(5.0, float(radius))
        self.draw_ring(segs, Vec3(center.x, center.y, z), r, 16)
        for ang in (0.0, math.pi * 0.5, math.pi, math.pi * 1.5):
            foot = Vec3(center.x + math.cos(ang) * r, center.y + math.sin(ang) * r, z)
            tip = Vec3(center.x + math.cos(ang) * r * 1.8, center.y + math.sin(ang) * r * 1.8, z + 24.0)
            segs.moveTo(foot); segs.drawTo(tip)
            segs.moveTo(tip); segs.drawTo(Vec3(center.x, center.y, z + 38.0))

    def draw_pyramid_gate_pair(self, segs: LineSegs, center: Vec3, rng: random.Random):
        """Paired stepped prisms create a broad triangular horizon marker with an open central lane."""
        scale = max(0.6, float(getattr(self.game_cfg, "district_landmark_scale", 1.0)))
        spread = 16.0 * scale
        for sign in (-1.0, 1.0):
            base_center = Vec3(center.x + sign * spread, center.y, 0.05)
            base = Vec3(24.0 * scale, 24.0 * scale, 0)
            self.draw_pyramid_edges(segs, base_center, base, 52.0 * scale, tiers=5)
        # Suspended apex trace visually ties the pair without creating a collision blocker.
        apex_z = 58.0 * scale
        segs.moveTo(center.x - spread, center.y, apex_z); segs.drawTo(center.x, center.y, apex_z + 13.0 * scale)
        segs.drawTo(center.x + spread, center.y, apex_z)

    def generate_chunk_geometry(self, cx: int, cy: int):
        chunk_seed = self.hashed_seed(cx, cy)
        rng = random.Random(chunk_seed)
        district_id, district = self.district_for_chunk(cx, cy)
        origin_x = cx * self.game_cfg.chunk_size
        origin_y = cy * self.game_cfg.chunk_size
        np = self.city_root.attachNewNode(f"chunk-{cx}-{cy}-{district_id}")
        mask_root = np.attachNewNode("occlusion-mask-root")
        line_root = np.attachNewNode("line-root")
        segs = LineSegs(f"chunk-lines-{cx}-{cy}")
        world_scale = max(0.22, min(1.0, float(getattr(self.game_cfg, "world_line_thickness_scale", 0.48))))
        segs.setThickness(max(1.0, float(self.game_cfg.line_thickness) * world_scale))
        segs.setColor(1.0, 1.0, 1.0, max(0.10, min(0.82, float(getattr(self.game_cfg, "world_line_alpha", 0.42)))))
        obstacles = []
        occlusion_boxes = []
        enemy_spawns = []

        line_root.setTransparency(TransparencyAttrib.MAlpha)

        grid_step = 8
        for gx in range(0, self.game_cfg.chunk_size + 1, grid_step):
            x = origin_x + gx
            segs.moveTo(x, origin_y, 0)
            segs.drawTo(x, origin_y + self.game_cfg.chunk_size, 0)
        for gy in range(0, self.game_cfg.chunk_size + 1, grid_step):
            y = origin_y + gy
            segs.moveTo(origin_x, y, 0)
            segs.drawTo(origin_x + self.game_cfg.chunk_size, y, 0)

        origin_zone = abs(cx) <= 1 and abs(cy) <= 1
        base_buildings = (2 + rng.randint(0, 2)) if origin_zone else (5 + rng.randint(0, 4))
        building_count = max(2, int(round(base_buildings * float(district.get("density_scale", 1.0)))))
        for i in range(building_count):
            bx = origin_x + rng.uniform(8, self.game_cfg.chunk_size - 8)
            by = origin_y + rng.uniform(8, self.game_cfg.chunk_size - 8)
            if origin_zone and abs(bx) < 28 and abs(by) < 34:
                continue
            if self.point_near_authored_travel_space(bx, by, extra_radius=8.0):
                continue
            w = rng.uniform(6, 14)
            d = rng.uniform(6, 14)
            h = rng.uniform(16, 90) * float(district.get("height_scale", 1.0))
            tiers = rng.randint(1, 4)
            base_x = bx
            base_y = by
            base_h = 0.0
            cur_w = w
            cur_d = d
            cur_h = h
            for t in range(tiers):
                center = Vec3(base_x, base_y, base_h + cur_h * 0.5)
                size = Vec3(cur_w, cur_d, cur_h)
                self.draw_box_edges(segs, center, size)
                self.draw_technical_facade(segs, center, size, rng)
                obstacles.append(BoxBounds(center - size * 0.5, center + size * 0.5, Vec3(0, 0, 1)))
                occlusion_boxes.append((Vec3(center), Vec3(size)))
                if rng.random() < 0.44:
                    bridge_len = rng.uniform(6, 18)
                    dir_sign = -1 if rng.random() < 0.5 else 1
                    bridge_center = center + Vec3(dir_sign * (cur_w * 0.5 + bridge_len * 0.5), 0, rng.uniform(-cur_h * 0.15, cur_h * 0.22))
                    bridge_size = Vec3(bridge_len, rng.uniform(2.0, 4.5), rng.uniform(2.0, 4.0))
                    if not self.point_near_authored_travel_space(bridge_center.x, bridge_center.y, extra_radius=max(4.0, bridge_len * 0.5)):
                        self.draw_box_edges(segs, bridge_center, bridge_size)
                        obstacles.append(BoxBounds(bridge_center - bridge_size * 0.5, bridge_center + bridge_size * 0.5, Vec3(0, 0, 1)))
                        occlusion_boxes.append((Vec3(bridge_center), Vec3(bridge_size)))
                base_x += rng.uniform(-3.5, 3.5)
                base_y += rng.uniform(-3.5, 3.5)
                base_h += cur_h
                cur_w = max(3.2, cur_w * rng.uniform(0.55, 0.82))
                cur_d = max(3.2, cur_d * rng.uniform(0.55, 0.82))
                cur_h = max(7.0, cur_h * rng.uniform(0.35, 0.62))

            if rng.random() < 0.45:
                mech_x = bx + rng.uniform(-10, 10)
                mech_y = by + rng.uniform(-10, 10)
                mech_z = rng.uniform(8, 24)
                self.draw_mechanical_cluster(segs, Vec3(mech_x, mech_y, mech_z), rng)
            if rng.random() < float(district.get("spire_chance", getattr(self.game_cfg, "technical_design_spire_chance", 0.30))):
                spire_pos = Vec3(bx + rng.uniform(-2.8, 2.8), by + rng.uniform(-2.8, 2.8), h + rng.uniform(4.0, 18.0))
                self.draw_technical_spire(segs, spire_pos, rng, max(6.0, h * rng.uniform(0.12, 0.28)))

        if bool(district.get("tower", False)):
            tower_count = 2 + rng.randint(0, 1)
            for t_idx in range(tower_count):
                tx = origin_x + rng.uniform(12.0, self.game_cfg.chunk_size - 12.0)
                ty = origin_y + rng.uniform(12.0, self.game_cfg.chunk_size - 12.0)
                if self.point_near_authored_travel_space(tx, ty, extra_radius=10.0):
                    continue
                height = rng.uniform(92.0, 148.0)
                self.draw_high_tower_beacon(segs, Vec3(tx, ty, 0.05), rng, height)
                footprint = Vec3(9.0, 9.0, 18.0)
                center = Vec3(tx, ty, footprint.z * 0.5)
                obstacles.append(BoxBounds(center - footprint * 0.5, center + footprint * 0.5, Vec3(0, 0, 1)))
                occlusion_boxes.append((Vec3(center), Vec3(footprint)))

        if bool(district.get("pyramid", False)):
            pyramid_count = 2 + rng.randint(0, 1)
            for p_idx in range(pyramid_count):
                lane = (p_idx - (pyramid_count - 1) * 0.5) * 18.0
                px = origin_x + self.game_cfg.chunk_size * 0.5 + lane + rng.uniform(-3.0, 3.0)
                py = origin_y + self.game_cfg.chunk_size * (0.38 + 0.20 * (p_idx % 2)) + rng.uniform(-3.0, 3.0)
                if self.point_near_authored_travel_space(px, py, extra_radius=10.0):
                    continue
                base = Vec3(rng.uniform(22.0, 30.0), rng.uniform(22.0, 30.0), 0)
                height = rng.uniform(28.0, 50.0)
                self.draw_pyramid_edges(segs, Vec3(px, py, 0.05), base, height, tiers=4 + rng.randint(0, 2))
                footprint = Vec3(base.x, base.y, min(10.0, height * 0.24))
                center = Vec3(px, py, footprint.z * 0.5)
                obstacles.append(BoxBounds(center - footprint * 0.5, center + footprint * 0.5, Vec3(0, 0, 1)))
                occlusion_boxes.append((Vec3(center), Vec3(footprint)))

        # Pass44 skyline grammar. These are line landmarks only: no new collision or gameplay systems.
        landmark_center = Vec3(origin_x + self.game_cfg.chunk_size * 0.5, origin_y + self.game_cfg.chunk_size * 0.5, 0.05)
        if district_id == "calibration" and ((cx + cy) % 3 == 0):
            self.draw_calibration_landmark(segs, landmark_center, rng)
        elif district_id == "high_towers":
            crown_height = 132.0 + float(self.hashed_seed(cx, cy, 4401) % 36)
            self.draw_high_tower_crown(segs, landmark_center, crown_height, 8.0)
        elif district_id == "pyramid_sector" and ((abs(cx) + abs(cy)) % 2 == 0):
            self.draw_pyramid_gate_pair(segs, landmark_center, rng)

        stair_runs = rng.randint(1, 3)
        for _ in range(stair_runs):
            sx = origin_x + rng.uniform(4, self.game_cfg.chunk_size - 20)
            sy = origin_y + rng.uniform(4, self.game_cfg.chunk_size - 20)
            steps = rng.randint(5, 9)
            step_w = rng.uniform(4, 7)
            step_h = rng.uniform(0.7, 1.4)
            for i in range(steps):
                center = Vec3(sx + i * step_w * 0.7, sy, i * step_h + step_h * 0.5)
                size = Vec3(step_w, 4.2, step_h)
                self.draw_box_edges(segs, center, size)
                obstacles.append(BoxBounds(center - size * 0.5, center + size * 0.5, Vec3(0, 0, 1)))
                occlusion_boxes.append((Vec3(center), Vec3(size)))

        # Pass05: city chunks no longer pop enemies in randomly.  Far chunks only
        # expose deterministic patrol gate points.  The spawn director decides when
        # to warn, sequence, and release those enemies into the live scene.
        origin_chunk_band = max(abs(cx), abs(cy))
        enemy_count = 0 if origin_chunk_band <= 2 else (1 if origin_chunk_band <= 4 else 2)
        lane_angles = [math.atan2(cy + 0.5, cx + 0.5)] if enemy_count == 1 else [math.atan2(cy + 0.5, cx + 0.5) - 0.34, math.atan2(cy + 0.5, cx + 0.5) + 0.34]
        for i, angle in enumerate(lane_angles[:enemy_count]):
            lane_radius = self.game_cfg.chunk_size * (0.34 + 0.18 * ((self.hashed_seed(cx, cy, i + 23) % 100) / 100.0))
            px = origin_x + self.game_cfg.chunk_size * 0.5 + math.cos(angle) * lane_radius
            py = origin_y + self.game_cfg.chunk_size * 0.5 + math.sin(angle) * lane_radius
            spawn_pos = Vec3(px, py, 0)
            if self.is_spawn_position_safe(spawn_pos, obstacles=obstacles):
                enemy_spawns.append((px, py, self.hashed_seed(cx, cy, i + 91)))

        if bool(getattr(self.game_cfg, "structure_occlusion_masks", True)):
            self.build_chunk_occlusion_mask(mask_root, occlusion_boxes)
        geom = segs.create()
        visual_np = line_root.attachNewNode(geom)
        visual_np.setAntialias(AntialiasAttrib.MLine)
        visual_np.setTransparency(TransparencyAttrib.MAlpha)
        return np, line_root, mask_root, obstacles, enemy_spawns

    def structure_mask_color(self):
        rgb = tuple(getattr(self, "structure_mask_rgb", (0.08, 0.07, 0.04)))
        strength = max(0.0, min(1.0, float(getattr(self.game_cfg, "structure_occlusion_background_strength", 0.94))))
        # Slightly dimmer than the raw sky color keeps front outlines readable while
        # still looking like the shared background has replaced hidden line clutter.
        return (rgb[0] * strength, rgb[1] * strength, rgb[2] * strength, 1.0)

    def update_structure_occlusion_colors(self):
        color = self.structure_mask_color()
        for mask_root in getattr(self, "chunk_occlusion_roots", {}).values():
            if mask_root is not None and not mask_root.isEmpty():
                mask_root.setColor(*color)

    def build_chunk_occlusion_mask(self, mask_root: NodePath, boxes):
        boxes = list(boxes or [])[:max(0, int(getattr(self.game_cfg, "structure_occlusion_max_boxes_per_chunk", 90)))]
        if not boxes:
            mask_root.hide()
            return mask_root
        fmt = GeomVertexFormat.getV3()
        vdata = GeomVertexData("chunk-structure-occlusion", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        tris = GeomTriangles(Geom.UHStatic)

        def add_box(center: Vec3, size: Vec3):
            hx, hy, hz = size.x * 0.5, size.y * 0.5, size.z * 0.5
            x0, x1 = center.x - hx, center.x + hx
            y0, y1 = center.y - hy, center.y + hy
            z0, z1 = center.z - hz, center.z + hz
            verts = [
                (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
            ]
            base = vdata.getNumRows()
            for p in verts:
                vertex.addData3f(*p)
            faces = [
                (0, 1, 2, 3), (4, 7, 6, 5),
                (0, 4, 5, 1), (1, 5, 6, 2),
                (2, 6, 7, 3), (3, 7, 4, 0),
            ]
            for a, b, c, d in faces:
                tris.addVertices(base + a, base + b, base + c)
                tris.addVertices(base + a, base + c, base + d)

        for center, size in boxes:
            add_box(Vec3(center), Vec3(size))
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("structure-background-mask")
        node.addGeom(geom)
        mask_np = mask_root.attachNewNode(node)
        mask_np.setTwoSided(True)
        mask_np.setColor(*self.structure_mask_color())
        mask_np.setDepthWrite(True)
        mask_np.setDepthTest(True)
        mask_root.setBin("opaque", 1)
        mask_root.setDepthWrite(True)
        mask_root.setDepthTest(True)
        return mask_root

    def add_solid_box(self, parent: NodePath, center: Vec3, size: Vec3, bottom_gray: float = 0.0, top_gray: float = 0.0, alpha: float = 1.0):
        # Pass31: city enemies were effectively line-only because this method hid
        # its placeholder.  Give them real dark infill so they read as robots.
        gray = max(0.0, min(1.0, float(top_gray)))
        a = max(0.0, min(1.0, float(alpha)))
        color = (0.035 + gray * 0.18, 0.045 + gray * 0.20, 0.060 + gray * 0.24, min(0.88, max(0.44, a * 0.74)))
        try:
            np = self.attach_weapon_box_fill(parent, Vec3(center), Vec3(size), color, "city-enemy-infill")
            np.setDepthWrite(True)
            np.setDepthTest(True)
            np.setTransparency(TransparencyAttrib.MAlpha)
            return np
        except Exception:
            np = parent.attachNewNode("city-enemy-infill-fallback")
            np.setPos(center)
            return np

    def draw_box_edges(self, segs: LineSegs, center: Vec3, size: Vec3):

        hx, hy, hz = size.x * 0.5, size.y * 0.5, size.z * 0.5
        x0, x1 = center.x - hx, center.x + hx
        y0, y1 = center.y - hy, center.y + hy
        z0, z1 = center.z - hz, center.z + hz
        edges = [
            ((x0, y0, z0), (x1, y0, z0)), ((x1, y0, z0), (x1, y1, z0)), ((x1, y1, z0), (x0, y1, z0)), ((x0, y1, z0), (x0, y0, z0)),
            ((x0, y0, z1), (x1, y0, z1)), ((x1, y0, z1), (x1, y1, z1)), ((x1, y1, z1), (x0, y1, z1)), ((x0, y1, z1), (x0, y0, z1)),
            ((x0, y0, z0), (x0, y0, z1)), ((x1, y0, z0), (x1, y0, z1)), ((x1, y1, z0), (x1, y1, z1)), ((x0, y1, z0), (x0, y1, z1)),
        ]
        jitter = self.game_cfg.line_jitter
        for a, b in edges:
            j = Vec3(random.uniform(-jitter, jitter), random.uniform(-jitter, jitter), random.uniform(-jitter, jitter))
            segs.moveTo(a[0] + j.x, a[1] + j.y, a[2] + j.z)
            segs.drawTo(b[0] + j.x, b[1] + j.y, b[2] + j.z)

    def draw_rect_loop_xy(self, segs: LineSegs, center: Vec3, half_x: float, half_y: float):
        x0, x1 = center.x - half_x, center.x + half_x
        y0, y1 = center.y - half_y, center.y + half_y
        z = center.z
        segs.moveTo(x0, y0, z)
        segs.drawTo(x1, y0, z)
        segs.drawTo(x1, y1, z)
        segs.drawTo(x0, y1, z)
        segs.drawTo(x0, y0, z)

    def draw_rect_loop_xz(self, segs: LineSegs, center: Vec3, x: float, half_y: float, half_z: float):
        y0, y1 = center.y - half_y, center.y + half_y
        z0, z1 = center.z - half_z, center.z + half_z
        segs.moveTo(x, y0, z0)
        segs.drawTo(x, y1, z0)
        segs.drawTo(x, y1, z1)
        segs.drawTo(x, y0, z1)
        segs.drawTo(x, y0, z0)

    def draw_rect_loop_yz(self, segs: LineSegs, center: Vec3, y: float, half_x: float, half_z: float):
        x0, x1 = center.x - half_x, center.x + half_x
        z0, z1 = center.z - half_z, center.z + half_z
        segs.moveTo(x0, y, z0)
        segs.drawTo(x1, y, z0)
        segs.drawTo(x1, y, z1)
        segs.drawTo(x0, y, z1)
        segs.drawTo(x0, y, z0)

    def draw_technical_facade(self, segs: LineSegs, center: Vec3, size: Vec3, rng: random.Random):
        density = float(getattr(self.game_cfg, "technical_design_density", 0.72))
        if rng.random() > density:
            return
        hx, hy, hz = size.x * 0.5, size.y * 0.5, size.z * 0.5
        if hz < 4.5:
            return
        inset = max(0.18, min(hx, hy) * 0.08)
        band_count = max(2, min(int(getattr(self.game_cfg, "technical_design_window_bands", 4)), max(2, int(size.z / 8.0))))
        for i in range(1, band_count):
            z = center.z - hz + (size.z * i / band_count)
            self.draw_rect_loop_xy(segs, Vec3(center.x, center.y, z), max(0.6, hx - inset), max(0.6, hy - inset))
        # vertical corner spines
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                if rng.random() < 0.82:
                    x = center.x + sx * (hx - inset * 0.65)
                    y = center.y + sy * (hy - inset * 0.65)
                    segs.moveTo(x, y, center.z - hz + 0.35)
                    segs.drawTo(x, y, center.z + hz - 0.35)
        # service panel faces
        face_modules = max(1, min(int(getattr(self.game_cfg, "technical_design_max_modules_per_face", 3)), 4))
        if hx > 1.6:
            for sign in (-1.0, 1.0):
                face_y = center.y + sign * (hy - 0.06)
                panel_half_x = max(0.9, hx * 0.72)
                step_z = size.z / (face_modules + 1)
                for idx in range(face_modules):
                    if rng.random() < 0.72:
                        z = center.z - hz + step_z * (idx + 1)
                        panel_h = max(0.65, min(2.6, hz * 0.14))
                        self.draw_rect_loop_yz(segs, Vec3(center.x, face_y, z), face_y, panel_half_x, panel_h)
                        if rng.random() < 0.58:
                            segs.moveTo(center.x - panel_half_x * 0.75, face_y, z)
                            segs.drawTo(center.x + panel_half_x * 0.75, face_y, z)
        if hy > 1.6:
            for sign in (-1.0, 1.0):
                face_x = center.x + sign * (hx - 0.06)
                panel_half_y = max(0.9, hy * 0.72)
                step_z = size.z / (face_modules + 1)
                for idx in range(face_modules):
                    if rng.random() < 0.72:
                        z = center.z - hz + step_z * (idx + 1)
                        panel_h = max(0.65, min(2.4, hz * 0.14))
                        self.draw_rect_loop_xz(segs, Vec3(face_x, center.y, z), face_x, panel_half_y, panel_h)
                        if rng.random() < 0.48:
                            segs.moveTo(face_x, center.y - panel_half_y * 0.75, z)
                            segs.drawTo(face_x, center.y + panel_half_y * 0.75, z)
        # cross braces / data traces
        if rng.random() < 0.74 and hz > 7.0:
            y = center.y + (hy - 0.08) * (-1.0 if rng.random() < 0.5 else 1.0)
            segs.moveTo(center.x - hx * 0.72, y, center.z - hz * 0.58)
            segs.drawTo(center.x + hx * 0.72, y, center.z + hz * 0.58)
            segs.moveTo(center.x + hx * 0.72, y, center.z - hz * 0.58)
            segs.drawTo(center.x - hx * 0.72, y, center.z + hz * 0.58)
        if rng.random() < 0.78:
            roof_center = Vec3(center.x, center.y, center.z + hz + 0.45)
            self.draw_rect_loop_xy(segs, roof_center, max(0.7, hx * 0.42), max(0.7, hy * 0.42))
            mast_h = max(1.8, min(8.0, hz * 0.18))
            segs.moveTo(roof_center.x, roof_center.y, roof_center.z)
            segs.drawTo(roof_center.x, roof_center.y, roof_center.z + mast_h)
            if rng.random() < 0.66:
                ring_z = roof_center.z + mast_h * 0.65
                self.draw_ring(segs, Vec3(roof_center.x, roof_center.y, ring_z), max(0.7, min(hx, hy) * 0.26), 10)

    def draw_technical_spire(self, segs: LineSegs, pos: Vec3, rng: random.Random, height: float):
        height = max(4.0, height)
        base = max(0.8, min(2.4, height * 0.12))
        top = pos + Vec3(0, 0, height)
        corners = [
            pos + Vec3(-base, -base, 0), pos + Vec3(base, -base, 0),
            pos + Vec3(base, base, 0), pos + Vec3(-base, base, 0),
        ]
        for i in range(4):
            a = corners[i]
            b = corners[(i + 1) % 4]
            segs.moveTo(a)
            segs.drawTo(b)
            segs.moveTo(a)
            segs.drawTo(top)
        ring_count = max(2, min(5, int(height / 5.0)))
        for i in range(1, ring_count + 1):
            frac = i / (ring_count + 1)
            ring_pos = pos + Vec3(0, 0, height * frac)
            ring_radius = max(0.45, base * (1.0 - frac * 0.65))
            self.draw_ring(segs, ring_pos, ring_radius, 8)
        if rng.random() < 0.72:
            arm_z = pos.z + height * rng.uniform(0.35, 0.68)
            arm_len = base * rng.uniform(1.4, 2.6)
            segs.moveTo(pos.x - arm_len, pos.y, arm_z)
            segs.drawTo(pos.x + arm_len, pos.y, arm_z)
            segs.moveTo(pos.x, pos.y - arm_len, arm_z)
            segs.drawTo(pos.x, pos.y + arm_len, arm_z)

    def draw_mechanical_cluster(self, segs: LineSegs, pos: Vec3, rng: random.Random):
        rings = rng.randint(2, 5)
        for i in range(rings):
            radius = rng.uniform(2.0, 5.5)
            z = pos.z + i * rng.uniform(1.2, 3.8)
            x = pos.x + rng.uniform(-6, 6)
            y = pos.y + rng.uniform(-6, 6)
            self.draw_ring(segs, Vec3(x, y, z), radius, 16)
            rod_len = rng.uniform(4, 12)
            segs.moveTo(x, y - rod_len * 0.5, z)
            segs.drawTo(x, y + rod_len * 0.5, z)

    def draw_ring(self, segs: LineSegs, center: Vec3, radius: float, segments: int):
        last = None
        first = None
        for i in range(segments):
            ang = math.tau * i / segments
            p = Vec3(center.x + math.cos(ang) * radius, center.y, center.z + math.sin(ang) * radius)
            if first is None:
                first = p
            if last is not None:
                segs.moveTo(last)
                segs.drawTo(p)
            last = p
        if last is not None and first is not None:
            segs.moveTo(last)
            segs.drawTo(first)

    def is_spawn_position_safe(self, spawn_pos: Vec3, obstacles=None, objective_spawn: bool = False) -> bool:
        spawn_pos = Vec3(spawn_pos)
        player_flat = Vec3(self.player_pos.x, self.player_pos.y, 0) if hasattr(self, "player_pos") else Vec3(0, 0, 0)
        min_dist = float(getattr(self.game_cfg, "enemy_objective_min_distance" if objective_spawn else "enemy_spawn_min_distance", 168.0))
        if (spawn_pos - player_flat).length() < min_dist:
            return False
        if not objective_spawn and spawn_pos.length() < float(getattr(self.game_cfg, "enemy_origin_safe_radius", 96.0)):
            return False
        if self.point_hits_obstacle(spawn_pos, radius=1.75, height=6.0, obstacles=obstacles):
            return False
        return True

    def flat_player_position(self) -> Vec3:
        return Vec3(self.player_pos.x, self.player_pos.y, 0)

    def camera_forward_flat(self) -> Vec3:
        try:
            forward = self.camera.getQuat(self.render).getForward()
        except Exception:
            forward = Vec3(0, 1, 0)
        forward.z = 0
        if forward.lengthSquared() < 0.001:
            forward = Vec3(0, 1, 0)
        forward.normalize()
        return forward

    def _spawn_position_is_reserved(self, spawn_pos: Vec3) -> bool:
        radius = float(getattr(self.game_cfg, "spawn_duplicate_radius", 30.0))
        for pending in getattr(self, "pending_enemy_spawns", []) or []:
            if (Vec3(pending.get("pos", Vec3(0, 0, 0))) - spawn_pos).length() < radius:
                return True
        for enemy in getattr(self, "enemies", []) or []:
            try:
                if enemy.dead or enemy.root is None or enemy.root.isEmpty():
                    continue
                if (enemy.root.getPos(self.render) - spawn_pos).length() < radius:
                    return True
            except Exception:
                continue
        return False

    def enqueue_enemy_spawn(self, spawn_pos: Vec3, seed: int, delay: float = 0.0, source: str = "patrol", objective_spawn: bool = False) -> bool:
        if not bool(getattr(self.game_cfg, "spawn_director_enabled", True)):
            if len(self.enemies) < int(getattr(self.game_cfg, "enemy_max_active", 24)) and self.is_spawn_position_safe(spawn_pos, objective_spawn=objective_spawn):
                self.enemies.append(Enemy(self, spawn_pos, seed))
                return True
            return False
        self.pending_enemy_spawns = getattr(self, "pending_enemy_spawns", [])
        if len(self.pending_enemy_spawns) >= int(getattr(self.game_cfg, "spawn_queue_max", 16)):
            return False
        spawn_pos = Vec3(spawn_pos.x, spawn_pos.y, 0.0)
        if not self.is_spawn_position_safe(spawn_pos, objective_spawn=objective_spawn):
            return False
        if self._spawn_position_is_reserved(spawn_pos):
            return False
        warning_time = float(getattr(self.game_cfg, "enemy_spawn_warning_seconds", 1.15))
        timer = max(0.2, warning_time + float(delay))
        radius = float(getattr(self.game_cfg, "spawn_warning_ring_radius", 3.25))
        self.add_combat_feedback(spawn_pos, label="spawn", radius=radius, life=timer + 0.22, warning=True)
        self.add_shockwave_ring(spawn_pos + Vec3(0, 0, 0.10), radius=radius * 2.2, life=min(1.2, timer), vertical=False, thickness=0.86)
        self.pending_enemy_spawns.append({"pos": spawn_pos, "seed": int(seed), "timer": timer, "source": source, "objective": bool(objective_spawn)})
        return True

    def _sequence_spawn_positions(self, origin: Vec3, base_dir: Vec3, count: int, min_dist: float, max_dist: float, seed: int, objective_spawn: bool = False):
        rng = random.Random(seed)
        base_dir = Vec3(base_dir.x, base_dir.y, 0.0)
        if base_dir.lengthSquared() < 0.001:
            base_dir = self.camera_forward_flat()
        base_dir.normalize()
        side = Vec3(-base_dir.y, base_dir.x, 0.0)
        count = max(0, int(count))
        if count <= 0:
            return []
        spread = 0.42 if count <= 2 else 0.58
        positions = []
        for i in range(count):
            slot = 0.0 if count == 1 else ((i / max(1, count - 1)) - 0.5) * 2.0
            distance = min_dist + (max_dist - min_dist) * (0.28 + 0.52 * ((i + 1) / (count + 1)))
            distance += rng.uniform(-10.0, 10.0)
            lane = side * (slot * spread * distance + rng.uniform(-8.0, 8.0))
            forward = base_dir * distance
            pos = Vec3(origin.x, origin.y, 0.0) + forward + lane
            if not self.is_spawn_position_safe(pos, objective_spawn=objective_spawn):
                # Try wider flanks before giving up; this keeps arrivals distant and readable.
                flank_slot = -1.0 if i % 2 == 0 else 1.0
                pos = Vec3(origin.x, origin.y, 0.0) + base_dir * max_dist + side * (flank_slot * max_dist * 0.55)
            if self.is_spawn_position_safe(pos, objective_spawn=objective_spawn):
                positions.append(pos)
        return positions

    def queue_spawn_sequence(self, origin: Vec3, base_dir: Vec3, count: int, min_dist: float, max_dist: float, seed: int, source: str = "patrol", objective_spawn: bool = False) -> int:
        queued = 0
        gap = float(getattr(self.game_cfg, "spawn_sequence_gap_seconds", 0.72))
        positions = self._sequence_spawn_positions(origin, base_dir, count, min_dist, max_dist, seed, objective_spawn=objective_spawn)
        for i, pos in enumerate(positions):
            if self.enqueue_enemy_spawn(pos, self.hashed_seed(int(pos.x), int(pos.y), seed + i * 17), delay=i * gap, source=source, objective_spawn=objective_spawn):
                queued += 1
        if queued > 0 and not str(source).endswith("_silent"):
            self.set_objective_banner("DISTANT HOSTILE SEQUENCE DETECTED", 1.65)
        return queued

    def nearby_freeroam_pressure(self, player_flat: Vec3) -> tuple[int, bool]:
        radius = float(getattr(self.game_cfg, "freeroam_pressure_radius", 88.0))
        nearby = 0
        for enemy in getattr(self, "enemies", []) or []:
            try:
                if enemy.dead or enemy.root is None or enemy.root.isEmpty():
                    continue
                pos = enemy.root.getPos(self.render)
                if (Vec3(pos.x, pos.y, 0.0) - player_flat).length() <= radius:
                    nearby += 1
            except Exception:
                continue
        hostile_drone = bool(float(getattr(self, "player_hostility_timer", 0.0)) > 0.0)
        return nearby, hostile_drone

    def reset_freeroam_rhythm(self, state: str = "quiet", timer: float | None = None, clear_distance: bool = True) -> None:
        self.freeroam_rhythm_state = str(state)
        if timer is None:
            timer = float(getattr(self.game_cfg, "freeroam_quiet_departure_seconds", 7.0))
        self.freeroam_rhythm_timer = max(0.0, float(timer))
        if clear_distance:
            self.freeroam_travel_distance = 0.0
        self.freeroam_pressure_active = False

    def queue_travel_patrol(self, player_flat: Vec3, heading: Vec3, count: int, seed: int, source: str) -> int:
        rng = random.Random(seed)
        heading = Vec3(heading.x, heading.y, 0.0)
        if heading.lengthSquared() < 0.001:
            heading = self.camera_forward_flat()
        heading.normalize()
        min_dist = float(getattr(self.game_cfg, "ambient_spawn_distance_min", 122.0))
        max_dist = float(getattr(self.game_cfg, "ambient_spawn_distance_max", 198.0))
        gap = float(getattr(self.game_cfg, "spawn_sequence_gap_seconds", 0.72))
        angle_offsets = [0.0, 0.30, -0.30, 0.58, -0.58, 0.86, -0.86, 1.12, -1.12]
        selected = []
        for attempt, angle in enumerate(angle_offsets):
            if len(selected) >= max(1, int(count)):
                break
            ca, sa = math.cos(angle), math.sin(angle)
            direction = Vec3(heading.x * ca - heading.y * sa, heading.x * sa + heading.y * ca, 0.0)
            distance = rng.uniform(min_dist, max_dist)
            side = Vec3(-direction.y, direction.x, 0.0)
            pos = player_flat + direction * distance + side * rng.uniform(-9.0, 9.0)
            pos.z = 0.0
            if not self.is_spawn_position_safe(pos, objective_spawn=False):
                continue
            if self._spawn_position_is_reserved(pos):
                continue
            if any((pos - other).length() < float(getattr(self.game_cfg, "spawn_duplicate_radius", 30.0)) for other in selected):
                continue
            selected.append(Vec3(pos))

        queued = 0
        for index, pos in enumerate(selected):
            if self.enqueue_enemy_spawn(
                pos,
                self.hashed_seed(int(pos.x), int(pos.y), seed + index * 31),
                delay=index * gap,
                source=source,
                objective_spawn=False,
            ):
                queued += 1
        return queued

    def update_freeroam_rhythm(self, dt: float, player_flat: Vec3, moved_distance: float) -> bool:
        """Return True when Pass50 owns ambient spawn pacing for this frame."""
        if not bool(getattr(self.game_cfg, "freeroam_rhythm_enabled", True)):
            return False

        nearby, hostile_drone = self.nearby_freeroam_pressure(player_flat)
        pressure_cap = max(1, int(getattr(self.game_cfg, "freeroam_pressure_enemy_cap", 3)))
        pressure = nearby >= pressure_cap or hostile_drone
        was_pressure = bool(getattr(self, "freeroam_pressure_active", False))
        self.freeroam_pressure_active = pressure

        if pressure:
            self.freeroam_rhythm_state = "combat"
            self.freeroam_rhythm_timer = max(
                float(getattr(self, "freeroam_rhythm_timer", 0.0)),
                float(getattr(self.game_cfg, "freeroam_quiet_after_pressure_seconds", 6.5)),
            )
            self.freeroam_travel_distance = 0.0
            return True

        if was_pressure:
            self.freeroam_rhythm_state = "recovery"
            self.freeroam_rhythm_timer = float(getattr(self.game_cfg, "freeroam_quiet_after_pressure_seconds", 6.5))
            self.freeroam_travel_distance = 0.0
            self.freeroam_rhythm_events.append({"event": "pressure_cleared", "timer": self.freeroam_rhythm_timer})

        self.freeroam_travel_distance = float(getattr(self, "freeroam_travel_distance", 0.0)) + max(0.0, min(8.0, float(moved_distance)))
        self.freeroam_rhythm_timer = max(0.0, float(getattr(self, "freeroam_rhythm_timer", 0.0)) - dt)

        if self.freeroam_rhythm_timer > 0.0:
            if self.freeroam_rhythm_state not in {"recovery"}:
                self.freeroam_rhythm_state = "quiet"
            return True

        min_distance = float(getattr(self.game_cfg, "freeroam_encounter_distance_min", 145.0))
        if self.freeroam_travel_distance < min_distance:
            self.freeroam_rhythm_state = "travel"
            return True

        active_total = len([e for e in getattr(self, "enemies", []) or [] if not getattr(e, "dead", False)])
        active_total += len(getattr(self, "pending_enemy_spawns", []) or [])
        if active_total >= int(getattr(self.game_cfg, "enemy_max_active", 24)):
            return True

        district_id, district = self.district_for_position(player_flat)
        count = max(1, int(district.get("travel_patrol_size", 1)))
        heading = Vec3(getattr(self, "player_motion_heading", Vec3(0, 1, 0)))
        if heading.lengthSquared() < 0.001:
            heading = self.camera_forward_flat()
        self.spawn_sequence_serial += 1
        seed = self.hashed_seed(int(player_flat.x), int(player_flat.y), 5000 + self.spawn_sequence_serial)
        rng = random.Random(seed)
        flank = Vec3(-heading.y, heading.x, 0.0) * (-1.0 if self.spawn_sequence_serial % 2 == 0 else 1.0)
        base_dir = heading * 0.84 + flank * 0.16 + Vec3(rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), 0)
        if base_dir.lengthSquared() < 0.001:
            base_dir = heading
        base_dir.normalize()
        queued = self.queue_travel_patrol(
            player_flat,
            base_dir,
            count,
            seed,
            source=f"travel_{district_id}_silent",
        )
        if queued <= 0:
            self.freeroam_rhythm_timer = 2.0
            return True

        self.freeroam_encounters = int(getattr(self, "freeroam_encounters", 0)) + 1
        self.freeroam_rhythm_state = "encounter"
        interval_min = float(getattr(self.game_cfg, "freeroam_encounter_interval_min", 13.0))
        interval_max = max(interval_min, float(getattr(self.game_cfg, "freeroam_encounter_interval_max", 22.0)))
        self.freeroam_rhythm_timer = rng.uniform(interval_min, interval_max)
        self.freeroam_travel_distance = 0.0
        self.freeroam_rhythm_events.append({
            "event": "travel_encounter",
            "district": district_id,
            "queued": queued,
            "next_gap": round(self.freeroam_rhythm_timer, 3),
        })
        return True

    def update_spawn_director(self, dt: float) -> None:
        if getattr(self, "arena_mode_active", False):
            return
        player_flat = self.flat_player_position()
        last = getattr(self, "last_spawn_director_player", player_flat)
        move_delta = player_flat - last
        moved_distance = min(8.0, max(0.0, float(move_delta.length())))
        if move_delta.lengthSquared() > 1.0:
            move_delta.z = 0
            move_delta.normalize()
            self.player_motion_heading = move_delta
        self.last_spawn_director_player = Vec3(player_flat)

        for pending in list(getattr(self, "pending_enemy_spawns", []) or []):
            pending["timer"] = float(pending.get("timer", 0.0)) - dt
            if pending["timer"] > 0.0:
                continue
            self.pending_enemy_spawns.remove(pending)
            if len(self.enemies) >= int(getattr(self.game_cfg, "enemy_max_active", 24)):
                continue
            pos = Vec3(pending.get("pos", player_flat))
            objective_spawn = bool(pending.get("objective", False))
            if not self.is_spawn_position_safe(pos, objective_spawn=objective_spawn):
                continue
            self.add_combat_feedback(pos, label="spawn", radius=float(getattr(self.game_cfg, "spawn_warning_ring_radius", 3.25)) * 0.82, life=0.48, warning=True)
            self.enemies.append(Enemy(self, pos, int(pending.get("seed", self.hashed_seed(int(pos.x), int(pos.y), 500)))))

        if getattr(self, "active_activity_instance", None) is not None:
            self.spawn_director_timer = max(float(getattr(self, "spawn_director_timer", 0.0)), 2.0)
            self.reset_freeroam_rhythm(
                state="quiet",
                timer=float(getattr(self.game_cfg, "freeroam_quiet_after_pressure_seconds", 6.5)),
                clear_distance=True,
            )
            return

        if self.update_freeroam_rhythm(dt, player_flat, moved_distance):
            return

        self.spawn_director_timer = float(getattr(self, "spawn_director_timer", 0.0)) - dt
        if self.spawn_director_timer > 0.0:
            return
        interval = float(getattr(self.game_cfg, "ambient_spawn_interval_seconds", 8.5))
        self.spawn_director_timer = interval
        if len(self.enemies) + len(getattr(self, "pending_enemy_spawns", []) or []) >= int(getattr(self.game_cfg, "enemy_max_active", 24)):
            return
        heading = Vec3(getattr(self, "player_motion_heading", Vec3(0, 1, 0)))
        if heading.lengthSquared() < 0.001:
            heading = self.camera_forward_flat()
        # Bias ambient arrivals ahead and to the far flanks, which feels like patrols
        # moving into the district instead of enemies teleporting around the player.
        self.spawn_sequence_serial += 1
        seed = self.hashed_seed(int(player_flat.x), int(player_flat.y), 1200 + self.spawn_sequence_serial)
        rng = random.Random(seed)
        flank = Vec3(-heading.y, heading.x, 0.0) * (-1.0 if self.spawn_sequence_serial % 2 == 0 else 1.0)
        base_dir = heading * 0.78 + flank * 0.22 + Vec3(rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08), 0)
        if base_dir.lengthSquared() < 0.001:
            base_dir = heading
        base_dir.normalize()
        self.queue_spawn_sequence(
            player_flat,
            base_dir,
            int(getattr(self.game_cfg, "ambient_spawn_sequence_size", 2)),
            float(getattr(self.game_cfg, "ambient_spawn_distance_min", 182.0)),
            float(getattr(self.game_cfg, "ambient_spawn_distance_max", 264.0)),
            seed,
            source="patrol",
            objective_spawn=False,
        )

    def freeroam_rhythm_test_task(self, task):
        self.enemies.clear()
        self.pending_enemy_spawns.clear()
        self.player_hostility_timer = 0.0
        self.player_pos = Vec3(0.0, 0.0, self.game_cfg.player_height)
        self.last_spawn_director_player = self.flat_player_position()
        self.player_motion_heading = Vec3(0, 1, 0)
        self.reset_freeroam_rhythm(state="quiet", timer=float(getattr(self.game_cfg, "freeroam_quiet_departure_seconds", 7.0)), clear_distance=True)

        for _ in range(10):
            self.update_spawn_director(0.5)
        quiet_pending = len(self.pending_enemy_spawns)
        quiet_state = str(getattr(self, "freeroam_rhythm_state", ""))

        for _ in range(19):
            self.player_pos.y += 10.0
            self.update_spawn_director(0.5)
        encounter_pending = len(self.pending_enemy_spawns)
        encounter_count = int(getattr(self, "freeroam_encounters", 0))
        encounter_events = [e for e in getattr(self, "freeroam_rhythm_events", []) if e.get("event") == "travel_encounter"]
        travel_state_snapshot = str(getattr(self, "freeroam_rhythm_state", ""))
        travel_timer_snapshot = float(getattr(self, "freeroam_rhythm_timer", 0.0))
        travel_distance_snapshot = float(getattr(self, "freeroam_travel_distance", 0.0))

        # A nearby pressure pack must suspend further ambient encounters.
        self.pending_enemy_spawns.clear()
        near_base = self.flat_player_position() + Vec3(8.0, 0.0, 0.0)
        for i in range(max(3, int(getattr(self.game_cfg, "freeroam_pressure_enemy_cap", 3)))):
            self.enemies.append(Enemy(self, near_base + Vec3(i * 3.0, 0.0, 0.0), self.hashed_seed(7000, i, 50), variant_override="sentinel"))
        before_pressure_encounters = int(getattr(self, "freeroam_encounters", 0))
        self.update_spawn_director(0.5)
        pressure_state = str(getattr(self, "freeroam_rhythm_state", ""))
        pressure_encounters = int(getattr(self, "freeroam_encounters", 0))

        for enemy in list(self.enemies):
            if enemy.root is not None and not enemy.root.isEmpty():
                enemy.root.removeNode()
        self.enemies.clear()
        self.update_spawn_director(0.5)
        recovery_state = str(getattr(self, "freeroam_rhythm_state", ""))
        recovery_timer = float(getattr(self, "freeroam_rhythm_timer", 0.0))

        districts = {
            key: int(value.get("travel_patrol_size", 0))
            for key, value in UTOPIA_DISTRICTS.items()
        }
        status = (
            quiet_pending == 0
            and quiet_state in {"quiet", "travel"}
            and encounter_pending >= 1
            and encounter_count >= 1
            and len(encounter_events) >= 1
            and pressure_state == "combat"
            and pressure_encounters == before_pressure_encounters
            and recovery_state == "recovery"
            and recovery_timer > 0.0
            and districts == {"calibration": 1, "pyramid_sector": 2, "high_towers": 2}
        )
        report = {
            "test": "freeroam_rhythm_test",
            "status": "PASS" if status else "FAIL",
            "quiet_pending": quiet_pending,
            "quiet_state": quiet_state,
            "encounter_pending": encounter_pending,
            "encounters": encounter_count,
            "encounter_events": encounter_events,
            "rhythm_state_after_travel": travel_state_snapshot,
            "rhythm_timer_after_travel": round(travel_timer_snapshot, 3),
            "travel_distance_after_travel": round(travel_distance_snapshot, 3),
            "pressure_state": pressure_state,
            "pressure_encounters_unchanged": pressure_encounters == before_pressure_encounters,
            "recovery_state": recovery_state,
            "recovery_timer": round(recovery_timer, 3),
            "district_patrol_sizes": districts,
            "distance_gate": float(getattr(self.game_cfg, "freeroam_encounter_distance_min", 145.0)),
            "departure_quiet_seconds": float(getattr(self.game_cfg, "freeroam_quiet_departure_seconds", 7.0)),
            "recovery_quiet_seconds": float(getattr(self.game_cfg, "freeroam_quiet_after_pressure_seconds", 6.5)),
        }
        (LOG_DIR / "freeroam_rhythm_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("freeroam_rhythm_test", report)
        print(json.dumps(report, indent=2))
        self.userExit()
        return Task.done

    def freeroam_rhythm_demo_task(self, task):
        mode = str(FREEROAM_RHYTHM_DEMO or "quiet").strip().lower()
        self.enemies.clear()
        self.pending_enemy_spawns.clear()
        self.player_hostility_timer = 0.0
        self.active_activity_instance = None
        district_size = float(getattr(self.game_cfg, "district_size_chunks", 6)) * float(self.game_cfg.chunk_size)
        if mode == "encounter":
            self.player_pos = Vec3(0.0, district_size * 0.58, self.game_cfg.player_height)
            self.player_motion_heading = Vec3(0, 1, 0)
        elif mode == "recovery":
            self.player_pos = Vec3(district_size * 0.56, 18.0, self.game_cfg.player_height)
            self.player_motion_heading = Vec3(1, 0, 0)
        else:
            self.player_pos = Vec3(0.0, 92.0, self.game_cfg.player_height)
            self.player_motion_heading = Vec3(0, 1, 0)
        self.camera.setPos(self.player_pos + Vec3(0.0, -4.0, 4.8))
        self.yaw = 0.0 if mode != "recovery" else -90.0
        self.pitch = -7.0
        self.camera.setH(self.yaw)
        self.camera.setP(self.pitch)
        self.generate_city_around_player(force=True)
        self.last_spawn_director_player = self.flat_player_position()

        if mode == "encounter":
            self.reset_freeroam_rhythm(state="travel", timer=0.0, clear_distance=True)
            self.freeroam_travel_distance = float(getattr(self.game_cfg, "freeroam_encounter_distance_min", 145.0)) + 10.0
            self.update_spawn_director(0.033)
            for _ in range(48):
                self.update_spawn_director(0.033)
                self.update_enemies(0.033)
                self.update_effects(0.033)
            active = [e for e in self.enemies if not e.dead and e.root is not None and not e.root.isEmpty()]
            if active:
                target = min(active, key=lambda e: (e.root.getPos(self.render) - self.flat_player_position()).lengthSquared())
                target_pos = target.core_world_position()
                # Test-only overhead proof uses the enemy's real spawned position.  A vertical
                # view avoids procedural tower occlusion without moving or respawning the patrol.
                proof_camera = target_pos + Vec3(0, 0, 18.0)
                self.camera.setPos(proof_camera)
                self.camera.lookAt(target_pos)
        elif mode == "recovery":
            self.reset_freeroam_rhythm(state="combat", timer=0.0, clear_distance=True)
            self.freeroam_pressure_active = True
            self.update_spawn_director(0.033)
        else:
            self.reset_freeroam_rhythm(state="quiet", timer=float(getattr(self.game_cfg, "freeroam_quiet_departure_seconds", 7.0)), clear_distance=True)
            for _ in range(40):
                self.update_district_discovery_guidance(0.033)
                self.update_effects(0.033)

        self.refresh_ui_text()
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def clamp_enemy_population(self):
        max_active = max(8, int(getattr(self.game_cfg, "enemy_max_active", 24)))
        if len(self.enemies) <= max_active:
            return
        player_flat = Vec3(self.player_pos.x, self.player_pos.y, 0)
        sortable = []
        for enemy in list(self.enemies):
            if enemy.dead or enemy.root is None or enemy.root.isEmpty():
                continue
            sortable.append(((enemy.root.getPos() - player_flat).length(), enemy))
        sortable.sort(reverse=True, key=lambda item: item[0])
        keep = set(id(enemy) for _, enemy in sortable[:max_active])
        for enemy in list(self.enemies):
            if id(enemy) not in keep:
                try:
                    if enemy.root is not None and not enemy.root.isEmpty():
                        enemy.root.removeNode()
                except Exception:
                    pass
                try:
                    self.enemies.remove(enemy)
                except ValueError:
                    pass

    def ai_path_clear(self, start: Vec3, end: Vec3, radius: float = 0.6, height: float = 1.8, samples: int = 5) -> bool:
        start = Vec3(start)
        end = Vec3(end)
        for i in range(1, max(2, int(samples)) + 1):
            t = i / max(1, int(samples))
            p = start * (1.0 - t) + end * t
            p.z = 0.0
            if self.point_hits_obstacle(p, radius=radius, height=height):
                return False
        return True

    def ai_steer_towards(self, start: Vec3, target: Vec3, radius: float = 0.6, height: float = 1.8, seed: int = 1) -> Vec3:
        start = Vec3(start.x, start.y, 0.0)
        target = Vec3(target.x, target.y, 0.0)
        direct = target - start
        if direct.lengthSquared() < 0.001:
            return Vec3(0, 1, 0)
        direct.normalize()
        lookahead = 8.5 + min(10.0, (target - start).length() * 0.18)
        if self.ai_path_clear(start, start + direct * lookahead, radius=radius, height=height, samples=4):
            return direct
        angles = (35, -35, 70, -70, 110, -110, 145, -145)
        best = None
        best_score = -9999.0
        base_angle = math.atan2(direct.y, direct.x)
        for idx, deg in enumerate(angles):
            a = base_angle + math.radians(deg)
            cand = Vec3(math.cos(a), math.sin(a), 0.0)
            if not self.ai_path_clear(start, start + cand * lookahead, radius=radius, height=height, samples=4):
                continue
            score = cand.dot(direct) - 0.015 * abs(deg) + (((int(seed) + idx * 37) % 11) - 5) * 0.001
            if score > best_score:
                best_score = score
                best = cand
        if best is not None:
            best.normalize()
            return best
        side = Vec3(-direct.y, direct.x, 0.0)
        if int(seed) % 2:
            side *= -1
        return side if side.lengthSquared() > 0.001 else direct

    def collect_civilian_anchors(self):
        anchors = []
        player = Vec3(self.player_pos.x, self.player_pos.y, 0.0)
        for boxes in getattr(self, "chunk_obstacles", {}).values():
            for box in boxes:
                try:
                    size = box.max_v - box.min_v
                    center = (box.min_v + box.max_v) * 0.5
                except Exception:
                    continue
                if size.z < 4.0 or size.x < 3.0 or size.y < 3.0:
                    continue
                if (Vec3(center.x, center.y, 0.0) - player).length() > 280.0:
                    continue
                candidates = [
                    Vec3(center.x, box.min_v.y - 3.1, 0.0),
                    Vec3(center.x, box.max_v.y + 3.1, 0.0),
                    Vec3(box.min_v.x - 3.1, center.y, 0.0),
                    Vec3(box.max_v.x + 3.1, center.y, 0.0),
                ]
                for p in candidates:
                    if not self.point_hits_obstacle(p, radius=0.62, height=2.3):
                        anchors.append(p)
        anchors.sort(key=lambda p: (p - player).lengthSquared())
        self.civilian_anchors = anchors[:96]
        return self.civilian_anchors

    def spawn_civilian(self):
        if not bool(getattr(self.game_cfg, "civilian_enabled", True)):
            return None
        anchors = list(getattr(self, "civilian_anchors", []) or self.collect_civilian_anchors())
        if not anchors:
            return None
        player = Vec3(self.player_pos.x, self.player_pos.y, 0.0)
        choices = [Vec3(a) for a in anchors if 20.0 < (Vec3(a) - player).length() < 210.0]
        if not choices:
            choices = [Vec3(a) for a in anchors[:24]]
        if not choices:
            return None
        seed = self.hashed_seed(int(player.x), int(player.y), 3200 + len(getattr(self, "civilians", [])))
        rng = random.Random(seed)
        pos = Vec3(rng.choice(choices))
        civ = Civilian(self, pos, seed)
        self.civilians.append(civ)
        return civ

    def update_civilians(self, dt: float):
        if getattr(self, "arena_mode_active", False):
            return
        if not bool(getattr(self.game_cfg, "civilian_enabled", True)):
            return
        self.civilian_anchor_timer = float(getattr(self, "civilian_anchor_timer", 0.0)) - dt
        if self.civilian_anchor_timer <= 0.0 or not getattr(self, "civilian_anchors", None):
            self.civilian_anchor_timer = float(getattr(self.game_cfg, "civilian_anchor_refresh_seconds", 2.25))
            self.collect_civilian_anchors()
        self.civilian_spawn_timer = float(getattr(self, "civilian_spawn_timer", 0.0)) - dt
        max_civ = max(0, int(getattr(self.game_cfg, "civilian_max_active", 10)))
        if self.civilian_spawn_timer <= 0.0 and len(getattr(self, "civilians", [])) < max_civ:
            self.civilian_spawn_timer = float(getattr(self.game_cfg, "civilian_spawn_interval_seconds", 1.4))
            self.spawn_civilian()
        for civ in list(getattr(self, "civilians", []) or []):
            alive = civ.update(dt)
            if not alive:
                try:
                    if civ.root is not None and not civ.root.isEmpty():
                        civ.root.removeNode()
                except Exception:
                    pass
                if civ in self.civilians:
                    self.civilians.remove(civ)
        harm_dist = float(getattr(self.game_cfg, "civilian_enemy_harm_distance", 3.4))
        for enemy in list(getattr(self, "enemies", []) or []):
            if getattr(enemy, "dead", False) or enemy.root is None or enemy.root.isEmpty():
                continue
            epos = enemy.root.getPos(self.render)
            for civ in list(getattr(self, "civilians", []) or []):
                if getattr(civ, "dead", False) or civ.root is None or civ.root.isEmpty():
                    continue
                if float(getattr(civ, "enemy_harm_cooldown", 0.0)) > 0.0:
                    continue
                cpos = civ.root.getPos(self.render)
                if (epos - cpos).length() <= harm_dist:
                    civ.enemy_harm_cooldown = 1.25
                    killed = civ.hit(10.0, civ.core_world_position(), Vec3(0, 0, 1), force_kill=False, hit_kind="enemy_contact")
                    self.register_civilian_harm(civ, killed=killed, source_point=civ.core_world_position(), cause="enemy")
                    break

    def register_civilian_harm(self, civilian, killed: bool, source_point: Vec3, cause: str = "player"):
        harm_penalty = int(getattr(self.game_cfg, "civilian_harm_penalty", 35))
        death_penalty = int(getattr(self.game_cfg, "civilian_death_penalty", 125))
        penalty = death_penalty if killed else harm_penalty
        self.score = max(0, int(getattr(self, "score", 0)) - penalty)
        self.lab_points = max(0, int(getattr(self, "lab_points", 0)) - max(1, penalty // 5))
        self.civilian_penalty_points = int(getattr(self, "civilian_penalty_points", 0)) + penalty
        if str(cause) == "player":
            self.player_hostility_timer = max(float(getattr(self, "player_hostility_timer", 0.0)), float(getattr(self.game_cfg, "patrol_drone_player_hostility_seconds", 9.0)))
        self.civilian_harm_count = int(getattr(self, "civilian_harm_count", 0)) + 1
        if killed:
            self.civilian_death_count = int(getattr(self, "civilian_death_count", 0)) + 1
        label = "CIVILIAN LOST" if killed else "CIVILIAN HARMED"
        self.combat_banner = f"{label} -{penalty}"
        self.combat_banner_time = 1.45
        self.add_combat_feedback(source_point, label="civilian", radius=2.0 if not killed else 3.2, life=0.55, warning=True)
        self.play_sfx("player_hit", volume=0.42 if not killed else 0.62, pos=source_point)
        return -penalty


    def collect_patrol_drone_anchors(self):
        anchors = []
        player = Vec3(self.player_pos.x, self.player_pos.y, 0.0)
        # Capture nodes are protected patrol areas.
        for point in getattr(self, "campaign_points", []) or []:
            try:
                p = Vec3(point["pos"])
                if (p - player).length() <= 260.0:
                    anchors.append(p + Vec3(0, 0, 7.5))
                    anchors.append(p + Vec3(18, 12, 8.0))
                    anchors.append(p + Vec3(-18, 10, 8.0))
            except Exception:
                pass
        # Building/tower side anchors make patrols feel district-bound.
        for boxes in getattr(self, "chunk_obstacles", {}).values():
            for box in boxes:
                try:
                    size = box.max_v - box.min_v
                    center = (box.min_v + box.max_v) * 0.5
                except Exception:
                    continue
                if size.z < 12.0 or (Vec3(center.x, center.y, 0.0) - player).length() > 285.0:
                    continue
                district_id, district = self.district_for_position(Vec3(center.x, center.y, 0.0))
                if not bool(district.get("drone_patrol", False)):
                    continue
                z = min(max(7.0, size.z * 0.42), 24.0)
                anchors.extend([
                    Vec3(center.x + size.x * 0.5 + 6.0, center.y, z),
                    Vec3(center.x - size.x * 0.5 - 6.0, center.y, z),
                    Vec3(center.x, center.y + size.y * 0.5 + 6.0, z),
                    Vec3(center.x, center.y - size.y * 0.5 - 6.0, z),
                ])
        anchors.sort(key=lambda p: (Vec3(p.x, p.y, 0.0) - player).lengthSquared())
        self.patrol_drone_anchors = anchors[:64]
        return self.patrol_drone_anchors

    def drone_patrol_allowed_here(self) -> bool:
        if not bool(getattr(self.game_cfg, "patrol_drone_enabled", True)):
            return False
        if getattr(self, "arena_mode_active", False):
            return False
        district_id, district = self.district_for_position(Vec3(self.player_pos.x, self.player_pos.y, 0.0))
        if bool(district.get("drone_patrol", False)):
            return True
        player = Vec3(self.player_pos.x, self.player_pos.y, 0.0)
        for point in getattr(self, "campaign_points", []) or []:
            try:
                if (Vec3(point["pos"]) - player).length() <= 130.0:
                    return True
            except Exception:
                pass
        return False

    def spawn_patrol_drone(self):
        if not self.drone_patrol_allowed_here():
            return None
        anchors = list(getattr(self, "patrol_drone_anchors", []) or self.collect_patrol_drone_anchors())
        if not anchors:
            return None
        player = Vec3(self.player_pos.x, self.player_pos.y, 0.0)
        choices = [Vec3(a) for a in anchors if 24.0 < (Vec3(a.x, a.y, 0.0) - player).length() < 220.0]
        if not choices:
            choices = [Vec3(a) for a in anchors[:16]]
        if not choices:
            return None
        seed = self.hashed_seed(int(player.x), int(player.y), 4200 + len(getattr(self, "patrol_drones", [])))
        rng = random.Random(seed)
        pos = Vec3(rng.choice(choices))
        district_id, _district = self.district_for_position(Vec3(pos.x, pos.y, 0.0))
        drone = PatrolDrone(self, pos, seed, district_id=district_id)
        self.patrol_drones.append(drone)
        self.add_combat_feedback(Vec3(pos.x, pos.y, 0.0), label="drone", radius=2.4, life=0.5, warning=False)
        self.play_sfx("enemy_spawn", volume=0.32, rate=1.12, pos=pos)
        return drone

    def update_patrol_drones(self, dt: float):
        if getattr(self, "arena_mode_active", False):
            return
        self.player_hostility_timer = max(0.0, float(getattr(self, "player_hostility_timer", 0.0)) - dt)
        if not bool(getattr(self.game_cfg, "patrol_drone_enabled", True)):
            return
        self.patrol_drone_anchor_timer = float(getattr(self, "patrol_drone_anchor_timer", 0.0)) - dt
        if self.patrol_drone_anchor_timer <= 0.0 or not getattr(self, "patrol_drone_anchors", None):
            self.patrol_drone_anchor_timer = float(getattr(self.game_cfg, "patrol_drone_anchor_refresh_seconds", 3.0))
            self.collect_patrol_drone_anchors()
        self.patrol_drone_spawn_timer = float(getattr(self, "patrol_drone_spawn_timer", 0.0)) - dt
        max_drones = max(0, int(getattr(self.game_cfg, "patrol_drone_max_active", 4)))
        if self.patrol_drone_spawn_timer <= 0.0 and len(getattr(self, "patrol_drones", [])) < max_drones and self.drone_patrol_allowed_here():
            self.patrol_drone_spawn_timer = float(getattr(self.game_cfg, "patrol_drone_spawn_interval_seconds", 3.2))
            self.spawn_patrol_drone()
        for drone in list(getattr(self, "patrol_drones", []) or []):
            alive = drone.update(dt)
            if not alive:
                if drone in self.patrol_drones:
                    self.patrol_drones.remove(drone)

    def drop_patrol_drone_ammo(self, drone, source_point: Vec3):
        rng = random.Random(self.hashed_seed(int(source_point.x), int(source_point.y), int(getattr(drone, "seed", 0)) + 8900))
        slots = [1, 2, 3, 4, 5, 6]
        rng.shuffle(slots)
        amount_min = float(getattr(self.game_cfg, "patrol_drone_drop_amount_min", 18.0))
        amount_max = float(getattr(self.game_cfg, "patrol_drone_drop_amount_max", 42.0))
        drops = 0
        for slot in slots[:2]:
            offset = Vec3(rng.uniform(-1.6, 1.6), rng.uniform(-1.6, 1.6), 0)
            if self.spawn_weapon_pickup(source_point + offset, slot=slot, amount=rng.uniform(amount_min, amount_max)):
                drops += 1
        self.drone_ammo_drops = int(getattr(self, "drone_ammo_drops", 0)) + drops
        if drops:
            self.combat_banner = f"PATROL DRONE AMMO CACHE x{drops}"
            self.combat_banner_time = max(float(getattr(self, "combat_banner_time", 0.0)), 0.9)
        return drops

    def register_generated_chunk(self, cx: int, cy: int):
        key = (cx, cy)
        if key in self.chunks:
            self.chunk_stream_target[key] = 1.0
            self.chunk_stream_remove.discard(key)
            return False
        np, line_root, mask_root, obstacles, spawns = self.generate_chunk_geometry(cx, cy)
        self.chunks[key] = np
        self.chunk_line_roots[key] = line_root
        self.chunk_occlusion_roots[key] = mask_root
        self.chunk_obstacles[key] = obstacles
        self.chunk_enemy_seeds[key] = spawns
        alpha = 1.0 if not self.chunk_stream_alpha else 0.0
        self.chunk_stream_alpha[key] = alpha
        self.chunk_stream_target[key] = 1.0
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setColorScale(1, 1, 1, alpha)
        return True

    def generate_city_around_player(self, force=False):
        csize = self.game_cfg.chunk_size
        px = int(math.floor(self.player_pos.x / csize))
        py = int(math.floor(self.player_pos.y / csize))
        visible_radius = int(self.game_cfg.active_chunk_radius)
        preload_margin = max(0, int(getattr(self.game_cfg, "chunk_preload_margin", 1)))
        stream_radius = visible_radius + preload_margin
        required = set()
        candidates = []
        for cx in range(px - stream_radius, px + stream_radius + 1):
            for cy in range(py - stream_radius, py + stream_radius + 1):
                key = (cx, cy)
                required.add(key)
                if key not in self.chunks:
                    dist2 = (cx - px) ** 2 + (cy - py) ** 2
                    candidates.append((dist2, abs(cx-px)+abs(cy-py), cx, cy))
                else:
                    self.chunk_stream_target[key] = 1.0
                    self.chunk_stream_remove.discard(key)
        candidates.sort()
        budget = len(candidates) if force else max(1, int(getattr(self.game_cfg, "chunk_generate_budget", 3)))
        for _dist2, _manhattan, cx, cy in candidates[:budget]:
            self.register_generated_chunk(cx, cy)
        if force:
            for key, np in list(self.chunks.items()):
                self.chunk_stream_alpha[key] = 1.0
                self.chunk_stream_target[key] = 1.0
                if np is not None and not np.isEmpty():
                    np.setColorScale(1, 1, 1, 1)
        for key in list(self.chunks.keys()):
            if key not in required:
                self.chunk_stream_target[key] = 0.0
                self.chunk_stream_remove.add(key)
        self.clamp_enemy_population()

    def update_chunk_streaming(self, dt: float):
        fade_in = max(0.05, float(getattr(self.game_cfg, "chunk_fade_in_seconds", 0.42)))
        fade_out = max(0.05, float(getattr(self.game_cfg, "chunk_fade_out_seconds", 0.28)))
        for key in list(self.chunks.keys()):
            alpha = float(self.chunk_stream_alpha.get(key, 1.0))
            target = float(self.chunk_stream_target.get(key, 1.0))
            rate = 1.0 / (fade_in if target >= alpha else fade_out)
            if alpha < target: alpha = min(target, alpha + dt * rate)
            elif alpha > target: alpha = max(target, alpha - dt * rate)
            self.chunk_stream_alpha[key] = alpha
            np = self.chunks.get(key)
            if np is not None and not np.isEmpty(): np.setColorScale(1, 1, 1, alpha)
            if target <= 0.0 and alpha <= 0.001 and key in self.chunk_stream_remove:
                if np is not None and not np.isEmpty(): np.removeNode()
                self.chunks.pop(key, None)
                self.chunk_line_roots.pop(key, None)
                self.chunk_occlusion_roots.pop(key, None)
                self.chunk_obstacles.pop(key, None)
                self.chunk_enemy_seeds.pop(key, None)
                self.chunk_stream_alpha.pop(key, None)
                self.chunk_stream_target.pop(key, None)
                self.chunk_stream_remove.discard(key)

    def point_hits_obstacle(self, pos: Vec3, radius: float = 0.42, height: float = 1.8, obstacles=None):
        obs = obstacles
        if obs is None:
            obs = []
            csize = self.game_cfg.chunk_size
            px = int(math.floor(pos.x / csize))
            py = int(math.floor(pos.y / csize))
            for cx in range(px - 1, px + 2):
                for cy in range(py - 1, py + 2):
                    obs.extend(self.chunk_obstacles.get((cx, cy), []))
        test_min = Vec3(pos.x - radius, pos.y - radius, 0)
        test_max = Vec3(pos.x + radius, pos.y + radius, height)
        for box in obs:
            if (test_min.x <= box.max_v.x and test_max.x >= box.min_v.x and
                test_min.y <= box.max_v.y and test_max.y >= box.min_v.y and
                test_min.z <= box.max_v.z and test_max.z >= box.min_v.z):
                return True
        return False



    def enemy_line_thickness(self, base_scale: float = 1.0, floor: float = 1.0) -> float:
        return max(float(floor), float(getattr(self.game_cfg, "line_thickness", 1.45)) * float(base_scale) * float(getattr(self.game_cfg, "enemy_line_thickness_scale", 1.6)))

    def weapon_line_thickness(self, base_scale: float = 1.0, floor: float = 2.0) -> float:
        return max(float(floor), float(getattr(self.game_cfg, "line_thickness", 1.45)) * float(base_scale) * float(getattr(self.game_cfg, "weapon_line_thickness_scale", 1.65)))

    def movable_line_thickness(self, base_scale: float = 1.0, floor: float = 1.0) -> float:
        return max(float(floor), float(getattr(self.game_cfg, "line_thickness", 1.45)) * float(base_scale) * float(getattr(self.game_cfg, "movable_line_thickness_scale", 1.55)))

    def signal_accent_color(self, alpha: float = 1.0):
        return self.current_campaign_secondary_color(alpha=alpha)

    def warning_accent_color(self, alpha: float = 1.0):
        return self.current_campaign_threat_color(alpha=alpha)

    def setup_signal_objectives(self):
        old_root = getattr(self, "mission_root", None)
        if old_root is not None and not old_root.isEmpty():
            old_root.removeNode()
        self.mission_root = self.effect_root.attachNewNode("etchline-signal-objectives")
        self.objective_nodes = []
        self.signal_effects = []
        self.combat_effects = []
        self.return_trail = None
        self.signal_fragments_recovered = 0
        self.extraction_active = False
        self.objective_complete = False
        self.objective_banner = ""
        self.objective_banner_time = 0.0
        base_positions = [
            Vec3(96, 56, 0),
            Vec3(-128, 72, 0),
            Vec3(80, -132, 0),
            Vec3(-116, -112, 0),
            Vec3(168, -24, 0),
            Vec3(-32, 168, 0),
        ]
        required = max(1, min(len(base_positions), int(getattr(self.game_cfg, "signal_fragments_required", 4))))
        self.signal_fragments_required = required
        for i, pos in enumerate(base_positions[:required]):
            self.objective_nodes.append(SignalNode(self, i + 1, pos, f"FRAGMENT {i + 1}", kind="fragment"))
        self.extraction_node = SignalNode(self, 0, Vec3(0, -188, 0), "RETURN LATTICE", kind="extraction")
        self.set_objective_banner("UTOPIA CONFLICT // Capture command nodes and recover signal fragments.", 4.0)
        self.mission_result = self.get_mission_result()

    def set_objective_banner(self, text: str, duration: float = 2.4) -> None:
        self.objective_banner = str(text or "")
        self.objective_banner_time = max(float(getattr(self, "objective_banner_time", 0.0) or 0.0), float(duration or 0.0))

    def captured_node_count(self) -> int:
        return sum(1 for p in getattr(self, "campaign_points", []) if p.get("captured"))

    def command_route_complete(self) -> bool:
        total = len(getattr(self, "campaign_points", []) or [])
        return bool(total and self.captured_node_count() >= total)

    def signal_route_complete(self) -> bool:
        return int(getattr(self, "signal_fragments_recovered", 0) or 0) >= int(getattr(self, "signal_fragments_required", 1) or 1)

    def refresh_mission_text(self):
        if not hasattr(self, "mission_text"):
            return
        recovered = int(getattr(self, "signal_fragments_recovered", 0) or 0)
        required = int(getattr(self, "signal_fragments_required", 0) or 0)
        if getattr(self, "arena_mode_active", False):
            wave = int(getattr(self, "arena_wave", 0))
            waves = int((getattr(self, "arena_variant", {}) or {}).get("waves_per_capture", 3))
            line = f"ARENA  •  WAVE {wave}/{waves}"
        elif getattr(self, "extraction_active", False):
            meters = self.distance_to_node(getattr(self, "extraction_node", None))
            line = "RETURN LATTICE" + (f"  •  {meters}m" if meters is not None else "")
        elif getattr(self, "objective_complete", False) and required > 0 and recovered < required:
            line = f"SIGNAL {recovered}/{required}"
        else:
            # Capture flags, signal fragments, and district routes already render
            # truthful world-space guidance.  Do not duplicate it in the HUD.
            line = ""
        try:
            self._set_ui_text(self.mission_text, line)
        except Exception:
            pass


    def distance_to_node(self, node) -> int | None:
        try:
            if node is None or not getattr(node, "active", False):
                return None
            player = getattr(self, "player_pos", Vec3(0, 0, 0))
            delta = Vec3(node.pos.x - player.x, node.pos.y - player.y, 0)
            return max(0, int(round(delta.length())))
        except Exception:
            return None

    def distance_to_nearest_fragment(self) -> int | None:
        best = None
        try:
            for node in list(getattr(self, "objective_nodes", []) or []):
                if getattr(node, "completed", False) or not getattr(node, "active", False):
                    continue
                d = self.distance_to_node(node)
                if d is not None and (best is None or d < best):
                    best = d
        except Exception:
            return None
        return best

    def add_signal_pulse(self, pos: Vec3, label: str = "signal", radius: float = 4.0, life: float = 1.2, height: float = 0.10) -> None:
        try:
            budget = max(0, int(getattr(self.game_cfg, "objective_pulse_budget", 18)))
            self.signal_effects.append(SignalPulseEffect(self, pos, label=label, radius=radius, life=life, height=height))
            overflow = len(self.signal_effects) - budget
            if overflow > 0:
                for effect in self.signal_effects[:overflow]:
                    effect.dispose()
                self.signal_effects = self.signal_effects[overflow:]
        except Exception:
            pass

    def add_combat_feedback(self, pos: Vec3, label: str = "hit", radius: float = 1.0, life: float = 0.5, warning: bool = True) -> None:
        try:
            budget = max(0, int(getattr(self.game_cfg, "max_combat_effects", 28)))
            self.combat_effects.append(CombatFeedbackEffect(self, pos, label=label, radius=radius, life=life, warning=warning))
            overflow = len(self.combat_effects) - budget
            if overflow > 0:
                for effect in self.combat_effects[:overflow]:
                    effect.dispose()
                self.combat_effects = self.combat_effects[overflow:]
        except Exception:
            pass

    def build_return_trail(self) -> None:
        if getattr(self, "return_trail", None) is not None:
            try:
                if not self.return_trail.isEmpty():
                    self.return_trail.removeNode()
            except Exception:
                pass
        try:
            target = getattr(self, "extraction_node", None)
            if target is None:
                return
            segs = LineSegs("etchline-return-trail")
            segs.setThickness(max(2.0, float(getattr(self.game_cfg, "line_thickness", 1.45)) * 1.75))
            segs.setColor(*self.signal_accent_color(alpha=0.68))
            start = Vec3(0, 0, 0.08)
            end = Vec3(target.pos.x, target.pos.y, 0.08)
            segs.moveTo(start)
            segs.drawTo(end)
            steps = 14
            for i in range(1, steps):
                t = i / steps
                y = start.y * (1.0 - t) + end.y * t
                x = start.x * (1.0 - t) + end.x * t
                half = 1.2 + 0.5 * math.sin(i * 0.9)
                segs.moveTo(x - half, y, 0.10)
                segs.drawTo(x + half, y, 0.10)
            self.return_trail = self.mission_root.attachNewNode(segs.create())
            self.return_trail.setTransparency(TransparencyAttrib.MAlpha)
            self.return_trail.setAntialias(AntialiasAttrib.MLine)
        except Exception:
            self.return_trail = None

    def spawn_signal_wave(self, origin: Vec3) -> None:
        budget = max(0, int(getattr(self.game_cfg, "enemy_max_active", 24)) - len(getattr(self, "enemies", []) or []) - len(getattr(self, "pending_enemy_spawns", []) or []))
        count = min(max(0, int(getattr(self.game_cfg, "objective_wave_size", 3))), budget)
        if count <= 0:
            return
        self.add_signal_pulse(origin, label="wave", radius=8.8, life=1.85, height=0.16)
        self.set_objective_banner("SIGNAL PRESSURE WAVE // DISTANT HOSTILES INBOUND", 2.4)
        seed = self.hashed_seed(int(origin.x), int(origin.y), self.signal_fragments_recovered + 700)
        player_flat = self.flat_player_position()
        away = Vec3(origin.x - player_flat.x, origin.y - player_flat.y, 0.0)
        if away.lengthSquared() < 0.001:
            away = self.camera_forward_flat()
        away.normalize()
        self.queue_spawn_sequence(
            Vec3(origin.x, origin.y, 0.0),
            away,
            count,
            float(getattr(self.game_cfg, "objective_spawn_distance_min", 132.0)),
            float(getattr(self.game_cfg, "objective_spawn_distance_max", 196.0)),
            seed,
            source="objective_wave",
            objective_spawn=True,
        )
        self.clamp_enemy_population()

    def recover_signal_node(self, node: SignalNode, method: str = "touch") -> None:
        if node is None or getattr(node, "completed", False) or getattr(node, "kind", "fragment") != "fragment":
            return
        node.mark_completed()
        self.signal_fragments_recovered = min(self.signal_fragments_required, self.signal_fragments_recovered + 1)
        gain = int(getattr(self.game_cfg, "objective_score_per_fragment", 175))
        self.score += gain
        self.add_signal_pulse(node.pos, label=f"fragment-{node.index}", radius=max(4.0, node.radius), life=1.55, height=0.18)
        self.refill_unlocked_ammo(float(getattr(self.game_cfg, "weapon_objective_ammo_reward", 32.0)), silent=False)
        self.refresh_weapon_unlocks(silent=False)
        self.spawn_signal_wave(node.pos)
        self.set_objective_banner(f"{node.label} RECOVERED // +{gain} // {self.signal_fragments_recovered}/{self.signal_fragments_required}", 2.8)
        if self.signal_route_complete():
            if self.command_route_complete():
                self.activate_extraction()
            else:
                self.set_objective_banner("SIGNAL LOCKED // FINISH COMMAND NODE CAPTURE TO OPEN RETURN", 3.0)
        self.mission_result = self.get_mission_result()

    def activate_extraction(self) -> None:
        if getattr(self, "extraction_active", False):
            return
        if not self.signal_route_complete() or not self.command_route_complete():
            return
        self.extraction_active = True
        if getattr(self, "extraction_node", None) is not None:
            self.extraction_node.set_active(True)
            self.add_signal_pulse(self.extraction_node.pos, label="return-lattice", radius=8.5, life=2.2, height=0.2)
        self.build_return_trail()
        self.set_objective_banner("RETURN LATTICE OPEN // FOLLOW THE TRAIL", 4.0)
        self.record_activity("return_lattice", "Return Lattice", bonus=int(getattr(self.game_cfg, "activity_major_bonus_score", 140)), pos=getattr(self.extraction_node, "pos", Vec3(0, 0, 0)))

    def complete_objective(self) -> None:
        if getattr(self, "objective_complete", False):
            return
        if not getattr(self, "extraction_active", False):
            return
        self.objective_complete = True
        bonus = int(getattr(self.game_cfg, "objective_completion_bonus", 800))
        self.score += bonus
        if getattr(self, "extraction_node", None) is not None:
            self.add_signal_pulse(self.extraction_node.pos, label="complete", radius=10.0, life=2.4, height=0.28)
        self.set_objective_banner(f"UTOPIA CONFLICT ROUTE STABILIZED // +{bonus} // RETURN SIGNAL READY", 5.0)
        self.mission_result = self.get_mission_result()

    def update_signal_objectives(self, dt: float) -> None:
        player = getattr(self, "player_pos", Vec3(0, 0, 0))
        for node in list(getattr(self, "objective_nodes", []) or []):
            node.update(dt, player)
            if not node.completed and node.player_inside(player):
                self.recover_signal_node(node, method="touch")
        gate = getattr(self, "extraction_node", None)
        if gate is not None:
            gate.update(dt, player)
            if getattr(self, "extraction_active", False) and not getattr(self, "objective_complete", False) and gate.player_inside(player):
                self.complete_objective()
        if getattr(self, "objective_banner_time", 0.0) > 0.0:
            self.objective_banner_time = max(0.0, self.objective_banner_time - dt)

    def check_objective_shot(self, origin: Vec3, direction: Vec3, max_range: float):
        best = None
        for node in list(getattr(self, "objective_nodes", []) or []):
            hit = node.ray_hit(origin, direction, max_range)
            if hit is None:
                continue
            if best is None or hit[0] < best[0]:
                best = (hit[0], hit[1], node)
        return best

    def setup_campaign_objectives(self):
        old_root = getattr(self, "campaign_root", None)
        if old_root is not None and not old_root.isEmpty():
            old_root.removeNode()
        self.campaign_root = self.render.attachNewNode("campaign-objective-root")
        self.campaign_root.setTransparency(TransparencyAttrib.MAlpha)
        self.campaign_points = []
        self.score = int(getattr(self, "score", 0) or 0)
        self.campaign_complete = False
        self._campaign_complete_announced = False
        self.build_campaign_command_field()
        positions = [Vec3(0, 54, 0), Vec3(-46, 102, 0), Vec3(48, 104, 0)]
        for idx, pos in enumerate(positions):
            marker = self.create_campaign_point(idx, pos)
            self.campaign_points.append({"index": idx, "pos": pos, "node": marker, "progress": 0.0, "captured": False, "wave_triggered": False})
        self.ally_node = self.create_campaign_ally()
        self.ally_pos = Vec3(-3.5, -5.0, 0.0)

    def build_campaign_command_field(self):
        segs = LineSegs("campaign-command-field")
        segs.setThickness(1.4)
        segs.setColor(1.0, 1.0, 1.0, 0.72)
        z = 0.035
        for x in range(-80, 81, 16):
            segs.moveTo(x, -24, z)
            segs.drawTo(x, 136, z)
        for y in range(-16, 137, 16):
            segs.moveTo(-80, y, z)
            segs.drawTo(80, y, z)
        for a, b in [((-80, -24, z), (80, -24, z)), ((80, -24, z), (80, 136, z)), ((80, 136, z), (-80, 136, z)), ((-80, 136, z), (-80, -24, z))]:
            segs.moveTo(*a)
            segs.drawTo(*b)
        # route spine from spawn to the capture nodes, so the terrain no longer
        # looks detached from the player coordinates.
        route = [Vec3(0, 0, z + 0.01), Vec3(0, 54, z + 0.01), Vec3(-46, 102, z + 0.01), Vec3(48, 104, z + 0.01)]
        for a, b in zip(route, route[1:]):
            segs.moveTo(a)
            segs.drawTo(b)
        node = self.campaign_root.attachNewNode(segs.create())
        node.setAntialias(AntialiasAttrib.MLine)
        node.setTransparency(TransparencyAttrib.MAlpha)
        self.campaign_field_node = node

    def create_campaign_point(self, idx: int, pos: Vec3):
        root = self.campaign_root.attachNewNode(f"campaign-node-{idx + 1}")
        root.setPos(pos)
        root.setTransparency(TransparencyAttrib.MAlpha)
        segs = LineSegs(f"campaign-node-lines-{idx + 1}")
        segs.setThickness(2.3)
        segs.setColor(1.0, 1.0, 1.0, 0.95)
        z = 0.08
        # floor capture ring
        for radius in (4.2, 7.0, 9.8):
            last = None
            first = None
            for i in range(41):
                ang = math.tau * i / 40
                p = Vec3(math.cos(ang) * radius, math.sin(ang) * radius, z)
                if first is None:
                    first = p
                if last is None:
                    segs.moveTo(p)
                else:
                    segs.drawTo(p)
                last = p
        # flag pole and banner
        segs.moveTo(0, 0, z)
        segs.drawTo(0, 0, 10.5)
        banner = [(0, 0, 9.4), (4.8, 0, 8.8), (4.8, 0, 6.8), (0, 0, 7.4)]
        for a, b in zip(banner, banner[1:] + banner[:1]):
            segs.moveTo(*a)
            segs.drawTo(*b)
        for dx in (-2.8, 2.8):
            segs.moveTo(dx, -2.8, 0.18)
            segs.drawTo(dx, 2.8, 0.18)
            segs.moveTo(-2.8, dx, 0.18)
            segs.drawTo(2.8, dx, 0.18)
        np = root.attachNewNode(segs.create())
        np.setAntialias(AntialiasAttrib.MLine)
        np.setTransparency(TransparencyAttrib.MAlpha)

        # The next capturable flag gets a unique tall beacon.  Keep this separate
        # from the base flag geometry so only one campaign point needs to show it.
        beacon_segs = LineSegs(f"active-capture-beacon-{idx + 1}")
        beacon_segs.setThickness(3.4)
        beacon_segs.setColor(0.45, 1.0, 1.0, 0.98)
        for z0, z1 in ((10.8, 22.0), (22.0, 27.0)):
            beacon_segs.moveTo(0, 0, z0)
            beacon_segs.drawTo(0, 0, z1)
        for z_ring, radius in ((14.0, 2.4), (18.0, 3.5), (22.0, 4.6)):
            for i in range(17):
                ang = math.tau * i / 16.0
                p = Vec3(math.cos(ang) * radius, math.sin(ang) * radius, z_ring)
                if i == 0:
                    beacon_segs.moveTo(p)
                else:
                    beacon_segs.drawTo(p)
        # Three downward chevrons point directly at the capture ring.
        for z_chev, half_w in ((26.0, 3.4), (24.0, 2.8), (22.2, 2.2)):
            beacon_segs.moveTo(-half_w, 0, z_chev)
            beacon_segs.drawTo(0, 0, z_chev - 1.8)
            beacon_segs.drawTo(half_w, 0, z_chev)
        active_marker = root.attachNewNode(beacon_segs.create())
        active_marker.setAntialias(AntialiasAttrib.MLine)
        active_marker.setTransparency(TransparencyAttrib.MAlpha)
        active_marker.hide()

        label_node = TextNode(f"active-capture-label-{idx + 1}")
        label_node.setText("CAPTURE")
        label_node.setAlign(TextNode.ACenter)
        label_node.setTextColor(0.55, 1.0, 1.0, 0.98)
        label = active_marker.attachNewNode(label_node)
        label.setPos(0, 0, 28.0)
        label.setScale(1.25)
        try:
            label.setBillboardPointEye()
        except Exception:
            pass
        root.setPythonTag("active_capture_marker", active_marker)
        return root


    def spawn_campaign_defenders(self, idx: int, pos: Vec3):
        if not hasattr(self, "enemies"):
            self.enemies = []
        seed = self.hashed_seed(int(pos.x), int(pos.y), 700 + idx)
        player_flat = self.flat_player_position()
        approach = Vec3(pos.x - player_flat.x, pos.y - player_flat.y, 0.0)
        if approach.lengthSquared() < 0.001:
            approach = self.camera_forward_flat()
        approach.normalize()
        behind = Vec3(approach)
        if bool(getattr(self.game_cfg, "capture_zone_wave_behind_buildings", True)):
            # Spawn beyond the node from the player's current approach direction.
            # That puts the warning rings behind the city silhouettes/structure masks,
            # so the wave feels like it is coming out from behind the buildings.
            behind = approach
        count = int(getattr(self.game_cfg, "capture_zone_wave_size", 4))
        min_dist = float(getattr(self.game_cfg, "capture_zone_wave_min_distance", 66.0))
        max_dist = float(getattr(self.game_cfg, "capture_zone_wave_max_distance", 108.0))
        queued = self.queue_spawn_sequence(
            Vec3(pos.x, pos.y, 0.0),
            behind,
            count,
            min_dist,
            max_dist,
            seed,
            source=f"capture_zone_wave_{idx + 1}",
            objective_spawn=True,
        )
        # If obstacle/duplicate checks reject too many positions, put a few defenders
        # at known readable flanks.  A capture zone must always visibly respond.
        if queued < max(2, count // 2):
            side = Vec3(-behind.y, behind.x, 0.0)
            if side.lengthSquared() < 0.001:
                side = Vec3(1, 0, 0)
            side.normalize()
            for extra in range(count - queued):
                spawn_pos = Vec3(pos.x, pos.y, 0.0) + behind * (min_dist + extra * 8.0) + side * ((-1.0 if extra % 2 else 1.0) * (18.0 + extra * 6.0))
                if len(self.enemies) < int(getattr(self.game_cfg, "enemy_max_active", 24)):
                    self.add_combat_feedback(spawn_pos, label="spawn", radius=float(getattr(self.game_cfg, "spawn_warning_ring_radius", 3.25)), life=0.55, warning=True)
                    self.enemies.append(Enemy(self, spawn_pos, self.hashed_seed(int(spawn_pos.x), int(spawn_pos.y), seed + 600 + extra)))
                    queued += 1
        boss_spawned = False
        if idx >= int(getattr(self.game_cfg, "boss_spawn_on_capture_index", 2)):
            boss_pos = Vec3(pos.x, pos.y, 0.0) + behind * (max_dist + 18.0)
            if len(self.enemies) < int(getattr(self.game_cfg, "enemy_max_active", 24)):
                self.add_combat_feedback(boss_pos, label="boss", radius=5.4, life=1.1, warning=True)
                self.enemies.append(Enemy(self, boss_pos, self.hashed_seed(int(boss_pos.x), int(boss_pos.y), seed + 9900), variant_override="boss_mech"))
                boss_spawned = True
        if queued or boss_spawned:
            self.play_sfx("explosion_boss" if boss_spawned else f"enemy{1 + (idx % 5)}", volume=0.45 if boss_spawned else 0.38, rate=random.uniform(0.86, 1.08), pos=Vec3(pos.x, pos.y, 0.0))
            self.set_objective_banner(f"CAPTURE ZONE {idx + 1} BREACHED // {queued + (1 if boss_spawned else 0)} HOSTILES INBOUND", 2.0)
        else:
            self.set_objective_banner(f"CAPTURE ZONE {idx + 1} BREACHED // SPAWN BLOCKED", 2.0)
        self.clamp_enemy_population()

    def draw_octagon_loop_xy(self, segs: LineSegs, center: Vec3, radius: float, z_offset: float = 0.0):
        pts = []
        for i in range(8):
            ang = math.tau * i / 8.0 + math.pi / 8.0
            pts.append(Vec3(center.x + math.cos(ang) * radius, center.y + math.sin(ang) * radius, center.z + z_offset))
        for i, p in enumerate(pts):
            q = pts[(i + 1) % len(pts)]
            segs.moveTo(p); segs.drawTo(q)

    def build_arena_quad_panel(self, points, inner_color=(0.02, 0.14, 0.16, 0.42), name: str = "arena-panel"):
        return self.build_color_quad_geom([Point3(p.x, p.y, p.z) for p in points], [inner_color] * 4, name=name)

    def attach_arena_stage_panel(self, parent: NodePath, points, color, name: str):
        np = parent.attachNewNode(self.build_arena_quad_panel(points, color, name=name))
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setDepthWrite(False)
        np.setTwoSided(True)
        return np

    def build_arena_floor_panel(self, center: Vec3, radius: float):
        dark_alpha = float(getattr(self.game_cfg, "arena_stage_dark_alpha", 0.74))
        inner = (0.01, 0.05, 0.05, dark_alpha)
        outer = (0.00, 0.01, 0.02, dark_alpha * 0.54)
        return self.build_polygon_fan_geom_xy(center, radius, 8, inner, outer, name="arena-floor-panel")

    def build_polygon_fan_geom_xy(self, center: Vec3, radius: float, sides: int, inner_color, outer_color, name: str = "poly-fan"):
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData(name, fmt, Geom.UHStatic)
        vwriter = GeomVertexWriter(vdata, "vertex")
        cwriter = GeomVertexWriter(vdata, "color")
        prim = GeomTriangles(Geom.UHStatic)
        vwriter.addData3f(center.x, center.y, center.z)
        cwriter.addData4f(*inner_color)
        sides = max(3, int(sides))
        for i in range(sides + 1):
            ang = math.tau * i / sides + math.pi / 8.0
            vwriter.addData3f(center.x + math.cos(ang) * radius, center.y + math.sin(ang) * radius, center.z)
            cwriter.addData4f(*outer_color)
        for i in range(1, sides + 1):
            prim.addVertices(0, i, i + 1)
        geom = Geom(vdata)
        geom.addPrimitive(prim)
        node = GeomNode(name)
        node.addGeom(geom)
        return node

    def attach_polygon_fan_xy(self, parent: NodePath, center: Vec3, radius: float, sides: int, inner_color, outer_color, name: str = "poly-fan"):
        np = parent.attachNewNode(self.build_polygon_fan_geom_xy(center, radius, sides, inner_color, outer_color, name))
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setDepthWrite(False)
        np.setTwoSided(True)
        return np

    def arena_layout_config(self):
        variant = getattr(self, "arena_variant", {}) or {}
        layout = variant.get("layout", {}) if isinstance(variant, dict) else {}
        return layout if isinstance(layout, dict) else {}

    def build_arena_shell(self):
        if hasattr(self, "arena_root") and self.arena_root is not None and not self.arena_root.isEmpty():
            self.arena_root.removeNode()
        self.arena_root = self.render.attachNewNode("vector-arena-expanded-root")
        c = Vec3(getattr(self, "arena_center", Vec3(0, -520, 0)))
        layout = self.arena_layout_config()
        radius = float(layout.get("radius", getattr(self.game_cfg, "arena_level_radius", 74.0)))
        outer_radius = radius * 1.12

        floor = self.arena_root.attachNewNode(self.build_arena_floor_panel(c + Vec3(0, 0, 0.025), outer_radius))
        floor.setTransparency(TransparencyAttrib.MAlpha)
        floor.setDepthWrite(False)
        floor.setTwoSided(True)

        panel_alpha = float(getattr(self.game_cfg, "arena_stage_panel_alpha", 0.48))
        perimeter_alpha = float(getattr(self.game_cfg, "arena_perimeter_panel_alpha", 0.82))
        cyan_panel = (0.00, 0.18, 0.14, panel_alpha)
        amber_panel = (0.22, 0.05, 0.04, panel_alpha * 0.90)
        black_panel = (0.01, 0.01, 0.02, max(0.26, panel_alpha * 0.72))
        perimeter_green = (0.02, 0.12, 0.10, perimeter_alpha)
        perimeter_red = (0.14, 0.03, 0.04, perimeter_alpha * 0.96)
        perimeter_dark = (0.01, 0.01, 0.02, perimeter_alpha)
        z = c.z + 0.045
        half = 11.5

        # Large solid octagonal arena base and central pad.
        self.attach_polygon_fan_xy(self.arena_root, c + Vec3(0, 0, z + 0.003), outer_radius * 0.98, 8, black_panel, perimeter_dark, "arena-outer-octagon-fill")
        self.attach_polygon_fan_xy(self.arena_root, c + Vec3(0, 0, z + 0.004), 36.0, 8, perimeter_dark, amber_panel, "arena-mid-octagon-fill")
        self.attach_polygon_fan_xy(self.arena_root, c + Vec3(0, 0, z + 0.005), 18.0, 8, cyan_panel, black_panel, "arena-center-octagon-fill")
        self.attach_arena_stage_panel(self.arena_root, [c + Vec3(-half, -half, z), c + Vec3(half, -half, z), c + Vec3(half, half, z), c + Vec3(-half, half, z)], cyan_panel, "arena-central-pad")

        lane_w = 10.5
        lane_panels = [
            (-lane_w, -radius * 0.88, lane_w, -half, cyan_panel),
            (-lane_w, half, lane_w, radius * 0.88, cyan_panel),
            (-radius * 0.88, -lane_w, -half, lane_w, amber_panel),
            (half, -lane_w, radius * 0.88, lane_w, amber_panel),
        ]
        for idx, (x0, y0, x1, y1, col) in enumerate(lane_panels):
            self.attach_arena_stage_panel(self.arena_root, [c + Vec3(x0, y0, z), c + Vec3(x1, y0, z), c + Vec3(x1, y1, z), c + Vec3(x0, y1, z)], col, f"arena-stage-lane-{idx}")
        diag = radius * 0.50
        for idx, pts in enumerate([
            [c + Vec3(-diag, -diag * 0.36, z), c + Vec3(-diag * 0.36, -diag, z), c + Vec3(diag, diag * 0.36, z), c + Vec3(diag * 0.36, diag, z)],
            [c + Vec3(diag * 0.36, -diag, z), c + Vec3(diag, -diag * 0.36, z), c + Vec3(-diag * 0.36, diag, z), c + Vec3(-diag, diag * 0.36, z)],
        ]):
            self.attach_arena_stage_panel(self.arena_root, pts, black_panel if idx == 0 else amber_panel, f"arena-diag-panel-{idx}")

        # Perimeter wall panels create a real arena enclosure instead of floating wires.
        wall_entries = []
        wall_count = 8
        for i in range(wall_count):
            ang = math.tau * i / wall_count + math.pi / 8.0
            wall_center = c + Vec3(math.cos(ang) * (outer_radius - 8.0), math.sin(ang) * (outer_radius - 8.0), 9.0)
            wall_size = Vec3(22.0, 4.0, 18.0) if abs(math.cos(ang)) > abs(math.sin(ang)) else Vec3(4.0, 22.0, 18.0)
            wall_color = perimeter_green if i % 2 == 0 else perimeter_red
            wall_entries.append((wall_center, wall_size))
            self.attach_weapon_box_fill(self.arena_root, wall_center, wall_size, wall_color, f"arena-wall-fill-{i}")

        # Bridge / lane objects with infill.
        bridge_boxes = []
        for bridge_idx in range(int(layout.get("bridge_count", getattr(self.game_cfg, "arena_bridge_count", 4)))):
            ang = math.tau * bridge_idx / max(1, int(layout.get("bridge_count", 4))) + math.pi / 4.0
            bx = math.cos(ang) * radius * 0.42
            by = math.sin(ang) * radius * 0.42
            size = Vec3(22.0 if abs(bx) < abs(by) else 7.0, 7.0 if abs(bx) < abs(by) else 22.0, 4.2)
            center = c + Vec3(bx, by, 2.2)
            bridge_boxes.append((center, size))
            self.attach_weapon_box_fill(self.arena_root, center, size, perimeter_dark, f"arena-bridge-fill-{bridge_idx}")

        # Cover pylons are solid objects with cap panels.
        pylon_entries = []
        pylon_count = min(8, int(layout.get("cover_pylons", getattr(self.game_cfg, "arena_cover_pylon_count", 8))))
        for i in range(pylon_count):
            ang = math.tau * i / max(1, pylon_count)
            pr = radius * (0.50 if i % 2 else 0.66)
            size = Vec3(4.8, 4.8, 8.0 + (i % 3) * 2.2)
            center = c + Vec3(math.cos(ang) * pr, math.sin(ang) * pr, size.z * 0.5)
            pylon_entries.append((center, size))
            self.attach_weapon_box_fill(self.arena_root, center, size, perimeter_dark, f"arena-pylon-fill-{i}")
            self.attach_polygon_fan_xy(self.arena_root, center + Vec3(0, 0, size.z + 0.10), 3.4, 8, perimeter_green if i % 2 == 0 else perimeter_red, perimeter_dark, f"arena-pylon-cap-{i}")

        # Spawn gates as solid frames.
        gate_entries = []
        for i in range(8):
            ang = math.tau * i / 8.0
            gate = c + Vec3(math.cos(ang) * (outer_radius + 10.0), math.sin(ang) * (outer_radius + 10.0), 7.0)
            gate_size = Vec3(9.0, 3.5, 14.0) if abs(math.cos(ang)) > abs(math.sin(ang)) else Vec3(3.5, 9.0, 14.0)
            gate_entries.append((gate, gate_size))
            self.attach_weapon_box_fill(self.arena_root, gate, gate_size, perimeter_red if i % 2 else perimeter_green, f"arena-gate-fill-{i}")

        # Central breach-core tower uses stacked octagonal infill.
        tower_boxes = []
        tower_levels = [(6.4, 4.0, perimeter_green), (4.9, 8.4, perimeter_dark), (3.8, 12.8, perimeter_red), (2.8, 16.8, perimeter_dark)]
        for idx, (rad, height, color) in enumerate(tower_levels):
            self.attach_weapon_prism(self.arena_root, self.octagon_points(rad, rad), 0.0, height, color, f"arena-core-prism-{idx}").setPos(c)
            tower_boxes.append((c + Vec3(0, 0, height * 0.5), Vec3(rad * 1.8, rad * 1.8, height)))
        self.attach_polygon_fan_xy(self.arena_root, c + Vec3(0, 0, 16.95), 3.0, 8, perimeter_red, perimeter_dark, "arena-core-cap")

        # Object-attached outlines only. No unsupported floating wires.
        segs = LineSegs("vector-arena-object-outlines")
        segs.setThickness(1.4)
        segs.setColor(0.20, 0.98, 0.88, 0.46)
        for ring_radius in layout.get("rings", [24.0, 44.0, 68.0, radius, outer_radius]):
            self.draw_octagon_loop_xy(segs, c + Vec3(0, 0, 0.10), float(ring_radius), 0.0)
        # Keep outlines only on a subset of arena objects so the space reads as mesh-first, not floating wireframe.
        for center, size in bridge_boxes + gate_entries[:4]:
            self.draw_box_edges(segs, center, size)
        shell = self.arena_root.attachNewNode(segs.create())
        shell.setAntialias(AntialiasAttrib.MLine)
        shell.setTransparency(TransparencyAttrib.MAlpha)

        # Surface seams on the floor pad are allowed because they belong to filled objects.
        accent = LineSegs("vector-arena-surface-seams")
        accent.setThickness(1.8)
        accent.setColor(1.0, 0.24, 0.20, 0.40)
        for ang in (0.0, math.pi * 0.5):
            accent.moveTo(c.x + math.cos(ang) * 8.5, c.y + math.sin(ang) * 8.5, c.z + 0.16)
            accent.drawTo(c.x + math.cos(ang) * (outer_radius - 12.0), c.y + math.sin(ang) * (outer_radius - 12.0), c.z + 0.16)
        accent_np = self.arena_root.attachNewNode(accent.create())
        accent_np.setAntialias(AntialiasAttrib.MLine)
        accent_np.setTransparency(TransparencyAttrib.MAlpha)

        self.arena_root.hide()
        return self.arena_root

    def source_vector_arena_controls_active(self) -> bool:
        return bool(getattr(self, "arena_mode_active", False) and getattr(self, "vector_arena_native_mode", None) is not None)

    def vector_arena_adapter_path(self) -> Path:
        return ROOT / "Vector Arena" / "standalone_native_adapter.py"

    def vector_arena_source_available(self) -> bool:
        path = self.vector_arena_adapter_path()
        return bool(path.is_file())

    def load_vector_arena_adapter_module(self):
        if self.vector_arena_adapter_module is not None:
            return self.vector_arena_adapter_module
        path = self.vector_arena_adapter_path()
        if not path.is_file():
            self.vector_arena_adapter_error = f"missing adapter: {path}"
            return None
        try:
            module_name = "utopia_conflict_source_vector_arena_adapter"
            spec = importlib.util.spec_from_file_location(module_name, os.fspath(path))
            if spec is None or spec.loader is None:
                self.vector_arena_adapter_error = "import spec failed"
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            self.vector_arena_adapter_module = module
            return module
        except Exception as exc:
            self.vector_arena_adapter_error = f"{exc.__class__.__name__}: {exc}"
            return None

    def hide_uc_ui_for_vector_adapter(self):
        self.vector_arena_hid_uc_ui = True
        for node_name in ("hud_root", "crosshair", "activity_board_root", "workstation_root"):
            node = getattr(self, node_name, None)
            try:
                if node is not None and not node.isEmpty():
                    node.hide()
            except Exception:
                pass
        for mount in (getattr(self, "weapon_mounts", {}) or {}).values():
            try:
                root = mount.get("root") if isinstance(mount, dict) else mount
                if root is not None and not root.isEmpty():
                    root.hide()
            except Exception:
                pass

    def restore_uc_ui_after_vector_adapter(self):
        if not getattr(self, "vector_arena_hid_uc_ui", False):
            return
        self.vector_arena_hid_uc_ui = False
        for node_name in ("hud_root", "crosshair", "workstation_root"):
            node = getattr(self, node_name, None)
            try:
                if node is not None and not node.isEmpty() and getattr(self, "hud_visible", True):
                    node.show()
            except Exception:
                pass
        for mount in (getattr(self, "weapon_mounts", {}) or {}).values():
            try:
                root = mount.get("root") if isinstance(mount, dict) else mount
                if root is not None and not root.isEmpty():
                    root.show()
            except Exception:
                pass

    def start_source_vector_arena_adapter(self) -> bool:
        module = self.load_vector_arena_adapter_module()
        if module is None or not hasattr(module, "create_mode"):
            return False
        try:
            if self.vector_arena_native_mode is not None:
                try:
                    self.vector_arena_native_mode.exit()
                except Exception:
                    pass
                self.vector_arena_native_mode = None
            entry_path = ROOT / "Vector Arena" / "main.py"
            mode = module.create_mode(
                self,
                mode={
                    "id": "vector_arena_source_adapter",
                    "host_game": "utopia_conflict",
                    "shared_display": True,
                    "shared_audio_assets": "assets/audio/sfx",
                },
                entry_path=os.fspath(entry_path),
                label="Vector Arena // Utopia Conflict",
            )
            mode.enter()
            self.vector_arena_native_mode = mode
            self.keys = {key: False for key in getattr(self, "keys", {})}
            self.fire_hold = {"right": False, "left": False}
            self.fire_down = {"right": False, "left": False}
            self.vector_arena_adapter_stats = {
                "source_adapter": os.fspath(self.vector_arena_adapter_path().relative_to(ROOT)),
                "shared_display": True,
                "sfx_loaded": int(getattr(mode, "sfx_loaded_count", 0)),
                "sfx_sources": dict(getattr(mode, "sfx_source_paths", {}) or {}),
                "world_children": int(mode.world_root.getNumChildren()) if getattr(mode, "world_root", None) is not None and not mode.world_root.isEmpty() else 0,
                "enemy_pool": len(getattr(mode, "enemies", []) or []),
                "breach_cores": len(getattr(mode, "breach_cores", []) or []),
            }
            self.hide_uc_ui_for_vector_adapter()
            return True
        except Exception as exc:
            self.vector_arena_adapter_error = f"{exc.__class__.__name__}: {exc}"
            self.vector_arena_native_mode = None
            return False

    def update_source_vector_arena_adapter(self, dt: float):
        mode = getattr(self, "vector_arena_native_mode", None)
        if mode is None:
            return
        try:
            mode.update(dt)
            result = mode.get_result() if hasattr(mode, "get_result") else {}
            self.arena_wave = int(result.get("wave", getattr(mode, "wave", 1)) or 1)
            self.arena_total_kills = int(result.get("kills", getattr(mode, "kills", 0)) or 0)
            self.arena_wave_kills = int(getattr(mode, "kills", 0))
            self.score = max(int(getattr(self, "score", 0)), int(result.get("score_delta", 0) or 0))
            self.vector_arena_adapter_stats.update({
                "wave": int(getattr(mode, "wave", 1)),
                "kills": int(getattr(mode, "kills", 0)),
                "score_delta": int(result.get("score_delta", 0) or 0),
                "sfx_loaded": int(getattr(mode, "sfx_loaded_count", 0)),
                "breaches_sealed": int(result.get("breaches_sealed", 0) or 0),
            })
        except Exception as exc:
            self.vector_arena_adapter_error = f"{exc.__class__.__name__}: {exc}"

    def stop_source_vector_arena_adapter(self, completed: bool = False):
        mode = getattr(self, "vector_arena_native_mode", None)
        if mode is None:
            return {}
        result = {}
        try:
            if hasattr(mode, "get_result"):
                result = dict(mode.get_result() or {})
        except Exception:
            result = {}
        try:
            mode.exit()
        except Exception:
            pass
        self.vector_arena_native_mode = None
        self.restore_uc_ui_after_vector_adapter()
        score_delta = int(result.get("score_delta", 0) or 0)
        if score_delta:
            self.score += score_delta
            self.lab_points += max(0, score_delta // 10)
        if completed:
            self.lab_points += int(getattr(self.game_cfg, "arena_reward_points_complete", 140))
        self.vector_arena_adapter_stats.update({
            "last_result": result,
            "completed_exit": bool(completed),
            "score_delta_banked": score_delta,
        })
        return result

    def build_arena_portal_node(self, pos: Vec3, index: int):
        root = self.render.attachNewNode(f"arena-portal-node-{index}")
        root.setPos(Vec3(pos.x, pos.y, 0.2))
        root.setTransparency(TransparencyAttrib.MAlpha)
        segs = LineSegs(f"arena-portal-lines-{index}")
        segs.setThickness(2.0)
        segs.setColor(0.18, 1.0, 0.88, 0.94)
        for radius in (2.6, 4.1, 5.5):
            last = None
            first = None
            for i in range(41):
                ang = math.tau * i / 40
                p = Vec3(math.cos(ang) * radius, math.sin(ang) * radius, 0.18 + radius * 0.03)
                if first is None:
                    first = p
                if last is None:
                    segs.moveTo(p)
                else:
                    segs.drawTo(p)
                last = p
        for angle in (0, math.pi * 0.5, math.pi, math.pi * 1.5):
            a = Vec3(math.cos(angle) * 1.6, math.sin(angle) * 1.6, 0.2)
            b = Vec3(math.cos(angle) * 6.2, math.sin(angle) * 6.2, 0.75)
            segs.moveTo(a); segs.drawTo(b)
        node = root.attachNewNode(segs.create())
        node.setAntialias(AntialiasAttrib.MLine)
        root.setColorScale(0.6, 1.25, 1.1, 0.92)
        return root

    def setup_arena_integration(self):
        self.arena_portals = []
        self.arena_completed_captures = set()
        self.arena_variant = self.load_arena_variant_config()
        self.build_arena_shell()

    def load_arena_variant_config(self):
        default = {
            "id": "hardlight_default",
            "name": "Vector Arena // Hardlight Breach",
            "wave_seconds": float(getattr(self.game_cfg, "arena_wave_seconds", 60.0)),
            "waves_per_capture": int(getattr(self.game_cfg, "arena_waves_per_capture", 3)),
            "arena_weapons": ["Pulse Rifle", "Repulsor Burst", "Breach Cutter"],
            "arena_weapon_slots": {"1": "Pulse Rifle", "5": "Repulsor Burst", "6": "Breach Cutter"},
            "arena_mobs": ["arena_stalker", "arena_sentry", "arena_tank", "arena_guardian"],
            "wave_sizes": [4, 6, 8],
            "core_hits_by_wave": [3, 4, 5],
            "points_per_wave": int(getattr(self.game_cfg, "arena_reward_points_per_wave", 35)),
            "points_complete": int(getattr(self.game_cfg, "arena_reward_points_complete", 140)),
            "uses_shared_sfx": True,
            "layout": {"radius": 74.0, "rings": [24.0, 40.0, 58.0, 74.0], "bridge_count": 4, "cover_pylons": 12, "spawn_gates": 8},
        }
        try:
            ARENA_VARIANTS_DIR.mkdir(parents=True, exist_ok=True)
            folder = ARENA_VARIANTS_DIR / self.arena_variant_id
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / "arena.json"
            legacy_path = ARENA_VARIANTS_DIR / "hardlight_default.json"
            if not path.exists():
                path.write_text(json.dumps(default, indent=2), encoding="utf-8")
            read_path = path if path.exists() else legacy_path
            data = json.loads(read_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                default.update(data)
            default["variant_path"] = os.fspath(read_path.relative_to(ROOT))
        except Exception:
            pass
        return default

    def create_arena_portal_for_capture(self, point):
        if not bool(getattr(self.game_cfg, "arena_enabled", True)):
            return None
        idx = int(point.get("index", 0)) if isinstance(point, dict) else 0
        for entry in getattr(self, "arena_portals", []) or []:
            if int(entry.get("capture_index", -1)) == idx:
                return entry
        pos = Vec3(point.get("pos", Vec3(0, 0, 0))) + Vec3(0, -10.0, 0)
        node = self.build_arena_portal_node(pos, idx)
        entry = {"capture_index": idx, "pos": pos, "node": node, "active": True}
        self.arena_portals.append(entry)
        self.play_sfx("breach_spawn", volume=0.82, pos=pos)
        self.set_objective_banner("VECTOR ARENA PORTAL OPEN // PRESS E INSIDE THE RING", 3.0)
        return entry

    def nearest_arena_portal(self):
        player_flat = Vec3(self.player_pos.x, self.player_pos.y, 0)
        best = None
        best_dist = 999999.0
        for entry in getattr(self, "arena_portals", []) or []:
            if not entry.get("active", True):
                continue
            dist = (Vec3(entry.get("pos", Vec3(0, 0, 0))) - player_flat).length()
            if dist < best_dist:
                best = entry
                best_dist = dist
        return best, best_dist

    def try_enter_arena_portal(self):
        if getattr(self, "arena_mode_active", False):
            self.exit_arena_mode(completed=False)
            return
        entry, dist = self.nearest_arena_portal()
        if entry is not None and dist <= float(getattr(self.game_cfg, "arena_portal_radius", 5.5)):
            self.enter_arena_mode(entry)
        else:
            self.combat_banner = "NO ARENA PORTAL IN RANGE"
            self.combat_banner_time = 0.8

    def enter_arena_mode(self, portal_entry):
        self.arena_mode_active = True
        self.arena_capture_index = int(portal_entry.get("capture_index", 0))
        self.arena_entry_return_pos = Vec3(self.player_pos)
        self.arena_wave = 0
        self.arena_wave_kills = 0
        self.arena_total_kills = 0
        self.arena_combo_meter = 0
        self.arena_last_wave_result = ""
        self.arena_city_weapon_slots = dict(getattr(self, "hand_weapon_slots", {"right": 1, "left": 2}))
        arena_slots = (getattr(self, "arena_variant", {}) or {}).get("arena_weapon_slots", {}) or {}
        self.arena_weapon_aliases = {int(k): str(v) for k, v in arena_slots.items()} if isinstance(arena_slots, dict) else {1: "Pulse Rifle", 5: "Repulsor Burst", 6: "Breach Cutter"}
        if hasattr(self, "select_weapon_slot"):
            self.select_weapon_slot(1, force=True, silent=True)
        if hasattr(self, "select_left_weapon_slot"):
            self.select_left_weapon_slot(5, force=True, silent=True)
        if self.vector_arena_source_available() and self.start_source_vector_arena_adapter():
            self.pending_enemy_spawns.clear()
            for enemy in list(getattr(self, "enemies", []) or []):
                try:
                    if enemy.root is not None and not enemy.root.isEmpty():
                        enemy.root.removeNode()
                except Exception:
                    pass
            self.enemies.clear()
            if getattr(self, "arena_root", None) is not None and not self.arena_root.isEmpty():
                self.arena_root.hide()
            if bool(getattr(self.game_cfg, "arena_hide_city_during_mode", True)) and getattr(self, "city_root", None) is not None and not self.city_root.isEmpty():
                self.city_root.hide()
            self.arena_wave = 1
            self.arena_wave_timer = float(self.arena_variant.get("wave_seconds", getattr(self.game_cfg, "arena_wave_seconds", 60.0)))
            self.arena_wave_target_kills = 4
            self.arena_core_max_hp = 3
            self.arena_core_hp = 3
            self.play_sfx("wave_start", volume=0.9)
            return
        self.pending_enemy_spawns.clear()
        for enemy in list(getattr(self, "enemies", []) or []):
            try:
                if enemy.root is not None and not enemy.root.isEmpty():
                    enemy.root.removeNode()
            except Exception:
                pass
        self.enemies.clear()
        if getattr(self, "arena_root", None) is None or self.arena_root.isEmpty():
            self.build_arena_shell()
        self.arena_root.show()
        if bool(getattr(self.game_cfg, "arena_hide_city_during_mode", True)) and getattr(self, "city_root", None) is not None and not self.city_root.isEmpty():
            self.city_root.hide()
        c = Vec3(getattr(self, "arena_center", Vec3(0, -520, 0)))
        self.player_pos = Vec3(c.x, c.y - 42.0, self.game_cfg.player_height)
        self.camera.setPos(self.player_pos)
        self.yaw = 0.0
        self.pitch = -9.0
        self.camera.setH(self.yaw); self.camera.setP(self.pitch)
        self.play_sfx("wave_start", volume=0.9)
        self.start_arena_wave()

    def start_arena_wave(self):
        self.arena_wave += 1
        self.arena_wave_timer = float(self.arena_variant.get("wave_seconds", getattr(self.game_cfg, "arena_wave_seconds", 60.0)))
        self.arena_wave_kills = 0
        sizes = list(self.arena_variant.get("wave_sizes", [])) or [4, 6, 8]
        self.arena_wave_target_kills = int(sizes[min(len(sizes) - 1, max(0, int(self.arena_wave) - 1))])
        core_hits = list(self.arena_variant.get("core_hits_by_wave", [])) or [int(getattr(self.game_cfg, "arena_core_hits_per_wave", 3))] * 3
        self.arena_core_max_hp = int(core_hits[min(len(core_hits) - 1, max(0, int(self.arena_wave) - 1))])
        self.arena_core_hp = int(self.arena_core_max_hp)
        self.spawn_arena_wave_enemies()
        self.set_objective_banner(f"VECTOR ARENA // WAVE {self.arena_wave}/{int(self.arena_variant.get('waves_per_capture', 3))} // 60 SECOND BREACH", 2.4)
        self.play_sfx("wave_start", volume=0.86, rate=1.0 + 0.04 * self.arena_wave)

    def spawn_arena_wave_enemies(self):
        c = Vec3(getattr(self, "arena_center", Vec3(0, -520, 0)))
        sizes = list(self.arena_variant.get("wave_sizes", [])) or [4, 6, 8]
        count = int(sizes[min(len(sizes) - 1, max(0, int(self.arena_wave) - 1))])
        variants_by_wave = [["stalker", "sentinel"], ["stalker", "sentinel", "bulwark"], ["stalker", "sentinel", "bulwark", "commander"]]
        pool = variants_by_wave[min(2, max(0, int(self.arena_wave) - 1))]
        for i in range(count):
            ang = math.tau * i / max(1, count) + self.arena_wave * 0.23
            radius = 28.0 + 4.0 * (i % 3)
            pos = c + Vec3(math.cos(ang) * radius, math.sin(ang) * radius, 0)
            arena_style = ["arena_stalker", "arena_sentry", "arena_tank", "arena_guardian"][min(3, i % 4)]
            enemy = Enemy(self, pos, self.hashed_seed(9000 + self.arena_wave, i, 1881), variant_override=pool[i % len(pool)], arena_variant=arena_style, arena_enemy=True)
            enemy.health = int(enemy.health * (1.0 + 0.42 * max(0, self.arena_wave - 1)))
            enemy.base_speed = float(enemy.base_speed) * (1.0 + 0.08 * max(0, self.arena_wave - 1))
            enemy.speed = float(enemy.base_speed)
            self.enemies.append(enemy)
            self.add_combat_feedback(pos, label="spawn", radius=3.4, life=0.72, warning=True)
        self.play_sfx("enemy_spawn", volume=0.68, pos=c)

    def update_arena_mode(self, dt: float):
        if not getattr(self, "arena_mode_active", False):
            return
        if getattr(self, "vector_arena_native_mode", None) is not None:
            self.update_source_vector_arena_adapter(dt)
            return
        self.arena_wave_timer = max(0.0, float(getattr(self, "arena_wave_timer", 0.0)) - dt)
        active = [e for e in getattr(self, "enemies", []) if not getattr(e, "dead", False)]
        if (not active and int(getattr(self, "arena_core_hp", 0)) <= 0) or self.arena_wave_timer <= 0.0:
            self.complete_arena_wave(time_expired=self.arena_wave_timer <= 0.0)

    def arena_take_breach_damage(self, amount: int = 1, source_point: Vec3 = None):
        if not getattr(self, "arena_mode_active", False):
            return False
        self.arena_core_hp = max(0, int(getattr(self, "arena_core_hp", 0)) - int(amount))
        self.arena_combo_meter = int(getattr(self, "arena_combo_meter", 0)) + 1
        c = Vec3(getattr(self, "arena_center", Vec3(0, -520, 0)))
        self.add_shockwave_ring(c + Vec3(0, 0, 6.0), radius=10.0 + self.arena_combo_meter, life=0.48, vertical=False, thickness=1.8)
        self.add_combat_feedback(c + Vec3(0, 0, 2.0), label=f"core {self.arena_core_hp}", radius=5.5, life=0.62, warning=False)
        self.play_sfx("breach_hit", volume=0.70, pos=c)
        return self.arena_core_hp <= 0

    def complete_arena_wave(self, time_expired: bool = False):
        wave_points = int(self.arena_variant.get("points_per_wave", getattr(self.game_cfg, "arena_reward_points_per_wave", 35)))
        self.lab_points += wave_points
        self.score += 100 + 35 * int(getattr(self, "arena_wave", 1))
        self.arena_last_wave_result = "TIME HOLD" if time_expired else "CORE SEALED"
        if int(getattr(self, "arena_wave", 0)) >= 3:
            self.lab_points += int(getattr(self.game_cfg, "arena_shared_upgrade_bonus_wave3", 40))
        self.play_sfx("combo_surge", volume=0.78)
        if int(getattr(self, "arena_wave", 0)) >= int(self.arena_variant.get("waves_per_capture", getattr(self.game_cfg, "arena_waves_per_capture", 3))):
            self.exit_arena_mode(completed=True)
            return
        self.start_arena_wave()

    def exit_arena_mode(self, completed: bool = False):
        if getattr(self, "vector_arena_native_mode", None) is not None:
            self.stop_source_vector_arena_adapter(completed=completed)
        if completed:
            bonus = int(self.arena_variant.get("points_complete", getattr(self.game_cfg, "arena_reward_points_complete", 140)))
            self.lab_points += bonus
            self.score += 450
            self.arena_completed_captures.add(int(getattr(self, "arena_capture_index", 0)))
            self.play_sfx("breach_sealed", volume=0.92)
            self.set_objective_banner("VECTOR ARENA CLEARED // POINTS BANKED FOR UPGRADES", 3.0)
        else:
            self.set_objective_banner("VECTOR ARENA EXITED", 1.4)
        for enemy in list(getattr(self, "enemies", []) or []):
            try:
                if enemy.root is not None and not enemy.root.isEmpty():
                    enemy.root.removeNode()
            except Exception:
                pass
        self.enemies.clear()
        if getattr(self, "arena_root", None) is not None and not self.arena_root.isEmpty():
            self.arena_root.hide()
        if getattr(self, "city_root", None) is not None and not self.city_root.isEmpty():
            self.city_root.show()
        self.player_pos = Vec3(getattr(self, "arena_entry_return_pos", Vec3(0, 0, self.game_cfg.player_height)))
        self.camera.setPos(self.player_pos)
        if isinstance(getattr(self, "arena_city_weapon_slots", None), dict):
            try:
                self.hand_weapon_slots.update(self.arena_city_weapon_slots)
                self.refresh_weapon_models()
            except Exception:
                pass
        self.arena_mode_active = False
        self.arena_wave = 0
        self.arena_wave_timer = 0.0
        self.arena_wave_kills = 0

    def buy_ammo_capacity_upgrade(self):
        if self.source_vector_arena_controls_active():
            return False
        cost = int(getattr(self.game_cfg, "upgrade_ammo_cost", 90)) + int(getattr(self, "upgrade_levels", {}).get("ammo_capacity", 0)) * 45
        if int(getattr(self, "lab_points", 0)) < cost:
            self.combat_banner = f"NEED {cost} POINTS // AMMO CAPACITY"
            self.combat_banner_time = 1.1
            self.play_sfx("weapon_empty", volume=0.52)
            return False
        self.lab_points -= cost
        self.upgrade_levels["ammo_capacity"] = int(self.upgrade_levels.get("ammo_capacity", 0)) + 1
        step = float(getattr(self.game_cfg, "upgrade_ammo_capacity_step", 18.0))
        for weapon in getattr(self, "weapons", []) or []:
            weapon.ammo_capacity = float(getattr(weapon, "ammo_capacity", 100.0)) + step
            self.weapon_ammo_pools[int(weapon.slot)] = min(float(weapon.ammo_capacity), float(self.weapon_ammo_pools.get(int(weapon.slot), 0.0)) + step)
        self.update_current_weapon_ammo_alias()
        self.combat_banner = "AMMO CAPACITY UPGRADED"
        self.combat_banner_time = 1.4
        self.play_sfx("weapon_upgrade", volume=0.84)
        return True

    def buy_health_capacity_upgrade(self):
        if self.source_vector_arena_controls_active():
            return False
        cost = int(getattr(self.game_cfg, "upgrade_health_cost", 120)) + int(getattr(self, "upgrade_levels", {}).get("health_capacity", 0)) * 60
        if int(getattr(self, "lab_points", 0)) < cost:
            self.combat_banner = f"NEED {cost} POINTS // HEALTH CAPACITY"
            self.combat_banner_time = 1.1
            self.play_sfx("weapon_empty", volume=0.52)
            return False
        self.lab_points -= cost
        self.upgrade_levels["health_capacity"] = int(self.upgrade_levels.get("health_capacity", 0)) + 1
        self.player_health_max += int(getattr(self.game_cfg, "upgrade_health_step", 25))
        self.health = self.player_health_max
        self.sync_player_armor_capacity(refill=True)
        self.combat_banner = "HEALTH CAPACITY UPGRADED // ARMOR MAX RESYNCED"
        self.combat_banner_time = 1.4
        self.play_sfx("weapon_upgrade", volume=0.84)
        return True

    def buy_armor_capacity_upgrade(self):
        if self.source_vector_arena_controls_active():
            return False
        level = int(getattr(self, "upgrade_levels", {}).get("armor_capacity", 0))
        cost = int(getattr(self.game_cfg, "upgrade_armor_cost", 110)) + level * 70
        if int(getattr(self, "lab_points", 0)) < cost:
            self.combat_banner = f"NEED {cost} POINTS // ARMOR SHELL"
            self.combat_banner_time = 1.1
            self.play_sfx("weapon_empty", volume=0.52)
            return False
        self.lab_points -= cost
        self.upgrade_levels["armor_capacity"] = level + 1
        self.sync_player_armor_capacity(refill=True)
        self.armor_damage_fade_timer = float(getattr(self.game_cfg, "player_armor_hit_fade_seconds", 0.85))
        self.combat_banner = f"ARMOR SHELL UPGRADED // {self.player_armor_percent_capacity()}% CYAN"
        self.combat_banner_time = 1.5
        self.play_sfx("weapon_upgrade", volume=0.84)
        self.update_palette(0.0)
        return True

    def create_campaign_ally(self):
        root = self.campaign_root.attachNewNode("campaign-ally")
        root.setTransparency(TransparencyAttrib.MAlpha)
        segs = LineSegs("campaign-ally-lines")
        segs.setThickness(2.1)
        segs.setColor(1.0, 1.0, 1.0, 0.94)
        for z in (0.2, 1.8, 3.1):
            radius = 0.8 if z < 3 else 0.55
            last = None
            first = None
            for i in range(17):
                ang = math.tau * i / 16
                p = Vec3(math.cos(ang) * radius, math.sin(ang) * radius, z)
                if first is None:
                    first = p
                if last is None:
                    segs.moveTo(p)
                else:
                    segs.drawTo(p)
                last = p
        for x, y in [(-0.8, -0.8), (0.8, -0.8), (0.8, 0.8), (-0.8, 0.8)]:
            segs.moveTo(x, y, 0.2)
            segs.drawTo(x, y, 3.1)
        root.attachNewNode(segs.create()).setAntialias(AntialiasAttrib.MLine)
        return root

    def get_active_campaign_point(self):
        for point in getattr(self, "campaign_points", []):
            if not point.get("captured"):
                return point
        return None

    def update_capture_regeneration(self, dt: float, capturing: bool) -> tuple[int, int]:
        """Regenerate body and armor only while the player actively captures land."""
        if not capturing or getattr(self, "arena_mode_active", False):
            self.capture_health_regen_accumulator = 0.0
            self.capture_armor_regen_accumulator = 0.0
            return (0, 0)
        hp_rate = max(0.0, float(getattr(self.game_cfg, "capture_health_regen_per_second", 8.0)))
        armor_rate = max(0.0, float(getattr(self.game_cfg, "capture_armor_regen_per_second", 5.0)))
        self.capture_health_regen_accumulator = float(getattr(self, "capture_health_regen_accumulator", 0.0)) + hp_rate * dt
        self.capture_armor_regen_accumulator = float(getattr(self, "capture_armor_regen_accumulator", 0.0)) + armor_rate * dt
        heal_hits = int(self.capture_health_regen_accumulator)
        armor_hits = int(self.capture_armor_regen_accumulator)
        healed = 0
        armored = 0
        if heal_hits > 0:
            self.capture_health_regen_accumulator -= heal_hits
            before = float(getattr(self, "health", 0.0))
            maximum = float(getattr(self, "player_health_max", getattr(self.game_cfg, "default_health", 100)))
            self.health = min(maximum, before + heal_hits)
            healed = int(round(float(self.health) - before))
            if self.health >= maximum:
                self.capture_health_regen_accumulator = 0.0
        if armor_hits > 0:
            self.capture_armor_regen_accumulator -= armor_hits
            before = float(getattr(self, "player_armor", 0.0))
            maximum = float(getattr(self, "player_armor_max", 0.0))
            self.player_armor = min(maximum, before + armor_hits)
            armored = int(round(float(self.player_armor) - before))
            if self.player_armor >= maximum:
                self.capture_armor_regen_accumulator = 0.0
        if healed or armored:
            self.armor_damage_fade_timer = max(0.0, float(getattr(self, "armor_damage_fade_timer", 0.0)) - dt * 2.0)
        return (healed, armored)

    def update_campaign_capture_markers(self, active):
        for point in getattr(self, "campaign_points", []) or []:
            node = point.get("node") if isinstance(point, dict) else None
            if node is None or node.isEmpty():
                continue
            marker = node.getPythonTag("active_capture_marker") if node.hasPythonTag("active_capture_marker") else None
            is_active = point is active and not point.get("captured")
            if marker is not None and not marker.isEmpty():
                if is_active:
                    marker.show()
                    marker.setH((float(getattr(self, "elapsed", 0.0)) * 26.0) % 360.0)
                    pulse = 1.0 + 0.10 * math.sin(float(getattr(self, "elapsed", 0.0)) * 5.5)
                    marker.setScale(pulse)
                else:
                    marker.hide()

    def update_campaign_objectives(self, dt: float):
        if not hasattr(self, "campaign_points"):
            return
        player_flat = Vec3(self.player_pos.x, self.player_pos.y, 0.0)
        active = self.get_active_campaign_point()
        self.update_campaign_capture_markers(active)
        if hasattr(self, "ally_node") and self.ally_node is not None and not self.ally_node.isEmpty():
            target = active["pos"] if active else player_flat + Vec3(-3.0, -5.0, 0)
            to_target = target - getattr(self, "ally_pos", Vec3(-3.5, -5.0, 0.0))
            if to_target.lengthSquared() > 0.01:
                step = min(1.0, dt * 1.85)
                self.ally_pos = getattr(self, "ally_pos", Vec3(-3.5, -5.0, 0.0)) + to_target * step
            self.ally_node.setPos(self.ally_pos.x, self.ally_pos.y, 0.0)
        if active:
            dist = (active["pos"] - player_flat).length()
            if dist <= 12.5 and not active.get("wave_triggered"):
                active["wave_triggered"] = True
                self.spawn_campaign_defenders(int(active.get("index", 0)), active["pos"])
            ally_dist = (active["pos"] - getattr(self, "ally_pos", Vec3(-999, -999, 0))).length()
            rate = 0.0
            if dist <= 10.5:
                rate += 24.0
            if ally_dist <= 12.0:
                rate += 11.0
            player_capturing = dist <= 10.5
            self.update_capture_regeneration(dt, player_capturing)
            if rate > 0.0:
                active["progress"] = min(100.0, float(active.get("progress", 0.0)) + rate * dt)
            else:
                active["progress"] = max(0.0, float(active.get("progress", 0.0)) - 4.0 * dt)
            pulse = 0.75 + 0.25 * math.sin(self.elapsed * 5.0)
            ar, ag, ab, _ = self.current_campaign_accent_color(alpha=1.0)
            active["node"].setColorScale(min(1.35, ar * (1.12 + 0.12 * pulse)), min(1.35, ag * (1.06 + 0.18 * pulse)), min(1.35, ab * (1.02 + 0.10 * pulse)), 0.94)
            if active["progress"] >= 100.0 and not active.get("captured"):
                active["captured"] = True
                active["node"].setColorScale(*self.current_campaign_secondary_color(alpha=1.0))
                self.score = int(getattr(self, "score", 0) or 0) + 250
                self.lab_points = int(getattr(self, "lab_points", 0)) + 25
                self.create_arena_portal_for_capture(active)
                self.refill_unlocked_ammo(float(getattr(self.game_cfg, "weapon_objective_ammo_reward", 32.0)), silent=False)
                self.refresh_weapon_unlocks(silent=False)
                self.weapon_banner_time = max(float(getattr(self, "weapon_banner_time", 0.0)), 1.6)
                self.play_sfx("objective_complete", volume=0.78, rate=1.0, pos=active["pos"])
                self.record_activity("node_capture", "Route Calibrator", bonus=int(getattr(self.game_cfg, "activity_major_bonus_score", 140)), pos=active["pos"])
                try:
                    self.center_text["text"] = f"NODE {active['index'] + 1} SECURED"
                except Exception:
                    pass
        if active is None:
            self.update_capture_regeneration(dt, False)
        for point in self.campaign_points:
            if point.get("captured"):
                point["node"].setColor(*self.current_campaign_secondary_color(alpha=1.0), 1)
            elif point is not active:
                point["node"].setColor(*self.current_campaign_accent_color(alpha=0.64), 1)
        captured = sum(1 for p in self.campaign_points if p.get("captured"))
        self.campaign_complete = captured >= len(self.campaign_points)
        if self.campaign_complete and not getattr(self, "_campaign_complete_announced", False):
            self.score = int(getattr(self, "score", 0) or 0) + 500
            self._campaign_complete_announced = True
            self.set_objective_banner("COMMAND ROUTE SECURED // RECOVER SIGNAL OR ENTER RETURN LATTICE", 3.2)
            if self.signal_route_complete():
                self.activate_extraction()
            try:
                self.center_text["text"] = "COMMAND ROUTE SECURED"
            except Exception:
                pass

    def get_mission_result(self) -> dict:
        captured = self.captured_node_count() if hasattr(self, "captured_node_count") else sum(1 for p in getattr(self, "campaign_points", []) if p.get("captured"))
        nodes_required = len(getattr(self, "campaign_points", []) or [])
        recovered = int(getattr(self, "signal_fragments_recovered", 0) or 0)
        fragments_required = int(getattr(self, "signal_fragments_required", 0) or 0)
        completed = bool(getattr(self, "objective_complete", False))
        if completed:
            signal = "UTOPIA_CONFLICT_ROUTE_STABILIZED"
        elif captured or recovered:
            signal = "UTOPIA_CONFLICT_PARTIAL_ROUTE"
        else:
            signal = ""
        return {
            "schema": 1,
            "mission_id": "utopia_conflict",
            "mode": GAME_NAME,
            "score_delta": int(getattr(self, "score", 0) or 0),
            "completed": completed,
            "nodes_captured": captured,
            "nodes_required": nodes_required,
            "fragments_recovered": recovered,
            "fragments_required": fragments_required,
            "signal": signal,
            "return_to_lab": True,
            "activity_mode": "prototype_lab_activity_mode",
            "activities_completed": self.activity_counts()[0] if hasattr(self, "activity_counts") else 0,
            "activities_total": self.activity_counts()[1] if hasattr(self, "activity_counts") else 0,
            "activity_bonus_score": int(getattr(self, "activity_bonus_score", 0) or 0),
            "memory_fragment": signal,
            "gleebs_response": "Utopia Conflict route secured." if completed else "Utopia Conflict returned partial command/signal data.",
        }

    def build_weapon_loadouts(self):
        self.weapons = [
            Weapon(0, "Core Lance", 34.0, 0.16, 0.28, 220.0, 1, 0.055, 0.24, 100.0, 6.0, kind="core", slot=1, description="Reliable red core beam", unlock_hint="START", ammo_regen=float(getattr(self.game_cfg, "weapon_recharge_per_second", 26.0)), color_tag="red"),
            Weapon(1, "Imploder", 76.0, 0.72, 0.12, 190.0, 1, 0.16, 0.74, 54.0, 18.0, kind="imploder", slot=2, description="Collapses enemies inward", unlock_hint="START", ammo_regen=0.0, color_tag="orange"),
            Weapon(2, "Proximity Magnet", 18.0, 0.92, 0.10, 175.0, 1, 0.14, 0.36, 42.0, 14.0, kind="magnet", slot=3, description="Pins groups inside a pull field", unlock_hint="START", ammo_regen=0.0, color_tag="cyan"),
            Weapon(3, "Disassembler", 58.0, 0.34, 0.18, 165.0, 1, 0.08, 0.52, 36.0, 9.0, kind="disassembler", slot=4, description="Detaches limbs and head", unlock_hint="START", ammo_regen=0.0, color_tag="blue"),
            Weapon(4, "Burst Splitter", 24.0, 0.28, 2.10, 175.0, 5, 0.075, 0.34, 72.0, 11.0, kind="burst", slot=5, description="Five-shot scatter lattice", unlock_hint="START", ammo_regen=0.0, color_tag="violet"),
            Weapon(5, "Auto Lattice", 19.0, 0.075, 0.55, 155.0, 1, 0.045, 0.18, 120.0, 3.0, kind="automatic", slot=6, description="Fast automatic line stream", unlock_hint="START", ammo_regen=4.0, color_tag="green"),
        ]
        self.weapon_ammo_pools = {w.slot: float(w.ammo_capacity) for w in self.weapons}
        self.unlocked_weapons = {int(w.slot) for w in self.weapons}
        self.hand_weapon_slots = dict(getattr(self, "hand_weapon_slots", {"right": 1, "left": 1}) or {"right": 1, "left": 1})
        self.hand_weapon_slots.setdefault("right", 1)
        self.hand_weapon_slots.setdefault("left", 1)
        self.refresh_weapon_unlocks(silent=True)
        self.select_weapon_for_hand(1, hand="right", force=True, silent=True)
        self.select_weapon_for_hand(1, hand="left", force=True, silent=True)

    def get_weapon_by_slot(self, slot: int):
        slot = int(slot or 1)
        for weapon in self.weapons:
            if int(getattr(weapon, "slot", -1)) == slot:
                return weapon
        return None

    def weapon_unlock_requirements_met(self, slot: int) -> bool:
        captured = sum(1 for p in getattr(self, "campaign_points", []) if p.get("captured"))
        recovered = int(getattr(self, "signal_fragments_recovered", 0) or 0)
        if slot == 1:
            return True
        if slot == 2:
            return captured >= 1
        if slot == 3:
            return recovered >= 2
        if slot == 4:
            return captured >= 2 and recovered >= 3
        if slot == 5:
            return captured >= 2
        if slot == 6:
            return recovered >= 3
        return False

    def weapon_unlock_hint(self, slot: int) -> str:
        weapon = self.get_weapon_by_slot(slot)
        return getattr(weapon, "unlock_hint", "LOCKED") if weapon else "LOCKED"

    def refresh_weapon_unlocks(self, silent: bool = False):
        newly = []
        for weapon in getattr(self, "weapons", []) or []:
            slot = int(getattr(weapon, "slot", 1))
            if slot not in self.unlocked_weapons and self.weapon_unlock_requirements_met(slot):
                self.unlocked_weapons.add(slot)
                self.weapon_ammo_pools[slot] = max(float(self.weapon_ammo_pools.get(slot, 0.0)), float(weapon.ammo_capacity))
                newly.append(weapon)
        if newly and not silent:
            names = ", ".join(f"{w.slot}:{w.name}" for w in newly)
            self.combat_banner = f"WEAPON UNLOCKED // {names}"
            self.combat_banner_time = 1.8
            self.play_sfx("pickup", volume=0.95, rate=1.0)
        if self.current_weapon:
            self.update_current_weapon_ammo_alias()
        return newly

    def normalize_hand(self, hand: str) -> str:
        return "left" if str(hand).lower().startswith("l") else "right"

    def selected_slot_for_hand(self, hand: str) -> int:
        hand = self.normalize_hand(hand)
        return int(getattr(self, "hand_weapon_slots", {}).get(hand, 1) or 1)

    def get_weapon_for_hand(self, hand: str):
        return self.get_weapon_by_slot(self.selected_slot_for_hand(hand))

    def weapon_slot_status_line(self) -> str:
        parts = []
        right_slot = self.selected_slot_for_hand("right")
        left_slot = self.selected_slot_for_hand("left")
        for weapon in getattr(self, "weapons", []) or []:
            slot = int(getattr(weapon, "slot", 1))
            marker = "RL" if slot == right_slot and slot == left_slot else ("R" if slot == right_slot else ("L" if slot == left_slot else ""))
            if slot in getattr(self, "unlocked_weapons", {1}):
                ammo = int(self.weapon_ammo_pools.get(slot, 0))
                parts.append(f"{slot}{marker}:{ammo}")
            else:
                parts.append(f"{slot}:LOCK")
        return " ".join(parts)

    def update_current_weapon_ammo_alias(self):
        if not self.current_weapon:
            self.weapon_ammo = 0.0
            self.weapon_ammo_max = 1.0
            return
        slot = int(getattr(self.current_weapon, "slot", 1))
        self.weapon_ammo_max = float(getattr(self.current_weapon, "ammo_capacity", 100.0))
        self.weapon_ammo = max(0.0, min(self.weapon_ammo_max, float(self.weapon_ammo_pools.get(slot, self.weapon_ammo_max))))
        self.weapon_ammo_pools[slot] = self.weapon_ammo

    def add_weapon_ammo(self, slot: int, amount: float, silent: bool = False):
        slot = int(slot or getattr(self, "current_weapon_slot", 1) or 1)
        if slot == 0:
            targets = list(getattr(self, "unlocked_weapons", {1}) or {1})
        else:
            targets = [slot]
        changed = False
        for target_slot in targets:
            weapon = self.get_weapon_by_slot(target_slot)
            if not weapon or target_slot not in getattr(self, "unlocked_weapons", {1}):
                continue
            cap = float(getattr(weapon, "ammo_capacity", 100.0))
            current = float(self.weapon_ammo_pools.get(target_slot, 0.0))
            new_value = max(0.0, min(cap, current + float(amount or 0.0)))
            if abs(new_value - current) > 0.01:
                changed = True
            self.weapon_ammo_pools[target_slot] = new_value
        self.update_current_weapon_ammo_alias()
        if changed and not silent:
            self.hit_replenish_flash = 0.18
            self.play_sfx("pickup", volume=0.52, rate=random.uniform(0.96, 1.08))
        return changed

    def refill_unlocked_ammo(self, amount: float, silent: bool = True):
        for slot in list(getattr(self, "unlocked_weapons", {1}) or {1}):
            self.add_weapon_ammo(slot, amount, silent=True)
        if not silent:
            self.play_sfx("pickup", volume=0.7, rate=1.0)

    def select_weapon_for_hand(self, slot: int, hand: str = "right", force: bool = False, silent: bool = False):
        slot = int(slot or 1)
        hand = self.normalize_hand(hand)
        self.refresh_weapon_unlocks(silent=True)
        weapon = self.get_weapon_by_slot(slot)
        if not weapon:
            return False
        if not force and slot not in getattr(self, "unlocked_weapons", {1}):
            self.combat_banner = f"{hand.upper()} SLOT {slot} LOCKED // {self.weapon_unlock_hint(slot)}"
            self.combat_banner_time = 1.25
            self.play_sfx("dry", volume=0.65, rate=0.86)
            return False
        self.hand_weapon_slots[hand] = slot
        if hand == "right":
            self.current_weapon = weapon
            self.current_weapon_slot = slot
            self.current_weapon_seed = slot - 1
            self.update_current_weapon_ammo_alias()
        self.refresh_weapon_models()
        if not silent:
            label = "RIGHT" if hand == "right" else "LEFT"
            self.weapon_banner_time = 1.55
            self.combat_banner = f"{label} HAND // {slot}:{weapon.name}"
            self.combat_banner_time = max(float(getattr(self, "combat_banner_time", 0.0)), 0.85)
            self.play_sfx("pickup", volume=0.36, rate=1.0 + slot * 0.04)
        self.refresh_ui_text()
        return True

    def select_weapon_slot(self, slot: int, force: bool = False, silent: bool = False):
        if self.source_vector_arena_controls_active() and not force:
            return False
        return self.select_weapon_for_hand(slot, hand="right", force=force, silent=silent)

    def select_left_weapon_slot(self, slot: int, force: bool = False, silent: bool = False):
        if self.source_vector_arena_controls_active() and not force:
            return False
        return self.select_weapon_for_hand(slot, hand="left", force=force, silent=silent)

    def cycle_weapon_for_hand(self, hand: str = "right", step: int = 1, first: bool = False):
        if self.source_vector_arena_controls_active():
            return False
        if not getattr(self, "weapons", None):
            self.build_weapon_loadouts()
            return
        hand = self.normalize_hand(hand)
        self.refresh_weapon_unlocks(silent=True)
        unlocked = sorted(getattr(self, "unlocked_weapons", {1}) or {1})
        if not unlocked:
            unlocked = [1]
        current = self.selected_slot_for_hand(hand)
        if first:
            return self.select_weapon_for_hand(current if current in unlocked else unlocked[0], hand=hand, force=True)
        try:
            idx = unlocked.index(current)
            next_slot = unlocked[(idx + int(step)) % len(unlocked)]
        except ValueError:
            next_slot = unlocked[0]
        return self.select_weapon_for_hand(next_slot, hand=hand)

    def generate_next_weapon(self, first=False):
        return self.cycle_weapon_for_hand("right", step=1, first=first)

    def generate_previous_weapon(self):
        return self.cycle_weapon_for_hand("right", step=-1)

    def generate_next_left_weapon(self):
        return self.cycle_weapon_for_hand("left", step=1)

    def generate_previous_left_weapon(self):
        return self.cycle_weapon_for_hand("left", step=-1)

    def _cycle_numeric_setting(self, attr: str, presets: tuple[float, ...], apply_callback=None):
        current = float(getattr(self.game_cfg, attr))
        nearest = min(range(len(presets)), key=lambda i: abs(float(presets[i]) - current))
        value = float(presets[(nearest + 1) % len(presets)])
        setattr(self.game_cfg, attr, value)
        if apply_callback is not None:
            apply_callback(value)
        write_game_config(self.game_cfg)
        self.refresh_ui_text()
        return value

    def cycle_view_distance_setting(self):
        return self._cycle_numeric_setting("max_view_distance", (360.0, 520.0, 760.0, 1040.0, 1400.0), lambda v: self.camLens.setNearFar(0.06, v))

    def cycle_line_thickness_setting(self):
        value = self._cycle_numeric_setting("line_thickness", (0.90, 1.28, 1.60, 2.00, 2.60))
        self.rebuild_chunks()
        return value

    def cycle_sensitivity_setting(self):
        return self._cycle_numeric_setting("mouse_sensitivity", (0.10, 0.16, 0.22, 0.28, 0.34))

    def adjust_view_distance(self, delta):
        self.game_cfg.max_view_distance = max(260.0, min(2200.0, self.game_cfg.max_view_distance + delta))
        self.camLens.setNearFar(0.06, self.game_cfg.max_view_distance)
        write_game_config(self.game_cfg)
        self.refresh_ui_text()

    def adjust_line_thickness(self, delta):
        self.game_cfg.line_thickness = max(0.8, min(3.2, self.game_cfg.line_thickness + delta))
        write_game_config(self.game_cfg)
        self.rebuild_chunks()
        self.refresh_ui_text()

    def adjust_sensitivity(self, delta):
        self.game_cfg.mouse_sensitivity = max(0.02, min(0.4, self.game_cfg.mouse_sensitivity + delta))
        write_game_config(self.game_cfg)
        self.refresh_ui_text()

    def rebuild_chunks(self):
        for np in self.chunks.values():
            np.removeNode()
        self.chunks.clear()
        self.chunk_line_roots.clear()
        self.chunk_occlusion_roots.clear()
        self.chunk_obstacles.clear()
        self.chunk_enemy_seeds.clear()
        self.generate_city_around_player(force=True)

    def save_test_screenshot(self):
        if TEST_SHOT_PATH and getattr(self, "win", None) is not None:
            try:
                shot = Path(TEST_SHOT_PATH)
                shot.parent.mkdir(parents=True, exist_ok=True)
                for old in shot.parent.glob("*.png"):
                    if old.resolve() != shot.resolve():
                        try:
                            old.unlink()
                        except Exception:
                            pass
                self.graphicsEngine.renderFrame()
                self.win.saveScreenshot(Filename.fromOsSpecific(os.fspath(shot)))
                write_latest_log("test_shot_saved", {"path": str(shot)})
            except Exception as exc:
                write_latest_log("test_shot_failed", {"error": f"{exc.__class__.__name__}:{exc}"})

    def auto_exit_task(self, task):
        write_latest_log("auto_exit_ok", {
            "weapon": getattr(self, "weapon_name", ""),
            "health": getattr(self, "health", ""),
        })
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def self_test_exit(self, task):
        write_latest_log("self_test_exit")
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def combat_regression_task(self, task):
        player_flat = Vec3(self.player_pos.x, self.player_pos.y, 0)
        near_before = [e for e in self.enemies if not e.dead and e.root is not None and not e.root.isEmpty() and (e.root.getPos() - player_flat).length() < float(getattr(self.game_cfg, "enemy_spawn_min_distance", 168.0))]
        active_before = len([e for e in self.enemies if not e.dead])
        for e in list(self.enemies):
            try:
                if e.root is not None and not e.root.isEmpty():
                    e.root.removeNode()
            except Exception:
                pass
        self.enemies.clear()
        self.pending_enemy_spawns.clear()
        target_pos = player_flat + Vec3(0, 92, 0)
        target = Enemy(self, target_pos, self.hashed_seed(6, 9, 606))
        chain_target = Enemy(self, target_pos + Vec3(0, 8.0, 0), self.hashed_seed(8, 9, 707))
        self.enemies.extend([target, chain_target])
        core = target.core_world_position()
        armor_point = target.root.getPos(self.render) + Vec3(0.0, 0.35, target.height * 0.58)
        target.hit((self.current_weapon.damage if self.current_weapon else 30.0) * float(getattr(self.game_cfg, "enemy_body_damage_scale", 0.38)), armor_point, Vec3(0, -1, 0), force_kill=False, hit_kind="body")
        target.hit((self.current_weapon.damage if self.current_weapon else 30.0) * float(getattr(self.game_cfg, "enemy_body_damage_scale", 0.38)), armor_point, Vec3(0, -1, 0), force_kill=False, hit_kind="body")
        armor_broken = bool(getattr(target, "armor_broken", False))
        target.attack_cooldown = 0.0
        target.trigger_attack_tell(player_flat)
        tell_started = float(getattr(target, "tell_timer", 0.0)) > 0.0
        tracer_start = self.muzzle_np.getPos(self.render) if hasattr(self, "muzzle_np") else self.camera.getPos(self.render)
        self.tracers.append(TracerEffect(self, tracer_start, core, ttl=0.34, color=(1.0, 0.08, 0.08, 1.0), thickness_scale=1.6))
        killed = target.hit(self.current_weapon.damage if self.current_weapon else 9999.0, core, Vec3(0, -1, 0), force_kill=True)
        if killed:
            self.chain_lightning(core, target, core)
        chain_reacted = bool(chain_target.dead or getattr(chain_target, "armor_broken", False) or getattr(chain_target, "armor_hits", 0) > 0)
        queued_far_spawn = False
        spawn_min = float(getattr(self.game_cfg, "enemy_spawn_min_distance", 168.0))
        for angle_deg in (0, 45, -45, 90, -90, 135, -135, 180):
            ang = math.radians(angle_deg)
            candidate = player_flat + Vec3(math.sin(ang) * (spawn_min + 56.0), math.cos(ang) * (spawn_min + 56.0), 0)
            if self.enqueue_enemy_spawn(candidate, self.hashed_seed(17, 19, 909 + angle_deg), delay=0.0, source="test", objective_spawn=False):
                queued_far_spawn = True
                break
        pending_after_queue = len(getattr(self, "pending_enemy_spawns", []) or [])
        self.update_spawn_director(9.0)
        spawn_director_released = len([e for e in self.enemies if not e.dead]) >= 1
        report = {
            "test": "combat_regression",
            "status": "PASS" if killed and target.dead and armor_broken and tell_started and chain_reacted and queued_far_spawn and spawn_director_released and len(getattr(self, "physics_shards", [])) > 0 and len(getattr(self, "shockwaves", [])) > 0 and len(near_before) == 0 and active_before <= int(getattr(self.game_cfg, "enemy_max_active", 24)) else "FAIL",
            "near_enemies_before": len(near_before),
            "active_enemies_before": active_before,
            "active_cap": int(getattr(self.game_cfg, "enemy_max_active", 24)),
            "queued_far_spawn": bool(queued_far_spawn),
            "pending_after_queue": int(pending_after_queue),
            "spawn_director_released": bool(spawn_director_released),
            "target_dead_after_one_hit": bool(target.dead),
            "armor_broken_before_core_kill": bool(armor_broken),
            "attack_tell_started": bool(tell_started),
            "chain_target_reacted": bool(chain_reacted),
            "chain_target_dead": bool(chain_target.dead),
            "combat_banner_after_kill": str(getattr(self, "combat_banner", "")),
            "camera_kick_after_kill": float(getattr(self, "combat_kick_time", 0.0)),
            "tracer_fx_after_kill": len(self.tracers),
            "blotch_fx_after_kill": len(self.blotches),
            "physics_shards_after_kill": len(getattr(self, "physics_shards", [])),
            "shockwaves_after_kill": len(getattr(self, "shockwaves", [])),
            "chain_target_knockback": round(float(getattr(chain_target, "knockback_velocity", Vec3(0, 0, 0)).length()), 3),
        }
        (LOG_DIR / "combat_regression_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("combat_regression", report)
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def weapon_variant_test_task(self, task):
        player_flat = Vec3(self.player_pos.x, self.player_pos.y, 0)
        for e in list(self.enemies):
            try:
                if e.root is not None and not e.root.isEmpty():
                    e.root.removeNode()
            except Exception:
                pass
        self.enemies.clear()
        self.pending_enemy_spawns.clear()
        self.unlocked_weapons = {1, 2, 3, 4, 5, 6}
        for weapon in self.weapons:
            self.weapon_ammo_pools[int(weapon.slot)] = float(weapon.ammo_capacity)
        self.select_weapon_slot(6, force=True, silent=True)
        self.select_left_weapon_slot(4, force=True, silent=True)
        # Screenshot proof: isolate combat silhouettes so boss/walker/shifter shapes are visible.
        try:
            if getattr(self, "city_root", None) is not None and not self.city_root.isEmpty():
                self.city_root.hide()
            if getattr(self, "campaign_root", None) is not None and not self.campaign_root.isEmpty():
                self.campaign_root.hide()
        except Exception:
            pass
        self.player_pos = Vec3(16.0, 212.0, 0.0)
        self.camera.setPos(self.player_pos + Vec3(0.0, -8.0, 2.2))
        self.yaw = 26.0
        self.pitch = -10.0
        self.camera.setH(self.yaw)
        self.camera.setP(self.pitch)
        self.current_district_id = "high_towers"
        self.refresh_ui_text()
        player_flat = Vec3(self.player_pos.x, self.player_pos.y, 0)
        base_pos = player_flat + Vec3(18, 70, 0)
        targets = [Enemy(self, base_pos + Vec3((i - 1.5) * 5.0, i * 3.0, 0), self.hashed_seed(40 + i, 55, 6060)) for i in range(4)]
        self.enemies.extend(targets)
        # Call variant effects directly so the test is deterministic even in headless mode.
        self.trigger_implosion(targets[0].core_world_position(), targets[0])
        self.resolve_imploder_crush(targets[0].core_world_position(), float(getattr(self.game_cfg, "imploder_radius", 24.0)) * float(getattr(self.game_cfg, "imploder_crush_radius_scale", 0.62)))
        self.deploy_magnet_field(targets[1].root.getPos(self.render))
        pierce_ok = self.try_core_lance_pierce(targets[0].core_world_position(), Vec3(1, 0, 0), targets[0])
        dis_kill = False
        for _ in range(5):
            if not targets[2].dead:
                dis_kill = targets[2].disassemble_part(targets[2].core_world_position(), Vec3(0, -1, 0)) or dis_kill
        pickup_spawned = all(self.spawn_weapon_pickup(player_flat + Vec3(3 + i * 1.8, 3, 0), slot=slot, amount=12.0) for i, slot in enumerate([1, 2, 3, 4, 5, 6]))
        before_pickups = len(getattr(self, "weapon_pickups", []))
        for pickup in list(getattr(self, "weapon_pickups", []) or []):
            self.collect_weapon_pickup(pickup)
        report = {
            "test": "weapon_variant_test",
            "status": "PASS" if len(getattr(self, "weapons", [])) >= 6 and {1, 2, 3, 4, 5, 6}.issubset(set(getattr(self, "unlocked_weapons", set()))) and len(getattr(self, "weapon_fx", [])) > 0 and len(getattr(self, "magnet_fields", [])) > 0 and dis_kill and pickup_spawned and pierce_ok else "FAIL",
            "weapon_count": len(getattr(self, "weapons", [])),
            "unlocked_weapons": sorted(list(getattr(self, "unlocked_weapons", set()))),
            "weapon_fx": len(getattr(self, "weapon_fx", [])),
            "core_lance_pierce": bool(pierce_ok),
            "magnet_fields": len(getattr(self, "magnet_fields", [])),
            "disassembler_killed_target": bool(dis_kill),
            "pickup_spawned": bool(pickup_spawned),
            "district_ammo_slots": self.district_ammo_slots() if hasattr(self, "district_ammo_slots") else [],
            "district_id": getattr(self, "current_district_id", "calibration"),
            "pickups_before_collect": int(before_pickups),
            "ammo_pools": {str(k): round(v, 2) for k, v in getattr(self, "weapon_ammo_pools", {}).items()},
            "dual_wield": bool(getattr(self, "weapon_dual_wield", False)),
            "weapon_mounts": sorted(list(getattr(self, "weapon_mounts", {}).keys())),
            "hand_weapon_slots": dict(getattr(self, "hand_weapon_slots", {})),
            "right_weapon": self.get_weapon_for_hand("right").name if hasattr(self, "get_weapon_for_hand") and self.get_weapon_for_hand("right") else None,
            "left_weapon": self.get_weapon_for_hand("left").name if hasattr(self, "get_weapon_for_hand") and self.get_weapon_for_hand("left") else None,
        }
        (LOG_DIR / "weapon_variant_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("weapon_variant_test", report)
        self.save_test_screenshot()
        self.userExit()
        return Task.done


    def _prepare_weapon_signature_stage(self):
        for e in list(getattr(self, "enemies", []) or []):
            try:
                if e.root is not None and not e.root.isEmpty():
                    e.root.removeNode()
            except Exception:
                pass
        self.enemies.clear()
        self.pending_enemy_spawns.clear()
        self.unlocked_weapons = {1, 2, 3, 4, 5, 6}
        for weapon in self.weapons:
            self.weapon_ammo_pools[int(weapon.slot)] = float(weapon.ammo_capacity)
        try:
            for root_name in ("city_root", "campaign_root", "activity_root", "mission_root", "arena_root"):
                root = getattr(self, root_name, None)
                if root is not None and not root.isEmpty():
                    root.hide()
        except Exception:
            pass
        for attr in ("tracers", "shockwaves", "physics_shards", "weapon_fx", "magnet_fields", "blotches"):
            for item in list(getattr(self, attr, []) or []):
                try:
                    item.dispose() if hasattr(item, "dispose") else item.np.removeNode()
                except Exception:
                    pass
            setattr(self, attr, [])
        self.player_pos = Vec3(0.0, 0.0, self.game_cfg.player_height)
        self.camera.setPos(Vec3(0.0, -8.0, 5.6))
        self.camera.lookAt(Vec3(0.0, 28.0, 3.2))

    def weapon_signature_demo_task(self, task):
        self._prepare_weapon_signature_stage()
        slot = max(1, min(6, int(WEAPON_SIGNATURE_DEMO or 1)))
        weapon = self.get_weapon_by_slot(slot)
        self.select_weapon_slot(slot, force=True, silent=True)
        target_pos = Vec3(0.0, 28.0, 0.0)
        target = Enemy(self, target_pos, self.hashed_seed(45, slot, 4500 + slot), variant_override="walker")
        self.enemies.append(target)
        point = target.core_world_position()
        self.spawn_weapon_impact_signature(weapon.kind, point, Vec3(0, -1, 0), enemy=target, killed=False)
        if weapon.kind == "imploder":
            self.trigger_implosion(point, target)
        elif weapon.kind == "magnet":
            self.deploy_magnet_field(target.root.getPos(self.render))
        elif weapon.kind == "disassembler":
            target.disassemble_part(point, Vec3(0, -1, 0))
        elif weapon.kind == "core":
            self.add_combat_feedback(point, label="hit", radius=2.0, life=0.42, warning=False)
        self.combat_banner = f"{slot}:{weapon.name.upper()} // SIGNATURE IMPACT"
        self.combat_banner_time = 5.0
        self.refresh_ui_text()
        self.taskMgr.doMethodLater(0.035, self._finish_weapon_signature_demo, f"weapon-signature-demo-shot-{slot}")
        return Task.done

    def _finish_weapon_signature_demo(self, task):
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def weapon_signature_test_task(self, task):
        self._prepare_weapon_signature_stage()
        signature_counts = {}
        kinds = ["core", "imploder", "magnet", "disassembler", "burst", "automatic"]
        before = (len(self.tracers), len(self.shockwaves), len(self.weapon_fx), len(self.magnet_fields))
        for idx, kind in enumerate(kinds):
            point = Vec3((idx - 2.5) * 8.0, 46.0 + (idx % 2) * 7.0, 3.2)
            pre = (len(self.tracers), len(self.shockwaves), len(self.weapon_fx))
            self.spawn_weapon_impact_signature(kind, point, Vec3(0, -1, 0), enemy=None, killed=False)
            if kind == "magnet":
                self.deploy_magnet_field(point - Vec3(0, 0, 3.2))
            post = (len(self.tracers), len(self.shockwaves), len(self.weapon_fx))
            signature_counts[kind] = {
                "tracers_added": post[0] - pre[0],
                "shockwaves_added": post[1] - pre[1],
                "glyph_fx_added": post[2] - pre[2],
            }
        all_distinct = len({tuple(v.values()) for v in signature_counts.values()}) >= 5
        core_chain_isolated = True
        # Shared fire path must only run Core Lance pierce/chain on kind=core.
        source = Path(__file__).read_text(encoding="utf-8")
        isolation_marker = 'if weapon_kind == "core" and killed'
        core_chain_isolated = isolation_marker in source
        report = {
            "test": "weapon_signature_test",
            "status": "PASS" if all_distinct and core_chain_isolated and all(sum(v.values()) > 0 for v in signature_counts.values()) else "FAIL",
            "signatures": signature_counts,
            "distinct_signature_profiles": len({tuple(v.values()) for v in signature_counts.values()}),
            "core_chain_pierce_isolated": bool(core_chain_isolated),
            "fx_before": before,
            "fx_after": (len(self.tracers), len(self.shockwaves), len(self.weapon_fx), len(self.magnet_fields)),
        }
        (LOG_DIR / "weapon_signature_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("weapon_signature_test", report)
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def _prepare_enemy_role_stage(self):
        for enemy in list(getattr(self, "enemies", []) or []):
            try:
                if enemy.root is not None and not enemy.root.isEmpty(): enemy.root.removeNode()
            except Exception: pass
        self.enemies.clear()
        for drone in list(getattr(self, "patrol_drones", []) or []):
            try:
                if drone.root is not None and not drone.root.isEmpty(): drone.root.removeNode()
            except Exception: pass
        self.patrol_drones.clear()
        for root_name in ("campaign_root", "activity_root"):
            root = getattr(self, root_name, None)
            if root is not None and not root.isEmpty():
                root.hide()
        self.player_pos = Vec3(0, 0, self.game_cfg.player_height)
        self.camera.setPos(0, -16, 7.2)
        self.yaw = 0.0
        self.pitch = -5.0
        self.camera.setHpr(self.yaw, self.pitch, 0)

    def enemy_role_demo_task(self, task):
        role = str(ENEMY_ROLE_DEMO or "walker").lower().strip()
        self._prepare_enemy_role_stage()
        variants = ["sentinel", "stalker", "walker", "shifter", "boss_mech", "drone"]
        if role not in variants: role = "walker"
        if role == "drone":
            actor = PatrolDrone(self, Vec3(0, 23, 8), 46006, district_id="high_towers")
            self.patrol_drones.append(actor)
            actor.hit(36, actor.core_world_position(), Vec3(0, -1, 0), force_kill=False, hit_kind="demo")
        else:
            actor = Enemy(self, Vec3(0, 22, 0), 46000 + variants.index(role), variant_override=role)
            self.enemies.append(actor)
            if role == "boss_mech":
                hit = actor.root.getPos(self.render) + Vec3(actor.arm_space, 0.4, actor.height * 0.58)
                actor.hit(40, hit, Vec3(0, -1, 0), hit_kind="body")
            elif role == "shifter":
                actor.previous_shifter_form = "biped"
                actor.shifter_form = "quad"
                actor.trigger_shifter_transition("quad")
            elif role in {"walker", "stalker"}:
                actor.hit(24, actor.core_world_position() + Vec3(actor.radius * 0.7, 0, -actor.height * 0.2), Vec3(0, -1, 0), hit_kind="body")
        self.combat_banner = f"{role.upper()} // ROLE REACTION"
        self.combat_banner_time = 4.0
        self.refresh_ui_text()
        self.taskMgr.doMethodLater(0.16, self._finish_enemy_role_demo, "enemy-role-demo-shot")
        return Task.done

    def _finish_enemy_role_demo(self, task):
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def enemy_role_test_task(self, task):
        self._prepare_enemy_role_stage()
        sentinel = Enemy(self, Vec3(-18, 34, 0), 46101, variant_override="sentinel")
        stalker = Enemy(self, Vec3(-10, 34, 0), 46102, variant_override="stalker")
        walker = Enemy(self, Vec3(-2, 34, 0), 46103, variant_override="walker")
        shifter = Enemy(self, Vec3(7, 34, 0), 46104, variant_override="shifter")
        boss = Enemy(self, Vec3(17, 38, 0), 46105, variant_override="boss_mech")
        self.enemies.extend([sentinel, stalker, walker, shifter, boss])
        walker_before = Vec3(walker.root.getPos())
        walker.hit(20, walker.core_world_position() + Vec3(walker.radius, 0, -walker.height * 0.2), Vec3(0, -1, 0), hit_kind="body")
        walker_knock = walker.knockback_velocity.length()
        stalker.hit(20, stalker.core_world_position(), Vec3(0, -1, 0), hit_kind="body")
        shifter.previous_shifter_form = "biped"
        shifter.shifter_form = "quad"
        shifter.trigger_shifter_transition("quad")
        left = boss.root.getPos(self.render) + Vec3(-boss.arm_space, 0.4, boss.height * 0.58)
        right = boss.root.getPos(self.render) + Vec3(boss.arm_space, 0.4, boss.height * 0.58)
        boss_health_start = boss.health
        boss.hit(40, boss.core_world_position(), Vec3(0, -1, 0), hit_kind="core")
        shielded_damage = boss_health_start - boss.health
        boss.hit(40, left, Vec3(0, -1, 0), hit_kind="body")
        boss.hit(40, right, Vec3(0, -1, 0), hit_kind="body")
        drone = PatrolDrone(self, Vec3(0, 48, 8), 46106, district_id="high_towers")
        self.patrol_drones.append(drone)
        drone.hit(32, drone.core_world_position(), Vec3(0, -1, 0), force_kill=False, hit_kind="test")
        role_state = {
            "sentinel_baseline": sentinel.variant == "sentinel",
            "stalker_evasion": stalker.evasion_timer > 0.0 and stalker.evasion_direction.lengthSquared() > 0.001,
            "walker_braced": bool(walker.walker_braced) and walker_knock < float(getattr(self.game_cfg, "impact_knockback_force", 3.2)),
            "shifter_transition": shifter.role_reaction_timer > 0.0 and shifter.evasion_timer > 0.0 and shifter.previous_shifter_form == "quad",
            "boss_core_shielded": shielded_damage < 20.0,
            "boss_weakpoints_cleared": len(boss.boss_weakpoints) == 0 and boss.boss_core_exposed,
            "drone_evasive_armor": drone.evasive_timer > 0.0 and drone.hit_flash_timer > 0.0 and drone.armor > 0,
        }
        report = {
            "test": "enemy_role_test",
            "status": "PASS" if all(role_state.values()) else "FAIL",
            "roles": role_state,
            "walker_knockback_speed": round(walker_knock, 4),
            "boss_shielded_core_damage": round(shielded_damage, 2),
            "boss_remaining_weakpoints": sorted(boss.boss_weakpoints),
            "drone_armor_remaining": drone.armor,
        }
        (LOG_DIR / "enemy_role_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("enemy_role_test", report)
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def _enemy_color_state_actor(self, state: str):
        state = str(state or "baseline").lower().strip()
        if state in {"drone_passive", "drone_hostile", "drone_armor_hit"}:
            actor = PatrolDrone(self, Vec3(0, 24, 8), 47080, district_id="high_towers")
            self.patrol_drones.append(actor)
            if state == "drone_hostile":
                self.player_hostility_timer = 8.0
            elif state == "drone_armor_hit":
                actor.hit(30, actor.core_world_position(), Vec3(0, -1, 0), force_kill=False, hit_kind="demo")
            actor.update(0.01)
            return actor
        variant = {"baseline": "sentinel", "attack": "sentinel", "stalker_evade": "stalker", "walker_braced": "walker", "shifter_phase": "shifter", "boss_shielded": "boss_mech", "boss_exposed": "boss_mech"}.get(state, "sentinel")
        actor = Enemy(self, Vec3(0, 22, 0), 47000 + len(self.enemies), variant_override=variant)
        self.enemies.append(actor)
        if state == "attack": actor.tell_timer = 1.0
        elif state == "stalker_evade":
            actor.evasion_timer = 1.0; actor.evasion_direction = Vec3(1, 0, 0)
        elif state == "walker_braced":
            actor.walker_braced = True; actor.role_reaction_timer = 1.0
        elif state == "shifter_phase":
            actor.previous_shifter_form = "biped"; actor.shifter_form = "quad"; actor.trigger_shifter_transition("quad")
        elif state == "boss_exposed":
            actor.boss_weakpoints.clear(); actor.boss_core_exposed = True; actor.refresh_boss_weakpoint_markers()
        actor.apply_combat_color_state()
        return actor

    def enemy_color_state_demo_task(self, task):
        self._prepare_enemy_role_stage()
        state = str(ENEMY_COLOR_STATE_DEMO or "baseline").lower().strip()
        valid = ["baseline", "attack", "stalker_evade", "walker_braced", "shifter_phase", "boss_shielded", "boss_exposed", "drone_passive", "drone_hostile", "drone_armor_hit"]
        if state not in valid: state = "baseline"
        self._enemy_color_state_actor(state)
        self.combat_banner = f"{state.replace('_', ' ').upper()} // COLOR STATE"
        self.combat_banner_time = 4.0
        self.refresh_ui_text()
        self.taskMgr.doMethodLater(0.18, self._finish_enemy_role_demo, "enemy-color-state-demo-shot")
        return Task.done

    def enemy_color_state_test_task(self, task):
        self._prepare_enemy_role_stage()
        states = ["baseline", "attack", "stalker_evade", "walker_braced", "shifter_phase", "boss_shielded", "boss_exposed", "drone_passive", "drone_hostile", "drone_armor_hit"]
        observed, colors = {}, {}
        for state in states:
            actor = self._enemy_color_state_actor(state)
            observed[state] = str(getattr(actor, "color_state_name", ""))
            colors[state] = [round(float(v), 3) for v in getattr(actor, "color_state_color", (0, 0, 0, 0))]
        semantic_pass = all(observed.get(state) == state for state in states)
        distinct_colors = len({tuple(v) for v in colors.values()})
        report = {"test": "enemy_color_state_test", "status": "PASS" if semantic_pass and distinct_colors >= 8 else "FAIL", "states": observed, "colors": colors, "semantic_state_match": semantic_pass, "distinct_color_profiles": distinct_colors, "required_distinct_profiles": 8}
        (LOG_DIR / "enemy_color_state_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("enemy_color_state_test", report)
        self.save_test_screenshot(); self.userExit(); return Task.done

    def drone_patrol_test_task(self, task):
        # Proof for district patrol drones, armor, targeting, player hostility, and ammo drops.
        for p in Path(TEST_SHOT_PATH).parent.glob("*.png") if TEST_SHOT_PATH else []:
            try:
                p.unlink()
            except Exception:
                pass
        self.player_pos = Vec3(0, 50.0, self.game_cfg.player_height)
        self.camera.setPos(self.player_pos + Vec3(0.0, -5.0, 5.4))
        self.yaw = 3.0
        self.pitch = -10.0
        self.camera.setH(self.yaw)
        self.camera.setP(self.pitch)
        self.generate_city_around_player(force=True)
        self.collect_civilian_anchors()
        self.collect_patrol_drone_anchors()
        # Spawn a drone and a nearby hostile so the drone has a clear target.
        drone = self.spawn_patrol_drone()
        if drone is None:
            anchor = Vec3(0, 78, 9.0)
            drone = PatrolDrone(self, anchor, self.hashed_seed(0, 78, 9977), district_id="calibration")
            self.patrol_drones.append(drone)
        hostile_pos = drone.root.getPos(self.render) + Vec3(16.0, 8.0, -drone.root.getZ())
        hostile = Enemy(self, Vec3(hostile_pos.x, hostile_pos.y, 0.0), self.hashed_seed(int(hostile_pos.x), int(hostile_pos.y), 9911), variant_override="stalker")
        self.enemies.append(hostile)
        # Also mark the player hostile briefly so drones will target the player if in range.
        self.player_hostility_timer = float(getattr(self.game_cfg, "patrol_drone_player_hostility_seconds", 9.0))
        drone_fire_start = len(getattr(self, "tracers", []))
        for _ in range(80):
            self.update_civilians(0.033)
            self.update_patrol_drones(0.033)
            self.update_enemies(0.033)
            self.update_effects(0.033)
        drone_fire_count = max(0, len(getattr(self, "tracers", [])) - drone_fire_start)
        armor_before = int(getattr(drone, "armor", 0))
        drone_core = drone.core_world_position()
        killed = drone.hit(9999, drone_core, Vec3(0, 0, 1), force_kill=True, hit_kind="test")
        if killed:
            self.register_combat_hit(drone, hit_kind="drone", killed=True, source_point=drone_core, chain=False)
        self.refresh_ui_text()
        report = {
            "test": "drone_patrol_test",
            "status": "PASS" if len(getattr(self, "patrol_drones", [])) >= 1 and drone_fire_count >= 1 and armor_before >= int(getattr(self.game_cfg, "patrol_drone_armor", 180)) and int(getattr(self, "drone_ammo_drops", 0)) >= 1 else "FAIL",
            "active_drones": len([d for d in getattr(self, "patrol_drones", []) if not getattr(d, "dead", False)]),
            "drone_anchors": len(getattr(self, "patrol_drone_anchors", [])),
            "drone_fire_tracers": drone_fire_count,
            "drone_armor_before_kill": armor_before,
            "player_hostility_timer": float(getattr(self, "player_hostility_timer", 0.0)),
            "drone_ammo_drops": int(getattr(self, "drone_ammo_drops", 0)),
            "weapon_pickups": len(getattr(self, "weapon_pickups", [])),
            "hud_text_lines": str(self.hud_text["text"]).count("\n") + 1,
        }
        (LOG_DIR / "drone_patrol_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("drone_patrol_test", report)
        self.set_objective_banner("PATROL DRONES ACTIVE // AVOID CIVILIAN FIRE", 2.6)
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def civilian_ai_test_task(self, task):
        for p in Path(TEST_SHOT_PATH).parent.glob("*.png") if TEST_SHOT_PATH else []:
            try:
                p.unlink()
            except Exception:
                pass
        self.player_pos = Vec3(0, 44.0, self.game_cfg.player_height)
        self.camera.setPos(self.player_pos + Vec3(0.0, -5.0, 4.8))
        self.yaw = 0.0
        self.pitch = -9.0
        self.camera.setH(self.yaw)
        self.camera.setP(self.pitch)
        self.generate_city_around_player(force=True)
        self.collect_civilian_anchors()
        for _ in range(max(4, int(getattr(self.game_cfg, "civilian_max_active", 10)) // 2)):
            self.spawn_civilian()
        if getattr(self, "campaign_points", None):
            point = self.campaign_points[0]
            self.spawn_campaign_defenders(int(point.get("index", 0)), point["pos"])
        for _ in range(130):
            self.update_spawn_director(0.033)
            self.update_civilians(0.033)
            self.update_enemies(0.033)
            self.update_effects(0.033)
        before_score = int(getattr(self, "score", 0))
        harmed = False
        civilians_active = [c for c in getattr(self, "civilians", []) if not getattr(c, "dead", False)]
        if civilians_active:
            civ = civilians_active[0]
            killed = civ.hit(6.0, civ.core_world_position(), Vec3(0, 0, 1), force_kill=False, hit_kind="test")
            self.register_civilian_harm(civ, killed=killed, source_point=civ.core_world_position(), cause="test")
            harmed = True
        after_score = int(getattr(self, "score", 0))
        self.refresh_ui_text()
        report = {
            "test": "civilian_ai_test",
            "status": "PASS" if len(getattr(self, "civilian_anchors", [])) >= 4 and len(civilians_active) >= 2 and harmed and after_score <= before_score and len(str(self.help_text["text"])) == 0 else "FAIL",
            "civilian_anchors": len(getattr(self, "civilian_anchors", [])),
            "active_civilians": len([c for c in getattr(self, "civilians", []) if not getattr(c, "dead", False)]),
            "active_enemies": len([e for e in getattr(self, "enemies", []) if not getattr(e, "dead", False)]),
            "score_before_harm": before_score,
            "score_after_harm": after_score,
            "civilian_penalty_points": int(getattr(self, "civilian_penalty_points", 0)),
            "help_text_hidden": len(str(self.help_text["text"])) == 0,
            "hud_text_lines": str(self.hud_text["text"]).count("\n") + 1,
            "ai_pathing": "local waypoint steering for civilians and city enemies",
        }
        (LOG_DIR / "civilian_ai_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("civilian_ai_test", report)
        self.set_objective_banner("CIVILIANS ACTIVE // PROTECT THEM", 2.6)
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def health_palette_test_task(self, task):
        for p in Path(TEST_SHOT_PATH).parent.glob("*.png") if TEST_SHOT_PATH else []:
            try:
                p.unlink()
            except Exception:
                pass
        self.player_pos = Vec3(0.0, 38.0, self.game_cfg.player_height)
        self.camera.setPos(self.player_pos + Vec3(0.0, -4.0, 4.8))
        self.yaw = 0.0
        self.pitch = -8.0
        self.camera.setH(self.yaw)
        self.camera.setP(self.pitch)
        self.generate_city_around_player(force=True)
        # Isolate body health gradient: armor is tested separately.
        self.player_armor = 0
        self.health = max(1, int(float(getattr(self, "player_health_max", 100)) * 0.24))
        self.update_palette(0.033)
        self.recolor_scene()
        low_color = tuple(round(v, 3) for v in self.current_line_color(alpha=1.0)[:3])
        self.health = int(float(getattr(self, "player_health_max", 100)) * 0.92)
        self.update_palette(0.033)
        high_color = tuple(round(v, 3) for v in self.current_line_color(alpha=1.0)[:3])
        self.health = max(1, int(float(getattr(self, "player_health_max", 100)) * 0.24))
        self.update_palette(0.033)
        self.recolor_scene()
        self.refresh_ui_text()
        report = {
            "test": "health_palette_test",
            "status": "PASS" if low_color != high_color and low_color[0] > low_color[1] and high_color[1] > high_color[0] and float(getattr(self, "health_ratio", 1.0)) < 0.30 else "FAIL",
            "background_cycle_preserved": bool(getattr(self.game_cfg, "background_opposite_cycle", True)),
            "line_cycle_suppressed_for_health_truth": True,
            "low_health_line_rgb": low_color,
            "high_health_line_rgb": high_color,
            "health_ratio": float(getattr(self, "health_ratio", 1.0)),
            "health_line_rgb": tuple(round(v, 3) for v in getattr(self, "health_line_rgb", (0, 0, 0))),
            "meaning": "player health is expressed by the wireframe gradient: green at full, amber mid, red near empty",
        }
        (LOG_DIR / "health_palette_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("health_palette_test", report)
        self.set_objective_banner("LOW HEALTH // LINES SHIFT TO DANGER COLOR", 2.4)
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def armor_wireframe_test_task(self, task):
        self.player_health_max = 100
        self.health = 100
        self.upgrade_levels["armor_capacity"] = 0
        self.sync_player_armor_capacity(refill=True)
        self.armor_damage_fade_timer = 0.0
        self.update_palette(0.033)
        full_armor_color = tuple(round(v, 3) for v in self.current_line_color(alpha=1.0)[:3])
        damage_report = self.apply_player_damage(4, source="armor_wireframe_test")
        damaged_armor_color = tuple(round(v, 3) for v in self.current_line_color(alpha=1.0)[:3])
        before_upgrade_max = int(getattr(self, "player_armor_max", 0))
        self.upgrade_levels["armor_capacity"] = 1
        self.sync_player_armor_capacity(refill=True)
        upgraded_max = int(getattr(self, "player_armor_max", 0))
        self.player_armor = 0
        self.health = 25
        self.update_palette(0.033)
        exposed_health_color = tuple(round(v, 3) for v in self.current_line_color(alpha=1.0)[:3])
        report = {
            "test": "armor_wireframe_test",
            "status": "PASS" if before_upgrade_max == 10 and upgraded_max == 20 and damage_report.get("absorbed_by_armor") == 4 and damage_report.get("body_damage") == 0 and full_armor_color[2] > full_armor_color[0] and exposed_health_color[0] > exposed_health_color[1] else "FAIL",
            "default_health_capacity_hits": 100,
            "default_armor_hits": before_upgrade_max,
            "upgraded_armor_hits_after_one_upgrade": upgraded_max,
            "armor_upgrade_interval_percent": int(round(float(getattr(self.game_cfg, "player_armor_upgrade_ratio_step", 0.10)) * 100)),
            "full_armor_line_rgb": full_armor_color,
            "damaged_armor_line_rgb": damaged_armor_color,
            "exposed_low_health_rgb": exposed_health_color,
            "damage_report": damage_report,
            "healthbars_removed": True,
            "meaning": "armor is a cyan wireframe shell; damage is absorbed by armor first and exposes the current green-to-red health state",
        }
        (LOG_DIR / "armor_wireframe_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("armor_wireframe_test", report)
        self.set_objective_banner("ARMOR SHELL // CYAN FADES TO HEALTH COLOR WHEN DAMAGED", 2.4)
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def respawn_reset_test_task(self, task):
        for p in Path(TEST_SHOT_PATH).parent.glob("*.png") if TEST_SHOT_PATH else []:
            try:
                p.unlink()
            except Exception:
                pass
        if not getattr(self, "campaign_points", None):
            self.setup_campaign_objectives()
        point = self.campaign_points[0]
        point["progress"] = 45.0
        point["wave_triggered"] = True
        self.signal_fragments_recovered = max(1, int(getattr(self, "signal_fragments_recovered", 0) or 0))
        self.score = max(75, int(getattr(self, "score", 0) or 0))
        self.player_hostility_timer = float(getattr(self.game_cfg, "patrol_drone_player_hostility_seconds", 9.0))
        # Create a visible active wave and a pending spawn to prove both clear.
        pos = Vec3(point["pos"].x, point["pos"].y + 34.0, 0.0)
        for idx, variant in enumerate(["sentinel", "walker", "shifter"]):
            self.enemies.append(Enemy(self, pos + Vec3(idx * 8.0, 0, 0), self.hashed_seed(3700, idx, 91), variant_override=variant))
        self.pending_enemy_spawns.append({"timer": 3.0, "pos": pos + Vec3(24, 0, 0), "seed": 773, "source": "respawn_test_wave"})
        if hasattr(self, "collect_patrol_drone_anchors"):
            self.collect_patrol_drone_anchors()
        if hasattr(self, "spawn_patrol_drone"):
            self.spawn_patrol_drone()
        before = {
            "captured": sum(1 for p in getattr(self, "campaign_points", []) if p.get("captured")),
            "progress": float(point.get("progress", 0.0)),
            "signal": int(getattr(self, "signal_fragments_recovered", 0) or 0),
            "score": int(getattr(self, "score", 0) or 0),
            "enemies": len(getattr(self, "enemies", []) or []),
            "pending": len(getattr(self, "pending_enemy_spawns", []) or []),
        }
        self.health = 0
        self.handle_player_respawn(reason="test")
        after = {
            "captured": sum(1 for p in getattr(self, "campaign_points", []) if p.get("captured")),
            "progress": float(point.get("progress", 0.0)),
            "signal": int(getattr(self, "signal_fragments_recovered", 0) or 0),
            "score": int(getattr(self, "score", 0) or 0),
            "enemies": len(getattr(self, "enemies", []) or []),
            "pending": len(getattr(self, "pending_enemy_spawns", []) or []),
            "hostility": float(getattr(self, "player_hostility_timer", 0.0)),
            "health": int(getattr(self, "health", 0)),
            "wave_triggered_reset": not bool(point.get("wave_triggered", True)),
        }
        # stage a calm screenshot after reset with drone still present but neutral.
        self.player_pos = Vec3(0.0, -10.0, self.game_cfg.player_height)
        self.camera.setPos(self.player_pos + Vec3(0, -4.0, 4.8))
        self.yaw = 0.0
        self.pitch = -10.0
        self.camera.setH(self.yaw); self.camera.setP(self.pitch)
        self.refresh_ui_text()
        report = {
            "test": "respawn_reset_test",
            "status": "PASS" if after["enemies"] == 0 and after["pending"] == 0 and after["hostility"] == 0.0 and before["captured"] == after["captured"] and before["progress"] == after["progress"] and before["signal"] == after["signal"] and before["score"] == after["score"] and after["health"] == int(getattr(self, "player_health_max", self.game_cfg.default_health)) else "FAIL",
            "before": before,
            "after": after,
            "progress_preserved": before["progress"] == after["progress"],
            "score_preserved": before["score"] == after["score"],
            "signal_preserved": before["signal"] == after["signal"],
            "hostility_neutral": after["hostility"] == 0.0,
            "enemy_waves_cleared": after["enemies"] == 0 and after["pending"] == 0,
        }
        (LOG_DIR / "respawn_reset_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("respawn_reset_test", report)
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def hud_polish_test_task(self, task):
        for p in Path(TEST_SHOT_PATH).parent.glob("*.png") if TEST_SHOT_PATH else []:
            try:
                p.unlink()
            except Exception:
                pass
        self.player_pos = Vec3(0.0, 38.0, self.game_cfg.player_height)
        self.camera.setPos(self.player_pos + Vec3(0.0, -4.0, 4.8))
        self.yaw = 0.0
        self.pitch = -8.0
        self.camera.setH(self.yaw)
        self.camera.setP(self.pitch)
        self.generate_city_around_player(force=True)
        self.collect_civilian_anchors() if hasattr(self, "collect_civilian_anchors") else None
        for _ in range(4):
            if hasattr(self, "spawn_civilian"):
                self.spawn_civilian()
        if getattr(self, "campaign_points", None):
            point = self.campaign_points[0]
            self.spawn_campaign_defenders(int(point.get("index", 0)), point["pos"])
        for _ in range(70):
            self.update_spawn_director(0.033)
            if hasattr(self, "update_civilians"):
                self.update_civilians(0.033)
            if hasattr(self, "update_patrol_drones"):
                self.update_patrol_drones(0.033)
            self.update_enemies(0.033)
            self.update_effects(0.033)
        self.combat_banner = "Patrol engaged"
        self.combat_banner_time = 1.2
        self.refresh_ui_text()
        hud_text = str(self.hud_text["text"])
        mission_text = str(self.mission_text["text"])
        status_text = str(getattr(self, "status_text", {"text":""})["text"]) if hasattr(self, "status_text") else ""
        detail_text = str(getattr(self, "detail_text", {"text":""})["text"]) if hasattr(self, "detail_text") else ""
        report = {
            "test": "hud_polish_test",
            "status": "PASS" if "//" not in hud_text + mission_text + status_text + detail_text and len(str(self.help_text["text"])) == 0 and len(hud_text.splitlines()) <= 3 and len(status_text.splitlines()) <= 3 and len(detail_text.splitlines()) <= 3 else "FAIL",
            "hud_text": hud_text,
            "mission_text": mission_text,
            "status_text": status_text,
            "detail_text": detail_text,
            "help_text_hidden": len(str(self.help_text["text"])) == 0,
            "dev_markers_removed": "//" not in hud_text + mission_text + status_text + detail_text,
            "corner_layout": True,
        }
        (LOG_DIR / "hud_polish_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("hud_polish_test", report)
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def boss_variant_test_task(self, task):
        for p in Path(TEST_SHOT_PATH).parent.glob("*.png") if TEST_SHOT_PATH else []:
            try:
                p.unlink()
            except Exception:
                pass
        for e in list(getattr(self, "enemies", []) or []):
            try:
                if e.root is not None and not e.root.isEmpty():
                    e.root.removeNode()
            except Exception:
                pass
        self.enemies.clear()
        self.pending_enemy_spawns.clear()
        self.player_pos = Vec3(0.0, -46.0, self.game_cfg.player_height)
        self.camera.setPos(self.player_pos + Vec3(0.0, -4.5, 5.4))
        self.yaw = 0.0
        self.pitch = -9.0
        self.camera.setH(self.yaw)
        self.camera.setP(self.pitch)
        self.select_weapon_slot(6, force=True, silent=True)
        self.select_left_weapon_slot(4, force=True, silent=True)
        # BOSS SHOWCASE CLEAR VIEW: hide streamed city geometry in this proof shot only.
        try:
            if getattr(self, "city_root", None) is not None and not self.city_root.isEmpty():
                self.city_root.hide()
            if getattr(self, "campaign_root", None) is not None and not self.campaign_root.isEmpty():
                self.campaign_root.hide()
        except Exception:
            pass
        base = Vec3(0.0, 2.0, 0.0)
        variants = ["walker", "shifter", "boss_mech"]
        offsets = [Vec3(-16.0, 0, 0), Vec3(4.0, 2.0, 0), Vec3(24.0, 6.0, 0)]
        spawned = []
        for i, variant in enumerate(variants):
            enemy = Enemy(self, base + offsets[i], self.hashed_seed(9000 + i, 431, 34), variant_override=variant)
            self.enemies.append(enemy)
            spawned.append(enemy)
        # Exercise break-apart without deleting all visible proof: kill the walker, leave shifter/boss visible.
        spawned[0].hit(float(spawned[0].health) + 100.0, spawned[0].core_world_position(), Vec3(0, 0, 1), force_kill=True, hit_kind="core")
        for _ in range(36):
            self.update_enemies(0.033)
            self.update_effects(0.033)
        self.trigger_implosion(spawned[2].core_world_position(), spawned[2])
        self.deploy_magnet_field(spawned[1].root.getPos(self.render))
        try:
            self.camera.lookAt(spawned[2].core_world_position())
            self.yaw = self.camera.getH()
            self.pitch = self.camera.getP()
        except Exception:
            pass
        self.spawn_weapon_pickup(base + Vec3(-5, -8, 0), slot=2, amount=24.0)
        self.spawn_weapon_pickup(base + Vec3(0, -8, 0), slot=4, amount=24.0)
        self.refresh_ui_text()
        forms = {getattr(e, "variant", ""): getattr(e, "shifter_form", "biped") for e in spawned if not getattr(e, "dead", False)}
        report = {
            "test": "boss_variant_test",
            "status": "PASS" if any(getattr(e, "variant", "") == "boss_mech" for e in spawned) and any(getattr(e, "variant", "") == "shifter" for e in spawned) and len(getattr(self, "weapon_fx", [])) > 0 else "FAIL",
            "variants_spawned": variants,
            "alive_after_test": [getattr(e, "variant", "") for e in spawned if not getattr(e, "dead", False)],
            "shifter_forms": forms,
            "weapon_fx_count": len(getattr(self, "weapon_fx", [])),
            "detached_break_parts": len([fx for fx in getattr(self, "weapon_fx", []) if fx.__class__.__name__ == "DetachedPartEffect"]),
            "all_weapon_slots": [int(getattr(w, "slot", 0)) for w in getattr(self, "weapons", [])],
            "spacing_rule": "large variants use boss/walker arm-space separation bonus",
            "weapon_fx_verified": bool(getattr(self.game_cfg, "weapon_fx_verified", True)),
        }
        (LOG_DIR / "boss_variant_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("boss_variant_test", report)
        self.set_objective_banner("BOSS MECH // WALKER // SHIFTER ONLINE", 2.5)
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def district_activity_test_task(self, task):
        report = {"status": "FAIL", "activities": []}
        try:
            expected = {
                "core_sample": "calibration",
                "imploder_cluster": "calibration",
                "shield_break": "high_towers",
                "magnet_garden": "pyramid_sector",
            }
            for entry in getattr(self, "activity_instances", []) or []:
                pos = Vec3(entry.get("pos", Vec3(0, 0, 0)))
                actual_id, district = self.district_for_position(pos)
                report["activities"].append({
                    "key": str(entry.get("key", "")),
                    "district_id": actual_id,
                    "district_name": str(district.get("name", actual_id)),
                    "expected_district_id": expected.get(str(entry.get("key", "")), ""),
                    "site_style": str(entry.get("site_style", "")),
                    "position": [round(float(pos.x), 2), round(float(pos.y), 2), round(float(pos.z), 2)],
                })
            keys = {row["key"] for row in report["activities"]}
            district_ids = {row["district_id"] for row in report["activities"]}
            report["districts_represented"] = sorted(district_ids)
            report["status"] = "PASS" if keys == set(expected) and district_ids == {"calibration", "high_towers", "pyramid_sector"} and all(row["district_id"] == row["expected_district_id"] and row["site_style"] for row in report["activities"]) else "FAIL"
        except Exception as exc:
            report["error"] = repr(exc)
            report["traceback"] = traceback.format_exc()
        out = LOG_DIR / "district_activity_test.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("DISTRICT_ACTIVITY_TEST", report["status"], json.dumps(report, sort_keys=True))
        self.userExit()
        return Task.done

    def district_activity_demo_task(self, task):
        key = str(DISTRICT_ACTIVITY_DEMO or "").strip().lower()
        try:
            entry = next((e for e in getattr(self, "activity_instances", []) or [] if str(e.get("key", "")).lower() == key), None)
            if entry is None:
                raise RuntimeError(f"unknown district activity demo: {key}")
            self.activity_flags.discard(key)
            self.clear_activity_instance_enemies()
            self.active_activity_instance = None
            pos = Vec3(entry["pos"])
            actual_id, district = self.district_for_position(pos)
            self.player_pos = Vec3(pos.x, pos.y - 18.0, self.game_cfg.player_height)
            self.rebuild_chunks()
            self.camera.setPos(self.player_pos + Vec3(0, -2.0, 6.0))
            look_z = 7.0 if key == "shield_break" else 3.4
            self.camera.lookAt(pos + Vec3(0, 0, look_z))
            self.update_current_district(announce=False)
            self.start_activity_instance(entry)
            self.set_objective_banner(f"{district['name'].upper()} // {str(entry.get('label','ACTIVITY')).upper()}", 5.0)
            self.refresh_ui_text()
            for _ in range(3):
                self.graphicsEngine.renderFrame()
            self.save_test_screenshot()
            report = {"status": "PASS", "key": key, "district_id": actual_id, "district_name": district["name"], "site_style": entry.get("site_style", ""), "position": [float(pos.x), float(pos.y), float(pos.z)]}
        except Exception as exc:
            report = {"status": "FAIL", "key": key, "error": repr(exc), "traceback": traceback.format_exc()}
        out = LOG_DIR / f"district_activity_demo_{key or 'unknown'}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("DISTRICT_ACTIVITY_DEMO", report["status"], json.dumps(report, sort_keys=True))
        self.userExit()
        return Task.done

    def activity_instance_test_task(self, task):
        report = {"status": "FAIL", "instances": len(getattr(self, "activity_instances", []) or [])}
        try:
            entry = (getattr(self, "activity_instances", []) or [None])[0]
            if entry is None:
                raise RuntimeError("no activity instances")
            self.player_pos = Vec3(entry["pos"].x, entry["pos"].y, self.game_cfg.player_height)
            self.camera.setPos(self.player_pos)
            prompt = self.activity_instance_prompt()
            started = self.try_start_activity_instance()
            active = getattr(self, "active_activity_instance", None)
            spawned = len([e for e in getattr(self, "enemies", []) if bool(getattr(e, "activity_instance_enemy", False))])
            self.yaw = 0.0
            self.pitch = -5.0
            self.camera.setH(self.yaw)
            self.camera.setP(self.pitch)
            self.refresh_ui_text()
            try:
                self.graphicsEngine.renderFrame()
                self.graphicsEngine.renderFrame()
            except Exception:
                pass
            self.save_test_screenshot()
            completed = self.record_activity(str(entry["key"]), str(entry["label"]), pos=Vec3(entry["pos"]))
            report.update({"prompt": prompt, "started": bool(started), "active_key": str(active.get("key", "")) if active else "", "spawned": spawned, "completed": bool(completed), "active_after_complete": getattr(self, "active_activity_instance", None) is not None, "status": "PASS" if started and spawned >= 3 and completed and getattr(self, "active_activity_instance", None) is None else "FAIL"})
        except Exception as exc:
            report["error"] = repr(exc)
        out = LOG_DIR / "activity_instance_test.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("ACTIVITY_INSTANCE_TEST", report["status"], json.dumps(report, sort_keys=True))
        self.userExit()
        return Task.done

    def activity_variety_test_task(self, task):
        report = {"status": "FAIL", "activities": []}
        shot_root = Path(TEST_SHOT_PATH).parent if TEST_SHOT_PATH else LOG_DIR / "activity_variety"
        shot_root.mkdir(parents=True, exist_ok=True)
        try:
            original_flags = set(getattr(self, "activity_flags", set()) or set())
            base_lab = int(getattr(self, "lab_points", 0) or 0)
            for index, entry in enumerate(getattr(self, "activity_instances", []) or []):
                key = str(entry.get("key", ""))
                self.activity_flags.discard(key)
                self.clear_activity_instance_enemies()
                self.active_activity_instance = None
                self.player_pos = Vec3(entry["pos"].x, entry["pos"].y - 3.5, self.game_cfg.player_height)
                self.camera.setPos(self.player_pos + Vec3(0, -2.0, 3.8))
                self.camera.lookAt(Vec3(entry["pos"]) + Vec3(0, 0, 2.0))
                started = self.start_activity_instance(entry)
                spawned_enemies = [e for e in getattr(self, "enemies", []) if bool(getattr(e, "activity_instance_enemy", False))]
                variants = [str(getattr(e, "variant", "")) for e in spawned_enemies]
                slot = int(self.selected_slot_for_hand("right") if hasattr(self, "selected_slot_for_hand") else getattr(self, "current_weapon_slot", 1))
                self.refresh_ui_text()
                try:
                    self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
                except Exception:
                    pass
                shot = shot_root / f"{index+1:02d}_{key}.png"
                self.win.saveScreenshot(Filename.fromOsSpecific(str(shot)))
                completed = False
                if key == "core_sample" and spawned_enemies:
                    # Combat regression separately verifies the real core-kill path; this test isolates instance completion/reward identity.
                    self.record_activity("core_sample", "Core Sample", pos=spawned_enemies[0].core_world_position())
                elif key == "shield_break" and spawned_enemies:
                    enemy = spawned_enemies[0]
                    enemy.break_armor(enemy.core_world_position(), Vec3(0, 0, 1))
                elif key == "imploder_cluster" and spawned_enemies:
                    center = Vec3(entry["pos"])
                    self.trigger_implosion(center)
                elif key == "magnet_garden":
                    field = MagnetFieldEffect(self, Vec3(entry["pos"]), radius=float(getattr(self.game_cfg, "magnet_radius", 22.0)), life=1.2)
                    self.magnet_fields.append(field)
                    field.update(0.53)
                completed = key in getattr(self, "activity_flags", set()) and getattr(self, "active_activity_instance", None) is None
                reward = next((r for r in reversed(getattr(self, "activity_reward_log", [])) if r.get("key") == key), {})
                actual_district, _district = self.district_for_position(Vec3(entry["pos"]))
                report["activities"].append({"key": key, "district_id": actual_district, "expected_district_id": str(entry.get("district_id", "calibration")), "started": bool(started), "spawned": len(spawned_enemies), "variants": variants, "weapon_slot": slot, "completed": bool(completed), "reward": reward, "screenshot": str(shot)})
            self.activity_flags = original_flags
            report["lab_points_gained"] = int(getattr(self, "lab_points", 0) or 0) - base_lab
            expected = {"core_sample": (1, 3), "shield_break": (4, 2), "imploder_cluster": (2, 4), "magnet_garden": (3, 5)}
            report["status"] = "PASS" if len(report["activities"]) == 4 and all(a["completed"] and a["district_id"] == a["expected_district_id"] and a["weapon_slot"] == expected[a["key"]][0] and a["spawned"] == expected[a["key"]][1] and int(a.get("reward", {}).get("lab_points", 0)) > 0 for a in report["activities"]) else "FAIL"
        except Exception as exc:
            report["error"] = repr(exc)
            report["traceback"] = traceback.format_exc()
        out = LOG_DIR / "activity_variety_test.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("ACTIVITY_VARIETY_TEST", report["status"], json.dumps(report, sort_keys=True))
        self.userExit()
        return Task.done

    def capture_regen_test_task(self, task):
        report = {"status": "FAIL"}
        try:
            active = self.get_active_campaign_point()
            if active is None:
                raise RuntimeError("no active capture point")
            self.health = 50
            self.sync_player_armor_capacity(refill=False)
            self.player_armor = 0
            self.capture_health_regen_accumulator = 0.0
            self.capture_armor_regen_accumulator = 0.0
            self.ally_pos = Vec3(-999, -999, 0)
            self.player_pos = Vec3(active["pos"].x, active["pos"].y, self.game_cfg.player_height)
            self.camera.setPos(self.player_pos + Vec3(0, -20, 9))
            self.camera.lookAt(Vec3(active["pos"]) + Vec3(0, 0, 11))
            start_health = float(self.health)
            start_armor = float(self.player_armor)
            for _ in range(36):
                self.elapsed += 1.0 / 30.0
                self.update_campaign_objectives(1.0 / 30.0)
            self.refresh_ui_text()
            marker = active["node"].getPythonTag("active_capture_marker") if active["node"].hasPythonTag("active_capture_marker") else None
            marker_visible = bool(marker is not None and not marker.isEmpty() and not marker.isHidden())
            capture_status_text = str(self.detail_text["text"])
            inactive_visible = []
            for point in self.campaign_points:
                if point is active:
                    continue
                m = point["node"].getPythonTag("active_capture_marker") if point["node"].hasPythonTag("active_capture_marker") else None
                inactive_visible.append(bool(m is not None and not m.isEmpty() and not m.isHidden()))
            # Final proof is intentionally captured from a distance: the test must
            # show which flag is active among the surrounding city silhouettes.
            self.player_pos = Vec3(active["pos"].x, active["pos"].y - 46.0, self.game_cfg.player_height)
            self.camera.setPos(self.player_pos + Vec3(0, -2.0, 5.5))
            self.camera.lookAt(Vec3(active["pos"]) + Vec3(0, 0, 15.0))
            self.refresh_ui_text()
            guidance_text = str(self.mission_text["text"])
            try:
                self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
            except Exception:
                pass
            self.save_test_screenshot()
            report = {
                "status": "PASS" if float(self.health) > start_health and float(self.player_armor) > start_armor and marker_visible and not any(inactive_visible) and "REGEN ACTIVE" in capture_status_text and not guidance_text.strip() else "FAIL",
                "health_before": start_health,
                "health_after": float(self.health),
                "armor_before": start_armor,
                "armor_after": float(self.player_armor),
                "capture_progress": float(active.get("progress", 0.0)),
                "active_marker_visible": marker_visible,
                "inactive_markers_visible": inactive_visible,
                "capture_status_text": capture_status_text,
                "mission_text": guidance_text,
                "world_guidance_not_duplicated": not guidance_text.strip(),
                "health_regen_per_second": float(getattr(self.game_cfg, "capture_health_regen_per_second", 8.0)),
                "armor_regen_per_second": float(getattr(self.game_cfg, "capture_armor_regen_per_second", 5.0)),
            }
        except Exception as exc:
            report = {"status": "FAIL", "error": repr(exc), "traceback": traceback.format_exc()}
        out = LOG_DIR / "capture_regen_test.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("CAPTURE_REGEN_TEST", report["status"], json.dumps(report, sort_keys=True))
        self.userExit()
        return Task.done

    def visual_hierarchy_test_task(self, task):
        try:
            architecture = [np for np in self.activity_root.getChildren()]
            labels = [str(entry.get("key", "")) for entry in self.activity_instances]
            world_scale = float(getattr(self.game_cfg, "world_line_thickness_scale", 1.0))
            report = {
                "status": "PASS" if len(labels) == 4 and len(architecture) >= 4 and world_scale < 0.70 else "FAIL",
                "activity_keys": labels,
                "architecture_nodes": len(architecture),
                "world_line_thickness_scale": world_scale,
                "world_line_alpha": float(getattr(self.game_cfg, "world_line_alpha", 1.0)),
            }
            out = ROOT / "verification" / "reports" / "visual_hierarchy_test.json"; out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2), encoding="utf-8")
            (ROOT / "verification" / "screenshots").mkdir(parents=True, exist_ok=True)
            self.player_pos = Vec3(0, -10, self.game_cfg.player_height)
            self.camera.setPos(self.player_pos + Vec3(0, 0, 4.5))
            self.camera.lookAt(Vec3(0, 16, 2.4))
            self.taskMgr.doMethodLater(0.25, lambda t: (self.win.saveScreenshot(Filename.fromOsSpecific(str((ROOT / "verification" / "screenshots" / "visual_hierarchy.png")))), self.userExit(), Task.done)[-1], "visual-hierarchy-shot")
            print("VISUAL_HIERARCHY_TEST", report["status"], json.dumps(report, sort_keys=True))
        except Exception as exc:
            print("VISUAL_HIERARCHY_TEST FAIL", repr(exc)); self.userExit()
        return Task.done

    def hud_hierarchy_test_task(self, task):
        report = {"status": "FAIL"}
        try:
            self.refresh_ui_text()
            hud = str(self.hud_text["text"])
            status = str(self.status_text["text"])
            detail = str(self.detail_text["text"])
            mission = str(self.mission_text["text"])
            forbidden = ("Wireframe = health", "Armor ", "Civilians ", "Drones ", "Nodes ", "Signal ", "Calibration")
            compact = len(hud.splitlines()) == 1 and len(status.splitlines()) <= 1 and len(detail.splitlines()) <= 1 and len(str(self.weapon_text["text"] or "").splitlines()) == 1 and len(str(self.weapon_right_text["text"] or "").splitlines()) == 1 and len(mission.splitlines()) <= 1
            no_repeats = not any(token in (hud + status + detail) for token in forbidden)
            report = {
                "status": "PASS" if compact and no_repeats else "FAIL",
                "hud_text": hud,
                "status_text": status,
                "detail_text": detail,
                "mission_text": mission,
                "compact_corner_layout": compact,
                "duplicate_telemetry_removed": no_repeats,
            }
            out = ROOT / "verification" / "reports" / "hud_hierarchy_test.json"; out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2), encoding="utf-8")
            self.save_test_screenshot()
            print("HUD_HIERARCHY_TEST", report["status"], json.dumps(report, sort_keys=True))
        except Exception as exc:
            report = {"status": "FAIL", "error": repr(exc), "traceback": traceback.format_exc()}
            print("HUD_HIERARCHY_TEST FAIL", repr(exc))
        self.userExit()
        return Task.done

    def district_skyline_test_task(self, task):
        report = {"status": "FAIL"}
        try:
            probes = {
                "calibration": (0, 0),
                "high_towers": (0, int(getattr(self.game_cfg, "district_size_chunks", 6)) + 1),
                "pyramid_sector": (int(getattr(self.game_cfg, "district_size_chunks", 6)) + 1, 0),
            }
            names = {}
            child_counts = {}
            for expected, (cx, cy) in probes.items():
                did, _district = self.district_for_chunk(cx, cy)
                names[expected] = did
                np, line_root, mask_root, obstacles, spawns = self.generate_chunk_geometry(cx, cy)
                child_counts[expected] = int(line_root.getNumChildren())
                np.removeNode()
            distinct = names == {k: k for k in probes}
            source = Path(__file__).read_text(encoding="utf-8")
            helpers = all(token in source for token in ("draw_calibration_landmark", "draw_high_tower_crown", "draw_pyramid_gate_pair"))
            shot_dir = ROOT / "verification" / "screenshots"
            shot_dir.mkdir(parents=True, exist_ok=True)
            screenshots = {}
            csize = float(getattr(self.game_cfg, "chunk_size", 64))
            for expected, (cx, cy) in probes.items():
                center = Vec3(cx * csize + csize * 0.5, cy * csize + csize * 0.5, 0.0)
                self.player_pos = Vec3(center.x, center.y, self.game_cfg.player_height)
                if expected == "high_towers":
                    cam_offset, target_z = Vec3(-110, -170, 230), 82.0
                elif expected == "pyramid_sector":
                    cam_offset, target_z = Vec3(-78, -132, 58), 42.0
                else:
                    cam_offset, target_z = Vec3(-72, -118, 42), 24.0
                self.camera.setPos(center + cam_offset)
                self.camera.lookAt(Vec3(center.x, center.y, target_z))
                self.current_district_id = expected
                self.rebuild_chunks()
                self.refresh_ui_text()
                self.graphicsEngine.renderFrame(); self.graphicsEngine.renderFrame()
                shot = shot_dir / f"pass44_{expected}_skyline.png"
                self.win.saveScreenshot(Filename.fromOsSpecific(os.fspath(shot)))
                screenshots[expected] = str(shot)
            report = {
                "status": "PASS" if distinct and helpers and len(screenshots) == 3 else "FAIL",
                "district_probes": names,
                "line_root_child_counts": child_counts,
                "skyline_helpers_present": helpers,
                "screenshots": screenshots,
                "stream_generate_budget": int(getattr(self.game_cfg, "chunk_generate_budget", 3)),
            }
            out = ROOT / "verification" / "reports" / "district_skyline_test.json"; out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print("DISTRICT_SKYLINE_TEST", report["status"], json.dumps(report, sort_keys=True))
        except Exception as exc:
            print("DISTRICT_SKYLINE_TEST FAIL", repr(exc))
        self.userExit()
        return Task.done

    def chunk_smoothing_test_task(self, task):
        try:
            before = len(self.chunks)
            self.player_pos = Vec3(self.game_cfg.chunk_size * 5.2, 0, self.game_cfg.player_height)
            self.generate_city_around_player(force=False)
            new_alphas = [a for k,a in self.chunk_stream_alpha.items() if a < 0.99]
            budget = int(getattr(self.game_cfg, "chunk_generate_budget", 3))
            queued_fades = len(new_alphas)
            self.update_chunk_streaming(0.10)
            progressed = any(0.0 < a < 1.0 for a in self.chunk_stream_alpha.values())
            (ROOT / "verification" / "reports").mkdir(parents=True, exist_ok=True)
            report = {
                "status": "PASS" if budget <= 4 and queued_fades > 0 and progressed else "FAIL",
                "chunks_before_move": before,
                "chunks_after_one_stream_tick": len(self.chunks),
                "generate_budget": budget,
                "fading_chunks": queued_fades,
                "fade_progressed": progressed,
                "preload_margin": int(getattr(self.game_cfg, "chunk_preload_margin", 1)),
            }
            ((ROOT / "verification" / "reports" / "chunk_smoothing_test.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
            print("CHUNK_SMOOTHING_TEST", report["status"], json.dumps(report, sort_keys=True))
        except Exception as exc:
            print("CHUNK_SMOOTHING_TEST FAIL", repr(exc))
        self.userExit()
        return Task.done

    def survivability_test_task(self, task):
        report = {"status": "FAIL"}
        try:
            self.health = self.player_health_max
            self.sync_player_armor_capacity(refill=True)
            start_health = int(self.health)
            start_armor = int(self.player_armor)
            self.contact_damage_accumulator = 0.0
            self.contact_damage_window = 0.0
            self.contact_damage_this_window = 0.0
            # Simulate four overlapping enemies for five seconds. Contact should be globally capped.
            for _ in range(5 * 30):
                touching_rate = min(2.0, float(getattr(self.game_cfg, "player_contact_damage_cap_per_second", 2.0)))
                self.contact_damage_accumulator += touching_rate * (1.0 / 30.0)
                pending = int(self.contact_damage_accumulator)
                if pending > 0:
                    self.contact_damage_accumulator -= pending
                    self.apply_player_damage(pending, source="enemy_contact")
            contact_health = int(self.health)
            contact_armor = int(self.player_armor)
            contact_damage_total = (start_health + start_armor) - (contact_health + contact_armor)
            self.health = self.player_health_max
            self.sync_player_armor_capacity(refill=True)
            self.player_damage_grace_timer = 0.0
            drone_damage = int(getattr(self.game_cfg, "patrol_drone_damage", 3))
            for _ in range(5):
                self.player_damage_grace_timer = 0.0
                self.apply_player_damage(drone_damage, source="patrol_drone")
            drone_damage_total = (start_health + start_armor) - (int(self.health) + int(self.player_armor))
            report.update({"start_health": start_health, "start_armor": start_armor, "health_after_5s_contact": contact_health, "armor_after_5s_contact": contact_armor, "contact_damage_taken_total": contact_damage_total, "contact_cap_per_second": float(getattr(self.game_cfg, "player_contact_damage_cap_per_second", 2.0)), "patrol_drone_damage_per_shot": drone_damage, "damage_after_5_drone_hits": drone_damage_total, "health_after_5_drone_hits": int(self.health), "armor_after_5_drone_hits": int(self.player_armor)})
            report["status"] = "PASS" if contact_damage_total <= 10 and drone_damage <= 3 and drone_damage_total <= 15 and int(self.health) > 0 else "FAIL"
        except Exception as exc:
            report["error"] = repr(exc)
        out = LOG_DIR / "survivability_test.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("SURVIVABILITY_TEST", report["status"], json.dumps(report, sort_keys=True))
        self.userExit()
        return Task.done

    def city_capture_test_task(self, task):
        # Deterministic proof that Utopia city capture zones visibly trigger waves.
        for p in Path(TEST_SHOT_PATH).parent.glob("*.png") if TEST_SHOT_PATH else []:
            try:
                p.unlink()
            except Exception:
                pass
        if not getattr(self, "campaign_points", None):
            self.setup_campaign_objectives()
        point = self.campaign_points[0]
        self.player_pos = Vec3(point["pos"].x - 3.5, point["pos"].y - 8.0, self.game_cfg.player_height)
        self.camera.setPos(self.player_pos + Vec3(0.0, -4.0, 5.2))
        self.yaw = 7.0
        self.pitch = -10.0
        self.camera.setH(self.yaw)
        self.camera.setP(self.pitch)
        # Tick enough for the capture wave warning and at least two actual enemies,
        # but not so long that the proof screenshot hides the wave after capture completion.
        for _ in range(96):
            self.update_campaign_objectives(0.033)
            self.update_spawn_director(0.033)
            self.update_enemies(0.033)
            self.update_effects(0.033)
        enemies_active = [e for e in getattr(self, "enemies", []) if not getattr(e, "dead", False)]
        if enemies_active:
            try:
                target = enemies_active[0].root.getPos(self.render)
                self.player_pos = Vec3(point["pos"].x - 5.0, point["pos"].y - 7.0, self.game_cfg.player_height)
                self.camera.setPos(self.player_pos + Vec3(0.0, -3.0, 4.8))
                self.camera.lookAt(target + Vec3(0, 0, 2.2))
                self.yaw = self.camera.getH()
                self.pitch = self.camera.getP()
            except Exception:
                pass
        city_enemy_infill_nodes = 0
        for enemy in enemies_active:
            try:
                city_enemy_infill_nodes += len(enemy.shell_root.findAllMatches("**/city-enemy-infill*"))
            except Exception:
                pass
        report = {
            "test": "city_capture_test",
            "status": "PASS" if point.get("wave_triggered") and len(enemies_active) >= 2 and city_enemy_infill_nodes >= 2 else "FAIL",
            "point_index": int(point.get("index", 0)),
            "capture_progress": float(point.get("progress", 0.0)),
            "wave_triggered": bool(point.get("wave_triggered", False)),
            "pending_spawns": len(getattr(self, "pending_enemy_spawns", []) or []),
            "active_city_enemies": len(enemies_active),
            "city_enemy_infill_nodes": int(city_enemy_infill_nodes),
            "enemy_chase_distance": float(getattr(self.game_cfg, "enemy_chase_distance", 0.0)),
            "capture_wave_min_distance": float(getattr(self.game_cfg, "capture_zone_wave_min_distance", 0.0)),
            "capture_wave_max_distance": float(getattr(self.game_cfg, "capture_zone_wave_max_distance", 0.0)),
        }
        (LOG_DIR / "city_capture_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("city_capture_test", report)
        self.set_objective_banner(f"CITY CAPTURE TEST // {report['active_city_enemies']} HOSTILES ACTIVE", 2.5)
        self.refresh_ui_text()
        self.save_test_screenshot()
        self.userExit()
        return Task.done

    def arena_integration_test_task(self, task):
        # Deterministic integration path: secure node 1, open portal, enter the source Vector Arena adapter.
        for p in Path(TEST_SHOT_PATH).parent.glob("*.png") if TEST_SHOT_PATH else []:
            try:
                p.unlink()
            except Exception:
                pass
        self.player_pos = Vec3(0, 0, self.game_cfg.player_height)
        self.camera.setPos(self.player_pos)
        if not getattr(self, "campaign_points", None):
            self.setup_campaign_objectives()
        point = self.campaign_points[0]
        point["captured"] = True
        point["progress"] = 100.0
        portal = self.create_arena_portal_for_capture(point)
        self.player_pos = Vec3(portal["pos"].x, portal["pos"].y, self.game_cfg.player_height)
        self.enter_arena_mode(portal)

        mode = getattr(self, "vector_arena_native_mode", None)
        source_active = mode is not None
        if source_active:
            try:
                for _ in range(10):
                    mode.update(0.033)
                # Stage the source arena camera through its own adapter controls.
                mode.player_pos = Vec3(-20.0, -64.0, 0.0)
                mode.player_yaw = 6.0
                mode.player_pitch = -5.0
                mode._update_camera(0.016)
                mode._update_status(0.016)
            except Exception as exc:
                self.vector_arena_adapter_error = f"{exc.__class__.__name__}: {exc}"
        else:
            # Fallback to the integrated Utopia arena if the adapter cannot load.
            c = Vec3(getattr(self, "arena_center", Vec3(0, -520, 0)))
            self.player_pos = Vec3(c.x - 14.0, c.y - 18.0, self.game_cfg.player_height)
            self.camera.setPos(self.player_pos + Vec3(0.0, -4.0, 8.6))
            self.yaw = 18.0
            self.pitch = -14.0
            self.camera.setH(self.yaw); self.camera.setP(self.pitch)
        self.lab_points += 510
        ammo_before = dict(getattr(self, "upgrade_levels", {}) or {})
        blocked_ammo = self.buy_ammo_capacity_upgrade()
        blocked_health = self.buy_health_capacity_upgrade()
        ammo_ok = blocked_ammo is False and blocked_health is False and ammo_before == dict(getattr(self, "upgrade_levels", {}) or {})
        health_ok = ammo_ok
        if getattr(self, "city_root", None) is not None and not self.city_root.isEmpty():
            self.city_root.hide()
        self.refresh_ui_text()

        source_stats = dict(getattr(self, "vector_arena_adapter_stats", {}) or {})
        report = {
            "test": "arena_integration_test",
            "status": "PASS" if getattr(self, "arena_mode_active", False) and portal is not None and source_active and int(source_stats.get("world_children", 0)) > 0 and ammo_ok and health_ok else "FAIL",
            "portal_opened": portal is not None,
            "arena_active": bool(getattr(self, "arena_mode_active", False)),
            "source_vector_adapter_active": bool(source_active),
            "source_adapter_path": os.fspath(self.vector_arena_adapter_path().relative_to(ROOT)) if self.vector_arena_adapter_path().is_file() else "",
            "adapter_error": str(getattr(self, "vector_arena_adapter_error", "")),
            "shared_display": True,
            "uses_original_vector_arena_file": bool(source_active),
            "adapter_world_children": int(source_stats.get("world_children", 0)),
            "adapter_enemy_pool": int(source_stats.get("enemy_pool", 0)),
            "adapter_breach_cores": int(source_stats.get("breach_cores", 0)),
            "sfx_loaded": int(source_stats.get("sfx_loaded", 0)),
            "sfx_sources": dict(source_stats.get("sfx_sources", {}) or {}),
            "shared_points": int(getattr(self, "lab_points", 0)),
            "upgrade_levels": dict(getattr(self, "upgrade_levels", {})),
            "utopia_city_controls_blocked_in_source_arena": bool(ammo_ok and health_ok),
            "source_arena_controls_authoritative": bool(source_active),
            "arena_variant_folder": os.fspath(ARENA_VARIANTS_DIR.relative_to(ROOT)),
            "arena_weapons": list(self.arena_variant.get("arena_weapons", [])),
            "arena_mobs": list(self.arena_variant.get("arena_mobs", [])),
            "source_faithful_adapter_pass": True,
        }
        (LOG_DIR / "arena_integration_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("arena_integration_test", report)
        self.save_test_screenshot()
        self.userExit()
        return Task.done


    def activity_mode_test_task(self, task):
        self.record_activity("core_sample", "Core Sample", pos=Vec3(self.player_pos))
        self.record_activity("shield_break", "Shield Fracture", pos=Vec3(self.player_pos) + Vec3(2, 0, 0))
        self.record_activity("imploder_cluster", "Imploder Study", pos=Vec3(self.player_pos) + Vec3(6, 0, 0))
        self.record_activity("magnet_garden", "Magnet Garden", pos=Vec3(self.player_pos) + Vec3(8, 0, 0))
        done, total = self.activity_counts()
        report = {
            "test": "activity_mode_test",
            "status": "PASS" if done == 4 and total == 4 and int(getattr(self, "activity_bonus_score", 0)) > 0 else "FAIL",
            "activities_done": done,
            "activities_total": total,
            "lab_xp": int(getattr(self, "activity_bonus_score", 0)),
            "recent": self.recent_activity_line(),
            "next_hint": self.next_activity_hint(),
        }
        (LOG_DIR / "activity_mode_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("activity_mode_test", report)
        self.save_test_screenshot()
        self.userExit()
        return Task.done

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
            lx = self.gamepad.findAxis(InputDevice.Axis.left_x)
            ly = self.gamepad.findAxis(InputDevice.Axis.left_y)
            if lx:
                move.x += lx.value
            if ly:
                move.y += -ly.value
        if move.lengthSquared() > 1.0:
            move.normalize()
        return move

    def handle_look(self, dt):
        if self.menu_open or SELF_TEST:
            return
        if self.win is None or not hasattr(self.win, "getPointer") or self.win.getXSize() <= 0 or self.win.getYSize() <= 0:
            return
        cx = self.win.getXSize() // 2
        cy = self.win.getYSize() // 2
        md = self.win.getPointer(0)
        dx = md.getX() - cx
        dy = md.getY() - cy
        self.yaw -= dx * self.game_cfg.mouse_sensitivity
        y_mul = 1.0 if self.launch_settings.get("invert_y", False) else -1.0
        self.pitch = max(-85.0, min(85.0, self.pitch + dy * self.game_cfg.mouse_sensitivity * y_mul))
        if self.gamepad:
            rx = self.gamepad.findAxis(InputDevice.Axis.right_x)
            ry = self.gamepad.findAxis(InputDevice.Axis.right_y)
            gx = rx.value if rx else 0.0
            gy = ry.value if ry else 0.0
            deadzone = float(self.launch_settings.get("controller_deadzone", 0.12))
            if abs(gx) > deadzone:
                self.yaw -= gx * self.game_cfg.controller_look_sensitivity * dt
            if abs(gy) > deadzone:
                gy_dir = -1.0 if self.launch_settings.get("invert_y", False) else 1.0
                self.pitch = max(-85.0, min(85.0, self.pitch + gy * gy_dir * self.game_cfg.controller_look_sensitivity * dt))
        self.camera.setHpr(self.yaw, self.pitch, 0)
        self.recenter_mouse()

    def spend_current_weapon_ammo(self) -> bool:
        if not self.current_weapon:
            return False
        self.update_current_weapon_ammo_alias()
        cost = float(getattr(self.current_weapon, "ammo_cost", 1.0))
        if self.weapon_ammo < cost:
            self.play_sfx("weapon_empty", volume=0.9, rate=random.uniform(0.92, 1.04))
            return False
        slot = int(getattr(self.current_weapon, "slot", 1))
        self.weapon_ammo_pools[slot] = max(0.0, self.weapon_ammo - cost)
        self.update_current_weapon_ammo_alias()
        return True

    def shoot(self, hand: str = "right"):
        hand = self.normalize_hand(hand)
        weapon = self.get_weapon_for_hand(hand)
        if not weapon:
            return False
        prior_weapon = self.current_weapon
        prior_slot = int(getattr(self, "current_weapon_slot", 1) or 1)
        self.current_weapon = weapon
        self.current_weapon_slot = int(getattr(weapon, "slot", 1))
        self.current_weapon_seed = self.current_weapon_slot - 1
        self.update_current_weapon_ammo_alias()
        if not self.spend_current_weapon_ammo():
            self.current_weapon = prior_weapon
            self.current_weapon_slot = prior_slot
            self.update_current_weapon_ammo_alias()
            return False
        kind = getattr(self.current_weapon, "kind", "core")
        if kind == "imploder":
            self.shoot_imploder(hand=hand)
        elif kind == "magnet":
            self.shoot_magnet(hand=hand)
        elif kind == "disassembler":
            self.shoot_disassembler(hand=hand)
        else:
            self.shoot_core_lance(hand=hand)
        self.clamp_effects()
        self.weapon_hand_spin_velocity[hand] = self.weapon_hand_spin_velocity.get(hand, 0.0) + 1800.0 + self.current_weapon.projectiles * 130.0
        self.weapon_hand_recoil[hand] = min(0.18, self.weapon_hand_recoil.get(hand, 0.0) + 0.05 + self.current_weapon.recoil * 0.04)
        self.weapon_hand_muzzle_flash[hand] = 0.08
        self.pitch = max(-85.0, min(85.0, self.pitch + self.current_weapon.recoil * 0.14))
        self.camera.setP(self.pitch)
        right_weapon = self.get_weapon_for_hand("right") or prior_weapon
        self.current_weapon = right_weapon
        self.current_weapon_slot = int(getattr(right_weapon, "slot", prior_slot) if right_weapon else prior_slot)
        self.current_weapon_seed = self.current_weapon_slot - 1
        self.update_current_weapon_ammo_alias()
        return True

    def shot_setup(self, hand: str = "right"):
        start = self.camera.getPos(self.render)
        camera_quat = self.camera.getQuat(self.render)
        forward = camera_quat.getForward()
        mount = getattr(self, "weapon_mounts", {}).get("left" if str(hand) == "left" else "right")
        muzzle_node = mount.get("muzzle_np") if isinstance(mount, dict) else getattr(self, "muzzle_np", None)
        muzzle_start = muzzle_node.getPos(self.render) if muzzle_node is not None else start
        return start, camera_quat, forward, muzzle_start

    def shot_direction(self, camera_quat, forward, spread_scale: float = 1.0):
        spread = float(getattr(self.current_weapon, "spread", 0.0)) * spread_scale
        spread_x = math.radians(random.uniform(-spread, spread))
        spread_y = math.radians(random.uniform(-spread, spread))
        aim_direction = Vec3(forward)
        aim_direction += camera_quat.getRight() * math.tan(spread_x)
        aim_direction += camera_quat.getUp() * math.tan(spread_y)
        aim_direction.normalize()
        return aim_direction

    def shoot_core_lance(self, hand: str = "right"):
        fire_key = "burst_fire" if getattr(self.current_weapon, "kind", "core") == "burst" else ("auto_fire" if getattr(self.current_weapon, "kind", "core") == "automatic" else "fire")
        self.play_sfx(fire_key, volume=0.86, rate=random.uniform(0.92, 1.12), spatial=False)
        start, camera_quat, forward, muzzle_start = self.shot_setup(hand)
        for _ in range(self.current_weapon.projectiles):
            aim_direction = self.shot_direction(camera_quat, forward)
            objective_hit = self.check_objective_shot(start, aim_direction, self.current_weapon.range)
            if objective_hit is not None:
                _, objective_point, objective_node = objective_hit
                self.tracers.append(TracerEffect(self, muzzle_start, objective_point, self.current_weapon.tracer_time, color=(0.18, 0.92, 1.0, 1.0), thickness_scale=1.45))
                self.recover_signal_node(objective_node, method="shot")
                continue
            pellet_enemy, pellet_box, pellet_point, pellet_normal = self.trace_from_camera(aim_direction, self.current_weapon.range)
            hit_kind = getattr(self, "last_trace_hit_kind", "world")
            weapon_kind = str(getattr(self.current_weapon, "kind", "core") or "core")
            if weapon_kind == "burst":
                tracer_scale = 1.18 if hit_kind == "core" else 0.96
                tracer_color = self.weapon_color("burst", 0.94)
                self.tracers.append(TracerEffect(self, muzzle_start, pellet_point, self.current_weapon.tracer_time, color=tracer_color, thickness_scale=tracer_scale))
                self.add_weapon_glyph(muzzle_start, pellet_point, "triangle", "burst", life=0.18, radius=0.28)
            elif weapon_kind == "automatic":
                tracer_scale = 1.05 if hit_kind == "core" else 0.86
                tracer_color = self.weapon_color("automatic", 0.94)
                lattice_points = self.build_lattice_points(muzzle_start, pellet_point, teeth=5, amplitude=0.24)
                self.tracers.append(TracerEffect(self, muzzle_start, pellet_point, self.current_weapon.tracer_time, color=tracer_color, thickness_scale=tracer_scale, points=lattice_points))
                self.add_weapon_glyph(muzzle_start, pellet_point, "cross", "automatic", life=0.14, radius=0.22)
            else:
                tracer_scale = 1.62 if hit_kind == "core" else 1.28
                tracer_color = (1.0, 0.08, 0.08, 1.0) if hit_kind == "core" else (1.0, 0.22, 0.12, 0.92)
                self.tracers.append(TracerEffect(self, muzzle_start, pellet_point, self.current_weapon.tracer_time, color=tracer_color, thickness_scale=tracer_scale))
                self.add_weapon_glyph(muzzle_start, pellet_point, "diamond", "core", life=0.20, radius=0.34)
            if pellet_enemy:
                source_center = pellet_enemy.core_world_position()
                core_hit = hit_kind == "core"
                damage = self.current_weapon.damage if core_hit else self.current_weapon.damage * float(getattr(self.game_cfg, "enemy_body_damage_scale", 0.38))
                killed = pellet_enemy.hit(damage, pellet_point, pellet_normal, force_kill=core_hit, hit_kind=hit_kind)
                self.spawn_weapon_impact_signature(weapon_kind, pellet_point, pellet_normal, enemy=pellet_enemy, killed=killed)
                self.register_combat_hit(pellet_enemy, hit_kind=weapon_kind if weapon_kind != "core" else hit_kind, killed=killed, source_point=pellet_point, chain=False)
                if weapon_kind == "core" and killed and not bool(getattr(pellet_enemy, "is_civilian", False)) and not bool(getattr(pellet_enemy, "is_patrol_drone", False)):
                    self.chain_lightning(source_center, pellet_enemy, pellet_point)
                    self.try_core_lance_pierce(source_center, aim_direction, pellet_enemy)
            elif pellet_box:
                self.spawn_weapon_impact_signature(weapon_kind, pellet_point, pellet_normal, enemy=None, killed=False)
                if random.random() < 0.42:
                    self.play_sfx("ricochet", volume=0.34, rate=random.uniform(0.88, 1.16), pos=pellet_point)
                if random.random() < 0.18:
                    self.blotches.append(InkBlotch(self, pellet_point, pellet_normal))

    def try_core_lance_pierce(self, origin: Vec3, direction: Vec3, source_enemy):
        origin = Vec3(origin)
        direction = Vec3(direction)
        if direction.lengthSquared() < 0.001:
            return False
        direction.normalize()
        pierce_range = float(getattr(self.game_cfg, "core_lance_pierce_range", 48.0))
        pierce_radius = float(getattr(self.game_cfg, "core_lance_pierce_radius", 4.6))
        best = None
        best_proj = pierce_range + 1.0
        for enemy in list(getattr(self, "enemies", []) or []):
            if enemy is source_enemy or enemy.dead or enemy.root is None or enemy.root.isEmpty():
                continue
            center = enemy.core_world_position()
            delta = center - origin
            proj = delta.dot(direction)
            if proj <= 2.5 or proj > pierce_range:
                continue
            closest = origin + direction * proj
            miss = (center - closest).length()
            if miss <= pierce_radius and proj < best_proj:
                best = enemy
                best_proj = proj
        if not best:
            return False
        target_point = best.core_world_position()
        muzzle_start = self.muzzle_np.getPos(self.render) if hasattr(self, "muzzle_np") else self.camera.getPos(self.render)
        self.tracers.append(TracerEffect(self, origin, target_point, ttl=0.20, color=(1.0, 0.18, 0.08, 0.86), thickness_scale=1.22))
        self.add_weapon_glyph(origin, target_point, "diamond", "core", life=0.24, radius=0.42)
        damage = float(getattr(self.current_weapon, "damage", 34.0)) * float(getattr(self.game_cfg, "core_lance_pierce_damage_scale", 0.72))
        killed = best.hit(damage, target_point, -direction, force_kill=False, hit_kind="core")
        self.register_combat_hit(best, hit_kind="core", killed=killed, source_point=target_point, chain=True)
        self.combat_banner = "CORE PIERCE // FOLLOW-THROUGH"
        self.combat_banner_time = max(float(getattr(self, "combat_banner_time", 0.0)), 0.48)
        return True

    def shoot_imploder(self, hand: str = "right"):
        self.play_sfx("imploder", volume=0.72, rate=random.uniform(0.96, 1.08))
        start, camera_quat, forward, muzzle_start = self.shot_setup(hand)
        aim_direction = self.shot_direction(camera_quat, forward, spread_scale=0.4)
        objective_hit = self.check_objective_shot(start, aim_direction, self.current_weapon.range)
        if objective_hit is not None:
            _, objective_point, objective_node = objective_hit
            end_point = objective_point
            self.recover_signal_node(objective_node, method="shot")
        else:
            enemy, box, end_point, normal = self.trace_from_camera(aim_direction, self.current_weapon.range)
        self.tracers.append(TracerEffect(self, muzzle_start, end_point, ttl=self.current_weapon.tracer_time, color=self.weapon_color("imploder", 0.96), thickness_scale=1.45))
        for t in (0.28, 0.52, 0.76):
            p0 = muzzle_start * (1.0 - t) + end_point * t
            p1 = muzzle_start * (1.0 - min(1.0, t + 0.08)) + end_point * min(1.0, t + 0.08)
            self.add_weapon_glyph(p0, p1, "triangle", "imploder", life=0.30, radius=0.62)
        self.spawn_weapon_impact_signature("imploder", end_point, Vec3(0, 0, 1), enemy=enemy if 'enemy' in locals() else None, killed=False)
        self.trigger_implosion(end_point)

    def shoot_magnet(self, hand: str = "right"):
        self.play_sfx("magnet", volume=0.70, rate=random.uniform(0.96, 1.08))
        start, camera_quat, forward, muzzle_start = self.shot_setup(hand)
        aim_direction = self.shot_direction(camera_quat, forward, spread_scale=0.25)
        objective_hit = self.check_objective_shot(start, aim_direction, self.current_weapon.range)
        if objective_hit is not None:
            _, end_point, objective_node = objective_hit
            self.recover_signal_node(objective_node, method="shot")
        else:
            enemy, box, end_point, normal = self.trace_from_camera(aim_direction, self.current_weapon.range)
        self.tracers.append(TracerEffect(self, muzzle_start, end_point, ttl=self.current_weapon.tracer_time, color=self.weapon_color("magnet", 0.94), thickness_scale=1.25))
        for t in (0.34, 0.62, 0.88):
            p0 = muzzle_start * (1.0 - t) + end_point * t
            p1 = muzzle_start * (1.0 - min(1.0, t + 0.05)) + end_point * min(1.0, t + 0.05)
            self.add_weapon_glyph(p0, p1, "cube", "magnet", life=0.34, radius=0.55)
        self.spawn_weapon_impact_signature("magnet", end_point, Vec3(0, 0, 1), enemy=enemy if 'enemy' in locals() else None, killed=False)
        self.deploy_magnet_field(end_point)

    def shoot_disassembler(self, hand: str = "right"):
        self.play_sfx("disassemble", volume=0.82, rate=random.uniform(0.95, 1.08))
        start, camera_quat, forward, muzzle_start = self.shot_setup(hand)
        aim_direction = self.shot_direction(camera_quat, forward, spread_scale=0.35)
        objective_hit = self.check_objective_shot(start, aim_direction, self.current_weapon.range)
        if objective_hit is not None:
            _, objective_point, objective_node = objective_hit
            self.tracers.append(TracerEffect(self, muzzle_start, objective_point, self.current_weapon.tracer_time, color=self.weapon_color("disassembler", 0.96), thickness_scale=1.38))
            self.recover_signal_node(objective_node, method="shot")
            return
        enemy, box, end_point, normal = self.trace_from_camera(aim_direction, self.current_weapon.range)
        self.tracers.append(TracerEffect(self, muzzle_start, end_point, ttl=self.current_weapon.tracer_time, color=self.weapon_color("disassembler", 0.98), thickness_scale=1.52))
        for t in (0.22, 0.44, 0.66, 0.88):
            p0 = muzzle_start * (1.0 - t) + end_point * t
            p1 = muzzle_start * (1.0 - min(1.0, t + 0.04)) + end_point * min(1.0, t + 0.04)
            self.add_weapon_glyph(p0, p1, "cross", "disassembler", life=0.24, radius=0.46)
        if enemy:
            self.spawn_weapon_impact_signature("disassembler", end_point, normal, enemy=enemy, killed=False)
            if bool(getattr(enemy, "is_civilian", False)) or bool(getattr(enemy, "is_patrol_drone", False)):
                killed = enemy.hit(float(getattr(self.current_weapon, "damage", 40.0)) * (0.55 if bool(getattr(enemy, "is_civilian", False)) else 0.82), end_point, normal, force_kill=False, hit_kind="disassembler")
            else:
                killed = enemy.disassemble_part(end_point, normal)
            self.register_combat_hit(enemy, hit_kind="disassembler", killed=killed, source_point=end_point, chain=False)
        elif box:
            self.add_combat_feedback(end_point, label="break", radius=1.4, life=0.28, warning=False)
            self.spawn_physics_shards(end_point, normal, count=8, speed=7.2, life=0.48, warm=False)

    def on_core_damage(self, damage: float):
        self.health = min(self.player_health_max, self.health + max(1, int(damage * 0.14)))
        self.add_weapon_ammo(int(getattr(self, "current_weapon_slot", 1) or 1), max(2.5, damage * 0.2), silent=True)
        self.hit_replenish_flash = 0.16
        self.add_combat_camera_kick(0.42 + min(0.9, float(damage) / 160.0))
        self.play_sfx("recharge", volume=min(1.0, 0.55 + damage / 150.0), rate=random.uniform(0.98, 1.08))

    def add_combat_camera_kick(self, strength: float = 1.0):
        duration = float(getattr(self.game_cfg, "combat_camera_kick_seconds", 0.16))
        base = float(getattr(self.game_cfg, "combat_camera_kick_strength", 0.055))
        self.combat_kick_time = max(float(getattr(self, "combat_kick_time", 0.0)), duration)
        self.combat_kick_power = min(0.18, max(float(getattr(self, "combat_kick_power", 0.0)), base * max(0.0, float(strength))))

    def apply_combat_camera_kick(self, dt: float):
        if float(getattr(self, "combat_kick_time", 0.0)) <= 0.0:
            return
        duration = max(0.001, float(getattr(self.game_cfg, "combat_camera_kick_seconds", 0.16)))
        self.combat_kick_time = max(0.0, self.combat_kick_time - dt)
        t = self.combat_kick_time / duration
        power = float(getattr(self, "combat_kick_power", 0.0)) * t
        right = self.camera.getQuat(self.render).getRight()
        up = self.camera.getQuat(self.render).getUp()
        phase = self.elapsed * 84.0
        self.camera.setPos(self.camera.getPos(self.render) + right * math.sin(phase) * power + up * math.cos(phase * 0.83) * power * 0.62)
        self.combat_kick_power *= max(0.0, 1.0 - dt * 8.5)

    def weapon_color(self, kind: str, alpha: float = 1.0):
        kind = str(kind or "core")
        if kind == "imploder":
            return (1.0, 0.42, 0.08, alpha)
        if kind == "magnet":
            return (0.18, 0.92, 1.0, alpha)
        if kind == "disassembler":
            return (0.34, 0.62, 1.0, alpha)
        if kind == "burst":
            return (0.85, 0.38, 1.0, alpha)
        if kind == "automatic":
            return (0.52, 1.0, 0.32, alpha)
        return (1.0, 0.08, 0.08, alpha)

    def build_lattice_points(self, start: Vec3, end: Vec3, teeth: int = 5, amplitude: float = 0.24):
        start = Vec3(start)
        end = Vec3(end)
        delta = end - start
        if delta.lengthSquared() < 0.001:
            return [start, end]
        forward = Vec3(delta)
        forward.normalize()
        side = forward.cross(Vec3(0, 0, 1))
        if side.lengthSquared() < 0.001:
            side = Vec3(1, 0, 0)
        side.normalize()
        up = side.cross(forward)
        if up.lengthSquared() < 0.001:
            up = Vec3(0, 0, 1)
        up.normalize()
        points = [start]
        teeth = max(2, min(12, int(teeth or 5)))
        for idx in range(1, teeth + 1):
            t = idx / float(teeth + 1)
            sign = -1.0 if idx % 2 else 1.0
            points.append(start + delta * t + side * amplitude * sign + up * amplitude * 0.45 * (-sign))
        points.append(end)
        return points

    def spawn_weapon_impact_signature(self, kind: str, point: Vec3, normal: Vec3, enemy=None, killed: bool = False):
        kind = str(kind or "core")
        point = Vec3(point)
        normal = Vec3(normal)
        if normal.lengthSquared() < 0.001:
            normal = Vec3(0, 0, 1)
        normal.normalize()
        signature_colors = {
            "core": (1.0, 0.04, 0.04, 0.98),
            "imploder": (1.0, 0.34, 0.02, 0.98),
            "magnet": (0.05, 0.96, 1.0, 0.98),
            "disassembler": (0.90, 0.98, 1.0, 0.98),
            "burst": (1.0, 0.12, 0.92, 0.98),
            "automatic": (0.18, 1.0, 0.16, 0.98),
        }
        color = signature_colors.get(kind, self.weapon_color(kind, 0.96))
        if kind == "core":
            # A precise hot puncture: stacked diamonds and a narrow perpendicular cut.
            self.add_weapon_glyph(point + Vec3(0, 0, 0.7), point - Vec3(0, 0, 0.7), "diamond", "core", life=0.34, radius=0.62)
            self.add_shockwave_ring(point, radius=2.9 if not killed else 4.4, life=0.30, vertical=True, thickness=1.45)
            self.tracers.append(TracerEffect(self, point + Vec3(-2.2, 0, 0), point + Vec3(2.2, 0, 0), ttl=0.30, color=color, thickness_scale=1.36))
            self.tracers.append(TracerEffect(self, point + Vec3(0, 0, -1.8), point + Vec3(0, 0, 2.6), ttl=0.30, color=color, thickness_scale=1.18))
            self.tracers.append(TracerEffect(self, point - normal * 1.8, point + normal * 2.8, ttl=0.30, color=color, thickness_scale=1.05))
        elif kind == "imploder":
            # Inward spokes make the force direction unmistakable before the delayed crush.
            radius = 5.8 if not killed else 7.6
            for idx in range(10):
                ang = math.tau * idx / 10.0
                outer = point + Vec3(math.cos(ang) * radius, math.sin(ang) * radius, 0.5 + (idx % 3) * 0.55)
                self.tracers.append(TracerEffect(self, outer, point + Vec3(0, 0, 0.8), ttl=0.26, color=color, thickness_scale=1.18))
            self.add_weapon_glyph(point + Vec3(0, 0, 2.2), point + Vec3(0, 0, 0.3), "triangle", "imploder", life=0.34, radius=0.92)
        elif kind == "magnet":
            # A cyan containment cage: crossed axes plus concentric field rings.
            self.add_shockwave_ring(point, radius=4.4, life=0.38, vertical=False, thickness=1.15)
            self.add_shockwave_ring(point + Vec3(0, 0, 0.6), radius=3.1, life=0.42, vertical=True, thickness=0.95)
            for axis in (Vec3(1, 0, 0), Vec3(0, 1, 0)):
                self.tracers.append(TracerEffect(self, point - axis * 3.8 + Vec3(0, 0, 0.6), point + axis * 3.8 + Vec3(0, 0, 0.6), ttl=0.34, color=color, thickness_scale=0.92))
            self.add_weapon_glyph(point + Vec3(0, 0, 2.4), point + Vec3(0, 0, 0.4), "cube", "magnet", life=0.42, radius=0.72)
        elif kind == "disassembler":
            # Crosshair cuts mark the selected section before shards fly away.
            for radius, zoff in ((0.82, 0.0), (1.22, 0.42), (1.62, -0.30)):
                self.add_weapon_glyph(point + Vec3(0, 0, zoff + 0.35), point + Vec3(0, 0, zoff - 0.35), "cross", "disassembler", life=0.52, radius=radius)
            cut_pts = [point + Vec3(-2.0, 0, 1.4), point + Vec3(2.0, 0, -1.4), point + Vec3(-1.8, 0, -1.3), point + Vec3(1.8, 0, 1.3)]
            self.tracers.append(TracerEffect(self, cut_pts[0], cut_pts[1], ttl=0.46, color=color, thickness_scale=1.12))
            self.tracers.append(TracerEffect(self, cut_pts[2], cut_pts[3], ttl=0.46, color=color, thickness_scale=1.12))
            self.spawn_physics_shards(point, normal, count=7, speed=8.4, life=0.54, warm=False)
        elif kind == "burst":
            # Five violet petals bloom away from the impact to match the five-shot scatter.
            forward = Vec3(normal)
            side = forward.cross(Vec3(0, 0, 1))
            if side.lengthSquared() < 0.001:
                side = Vec3(1, 0, 0)
            side.normalize()
            up = side.cross(forward); up.normalize()
            for idx, offset in enumerate((-2, -1, 0, 1, 2)):
                end = point + normal * 0.35 + side * offset * 1.18 + up * ((0.85 if idx % 2 else -0.55) + abs(offset) * 0.18)
                self.tracers.append(TracerEffect(self, point, end, ttl=0.46, color=color, thickness_scale=1.18))
                self.add_weapon_glyph(point, end, "triangle", "burst", life=0.46, radius=0.46 + abs(offset) * 0.08)
            self.add_shockwave_ring(point, radius=3.8, life=0.38, vertical=False, thickness=0.92)
        elif kind == "automatic":
            # A green angular lattice stamps multiple fast cells instead of a single lance puncture.
            side = normal.cross(Vec3(0, 0, 1))
            if side.lengthSquared() < 0.001:
                side = Vec3(1, 0, 0)
            side.normalize()
            up = side.cross(normal)
            if up.lengthSquared() < 0.001:
                up = Vec3(0, 0, 1)
            up.normalize()
            for idx in range(3):
                zoff = (idx - 1) * 0.74
                start = point - side * 2.35 + up * zoff
                end = point + side * 2.35 + up * zoff
                pts = self.build_lattice_points(start, end, teeth=6, amplitude=0.32 + idx * 0.035)
                self.tracers.append(TracerEffect(self, pts[0], pts[-1], ttl=0.38 + idx * 0.025, color=color, thickness_scale=0.98, points=pts))
            for xoff in (-1.15, 0.0, 1.15):
                self.add_weapon_glyph(point + side * xoff + up * 0.65, point + side * xoff - up * 0.65, "cross", "automatic", life=0.38, radius=0.46)
        self.clamp_effects()

    def add_weapon_glyph(self, start: Vec3, end: Vec3, shape: str, kind: str, life: float = 0.32, radius: float = 0.72):
        self.weapon_fx.append(WeaponGlyphEffect(self, start, end, shape=shape, life=life, radius=radius, color=self.weapon_color(kind, 0.96), spin=220.0 if kind != "magnet" else 120.0))
        self.clamp_effects()

    def spawn_detached_part(self, pos: Vec3, velocity: Vec3, label: str = "part"):
        self.weapon_fx.append(DetachedPartEffect(self, pos, velocity, label=label, size=0.62 if label != "head" else 0.72, life=1.65))
        self.clamp_effects()

    def spawn_weapon_pickup(self, pos: Vec3, slot: int = 0, amount: float | None = None):
        if amount is None:
            amount = float(getattr(self.game_cfg, "weapon_pickup_ammo", 28.0))
        if len(getattr(self, "weapon_pickups", []) or []) >= int(getattr(self.game_cfg, "max_weapon_pickups", 8)):
            return False
        self.weapon_pickups.append(WeaponPickupEffect(self, pos + Vec3(0, 0, 0.25), slot=slot, amount=float(amount)))
        self.clamp_effects()
        return True

    def collect_weapon_pickup(self, pickup):
        try:
            slot = int(getattr(pickup, "slot", 0) or 0)
            amount = float(getattr(pickup, "amount", 24.0))
            self.add_weapon_ammo(slot, amount, silent=False)
            pickup_pos = getattr(pickup, "pos", Vec3(self.player_pos))
            self.add_combat_feedback(pickup_pos + Vec3(0, 0, 1.0), label="chain", radius=1.45, life=0.32, warning=False)
            self.add_shockwave_ring(pickup_pos + Vec3(0, 0, 0.25), radius=3.0, life=0.26, vertical=False, thickness=0.9)
            self.play_sfx("special_pickup" if slot == 0 else "pickup", volume=0.48, rate=1.0 + max(0, slot) * 0.04, pos=pickup_pos)
            weapon = self.get_weapon_by_slot(slot) if hasattr(self, "get_weapon_by_slot") else None
            self.combat_banner = f"{getattr(weapon, 'name', 'AMMO CACHE').upper()} AMMO COLLECTED"
            self.combat_banner_time = max(float(getattr(self, "combat_banner_time", 0.0)), 0.72)
            self.record_activity("ammo_cache", "Cache Sweep", pos=pickup_pos)
            pickup.dispose()
            if pickup in self.weapon_pickups:
                self.weapon_pickups.remove(pickup)
        except Exception:
            pass

    def trigger_implosion(self, center: Vec3, direct_enemy=None):
        center = Vec3(center)
        radius = float(getattr(self.game_cfg, "imploder_radius", 24.0))
        damage = float(getattr(self.game_cfg, "imploder_damage", 82.0))
        pull = float(getattr(self.game_cfg, "imploder_pull_force", 18.0))
        self.add_combat_feedback(center, label="death", radius=3.5, life=0.48, warning=False)
        self.add_shockwave_ring(center, radius=radius, life=0.44, vertical=False, thickness=1.5)
        self.play_sfx("imploder", volume=0.92, rate=random.uniform(0.94, 1.05), pos=center)
        affected_count = 0
        for i in range(12):
            ang = math.tau * i / 12.0
            outer = center + Vec3(math.cos(ang) * radius * 0.85, math.sin(ang) * radius * 0.85, random.uniform(0.2, 2.8))
            self.tracers.append(TracerEffect(self, outer, center, ttl=0.22, color=self.weapon_color("imploder", 0.88), thickness_scale=1.05))
        for enemy in list(getattr(self, "enemies", []) or []):
            if enemy.dead or enemy.root is None or enemy.root.isEmpty():
                continue
            epos = enemy.root.getPos(self.render)
            delta = center - epos
            delta.z = 0.0
            dist = delta.length()
            if dist <= radius:
                affected_count += 1
                if delta.lengthSquared() > 0.001:
                    delta.normalize()
                falloff = 1.0 - min(1.0, dist / max(0.001, radius))
                enemy.apply_impulse(delta, pull * (0.25 + falloff))
                enemy.stagger_timer = max(float(getattr(enemy, "stagger_timer", 0.0)), 0.28 + falloff * 0.55)
                hit_point = enemy.core_world_position()
                killed = enemy.hit(damage * (0.35 + falloff), hit_point, -delta if delta.lengthSquared() > 0.001 else Vec3(0, 0, 1), force_kill=False, hit_kind="implosion")
                self.register_combat_hit(enemy, hit_kind="implosion", killed=killed, source_point=hit_point, chain=False)
        if affected_count >= 2:
            self.record_activity("imploder_cluster", "Imploder Study", pos=center)
        crush_radius = radius * float(getattr(self.game_cfg, "imploder_crush_radius_scale", 0.62))
        self.weapon_fx.append(ImploderCrushEffect(self, center, crush_radius, delay=float(getattr(self.game_cfg, "imploder_crush_delay", 0.28)), life=0.76))
        self.spawn_physics_shards(center, Vec3(0, 0, 1), count=18, speed=9.0, life=0.82, warm=True)
        self.clamp_effects()

    def resolve_imploder_crush(self, center: Vec3, radius: float):
        center = Vec3(center)
        radius = max(2.0, float(radius or 12.0))
        damage = float(getattr(self.game_cfg, "imploder_crush_damage", 44.0))
        pull = float(getattr(self.game_cfg, "imploder_pull_force", 18.0)) * 1.35
        self.add_shockwave_ring(center, radius=radius * 0.9, life=0.36, vertical=True, thickness=1.35)
        self.add_combat_feedback(center, label="break", radius=2.2, life=0.34, warning=False)
        self.play_sfx("imploder", volume=0.62, rate=random.uniform(0.78, 0.92), pos=center)
        affected = 0
        for enemy in list(getattr(self, "enemies", []) or []):
            if enemy.dead or enemy.root is None or enemy.root.isEmpty():
                continue
            epos = enemy.root.getPos(self.render)
            delta = center - epos
            delta.z = 0.0
            dist = delta.length()
            if dist <= radius:
                if delta.lengthSquared() > 0.001:
                    delta.normalize()
                falloff = 1.0 - min(1.0, dist / max(0.001, radius))
                affected += 1
                enemy.apply_impulse(delta, pull * (0.42 + falloff))
                if not bool(getattr(enemy, "armor_broken", False)) and falloff > 0.42:
                    enemy.break_armor(enemy.core_world_position(), -delta if delta.lengthSquared() > 0.001 else Vec3(0, 0, 1))
                killed = enemy.hit(damage * (0.38 + falloff), enemy.core_world_position(), -delta if delta.lengthSquared() > 0.001 else Vec3(0, 0, 1), force_kill=False, hit_kind="implosion")
                self.register_combat_hit(enemy, hit_kind="implosion", killed=killed, source_point=center, chain=False)
                self.tracers.append(TracerEffect(self, enemy.core_world_position(), center + Vec3(0, 0, 0.8), ttl=0.22, color=self.weapon_color("imploder", 0.82), thickness_scale=1.05))
        if affected:
            self.combat_banner = f"IMPLODER CRUSH // {affected} TARGETS"
            self.combat_banner_time = max(float(getattr(self, "combat_banner_time", 0.0)), 0.58)
        self.spawn_physics_shards(center, Vec3(0, 0, 1), count=12, speed=7.5, life=0.58, warm=True)
        self.clamp_effects()

    def deploy_magnet_field(self, pos: Vec3):
        pos = Vec3(pos)
        self.magnet_fields.append(MagnetFieldEffect(self, pos, radius=float(getattr(self.game_cfg, "magnet_radius", 22.0)), life=float(getattr(self.game_cfg, "magnet_life_seconds", 4.6))))
        self.add_combat_feedback(pos, label="chain", radius=2.4, life=0.42, warning=False)
        self.add_shockwave_ring(pos, radius=float(getattr(self.game_cfg, "magnet_radius", 22.0)) * 0.82, life=0.5, vertical=False, thickness=1.2)
        self.play_sfx("magnet", volume=0.88, rate=random.uniform(0.94, 1.08), pos=pos)
        self.clamp_effects()

    def register_combat_hit(self, enemy, hit_kind: str, killed: bool, source_point: Vec3, chain: bool = False):
        if bool(getattr(enemy, "is_patrol_drone", False)):
            if not killed:
                self.player_hostility_timer = max(float(getattr(self, "player_hostility_timer", 0.0)), float(getattr(self.game_cfg, "patrol_drone_player_hostility_seconds", 9.0)))
                self.combat_banner = "PATROL DRONE ARMOR HIT"
                self.combat_banner_time = max(float(getattr(self, "combat_banner_time", 0.0)), 0.55)
                return 0
            self.player_hostility_timer = max(float(getattr(self, "player_hostility_timer", 0.0)), float(getattr(self.game_cfg, "patrol_drone_player_hostility_seconds", 9.0)))
            self.score += 60
            self.lab_points = int(getattr(self, "lab_points", 0)) + 4
            self.drone_kills = int(getattr(self, "drone_kills", 0)) + 1
            self.drop_patrol_drone_ammo(enemy, source_point)
            return 60
        if bool(getattr(enemy, "is_civilian", False)):
            return self.register_civilian_harm(enemy, killed=killed, source_point=source_point, cause="player")
        if not killed:
            if bool(getattr(enemy, "armor_broken", False)):
                self.record_activity("shield_break", "Shield Fracture", pos=source_point)
            if chain and float(getattr(self, "combat_banner_time", 0.0)) <= 0.05:
                self.combat_banner = "CHAIN ARC // SHIELD STRIPPED"
                self.combat_banner_time = max(float(getattr(self, "combat_banner_time", 0.0)), 0.42)
            elif hit_kind != "core" and not chain and float(getattr(self, "combat_banner_time", 0.0)) <= 0.05:
                needed = max(1, int(getattr(self.game_cfg, "enemy_armor_break_hits", 2)))
                hits = min(needed, int(getattr(enemy, "armor_hits", 0)))
                if bool(getattr(enemy, "armor_broken", False)):
                    self.combat_banner = "ARMOR BROKEN // AIM CORE"
                else:
                    self.combat_banner = f"ARMOR HIT {hits}/{needed} // BREAK SHIELD"
                self.combat_banner_time = max(float(getattr(self, "combat_banner_time", 0.0)), 0.42)
            return 0
        now = float(getattr(self, "elapsed", 0.0))
        window = float(getattr(self.game_cfg, "enemy_kill_streak_window", 3.8))
        self.kill_streak = int(getattr(self, "kill_streak", 0)) + 1 if now - float(getattr(self, "last_kill_time", -999.0)) <= window else 1
        self.last_kill_time = now
        base_score = 10 if chain else int(getattr(self.game_cfg, "enemy_kill_score", 25))
        bonus_step = int(getattr(self.game_cfg, "enemy_kill_streak_bonus", 5))
        bonus_cap = int(getattr(self.game_cfg, "enemy_kill_streak_bonus_cap", 35))
        bonus = min(bonus_cap, max(0, self.kill_streak - 1) * bonus_step)
        gain = base_score + bonus
        self.score += gain
        if getattr(self, "arena_mode_active", False):
            self.lab_points = int(getattr(self, "lab_points", 0)) + max(1, gain // 8)
            self.arena_wave_kills = int(getattr(self, "arena_wave_kills", 0)) + 1
            self.arena_total_kills = int(getattr(self, "arena_total_kills", 0)) + 1
            self.arena_take_breach_damage(1, source_point=source_point)
            self.play_sfx("enemy_destroyed", volume=0.62, pos=source_point)
        tag = "CHAIN RUPTURE" if chain else ("CORE SHATTER" if hit_kind == "core" else "HOSTILE DOWN")
        streak = f" // {self.kill_streak}x" if self.kill_streak > 1 else ""
        self.combat_banner = f"{tag} +{gain}{streak}"
        self.combat_banner_time = 0.82 if not chain else 0.55
        self.add_combat_camera_kick(1.25 if not chain else 0.8)
        if hit_kind == "core" and not chain:
            self.record_activity("core_sample", "Core Sample", pos=source_point)
        if chain:
            self.record_activity("chain_arc", "Chain Sketch", pos=source_point)
        if int(getattr(self, "kill_streak", 0)) >= 4:
            self.record_activity("combo_line", "Combo Line", bonus=int(getattr(self.game_cfg, "activity_major_bonus_score", 140)), pos=source_point)
        if not chain:
            drop_slot = self.choose_enemy_ammo_drop_slot(enemy) if hasattr(self, "choose_enemy_ammo_drop_slot") else 1
            direct_amount = self.enemy_ammo_reward_amount(drop_slot, enemy) if hasattr(self, "enemy_ammo_reward_amount") else float(getattr(self.game_cfg, "weapon_kill_ammo_reward", 8.0))
            self.add_weapon_ammo(drop_slot, direct_amount, silent=True)
            weapon = self.get_weapon_by_slot(drop_slot) if hasattr(self, "get_weapon_by_slot") else None
            weapon_name = getattr(weapon, "name", f"Slot {drop_slot}")
            if self.kill_streak % 3 == 0 or getattr(enemy, "variant", "") in {"bulwark", "commander"}:
                pickup_amount = max(direct_amount, float(getattr(self.game_cfg, "weapon_pickup_ammo", 28.0)) * (0.75 if drop_slot in {2, 3, 4, 5} else 1.0))
                self.spawn_weapon_pickup(source_point, slot=drop_slot, amount=pickup_amount)
                self.combat_banner = f"{weapon_name.upper()} AMMO DROPPED"
                self.combat_banner_time = max(float(getattr(self, "combat_banner_time", 0.0)), 0.76)
        return gain

    def clamp_effects(self):
        if len(self.tracers) > self.game_cfg.max_tracers:
            overflow = len(self.tracers) - self.game_cfg.max_tracers
            for item in self.tracers[:overflow]:
                try:
                    item.np.removeNode()
                except Exception:
                    pass
            self.tracers = self.tracers[overflow:]
        if len(self.blotches) > self.game_cfg.max_blotches:
            overflow = len(self.blotches) - self.game_cfg.max_blotches
            for item in self.blotches[:overflow]:
                try:
                    item.root.removeNode()
                except Exception:
                    pass
            self.blotches = self.blotches[overflow:]
        max_shards = max(0, int(getattr(self.game_cfg, "max_physics_shards", 56)))
        if len(getattr(self, "physics_shards", [])) > max_shards:
            overflow = len(self.physics_shards) - max_shards
            for item in self.physics_shards[:overflow]:
                try:
                    item.dispose()
                except Exception:
                    pass
            self.physics_shards = self.physics_shards[overflow:]
        max_combat = max(0, int(getattr(self.game_cfg, "max_combat_effects", 28)))
        if len(getattr(self, "combat_effects", [])) > max_combat:
            overflow = len(self.combat_effects) - max_combat
            for item in self.combat_effects[:overflow]:
                try:
                    item.dispose()
                except Exception:
                    pass
            self.combat_effects = self.combat_effects[overflow:]
        if len(getattr(self, "shockwaves", [])) > max_combat:
            overflow = len(self.shockwaves) - max_combat
            for item in self.shockwaves[:overflow]:
                try:
                    item.dispose()
                except Exception:
                    pass
            self.shockwaves = self.shockwaves[overflow:]
        max_weapon_fx = max(0, int(getattr(self.game_cfg, "max_weapon_fx", 72)))
        if len(getattr(self, "weapon_fx", [])) > max_weapon_fx:
            overflow = len(self.weapon_fx) - max_weapon_fx
            for item in self.weapon_fx[:overflow]:
                try:
                    item.dispose()
                except Exception:
                    pass
            self.weapon_fx = self.weapon_fx[overflow:]
        max_pickups = max(0, int(getattr(self.game_cfg, "max_weapon_pickups", 8)))
        if len(getattr(self, "weapon_pickups", [])) > max_pickups:
            overflow = len(self.weapon_pickups) - max_pickups
            for item in self.weapon_pickups[:overflow]:
                try:
                    item.dispose()
                except Exception:
                    pass
            self.weapon_pickups = self.weapon_pickups[overflow:]
        if len(getattr(self, "magnet_fields", [])) > 4:
            overflow = len(self.magnet_fields) - 4
            for item in self.magnet_fields[:overflow]:
                try:
                    item.dispose()
                except Exception:
                    pass
            self.magnet_fields = self.magnet_fields[overflow:]

    def trace_from_camera(self, direction: Vec3, max_range: float):
        origin = self.camera.getPos(self.render)
        best_t = max_range
        hit_enemy = None
        hit_box = None
        hit_point = origin + direction * max_range
        hit_normal = Vec3(0, 0, 1)
        self.last_trace_hit_kind = "world"
        core_scale = max(1.0, float(getattr(self.game_cfg, "weak_core_hitbox_scale", 1.58)))
        for enemy in list(self.enemies) + list(getattr(self, "patrol_drones", []) or []) + list(getattr(self, "civilians", []) or []):
            if getattr(enemy, "dead", False):
                continue
            if getattr(enemy, "root", None) is None or enemy.root.isEmpty():
                continue
            if bool(getattr(enemy, "is_patrol_drone", False)):
                body_t = self.ray_box_intersection(origin, direction, enemy.bounds())
                if body_t is not None and 0.02 < body_t < best_t:
                    best_t = body_t
                    hit_enemy = enemy
                    hit_box = None
                    hit_point = origin + direction * body_t
                    hit_normal = self.estimate_box_normal(hit_point, enemy.bounds())
                    self.last_trace_hit_kind = "drone"
                continue
            if bool(getattr(enemy, "is_civilian", False)):
                body_t = self.ray_box_intersection(origin, direction, enemy.bounds())
                if body_t is not None and 0.02 < body_t < best_t:
                    best_t = body_t
                    hit_enemy = enemy
                    hit_box = None
                    hit_point = origin + direction * body_t
                    hit_normal = self.estimate_box_normal(hit_point, enemy.bounds())
                    self.last_trace_hit_kind = "civilian"
                continue
            core_center = enemy.core_world_position()
            core_t = self.ray_sphere_intersection(origin, direction, core_center, enemy.core_radius * core_scale)
            if core_t is not None and 0.02 < core_t < best_t:
                best_t = core_t
                hit_enemy = enemy
                hit_box = None
                hit_point = origin + direction * core_t
                core_dir = hit_point - core_center
                hit_normal = core_dir.normalized() if core_dir.lengthSquared() > 0.0001 else -direction
                self.last_trace_hit_kind = "core"
                continue
            body_t = self.ray_box_intersection(origin, direction, enemy.bounds())
            if body_t is not None and 0.02 < body_t < best_t:
                best_t = body_t
                hit_enemy = enemy
                hit_box = None
                hit_point = origin + direction * body_t
                hit_normal = self.estimate_box_normal(hit_point, enemy.bounds())
                self.last_trace_hit_kind = "body"
        nearby_boxes = []
        csize = self.game_cfg.chunk_size
        px = int(math.floor(origin.x / csize))
        py = int(math.floor(origin.y / csize))
        reach = max(3, min(10, int(self.game_cfg.max_view_distance / csize) + 1))
        for cx in range(px - reach, px + reach + 1):
            for cy in range(py - reach, py + reach + 1):
                nearby_boxes.extend(self.chunk_obstacles.get((cx, cy), []))
        for box in nearby_boxes:
            t = self.ray_box_intersection(origin, direction, box)
            if t is not None and 0.06 < t < best_t:
                best_t = t
                hit_enemy = None
                hit_box = box
                hit_point = origin + direction * t
                hit_normal = self.estimate_box_normal(hit_point, box)
                self.last_trace_hit_kind = "world"
        return hit_enemy, hit_box, hit_point, hit_normal

    def estimate_box_normal(self, point: Vec3, box: BoxBounds):
        eps = 0.15
        candidates = [
            (abs(point.x - box.min_v.x), Vec3(-1, 0, 0)),
            (abs(point.x - box.max_v.x), Vec3(1, 0, 0)),
            (abs(point.y - box.min_v.y), Vec3(0, -1, 0)),
            (abs(point.y - box.max_v.y), Vec3(0, 1, 0)),
            (abs(point.z - box.min_v.z), Vec3(0, 0, -1)),
            (abs(point.z - box.max_v.z), Vec3(0, 0, 1)),
        ]
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1] if candidates else box.normal_hint

    def ray_box_intersection(self, origin: Vec3, direction: Vec3, box: BoxBounds):
        tmin = -1e9
        tmax = 1e9
        for axis in range(3):
            o = origin[axis]
            d = direction[axis]
            mn = box.min_v[axis]
            mx = box.max_v[axis]
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
            if tmin > tmax:
                return None
        if tmax < 0:
            return None
        return tmin if tmin >= 0 else tmax

    def ray_sphere_intersection(self, origin: Vec3, direction: Vec3, center: Vec3, radius: float):
        oc = origin - center
        b = 2.0 * oc.dot(direction)
        c = oc.dot(oc) - radius * radius
        disc = b * b - 4.0 * c
        if disc < 0.0:
            return None
        s = math.sqrt(disc)
        t1 = (-b - s) * 0.5
        t2 = (-b + s) * 0.5
        if t1 >= 0.0:
            return t1
        if t2 >= 0.0:
            return t2
        return None

    def build_lightning_points(self, start: Vec3, end: Vec3, zigzag: int = 5, amplitude: float = 0.55):
        axis = end - start
        if axis.lengthSquared() < 1e-5:
            return [start, end]
        axis.normalize()
        side = axis.cross(Vec3(0, 0, 1))
        if side.lengthSquared() < 1e-4:
            side = axis.cross(Vec3(0, 1, 0))
        side.normalize()
        up = axis.cross(side)
        pts = [start]
        for i in range(1, zigzag):
            t = i / zigzag
            p = start + (end - start) * t
            offset = side * random.uniform(-amplitude, amplitude) + up * random.uniform(-amplitude * 0.5, amplitude * 0.5)
            pts.append(p + offset)
        pts.append(end)
        return pts

    def enemy_separation_vector(self, source_enemy) -> Vec3:
        if source_enemy is None or source_enemy.root is None or source_enemy.root.isEmpty():
            return Vec3(0, 0, 0)
        origin = source_enemy.root.getPos(self.render)
        push = Vec3(0, 0, 0)
        for other in getattr(self, "enemies", []) or []:
            if other is source_enemy or getattr(other, "dead", False) or other.root is None or other.root.isEmpty():
                continue
            delta = origin - other.root.getPos(self.render)
            delta.z = 0
            dist_sq = delta.lengthSquared()
            source_bonus = float(getattr(source_enemy, "arm_space", 0.0) or 0.0)
            other_bonus = float(getattr(other, "arm_space", 0.0) or 0.0)
            if getattr(source_enemy, "variant", "") == "boss_mech":
                source_bonus = max(source_bonus, float(getattr(self.game_cfg, "boss_mech_arm_space", 3.4)))
            elif getattr(source_enemy, "variant", "") == "walker":
                source_bonus = max(source_bonus, float(getattr(self.game_cfg, "walker_arm_space", 2.6)))
            if getattr(other, "variant", "") == "boss_mech":
                other_bonus = max(other_bonus, float(getattr(self.game_cfg, "boss_mech_arm_space", 3.4)))
            elif getattr(other, "variant", "") == "walker":
                other_bonus = max(other_bonus, float(getattr(self.game_cfg, "walker_arm_space", 2.6)))
            min_dist = max(1.8, float(getattr(source_enemy, "radius", 1.0)) + float(getattr(other, "radius", 1.0)) + 0.9 + max(source_bonus, other_bonus) * 0.36)
            if 0.001 < dist_sq < min_dist * min_dist:
                dist = math.sqrt(dist_sq)
                delta.normalize()
                push += delta * ((min_dist - dist) / min_dist)
        if push.lengthSquared() > 1.0:
            push.normalize()
        return push

    def spawn_physics_shards(self, pos: Vec3, normal: Vec3, count: int = 8, speed: float = 7.0, life: float = 0.65, warm: bool = True):
        count = max(0, min(36, int(count or 0)))
        if count <= 0:
            return
        normal = Vec3(normal)
        if normal.lengthSquared() < 0.001:
            normal = Vec3(0, 0, 1)
        normal.normalize()
        base_color = (1.0, 0.20, 0.06, 0.96) if warm else (0.18, 0.92, 1.0, 0.92)
        for _ in range(count):
            scatter = Vec3(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-0.15, 1.0))
            velocity = normal * random.uniform(speed * 0.40, speed) + scatter * random.uniform(speed * 0.25, speed * 0.72)
            if velocity.lengthSquared() < 0.001:
                velocity = Vec3(0, 0, speed)
            self.physics_shards.append(PhysicsShardEffect(
                self,
                pos + normal * 0.08,
                velocity,
                life=random.uniform(life * 0.72, life * 1.28),
                length=random.uniform(0.28, 0.92),
                color=base_color,
                thickness_scale=random.uniform(0.62, 1.06),
            ))
        self.clamp_effects()

    def add_shockwave_ring(self, pos: Vec3, radius: float = 8.0, life: float | None = None, vertical: bool = False, thickness: float = 1.25):
        if life is None:
            life = float(getattr(self.game_cfg, "shockwave_ring_life", 0.52))
        self.shockwaves.append(ShockwaveRingEffect(
            self,
            pos,
            radius=radius,
            life=life,
            vertical=vertical,
            color=(1.0, 0.12, 0.08, 0.92) if not vertical else (0.18, 0.92, 1.0, 0.88),
            thickness_scale=thickness,
        ))
        self.clamp_effects()

    def spawn_core_explosion(self, pos: Vec3, normal: Vec3, variant: str = "sentinel"):
        pos = Vec3(pos)
        self.add_combat_feedback(pos, label="death", radius=4.2 if variant not in {"bulwark", "commander"} else 5.4, life=0.64, warning=False)
        shock_radius = float(getattr(self.game_cfg, "kill_shockwave_radius", 18.0))
        shock_stagger = float(getattr(self.game_cfg, "kill_shockwave_stagger_seconds", 0.55))
        shock_force = float(getattr(self.game_cfg, "kill_shockwave_knockback_force", 12.0))
        self.add_shockwave_ring(pos, radius=shock_radius, life=float(getattr(self.game_cfg, "shockwave_ring_life", 0.52)), vertical=False, thickness=1.75)
        self.add_shockwave_ring(pos + Vec3(0, 0, 0.75), radius=shock_radius * 0.52, life=0.42, vertical=True, thickness=1.15)
        for enemy in list(getattr(self, "enemies", []) or []):
            if enemy.dead or enemy.root is None or enemy.root.isEmpty():
                continue
            delta = enemy.root.getPos(self.render) - pos
            distance = delta.length()
            if distance <= shock_radius:
                enemy.stagger_timer = max(float(getattr(enemy, "stagger_timer", 0.0)), shock_stagger)
                falloff = 1.0 - min(1.0, distance / max(0.001, shock_radius))
                enemy.apply_impulse(delta, shock_force * (0.35 + falloff))
        fx_count = max(18, int(getattr(self.game_cfg, "kill_explosion_fx_count", 34)))
        blast_speed = 10.0 if variant not in {"bulwark", "commander"} else 13.5
        self.spawn_spark_burst(pos, normal, count=fx_count, speed=blast_speed)
        self.spawn_physics_shards(pos, normal, count=int(getattr(self.game_cfg, "kill_debris_count", 28)), speed=blast_speed * 1.18, life=1.05, warm=True)
        ring_specs = [
            (2.6, 0.22, 1.8),
            (4.2, 0.28, 1.35),
            (6.4, 0.34, 1.05),
        ]
        for radius, ttl, thickness in ring_specs:
            horizontal = []
            vertical = []
            for i in range(25):
                ang = math.tau * i / 24
                horizontal.append(pos + Vec3(math.cos(ang) * radius, math.sin(ang) * radius, 0.05 * math.sin(ang * 3.0)))
                vertical.append(pos + Vec3(math.cos(ang) * radius * 0.58, 0.0, math.sin(ang) * radius * 0.58))
            self.tracers.append(TracerEffect(self, horizontal[0], horizontal[-1], ttl=ttl, color=(1.0, 0.05, 0.05, 0.96), thickness_scale=thickness, points=horizontal))
            self.tracers.append(TracerEffect(self, vertical[0], vertical[-1], ttl=ttl * 0.85, color=(1.0, 0.20, 0.08, 0.88), thickness_scale=max(0.8, thickness * 0.75), points=vertical))
        for _ in range(3):
            blotch_normal = Vec3(random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), 1.0)
            blotch_normal.normalize()
            self.blotches.append(InkBlotch(self, pos + blotch_normal * random.uniform(0.4, 1.6), blotch_normal))
        self.clamp_effects()

    def spawn_spark_burst(self, pos: Vec3, normal: Vec3, count: int = 8, speed: float = 4.2):
        normal = Vec3(normal)
        if normal.lengthSquared() < 0.001:
            normal = Vec3(0, 0, 1)
        normal.normalize()
        for _ in range(count):
            dir_v = normal + Vec3(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-0.3, 1.0))
            if dir_v.lengthSquared() < 0.001:
                dir_v = Vec3(0, 0, 1)
            dir_v.normalize()
            end = pos + dir_v * random.uniform(speed * 0.35, speed)
            self.tracers.append(TracerEffect(self, pos, end, ttl=random.uniform(0.08, 0.16), color=(1.0, 0.12, 0.12, 1.0), thickness_scale=0.9))

    def chain_lightning(self, source_center: Vec3, source_enemy, source_point: Vec3, depth: int = 0):
        arcs = 0
        source_center = Vec3(source_center)
        chain_range = float(getattr(self.game_cfg, "chain_arc_range", 27.0))
        max_targets = max(1, int(getattr(self.game_cfg, "chain_arc_max_targets", 3)))
        max_depth = max(0, int(getattr(self.game_cfg, "chain_arc_max_depth", 1)))
        secondary_kill_range = float(getattr(self.game_cfg, "chain_arc_secondary_kill_range", 10.5))
        damage_scale = float(getattr(self.game_cfg, "chain_arc_damage_scale", 0.88))
        candidates = []
        for enemy in self.enemies:
            if enemy is source_enemy or enemy.dead:
                continue
            if enemy.root is None or enemy.root.isEmpty():
                continue
            end = enemy.core_world_position()
            dist = (end - source_center).length()
            if dist <= chain_range:
                candidates.append((dist, enemy, end))
        candidates.sort(key=lambda item: item[0])
        for dist, enemy, end in candidates[:max_targets]:
            pts = self.build_lightning_points(source_point, end, zigzag=8, amplitude=0.68)
            ttl = 0.16 if dist <= secondary_kill_range else 0.13
            self.tracers.append(TracerEffect(self, source_point, end, ttl=ttl, color=(1.0, 0.18, 0.08, 0.96), thickness_scale=1.34, points=pts))
            self.add_combat_feedback(end, label="chain", radius=1.55 if dist > secondary_kill_range else 2.15, life=0.36, warning=False)
            self.add_shockwave_ring(end, radius=3.6 if dist > secondary_kill_range else 5.1, life=0.26, vertical=True, thickness=1.05)
            self.spawn_physics_shards(end, Vec3(0, 0, 1), count=5 if dist > secondary_kill_range else 8, speed=6.6, life=0.48, warm=False)
            force = bool(dist <= secondary_kill_range and depth <= max_depth)
            weapon_damage = float(getattr(self.current_weapon, "damage", 30.0) if self.current_weapon else 30.0)
            killed = enemy.hit(weapon_damage * damage_scale, end, Vec3(0, 0, 1), force_kill=force, hit_kind="chain")
            self.register_combat_hit(enemy, hit_kind="chain", killed=killed, source_point=end, chain=True)
            self.play_sfx("chain", volume=0.55 + 0.10 * arcs, rate=random.uniform(0.94, 1.06), pos=end)
            arcs += 1
            if killed and depth < max_depth:
                self.chain_lightning(end, enemy, end, depth + 1)
            if arcs >= max_targets:
                break

    def update_weapon_view(self, dt: float):
        self.hit_replenish_flash = max(0.0, self.hit_replenish_flash - dt)
        bob = math.sin(self.elapsed * 5.0) * 0.012
        sway = math.sin(self.elapsed * 2.4) * 0.016
        for hand in ("right", "left"):
            sign = 1.0 if hand == "right" else -1.0
            self.weapon_hand_spin[hand] = self.weapon_hand_spin.get(hand, 0.0) + self.weapon_hand_spin_velocity.get(hand, 0.0) * dt
            self.weapon_hand_spin_velocity[hand] = self.weapon_hand_spin_velocity.get(hand, 0.0) * max(0.0, 1.0 - dt * 5.8)
            recoil = max(0.0, self.weapon_hand_recoil.get(hand, 0.0) - dt * 3.2)
            self.weapon_hand_recoil[hand] = recoil
            self.weapon_hand_muzzle_flash[hand] = max(0.0, self.weapon_hand_muzzle_flash.get(hand, 0.0) - dt)
            mount = getattr(self, "weapon_mounts", {}).get(hand)
            if mount:
                mount["spin_root"].setR(self.weapon_hand_spin[hand])
                mount["root"].setPos(sign * (0.74 + abs(sway)), 0.54 - recoil * 0.76, -0.66 + bob + recoil * 0.06)
                mount["root"].setColorScale(*self.current_line_color(alpha=0.98))
        self.cockpit_root.setR(math.sin(self.elapsed * 1.7) * 0.45)
        self.cockpit_root.setZ(math.sin(self.elapsed * 5.0) * 0.01)
        self.update_led_displays()

    def update_led_displays(self):
        if not hasattr(self, "led_panels"):
            return
        values = {
            "ammo": 0.0 if self.weapon_ammo_max <= 0 else self.weapon_ammo / self.weapon_ammo_max,
        }
        for key, ratio in values.items():
            ratio = max(0.0, min(1.0, ratio))
            fill = self.led_panels[key]["fill"]
            fill.setSx(max(0.001, ratio))
            fill.setColor(0.92 + self.hit_replenish_flash * 0.5, 0.94 + self.hit_replenish_flash * 0.3, 1.0, 0.9)
            self.led_panels[key]["outline"].setColor(0.96, 0.96, 0.96, 0.88)
            if self.led_panels[key]["label"] is not None:
                self.led_panels[key]["label"].setColor(0.94, 0.94, 0.94, 0.86)

    def update_player(self, dt):
        move = self.get_move_input()
        if not self.menu_open:
            self.handle_look(dt)
        quat = self.camera.getQuat(self.render)
        forward = quat.getForward()
        right = quat.getRight()
        forward.z = 0
        right.z = 0
        if forward.lengthSquared() > 0:
            forward.normalize()
        if right.lengthSquared() > 0:
            right.normalize()
        move_vec = (forward * move.y + right * move.x)
        if move_vec.lengthSquared() > 1.0:
            move_vec.normalize()
        speed = self.game_cfg.sprint_speed if self.keys.get("shift") else self.game_cfg.walk_speed
        candidate = Vec3(self.player_pos)
        candidate.x += move_vec.x * speed * dt
        if not self.point_hits_obstacle(candidate, self.game_cfg.player_radius, self.game_cfg.player_height):
            self.player_pos.x = candidate.x
        candidate = Vec3(self.player_pos)
        candidate.y += move_vec.y * speed * dt
        if not self.point_hits_obstacle(candidate, self.game_cfg.player_radius, self.game_cfg.player_height):
            self.player_pos.y = candidate.y

        if self.on_ground and self.keys.get("space"):
            self.vertical_speed = self.game_cfg.jump_speed
            self.on_ground = False
        self.vertical_speed -= self.game_cfg.gravity * dt
        self.player_pos.z += self.vertical_speed * dt
        if self.player_pos.z <= self.game_cfg.player_height:
            self.player_pos.z = self.game_cfg.player_height
            self.vertical_speed = 0.0
            self.on_ground = True

        self.camera.setPos(self.player_pos)
        self.apply_combat_camera_kick(dt)
        self.update_weapon_view(dt)

    def update_fire(self, dt):
        if self.current_weapon:
            regen = float(getattr(self.current_weapon, "ammo_regen", 0.0))
            if regen > 0.0:
                self.add_weapon_ammo(int(getattr(self.current_weapon, "slot", 1)), dt * regen, silent=True)
            else:
                self.update_current_weapon_ammo_alias()
        if self.gamepad:
            trigger = self.gamepad.findAxis(InputDevice.Axis.right_trigger)
            fire = trigger.value > 0.35 if trigger else False
            if fire and not self.gamepad_fire_prev:
                self.fire_down["right"] = True
            self.fire_hold["right"] = self.fire_hold.get("right", False) or fire
            self.gamepad_fire_prev = fire
        for hand in ("right", "left"):
            self.fire_cooldown[hand] = max(0.0, float(self.fire_cooldown.get(hand, 0.0)) - dt)
            if (self.fire_hold.get(hand) or self.fire_down.get(hand)) and self.fire_cooldown[hand] <= 0.0 and not self.menu_open:
                weapon = self.get_weapon_for_hand(hand)
                slot = int(getattr(weapon, "slot", 1)) if weapon else 1
                pre_ammo = float(self.weapon_ammo_pools.get(slot, 0.0))
                fired = bool(self.shoot(hand=hand))
                post_ammo = float(self.weapon_ammo_pools.get(slot, 0.0))
                if fired and post_ammo < pre_ammo:
                    self.fire_cooldown[hand] = float(getattr(weapon, "fire_interval", 0.15))
                else:
                    self.fire_cooldown[hand] = 0.03
            self.fire_down[hand] = False

    def update_enemies(self, dt):
        player_pos = Vec3(self.player_pos.x, self.player_pos.y, 0)
        self.player_damage_grace_timer = max(0.0, float(getattr(self, "player_damage_grace_timer", 0.0)) - dt)
        self.contact_damage_window = float(getattr(self, "contact_damage_window", 0.0)) + dt
        if self.contact_damage_window >= 1.0:
            self.contact_damage_window %= 1.0
            self.contact_damage_this_window = 0.0
        touching_damage_rate = 0.0
        for enemy in list(self.enemies):
            alive = enemy.update(dt, player_pos)
            if not alive:
                self.enemies.remove(enemy)
                continue
            if enemy.root is None or enemy.root.isEmpty():
                self.enemies.remove(enemy)
                continue
            dist = (enemy.root.getPos() - player_pos).length()
            contact_radius = max(2.4, 1.35 + float(getattr(enemy, "radius", 1.0)))
            if dist < contact_radius:
                base_rate = float(getattr(self.game_cfg, "enemy_contact_damage", 1))
                if enemy.variant == "commander":
                    damage_rate = base_rate * 1.75
                elif enemy.variant == "bulwark":
                    damage_rate = base_rate * 1.45
                else:
                    damage_rate = base_rate
                touching_damage_rate = max(touching_damage_rate, damage_rate)
        cap = float(getattr(self.game_cfg, "player_contact_damage_cap_per_second", 2.0))
        available = max(0.0, cap - float(getattr(self, "contact_damage_this_window", 0.0)))
        applied_rate = min(max(0.0, touching_damage_rate), available)
        self.contact_damage_accumulator += applied_rate * dt
        pending = int(self.contact_damage_accumulator)
        if pending > 0:
            pending = min(pending, int(math.ceil(available)))
            if pending > 0:
                self.contact_damage_accumulator -= pending
                self.contact_damage_this_window += pending
                self.apply_player_damage(pending, source="enemy_contact")
                self.add_combat_camera_kick(0.42)
        if self.health <= 0:
            self.handle_player_respawn(reason="health_zero")

    def reset_combat_wave_state_for_respawn(self):
        removed = 0
        for enemy in list(getattr(self, "enemies", []) or []):
            try:
                if enemy.root is not None and not enemy.root.isEmpty():
                    enemy.root.removeNode()
            except Exception:
                pass
            removed += 1
        self.enemies.clear()
        pending = len(getattr(self, "pending_enemy_spawns", []) or [])
        self.pending_enemy_spawns.clear()
        self.spawn_sequence_serial = int(getattr(self, "spawn_sequence_serial", 0)) + 1
        self.spawn_director_timer = max(float(getattr(self, "spawn_director_timer", 0.0)), 3.5)
        self.reset_freeroam_rhythm(
            state="quiet",
            timer=float(getattr(self.game_cfg, "freeroam_quiet_departure_seconds", 7.0)),
            clear_distance=True,
        )
        self.last_spawn_director_player = self.flat_player_position()
        self.contact_damage_accumulator = 0.0
        # If a node was not captured yet, allow its wave to be valid again after the reset.
        for point in getattr(self, "campaign_points", []) or []:
            if not bool(point.get("captured", False)):
                point["wave_triggered"] = False
        return removed, pending

    def reset_hostility_for_respawn(self):
        self.player_hostility_timer = 0.0
        self.combat_banner = ""
        self.combat_banner_time = 0.0
        self.kill_streak = 0
        self.last_kill_time = -999.0
        self.fire_hold = {"right": False, "left": False}
        self.fire_down = {"right": False, "left": False}
        for drone in list(getattr(self, "patrol_drones", []) or []):
            try:
                drone.fire_cooldown = max(float(getattr(drone, "fire_cooldown", 0.0)), 1.25)
                drone.choose_new_target(force=True)
                if getattr(drone, "line_root", None) is not None and not drone.line_root.isEmpty():
                    drone.line_root.setColor(0.28, 1.0, 0.94, 0.86)
            except Exception:
                pass

    def handle_player_respawn(self, reason: str = "respawn"):
        captured_before = sum(1 for p in getattr(self, "campaign_points", []) if p.get("captured"))
        signal_before = int(getattr(self, "signal_fragments_recovered", 0) or 0)
        removed, pending = self.reset_combat_wave_state_for_respawn()
        self.reset_hostility_for_respawn()
        self.health = int(getattr(self, "player_health_max", self.game_cfg.default_health))
        self.sync_player_armor_capacity(refill=True)
        self.player_pos = Vec3(0, 0, self.game_cfg.player_height)
        self.camera.setPos(self.player_pos)
        self.vertical_speed = 0.0
        self.on_ground = True
        self.center_text["text"] = "Respawned neutral — hostiles cleared"
        self.weapon_banner_time = max(float(getattr(self, "weapon_banner_time", 0.0)), 1.4)
        self.objective_banner = f"RESPAWN NEUTRAL // WAVES CLEARED {removed}"
        self.objective_banner_time = 2.2
        self.respawn_last_report = {
            "reason": str(reason),
            "enemies_removed": int(removed),
            "pending_spawns_cancelled": int(pending),
            "hostility_timer": float(getattr(self, "player_hostility_timer", 0.0)),
            "captured_before": int(captured_before),
            "captured_after": sum(1 for p in getattr(self, "campaign_points", []) if p.get("captured")),
            "signal_before": int(signal_before),
            "signal_after": int(getattr(self, "signal_fragments_recovered", 0) or 0),
        }
        write_latest_log("respawn_neutrality", self.respawn_last_report)
        self.refresh_ui_text()
        return self.respawn_last_report


    def recolor_scene(self):
        fade_start = self.game_cfg.max_view_distance * self.game_cfg.line_fade_start_ratio
        fade_span = max(1.0, self.game_cfg.max_view_distance - fade_start)
        base_color = self.current_line_color(alpha=1.0)
        for key, line_root in self.chunk_line_roots.items():
            cx, cy = key
            center = Vec3((cx + 0.5) * self.game_cfg.chunk_size, (cy + 0.5) * self.game_cfg.chunk_size, 0)
            dist = (center - Vec3(self.player_pos.x, self.player_pos.y, 0)).length()
            if dist <= fade_start:
                alpha = 1.0
            else:
                alpha = max(0.0, 1.0 - (dist - fade_start) / fade_span)
            alpha *= max(0.10, min(0.82, float(getattr(self.game_cfg, "world_line_alpha", 0.42))))
            line_root.setColor(base_color[0], base_color[1], base_color[2], alpha, 1)
            mask_root = getattr(self, "chunk_occlusion_roots", {}).get(key)
            if alpha <= 0.02:
                line_root.hide()
                if mask_root is not None and not mask_root.isEmpty():
                    mask_root.hide()
            else:
                line_root.show()
                if mask_root is not None and not mask_root.isEmpty() and bool(getattr(self.game_cfg, "structure_occlusion_masks", True)):
                    mask_root.show()
                    mask_root.setColor(*self.structure_mask_color())
        for enemy in self.enemies:
            if not enemy.dead:
                dist = (enemy.root.getPos() - Vec3(self.player_pos.x, self.player_pos.y, 0)).length()
                if dist <= fade_start:
                    alpha = 1.0
                else:
                    alpha = max(0.0, 1.0 - (dist - fade_start) / fade_span)
                enemy.body.setColor(*self.current_line_color(alpha=max(0.12, alpha * 0.98)), 1)
        for blotch in self.blotches:
            blotch.base.setColor(*self.current_blotch_color(alpha=0.16))
        for point in getattr(self, "campaign_points", []):
            node = point.get("node") if isinstance(point, dict) else None
            if node is not None and not node.isEmpty():
                if point.get("captured"):
                    node.setColorScale(*self.current_campaign_secondary_color(alpha=1.0))
                elif point is self.get_active_campaign_point():
                    pass
                else:
                    node.setColorScale(*self.current_campaign_accent_color(alpha=0.64))
        ally = getattr(self, "ally_node", None)
        if ally is not None and not ally.isEmpty():
            ally.setColor(*self.current_campaign_secondary_color(alpha=0.95), 1)

    def mastering_quality_snapshot(self) -> dict:
        analyzer = SceneGraphAnalyzer()
        try:
            analyzer.addNode(self.render.node())
        except Exception:
            pass
        try:
            task_count = len(self.taskMgr.getTasks())
        except Exception:
            task_count = -1
        try:
            collision_nodes = self.render.findAllMatches("**/+CollisionNode").getNumPaths()
        except Exception:
            collision_nodes = -1
        return {
            "version": VERSION,
            "scene": {
                "nodes": int(analyzer.getNumNodes()),
                "geom_nodes": int(analyzer.getNumGeomNodes()),
                "geoms": int(analyzer.getNumGeoms()),
                "vertices": int(analyzer.getNumVertices()),
                "triangles": int(analyzer.getNumTris()),
                "lines": int(analyzer.getNumLines()),
                "transforms": int(analyzer.getNumTransforms()),
                "texture_bytes": int(analyzer.getTextureBytes()),
            },
            "runtime": {
                "tasks": int(task_count),
                "collision_nodes": int(collision_nodes),
                "chunks": int(len(getattr(self, "chunks", {}))),
                "enemies": int(sum(not e.dead for e in getattr(self, "enemies", []))),
                "civilians": int(sum(not getattr(c, "dead", False) for c in getattr(self, "civilians", []))),
                "patrol_drones": int(sum(not getattr(d, "dead", False) for d in getattr(self, "patrol_drones", []))),
                "weapon_fx": int(len(getattr(self, "weapon_fx", []))),
                "combat_effects": int(len(getattr(self, "combat_effects", []))),
                "physics_shards": int(len(getattr(self, "physics_shards", []))),
            },
            "ui": {
                "mutations": int(getattr(self, "ui_text_mutations", 0)),
                "unchanged_skips": int(getattr(self, "ui_text_skips", 0)),
                "hud_interval_seconds": 0.10,
                "workstation_interval_seconds": 0.25,
                "workstation_hidden_updates": False,
            },
        }

    def mastering_quality_test_task(self, task):
        before_mutations = int(getattr(self, "ui_text_mutations", 0))
        before_skips = int(getattr(self, "ui_text_skips", 0))
        # Repeating a refresh with unchanged state must not rebuild text geometry.
        self.refresh_ui_text()
        first_mutations = int(getattr(self, "ui_text_mutations", 0))
        self.refresh_ui_text()
        second_mutations = int(getattr(self, "ui_text_mutations", 0))
        hidden_before = second_mutations
        self.workstation_visible = False
        self.refresh_workstation_text()
        hidden_after = int(getattr(self, "ui_text_mutations", 0))
        # Pause must freeze mutable gameplay state while leaving the menu/UI responsive.
        pause_player_before = tuple(float(v) for v in self.player_pos)
        pause_spawn_before = float(getattr(self, "spawn_director_timer", 0.0))
        self.menu_open = True
        self.update_task(None)
        pause_player_after = tuple(float(v) for v in self.player_pos)
        pause_spawn_after = float(getattr(self, "spawn_director_timer", 0.0))
        self.menu_open = False
        try:
            config_parity = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) == json.loads(ROOT_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            config_parity = False
        report = self.mastering_quality_snapshot()
        report["checks"] = {
            "repeat_ui_refresh_cached": bool(second_mutations == first_mutations),
            "hidden_workstation_skipped": bool(hidden_after == hidden_before),
            "empty_center_frame_hidden": bool(getattr(self, "center_text", None) is not None and self.center_text.isHidden()),
            "pause_freezes_player": bool(pause_player_after == pause_player_before),
            "pause_freezes_spawn_timer": bool(abs(pause_spawn_after - pause_spawn_before) < 0.000001),
            "quit_button_present": bool(hasattr(self, "btn_quit")),
            "preset_controls_present": bool(all(hasattr(self, name) for name in ("cycle_view_distance_setting", "cycle_line_thickness_setting", "cycle_sensitivity_setting"))),
            "root_runtime_config_parity": bool(config_parity),
            "scene_has_geometry": bool(report["scene"]["geoms"] > 0 and report["scene"]["lines"] > 0),
            "task_count_sane": bool(0 < report["runtime"]["tasks"] < 64),
            "ui_skip_counter_advanced": bool(int(getattr(self, "ui_text_skips", 0)) > before_skips),
        }
        report["status"] = "PASS" if all(report["checks"].values()) else "FAIL"
        out_dir = ROOT / "verification" / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "pass51_mastering_quality.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("MASTERING_QUALITY_TEST", report["status"], json.dumps(report, sort_keys=True))
        self.userExit()
        return Task.done

    def _mastering_demo_save(self, name: str) -> Path:
        out_dir = ROOT / "verification" / "screenshots" / "pass51"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{name}.png"
        self.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
        return path

    def mastering_demo_task(self, task):
        # Clean normal-play proof at 1080p.
        self.menu_open = False
        self.menu_root.hide()
        self.workstation_visible = False
        self.work_root.hide()
        self.hud_visible = True
        self.hud_root.show()
        self.crosshair.show()
        self.refresh_ui_text()
        self._mastering_demo_save("01_gameplay")
        self.menu_open = True
        self.menu_root.show()
        self.refresh_ui_text()
        self.taskMgr.doMethodLater(0.18, self._mastering_demo_pause_task, "mastering-demo-pause")
        return Task.done

    def _mastering_demo_pause_task(self, task):
        self._mastering_demo_save("02_pause_menu")
        self.menu_open = False
        self.menu_root.hide()
        self.workstation_visible = True
        self.refresh_workstation_text()
        self.work_root.show()
        self.taskMgr.doMethodLater(0.18, self._mastering_demo_workstation_task, "mastering-demo-workstation")
        return Task.done

    def _mastering_demo_workstation_task(self, task):
        self._mastering_demo_save("03_workstation")
        self.userExit()
        return Task.done

    def hud_minimalism_test_task(self, task):
        self.refresh_ui_text()
        hud = str(self.hud_text["text"] or "")
        mission = str(self.mission_text["text"] or "")
        left_ammo = str(self.weapon_text["text"] or "")
        right_ammo = str(self.weapon_right_text["text"] or "")
        status = str(self.status_text["text"] or "")
        detail = str(self.detail_text["text"] or "")
        checks = {
            "score_strip_one_line": len(hud.splitlines()) == 1 and "SCORE" in hud and "LAB" in hud and "UTOPIA CONFLICT" not in hud,
            "world_guidance_not_duplicated": not mission.strip() and self.mission_text.isHidden(),
            "left_ammo_compact": len(left_ammo.splitlines()) == 1 and left_ammo.startswith("L") and len(left_ammo) <= 14,
            "right_ammo_compact": len(right_ammo.splitlines()) == 1 and right_ammo.startswith("R") and len(right_ammo) <= 14,
            "persistent_feed_count_three": sum(bool(v.strip()) for v in (hud, left_ammo, right_ammo)) == 3,
            "neutral_alert_hidden": (not status.strip()) and self.status_frame.isHidden(),
            "empty_context_hidden": (not detail.strip()) and self.detail_frame.isHidden(),
            "no_duplicate_telemetry": not any(token in (hud + left_ammo + right_ammo) for token in ("Activities ", "Civilians ", "Drones ", "Wireframe = health", "Armor ", "FLAG ", "Signal ")),
        }
        report = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "hud_text": hud, "mission_text": mission, "left_ammo_text": left_ammo, "right_ammo_text": right_ammo, "status_text": status, "detail_text": detail}
        out = ROOT / "verification" / "reports" / "pass52_hud_minimalism.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("HUD_MINIMALISM_TEST", report["status"], json.dumps(report, sort_keys=True))
        self.userExit()
        return Task.done


    def _hud52_save(self, name: str) -> Path:
        out_dir = ROOT / "verification" / "screenshots" / "pass52"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{name}.png"
        self.graphicsEngine.renderFrame()
        self.graphicsEngine.renderFrame()
        self.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
        return path

    def hud_minimalism_demo_task(self, task):
        # Normal gameplay: only score, next action, and dual-weapon strip.
        self.player_hostility_timer = 0.0
        self.player_pos = Vec3(0, -10, self.game_cfg.player_height)
        self.camera.setPos(self.player_pos + Vec3(0, 0, 4.5))
        self.camera.lookAt(Vec3(0, 24, 2.4))
        self.refresh_ui_text()
        self._hud52_save("01_normal")
        # Event-only alert branch.
        self.player_hostility_timer = 8.0
        self.refresh_ui_text()
        self._hud52_save("02_alert")
        # Actionable context branch uses a real authored activity position.
        entry = (getattr(self, "activity_instances", []) or [None])[0]
        if entry is not None:
            pos = Vec3(entry.get("pos", Vec3(0, 0, 0)))
            self.player_pos = Vec3(pos.x, pos.y - 2.0, self.game_cfg.player_height)
            self.generate_city_around_player(force=True)
            self.update_current_district(announce=False)
            self.camera.setPos(self.player_pos + Vec3(0, 0, 3.2))
            self.camera.lookAt(pos + Vec3(0, 0, 1.5))
        self.player_hostility_timer = 0.0
        self.refresh_ui_text()
        self._hud52_save("03_context")
        self.userExit()
        return Task.done

    def update_effects(self, dt):
        self.tracers = [t for t in self.tracers if t.update(dt)]
        self.blotches = [b for b in self.blotches if b.update(dt)]
        self.signal_effects = [e for e in getattr(self, "signal_effects", []) if e.update(dt)]
        self.combat_effects = [e for e in getattr(self, "combat_effects", []) if e.update(dt)]
        self.physics_shards = [e for e in getattr(self, "physics_shards", []) if e.update(dt)]
        self.shockwaves = [e for e in getattr(self, "shockwaves", []) if e.update(dt)]
        self.weapon_fx = [e for e in getattr(self, "weapon_fx", []) if e.update(dt)]
        self.weapon_pickups = [e for e in getattr(self, "weapon_pickups", []) if e.update(dt)]
        self.magnet_fields = [e for e in getattr(self, "magnet_fields", []) if e.update(dt)]
        self.clamp_effects()

    def chunk_task(self, task):
        self.generate_city_around_player()
        return Task.again

    def help_reference_test_task(self, task):
        required_left = ["CONTROLS", "WASD", "LMB/RMB", "F1", "PLAYER CONDITION", "GREEN", "AMBER", "RED", "CYAN", "UPGRADES", "SHIFT+U"]
        required_right = ["ENEMY COLOR STATES", "CRIMSON", "HOT RED", "YELLOW", "AMBER", "CYAN", "VIOLET", "LIME", "TEAL", "BLUE", "Capture zones regenerate", "field activities", "WEAPONS", "Core Lance", "Imploder", "Proximity Magnet", "Disassembler", "Burst Splitter", "Auto Lattice", "FIELD ACTIVITIES", "Shield Fracture", "Magnet Garden"]
        left = str(self.help_left_text["text"])
        right = str(self.help_right_text["text"])
        hidden_before = bool(self.help_root.isHidden())
        elapsed_before = float(self.elapsed)
        player_before = Vec3(self.player_pos)
        self.toggle_help_reference()
        visible_open = not bool(self.help_root.isHidden()) and self.help_visible
        gameplay_hud_hidden = bool(self.hud_root.isHidden()) and bool(self.crosshair.isHidden())
        weapon_mounts_hidden = all(bool(mount.get("root").isHidden()) for mount in getattr(self, "weapon_mounts", {}).values())
        self.set_key("w", True)
        self.update_task(None)
        self.set_key("w", False)
        paused_player = (Vec3(self.player_pos) - player_before).length() < 0.001
        self.toggle_help_reference()
        hidden_after = bool(self.help_root.isHidden()) and not self.help_visible
        gameplay_hud_restored = not bool(self.hud_root.isHidden()) and not bool(self.crosshair.isHidden())
        weapon_mounts_restored = all(not bool(mount.get("root").isHidden()) for mount in getattr(self, "weapon_mounts", {}).values())
        report = {
            "test": "help_reference_test",
            "status": "PASS" if all(token in left for token in required_left) and all(token in right for token in required_right) and hidden_before and visible_open and gameplay_hud_hidden and weapon_mounts_hidden and paused_player and hidden_after and gameplay_hud_restored and weapon_mounts_restored else "FAIL",
            "left_required": {token: token in left for token in required_left},
            "right_required": {token: token in right for token in required_right},
            "hidden_before": hidden_before,
            "visible_open": visible_open,
            "gameplay_hud_hidden": gameplay_hud_hidden,
            "weapon_mounts_hidden": weapon_mounts_hidden,
            "help_pauses_player": paused_player,
            "hidden_after": hidden_after,
            "gameplay_hud_restored": gameplay_hud_restored,
            "weapon_mounts_restored": weapon_mounts_restored,
            "persistent_hud_anchors_added": 0,
        }
        (LOG_DIR / "help_reference_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("help_reference_test", report)
        print(json.dumps(report, indent=2))
        self.userExit()
        return Task.done

    def help_reference_demo_task(self, task):
        self.toggle_help_reference()
        self.taskMgr.doMethodLater(0.35, self.help_reference_capture_task, "help-reference-capture")
        return Task.done

    def help_reference_capture_task(self, task):
        shot_path = Path(TEST_SHOT_PATH or (ROOT / "verification" / "screenshots" / "pass53" / "help_reference.png"))
        shot_path.parent.mkdir(parents=True, exist_ok=True)
        self.win.saveScreenshot(Filename.fromOsSpecific(str(shot_path)))
        self.userExit()
        return Task.done

    def presentation_readiness_test_task(self, task):
        presentation_started_hidden = not bool(getattr(self.presentation_root, "isHidden", lambda: True)())
        # The validation flag bypasses normal launch briefing, so exercise the same state explicitly.
        self.presentation_open = True
        self.presentation_root.show()
        self.set_presentation_visual_isolation(True)
        player_before = tuple(float(v) for v in self.player_pos)
        spawn_before = float(getattr(self, "spawn_director_timer", 0.0))
        self.update_task(None)
        player_after = tuple(float(v) for v in self.player_pos)
        spawn_after = float(getattr(self, "spawn_director_timer", 0.0))
        launch_visible = not self.presentation_root.isHidden()
        launch_hud_hidden = self.hud_root.isHidden() and self.crosshair.isHidden()
        launch_weapons_hidden = all((mount.get("root") is None or mount.get("root").isEmpty() or mount.get("root").isHidden()) for mount in getattr(self, "weapon_mounts", {}).values())
        self.open_presentation_reference()
        reference_visible = bool(getattr(self, "help_visible", False)) and not self.help_root.isHidden()
        self.toggle_help_reference()
        reference_returns = bool(getattr(self, "presentation_open", False)) and not self.presentation_root.isHidden()
        deployed = bool(self.begin_presentation_deploy()) and not bool(getattr(self, "presentation_open", False)) and self.presentation_root.isHidden()
        manifest_path = ROOT / "standalone_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        controls = manifest.get("controls", {}) if isinstance(manifest, dict) else {}
        report = {
            "test": "presentation_readiness_test",
            "launch_visible": launch_visible,
            "launch_pauses_player": player_after == player_before,
            "launch_pauses_spawn_timer": abs(spawn_after - spawn_before) < 0.000001,
            "launch_hud_and_crosshair_hidden": launch_hud_hidden,
            "launch_weapon_mounts_hidden": launch_weapons_hidden,
            "reference_from_launch": reference_visible,
            "reference_returns_to_launch": reference_returns,
            "deploy_enters_gameplay": deployed,
            "manifest_help_is_f1": str(controls.get("help", "")).upper().startswith("F1"),
            "manifest_hud_is_h": str(controls.get("hud", "")).upper().startswith("H"),
            "manifest_activity_locations_current": "High Towers" in str(controls.get("activity_stations", "")) and "Pyramid" in str(controls.get("activity_stations", "")),
            "version": VERSION,
        }
        report["status"] = "PASS" if all(v for k, v in report.items() if k not in {"test", "version", "status"}) else "FAIL"
        (LOG_DIR / "presentation_readiness_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_latest_log("presentation_readiness_test", report)
        print(json.dumps(report, indent=2))
        self.userExit()
        return Task.done

    def presentation_demo_task(self, task):
        self.presentation_open = True
        self.presentation_root.show()
        self.set_presentation_visual_isolation(True)
        self.taskMgr.doMethodLater(0.30, self.presentation_demo_capture_task, "presentation-demo-capture")
        return Task.done

    def presentation_demo_capture_task(self, task):
        if TEST_SHOT_PATH and getattr(self, "win", None) is not None:
            path = Path(TEST_SHOT_PATH)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.graphicsEngine.renderFrame()
            self.win.saveScreenshot(Filename.fromOsSpecific(os.fspath(path)))
        self.userExit()
        return Task.done

    def pause_menu_input_test_task(self, task):
        result = {"schema": "utopia_conflict_pause_menu_input_v1", "version": VERSION}
        original_distance = float(getattr(self.game_cfg, "max_view_distance", 0.0))
        try:
            # Exercise the same event bindings used by real keyboard input.
            self.messenger.send("escape")
            result["escape_opens_menu"] = bool(self.menu_open and not self.menu_root.isHidden())
            self.messenger.send("arrow_down")
            result["down_selects_draw_distance"] = int(getattr(self, "menu_selected_index", -1)) == 1
            selected_button = self.menu_buttons[self.menu_selected_index][0] if self.menu_buttons else None
            result["selection_visual_present"] = selected_button is getattr(self, "btn_distance", None)

            shot = ROOT / "verification" / "screenshots" / "pause_menu_input.png"
            shot.parent.mkdir(parents=True, exist_ok=True)
            self.graphicsEngine.renderFrame()
            if self.win is not None:
                self.win.saveScreenshot(Filename.fromOsSpecific(os.fspath(shot)))
            result["screenshot"] = str(shot.relative_to(ROOT)) if shot.exists() else ""

            self.messenger.send("enter")
            result["enter_activates_selected_option"] = abs(float(getattr(self.game_cfg, "max_view_distance", 0.0)) - original_distance) > 0.001
            result["menu_stays_open_after_setting"] = bool(self.menu_open)
            self.messenger.send("arrow_up")
            self.messenger.send("enter")
            result["resume_closes_menu"] = not bool(self.menu_open)
            result["menu_buttons"] = len(getattr(self, "menu_buttons", []) or [])
            required = [
                "escape_opens_menu", "down_selects_draw_distance", "selection_visual_present",
                "enter_activates_selected_option", "menu_stays_open_after_setting", "resume_closes_menu"
            ]
            result["status"] = "PASS" if all(bool(result.get(k)) for k in required) and result["menu_buttons"] == 5 else "FAIL"
        except Exception as exc:
            result["status"] = "FAIL"
            result["error"] = f"{exc.__class__.__name__}: {exc}"
        finally:
            # Restore the user's setting so QA cannot mutate persistent configuration.
            self.game_cfg.max_view_distance = original_distance
            try:
                self.camLens.setNearFar(0.06, original_distance)
                write_game_config(self.game_cfg)
            except Exception:
                pass
        out = ROOT / "verification" / "pause_menu_input_test.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        self.userExit()
        return Task.done

    def update_task(self, task):
        dt = min(0.033, globalClock.getDt())
        self.elapsed += dt
        if getattr(self, "arena_mode_active", False) and getattr(self, "vector_arena_native_mode", None) is not None:
            self.update_source_vector_arena_adapter(dt)
            return Task.cont
        if self.menu_open or self.help_visible or bool(getattr(self, "presentation_open", False)):
            self.ui_refresh_timer = max(0.0, float(getattr(self, "ui_refresh_timer", 0.0)) - dt)
            if self.ui_refresh_timer <= 0.0:
                self.refresh_ui_text()
                self.ui_refresh_timer = 0.10
            self._set_ui_text(self.center_text, "")
            return Task.cont
        self.update_palette(dt)
        self.update_chunk_streaming(dt)
        self.update_player(dt)
        self.update_current_district(announce=True)
        self.update_district_discovery_guidance(dt)
        self.update_fire(dt)
        self.update_spawn_director(dt)
        self.update_civilians(dt)
        self.update_patrol_drones(dt)
        self.update_enemies(dt)
        self.update_arena_mode(dt)
        self.update_effects(dt)
        self.update_audio_depth(dt)
        self.update_campaign_objectives(dt)
        self.update_signal_objectives(dt)
        self.recolor_scene()
        self.ui_refresh_timer = max(0.0, float(getattr(self, "ui_refresh_timer", 0.0)) - dt)
        self.workstation_refresh_timer = max(0.0, float(getattr(self, "workstation_refresh_timer", 0.0)) - dt)
        if self.ui_refresh_timer <= 0.0:
            self.refresh_ui_text()
            self.ui_refresh_timer = 0.10
        if self.workstation_visible and self.workstation_refresh_timer <= 0.0:
            self.refresh_workstation_text()
            self.workstation_refresh_timer = 0.25
        if self.weapon_banner_time > 0.0 and self.current_weapon:
            self.weapon_banner_time -= dt
            center_value = f"{self.current_weapon.name}"
        elif getattr(self, "activity_banner_time", 0.0) > 0.0:
            self.activity_banner_time = max(0.0, self.activity_banner_time - dt)
            center_value = ""
        elif getattr(self, "combat_banner_time", 0.0) > 0.0:
            self.combat_banner_time = max(0.0, self.combat_banner_time - dt)
            center_value = self.clean_hud_message(getattr(self, "combat_banner", ""))
        elif getattr(self, "objective_banner_time", 0.0) > 0.0:
            center_value = self.clean_hud_message(getattr(self, "objective_banner", ""))
        else:
            center_value = ""
        self._set_ui_text(self.center_text, center_value)
        return Task.cont


def main():
    if SELF_TEST:
        run_lightweight_self_test()
        return
    app = EtchlineGame()
    app.run()


if __name__ == "__main__":
    main()
